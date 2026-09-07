"""Aggregate-only full-game symmetric trial for the opt-in pressure-pass Agent."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from agents.base import BaseAgent, require_legal_action_id
from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent
from agents.rule_based_ai import FrozenRuleBasedAIAgent
from engine.game import GuanDanGame


_TEAM = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}
_TEAMS = ("team_13", "team_24")
_LEVEL_RANKS = frozenset(("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"))
_TRIAL_DIAGNOSTICS = frozenset(
    {
        "invalid_public_player",
        "agent_action_invalid",
        "game_step_invalid",
        "invalid_terminal_winner",
        "invalid_finish_order",
        "game_step_limit_reached",
    }
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _players_for(team: str) -> tuple[int, int]:
    return (1, 3) if team == "team_13" else (2, 4)


def _opposing_team(team: str) -> str:
    return "team_24" if team == "team_13" else "team_13"


def _score(outcome: str) -> int:
    return {"loss": 0, "draw": 1, "win": 2}[outcome]


@dataclass(frozen=True, slots=True)
class RuntimeTrialGameOutcome:
    candidate_outcome: str
    baseline_outcome: str
    candidate_score: int
    baseline_score: int
    candidate_placement_sum: int
    baseline_placement_sum: int
    steps: int
    opportunity_count: int
    conditional_pass_count: int
    complete: bool
    diagnostics: tuple[str, ...]


def _failed(steps: int, candidates: Sequence[ConditionalPressurePassAIAgent], code: str) -> RuntimeTrialGameOutcome:
    return RuntimeTrialGameOutcome(
        "", "", 0, 0, 0, 0, steps,
        sum(agent.opportunity_count for agent in candidates),
        sum(agent.conditional_pass_count for agent in candidates),
        False, (code,),
    )


def _normalize_terminal(
    observation: object,
    winner: object,
    candidate_team: str,
    steps: int,
    candidates: Sequence[ConditionalPressurePassAIAgent],
) -> RuntimeTrialGameOutcome:
    if winner not in {*_TEAMS, "draw"}:
        return _failed(steps, candidates, "invalid_terminal_winner")
    history = observation.get("history") if isinstance(observation, Mapping) else None
    order = history.get("finish_order") if isinstance(history, Mapping) else None
    if not isinstance(order, list) or any(not _is_int(player) or player not in _TEAM for player in order) or len(set(order)) != len(order):
        return _failed(steps, candidates, "invalid_finish_order")
    if len(order) == 3:
        missing = [player for player in _TEAM if player not in order]
        if len(missing) != 1:
            return _failed(steps, candidates, "invalid_finish_order")
        order = order + missing
    if len(order) != 4:
        return _failed(steps, candidates, "invalid_finish_order")
    baseline_team = _opposing_team(candidate_team)
    candidate_outcome = "draw" if winner == "draw" else "win" if winner == candidate_team else "loss"
    baseline_outcome = "draw" if winner == "draw" else "win" if winner == baseline_team else "loss"
    candidate_placement = sum(order.index(player) + 1 for player in _players_for(candidate_team))
    baseline_placement = sum(order.index(player) + 1 for player in _players_for(baseline_team))
    return RuntimeTrialGameOutcome(
        candidate_outcome,
        baseline_outcome,
        _score(candidate_outcome),
        _score(baseline_outcome),
        candidate_placement,
        baseline_placement,
        steps,
        sum(agent.opportunity_count for agent in candidates),
        sum(agent.conditional_pass_count for agent in candidates),
        True,
        (),
    )


def _play_trial_game(seed: int, candidate_team: str, current_level_rank: str, max_steps: int) -> RuntimeTrialGameOutcome:
    """Play one game using only public game APIs and persistent per-game Agents."""

    game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
    game.reset()
    agents: dict[int, BaseAgent] = {}
    candidates: list[ConditionalPressurePassAIAgent] = []
    for player in _TEAM:
        if _TEAM[player] == candidate_team:
            agent = ConditionalPressurePassAIAgent(player_id=player)
            candidates.append(agent)
        else:
            agent = FrozenRuleBasedAIAgent(player_id=player)
        agents[player] = agent
    for steps in range(max_steps):
        observation = game.observe()
        legal_actions = game.legal_actions()
        my_info = observation.get("my_info") if isinstance(observation, Mapping) else None
        player = my_info.get("player_id") if isinstance(my_info, Mapping) else None
        if not _is_int(player) or player not in agents:
            return _failed(steps, candidates, "invalid_public_player")
        try:
            action_id = require_legal_action_id(agents[player].select_action(observation, legal_actions), legal_actions)
        except Exception:
            return _failed(steps, candidates, "agent_action_invalid")
        try:
            result = game.step(action_id)
        except Exception:
            return _failed(steps, candidates, "game_step_invalid")
        if result.get("game_over") is True:
            return _normalize_terminal(game.observe(), result.get("winner"), candidate_team, steps + 1, candidates)
    return _failed(max_steps, candidates, "game_step_limit_reached")


def _pair_schedule(seeds: Sequence[int]) -> tuple[tuple[int, str], ...]:
    return tuple((seed, team) for seed in seeds for team in _TEAMS)


def _compare_pair(candidate_score: int, baseline_score: int, candidate_placement: int, baseline_placement: int) -> str:
    if candidate_score != baseline_score:
        return "candidate_better" if candidate_score > baseline_score else "baseline_better"
    if candidate_placement != baseline_placement:
        return "candidate_better" if candidate_placement < baseline_placement else "baseline_better"
    return "tie"


@dataclass(frozen=True, slots=True)
class ConditionalPressurePassRuntimeTrialReport:
    requested_seed_pair_count: int
    completed_seed_pair_count: int
    incomplete_seed_pair_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    scheduled_candidate_team_13_game_count: int
    scheduled_candidate_team_24_game_count: int
    current_level_rank: str
    max_steps: int
    candidate_opportunity_count: int
    candidate_conditional_pass_count: int
    active_conditional_pass_seed_pair_count: int
    candidate_win_count: int
    candidate_draw_count: int
    candidate_loss_count: int
    baseline_win_count: int
    baseline_draw_count: int
    baseline_loss_count: int
    candidate_team_outcome_score_total: int
    baseline_team_outcome_score_total: int
    candidate_placement_sum_total: int
    baseline_placement_sum_total: int
    candidate_better_count: int
    baseline_better_count: int
    tie_count: int
    trial_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "diagnostic_counts"}
        values["diagnostic_counts"] = dict(self.diagnostic_counts)
        values["decision"] = runtime_trial_decision(self)
        return values

    def canonical_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def _valid_report(report: ConditionalPressurePassRuntimeTrialReport) -> bool:
    count_names = (
        "requested_seed_pair_count", "completed_seed_pair_count", "incomplete_seed_pair_count",
        "requested_game_count", "completed_game_count", "incomplete_game_count",
        "scheduled_candidate_team_13_game_count", "scheduled_candidate_team_24_game_count",
        "max_steps", "candidate_opportunity_count", "candidate_conditional_pass_count",
        "active_conditional_pass_seed_pair_count", "candidate_win_count", "candidate_draw_count",
        "candidate_loss_count", "baseline_win_count", "baseline_draw_count", "baseline_loss_count",
        "candidate_team_outcome_score_total", "baseline_team_outcome_score_total",
        "candidate_placement_sum_total", "baseline_placement_sum_total",
        "candidate_better_count", "baseline_better_count", "tie_count",
    )
    if (
        not isinstance(report.current_level_rank, str)
        or report.current_level_rank not in _LEVEL_RANKS
        or any(type(getattr(report, name)) is not int or getattr(report, name) < 0 for name in count_names)
        or report.requested_seed_pair_count <= 0
        or report.max_steps <= 0
        or not isinstance(report.trial_sha256, str)
        or len(report.trial_sha256) != 64
        or any(character not in "0123456789abcdef" for character in report.trial_sha256)
        or not isinstance(report.diagnostic_counts, Mapping)
        or any(not isinstance(name, str) or name not in _TRIAL_DIAGNOSTICS or type(count) is not int or count <= 0 for name, count in report.diagnostic_counts.items())
    ):
        return False
    completed = report.completed_game_count
    return (
        report.requested_game_count == report.requested_seed_pair_count * 2
        and report.completed_seed_pair_count + report.incomplete_seed_pair_count == report.requested_seed_pair_count
        and report.completed_game_count + report.incomplete_game_count == report.requested_game_count
        and report.completed_seed_pair_count * 2 <= report.completed_game_count
        and report.completed_game_count <= report.completed_seed_pair_count * 2 + report.incomplete_seed_pair_count
        and report.incomplete_seed_pair_count <= report.incomplete_game_count <= report.incomplete_seed_pair_count * 2
        and report.scheduled_candidate_team_13_game_count == report.requested_seed_pair_count
        and report.scheduled_candidate_team_24_game_count == report.requested_seed_pair_count
        and report.candidate_win_count + report.candidate_draw_count + report.candidate_loss_count == completed
        and report.baseline_win_count + report.baseline_draw_count + report.baseline_loss_count == completed
        and report.candidate_win_count == report.baseline_loss_count
        and report.candidate_loss_count == report.baseline_win_count
        and report.candidate_draw_count == report.baseline_draw_count
        and report.candidate_team_outcome_score_total == report.candidate_win_count * 2 + report.candidate_draw_count
        and report.baseline_team_outcome_score_total == report.baseline_win_count * 2 + report.baseline_draw_count
        and report.candidate_placement_sum_total + report.baseline_placement_sum_total == completed * 10
        and report.candidate_conditional_pass_count == report.candidate_opportunity_count
        and 0 <= report.active_conditional_pass_seed_pair_count <= report.completed_seed_pair_count
        and report.candidate_conditional_pass_count >= report.active_conditional_pass_seed_pair_count
        and (report.active_conditional_pass_seed_pair_count == 0) == (report.candidate_conditional_pass_count == 0)
        and 3 * completed <= report.candidate_placement_sum_total <= 7 * completed
        and 3 * completed <= report.baseline_placement_sum_total <= 7 * completed
        and report.candidate_better_count + report.baseline_better_count + report.tie_count == report.completed_seed_pair_count
    )


def runtime_trial_decision(report: ConditionalPressurePassRuntimeTrialReport) -> str:
    if not _valid_report(report) or report.incomplete_game_count or report.diagnostic_counts:
        return "conditional_pressure_pass_runtime_trial_invalid"
    if report.active_conditional_pass_seed_pair_count < 20:
        return "conditional_pressure_pass_runtime_trial_evidence_insufficient"
    if (
        report.candidate_better_count > report.baseline_better_count
        and report.candidate_team_outcome_score_total >= report.baseline_team_outcome_score_total
        and report.candidate_placement_sum_total <= report.baseline_placement_sum_total
    ):
        return "retain_conditional_pressure_pass_for_botzone_opt_in_smoke"
    return "reject_conditional_pressure_pass_runtime_candidate"


def run_conditional_pressure_pass_runtime_trial(
    seeds: Sequence[int], *, current_level_rank: str = "2", max_steps: int = 5000,
) -> ConditionalPressurePassRuntimeTrialReport:
    """Run the fixed two-team-swapped full-game trial without retaining game data."""

    if (
        not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)) or not seeds
        or any(not _is_int(seed) for seed in seeds) or len(set(seeds)) != len(seeds)
        or not isinstance(current_level_rank, str) or not current_level_rank
        or not _is_int(max_steps) or max_steps <= 0
    ):
        raise ValueError("invalid_conditional_pressure_pass_runtime_trial_input")
    counts: Counter[str] = Counter()
    diagnostics: Counter[str] = Counter()
    digest = hashlib.sha256()
    for seed in seeds:
        outcomes: list[RuntimeTrialGameOutcome] = []
        for candidate_team in _TEAMS:
            counts[f"scheduled_candidate_{candidate_team}_game_count"] += 1
            outcome = _play_trial_game(seed, candidate_team, current_level_rank, max_steps)
            outcomes.append(outcome)
            counts["candidate_opportunity_count"] += outcome.opportunity_count
            counts["candidate_conditional_pass_count"] += outcome.conditional_pass_count
            for code in outcome.diagnostics:
                diagnostics[code] += 1
            digest.update(json.dumps(
                [candidate_team, outcome.complete, outcome.candidate_outcome, outcome.baseline_outcome,
                 outcome.candidate_placement_sum, outcome.baseline_placement_sum,
                 outcome.opportunity_count, outcome.conditional_pass_count],
                separators=(",", ":"),
            ).encode("utf-8"))
            if outcome.complete:
                counts["completed_game_count"] += 1
                for prefix, value in (("candidate", outcome.candidate_outcome), ("baseline", outcome.baseline_outcome)):
                    counts[f"{prefix}_{value}_count"] += 1
                counts["candidate_team_outcome_score_total"] += outcome.candidate_score
                counts["baseline_team_outcome_score_total"] += outcome.baseline_score
                counts["candidate_placement_sum_total"] += outcome.candidate_placement_sum
                counts["baseline_placement_sum_total"] += outcome.baseline_placement_sum
            else:
                counts["incomplete_game_count"] += 1
        if all(outcome.complete for outcome in outcomes):
            counts["completed_seed_pair_count"] += 1
            if any(outcome.conditional_pass_count for outcome in outcomes):
                counts["active_conditional_pass_seed_pair_count"] += 1
            comparison = _compare_pair(
                sum(outcome.candidate_score for outcome in outcomes),
                sum(outcome.baseline_score for outcome in outcomes),
                sum(outcome.candidate_placement_sum for outcome in outcomes),
                sum(outcome.baseline_placement_sum for outcome in outcomes),
            )
            counts[f"{comparison}_count"] += 1
        else:
            counts["incomplete_seed_pair_count"] += 1
    return ConditionalPressurePassRuntimeTrialReport(
        requested_seed_pair_count=len(seeds),
        completed_seed_pair_count=counts["completed_seed_pair_count"],
        incomplete_seed_pair_count=counts["incomplete_seed_pair_count"],
        requested_game_count=len(seeds) * 2,
        completed_game_count=counts["completed_game_count"],
        incomplete_game_count=counts["incomplete_game_count"],
        scheduled_candidate_team_13_game_count=counts["scheduled_candidate_team_13_game_count"],
        scheduled_candidate_team_24_game_count=counts["scheduled_candidate_team_24_game_count"],
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        candidate_opportunity_count=counts["candidate_opportunity_count"],
        candidate_conditional_pass_count=counts["candidate_conditional_pass_count"],
        active_conditional_pass_seed_pair_count=counts["active_conditional_pass_seed_pair_count"],
        candidate_win_count=counts["candidate_win_count"],
        candidate_draw_count=counts["candidate_draw_count"],
        candidate_loss_count=counts["candidate_loss_count"],
        baseline_win_count=counts["baseline_win_count"],
        baseline_draw_count=counts["baseline_draw_count"],
        baseline_loss_count=counts["baseline_loss_count"],
        candidate_team_outcome_score_total=counts["candidate_team_outcome_score_total"],
        baseline_team_outcome_score_total=counts["baseline_team_outcome_score_total"],
        candidate_placement_sum_total=counts["candidate_placement_sum_total"],
        baseline_placement_sum_total=counts["baseline_placement_sum_total"],
        candidate_better_count=counts["candidate_better_count"],
        baseline_better_count=counts["baseline_better_count"],
        tie_count=counts["tie_count"],
        trial_sha256=digest.hexdigest(),
        diagnostic_counts=MappingProxyType(dict(sorted(diagnostics.items()))),
    )
