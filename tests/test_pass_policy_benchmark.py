"""Tests for evaluation-only strategic-pass benchmark policy variants."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
import unittest

from agents.rule_based_ai import RuleBasedAIAgent
from evaluation.pass_policy_benchmark import (
    StrategicPassAIAgent,
    run_pass_policy_benchmark,
)
from evaluation.rank_benchmark import run_rank_benchmark


def _observation(
    *,
    step_no: int = 0,
    round_no: int = 1,
    pattern: str = "single",
    leader_id: int = 1,
    leader_team: str = "team_13",
    current_team: str = "team_24",
    history: object | None = None,
) -> dict[str, object]:
    if history is None:
        history = [
            {
                "step_no": max(0, step_no - 1),
                "round_no": round_no,
                "player_id": leader_id,
                "declared_pattern": pattern,
                "declared_cards": ["3"],
                "carrier_cards": ["3S"],
            }
        ]
    return {
        "my_info": {"player_id": 2, "team": current_team},
        "other_players": [
            {"player_id": 1, "team": leader_team},
            {"player_id": 3, "team": "team_13"},
            {"player_id": 4, "team": "team_24"},
        ],
        "current_round": {
            "step_no": step_no,
            "round_no": round_no,
            "table_action": {"declared_pattern": pattern},
        },
        "history": {"actions": history},
    }


def _legal_actions(*, include_pass: bool = True, include_play: bool = True) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if include_pass:
        actions.append({"action_id": 7, "declared_pattern": "pass", "carrier_cards": []})
    if include_play:
        actions.append({"action_id": 8, "declared_pattern": "single", "carrier_cards": ["4S"]})
    return actions


class StrategicPassAgentTests(unittest.TestCase):
    def test_rates_and_policy_names_validate(self) -> None:
        for rates in ((), (0, 0), (True,), (-1,), (101,), ("25",)):
            with self.subTest(rates=rates):
                with self.assertRaises(ValueError):
                    run_pass_policy_benchmark([7], strategic_pass_rates=rates)  # type: ignore[arg-type]

        report = run_pass_policy_benchmark([7], strategic_pass_rates=(0, 25, 50, 100), max_steps=1)
        self.assertEqual(
            tuple(report.by_policy),
            ("forced_only", "strategic_pass_25", "strategic_pass_50", "strategic_pass_100"),
        )

    def test_enemy_single_with_pass_and_play_is_an_opportunity(self) -> None:
        agent = StrategicPassAIAgent(player_id=2, strategic_pass_rate=100)
        action_id = agent.select_action(_observation(), _legal_actions())

        self.assertEqual(action_id, 7)
        self.assertEqual(agent.strategic_pass_opportunity_count, 1)
        self.assertEqual(agent.strategic_pass_count, 1)

    def test_teammate_non_single_or_invalid_history_are_not_opportunities(self) -> None:
        cases = (
            _observation(leader_team="team_24"),
            _observation(pattern="pair"),
            _observation(history=[]),
            _observation(history=[{"round_no": 2, "player_id": 1, "declared_pattern": "single"}]),
            _observation(history=[
                {"round_no": 1, "player_id": 1, "declared_pattern": "single"},
                {"round_no": 2, "player_id": 1, "declared_pattern": "single"},
            ]),
            _observation(history=[
                {"round_no": 2, "player_id": 1, "declared_pattern": "single"},
                {"round_no": 1, "player_id": 1, "declared_pattern": "single"},
            ]),
        )
        for observation in cases:
            with self.subTest(observation=observation):
                agent = StrategicPassAIAgent(player_id=2, strategic_pass_rate=100)
                self.assertEqual(agent.select_action(observation, _legal_actions()), 8)
                self.assertEqual(agent.strategic_pass_opportunity_count, 0)
                self.assertEqual(agent.strategic_pass_count, 0)

    def test_only_pass_missing_pass_and_malformed_public_data_do_not_count(self) -> None:
        agent = StrategicPassAIAgent(player_id=2, strategic_pass_rate=100)
        self.assertEqual(agent.select_action(_observation(), _legal_actions(include_play=False)), 7)
        self.assertEqual(agent.strategic_pass_count, 0)
        self.assertEqual(agent.select_action(_observation(), _legal_actions(include_pass=False)), 8)
        self.assertEqual(agent.strategic_pass_count, 0)
        malformed = _observation()
        malformed["my_info"] = {"player_id": "2", "team": "team_24"}
        self.assertEqual(agent.select_action(malformed, _legal_actions()), 8)
        self.assertEqual(agent.strategic_pass_opportunity_count, 0)

    def test_rate_zero_is_rule_equivalent_and_forced_pass_is_not_strategic(self) -> None:
        observation = _observation(step_no=7)
        legal_actions = _legal_actions()
        agent = StrategicPassAIAgent(player_id=2, strategic_pass_rate=0)
        expected = RuleBasedAIAgent(player_id=2).select_action(observation, legal_actions)

        self.assertEqual(agent.select_action(observation, legal_actions), expected)
        self.assertEqual(agent.strategic_pass_opportunity_count, 1)
        self.assertEqual(agent.strategic_pass_count, 0)

        forced = StrategicPassAIAgent(player_id=2, strategic_pass_rate=100)
        self.assertEqual(forced.select_action(observation, _legal_actions(include_play=False)), 7)
        self.assertEqual(forced.strategic_pass_opportunity_count, 0)
        self.assertEqual(forced.strategic_pass_count, 0)

    def test_public_gate_is_deterministic_and_only_uses_step_and_player(self) -> None:
        rate_25_a = StrategicPassAIAgent(player_id=2, strategic_pass_rate=25)
        rate_25_b = StrategicPassAIAgent(player_id=2, strategic_pass_rate=25)
        hit_observation = _observation(step_no=7)
        miss_observation = _observation(step_no=0)

        self.assertEqual(rate_25_a.select_action(hit_observation, _legal_actions()), 7)
        self.assertEqual(rate_25_b.select_action(hit_observation, _legal_actions()), 7)
        self.assertEqual(
            StrategicPassAIAgent(player_id=2, strategic_pass_rate=50).select_action(miss_observation, _legal_actions()),
            7,
        )
        self.assertEqual(
            StrategicPassAIAgent(player_id=2, strategic_pass_rate=25).select_action(miss_observation, _legal_actions()),
            8,
        )
        self.assertEqual(StrategicPassAIAgent._gate(7, 2), StrategicPassAIAgent._gate(7, 2))
        source = Path("evaluation/pass_policy_benchmark.py").read_text(encoding="utf-8")
        self.assertNotIn("random", source)
        self.assertNotIn("hash(", source)
        self.assertNotIn("time.", source)


class PassPolicyBenchmarkTests(unittest.TestCase):
    def test_factory_is_once_per_seed_player_and_default_remains_compatible(self) -> None:
        calls: list[tuple[int, int]] = []

        def factory(seed: int, player_id: int) -> RuleBasedAIAgent:
            calls.append((seed, player_id))
            return RuleBasedAIAgent(player_id=player_id)

        default = run_rank_benchmark([7], max_steps=100, max_samples_per_game=1)
        supplied = run_rank_benchmark(
            [7],
            max_steps=100,
            max_samples_per_game=1,
            agent_factory=factory,
        )
        self.assertEqual(default, supplied)
        self.assertEqual(calls, [(7, 1), (7, 2), (7, 3), (7, 4)])

    def test_rate_zero_full_benchmark_matches_default_and_variants_are_isolated(self) -> None:
        default = run_rank_benchmark([7], max_steps=150, max_samples_per_game=2)
        variants = run_pass_policy_benchmark(
            [7],
            strategic_pass_rates=(0, 100),
            max_steps=150,
            max_samples_per_game=2,
        )
        forced_only = variants.by_policy["forced_only"]
        strategic = variants.by_policy["strategic_pass_100"]

        self.assertEqual(forced_only.rank_benchmark, default)
        self.assertEqual(forced_only.strategic_pass_count, 0)
        self.assertLessEqual(strategic.strategic_pass_count, strategic.strategic_pass_opportunity_count)
        self.assertEqual(strategic.strategic_pass_count, strategic.strategic_pass_opportunity_count)
        self.assertEqual(variants.requested_policy_count, 2)

    def test_variant_report_is_deterministic_safe_and_immutable(self) -> None:
        first = run_pass_policy_benchmark([7], strategic_pass_rates=(0, 25), max_steps=80, max_samples_per_game=1)
        second = run_pass_policy_benchmark([7], strategic_pass_rates=(0, 25), max_steps=80, max_samples_per_game=1)
        serialized = json.dumps(first.to_dict(), allow_nan=False)

        self.assertEqual(first, second)
        self.assertNotIn("seed", serialized)
        self.assertNotIn("observation", serialized)
        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("3S", serialized)
        with self.assertRaises(FrozenInstanceError):
            first.requested_policy_count = 0  # type: ignore[misc]

    def test_runtime_modules_do_not_import_evaluation_and_policy_has_no_engine_state_access(self) -> None:
        policy_source = Path("evaluation/pass_policy_benchmark.py").read_text(encoding="utf-8")
        self.assertNotIn("_state", policy_source)
        self.assertNotIn("engine.state", policy_source)
        for directory in ("agents", "cli", "rag"):
            for path in Path(directory).rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                self.assertIsNone(
                    re.search(r"^\\s*(?:from|import)\\s+evaluation(?:\\.|\\s|$)", source, re.MULTILINE),
                    str(path),
                )


if __name__ == "__main__":
    unittest.main()
