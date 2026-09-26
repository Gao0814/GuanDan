"""Offline H3-A11 continuation-policy sensitivity contracts."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from agents.rag_advisor import RAGAdvisor
from evaluation import action_quality_sensitivity as sensitivity
from evaluation.action_quality_calibration import (
    CalibrationStatus,
    calibrate_h3_a10_sample_sets,
)
from evaluation.action_quality_proxy import build_replayable_quality_samples
from evaluation.h3_a9_quality_queue import build_h3_a9_quality_samples
from evaluation.h3_model_probe_fixtures import _advisor
from evaluation.strategy_intent_action_quality import RuleRolloutOutcome


def _outcome(label: str = "draw", placement: int = 5) -> RuleRolloutOutcome:
    score = {"loss": 0, "draw": 1, "win": 2}[label]
    return RuleRolloutOutcome(label, score, placement, 100, True, ())


class ActionQualitySensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.advisor: RAGAdvisor = _advisor()
        cls.h3_a8 = build_replayable_quality_samples(advisor=cls.advisor)
        cls.h3_a9 = build_h3_a9_quality_samples(advisor=cls.advisor)
        if not cls.h3_a8.ready or not cls.h3_a9.ready:
            raise AssertionError("frozen_quality_queues_not_ready")
        cls.samples = (*cls.h3_a8.samples, *cls.h3_a9.samples)
        cls.baseline = calibrate_h3_a10_sample_sets(cls.h3_a8, cls.h3_a9)
        cls.report = sensitivity.evaluate_h3_a11_sample_sets(cls.h3_a8, cls.h3_a9)

    def test_frozen_step_zero_state_and_candidate_coverage_are_reported_without_substitution(self) -> None:
        self.assertEqual(self.baseline.status, CalibrationStatus.READY)
        self.assertEqual(self.report.status, sensitivity.SensitivityStatus.READY)
        self.assertEqual(
            tuple(row.sample_name for row in self.report.samples),
            tuple(row.sample_name for row in self.baseline.samples),
        )
        self.assertEqual(
            tuple((row.phase, row.canonical_candidate_count, row.final_candidate_count) for row in self.report.samples),
            tuple((row.phase, row.canonical_candidate_count, row.final_candidate_count) for row in self.baseline.samples),
        )
        self.assertEqual(tuple(row.status for row in self.report.samples), (sensitivity.SensitivityStatus.READY,) * 12)
        self.assertEqual(tuple(row.reference_action_visible for row in self.report.samples), (True,) * 12)
        self.assertEqual(tuple(row.reference_tied_in_both_count for row in self.report.samples), (1,) * 12)
        self.assertEqual(
            tuple(sample.opening_formula_enabled for sample in self.h3_a9.samples),
            (True, False, True, True, True, True),
        )
        expected_completed = tuple(row.final_candidate_count for row in self.report.samples)
        self.assertEqual(tuple(row.baseline_completed_candidate_count for row in self.report.samples), expected_completed)
        self.assertEqual(tuple(row.frozen_completed_candidate_count for row in self.report.samples), expected_completed)
        self.assertEqual(tuple(row.paired_completed_candidate_count for row in self.report.samples), expected_completed)

        for index, (baseline_row, sensitivity_row) in enumerate(zip(self.baseline.samples, self.report.samples)):
            transition_rows = sensitivity_row.transition_counts
            self.assertEqual(sum(transition_rows[0]), baseline_row.better_than_reference)
            self.assertEqual(sum(transition_rows[1]), baseline_row.tie_with_reference)
            self.assertEqual(sum(transition_rows[2]), baseline_row.worse_than_reference)
            self.assertEqual(sum(sum(row) for row in transition_rows), sensitivity_row.final_candidate_count)
            diagonal = sum(transition_rows[index][index] for index in range(3))
            expected_changed = sensitivity_row.final_candidate_count - diagonal
            self.assertEqual(sensitivity_row.label_changed_count, expected_changed)
            self.assertEqual(
                sensitivity_row.strict_preference_reversal_count,
                transition_rows[0][2] + transition_rows[2][0],
            )
            self.assertLessEqual(sensitivity_row.strict_preference_reversal_count, sensitivity_row.label_changed_count)

        report = self.report.to_dict()
        expected_candidates = sum(row.final_candidate_count for row in self.baseline.samples)
        self.assertEqual(report["planned_candidate_count"], expected_candidates)
        expected_completed_candidates = expected_candidates
        self.assertEqual(report["paired_completed_candidate_count"], expected_completed_candidates)
        self.assertEqual(sum(sum(row.values()) for row in report["transition_counts"].values()), expected_completed_candidates)  # type: ignore[union-attr]
        self.assertEqual(report["reference_tied_in_both_count"], 12)
        total_rows = report["transition_counts"]
        self.assertEqual(
            sum(sum(total_rows[label].values()) for label in ("better", "tie", "worse")),  # type: ignore[index,union-attr]
            expected_completed_candidates,
        )

    def test_frozen_continuation_has_measured_decision_differences(self) -> None:
        result = self.report.to_dict()
        difference_branches = result["frozen_difference_candidate_branch_count"]
        difference_states = result["frozen_difference_public_state_count"]
        self.assertIsInstance(difference_branches, int)
        self.assertIsInstance(difference_states, int)
        self.assertGreater(difference_branches, 0)
        self.assertGreater(difference_states, 0)
        self.assertEqual(result["information_value"], "continuation_difference_observed")
        self.assertEqual(self.report.frozen_difference_candidate_branch_count, difference_branches)
        self.assertEqual(self.report.frozen_difference_public_state_count, difference_states)

    def test_independent_real_snapshot_clones_receive_identical_first_action_queues(self) -> None:
        snapshots = tuple(sample.game_snapshot for sample in self.samples)
        baseline_branches: list[object] = []
        frozen_branches: list[object] = []
        baseline_ids: list[int] = []
        frozen_ids: list[int] = []
        original_public = tuple((deepcopy(snapshot.observe()), deepcopy(snapshot.legal_actions())) for snapshot in snapshots)

        def baseline_rollout(branch: object, action_id: object, observer: object, max_steps: object) -> RuleRolloutOutcome:
            self.assertTrue(all(branch is not snapshot for snapshot in snapshots))
            self.assertTrue(any(branch.observe() == sample.observation and branch.legal_actions() == sample.legal_actions for sample in self.samples))  # type: ignore[attr-defined]
            self.assertEqual(observer, 1)
            self.assertEqual(max_steps, 5000)
            baseline_branches.append(branch)
            baseline_ids.append(action_id)  # type: ignore[arg-type]
            return _outcome()

        def frozen_rollout(branch: object, action_id: object, observer: object) -> tuple[RuleRolloutOutcome, tuple[str, ...]]:
            self.assertTrue(all(branch is not snapshot for snapshot in snapshots))
            self.assertTrue(any(branch.observe() == sample.observation and branch.legal_actions() == sample.legal_actions for sample in self.samples))  # type: ignore[attr-defined]
            frozen_branches.append(branch)
            frozen_ids.append(action_id)  # type: ignore[arg-type]
            return _outcome(), ()

        with patch.object(sensitivity, "_rollout", side_effect=baseline_rollout), patch.object(
            sensitivity, "_frozen_rollout", side_effect=frozen_rollout
        ):
            result = sensitivity.evaluate_h3_a11_sample_sets(self.h3_a8, self.h3_a9)
        self.assertEqual(result.status, sensitivity.SensitivityStatus.READY)
        expected_branches = sum(sample.final_candidate_count for sample in self.samples)
        self.assertEqual(len(baseline_branches), expected_branches)
        self.assertEqual(len(frozen_branches), expected_branches)
        all_branches = [*baseline_branches, *frozen_branches]
        self.assertEqual(len({id(branch) for branch in all_branches}), 2 * expected_branches)
        self.assertTrue(all(baseline is not frozen for baseline, frozen in zip(baseline_branches, frozen_branches)))
        self.assertEqual(baseline_ids, frozen_ids)
        self.assertEqual(tuple((snapshot.observe(), snapshot.legal_actions()) for snapshot in snapshots), original_public)

    def test_fail_closed_on_incomplete_branch_and_do_not_continue_later_states(self) -> None:
        incomplete = RuleRolloutOutcome("draw", 1, 5, 5000, False, ("rollout_step_limit_reached",))
        with patch.object(sensitivity, "_rollout", return_value=incomplete) as rollout, patch.object(
            sensitivity, "_frozen_rollout"
        ) as frozen:
            result = sensitivity.evaluate_h3_a11_sample_sets(self.h3_a8, self.h3_a9)
        self.assertEqual(rollout.call_count, 1)
        frozen.assert_not_called()
        self.assertEqual(result.status, sensitivity.SensitivityStatus.INCOMPLETE)
        self.assertEqual(result.samples[0].status, sensitivity.SensitivityStatus.ROLLOUT_INCOMPLETE)
        self.assertEqual(result.samples[0].paired_completed_candidate_count, 0)
        self.assertEqual(result.samples[0].transition_counts, ((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        self.assertTrue(all(row.status is sensitivity.SensitivityStatus.NOT_RUN_AFTER_FAILURE for row in result.samples[1:]))

    def test_comparison_exception_fails_whole_state_closed_after_complete_rollouts(self) -> None:
        with patch.object(sensitivity, "_rollout", return_value=_outcome()) as baseline, patch.object(
            sensitivity, "_frozen_rollout", return_value=(_outcome(), ())
        ) as frozen, patch.object(sensitivity, "_compare_quality", side_effect=RuntimeError("private-detail")):
            result = sensitivity.evaluate_h3_a11_sample_sets(self.h3_a8, self.h3_a9)
        self.assertEqual(baseline.call_count, self.h3_a8.samples[0].final_candidate_count)
        self.assertEqual(frozen.call_count, self.h3_a8.samples[0].final_candidate_count)
        self.assertEqual(result.status, sensitivity.SensitivityStatus.INCOMPLETE)
        self.assertEqual(result.samples[0].status, sensitivity.SensitivityStatus.COMPARISON_INVALID)
        self.assertEqual(result.samples[0].baseline_completed_candidate_count, self.h3_a8.samples[0].final_candidate_count)
        self.assertEqual(result.samples[0].frozen_completed_candidate_count, self.h3_a8.samples[0].final_candidate_count)
        self.assertEqual(result.samples[0].paired_completed_candidate_count, 0)
        self.assertEqual(result.samples[0].transition_counts, ((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        self.assertTrue(all(row.status is sensitivity.SensitivityStatus.NOT_RUN_AFTER_FAILURE for row in result.samples[1:]))

    def test_low_sensitivity_serialization_is_stable_and_contains_no_private_fields(self) -> None:
        serialized = self.report.to_json()
        self.assertEqual(serialized.encode("utf-8"), self.report.to_json().encode("utf-8"))
        decoded = json.loads(serialized)
        self.assertEqual(decoded["sample_count"], 12)
        self.assertEqual(len(decoded["samples"]), 12)
        for forbidden in ("action_id", "hand_cards", "game_snapshot", "source_seed", "prompt", "seed"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
