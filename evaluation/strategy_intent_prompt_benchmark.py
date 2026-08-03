"""Deterministic, aggregate-only coverage collection for strategy-intent prompts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.deepseek_client import DeepSeekClient
from agents.game_phase import (
    CRITICAL_ENDGAME,
    ENDGAME,
    MIDGAME,
    NEAR_OPEN_ENDGAME,
    OPENING,
    classify_game_phase,
)
from agents.hand_evaluator import evaluate_hand
from agents.strategy_intent_prompt import (
    StrategyIntentPromptPayload,
    build_strategy_intent_prompt_payload,
)
from agents.strategy_router import StrategyIntentContext, route_strategy_intent
from engine.cards import RANKS
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_PHASES = (MIDGAME, ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME)
_ROUTER_SOURCE = "public_strategy_router_v1"


def _is_int(value: object) -> bool:
    return type(value) is int


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType({key: int(values[key]) for key in sorted(values)})


def _add_diagnostic(counts: Counter[str], *values: object) -> None:
    categories = {
        value.split(":", 1)[0]
        for value in values
        if isinstance(value, str) and value.split(":", 1)[0]
    }
    counts.update(categories)


def _only_pass(actions: list[dict[str, object]]) -> bool:
    return bool(actions) and all(action.get("declared_pattern") == "pass" for action in actions)


def _has_finishing_action(actions: list[dict[str, object]], hand_count: object) -> bool:
    return (
        _is_int(hand_count)
        and hand_count > 0
        and any(
            action.get("declared_pattern") != "pass"
            and isinstance(action.get("carrier_cards"), list)
            and len(action["carrier_cards"]) == hand_count
            for action in actions
        )
    )


def _validate_inputs(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int],
    current_level_rank: str,
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence")
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
    if not _is_int(max_steps) or max_steps <= 0:
        raise ValueError("max_steps must be a positive non-bool integer")
    if not _is_int(max_samples_per_phase_per_game) or max_samples_per_phase_per_game <= 0:
        raise ValueError("max_samples_per_phase_per_game must be a positive non-bool integer")
    return normalized_seeds, rates


@dataclass(slots=True)
class _BucketAccumulator:
    sample_count: int = 0
    router_available_count: int = 0
    router_unavailable_count: int = 0
    router_invalid_count: int = 0
    payload_ready_count: int = 0
    payload_omitted_count: int = 0
    payload_invalid_count: int = 0
    exact_insertion_count: int = 0
    omitted_prompt_equal_count: int = 0
    ready_pair_mismatch_count: int = 0
    omitted_pair_mismatch_count: int = 0
    payload_char_sum: int = 0
    payload_char_min: int = 0
    payload_char_max: int = 0
    prompt_delta_char_sum: int = 0
    prompt_delta_char_min: int = 0
    prompt_delta_char_max: int = 0
    diagnostic_counts: Counter[str] = field(default_factory=Counter)

    def _record_ready_cost(self, payload_chars: int, delta: int) -> None:
        self.payload_char_sum += payload_chars
        self.prompt_delta_char_sum += delta
        self.payload_char_min = payload_chars if self.payload_char_min == 0 else min(self.payload_char_min, payload_chars)
        self.payload_char_max = max(self.payload_char_max, payload_chars)
        self.prompt_delta_char_min = delta if self.prompt_delta_char_min == 0 else min(self.prompt_delta_char_min, delta)
        self.prompt_delta_char_max = max(self.prompt_delta_char_max, delta)

    def add(self, other: _BucketAccumulator) -> None:
        for name in (
            "sample_count", "router_available_count", "router_unavailable_count", "router_invalid_count",
            "payload_ready_count", "payload_omitted_count", "payload_invalid_count", "exact_insertion_count",
            "omitted_prompt_equal_count", "ready_pair_mismatch_count", "omitted_pair_mismatch_count",
            "payload_char_sum", "prompt_delta_char_sum",
        ):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        if other.payload_char_min:
            self.payload_char_min = other.payload_char_min if not self.payload_char_min else min(self.payload_char_min, other.payload_char_min)
            self.payload_char_max = max(self.payload_char_max, other.payload_char_max)
            self.prompt_delta_char_min = other.prompt_delta_char_min if not self.prompt_delta_char_min else min(self.prompt_delta_char_min, other.prompt_delta_char_min)
            self.prompt_delta_char_max = max(self.prompt_delta_char_max, other.prompt_delta_char_max)
        self.diagnostic_counts.update(other.diagnostic_counts)


@dataclass(frozen=True, slots=True)
class StrategyIntentPromptCoverageBucket:
    bucket_name: str
    sample_count: int
    router_available_count: int
    router_unavailable_count: int
    router_invalid_count: int
    payload_ready_count: int
    payload_omitted_count: int
    payload_invalid_count: int
    exact_insertion_count: int
    omitted_prompt_equal_count: int
    ready_pair_mismatch_count: int
    omitted_pair_mismatch_count: int
    prompt_pair_mismatch_count: int
    payload_char_sum: int
    payload_char_min: int
    payload_char_max: int
    prompt_delta_char_sum: int
    prompt_delta_char_min: int
    prompt_delta_char_max: int
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "bucket_name": self.bucket_name,
            "sample_count": self.sample_count,
            "router_available_count": self.router_available_count,
            "router_unavailable_count": self.router_unavailable_count,
            "router_invalid_count": self.router_invalid_count,
            "payload_ready_count": self.payload_ready_count,
            "payload_omitted_count": self.payload_omitted_count,
            "payload_invalid_count": self.payload_invalid_count,
            "exact_insertion_count": self.exact_insertion_count,
            "omitted_prompt_equal_count": self.omitted_prompt_equal_count,
            "ready_pair_mismatch_count": self.ready_pair_mismatch_count,
            "omitted_pair_mismatch_count": self.omitted_pair_mismatch_count,
            "prompt_pair_mismatch_count": self.prompt_pair_mismatch_count,
            "payload_char_sum": self.payload_char_sum,
            "payload_char_min": self.payload_char_min,
            "payload_char_max": self.payload_char_max,
            "prompt_delta_char_sum": self.prompt_delta_char_sum,
            "prompt_delta_char_min": self.prompt_delta_char_min,
            "prompt_delta_char_max": self.prompt_delta_char_max,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class PolicyStrategyIntentPromptReport:
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
    overall: StrategyIntentPromptCoverageBucket
    by_phase: Mapping[str, StrategyIntentPromptCoverageBucket]
    prompt_pair_sha256: str
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
            "by_phase": [self.by_phase[phase].to_dict() for phase in _PHASES],
            "prompt_pair_sha256": self.prompt_pair_sha256,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class StrategyIntentPromptBenchmarkReport:
    requested_policy_count: int
    current_level_rank: str
    max_steps: int
    max_samples_per_phase_per_game: int
    policies: tuple[PolicyStrategyIntentPromptReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "current_level_rank": self.current_level_rank,
            "max_steps": self.max_steps,
            "max_samples_per_phase_per_game": self.max_samples_per_phase_per_game,
            "policies": [policy.to_dict() for policy in self.policies],
        }


def _freeze_bucket(name: str, value: _BucketAccumulator) -> StrategyIntentPromptCoverageBucket:
    return StrategyIntentPromptCoverageBucket(
        bucket_name=name,
        sample_count=value.sample_count,
        router_available_count=value.router_available_count,
        router_unavailable_count=value.router_unavailable_count,
        router_invalid_count=value.router_invalid_count,
        payload_ready_count=value.payload_ready_count,
        payload_omitted_count=value.payload_omitted_count,
        payload_invalid_count=value.payload_invalid_count,
        exact_insertion_count=value.exact_insertion_count,
        omitted_prompt_equal_count=value.omitted_prompt_equal_count,
        ready_pair_mismatch_count=value.ready_pair_mismatch_count,
        omitted_pair_mismatch_count=value.omitted_pair_mismatch_count,
        prompt_pair_mismatch_count=value.ready_pair_mismatch_count + value.omitted_pair_mismatch_count,
        payload_char_sum=value.payload_char_sum,
        payload_char_min=value.payload_char_min,
        payload_char_max=value.payload_char_max,
        prompt_delta_char_sum=value.prompt_delta_char_sum,
        prompt_delta_char_min=value.prompt_delta_char_min,
        prompt_delta_char_max=value.prompt_delta_char_max,
        diagnostic_counts=_freeze_counts(value.diagnostic_counts),
    )


def _router_status(value: object, expected_phase: str) -> str | None:
    if type(value) is not StrategyIntentContext:
        return None
    if value.source != _ROUTER_SOURCE or value.phase != expected_phase:
        return None
    if value.status == "available" and value.diagnostics == ():
        return "available"
    if value.status == "unavailable" and type(value.diagnostics) is tuple and value.diagnostics:
        return "unavailable"
    return None


def _payload_status(value: object) -> str | None:
    if type(value) is not StrategyIntentPromptPayload:
        return None
    if (
        value.status == "ready"
        and value.diagnostics == ()
        and type(value.text) is str
        and bool(value.text)
        and _is_int(value.char_count)
        and value.char_count == len(value.text)
        and 0 < value.char_count <= 800
    ):
        return "ready"
    if (
        value.status == "omitted"
        and type(value.diagnostics) is tuple
        and bool(value.diagnostics)
        and value.text == ""
        and value.char_count == 0
        and value.router_source is None
        and value.phase is None
        and value.intent is None
    ):
        return "omitted"
    return None


def _prompts(
    observation: dict[str, object],
    prompt_actions: list[dict[str, object]],
    phase_context: object,
    hand_evaluation: dict[str, object],
    payload: StrategyIntentPromptPayload,
) -> tuple[str, str]:
    my_info = dict(observation.get("my_info", {}))
    current_round = dict(observation.get("current_round", {}))
    other_players = list(observation.get("other_players", []))
    history = dict(observation.get("history", {}))
    common = {
        "my_info": my_info,
        "current_round": current_round,
        "other_players": other_players,
        "history": history,
        "legal_actions": prompt_actions,
        "rag_context": None,
        "hand_evaluation": hand_evaluation,
        "card_tracking_summary": None,
        "phase_context": phase_context,
        "card_confidence_prompt": None,
    }
    off = DeepSeekClient._build_structured_prompt(**common)
    on = DeepSeekClient._build_structured_prompt(**common, strategy_intent_prompt=payload)
    return off, on


def _record_pair(
    accumulator: _BucketAccumulator,
    *,
    phase: str,
    payload: StrategyIntentPromptPayload,
    off: str,
    on: str,
    hasher: object,
) -> None:
    status = _payload_status(payload)
    if status is None:
        accumulator.payload_invalid_count += 1
        _add_diagnostic(accumulator.diagnostic_counts, "invalid_payload_result")
        return
    canonical = json.dumps([phase, off, on], ensure_ascii=False, separators=(",", ":"))
    hasher.update(canonical.encode("utf-8"))
    if status == "ready":
        accumulator.payload_ready_count += 1
        expected = off.replace("【场景标签】", f"【策略意图】\n{payload.text}\n\n【场景标签】", 1)
        delta = len(on) - len(off)
        accumulator._record_ready_cost(payload.char_count, delta)
        if (
            off.count("【场景标签】") == 1
            and "【策略意图】" not in off
            and on == expected
            and on.count("【策略意图】") == 1
            and on.count(payload.text) == 1
            and delta == payload.char_count + 9
        ):
            accumulator.exact_insertion_count += 1
        else:
            accumulator.ready_pair_mismatch_count += 1
            _add_diagnostic(accumulator.diagnostic_counts, "prompt_pair_mismatch")
    else:
        accumulator.payload_omitted_count += 1
        if on == off:
            accumulator.omitted_prompt_equal_count += 1
        else:
            accumulator.omitted_pair_mismatch_count += 1
            _add_diagnostic(accumulator.diagnostic_counts, "prompt_pair_mismatch")


def _run_policy(
    seeds: tuple[int, ...],
    *,
    rate: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_phase_per_game: int,
) -> PolicyStrategyIntentPromptReport:
    accumulators = {phase: _BucketAccumulator() for phase in _PHASES}
    diagnostics: Counter[str] = Counter()
    seen: set[tuple[int, int, int]] = set()
    hasher = hashlib.sha256()
    observed = only_pass = finishing = opening = eligible = evaluated = duplicate = limited = 0
    complete = incomplete = opportunity = active_pass = 0

    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {player: StrategicPassAIAgent(player_id=player, strategic_pass_rate=rate) for player in (1, 2, 3, 4)}
        per_phase = {phase: 0 for phase in _PHASES}
        game_over = False
        for _ in range(max_steps):
            observation = game.observe()
            actions = game.legal_actions()
            observed += 1
            my_info = observation.get("my_info")
            current_round = observation.get("current_round")
            if _only_pass(actions):
                only_pass += 1
            elif _has_finishing_action(actions, my_info.get("hand_count") if isinstance(my_info, dict) else None):
                finishing += 1
            else:
                phase_context = classify_game_phase(observation)
                phase = phase_context.phase
                if phase == OPENING:
                    opening += 1
                elif phase in _PHASES:
                    eligible += 1
                    observer = my_info.get("player_id") if isinstance(my_info, dict) else None
                    step_no = current_round.get("step_no") if isinstance(current_round, dict) else None
                    if not _is_int(observer) or not _is_int(step_no):
                        evaluated += 1
                        per_phase[phase] += 1
                        accumulators[phase].sample_count += 1
                        accumulators[phase].router_invalid_count += 1
                        _add_diagnostic(accumulators[phase].diagnostic_counts, "invalid_observer" if not _is_int(observer) else "invalid_step_no")
                        _add_diagnostic(diagnostics, "invalid_observer" if not _is_int(observer) else "invalid_step_no")
                    elif (seed, step_no, observer) in seen:
                        duplicate += 1
                        _add_diagnostic(diagnostics, "duplicate_sample")
                    elif per_phase[phase] >= max_samples_per_phase_per_game:
                        limited += 1
                        _add_diagnostic(diagnostics, "sample_limit_reached")
                    else:
                        seen.add((seed, step_no, observer))
                        per_phase[phase] += 1
                        evaluated += 1
                        bucket = accumulators[phase]
                        bucket.sample_count += 1
                        try:
                            hand_evaluation = evaluate_hand(observation, actions)
                            routed = route_strategy_intent(
                                observation,
                                actions,
                                phase_context=phase_context,
                                hand_evaluation=hand_evaluation,
                            )
                        except Exception:
                            bucket.router_invalid_count += 1
                            _add_diagnostic(bucket.diagnostic_counts, "router_error")
                            _add_diagnostic(diagnostics, "router_error")
                        else:
                            router_status = _router_status(routed, phase)
                            if router_status is None:
                                bucket.router_invalid_count += 1
                                _add_diagnostic(bucket.diagnostic_counts, "invalid_router_result")
                                _add_diagnostic(diagnostics, "invalid_router_result")
                            else:
                                if router_status == "available":
                                    bucket.router_available_count += 1
                                else:
                                    bucket.router_unavailable_count += 1
                                    _add_diagnostic(bucket.diagnostic_counts, *routed.diagnostics)
                                try:
                                    payload = build_strategy_intent_prompt_payload(routed)
                                    prompt_actions = DeepSeekClient._prune_legal_actions(
                                        actions,
                                        str(current_round.get("constraint", "free")) if isinstance(current_round, dict) else "free",
                                        step_no=step_no,
                                        hand_count=my_info.get("hand_count") if isinstance(my_info, dict) and _is_int(my_info.get("hand_count")) else 0,
                                        phase_context=phase_context,
                                    )
                                    off, on = _prompts(observation, prompt_actions, phase_context, hand_evaluation, payload)
                                except Exception:
                                    bucket.payload_invalid_count += 1
                                    _add_diagnostic(bucket.diagnostic_counts, "payload_error")
                                    _add_diagnostic(diagnostics, "payload_error")
                                else:
                                    _record_pair(bucket, phase=phase, payload=payload, off=off, on=on, hasher=hasher)
            player_id = my_info.get("player_id") if isinstance(my_info, dict) else None
            try:
                chosen = require_legal_action_id(agents[player_id].select_action(observation, actions), actions)  # type: ignore[index]
                result = game.step(chosen)
            except Exception:
                _add_diagnostic(diagnostics, "game_progress_error")
                break
            if result.get("game_over") is True:
                game_over = True
                break
        opportunity += sum(agent.strategic_pass_opportunity_count for agent in agents.values())
        active_pass += sum(agent.strategic_pass_count for agent in agents.values())
        if game_over:
            complete += 1
        else:
            incomplete += 1
            _add_diagnostic(diagnostics, "max_steps_reached")

    overall = _BucketAccumulator()
    for phase in _PHASES:
        overall.add(accumulators[phase])
    by_phase = MappingProxyType({phase: _freeze_bucket(phase, accumulators[phase]) for phase in _PHASES})
    return PolicyStrategyIntentPromptReport(
        policy_name=_policy_name(rate),
        strategic_pass_rate=rate,
        strategic_pass_opportunity_count=opportunity,
        strategic_pass_count=active_pass,
        requested_game_count=len(seeds),
        completed_game_count=complete,
        incomplete_game_count=incomplete,
        observed_turn_count=observed,
        only_pass_skipped_count=only_pass,
        finishing_skipped_count=finishing,
        opening_skipped_count=opening,
        eligible_sample_count=eligible,
        evaluated_sample_count=evaluated,
        duplicate_sample_count=duplicate,
        sample_limit_skipped_count=limited,
        overall=_freeze_bucket("overall", overall),
        by_phase=by_phase,
        prompt_pair_sha256=hasher.hexdigest(),
        diagnostic_counts=_freeze_counts(diagnostics),
    )


def run_strategy_intent_prompt_benchmark(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    max_steps: int = 5000,
    max_samples_per_phase_per_game: int = 128,
) -> StrategyIntentPromptBenchmarkReport:
    """Collect deterministic, aggregate-only off/on prompt coverage evidence."""

    normalized_seeds, rates = _validate_inputs(
        seeds,
        current_level_rank=current_level_rank,
        strategic_pass_rates=strategic_pass_rates,
        max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game,
    )
    return StrategyIntentPromptBenchmarkReport(
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
