"""Offline contracts for H3-A10's all-candidate proxy calibration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from agents.base import require_legal_action_id
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from evaluation import action_quality_calibration as calibration
from evaluation.action_quality_calibration import (
    CandidateCalibrationReport,
    CalibrationStatus,
    calibrate_h3_a10_candidate_distribution,
    calibrate_h3_a10_sample_sets,
    calibrate_sample_candidates,
)
from evaluation.action_quality_proxy import SampleSetResult, build_replayable_quality_samples
from evaluation.h3_a9_quality_queue import build_h3_a9_quality_samples
from evaluation.h3_model_probe_fixtures import _advisor
from evaluation.strategy_intent_action_quality import RuleRolloutOutcome


def _outcome(label: str, rank_sum: int) -> RuleRolloutOutcome:
    scores = {"loss": 0, "draw": 1, "win": 2}
    return RuleRolloutOutcome(label, scores[label], rank_sum, 100, True, ())


class ActionQualityCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.advisor: RAGAdvisor = _advisor()
        cls.h3_a8 = build_replayable_quality_samples(advisor=cls.advisor)
        cls.h3_a9 = build_h3_a9_quality_samples(advisor=cls.advisor)
        if not cls.h3_a8.ready or not cls.h3_a9.ready:
            raise AssertionError("frozen_quality_queues_not_ready")
        cls.samples = (*cls.h3_a8.samples, *cls.h3_a9.samples)
        cls.report = calibrate_h3_a10_sample_sets(cls.h3_a8, cls.h3_a9)

    def test_all_twelve_frozen_engine_states_keep_step_zero_and_report_reference_coverage(self) -> None:
        self.assertEqual(self.report.status, CalibrationStatus.CALIBRATION_INCOMPLETE)
        self.assertEqual(
            tuple(row.sample_name for row in self.report.samples),
            (
                "h3_a8:opening_low_cost_single",
                "h3_a8:opening_neutral_soft_pair",
                "h3_a8:midgame_1",
                "h3_a8:midgame_2",
                "h3_a8:endgame_1",
                "h3_a8:endgame_2",
                "h3_a9:opening_1",
                "h3_a9:opening_2",
                "h3_a9:midgame_1",
                "h3_a9:midgame_2",
                "h3_a9:endgame_1",
                "h3_a9:endgame_2",
            ),
        )
        self.assertEqual(
            tuple((row.phase, row.canonical_candidate_count, row.final_candidate_count) for row in self.report.samples),
            (
                ("opening", 211, 24),
                ("opening", 378, 40),
                ("midgame", 22, 6),
                ("midgame", 8, 6),
                ("endgame", 5, 3),
                ("near_open_endgame", 9, 8),
                ("opening", 305, 40),
                ("opening", 573, 52),
                ("midgame", 65, 13),
                ("midgame", 22, 20),
                ("critical_endgame", 8, 7),
                ("critical_endgame", 11, 7),
            ),
        )
        self.assertEqual(tuple(row.status for row in self.report.samples), (CalibrationStatus.READY, CalibrationStatus.REFERENCE_ACTION_NOT_VISIBLE, *(CalibrationStatus.READY,) * 10))
        self.assertEqual(tuple(row.reference_action_visible for row in self.report.samples), (True, False, *(True,) * 10))
        self.assertEqual(tuple(row.completed_candidate_count for row in self.report.samples), tuple(0 if index == 1 else row.final_candidate_count for index, row in enumerate(self.report.samples)))
        self.assertEqual(
            tuple(sample.opening_formula_enabled for sample in self.h3_a9.samples),
            (True, False, True, True, True, True),
        )
        self.assertEqual(
            self.h3_a9.samples[1].to_dict(),
            {
                "name": "opening_2",
                "phase": "opening",
                "canonical_candidate_count": 573,
                "final_candidate_count": 52,
                "opening_formula_enabled": False,
                "candidate_projection": "frozen_h3_pre_budget_representatives",
            },
        )
        report_dict = self.report.to_dict()
        production_rows = tuple(
            row for row in self.report.samples
            if row.candidate_projection == "production_relation_budget"
        )
        counterfactual_rows = tuple(
            row for row in self.report.samples
            if row.candidate_projection == "frozen_h3_pre_budget_representatives"
        )
        self.assertEqual(len(production_rows), 11)
        self.assertEqual(len(counterfactual_rows), 1)
        self.assertEqual(counterfactual_rows[0].sample_name, "h3_a9:opening_2")
        self.assertEqual(
            report_dict["comparison_counts"],
            {
                "better_than_reference": sum(row.better_than_reference for row in production_rows),
                "tie_with_reference": sum(row.tie_with_reference for row in production_rows),
                "worse_than_reference": sum(row.worse_than_reference for row in production_rows),
            },
        )
        summaries = report_dict["candidate_projection_summaries"]
        self.assertEqual(
            summaries["frozen_h3_pre_budget_representatives"]["sample_count"],  # type: ignore[index]
            1,
        )
        report_opening_2 = next(
            row for row in report_dict["samples"]  # type: ignore[union-attr]
            if row["sample_name"] == "h3_a9:opening_2"
        )
        self.assertEqual(
            report_opening_2["candidate_projection"],
            "frozen_h3_pre_budget_representatives",
        )
        planned_candidates = sum(row.final_candidate_count for row in self.report.samples)
        completed_candidates = sum(row.completed_candidate_count for row in self.report.samples)
        self.assertEqual(self.report.to_dict()["final_candidate_count"], planned_candidates)  # type: ignore[index]
        production_completed = sum(row.completed_candidate_count for row in production_rows)
        self.assertEqual(sum(report_dict["comparison_counts"].values()), production_completed)  # type: ignore[union-attr]
        self.assertEqual(
            summaries["frozen_h3_pre_budget_representatives"]["completed_candidate_count"],  # type: ignore[index]
            counterfactual_rows[0].completed_candidate_count,
        )
        self.assertEqual(self.report.completed_sample_count, 11)
        self.assertEqual(self.report.completed_candidate_count, completed_candidates)
        self.assertEqual(completed_candidates, planned_candidates - self.report.samples[1].final_candidate_count)
        self.assertGreaterEqual(sum(row.tie_with_reference for row in self.report.samples), 12)

    def test_public_entrypoint_uses_the_two_frozen_queues(self) -> None:
        expected = CandidateCalibrationReport(CalibrationStatus.READY)
        with patch.object(calibration, "build_replayable_quality_samples", return_value=self.h3_a8), patch.object(
            calibration, "build_h3_a9_quality_samples", return_value=self.h3_a9
        ), patch.object(calibration, "calibrate_h3_a10_sample_sets", return_value=expected) as calibrate_sets:
            result = calibrate_h3_a10_candidate_distribution(advisor=self.advisor)
        self.assertIs(result, expected)
        calibrate_sets.assert_called_once_with(self.h3_a8, self.h3_a9)

    def test_synthetic_comparison_fixture_covers_better_tie_worse_and_independent_clones(self) -> None:
        sample = self.samples[0]
        reference_id = require_legal_action_id(
            RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions),
            sample.legal_actions,
        )
        better_id = next(action_id for action_id in sample.final_candidate_ids if action_id != reference_id)
        worse_id = next(
            action_id
            for action_id in sample.final_candidate_ids
            if action_id not in (reference_id, better_id)
        )
        outcomes = {action_id: _outcome("draw", 5) for action_id in sample.final_candidate_ids}
        outcomes[better_id] = _outcome("win", 3)
        outcomes[worse_id] = _outcome("loss", 7)
        clones: list[object] = []
        called_ids: list[int] = []

        def fake_rollout(branch: object, action_id: object, observer: object, max_steps: object) -> object:
            self.assertIsNot(branch, sample.game_snapshot)
            self.assertEqual(branch.observe(), sample.observation)  # type: ignore[attr-defined]
            self.assertEqual(branch.legal_actions(), sample.legal_actions)  # type: ignore[attr-defined]
            self.assertEqual(observer, 1)
            self.assertEqual(max_steps, 5000)
            clones.append(branch)
            called_ids.append(action_id)  # type: ignore[arg-type]
            return outcomes[action_id]  # type: ignore[index]

        original_public = (deepcopy(sample.game_snapshot.observe()), deepcopy(sample.game_snapshot.legal_actions()))
        with patch.object(calibration, "_rollout", side_effect=fake_rollout):
            result = calibrate_sample_candidates(sample)
        self.assertEqual(result.status, CalibrationStatus.READY)
        self.assertEqual(result.better_than_reference, 1)
        self.assertEqual(result.worse_than_reference, 1)
        self.assertEqual(result.tie_with_reference, sample.final_candidate_count - 2)
        self.assertEqual(result.completed_candidate_count, sample.final_candidate_count)
        self.assertEqual(len(called_ids), sample.final_candidate_count)
        self.assertEqual(len(called_ids), len(set(called_ids)))
        self.assertTrue(set(called_ids) == set(sample.final_candidate_ids))
        self.assertEqual(len({id(branch) for branch in clones}), len(clones))
        self.assertEqual((sample.game_snapshot.observe(), sample.game_snapshot.legal_actions()), original_public)

    def test_missing_illegal_or_unseen_candidates_fail_closed_before_rollout(self) -> None:
        sample = self.samples[0]
        missing = replace(sample, final_candidate_ids=sample.final_candidate_ids[:-1])
        illegal_ids = (*sample.final_candidate_ids[:-1], max(action["action_id"] for action in sample.legal_actions) + 1)
        illegal = replace(sample, final_candidate_ids=illegal_ids)
        reference_id = require_legal_action_id(
            RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions),
            sample.legal_actions,
        )
        replacement_id = next(
            action["action_id"]
            for action in sample.legal_actions
            if action["action_id"] not in sample.final_candidate_ids
        )
        unseen_ids = tuple(action_id for action_id in sample.final_candidate_ids if action_id != reference_id)
        unseen_reference = replace(sample, final_candidate_ids=(*unseen_ids, replacement_id))

        with patch.object(calibration, "_rollout") as rollout:
            missing_result = calibrate_sample_candidates(missing)
            illegal_result = calibrate_sample_candidates(illegal)
            unseen_result = calibrate_sample_candidates(unseen_reference)
        rollout.assert_not_called()
        self.assertEqual(missing_result.status, CalibrationStatus.FINAL_CANDIDATES_INVALID)
        self.assertEqual(illegal_result.status, CalibrationStatus.FINAL_CANDIDATES_INVALID)
        self.assertEqual(unseen_result.status, CalibrationStatus.REFERENCE_ACTION_NOT_VISIBLE)
        self.assertFalse(unseen_result.reference_action_visible)

    def test_duplicate_state_across_frozen_queues_blocks_the_whole_distribution(self) -> None:
        opening_a8 = self.h3_a8.samples[0]
        opening_a9 = self.h3_a9.samples[0]
        duplicate_a9 = replace(
            opening_a9,
            phase=opening_a8.phase,
            canonical_candidate_count=opening_a8.canonical_candidate_count,
            final_candidate_count=opening_a8.final_candidate_count,
            observation=opening_a8.observation,
            legal_actions=opening_a8.legal_actions,
            game_snapshot=opening_a8.game_snapshot,
            final_candidate_ids=opening_a8.final_candidate_ids,
        )
        duplicated_set = SampleSetResult(self.h3_a9.stage, (duplicate_a9, *self.h3_a9.samples[1:]))
        with patch.object(calibration, "_rollout") as rollout:
            report = calibrate_h3_a10_sample_sets(self.h3_a8, duplicated_set)
        rollout.assert_not_called()
        self.assertEqual(report.status, CalibrationStatus.DUPLICATE_SAMPLE)
        self.assertEqual(len(report.samples), 12)
        self.assertEqual(set(row.status for row in report.samples), {CalibrationStatus.DUPLICATE_SAMPLE})
        self.assertEqual(report.completed_candidate_count, 0)

    def test_snapshot_drift_and_unfinished_rollout_fail_closed_without_skipping(self) -> None:
        sample = self.samples[0]
        changed_observation = deepcopy(sample.observation)
        changed_observation["current_round"]["step_no"] += 1  # type: ignore[index,operator]
        drifted = replace(sample, observation=changed_observation)
        with patch.object(calibration, "_rollout") as rollout:
            drifted_result = calibrate_sample_candidates(drifted)
        rollout.assert_not_called()
        self.assertEqual(drifted_result.status, CalibrationStatus.SNAPSHOT_PUBLIC_MISMATCH)

        incomplete = RuleRolloutOutcome("draw", 1, 5, 5000, False, ("rollout_step_limit_reached",))
        with patch.object(calibration, "_rollout", return_value=incomplete) as rollout:
            incomplete_result = calibrate_sample_candidates(sample)
        self.assertEqual(rollout.call_count, 1)
        self.assertEqual(incomplete_result.status, CalibrationStatus.ROLLOUT_INCOMPLETE)
        self.assertEqual(incomplete_result.completed_candidate_count, 0)
        self.assertEqual(incomplete_result.comparison_count, 0)

    def test_comparison_exceptions_fail_closed_and_low_sensitivity_json_is_stable(self) -> None:
        sample = self.samples[0]
        complete = _outcome("draw", 5)
        with patch.object(calibration, "_rollout", return_value=complete):
            with patch.object(calibration, "_compare_quality", side_effect=RuntimeError("private-detail")):
                failed = calibrate_sample_candidates(sample)
        self.assertEqual(failed.status, CalibrationStatus.COMPARISON_INVALID)
        self.assertEqual(failed.completed_candidate_count, sample.final_candidate_count)

        serialized = self.report.to_json()
        self.assertEqual(serialized.encode("utf-8"), self.report.to_json().encode("utf-8"))
        repeated_report = calibrate_h3_a10_sample_sets(self.h3_a8, self.h3_a9)
        self.assertEqual(repeated_report.status, CalibrationStatus.CALIBRATION_INCOMPLETE)
        self.assertEqual(repeated_report.to_json().encode("utf-8"), serialized.encode("utf-8"))
        for forbidden in (
            "action_id",
            "hand_cards",
            "game_snapshot",
            "source_seed",
            "prompt",
            "private-detail",
        ):
            self.assertNotIn(forbidden, serialized)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["sample_count"], 12)
        self.assertEqual(len(parsed["samples"]), 12)


if __name__ == "__main__":
    unittest.main()
