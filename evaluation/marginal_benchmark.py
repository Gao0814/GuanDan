"""Exact micro-aggregation for offline J-D1c1 marginal reports.

This module consumes report objects already held in memory.  It neither
collects games nor accepts truth hands, so its output is safe to use as a
future calibration input without retaining sample-level details.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from evaluation.marginal_metrics import MarginalCalibrationBin, MarginalEvaluationReport


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _fraction(numerator: object, denominator: object, *, name: str) -> Fraction:
    if not _is_non_negative_int(numerator) or not _is_positive_int(denominator):
        raise ValueError(f"invalid {name}")
    return Fraction(numerator, denominator)


@dataclass(frozen=True, slots=True)
class MarginalCalibrationAggregate:
    """Exact, sample-order-independent aggregate for one calibration bin."""

    bin_index: int
    prediction_count: int
    prediction_sum_numerator: int
    prediction_sum_denominator: int
    truth_positive_count: int
    mean_prediction_numerator: int
    mean_prediction_denominator: int
    observed_rate_numerator: int
    observed_rate_denominator: int
    absolute_gap_numerator: int
    absolute_gap_denominator: int

    def to_dict(self) -> dict[str, int]:
        return {
            "bin_index": self.bin_index,
            "prediction_count": self.prediction_count,
            "prediction_sum_numerator": self.prediction_sum_numerator,
            "prediction_sum_denominator": self.prediction_sum_denominator,
            "truth_positive_count": self.truth_positive_count,
            "mean_prediction_numerator": self.mean_prediction_numerator,
            "mean_prediction_denominator": self.mean_prediction_denominator,
            "observed_rate_numerator": self.observed_rate_numerator,
            "observed_rate_denominator": self.observed_rate_denominator,
            "absolute_gap_numerator": self.absolute_gap_numerator,
            "absolute_gap_denominator": self.absolute_gap_denominator,
        }


@dataclass(frozen=True, slots=True)
class MarginalBenchmarkBucket:
    """Aggregate-only exact calibration statistics for a report collection."""

    phase: str
    sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    rank_pair_count: int
    truth_positive_pair_count: int
    certainty_error_count: int
    truth_positive_rate_numerator: int
    truth_positive_rate_denominator: int
    certainty_error_rate_numerator: int
    certainty_error_rate_denominator: int
    presence_brier_sum_numerator: int
    presence_brier_sum_denominator: int
    presence_brier_mean_numerator: int
    presence_brier_mean_denominator: int
    copy_squared_error_sum_numerator: int
    copy_squared_error_sum_denominator: int
    copy_mse_numerator: int
    copy_mse_denominator: int
    expected_calibration_error_numerator: int
    expected_calibration_error_denominator: int
    maximum_calibration_error_numerator: int
    maximum_calibration_error_denominator: int
    calibration_bins: tuple[MarginalCalibrationAggregate, ...]
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "sample_count": self.sample_count,
            "valid_sample_count": self.valid_sample_count,
            "invalid_sample_count": self.invalid_sample_count,
            "rank_pair_count": self.rank_pair_count,
            "truth_positive_pair_count": self.truth_positive_pair_count,
            "certainty_error_count": self.certainty_error_count,
            "truth_positive_rate_numerator": self.truth_positive_rate_numerator,
            "truth_positive_rate_denominator": self.truth_positive_rate_denominator,
            "certainty_error_rate_numerator": self.certainty_error_rate_numerator,
            "certainty_error_rate_denominator": self.certainty_error_rate_denominator,
            "presence_brier_sum_numerator": self.presence_brier_sum_numerator,
            "presence_brier_sum_denominator": self.presence_brier_sum_denominator,
            "presence_brier_mean_numerator": self.presence_brier_mean_numerator,
            "presence_brier_mean_denominator": self.presence_brier_mean_denominator,
            "copy_squared_error_sum_numerator": self.copy_squared_error_sum_numerator,
            "copy_squared_error_sum_denominator": self.copy_squared_error_sum_denominator,
            "copy_mse_numerator": self.copy_mse_numerator,
            "copy_mse_denominator": self.copy_mse_denominator,
            "expected_calibration_error_numerator": self.expected_calibration_error_numerator,
            "expected_calibration_error_denominator": self.expected_calibration_error_denominator,
            "maximum_calibration_error_numerator": self.maximum_calibration_error_numerator,
            "maximum_calibration_error_denominator": self.maximum_calibration_error_denominator,
            "calibration_bins": [item.to_dict() for item in self.calibration_bins],
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


def _empty_calibration_aggregates() -> tuple[MarginalCalibrationAggregate, ...]:
    return tuple(
        MarginalCalibrationAggregate(
            bin_index=index,
            prediction_count=0,
            prediction_sum_numerator=0,
            prediction_sum_denominator=1,
            truth_positive_count=0,
            mean_prediction_numerator=0,
            mean_prediction_denominator=1,
            observed_rate_numerator=0,
            observed_rate_denominator=1,
            absolute_gap_numerator=0,
            absolute_gap_denominator=1,
        )
        for index in range(10)
    )


def _zero_fraction() -> Fraction:
    return Fraction(0, 1)


def _validate_bins(
    report: MarginalEvaluationReport,
    *,
    valid: bool,
) -> tuple[MarginalCalibrationBin, ...]:
    bins = report.calibration_bins
    if not isinstance(bins, tuple) or len(bins) != 10:
        raise ValueError("invalid calibration bins")
    for index, item in enumerate(bins):
        if not isinstance(item, MarginalCalibrationBin) or item.bin_index != index:
            raise ValueError("invalid calibration bins")
        prediction_sum = _fraction(
            item.prediction_sum_numerator,
            item.prediction_sum_denominator,
            name="calibration prediction sum",
        )
        if (
            not _is_non_negative_int(item.prediction_count)
            or not _is_non_negative_int(item.truth_positive_count)
            or item.truth_positive_count > item.prediction_count
            or prediction_sum > item.prediction_count
        ):
            raise ValueError("invalid calibration bin")
        if not valid and (
            item.prediction_count != 0
            or item.truth_positive_count != 0
            or item.prediction_sum_numerator != 0
            or item.prediction_sum_denominator != 1
        ):
            raise ValueError("invalid zeroed report")
        if item.prediction_count == 0 and (
            item.prediction_sum_numerator != 0
            or item.prediction_sum_denominator != 1
        ):
            raise ValueError("invalid empty calibration bin")
    return bins


def _validate_report(report: object) -> None:
    if not isinstance(report, MarginalEvaluationReport):
        raise ValueError("reports must contain MarginalEvaluationReport instances")
    if not _is_nonempty_string(report.phase) or not isinstance(report.valid_input, bool):
        raise ValueError("invalid marginal report")
    if not isinstance(report.diagnostics, tuple) or any(
        not _is_nonempty_string(item) for item in report.diagnostics
    ):
        raise ValueError("invalid diagnostics")
    if report.valid_input:
        if report.prediction_source != "j_d1b_physical_marginals" or report.diagnostics:
            raise ValueError("invalid valid marginal report")
        if not _is_positive_int(report.physical_assignment_count):
            raise ValueError("invalid physical assignment count")
        if not all(
            _is_non_negative_int(value)
            for value in (
                report.rank_pair_count,
                report.truth_positive_pair_count,
                report.certainty_error_count,
            )
        ):
            raise ValueError("invalid report counts")
        if (
            report.truth_positive_pair_count > report.rank_pair_count
            or report.certainty_error_count > report.rank_pair_count
        ):
            raise ValueError("invalid report count bounds")
        brier = _fraction(
            report.presence_brier_sum_numerator,
            report.presence_brier_sum_denominator,
            name="presence brier sum",
        )
        _fraction(
            report.copy_squared_error_sum_numerator,
            report.copy_squared_error_sum_denominator,
            name="copy squared error sum",
        )
        if brier > report.rank_pair_count:
            raise ValueError("invalid presence brier sum")
        bins = _validate_bins(report, valid=True)
        if (
            sum(item.prediction_count for item in bins) != report.rank_pair_count
            or sum(item.truth_positive_count for item in bins)
            != report.truth_positive_pair_count
        ):
            raise ValueError("inconsistent calibration totals")
        return

    if report.prediction_source != "none":
        raise ValueError("invalid invalid-report source")
    zero_fields = (
        report.physical_assignment_count,
        report.rank_pair_count,
        report.truth_positive_pair_count,
        report.certainty_error_count,
        report.presence_brier_sum_numerator,
        report.copy_squared_error_sum_numerator,
    )
    if (
        not all(_is_non_negative_int(value) and value == 0 for value in zero_fields)
        or not _is_positive_int(report.presence_brier_sum_denominator)
        or not _is_positive_int(report.copy_squared_error_sum_denominator)
        or report.presence_brier_sum_denominator != 1
        or report.copy_squared_error_sum_denominator != 1
    ):
        raise ValueError("invalid zeroed report")
    _validate_bins(report, valid=False)


def aggregate_marginal_reports(
    reports: Sequence[MarginalEvaluationReport],
    *,
    phase: str,
) -> MarginalBenchmarkBucket:
    """Exactly micro-aggregate complete J-D1c1 sufficient statistics.

    Invalid-but-well-formed reports contribute only sample and normalized
    diagnostic counts.  Malformed hand-constructed reports raise ``ValueError``
    rather than silently contaminating downstream calibration.
    """

    if not _is_nonempty_string(phase):
        raise ValueError("phase must be a non-empty string")
    if isinstance(reports, (str, bytes)) or not isinstance(reports, Sequence):
        raise ValueError("reports must be a non-string sequence")
    report_items = tuple(reports)
    for report in report_items:
        _validate_report(report)
        if phase != "overall" and report.phase != phase:
            raise ValueError("report phase does not match aggregate phase")

    valid_reports = tuple(report for report in report_items if report.valid_input)
    diagnostics: dict[str, int] = {}
    for report in report_items:
        if report.valid_input:
            continue
        categories = {diagnostic.split(":", 1)[0] for diagnostic in report.diagnostics}
        for category in categories:
            diagnostics[category] = diagnostics.get(category, 0) + 1

    rank_pair_count = sum(report.rank_pair_count for report in valid_reports)
    truth_positive_pair_count = sum(
        report.truth_positive_pair_count for report in valid_reports
    )
    certainty_error_count = sum(report.certainty_error_count for report in valid_reports)
    presence_brier_sum = sum(
        (
            Fraction(
                report.presence_brier_sum_numerator,
                report.presence_brier_sum_denominator,
            )
            for report in valid_reports
        ),
        _zero_fraction(),
    )
    copy_squared_error_sum = sum(
        (
            Fraction(
                report.copy_squared_error_sum_numerator,
                report.copy_squared_error_sum_denominator,
            )
            for report in valid_reports
        ),
        _zero_fraction(),
    )

    bin_counts = [0] * 10
    bin_truth_positives = [0] * 10
    bin_prediction_sums = [_zero_fraction() for _ in range(10)]
    for report in valid_reports:
        for item in report.calibration_bins:
            bin_counts[item.bin_index] += item.prediction_count
            bin_truth_positives[item.bin_index] += item.truth_positive_count
            bin_prediction_sums[item.bin_index] += Fraction(
                item.prediction_sum_numerator,
                item.prediction_sum_denominator,
            )

    calibration_bins: list[MarginalCalibrationAggregate] = []
    ece_numerator = _zero_fraction()
    maximum_gap = _zero_fraction()
    for index in range(10):
        count = bin_counts[index]
        prediction_sum = bin_prediction_sums[index]
        positives = bin_truth_positives[index]
        if count:
            mean_prediction = prediction_sum / count
            observed_rate = Fraction(positives, count)
            gap = abs(mean_prediction - observed_rate)
            ece_numerator += abs(prediction_sum - positives)
            maximum_gap = max(maximum_gap, gap)
        else:
            mean_prediction = _zero_fraction()
            observed_rate = _zero_fraction()
            gap = _zero_fraction()
        calibration_bins.append(
            MarginalCalibrationAggregate(
                bin_index=index,
                prediction_count=count,
                prediction_sum_numerator=prediction_sum.numerator,
                prediction_sum_denominator=prediction_sum.denominator,
                truth_positive_count=positives,
                mean_prediction_numerator=mean_prediction.numerator,
                mean_prediction_denominator=mean_prediction.denominator,
                observed_rate_numerator=observed_rate.numerator,
                observed_rate_denominator=observed_rate.denominator,
                absolute_gap_numerator=gap.numerator,
                absolute_gap_denominator=gap.denominator,
            )
        )

    if rank_pair_count:
        truth_positive_rate = Fraction(truth_positive_pair_count, rank_pair_count)
        certainty_error_rate = Fraction(certainty_error_count, rank_pair_count)
        presence_brier_mean = presence_brier_sum / rank_pair_count
        copy_mse = copy_squared_error_sum / rank_pair_count
        ece = ece_numerator / rank_pair_count
    else:
        truth_positive_rate = _zero_fraction()
        certainty_error_rate = _zero_fraction()
        presence_brier_mean = _zero_fraction()
        copy_mse = _zero_fraction()
        ece = _zero_fraction()

    return MarginalBenchmarkBucket(
        phase=phase,
        sample_count=len(report_items),
        valid_sample_count=len(valid_reports),
        invalid_sample_count=len(report_items) - len(valid_reports),
        rank_pair_count=rank_pair_count,
        truth_positive_pair_count=truth_positive_pair_count,
        certainty_error_count=certainty_error_count,
        truth_positive_rate_numerator=truth_positive_rate.numerator,
        truth_positive_rate_denominator=truth_positive_rate.denominator,
        certainty_error_rate_numerator=certainty_error_rate.numerator,
        certainty_error_rate_denominator=certainty_error_rate.denominator,
        presence_brier_sum_numerator=presence_brier_sum.numerator,
        presence_brier_sum_denominator=presence_brier_sum.denominator,
        presence_brier_mean_numerator=presence_brier_mean.numerator,
        presence_brier_mean_denominator=presence_brier_mean.denominator,
        copy_squared_error_sum_numerator=copy_squared_error_sum.numerator,
        copy_squared_error_sum_denominator=copy_squared_error_sum.denominator,
        copy_mse_numerator=copy_mse.numerator,
        copy_mse_denominator=copy_mse.denominator,
        expected_calibration_error_numerator=ece.numerator,
        expected_calibration_error_denominator=ece.denominator,
        maximum_calibration_error_numerator=maximum_gap.numerator,
        maximum_calibration_error_denominator=maximum_gap.denominator,
        calibration_bins=tuple(calibration_bins),
        diagnostic_counts=MappingProxyType(dict(sorted(diagnostics.items()))),
    )
