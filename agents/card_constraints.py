"""Hard public ownership constraints derived from :mod:`agents.card_belief`.

Step J-B1 deliberately does not infer hidden cards.  It records the set of
players that *could* hold each unseen card using only public remaining-hand
capacities.  A card is confirmed only when that public domain has one possible
owner and the complete external capacity is that owner's capacity.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from agents.card_belief import CardBeliefState


def _is_valid_capacity(value: object) -> bool:
    """Return whether *value* is a usable public hand capacity.

    ``bool`` is intentionally rejected even though it is an ``int`` subclass:
    a malformed payload must not silently become a one-card capacity.
    """

    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_count(value: object) -> int:
    """Return a non-negative public card count without trusting malformed input."""

    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


@dataclass(frozen=True, slots=True)
class PlayerCardConstraints:
    """The public ownership domain and capacity for one player."""

    player_id: object
    relation: str
    remaining_capacity: int
    possible_tokens: tuple[str, ...]
    possible_ranks: tuple[str, ...]
    confirmed_cards: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "relation": self.relation,
            "remaining_capacity": self.remaining_capacity,
            "possible_tokens": list(self.possible_tokens),
            "possible_ranks": list(self.possible_ranks),
            "confirmed_cards": list(self.confirmed_cards),
        }


@dataclass(frozen=True, slots=True)
class CardConstraintState:
    """Immutable public hard constraints for every unseen card domain."""

    phase: str
    possible_owners_by_token: Mapping[str, tuple[object, ...]]
    possible_owners_by_rank: Mapping[str, tuple[object, ...]]
    players: tuple[PlayerCardConstraints, ...]
    diagnostics: tuple[str, ...]
    is_consistent: bool
    token_constraints_exact: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "possible_owners_by_token": {
                token: list(owners)
                for token, owners in self.possible_owners_by_token.items()
            },
            "possible_owners_by_rank": {
                rank: list(owners)
                for rank, owners in self.possible_owners_by_rank.items()
            },
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
            "is_consistent": self.is_consistent,
            "token_constraints_exact": self.token_constraints_exact,
        }


def build_card_constraints(card_belief: CardBeliefState) -> CardConstraintState:
    """Build hard ownership domains solely from a public ``CardBeliefState``.

    No history is re-parsed and no pass, team, or behavioural signal narrows a
    domain.  Therefore every live external player with positive valid public
    capacity begins in every unseen card's domain.
    """

    diagnostics: list[str] = []
    is_consistent = True

    def diagnose(message: str, *, inconsistent: bool = False) -> None:
        nonlocal is_consistent
        if message not in diagnostics:
            diagnostics.append(message)
        if inconsistent:
            is_consistent = False

    candidate_players = []
    for player in card_belief.players:
        capacity = player.remaining_count
        if not _is_valid_capacity(capacity):
            diagnose(
                f"invalid_remaining_capacity:{player.player_id}",
                inconsistent=True,
            )
            continue
        if (
            player.relation != "self"
            and not player.finished
            and capacity > 0
        ):
            candidate_players.append(player)

    candidate_ids = tuple(player.player_id for player in candidate_players)
    candidate_capacity = sum(player.remaining_count for player in candidate_players)

    unseen_ranks = {
        rank: _positive_count(count)
        for rank, count in card_belief.unseen_cards_by_rank.items()
        if _positive_count(count)
    }
    unseen_tokens = {
        token: _positive_count(count)
        for token, count in card_belief.unseen_cards_by_token.items()
        if _positive_count(count)
    }
    unseen_count = sum(unseen_ranks.values())

    if candidate_capacity != unseen_count:
        diagnose(
            "external_capacity_mismatch:"
            f"expected={unseen_count}:actual={candidate_capacity}",
            inconsistent=True,
        )

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")

    token_constraints_exact = card_belief.token_pool_exact
    if token_constraints_exact and sum(unseen_tokens.values()) != unseen_count:
        diagnose("token_rank_count_mismatch", inconsistent=True)

    possible_owners_by_rank = {
        rank: candidate_ids for rank in unseen_ranks
    }
    possible_owners_by_token = (
        {token: candidate_ids for token in unseen_tokens}
        if token_constraints_exact
        else {}
    )

    if unseen_count and not candidate_ids:
        diagnose("no_possible_owner", inconsistent=True)

    for rank, owners in possible_owners_by_rank.items():
        if not owners:
            diagnose(f"empty_owner_domain:rank:{rank}", inconsistent=True)
    for token, owners in possible_owners_by_token.items():
        if not owners:
            diagnose(f"empty_owner_domain:token:{token}", inconsistent=True)

    # With no behavioural hard exclusions in J-B1, an exact unique domain can
    # occur only when all unseen cards fit in one qualified public capacity.
    sole_owner_id: object | None = None
    if (
        token_constraints_exact
        and is_consistent
        and len(candidate_players) == 1
        and candidate_capacity == unseen_count
    ):
        sole_owner_id = candidate_players[0].player_id

    confirmed_by_player: dict[object, tuple[str, ...]] = {}
    if sole_owner_id is not None:
        confirmed_by_player[sole_owner_id] = tuple(
            token
            for token, count in unseen_tokens.items()
            for _ in range(count)
        )

    player_constraints = tuple(
        PlayerCardConstraints(
            player_id=player.player_id,
            relation=player.relation,
            remaining_capacity=(
                player.remaining_count
                if _is_valid_capacity(player.remaining_count)
                else 0
            ),
            possible_tokens=(
                tuple(
                    token
                    for token, owners in possible_owners_by_token.items()
                    if player.player_id in owners
                )
                if token_constraints_exact
                else ()
            ),
            possible_ranks=tuple(
                rank
                for rank, owners in possible_owners_by_rank.items()
                if player.player_id in owners
            ),
            confirmed_cards=confirmed_by_player.get(player.player_id, ()),
        )
        for player in card_belief.players
    )

    return CardConstraintState(
        phase=card_belief.phase,
        possible_owners_by_token=MappingProxyType(possible_owners_by_token),
        possible_owners_by_rank=MappingProxyType(possible_owners_by_rank),
        players=player_constraints,
        diagnostics=tuple(diagnostics),
        is_consistent=is_consistent,
        token_constraints_exact=token_constraints_exact,
    )
