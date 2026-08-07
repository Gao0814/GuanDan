"""Aggregate-only paired action ablation for strategy-intent prompt payloads.

The caller supplies the provider.  This module never creates a model client,
reads configuration, or makes a network request.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Protocol

from agents.base import require_legal_action_id
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.game_phase import (
    CRITICAL_ENDGAME,
    ENDGAME,
    MIDGAME,
    NEAR_OPEN_ENDGAME,
    OPENING,
    GamePhaseContext,
    classify_game_phase,
)
from agents.hand_evaluator import evaluate_hand
from agents.strategy_intent_prompt import (
    StrategyIntentPromptPayload,
    build_strategy_intent_prompt_payload,
)
from agents.strategy_router import StrategyIntentContext, route_strategy_intent
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_PHASES = (MIDGAME, ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME)
_NORMAL_RANKS = frozenset({"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"})
_PRESSURE_PATTERNS = frozenset({"bomb", "straight_flush", "joker_bomb"})
_OUTCOMES = (
    "valid",
    "no_action",
    "exception",
    "malformed_result",
    "invalid_action_type",
    "outside_legal",
    "outside_prompt",
)


class SuggestionProvider(Protocol):
    """An injected model-compatible suggestion callable."""

    def __call__(self, **kwargs: object) -> DeepSeekSuggestion:
        ...


def _is_int(value: object) -> bool:
    return type(value) is int


def _positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


def _category(value: object) -> str:
    return str(value).split(":", 1)[0]


def _add_diagnostic(counter: Counter[str], *values: object) -> None:
    for category in {_category(value) for value in values if isinstance(value, str) and value}:
        counter[category] += 1


def _validate_inputs(
    seeds: Sequence[int],
    *,
    suggestion_provider: object,
    strategic_pass_rates: Sequence[int],
    samples_per_phase: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence")
    normalized_seeds = tuple(seeds)
    if any(not _is_int(seed) for seed in normalized_seeds) or len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must contain unique non-bool integers")
    if (
        isinstance(strategic_pass_rates, (str, bytes))
        or not isinstance(strategic_pass_rates, Sequence)
        or not strategic_pass_rates
    ):
        raise ValueError("strategic_pass_rates must be a non-empty sequence")
    rates = tuple(strategic_pass_rates)
    if (
        any(not _is_int(rate) or not 0 <= rate <= 100 for rate in rates)
        or len(set(rates)) != len(rates)
    ):
        raise ValueError("strategic_pass_rates must contain unique integers from 0 through 100")
    if not callable(suggestion_provider):
        raise ValueError("suggestion_provider must be callable")
    if not _positive_int(samples_per_phase) or samples_per_phase % 2:
        raise ValueError("samples_per_phase must be a positive even non-bool integer")
    if not isinstance(current_level_rank, str) or current_level_rank not in _NORMAL_RANKS:
        raise ValueError("current_level_rank must be a normal rank")
    if not _positive_int(max_steps) or not _positive_int(max_samples_per_phase_per_game):
        raise ValueError("limits must be positive non-bool integers")
    return normalized_seeds, rates


@dataclass(frozen=True, slots=True)
class StrategyIntentActionAblationBucket:
    only_pass_skip_count: int
    finishing_skip_count: int
    router_unavailable_skip_count: int
    router_invalid_skip_count: int
    payload_omitted_skip_count: int
    payload_invalid_skip_count: int
    insufficient_prompt_candidates_count: int
    prompt_mismatch_count: int
    qualified_candidate_count: int
    quota_not_selected_count: int
    selected_sample_count: int
    off_first_pair_count: int
    on_first_pair_count: int
    off_attempted_call_count: int
    on_attempted_call_count: int
    off_valid_response_count: int
    on_valid_response_count: int
    off_no_action_count: int
    on_no_action_count: int
    off_exception_count: int
    on_exception_count: int
    off_malformed_result_count: int
    on_malformed_result_count: int
    off_invalid_action_type_count: int
    on_invalid_action_type_count: int
    off_outside_legal_count: int
    on_outside_legal_count: int
    off_outside_prompt_count: int
    on_outside_prompt_count: int
    both_valid_pair_count: int
    only_off_valid_count: int
    only_on_valid_count: int
    neither_valid_count: int
    same_action_count: int
    changed_action_count: int
    off_pass_selection_count: int
    on_pass_selection_count: int
    off_pressure_selection_count: int
    on_pressure_selection_count: int
    prompt_pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        values = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "diagnostic_counts"
        }
        values["diagnostic_counts"] = dict(self.diagnostic_counts)
        return values


@dataclass(frozen=True, slots=True)
class PolicyStrategyIntentActionAblationReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    observed_turn_count: int
    opening_skip_count: int
    eligible_sample_count: int
    evaluated_sample_count: int
    duplicate_sample_count: int
    sample_limit_skipped_count: int
    overall: StrategyIntentActionAblationBucket
    by_phase: Mapping[str, StrategyIntentActionAblationBucket]
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_name": self.policy_name,
            "strategic_pass_rate": self.strategic_pass_rate,
            "strategic_pass_opportunity_count": self.strategic_pass_opportunity_count,
            "strategic_pass_count": self.strategic_pass_count,
            "requested_game_count": self.requested_game_count,
            "completed_game_count": self.completed_game_count,
            "incomplete_game_count": self.incomplete_game_count,
            "observed_turn_count": self.observed_turn_count,
            "opening_skip_count": self.opening_skip_count,
            "eligible_sample_count": self.eligible_sample_count,
            "evaluated_sample_count": self.evaluated_sample_count,
            "duplicate_sample_count": self.duplicate_sample_count,
            "sample_limit_skipped_count": self.sample_limit_skipped_count,
            "overall": self.overall.to_dict(),
            "by_phase": [self.by_phase[phase].to_dict() for phase in _PHASES],
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class StrategyIntentActionAblationReport:
    requested_policy_count: int
    current_level_rank: str
    max_steps: int
    max_samples_per_phase_per_game: int
    policies: tuple[PolicyStrategyIntentActionAblationReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "current_level_rank": self.current_level_rank,
            "max_steps": self.max_steps,
            "max_samples_per_phase_per_game": self.max_samples_per_phase_per_game,
            "policies": [policy.to_dict() for policy in self.policies],
        }


class _BucketAccumulator:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.diagnostics: Counter[str] = Counter()
        self.hasher = hashlib.sha256()

    def digest_pair(self, phase: str, off_prompt: str, on_prompt: str) -> None:
        encoded = json.dumps(
            [phase, off_prompt, on_prompt],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.hasher.update(encoded.encode("utf-8"))

    def freeze(self) -> StrategyIntentActionAblationBucket:
        names = StrategyIntentActionAblationBucket.__dataclass_fields__
        return StrategyIntentActionAblationBucket(
            **{name: self.counts[name] for name in names if name not in {"prompt_pair_sha256", "diagnostic_counts"}},
            prompt_pair_sha256=self.hasher.hexdigest(),
            diagnostic_counts=_freeze_counts(self.diagnostics),
        )


@dataclass(slots=True)
class _Candidate:
    priority_digest: str
    step_no: int
    observer_player_id: int
    phase: str
    observation: dict[str, object]
    legal_actions: list[dict[str, object]]
    prompt_actions: list[dict[str, object]]
    phase_context: GamePhaseContext
    hand_evaluation: dict[str, object]
    payload: StrategyIntentPromptPayload
    off_prompt: str
    on_prompt: str


def _only_pass(actions: Sequence[Mapping[str, object]]) -> bool:
    return bool(actions) and all(action.get("declared_pattern") == "pass" for action in actions)


def _has_finishing_action(actions: Sequence[Mapping[str, object]], hand_count: object) -> bool:
    return _positive_int(hand_count) and any(
        action.get("declared_pattern") != "pass"
        and isinstance(action.get("carrier_cards"), list)
        and len(action["carrier_cards"]) == hand_count
        for action in actions
    )


def _priority(policy_name: str, phase: str, seed: int, step_no: int, observer: int) -> str:
    raw = "|".join((policy_name, phase, str(seed), str(step_no), str(observer)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _router_available(value: object, phase: str) -> bool:
    return (
        type(value) is StrategyIntentContext
        and value.status == "available"
        and value.source == "public_strategy_router_v1"
        and value.phase == phase
        and value.diagnostics == ()
    )


def _payload_ready(value: object) -> bool:
    return (
        type(value) is StrategyIntentPromptPayload
        and value.status == "ready"
        and value.source == "strategy_intent_prompt_v1"
        and value.diagnostics == ()
        and isinstance(value.text, str)
        and bool(value.text)
        and _is_int(value.char_count)
        and value.char_count == len(value.text)
        and value.char_count <= 800
    )


def _prompt_actions(
    observation: Mapping[str, object],
    legal_actions: list[dict[str, object]],
    phase_context: GamePhaseContext,
) -> list[dict[str, object]]:
    current_round = observation.get("current_round")
    my_info = observation.get("my_info")
    if not isinstance(current_round, Mapping) or not isinstance(my_info, Mapping):
        return []
    constraint = current_round.get("constraint")
    step_no = current_round.get("step_no")
    hand_count = my_info.get("hand_count")
    if not isinstance(constraint, str):
        return []
    return DeepSeekClient._prune_legal_actions(
        legal_actions,
        constraint,
        step_no=step_no if _is_int(step_no) else 0,
        hand_count=hand_count if _is_int(hand_count) else None,
        phase_context=phase_context,
    )


def _build_prompt(
    observation: Mapping[str, object],
    prompt_actions: list[dict[str, object]],
    phase_context: GamePhaseContext,
    hand_evaluation: dict[str, object],
    payload: StrategyIntentPromptPayload | None,
) -> str:
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    other_players = observation.get("other_players")
    history = observation.get("history")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping):
        raise ValueError("malformed public observation")
    return DeepSeekClient._build_structured_prompt(
        my_info=dict(my_info),
        current_round=dict(current_round),
        other_players=list(other_players) if isinstance(other_players, list) else [],
        history=dict(history) if isinstance(history, Mapping) else {},
        legal_actions=prompt_actions,
        rag_context=None,
        hand_evaluation=hand_evaluation,
        card_tracking_summary=None,
        phase_context=phase_context,
        strategy_intent_prompt=payload,
    )


def _exact_prompt_pair(off_prompt: str, on_prompt: str, payload: StrategyIntentPromptPayload) -> bool:
    marker = "【场景标签】"
    expected = off_prompt.replace(marker, f"【策略意图】\n{payload.text}\n\n{marker}", 1)
    return (
        off_prompt.count(marker) == 1
        and "【策略意图】" not in off_prompt
        and on_prompt == expected
        and on_prompt.count("【策略意图】") == 1
        and on_prompt.count(payload.text) == 1
    )


def _legal_mapping(actions: Sequence[Mapping[str, object]]) -> dict[int, Mapping[str, object]]:
    result: dict[int, Mapping[str, object]] = {}
    for action in actions:
        action_id = action.get("action_id")
        if _is_int(action_id):
            result[action_id] = action
    return result


def _classify(
    result: object,
    legal_by_id: Mapping[int, Mapping[str, object]],
    prompt_ids: frozenset[int],
) -> tuple[str, int | None]:
    if type(result) is not DeepSeekSuggestion:
        return "malformed_result", None
    action_id = result.action_id
    if action_id is None:
        return "no_action", None
    if not _is_int(action_id):
        return "invalid_action_type", None
    if action_id not in legal_by_id:
        return "outside_legal", None
    if action_id not in prompt_ids:
        return "outside_prompt", None
    return "valid", action_id


def _call_provider(
    provider: Callable[..., object],
    kwargs: Mapping[str, object],
    legal_by_id: Mapping[int, Mapping[str, object]],
    prompt_ids: frozenset[int],
) -> tuple[str, int | None]:
    try:
        return _classify(provider(**kwargs), legal_by_id, prompt_ids)
    except Exception:
        return "exception", None


def _record_condition(
    accumulator: _BucketAccumulator,
    condition: str,
    outcome: str,
    action_id: int | None,
    legal_by_id: Mapping[int, Mapping[str, object]],
) -> bool:
    accumulator.counts[f"{condition}_attempted_call_count"] += 1
    if outcome != "valid" or action_id is None:
        accumulator.counts[f"{condition}_{outcome}_count"] += 1
        return False
    accumulator.counts[f"{condition}_valid_response_count"] += 1
    pattern = legal_by_id[action_id].get("declared_pattern")
    if pattern == "pass":
        accumulator.counts[f"{condition}_pass_selection_count"] += 1
    if pattern in _PRESSURE_PATTERNS:
        accumulator.counts[f"{condition}_pressure_selection_count"] += 1
    return True


def _record_pair(
    accumulator: _BucketAccumulator,
    candidate: _Candidate,
    provider: Callable[..., object],
    *,
    off_first: bool,
) -> None:
    legal_by_id = _legal_mapping(candidate.legal_actions)
    prompt_ids = frozenset(
        action_id
        for action_id in (action.get("action_id") for action in candidate.prompt_actions)
        if _is_int(action_id)
    )
    common = {
        "observation": candidate.observation,
        "legal_actions": candidate.legal_actions,
        "prompt_actions": candidate.prompt_actions,
        "rag_context": None,
        "hand_evaluation": candidate.hand_evaluation,
        "card_tracking_summary": None,
        "phase_context": candidate.phase_context,
        "verbose": False,
        "debug_prefix": "strategy_intent_ablation",
    }
    on_kwargs = {**common, "strategy_intent_prompt": candidate.payload}
    accumulator.digest_pair(candidate.phase, candidate.off_prompt, candidate.on_prompt)
    if off_first:
        accumulator.counts["off_first_pair_count"] += 1
        off = _call_provider(provider, common, legal_by_id, prompt_ids)
        on = _call_provider(provider, on_kwargs, legal_by_id, prompt_ids)
    else:
        accumulator.counts["on_first_pair_count"] += 1
        on = _call_provider(provider, on_kwargs, legal_by_id, prompt_ids)
        off = _call_provider(provider, common, legal_by_id, prompt_ids)
    off_valid = _record_condition(accumulator, "off", *off, legal_by_id)
    on_valid = _record_condition(accumulator, "on", *on, legal_by_id)
    if off_valid and on_valid:
        accumulator.counts["both_valid_pair_count"] += 1
        if off[1] == on[1]:
            accumulator.counts["same_action_count"] += 1
        else:
            accumulator.counts["changed_action_count"] += 1
    elif off_valid:
        accumulator.counts["only_off_valid_count"] += 1
    elif on_valid:
        accumulator.counts["only_on_valid_count"] += 1
    else:
        accumulator.counts["neither_valid_count"] += 1


def _merge(accumulators: Mapping[str, _BucketAccumulator]) -> _BucketAccumulator:
    combined = _BucketAccumulator()
    for phase in _PHASES:
        source = accumulators[phase]
        combined.counts.update(source.counts)
        combined.diagnostics.update(source.diagnostics)
        combined.hasher.update(source.hasher.digest())
    return combined


def _run_policy(
    seeds: tuple[int, ...],
    *,
    rate: int,
    suggestion_provider: Callable[..., object],
    samples_per_phase: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> PolicyStrategyIntentActionAblationReport:
    policy_name = _policy_name(rate)
    accumulators = {phase: _BucketAccumulator() for phase in _PHASES}
    candidates = {phase: [] for phase in _PHASES}
    seen: set[tuple[int, int, int]] = set()
    diagnostics: Counter[str] = Counter()
    observed = opening = eligible = evaluated = duplicate = limited = 0
    only_pass = finishing = complete = incomplete = opportunity = active = 0

    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {
            player_id: StrategicPassAIAgent(player_id=player_id, strategic_pass_rate=rate)
            for player_id in (1, 2, 3, 4)
        }
        per_game_phase = {phase: 0 for phase in _PHASES}
        done = False
        for _ in range(max_steps):
            observation = game.observe()
            legal_actions = game.legal_actions()
            observed += 1
            my_info = observation.get("my_info")
            if _only_pass(legal_actions):
                only_pass += 1
            elif _has_finishing_action(
                legal_actions,
                my_info.get("hand_count") if isinstance(my_info, Mapping) else None,
            ):
                finishing += 1
            else:
                phase_context = classify_game_phase(observation)
                phase = phase_context.phase
                if phase == OPENING:
                    opening += 1
                elif phase in _PHASES:
                    eligible += 1
                    current_round = observation.get("current_round")
                    observer = my_info.get("player_id") if isinstance(my_info, Mapping) else None
                    step_no = current_round.get("step_no") if isinstance(current_round, Mapping) else None
                    if not _is_int(observer) or not _is_int(step_no):
                        _add_diagnostic(diagnostics, "invalid_sample_identity")
                    elif (seed, step_no, observer) in seen:
                        duplicate += 1
                        _add_diagnostic(diagnostics, "duplicate_sample")
                    elif per_game_phase[phase] >= max_samples_per_phase_per_game:
                        limited += 1
                        _add_diagnostic(diagnostics, "sample_limit_reached")
                    else:
                        seen.add((seed, step_no, observer))
                        per_game_phase[phase] += 1
                        evaluated += 1
                        bucket = accumulators[phase]
                        try:
                            hand_evaluation = evaluate_hand(observation, legal_actions)
                            context = route_strategy_intent(
                                observation,
                                legal_actions,
                                phase_context=phase_context,
                                hand_evaluation=hand_evaluation,
                            )
                        except Exception:
                            bucket.counts["router_invalid_skip_count"] += 1
                            _add_diagnostic(bucket.diagnostics, "router_error")
                        else:
                            if type(context) is not StrategyIntentContext:
                                bucket.counts["router_invalid_skip_count"] += 1
                                _add_diagnostic(bucket.diagnostics, "invalid_router_result")
                            elif not _router_available(context, phase):
                                bucket.counts["router_unavailable_skip_count"] += 1
                                _add_diagnostic(bucket.diagnostics, *context.diagnostics)
                            else:
                                try:
                                    payload = build_strategy_intent_prompt_payload(context)
                                except Exception:
                                    bucket.counts["payload_invalid_skip_count"] += 1
                                    _add_diagnostic(bucket.diagnostics, "payload_error")
                                else:
                                    if type(payload) is not StrategyIntentPromptPayload:
                                        bucket.counts["payload_invalid_skip_count"] += 1
                                        _add_diagnostic(bucket.diagnostics, "invalid_payload_result")
                                    elif payload.status == "omitted":
                                        bucket.counts["payload_omitted_skip_count"] += 1
                                        _add_diagnostic(bucket.diagnostics, *payload.diagnostics)
                                    elif not _payload_ready(payload):
                                        bucket.counts["payload_invalid_skip_count"] += 1
                                        _add_diagnostic(bucket.diagnostics, "invalid_payload_result")
                                    else:
                                        prompt_actions = _prompt_actions(observation, legal_actions, phase_context)
                                        prompt_ids = {
                                            action.get("action_id")
                                            for action in prompt_actions
                                            if _is_int(action.get("action_id"))
                                        }
                                        if len(prompt_ids) < 2:
                                            bucket.counts["insufficient_prompt_candidates_count"] += 1
                                            _add_diagnostic(bucket.diagnostics, "insufficient_prompt_candidates")
                                        else:
                                            try:
                                                off_prompt = _build_prompt(
                                                    observation, prompt_actions, phase_context, hand_evaluation, None
                                                )
                                                on_prompt = _build_prompt(
                                                    observation, prompt_actions, phase_context, hand_evaluation, payload
                                                )
                                            except Exception:
                                                bucket.counts["prompt_mismatch_count"] += 1
                                                _add_diagnostic(bucket.diagnostics, "prompt_pair_mismatch")
                                            else:
                                                if not _exact_prompt_pair(off_prompt, on_prompt, payload):
                                                    bucket.counts["prompt_mismatch_count"] += 1
                                                    _add_diagnostic(bucket.diagnostics, "prompt_pair_mismatch")
                                                else:
                                                    bucket.counts["qualified_candidate_count"] += 1
                                                    candidates[phase].append(
                                                        _Candidate(
                                                            _priority(policy_name, phase, seed, step_no, observer),
                                                            step_no,
                                                            observer,
                                                            phase,
                                                            observation,
                                                            legal_actions,
                                                            prompt_actions,
                                                            phase_context,
                                                            hand_evaluation,
                                                            payload,
                                                            off_prompt,
                                                            on_prompt,
                                                        )
                                                    )
            player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            try:
                chosen = require_legal_action_id(agents[player_id].select_action(observation, legal_actions), legal_actions)  # type: ignore[index]
                result = game.step(chosen)
            except Exception:
                _add_diagnostic(diagnostics, "game_progress_error")
                break
            if result.get("game_over") is True:
                done = True
                break
        opportunity += sum(agent.strategic_pass_opportunity_count for agent in agents.values())
        active += sum(agent.strategic_pass_count for agent in agents.values())
        if done:
            complete += 1
        else:
            incomplete += 1
            _add_diagnostic(diagnostics, "max_steps_reached")

    for phase in _PHASES:
        ordered = sorted(candidates[phase], key=lambda item: (item.priority_digest, item.step_no, item.observer_player_id))
        selected = ordered[:samples_per_phase]
        bucket = accumulators[phase]
        bucket.counts["quota_not_selected_count"] = len(ordered) - len(selected)
        for index, candidate in enumerate(selected):
            bucket.counts["selected_sample_count"] += 1
            _record_pair(bucket, candidate, suggestion_provider, off_first=(index % 2 == 0))

    overall = _merge(accumulators)
    return PolicyStrategyIntentActionAblationReport(
        policy_name=policy_name,
        strategic_pass_rate=rate,
        strategic_pass_opportunity_count=opportunity,
        strategic_pass_count=active,
        requested_game_count=len(seeds),
        completed_game_count=complete,
        incomplete_game_count=incomplete,
        observed_turn_count=observed,
        opening_skip_count=opening,
        eligible_sample_count=eligible,
        evaluated_sample_count=evaluated,
        duplicate_sample_count=duplicate,
        sample_limit_skipped_count=limited,
        overall=overall.freeze(),
        by_phase=MappingProxyType({phase: accumulators[phase].freeze() for phase in _PHASES}),
        diagnostic_counts=_freeze_counts(diagnostics),
    )


def run_strategy_intent_action_ablation(
    seeds: Sequence[int],
    *,
    suggestion_provider: Callable[..., object],
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    samples_per_phase: int = 4,
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_phase_per_game: int = 128,
) -> StrategyIntentActionAblationReport:
    """Collect aggregate-only paired off/on strategy-intent response evidence."""

    normalized_seeds, rates = _validate_inputs(
        seeds,
        suggestion_provider=suggestion_provider,
        strategic_pass_rates=strategic_pass_rates,
        samples_per_phase=samples_per_phase,
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game,
    )
    return StrategyIntentActionAblationReport(
        requested_policy_count=len(rates),
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game,
        policies=tuple(
            _run_policy(
                normalized_seeds,
                rate=rate,
                suggestion_provider=suggestion_provider,
                samples_per_phase=samples_per_phase,
                current_level_rank=current_level_rank,
                max_steps=max_steps,
                max_samples_per_phase_per_game=max_samples_per_phase_per_game,
            )
            for rate in rates
        ),
    )
