"""Offline truth metrics for the J-A/J-B1/J-B2 public belief pipeline.

The caller must explicitly supply ``ground_truth_hands``.  This module never
reads observations or engine state, and runtime agent modules do not depend on
it.  Reports intentionally contain only aggregate metrics, never truth hands.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agents.card_allocations import CardAllocationResult, PlayerAllocationBounds
from agents.card_belief import CardBeliefState
from agents.card_constraints import CardConstraintState


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _bounded_ratio(numerator: int, denominator: int, empty_value: float) -> float:
    if not denominator:
        return empty_value
    return max(0.0, min(1.0, numerator / denominator))


def _unique_owners(owners: Sequence[object]) -> tuple[object, ...]:
    """Return an order-preserving domain set for edge counting."""

    result: list[object] = []
    for owner in owners:
        if owner not in result:
            result.append(owner)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class BeliefEvaluationReport:
    """Aggregate-only offline accuracy report; it contains no truth hands."""

    phase: str
    valid_input: bool
    prediction_source: str
    truth_card_count: int
    domain_covered_count: int
    domain_missed_count: int
    domain_recall: float
    confirmed_count: int
    confirmed_correct_count: int
    false_confirmed_count: int
    confirmed_precision: float
    confirmed_coverage: float
    bound_check_count: int
    bound_violation_count: int
    bounds_valid_rate: float
    j_b1_owner_edge_count: int
    final_owner_edge_count: int
    owner_edge_reduction_count: int
    owner_edge_reduction_rate: float
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "valid_input": self.valid_input,
            "prediction_source": self.prediction_source,
            "truth_card_count": self.truth_card_count,
            "domain_covered_count": self.domain_covered_count,
            "domain_missed_count": self.domain_missed_count,
            "domain_recall": self.domain_recall,
            "confirmed_count": self.confirmed_count,
            "confirmed_correct_count": self.confirmed_correct_count,
            "false_confirmed_count": self.false_confirmed_count,
            "confirmed_precision": self.confirmed_precision,
            "confirmed_coverage": self.confirmed_coverage,
            "bound_check_count": self.bound_check_count,
            "bound_violation_count": self.bound_violation_count,
            "bounds_valid_rate": self.bounds_valid_rate,
            "j_b1_owner_edge_count": self.j_b1_owner_edge_count,
            "final_owner_edge_count": self.final_owner_edge_count,
            "owner_edge_reduction_count": self.owner_edge_reduction_count,
            "owner_edge_reduction_rate": self.owner_edge_reduction_rate,
            "diagnostics": list(self.diagnostics),
        }


def _zero_report(phase: str, diagnostics: tuple[str, ...]) -> BeliefEvaluationReport:
    """Return the prescribed non-scoring report for invalid base input."""

    return BeliefEvaluationReport(
        phase=phase,
        valid_input=False,
        prediction_source="none",
        truth_card_count=0,
        domain_covered_count=0,
        domain_missed_count=0,
        domain_recall=0.0,
        confirmed_count=0,
        confirmed_correct_count=0,
        false_confirmed_count=0,
        confirmed_precision=0.0,
        confirmed_coverage=0.0,
        bound_check_count=0,
        bound_violation_count=0,
        bounds_valid_rate=0.0,
        j_b1_owner_edge_count=0,
        final_owner_edge_count=0,
        owner_edge_reduction_count=0,
        owner_edge_reduction_rate=0.0,
        diagnostics=diagnostics,
    )


def evaluate_belief_state(
    card_belief: CardBeliefState,
    constraints: CardConstraintState,
    allocation: CardAllocationResult | None,
    ground_truth_hands: Mapping[object, Sequence[str]],
) -> BeliefEvaluationReport:
    """Evaluate public belief outputs against caller-supplied offline truth.

    The function is deliberately fail-closed.  Invalid truth or public inputs
    return an aggregate zero report rather than an exception or partial score.
    A non-complete allocation is recoverable: J-B1 remains the prediction
    source and no partial allocation bounds are scored.
    """

    diagnostics: list[str] = []

    def diagnose(message: str) -> None:
        if message not in diagnostics:
            diagnostics.append(message)

    def diagnose_detail(category: str, detail: object) -> None:
        """Keep both a stable category and an auditable public identifier."""

        diagnose(category)
        diagnose(f"{category}:{detail}")

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")
    if not constraints.token_constraints_exact:
        diagnose("constraints_inexact")
    if not constraints.is_consistent:
        diagnose("constraints_inconsistent")
    if card_belief.phase != constraints.phase:
        diagnose("phase_mismatch")

    token_counts: Counter[str] = Counter()
    for token, count in card_belief.unseen_cards_by_token.items():
        if not _is_non_negative_int(count):
            diagnose_detail("invalid_public_token_count", token)
            continue
        if count:
            token_counts[token] = count

    # Domains must exist even if no allocation result is supplied.  J-B1's
    # consistency normally guarantees non-empty domains; check it explicitly
    # to keep hand-built test fixtures from receiving a deceptive score.
    for token in token_counts:
        owners = constraints.possible_owners_by_token.get(token)
        if not owners:
            diagnose_detail("missing_constraint_domain", token)

    public_players = {player.player_id: player for player in card_belief.players}
    allowed_truth_players = {
        player_id: player
        for player_id, player in public_players.items()
        if player.relation != "self" and not player.finished
    }
    required_truth_players = {
        player_id: player
        for player_id, player in allowed_truth_players.items()
        if _is_non_negative_int(player.remaining_count) and player.remaining_count > 0
    }

    truth_by_player: dict[object, Counter[str]] = {}
    if not isinstance(ground_truth_hands, Mapping):
        diagnose("missing_truth_player")
        truth_items: tuple[tuple[object, object], ...] = ()
    else:
        truth_items = tuple(ground_truth_hands.items())

    supplied_players = {player_id for player_id, _ in truth_items}
    for player_id in required_truth_players:
        if player_id not in supplied_players:
            diagnose_detail("missing_truth_player", player_id)
    for player_id, hand in truth_items:
        if player_id not in allowed_truth_players:
            diagnose_detail("unexpected_truth_player", player_id)
            continue
        player = allowed_truth_players[player_id]
        if isinstance(hand, (str, bytes)) or not isinstance(hand, Sequence):
            diagnose_detail("invalid_truth_token", player_id)
            continue
        if not _is_non_negative_int(player.remaining_count) or len(hand) != player.remaining_count:
            diagnose_detail("truth_hand_count_mismatch", player_id)
        cards: Counter[str] = Counter()
        for token in hand:
            if not isinstance(token, str) or not token:
                diagnose_detail("invalid_truth_token", player_id)
                continue
            cards[token] += 1
        truth_by_player[player_id] = cards

    truth_pool = Counter()
    for cards in truth_by_player.values():
        truth_pool.update(cards)
    if truth_pool != token_counts:
        diagnose("truth_pool_mismatch")

    use_allocation = False
    if allocation is not None:
        if allocation.phase != card_belief.phase:
            diagnose("allocation_phase_mismatch")
        elif allocation.status != "complete" or not allocation.search_complete:
            diagnose("allocation_not_complete")
        else:
            use_allocation = True

    # All diagnostics except a non-complete allocation invalidate scoring.
    fatal_diagnostics = [
        diagnostic for diagnostic in diagnostics
        if diagnostic != "allocation_not_complete"
    ]
    if fatal_diagnostics:
        return _zero_report(card_belief.phase, tuple(diagnostics))

    final_domains = (
        allocation.possible_owners_by_token
        if use_allocation and allocation is not None
        else constraints.possible_owners_by_token
    )
    source_players = (
        allocation.players
        if use_allocation and allocation is not None
        else constraints.players
    )
    prediction_source = "j_b2_allocation" if use_allocation else "j_b1_constraints"

    truth_card_count = sum(truth_pool.values())
    domain_covered_count = sum(
        1
        for player_id, cards in truth_by_player.items()
        for token, count in cards.items()
        for _ in range(count)
        if player_id in final_domains.get(token, ())
    )
    domain_missed_count = truth_card_count - domain_covered_count

    confirmed_by_player: dict[object, Counter[str]] = {}
    for player in source_players:
        cards = confirmed_by_player.setdefault(player.player_id, Counter())
        cards.update(player.confirmed_cards)
    confirmed_count = sum(sum(cards.values()) for cards in confirmed_by_player.values())
    confirmed_correct_count = sum(
        min(count, truth_by_player.get(player_id, Counter())[token])
        for player_id, cards in confirmed_by_player.items()
        for token, count in cards.items()
    )
    false_confirmed_count = confirmed_count - confirmed_correct_count

    bound_check_count = 0
    bound_violation_count = 0
    if use_allocation and allocation is not None:
        bounds_by_player: dict[object, PlayerAllocationBounds] = {
            player.player_id: player for player in allocation.players
        }
        for player_id in required_truth_players:
            bounds = bounds_by_player.get(player_id)
            for token in token_counts:
                bound_check_count += 1
                truth_count = truth_by_player.get(player_id, Counter())[token]
                if bounds is None:
                    bound_violation_count += 1
                    continue
                lower = bounds.min_count_by_token.get(token)
                upper = bounds.max_count_by_token.get(token)
                if (
                    not _is_non_negative_int(lower)
                    or not _is_non_negative_int(upper)
                    or lower > upper
                    or truth_count < lower
                    or truth_count > upper
                ):
                    bound_violation_count += 1

    def owner_edge_count(domains: Mapping[str, Sequence[object]]) -> int:
        return sum(
            len(_unique_owners(domains.get(token, ())))
            for token in token_counts
        )

    j_b1_owner_edges = owner_edge_count(constraints.possible_owners_by_token)
    final_owner_edges = owner_edge_count(final_domains)
    edge_reduction = max(j_b1_owner_edges - final_owner_edges, 0)

    return BeliefEvaluationReport(
        phase=card_belief.phase,
        valid_input=True,
        prediction_source=prediction_source,
        truth_card_count=truth_card_count,
        domain_covered_count=domain_covered_count,
        domain_missed_count=domain_missed_count,
        domain_recall=_bounded_ratio(domain_covered_count, truth_card_count, 1.0),
        confirmed_count=confirmed_count,
        confirmed_correct_count=confirmed_correct_count,
        false_confirmed_count=false_confirmed_count,
        confirmed_precision=_bounded_ratio(
            confirmed_correct_count,
            confirmed_count,
            1.0,
        ),
        confirmed_coverage=_bounded_ratio(
            confirmed_correct_count,
            truth_card_count,
            1.0,
        ),
        bound_check_count=bound_check_count,
        bound_violation_count=bound_violation_count,
        bounds_valid_rate=_bounded_ratio(
            bound_check_count - bound_violation_count,
            bound_check_count,
            1.0,
        ),
        j_b1_owner_edge_count=j_b1_owner_edges,
        final_owner_edge_count=final_owner_edges,
        owner_edge_reduction_count=edge_reduction,
        owner_edge_reduction_rate=_bounded_ratio(
            edge_reduction,
            j_b1_owner_edges,
            0.0,
        ),
        diagnostics=tuple(diagnostics),
    )
