"""Deterministic critical-endgame corpus collection for J-D1 marginals.

This is an evaluation-only development collector.  It records aggregate
statistics, never samples or truth details, and only feeds explicit truth to
the single-sample evaluator after all public inference has completed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from agents.base import BaseAgent, require_legal_action_id
from agents.card_allocations import enumerate_card_allocations
from agents.card_belief import NORMAL_RANKS, build_card_belief
from agents.card_constraints import build_card_constraints
from agents.game_phase import CRITICAL_ENDGAME, classify_game_phase
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.benchmark_truth import extract_ground_truth_hands
from evaluation.marginal_benchmark import (
    MarginalBenchmarkBucket,
    aggregate_marginal_reports,
)
from evaluation.marginal_metrics import MarginalEvaluationReport, evaluate_rank_marginals


_EXTERNAL_BUCKETS = (
    ("external_0_4", 0, 4),
    ("external_5_8", 5, 8),
    ("external_9_12", 9, 12),
)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _diagnostic_category(value: object) -> str:
    return str(value).split(":", 1)[0]


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


def _record_category(counts: Counter[str], category: object) -> None:
    counts[_diagnostic_category(category)] += 1


def _validate_inputs(
    seeds: Sequence[int],
    *,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_game: int,
    max_external_cards: int,
    max_search_nodes: int,
    max_solutions: int,
    agent_factory: Callable[[int, int], BaseAgent] | None,
) -> tuple[int, ...]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    normalized_seeds = tuple(seeds)
    if any(not _is_int(seed) for seed in normalized_seeds):
        raise ValueError("each seed must be an integer")
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must not contain duplicates")
    if not isinstance(current_level_rank, str) or current_level_rank not in NORMAL_RANKS:
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
    if max_external_cards > 12:
        raise ValueError("max_external_cards must not exceed 12")
    if agent_factory is not None and not callable(agent_factory):
        raise ValueError("agent_factory must be callable or None")
    return normalized_seeds


def _external_bucket(external_unknown_count: object) -> str | None:
    if not isinstance(external_unknown_count, int) or isinstance(external_unknown_count, bool):
        return None
    for name, lower, upper in _EXTERNAL_BUCKETS:
        if lower <= external_unknown_count <= upper:
            return name
    return None


@dataclass(frozen=True, slots=True)
class MarginalCorpusReport:
    """Aggregate-only result of deterministic critical-endgame collection."""

    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    eligible_sample_count: int
    evaluated_sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    sample_limit_skipped_count: int
    overall: MarginalBenchmarkBucket
    by_external_count: Mapping[str, MarginalBenchmarkBucket]
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
            "by_external_count": {
                name: bucket.to_dict()
                for name, bucket in self.by_external_count.items()
            },
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


def run_marginal_corpus(
    seeds: Sequence[int],
    *,
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
    agent_factory: Callable[[int, int], BaseAgent] | None = None,
) -> MarginalCorpusReport:
    """Collect only complete-scoring candidates in ``critical_endgame``.

    The evaluator receives an invalid report for a truncated or otherwise
    inconsistent allocation.  Such reports remain auditable in aggregate but
    never contribute pair-level calibration statistics.
    """

    normalized_seeds = _validate_inputs(
        seeds,
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_game=max_samples_per_game,
        max_external_cards=max_external_cards,
        max_search_nodes=max_search_nodes,
        max_solutions=max_solutions,
        agent_factory=agent_factory,
    )
    reports_by_bucket: dict[str, list[MarginalEvaluationReport]] = {
        name: [] for name, _, _ in _EXTERNAL_BUCKETS
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
        agents = {player_id: factory(seed, player_id) for player_id in (1, 2, 3, 4)}
        game_sample_count = 0
        sample_limit_reported = False
        game_over = False

        for _ in range(max_steps):
            observation = game.observe()
            phase_context = classify_game_phase(observation)
            my_info = observation.get("my_info")
            current_round = observation.get("current_round")
            observer_player_id = my_info.get("player_id") if isinstance(my_info, dict) else None
            step_no = current_round.get("step_no") if isinstance(current_round, dict) else None

            if phase_context.phase == CRITICAL_ENDGAME:
                eligible_sample_count += 1
                sample_id = (seed, step_no, observer_player_id)
                if sample_id in seen_sample_ids:
                    _record_category(runtime_diagnostics, "duplicate_sample")
                else:
                    seen_sample_ids.add(sample_id)
                    bucket_name = _external_bucket(phase_context.external_unknown_count)
                    if bucket_name is None:
                        _record_category(runtime_diagnostics, "unexpected_external_count")
                    elif game_sample_count >= max_samples_per_game:
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
                        truth = extract_ground_truth_hands(game, observer_player_id)
                        report = evaluate_rank_marginals(card_belief, allocation, truth)
                        reports_by_bucket[bucket_name].append(report)
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

    external_buckets = {
        name: aggregate_marginal_reports(reports_by_bucket[name], phase=CRITICAL_ENDGAME)
        for name, _, _ in _EXTERNAL_BUCKETS
    }
    all_reports = tuple(
        report
        for name, _, _ in _EXTERNAL_BUCKETS
        for report in reports_by_bucket[name]
    )
    overall = aggregate_marginal_reports(all_reports, phase="overall")
    combined_diagnostics = Counter(runtime_diagnostics)
    combined_diagnostics.update(overall.diagnostic_counts)

    return MarginalCorpusReport(
        requested_game_count=len(normalized_seeds),
        completed_game_count=completed_game_count,
        incomplete_game_count=incomplete_game_count,
        eligible_sample_count=eligible_sample_count,
        evaluated_sample_count=len(all_reports),
        valid_sample_count=overall.valid_sample_count,
        invalid_sample_count=overall.invalid_sample_count,
        sample_limit_skipped_count=sample_limit_skipped_count,
        overall=overall,
        by_external_count=MappingProxyType(dict(external_buckets)),
        diagnostic_counts=_freeze_counts(combined_diagnostics),
    )
