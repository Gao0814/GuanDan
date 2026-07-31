"""Offline-only exact scoring for J-D1b physical rank marginals.

The caller supplies ground truth explicitly.  This module never reads an
observation or engine state, and reports contain aggregate error statistics
only: they deliberately do not retain truth hands or per-player predictions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from agents.card_allocations import CardAllocationResult, PlayerAllocationBounds
from agents.card_belief import CardBeliefState, JOKER_RANKS, NORMAL_RANKS, SUITS


_VALID_RANKS = frozenset(NORMAL_RANKS + JOKER_RANKS)
_RANK_ORDER = {rank: index for index, rank in enumerate(NORMAL_RANKS + JOKER_RANKS)}


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _token_rank(token: object) -> str | None:
    if not isinstance(token, str):
        return None
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


@dataclass(frozen=True, slots=True)
class MarginalCalibrationBin:
    """Exact aggregate holding-marginal totals for one fixed probability bin."""

    bin_index: int
    prediction_count: int
    prediction_sum_numerator: int
    prediction_sum_denominator: int
    truth_positive_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "bin_index": self.bin_index,
            "prediction_count": self.prediction_count,
            "prediction_sum_numerator": self.prediction_sum_numerator,
            "prediction_sum_denominator": self.prediction_sum_denominator,
            "truth_positive_count": self.truth_positive_count,
        }


@dataclass(frozen=True, slots=True)
class MarginalEvaluationReport:
    """Aggregate exact error report for complete J-D1b physical marginals."""

    phase: str
    valid_input: bool
    prediction_source: str
    physical_assignment_count: int
    rank_pair_count: int
    truth_positive_pair_count: int
    certainty_error_count: int
    presence_brier_sum_numerator: int
    presence_brier_sum_denominator: int
    copy_squared_error_sum_numerator: int
    copy_squared_error_sum_denominator: int
    calibration_bins: tuple[MarginalCalibrationBin, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "valid_input": self.valid_input,
            "prediction_source": self.prediction_source,
            "physical_assignment_count": self.physical_assignment_count,
            "rank_pair_count": self.rank_pair_count,
            "truth_positive_pair_count": self.truth_positive_pair_count,
            "certainty_error_count": self.certainty_error_count,
            "presence_brier_sum_numerator": self.presence_brier_sum_numerator,
            "presence_brier_sum_denominator": self.presence_brier_sum_denominator,
            "copy_squared_error_sum_numerator": self.copy_squared_error_sum_numerator,
            "copy_squared_error_sum_denominator": self.copy_squared_error_sum_denominator,
            "calibration_bins": [item.to_dict() for item in self.calibration_bins],
            "diagnostics": list(self.diagnostics),
        }


def _empty_bins() -> tuple[MarginalCalibrationBin, ...]:
    return tuple(
        MarginalCalibrationBin(
            bin_index=index,
            prediction_count=0,
            prediction_sum_numerator=0,
            prediction_sum_denominator=1,
            truth_positive_count=0,
        )
        for index in range(10)
    )


def _zero_report(phase: str, diagnostics: tuple[str, ...]) -> MarginalEvaluationReport:
    return MarginalEvaluationReport(
        phase=phase,
        valid_input=False,
        prediction_source="none",
        physical_assignment_count=0,
        rank_pair_count=0,
        truth_positive_pair_count=0,
        certainty_error_count=0,
        presence_brier_sum_numerator=0,
        presence_brier_sum_denominator=1,
        copy_squared_error_sum_numerator=0,
        copy_squared_error_sum_denominator=1,
        calibration_bins=_empty_bins(),
        diagnostics=diagnostics,
    )


def evaluate_rank_marginals(
    card_belief: CardBeliefState,
    allocation: CardAllocationResult,
    ground_truth_hands: Mapping[object, Sequence[str]],
) -> MarginalEvaluationReport:
    """Score complete J-D1b rank marginals against explicit offline truth.

    The physical numerator/denominator model is only a uniform distribution
    over allocations compatible with current public hard constraints.  It is
    not a calibrated confidence model and makes no independence assumption.
    """

    diagnostics: list[str] = []

    def diagnose(message: str) -> None:
        if message not in diagnostics:
            diagnostics.append(message)

    def diagnose_detail(category: str, detail: object) -> None:
        diagnose(category)
        diagnose(f"{category}:{detail}")

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")
    if allocation.phase != card_belief.phase:
        diagnose("allocation_phase_mismatch")
    if allocation.status != "complete" or not allocation.search_complete:
        diagnose("allocation_not_complete")
    if not _is_positive_int(allocation.physical_assignment_count):
        diagnose("invalid_physical_assignment_count")

    token_counts: Counter[str] = Counter()
    rank_counts: Counter[str] = Counter()
    for token, count in card_belief.unseen_cards_by_token.items():
        rank = _token_rank(token)
        if not _is_non_negative_int(count) or rank is None:
            diagnose("allocation_card_count_mismatch")
            continue
        if count:
            token_counts[token] = count
            rank_counts[rank] += count

    public_rank_counts: Counter[str] = Counter()
    for rank, count in card_belief.unseen_cards_by_rank.items():
        if not _is_non_negative_int(count) or rank not in _VALID_RANKS:
            diagnose("rank_marginal_key_mismatch")
            continue
        if count:
            public_rank_counts[rank] = count
    if public_rank_counts != rank_counts:
        diagnose("rank_marginal_key_mismatch")

    total_cards = sum(token_counts.values())
    if (
        allocation.total_unseen_cards != total_cards
        or card_belief.external_unknown_count != total_cards
    ):
        diagnose("allocation_card_count_mismatch")

    active_players: dict[object, object] = {}
    for player in card_belief.players:
        if (
            player.relation != "self"
            and not player.finished
            and _is_positive_int(player.remaining_count)
        ):
            if player.player_id in active_players:
                diagnose_detail("missing_allocation_player", player.player_id)
            active_players[player.player_id] = player

    allocation_players: dict[object, PlayerAllocationBounds] = {}
    for player in allocation.players:
        if player.player_id in allocation_players:
            diagnose_detail("unexpected_allocation_player", player.player_id)
        allocation_players[player.player_id] = player
    for player_id in active_players:
        if player_id not in allocation_players:
            diagnose_detail("missing_allocation_player", player_id)
    for player_id in allocation_players:
        if player_id not in active_players:
            diagnose_detail("unexpected_allocation_player", player_id)

    ranks = tuple(sorted(rank_counts, key=lambda rank: _RANK_ORDER[rank]))
    denominator = allocation.physical_assignment_count
    for player_id, public_player in active_players.items():
        player = allocation_players.get(player_id)
        if player is None:
            continue
        if (
            not _is_positive_int(player.remaining_capacity)
            or player.remaining_capacity != public_player.remaining_count
        ):
            diagnose_detail("allocation_capacity_mismatch", player_id)
        holding = player.holding_assignment_count_by_rank
        copies = player.copy_assignment_count_by_rank
        if not isinstance(holding, Mapping) or not isinstance(copies, Mapping):
            diagnose_detail("rank_marginal_key_mismatch", player_id)
            continue
        if set(holding) != set(ranks) or set(copies) != set(ranks):
            diagnose_detail("rank_marginal_key_mismatch", player_id)
            continue
        for rank in ranks:
            holding_count = holding[rank]
            copy_count = copies[rank]
            if (
                not _is_non_negative_int(holding_count)
                or not _is_non_negative_int(copy_count)
                or holding_count > denominator
                or copy_count > rank_counts[rank] * denominator
            ):
                diagnose_detail("invalid_rank_marginal", f"{player_id}:{rank}")

    for rank in ranks:
        if all(
            player_id in allocation_players
            and isinstance(allocation_players[player_id].copy_assignment_count_by_rank, Mapping)
            and rank in allocation_players[player_id].copy_assignment_count_by_rank
            and _is_non_negative_int(
                allocation_players[player_id].copy_assignment_count_by_rank[rank]
            )
            for player_id in active_players
        ):
            copy_total = sum(
                allocation_players[player_id].copy_assignment_count_by_rank[rank]
                for player_id in active_players
            )
            if copy_total != rank_counts[rank] * denominator:
                diagnose_detail("rank_copy_conservation_mismatch", rank)

    truth_by_player: dict[object, Counter[str]] = {}
    if not isinstance(ground_truth_hands, Mapping):
        diagnose("missing_truth_player")
        truth_items: tuple[tuple[object, object], ...] = ()
    else:
        truth_items = tuple(ground_truth_hands.items())
    supplied_truth_players = {player_id for player_id, _ in truth_items}
    for player_id in active_players:
        if player_id not in supplied_truth_players:
            diagnose_detail("missing_truth_player", player_id)
    for player_id, hand in truth_items:
        public_player = active_players.get(player_id)
        if public_player is None:
            diagnose_detail("unexpected_truth_player", player_id)
            continue
        if isinstance(hand, (str, bytes)) or not isinstance(hand, Sequence):
            diagnose_detail("invalid_truth_token", player_id)
            continue
        if len(hand) != public_player.remaining_count:
            diagnose_detail("truth_hand_count_mismatch", player_id)
        cards: Counter[str] = Counter()
        for token in hand:
            if _token_rank(token) is None:
                diagnose_detail("invalid_truth_token", player_id)
                continue
            cards[token] += 1
        truth_by_player[player_id] = cards

    truth_pool: Counter[str] = Counter()
    for cards in truth_by_player.values():
        truth_pool.update(cards)
    if truth_pool != token_counts:
        diagnose("truth_pool_mismatch")

    if diagnostics:
        return _zero_report(card_belief.phase, tuple(diagnostics))

    presence_brier = Fraction(0, 1)
    copy_squared_error = Fraction(0, 1)
    certainty_error_count = 0
    truth_positive_pair_count = 0
    bin_counts = [0] * 10
    bin_sums = [Fraction(0, 1) for _ in range(10)]
    bin_truth_positives = [0] * 10

    for player_id in active_players:
        player = allocation_players[player_id]
        truth_rank_counts: Counter[str] = Counter()
        for token, count in truth_by_player[player_id].items():
            rank = _token_rank(token)
            if rank is not None:
                truth_rank_counts[rank] += count
        for rank in ranks:
            holding_numerator = player.holding_assignment_count_by_rank[rank]
            copy_numerator = player.copy_assignment_count_by_rank[rank]
            presence = Fraction(holding_numerator, denominator)
            expected_copies = Fraction(copy_numerator, denominator)
            truth_copies = truth_rank_counts[rank]
            truth_presence = 1 if truth_copies else 0
            truth_positive_pair_count += truth_presence
            presence_brier += (presence - truth_presence) ** 2
            copy_squared_error += (expected_copies - truth_copies) ** 2
            if (presence == 0 and truth_presence) or (presence == 1 and not truth_presence):
                certainty_error_count += 1
            bin_index = min(9, holding_numerator * 10 // denominator)
            bin_counts[bin_index] += 1
            bin_sums[bin_index] += presence
            bin_truth_positives[bin_index] += truth_presence

    calibration_bins = tuple(
        MarginalCalibrationBin(
            bin_index=index,
            prediction_count=bin_counts[index],
            prediction_sum_numerator=bin_sums[index].numerator,
            prediction_sum_denominator=bin_sums[index].denominator,
            truth_positive_count=bin_truth_positives[index],
        )
        for index in range(10)
    )
    return MarginalEvaluationReport(
        phase=card_belief.phase,
        valid_input=True,
        prediction_source="j_d1b_physical_marginals",
        physical_assignment_count=denominator,
        rank_pair_count=len(active_players) * len(ranks),
        truth_positive_pair_count=truth_positive_pair_count,
        certainty_error_count=certainty_error_count,
        presence_brier_sum_numerator=presence_brier.numerator,
        presence_brier_sum_denominator=presence_brier.denominator,
        copy_squared_error_sum_numerator=copy_squared_error.numerator,
        copy_squared_error_sum_denominator=copy_squared_error.denominator,
        calibration_bins=calibration_bins,
        diagnostics=(),
    )
