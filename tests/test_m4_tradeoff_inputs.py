"""Legal-state and request-boundary tests for M4 trade-off inputs."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.action_structure import summarize_candidate_contrasts
from agents.deepseek_client import DeepSeekClient
from engine.cards import Card, build_double_deck, card_to_token
from engine.game import GuanDanGame
from integrations.botzone.agent_runtime import build_agent_factory
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever
from agents.rag_advisor import RAGAdvisor


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(token)
    return Card(token[:-1], token[-1])


def _take(deck: list[Card], tokens: list[str]) -> list[Card]:
    result: list[Card] = []
    for token in tokens:
        card = _card(token)
        deck.remove(card)
        result.append(card)
    return result


def _deal(
    *,
    own_tokens: list[str],
    own_excluded_ranks: set[str],
    player_two_tokens: list[str] | None = None,
    player_two_excluded_ranks: set[str] | None = None,
    player_three_tokens: list[str] | None = None,
    player_three_excluded_ranks: set[str] | None = None,
) -> dict[int, tuple[Card, ...]]:
    """Build a complete 108-card deal with focused but unaltered legal hands."""
    deck = list(build_double_deck())
    hands = {1: _take(deck, own_tokens), 2: [], 3: [], 4: []}
    if player_two_tokens:
        hands[2] = _take(deck, player_two_tokens)
    if player_three_tokens:
        hands[3] = _take(deck, player_three_tokens)

    def fill(player_id: int, excluded_ranks: set[str] | None = None) -> None:
        excluded = excluded_ranks or set()
        while len(hands[player_id]) < 27:
            card = next((item for item in deck if item.rank not in excluded), None)
            if card is None:
                raise AssertionError("could not complete focused hand")
            deck.remove(card)
            hands[player_id].append(card)

    fill(1, own_excluded_ranks)
    fill(2, player_two_excluded_ranks)
    fill(3, player_three_excluded_ranks)
    hands[4] = list(deck)
    assert all(len(hand) == 27 for hand in hands.values())
    dealt = Counter(card_to_token(card) for hand in hands.values() for card in hand)
    full_deck = Counter(card_to_token(card) for card in build_double_deck())
    assert dealt == full_deck
    return {player_id: tuple(cards) for player_id, cards in hands.items()}


def _action(game: GuanDanGame, predicate) -> dict[str, object]:
    return next(item for item in game.legal_actions() if predicate(item))


def _step_pass(game: GuanDanGame) -> None:
    game.step(int(_action(game, lambda item: item["declared_pattern"] == "pass")["action_id"]))


def _warm_free_leader(
    game: GuanDanGame,
    *,
    leader_id: int,
    target_rank: str,
    rounds: int,
    protected_tokens: set[str] | None = None,
) -> None:
    protected = protected_tokens or set()
    for _ in range(rounds):
        observation = game.observe()
        assert observation["my_info"]["player_id"] == leader_id
        lead = _action(
            game,
            lambda item: item["declared_pattern"] == "single"
            and item["wildcard_count"] == 0
            and item["carrier_cards"][0] not in protected
            and item["carrier_cards"][0][:-1] != target_rank,
        )
        game.step(int(lead["action_id"]))
        for _ in range(3):
            _step_pass(game)


def _free_bomb_split_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["3S", "3S", "3H", "3C", "3D", "QS", "QH"],
            own_excluded_ranks={"2", "3", "Q", "K", "A"},
        ),
    )
    game.reset()
    _warm_free_leader(game, leader_id=1, target_rank="3", rounds=3)
    return game


def _wildcard_bomb_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["7S", "7H", "7C", "7D", "2H"],
            own_excluded_ranks={"2", "7"},
        ),
    )
    game.reset()
    _warm_free_leader(
        game, leader_id=1, target_rank="7", rounds=3, protected_tokens={"2H"},
    )
    return game


def _follow_game(*, teammate_leads: bool, urgent_opponent: bool = False) -> GuanDanGame:
    own_tokens = ["10S", "2H"] if teammate_leads else ["8S", "2H"]
    own_excluded = {"2", "8", "10"} if teammate_leads else {"2", "5", "8"}
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks=own_excluded,
        player_two_tokens=["5S"],
        player_two_excluded_ranks={"5"},
        player_three_tokens=["4S"] if teammate_leads else [],
        player_three_excluded_ranks={"4"} if teammate_leads else None,
    )
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=hands,
        starting_player_id=3 if teammate_leads else 2,
    )
    game.reset()
    leader_id = 3 if teammate_leads else 2
    if urgent_opponent:
        # Reach a public two-card opposing leader through 24 real single-card
        # plays and complete pass cycles.  The 5S lead remains in hand.
        for _ in range(24):
            lead = _action(
                game,
                lambda item: item["declared_pattern"] == "single"
                and item["carrier_cards"] != ["5S"],
            )
            game.step(int(lead["action_id"]))
            for _ in range(3):
                _step_pass(game)
        assert game.observe()["my_info"]["hand_count"] == 3
    else:
        _warm_free_leader(game, leader_id=leader_id, target_rank="4" if teammate_leads else "5", rounds=2)

    lead_token = "4S" if teammate_leads else "5S"
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "single" and item["carrier_cards"] == [lead_token],
    )
    game.step(int(lead["action_id"]))
    passes_to_me = 1 if teammate_leads else 2
    for _ in range(passes_to_me):
        _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["current_round"]["table_action"]["carrier_cards"] == [lead_token]
    if urgent_opponent:
        leader = next(item for item in observation["other_players"] if item["player_id"] == 2)
        assert leader["hand_count"] == 2
    return game


def _urgent_bomb_follow_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["7S", "7H", "7C", "7D", "2H"],
            own_excluded_ranks={"2", "7"},
            player_two_tokens=["6S", "6H", "6C", "6D"],
            player_two_excluded_ranks={"6"},
        ),
        starting_player_id=2,
    )
    game.reset()
    # Retain the four natural sixes while the opponent legally spends 21
    # single cards and reaches a two-card public remainder after the bomb.
    for _ in range(21):
        lead = _action(
            game,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"][0][:-1] != "6",
        )
        game.step(int(lead["action_id"]))
        for _ in range(3):
            _step_pass(game)
    bomb = _action(
        game,
        lambda item: item["declared_pattern"] == "bomb"
        and item["wildcard_count"] == 0
        and len(item["carrier_cards"]) == 4
        and all(card[:-1] == "6" for card in item["carrier_cards"]),
    )
    game.step(int(bomb["action_id"]))
    _step_pass(game)
    _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["other_players"][0]["player_id"] == 2
    assert observation["other_players"][0]["hand_count"] == 2
    return game


class M4TradeoffInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rag_advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )

    def _factory_request(self, game: GuanDanGame, requested_action_id: int) -> tuple[str, list[int], int]:
        observation = game.observe()
        legal_actions = game.legal_actions()
        captured: list[str] = []
        chosen_ids: list[int] = []

        def fake_transport(request, _timeout):
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][1]["content"]
            captured.append(prompt)
            candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
            candidate_ids = [int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)]
            if requested_action_id not in candidate_ids:
                raise AssertionError("fake response ID was not in the model-visible candidates")
            chosen_ids.append(requested_action_id)
            content = json.dumps({"action_id": requested_action_id, "reason": "synthetic test"})
            event = json.dumps({"choices": [{"delta": {"content": content}}]})
            return f"data: {event}\n\ndata: [DONE]\n\n"

        config = SimpleNamespace(
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://example.invalid",
            deepseek_model="synthetic-model",
            deepseek_timeout=2.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=False,
            card_tracking_enabled=True,
            opening_formula_enabled=True,
        )
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_transport),
            rag_factory=lambda: self.rag_advisor,
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = factory(1)
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen_ids, [requested_action_id])
        self.assertEqual(chosen, requested_action_id)
        self.assertEqual(agent.last_decision_source, "model")
        prompt = captured[0]
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        candidate_ids = {int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)}
        self.assertLessEqual(len(candidate_ids), 80)
        self.assertTrue(candidate_ids.issubset({int(action["action_id"]) for action in legal_actions}))
        for first, second in re.findall(r"公开关系对照 action_id=(\d+).*?action_id=(\d+)", prompt):
            self.assertIn(int(first), candidate_ids)
            self.assertIn(int(second), candidate_ids)
        recommendation = re.search(r"优先核验候选 action_id：([^\n]+)", prompt)
        if recommendation:
            self.assertTrue(all(int(value) in candidate_ids for value in re.findall(r"\d+", recommendation.group(1))))
        return prompt, sorted(candidate_ids), len(legal_actions)

    @staticmethod
    def _contrast(game: GuanDanGame, kind: str):
        observation = game.observe()
        contrasts = summarize_candidate_contrasts(observation, game.legal_actions())
        assert contrasts is not None
        return next(item for item in contrasts if item.kind == kind)

    def test_natural_five_bomb_is_compared_to_three_plus_two_and_request_keeps_both_ids(self) -> None:
        game = _free_bomb_split_game()
        observation = game.observe()
        actions = game.legal_actions()
        contrast = self._contrast(game, "triple_bomb_split")
        action_by_id = {int(action["action_id"]): action for action in actions}
        triple, bomb = (action_by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(triple["declared_pattern"], "triple_with_pair")
        self.assertEqual(Counter(card[:-1] for card in triple["carrier_cards"]), Counter({"3": 3, "Q": 2}))
        self.assertEqual(bomb["declared_pattern"], "bomb")
        self.assertEqual(len(bomb["carrier_cards"]), 5)
        self.assertEqual(set(card[:-1] for card in bomb["carrier_cards"]), {"3"})
        prompt, visible, raw_count = self._factory_request(game, contrast.action_ids[0])
        self.assertGreater(raw_count, len(visible))
        self.assertIn(contrast.action_ids[0], visible)
        self.assertIn(contrast.action_ids[1], visible)
        self.assertIn("三带二拆自然炸/对子成本", prompt)
        self.assertIn("Q对子", prompt)
        self.assertIn("炸弹牌型获得高于普通三带二的即时压制层级", prompt)
        self.assertIn("三带二携带对子成本", prompt)
        rag_context = self.rag_advisor.get_rag_context(
            observation=observation,
            legal_actions=actions,
            top_k=1,
        )
        self.assertIn("exp_bomb_wildcard_001", {
            str(item["source_id"]) for item in rag_context["experience_hits"]
        })

    def test_natural_four_seven_and_wildcard_extended_five_bomb_are_compared(self) -> None:
        game = _wildcard_bomb_game()
        actions = game.legal_actions()
        contrast = self._contrast(game, "bomb_wildcard_strength")
        action_by_id = {int(action["action_id"]): action for action in actions}
        natural, extended = (action_by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(natural["declared_pattern"], "bomb")
        self.assertEqual(len(natural["carrier_cards"]), 4)
        self.assertEqual(extended["declared_pattern"], "bomb")
        self.assertEqual(len(extended["carrier_cards"]), 5)
        self.assertEqual(extended["wildcard_count"], 1)
        self.assertEqual(extended["wildcard_info"][0]["carrier_card"], "2H")
        prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
        self.assertTrue(set(contrast.action_ids).issubset(visible))
        self.assertIn("自然炸/通配加长炸对照", prompt)
        self.assertIn("多用一张逢人配", prompt)
        self.assertIn("急需更强压制", prompt)
        self.assertIn("本次出完可以支持花配", prompt)

    def test_teammate_single_compares_pass_ordinary_response_and_order(self) -> None:
        game = _follow_game(teammate_leads=True)
        actions = game.legal_actions()
        contrasts = summarize_candidate_contrasts(game.observe(), actions)
        assert contrasts is not None
        table_choice = next(item for item in contrasts if item.kind == "teammate_table_choice")
        resource_choice = next(item for item in contrasts if item.kind == "teammate_control_resource")
        by_id = {int(action["action_id"]): action for action in actions}
        self.assertEqual(by_id[table_choice.action_ids[0]]["declared_pattern"], "pass")
        self.assertEqual(by_id[table_choice.action_ids[1]]["declared_pattern"], "single")
        self.assertEqual(by_id[table_choice.action_ids[1]]["carrier_cards"], ["10S"])
        self.assertEqual(by_id[resource_choice.action_ids[0]]["declared_pattern"], "pass")
        prompt, visible, _raw_count = self._factory_request(game, table_choice.action_ids[1])
        self.assertTrue(set(table_choice.action_ids).issubset(visible))
        self.assertTrue(set(resource_choice.action_ids).issubset(visible))
        self.assertIn("队友控桌对照", prompt)
        self.assertIn("比较让队友继续与本家接牌", prompt)
        self.assertIn("下一名仍在局玩家为玩家2（对手", prompt)
        self.assertIn("队友协同与让牌", prompt)
        _pass_prompt, pass_visible, _raw_count = self._factory_request(game, table_choice.action_ids[0])
        self.assertTrue(set(table_choice.action_ids).issubset(pass_visible))

    def test_ambiguous_history_or_unknown_team_omits_follow_relationship(self) -> None:
        game = _follow_game(teammate_leads=True)
        observation = game.observe()
        table_action = observation["current_round"]["table_action"]
        history = observation["history"]
        matching = next(
            item for item in history["actions"]
            if item["round_no"] == observation["current_round"]["round_no"]
            and item["declared_pattern"] == table_action["declared_pattern"]
            and item["declared_cards"] == table_action["declared_cards"]
            and item["carrier_cards"] == table_action["carrier_cards"]
        )

        duplicated_observation = dict(observation)
        duplicated_history = dict(history)
        duplicated_history["actions"] = [*history["actions"], dict(matching)]
        duplicated_observation["history"] = duplicated_history
        ambiguous_contrasts = summarize_candidate_contrasts(
            duplicated_observation, game.legal_actions()
        )
        assert ambiguous_contrasts is not None
        self.assertFalse(
            any(item.kind in {"teammate_table_choice", "teammate_control_resource"}
                for item in ambiguous_contrasts)
        )

        unknown_team_observation = dict(observation)
        unknown_team_observation["my_info"] = {**observation["my_info"], "team": None}
        unknown_team_contrasts = summarize_candidate_contrasts(
            unknown_team_observation, game.legal_actions()
        )
        self.assertIsNone(unknown_team_contrasts)

    def test_opponent_single_compares_eight_and_level_control_two_with_urgent_exception(self) -> None:
        for urgent in (False, True):
            with self.subTest(urgent=urgent):
                game = _follow_game(teammate_leads=False, urgent_opponent=urgent)
                contrast = self._contrast(game, "opponent_single_control_cost")
                self.assertEqual(contrast.rank_labels, ("8", "2"))
                prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[0])
                self.assertTrue(set(contrast.action_ids).issubset(visible))
                self.assertIn("自然普通单张8", prompt)
                self.assertIn("控制资源自然单张2", prompt)
                if urgent:
                    self.assertEqual(contrast.table_leader_hand_count, 2)
                    self.assertIn("对手领出后公开余2张", prompt)
                    self.assertIn("可值得花控制牌阻断", prompt)
                    _high_prompt, _high_visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
                else:
                    self.assertGreater(contrast.table_leader_hand_count or 0, 2)
                    self.assertIn("控制牌与牌权争夺", prompt)

    def test_urgent_opponent_bomb_response_can_spend_wildcard_for_a_longer_bomb(self) -> None:
        game = _urgent_bomb_follow_game()
        actions = game.legal_actions()
        contrast = self._contrast(game, "bomb_wildcard_strength")
        by_id = {int(action["action_id"]): action for action in actions}
        natural, extended = (by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(len(natural["carrier_cards"]), 4)
        self.assertEqual(len(extended["carrier_cards"]), 5)
        self.assertEqual(extended["wildcard_count"], 1)
        prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
        self.assertTrue(set(contrast.action_ids).issubset(visible))
        self.assertIn("自然炸/通配加长炸对照", prompt)
        self.assertIn("公开危险对手", prompt)
        self.assertIn("多用一张逢人配", prompt)


if __name__ == "__main__":
    unittest.main()
