"""Tests for exact multi-sample J-D1c1 marginal aggregation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import json
from types import MappingProxyType
import unittest

from evaluation.marginal_benchmark import aggregate_marginal_reports
from evaluation.marginal_metrics import MarginalCalibrationBin, MarginalEvaluationReport


def _bins(
    values: dict[int, tuple[int, Fraction, int]] | None = None,
) -> tuple[MarginalCalibrationBin, ...]:
    values = {} if values is None else values
    return tuple(
        MarginalCalibrationBin(
            bin_index=index,
            prediction_count=values.get(index, (0, Fraction(0, 1), 0))[0],
            prediction_sum_numerator=values.get(index, (0, Fraction(0, 1), 0))[1].numerator,
            prediction_sum_denominator=values.get(index, (0, Fraction(0, 1), 0))[1].denominator,
            truth_positive_count=values.get(index, (0, Fraction(0, 1), 0))[2],
        )
        for index in range(10)
    )


def _valid(
    *,
    phase: str = "endgame",
    pairs: int = 2,
    positives: int = 1,
    certainty: int = 1,
    brier: Fraction = Fraction(1, 2),
    copy: Fraction = Fraction(3, 2),
    bins: dict[int, tuple[int, Fraction, int]] | None = None,
) -> MarginalEvaluationReport:
    return MarginalEvaluationReport(
        phase=phase,
        valid_input=True,
        prediction_source="j_d1b_physical_marginals",
        physical_assignment_count=1,
        rank_pair_count=pairs,
        truth_positive_pair_count=positives,
        certainty_error_count=certainty,
        presence_brier_sum_numerator=brier.numerator,
        presence_brier_sum_denominator=brier.denominator,
        copy_squared_error_sum_numerator=copy.numerator,
        copy_squared_error_sum_denominator=copy.denominator,
        calibration_bins=_bins(
            {0: (1, Fraction(0, 1), 0), 5: (1, Fraction(1, 2), 1)}
            if bins is None else bins
        ),
        diagnostics=(),
    )


def _invalid(
    diagnostics: tuple[str, ...] = ("truth_pool_mismatch",),
) -> MarginalEvaluationReport:
    return MarginalEvaluationReport(
        phase="endgame",
        valid_input=False,
        prediction_source="none",
        physical_assignment_count=0,
        rank_pair_count=0,
        truth_positive_pair_count=0,
        certainty_error_count=0,
        presence_brier_sum_numerator=0,
        presence_brier_sum_denominator=1,
        copy_squared_error_sum_numerator=0,
        copy_squared_error_sum_denominator=1,
        calibration_bins=_bins(),
        diagnostics=diagnostics,
    )


class MarginalBenchmarkTests(unittest.TestCase):
    def _two_valid_reports(self) -> tuple[MarginalEvaluationReport, MarginalEvaluationReport]:
        first = _valid()
        second = _valid(
            pairs=4,
            positives=3,
            certainty=1,
            brier=Fraction(5, 3),
            copy=Fraction(7, 3),
            bins={5: (2, Fraction(1, 1), 1), 9: (2, Fraction(2, 1), 2)},
        )
        return first, second

    def test_empty_sequence_returns_zero_bucket_with_ten_bins(self) -> None:
        bucket = aggregate_marginal_reports((), phase="endgame")

        self.assertEqual(bucket.sample_count, 0)
        self.assertEqual(bucket.valid_sample_count, 0)
        self.assertEqual(bucket.invalid_sample_count, 0)
        self.assertEqual(bucket.rank_pair_count, 0)
        self.assertEqual((bucket.presence_brier_mean_numerator, bucket.presence_brier_mean_denominator), (0, 1))
        self.assertEqual((bucket.expected_calibration_error_numerator, bucket.expected_calibration_error_denominator), (0, 1))
        self.assertEqual(len(bucket.calibration_bins), 10)

    def test_single_valid_report_preserves_raw_sufficient_statistics(self) -> None:
        report = _valid()
        bucket = aggregate_marginal_reports((report,), phase="endgame")

        self.assertEqual(bucket.valid_sample_count, 1)
        self.assertEqual((bucket.presence_brier_sum_numerator, bucket.presence_brier_sum_denominator), (1, 2))
        self.assertEqual((bucket.copy_squared_error_sum_numerator, bucket.copy_squared_error_sum_denominator), (3, 2))
        self.assertEqual(bucket.calibration_bins[5].prediction_count, 1)

    def test_fraction_micro_aggregation_uses_pair_denominators_not_sample_means(self) -> None:
        first, second = self._two_valid_reports()
        bucket = aggregate_marginal_reports((first, second), phase="endgame")

        self.assertEqual(bucket.rank_pair_count, 6)
        self.assertEqual(bucket.truth_positive_pair_count, 4)
        self.assertEqual(bucket.certainty_error_count, 2)
        self.assertEqual((bucket.presence_brier_sum_numerator, bucket.presence_brier_sum_denominator), (13, 6))
        self.assertEqual((bucket.presence_brier_mean_numerator, bucket.presence_brier_mean_denominator), (13, 36))
        self.assertEqual((bucket.copy_squared_error_sum_numerator, bucket.copy_squared_error_sum_denominator), (23, 6))
        self.assertEqual((bucket.copy_mse_numerator, bucket.copy_mse_denominator), (23, 36))
        self.assertEqual((bucket.truth_positive_rate_numerator, bucket.truth_positive_rate_denominator), (2, 3))
        self.assertEqual((bucket.certainty_error_rate_numerator, bucket.certainty_error_rate_denominator), (1, 3))

    def test_calibration_aggregate_ece_and_mce_are_exact(self) -> None:
        first, second = self._two_valid_reports()
        bucket = aggregate_marginal_reports((first, second), phase="endgame")
        middle = bucket.calibration_bins[5]

        self.assertEqual(middle.prediction_count, 3)
        self.assertEqual((middle.prediction_sum_numerator, middle.prediction_sum_denominator), (3, 2))
        self.assertEqual((middle.mean_prediction_numerator, middle.mean_prediction_denominator), (1, 2))
        self.assertEqual((middle.observed_rate_numerator, middle.observed_rate_denominator), (2, 3))
        self.assertEqual((middle.absolute_gap_numerator, middle.absolute_gap_denominator), (1, 6))
        self.assertEqual((bucket.expected_calibration_error_numerator, bucket.expected_calibration_error_denominator), (1, 12))
        self.assertEqual((bucket.maximum_calibration_error_numerator, bucket.maximum_calibration_error_denominator), (1, 6))

    def test_empty_bins_keep_zero_over_one_fractions(self) -> None:
        bucket = aggregate_marginal_reports((_valid(),), phase="endgame")
        empty = bucket.calibration_bins[1]

        self.assertEqual(
            (
                empty.prediction_sum_numerator,
                empty.prediction_sum_denominator,
                empty.mean_prediction_numerator,
                empty.mean_prediction_denominator,
                empty.observed_rate_numerator,
                empty.observed_rate_denominator,
                empty.absolute_gap_numerator,
                empty.absolute_gap_denominator,
            ),
            (0, 1, 0, 1, 0, 1, 0, 1),
        )

    def test_invalid_reports_are_counted_without_polluting_metrics(self) -> None:
        valid = _valid()
        invalid = _invalid(("rank_marginal_key_mismatch:2", "rank_marginal_key_mismatch:3", "truth_pool_mismatch"))
        bucket = aggregate_marginal_reports((valid, invalid), phase="endgame")

        self.assertEqual((bucket.sample_count, bucket.valid_sample_count, bucket.invalid_sample_count), (2, 1, 1))
        self.assertEqual(bucket.rank_pair_count, valid.rank_pair_count)
        self.assertEqual(bucket.diagnostic_counts, {"rank_marginal_key_mismatch": 1, "truth_pool_mismatch": 1})

    def test_all_invalid_reports_zero_metrics_and_normalize_diagnostics(self) -> None:
        bucket = aggregate_marginal_reports(
            (_invalid(("truth_pool_mismatch:one",)), _invalid(("truth_pool_mismatch:two", "token_pool_inexact"))),
            phase="endgame",
        )

        self.assertEqual((bucket.valid_sample_count, bucket.invalid_sample_count, bucket.rank_pair_count), (0, 2, 0))
        self.assertEqual(bucket.diagnostic_counts, {"token_pool_inexact": 1, "truth_pool_mismatch": 2})
        self.assertEqual((bucket.copy_mse_numerator, bucket.copy_mse_denominator), (0, 1))

    def test_overall_accepts_mixed_phases_and_nonoverall_rejects_them(self) -> None:
        first, second = self._two_valid_reports()
        critical = replace(second, phase="critical_endgame")

        self.assertEqual(aggregate_marginal_reports((first, critical), phase="overall").sample_count, 2)
        with self.assertRaises(ValueError):
            aggregate_marginal_reports((first, critical), phase="endgame")

    def test_input_order_does_not_change_result(self) -> None:
        first, second = self._two_valid_reports()
        invalid = _invalid(("truth_pool_mismatch",))

        self.assertEqual(
            aggregate_marginal_reports((first, second, invalid), phase="endgame"),
            aggregate_marginal_reports((invalid, second, first), phase="endgame"),
        )

    def test_invalid_input_container_element_and_phase_are_rejected(self) -> None:
        report = _valid()
        for reports, phase in (("reports", "endgame"), (42, "endgame"), ((object(),), "endgame"), ((report,), ""), ((report,), True)):
            with self.subTest(reports=type(reports).__name__, phase=phase):
                with self.assertRaises(ValueError):
                    aggregate_marginal_reports(reports, phase=phase)  # type: ignore[arg-type]

    def test_malformed_valid_report_source_diagnostics_and_count_bounds_are_rejected(self) -> None:
        report = _valid()
        cases = (
            replace(report, prediction_source="none"),
            replace(report, diagnostics=("unexpected",)),
            replace(report, rank_pair_count=True),
            replace(report, truth_positive_pair_count=3),
            replace(report, certainty_error_count=3),
            replace(report, presence_brier_sum_numerator=5),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    aggregate_marginal_reports((changed,), phase="endgame")

    def test_malformed_fraction_bin_and_total_contracts_are_rejected(self) -> None:
        report = _valid()
        changed_bins = list(report.calibration_bins)
        changed_bins[0] = replace(changed_bins[0], prediction_sum_denominator=0)
        duplicate_bins = report.calibration_bins[:1] + (report.calibration_bins[0],) + report.calibration_bins[2:]
        nonzero_empty = list(report.calibration_bins)
        nonzero_empty[1] = replace(nonzero_empty[1], prediction_sum_numerator=1)
        cases = (
            replace(report, presence_brier_sum_denominator=0),
            replace(report, calibration_bins=tuple(changed_bins)),
            replace(report, calibration_bins=duplicate_bins),
            replace(report, calibration_bins=tuple(nonzero_empty)),
            replace(report, rank_pair_count=3),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    aggregate_marginal_reports((changed,), phase="endgame")

    def test_nonzero_invalid_report_is_rejected(self) -> None:
        invalid = _invalid()
        nonempty_bins = list(invalid.calibration_bins)
        nonempty_bins[0] = replace(nonempty_bins[0], prediction_count=1)
        for changed in (
            replace(invalid, rank_pair_count=1),
            replace(invalid, presence_brier_sum_denominator=2),
            replace(invalid, calibration_bins=tuple(nonempty_bins)),
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    aggregate_marginal_reports((changed,), phase="endgame")

    def test_output_is_frozen_json_safe_and_does_not_keep_sample_details(self) -> None:
        bucket = aggregate_marginal_reports((_valid(), _invalid()), phase="endgame")
        payload = bucket.to_dict()

        with self.assertRaises(FrozenInstanceError):
            bucket.phase = "overall"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            bucket.diagnostic_counts["x"] = 1  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            bucket.calibration_bins[0].prediction_count = 1  # type: ignore[misc]
        serialized = json.dumps(payload, allow_nan=False)
        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("player_id", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("seed", serialized)


if __name__ == "__main__":
    unittest.main()
