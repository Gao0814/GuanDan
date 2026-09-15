"""Fail-closed residual structure facts derived from public action payloads."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


_NORMAL_RANKS = frozenset({"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"})
_SUITS = frozenset({"S", "H", "C", "D"})
_PATTERNS = frozenset(
    {
        "single",
        "pair",
        "triple",
        "triple_with_pair",
        "straight",
        "pair_straight",
        "steel_plate",
        "bomb",
        "straight_flush",
        "joker_bomb",
    }
)


@dataclass(frozen=True, slots=True)
class FreeLeadResidualStructure:
    """Public, non-prescriptive facts about one canonical free-lead action."""

    action_id: int
    clears_played_rank_groups: bool
    residual_singleton_rank_count: int
    estimated_remaining_rank_groups: int


@dataclass(frozen=True, slots=True)
class CandidateStructure:
    """Compact, public-only comparison facts for one canonical action.

    These facts deliberately describe the visible before/after hand only.  They
    are not a valuation, a legality check, or a prediction of who wins a trick.
    ``None`` fields mean that the public payload did not establish that fact.
    """

    action_id: int
    pattern: str
    carrier_count: int
    uses_wildcard: bool
    finishes_hand: bool
    clears_played_rank_groups: bool
    residual_singleton_rank_count: int
    estimated_remaining_rank_groups: int
    fragments_played_rank_group: bool
    natural_single_rank_value: int | None
    consumes_control_resource: bool
    bomb_length: int | None
    leaves_bomb_rank_singleton: bool | None
    teammate_hand_count: int | None
    minimum_opponent_hand_count: int | None
    is_free_lead: bool


_RANK_VALUES = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15,
    "SJ": 16, "BJ": 17,
}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _rank_of(token: str) -> str:
    if token in {"SJ", "BJ"}:
        return token
    return token[:-1]


def _valid_token(token: object) -> bool:
    if not isinstance(token, str):
        return False
    if token in {"SJ", "BJ"}:
        return True
    return len(token) >= 2 and token[-1] in _SUITS and token[:-1] in _NORMAL_RANKS


def summarize_free_lead_residual_structures(
    observation: object,
    legal_actions: object,
) -> tuple[FreeLeadResidualStructure, ...] | None:
    """Return residual rank-group facts, or ``None`` when evidence is incomplete.

    The rank-group count is deliberately an estimate: it counts non-empty
    rank groups after removing the carrier and does not predict future control
    or trick ownership.  This function never selects or ranks an action.
    """

    if not isinstance(observation, Mapping):
        return None
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping):
        return None
    hand_cards = my_info.get("hand_cards")
    hand_count = my_info.get("hand_count")
    player_id = my_info.get("player_id")
    level_rank = current_round.get("current_level_rank")
    hand = Counter(hand_cards) if isinstance(hand_cards, list) else Counter()
    if (
        not _is_int(player_id)
        or not _is_int(hand_count)
        or hand_count <= 0
        or not isinstance(hand_cards, list)
        or len(hand_cards) != hand_count
        or any(not _valid_token(card) for card in hand_cards)
        or any(count > 2 for count in hand.values())
        or type(level_rank) is not str
        or level_rank not in _NORMAL_RANKS
        or current_round.get("current_player_id") != player_id
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
        or not isinstance(legal_actions, Sequence)
        or isinstance(legal_actions, (str, bytes))
        or not legal_actions
    ):
        return None

    action_ids: set[int] = set()
    summaries: list[FreeLeadResidualStructure] = []
    for action in legal_actions:
        if not isinstance(action, Mapping):
            return None
        action_id = action.get("action_id")
        pattern = action.get("declared_pattern")
        declared_cards = action.get("declared_cards")
        carrier_cards = action.get("carrier_cards")
        wildcard_count = action.get("wildcard_count")
        wildcard_info = action.get("wildcard_info")
        if (
            not _is_int(action_id)
            or action_id in action_ids
            or not isinstance(pattern, str)
            or pattern not in _PATTERNS
            or not isinstance(declared_cards, list)
            or not declared_cards
            or any(not isinstance(card, str) or not card for card in declared_cards)
            or not isinstance(carrier_cards, list)
            or not carrier_cards
            or len(declared_cards) != len(carrier_cards)
            or any(not _valid_token(card) for card in carrier_cards)
            or not _is_int(wildcard_count)
            or wildcard_count < 0
            or wildcard_count > len(carrier_cards)
            or not isinstance(wildcard_info, list)
            or len(wildcard_info) != wildcard_count
            or any(not isinstance(item, Mapping) for item in wildcard_info)
            or not isinstance(action.get("display_text"), str)
            or not action.get("display_text")
        ):
            return None
        used = Counter(carrier_cards)
        if any(count <= 0 or count > hand.get(card, 0) for card, count in used.items()):
            return None

        remaining = hand.copy()
        remaining.subtract(used)
        remaining = Counter({card: count for card, count in remaining.items() if count > 0})
        remaining_ranks = Counter(_rank_of(card) for card in remaining.elements())
        played_ranks = {_rank_of(card) for card in carrier_cards}
        summaries.append(
            FreeLeadResidualStructure(
                action_id=action_id,
                clears_played_rank_groups=all(remaining_ranks.get(rank, 0) == 0 for rank in played_ranks),
                residual_singleton_rank_count=sum(1 for count in remaining_ranks.values() if count == 1),
                estimated_remaining_rank_groups=len(remaining_ranks),
            )
        )
        action_ids.add(action_id)
    return tuple(summaries)


def summarize_candidate_structures(
    observation: object,
    legal_actions: object,
) -> tuple[CandidateStructure, ...] | None:
    """Return bounded action-comparison facts from canonical public payloads.

    Validation intentionally reuses the conservative free-lead parser when it
    applies.  Follow-play is also useful to the model, so its table constraint
    is not rejected; malformed payloads fail closed as a whole.
    """
    if not isinstance(observation, Mapping) or not isinstance(legal_actions, Sequence) or isinstance(legal_actions, (str, bytes)):
        return None
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    other_players = observation.get("other_players")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping) or not isinstance(other_players, list):
        return None
    hand_cards = my_info.get("hand_cards")
    hand_count = my_info.get("hand_count")
    player_id = my_info.get("player_id")
    level_rank = current_round.get("current_level_rank")
    if (not _is_int(player_id) or not _is_int(hand_count) or hand_count <= 0
            or not isinstance(hand_cards, list) or len(hand_cards) != hand_count
            or any(not _valid_token(card) for card in hand_cards)
            or type(level_rank) is not str or level_rank not in _NORMAL_RANKS
            or current_round.get("current_player_id") != player_id):
        return None
    hand = Counter(hand_cards)
    if any(count > 2 for count in hand.values()):
        return None
    team = my_info.get("team")
    teammate_count: int | None = None
    opponent_counts: list[int] = []
    if isinstance(team, str):
        for other in other_players:
            if not isinstance(other, Mapping) or not _is_int(other.get("hand_count")) or other.get("hand_count") < 0:
                return None
            if other.get("team") == team and other.get("player_id") != player_id:
                teammate_count = int(other["hand_count"])
            elif other.get("team") != team and not bool(other.get("finished", False)):
                opponent_counts.append(int(other["hand_count"]))
    else:
        return None
    seen: set[int] = set()
    results: list[CandidateStructure] = []
    for action in legal_actions:
        if not isinstance(action, Mapping):
            return None
        action_id, pattern = action.get("action_id"), action.get("declared_pattern")
        carrier = action.get("carrier_cards")
        wildcard_count = action.get("wildcard_count")
        if (not _is_int(action_id) or action_id in seen or not isinstance(pattern, str)
                or pattern not in (_PATTERNS | {"pass"}) or not isinstance(carrier, list)
                or (pattern != "pass" and (not carrier or any(not _valid_token(card) for card in carrier)))
                or not _is_int(wildcard_count) or wildcard_count < 0):
            return None
        if pattern == "pass":
            results.append(CandidateStructure(
                action_id, pattern, 0, False, False, False, 0, len({_rank_of(card) for card in hand}),
                False, None, False, None, None, teammate_count,
                min(opponent_counts) if opponent_counts else None,
                current_round.get("constraint") == "free",
            ))
            seen.add(action_id)
            continue
        used = Counter(carrier)
        if any(count > hand.get(card, 0) for card, count in used.items()):
            return None
        remaining = hand.copy(); remaining.subtract(used)
        remaining = Counter({card: count for card, count in remaining.items() if count > 0})
        remaining_ranks = Counter(_rank_of(card) for card in remaining.elements())
        played_ranks = {_rank_of(card) for card in carrier}
        fragments = any(remaining_ranks.get(rank, 0) > 0 for rank in played_ranks)
        natural_single_value = None
        if pattern == "single" and wildcard_count == 0 and len(carrier) == 1:
            natural_single_value = _RANK_VALUES.get(_rank_of(carrier[0]))
        control = any(_rank_of(card) in {"SJ", "BJ", "A", level_rank} for card in carrier)
        bomb_length = len(carrier) if pattern == "bomb" else None
        leaves_bomb_singleton = bool(pattern == "bomb" and any(remaining_ranks.get(rank) == 1 for rank in played_ranks)) if pattern == "bomb" else None
        results.append(CandidateStructure(
            int(action_id), pattern, len(carrier), wildcard_count > 0, len(carrier) == hand_count,
            not fragments, sum(1 for count in remaining_ranks.values() if count == 1), len(remaining_ranks),
            fragments, natural_single_value, control, bomb_length, leaves_bomb_singleton,
            teammate_count, min(opponent_counts) if opponent_counts else None,
            current_round.get("constraint") == "free",
        ))
        seen.add(action_id)
    return tuple(results)
