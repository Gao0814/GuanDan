"""Offline tie-safe Top-K and ablation metrics for J-C2b1 rank rankings."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agents.card_belief import CardBeliefState, JOKER_RANKS, NORMAL_RANKS, SUITS
from agents.card_ranker import CardRankRankingState, PlayerRankCandidate


_VALID_RANKS = frozenset(NORMAL_RANKS + JOKER_RANKS)


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _token_rank(token: str) -> str | None:
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _ratio(numerator: int, denominator: int, empty_value: float) -> float:
    if not denominator:
        return empty_value
    return max(0.0, min(1.0, numerator / denominator))


@dataclass(frozen=True, slots=True)
class RankMetricSnapshot:
    player_count: int
    truth_rank_count: int
    candidate_covered_count: int
    candidate_missed_count: int
    candidate_recall: float
    top1_hit_count: int
    top1_recall: float
    top1_selected_count: int
    top1_precision: float
    top1_average_selection_size: float
    top3_hit_count: int
    top3_recall: float
    top3_selected_count: int
    top3_precision: float
    top3_average_selection_size: float
    worst_case_mrr: float

    def to_dict(self) -> dict[str, object]:
        return {
            "player_count": self.player_count,
            "truth_rank_count": self.truth_rank_count,
            "candidate_covered_count": self.candidate_covered_count,
            "candidate_missed_count": self.candidate_missed_count,
            "candidate_recall": self.candidate_recall,
            "top1_hit_count": self.top1_hit_count,
            "top1_recall": self.top1_recall,
            "top1_selected_count": self.top1_selected_count,
            "top1_precision": self.top1_precision,
            "top1_average_selection_size": self.top1_average_selection_size,
            "top3_hit_count": self.top3_hit_count,
            "top3_recall": self.top3_recall,
            "top3_selected_count": self.top3_selected_count,
            "top3_precision": self.top3_precision,
            "top3_average_selection_size": self.top3_average_selection_size,
            "worst_case_mrr": self.worst_case_mrr,
        }


@dataclass(frozen=True, slots=True)
class RankAblationReport:
    phase: str
    valid_input: bool
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
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "valid_input": self.valid_input,
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
            "diagnostics": list(self.diagnostics),
        }


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


def _invalid_report(phase: str, diagnostics: tuple[str, ...]) -> RankAblationReport:
    zero = _zero_snapshot()
    return RankAblationReport(
        phase=phase,
        valid_input=False,
        baseline=zero,
        soft=zero,
        candidate_recall_delta=0.0,
        top1_recall_delta=0.0,
        top1_precision_delta=0.0,
        top1_average_selection_size_delta=0.0,
        top3_recall_delta=0.0,
        top3_precision_delta=0.0,
        top3_average_selection_size_delta=0.0,
        worst_case_mrr_delta=0.0,
        diagnostics=diagnostics,
    )


def _baseline_groups(
    candidates: Sequence[PlayerRankCandidate],
) -> dict[str, tuple[int, str, int]]:
    """Return rank -> (baseline tier, hard status, score) without re-ranking."""

    has_confirmed = any(candidate.hard_status == "confirmed" for candidate in candidates)
    return {
        candidate.rank: (
            1 if candidate.hard_status == "confirmed" or not has_confirmed else 2,
            candidate.hard_status,
            0,
        )
        for candidate in candidates
    }


def _soft_groups(
    candidates: Sequence[PlayerRankCandidate],
) -> dict[str, tuple[int, str, int]]:
    return {
        candidate.rank: (candidate.score_tier, candidate.hard_status, candidate.soft_score)
        for candidate in candidates
    }


def _select_tied_top_k(groups: Mapping[str, tuple[int, str, int]], k: int) -> set[str]:
    selected: set[str] = set()
    for tier in sorted({group[0] for group in groups.values()}):
        selected.update(rank for rank, group in groups.items() if group[0] == tier)
        if len(selected) >= k:
            break
    return selected


def _snapshot(
    truth_by_player: Mapping[object, set[str]],
    groups_by_player: Mapping[object, Mapping[str, tuple[int, str, int]]],
) -> RankMetricSnapshot:
    player_count = len(truth_by_player)
    truth_rank_count = sum(len(ranks) for ranks in truth_by_player.values())
    covered = sum(
        len(truth_ranks & set(groups_by_player[player_id]))
        for player_id, truth_ranks in truth_by_player.items()
    )

    def top_metrics(k: int) -> tuple[int, int]:
        selected_count = 0
        hit_count = 0
        for player_id, truth_ranks in truth_by_player.items():
            selected = _select_tied_top_k(groups_by_player[player_id], k)
            selected_count += len(selected)
            hit_count += len(selected & truth_ranks)
        return hit_count, selected_count

    top1_hits, top1_selected = top_metrics(1)
    top3_hits, top3_selected = top_metrics(3)

    reciprocal_total = 0.0
    for player_id, truth_ranks in truth_by_player.items():
        groups = groups_by_player[player_id]
        tier_end_positions: dict[int, int] = {}
        position = 0
        for tier in sorted({group[0] for group in groups.values()}):
            position += sum(1 for group in groups.values() if group[0] == tier)
            tier_end_positions[tier] = position
        for rank in truth_ranks:
            group = groups.get(rank)
            if group is not None:
                reciprocal_total += 1.0 / tier_end_positions[group[0]]

    return RankMetricSnapshot(
        player_count=player_count,
        truth_rank_count=truth_rank_count,
        candidate_covered_count=covered,
        candidate_missed_count=truth_rank_count - covered,
        candidate_recall=_ratio(covered, truth_rank_count, 1.0),
        top1_hit_count=top1_hits,
        top1_recall=_ratio(top1_hits, truth_rank_count, 1.0),
        top1_selected_count=top1_selected,
        top1_precision=(
            _ratio(top1_hits, top1_selected, 1.0 if not truth_rank_count else 0.0)
        ),
        top1_average_selection_size=(top1_selected / player_count if player_count else 0.0),
        top3_hit_count=top3_hits,
        top3_recall=_ratio(top3_hits, truth_rank_count, 1.0),
        top3_selected_count=top3_selected,
        top3_precision=(
            _ratio(top3_hits, top3_selected, 1.0 if not truth_rank_count else 0.0)
        ),
        top3_average_selection_size=(top3_selected / player_count if player_count else 0.0),
        worst_case_mrr=(reciprocal_total / truth_rank_count if truth_rank_count else 1.0),
    )


def evaluate_rank_ranking(
    card_belief: CardBeliefState,
    soft_ranking: CardRankRankingState,
    ground_truth_hands: Mapping[object, Sequence[str]],
) -> RankAblationReport:
    """Evaluate one rank-ranking sample against explicit offline truth only."""

    diagnostics: list[str] = []

    def diagnose(category: str, detail: object | None = None) -> None:
        if category not in diagnostics:
            diagnostics.append(category)
        if detail is not None:
            detailed = f"{category}:{detail}"
            if detailed not in diagnostics:
                diagnostics.append(detailed)

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")

    expected_players = {
        player.player_id: player
        for player in card_belief.players
        if (
            player.relation != "self"
            and not player.finished
            and _is_positive_int(player.remaining_count)
        )
    }

    truth_by_player: dict[object, set[str]] = {}
    if not isinstance(ground_truth_hands, Mapping):
        diagnose("missing_truth_player")
        truth_items: tuple[tuple[object, object], ...] = ()
    else:
        truth_items = tuple(ground_truth_hands.items())
    supplied_players = {player_id for player_id, _ in truth_items}
    for player_id in expected_players:
        if player_id not in supplied_players:
            diagnose("missing_truth_player", player_id)
    for player_id, hand in truth_items:
        if player_id not in expected_players:
            diagnose("unexpected_truth_player", player_id)
            continue
        public_player = expected_players[player_id]
        if isinstance(hand, (str, bytes)) or not isinstance(hand, Sequence):
            diagnose("invalid_truth_token", player_id)
            continue
        if len(hand) != public_player.remaining_count:
            diagnose("truth_hand_count_mismatch", player_id)
        ranks: set[str] = set()
        for token in hand:
            if not isinstance(token, str) or not token:
                diagnose("invalid_truth_token", player_id)
                continue
            rank = _token_rank(token)
            if rank is None:
                diagnose("invalid_truth_token", player_id)
                continue
            ranks.add(rank)
        truth_by_player[player_id] = ranks

    expected_pool = Counter({
        token: count
        for token, count in card_belief.unseen_cards_by_token.items()
        if _is_positive_int(count)
    })
    truth_pool = Counter(
        token
        for _, hand in truth_items
        if isinstance(hand, Sequence) and not isinstance(hand, (str, bytes))
        for token in hand
        if isinstance(token, str) and token
    )
    if truth_pool != expected_pool:
        diagnose("truth_pool_mismatch")

    if soft_ranking.phase != card_belief.phase:
        diagnose("ranking_phase_mismatch")

    rankings_by_player: dict[object, object] = {}
    for ranking in soft_ranking.players:
        player_id = ranking.player_id
        if player_id in rankings_by_player:
            diagnose("duplicate_ranking_player", player_id)
            continue
        rankings_by_player[player_id] = ranking
        if player_id not in expected_players:
            diagnose("unexpected_ranking_player", player_id)
            continue
        if ranking.relation != expected_players[player_id].relation:
            diagnose("relation_mismatch", player_id)
    for player_id in expected_players:
        if player_id not in rankings_by_player:
            diagnose("missing_ranking_player", player_id)

    soft_groups_by_player: dict[object, dict[str, tuple[int, str, int]]] = {}
    baseline_groups_by_player: dict[object, dict[str, tuple[int, str, int]]] = {}
    for player_id in expected_players:
        ranking = rankings_by_player.get(player_id)
        if ranking is None:
            continue
        seen_ranks: set[str] = set()
        group_to_tier: dict[tuple[str, int], int] = {}
        tier_to_group: dict[int, tuple[str, int]] = {}
        candidate_ranks: dict[str, tuple[int, str, int]] = {}
        for candidate in ranking.candidates:
            if not isinstance(candidate.rank, str):
                diagnose("invalid_candidate_rank", player_id)
                continue
            if candidate.rank in seen_ranks:
                diagnose("duplicate_candidate_rank", player_id)
                continue
            seen_ranks.add(candidate.rank)
            if candidate.rank not in _VALID_RANKS:
                diagnose("invalid_candidate_rank", player_id)
            status_is_valid = (
                isinstance(candidate.hard_status, str)
                and candidate.hard_status in {"confirmed", "possible"}
            )
            if not status_is_valid:
                diagnose("invalid_hard_status", player_id)
            count_is_valid = _is_non_negative_int(candidate.confirmed_count)
            if not count_is_valid:
                diagnose("invalid_confirmed_count", player_id)
            elif (
                (candidate.hard_status == "confirmed" and candidate.confirmed_count <= 0)
                or (candidate.hard_status == "possible" and candidate.confirmed_count != 0)
            ):
                diagnose("invalid_confirmed_count", player_id)
            score_is_valid = (
                isinstance(candidate.soft_score, int)
                and not isinstance(candidate.soft_score, bool)
                and candidate.soft_score <= 0
            )
            if not score_is_valid:
                diagnose("invalid_soft_score", player_id)
            if candidate.hard_status == "confirmed":
                if candidate.soft_score != 0:
                    diagnose("invalid_soft_score", player_id)
                if candidate.evidence:
                    diagnose("invalid_evidence_delta", player_id)
            else:
                evidence_total = 0
                for evidence in candidate.evidence:
                    if not isinstance(evidence.delta, int) or isinstance(evidence.delta, bool) or evidence.delta >= 0:
                        diagnose("invalid_evidence_delta", player_id)
                    else:
                        evidence_total += evidence.delta
                if evidence_total != candidate.soft_score:
                    diagnose("evidence_score_mismatch", player_id)
            if not _is_positive_int(candidate.score_tier):
                diagnose("invalid_score_tier", player_id)
                continue
            if not status_is_valid or not score_is_valid:
                continue
            group = (candidate.hard_status, candidate.soft_score)
            known_tier = group_to_tier.get(group)
            if known_tier is not None and known_tier != candidate.score_tier:
                diagnose("inconsistent_tier_group", player_id)
            group_at_tier = tier_to_group.get(candidate.score_tier)
            if group_at_tier is not None and group_at_tier != group:
                diagnose("inconsistent_tier_group", player_id)
            group_to_tier[group] = candidate.score_tier
            tier_to_group[candidate.score_tier] = group
            candidate_ranks[candidate.rank] = (candidate.score_tier, candidate.hard_status, candidate.soft_score)

        tiers = set(tier_to_group)
        if tiers and tiers != set(range(1, max(tiers) + 1)):
            diagnose("non_contiguous_score_tier", player_id)
        ordered_groups = sorted(
            group_to_tier,
            key=lambda group: (0 if group[0] == "confirmed" else 1, -group[1]),
        )
        for expected_tier, group in enumerate(ordered_groups, start=1):
            if group_to_tier[group] != expected_tier:
                diagnose("invalid_tier_order", player_id)
                break
        soft_groups_by_player[player_id] = candidate_ranks
        baseline_groups_by_player[player_id] = _baseline_groups(ranking.candidates)

    if diagnostics:
        return _invalid_report(card_belief.phase, tuple(diagnostics))

    baseline = _snapshot(truth_by_player, baseline_groups_by_player)
    soft = _snapshot(truth_by_player, soft_groups_by_player)
    return RankAblationReport(
        phase=card_belief.phase,
        valid_input=True,
        baseline=baseline,
        soft=soft,
        candidate_recall_delta=soft.candidate_recall - baseline.candidate_recall,
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
        diagnostics=tuple(diagnostics),
    )
