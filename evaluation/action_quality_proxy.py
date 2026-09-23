"""Small, deterministic same-state action-quality proxy for offline evaluation.

The injected provider sees only an engine-produced public observation, its
complete canonical legal actions, and the actions actually assembled by the
production DeepSeek client.  Engine snapshots remain private to this module
and are used only to run independent local continuations.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
import json

from agents.base import require_legal_action_id
from agents.deepseek_client import DeepSeekClient, PROMPT_MAX_CANDIDATE_ACTIONS
from agents.game_phase import ENDGAME_PHASES, MIDGAME, OPENING, classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.h3_model_probe_fixtures import (
    ProbeFixture,
    _RecordingDeepSeekClient,
    _advisor as _h3_advisor,
    _run_projection,
    build_h3_model_probe_opening_fixtures,
)
from evaluation.strategy_intent_action_quality import (
    RuleRolloutOutcome,
    _compare_quality,
    _rollout,
)


MAX_ROLLOUT_STEPS = 5000
SAMPLE_SEEDS = tuple(range(900, 920))
SAMPLE_COUNT = 6


class SampleSetStage(StrEnum):
    READY = "ready"
    OPENING_FIXTURE_INVALID = "opening_fixture_invalid"
    MIDGAME_SAMPLE_MISSING = "midgame_sample_missing"
    ENDGAME_SAMPLE_MISSING = "endgame_sample_missing"
    DUPLICATE_STATE = "duplicate_state"
    MODEL_PATH_INVALID = "model_path_invalid"


class Comparison(StrEnum):
    SELECTED_BETTER = "selected_better"
    REFERENCE_BETTER = "reference_better"
    TIE = "tie"
    UNEVALUABLE = "unevaluable"


@dataclass(frozen=True, slots=True)
class ProviderInput:
    """Public inputs delivered to a test provider; no engine snapshot/prompt."""

    observation: dict[str, object] = field(repr=False)
    legal_actions: list[dict[str, object]] = field(repr=False)
    final_candidates: list[dict[str, object]] = field(repr=False)


ActionIdProvider = Callable[[ProviderInput], object]


@dataclass(frozen=True, slots=True)
class ReplayableQualitySample:
    name: str
    phase: str
    canonical_candidate_count: int
    final_candidate_count: int
    observation: dict[str, object] = field(repr=False, compare=False)
    legal_actions: list[dict[str, object]] = field(repr=False, compare=False)
    game_snapshot: GuanDanGame = field(repr=False, compare=False)
    source_seed: int | None = field(default=None, repr=False, compare=False)
    final_candidate_ids: tuple[int, ...] = field(default=(), repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "phase": self.phase,
            "canonical_candidate_count": self.canonical_candidate_count,
            "final_candidate_count": self.final_candidate_count,
        }


@dataclass(frozen=True, slots=True)
class SampleSetResult:
    stage: SampleSetStage
    samples: tuple[ReplayableQualitySample, ...]

    @property
    def ready(self) -> bool:
        return self.stage is SampleSetStage.READY and len(self.samples) == SAMPLE_COUNT

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "sample_count": len(self.samples),
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class BranchQuality:
    completed: bool
    team_outcome: str | None
    team_rank_sum: int | None
    continuation_steps: int

    def to_dict(self) -> dict[str, object]:
        return {
            "completed": self.completed,
            "team_outcome": self.team_outcome,
            "team_rank_sum": self.team_rank_sum,
            "continuation_steps": self.continuation_steps,
        }


@dataclass(frozen=True, slots=True)
class ActionQualityResult:
    sample_name: str
    phase: str
    canonical_candidate_count: int
    final_candidate_count: int
    reference_action_in_model_candidates: bool
    selected: BranchQuality
    reference: BranchQuality
    comparison: Comparison
    failure_code: str | None
    same_action_reused: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_name": self.sample_name,
            "phase": self.phase,
            "canonical_candidate_count": self.canonical_candidate_count,
            "final_candidate_count": self.final_candidate_count,
            "reference_action_in_model_candidates": self.reference_action_in_model_candidates,
            "selected": self.selected.to_dict(),
            "reference": self.reference.to_dict(),
            "comparison": self.comparison.value,
            "failure_code": self.failure_code,
            "same_action_reused": self.same_action_reused,
        }


@dataclass(frozen=True, slots=True)
class ActionQualityReport:
    sample_set_stage: SampleSetStage
    results: tuple[ActionQualityResult, ...]

    @property
    def completed_sample_count(self) -> int:
        return sum(result.selected.completed and result.reference.completed for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "proxy_kind": "frozen_rule_based_continuation_not_win_rate",
            "sample_set_stage": self.sample_set_stage.value,
            "sample_count": len(self.results),
            "completed_sample_count": self.completed_sample_count,
            "comparison_counts": {
                value.value: sum(result.comparison is value for result in self.results)
                for value in Comparison
            },
            "results": [result.to_dict() for result in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


@dataclass(frozen=True, slots=True)
class _ModelSelection:
    action_id: int | None
    reference_action_id: int | None
    final_action_ids: tuple[int, ...]
    failure_code: str | None


def _reference_action_id(observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int | None:
    info = observation.get("my_info")
    player_id = info.get("player_id") if isinstance(info, Mapping) else None
    if type(player_id) is not int or not 1 <= player_id <= 4:
        return None
    try:
        reference = RuleBasedAIAgent(player_id=player_id).select_action(observation, legal_actions)
        return require_legal_action_id(reference, legal_actions)
    except Exception:
        return None


def _actual_game_matches_public(
    game: GuanDanGame,
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
) -> bool:
    try:
        return game.observe() == observation and game.legal_actions() == legal_actions
    except Exception:
        return False


def _invoke_model_path(
    game: GuanDanGame,
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    provider: ActionIdProvider,
    advisor: RAGAdvisor,
) -> _ModelSelection:
    if not _actual_game_matches_public(game, observation, legal_actions):
        return _ModelSelection(None, None, (), "snapshot_public_mismatch")
    info = observation.get("my_info")
    player_id = info.get("player_id") if isinstance(info, Mapping) else None
    if type(player_id) is not int or not 1 <= player_id <= 4:
        return _ModelSelection(None, None, (), "player_invalid")
    # Freeze the RuleBased reference before the injected provider is invoked.
    reference_id = _reference_action_id(observation, legal_actions)
    if reference_id is None:
        return _ModelSelection(None, None, (), "reference_action_invalid")

    def dispatch_provider(
        public_observation: dict[str, object],
        canonical_actions: list[dict[str, object]],
        final_candidates: list[dict[str, object]],
    ) -> object:
        return provider(ProviderInput(public_observation, canonical_actions, final_candidates))

    fixture = ProbeFixture(
        "action_quality_proxy",
        deepcopy(observation),
        deepcopy(legal_actions),
        game_snapshot=game,
    )
    client_factory = lambda: _RecordingDeepSeekClient(selection_provider=dispatch_provider)
    try:
        agent, client, chosen = _run_projection(fixture, advisor, client_factory=client_factory)
    except Exception:
        return _ModelSelection(None, reference_id, (), "model_pipeline_failure")
    transport = client.transport
    failure = transport.failure_code
    if client._max_retries != 0:  # the offline path must never retry
        failure = "retry_configuration_invalid"
    if transport.calls != 1:
        failure = failure or "model_path_not_reached"
    final_actions = client.final_actions
    candidate_ids: tuple[object, ...] = tuple(item.get("action_id") for item in final_actions)
    final_ids = tuple(action_id for action_id in candidate_ids if type(action_id) is int)
    if (
        client.calls != 1
        or transport.calls != 1
        or client.provider_call_count != 1
    ):
        failure = failure or "model_path_call_count"
    if (
        not transport.envelope_valid
        or client.final_prompt is None
        or transport.user_prompt != client.final_prompt
    ):
        failure = failure or "request_body_binding_invalid"
    if final_actions:
        canonical = DeepSeekClient._canonical_subset_actions(legal_actions, final_actions)
        raw_ids = {item.get("action_id") for item in legal_actions if type(item.get("action_id")) is int}
        signatures = tuple(DeepSeekClient._action_signature(item) for item in final_actions)
        body_ids = transport.prompt_action_ids
        if (
            canonical is None
            or len(final_actions) > PROMPT_MAX_CANDIDATE_ACTIONS
            or any(type(action_id) is not int for action_id in candidate_ids)
            or len(candidate_ids) != len(set(candidate_ids))
            or len(signatures) != len(set(signatures))
            or any(action_id not in raw_ids for action_id in candidate_ids)
            or len(body_ids) != len(candidate_ids)
            or len(body_ids) != len(set(body_ids))
            or any(type(action_id) is not int for action_id in body_ids)
            or set(candidate_ids) != set(body_ids)
            or client.displayed_actions != final_actions
        ):
            failure = failure or "final_candidate_closure"
    else:
        failure = failure or "final_candidates_missing"
    if len(final_actions) < 2:
        failure = failure or "insufficient_final_candidates"
    raw_selected = client.provider_action_id
    selected_is_int = type(raw_selected) is int
    if not selected_is_int or raw_selected not in final_ids:
        failure = failure or "provider_action_not_in_final_candidates"
    if type(chosen) is not int or chosen != raw_selected:
        failure = failure or "selected_action_mismatch"
    source_is_model = agent.last_decision_source == "model"
    if not source_is_model:
        failure = failure or "decision_source_mismatch"
    if not _actual_game_matches_public(game, observation, legal_actions):
        failure = failure or "snapshot_changed"
    return _ModelSelection(
        action_id=chosen if type(chosen) is int else None,
        reference_action_id=reference_id,
        final_action_ids=final_ids,
        failure_code=failure,
    )


def _first_candidate_provider(request: ProviderInput) -> object:
    if not request.final_candidates:
        return None
    return request.final_candidates[0].get("action_id")


def _make_sample(
    *,
    name: str,
    phase: str,
    game: GuanDanGame,
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    source_seed: int | None,
    advisor: RAGAdvisor,
) -> tuple[ReplayableQualitySample | None, str | None]:
    selection = _invoke_model_path(game, observation, legal_actions, _first_candidate_provider, advisor)
    if selection.failure_code in {"model_path_not_reached", "insufficient_final_candidates"}:
        return None, None
    if selection.failure_code is not None:
        return None, selection.failure_code
    if selection.action_id is None or selection.reference_action_id is None:
        return None, "model_selection_invalid"
    return ReplayableQualitySample(
        name=name,
        phase=phase,
        canonical_candidate_count=len(legal_actions),
        final_candidate_count=len(selection.final_action_ids),
        observation=deepcopy(observation),
        legal_actions=deepcopy(legal_actions),
        game_snapshot=deepcopy(game),
        source_seed=source_seed,
        final_candidate_ids=selection.final_action_ids,
    ), None


def _opening_sample(fixture: ProbeFixture, advisor: RAGAdvisor) -> tuple[ReplayableQualitySample | None, str | None]:
    game = fixture.game_snapshot
    if game is None or not _actual_game_matches_public(game, fixture.observation, fixture.legal_actions):
        return None, "opening_snapshot_invalid"
    observation = fixture.observation
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    history = observation.get("history")
    others = observation.get("other_players")
    if (
        not isinstance(my_info, Mapping)
        or my_info.get("player_id") != 1
        or my_info.get("hand_count") != 27
        or not isinstance(current_round, Mapping)
        or current_round.get("step_no") != 0
        or current_round.get("current_level_rank") != "2"
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
        or not isinstance(history, Mapping)
        or history.get("actions") != []
        or history.get("finish_order") != []
        or not isinstance(others, list)
        or len(others) != 3
        or any(not isinstance(item, Mapping) or item.get("hand_count") != 27 for item in others)
        or sum([int(my_info["hand_count"]), *(int(item["hand_count"]) for item in others if isinstance(item, Mapping))]) != 108
        or classify_game_phase(observation).phase != OPENING
        or sum(action.get("declared_pattern") != "pass" for action in fixture.legal_actions) < 2
    ):
        return None, "opening_public_qualification"
    return _make_sample(
        name=f"opening_{fixture.name}",
        phase=OPENING,
        game=game,
        observation=fixture.observation,
        legal_actions=fixture.legal_actions,
        source_seed=None,
        advisor=advisor,
    )


def _first_seed_sample(
    seed: int,
    target: str,
    advisor: RAGAdvisor,
) -> tuple[ReplayableQualitySample | None, str | None]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    initial = game.reset()
    initial_info = initial.get("my_info")
    initial_round = initial.get("current_round")
    initial_history = initial.get("history")
    initial_others = initial.get("other_players")
    if (
        not isinstance(initial_info, Mapping)
        or initial_info.get("player_id") != 1
        or initial_info.get("hand_count") != 27
        or not isinstance(initial_round, Mapping)
        or initial_round.get("step_no") != 0
        or initial_round.get("current_level_rank") != "2"
        or initial_round.get("constraint") != "free"
        or not isinstance(initial_history, Mapping)
        or initial_history.get("actions") != []
        or initial_history.get("finish_order") != []
        or not isinstance(initial_others, list)
        or len(initial_others) != 3
        or any(not isinstance(item, Mapping) or item.get("hand_count") != 27 for item in initial_others)
        or sum([int(initial_info["hand_count"]), *(int(item["hand_count"]) for item in initial_others if isinstance(item, Mapping))]) != 108
    ):
        return None, "seed_initial_deal_invalid"
    agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
    for _step in range(MAX_ROLLOUT_STEPS):
        observation = game.observe()
        legal_actions = game.legal_actions()
        my_info = observation.get("my_info")
        player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
        phase = classify_game_phase(observation).phase
        if (
            player_id == 1
            and (phase == MIDGAME if target == MIDGAME else phase in ENDGAME_PHASES)
            and sum(action.get("declared_pattern") != "pass" for action in legal_actions) >= 2
        ):
            sample, failure = _make_sample(
                name="midgame" if target == MIDGAME else "endgame",
                phase=phase,
                game=game,
                observation=observation,
                legal_actions=legal_actions,
                source_seed=seed,
                advisor=advisor,
            )
            if failure is not None:
                return None, failure
            if sample is not None:
                return sample, None
        if type(player_id) is not int or player_id not in agents:
            return None, "sample_player_invalid"
        try:
            action_id = require_legal_action_id(agents[player_id].select_action(observation, legal_actions), legal_actions)
            result = game.step(action_id)
        except Exception:
            return None, "sample_game_progress_failure"
        if result.get("game_over") is True:
            return None, None
    return None, "sample_game_step_limit"


def build_replayable_quality_samples(*, advisor: RAGAdvisor | None = None) -> SampleSetResult:
    """Build two complete openings plus earliest eligible seed-based states.

    The deterministic search never uses a fake/model-selected action to advance
    a game: every replay step is selected by the frozen RuleBased agent.
    """
    try:
        rag_advisor = advisor or _h3_advisor()
        opening_fixtures = build_h3_model_probe_opening_fixtures()
    except Exception:
        return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, ())
    samples: list[ReplayableQualitySample] = []
    if tuple(item.name for item in opening_fixtures) != ("low_cost_single", "neutral_soft_pair"):
        return SampleSetResult(SampleSetStage.OPENING_FIXTURE_INVALID, ())
    for fixture in opening_fixtures:
        try:
            sample, failure = _opening_sample(fixture, rag_advisor)
        except Exception:
            return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, tuple(samples))
        if failure is not None:
            return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, tuple(samples))
        if sample is None:
            return SampleSetResult(SampleSetStage.OPENING_FIXTURE_INVALID, tuple(samples))
        samples.append(sample)

    used_seeds: set[int] = set()
    for target, missing_stage in ((MIDGAME, SampleSetStage.MIDGAME_SAMPLE_MISSING), ("endgame_family", SampleSetStage.ENDGAME_SAMPLE_MISSING)):
        count = 0
        for seed in SAMPLE_SEEDS:
            if seed in used_seeds:
                continue
            try:
                sample, failure = _first_seed_sample(seed, target, rag_advisor)
            except Exception:
                return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, tuple(samples))
            if failure is not None:
                return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, tuple(samples))
            if sample is None:
                continue
            if any(
                item.observation == sample.observation and item.legal_actions == sample.legal_actions
                for item in samples
            ):
                return SampleSetResult(SampleSetStage.DUPLICATE_STATE, tuple(samples))
            if sample.source_seed is None or sample.source_seed in used_seeds:
                return SampleSetResult(SampleSetStage.DUPLICATE_STATE, tuple(samples))
            used_seeds.add(sample.source_seed)
            count += 1
            samples.append(
                ReplayableQualitySample(
                    name=f"{target}_{count}" if target == MIDGAME else f"endgame_{count}",
                    phase=sample.phase,
                    canonical_candidate_count=sample.canonical_candidate_count,
                    final_candidate_count=sample.final_candidate_count,
                    observation=sample.observation,
                    legal_actions=sample.legal_actions,
                    game_snapshot=sample.game_snapshot,
                    source_seed=sample.source_seed,
                    final_candidate_ids=sample.final_candidate_ids,
                )
            )
            if count == 2:
                break
        if count != 2:
            return SampleSetResult(missing_stage, tuple(samples))
    if len(samples) != SAMPLE_COUNT:
        return SampleSetResult(SampleSetStage.DUPLICATE_STATE, tuple(samples))
    signatures = [(item.observation, item.legal_actions) for item in samples]
    if any(signatures[index] == signatures[other] for index in range(len(signatures)) for other in range(index + 1, len(signatures))):
        return SampleSetResult(SampleSetStage.DUPLICATE_STATE, tuple(samples))
    return SampleSetResult(SampleSetStage.READY, tuple(samples))


def _branch_quality(outcome: RuleRolloutOutcome) -> BranchQuality:
    return BranchQuality(
        completed=outcome.complete,
        team_outcome=outcome.team_outcome if outcome.complete else None,
        team_rank_sum=outcome.team_placement_sum if outcome.complete else None,
        continuation_steps=outcome.rollout_step_count,
    )


def _unevaluable_result(
    sample: ReplayableQualitySample,
    *,
    final_count: int = 0,
    reference_visible: bool = False,
    failure_code: str,
) -> ActionQualityResult:
    empty = BranchQuality(False, None, None, 0)
    return ActionQualityResult(
        sample.name,
        sample.phase,
        sample.canonical_candidate_count,
        final_count,
        reference_visible,
        empty,
        empty,
        Comparison.UNEVALUABLE,
        failure_code,
        False,
    )


def evaluate_quality_sample(
    sample: ReplayableQualitySample,
    provider: ActionIdProvider,
    *,
    advisor: RAGAdvisor | None = None,
) -> ActionQualityResult:
    """Call the production client path offline, then compare two frozen rollouts."""
    if not _actual_game_matches_public(sample.game_snapshot, sample.observation, sample.legal_actions):
        return _unevaluable_result(sample, failure_code="snapshot_public_mismatch")
    canonical_ids = tuple(action.get("action_id") for action in sample.legal_actions)
    if (
        sample.canonical_candidate_count != len(sample.legal_actions)
        or sample.final_candidate_count != len(sample.final_candidate_ids)
        or not 2 <= sample.final_candidate_count <= PROMPT_MAX_CANDIDATE_ACTIONS
        or any(type(action_id) is not int for action_id in canonical_ids)
        or len(canonical_ids) != len(set(canonical_ids))
        or any(type(action_id) is not int for action_id in sample.final_candidate_ids)
        or len(sample.final_candidate_ids) != len(set(sample.final_candidate_ids))
        or not set(sample.final_candidate_ids).issubset(set(canonical_ids))
        or classify_game_phase(sample.observation).phase != sample.phase
    ):
        return _unevaluable_result(sample, failure_code="sample_metadata_invalid")
    info = sample.observation.get("my_info")
    player_id = info.get("player_id") if isinstance(info, Mapping) else None
    if type(player_id) is not int or not 1 <= player_id <= 4:
        return _unevaluable_result(sample, failure_code="player_invalid")
    # Reference action is frozen from the full canonical set before transport invokes provider.
    reference_id = _reference_action_id(sample.observation, sample.legal_actions)
    if reference_id is None:
        return _unevaluable_result(sample, failure_code="reference_action_invalid")
    selection = _invoke_model_path(
        sample.game_snapshot,
        sample.observation,
        sample.legal_actions,
        provider,
        advisor or _h3_advisor(),
    )
    reference_visible = reference_id in selection.final_action_ids
    if selection.failure_code is not None or selection.reference_action_id != reference_id:
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code=selection.failure_code or "reference_action_changed",
        )
    if (
        selection.final_action_ids != sample.final_candidate_ids
        or len(selection.final_action_ids) != sample.final_candidate_count
    ):
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code="final_candidate_set_changed",
        )
    selected_id = selection.action_id
    try:
        if type(selected_id) is not int or selected_id not in selection.final_action_ids:
            raise ValueError("selected_action_not_prompt_candidate")
        require_legal_action_id(selected_id, sample.legal_actions)
        require_legal_action_id(reference_id, sample.legal_actions)
    except Exception:
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code="action_legality_mismatch",
        )
    if not _actual_game_matches_public(sample.game_snapshot, sample.observation, sample.legal_actions):
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code="snapshot_changed",
        )
    try:
        selected_outcome = _rollout(
            deepcopy(sample.game_snapshot), selected_id, player_id, MAX_ROLLOUT_STEPS
        )
        if selected_id == reference_id:
            reference_outcome = selected_outcome
            same_action_reused = True
        else:
            reference_outcome = _rollout(
                deepcopy(sample.game_snapshot), reference_id, player_id, MAX_ROLLOUT_STEPS
            )
            same_action_reused = False
    except Exception:
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code="rollout_failure",
        )
    selected_branch = _branch_quality(selected_outcome)
    reference_branch = _branch_quality(reference_outcome)
    if any(
        type(outcome.rollout_step_count) is not int
        or not 1 <= outcome.rollout_step_count <= MAX_ROLLOUT_STEPS
        for outcome in (selected_outcome, reference_outcome)
    ):
        return _unevaluable_result(
            sample,
            final_count=len(selection.final_action_ids),
            reference_visible=reference_visible,
            failure_code="rollout_step_count_invalid",
        )
    if not selected_outcome.complete or not reference_outcome.complete:
        comparison = Comparison.UNEVALUABLE
        failure_code = "rollout_incomplete"
    elif selected_id == reference_id:
        comparison = Comparison.TIE
        failure_code = None
    else:
        # Existing helper compares (before, after); reference is baseline and selected is treatment.
        raw_comparison = _compare_quality(reference_outcome, selected_outcome)
        comparison = {
            "on_better": Comparison.SELECTED_BETTER,
            "off_better": Comparison.REFERENCE_BETTER,
            "tie": Comparison.TIE,
        }[raw_comparison]
        failure_code = None
    return ActionQualityResult(
        sample.name,
        sample.phase,
        sample.canonical_candidate_count,
        len(selection.final_action_ids),
        reference_visible,
        selected_branch,
        reference_branch,
        comparison,
        failure_code,
        same_action_reused,
    )


def evaluate_quality_samples(
    sample_set: SampleSetResult,
    provider: ActionIdProvider,
    *,
    advisor: RAGAdvisor | None = None,
) -> ActionQualityReport:
    if not sample_set.ready:
        return ActionQualityReport(sample_set.stage, ())
    rag_advisor = advisor or _h3_advisor()
    results = tuple(evaluate_quality_sample(sample, provider, advisor=rag_advisor) for sample in sample_set.samples)
    return ActionQualityReport(sample_set.stage, results)
