"""Repeatable offline endgame benchmark for the J-C2b1 rank ordering.

This module is deliberately the sole place where the offline benchmark reads
``GuanDanGame._state``.  That read is delayed until after the public-only
agent pipeline has produced a ranking, and the resulting truth mapping is
passed directly to the evaluation function without being stored in a report.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from agents.base import BaseAgent, require_legal_action_id
from agents.card_allocations import enumerate_card_allocations
from agents.card_belief import build_card_belief
from agents.card_constraints import build_card_constraints
from agents.card_ranker import build_card_rankings
from agents.card_signals import build_public_signal_state
from agents.game_phase import CRITICAL_ENDGAME, NEAR_OPEN_ENDGAME, classify_game_phase
from agents.rule_based_ai import RuleBasedAIAgent
from engine.cards import RANKS, card_to_token
from engine.game import GuanDanGame
from evaluation.ranking_metrics import (
    RankAblationReport,
    RankMetricSnapshot,
    evaluate_rank_ranking,
)


_TARGET_PHASES = (NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(values))


def _zero_snapshot() -> RankMetricSnapshot:
    return RankMetricSnapshot(
        player_count=0,
        truth_rank_count=0,
        candidate_covered_count=0,
        candidate_missed_count=0,
        candidate_recall=0.0,
        top1_hit_count=0,
        top1_recall=0.0,
        top1_selected_count=0,
        top1_precision=0.0,
        top1_average_selection_size=0.0,
        top3_hit_count=0,
        top3_recall=0.0,
        top3_selected_count=0,
        top3_precision=0.0,
        top3_average_selection_size=0.0,
        worst_case_mrr=0.0,
    )


def _ratio(numerator: int, denominator: int, empty_value: float) -> float:
    if not denominator:
        return empty_value
    return max(0.0, min(1.0, numerator / denominator))


def _diagnostic_category(diagnostic: object) -> str:
    """Collapse detailed diagnostics without retaining sample identifiers."""

    return str(diagnostic).split(":", 1)[0]


def _diagnostic_counts(reports: Sequence[RankAblationReport]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for report in reports:
        categories = {_diagnostic_category(item) for item in report.diagnostics}
        counts.update(categories)
    return counts


def _aggregate_snapshot(
    reports: Sequence[RankAblationReport],
    *,
    source: str,
) -> RankMetricSnapshot:
    """Micro-aggregate one report side from valid reports only."""

    valid_reports = tuple(report for report in reports if report.valid_input)
    if not valid_reports:
        return _zero_snapshot()

    snapshots = tuple(getattr(report, source) for report in valid_reports)
    player_count = sum(item.player_count for item in snapshots)
    truth_rank_count = sum(item.truth_rank_count for item in snapshots)
    candidate_covered_count = sum(item.candidate_covered_count for item in snapshots)
    candidate_missed_count = sum(item.candidate_missed_count for item in snapshots)
    top1_hit_count = sum(item.top1_hit_count for item in snapshots)
    top1_selected_count = sum(item.top1_selected_count for item in snapshots)
    top3_hit_count = sum(item.top3_hit_count for item in snapshots)
    top3_selected_count = sum(item.top3_selected_count for item in snapshots)

    weighted_mrr_numerator = sum(
        item.worst_case_mrr * item.truth_rank_count for item in snapshots
    )
    return RankMetricSnapshot(
        player_count=player_count,
        truth_rank_count=truth_rank_count,
        candidate_covered_count=candidate_covered_count,
        candidate_missed_count=candidate_missed_count,
        candidate_recall=_ratio(candidate_covered_count, truth_rank_count, 1.0),
        top1_hit_count=top1_hit_count,
        top1_recall=_ratio(top1_hit_count, truth_rank_count, 1.0),
        top1_selected_count=top1_selected_count,
        top1_precision=_ratio(
            top1_hit_count,
            top1_selected_count,
            1.0 if not truth_rank_count else 0.0,
        ),
        top1_average_selection_size=(
            top1_selected_count / player_count if player_count else 0.0
        ),
        top3_hit_count=top3_hit_count,
        top3_recall=_ratio(top3_hit_count, truth_rank_count, 1.0),
        top3_selected_count=top3_selected_count,
        top3_precision=_ratio(
            top3_hit_count,
            top3_selected_count,
            1.0 if not truth_rank_count else 0.0,
        ),
        top3_average_selection_size=(
            top3_selected_count / player_count if player_count else 0.0
        ),
        worst_case_mrr=(
            weighted_mrr_numerator / truth_rank_count if truth_rank_count else 1.0
        ),
    )


@dataclass(frozen=True, slots=True)
class RankBenchmarkBucket:
    """One phase's aggregate, without retaining any individual sample."""

    phase: str
    sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    baseline: RankMetricSnapshot
    soft: RankMetricSnapshot
    candidate_recall_delta: float
    top1_recall_delta: float
    top1_precision_delta: float
    top1_average_selection_size_delta: float
    top3_recall_delta: float
    top3_precision_delta: float
    top3_average_selection_size_delta: float
    worst_case_mrr_delta: float
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "sample_count": self.sample_count,
            "valid_sample_count": self.valid_sample_count,
            "invalid_sample_count": self.invalid_sample_count,
            "baseline": self.baseline.to_dict(),
            "soft": self.soft.to_dict(),
            "candidate_recall_delta": self.candidate_recall_delta,
            "top1_recall_delta": self.top1_recall_delta,
            "top1_precision_delta": self.top1_precision_delta,
            "top1_average_selection_size_delta": self.top1_average_selection_size_delta,
            "top3_recall_delta": self.top3_recall_delta,
            "top3_precision_delta": self.top3_precision_delta,
            "top3_average_selection_size_delta": self.top3_average_selection_size_delta,
            "worst_case_mrr_delta": self.worst_case_mrr_delta,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class RankBenchmarkReport:
    """Safe aggregate output of deterministic, fixed-seed benchmark games."""

    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    eligible_sample_count: int
    evaluated_sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    sample_limit_skipped_count: int
    overall: RankBenchmarkBucket
    by_phase: Mapping[str, RankBenchmarkBucket]
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_game_count": self.requested_game_count,
            "completed_game_count": self.completed_game_count,
            "incomplete_game_count": self.incomplete_game_count,
            "eligible_sample_count": self.eligible_sample_count,
            "evaluated_sample_count": self.evaluated_sample_count,
            "valid_sample_count": self.valid_sample_count,
            "invalid_sample_count": self.invalid_sample_count,
            "sample_limit_skipped_count": self.sample_limit_skipped_count,
            "overall": self.overall.to_dict(),
            "by_phase": {
                phase: bucket.to_dict() for phase, bucket in self.by_phase.items()
            },
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


def aggregate_rank_reports(
    reports: Sequence[RankAblationReport],
    *,
    phase: str,
) -> RankBenchmarkBucket:
    """Aggregate J-C2b2 reports by summing counts before deriving rates."""

    frozen_reports = tuple(reports)
    valid_sample_count = sum(1 for report in frozen_reports if report.valid_input)
    invalid_sample_count = len(frozen_reports) - valid_sample_count
    baseline = _aggregate_snapshot(frozen_reports, source="baseline")
    soft = _aggregate_snapshot(frozen_reports, source="soft")
    candidate_recall_delta = soft.candidate_recall - baseline.candidate_recall
    if candidate_recall_delta != 0.0:
        raise ValueError("candidate_recall_delta must be zero for identical hard candidates")

    diagnostic_counts = _diagnostic_counts(frozen_reports)
    return RankBenchmarkBucket(
        phase=phase,
        sample_count=len(frozen_reports),
        valid_sample_count=valid_sample_count,
        invalid_sample_count=invalid_sample_count,
        baseline=baseline,
        soft=soft,
        candidate_recall_delta=0.0,
        top1_recall_delta=soft.top1_recall - baseline.top1_recall,
        top1_precision_delta=soft.top1_precision - baseline.top1_precision,
        top1_average_selection_size_delta=(
            soft.top1_average_selection_size - baseline.top1_average_selection_size
        ),
        top3_recall_delta=soft.top3_recall - baseline.top3_recall,
        top3_precision_delta=soft.top3_precision - baseline.top3_precision,
        top3_average_selection_size_delta=(
            soft.top3_average_selection_size - baseline.top3_average_selection_size
        ),
        worst_case_mrr_delta=soft.worst_case_mrr - baseline.worst_case_mrr,
        diagnostic_counts=_freeze_counts(diagnostic_counts),
    )


def _validate_benchmark_inputs(
    seeds: Sequence[int],
    *,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_game: int,
    max_external_cards: int,
    max_search_nodes: int,
    max_solutions: int,
) -> tuple[int, ...]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    normalized_seeds = tuple(seeds)
    if any(not _is_int(seed) for seed in normalized_seeds):
        raise ValueError("each seed must be an integer")
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must not contain duplicates")
    if not isinstance(current_level_rank, str) or current_level_rank not in RANKS:
        raise ValueError("current_level_rank must be a supported normal rank")
    for name, value in (
        ("max_steps", max_steps),
        ("max_samples_per_game", max_samples_per_game),
        ("max_external_cards", max_external_cards),
        ("max_search_nodes", max_search_nodes),
        ("max_solutions", max_solutions),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")
    return normalized_seeds


def _ground_truth_hands_from_state(
    game: GuanDanGame,
    observer_player_id: object,
) -> dict[object, tuple[str, ...]]:
    """Extract offline truth only after public inference has completed."""

    state = game._state
    if state is None or state.current_player_id != observer_player_id:
        raise ValueError("offline truth observer must match the current game player")
    return {
        player.player_id: tuple(card_to_token(card) for card in player.hand_cards)
        for player in state.players
        if (
            player.player_id != observer_player_id
            and not player.is_finished
            and player.hand_cards
        )
    }


def _record_category(counts: Counter[str], category: str) -> None:
    counts[_diagnostic_category(category)] += 1


def run_rank_benchmark(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 24,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
    agent_factory: Callable[[int, int], BaseAgent] | None = None,
) -> RankBenchmarkReport:
    """Run deterministic games and evaluate only the two target endgame phases."""

    normalized_seeds = _validate_benchmark_inputs(
        seeds,
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_game=max_samples_per_game,
        max_external_cards=max_external_cards,
        max_search_nodes=max_search_nodes,
        max_solutions=max_solutions,
    )
    reports_by_phase: dict[str, list[RankAblationReport]] = {
        NEAR_OPEN_ENDGAME: [],
        CRITICAL_ENDGAME: [],
    }
    runtime_diagnostics: Counter[str] = Counter()
    seen_sample_ids: set[tuple[int, object, object]] = set()
    eligible_sample_count = 0
    sample_limit_skipped_count = 0
    completed_game_count = 0
    incomplete_game_count = 0

    for seed in normalized_seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        factory = agent_factory or (
            lambda _seed, player_id: RuleBasedAIAgent(player_id=player_id)
        )
        agents = {
            player_id: factory(seed, player_id)
            for player_id in (1, 2, 3, 4)
        }
        game_sample_count = 0
        sample_limit_reported = False
        game_over = False

        for _ in range(max_steps):
            observation = game.observe()
            phase_context = classify_game_phase(observation)
            observer_player_id = observation.get("my_info", {}).get("player_id") if isinstance(observation.get("my_info"), dict) else None
            step_no = observation.get("current_round", {}).get("step_no") if isinstance(observation.get("current_round"), dict) else None

            if phase_context.phase in _TARGET_PHASES:
                eligible_sample_count += 1
                sample_id = (seed, step_no, observer_player_id)
                if sample_id in seen_sample_ids:
                    _record_category(runtime_diagnostics, "duplicate_sample")
                else:
                    seen_sample_ids.add(sample_id)
                    if game_sample_count >= max_samples_per_game:
                        sample_limit_skipped_count += 1
                        if not sample_limit_reported:
                            _record_category(runtime_diagnostics, "sample_limit_reached")
                            sample_limit_reported = True
                    else:
                        card_belief = build_card_belief(observation, phase_context)
                        constraints = build_card_constraints(card_belief)
                        allocation = enumerate_card_allocations(
                            card_belief,
                            constraints,
                            max_external_cards=max_external_cards,
                            max_search_nodes=max_search_nodes,
                            max_solutions=max_solutions,
                        )
                        signals = build_public_signal_state(observation, card_belief)
                        ranking = build_card_rankings(
                            card_belief,
                            constraints,
                            allocation,
                            signals,
                        )
                        ground_truth_hands = _ground_truth_hands_from_state(
                            game,
                            observer_player_id,
                        )
                        report = evaluate_rank_ranking(
                            card_belief,
                            ranking,
                            ground_truth_hands,
                        )
                        reports_by_phase[phase_context.phase].append(report)
                        game_sample_count += 1

            legal_actions = game.legal_actions()
            chosen_action_id = agents[observer_player_id].select_action(
                observation,
                legal_actions,
            )
            step_result = game.step(require_legal_action_id(chosen_action_id, legal_actions))
            if bool(step_result["game_over"]):
                game_over = True
                break

        if game_over:
            completed_game_count += 1
        else:
            incomplete_game_count += 1
            _record_category(runtime_diagnostics, "max_steps_reached")

    phase_buckets = {
        phase: aggregate_rank_reports(reports_by_phase[phase], phase=phase)
        for phase in _TARGET_PHASES
    }
    all_reports = tuple(
        report for phase in _TARGET_PHASES for report in reports_by_phase[phase]
    )
    overall = aggregate_rank_reports(all_reports, phase="overall")
    combined_diagnostics = Counter(runtime_diagnostics)
    for bucket in phase_buckets.values():
        combined_diagnostics.update(bucket.diagnostic_counts)

    return RankBenchmarkReport(
        requested_game_count=len(normalized_seeds),
        completed_game_count=completed_game_count,
        incomplete_game_count=incomplete_game_count,
        eligible_sample_count=eligible_sample_count,
        evaluated_sample_count=len(all_reports),
        valid_sample_count=overall.valid_sample_count,
        invalid_sample_count=overall.invalid_sample_count,
        sample_limit_skipped_count=sample_limit_skipped_count,
        overall=overall,
        by_phase=MappingProxyType(dict(phase_buckets)),
        diagnostic_counts=_freeze_counts(combined_diagnostics),
    )
