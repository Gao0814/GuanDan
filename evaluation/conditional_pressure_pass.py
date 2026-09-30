"""Aggregate-only paired evaluation for a narrow public bomb-preservation pass.

Nothing in this module is imported by runtime policy code.  The candidate reads
only the public agent payload and always returns an action_id already supplied
by the engine.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent
from agents.rule_based_ai import FrozenRuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.terminal import terminal_team_facts


_TEAM = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, slots=True)
class RolloutOutcome:
    team_outcome: str
    team_outcome_score: int
    team_placement_sum: int
    steps: int
    complete: bool
    diagnostics: tuple[str, ...]


def _team(player: int) -> str:
    return _TEAM[player]


def _terminal(game: GuanDanGame, winner: object, observer: int, steps: int) -> RolloutOutcome:
    outcome, score, placement, diagnostic = terminal_team_facts(game.observe(), winner, observer)
    return RolloutOutcome(outcome, score, placement, steps, diagnostic is None,
                          ("invalid_terminal",) if diagnostic else ())


def _rollout(game: GuanDanGame, first_action_id: object, observer: int, max_steps: int) -> RolloutOutcome:
    try:
        legal = game.legal_actions()
        game.step(require_legal_action_id(first_action_id, legal))
        steps = 1
        agents = {player: FrozenRuleBasedAIAgent(player_id=player) for player in _TEAM}
        while steps < max_steps:
            observation = game.observe()
            my_info = observation.get("my_info") if isinstance(observation, Mapping) else None
            player = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            legal = game.legal_actions()
            if not _is_int(player) or player not in agents:
                return RolloutOutcome("", 0, 0, steps, False, ("rollout_action_invalid",))
            action = require_legal_action_id(agents[player].select_action(observation, legal), legal)
            result = game.step(action)
            steps += 1
            if result.get("game_over") is True:
                return _terminal(game, result.get("winner"), observer, steps)
        return RolloutOutcome("", 0, 0, steps, False, ("rollout_step_limit_reached",))
    except Exception:
        return RolloutOutcome("", 0, 0, 0, False, ("rollout_exception",))


def _compare(baseline: RolloutOutcome, candidate: RolloutOutcome) -> str:
    if baseline.team_outcome_score != candidate.team_outcome_score:
        return "candidate_better" if candidate.team_outcome_score > baseline.team_outcome_score else "baseline_better"
    if baseline.team_placement_sum != candidate.team_placement_sum:
        return "candidate_better" if candidate.team_placement_sum < baseline.team_placement_sum else "baseline_better"
    return "tie"


@dataclass(frozen=True, slots=True)
class ConditionalPressurePassReport:
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    max_opportunities_per_game: int
    max_game_steps: int
    max_rollout_steps: int
    opportunity_count: int
    changed_pair_count: int
    rollout_branch_attempted_count: int
    rollout_branch_completed_count: int
    rollout_branch_failed_count: int
    quality_evaluable_changed_pair_count: int
    quality_unevaluable_pair_count: int
    candidate_better_count: int
    baseline_better_count: int
    tie_count: int
    baseline_win_count: int
    baseline_draw_count: int
    baseline_loss_count: int
    candidate_win_count: int
    candidate_draw_count: int
    candidate_loss_count: int
    baseline_team_outcome_score_total: int
    candidate_team_outcome_score_total: int
    baseline_placement_sum_total: int
    candidate_placement_sum_total: int
    pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "diagnostic_counts"}
        values["diagnostic_counts"] = dict(self.diagnostic_counts)
        values["decision"] = benchmark_decision(self)
        return values

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def _valid_report(report: ConditionalPressurePassReport) -> bool:
    evaluated = report.quality_evaluable_changed_pair_count
    return (
        report.completed_game_count + report.incomplete_game_count == report.requested_game_count
        and report.rollout_branch_completed_count + report.rollout_branch_failed_count == report.rollout_branch_attempted_count
        and report.candidate_better_count + report.baseline_better_count + report.tie_count == evaluated
        and report.baseline_win_count + report.baseline_draw_count + report.baseline_loss_count == evaluated
        and report.candidate_win_count + report.candidate_draw_count + report.candidate_loss_count == evaluated
        and report.quality_unevaluable_pair_count + evaluated == report.changed_pair_count
    )


def benchmark_decision(report: ConditionalPressurePassReport) -> str:
    if not _valid_report(report) or report.incomplete_game_count or report.rollout_branch_failed_count or report.diagnostic_counts:
        return "conditional_pressure_pass_benchmark_invalid"
    if report.quality_evaluable_changed_pair_count < 20:
        return "conditional_pressure_pass_evidence_insufficient"
    if (
        report.candidate_better_count > report.baseline_better_count
        and report.candidate_team_outcome_score_total >= report.baseline_team_outcome_score_total
        and report.candidate_placement_sum_total <= report.baseline_placement_sum_total
    ):
        return "retain_conditional_pressure_pass_for_runtime_trial"
    return "reject_conditional_pressure_pass_candidate"


def run_conditional_pressure_pass_benchmark(
    seeds: Sequence[int], *, current_level_rank: str = "2", max_opportunities_per_game: int = 4,
    max_game_steps: int = 5000, max_rollout_steps: int = 5000,
) -> ConditionalPressurePassReport:
    """Run deterministic aggregate-only same-state baseline/pass comparisons."""

    if (
        not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)) or not seeds
        or any(not _is_int(seed) for seed in seeds) or len(set(seeds)) != len(seeds)
        or not isinstance(current_level_rank, str) or not current_level_rank
        or any(not _is_int(value) or value <= 0 for value in (max_opportunities_per_game, max_game_steps, max_rollout_steps))
    ):
        raise ValueError("invalid_conditional_pressure_pass_benchmark_input")
    counts: Counter[str] = Counter()
    diagnostics: Counter[str] = Counter()
    digest = hashlib.sha256()
    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {player: FrozenRuleBasedAIAgent(player_id=player) for player in _TEAM}
        selected = 0
        ended = False
        for _ in range(max_game_steps):
            observation, legal = game.observe(), game.legal_actions()
            my_info = observation.get("my_info") if isinstance(observation, Mapping) else None
            player = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            if not _is_int(player) or player not in agents:
                diagnostics["invalid_public_player"] += 1
                break
            baseline_action = agents[player].select_action(observation, legal)
            probe = ConditionalPressurePassAIAgent(player_id=player)
            candidate_action = probe.select_action(observation, legal)
            if probe.conditional_pass_count:
                counts["opportunity_count"] += 1
                if selected < max_opportunities_per_game:
                    selected += 1
                    snapshot = copy.deepcopy(game)
                    if snapshot.observe() != observation or snapshot.legal_actions() != legal:
                        diagnostics["clone_mismatch"] += 1
                    else:
                        try:
                            baseline_id = require_legal_action_id(baseline_action, legal)
                            candidate_id = require_legal_action_id(candidate_action, legal)
                        except Exception:
                            diagnostics["initial_action_invalid"] += 1
                        else:
                            if baseline_id != candidate_id:
                                counts["changed_pair_count"] += 1
                                counts["rollout_branch_attempted_count"] += 2
                                baseline = _rollout(copy.deepcopy(snapshot), baseline_id, player, max_rollout_steps)
                                candidate = _rollout(copy.deepcopy(snapshot), candidate_id, player, max_rollout_steps)
                                for prefix, outcome in (("baseline", baseline), ("candidate", candidate)):
                                    counts[f"rollout_branch_{'completed' if outcome.complete else 'failed'}_count"] += 1
                                    for diagnostic in outcome.diagnostics:
                                        diagnostics[diagnostic] += 1
                                    if outcome.complete:
                                        counts[f"{prefix}_{outcome.team_outcome}_count"] += 1
                                        counts[f"{prefix}_team_outcome_score_total"] += outcome.team_outcome_score
                                        counts[f"{prefix}_placement_sum_total"] += outcome.team_placement_sum
                                digest.update(json.dumps([baseline.complete, candidate.complete, baseline.team_outcome, candidate.team_outcome, baseline.team_placement_sum, candidate.team_placement_sum], separators=(",", ":")).encode("utf-8"))
                                if baseline.complete and candidate.complete:
                                    counts["quality_evaluable_changed_pair_count"] += 1
                                    counts[f"{_compare(baseline, candidate)}_count"] += 1
                                else:
                                    counts["quality_unevaluable_pair_count"] += 1
            try:
                result = game.step(require_legal_action_id(baseline_action, legal))
            except Exception:
                diagnostics["baseline_action_invalid"] += 1
                break
            if result.get("game_over") is True:
                ended = True
                break
        if ended:
            counts["completed_game_count"] += 1
        else:
            counts["incomplete_game_count"] += 1
            diagnostics["game_incomplete"] += 1
    return ConditionalPressurePassReport(
        requested_game_count=len(seeds), completed_game_count=counts["completed_game_count"], incomplete_game_count=counts["incomplete_game_count"],
        max_opportunities_per_game=max_opportunities_per_game, max_game_steps=max_game_steps, max_rollout_steps=max_rollout_steps,
        opportunity_count=counts["opportunity_count"], changed_pair_count=counts["changed_pair_count"],
        rollout_branch_attempted_count=counts["rollout_branch_attempted_count"], rollout_branch_completed_count=counts["rollout_branch_completed_count"], rollout_branch_failed_count=counts["rollout_branch_failed_count"],
        quality_evaluable_changed_pair_count=counts["quality_evaluable_changed_pair_count"], quality_unevaluable_pair_count=counts["quality_unevaluable_pair_count"],
        candidate_better_count=counts["candidate_better_count"], baseline_better_count=counts["baseline_better_count"], tie_count=counts["tie_count"],
        baseline_win_count=counts["baseline_win_count"], baseline_draw_count=counts["baseline_draw_count"], baseline_loss_count=counts["baseline_loss_count"],
        candidate_win_count=counts["candidate_win_count"], candidate_draw_count=counts["candidate_draw_count"], candidate_loss_count=counts["candidate_loss_count"],
        baseline_team_outcome_score_total=counts["baseline_team_outcome_score_total"], candidate_team_outcome_score_total=counts["candidate_team_outcome_score_total"],
        baseline_placement_sum_total=counts["baseline_placement_sum_total"], candidate_placement_sum_total=counts["candidate_placement_sum_total"],
        pair_sha256=digest.hexdigest(), diagnostic_counts=MappingProxyType(dict(sorted(diagnostics.items()))),
    )
