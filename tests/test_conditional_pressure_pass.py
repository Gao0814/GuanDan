"""Boundary and determinism tests for the evaluation-only pass candidate."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent as RuntimeConditionalPressurePassAIAgent
from agents.rule_based_ai import FrozenRuleBasedAIAgent, RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.conditional_pressure_pass import (
    ConditionalPressurePassAIAgent,
    benchmark_decision,
    run_conditional_pressure_pass_benchmark,
)


def _action(action_id: int, pattern: str, count: int = 0) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"] * count,
        "carrier_cards": [] if pattern == "pass" else ["9S"] * count,
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": pattern,
    }


def _history_row(action: dict[str, object], *, step_no: int = 7, round_no: int = 2, player_id: int = 1) -> dict[str, object]:
    return {
        "step_no": step_no,
        "round_no": round_no,
        "player_id": player_id,
        "declared_pattern": action["declared_pattern"],
        "declared_cards": action["declared_cards"],
        "carrier_cards": action["carrier_cards"],
    }


def _observation(*, leader: int = 1, my_hand_count: int = 10, opponent_count: int = 8, finished: bool = False) -> dict[str, object]:
    table = _action(99, "triple", 3)
    return {
        "my_info": {"player_id": 2, "team": "team_24", "hand_count": my_hand_count},
        "other_players": [
            {"player_id": 1, "team": "team_13", "hand_count": 0 if finished else opponent_count, "finished": finished},
            {"player_id": 3, "team": "team_13", "hand_count": opponent_count, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": opponent_count, "finished": False},
        ],
        "current_round": {"step_no": 7, "round_no": 2, "current_player_id": 2, "constraint": "triple", "table_action": table},
        "history": {"actions": [_history_row(table, player_id=leader)]},
    }


def _legal(*patterns: tuple[str, int]) -> list[dict[str, object]]:
    return [_action(1, "pass")] + [_action(index + 2, pattern, count) for index, (pattern, count) in enumerate(patterns)]


class ConditionalPressurePassAgentTests(unittest.TestCase):
    def _select(self, observation: dict[str, object], actions: list[dict[str, object]]) -> int:
        return ConditionalPressurePassAIAgent(player_id=2).select_action(observation, actions)

    def test_enemy_leader_special_only_chooses_original_pass(self) -> None:
        for patterns in (
            (("bomb", 4),),
            (("straight_flush", 5),),
            (("joker_bomb", 4),),
            (("bomb", 4), ("straight_flush", 5)),
        ):
            with self.subTest(patterns=patterns):
                self.assertEqual(self._select(_observation(), _legal(*patterns)), 1)

    def test_default_rule_based_agent_uses_shared_pressure_pass_and_frozen_baseline_does_not(self) -> None:
        actions = _legal(("bomb", 4))
        self.assertEqual(FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), actions), 2)
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), actions), 1)
        self.assertEqual(self._select(_observation(), actions), 1)

    def test_normal_play_finish_and_pressure_all_fall_back_exactly(self) -> None:
        cases = (
            (_observation(), _legal(("bomb", 4), ("triple", 3))),
            (_observation(my_hand_count=4), _legal(("bomb", 4))),
            (_observation(opponent_count=2), _legal(("bomb", 4))),
            (_observation(finished=True), _legal(("bomb", 4))),
        )
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)

    def test_non_opportunity_context_and_malformed_public_inputs_fall_back(self) -> None:
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        teammate = _observation(leader=4)
        teammate["history"] = {"actions": [_history_row(_action(99, "triple", 3), player_id=4)]}
        cases.append((teammate, _legal(("bomb", 4))))
        free = _observation(); free["current_round"] = {"step_no": 7, "round_no": 2, "current_player_id": 2, "constraint": "free", "table_action": None}; free["history"] = {"actions": []}
        cases.append((free, _legal(("bomb", 4))))
        mismatch = _observation(); mismatch["my_info"] = {"player_id": 1, "team": "team_13", "hand_count": 10}
        cases.append((mismatch, _legal(("bomb", 4))))
        malformed = _observation(); malformed["history"] = {"actions": [{"bad": "history"}]}
        cases.append((malformed, _legal(("bomb", 4))))
        missing_history_field = _observation(); del missing_history_field["history"]["actions"][0]["carrier_cards"]  # type: ignore[index]
        cases.append((missing_history_field, _legal(("bomb", 4))))
        bad_history_type = _observation(); bad_history_type["history"]["actions"][0]["step_no"] = "7"  # type: ignore[index]
        cases.append((bad_history_type, _legal(("bomb", 4))))
        invalid_history_player = _observation(); invalid_history_player["history"]["actions"][0]["player_id"] = 5  # type: ignore[index]
        cases.append((invalid_history_player, _legal(("bomb", 4))))
        regressing_history = _observation(); regressing_history["history"] = {"actions": [_history_row(_action(98, "single", 1), step_no=6), _history_row(_action(99, "triple", 3), step_no=5)]}
        cases.append((regressing_history, _legal(("bomb", 4))))
        bad_team = _observation(); bad_team["other_players"][0]["team"] = "wrong"  # type: ignore[index]
        cases.append((bad_team, _legal(("bomb", 4))))
        bad_count = _observation(); bad_count["other_players"][0]["hand_count"] = "8"  # type: ignore[index]
        cases.append((bad_count, _legal(("bomb", 4))))
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)
        self.assertEqual(self._select(_observation(), [_action(1, "pass")]), 1)
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), [_action(1, "pass")]), 1)
        no_pass = [_action(2, "bomb", 4)]
        self.assertEqual(self._select(_observation(), no_pass), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass))
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass))
        malformed_action = _legal(("bomb", 4)); malformed_action[0]["action_id"] = True
        self.assertEqual(self._select(_observation(), malformed_action), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action))
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action))

    def test_history_table_semantics_and_complete_action_schemas_fail_closed(self) -> None:
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        mismatch = _observation(); mismatch["history"]["actions"][0]["declared_cards"] = ["8", "8", "8"]  # type: ignore[index]
        cases.append((mismatch, _legal(("bomb", 4))))
        malformed_table = _observation(); del malformed_table["current_round"]["table_action"]["wildcard_info"]  # type: ignore[index]
        cases.append((malformed_table, _legal(("bomb", 4))))
        malformed_legal = _legal(("bomb", 4)); del malformed_legal[1]["display_text"]
        cases.append((_observation(), malformed_legal))
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)

    def test_real_public_observation_accepts_minimal_history_schema_and_chooses_pass(self) -> None:
        game = GuanDanGame(seed=46000, current_level_rank="2")
        game.reset()
        agents = {player: FrozenRuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        for _ in range(100):
            observation = game.observe()
            legal_actions = game.legal_actions()
            current = observation["current_round"]
            player_id = observation["my_info"]["player_id"]
            if current["step_no"] == 8:
                self.assertEqual((current["round_no"], player_id), (2, 1))
                self.assertEqual({action["declared_pattern"] for action in legal_actions}, {"pass", "bomb"})
                history_row = observation["history"]["actions"][-1]
                self.assertEqual(
                    set(history_row),
                    {"step_no", "round_no", "player_id", "declared_pattern", "declared_cards", "carrier_cards"},
                )
                self.assertNotIn("wildcard_count", history_row)
                self.assertNotIn("wildcard_info", history_row)
                self.assertNotIn("display_text", history_row)
                baseline = FrozenRuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)
                default = RuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)
                candidate = ConditionalPressurePassAIAgent(player_id=1).select_action(observation, legal_actions)
                patterns = {action["action_id"]: action["declared_pattern"] for action in legal_actions}
                self.assertEqual(patterns[baseline], "bomb")
                self.assertEqual(patterns[default], "pass")
                self.assertEqual(patterns[candidate], "pass")
                self.assertIn(baseline, patterns)
                self.assertIn(default, patterns)
                self.assertIn(candidate, patterns)
                return
            game.step(agents[player_id].select_action(observation, legal_actions))
        self.fail("seed_46000_public_opportunity_not_reached")

    def test_agents_share_one_public_predicate_and_evaluation_uses_frozen_baseline(self) -> None:
        self.assertIs(ConditionalPressurePassAIAgent, RuntimeConditionalPressurePassAIAgent)
        candidate_source = Path("agents/conditional_pressure_pass_ai.py").read_text(encoding="utf-8")
        rule_source = Path("agents/rule_based_ai.py").read_text(encoding="utf-8")
        policy_source = Path("agents/conditional_pressure_pass_policy.py").read_text(encoding="utf-8")
        for source in (candidate_source, rule_source, policy_source):
            self.assertNotIn("_state", source)
            self.assertNotIn("engine.state", source)
        for source in (candidate_source, policy_source):
            self.assertNotIn("evaluation.", source)
        self.assertIn("from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id", candidate_source)
        self.assertIn("from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id", rule_source)
        self.assertEqual(policy_source.count("def conditional_pressure_pass_id("), 1)
        self.assertIn("class FrozenRuleBasedAIAgent", rule_source)
        evaluation_source = Path("evaluation/conditional_pressure_pass.py").read_text(encoding="utf-8")
        self.assertIn("from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent", evaluation_source)
        self.assertIn("from agents.rule_based_ai import FrozenRuleBasedAIAgent", evaluation_source)
        self.assertNotIn("conditional_pressure_pass_id(", evaluation_source)
        for directory in ("cli", "rag"):
            for path in Path(directory).rglob("*.py"):
                self.assertNotIn("conditional_pressure_pass", path.read_text(encoding="utf-8"), str(path))
        for path in Path("integrations").rglob("*.py"):
            self.assertNotIn("evaluation.conditional_pressure_pass", path.read_text(encoding="utf-8"), str(path))


class ConditionalPressurePassBenchmarkTests(unittest.TestCase):
    def test_report_is_deterministic_aggregate_only_and_has_a_fixed_decision(self) -> None:
        kwargs = {"max_opportunities_per_game": 2, "max_game_steps": 5000, "max_rollout_steps": 5000}
        first = run_conditional_pressure_pass_benchmark((17, 18), **kwargs)
        second = run_conditional_pressure_pass_benchmark((17, 18), **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.canonical_json_bytes(), second.canonical_json_bytes())
        serialized = json.dumps(first.to_dict(), sort_keys=True)
        for forbidden in ("seed", "hand_cards", "observation", "action_id", "player_id", "snapshot"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(benchmark_decision(first), first.to_dict()["decision"])

    def test_real_seed_has_changed_public_opportunity(self) -> None:
        report = run_conditional_pressure_pass_benchmark(
            (46000,), max_opportunities_per_game=4, max_game_steps=5000, max_rollout_steps=5000,
        )
        self.assertGreater(report.opportunity_count, 0)
        self.assertGreater(report.changed_pair_count, 0)

    def test_input_validation_rejects_ambiguous_runs(self) -> None:
        for seeds in ((), (1, 1), (True,), ("1",)):
            with self.subTest(seeds=seeds):
                with self.assertRaises(ValueError):
                    run_conditional_pressure_pass_benchmark(seeds)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
