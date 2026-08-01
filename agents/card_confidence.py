"""Fail-closed runtime representation of exact public rank marginals."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from agents.card_allocations import CardAllocationResult
from agents.card_belief import CardBeliefState, JOKER_RANKS, NORMAL_RANKS
from agents.card_constraints import CardConstraintState
from agents.game_phase import CRITICAL_ENDGAME


_RANK_ORDER = NORMAL_RANKS + JOKER_RANKS


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_negative_int(value: object) -> bool:
    return _is_int(value) and value >= 0


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _is_usable_player_id(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _mapping(value: object) -> Mapping[object, object] | None:
    return value if isinstance(value, Mapping) else None


@dataclass(frozen=True, slots=True)
class RankMarginalConfidence:
    """Exact numerator form for one player's public rank marginal."""

    rank: str
    presence_numerator: int
    expected_copy_numerator: int
    denominator: int

    @property
    def is_certain(self) -> bool:
        return self.presence_numerator == self.denominator

    @property
    def is_impossible(self) -> bool:
        return self.presence_numerator == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "presence_numerator": self.presence_numerator,
            "expected_copy_numerator": self.expected_copy_numerator,
            "denominator": self.denominator,
            "is_certain": self.is_certain,
            "is_impossible": self.is_impossible,
        }


@dataclass(frozen=True, slots=True)
class PlayerCardConfidence:
    """Exact public rank marginals for one active external player."""

    player_id: object
    remaining_capacity: int
    ranks: tuple[RankMarginalConfidence, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "remaining_capacity": self.remaining_capacity,
            "ranks": [rank.to_dict() for rank in self.ranks],
        }


@dataclass(frozen=True, slots=True)
class CardConfidenceState:
    """Runtime-safe exact marginals, available only for verified critical input."""

    phase: str
    status: str
    source: str
    calibration_scope: str
    external_unknown_count: int
    physical_assignment_count: int
    players: tuple[PlayerCardConfidence, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "status": self.status,
            "source": self.source,
            "calibration_scope": self.calibration_scope,
            "external_unknown_count": self.external_unknown_count,
            "physical_assignment_count": self.physical_assignment_count,
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
        }


def build_card_confidence(
    card_belief: CardBeliefState,
    constraints: CardConstraintState,
    allocation: CardAllocationResult,
) -> CardConfidenceState:
    """Convert complete exact public marginals into an auditable runtime state.

    The function intentionally validates every boundary again.  It does not
    derive missing values or retain partial statistics: malformed, stale, or
    incomplete input always returns an empty unavailable state.
    """

    diagnostics: list[str] = []

    def diagnose(code: str) -> None:
        if code not in diagnostics:
            diagnostics.append(code)

    def unavailable(phase: object = "") -> CardConfidenceState:
        return CardConfidenceState(
            phase=phase if isinstance(phase, str) else "",
            status="unavailable",
            source="none",
            calibration_scope="none",
            external_unknown_count=0,
            physical_assignment_count=0,
            players=(),
            diagnostics=tuple(diagnostics),
        )

    try:
        belief_phase = card_belief.phase
        constraint_phase = constraints.phase
        allocation_phase = allocation.phase
    except (AttributeError, TypeError):
        diagnose("phase_mismatch")
        return unavailable()

    if not all(isinstance(value, str) for value in (belief_phase, constraint_phase, allocation_phase)):
        diagnose("phase_mismatch")
    elif not (belief_phase == constraint_phase == allocation_phase):
        diagnose("phase_mismatch")
    elif belief_phase != CRITICAL_ENDGAME:
        diagnose("unsupported_phase")

    if getattr(card_belief, "token_pool_exact", None) is not True:
        diagnose("token_pool_inexact")
    if not isinstance(getattr(card_belief, "diagnostics", None), tuple) or card_belief.diagnostics:
        diagnose("belief_diagnostics_present")
    if getattr(constraints, "token_constraints_exact", None) is not True:
        diagnose("constraints_inexact")
    if getattr(constraints, "is_consistent", None) is not True:
        diagnose("constraints_inconsistent")
    if not isinstance(getattr(constraints, "diagnostics", None), tuple) or constraints.diagnostics:
        diagnose("constraint_diagnostics_present")
    if getattr(allocation, "status", None) != "complete" or getattr(allocation, "search_complete", None) is not True:
        diagnose("allocation_not_complete")
    if not isinstance(getattr(allocation, "diagnostics", None), tuple) or allocation.diagnostics:
        diagnose("allocation_diagnostics_present")

    external_count = getattr(card_belief, "external_unknown_count", None)
    if not _is_int(external_count) or not 1 <= external_count <= 12:
        diagnose("invalid_external_unknown_count")
    if getattr(allocation, "total_unseen_cards", None) != external_count:
        diagnose("external_count_mismatch")
    denominator = getattr(allocation, "physical_assignment_count", None)
    if not _is_positive_int(denominator):
        diagnose("invalid_physical_assignment_count")

    rank_counts_raw = _mapping(getattr(card_belief, "unseen_cards_by_rank", None))
    if rank_counts_raw is None:
        diagnose("invalid_rank_count")
        rank_counts: dict[str, int] = {}
    else:
        rank_counts = {}
        for rank, count in rank_counts_raw.items():
            if not isinstance(rank, str) or rank not in _RANK_ORDER or not _is_non_negative_int(count):
                diagnose("invalid_rank_count")
                continue
            if count:
                rank_counts[rank] = count
    ranks = tuple(rank for rank in _RANK_ORDER if rank in rank_counts)
    if sum(rank_counts.values()) != external_count:
        diagnose("external_count_mismatch")

    belief_players = getattr(card_belief, "players", ())
    constraint_players = getattr(constraints, "players", ())
    allocation_players = getattr(allocation, "players", ())
    if not all(isinstance(value, tuple) for value in (belief_players, constraint_players, allocation_players)):
        diagnose("player_set_mismatch")
        return unavailable(belief_phase)

    belief_external: dict[object, int] = {}
    for player in belief_players:
        player_id = getattr(player, "player_id", None)
        remaining = getattr(player, "remaining_count", None)
        if not _is_usable_player_id(player_id):
            diagnose("player_set_mismatch")
            continue
        if (
            getattr(player, "relation", None) != "self"
            and not bool(getattr(player, "finished", True))
            and _is_positive_int(remaining)
        ):
            if player_id in belief_external:
                diagnose("player_set_mismatch")
            else:
                belief_external[player_id] = remaining

    constraint_external: dict[object, int] = {}
    for player in constraint_players:
        player_id = getattr(player, "player_id", None)
        remaining = getattr(player, "remaining_capacity", None)
        if getattr(player, "relation", None) == "self":
            continue
        if not _is_usable_player_id(player_id):
            diagnose("player_set_mismatch")
            continue
        if _is_positive_int(remaining):
            if player_id in constraint_external:
                diagnose("player_set_mismatch")
            else:
                constraint_external[player_id] = remaining
        elif player_id in belief_external:
            diagnose("capacity_mismatch")
        elif player_id not in belief_external:
            # Standard J-B1 output can retain zero-capacity finished players,
            # but a positive-capacity external candidate cannot be omitted.
            continue

    allocation_external: dict[object, object] = {}
    for player in allocation_players:
        player_id = getattr(player, "player_id", None)
        if not _is_usable_player_id(player_id):
            diagnose("player_set_mismatch")
            continue
        if player_id in allocation_external:
            diagnose("player_set_mismatch")
        else:
            allocation_external[player_id] = player

    if (
        set(constraint_external) != set(belief_external)
        or set(allocation_external) != set(belief_external)
    ):
        diagnose("player_set_mismatch")
    if sum(belief_external.values()) != external_count:
        diagnose("capacity_mismatch")
    if any(constraint_external.get(player_id) != remaining for player_id, remaining in belief_external.items()):
        diagnose("capacity_mismatch")

    output_players: list[PlayerCardConfidence] = []
    validated_copies: dict[object, dict[str, int]] = {}
    for player in allocation_players:
        player_id = getattr(player, "player_id", None)
        remaining = getattr(player, "remaining_capacity", None)
        if not _is_usable_player_id(player_id):
            diagnose("player_set_mismatch")
            continue
        if player_id not in belief_external or remaining != belief_external[player_id]:
            diagnose("capacity_mismatch")
            continue
        holding = _mapping(getattr(player, "holding_assignment_count_by_rank", None))
        copies = _mapping(getattr(player, "copy_assignment_count_by_rank", None))
        if holding is None or copies is None or set(holding) != set(ranks) or set(copies) != set(ranks):
            diagnose("rank_key_mismatch")
            continue
        player_ranks: list[RankMarginalConfidence] = []
        player_copy_values: dict[str, int] = {}
        for rank in ranks:
            presence = holding.get(rank)
            copy_count = copies.get(rank)
            if not _is_non_negative_int(presence) or (denominator is not None and _is_positive_int(denominator) and presence > denominator):
                diagnose("invalid_presence_numerator")
                continue
            if not _is_non_negative_int(copy_count):
                diagnose("invalid_copy_numerator")
                continue
            if _is_positive_int(denominator):
                maximum_copies = min(remaining, rank_counts[rank]) * denominator
                if copy_count > maximum_copies:
                    diagnose("invalid_copy_numerator")
                    continue
            player_copy_values[rank] = copy_count
            player_ranks.append(
                RankMarginalConfidence(
                    rank=rank,
                    presence_numerator=presence,
                    expected_copy_numerator=copy_count,
                    denominator=denominator if _is_positive_int(denominator) else 1,
                )
            )
        output_players.append(
            PlayerCardConfidence(
                player_id=player_id,
                remaining_capacity=remaining,
                ranks=tuple(player_ranks),
            )
        )
        validated_copies[player_id] = player_copy_values

    if diagnostics:
        return unavailable(belief_phase)

    if _is_positive_int(denominator):
        for rank in ranks:
            total_copies = sum(values[rank] for values in validated_copies.values())
            if total_copies != rank_counts[rank] * denominator:
                diagnose("copy_conservation_mismatch")

    if diagnostics:
        return unavailable(belief_phase)
    return CardConfidenceState(
        phase=belief_phase,
        status="available",
        source="physical_assignment_marginal_v1",
        calibration_scope="critical_endgame_policy_diverse_v1",
        external_unknown_count=external_count,
        physical_assignment_count=denominator,
        players=tuple(output_players),
        diagnostics=(),
    )
