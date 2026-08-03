"""Repeatable public-only distribution benchmark for strategy-router intents.

This module drives deterministic evaluation policy games, but never feeds a
route back into the acting agents.  Reports retain only aggregate counts.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from agents.base import require_legal_action_id
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
from agents.strategy_router import (
    BLOCK_OPPONENT,
    CONTROL,
    RUN_OUT,
    SUPPORT_TEAMMATE,
    StrategyIntentContext,
    route_strategy_intent,
)
from engine.cards import RANKS
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_ROUTED_PHASES = (MIDGAME, ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME)
_INTENTS = (RUN_OUT, BLOCK_OPPONENT, SUPPORT_TEAMMATE, CONTROL)
_RELATIONS = ("none", "teammate", "opponent")
_SOURCE = "public_strategy_router_v1"
_REASONS_BY_INTENT = {
    RUN_OUT: frozenset({"can_finish_now", "weak_hand"}),
    BLOCK_OPPONENT: frozenset({
        "urgent_opponent_controls_table",
        "opponent_more_urgent",
        "urgency_tie_block_opponent",
        "opponent_urgent",
    }),
    SUPPORT_TEAMMATE: frozenset({
        "teammate_controls_table",
        "teammate_more_urgent",
        "teammate_urgent",
    }),
    CONTROL: frozenset({"stable_control"}),
}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _freeze_counts(values: Mapping[str, int], *, fixed_keys: Sequence[str] = ()) -> Mapping[str, int]:
    result = {key: int(values.get(key, 0)) for key in fixed_keys}
    result.update({key: int(values[key]) for key in sorted(values) if key not in result})
    return MappingProxyType(result)


def _diagnostic_category(value: object) -> str:
    return str(value).split(":", 1)[0]


def _add_diagnostics(counts: Counter[str], diagnostics: Sequence[object]) -> None:
    """Count each normalized diagnostic category no more than once per event."""

    counts.update({_diagnostic_category(item) for item in diagnostics})


def _validate_inputs(
    seeds: Sequence[int],
    *,
    current_level_rank: str,
    strategic_pass_rates: Sequence[int],
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    normalized_seeds = tuple(seeds)
    if any(not _is_int(seed) for seed in normalized_seeds) or len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must be unique non-bool integers")
    if not isinstance(current_level_rank, str) or current_level_rank not in RANKS:
        raise ValueError("current_level_rank must be a supported normal rank")
    if (
        isinstance(strategic_pass_rates, (str, bytes))
        or not isinstance(strategic_pass_rates, Sequence)
        or not strategic_pass_rates
    ):
        raise ValueError("strategic_pass_rates must be a non-empty sequence")
    rates = tuple(strategic_pass_rates)
    if any(not _is_int(rate) or not 0 <= rate <= 100 for rate in rates) or len(set(rates)) != len(rates):
        raise ValueError("strategic_pass_rates must be unique integers from 0 to 100")
    for name, value in (
        ("max_steps", max_steps),
        ("max_samples_per_phase_per_game", max_samples_per_phase_per_game),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")
    return normalized_seeds, rates


def _only_pass(legal_actions: list[dict[str, object]]) -> bool:
    return bool(legal_actions) and all(action.get("declared_pattern") == "pass" for action in legal_actions)


def _has_finishing_action(legal_actions: list[dict[str, object]], hand_count: object) -> bool:
    if not _is_positive_int(hand_count):
        return False
    return any(
        action.get("declared_pattern") != "pass"
        and isinstance(action.get("carrier_cards"), list)
        and len(action["carrier_cards"]) == hand_count
        for action in legal_actions
    )


@dataclass(slots=True)
class _BucketAccumulator:
    sample_count: int = 0
    available_count: int = 0
    unavailable_count: int = 0
    invalid_count: int = 0
    intent_counts: Counter[str] = field(default_factory=Counter)
    reason_counts: Counter[str] = field(default_factory=Counter)
    relation_counts: Counter[str] = field(default_factory=Counter)
    free_lead_count: int = 0
    follow_count: int = 0
    weak_count: int = 0
    non_weak_count: int = 0
    diagnostic_counts: Counter[str] = field(default_factory=Counter)

    def record_available(self, context: StrategyIntentContext) -> None:
        relation = "none" if context.table_leader_relation is None else context.table_leader_relation
        self.sample_count += 1
        self.available_count += 1
        self.intent_counts[context.intent] += 1  # type: ignore[index]
        self.reason_counts[context.reason_codes[0]] += 1
        self.relation_counts[relation] += 1
        if context.is_free_lead:
            self.free_lead_count += 1
        else:
            self.follow_count += 1
        if context.hand_strength == "weak":
            self.weak_count += 1
        else:
            self.non_weak_count += 1

    def record_unavailable(self, diagnostics: Sequence[object]) -> None:
        self.sample_count += 1
        self.unavailable_count += 1
        _add_diagnostics(self.diagnostic_counts, diagnostics or ("router_unavailable",))

    def record_invalid(self, diagnostic: str) -> None:
        self.sample_count += 1
        self.invalid_count += 1
        _add_diagnostics(self.diagnostic_counts, (diagnostic,))

    def add(self, other: _BucketAccumulator) -> None:
        self.sample_count += other.sample_count
        self.available_count += other.available_count
        self.unavailable_count += other.unavailable_count
        self.invalid_count += other.invalid_count
        self.intent_counts.update(other.intent_counts)
        self.reason_counts.update(other.reason_counts)
        self.relation_counts.update(other.relation_counts)
        self.free_lead_count += other.free_lead_count
        self.follow_count += other.follow_count
        self.weak_count += other.weak_count
        self.non_weak_count += other.non_weak_count
        self.diagnostic_counts.update(other.diagnostic_counts)


@dataclass(frozen=True, slots=True)
class StrategyRouteBucket:
    bucket_name: str
    sample_count: int
    available_count: int
    unavailable_count: int
    invalid_count: int
    intent_counts: Mapping[str, int]
    reason_counts: Mapping[str, int]
    table_leader_relation_counts: Mapping[str, int]
    free_lead_count: int
    follow_count: int
    weak_count: int
    non_weak_count: int
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "bucket_name": self.bucket_name,
            "sample_count": self.sample_count,
            "available_count": self.available_count,
            "unavailable_count": self.unavailable_count,
            "invalid_count": self.invalid_count,
            "intent_counts": dict(self.intent_counts),
            "reason_counts": dict(self.reason_counts),
            "table_leader_relation_counts": dict(self.table_leader_relation_counts),
            "free_lead_count": self.free_lead_count,
            "follow_count": self.follow_count,
            "weak_count": self.weak_count,
            "non_weak_count": self.non_weak_count,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class PolicyStrategyRouteReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    observed_turn_count: int
    only_pass_skipped_count: int
    finishing_skipped_count: int
    opening_skipped_count: int
    eligible_sample_count: int
    evaluated_sample_count: int
    duplicate_sample_count: int
    sample_limit_skipped_count: int
    overall: StrategyRouteBucket
    by_phase: Mapping[str, StrategyRouteBucket]
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
            "only_pass_skipped_count": self.only_pass_skipped_count,
            "finishing_skipped_count": self.finishing_skipped_count,
            "opening_skipped_count": self.opening_skipped_count,
            "eligible_sample_count": self.eligible_sample_count,
            "evaluated_sample_count": self.evaluated_sample_count,
            "duplicate_sample_count": self.duplicate_sample_count,
            "sample_limit_skipped_count": self.sample_limit_skipped_count,
            "overall": self.overall.to_dict(),
            "by_phase": [self.by_phase[phase].to_dict() for phase in _ROUTED_PHASES],
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class StrategyRouterBenchmarkReport:
    requested_policy_count: int
    current_level_rank: str
    max_steps: int
    max_samples_per_phase_per_game: int
    policies: tuple[PolicyStrategyRouteReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "current_level_rank": self.current_level_rank,
            "max_steps": self.max_steps,
            "max_samples_per_phase_per_game": self.max_samples_per_phase_per_game,
            "policies": [policy.to_dict() for policy in self.policies],
        }


def _freeze_bucket(name: str, accumulator: _BucketAccumulator) -> StrategyRouteBucket:
    return StrategyRouteBucket(
        bucket_name=name,
        sample_count=accumulator.sample_count,
        available_count=accumulator.available_count,
        unavailable_count=accumulator.unavailable_count,
        invalid_count=accumulator.invalid_count,
        intent_counts=_freeze_counts(accumulator.intent_counts, fixed_keys=_INTENTS),
        reason_counts=_freeze_counts(accumulator.reason_counts),
        table_leader_relation_counts=_freeze_counts(accumulator.relation_counts, fixed_keys=_RELATIONS),
        free_lead_count=accumulator.free_lead_count,
        follow_count=accumulator.follow_count,
        weak_count=accumulator.weak_count,
        non_weak_count=accumulator.non_weak_count,
        diagnostic_counts=_freeze_counts(accumulator.diagnostic_counts),
    )


def _strict_bool(value: object) -> bool:
    return type(value) is bool


def _valid_leader_id(value: object) -> bool:
    return _is_int(value) and 1 <= value <= 4


def _valid_diagnostic(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    category = value.split(":", 1)[0]
    return bool(category.strip())


def _validate_router_context(
    context: object,
    *,
    expected_phase: str,
) -> str | None:
    """Return the sole accepted context status, otherwise fail closed.

    This deliberately checks only the serialized router output contract used by
    this benchmark.  It does not derive a replacement intent from observations.
    """

    if type(context) is not StrategyIntentContext:
        return None
    if (
        context.source != _SOURCE
        or context.phase != expected_phase
        or context.status not in {"available", "unavailable"}
        or type(context.reason_codes) is not tuple
        or type(context.urgent_opponent_ids) is not tuple
        or type(context.diagnostics) is not tuple
        or not all(
            _strict_bool(value)
            for value in (
                context.can_finish_now,
                context.is_free_lead,
                context.table_leader_is_urgent,
            )
        )
    ):
        return None
    if context.status == "available":
        return "available" if _available_context_is_well_formed(context) else None
    return "unavailable" if _unavailable_context_is_well_formed(context) else None


def _available_context_is_well_formed(context: StrategyIntentContext) -> bool:
    relation = "none" if context.table_leader_relation is None else context.table_leader_relation
    if context.diagnostics or context.intent not in _INTENTS or len(context.reason_codes) != 1:
        return False
    reason = context.reason_codes[0]
    if not isinstance(reason, str) or not reason or reason not in _REASONS_BY_INTENT[context.intent]:
        return False
    if context.can_finish_now != (reason == "can_finish_now"):
        return False
    if reason == "teammate_controls_table" and context.table_leader_relation != "teammate":
        return False
    if reason == "urgent_opponent_controls_table" and (
        context.table_leader_relation != "opponent" or not context.table_leader_is_urgent
    ):
        return False
    if context.is_free_lead and (
        context.table_leader_relation is not None or context.table_leader_player_id is not None
    ):
        return False
    if relation == "none":
        if context.table_leader_player_id is not None:
            return False
    elif not _valid_leader_id(context.table_leader_player_id):
        return False
    return relation in _RELATIONS and context.hand_strength in {"weak", "non_weak"}


def _unavailable_context_is_well_formed(context: StrategyIntentContext) -> bool:
    neutral_fields = (
        context.intent,
        context.my_player_id,
        context.my_team,
        context.my_hand_count,
        context.teammate_player_id,
        context.teammate_hand_count,
        context.minimum_opponent_hand_count,
        context.table_leader_player_id,
        context.table_leader_relation,
        context.hand_strength,
        context.hand_total_score,
        context.hand_control_score,
    )
    return (
        context.intent is None
        and context.reason_codes == ()
        and all(value is None for value in neutral_fields[1:])
        and context.urgent_opponent_ids == ()
        and context.can_finish_now is False
        and context.is_free_lead is False
        and context.table_leader_is_urgent is False
        and bool(context.diagnostics)
        and all(_valid_diagnostic(item) for item in context.diagnostics)
    )


def _run_policy(
    seeds: tuple[int, ...],
    *,
    rate: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> PolicyStrategyRouteReport:
    phase_accumulators = {phase: _BucketAccumulator() for phase in _ROUTED_PHASES}
    runtime_diagnostics: Counter[str] = Counter()
    seen_sample_ids: set[tuple[int, int, int]] = set()
    observed_turn_count = 0
    only_pass_skipped_count = 0
    finishing_skipped_count = 0
    opening_skipped_count = 0
    eligible_sample_count = 0
    evaluated_sample_count = 0
    duplicate_sample_count = 0
    sample_limit_skipped_count = 0
    completed_game_count = 0
    incomplete_game_count = 0
    opportunity_count = 0
    pass_count = 0

    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {
            player_id: StrategicPassAIAgent(player_id=player_id, strategic_pass_rate=rate)
            for player_id in (1, 2, 3, 4)
        }
        per_phase_sample_count = {phase: 0 for phase in _ROUTED_PHASES}
        limit_reported: set[str] = set()
        game_over = False

        for _ in range(max_steps):
            observation = game.observe()
            legal_actions = game.legal_actions()
            observed_turn_count += 1
            my_info = observation.get("my_info")
            current_round = observation.get("current_round")
            observer_player_id = my_info.get("player_id") if isinstance(my_info, dict) else None
            step_no = current_round.get("step_no") if isinstance(current_round, dict) else None

            if _only_pass(legal_actions):
                only_pass_skipped_count += 1
            elif _has_finishing_action(
                legal_actions,
                my_info.get("hand_count") if isinstance(my_info, dict) else None,
            ):
                finishing_skipped_count += 1
            else:
                phase_context = classify_game_phase(observation)
                if phase_context.phase == OPENING:
                    opening_skipped_count += 1
                elif phase_context.phase in _ROUTED_PHASES:
                    eligible_sample_count += 1
                    accumulator = phase_accumulators[phase_context.phase]
                    if not _is_int(observer_player_id) or not _is_int(step_no) or step_no < 0:
                        diagnostic = "invalid_observer" if not _is_int(observer_player_id) else "invalid_step_no"
                        if per_phase_sample_count[phase_context.phase] >= max_samples_per_phase_per_game:
                            sample_limit_skipped_count += 1
                            if phase_context.phase not in limit_reported:
                                _add_diagnostics(runtime_diagnostics, ("sample_limit_reached",))
                                _add_diagnostics(accumulator.diagnostic_counts, ("sample_limit_reached",))
                                limit_reported.add(phase_context.phase)
                        else:
                            per_phase_sample_count[phase_context.phase] += 1
                            evaluated_sample_count += 1
                            accumulator.record_invalid(diagnostic)
                            _add_diagnostics(runtime_diagnostics, (diagnostic,))
                    else:
                        sample_id = (seed, step_no, observer_player_id)
                        if sample_id in seen_sample_ids:
                            duplicate_sample_count += 1
                            _add_diagnostics(runtime_diagnostics, ("duplicate_sample",))
                            _add_diagnostics(accumulator.diagnostic_counts, ("duplicate_sample",))
                        else:
                            seen_sample_ids.add(sample_id)
                            if per_phase_sample_count[phase_context.phase] >= max_samples_per_phase_per_game:
                                sample_limit_skipped_count += 1
                                if phase_context.phase not in limit_reported:
                                    _add_diagnostics(runtime_diagnostics, ("sample_limit_reached",))
                                    _add_diagnostics(accumulator.diagnostic_counts, ("sample_limit_reached",))
                                    limit_reported.add(phase_context.phase)
                            else:
                                per_phase_sample_count[phase_context.phase] += 1
                                evaluated_sample_count += 1
                                try:
                                    hand_evaluation = evaluate_hand(observation, legal_actions)
                                except Exception:
                                    accumulator.record_invalid("hand_evaluation_error")
                                    _add_diagnostics(runtime_diagnostics, ("hand_evaluation_error",))
                                else:
                                    try:
                                        routed = route_strategy_intent(
                                            observation,
                                            legal_actions,
                                            phase_context=phase_context,
                                            hand_evaluation=hand_evaluation,
                                        )
                                    except Exception:
                                        accumulator.record_invalid("router_error")
                                        _add_diagnostics(runtime_diagnostics, ("router_error",))
                                    else:
                                        context_status = _validate_router_context(
                                            routed,
                                            expected_phase=phase_context.phase,
                                        )
                                        if context_status is None:
                                            accumulator.record_invalid("invalid_router_result")
                                            _add_diagnostics(runtime_diagnostics, ("invalid_router_result",))
                                        elif context_status == "available":
                                            accumulator.record_available(routed)
                                        else:
                                            accumulator.record_unavailable(routed.diagnostics)
                                            _add_diagnostics(runtime_diagnostics, routed.diagnostics or ("router_unavailable",))

            if not _is_int(observer_player_id) or observer_player_id not in agents:
                _add_diagnostics(runtime_diagnostics, ("invalid_observer",))
                break
            chosen_action_id = agents[observer_player_id].select_action(observation, legal_actions)
            step_result = game.step(require_legal_action_id(chosen_action_id, legal_actions))
            if bool(step_result["game_over"]):
                game_over = True
                break

        opportunity_count += sum(agent.strategic_pass_opportunity_count for agent in agents.values())
        pass_count += sum(agent.strategic_pass_count for agent in agents.values())
        if game_over:
            completed_game_count += 1
        else:
            incomplete_game_count += 1
            _add_diagnostics(runtime_diagnostics, ("max_steps_reached",))

    overall_accumulator = _BucketAccumulator()
    for phase in _ROUTED_PHASES:
        overall_accumulator.add(phase_accumulators[phase])
    by_phase = MappingProxyType({
        phase: _freeze_bucket(phase, phase_accumulators[phase]) for phase in _ROUTED_PHASES
    })
    return PolicyStrategyRouteReport(
        policy_name=_policy_name(rate),
        strategic_pass_rate=rate,
        strategic_pass_opportunity_count=opportunity_count,
        strategic_pass_count=pass_count,
        requested_game_count=len(seeds),
        completed_game_count=completed_game_count,
        incomplete_game_count=incomplete_game_count,
        observed_turn_count=observed_turn_count,
        only_pass_skipped_count=only_pass_skipped_count,
        finishing_skipped_count=finishing_skipped_count,
        opening_skipped_count=opening_skipped_count,
        eligible_sample_count=eligible_sample_count,
        evaluated_sample_count=evaluated_sample_count,
        duplicate_sample_count=duplicate_sample_count,
        sample_limit_skipped_count=sample_limit_skipped_count,
        overall=_freeze_bucket("overall", overall_accumulator),
        by_phase=by_phase,
        diagnostic_counts=_freeze_counts(runtime_diagnostics),
    )


def run_strategy_router_benchmark(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    max_steps: int = 5000,
    max_samples_per_phase_per_game: int = 128,
) -> StrategyRouterBenchmarkReport:
    """Collect isolated, public-only strategy-router distributions."""

    normalized_seeds, rates = _validate_inputs(
        seeds,
        current_level_rank=current_level_rank,
        strategic_pass_rates=strategic_pass_rates,
        max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game,
    )
    return StrategyRouterBenchmarkReport(
        requested_policy_count=len(rates),
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game,
        policies=tuple(
            _run_policy(
                normalized_seeds,
                rate=rate,
                current_level_rank=current_level_rank,
                max_steps=max_steps,
                max_samples_per_phase_per_game=max_samples_per_phase_per_game,
            )
            for rate in rates
        ),
    )
