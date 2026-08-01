"""Deterministic public-API rule-rollout quality harness for paired actions."""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.card_confidence_prompt import CardConfidencePromptPayload, build_card_confidence_prompt_payload
from agents.card_confidence_pipeline import build_runtime_card_confidence
from agents.game_phase import CRITICAL_ENDGAME, GamePhaseContext, classify_game_phase
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.confidence_action_ablation import (
    SuggestionProvider, _classify_result, _external_bucket, _is_int, _policy_name,
    _priority, _prompt_actions, _prompt_pair_is_exact, _structured_prompt, _validate_inputs,
)
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_BUCKETS = ("external_0_4", "external_5_8", "external_9_12")


def _freeze(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


@dataclass(frozen=True, slots=True)
class RuleRolloutOutcome:
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
class ActionQualityBucket:
    selected_pair_count: int
    provider_off_attempted_count: int
    provider_on_attempted_count: int
    provider_off_valid_count: int
    provider_on_valid_count: int
    both_valid_pair_count: int
    same_action_count: int
    changed_action_count: int
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
    off_placement_sum_total: int
    on_placement_sum_total: int
    off_rollout_step_total: int
    on_rollout_step_total: int
    prompt_pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "diagnostic_counts"}
        result["diagnostic_counts"] = dict(self.diagnostic_counts)
        return result


@dataclass(frozen=True, slots=True)
class PolicyActionQualityReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    overall: ActionQualityBucket
    by_external_count: Mapping[str, ActionQualityBucket]
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_name": self.policy_name, "strategic_pass_rate": self.strategic_pass_rate,
            "strategic_pass_opportunity_count": self.strategic_pass_opportunity_count,
            "strategic_pass_count": self.strategic_pass_count,
            "requested_game_count": self.requested_game_count, "completed_game_count": self.completed_game_count,
            "incomplete_game_count": self.incomplete_game_count, "overall": self.overall.to_dict(),
            "by_external_count": {name: value.to_dict() for name, value in self.by_external_count.items()},
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceActionQualityReport:
    requested_policy_count: int
    by_policy: Mapping[str, PolicyActionQualityReport]

    def to_dict(self) -> dict[str, object]:
        return {"requested_policy_count": self.requested_policy_count, "by_policy": {name: value.to_dict() for name, value in self.by_policy.items()}}


class _Accumulator:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.diagnostics: Counter[str] = Counter()
        self.hasher = hashlib.sha256()

    def diagnostic(self, code: str) -> None:
        self.diagnostics[code.split(":", 1)[0]] += 1

    def digest(self, bucket: str, off: str, on: str) -> None:
        self.hasher.update(json.dumps([bucket, off, on], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    def freeze(self) -> ActionQualityBucket:
        return ActionQualityBucket(
            **{name: self.counts[name] for name in ActionQualityBucket.__dataclass_fields__ if name not in {"prompt_pair_sha256", "diagnostic_counts"}},
            prompt_pair_sha256=self.hasher.hexdigest(), diagnostic_counts=_freeze(self.diagnostics),
        )


@dataclass(slots=True)
class _Candidate:
    priority: str
    step_no: int
    player_id: int
    bucket: str
    observation: dict[str, object]
    legal_actions: list[dict[str, object]]
    prompt_actions: list[dict[str, object]]
    phase: GamePhaseContext
    payload: CardConfidencePromptPayload
    snapshot: GuanDanGame
    off_prompt: str
    on_prompt: str


def _team(player_id: int) -> str:
    return "team_13" if player_id in (1, 3) else "team_24"


def _normalize_terminal(observation: object, winner: object, observer: int, steps: int) -> RuleRolloutOutcome:
    if winner not in {"team_13", "team_24", "draw"}:
        return RuleRolloutOutcome("", 0, 0, steps, False, ("invalid_terminal_winner",))
    if not isinstance(observation, Mapping):
        return RuleRolloutOutcome("", 0, 0, steps, False, ("invalid_finish_order",))
    history = observation.get("history")
    order = history.get("finish_order") if isinstance(history, Mapping) else None
    if not isinstance(order, list) or any(not _is_int(item) or not 1 <= item <= 4 for item in order) or len(set(order)) != len(order):
        return RuleRolloutOutcome("", 0, 0, steps, False, ("invalid_finish_order",))
    if len(order) == 3:
        missing = [item for item in (1, 2, 3, 4) if item not in order]
        if len(missing) != 1:
            return RuleRolloutOutcome("", 0, 0, steps, False, ("invalid_finish_order",))
        order = order + missing
    if len(order) != 4:
        return RuleRolloutOutcome("", 0, 0, steps, False, ("invalid_finish_order",))
    team = _team(observer)
    outcome = "draw" if winner == "draw" else "win" if winner == team else "loss"
    score = {"loss": 0, "draw": 1, "win": 2}[outcome]
    partner = 4 - observer if observer in (1, 3) else 6 - observer
    placement = order.index(observer) + 1 + order.index(partner) + 1
    return RuleRolloutOutcome(outcome, score, placement, steps, True, ())


def _rollout(snapshot: GuanDanGame, action_id: object, observer: int, max_steps: int) -> RuleRolloutOutcome:
    try:
        if not _is_int(observer) or not 1 <= observer <= 4:
            return RuleRolloutOutcome("", 0, 0, 0, False, ("initial_action_invalid",))
        legal = snapshot.legal_actions()
        try:
            chosen = require_legal_action_id(action_id, legal)
        except Exception:
            return RuleRolloutOutcome("", 0, 0, 0, False, ("initial_action_invalid",))
        result = snapshot.step(chosen)
        steps = 1
        if result.get("game_over") is True:
            return _normalize_terminal(snapshot.observe(), result.get("winner"), observer, steps)
        agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        while steps < max_steps:
            observation = snapshot.observe()
            my_info = observation.get("my_info")
            player = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            legal = snapshot.legal_actions()
            if not _is_int(player) or player not in agents:
                return RuleRolloutOutcome("", 0, 0, steps, False, ("rollout_action_invalid",))
            try:
                next_id = require_legal_action_id(agents[player].select_action(observation, legal), legal)
            except Exception:
                return RuleRolloutOutcome("", 0, 0, steps, False, ("rollout_action_invalid",))
            result = snapshot.step(next_id)
            steps += 1
            if result.get("game_over") is True:
                return _normalize_terminal(snapshot.observe(), result.get("winner"), observer, steps)
        return RuleRolloutOutcome("", 0, 0, steps, False, ("rollout_step_limit_reached",))
    except Exception:
        return RuleRolloutOutcome("", 0, 0, 0, False, ("rollout_exception",))


def _compare(off: RuleRolloutOutcome, on: RuleRolloutOutcome) -> str:
    if off.team_outcome_score != on.team_outcome_score:
        return "on_better" if on.team_outcome_score > off.team_outcome_score else "off_better"
    if off.team_placement_sum != on.team_placement_sum:
        return "on_better" if on.team_placement_sum < off.team_placement_sum else "off_better"
    return "tie"


def _record_outcome(acc: _Accumulator, prefix: str, outcome: RuleRolloutOutcome) -> None:
    acc.counts[f"{prefix}_{outcome.team_outcome}_count"] += 1
    acc.counts[f"{prefix}_placement_sum_total"] += outcome.team_placement_sum
    acc.counts[f"{prefix}_rollout_step_total"] += outcome.rollout_step_count


def _overall(accs: Mapping[str, _Accumulator]) -> ActionQualityBucket:
    combined = _Accumulator()
    for name in _BUCKETS:
        combined.counts.update(accs[name].counts)
        combined.diagnostics.update(accs[name].diagnostics)
        combined.hasher.update(accs[name].hasher.digest())
    return combined.freeze()


def _validate_quality_inputs(max_rollout_steps: int, **kwargs: object) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not _is_int(max_rollout_steps) or max_rollout_steps <= 0:
        raise ValueError("max_rollout_steps must be a positive non-bool integer")
    return _validate_inputs(**kwargs)  # type: ignore[arg-type]


def _collect_policy(seeds: tuple[int, ...], *, rate: int, suggestion_provider: SuggestionProvider, samples_per_bucket: int, current_level_rank: str, max_steps: int, max_samples_per_game: int, max_external_cards: int, max_search_nodes: int, max_solutions: int, max_rollout_steps: int) -> PolicyActionQualityReport:
    name = _policy_name(rate); accs = {bucket: _Accumulator() for bucket in _BUCKETS}; selected = {bucket: [] for bucket in _BUCKETS}; runtime = Counter(); agents_all = []
    completed = incomplete = 0
    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank); game.reset()
        agents = {p: StrategicPassAIAgent(player_id=p, strategic_pass_rate=rate) for p in (1, 2, 3, 4)}; agents_all.extend(agents.values())
        critical_seen = 0; ended = False
        for _ in range(max_steps):
            observation = game.observe(); phase = classify_game_phase(observation); legal = game.legal_actions()
            my = observation.get("my_info"); rnd = observation.get("current_round"); player = my.get("player_id") if isinstance(my, Mapping) else None; step = rnd.get("step_no") if isinstance(rnd, Mapping) else None
            if phase.phase == CRITICAL_ENDGAME and _is_int(player) and _is_int(step):
                bucket = _external_bucket(phase.external_unknown_count)
                if bucket is None: runtime["unexpected_external_count"] += 1
                elif critical_seen >= max_samples_per_game: runtime["sample_limit_reached"] += 1
                else:
                    critical_seen += 1; a = accs[bucket]
                    only_pass = legal and all(item.get("declared_pattern") == "pass" for item in legal)
                    finish = _is_int(my.get("hand_count") if isinstance(my, Mapping) else None) and any(item.get("declared_pattern") != "pass" and isinstance(item.get("carrier_cards"), list) and len(item["carrier_cards"]) == my["hand_count"] for item in legal)
                    if not only_pass and not finish:
                        confidence = build_runtime_card_confidence(observation, phase, max_external_cards=max_external_cards, max_search_nodes=max_search_nodes, max_solutions=max_solutions)
                        payload = build_card_confidence_prompt_payload(confidence)
                        if confidence.status == "available" and payload.status == "ready":
                            prompt_actions = _prompt_actions(observation, legal, phase)
                            off = _structured_prompt(observation, prompt_actions, phase, None); on = _structured_prompt(observation, prompt_actions, phase, payload)
                            if prompt_actions and _prompt_pair_is_exact(off, on, payload):
                                snapshot = copy.deepcopy(game)
                                if snapshot.observe() != observation or snapshot.legal_actions() != legal:
                                    a.diagnostic("clone_mismatch")
                                else:
                                    candidate = _Candidate(_priority(name, bucket, seed, step, player), step, player, bucket, observation, legal, prompt_actions, phase, payload, snapshot, off, on)
                                    selected[bucket].append(candidate); selected[bucket].sort(key=lambda x: (x.priority, x.step_no, x.player_id))
                                    if len(selected[bucket]) > samples_per_bucket: selected[bucket].pop()
            if not _is_int(player) or player not in agents: raise RuntimeError("invalid public player")
            result = game.step(require_legal_action_id(agents[player].select_action(observation, legal), legal))
            if result.get("game_over") is True: ended = True; break
        if ended: completed += 1
        else: incomplete += 1; runtime["max_steps_reached"] += 1
    for bucket in _BUCKETS:
        a = accs[bucket]
        for index, c in enumerate(selected[bucket]):
            a.counts["selected_pair_count"] += 1; a.digest(bucket, c.off_prompt, c.on_prompt)
            legal_by_id = {item["action_id"]: item for item in c.legal_actions if _is_int(item.get("action_id"))}; prompt_ids = frozenset(item["action_id"] for item in c.prompt_actions if _is_int(item.get("action_id")))
            common = {"observation": c.observation, "legal_actions": c.legal_actions, "prompt_actions": c.prompt_actions, "rag_context": None, "hand_evaluation": None, "card_tracking_summary": None, "phase_context": c.phase, "verbose": False, "debug_prefix": "[confidence-quality]"}
            on_kwargs = dict(common); on_kwargs["card_confidence_prompt"] = c.payload
            first = ("off", common) if index % 2 == 0 else ("on", on_kwargs); second = ("on", on_kwargs) if first[0] == "off" else ("off", common)
            results = {}
            for condition, kwargs in (first, second):
                try: results[condition] = _classify_result(suggestion_provider(**kwargs), legal_by_id, prompt_ids)
                except Exception: results[condition] = ("exception", None)
                a.counts[f"provider_{condition}_attempted_count"] += 1
                if results[condition][0] == "valid": a.counts[f"provider_{condition}_valid_count"] += 1
                else: a.diagnostic(f"provider_{condition}_{results[condition][0]}")
            off_ok, on_ok = results["off"][0] == "valid", results["on"][0] == "valid"
            if not (off_ok and on_ok): continue
            a.counts["both_valid_pair_count"] += 1; same = results["off"][1] == results["on"][1]; a.counts["same_action_count" if same else "changed_action_count"] += 1
            if same:
                a.counts["rollout_branch_attempted_count"] += 1; outcome = _rollout(copy.deepcopy(c.snapshot), results["off"][1], c.player_id, max_rollout_steps); off_out = on_out = outcome; a.counts["same_action_reused_rollout_count"] += 1
                a.counts["rollout_branch_completed_count" if outcome.complete else "rollout_branch_failed_count"] += 1
            else:
                a.counts["rollout_branch_attempted_count"] += 2; off_out = _rollout(copy.deepcopy(c.snapshot), results["off"][1], c.player_id, max_rollout_steps); on_out = _rollout(copy.deepcopy(c.snapshot), results["on"][1], c.player_id, max_rollout_steps)
                for outcome in (off_out, on_out): a.counts["rollout_branch_completed_count" if outcome.complete else "rollout_branch_failed_count"] += 1
            for outcome in (off_out, on_out):
                for diagnostic in outcome.diagnostics: a.diagnostic(diagnostic)
            if not (off_out.complete and on_out.complete): a.counts["quality_unevaluable_pair_count"] += 1; continue
            a.counts["quality_evaluable_pair_count"] += 1; comparison = _compare(off_out, on_out); a.counts[f"{comparison}_count"] += 1
            if not same: a.counts[f"changed_{comparison}_count"] += 1
            _record_outcome(a, "off", off_out); _record_outcome(a, "on", on_out)
    buckets = {bucket: accs[bucket].freeze() for bucket in _BUCKETS}; diagnostics = Counter(runtime)
    for value in buckets.values(): diagnostics.update(value.diagnostic_counts)
    return PolicyActionQualityReport(name, rate, sum(agent.strategic_pass_opportunity_count for agent in agents_all), sum(agent.strategic_pass_count for agent in agents_all), len(seeds), completed, incomplete, _overall(accs), MappingProxyType(buckets), _freeze(diagnostics))


def run_confidence_action_quality(seeds: Sequence[int], *, suggestion_provider: SuggestionProvider, strategic_pass_rates: Sequence[int] = (0, 25, 50, 100), samples_per_bucket: int = 2, current_level_rank: str = "2", max_steps: int = 5000, max_samples_per_game: int = 128, max_external_cards: int = 12, max_search_nodes: int = 1_000_000, max_solutions: int = 100_000, max_rollout_steps: int = 5000) -> ConfidenceActionQualityReport:
    normalized, rates = _validate_quality_inputs(max_rollout_steps, seeds=seeds, suggestion_provider=suggestion_provider, strategic_pass_rates=strategic_pass_rates, samples_per_bucket=samples_per_bucket, current_level_rank=current_level_rank, max_steps=max_steps, max_samples_per_game=max_samples_per_game, max_external_cards=max_external_cards, max_search_nodes=max_search_nodes, max_solutions=max_solutions)
    reports = { _policy_name(rate): _collect_policy(normalized, rate=rate, suggestion_provider=suggestion_provider, samples_per_bucket=samples_per_bucket, current_level_rank=current_level_rank, max_steps=max_steps, max_samples_per_game=max_samples_per_game, max_external_cards=max_external_cards, max_search_nodes=max_search_nodes, max_solutions=max_solutions, max_rollout_steps=max_rollout_steps) for rate in rates }
    return ConfidenceActionQualityReport(len(rates), MappingProxyType(reports))
