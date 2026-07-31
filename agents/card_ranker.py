"""Neutral rank ordering projected from J-B1/J-B2 hard ownership facts.

The previously evaluated enemy-single pass signal was rejected by the
strategy-distribution benchmark.  This module therefore emits the safe
hard-only baseline: it never converts public pass events into rank scoring.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agents.card_allocations import CardAllocationResult
from agents.card_belief import CardBeliefState, JOKER_RANKS, NORMAL_RANKS, SUITS
from agents.card_constraints import CardConstraintState
from agents.card_signals import PublicSignalState


_RANK_ORDER = NORMAL_RANKS + JOKER_RANKS
_RANK_SORT_INDEX = {rank: index for index, rank in enumerate(_RANK_ORDER)}


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _token_rank(token: str) -> str | None:
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


@dataclass(frozen=True, slots=True)
class RankScoreEvidence:
    code: str
    action_index: int
    response_action_index: int
    leading_rank: str
    delta: int

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "action_index": self.action_index,
            "response_action_index": self.response_action_index,
            "leading_rank": self.leading_rank,
            "delta": self.delta,
        }


@dataclass(frozen=True, slots=True)
class PlayerRankCandidate:
    rank: str
    hard_status: str
    confirmed_count: int
    soft_score: int
    score_tier: int
    evidence: tuple[RankScoreEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "hard_status": self.hard_status,
            "confirmed_count": self.confirmed_count,
            "soft_score": self.soft_score,
            "score_tier": self.score_tier,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class PlayerRankRanking:
    player_id: object
    relation: str
    candidates: tuple[PlayerRankCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "relation": self.relation,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class CardRankRankingState:
    phase: str
    hard_source: str
    players: tuple[PlayerRankRanking, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "hard_source": self.hard_source,
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
        }


def build_card_rankings(
    card_belief: CardBeliefState,
    constraints: CardConstraintState,
    allocation: CardAllocationResult | None,
    signals: PublicSignalState,
) -> CardRankRankingState:
    """Build deterministic neutral tiers without changing hard facts."""

    diagnostics: list[str] = []

    def diagnose(category: str, detail: object | None = None) -> None:
        if category not in diagnostics:
            diagnostics.append(category)
        if detail is not None:
            detailed = f"{category}:{detail}"
            if detailed not in diagnostics:
                diagnostics.append(detailed)

    def empty(hard_source: str = "j_b1_constraints") -> CardRankRankingState:
        return CardRankRankingState(
            phase=card_belief.phase,
            hard_source=hard_source,
            players=(),
            diagnostics=tuple(diagnostics),
        )

    if not card_belief.token_pool_exact:
        diagnose("token_pool_inexact")
    if not constraints.token_constraints_exact:
        diagnose("constraints_inexact")
    if not constraints.is_consistent:
        diagnose("constraints_inconsistent")
    if (
        card_belief.phase != constraints.phase
        or card_belief.phase != signals.phase
    ):
        diagnose("phase_mismatch")

    use_allocation = False
    hard_source = "j_b1_constraints"
    if allocation is not None:
        if allocation.phase != card_belief.phase:
            diagnose("allocation_phase_mismatch")
        elif allocation.status == "complete" and allocation.search_complete:
            use_allocation = True
            hard_source = "j_b2_allocation"
        else:
            diagnose("allocation_not_complete")

    if diagnostics and any(
        item in diagnostics
        for item in (
            "token_pool_inexact",
            "constraints_inexact",
            "constraints_inconsistent",
            "phase_mismatch",
            "allocation_phase_mismatch",
        )
    ):
        return empty(hard_source)

    owner_domains = (
        allocation.possible_owners_by_token
        if use_allocation and allocation is not None
        else constraints.possible_owners_by_token
    )
    hard_players = (
        allocation.players
        if use_allocation and allocation is not None
        else constraints.players
    )

    eligible_players = {
        player.player_id: player
        for player in card_belief.players
        if (
            player.relation != "self"
            and not player.finished
            and _is_positive_int(player.remaining_count)
        )
    }
    token_ranks: dict[str, str] = {}
    for token, count in card_belief.unseen_cards_by_token.items():
        if not _is_positive_int(count):
            continue
        rank = _token_rank(token)
        if rank is None:
            diagnose("unknown_candidate_token", token)
            continue
        token_ranks[token] = rank
        if token not in owner_domains:
            diagnose("missing_token_domain", token)
            continue
        owners = owner_domains[token]
        if not owners:
            diagnose("empty_token_domain", token)
            continue
        for owner in owners:
            if owner not in eligible_players:
                diagnose("unknown_domain_owner", f"{token}:{owner}")

    if any(
        item in diagnostics
        for item in (
            "unknown_candidate_token",
            "missing_token_domain",
            "empty_token_domain",
            "unknown_domain_owner",
        )
    ):
        return empty(hard_source)

    ranks_by_player: dict[object, set[str]] = {
        player_id: set() for player_id in eligible_players
    }
    for token, rank in token_ranks.items():
        for owner in owner_domains[token]:
            ranks_by_player[owner].add(rank)

    confirmed_by_player: dict[object, Counter[str]] = {
        player_id: Counter() for player_id in eligible_players
    }
    for player in hard_players:
        if player.player_id not in confirmed_by_player:
            continue
        for token in player.confirmed_cards:
            rank = _token_rank(token)
            if rank is None:
                diagnose("unknown_candidate_token", token)
                continue
            if rank in ranks_by_player[player.player_id]:
                confirmed_by_player[player.player_id][rank] += 1

    # An unexpected confirmed token is an invalid hard input, never a source of
    # a soft-only rank.  Re-check after reading hard confirmation payloads.
    if "unknown_candidate_token" in diagnostics:
        return empty(hard_source)

    candidate_state: dict[object, dict[str, dict[str, object]]] = {}
    for player_id, ranks in ranks_by_player.items():
        candidate_state[player_id] = {
            rank: {
                "confirmed_count": confirmed_by_player[player_id][rank],
                "score": 0,
                "evidence": [],
            }
            for rank in ranks
        }

    if signals.diagnostics:
        diagnose("signal_diagnostics_present")

    rankings: list[PlayerRankRanking] = []
    for player_id, player in eligible_players.items():
        raw_candidates = candidate_state[player_id]
        ordered = sorted(
            raw_candidates,
            key=lambda rank: (
                0 if raw_candidates[rank]["confirmed_count"] else 1,
                _RANK_SORT_INDEX[rank],
            ),
        )
        candidates: list[PlayerRankCandidate] = []
        previous_group: tuple[str, int] | None = None
        tier = 0
        for rank in ordered:
            raw = raw_candidates[rank]
            status = "confirmed" if raw["confirmed_count"] else "possible"
            group = (status, 0)
            if group != previous_group:
                tier += 1
                previous_group = group
            candidates.append(
                PlayerRankCandidate(
                    rank=rank,
                    hard_status=status,
                    confirmed_count=raw["confirmed_count"],
                    soft_score=0,
                    score_tier=tier,
                    evidence=(),
                )
            )
        rankings.append(
            PlayerRankRanking(
                player_id=player_id,
                relation=player.relation,
                candidates=tuple(candidates),
            )
        )

    return CardRankRankingState(
        phase=card_belief.phase,
        hard_source=hard_source,
        players=tuple(rankings),
        diagnostics=tuple(diagnostics),
    )
