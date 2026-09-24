"""Offline candidate-distribution calibration for the frozen H3-A8/A9 states.

This module evaluates every production-displayed candidate against the same
frozen RuleBased reference used by the action-quality proxy. It never calls a
model or exposes engine snapshots outside this process.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
import json

from agents.game_phase import classify_game_phase
from agents.rag_advisor import RAGAdvisor
from evaluation.action_quality_proxy import (
    MAX_ROLLOUT_STEPS,
    ReplayableQualitySample,
    SampleSetResult,
    _actual_game_matches_public,
    _reference_action_id,
    build_replayable_quality_samples,
)
from evaluation.h3_a9_quality_queue import build_h3_a9_quality_samples
from evaluation.h3_model_probe_fixtures import _advisor as _h3_advisor
from evaluation.strategy_intent_action_quality import (
    RuleRolloutOutcome,
    _compare_quality,
    _rollout,
)


class CalibrationStatus(StrEnum):
    READY = "ready"
    SAMPLE_SET_INVALID = "sample_set_invalid"
    SAMPLE_SET_CONTRACT_INVALID = "sample_set_contract_invalid"
    CALIBRATION_INCOMPLETE = "calibration_incomplete"
    DUPLICATE_SAMPLE = "duplicate_sample"
    SAMPLE_CONTRACT_INVALID = "sample_contract_invalid"
    SNAPSHOT_PUBLIC_MISMATCH = "snapshot_public_mismatch"
    CANONICAL_ACTIONS_INVALID = "canonical_actions_invalid"
    FINAL_CANDIDATES_INVALID = "final_candidates_invalid"
    REFERENCE_ACTION_INVALID = "reference_action_invalid"
    REFERENCE_ACTION_NOT_VISIBLE = "reference_action_not_visible"
    PLAYER_INVALID = "player_invalid"
    ROLLOUT_CLONE_INVALID = "rollout_clone_invalid"
    ROLLOUT_FAILURE = "rollout_failure"
    ROLLOUT_RESULT_INVALID = "rollout_result_invalid"
    ROLLOUT_STEP_COUNT_INVALID = "rollout_step_count_invalid"
    ROLLOUT_INCOMPLETE = "rollout_incomplete"
    SNAPSHOT_CHANGED = "snapshot_changed"
    COMPARISON_INVALID = "comparison_invalid"


_COMPARISON_FIELDS = (
    "better_than_reference",
    "tie_with_reference",
    "worse_than_reference",
)
_QUALITY_LABELS = {"win": 2, "draw": 1, "loss": 0}
_QUALITY_COMPARISONS = {
    "on_better": "better_than_reference",
    "tie": "tie_with_reference",
    "off_better": "worse_than_reference",
}

# Frozen metadata only. Candidate/action IDs are deliberately not part of this
# contract: each run takes the actual final IDs emitted by the existing queue.
_H3_A8_CONTRACT = (
    ("opening_low_cost_single", "opening", 53, 23),
    ("opening_neutral_soft_pair", "opening", 83, 51),
    ("midgame_1", "midgame", 6, 6),
    ("midgame_2", "midgame", 6, 6),
    ("endgame_1", "endgame", 9, 9),
    ("endgame_2", "near_open_endgame", 8, 4),
)
_H3_A9_CONTRACT = (
    ("opening_1", "opening", 77, 53),
    ("opening_2", "opening", 74, 48),
    ("midgame_1", "midgame", 25, 13),
    ("midgame_2", "midgame", 11, 11),
    ("endgame_1", "critical_endgame", 8, 8),
    ("endgame_2", "near_open_endgame", 9, 9),
)
_FIXED_CONTRACTS = {
    **{
        ("h3_a8", name): (phase, canonical_count, final_count)
        for name, phase, canonical_count, final_count in _H3_A8_CONTRACT
    },
    **{
        ("h3_a9", name): (phase, canonical_count, final_count)
        for name, phase, canonical_count, final_count in _H3_A9_CONTRACT
    },
}


@dataclass(frozen=True, slots=True)
class CandidateDistribution:
    """Low-sensitivity aggregate for one fixed state."""

    sample_name: str
    phase: str
    canonical_candidate_count: int
    final_candidate_count: int
    completed_candidate_count: int
    better_than_reference: int
    tie_with_reference: int
    worse_than_reference: int
    reference_action_visible: bool
    status: CalibrationStatus

    @property
    def comparison_count(self) -> int:
        return self.better_than_reference + self.tie_with_reference + self.worse_than_reference

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_name": self.sample_name,
            "phase": self.phase,
            "canonical_candidate_count": self.canonical_candidate_count,
            "final_candidate_count": self.final_candidate_count,
            "completed_candidate_count": self.completed_candidate_count,
            "better_than_reference": self.better_than_reference,
            "tie_with_reference": self.tie_with_reference,
            "worse_than_reference": self.worse_than_reference,
            "reference_action_visible": self.reference_action_visible,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class CandidateCalibrationReport:
    status: CalibrationStatus
    samples: tuple[CandidateDistribution, ...] = field(default=(), repr=False)

    @property
    def completed_sample_count(self) -> int:
        return sum(sample.status is CalibrationStatus.READY for sample in self.samples)

    @property
    def completed_candidate_count(self) -> int:
        return sum(sample.completed_candidate_count for sample in self.samples)

    def to_dict(self) -> dict[str, object]:
        totals = Counter({name: 0 for name in _COMPARISON_FIELDS})
        for sample in self.samples:
            for name in _COMPARISON_FIELDS:
                totals[name] += getattr(sample, name)
        return {
            "proxy_kind": "frozen_rule_based_candidate_distribution_not_win_rate",
            "status": self.status.value,
            "sample_count": len(self.samples),
            "completed_sample_count": self.completed_sample_count,
            "canonical_candidate_count": sum(sample.canonical_candidate_count for sample in self.samples),
            "final_candidate_count": sum(sample.final_candidate_count for sample in self.samples),
            "completed_candidate_count": self.completed_candidate_count,
            "comparison_counts": {name: totals[name] for name in _COMPARISON_FIELDS},
            "samples": [sample.to_dict() for sample in self.samples],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _empty_distribution(
    sample: ReplayableQualitySample,
    status: CalibrationStatus,
    *,
    sample_name: str | None = None,
    completed_candidate_count: int = 0,
    reference_action_visible: bool = False,
    counts: Counter[str] | None = None,
) -> CandidateDistribution:
    comparison_counts = counts or Counter()
    return CandidateDistribution(
        sample_name=sample.name if sample_name is None else sample_name,
        phase=sample.phase,
        canonical_candidate_count=sample.canonical_candidate_count,
        final_candidate_count=sample.final_candidate_count,
        completed_candidate_count=completed_candidate_count,
        better_than_reference=comparison_counts["better_than_reference"],
        tie_with_reference=comparison_counts["tie_with_reference"],
        worse_than_reference=comparison_counts["worse_than_reference"],
        reference_action_visible=reference_action_visible,
        status=status,
    )


def _valid_rollout_outcome(outcome: object) -> CalibrationStatus | None:
    if not isinstance(outcome, RuleRolloutOutcome):
        return CalibrationStatus.ROLLOUT_RESULT_INVALID
    if (
        type(outcome.complete) is not bool
        or type(outcome.rollout_step_count) is not int
        or not 1 <= outcome.rollout_step_count <= MAX_ROLLOUT_STEPS
    ):
        return CalibrationStatus.ROLLOUT_STEP_COUNT_INVALID
    if not outcome.complete:
        return CalibrationStatus.ROLLOUT_INCOMPLETE
    if (
        type(outcome.team_outcome_score) is not int
        or outcome.team_outcome_score not in (0, 1, 2)
        or type(outcome.team_placement_sum) is not int
        or not 3 <= outcome.team_placement_sum <= 7
        or not isinstance(outcome.team_outcome, str)
        or outcome.team_outcome not in _QUALITY_LABELS
    ):
        return CalibrationStatus.ROLLOUT_RESULT_INVALID
    if outcome.team_outcome_score != _QUALITY_LABELS[outcome.team_outcome]:
        return CalibrationStatus.ROLLOUT_RESULT_INVALID
    if not isinstance(outcome.diagnostics, tuple) or outcome.diagnostics:
        return CalibrationStatus.ROLLOUT_RESULT_INVALID
    return None


def _public_snapshot_signature(sample: ReplayableQualitySample) -> str | None:
    try:
        return json.dumps(
            [sample.observation, sample.legal_actions],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None


def calibrate_sample_candidates(
    sample: ReplayableQualitySample,
    *,
    sample_name: str | None = None,
) -> CandidateDistribution:
    """Compare every final candidate with the frozen RuleBased action.

    This lower-level entry point is useful for fail-closed tests. Production
    callers should use :func:`calibrate_h3_a10_candidate_distribution`, which
    additionally verifies the fixed twelve-state metadata contract.
    """
    if not isinstance(sample, ReplayableQualitySample):
        raise TypeError("sample_invalid")
    snapshot = sample.game_snapshot
    if not _actual_game_matches_public(snapshot, sample.observation, sample.legal_actions):
        return _empty_distribution(sample, CalibrationStatus.SNAPSHOT_PUBLIC_MISMATCH, sample_name=sample_name)
    try:
        if classify_game_phase(sample.observation).phase != sample.phase:
            return _empty_distribution(sample, CalibrationStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name)
    except Exception:
        return _empty_distribution(sample, CalibrationStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name)

    legal_actions = sample.legal_actions
    if not isinstance(legal_actions, list) or not legal_actions:
        return _empty_distribution(sample, CalibrationStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name)
    canonical_ids: list[int] = []
    canonical_by_id: dict[int, dict[str, object]] = {}
    try:
        for action in legal_actions:
            if not isinstance(action, Mapping):
                return _empty_distribution(sample, CalibrationStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name)
            action_id = action.get("action_id")
            if type(action_id) is not int or action_id in canonical_by_id:
                return _empty_distribution(sample, CalibrationStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name)
            canonical_ids.append(action_id)
            canonical_by_id[action_id] = action  # type: ignore[assignment]
    except Exception:
        return _empty_distribution(sample, CalibrationStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name)
    if sample.canonical_candidate_count != len(canonical_ids):
        return _empty_distribution(sample, CalibrationStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name)

    final_ids = sample.final_candidate_ids
    if (
        not isinstance(final_ids, tuple)
        or sample.final_candidate_count != len(final_ids)
        or not 2 <= len(final_ids) <= 80
        or any(type(action_id) is not int for action_id in final_ids)
        or len(final_ids) != len(set(final_ids))
        or not set(final_ids).issubset(set(canonical_ids))
    ):
        return _empty_distribution(sample, CalibrationStatus.FINAL_CANDIDATES_INVALID, sample_name=sample_name)
    reference_id = _reference_action_id(sample.observation, legal_actions)
    if type(reference_id) is not int or reference_id not in canonical_by_id:
        return _empty_distribution(sample, CalibrationStatus.REFERENCE_ACTION_INVALID, sample_name=sample_name, reference_action_visible=False)
    reference_visible = reference_id in final_ids
    if not reference_visible:
        return _empty_distribution(
            sample,
            CalibrationStatus.REFERENCE_ACTION_NOT_VISIBLE,
            sample_name=sample_name,
            reference_action_visible=False,
        )
    info = sample.observation.get("my_info")
    player_id = info.get("player_id") if isinstance(info, Mapping) else None
    if type(player_id) is not int or not 1 <= player_id <= 4:
        return _empty_distribution(sample, CalibrationStatus.PLAYER_INVALID, sample_name=sample_name, reference_action_visible=True)

    reference_snapshot = _public_snapshot_signature(sample)
    if reference_snapshot is None:
        return _empty_distribution(sample, CalibrationStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name, reference_action_visible=True)

    outcomes: dict[int, RuleRolloutOutcome] = {}
    for action_id in final_ids:
        if not _actual_game_matches_public(snapshot, sample.observation, legal_actions):
            return _empty_distribution(
                sample,
                CalibrationStatus.SNAPSHOT_CHANGED,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        try:
            branch = deepcopy(snapshot)
        except Exception:
            return _empty_distribution(
                sample,
                CalibrationStatus.ROLLOUT_CLONE_INVALID,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        if branch is snapshot or not _actual_game_matches_public(branch, sample.observation, legal_actions):
            return _empty_distribution(
                sample,
                CalibrationStatus.ROLLOUT_CLONE_INVALID,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        try:
            outcome = _rollout(branch, action_id, player_id, MAX_ROLLOUT_STEPS)
        except Exception:
            return _empty_distribution(
                sample,
                CalibrationStatus.ROLLOUT_FAILURE,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        failure = _valid_rollout_outcome(outcome)
        if failure is not None:
            return _empty_distribution(
                sample,
                failure,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        outcomes[action_id] = outcome
        if not _actual_game_matches_public(snapshot, sample.observation, legal_actions):
            return _empty_distribution(
                sample,
                CalibrationStatus.SNAPSHOT_CHANGED,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )
        if _public_snapshot_signature(sample) != reference_snapshot:
            return _empty_distribution(
                sample,
                CalibrationStatus.SNAPSHOT_CHANGED,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
            )

    reference_outcome = outcomes.get(reference_id)
    if reference_outcome is None:
        return _empty_distribution(
            sample,
            CalibrationStatus.REFERENCE_ACTION_NOT_VISIBLE,
            sample_name=sample_name,
            completed_candidate_count=len(outcomes),
            reference_action_visible=True,
        )

    counts: Counter[str] = Counter()
    for action_id in final_ids:
        try:
            comparison = _compare_quality(reference_outcome, outcomes[action_id])
        except Exception:
            return _empty_distribution(
                sample,
                CalibrationStatus.COMPARISON_INVALID,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
                counts=counts,
            )
        category = _QUALITY_COMPARISONS.get(comparison)
        if category is None:
            return _empty_distribution(
                sample,
                CalibrationStatus.COMPARISON_INVALID,
                sample_name=sample_name,
                completed_candidate_count=len(outcomes),
                reference_action_visible=True,
                counts=counts,
            )
        counts[category] += 1

    if (
        sum(counts.values()) != len(final_ids)
        or len(outcomes) != len(final_ids)
        or not _actual_game_matches_public(snapshot, sample.observation, legal_actions)
    ):
        return _empty_distribution(
            sample,
            CalibrationStatus.SNAPSHOT_CHANGED,
            sample_name=sample_name,
            completed_candidate_count=len(outcomes),
            reference_action_visible=True,
            counts=counts,
        )
    return _empty_distribution(
        sample,
        CalibrationStatus.READY,
        sample_name=sample_name,
        completed_candidate_count=len(outcomes),
        reference_action_visible=True,
        counts=counts,
    )


def _contract_status(sample: ReplayableQualitySample, expected: tuple[str, int, int]) -> CalibrationStatus:
    phase, canonical_count, final_count = expected
    if (
        sample.phase != phase
        or sample.canonical_candidate_count != canonical_count
        or sample.final_candidate_count != final_count
    ):
        return CalibrationStatus.SAMPLE_CONTRACT_INVALID
    return CalibrationStatus.READY


def calibrate_h3_a10_candidate_distribution(
    *, advisor: RAGAdvisor | None = None,
) -> CandidateCalibrationReport:
    """Build the frozen H3-A8/A9 queues and exhaustively calibrate candidates."""
    try:
        rag_advisor = advisor or _h3_advisor()
        h3_a8 = build_replayable_quality_samples(advisor=rag_advisor)
        h3_a9 = build_h3_a9_quality_samples(advisor=rag_advisor)
    except Exception:
        return CandidateCalibrationReport(CalibrationStatus.SAMPLE_SET_INVALID)
    return calibrate_h3_a10_sample_sets(h3_a8, h3_a9)


def calibrate_h3_a10_sample_sets(
    h3_a8: SampleSetResult,
    h3_a9: SampleSetResult,
) -> CandidateCalibrationReport:
    """Calibrate already-built H3-A8/A9 queues without rebuilding snapshots."""
    if not isinstance(h3_a8, SampleSetResult) or not isinstance(h3_a9, SampleSetResult) or not h3_a8.ready or not h3_a9.ready:
        return CandidateCalibrationReport(CalibrationStatus.SAMPLE_SET_INVALID)

    if (
        tuple(sample.name for sample in h3_a8.samples) != tuple(row[0] for row in _H3_A8_CONTRACT)
        or tuple(sample.name for sample in h3_a9.samples) != tuple(row[0] for row in _H3_A9_CONTRACT)
    ):
        return CandidateCalibrationReport(CalibrationStatus.SAMPLE_SET_CONTRACT_INVALID)
    samples = tuple(("h3_a8", sample) for sample in h3_a8.samples) + tuple(
        ("h3_a9", sample) for sample in h3_a9.samples
    )
    if len(samples) != 12 or any((cohort, sample.name) not in _FIXED_CONTRACTS for cohort, sample in samples):
        return CandidateCalibrationReport(CalibrationStatus.SAMPLE_SET_CONTRACT_INVALID)

    signatures = tuple(_public_snapshot_signature(sample) for _cohort, sample in samples)
    if any(signature is None for signature in signatures):
        return CandidateCalibrationReport(CalibrationStatus.SAMPLE_SET_CONTRACT_INVALID)
    repeated = {signature for signature in signatures if signatures.count(signature) > 1}
    if repeated:
        results = tuple(
            _empty_distribution(
                sample,
                CalibrationStatus.DUPLICATE_SAMPLE,
                sample_name=f"{cohort}:{sample.name}",
            )
            for cohort, sample in samples
        )
        return CandidateCalibrationReport(CalibrationStatus.DUPLICATE_SAMPLE, results)

    results: list[CandidateDistribution] = []
    for cohort, sample in samples:
        display_name = f"{cohort}:{sample.name}"
        contract = _contract_status(sample, _FIXED_CONTRACTS[(cohort, sample.name)])
        if contract is not CalibrationStatus.READY:
            results.append(_empty_distribution(sample, contract, sample_name=display_name))
            continue
        results.append(calibrate_sample_candidates(sample, sample_name=display_name))
    overall = (
        CalibrationStatus.READY
        if len(results) == 12 and all(result.status is CalibrationStatus.READY for result in results)
        else CalibrationStatus.CALIBRATION_INCOMPLETE
    )
    return CandidateCalibrationReport(overall, tuple(results))
