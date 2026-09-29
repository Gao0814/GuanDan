from __future__ import annotations

import json
import random
import re
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.card_tracker import (
    _candidate_comparison_line,
    _candidate_pairs,
    _public_pass_evidence,
    _validated_public_state,
    build_card_tracking_summary,
    exact_public_hand_assignment,
)
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from agents.rule_based_ai import RuleBasedAIAgent
from engine.cards import build_double_deck
from engine.game import GuanDanGame
from engine.public_endgame import PublicEndgameAnalysis, analyze_public_endgame
from engine.rules import BaseRuleEngine
from integrations.botzone.agent_runtime import build_agent_factory


def _rollout_to_step(seed: int, target_step: int) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]]]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    game.reset()
    while game.observe()["current_round"]["step_no"] < target_step:
        observation = game.observe()
        actions = game.legal_actions()
        player_id = int(observation["my_info"]["player_id"])
        game.step(RuleBasedAIAgent(player_id).select_action(observation, actions))
        if game._state.is_finished:  # noqa: SLF001 - deterministic test rollout
            raise AssertionError("seeded game ended before requested observation")
    return game, game.observe(), game.legal_actions()


def _clone_game(game: GuanDanGame) -> GuanDanGame:
    clone = GuanDanGame(current_level_rank=game._current_level_rank)  # noqa: SLF001
    clone._state = game._require_state()  # noqa: SLF001 - test-only perfect-information oracle
    clone._invalidate_legal_actions_cache()  # noqa: SLF001
    return clone


def _reference_team_value(
    game: GuanDanGame,
    root_team: str,
    trace: Counter[str],
) -> int:
    state = game._require_state()  # noqa: SLF001 - test-only perfect-information oracle
    if state.is_finished:
        if state.winner == "draw":
            return 0
        return 1 if state.winner == root_team else -1
    player_team = "team_13" if state.current_player_id in {1, 3} else "team_24"
    maximize = player_team == root_team
    values = []
    for action in game.legal_actions():
        child = _clone_game(game)
        result = child.step(int(action["action_id"]))
        if action["declared_pattern"] == "pass":
            trace["pass"] += 1
        if result["round_ended"]:
            trace["round_reset"] += 1
        if result["game_over"]:
            trace["terminal"] += 1
        values.append(_reference_team_value(child, root_team, trace))
    if not values:
        raise AssertionError("engine returned no legal actions in nonterminal reference state")
    return max(values) if maximize else min(values)


def _reference_root_values(
    game: GuanDanGame,
) -> tuple[tuple[tuple[int, int], ...], Counter[str]]:
    current_id = game._require_state().current_player_id  # noqa: SLF001
    root_team = "team_13" if current_id in {1, 3} else "team_24"
    trace: Counter[str] = Counter()
    values = []
    for action in game.legal_actions():
        child = _clone_game(game)
        result = child.step(int(action["action_id"]))
        if action["declared_pattern"] == "pass":
            trace["pass"] += 1
        if result["round_ended"]:
            trace["round_reset"] += 1
        if result["game_over"]:
            trace["terminal"] += 1
        values.append((
            int(action["action_id"]),
            _reference_team_value(child, root_team, trace),
        ))
    return tuple(values), trace


def _shuffled_hands(seed: int) -> dict[int, tuple[object, ...]]:
    deck = build_double_deck()
    random.Random(seed).shuffle(deck)
    return {
        player_id: tuple(deck[(player_id - 1) * 27:player_id * 27])
        for player_id in range(1, 5)
    }


def _select_action(
    actions: list[dict[str, object]],
    predicate,
) -> dict[str, object]:
    return next(action for action in actions if predicate(action))


class M5PublicPassEvidenceTests(unittest.TestCase):
    def _pass_observation(self) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]], dict[int, bool]]:
        game = GuanDanGame(
            preset_hands=_shuffled_hands(694),
            current_level_rank="2",
            starting_player_id=1,
        )
        game.reset()
        lead = _select_action(
            game.legal_actions(),
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["SJ"],
        )
        game.step(int(lead["action_id"]))

        actual_had_response: dict[int, bool] = {}
        player_two_actions = game.legal_actions()
        self.assertTrue(any(
            action["declared_pattern"] == "single"
            and action["carrier_cards"] == ["BJ"]
            for action in player_two_actions
        ))
        actual_had_response[2] = any(
            action["declared_pattern"] != "pass" for action in player_two_actions
        )
        game.step(int(_select_action(player_two_actions, lambda item: item["declared_pattern"] == "pass")["action_id"]))

        player_three_actions = game.legal_actions()
        self.assertEqual(
            [action["declared_pattern"] for action in player_three_actions],
            ["pass"],
        )
        actual_had_response[3] = any(
            action["declared_pattern"] != "pass" for action in player_three_actions
        )
        game.step(int(player_three_actions[0]["action_id"]))

        player_four_actions = game.legal_actions()
        game.step(int(_select_action(player_four_actions, lambda item: item["declared_pattern"] == "pass")["action_id"]))
        observation = game.observe()
        return game, observation, game.legal_actions(), actual_had_response

    def test_pass_is_soft_candidate_specific_and_later_public_play_confirms_only_what_it_proves(self) -> None:
        game, observation, actions, actual_had_response = self._pass_observation()
        self.assertEqual(observation["my_info"]["player_id"], 1)
        state = _validated_public_state(observation)
        self.assertIsNotNone(state)
        assert state is not None
        original_constraints = state.constraints.to_dict()
        evidence = _public_pass_evidence(observation, state, BaseRuleEngine())
        pass_by_player = {item.player_id: item for item in evidence}
        self.assertIsNone(pass_by_player[2].response_confirmed_step_no)
        self.assertIsNone(pass_by_player[3].response_confirmed_step_no)
        self.assertTrue(actual_had_response[2])
        self.assertFalse(actual_had_response[3])

        low_single = _select_action(
            actions,
            lambda item: item["declared_pattern"] == "single"
            and item["declared_cards"][0] not in {"SJ", "BJ"},
        )
        high_single = _select_action(
            actions,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["BJ"],
        )
        profiles: dict[int, tuple[dict[str, object], ...]] = {}
        facts = {}
        pairs = _candidate_pairs(
            [low_single, high_single],
            Counter(observation["my_info"]["hand_cards"]),
            state=state,
            engine=BaseRuleEngine(),
            owner=None,
            profile_cache=profiles,
            facts_cache=facts,
            pass_evidence=evidence,
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(
            {int(pairs[0][0]["action_id"]), int(pairs[0][1]["action_id"])},
            {int(low_single["action_id"]), int(high_single["action_id"])},
        )
        low_profile = next(item for item in profiles[int(low_single["action_id"])] if item["relation"] == "敌")
        high_profile = next(item for item in profiles[int(high_single["action_id"])] if item["relation"] == "敌")
        self.assertEqual(low_profile["pass_signature"], ())
        self.assertEqual(high_profile["pass_signature"], (("single", "ambiguous"),))
        line = _candidate_comparison_line(
            low_single,
            high_single,
            profiles,
            facts,
            recommendation_anchored=False,
        )
        self.assertIn("历史软pass", line)
        self.assertIn("当时无应手或策略让牌无法区分", line)

        summary = build_card_tracking_summary(observation, actions)
        after_summary_state = _validated_public_state(observation)
        self.assertIsNotNone(after_summary_state)
        assert after_summary_state is not None
        self.assertEqual(after_summary_state.constraints.to_dict(), original_constraints)
        self.assertIn("历史软pass", summary)
        self.assertIn("pass不证明无牌", summary)

        # P1 leads a smaller single; P2's later public BJ play proves it held a
        # beating carrier at the earlier pass. The old event changes to a
        # confirmed historical fact, while P3's no-response pass stays ambiguous.
        game.step(int(low_single["action_id"]))
        p2_actions = game.legal_actions()
        later_bj = _select_action(
            p2_actions,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["BJ"],
        )
        game.step(int(later_bj["action_id"]))
        later_observation = game.observe()
        later_state = _validated_public_state(later_observation)
        self.assertIsNotNone(later_state)
        assert later_state is not None
        later_events = {
            item.player_id: item
            for item in _public_pass_evidence(later_observation, later_state, BaseRuleEngine())
        }
        self.assertEqual(later_events[2].response_confirmed_step_no, 6)
        self.assertIsNone(later_events[3].response_confirmed_step_no)
        self.assertFalse(actual_had_response[3])

        incomplete = deepcopy(later_observation)
        incomplete["history"]["actions"].pop(0)
        self.assertEqual(
            _public_pass_evidence(
                incomplete,
                later_state,
                BaseRuleEngine(),
            ),
            (),
        )

    def test_multi_seed_pass_signal_has_no_false_confirmations_and_keeps_both_ambiguous_outcomes(self) -> None:
        actual_had_response: dict[tuple[int, int], bool] = {}
        latest_inference: dict[tuple[int, int], bool] = {}
        for seed in (0, 2, 4, 6, 8):
            rng = random.Random(seed * 17 + 4)
            game = GuanDanGame(seed=seed, current_level_rank="2")
            game.reset()
            for _ in range(1_500):
                observation = game.observe()
                actions = game.legal_actions()
                player_id = int(observation["my_info"]["player_id"])
                step_no = int(observation["current_round"]["step_no"]) + 1
                plays = [action for action in actions if action["declared_pattern"] != "pass"]
                pass_action = next(
                    (action for action in actions if action["declared_pattern"] == "pass"),
                    None,
                )
                if (
                    pass_action is not None
                    and observation["current_round"]["table_action"] is not None
                    and rng.random() < 0.35
                ):
                    chosen = pass_action
                    actual_had_response[(seed, step_no)] = bool(plays)
                elif plays:
                    ordered = sorted(
                        plays,
                        key=lambda action: (-len(action["carrier_cards"]), action["action_id"]),
                    )
                    chosen = rng.choice(ordered[:min(8, len(ordered))])
                elif pass_action is not None:
                    chosen = pass_action
                    actual_had_response[(seed, step_no)] = False
                else:
                    self.fail("engine returned no legal action")
                game.step(int(chosen["action_id"]))
                if game._state.is_finished:  # noqa: SLF001 - test rollout boundary
                    break
                current = game.observe()
                state = _validated_public_state(current)
                if state is None:
                    continue
                for event in _public_pass_evidence(current, state, BaseRuleEngine()):
                    key = (seed, event.step_no)
                    latest_inference[key] = event.response_confirmed_step_no is not None

        self.assertGreater(len(latest_inference), 100)
        confirmed = [key for key, value in latest_inference.items() if value]
        ambiguous = [key for key, value in latest_inference.items() if not value]
        self.assertTrue(confirmed)
        self.assertTrue(ambiguous)
        self.assertTrue(all(actual_had_response[key] for key in confirmed))
        self.assertTrue(any(actual_had_response[key] for key in ambiguous))
        self.assertTrue(any(not actual_had_response[key] for key in ambiguous))


class M5PublicEndgameTests(unittest.TestCase):
    def test_bounded_search_matches_full_engine_minimax_and_fails_closed(self) -> None:
        game, observation, actions = _rollout_to_step(10, 86)
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertEqual(sum(map(len, assignment.values())), 4)
        expected, trace = _reference_root_values(game)
        analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "solved")
        self.assertEqual(analysis.action_values, expected)
        self.assertGreater(analysis.nodes, 1)
        self.assertTrue(trace["terminal"])

        limited = analyze_public_endgame(
            observation,
            actions,
            assignment,
            max_nodes=1,
        )
        self.assertEqual(limited.status, "budget_exceeded")
        self.assertEqual(limited.action_values, ())

        truncated = deepcopy(observation)
        truncated["history"]["actions"].pop()
        truncated_assignment = exact_public_hand_assignment(truncated)
        self.assertIsNone(truncated_assignment)
        self.assertEqual(
            analyze_public_endgame(truncated, actions, truncated_assignment).status,
            "ineligible",
        )
        self.assertEqual(
            analyze_public_endgame(observation, actions, {}).status,
            "ineligible",
        )

    def test_partner_pass_resets_to_active_leader_and_search_matches_engine(self) -> None:
        game, observation, actions = _rollout_to_step(12, 87)
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertEqual(observation["history"]["finish_order"], [2, 4])
        self.assertEqual(observation["my_info"]["team"], "team_13")
        partner = next(
            player for player in observation["other_players"]
            if not player["finished"]
        )
        self.assertEqual(partner["team"], "team_13")
        lead = observation["current_round"]["table_action"]
        self.assertIsNotNone(lead)
        lead_entry = next(
            item for item in reversed(observation["history"]["actions"])
            if item["round_no"] == observation["current_round"]["round_no"]
            and item["declared_pattern"] != "pass"
        )
        self.assertEqual(lead_entry["player_id"], partner["player_id"])

        pass_action = _select_action(actions, lambda item: item["declared_pattern"] == "pass")
        pass_branch = _clone_game(game)
        transition = pass_branch.step(int(pass_action["action_id"]))
        self.assertTrue(transition["round_ended"])
        self.assertEqual(transition["current_player"], partner["player_id"])
        self.assertTrue(pass_branch.observe()["current_round"]["table_action"] is None)

        expected, trace = _reference_root_values(game)
        analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "solved")
        self.assertEqual(analysis.action_values, expected)
        self.assertGreater(analysis.nodes, 1)
        self.assertTrue(trace["terminal"])

    def test_default_factory_sends_endgame_relations_and_preserves_model_action(self) -> None:
        _, observation, actions = _rollout_to_step(10, 86)
        captured: list[dict[str, object]] = []

        def fake_transport(request, _timeout):
            payload = json.loads(request.data.decode("utf-8"))
            captured.append(payload)
            section = payload["messages"][1]["content"].split("【候选动作】", 1)[1]
            candidate_section = section.split("【规则库依据】", 1)[0]
            match = re.search(r"action_id=(\d+)", candidate_section)
            assert match is not None
            answer = int(match.group(1))
            event = json.dumps({
                "choices": [{
                    "delta": {
                        "content": json.dumps({"action_id": answer, "reason": "synthetic"})
                    }
                }]
            })
            return f"data: {event}\n\ndata: [DONE]\n\n"

        config = SimpleNamespace(
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://example.invalid",
            deepseek_model="synthetic-model",
            deepseek_timeout=2.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
            card_tracking_enabled=True,
        )
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_transport),
            rag_factory=lambda: None,
        )
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch(
                "engine.public_endgame.analyze_public_endgame",
                return_value=PublicEndgameAnalysis(
                    status="budget_exceeded",
                    reason="search_limit",
                ),
            ),
        ):
            agent = factory(3)
            selected = agent.select_action(observation, actions)

        self.assertEqual(len(captured), 1)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertEqual(agent.last_public_endgame_analysis.status, "budget_exceeded")
        prompt = captured[0]["messages"][1]["content"]
        self.assertIn("【公开确证手牌】", prompt)
        self.assertIn("守恒", prompt)
        self.assertNotIn("M5公开残局对照", prompt)
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        displayed = {
            int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)
        }
        self.assertLessEqual(len(displayed), 80)

    def test_unique_proven_winning_action_is_the_only_endgame_shortcut(self) -> None:
        _, observation, actions = _rollout_to_step(10, 87)
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        assert assignment is not None
        analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "solved")
        self.assertIsNotNone(analysis.unique_best_action_id)
        self.assertEqual(dict(analysis.action_values)[analysis.unique_best_action_id], 1)

        class _NoCallClient:
            calls = 0

            def suggest_action_id(self, **_kwargs):
                self.calls += 1
                raise AssertionError("proven unique win should not call the model")

        config = SimpleNamespace(
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
            card_tracking_enabled=False,
        )
        client = _NoCallClient()
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(
                player_id=int(observation["my_info"]["player_id"]),
                client=client,  # type: ignore[arg-type]
                hand_evaluation_enabled=False,
                opening_formula_enabled=False,
            )
            selected = agent.select_action(observation, actions)
        self.assertEqual(selected, analysis.unique_best_action_id)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
