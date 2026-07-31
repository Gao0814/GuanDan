"""Tests for deterministic critical-endgame marginal corpus collection."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from agents.base import BaseAgent
from agents.game_phase import CRITICAL_ENDGAME, GamePhaseContext, NEAR_OPEN_ENDGAME
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.benchmark_truth import extract_ground_truth_hands
from evaluation.marginal_corpus import _external_bucket, run_marginal_corpus
from evaluation.rank_benchmark import run_rank_benchmark


class _IllegalAgent(BaseAgent):
    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        return -1


class MarginalCorpusTests(unittest.TestCase):
    def test_fixed_seed_run_is_deterministic_and_critical_only(self) -> None:
        first = run_marginal_corpus([40], max_steps=500, max_samples_per_game=2)
        second = run_marginal_corpus([40], max_steps=500, max_samples_per_game=2)

        self.assertEqual(first, second)
        self.assertEqual(first.completed_game_count + first.incomplete_game_count, 1)
        self.assertEqual(first.evaluated_sample_count, first.valid_sample_count + first.invalid_sample_count)
        self.assertEqual(first.overall.sample_count, first.evaluated_sample_count)
        self.assertTrue(all(bucket.phase == CRITICAL_ENDGAME for bucket in first.by_external_count.values()))
        self.assertEqual(tuple(first.by_external_count), ("external_0_4", "external_5_8", "external_9_12"))

    def test_multiple_game_and_bucket_totals_are_auditable(self) -> None:
        report = run_marginal_corpus([40, 41], max_steps=500, max_samples_per_game=2)

        self.assertEqual(report.requested_game_count, 2)
        self.assertEqual(report.completed_game_count + report.incomplete_game_count, 2)
        self.assertEqual(
            sum(bucket.sample_count for bucket in report.by_external_count.values()),
            report.evaluated_sample_count,
        )
        self.assertEqual(
            sum(bucket.valid_sample_count for bucket in report.by_external_count.values()),
            report.valid_sample_count,
        )
        self.assertEqual(
            sum(bucket.rank_pair_count for bucket in report.by_external_count.values()),
            report.overall.rank_pair_count,
        )

    def test_external_count_bucket_boundaries(self) -> None:
        expected = {
            0: "external_0_4", 4: "external_0_4", 5: "external_5_8",
            8: "external_5_8", 9: "external_9_12", 12: "external_9_12",
        }
        self.assertEqual({value: _external_bucket(value) for value in expected}, expected)
        self.assertIsNone(_external_bucket(13))
        self.assertIsNone(_external_bucket(True))

    def test_near_open_is_not_eligible(self) -> None:
        context = GamePhaseContext(NEAR_OPEN_ENDGAME, 10, (7, 7, 7), 21, 1, 0)
        with patch("evaluation.marginal_corpus.classify_game_phase", return_value=context):
            report = run_marginal_corpus([40], max_steps=1)

        self.assertEqual(report.eligible_sample_count, 0)
        self.assertEqual(report.evaluated_sample_count, 0)

    def test_unexpected_critical_external_count_is_diagnosed_without_scoring(self) -> None:
        context = GamePhaseContext(CRITICAL_ENDGAME, 10, (7, 7, 7), 13, 1, 0)
        with patch("evaluation.marginal_corpus.classify_game_phase", return_value=context):
            report = run_marginal_corpus([40], max_steps=1)

        self.assertEqual(report.eligible_sample_count, 1)
        self.assertEqual(report.evaluated_sample_count, 0)
        self.assertEqual(report.diagnostic_counts["unexpected_external_count"], 1)

    def test_factory_is_called_once_per_seed_and_player(self) -> None:
        calls: list[tuple[int, int]] = []

        def factory(seed: int, player_id: int) -> BaseAgent:
            calls.append((seed, player_id))
            return RuleBasedAIAgent(player_id=player_id)

        run_marginal_corpus([40, 41], max_steps=2, max_samples_per_game=1, agent_factory=factory)

        self.assertEqual(calls, [(40, 1), (40, 2), (40, 3), (40, 4), (41, 1), (41, 2), (41, 3), (41, 4)])

    def test_agent_action_is_checked_against_legal_actions(self) -> None:
        with self.assertRaises(ValueError):
            run_marginal_corpus([40], max_steps=1, agent_factory=lambda _seed, player_id: _IllegalAgent(player_id))

    def test_sample_limit_and_step_limit_are_reported(self) -> None:
        sample_limited = run_marginal_corpus([40], max_steps=500, max_samples_per_game=1)
        self.assertGreater(sample_limited.sample_limit_skipped_count, 0)
        self.assertEqual(sample_limited.diagnostic_counts["sample_limit_reached"], 1)

        step_limited = run_marginal_corpus([40], max_steps=1, max_samples_per_game=1)
        self.assertEqual(step_limited.incomplete_game_count, 1)
        self.assertEqual(step_limited.diagnostic_counts["max_steps_reached"], 1)

    def test_truncated_allocation_becomes_invalid_report_without_pair_metrics(self) -> None:
        report = run_marginal_corpus(
            [40], max_steps=500, max_samples_per_game=1, max_search_nodes=1,
        )

        self.assertEqual(report.evaluated_sample_count, 1)
        self.assertEqual(report.valid_sample_count, 0)
        self.assertEqual(report.invalid_sample_count, 1)
        self.assertEqual(report.overall.rank_pair_count, 0)
        self.assertIn("allocation_not_complete", report.diagnostic_counts)

    def test_invalid_parameters_are_rejected_before_running_games(self) -> None:
        invalid_seeds = ((), "40", [True], [40, 40])
        for seeds in invalid_seeds:
            with self.subTest(seeds=seeds):
                with self.assertRaises(ValueError):
                    run_marginal_corpus(seeds)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            run_marginal_corpus([40], current_level_rank="SJ")
        for name in ("max_steps", "max_samples_per_game", "max_external_cards", "max_search_nodes", "max_solutions"):
            for value in (0, -1, True):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        run_marginal_corpus([40], **{name: value})
        with self.assertRaises(ValueError):
            run_marginal_corpus([40], max_external_cards=13)
        with self.assertRaises(ValueError):
            run_marginal_corpus([40], agent_factory=object())  # type: ignore[arg-type]

    def test_truth_helper_requires_current_observer_and_returns_only_active_external_players(self) -> None:
        game = GuanDanGame(seed=40)
        observation = game.reset()
        observer = observation["my_info"]["player_id"]

        truth = extract_ground_truth_hands(game, observer)

        self.assertNotIn(observer, truth)
        self.assertEqual(set(truth), {2, 3, 4})
        self.assertTrue(all(token for hand in truth.values() for token in hand))
        with self.assertRaises(ValueError):
            extract_ground_truth_hands(game, 99)

    def test_rank_benchmark_default_contract_still_runs_with_shared_truth_helper(self) -> None:
        report = run_rank_benchmark([40], max_steps=500, max_samples_per_game=1)
        self.assertEqual(report.requested_game_count, 1)
        self.assertEqual(report.completed_game_count + report.incomplete_game_count, 1)

    def test_only_benchmark_truth_reads_engine_state_and_reports_are_safe(self) -> None:
        state_readers = []
        for path in Path("evaluation").glob("*.py"):
            if "game._state" in path.read_text(encoding="utf-8"):
                state_readers.append(path.name)
        self.assertEqual(sorted(state_readers), ["benchmark_truth.py"])

        report = run_marginal_corpus([40], max_steps=500, max_samples_per_game=1)
        payload = report.to_dict()
        with self.assertRaises(FrozenInstanceError):
            report.completed_game_count = 0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            report.by_external_count["external_0_4"] = report.overall  # type: ignore[index]
        serialized = json.dumps(payload, allow_nan=False)
        for forbidden in ("seed", "observation", "player_id", "ground_truth", "token", "3S"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
