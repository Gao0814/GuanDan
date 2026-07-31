"""Controlled exact enumeration of public endgame card allocations for J-B2.

This module consumes only the immutable J-A and J-B1 outputs.  It never
interprets an observation, and it deliberately makes no probabilistic or
behavioural inference.  Search is limited to a small exact token pool so that
any confirmations come from every complete feasible allocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import factorial
from types import MappingProxyType
from typing import Mapping

from agents.card_belief import CardBeliefState, JOKER_RANKS, NORMAL_RANKS, SUITS
from agents.card_constraints import CardConstraintState


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


_RANK_ORDER = NORMAL_RANKS + JOKER_RANKS
_RANK_POSITION = {rank: position for position, rank in enumerate(_RANK_ORDER)}


def _token_rank(token: object) -> str | None:
    """Return the public rank for one exact physical token, if valid."""

    if not isinstance(token, str):
        return None
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _rank_sort_key(rank: str) -> int:
    return _RANK_POSITION[rank]


@dataclass(frozen=True, slots=True)
class PlayerAllocationBounds:
    """Token-count bounds established across complete feasible allocations."""

    player_id: object
    remaining_capacity: int
    min_count_by_token: Mapping[str, int]
    max_count_by_token: Mapping[str, int]
    confirmed_cards: tuple[str, ...]
    holding_assignment_count_by_token: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    copy_assignment_count_by_token: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    holding_assignment_count_by_rank: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    copy_assignment_count_by_rank: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "remaining_capacity": self.remaining_capacity,
            "min_count_by_token": dict(self.min_count_by_token),
            "max_count_by_token": dict(self.max_count_by_token),
            "confirmed_cards": list(self.confirmed_cards),
            "holding_assignment_count_by_token": dict(
                self.holding_assignment_count_by_token
            ),
            "copy_assignment_count_by_token": dict(
                self.copy_assignment_count_by_token
            ),
            "holding_assignment_count_by_rank": dict(
                self.holding_assignment_count_by_rank
            ),
            "copy_assignment_count_by_rank": dict(
                self.copy_assignment_count_by_rank
            ),
        }


@dataclass(frozen=True, slots=True)
class CardAllocationResult:
    """Aggregate result of a bounded deterministic allocation search."""

    phase: str
    status: str
    total_unseen_cards: int
    feasible_assignment_count: int
    search_nodes: int
    search_complete: bool
    possible_owners_by_token: Mapping[str, tuple[object, ...]]
    players: tuple[PlayerAllocationBounds, ...]
    diagnostics: tuple[str, ...]
    physical_assignment_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "status": self.status,
            "total_unseen_cards": self.total_unseen_cards,
            "feasible_assignment_count": self.feasible_assignment_count,
            "search_nodes": self.search_nodes,
            "search_complete": self.search_complete,
            "possible_owners_by_token": {
                token: list(owners)
                for token, owners in self.possible_owners_by_token.items()
            },
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
            "physical_assignment_count": self.physical_assignment_count,
        }


def _raw_token_domains(constraints: CardConstraintState) -> dict[str, tuple[object, ...]]:
    """Return a detached, order-preserving copy of J-B1 token domains."""

    return {
        token: tuple(owners)
        for token, owners in constraints.possible_owners_by_token.items()
    }


def _normalise_domain(owners: tuple[object, ...]) -> tuple[object, ...]:
    """Treat ownership domains as sets while preserving their supplied order."""

    result: list[object] = []
    for owner in owners:
        if owner not in result:
            result.append(owner)
    return tuple(result)


def enumerate_card_allocations(
    card_belief: CardBeliefState,
    constraints: CardConstraintState,
    *,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> CardAllocationResult:
    """Enumerate all bounded exact token allocations allowed by public facts.

    A token with count ``n`` is allocated as an integer vector over its allowed
    owners.  Consequently, swapping two identical copies never creates a
    second solution.  Preconditions are intentionally strict: if they fail,
    no search-derived fact is returned.
    """

    for name, value in (
        ("max_external_cards", max_external_cards),
        ("max_search_nodes", max_search_nodes),
        ("max_solutions", max_solutions),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")

    diagnostics: list[str] = []

    def diagnose(message: str) -> None:
        if message not in diagnostics:
            diagnostics.append(message)

    raw_domains = _raw_token_domains(constraints)

    token_counts: dict[str, int] = {}
    for token, count in card_belief.unseen_cards_by_token.items():
        if not _is_non_negative_int(count):
            diagnose(f"invalid_token_count:{token}")
            continue
        if count:
            token_counts[token] = count

    token_rank_counts: dict[str, int] = {}
    for token, count in token_counts.items():
        rank = _token_rank(token)
        if rank is None:
            diagnose(f"invalid_token_rank:{token}")
            continue
        token_rank_counts[rank] = token_rank_counts.get(rank, 0) + count

    rank_total = 0
    public_rank_counts: dict[str, int] = {}
    for rank, count in card_belief.unseen_cards_by_rank.items():
        if not _is_non_negative_int(count):
            diagnose(f"invalid_rank_count:{rank}")
            continue
        rank_total += count
        if count:
            if rank not in _RANK_POSITION:
                diagnose(f"rank_pool_mismatch:{rank}")
            else:
                public_rank_counts[rank] = count
    for rank in sorted(
        set(token_rank_counts) | set(public_rank_counts),
        key=lambda value: _RANK_POSITION.get(value, len(_RANK_POSITION)),
    ):
        if token_rank_counts.get(rank, 0) != public_rank_counts.get(rank, 0):
            diagnose(f"rank_pool_mismatch:{rank}")
    total_unseen = sum(token_counts.values())

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")
    if not constraints.token_constraints_exact:
        diagnose("constraints_inexact")
    if not constraints.is_consistent:
        diagnose("constraints_inconsistent")
    if card_belief.phase != constraints.phase:
        diagnose("phase_mismatch")
    if total_unseen != rank_total or total_unseen != card_belief.external_unknown_count:
        diagnose("external_count_mismatch")

    # A valid allocation owner must be a current positive-capacity external
    # player in both J-A and J-B1.  Matching the two capacities prevents a
    # hand-constructed stale constraint state from being treated as fact.
    belief_external: dict[object, int] = {}
    for player in card_belief.players:
        if (
            player.relation != "self"
            and not player.finished
            and _is_positive_int(player.remaining_count)
        ):
            belief_external[player.player_id] = player.remaining_count

    candidate_capacities: dict[object, int] = {}
    for player in constraints.players:
        if (
            player.relation != "self"
            and _is_positive_int(player.remaining_capacity)
            and player.player_id in belief_external
            and belief_external[player.player_id] == player.remaining_capacity
        ):
            candidate_capacities[player.player_id] = player.remaining_capacity

    if sum(candidate_capacities.values()) != total_unseen:
        diagnose("capacity_mismatch")

    normalised_domains: dict[str, tuple[object, ...]] = {}
    for token in token_counts:
        if token not in raw_domains:
            diagnose(f"missing_token_domain:{token}")
            continue
        owners = _normalise_domain(raw_domains[token])
        if not owners:
            diagnose(f"empty_token_domain:{token}")
            continue
        normalised_domains[token] = owners
        for owner in owners:
            if owner not in candidate_capacities:
                diagnose(f"unknown_domain_owner:{token}:{owner}")

    invalid_input = bool(diagnostics)
    # Invalid public pools fail closed even when they are also too large for
    # the bounded search.  A size skip is only meaningful for exact input.
    if invalid_input:
        return CardAllocationResult(
            phase=card_belief.phase,
            status="invalid_input",
            total_unseen_cards=total_unseen,
            feasible_assignment_count=0,
            search_nodes=0,
            search_complete=False,
            possible_owners_by_token=MappingProxyType(raw_domains),
            players=(),
            diagnostics=tuple(diagnostics),
        )

    if total_unseen > max_external_cards:
        diagnose("too_many_external_cards")
        return CardAllocationResult(
            phase=card_belief.phase,
            status="skipped_too_many_cards",
            total_unseen_cards=total_unseen,
            feasible_assignment_count=0,
            search_nodes=0,
            search_complete=False,
            possible_owners_by_token=MappingProxyType(raw_domains),
            players=(),
            diagnostics=tuple(diagnostics),
        )

    # Preserve J-B1's player order for deterministic bounds and use a stable
    # token order so mappings built in a different order still search equally.
    player_ids = tuple(candidate_capacities)
    capacities = tuple(candidate_capacities[player_id] for player_id in player_ids)
    player_index = {player_id: index for index, player_id in enumerate(player_ids)}
    tokens = tuple(sorted(token_counts))
    counts = tuple(token_counts[token] for token in tokens)
    token_ranks = tuple(_token_rank(token) for token in tokens)
    # Invalid token ranks have already fail-closed above, so each item is a
    # concrete public rank here rather than an inferred string fragment.
    ranks = tuple(sorted(token_rank_counts, key=_rank_sort_key))
    domains = tuple(
        tuple(player_index[owner] for owner in normalised_domains[token])
        for token in tokens
    )

    search_nodes = 0
    feasible_assignment_count = 0
    node_limit_reached = False
    solution_limit_reached = False
    min_counts: list[list[int]] | None = None
    max_counts: list[list[int]] | None = None
    allocation = [[0 for _ in tokens] for _ in player_ids]
    physical_assignment_count = 0
    holding_assignment_counts = [[0 for _ in tokens] for _ in player_ids]
    copy_assignment_counts = [[0 for _ in tokens] for _ in player_ids]
    holding_assignment_counts_by_rank = [[0 for _ in ranks] for _ in player_ids]
    copy_assignment_counts_by_rank = [[0 for _ in ranks] for _ in player_ids]

    def can_fill_remaining(token_index: int, remaining: tuple[int, ...]) -> bool:
        if sum(counts[token_index:]) != sum(remaining):
            return False
        for player_position, required in enumerate(remaining):
            available = sum(
                counts[index]
                for index in range(token_index, len(tokens))
                if player_position in domains[index]
            )
            if available < required:
                return False
        return True

    def distributions(
        amount: int,
        owner_positions: tuple[int, ...],
        remaining: tuple[int, ...],
    ):
        """Yield integer count splits, never individual-copy permutations."""

        chosen = [0] * len(owner_positions)

        def visit_owner(position: int, amount_left: int):
            if position == len(owner_positions) - 1:
                owner = owner_positions[position]
                if amount_left <= remaining[owner]:
                    chosen[position] = amount_left
                    yield tuple(chosen)
                return
            owner = owner_positions[position]
            upper = min(amount_left, remaining[owner])
            for assigned in range(upper + 1):
                chosen[position] = assigned
                yield from visit_owner(position + 1, amount_left - assigned)

        yield from visit_owner(0, amount)

    def record_solution() -> None:
        nonlocal feasible_assignment_count, min_counts, max_counts
        nonlocal solution_limit_reached, physical_assignment_count
        feasible_assignment_count += 1
        matrix_weight = 1
        for token_position, count in enumerate(counts):
            denominator = 1
            for player_position in range(len(player_ids)):
                denominator *= factorial(allocation[player_position][token_position])
            matrix_weight *= factorial(count) // denominator
        physical_assignment_count += matrix_weight
        for player_position in range(len(player_ids)):
            for token_position in range(len(tokens)):
                assigned = allocation[player_position][token_position]
                if assigned:
                    holding_assignment_counts[player_position][token_position] += matrix_weight
                    copy_assignment_counts[player_position][token_position] += (
                        matrix_weight * assigned
                    )
            for rank_position, rank in enumerate(ranks):
                rank_copy_count = sum(
                    allocation[player_position][token_position]
                    for token_position, token_rank in enumerate(token_ranks)
                    if token_rank == rank
                )
                if rank_copy_count:
                    holding_assignment_counts_by_rank[player_position][rank_position] += (
                        matrix_weight
                    )
                    copy_assignment_counts_by_rank[player_position][rank_position] += (
                        matrix_weight * rank_copy_count
                    )
        if min_counts is None or max_counts is None:
            min_counts = [row[:] for row in allocation]
            max_counts = [row[:] for row in allocation]
        else:
            for player_position in range(len(player_ids)):
                for token_position in range(len(tokens)):
                    current = allocation[player_position][token_position]
                    min_counts[player_position][token_position] = min(
                        min_counts[player_position][token_position], current
                    )
                    max_counts[player_position][token_position] = max(
                        max_counts[player_position][token_position], current
                    )
        if feasible_assignment_count >= max_solutions:
            solution_limit_reached = True

    def search(token_index: int, remaining: tuple[int, ...]) -> None:
        nonlocal search_nodes, node_limit_reached
        if node_limit_reached or solution_limit_reached:
            return
        if search_nodes >= max_search_nodes:
            node_limit_reached = True
            return
        search_nodes += 1
        if not can_fill_remaining(token_index, remaining):
            return
        if token_index == len(tokens):
            if not any(remaining):
                record_solution()
            return

        for split in distributions(counts[token_index], domains[token_index], remaining):
            if node_limit_reached or solution_limit_reached:
                return
            next_remaining = list(remaining)
            for owner_position, assigned in zip(domains[token_index], split):
                next_remaining[owner_position] -= assigned
                allocation[owner_position][token_index] = assigned
            search(token_index + 1, tuple(next_remaining))
            for owner_position in domains[token_index]:
                allocation[owner_position][token_index] = 0

    search(0, capacities)
    search_complete = not node_limit_reached and not solution_limit_reached

    if min_counts is None or max_counts is None:
        min_counts = [[0 for _ in tokens] for _ in player_ids]
        max_counts = [[0 for _ in tokens] for _ in player_ids]

    if search_complete:
        possible_owners = {
            token: tuple(
                player_ids[player_position]
                for player_position in range(len(player_ids))
                if max_counts[player_position][token_position] > 0
            )
            for token_position, token in enumerate(tokens)
        }
        if not feasible_assignment_count:
            diagnose("no_feasible_allocation")
            status = "no_feasible_allocation"
        else:
            status = "complete"
    else:
        # A partial traversal can expose neither confirmations nor narrowed
        # domains.  Retain J-B1 exactly as supplied for downstream auditing.
        possible_owners = raw_domains
        if node_limit_reached:
            diagnose("search_node_limit_reached")
        if solution_limit_reached:
            diagnose("solution_limit_reached")
        status = "truncated"

    players = tuple(
        PlayerAllocationBounds(
            player_id=player_id,
            remaining_capacity=capacities[player_position],
            min_count_by_token=MappingProxyType({
                token: min_counts[player_position][token_position]
                for token_position, token in enumerate(tokens)
            }),
            max_count_by_token=MappingProxyType({
                token: max_counts[player_position][token_position]
                for token_position, token in enumerate(tokens)
            }),
            confirmed_cards=(
                tuple(
                    token
                    for token_position, token in enumerate(tokens)
                    for _ in range(min_counts[player_position][token_position])
                )
                if search_complete and feasible_assignment_count
                else ()
            ),
            holding_assignment_count_by_token=(
                MappingProxyType({
                    token: holding_assignment_counts[player_position][token_position]
                    for token_position, token in enumerate(tokens)
                })
                if search_complete and feasible_assignment_count
                else MappingProxyType({})
            ),
            copy_assignment_count_by_token=(
                MappingProxyType({
                    token: copy_assignment_counts[player_position][token_position]
                    for token_position, token in enumerate(tokens)
                })
                if search_complete and feasible_assignment_count
                else MappingProxyType({})
            ),
            holding_assignment_count_by_rank=(
                MappingProxyType({
                    rank: holding_assignment_counts_by_rank[player_position][rank_position]
                    for rank_position, rank in enumerate(ranks)
                })
                if search_complete and feasible_assignment_count
                else MappingProxyType({})
            ),
            copy_assignment_count_by_rank=(
                MappingProxyType({
                    rank: copy_assignment_counts_by_rank[player_position][rank_position]
                    for rank_position, rank in enumerate(ranks)
                })
                if search_complete and feasible_assignment_count
                else MappingProxyType({})
            ),
        )
        for player_position, player_id in enumerate(player_ids)
    )

    return CardAllocationResult(
        phase=card_belief.phase,
        status=status,
        total_unseen_cards=total_unseen,
        feasible_assignment_count=feasible_assignment_count,
        search_nodes=search_nodes,
        search_complete=search_complete,
        possible_owners_by_token=MappingProxyType(possible_owners),
        players=players,
        diagnostics=tuple(diagnostics),
        physical_assignment_count=(
            physical_assignment_count
            if search_complete and feasible_assignment_count
            else 0
        ),
    )
