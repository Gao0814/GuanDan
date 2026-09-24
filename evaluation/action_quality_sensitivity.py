"""Offline continuation-policy sensitivity for the frozen H3-A8/A9 states.

The first action and candidate set are held fixed.  Only the agents used after
that action differ: the existing RuleBased selector is compared with its
historical FrozenRuleBased predecessor.  Reports contain aggregate counts
only; snapshots and action IDs remain in memory.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json

from agents.base import require_legal_action_id
from agents.game_phase import classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import FrozenRuleBasedAIAgent, RuleBasedAIAgent
from evaluation.action_quality_calibration import (
    CalibrationStatus,
    _FIXED_CONTRACTS,
    _valid_rollout_outcome,
)
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
    _normalize_terminal,
    _rollout,
)


_LABELS = ("better", "tie", "worse")
_BASELINE_LABELS = {
    "on_better": "better",
    "tie": "tie",
    "off_better": "worse",
}
_COHORTS = (
    ("h3_a8", ("opening_low_cost_single", "opening_neutral_soft_pair", "midgame_1", "midgame_2", "endgame_1", "endgame_2")),
    ("h3_a9", ("opening_1", "opening_2", "midgame_1", "midgame_2", "endgame_1", "endgame_2")),
)


class SensitivityStatus(StrEnum):
    READY = "ready"
    INCOMPLETE = "incomplete"
    SAMPLE_SET_INVALID = "sample_set_invalid"
    SAMPLE_SET_CONTRACT_INVALID = "sample_set_contract_invalid"
    DUPLICATE_SAMPLE = "duplicate_sample"
    SNAPSHOT_PUBLIC_MISMATCH = "snapshot_public_mismatch"
    SAMPLE_CONTRACT_INVALID = "sample_contract_invalid"
    CANONICAL_ACTIONS_INVALID = "canonical_actions_invalid"
    FINAL_CANDIDATES_INVALID = "final_candidates_invalid"
    REFERENCE_ACTION_INVALID = "reference_action_invalid"
    REFERENCE_ACTION_NOT_VISIBLE = "reference_action_not_visible"
    PLAYER_INVALID = "player_invalid"
    ROLLOUT_CLONE_INVALID = "rollout_clone_invalid"
    BASELINE_ROLLOUT_FAILURE = "baseline_rollout_failure"
    FROZEN_ROLLOUT_FAILURE = "frozen_rollout_failure"
    ROLLOUT_STEP_COUNT_INVALID = "rollout_step_count_invalid"
    ROLLOUT_RESULT_INVALID = "rollout_result_invalid"
    ROLLOUT_INCOMPLETE = "rollout_incomplete"
    SNAPSHOT_CHANGED = "snapshot_changed"
    COMPARISON_INVALID = "comparison_invalid"
    NOT_RUN_AFTER_FAILURE = "not_run_after_failure"


@dataclass(frozen=True, slots=True)
class SensitivityStateResult:
    sample_name: str
    phase: str
    canonical_candidate_count: int
    final_candidate_count: int
    baseline_completed_candidate_count: int
    frozen_completed_candidate_count: int
    paired_completed_candidate_count: int
    transition_counts: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
    label_changed_count: int
    strict_preference_reversal_count: int
    frozen_difference_candidate_branch_count: int
    frozen_difference_public_state_count: int
    reference_tied_in_both_count: int
    reference_action_visible: bool
    status: SensitivityStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_name": self.sample_name,
            "phase": self.phase,
            "canonical_candidate_count": self.canonical_candidate_count,
            "final_candidate_count": self.final_candidate_count,
            "baseline_completed_candidate_count": self.baseline_completed_candidate_count,
            "frozen_completed_candidate_count": self.frozen_completed_candidate_count,
            "paired_completed_candidate_count": self.paired_completed_candidate_count,
            "transition_counts": _matrix_dict(self.transition_counts),
            "label_changed_count": self.label_changed_count,
            "strict_preference_reversal_count": self.strict_preference_reversal_count,
            "frozen_difference_candidate_branch_count": self.frozen_difference_candidate_branch_count,
            "frozen_difference_public_state_count": self.frozen_difference_public_state_count,
            "reference_tied_in_both_count": self.reference_tied_in_both_count,
            "reference_action_visible": self.reference_action_visible,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    status: SensitivityStatus
    samples: tuple[SensitivityStateResult, ...] = field(default=(), repr=False)
    frozen_difference_public_state_count: int = 0

    @property
    def planned_candidate_count(self) -> int:
        return sum(sample.final_candidate_count for sample in self.samples)

    @property
    def paired_completed_candidate_count(self) -> int:
        return sum(sample.paired_completed_candidate_count for sample in self.samples)

    @property
    def frozen_difference_candidate_branch_count(self) -> int:
        return sum(sample.frozen_difference_candidate_branch_count for sample in self.samples)

    def to_dict(self) -> dict[str, object]:
        matrix = _empty_matrix()
        for sample in self.samples:
            for row_index in range(3):
                for column_index in range(3):
                    matrix[row_index][column_index] += sample.transition_counts[row_index][column_index]
        total_matrix = _matrix_tuple(matrix)
        result = {
            "proxy_kind": "continuation_policy_sensitivity_not_win_rate",
            "interpretation": "candidate_proxy_distribution_not_model_probability_or_win_rate",
            "status": self.status.value,
            "sample_count": len(self.samples),
            "ready_sample_count": sum(sample.status is SensitivityStatus.READY for sample in self.samples),
            "planned_candidate_count": self.planned_candidate_count,
            "baseline_completed_candidate_count": sum(sample.baseline_completed_candidate_count for sample in self.samples),
            "frozen_completed_candidate_count": sum(sample.frozen_completed_candidate_count for sample in self.samples),
            "paired_completed_candidate_count": self.paired_completed_candidate_count,
            "transition_counts": _matrix_dict(total_matrix),
            "transition_axes": {
                "rows": "rule_based_continuation_label",
                "columns": "frozen_rule_based_continuation_label",
            },
            "label_changed_count": sum(sample.label_changed_count for sample in self.samples),
            "strict_preference_reversal_count": sum(sample.strict_preference_reversal_count for sample in self.samples),
            "frozen_difference_candidate_branch_count": self.frozen_difference_candidate_branch_count,
            "frozen_difference_public_state_count": self.frozen_difference_public_state_count,
            "reference_tied_in_both_count": sum(sample.reference_tied_in_both_count for sample in self.samples),
            "information_value": (
                "no_continuation_difference_observed"
                if self.frozen_difference_candidate_branch_count == 0
                else "continuation_difference_observed"
            ),
            "samples": [sample.to_dict() for sample in self.samples],
        }
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _empty_matrix() -> list[list[int]]:
    return [[0, 0, 0] for _ in range(3)]


def _matrix_tuple(matrix: list[list[int]]) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    return tuple(tuple(row) for row in matrix)  # type: ignore[return-value]


def _matrix_dict(matrix: tuple[tuple[int, int, int], ...]) -> dict[str, dict[str, int]]:
    return {baseline: {frozen: matrix[row][column] for column, frozen in enumerate(_LABELS)} for row, baseline in enumerate(_LABELS)}


def _sample_public_signature(sample: ReplayableQualitySample) -> str | None:
    try:
        return json.dumps([sample.observation, sample.legal_actions], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None


def _decision_state_digest(observation: object, legal_actions: object) -> str:
    encoded = json.dumps([observation, legal_actions], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _failure_outcome(steps: int, diagnostic: str) -> RuleRolloutOutcome:
    return RuleRolloutOutcome("", 0, 0, steps, False, (diagnostic,))


def _frozen_rollout(
    branch: object,
    action_id: object,
    observer: object,
) -> tuple[RuleRolloutOutcome, tuple[str, ...]]:
    """Run the same first action, then Frozen agents; return private state hashes."""
    from engine.game import GuanDanGame

    if not isinstance(branch, GuanDanGame) or type(observer) is not int or not 1 <= observer <= 4:
        return _failure_outcome(0, "initial_action_invalid"), ()
    try:
        legal = branch.legal_actions()
        if type(action_id) is not int:
            return _failure_outcome(0, "initial_action_invalid"), ()
        first_action = require_legal_action_id(action_id, legal)
        result = branch.step(first_action)
        if type(result.get("game_over")) is not bool:
            return _failure_outcome(1, "invalid_step_result"), ()
        steps = 1
        if result["game_over"]:
            return _normalize_terminal(branch.observe(), result.get("winner"), observer, steps), ()

        frozen_agents = {player: FrozenRuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        regular_agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        differences: list[str] = []
        while steps < MAX_ROLLOUT_STEPS:
            observation = branch.observe()
            info = observation.get("my_info")
            player = info.get("player_id") if isinstance(info, Mapping) else None
            legal = branch.legal_actions()
            if type(player) is not int or player not in frozen_agents:
                return _failure_outcome(steps, "rollout_action_invalid"), tuple(differences)
            frozen_raw = frozen_agents[player].select_action(observation, legal)
            regular_raw = regular_agents[player].select_action(observation, legal)
            if type(frozen_raw) is not int or type(regular_raw) is not int:
                return _failure_outcome(steps, "rollout_action_invalid"), tuple(differences)
            frozen_action = require_legal_action_id(frozen_raw, legal)
            regular_action = require_legal_action_id(regular_raw, legal)
            if frozen_action != regular_action:
                differences.append(_decision_state_digest(observation, legal))
            result = branch.step(frozen_action)
            steps += 1
            if type(result.get("game_over")) is not bool:
                return _failure_outcome(steps, "invalid_step_result"), tuple(differences)
            if result["game_over"]:
                return _normalize_terminal(branch.observe(), result.get("winner"), observer, steps), tuple(differences)
        return _failure_outcome(steps, "rollout_step_limit_reached"), tuple(differences)
    except Exception:
        return _failure_outcome(0, "rollout_exception"), ()


def _labels(reference: RuleRolloutOutcome, candidate: RuleRolloutOutcome) -> tuple[str, str] | None:
    comparison = _compare_quality(reference, candidate)
    label = _BASELINE_LABELS.get(comparison)
    return (label, comparison) if label is not None else None


def _state_result(
    sample: ReplayableQualitySample,
    status: SensitivityStatus,
    *,
    sample_name: str,
    baseline_completed: int = 0,
    frozen_completed: int = 0,
    paired_completed: int = 0,
    matrix: list[list[int]] | None = None,
    changed: int = 0,
    reversals: int = 0,
    differing_branches: int = 0,
    differing_states: int = 0,
    reference_ties: int = 0,
    reference_visible: bool = False,
) -> SensitivityStateResult:
    return SensitivityStateResult(
        sample_name=sample_name,
        phase=sample.phase,
        canonical_candidate_count=sample.canonical_candidate_count,
        final_candidate_count=sample.final_candidate_count,
        baseline_completed_candidate_count=baseline_completed,
        frozen_completed_candidate_count=frozen_completed,
        paired_completed_candidate_count=paired_completed,
        transition_counts=_matrix_tuple(matrix or _empty_matrix()),
        label_changed_count=changed,
        strict_preference_reversal_count=reversals,
        frozen_difference_candidate_branch_count=differing_branches,
        frozen_difference_public_state_count=differing_states,
        reference_tied_in_both_count=reference_ties,
        reference_action_visible=reference_visible,
        status=status,
    )


def _not_run(sample: ReplayableQualitySample, cohort: str) -> SensitivityStateResult:
    return _state_result(sample, SensitivityStatus.NOT_RUN_AFTER_FAILURE, sample_name=f"{cohort}:{sample.name}")


def evaluate_h3_a11_sample_sets(h3_a8: SampleSetResult, h3_a9: SampleSetResult) -> SensitivityReport:
    """Compare all final candidates on the frozen twelve-state queues."""
    if not isinstance(h3_a8, SampleSetResult) or not isinstance(h3_a9, SampleSetResult) or not h3_a8.ready or not h3_a9.ready:
        return SensitivityReport(SensitivityStatus.SAMPLE_SET_INVALID)
    if tuple(sample.name for sample in h3_a8.samples) != _COHORTS[0][1] or tuple(sample.name for sample in h3_a9.samples) != _COHORTS[1][1]:
        return SensitivityReport(SensitivityStatus.SAMPLE_SET_CONTRACT_INVALID)

    rows = tuple((cohort, sample) for cohort, names in _COHORTS for sample in (h3_a8.samples if cohort == "h3_a8" else h3_a9.samples))
    if len(rows) != 12:
        return SensitivityReport(SensitivityStatus.SAMPLE_SET_CONTRACT_INVALID)
    expected_final_total = sum(sample.final_candidate_count for _cohort, sample in rows)
    signatures = tuple(_sample_public_signature(sample) for _cohort, sample in rows)
    if any(signature is None for signature in signatures):
        return SensitivityReport(SensitivityStatus.SAMPLE_SET_CONTRACT_INVALID)
    if len(set(signatures)) != len(signatures):
        results = tuple(_state_result(sample, SensitivityStatus.DUPLICATE_SAMPLE, sample_name=f"{cohort}:{sample.name}") for cohort, sample in rows)
        return SensitivityReport(SensitivityStatus.DUPLICATE_SAMPLE, results)

    results: list[SensitivityStateResult] = []
    all_differing_public_states: set[str] = set()
    failed = False
    for row_index, (cohort, sample) in enumerate(rows):
        sample_name = f"{cohort}:{sample.name}"
        if failed:
            results.append(_not_run(sample, cohort))
            continue

        expected = _FIXED_CONTRACTS.get((cohort, sample.name))
        if expected is None or expected != (sample.phase, sample.canonical_candidate_count, sample.final_candidate_count):
            results.append(_state_result(sample, SensitivityStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name))
            failed = True
            continue
        snapshot = sample.game_snapshot
        if not _actual_game_matches_public(snapshot, sample.observation, sample.legal_actions):
            results.append(_state_result(sample, SensitivityStatus.SNAPSHOT_PUBLIC_MISMATCH, sample_name=sample_name))
            failed = True
            continue
        try:
            if classify_game_phase(sample.observation).phase != sample.phase:
                results.append(_state_result(sample, SensitivityStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name))
                failed = True
                continue
        except Exception:
            results.append(_state_result(sample, SensitivityStatus.SAMPLE_CONTRACT_INVALID, sample_name=sample_name))
            failed = True
            continue

        legal = sample.legal_actions
        canonical_by_id: dict[int, Mapping[str, object]] = {}
        canonical_signatures: set[str] = set()
        malformed = not isinstance(legal, list) or not legal
        if not malformed:
            try:
                for action in legal:
                    if not isinstance(action, Mapping) or type(action.get("action_id")) is not int or action["action_id"] in canonical_by_id:
                        malformed = True
                        break
                    action_signature = json.dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                    if action_signature in canonical_signatures:
                        malformed = True
                        break
                    canonical_signatures.add(action_signature)
                    canonical_by_id[action["action_id"]] = action
            except Exception:
                malformed = True
        if malformed or len(canonical_by_id) != sample.canonical_candidate_count:
            results.append(_state_result(sample, SensitivityStatus.CANONICAL_ACTIONS_INVALID, sample_name=sample_name))
            failed = True
            continue
        final_ids = sample.final_candidate_ids
        if (
            not isinstance(final_ids, tuple)
            or len(final_ids) != sample.final_candidate_count
            or not 2 <= len(final_ids) <= 80
            or any(type(action_id) is not int for action_id in final_ids)
            or len(set(final_ids)) != len(final_ids)
            or not set(final_ids).issubset(canonical_by_id)
        ):
            results.append(_state_result(sample, SensitivityStatus.FINAL_CANDIDATES_INVALID, sample_name=sample_name))
            failed = True
            continue
        reference_id = _reference_action_id(sample.observation, legal)
        if type(reference_id) is not int or reference_id not in canonical_by_id:
            results.append(_state_result(sample, SensitivityStatus.REFERENCE_ACTION_INVALID, sample_name=sample_name))
            failed = True
            continue
        if reference_id not in final_ids:
            results.append(_state_result(sample, SensitivityStatus.REFERENCE_ACTION_NOT_VISIBLE, sample_name=sample_name))
            failed = True
            continue
        my_info = sample.observation.get("my_info")
        player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
        if type(player_id) is not int or not 1 <= player_id <= 4:
            results.append(_state_result(sample, SensitivityStatus.PLAYER_INVALID, sample_name=sample_name, reference_visible=True))
            failed = True
            continue

        original_signature = signatures[row_index]
        baseline_outcomes: dict[int, RuleRolloutOutcome] = {}
        frozen_outcomes: dict[int, RuleRolloutOutcome] = {}
        baseline_completed = 0
        frozen_completed = 0
        differing_branches = 0
        differing_public_states: set[str] = set()
        failure_status: SensitivityStatus | None = None

        for candidate_id in final_ids:
            if not _actual_game_matches_public(snapshot, sample.observation, legal) or _sample_public_signature(sample) != original_signature:
                failure_status = SensitivityStatus.SNAPSHOT_CHANGED
                break
            try:
                baseline_branch = deepcopy(snapshot)
                frozen_branch = deepcopy(snapshot)
            except Exception:
                failure_status = SensitivityStatus.ROLLOUT_CLONE_INVALID
                break
            if (
                baseline_branch is snapshot
                or frozen_branch is snapshot
                or baseline_branch is frozen_branch
                or not _actual_game_matches_public(baseline_branch, sample.observation, legal)
                or not _actual_game_matches_public(frozen_branch, sample.observation, legal)
            ):
                failure_status = SensitivityStatus.ROLLOUT_CLONE_INVALID
                break
            try:
                baseline_outcome = _rollout(baseline_branch, candidate_id, player_id, MAX_ROLLOUT_STEPS)
            except Exception:
                failure_status = SensitivityStatus.BASELINE_ROLLOUT_FAILURE
                break
            baseline_failure = _valid_rollout_outcome(baseline_outcome)
            if baseline_failure is not None:
                failure_status = (
                    SensitivityStatus.BASELINE_ROLLOUT_FAILURE
                    if baseline_failure not in (CalibrationStatus.ROLLOUT_INCOMPLETE, CalibrationStatus.ROLLOUT_RESULT_INVALID, CalibrationStatus.ROLLOUT_STEP_COUNT_INVALID)
                    else SensitivityStatus(baseline_failure.value)
                )
                break
            baseline_completed += 1
            # The other clone must remain at the shared initial snapshot after
            # the baseline branch has already advanced to its terminal state.
            if not _actual_game_matches_public(frozen_branch, sample.observation, legal):
                failure_status = SensitivityStatus.ROLLOUT_CLONE_INVALID
                break
            try:
                frozen_outcome, difference_signatures = _frozen_rollout(frozen_branch, candidate_id, player_id)
            except Exception:
                failure_status = SensitivityStatus.FROZEN_ROLLOUT_FAILURE
                break
            frozen_failure = _valid_rollout_outcome(frozen_outcome)
            if frozen_failure is not None:
                failure_status = (
                    SensitivityStatus.FROZEN_ROLLOUT_FAILURE
                    if frozen_failure not in (CalibrationStatus.ROLLOUT_INCOMPLETE, CalibrationStatus.ROLLOUT_RESULT_INVALID, CalibrationStatus.ROLLOUT_STEP_COUNT_INVALID)
                    else SensitivityStatus(frozen_failure.value)
                )
                break
            frozen_completed += 1
            if not isinstance(difference_signatures, tuple) or any(not isinstance(value, str) for value in difference_signatures):
                failure_status = SensitivityStatus.ROLLOUT_RESULT_INVALID
                break
            if difference_signatures:
                differing_branches += 1
                differing_public_states.update(difference_signatures)
            baseline_outcomes[candidate_id] = baseline_outcome
            frozen_outcomes[candidate_id] = frozen_outcome
            if not _actual_game_matches_public(snapshot, sample.observation, legal) or _sample_public_signature(sample) != original_signature:
                failure_status = SensitivityStatus.SNAPSHOT_CHANGED
                break

        if failure_status is not None:
            all_differing_public_states.update(differing_public_states)
            results.append(_state_result(
                sample, failure_status, sample_name=sample_name,
                baseline_completed=baseline_completed, frozen_completed=frozen_completed,
                differing_branches=differing_branches, differing_states=len(differing_public_states),
                reference_visible=True,
            ))
            failed = True
            continue

        if len(baseline_outcomes) != len(final_ids) or len(frozen_outcomes) != len(final_ids):
            all_differing_public_states.update(differing_public_states)
            results.append(_state_result(
                sample, SensitivityStatus.ROLLOUT_RESULT_INVALID, sample_name=sample_name,
                baseline_completed=baseline_completed, frozen_completed=frozen_completed,
                differing_branches=differing_branches, differing_states=len(differing_public_states),
                reference_visible=True,
            ))
            failed = True
            continue

        matrix = _empty_matrix()
        changed = reversals = reference_ties = 0
        comparison_failed = False
        for candidate_id in final_ids:
            try:
                baseline_pair = _labels(baseline_outcomes[reference_id], baseline_outcomes[candidate_id])
                frozen_pair = _labels(frozen_outcomes[reference_id], frozen_outcomes[candidate_id])
            except Exception:
                comparison_failed = True
                break
            if baseline_pair is None or frozen_pair is None:
                comparison_failed = True
                break
            baseline_label, _baseline_raw = baseline_pair
            frozen_label, _frozen_raw = frozen_pair
            matrix[_LABELS.index(baseline_label)][_LABELS.index(frozen_label)] += 1
            if baseline_label != frozen_label:
                changed += 1
            if (baseline_label, frozen_label) in (("better", "worse"), ("worse", "better")):
                reversals += 1
            if candidate_id == reference_id:
                if baseline_label != "tie" or frozen_label != "tie":
                    comparison_failed = True
                    break
                reference_ties += 1
        if comparison_failed or reference_ties != 1 or sum(sum(row) for row in matrix) != len(final_ids):
            all_differing_public_states.update(differing_public_states)
            results.append(_state_result(
                sample, SensitivityStatus.COMPARISON_INVALID, sample_name=sample_name,
                baseline_completed=baseline_completed, frozen_completed=frozen_completed,
                differing_branches=differing_branches, differing_states=len(differing_public_states),
                reference_visible=True,
            ))
            failed = True
            continue
        all_differing_public_states.update(differing_public_states)
        results.append(_state_result(
            sample, SensitivityStatus.READY, sample_name=sample_name,
            baseline_completed=baseline_completed, frozen_completed=frozen_completed,
            paired_completed=len(final_ids), matrix=matrix, changed=changed, reversals=reversals,
            differing_branches=differing_branches, differing_states=len(differing_public_states),
            reference_ties=reference_ties, reference_visible=True,
        ))

    complete = (
        len(results) == 12
        and all(row.status is SensitivityStatus.READY for row in results)
        and sum(row.final_candidate_count for row in results)
        == expected_final_total
        and sum(row.paired_completed_candidate_count for row in results)
        == expected_final_total
        and sum(row.reference_tied_in_both_count for row in results) == 12
    )
    status = SensitivityStatus.READY if complete else SensitivityStatus.INCOMPLETE
    return SensitivityReport(status, tuple(results), len(all_differing_public_states))


def evaluate_h3_a11_sensitivity(*, advisor: RAGAdvisor | None = None) -> SensitivityReport:
    """Rebuild the exact H3-A8/A9 queues and evaluate continuation sensitivity."""
    try:
        rag_advisor = advisor or _h3_advisor()
        h3_a8 = build_replayable_quality_samples(advisor=rag_advisor)
        h3_a9 = build_h3_a9_quality_samples(advisor=rag_advisor)
    except Exception:
        return SensitivityReport(SensitivityStatus.SAMPLE_SET_INVALID)
    return evaluate_h3_a11_sample_sets(h3_a8, h3_a9)
