"""Aggregate-only deterministic RuleBased rollouts for intent-prompt pairs.

The provider is injected by the caller.  The collector observes only the
public game API while it gathers candidates; snapshots are in-memory only.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.game_phase import GamePhaseContext, OPENING, classify_game_phase
from agents.hand_evaluator import evaluate_hand
from agents.rule_based_ai import RuleBasedAIAgent
from agents.strategy_intent_prompt import StrategyIntentPromptPayload, build_strategy_intent_prompt_payload
from agents.strategy_router import StrategyIntentContext, route_strategy_intent
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent
from evaluation.strategy_intent_action_ablation import (
    SuggestionProvider,
    _PHASES,
    _PRESSURE_PATTERNS,
    _add_diagnostic,
    _build_prompt,
    _call_provider,
    _classify,
    _exact_prompt_pair,
    _freeze_counts,
    _has_finishing_action,
    _is_int,
    _legal_mapping,
    _only_pass,
    _payload_ready,
    _policy_name,
    _priority,
    _prompt_actions,
    _router_available,
    _validate_inputs,
)


def _team_for(player_id: int) -> str:
    return "team_13" if player_id in (1, 3) else "team_24"


def _partner_for(player_id: int) -> int:
    return 3 if player_id == 1 else 1 if player_id == 3 else 4 if player_id == 2 else 2


@dataclass(frozen=True, slots=True)
class RuleRolloutOutcome:
    """Aggregate-safe terminal result for one independent public rollout."""

    team_outcome: str
    team_outcome_score: int
    team_placement_sum: int
    rollout_step_count: int
    complete: bool
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "team_outcome": self.team_outcome,
            "team_outcome_score": self.team_outcome_score,
            "team_placement_sum": self.team_placement_sum,
            "rollout_step_count": self.rollout_step_count,
            "complete": self.complete,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True, slots=True)
class StrategyIntentActionQualityBucket:
    only_pass_skip_count: int
    finishing_skip_count: int
    router_unavailable_skip_count: int
    router_invalid_skip_count: int
    payload_omitted_skip_count: int
    payload_invalid_skip_count: int
    insufficient_prompt_candidates_count: int
    prompt_mismatch_count: int
    clone_mismatch_count: int
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
    rollout_branch_attempted_count: int
    rollout_branch_completed_count: int
    rollout_branch_failed_count: int
    same_action_reused_rollout_count: int
    quality_evaluable_pair_count: int
    quality_unevaluable_pair_count: int
    on_better_count: int
    off_better_count: int
    tie_count: int
    changed_on_better_count: int
    changed_off_better_count: int
    changed_tie_count: int
    off_win_count: int
    off_draw_count: int
    off_loss_count: int
    on_win_count: int
    on_draw_count: int
    on_loss_count: int
    off_team_placement_sum_total: int
    on_team_placement_sum_total: int
    off_rollout_step_total: int
    on_rollout_step_total: int
    prompt_pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        value = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "diagnostic_counts"}
        value["diagnostic_counts"] = dict(self.diagnostic_counts)
        return value


@dataclass(frozen=True, slots=True)
class PolicyStrategyIntentActionQualityReport:
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
    overall: StrategyIntentActionQualityBucket
    by_phase: Mapping[str, StrategyIntentActionQualityBucket]
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
class StrategyIntentActionQualityReport:
    requested_policy_count: int
    current_level_rank: str
    max_steps: int
    max_samples_per_phase_per_game: int
    max_rollout_steps: int
    policies: tuple[PolicyStrategyIntentActionQualityReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "current_level_rank": self.current_level_rank,
            "max_steps": self.max_steps,
            "max_samples_per_phase_per_game": self.max_samples_per_phase_per_game,
            "max_rollout_steps": self.max_rollout_steps,
            "policies": [policy.to_dict() for policy in self.policies],
        }


class _BucketAccumulator:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.diagnostics: Counter[str] = Counter()
        self.hasher = hashlib.sha256()

    def digest_pair(self, phase: str, off_prompt: str, on_prompt: str) -> None:
        self.hasher.update(json.dumps([phase, off_prompt, on_prompt], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    def freeze(self) -> StrategyIntentActionQualityBucket:
        names = StrategyIntentActionQualityBucket.__dataclass_fields__
        return StrategyIntentActionQualityBucket(
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
    legal_actions: list[dict[str, object]
    ]
    prompt_actions: list[dict[str, object]]
    phase_context: GamePhaseContext
    hand_evaluation: dict[str, object]
    payload: StrategyIntentPromptPayload
    off_prompt: str
    on_prompt: str
    snapshot: GuanDanGame

    @property
    def sort_key(self) -> tuple[str, int, int]:
        return (self.priority_digest, self.step_no, self.observer_player_id)


def _failed(steps: int, code: str) -> RuleRolloutOutcome:
    return RuleRolloutOutcome("", 0, 0, steps, False, (code,))


def _normalize_terminal(observation: object, winner: object, observer: object, steps: int) -> RuleRolloutOutcome:
    if winner not in {"team_13", "team_24", "draw"}:
        return _failed(steps, "invalid_terminal_winner")
    if not _is_int(observer) or not 1 <= observer <= 4 or not isinstance(observation, Mapping):
        return _failed(steps, "invalid_finish_order")
    history = observation.get("history")
    order = history.get("finish_order") if isinstance(history, Mapping) else None
    if not isinstance(order, list) or any(not _is_int(player) or not 1 <= player <= 4 for player in order) or len(set(order)) != len(order):
        return _failed(steps, "invalid_finish_order")
    if len(order) == 3:
        missing = [player for player in (1, 2, 3, 4) if player not in order]
        if len(missing) != 1:
            return _failed(steps, "invalid_finish_order")
        order = [*order, missing[0]]
    if len(order) != 4:
        return _failed(steps, "invalid_finish_order")
    outcome = "draw" if winner == "draw" else "win" if winner == _team_for(observer) else "loss"
    score = {"loss": 0, "draw": 1, "win": 2}[outcome]
    placement = order.index(observer) + order.index(_partner_for(observer)) + 2
    return RuleRolloutOutcome(outcome, score, placement, steps, True, ())


def _rollout(branch: GuanDanGame, action_id: object, observer: object, max_steps: int) -> RuleRolloutOutcome:
    """Advance one clone solely through public game methods and RuleBased agents."""
    if not _is_int(observer) or not 1 <= observer <= 4:
        return _failed(0, "initial_action_invalid")
    try:
        legal = branch.legal_actions()
        try:
            initial_action = require_legal_action_id(action_id, legal)
        except Exception:
            return _failed(0, "initial_action_invalid")
        result = branch.step(initial_action)
        steps = 1
        if result.get("game_over") is True:
            return _normalize_terminal(branch.observe(), result.get("winner"), observer, steps)
        agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        while steps < max_steps:
            observation = branch.observe()
            info = observation.get("my_info")
            player = info.get("player_id") if isinstance(info, Mapping) else None
            legal = branch.legal_actions()
            if not _is_int(player) or player not in agents:
                return _failed(steps, "rollout_action_invalid")
            try:
                action = require_legal_action_id(agents[player].select_action(observation, legal), legal)
            except Exception:
                return _failed(steps, "rollout_action_invalid")
            result = branch.step(action)
            steps += 1
            if result.get("game_over") is True:
                return _normalize_terminal(branch.observe(), result.get("winner"), observer, steps)
        return _failed(steps, "rollout_step_limit_reached")
    except Exception:
        return _failed(0, "rollout_exception")


def _compare_quality(off: RuleRolloutOutcome, on: RuleRolloutOutcome) -> str:
    if off.team_outcome_score != on.team_outcome_score:
        return "on_better" if on.team_outcome_score > off.team_outcome_score else "off_better"
    if off.team_placement_sum != on.team_placement_sum:
        return "on_better" if on.team_placement_sum < off.team_placement_sum else "off_better"
    return "tie"


def _record_provider(acc: _BucketAccumulator, condition: str, outcome: str, action_id: int | None, legal: Mapping[int, Mapping[str, object]]) -> bool:
    acc.counts[f"{condition}_attempted_call_count"] += 1
    if outcome != "valid" or action_id is None:
        acc.counts[f"{condition}_{outcome}_count"] += 1
        return False
    acc.counts[f"{condition}_valid_response_count"] += 1
    pattern = legal[action_id].get("declared_pattern")
    if pattern == "pass":
        acc.counts[f"{condition}_pass_selection_count"] += 1
    if pattern in _PRESSURE_PATTERNS:
        acc.counts[f"{condition}_pressure_selection_count"] += 1
    return True


def _record_branch(acc: _BucketAccumulator, outcome: RuleRolloutOutcome) -> None:
    if outcome.complete:
        acc.counts["rollout_branch_completed_count"] += 1
    else:
        acc.counts["rollout_branch_failed_count"] += 1
        _add_diagnostic(acc.diagnostics, *outcome.diagnostics)


def _record_condition_outcome(acc: _BucketAccumulator, prefix: str, outcome: RuleRolloutOutcome) -> None:
    if outcome.complete:
        acc.counts[f"{prefix}_{outcome.team_outcome}_count"] += 1
        acc.counts[f"{prefix}_team_placement_sum_total"] += outcome.team_placement_sum
        acc.counts[f"{prefix}_rollout_step_total"] += outcome.rollout_step_count


def _record_pair(acc: _BucketAccumulator, candidate: _Candidate, provider: Callable[..., object], *, off_first: bool, max_rollout_steps: int) -> None:
    legal = _legal_mapping(candidate.legal_actions)
    prompt_ids = frozenset(item.get("action_id") for item in candidate.prompt_actions if _is_int(item.get("action_id")))
    common: dict[str, object] = {
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
    acc.digest_pair(candidate.phase, candidate.off_prompt, candidate.on_prompt)
    if off_first:
        acc.counts["off_first_pair_count"] += 1
        off = _call_provider(provider, common, legal, prompt_ids)
        on = _call_provider(provider, on_kwargs, legal, prompt_ids)
    else:
        acc.counts["on_first_pair_count"] += 1
        on = _call_provider(provider, on_kwargs, legal, prompt_ids)
        off = _call_provider(provider, common, legal, prompt_ids)
    off_valid = _record_provider(acc, "off", *off, legal)
    on_valid = _record_provider(acc, "on", *on, legal)
    if not off_valid and not on_valid:
        acc.counts["neither_valid_count"] += 1
        acc.counts["quality_unevaluable_pair_count"] += 1
        return
    if not off_valid:
        acc.counts["only_on_valid_count"] += 1
        acc.counts["quality_unevaluable_pair_count"] += 1
        return
    if not on_valid:
        acc.counts["only_off_valid_count"] += 1
        acc.counts["quality_unevaluable_pair_count"] += 1
        return
    acc.counts["both_valid_pair_count"] += 1
    assert off[1] is not None and on[1] is not None
    if off[1] == on[1]:
        acc.counts["same_action_count"] += 1
        acc.counts["same_action_reused_rollout_count"] += 1
        acc.counts["rollout_branch_attempted_count"] += 1
        shared = _rollout(copy.deepcopy(candidate.snapshot), off[1], candidate.observer_player_id, max_rollout_steps)
        _record_branch(acc, shared)
        if not shared.complete:
            acc.counts["quality_unevaluable_pair_count"] += 1
            return
        _record_condition_outcome(acc, "off", shared)
        _record_condition_outcome(acc, "on", shared)
        comparison = "tie"
        off_outcome = on_outcome = shared
    else:
        acc.counts["changed_action_count"] += 1
        acc.counts["rollout_branch_attempted_count"] += 2
        off_outcome = _rollout(copy.deepcopy(candidate.snapshot), off[1], candidate.observer_player_id, max_rollout_steps)
        on_outcome = _rollout(copy.deepcopy(candidate.snapshot), on[1], candidate.observer_player_id, max_rollout_steps)
        _record_branch(acc, off_outcome)
        _record_branch(acc, on_outcome)
        if not off_outcome.complete or not on_outcome.complete:
            acc.counts["quality_unevaluable_pair_count"] += 1
            return
        _record_condition_outcome(acc, "off", off_outcome)
        _record_condition_outcome(acc, "on", on_outcome)
        comparison = _compare_quality(off_outcome, on_outcome)
    acc.counts["quality_evaluable_pair_count"] += 1
    acc.counts[f"{comparison}_count"] += 1
    if off[1] != on[1]:
        acc.counts[f"changed_{comparison}_count"] += 1


def _overall(accumulators: Mapping[str, _BucketAccumulator]) -> _BucketAccumulator:
    combined = _BucketAccumulator()
    for phase in _PHASES:
        item = accumulators[phase]
        combined.counts.update(item.counts)
        combined.diagnostics.update(item.diagnostics)
        combined.hasher.update(item.hasher.digest())
    return combined


def _try_reserve(
    reservoir: list[_Candidate],
    *,
    capacity: int,
    priority: tuple[str, int, int],
    build: Callable[[], _Candidate | None],
) -> bool:
    """Keep only current top-N snapshots, equivalent to a final stable sort."""
    if len(reservoir) == capacity and priority >= reservoir[-1].sort_key:
        return False
    candidate = build()
    if candidate is None:
        return False
    reservoir.append(candidate)
    reservoir.sort(key=lambda item: item.sort_key)
    if len(reservoir) > capacity:
        reservoir.pop()
    return True


def _run_policy(
    seeds: tuple[int, ...], *, rate: int, suggestion_provider: Callable[..., object], samples_per_phase: int,
    current_level_rank: str, max_steps: int, max_samples_per_phase_per_game: int, max_rollout_steps: int,
) -> PolicyStrategyIntentActionQualityReport:
    name = _policy_name(rate)
    accs = {phase: _BucketAccumulator() for phase in _PHASES}
    reservoirs: dict[str, list[_Candidate]] = {phase: [] for phase in _PHASES}
    seen: set[tuple[int, int, int]] = set()
    policy_diagnostics: Counter[str] = Counter()
    observed = opening = eligible = evaluated = duplicate = limited = 0
    only_pass = finishing = completed = incomplete = opportunity = active = 0
    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {player: StrategicPassAIAgent(player_id=player, strategic_pass_rate=rate) for player in (1, 2, 3, 4)}
        per_game = {phase: 0 for phase in _PHASES}
        done = False
        for _ in range(max_steps):
            observation = game.observe()
            legal_actions = game.legal_actions()
            observed += 1
            info = observation.get("my_info")
            if _only_pass(legal_actions):
                only_pass += 1
            elif _has_finishing_action(legal_actions, info.get("hand_count") if isinstance(info, Mapping) else None):
                finishing += 1
            else:
                phase_context = classify_game_phase(observation)
                phase = phase_context.phase
                if phase == OPENING:
                    opening += 1
                elif phase in _PHASES:
                    eligible += 1
                    round_data = observation.get("current_round")
                    observer = info.get("player_id") if isinstance(info, Mapping) else None
                    step_no = round_data.get("step_no") if isinstance(round_data, Mapping) else None
                    if not _is_int(observer) or not _is_int(step_no):
                        _add_diagnostic(policy_diagnostics, "invalid_sample_identity")
                    elif (seed, step_no, observer) in seen:
                        duplicate += 1; _add_diagnostic(policy_diagnostics, "duplicate_sample")
                    elif per_game[phase] >= max_samples_per_phase_per_game:
                        limited += 1; _add_diagnostic(policy_diagnostics, "sample_limit_reached")
                    else:
                        seen.add((seed, step_no, observer)); per_game[phase] += 1; evaluated += 1
                        acc = accs[phase]
                        try:
                            hand = evaluate_hand(observation, legal_actions)
                            context = route_strategy_intent(observation, legal_actions, phase_context=phase_context, hand_evaluation=hand)
                        except Exception:
                            acc.counts["router_invalid_skip_count"] += 1; _add_diagnostic(acc.diagnostics, "router_error")
                        else:
                            if type(context) is not StrategyIntentContext:
                                acc.counts["router_invalid_skip_count"] += 1; _add_diagnostic(acc.diagnostics, "invalid_router_result")
                            elif not _router_available(context, phase):
                                acc.counts["router_unavailable_skip_count"] += 1; _add_diagnostic(acc.diagnostics, *context.diagnostics)
                            else:
                                try:
                                    payload = build_strategy_intent_prompt_payload(context)
                                except Exception:
                                    acc.counts["payload_invalid_skip_count"] += 1; _add_diagnostic(acc.diagnostics, "payload_error")
                                else:
                                    if type(payload) is not StrategyIntentPromptPayload:
                                        acc.counts["payload_invalid_skip_count"] += 1; _add_diagnostic(acc.diagnostics, "invalid_payload_result")
                                    elif payload.status == "omitted":
                                        acc.counts["payload_omitted_skip_count"] += 1; _add_diagnostic(acc.diagnostics, *payload.diagnostics)
                                    elif not _payload_ready(payload):
                                        acc.counts["payload_invalid_skip_count"] += 1; _add_diagnostic(acc.diagnostics, "invalid_payload_result")
                                    else:
                                        prompt_actions = _prompt_actions(observation, legal_actions, phase_context)
                                        prompt_ids = {item.get("action_id") for item in prompt_actions if _is_int(item.get("action_id"))}
                                        if len(prompt_ids) < 2:
                                            acc.counts["insufficient_prompt_candidates_count"] += 1; _add_diagnostic(acc.diagnostics, "insufficient_prompt_candidates")
                                        else:
                                            try:
                                                off_prompt = _build_prompt(observation, prompt_actions, phase_context, hand, None)
                                                on_prompt = _build_prompt(observation, prompt_actions, phase_context, hand, payload)
                                            except Exception:
                                                acc.counts["prompt_mismatch_count"] += 1; _add_diagnostic(acc.diagnostics, "prompt_pair_mismatch")
                                            else:
                                                if not _exact_prompt_pair(off_prompt, on_prompt, payload):
                                                    acc.counts["prompt_mismatch_count"] += 1; _add_diagnostic(acc.diagnostics, "prompt_pair_mismatch")
                                                else:
                                                    priority = (_priority(name, phase, seed, step_no, observer), step_no, observer)
                                                    def make_candidate() -> _Candidate | None:
                                                        try:
                                                            snapshot = copy.deepcopy(game)
                                                            if game.observe() != snapshot.observe() or game.legal_actions() != snapshot.legal_actions():
                                                                raise ValueError("snapshot public mismatch")
                                                        except Exception:
                                                            acc.counts["clone_mismatch_count"] += 1; _add_diagnostic(acc.diagnostics, "clone_mismatch")
                                                            return None
                                                        acc.counts["qualified_candidate_count"] += 1
                                                        return _Candidate(priority[0], step_no, observer, phase, observation, legal_actions, prompt_actions, phase_context, hand, payload, off_prompt, on_prompt, snapshot)
                                                    if len(reservoirs[phase]) < samples_per_phase or priority < reservoirs[phase][-1].sort_key:
                                                        _try_reserve(reservoirs[phase], capacity=samples_per_phase, priority=priority, build=make_candidate)
                                                    else:
                                                        acc.counts["qualified_candidate_count"] += 1
            player = info.get("player_id") if isinstance(info, Mapping) else None
            try:
                action = require_legal_action_id(agents[player].select_action(observation, legal_actions), legal_actions)  # type: ignore[index]
                result = game.step(action)
            except Exception:
                _add_diagnostic(policy_diagnostics, "game_progress_error")
                break
            if result.get("game_over") is True:
                done = True
                break
        opportunity += sum(agent.strategic_pass_opportunity_count for agent in agents.values())
        active += sum(agent.strategic_pass_count for agent in agents.values())
        if done:
            completed += 1
        else:
            incomplete += 1; _add_diagnostic(policy_diagnostics, "max_steps_reached")
    for phase in _PHASES:
        acc = accs[phase]
        candidates = reservoirs[phase]
        acc.counts["quota_not_selected_count"] = acc.counts["qualified_candidate_count"] - len(candidates)
        for index, candidate in enumerate(candidates):
            acc.counts["selected_sample_count"] += 1
            _record_pair(acc, candidate, suggestion_provider, off_first=index % 2 == 0, max_rollout_steps=max_rollout_steps)
    overall = _overall(accs)
    return PolicyStrategyIntentActionQualityReport(
        policy_name=name, strategic_pass_rate=rate, strategic_pass_opportunity_count=opportunity, strategic_pass_count=active,
        requested_game_count=len(seeds), completed_game_count=completed, incomplete_game_count=incomplete,
        observed_turn_count=observed, opening_skip_count=opening, eligible_sample_count=eligible, evaluated_sample_count=evaluated,
        duplicate_sample_count=duplicate, sample_limit_skipped_count=limited, overall=overall.freeze(),
        by_phase=MappingProxyType({phase: accs[phase].freeze() for phase in _PHASES}),
        diagnostic_counts=_freeze_counts(policy_diagnostics),
    )


def run_strategy_intent_action_quality(
    seeds: Sequence[int], *, suggestion_provider: SuggestionProvider,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100), samples_per_phase: int = 2,
    current_level_rank: str = "2", max_steps: int = 5000,
    max_samples_per_phase_per_game: int = 128, max_rollout_steps: int = 5000,
) -> StrategyIntentActionQualityReport:
    """Collect aggregate-only same-state off/on RuleBased rollout evidence."""
    if not _is_int(max_rollout_steps) or max_rollout_steps <= 0:
        raise ValueError("max_rollout_steps must be a positive non-bool integer")
    normalized_seeds, rates = _validate_inputs(
        seeds, suggestion_provider=suggestion_provider, strategic_pass_rates=strategic_pass_rates,
        samples_per_phase=samples_per_phase, current_level_rank=current_level_rank,
        max_steps=max_steps, max_samples_per_phase_per_game=max_samples_per_phase_per_game,
    )
    return StrategyIntentActionQualityReport(
        requested_policy_count=len(rates), current_level_rank=current_level_rank, max_steps=max_steps,
        max_samples_per_phase_per_game=max_samples_per_phase_per_game, max_rollout_steps=max_rollout_steps,
        policies=tuple(_run_policy(normalized_seeds, rate=rate, suggestion_provider=suggestion_provider,
                                   samples_per_phase=samples_per_phase, current_level_rank=current_level_rank,
                                   max_steps=max_steps, max_samples_per_phase_per_game=max_samples_per_phase_per_game,
                                   max_rollout_steps=max_rollout_steps) for rate in rates),
    )
