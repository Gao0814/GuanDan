"""Tests for Step J-C3a deterministic offline rank benchmark."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import re
from types import MappingProxyType
import unittest
from unittest.mock import patch

from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_ranker import CardRankRankingState, PlayerRankCandidate, PlayerRankRanking
from engine.game import GuanDanGame
from evaluation.rank_benchmark import (
    aggregate_rank_reports,
    run_rank_benchmark,
    _ground_truth_hands_from_state,
)
from evaluation.ranking_metrics import RankAblationReport, RankMetricSnapshot, evaluate_rank_ranking


def _snapshot(
    *,
    players: int = 1,
    truth: int = 1,
    covered: int = 1,
    top1_hits: int = 1,
    top1_selected: int = 1,
    top3_hits: int = 1,
    top3_selected: int = 1,
    mrr: float = 1.0,
) -> RankMetricSnapshot:
    def ratio(numerator: int, denominator: int, empty: float) -> float:
        return numerator / denominator if denominator else empty
    return RankMetricSnapshot(
        player_count=players,
        truth_rank_count=truth,
        candidate_covered_count=covered,
        candidate_missed_count=truth - covered,
        candidate_recall=ratio(covered, truth, 1.0),
        top1_hit_count=top1_hits,
        top1_recall=ratio(top1_hits, truth, 1.0),
        top1_selected_count=top1_selected,
        top1_precision=ratio(top1_hits, top1_selected, 1.0 if not truth else 0.0),
        top1_average_selection_size=top1_selected / players if players else 0.0,
        top3_hit_count=top3_hits,
        top3_recall=ratio(top3_hits, truth, 1.0),
        top3_selected_count=top3_selected,
        top3_precision=ratio(top3_hits, top3_selected, 1.0 if not truth else 0.0),
        top3_average_selection_size=top3_selected / players if players else 0.0,
        worst_case_mrr=mrr,
    )


def _report(
    *,
    phase: str = "critical_endgame",
    baseline: RankMetricSnapshot | None = None,
    soft: RankMetricSnapshot | None = None,
    valid: bool = True,
    diagnostics: tuple[str, ...] = (),
) -> RankAblationReport:
    baseline = baseline or _snapshot()
    soft = soft or baseline
    return RankAblationReport(
        phase=phase,
        valid_input=valid,
        baseline=baseline,
        soft=soft,
        candidate_recall_delta=soft.candidate_recall - baseline.candidate_recall,
        top1_recall_delta=soft.top1_recall - baseline.top1_recall,
        top1_precision_delta=soft.top1_precision - baseline.top1_precision,
        top1_average_selection_size_delta=soft.top1_average_selection_size - baseline.top1_average_selection_size,
        top3_recall_delta=soft.top3_recall - baseline.top3_recall,
        top3_precision_delta=soft.top3_precision - baseline.top3_precision,
        top3_average_selection_size_delta=soft.top3_average_selection_size - baseline.top3_average_selection_size,
        worst_case_mrr_delta=soft.worst_case_mrr - baseline.worst_case_mrr,
        diagnostics=diagnostics,
    )


class RankBenchmarkTests(unittest.TestCase):
    def test_invalid_benchmark_parameters_are_rejected(self) -> None:
        invalid_seeds = ((), "7", [True], [7, 7])
        for seeds in invalid_seeds:
            with self.subTest(seeds=seeds):
                with self.assertRaises(ValueError):
                    run_rank_benchmark(seeds)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            run_rank_benchmark([7], current_level_rank="SJ")
        for name in ("max_steps", "max_samples_per_game", "max_external_cards", "max_search_nodes", "max_solutions"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    run_rank_benchmark([7], **{name: 0})
                with self.assertRaises(ValueError):
                    run_rank_benchmark([7], **{name: True})
                with self.assertRaises(ValueError):
                    run_rank_benchmark([7], **{name: "1"})

    def test_aggregate_is_micro_aggregation_and_weights_mrr(self) -> None:
        first = _report(
            baseline=_snapshot(truth=1, covered=1, top1_hits=1, top1_selected=1, mrr=1.0),
            soft=_snapshot(truth=1, covered=1, top1_hits=1, top1_selected=2, mrr=1.0),
        )
        second = _report(
            baseline=_snapshot(truth=3, covered=0, top1_hits=0, top1_selected=3, mrr=0.0),
            soft=_snapshot(truth=3, covered=0, top1_hits=1, top1_selected=4, mrr=1 / 3),
        )
        invalid = _report(valid=False, diagnostics=("truth_pool_mismatch:player=2", "truth_pool_mismatch"))

        bucket = aggregate_rank_reports((first, second, invalid), phase="critical_endgame")

        self.assertEqual(bucket.sample_count, 3)
        self.assertEqual(bucket.valid_sample_count, 2)
        self.assertEqual(bucket.invalid_sample_count, 1)
        self.assertEqual(bucket.baseline.truth_rank_count, 4)
        self.assertEqual(bucket.baseline.top1_recall, 0.25)
        self.assertEqual(bucket.baseline.top1_precision, 0.25)
        self.assertEqual(bucket.baseline.top1_average_selection_size, 2.0)
        self.assertEqual(bucket.soft.worst_case_mrr, 0.5)
        self.assertEqual(bucket.top1_recall_delta, 0.25)
        self.assertEqual(bucket.candidate_recall_delta, 0.0)
        self.assertEqual(bucket.diagnostic_counts["truth_pool_mismatch"], 1)

    def test_empty_bucket_uses_zero_rates_without_fabricating_samples(self) -> None:
        bucket = aggregate_rank_reports((), phase="near_open_endgame")
        self.assertEqual(bucket.sample_count, 0)
        self.assertEqual(bucket.baseline.candidate_recall, 0.0)
        self.assertEqual(bucket.soft.worst_case_mrr, 0.0)

    def test_valid_zero_truth_bucket_uses_j_c2b2_zero_denominators(self) -> None:
        zero_truth = _report(
            baseline=_snapshot(players=0, truth=0, covered=0, top1_hits=0, top1_selected=0, top3_hits=0, top3_selected=0),
            soft=_snapshot(players=0, truth=0, covered=0, top1_hits=0, top1_selected=0, top3_hits=0, top3_selected=0),
        )

        bucket = aggregate_rank_reports((zero_truth,), phase="critical_endgame")

        self.assertEqual(bucket.valid_sample_count, 1)
        self.assertEqual(bucket.baseline.candidate_recall, 1.0)
        self.assertEqual(bucket.baseline.top1_precision, 1.0)
        self.assertEqual(bucket.baseline.worst_case_mrr, 1.0)

    def test_truth_extraction_excludes_observer_finished_and_empty_players(self) -> None:
        game = GuanDanGame(seed=7)
        observation = game.reset()
        observer = observation["my_info"]["player_id"]
        truth = _ground_truth_hands_from_state(game, observer)

        self.assertNotIn(observer, truth)
        self.assertEqual(set(truth), {2, 3, 4})
        self.assertTrue(all(token for hand in truth.values() for token in hand))
        with self.assertRaises(ValueError):
            _ground_truth_hands_from_state(game, 99)

    def test_fixed_seed_benchmark_is_deterministic_and_safe(self) -> None:
        first = run_rank_benchmark([7], max_steps=500, max_samples_per_game=2)
        second = run_rank_benchmark([7], max_steps=500, max_samples_per_game=2)

        self.assertEqual(first, second)
        self.assertIn("near_open_endgame", first.by_phase)
        self.assertIn("critical_endgame", first.by_phase)
        self.assertEqual(first.evaluated_sample_count, first.valid_sample_count + first.invalid_sample_count)
        self.assertEqual(first.overall.sample_count, first.evaluated_sample_count)
        self.assertEqual(first.completed_game_count + first.incomplete_game_count, 1)
        self.assertEqual(
            first.overall.sample_count,
            sum(bucket.sample_count for bucket in first.by_phase.values()),
        )
        serialized = json.dumps(first.to_dict())
        self.assertNotIn("seeds", serialized)
        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("3S", serialized)
        with self.assertRaises(FrozenInstanceError):
            first.completed_game_count = 0  # type: ignore[misc]

    def test_step_limit_and_sample_limit_are_recorded(self) -> None:
        step_limited = run_rank_benchmark([7], max_steps=1, max_samples_per_game=1)
        self.assertEqual(step_limited.incomplete_game_count, 1)
        self.assertEqual(step_limited.diagnostic_counts["max_steps_reached"], 1)

        sample_limited = run_rank_benchmark([7], max_steps=500, max_samples_per_game=1)
        self.assertGreater(sample_limited.sample_limit_skipped_count, 0)
        self.assertEqual(sample_limited.diagnostic_counts["sample_limit_reached"], 1)

    def test_rule_agent_selection_is_checked_against_current_legal_actions(self) -> None:
        from evaluation.rank_benchmark import RuleBasedAIAgent

        original = RuleBasedAIAgent.select_action
        test_case = self

        def checked_select(
            self: RuleBasedAIAgent,
            observation: dict[str, object],
            legal_actions: list[dict[str, object]],
        ) -> int:
            action_id = original(self, observation, legal_actions)
            test_case.assertIn(action_id, {int(action["action_id"]) for action in legal_actions})
            return action_id

        with patch.object(RuleBasedAIAgent, "select_action", checked_select):
            report = run_rank_benchmark([7], max_steps=3, max_samples_per_game=1)
        self.assertEqual(report.incomplete_game_count, 1)

    def test_single_sample_pipeline_uses_public_inputs_before_offline_truth(self) -> None:
        game = GuanDanGame(seed=7)
        observation = game.reset()
        belief = CardBeliefState(
            phase="critical_endgame",
            external_unknown_count=1,
            unseen_cards_by_token=MappingProxyType({"3S": 1}),
            unseen_cards_by_rank=MappingProxyType({"3": 1}),
            players=(
                PlayerPublicBelief(1, "team_13", "self", 1, False, None, (), 0),
                PlayerPublicBelief(2, "team_24", "opponent", 1, False, None, (), 0),
            ),
            diagnostics=(),
            token_pool_exact=True,
        )
        ranking = CardRankRankingState(
            phase="critical_endgame",
            hard_source="j_b1_constraints",
            players=(PlayerRankRanking(2, "opponent", (PlayerRankCandidate("3", "possible", 0, 0, 1, ()),)),),
            diagnostics=(),
        )
        report = evaluate_rank_ranking(belief, ranking, {2: ["3S"]})
        self.assertTrue(report.valid_input)
        self.assertEqual(observation["my_info"]["player_id"], 1)

    def test_no_runtime_module_imports_evaluation(self) -> None:
        from pathlib import Path

        for directory in ("agents", "cli", "rag"):
            for path in Path(directory).rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                self.assertIsNone(
                    re.search(r"^\\s*(?:from|import)\\s+evaluation(?:\\.|\\s|$)", source, re.MULTILINE),
                    str(path),
                )


if __name__ == "__main__":
    unittest.main()
