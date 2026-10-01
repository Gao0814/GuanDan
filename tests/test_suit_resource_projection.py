from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame
from engine.rules import BaseRuleEngine
from integrations.botzone.agent_runtime import build_agent_factory


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(rank=token)
    return Card(rank=token[:-1], suit=token[-1])


def _complete_game(
    required_hand: list[str],
    *,
    avoid_fill_tokens: set[str] | None = None,
    fill_hand_tokens: list[str] | None = None,
    starting_player_id: int = 1,
    lead_token: str | None = None,
) -> GuanDanGame:
    """Create a conserved 108-card deal with a chosen seat-one hand."""
    deck = list(build_double_deck())
    hand: list[Card] = []
    for token in required_hand:
        card = _card(token)
        deck.remove(card)
        hand.append(card)
    avoided = set(avoid_fill_tokens or ())
    if len(hand) > 27:
        raise AssertionError("fixture_hand_too_large")
    if fill_hand_tokens is not None:
        required_counts = Counter(required_hand)
        for token in fill_hand_tokens:
            if len(hand) >= 27:
                break
            if required_counts[token] or token in avoided:
                continue
            card = _card(token)
            deck.remove(card)
            hand.append(card)
    else:
        for card in tuple(deck):
            token = f"{card.rank}{card.suit or ''}"
            if token in avoided or len(hand) >= 27:
                continue
            hand.append(card)
            deck.remove(card)
    if len(hand) != 27:
        raise AssertionError("fixture_hand_incomplete")

    hands: dict[int, tuple[Card, ...]] = {1: tuple(hand)}
    if lead_token is None:
        if starting_player_id != 1:
            raise AssertionError("fixture_lead_card_missing")
        hands.update({
            2: tuple(deck[:27]),
            3: tuple(deck[27:54]),
            4: tuple(deck[54:81]),
        })
    else:
        lead_card = _card(lead_token)
        if lead_card in hand:
            raise AssertionError("fixture_lead_overlaps_target_hand")
        deck.remove(lead_card)
        leader_hand = [lead_card]
        for card in tuple(deck):
            if len(leader_hand) >= 27:
                break
            leader_hand.append(card)
            deck.remove(card)
        if len(leader_hand) != 27 or len(deck) != 54:
            raise AssertionError("fixture_follow_deal_incomplete")
        hands.update({
            2: tuple(deck[:27]),
            3: tuple(deck[27:54]),
            4: tuple(leader_hand),
        })

    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=hands,
        starting_player_id=starting_player_id,
    )
    game.reset()
    if lead_token is not None:
        lead = next(
            action for action in game.legal_actions()
            if action["declared_pattern"] == "single"
            and action["carrier_cards"] == [lead_token]
        )
        game.step(int(lead["action_id"]))
        if game.observe()["my_info"]["player_id"] != 1:
            raise AssertionError("fixture_follow_turn_not_reached")
    return game


def _no_flush_hand() -> list[str]:
    ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
    hand: list[str] = []
    for index, rank in enumerate(ranks):
        suits = ("S", "C") if index % 2 == 0 else ("H", "D")
        hand.extend(f"{rank}{suit}" for suit in suits)
    hand.append("SJ")
    return hand


def _no_flush_fill(required: list[str], avoid: set[str] | None = None) -> list[str]:
    excluded = set(avoid or ())
    excluded.update(required)
    return [token for token in _no_flush_hand() if token not in excluded]


class _CapturingTransport:
    def __init__(self, desired_action_id: int) -> None:
        self.desired_action_id = desired_action_id
        self.prompt = ""
        self.candidate_ids: tuple[int, ...] = ()
        self.candidate_section = ""
        self.body_char_count = 0
        self.body_byte_count = 0

    def __call__(self, request: object, timeout: float) -> str:
        body = getattr(request, "data", None)
        if not isinstance(body, bytes):
            raise OSError("offline_request_body_missing")
        payload = json.loads(body.decode("utf-8"))
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise OSError("offline_request_messages_missing")
        user = next(
            item for item in messages
            if isinstance(item, dict) and item.get("role") == "user"
        )
        self.prompt = str(user["content"])
        self.body_char_count = len(body.decode("utf-8"))
        self.body_byte_count = len(body)
        start = self.prompt.index("【候选动作】")
        end = self.prompt.index("【输出格式】", start)
        self.candidate_section = self.prompt[start:end]
        rows = re.findall(
            r"#(\d+)\s+action_id=(\d+)\s+\|",
            self.candidate_section,
        )
        if not rows or any(left != right for left, right in rows):
            raise OSError("offline_candidate_rows_invalid")
        self.candidate_ids = tuple(int(left) for left, _ in rows)
        if self.desired_action_id not in self.candidate_ids:
            raise AssertionError("requested_raw_action_not_displayed")
        content = json.dumps({"action_id": self.desired_action_id}, separators=(",", ":"))
        event = json.dumps({"choices": [{"delta": {"content": content}}]})
        return f"data: {event}\n\ndata: [DONE]\n"


def _capture_default_factory_request(
    game: GuanDanGame,
    desired_action_id: int,
) -> tuple[int, object, _CapturingTransport]:
    observation = game.observe()
    legal_actions = game.legal_actions()
    transport = _CapturingTransport(desired_action_id)
    config = SimpleNamespace(
        deepseek_api_key="offline-only",
        deepseek_base_url="https://offline.invalid",
        deepseek_model="offline-only",
        deepseek_timeout=1.0,
        deepseek_max_retries=0,
        hand_evaluation_enabled=False,
        opening_formula_enabled=True,
        card_tracking_enabled=True,
    )

    def client_factory(**kwargs: object) -> DeepSeekClient:
        return DeepSeekClient(**kwargs, transport=transport)  # type: ignore[arg-type]

    with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=client_factory,
        )
        agent = factory(int(observation["my_info"]["player_id"]))
        selected = agent.select_action(observation, legal_actions)
    return selected, agent, transport


class SuitResourceProjectionTests(unittest.TestCase):
    def test_teammate_head_double_down_context_reaches_request_without_changing_model_choice(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _rollout_to_step

        game, observation, actions = _rollout_to_step(13, 74)
        original = deepcopy((observation, actions))
        cue = "本家成为下一位出完者可形成双下并立即结束"
        selected, agent, first = _capture_default_factory_request(game, actions[0]["action_id"])
        self.assertIn(cue, first.prompt)
        alternate = next(aid for aid in reversed(first.candidate_ids) if aid != selected)
        chosen, other_agent, second = _capture_default_factory_request(game, alternate)
        self.assertEqual(chosen, alternate)
        self.assertEqual(other_agent.last_decision_source, "model")
        self.assertEqual(agent.last_decision_source, "model")
        self.assertEqual(first.candidate_ids, second.candidate_ids)
        self.assertLessEqual(len(first.candidate_ids), 80)
        self.assertTrue(set(first.candidate_ids).issubset({a["action_id"] for a in actions}))
        self.assertEqual((game.observe(), game.legal_actions()), original)

        # A finished partner who was second cannot produce a double-down now.
        game, _, actions = _rollout_to_step(13, 94)
        _, _, nonhead = _capture_default_factory_request(game, actions[0]["action_id"])
        self.assertNotIn(cue, nonhead.prompt)
        for field, value in (("finish_rank", 2), ("hand_count", False)):
            broken = deepcopy(observation)
            next(p for p in broken["other_players"] if p["player_id"] == 3)[field] = value
            prompt = DeepSeekClient._build_structured_prompt(
                my_info=broken["my_info"], current_round=broken["current_round"],
                other_players=broken["other_players"], history=broken["history"], legal_actions=original[1],
            )
            self.assertNotIn(cue, prompt)

    def _action_id(self, actions: list[dict[str, object]], carrier: str) -> int:
        action = next(
            item for item in actions
            if item["declared_pattern"] == "single"
            and item["wildcard_count"] == 0
            and item["carrier_cards"] == [carrier]
        )
        return int(action["action_id"])

    def test_no_flush_suit_duplicates_compress_in_real_factory_request(self) -> None:
        game = _complete_game(_no_flush_hand())
        observation = game.observe()
        legal_actions = game.legal_actions()
        canonical_before = deepcopy(legal_actions)
        first_id = self._action_id(legal_actions, "3H")
        second_id = self._action_id(legal_actions, "3D")
        projected = DeepSeekClient._project_prompt_actions(observation, legal_actions)
        by_id = {int(action["action_id"]): action for action in projected}

        self.assertEqual(
            DeepSeekClient._action_signature(by_id[first_id]),
            DeepSeekClient._action_signature(by_id[second_id]),
        )
        final = DeepSeekClient.prepare_prompt_actions(
            legal_actions,
            constraint="free",
            step_no=0,
            hand_count=27,
            observation=observation,
            project_prompt_suits=True,
        )
        alias_ids = {first_id, second_id}
        representative_ids = alias_ids & {int(action["action_id"]) for action in final}
        self.assertEqual(len(representative_ids), 1)
        representative_id = next(iter(representative_ids))
        selected, agent, transport = _capture_default_factory_request(game, representative_id)
        self.assertEqual(selected, representative_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn(representative_id, transport.candidate_ids)
        self.assertEqual(len(alias_ids & set(transport.candidate_ids)), 1)
        self.assertIn('carrier_cards=["3"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["3H"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["3D"]', transport.candidate_section)
        self.assertEqual(game.legal_actions(), canonical_before)

    def test_existing_flush_does_not_prevent_equivalent_suit_compression(self) -> None:
        hand = [
            "3H", "3C", "9D", "10D", "JD", "QD", "KD",
            "4S", "6S", "8S", "2S", "5H", "7H", "9H", "JH",
            "3D", "5C", "7C", "9C", "JC", "2C", "4D", "6D", "8D",
            "10C", "QS", "AS",
        ]
        game = _complete_game(
            hand,
            fill_hand_tokens=_no_flush_fill(hand),
        )
        observation = game.observe()
        actions = game.legal_actions()
        first_id = self._action_id(actions, "3H")
        second_id = self._action_id(actions, "3C")
        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        by_id = {int(action["action_id"]): action for action in projected}

        self.assertTrue(BaseRuleEngine().public_straight_flush_resources(
            tuple(_card(token) for token in hand), "2",
        ))
        self.assertEqual(
            DeepSeekClient._action_signature(by_id[first_id]),
            DeepSeekClient._action_signature(by_id[second_id]),
        )
        final = DeepSeekClient.prepare_prompt_actions(
            actions,
            constraint="free",
            step_no=0,
            hand_count=27,
            observation=observation,
            project_prompt_suits=True,
        )
        visible = {int(action["action_id"]) for action in final}
        self.assertEqual(len({first_id, second_id} & visible), 1)
        representative_id = next(iter({first_id, second_id} & visible))
        selected, agent, transport = _capture_default_factory_request(game, representative_id)
        self.assertEqual(selected, representative_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertEqual(len({first_id, second_id} & set(transport.candidate_ids)), 1)
        self.assertIn('carrier_cards=["3"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["3H"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["3C"]', transport.candidate_section)

    def test_natural_flush_carrier_costs_are_kept_and_bound_to_real_ids(self) -> None:
        hand = ["9S", "9H", "10S", "JS", "QS", "KS"]
        game = _complete_game(
            hand,
            avoid_fill_tokens={"9S", "2H", "8S"},
            fill_hand_tokens=_no_flush_fill(hand, {"9S", "2H", "8S"}),
        )
        actions = game.legal_actions()
        projected = DeepSeekClient._project_prompt_actions(game.observe(), actions)
        groups = DeepSeekClient._prompt_suit_resource_groups(projected)
        self.assertTrue(groups)
        group = groups[0]
        by_id = {int(action["action_id"]): action for action in projected}
        self.assertTrue(any(
            isinstance(by_id[action_id], dict)
            and getattr(by_id[action_id], "suit_resource_text", "")
            for action_id in group
        ))
        self.assertNotEqual(
            DeepSeekClient._action_signature(by_id[group[0]]),
            DeepSeekClient._action_signature(by_id[group[1]]),
        )
        selected, agent, transport = _capture_default_factory_request(game, group[0])
        self.assertEqual(selected, group[0])
        self.assertEqual(agent.last_decision_source, "model")
        self.assertTrue(set(group).issubset(transport.candidate_ids))
        self.assertIn("【同花顺/逢人配花色资源对照】", transport.prompt)
        contrast_line = next(
            line for line in transport.prompt.splitlines()
            if line.startswith("同型花色资源对照：")
            and f"action_id={group[0]}[" in line
            and f"action_id={group[1]}[" in line
        )
        self.assertIn("SF", contrast_line)
        self.assertIn("-S", contrast_line)
        self.assertIn('carrier_cards=["10"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["10S"]', transport.candidate_section)
        self.assertNotIn('carrier_cards=["10C"]', transport.candidate_section)

    def test_wildcard_completed_flush_and_natural_red_two_costs_stay_distinct(self) -> None:
        wildcard_hand = ["9D", "9H", "10D", "JD", "QD", "2H"]
        wildcard_game = _complete_game(
            wildcard_hand,
            avoid_fill_tokens={"9D", "2H"},
            fill_hand_tokens=_no_flush_fill(wildcard_hand, {"9D", "2H"}),
        )
        wildcard_actions = wildcard_game.legal_actions()
        resources = BaseRuleEngine().public_straight_flush_resources(
            tuple(_card(token) for token in wildcard_hand), "2",
        )
        self.assertTrue(any(item.wildcard_count == 1 for item in resources))
        projected = DeepSeekClient._project_prompt_actions(wildcard_game.observe(), wildcard_actions)
        groups = DeepSeekClient._prompt_suit_resource_groups(projected)
        by_id = {int(action["action_id"]): action for action in projected}
        wildcard_group = next(
            group for group in groups
            if any(
                by_id[action_id].get("wildcard_count") == 1
                and "2H" in by_id[action_id].get("carrier_cards", [])
                for action_id in group
            )
        )
        selected, agent, transport = _capture_default_factory_request(wildcard_game, wildcard_group[0])
        self.assertEqual(selected, wildcard_group[0])
        self.assertEqual(agent.last_decision_source, "model")
        self.assertTrue(set(wildcard_group).issubset(transport.candidate_ids))
        self.assertIn("2H-1(N0/W1)", transport.prompt)
        self.assertIn("失", transport.prompt)

        natural_wildcard_group = next(
            group for group in groups
            if any(
                by_id[action_id].get("wildcard_count") == 0
                and by_id[action_id].get("carrier_cards") == ["2H"]
                for action_id in group
            )
        )
        red_two_id = next(
            action_id for action_id in natural_wildcard_group
            if by_id[action_id].get("carrier_cards") == ["2H"]
        )
        selected, agent, transport = _capture_default_factory_request(wildcard_game, red_two_id)
        self.assertEqual(selected, red_two_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertTrue(set(natural_wildcard_group).issubset(transport.candidate_ids))
        self.assertIn("2H-1(N1/W0)", transport.prompt)
        self.assertIn('carrier_cards=["2H"]', transport.candidate_section)

        natural_hand = ["2H", "2S", "3C", "4D", "5S", "6H", "7C"]
        natural_game = _complete_game(
            natural_hand,
            avoid_fill_tokens={"2H", "2S"},
            fill_hand_tokens=_no_flush_fill(natural_hand, {"2H", "2S"}),
        )
        natural_actions = natural_game.legal_actions()
        red_heart_id = self._action_id(natural_actions, "2H")
        black_spade_id = self._action_id(natural_actions, "2S")
        red_heart = next(item for item in natural_actions if item["action_id"] == red_heart_id)
        self.assertEqual(red_heart["wildcard_count"], 0)
        selected, agent, transport = _capture_default_factory_request(natural_game, red_heart_id)
        self.assertEqual(selected, red_heart_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertTrue({red_heart_id, black_spade_id}.issubset(transport.candidate_ids))
        self.assertIn('carrier_cards=["2H"]', transport.candidate_section)
        self.assertIn("2H-1(N1/W0)", transport.prompt)

        wildcard_action = next(
            item for item in natural_actions
            if item["declared_pattern"] == "single"
            and item["wildcard_count"] == 1
            and item["carrier_cards"] == ["2H"]
        )
        self.assertIn(int(wildcard_action["action_id"]), transport.candidate_ids)

    def test_follow_and_dense_opening_requests_keep_canonical_pressure_and_pass(self) -> None:
        hand = ["9S", "9H", "10S", "JS", "QS", "KS"]
        follow_game = _complete_game(
            hand,
            avoid_fill_tokens={"9S", "2H", "8S"},
            fill_hand_tokens=_no_flush_fill(hand, {"9S", "2H", "8S"}),
            starting_player_id=4,
            lead_token="5C",
        )
        follow_actions = follow_game.legal_actions()
        response_id = self._action_id(follow_actions, "9S")
        alternate_id = self._action_id(follow_actions, "9H")
        selected, agent, transport = _capture_default_factory_request(follow_game, response_id)
        self.assertEqual(selected, response_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertTrue({response_id, alternate_id}.issubset(transport.candidate_ids))
        self.assertIn("pass", transport.candidate_section)

        pressure_hand = [
            "3S", "3C", "3H", "3D", "5S", "6S", "7S", "8S", "9S",
            "SJ", "SJ", "BJ", "BJ",
        ]
        pressure_game = _complete_game(
            pressure_hand,
            starting_player_id=4,
            lead_token="4C",
        )
        pressure_actions = pressure_game.legal_actions()
        pressure_by_id = {int(action["action_id"]): action for action in pressure_actions}
        pressure_target = next(
            int(action["action_id"])
            for action in pressure_actions
            if action["declared_pattern"] == "single"
        )
        selected, pressure_agent, pressure_transport = _capture_default_factory_request(
            pressure_game,
            pressure_target,
        )
        self.assertEqual(selected, pressure_target)
        self.assertEqual(pressure_agent.last_decision_source, "model")
        self.assertLessEqual(len(pressure_transport.candidate_ids), 80)
        pressure_patterns = {
            pressure_by_id[action_id]["declared_pattern"]
            for action_id in pressure_transport.candidate_ids
        }
        self.assertTrue({"pass", "bomb", "straight_flush", "joker_bomb"}.issubset(pressure_patterns))

        dense_game = GuanDanGame(seed=0, current_level_rank="2")
        dense_game.reset()
        dense_actions = dense_game.legal_actions()
        dense_by_id = {int(action["action_id"]): action for action in dense_actions}
        wanted = next(int(action["action_id"]) for action in dense_actions if action["declared_pattern"] != "pass")
        selected, dense_agent, dense_transport = _capture_default_factory_request(dense_game, wanted)
        self.assertEqual(selected, wanted)
        self.assertEqual(dense_agent.last_decision_source, "model")
        self.assertLessEqual(len(dense_transport.candidate_ids), 80)
        self.assertTrue(set(dense_transport.candidate_ids).issubset(dense_by_id))
        visible_patterns = {dense_by_id[action_id]["declared_pattern"] for action_id in dense_transport.candidate_ids}
        self.assertIn("bomb", visible_patterns)
        self.assertIn("straight_flush", visible_patterns)
        self.assertEqual(len(dense_actions), len(dense_by_id))
        self.assertTrue(dense_actions)

    def test_default_factory_request_preserves_double_wild_bomb_id(self) -> None:
        game = _complete_game(["7S", "7C", "2H", "2H"])
        legal_actions = game.legal_actions()
        double_wild_bomb = next(
            action for action in legal_actions
            if action["declared_pattern"] == "bomb"
            and action["wildcard_count"] == 2
            and len(action["declared_cards"]) == 4
            and set(action["declared_cards"]) == {"7"}
            and action["carrier_cards"].count("2H") == 2
        )
        target_id = int(double_wild_bomb["action_id"])

        selected, agent, transport = _capture_default_factory_request(game, target_id)

        self.assertIn(target_id, transport.candidate_ids)
        self.assertEqual(selected, target_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertLessEqual(len(transport.candidate_ids), 80)

    def test_follow_request_compresses_equivalent_rank_only_suit_aliases(self) -> None:
        game = _complete_game(
            _no_flush_hand(),
            starting_player_id=4,
            lead_token="5C",
        )
        observation = game.observe()
        legal_actions = game.legal_actions()
        projected = DeepSeekClient._project_prompt_actions(observation, legal_actions)
        classes: dict[tuple[object, ...], list[int]] = {}
        for action in projected:
            if action["declared_pattern"] != "single" or action["wildcard_count"] != 0:
                continue
            classes.setdefault(DeepSeekClient._action_signature(action), []).append(
                int(action["action_id"]),
            )
        raw_prompt_actions = DeepSeekClient.prepare_prompt_actions(
            legal_actions,
            constraint="follow",
            step_no=int(observation["current_round"]["step_no"]),
            hand_count=27,
            observation=observation,
        )
        raw_visible_ids = {int(action["action_id"]) for action in raw_prompt_actions}
        alias_ids = next(
            ids for ids in classes.values()
            if len(ids) > 1 and len(set(ids) & raw_visible_ids) > 1
        )

        projected_prompt_actions = DeepSeekClient.prepare_prompt_actions(
            legal_actions,
            constraint="follow",
            step_no=int(observation["current_round"]["step_no"]),
            hand_count=27,
            observation=observation,
            project_prompt_suits=True,
        )
        projected_visible_ids = {
            int(action["action_id"]) for action in projected_prompt_actions
        }
        representative_ids = set(alias_ids) & projected_visible_ids
        self.assertEqual(len(representative_ids), 1)

        representative_id = next(iter(representative_ids))
        selected, agent, transport = _capture_default_factory_request(
            game,
            representative_id,
        )
        self.assertEqual(selected, representative_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertEqual(len(set(alias_ids) & set(transport.candidate_ids)), 1)
        self.assertIn('carrier_cards=["', transport.candidate_section)
        self.assertNotRegex(transport.candidate_section, r'carrier_cards=\["\d+[SHCD]"\]')

    def test_invalid_projection_inputs_fall_back_to_original_candidates(self) -> None:
        game = _complete_game(_no_flush_hand())
        observation = game.observe()
        actions = game.legal_actions()
        self.assertIs(DeepSeekClient._project_prompt_actions({}, actions), actions)
        malformed = deepcopy(observation)
        malformed["my_info"]["hand_cards"][0] = "bad-token"
        self.assertIs(DeepSeekClient._project_prompt_actions(malformed, actions), actions)
        with patch.object(
            BaseRuleEngine,
            "public_straight_flush_resources",
            side_effect=RuntimeError("offline_rule_projection_failure"),
        ):
            self.assertIs(DeepSeekClient._project_prompt_actions(observation, actions), actions)


if __name__ == "__main__":
    unittest.main()
