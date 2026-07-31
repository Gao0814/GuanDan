"""Minimal, auditable rank ordering from hard domains and public pass events.

J-C2b1 is a view over existing hard facts.  It never alters ownership domains
or confirmations; a pass to an opponent's single can only lower an already
possible rank's ordering with an explicit public-event record.
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
_BASE_STRENGTH = {rank: index + 3 for index, rank in enumerate(NORMAL_RANKS)}
_BASE_STRENGTH.update({"SJ": 17, "BJ": 18})


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _token_rank(token: str) -> str | None:
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _rank_strength(rank: str, current_level_rank: str) -> int:
    """Public rank-strength mirror used only for the soft ordering rule."""

    if rank == current_level_rank:
        return 16
    return _BASE_STRENGTH[rank]


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
    *,
    pass_single_penalty: int = 1,
    max_pass_single_penalty: int = 4,
) -> CardRankRankingState:
    """Build a deterministic soft ordering without changing any hard fact."""

    for name, value in (
        ("pass_single_penalty", pass_single_penalty),
        ("max_pass_single_penalty", max_pass_single_penalty),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")

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

    current_level_rank = signals.current_level_rank
    level_is_valid = current_level_rank in NORMAL_RANKS
    if not level_is_valid:
        diagnose("invalid_level_rank")

    event_by_index: dict[int, object] = {}
    for event in signals.events:
        if event.action_index in event_by_index:
            diagnose("invalid_response_link", event.action_index)
            continue
        event_by_index[event.action_index] = event

    facts_by_player = {player.player_id: player for player in card_belief.players}
    if level_is_valid:
        for event in signals.events:
            if event.event_type != "pass":
                continue
            response_index = event.response_to_action_index
            if not isinstance(response_index, int) or isinstance(response_index, bool):
                diagnose("invalid_response_link", event.action_index)
                continue
            response = event_by_index.get(response_index)
            if response is None:
                diagnose("missing_response_event", event.action_index)
                continue
            if response.action_index >= event.action_index:
                diagnose("invalid_response_link", event.action_index)
                continue
            if (
                not _is_non_negative_int(event.round_no)
                or not _is_non_negative_int(response.round_no)
                or event.round_no != response.round_no
            ):
                diagnose("cross_round_response", event.action_index)
                continue
            if response.event_type not in {"lead", "follow"}:
                diagnose("invalid_response_link", event.action_index)
                continue
            if (
                response.declared_pattern != "single"
                or len(response.declared_ranks) != 1
                or response.declared_ranks[0] not in _RANK_SORT_INDEX
            ):
                diagnose("invalid_leading_single", event.action_index)
                continue

            pass_player = facts_by_player.get(event.player_id)
            response_player = facts_by_player.get(response.player_id)
            if (
                pass_player is None
                or response_player is None
                or not pass_player.team
                or not response_player.team
            ):
                diagnose("unknown_player_team", event.action_index)
                continue
            if pass_player.team == response_player.team:
                continue
            if event.player_id not in candidate_state:
                continue

            leading_rank = response.declared_ranks[0]
            leading_strength = _rank_strength(leading_rank, current_level_rank)
            for rank in sorted(candidate_state[event.player_id], key=_RANK_SORT_INDEX.__getitem__):
                candidate = candidate_state[event.player_id][rank]
                if candidate["confirmed_count"]:
                    continue
                if _rank_strength(rank, current_level_rank) <= leading_strength:
                    continue
                old_score = candidate["score"]
                new_score = max(-max_pass_single_penalty, old_score - pass_single_penalty)
                delta = new_score - old_score
                if not delta:
                    continue
                candidate["score"] = new_score
                candidate["evidence"].append(
                    RankScoreEvidence(
                        code="opponent_single_pass",
                        action_index=event.action_index,
                        response_action_index=response_index,
                        leading_rank=leading_rank,
                        delta=delta,
                    )
                )

    rankings: list[PlayerRankRanking] = []
    for player_id, player in eligible_players.items():
        raw_candidates = candidate_state[player_id]
        ordered = sorted(
            raw_candidates,
            key=lambda rank: (
                0 if raw_candidates[rank]["confirmed_count"] else 1,
                -raw_candidates[rank]["score"],
                _RANK_SORT_INDEX[rank],
            ),
        )
        candidates: list[PlayerRankCandidate] = []
        previous_group: tuple[str, int] | None = None
        tier = 0
        for rank in ordered:
            raw = raw_candidates[rank]
            status = "confirmed" if raw["confirmed_count"] else "possible"
            group = (status, raw["score"])
            if group != previous_group:
                tier += 1
                previous_group = group
            candidates.append(
                PlayerRankCandidate(
                    rank=rank,
                    hard_status=status,
                    confirmed_count=raw["confirmed_count"],
                    soft_score=0 if status == "confirmed" else raw["score"],
                    score_tier=tier,
                    evidence=tuple(raw["evidence"]) if status == "possible" else (),
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
