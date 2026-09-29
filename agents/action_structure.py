"""Fail-closed residual structure facts derived from public action payloads."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agents.game_phase import OPENING, classify_game_phase


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
class ResidualRankUse:
    """Conservative natural-structure cues for one played rank after an action."""

    rank: str
    # Counts exclude the red-heart level wildcard; it is reported separately.
    remaining_count: int
    natural_pattern_kinds: tuple[str, ...]
    wildcard_count: int = 0


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
    teammate_active: bool
    minimum_opponent_hand_count: int | None
    is_free_lead: bool
    residual_rank_uses: tuple[ResidualRankUse, ...] | None = None
    residual_hand_natural_pattern_kinds: tuple[str, ...] | None = None
    residual_natural_control_resource_count: int | None = None
    residual_card_count: int | None = None


@dataclass(frozen=True, slots=True)
class CandidateContrast:
    """One strictly established, public comparison between canonical actions.

    The contrast names no preferred action.  It only records the exact
    original IDs which must be present together before the prompt may state
    the corresponding trade-off.
    """

    kind: str
    action_ids: tuple[int, int]
    teammate_hand_count: int | None
    # Optional, strictly public details used to explain a relation without
    # reparsing actions in the prompt layer.  Rank labels are ordered by the
    # relation's documented endpoint order.
    rank_labels: tuple[str, ...] = ()
    table_leader_relation: str | None = None
    table_leader_hand_count: int | None = None
    next_active_player_id: int | None = None
    next_active_player_relation: str | None = None
    next_active_player_hand_count: int | None = None


@dataclass(frozen=True, slots=True)
class CandidateNetEffect:
    """Public facts changed by one canonical response versus passing.

    This is a compact description of observable gains and costs, not a score
    for choosing the response.  The same fields may prioritize which real
    response/pass comparison is shown and render that comparison.
    """

    cards_played: int
    finishes_hand: bool
    uses_wildcard: bool
    spends_control_resource: bool
    fragments_rank_group: bool
    singleton_rank_delta: int
    rank_group_delta: int
    control_resource_delta: int | None
    lost_natural_uses: tuple[str, ...]

    @property
    def comparison_information(self) -> int:
        """Stable display priority for contrasts with distinct public costs."""
        return (
            int(self.finishes_hand) * 20
            + self.cards_played
            + int(self.uses_wildcard) * 8
            + int(self.spends_control_resource) * 6
            + int(self.fragments_rank_group) * 5
            + abs(self.singleton_rank_delta) * 2
            + abs(self.rank_group_delta)
            + max(0, self.control_resource_delta or 0) * 2
            + len(self.lost_natural_uses) * 2
        )


_RANK_VALUES = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15,
    "SJ": 16, "BJ": 17,
}
# These rank windows describe possible natural structures in the visible
# residual hand. They neither construct nor validate actions; overlapping
# windows are not counted as guaranteed future plays.
_RESIDUAL_STRAIGHT_WINDOWS = (
    ("A", "2", "3", "4", "5"), ("2", "3", "4", "5", "6"),
    ("3", "4", "5", "6", "7"), ("4", "5", "6", "7", "8"),
    ("5", "6", "7", "8", "9"), ("6", "7", "8", "9", "10"),
    ("7", "8", "9", "10", "J"), ("8", "9", "10", "J", "Q"),
    ("9", "10", "J", "Q", "K"), ("10", "J", "Q", "K", "A"),
)
_RESIDUAL_PAIR_STRAIGHT_WINDOWS = (
    ("3", "4", "5"), ("4", "5", "6"), ("5", "6", "7"),
    ("6", "7", "8"), ("7", "8", "9"), ("8", "9", "10"),
    ("9", "10", "J"), ("10", "J", "Q"), ("J", "Q", "K"),
    ("Q", "K", "A"),
)
_RESIDUAL_STEEL_PLATE_WINDOWS = (
    ("3", "4"), ("4", "5"), ("5", "6"), ("6", "7"), ("7", "8"),
    ("8", "9"), ("9", "10"), ("10", "J"), ("J", "Q"),
    ("Q", "K"), ("K", "A"),
)
_RESIDUAL_USE_ORDER = (
    "pair", "triple", "bomb", "triple_with_pair", "straight",
    "pair_straight", "steel_plate",
)
_TEAM_BY_PLAYER = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}
CANDIDATE_RELATION_KINDS = (
    "natural_single_cost",
    "single_control_resource",
    "natural_pair_single",
    "natural_group_single",
    "natural_sequence_single",
    "bomb_strength_resource",
    "triple_bomb_split",
    "bomb_wildcard_strength",
    "sequence_structure_loss",
    "triple_split_repartition",
    "straight_flush_bomb_fragment",
    "straight_strength",
    "steel_plate_strength",
    "triple_pair_kicker_gradient",
    "bomb_residual",
    "wildcard_resource",
    "teammate_control_resource",
    "teammate_table_choice",
    "danger_block_resource",
    "danger_block_choice",
    "opponent_single_control_cost",
    "follow_response_net_tradeoff",
)


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


def _valid_declared(token: object) -> bool:
    return isinstance(token, str) and (token in _NORMAL_RANKS | {"SJ", "BJ"} or _valid_token(token))


def _declared_multiset_key(token: str, pattern: str) -> str:
    """Return the public declaration identity relevant to one pattern.

    Most public declarations are rank-only even when their carrier has a
    suit.  Straight flushes are the exception: their public declaration is
    deliberately suit-specific.
    """
    if pattern == "straight_flush" or token in _NORMAL_RANKS | {"SJ", "BJ"}:
        return token
    return _rank_of(token)


def _validate_public_action_schema(
    action: object,
    *,
    level_rank: str,
    allow_missing_action_id: bool,
    allow_pass: bool,
) -> tuple[int | None, str, list[str], list[str], int] | None:
    """Validate public action shape and declared/carrier multiset conservation.

    This intentionally stops before pattern legality or trick comparison.  It
    is shared by table and candidate actions so the two public projections
    cannot drift; ownership of carriers remains a candidate-only check.
    """
    if not isinstance(action, Mapping):
        return None
    action_id = action.get("action_id")
    pattern = action.get("declared_pattern")
    declared = action.get("declared_cards")
    carrier = action.get("carrier_cards")
    wildcard_count = action.get("wildcard_count")
    wildcard_info = action.get("wildcard_info")
    display = action.get("display_text")
    if (
        (not allow_missing_action_id and not _is_int(action_id))
        or (allow_missing_action_id and action_id is not None and not _is_int(action_id))
        or not isinstance(pattern, str)
        or not isinstance(declared, list)
        or not isinstance(carrier, list)
        or not _is_int(wildcard_count)
        or wildcard_count < 0
        or not isinstance(wildcard_info, list)
        or not isinstance(display, str)
        or not display
    ):
        return None
    if pattern == "pass":
        if not allow_pass or declared or carrier or wildcard_count != 0 or wildcard_info:
            return None
        return action_id, pattern, declared, carrier, wildcard_count
    if (
        pattern not in _PATTERNS
        or not declared
        or not carrier
        or len(declared) != len(carrier)
        or any(not _valid_declared(card) for card in declared)
        or any(not _valid_token(card) for card in carrier)
        or wildcard_count > len(carrier)
        or len(wildcard_info) != wildcard_count
    ):
        return None
    if pattern == "straight_flush" and any(not _valid_token(card) or card in {"SJ", "BJ"} for card in declared):
        return None

    declared_counts = Counter(_declared_multiset_key(card, pattern) for card in declared)
    wildcard_token = f"{level_rank}H"
    wildcard_carriers = Counter(carrier).get(wildcard_token, 0)
    if wildcard_carriers < wildcard_count:
        return None
    for item in wildcard_info:
        if not isinstance(item, Mapping):
            return None
        carrier_card = item.get("carrier_card")
        declared_as = item.get("declared_as")
        if carrier_card != wildcard_token or not _valid_declared(declared_as):
            return None
        if pattern == "straight_flush" and (not _valid_token(declared_as) or declared_as in {"SJ", "BJ"}):
            return None
        key = _declared_multiset_key(declared_as, pattern)
        if declared_counts.get(key, 0) <= 0:
            return None
        declared_counts[key] -= 1

    natural_wildcard_carriers = wildcard_carriers - wildcard_count
    for card in carrier:
        if card == wildcard_token and natural_wildcard_carriers > 0:
            natural_wildcard_carriers -= 1
            key = _declared_multiset_key(card, pattern)
            if declared_counts.get(key, 0) <= 0:
                return None
            declared_counts[key] -= 1
        elif card != wildcard_token:
            key = _declared_multiset_key(card, pattern)
            if declared_counts.get(key, 0) <= 0:
                return None
            declared_counts[key] -= 1
        else:
            # This instance is represented by one wildcard_info entry above.
            continue
    return (action_id, pattern, declared, carrier, wildcard_count) if not any(declared_counts.values()) else None


def _residual_natural_pattern_kinds(
    residual_hand: Counter[str],
    *,
    wildcard_token: str,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    """Describe possible natural rank structures without asserting action legality.

    The wildcard carrier is excluded rather than treated as a natural card.
    Returned structures may overlap and are only cues about the current public
    residual multiset; they say nothing about future control or completion.
    """
    counts = Counter(
        _rank_of(card)
        for card in residual_hand.elements()
        if card != wildcard_token
    )
    patterns_by_rank: dict[str, set[str]] = {rank: set() for rank in counts}
    for rank, count in counts.items():
        if count >= 2:
            patterns_by_rank[rank].add("pair")
        if rank in _NORMAL_RANKS and count >= 3:
            patterns_by_rank[rank].add("triple")
        if rank in _NORMAL_RANKS and count >= 4:
            patterns_by_rank[rank].add("bomb")

    triples = {rank for rank, count in counts.items() if rank in _NORMAL_RANKS and count >= 3}
    pairs = {rank for rank, count in counts.items() if count >= 2}
    for triple_rank in triples:
        for pair_rank in pairs - {triple_rank}:
            patterns_by_rank[triple_rank].add("triple_with_pair")
            patterns_by_rank[pair_rank].add("triple_with_pair")

    for window in _RESIDUAL_STRAIGHT_WINDOWS:
        if all(counts.get(rank, 0) >= 1 for rank in window):
            for rank in window:
                patterns_by_rank[rank].add("straight")
    for window in _RESIDUAL_PAIR_STRAIGHT_WINDOWS:
        if all(counts.get(rank, 0) >= 2 for rank in window):
            for rank in window:
                patterns_by_rank[rank].add("pair_straight")
    for window in _RESIDUAL_STEEL_PLATE_WINDOWS:
        if all(counts.get(rank, 0) >= 3 for rank in window):
            for rank in window:
                patterns_by_rank[rank].add("steel_plate")

    ordered_by_rank = {
        rank: tuple(kind for kind in _RESIDUAL_USE_ORDER if kind in kinds)
        for rank, kinds in patterns_by_rank.items()
    }
    all_kinds = tuple(
        kind for kind in _RESIDUAL_USE_ORDER
        if any(kind in kinds for kinds in ordered_by_rank.values())
    )
    return ordered_by_rank, all_kinds


def _residual_use_facts(
    *,
    action: Mapping[str, object],
    residual_hand: Counter[str],
    level_rank: str,
    played_ranks: set[str],
) -> tuple[tuple[ResidualRankUse, ...], tuple[str, ...], int] | None:
    """Return public natural-use cues, omitting wildcard/declaration ambiguity."""
    if action.get("declared_pattern") != "pass":
        carrier = action.get("carrier_cards")
        declared = action.get("declared_cards")
        pattern = action.get("declared_pattern")
        if (
            action.get("wildcard_count") != 0
            or not isinstance(carrier, list)
            or not isinstance(declared, list)
            or not isinstance(pattern, str)
            or f"{level_rank}H" in carrier
            or Counter(_declared_multiset_key(card, pattern) for card in declared)
            != Counter(_declared_multiset_key(card, pattern) for card in carrier)
            or (pattern == "straight_flush" and Counter(declared) != Counter(carrier))
        ):
            return None

    patterns_by_rank, all_kinds = _residual_natural_pattern_kinds(
        residual_hand,
        wildcard_token=f"{level_rank}H",
    )
    physical_counts = Counter(_rank_of(card) for card in residual_hand.elements())
    natural_counts = Counter(
        _rank_of(card)
        for card in residual_hand.elements()
        if card != f"{level_rank}H"
    )
    rank_uses = tuple(
        ResidualRankUse(
            rank=rank,
            remaining_count=natural_counts.get(rank, 0),
            natural_pattern_kinds=patterns_by_rank.get(rank, ()),
            wildcard_count=(
                physical_counts.get(rank, 0) - natural_counts.get(rank, 0)
                if rank == level_rank else 0
            ),
        )
        for rank in sorted(played_ranks, key=lambda item: _RANK_VALUES.get(item, 99))
    )
    control_ranks = {"SJ", "BJ", "A", level_rank}
    natural_control_count = sum(
        count
        for token, count in residual_hand.items()
        if token != f"{level_rank}H" and _rank_of(token) in control_ranks
    )
    return rank_uses, all_kinds, natural_control_count


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
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping) or not isinstance(other_players, list) or len(other_players) != 3:
        return None
    hand_cards = my_info.get("hand_cards")
    hand_count = my_info.get("hand_count")
    player_id = my_info.get("player_id")
    level_rank = current_round.get("current_level_rank")
    if (not _is_int(player_id) or not _is_int(hand_count) or hand_count <= 0
            or not isinstance(hand_cards, list) or len(hand_cards) != hand_count
            or any(not _valid_token(card) for card in hand_cards)
            or type(level_rank) is not str or level_rank not in _NORMAL_RANKS
            or player_id not in _TEAM_BY_PLAYER
            or my_info.get("team") != _TEAM_BY_PLAYER.get(player_id)
            or current_round.get("current_player_id") != player_id
            or not isinstance(current_round.get("constraint"), str)):
        return None
    constraint = current_round["constraint"]
    table_action = current_round.get("table_action")
    if (constraint == "free" and table_action is not None) or (constraint != "free" and not isinstance(table_action, Mapping)):
        return None
    if isinstance(table_action, Mapping):
        if (
            _validate_public_action_schema(
                table_action,
                level_rank=level_rank,
                allow_missing_action_id=True,
                allow_pass=False,
            ) is None
            or constraint != table_action.get("display_text")
        ):
            return None
    hand = Counter(hand_cards)
    if any(count > 2 for count in hand.values()):
        return None
    team = my_info.get("team")
    teammate_count: int | None = None
    teammate_active = False
    opponent_counts: list[int] = []
    if isinstance(team, str) and team == _TEAM_BY_PLAYER[player_id]:
        other_ids: set[int] = set()
        for other in other_players:
            other_id = other.get("player_id") if isinstance(other, Mapping) else None
            other_team = other.get("team") if isinstance(other, Mapping) else None
            if (not isinstance(other, Mapping) or not _is_int(other_id) or other_id == player_id or other_id in other_ids
                    or other_id not in _TEAM_BY_PLAYER or other_team != _TEAM_BY_PLAYER[other_id]
                    or not _is_int(other.get("hand_count")) or other.get("hand_count") < 0
                    or type(other.get("finished")) is not bool):
                return None
            other_ids.add(other_id)
            if other_team == team:
                if teammate_count is not None:
                    return None
                teammate_count = int(other["hand_count"])
                teammate_active = not other["finished"]
            elif not other["finished"]:
                opponent_counts.append(int(other["hand_count"]))
            if other["finished"] and other["hand_count"] != 0:
                return None
            if not other["finished"] and other["hand_count"] <= 0:
                return None
    else:
        return None
    if teammate_count is None or other_ids != (set(_TEAM_BY_PLAYER) - {player_id}) or len(opponent_counts) > 2:
        return None
    seen: set[int] = set()
    results: list[CandidateStructure] = []
    for action in legal_actions:
        validated = _validate_public_action_schema(
            action,
            level_rank=level_rank,
            allow_missing_action_id=False,
            allow_pass=True,
        )
        if validated is None:
            return None
        action_id, pattern, declared, carrier, wildcard_count = validated
        if action_id is None or action_id in seen:
            return None
        if pattern == "pass":
            if constraint == "free":
                return None
            residual_uses = _residual_use_facts(
                action=action,
                residual_hand=hand,
                level_rank=level_rank,
                played_ranks=set(),
            )
            results.append(CandidateStructure(
                action_id, pattern, 0, False, False, False,
                sum(1 for count in Counter(_rank_of(card) for card in hand).values() if count == 1),
                len({_rank_of(card) for card in hand}),
                False, None, False, None, None, teammate_count, teammate_active,
                min(opponent_counts) if opponent_counts else None,
                current_round.get("constraint") == "free",
                residual_uses[0] if residual_uses is not None else None,
                residual_uses[1] if residual_uses is not None else None,
                residual_uses[2] if residual_uses is not None else None,
                sum(hand.values()),
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
        residual_uses = _residual_use_facts(
            action=action,
            residual_hand=remaining,
            level_rank=level_rank,
            played_ranks=played_ranks,
        )
        results.append(CandidateStructure(
            int(action_id), pattern, len(carrier), wildcard_count > 0, len(carrier) == hand_count,
            not fragments, sum(1 for count in remaining_ranks.values() if count == 1), len(remaining_ranks),
            fragments, natural_single_value, control, bomb_length, leaves_bomb_singleton,
            teammate_count, teammate_active, min(opponent_counts) if opponent_counts else None,
            current_round.get("constraint") == "free",
            residual_uses[0] if residual_uses is not None else None,
            residual_uses[1] if residual_uses is not None else None,
            residual_uses[2] if residual_uses is not None else None,
            sum(remaining.values()),
        ))
        seen.add(action_id)
    return tuple(results)


def candidate_response_net_effect(
    passing: CandidateStructure,
    response: CandidateStructure,
) -> CandidateNetEffect | None:
    """Compare a canonical non-pass response's public effects with pass.

    ``summarize_candidate_structures`` has already validated carrier ownership
    and canonical action shape.  No action is created or re-evaluated here.
    """
    if passing.pattern != "pass" or response.pattern == "pass":
        return None
    pass_uses = set(passing.residual_hand_natural_pattern_kinds or ())
    response_uses = set(response.residual_hand_natural_pattern_kinds or ())
    control_delta = None
    if (
        passing.residual_natural_control_resource_count is not None
        and response.residual_natural_control_resource_count is not None
    ):
        control_delta = (
            passing.residual_natural_control_resource_count
            - response.residual_natural_control_resource_count
        )
    return CandidateNetEffect(
        cards_played=response.carrier_count,
        finishes_hand=response.finishes_hand,
        uses_wildcard=response.uses_wildcard,
        spends_control_resource=response.consumes_control_resource,
        fragments_rank_group=response.fragments_played_rank_group,
        singleton_rank_delta=(
            response.residual_singleton_rank_count
            - passing.residual_singleton_rank_count
        ),
        rank_group_delta=(
            response.estimated_remaining_rank_groups
            - passing.estimated_remaining_rank_groups
        ),
        control_resource_delta=control_delta,
        lost_natural_uses=tuple(sorted(pass_uses - response_uses)),
    )


def _natural_same_rank(action: Mapping[str, object], *, count: int) -> str | None:
    """Return the one natural normal rank used by a strict comparison action."""

    carrier = action.get("carrier_cards")
    declared = action.get("declared_cards")
    if (
        action.get("wildcard_count") != 0
        or not isinstance(carrier, list)
        or not isinstance(declared, list)
        or len(carrier) != count
        or len(declared) != count
        or any(not isinstance(card, str) for card in carrier + declared)
    ):
        return None
    carrier_ranks = {_rank_of(card) for card in carrier}
    declared_ranks = {
        card if card in _NORMAL_RANKS | {"SJ", "BJ"} else _rank_of(card)
        for card in declared
    }
    if len(carrier_ranks) != 1 or carrier_ranks != declared_ranks:
        return None
    rank = next(iter(carrier_ranks))
    return rank if rank in _NORMAL_RANKS else None


def _natural_sequence_high_rank(action: Mapping[str, object], *, pattern: str) -> str | None:
    """Return a public high rank for one unmodified natural sequence action."""

    carrier = action.get("carrier_cards")
    declared = action.get("declared_cards")
    expected_count = 5 if pattern == "straight" else 6 if pattern == "steel_plate" else 0
    if (
        action.get("declared_pattern") != pattern
        or action.get("wildcard_count") != 0
        or not isinstance(carrier, list)
        or not isinstance(declared, list)
        or len(carrier) != expected_count
        or len(declared) != expected_count
        or any(not isinstance(card, str) for card in carrier + declared)
    ):
        return None
    carrier_ranks = Counter(_rank_of(card) for card in carrier)
    declared_ranks = Counter(
        card if card in _NORMAL_RANKS | {"SJ", "BJ"} else _rank_of(card)
        for card in declared
    )
    if carrier_ranks != declared_ranks:
        return None
    expected_multiplicity = 1 if pattern == "straight" else 3
    if len(carrier_ranks) != (5 if pattern == "straight" else 2):
        return None
    if any(
        rank not in _RANK_VALUES or count != expected_multiplicity
        for rank, count in carrier_ranks.items()
    ):
        return None
    if pattern == "steel_plate":
        ordered_ranks = sorted((_RANK_VALUES[rank] for rank in carrier_ranks))
        if ordered_ranks[-1] > _RANK_VALUES["A"] or ordered_ranks[1] - ordered_ranks[0] != 1:
            return None
    if pattern == "straight" and set(carrier_ranks) == {"A", "2", "3", "4", "5"}:
        # A2345 is the engine's weakest straight window; treating its ace as
        # high would incorrectly rank it above 23456 in a public comparison.
        return "5"
    return max(carrier_ranks, key=lambda rank: _RANK_VALUES[rank])


def _natural_triple_pair_kicker(action: Mapping[str, object]) -> tuple[str, str] | None:
    """Return (triple rank, pair rank) only for a natural canonical 3+2 shape."""

    carrier = action.get("carrier_cards")
    declared = action.get("declared_cards")
    if (
        action.get("declared_pattern") != "triple_with_pair"
        or action.get("wildcard_count") != 0
        or not isinstance(carrier, list)
        or not isinstance(declared, list)
        or len(carrier) != 5
        or len(declared) != 5
        or any(not isinstance(card, str) for card in carrier + declared)
    ):
        return None
    carrier_ranks = Counter(_rank_of(card) for card in carrier)
    declared_ranks = Counter(
        card if card in _NORMAL_RANKS | {"SJ", "BJ"} else _rank_of(card)
        for card in declared
    )
    if carrier_ranks != declared_ranks:
        return None
    triples = [rank for rank, count in carrier_ranks.items() if count == 3]
    pairs = [rank for rank, count in carrier_ranks.items() if count == 2]
    if len(triples) != 1 or len(pairs) != 1 or triples[0] in {"SJ", "BJ"} or pairs[0] in {"SJ", "BJ"}:
        return None
    return triples[0], pairs[0]


def _wildcard_bomb_rank(action: Mapping[str, object], *, level_rank: str) -> str | None:
    """Return the declared rank for a canonical bomb using one wildcard.

    The caller has already passed the shared public action schema validator.
    This helper still checks the physical wildcard carrier and the same-rank
    natural carriers so a malformed or otherwise ambiguous declaration fails
    closed.
    """
    carrier = action.get("carrier_cards")
    declared = action.get("declared_cards")
    if (
        action.get("declared_pattern") != "bomb"
        or action.get("wildcard_count") != 1
        or not isinstance(carrier, list)
        or not isinstance(declared, list)
        or len(carrier) < 5
        or len(declared) != len(carrier)
        or any(not isinstance(card, str) for card in carrier + declared)
    ):
        return None
    wildcard_token = f"{level_rank}H"
    if carrier.count(wildcard_token) != 1:
        return None
    natural_carriers = [card for card in carrier if card != wildcard_token]
    carrier_ranks = {_rank_of(card) for card in natural_carriers}
    declared_ranks = {
        card if card in _NORMAL_RANKS | {"SJ", "BJ"} else _rank_of(card)
        for card in declared
    }
    if (
        len(carrier_ranks) != 1
        or len(declared_ranks) != 1
        or carrier_ranks != declared_ranks
    ):
        return None
    rank = next(iter(carrier_ranks))
    return rank if rank in _NORMAL_RANKS else None


def _rank_residual_use(fact: CandidateStructure, rank: str) -> ResidualRankUse | None:
    if fact.residual_rank_uses is None:
        return None
    return next((item for item in fact.residual_rank_uses if item.rank == rank), None)


def _bomb_residual_contrasts(
    bombs_by_rank: dict[str, dict[int, CandidateStructure]],
) -> tuple[CandidateContrast, ...]:
    """Choose at most two complete, stable natural-bomb residual comparisons.

    Prefer one contrast where the shorter route leaves an identified natural
    use, then one where it leaves an unclassified singleton that the longer
    route clears. These are descriptive representatives, not action rankings.
    """
    options: list[tuple[str, CandidateStructure, CandidateStructure, ResidualRankUse, ResidualRankUse]] = []
    for rank in sorted(bombs_by_rank, key=lambda item: _RANK_VALUES[item]):
        choices = bombs_by_rank[rank]
        lengths = sorted(choices)
        for shorter_length, longer_length in zip(lengths, lengths[1:]):
            if shorter_length == longer_length:
                continue
            shorter = choices[shorter_length]
            longer = choices[longer_length]
            shorter_use = _rank_residual_use(shorter, rank)
            longer_use = _rank_residual_use(longer, rank)
            if shorter_use is None or longer_use is None:
                continue
            if shorter_use.remaining_count <= longer_use.remaining_count:
                continue
            options.append((rank, shorter, longer, shorter_use, longer_use))

    if not options:
        return ()

    retained = [option for option in options if option[3].natural_pattern_kinds]
    retained.sort(
        key=lambda option: (
            -option[3].remaining_count,
            _RANK_VALUES[option[0]],
            option[1].bomb_length or 0,
            option[1].action_id,
            option[2].action_id,
        )
    )
    singleton_clear = [
        option for option in options
        if option[3].remaining_count == 1
        and not option[3].natural_pattern_kinds
        and option[4].remaining_count == 0
    ]
    singleton_clear.sort(
        key=lambda option: (
            _RANK_VALUES[option[0]],
            option[1].bomb_length or 0,
            option[1].action_id,
            option[2].action_id,
        )
    )

    selected: list[tuple[str, CandidateStructure, CandidateStructure, ResidualRankUse, ResidualRankUse]] = []
    for pool in (retained, singleton_clear, options):
        candidate = next(
            (item for item in pool if (item[1].action_id, item[2].action_id) not in {
                (selected_item[1].action_id, selected_item[2].action_id) for selected_item in selected
            }),
            None,
        )
        if candidate is not None and candidate not in selected:
            selected.append(candidate)
        if len(selected) == 2:
            break
    return tuple(
        CandidateContrast("bomb_residual", (shorter.action_id, longer.action_id), shorter.teammate_hand_count)
        for _, shorter, longer, _, _ in selected
    )


def summarize_candidate_contrasts(
    observation: object,
    legal_actions: object,
) -> tuple[CandidateContrast, ...] | None:
    """Return only fully established public action relationships.

    The caller supplies the canonical action set.  A relationship is omitted
    rather than approximated if either side, the shared natural rank, or the
    visible before/after residual structure cannot be proven from that set.
    """

    facts = summarize_candidate_structures(observation, legal_actions)
    if facts is None or not isinstance(legal_actions, Sequence):
        return None
    actions_by_id: dict[int, Mapping[str, object]] = {}
    for action in legal_actions:
        if not isinstance(action, Mapping) or type(action.get("action_id")) is not int:
            return None
        action_id = int(action["action_id"])
        if action_id in actions_by_id:
            return None
        actions_by_id[action_id] = action

    current_round = observation.get("current_round") if isinstance(observation, Mapping) else None
    level_rank = current_round.get("current_level_rank") if isinstance(current_round, Mapping) else None

    bombs_by_rank: dict[str, dict[int, CandidateStructure]] = {}
    natural_bomb_facts_by_rank: dict[str, dict[int, list[CandidateStructure]]] = {}
    pairs_by_rank: dict[str, CandidateStructure] = {}
    singles_by_rank: dict[str, CandidateStructure] = {}
    all_singles: list[CandidateStructure] = []
    for fact in facts:
        action = actions_by_id.get(fact.action_id)
        if action is None:
            continue
        # Natural same-rank bombs of any engine-supported length are
        # comparable on a lead or follow, but only when both are canonical.
        if fact.pattern == "bomb" and fact.bomb_length is not None and 4 <= fact.bomb_length <= 8:
            rank = _natural_same_rank(action, count=fact.bomb_length)
            if rank is not None and not fact.uses_wildcard:
                bombs_by_rank.setdefault(rank, {}).setdefault(fact.bomb_length, fact)
                natural_bomb_facts_by_rank.setdefault(rank, {}).setdefault(
                    fact.bomb_length, []
                ).append(fact)
        elif not fact.is_free_lead:
            continue
        elif fact.pattern == "pair":
            rank = _natural_same_rank(action, count=2)
            if rank is not None:
                pairs_by_rank.setdefault(rank, fact)
        elif fact.pattern == "single":
            rank = _natural_same_rank(action, count=1)
            if rank is not None:
                singles_by_rank.setdefault(rank, fact)
                all_singles.append(fact)

    contrasts: list[CandidateContrast] = []
    contrasts.extend(_bomb_residual_contrasts(bombs_by_rank))

    # A natural 3+2 action can consume a pair while splitting the same-rank
    # natural bomb that is also currently legal.  Keep this relation tied to
    # the two real canonical endpoints; the prompt can then distinguish the
    # structural cost from the bomb's stronger immediate pressure.
    triple_bomb_pairs: list[tuple[int, int, int, str, str, CandidateStructure, CandidateStructure]] = []
    for triple_fact in facts:
        if triple_fact.pattern != "triple_with_pair" or triple_fact.uses_wildcard:
            continue
        triple_action = actions_by_id[triple_fact.action_id]
        shape = _natural_triple_pair_kicker(triple_action)
        if shape is None:
            continue
        triple_rank, kicker_rank = shape
        for bomb_length, bomb_fact in bombs_by_rank.get(triple_rank, {}).items():
            if bomb_length < 5:
                continue
            triple_bomb_pairs.append(
                (
                    -_RANK_VALUES[kicker_rank],
                    -bomb_length,
                    triple_fact.action_id,
                    triple_rank,
                    kicker_rank,
                    triple_fact,
                    bomb_fact,
                )
            )
    if triple_bomb_pairs:
        _kicker_order, _length_order, _triple_id, triple_rank, kicker_rank, triple_fact, bomb_fact = min(
            triple_bomb_pairs,
            key=lambda item: item[:3],
        )
        contrasts.append(
            CandidateContrast(
                "triple_bomb_split",
                (triple_fact.action_id, bomb_fact.action_id),
                triple_fact.teammate_hand_count,
                rank_labels=(triple_rank, kicker_rank),
            )
        )

    # Pair a natural N-card bomb with the canonical (N+1)-card realization
    # only when that route carries the same natural N cards plus the public
    # level-heart wildcard.  This is a concrete strength/resource comparison,
    # not a general claim that spending the wildcard is good or bad.
    wildcard_bomb_pairs: list[tuple[int, int, int, str, CandidateStructure, CandidateStructure]] = []
    wildcard_token = (
        f"{level_rank}H"
        if isinstance(level_rank, str) and level_rank in _NORMAL_RANKS
        else ""
    )
    if wildcard_token:
        for wildcard_fact in facts:
            if wildcard_fact.pattern != "bomb" or not wildcard_fact.uses_wildcard:
                continue
            wildcard_action = actions_by_id[wildcard_fact.action_id]
            rank = _wildcard_bomb_rank(wildcard_action, level_rank=level_rank)
            if rank is None:
                continue
            natural_length = wildcard_fact.carrier_count - 1
            wildcard_carrier = wildcard_action.get("carrier_cards")
            if not isinstance(wildcard_carrier, list):
                continue
            wildcard_natural_carrier = [card for card in wildcard_carrier if card != wildcard_token]
            natural_matches = [
                fact for fact in natural_bomb_facts_by_rank.get(rank, {}).get(natural_length, ())
                if Counter(actions_by_id[fact.action_id].get("carrier_cards", ()))
                == Counter(wildcard_natural_carrier)
            ]
            if not natural_matches:
                continue
            natural_fact = min(natural_matches, key=lambda fact: fact.action_id)
            wildcard_bomb_pairs.append(
                (
                    -wildcard_fact.carrier_count,
                    _RANK_VALUES[rank],
                    natural_fact.action_id,
                    rank,
                    natural_fact,
                    wildcard_fact,
                )
            )
    if wildcard_bomb_pairs:
        _length_order, _rank_order, _natural_id, rank, natural_fact, wildcard_fact = min(
            wildcard_bomb_pairs,
            key=lambda item: item[:3],
        )
        contrasts.append(
            CandidateContrast(
                "bomb_wildcard_strength",
                (natural_fact.action_id, wildcard_fact.action_id),
                natural_fact.teammate_hand_count,
                rank_labels=(rank,),
            )
        )

    # Compare the weakest and strongest natural bomb routes when both are
    # present. GuanDan bomb strength is public: length first, then rank with
    # the current level rank elevated. This exposes the resource/control
    # tradeoff without imposing a small-first or large-first action rule.
    natural_bomb_options: dict[tuple[int, int], CandidateStructure] = {}
    if isinstance(level_rank, str) and level_rank in _NORMAL_RANKS:
        for fact in facts:
            if (
                not fact.is_free_lead
                or fact.pattern != "bomb"
                or fact.uses_wildcard
                or fact.bomb_length is None
            ):
                continue
            rank = _natural_same_rank(actions_by_id[fact.action_id], count=fact.bomb_length)
            if rank is None:
                continue
            rank_strength = 16 if rank == level_rank else _RANK_VALUES[rank]
            strength = (fact.bomb_length, rank_strength)
            previous = natural_bomb_options.get(strength)
            if previous is None or fact.action_id < previous.action_id:
                natural_bomb_options[strength] = fact
    if len(natural_bomb_options) >= 2:
        ordered_bombs = sorted(natural_bomb_options.items())
        lower_bomb = ordered_bombs[0][1]
        higher_bomb = ordered_bombs[-1][1]
        pair = (lower_bomb.action_id, higher_bomb.action_id)
        already_shown = any(
            contrast.kind == "bomb_residual" and set(contrast.action_ids) == set(pair)
            for contrast in contrasts
        )
        if not already_shown:
            contrasts.append(
                CandidateContrast(
                    "bomb_strength_resource",
                    pair,
                    lower_bomb.teammate_hand_count,
                )
            )
    for rank in sorted(set(pairs_by_rank) & set(singles_by_rank), key=lambda item: _RANK_VALUES[item]):
        pair = pairs_by_rank[rank]
        single = singles_by_rank[rank]
        if (
            pair.clears_played_rank_groups
            and single.fragments_played_rank_group
            and not pair.consumes_control_resource
        ):
            contrasts.append(
                CandidateContrast(
                    "natural_pair_single",
                    (pair.action_id, single.action_id),
                    pair.teammate_hand_count,
                )
            )

    # A broader group-vs-single route covers natural pairs/triples even when
    # the ordinary singleton is a different rank.  Prefer the exact same-rank
    # pair/single contrast above when no other rank provides a distinct route.
    natural_groups = sorted(
        (
            fact for fact in facts
            if fact.is_free_lead
            and fact.pattern in {"pair", "triple"}
            and not fact.uses_wildcard
            and not fact.finishes_hand
            and fact.clears_played_rank_groups
        ),
        key=lambda fact: ({"pair": 0, "triple": 1}[fact.pattern], fact.residual_singleton_rank_count, fact.action_id),
    )
    group_singles = sorted(
        (
            fact for fact in all_singles
            if not fact.finishes_hand and not fact.fragments_played_rank_group
        ),
        key=lambda fact: (fact.natural_single_rank_value or 99, fact.action_id),
    )
    for group in natural_groups:
        group_rank = _natural_same_rank(actions_by_id[group.action_id], count=group.carrier_count)
        if group_rank is None:
            continue
        separate_single = next(
            (
                fact for fact in group_singles
                if _natural_same_rank(actions_by_id[fact.action_id], count=1) != group_rank
            ),
            None,
        )
        if separate_single is not None:
            contrasts.append(
                CandidateContrast(
                    "natural_group_single",
                    (group.action_id, separate_single.action_id),
                    group.teammate_hand_count,
                )
            )
            break

    # A natural singleton can also be one card of an available natural
    # straight.  Do not blanket-protect that card as an untouchable sequence
    # member: expose one bounded, complete comparison between the canonical
    # straight and its canonical single so the model can weigh clearing the
    # run against a low-cost probe and the residual hand.
    sequence_single_pairs: list[tuple[CandidateStructure, CandidateStructure]] = []
    try:
        opening_lead = (
            isinstance(observation, Mapping)
            and classify_game_phase(observation).phase == OPENING
            and isinstance(current_round, Mapping)
            and current_round.get("constraint") == "free"
            and current_round.get("table_action") is None
        )
    except Exception:
        opening_lead = False
    for sequence_fact in facts:
        if (
            not opening_lead
            or not sequence_fact.is_free_lead
            or sequence_fact.pattern != "straight"
            or sequence_fact.uses_wildcard
            or sequence_fact.finishes_hand
        ):
            continue
        sequence_action = actions_by_id.get(sequence_fact.action_id)
        sequence_carrier = sequence_action.get("carrier_cards") if sequence_action is not None else None
        if not isinstance(sequence_carrier, list):
            continue
        sequence_ranks = {_rank_of(card) for card in sequence_carrier}
        for single_fact in all_singles:
            if (
                single_fact.finishes_hand
                or single_fact.uses_wildcard
                or single_fact.fragments_played_rank_group
                or single_fact.consumes_control_resource
            ):
                continue
            single_action = actions_by_id.get(single_fact.action_id)
            single_rank = _natural_same_rank(single_action or {}, count=1)
            if single_rank is not None and single_rank in sequence_ranks:
                sequence_single_pairs.append((sequence_fact, single_fact))
    if sequence_single_pairs:
        sequence_fact, single_fact = min(
            sequence_single_pairs,
            key=lambda pair: (
                pair[1].natural_single_rank_value or 99,
                pair[0].estimated_remaining_rank_groups,
                pair[0].action_id,
                pair[1].action_id,
            ),
        )
        contrasts.append(
            CandidateContrast(
                "natural_sequence_single",
                (sequence_fact.action_id, single_fact.action_id),
                sequence_fact.teammate_hand_count,
            )
        )

    # Compare a natural sequence that breaks a complete same-rank group with
    # the canonical pair/triple action that clears that exact group.  The
    # relation reports a local structural choice, not which route is better.
    my_info = observation.get("my_info") if isinstance(observation, Mapping) else None
    hand_cards = my_info.get("hand_cards") if isinstance(my_info, Mapping) else None
    hand_rank_counts = Counter(_rank_of(card) for card in hand_cards) if isinstance(hand_cards, list) else Counter()
    sequence_group_pair: tuple[CandidateStructure, CandidateStructure] | None = None
    for sequence_fact in sorted(facts, key=lambda fact: fact.action_id):
        if (
            not sequence_fact.is_free_lead
            or sequence_fact.pattern not in {"straight", "pair_straight", "steel_plate"}
            or sequence_fact.uses_wildcard
            or sequence_fact.finishes_hand
            or not sequence_fact.fragments_played_rank_group
        ):
            continue
        sequence_action = actions_by_id[sequence_fact.action_id]
        sequence_carrier = sequence_action.get("carrier_cards")
        if not isinstance(sequence_carrier, list):
            continue
        used_ranks = Counter(_rank_of(card) for card in sequence_carrier)
        for rank in sorted(used_ranks, key=lambda item: _RANK_VALUES.get(item, 99)):
            group_size = hand_rank_counts.get(rank, 0)
            if group_size not in {2, 3} or used_ranks[rank] >= group_size:
                continue
            group_fact = next(
                (
                    fact for fact in facts
                    if fact.is_free_lead
                    and fact.pattern == ("pair" if group_size == 2 else "triple")
                    and not fact.uses_wildcard
                    and not fact.finishes_hand
                    and _natural_same_rank(actions_by_id[fact.action_id], count=group_size) == rank
                ),
                None,
            )
            if group_fact is not None:
                sequence_group_pair = (sequence_fact, group_fact)
                break
        if sequence_group_pair is not None:
            break
    if sequence_group_pair is not None:
        sequence_fact, group_fact = sequence_group_pair
        contrasts.append(
            CandidateContrast(
                "sequence_structure_loss",
                (sequence_fact.action_id, group_fact.action_id),
                sequence_fact.teammate_hand_count,
            )
        )

    # A public three-triple/one-pair hand can expose a useful alternative to
    # splitting a triple for a singleton: after that legal single, the visible
    # remainder contains two intact triples and two natural pairs.  Pair it
    # only with a currently canonical 3+2 action using another triple rank;
    # no future action ID is synthesized.
    triple_repartition_pair: tuple[CandidateStructure, CandidateStructure] | None = None
    triples_in_hand = sorted(
        (rank for rank, count in hand_rank_counts.items() if count == 3),
        key=lambda rank: _RANK_VALUES.get(rank, 99),
    )
    pair_ranks_in_hand = {
        rank for rank, count in hand_rank_counts.items()
        if count >= 2 and rank not in triples_in_hand and rank not in {"SJ", "BJ"}
    }
    if len(triples_in_hand) >= 3 and pair_ranks_in_hand:
        for single_fact in facts:
            if (
                not single_fact.is_free_lead
                or single_fact.pattern != "single"
                or single_fact.uses_wildcard
                or single_fact.finishes_hand
            ):
                continue
            single_action = actions_by_id[single_fact.action_id]
            split_rank = _natural_same_rank(single_action, count=1)
            if split_rank not in triples_in_hand or not single_fact.fragments_played_rank_group:
                continue
            other_triples = set(triples_in_hand) - {split_rank}
            direct_plays: list[CandidateStructure] = []
            for fact in facts:
                if (
                    not fact.is_free_lead
                    or fact.pattern != "triple_with_pair"
                    or fact.uses_wildcard
                    or fact.finishes_hand
                ):
                    continue
                shape = _natural_triple_pair_kicker(actions_by_id[fact.action_id])
                if shape is not None and shape[0] in other_triples and shape[1] in pair_ranks_in_hand:
                    direct_plays.append(fact)
            if direct_plays:
                triple_repartition_pair = (single_fact, min(direct_plays, key=lambda fact: fact.action_id))
                break
    if triple_repartition_pair is not None:
        single_fact, triple_pair_fact = triple_repartition_pair
        contrasts.append(
            CandidateContrast(
                "triple_split_repartition",
                (single_fact.action_id, triple_pair_fact.action_id),
                single_fact.teammate_hand_count,
            )
        )

    # Only surface the straight-flush/bomb split relation when the current
    # natural straight flush visibly takes cards from two exact four-card rank
    # groups and a corresponding canonical natural four-bomb is also present.
    flush_bomb_pair: tuple[CandidateStructure, CandidateStructure] | None = None
    four_bomb_ranks = {
        _natural_same_rank(actions_by_id[fact.action_id], count=4)
        for fact in facts
        if fact.is_free_lead
        and fact.pattern == "bomb" and fact.bomb_length == 4 and not fact.uses_wildcard
    }
    four_bomb_ranks.discard(None)
    for flush_fact in facts:
        if (
            not flush_fact.is_free_lead
            or flush_fact.pattern != "straight_flush"
            or flush_fact.uses_wildcard
            or flush_fact.finishes_hand
        ):
            continue
        flush_carrier = actions_by_id[flush_fact.action_id].get("carrier_cards")
        if not isinstance(flush_carrier, list):
            continue
        affected = sorted(
            (
                rank for rank in set(_rank_of(card) for card in flush_carrier)
                if hand_rank_counts.get(rank) == 4 and rank in four_bomb_ranks
            ),
            key=lambda rank: _RANK_VALUES[rank],
        )
        if len(affected) < 2:
            continue
        bomb_fact = next(
            (
                fact for fact in facts
                if fact.is_free_lead
                and fact.pattern == "bomb" and fact.bomb_length == 4 and not fact.uses_wildcard
                and _natural_same_rank(actions_by_id[fact.action_id], count=4) == affected[0]
            ),
            None,
        )
        if bomb_fact is not None:
            flush_bomb_pair = (flush_fact, bomb_fact)
            break
    if flush_bomb_pair is not None:
        flush_fact, bomb_fact = flush_bomb_pair
        contrasts.append(
            CandidateContrast(
                "straight_flush_bomb_fragment",
                (flush_fact.action_id, bomb_fact.action_id),
                flush_fact.teammate_hand_count,
            )
        )

    # A same-shape natural sequence can be released at different public
    # strengths.  Show the weakest and strongest available routes together;
    # the model still weighs timing, team urgency, and residual hand structure.
    for pattern, relation_kind in (
        ("straight", "straight_strength"),
        ("steel_plate", "steel_plate_strength"),
    ):
        by_high_rank: dict[str, CandidateStructure] = {}
        for fact in facts:
            if not fact.is_free_lead or fact.pattern != pattern or fact.finishes_hand:
                continue
            action = actions_by_id[fact.action_id]
            high_rank = _natural_sequence_high_rank(action, pattern=pattern)
            if high_rank is not None:
                by_high_rank.setdefault(high_rank, fact)
        if len(by_high_rank) >= 2:
            ordered_ranks = sorted(by_high_rank, key=lambda rank: _RANK_VALUES[rank])
            lower, higher = by_high_rank[ordered_ranks[0]], by_high_rank[ordered_ranks[-1]]
            contrasts.append(
                CandidateContrast(
                    relation_kind,
                    (lower.action_id, higher.action_id),
                    lower.teammate_hand_count,
                )
            )

    # The 3+2 kicker is strategically distinct only when the same natural
    # triple can legally carry at least three different natural pairs.  Use
    # the middle kicker and a deterministic edge as a bounded comparison;
    # no fixed rank direction is prescribed.
    kicker_options: dict[str, dict[str, CandidateStructure]] = {}
    for fact in facts:
        if not fact.is_free_lead or fact.finishes_hand:
            continue
        action = actions_by_id[fact.action_id]
        shape = _natural_triple_pair_kicker(action)
        if shape is None:
            continue
        triple_rank, pair_rank = shape
        kicker_options.setdefault(triple_rank, {}).setdefault(pair_rank, fact)
    for triple_rank in sorted(kicker_options, key=lambda rank: _RANK_VALUES.get(rank, 99)):
        choices = kicker_options[triple_rank]
        if len(choices) < 3:
            continue
        ordered_kickers = sorted(choices, key=lambda rank: _RANK_VALUES[rank])
        middle_rank = ordered_kickers[len(ordered_kickers) // 2]
        edge_ranks = (ordered_kickers[0], ordered_kickers[-1])
        edge_rank = max(
            edge_ranks,
            key=lambda rank: (
                abs(_RANK_VALUES[rank] - _RANK_VALUES[middle_rank]),
                -_RANK_VALUES[rank],
            ),
        )
        first_rank, second_rank = sorted(
            (middle_rank, edge_rank),
            key=lambda rank: _RANK_VALUES[rank],
        )
        contrasts.append(
            CandidateContrast(
                "triple_pair_kicker_gradient",
                (choices[first_rank].action_id, choices[second_rank].action_id),
                choices[first_rank].teammate_hand_count,
                rank_labels=(triple_rank, first_rank, second_rank),
            )
        )
        break

    # This relation only certifies that a single does not fragment an already
    # held same-rank group.  It does not certify that a card has no possible
    # sequence role: sequence alternatives are evaluated from their own
    # canonical actions and remain an explicit counterexample in the prompt.
    safe_singles: list[CandidateStructure] = []
    control_singles: list[CandidateStructure] = []
    for fact in all_singles:
        action = actions_by_id[fact.action_id]
        carrier = action.get("carrier_cards")
        if not isinstance(carrier, list) or len(carrier) != 1:
            continue
        if (
            not fact.uses_wildcard
            and not fact.fragments_played_rank_group
        ):
            if fact.consumes_control_resource:
                control_singles.append(fact)
            else:
                safe_singles.append(fact)
    safe_singles.sort(key=lambda item: (item.natural_single_rank_value or 99, item.action_id))
    if len(safe_singles) >= 2:
        # Pair the cheapest natural singleton with a deterministic middle
        # alternative.  The relation does not encode which should be chosen.
        middle = safe_singles[len(safe_singles) // 2]
        contrasts.append(
            CandidateContrast(
                "natural_single_cost",
                (safe_singles[0].action_id, middle.action_id),
                safe_singles[0].teammate_hand_count,
            )
        )
    if safe_singles and control_singles:
        control_singles.sort(
            key=lambda item: (item.natural_single_rank_value or 99, item.action_id)
        )
        contrasts.append(
            CandidateContrast(
                "single_control_resource",
                (safe_singles[0].action_id, control_singles[0].action_id),
                safe_singles[0].teammate_hand_count,
            )
        )

    # Compare a natural and wildcard realization only when the public
    # declaration, pattern, and carrier length match exactly.
    realizations: dict[tuple[str, tuple[str, ...], int], dict[bool, CandidateStructure]] = {}
    for fact in facts:
        action = actions_by_id[fact.action_id]
        declared = action.get("declared_cards")
        if not isinstance(declared, list) or not declared:
            continue
        declaration = tuple(
            sorted(_declared_multiset_key(str(card), fact.pattern) for card in declared)
        )
        key = (fact.pattern, declaration, fact.carrier_count)
        realizations.setdefault(key, {}).setdefault(fact.uses_wildcard, fact)
    for key in sorted(realizations):
        options = realizations[key]
        natural = options.get(False)
        wildcard = options.get(True)
        if natural is not None and wildcard is not None:
            contrasts.append(
                CandidateContrast(
                    "wildcard_resource",
                    (natural.action_id, wildcard.action_id),
                    natural.teammate_hand_count,
                )
            )

    # On a follow, derive the table leader only from a matching public history
    # action.  Missing or mismatched history omits the relationship entirely.
    observation_map = observation if isinstance(observation, Mapping) else {}
    current_round = observation_map.get("current_round")
    history = observation_map.get("history")
    if isinstance(current_round, Mapping) and isinstance(history, Mapping):
        table_action = current_round.get("table_action")
        history_actions = history.get("actions")
        round_no = current_round.get("round_no")
        player_id = observation_map.get("my_info", {}).get("player_id") if isinstance(observation_map.get("my_info"), Mapping) else None
        if (
            current_round.get("constraint") != "free"
            and isinstance(table_action, Mapping)
            and isinstance(history_actions, list)
            and _is_int(round_no)
            and _is_int(player_id)
        ):
            leaders = [
                item for item in history_actions
                if isinstance(item, Mapping)
                and item.get("round_no") == round_no
                and item.get("declared_pattern") != "pass"
                and all(item.get(key) == table_action.get(key) for key in (
                    "declared_pattern", "declared_cards", "carrier_cards",
                ))
                and all(
                    key not in item or item.get(key) == table_action.get(key)
                    for key in ("wildcard_count", "wildcard_info", "display_text")
                )
            ]
            leader_id = (
                leaders[0].get("player_id")
                if len(leaders) == 1 and _is_int(leaders[0].get("player_id"))
                else None
            )
            my_team = observation_map.get("my_info", {}).get("team") if isinstance(observation_map.get("my_info"), Mapping) else None
            known_teams = {"team_13", "team_24"}
            my_team_is_known = isinstance(my_team, str) and my_team in known_teams
            player_by_id = {
                item.get("player_id"): item
                for item in observation_map.get("other_players", [])
                if isinstance(item, Mapping)
            } if isinstance(observation_map.get("other_players"), list) else {}
            leader = player_by_id.get(leader_id)
            leader_team = leader.get("team") if isinstance(leader, Mapping) else None
            leader_team_is_known = (
                isinstance(leader_team, str) and leader_team in known_teams
            )
            is_teammate_leader = (
                my_team_is_known and leader_team_is_known and leader_team == my_team
            )
            is_urgent_opponent = (
                isinstance(leader, Mapping)
                and my_team_is_known
                and leader_team_is_known
                and leader_team != my_team
                and _is_int(leader.get("hand_count"))
                and 0 < int(leader["hand_count"]) <= 2
            )
            leader_relation = (
                "teammate" if is_teammate_leader
                else "opponent" if isinstance(leader, Mapping)
                and my_team_is_known and leader_team_is_known and leader_team != my_team
                else None
            )
            leader_hand_count = (
                int(leader["hand_count"])
                if isinstance(leader, Mapping) and _is_int(leader.get("hand_count"))
                else None
            )
            next_active: Mapping[str, object] | None = None
            next_active_id: int | None = None
            for offset in range(1, 4):
                candidate_player_id = (int(player_id) - 1 + offset) % 4 + 1
                candidate_player = player_by_id.get(candidate_player_id)
                if isinstance(candidate_player, Mapping) and candidate_player.get("finished") is False:
                    next_active = candidate_player
                    next_active_id = candidate_player_id
                    break
            next_active_team = next_active.get("team") if isinstance(next_active, Mapping) else None
            next_active_team_is_known = (
                isinstance(next_active_team, str) and next_active_team in known_teams
            )
            next_active_relation = (
                "teammate" if isinstance(next_active, Mapping)
                and my_team_is_known and next_active_team_is_known and next_active_team == my_team
                else "opponent" if isinstance(next_active, Mapping)
                and my_team_is_known and next_active_team_is_known and next_active_team != my_team
                else None
            )
            next_active_hand_count = (
                int(next_active["hand_count"])
                if isinstance(next_active, Mapping) and _is_int(next_active.get("hand_count"))
                else None
            )
            pass_fact = next((fact for fact in facts if fact.pattern == "pass"), None)

            def follow_contrast(
                kind: str,
                action_ids: tuple[int, int],
                *,
                rank_labels: tuple[str, ...] = (),
                teammate_hand_count: int | None = None,
            ) -> CandidateContrast:
                return CandidateContrast(
                    kind,
                    action_ids,
                    teammate_hand_count,
                    rank_labels=rank_labels,
                    table_leader_relation=leader_relation,
                    table_leader_hand_count=leader_hand_count,
                    next_active_player_id=next_active_id,
                    next_active_player_relation=next_active_relation,
                    next_active_player_hand_count=next_active_hand_count,
                )

            resource_facts = sorted(
                (
                    fact for fact in facts
                    if fact.pattern != "pass"
                    and (
                        fact.consumes_control_resource
                        or fact.uses_wildcard
                        or fact.pattern in {"bomb", "straight_flush", "joker_bomb"}
                    )
                ),
                key=lambda fact: (not fact.consumes_control_resource, fact.carrier_count, fact.action_id),
            )
            nonpass_facts = sorted(
                (fact for fact in facts if fact.pattern != "pass"),
                key=lambda fact: (fact.carrier_count, fact.action_id),
            )
            if pass_fact is not None:
                # Keep the full legal response denominator here. Prompt-time
                # ranking below can then choose a recommended or structurally
                # informative response without inventing an action or relying
                # on the leader being an opponent with a low card count.
                contrasts.extend(
                    follow_contrast(
                        "follow_response_net_tradeoff",
                        (pass_fact.action_id, fact.action_id),
                        teammate_hand_count=pass_fact.teammate_hand_count,
                    )
                    for fact in nonpass_facts
                )
            if pass_fact is not None and is_teammate_leader and nonpass_facts:
                table_pattern = table_action.get("declared_pattern")
                same_shape = [fact for fact in nonpass_facts if fact.pattern == table_pattern]
                ordinary_responses = [
                    fact for fact in same_shape
                    if not fact.uses_wildcard
                    and not fact.consumes_control_resource
                    and fact.pattern not in {"bomb", "straight_flush", "joker_bomb"}
                ]
                response_pool = ordinary_responses or same_shape or nonpass_facts
                selected_response = min(
                    response_pool,
                    key=lambda fact: (
                        not fact.finishes_hand,
                        fact.fragments_played_rank_group,
                        fact.uses_wildcard,
                        fact.consumes_control_resource,
                        fact.residual_singleton_rank_count,
                        fact.estimated_remaining_rank_groups,
                        fact.natural_single_rank_value or 99,
                        fact.action_id,
                    ),
                )
                contrasts.append(
                    follow_contrast(
                        "teammate_table_choice",
                        (pass_fact.action_id, selected_response.action_id),
                        teammate_hand_count=pass_fact.teammate_hand_count,
                    )
                )
                if resource_facts:
                    contrasts.append(
                        follow_contrast(
                            "teammate_control_resource",
                            (pass_fact.action_id, resource_facts[0].action_id),
                            teammate_hand_count=pass_fact.teammate_hand_count,
                        )
                    )

            if pass_fact is not None and is_urgent_opponent and (resource_facts or nonpass_facts):
                kind = "danger_block_resource" if resource_facts else "danger_block_choice"
                selected_action = resource_facts[0] if resource_facts else nonpass_facts[0]
                contrasts.append(
                    follow_contrast(
                        kind,
                        (pass_fact.action_id, selected_action.action_id),
                        teammate_hand_count=pass_fact.teammate_hand_count,
                    )
                )

            # Opponent single-follow comparisons are kept to two canonical
            # natural singles: a lower ordinary response and a level/control
            # response.  This works for any public rank/seat and does not turn
            # the opponent's remaining cards into a prediction.
            if leader_relation == "opponent" and table_action.get("declared_pattern") == "single":
                ordinary_singles = [
                    fact for fact in facts
                    if fact.pattern == "single"
                    and not fact.uses_wildcard
                    and not fact.consumes_control_resource
                    and fact.natural_single_rank_value is not None
                    and not fact.finishes_hand
                ]
                control_singles_follow = [
                    fact for fact in facts
                    if fact.pattern == "single"
                    and not fact.uses_wildcard
                    and fact.consumes_control_resource
                    and fact.natural_single_rank_value is not None
                    and not fact.finishes_hand
                ]
                if ordinary_singles and control_singles_follow:
                    ordinary_singles.sort(
                        key=lambda fact: (
                            fact.fragments_played_rank_group,
                            fact.residual_singleton_rank_count,
                            fact.estimated_remaining_rank_groups,
                            fact.natural_single_rank_value or 99,
                            fact.action_id,
                        )
                    )
                    level_rank_value = (
                        _RANK_VALUES.get(level_rank, -1)
                        if isinstance(level_rank, str)
                        else -1
                    )
                    control_singles_follow.sort(
                        key=lambda fact: (
                            0 if fact.natural_single_rank_value == level_rank_value else 1,
                            -(fact.natural_single_rank_value or 0),
                            fact.action_id,
                        )
                    )
                    low_fact = ordinary_singles[0]
                    high_fact = control_singles_follow[0]
                    low_rank = _natural_same_rank(actions_by_id[low_fact.action_id], count=1)
                    high_rank = _natural_same_rank(actions_by_id[high_fact.action_id], count=1)
                    if low_rank is not None and high_rank is not None:
                        contrasts.append(
                            follow_contrast(
                                "opponent_single_control_cost",
                                (low_fact.action_id, high_fact.action_id),
                                rank_labels=(low_rank, high_rank),
                                teammate_hand_count=low_fact.teammate_hand_count,
                            )
                        )

    contrasts.sort(
        key=lambda item: (
            CANDIDATE_RELATION_KINDS.index(item.kind) if item.kind in CANDIDATE_RELATION_KINDS else len(CANDIDATE_RELATION_KINDS),
            item.action_ids,
        )
    )
    return tuple(contrasts)


def representative_candidate_contrasts(
    observation: object,
    legal_actions: object,
) -> tuple[CandidateContrast, ...] | None:
    """Return bounded, complete, stable representatives of public relations."""
    contrasts = summarize_candidate_contrasts(observation, legal_actions)
    if contrasts is None:
        return None
    representatives: list[CandidateContrast] = []
    counts: dict[str, int] = {}
    for contrast in contrasts:
        limit = 2 if contrast.kind == "bomb_residual" else 1
        if counts.get(contrast.kind, 0) < limit:
            representatives.append(contrast)
            counts[contrast.kind] = counts.get(contrast.kind, 0) + 1
    return tuple(representatives)


def select_candidate_structure_representatives(
    facts: tuple[CandidateStructure, ...],
    *,
    recommended_ids: tuple[int, ...] = (),
    contrast_action_id_groups: tuple[tuple[int, int], ...] = (),
    limit: int = 12,
) -> tuple[CandidateStructure, ...]:
    """Select deterministic comparison representatives without changing actions."""
    if type(limit) is not int or limit <= 0:
        return ()
    by_id = {fact.action_id: fact for fact in facts}
    chosen: list[CandidateStructure] = []
    def add(fact: CandidateStructure | None) -> None:
        if fact is not None and fact not in chosen and len(chosen) < limit:
            chosen.append(fact)
    for action_id in recommended_ids:
        add(by_id.get(action_id))
    # A relationship is useful only if both canonical alternatives can be
    # inspected together.  Do not retain half of a contrast when the bounded
    # representative budget cannot accommodate the complete pair.
    for group in contrast_action_id_groups:
        if (
            type(group) is not tuple
            or len(group) != 2
            or any(type(action_id) is not int or action_id not in by_id for action_id in group)
            or len(set(group)) != 2
            or len(chosen) + sum(1 for action_id in group if by_id[action_id] not in chosen) > limit
        ):
            continue
        for action_id in group:
            add(by_id[action_id])
    ordered = sorted(facts, key=lambda fact: fact.action_id)
    for predicate, key in (
        (lambda fact: fact.finishes_hand, lambda fact: fact.action_id),
        (lambda fact: fact.natural_single_rank_value is not None, lambda fact: (fact.natural_single_rank_value or 99, fact.action_id)),
        (lambda fact: fact.pattern == "pair" and not fact.fragments_played_rank_group, lambda fact: (fact.residual_singleton_rank_count, fact.action_id)),
        (lambda fact: fact.consumes_control_resource, lambda fact: fact.action_id),
        (lambda fact: fact.uses_wildcard, lambda fact: fact.action_id),
        (lambda fact: fact.fragments_played_rank_group, lambda fact: fact.action_id),
    ):
        matches = sorted((fact for fact in ordered if predicate(fact)), key=key)
        add(matches[0] if matches else None)
    for length in sorted({fact.bomb_length for fact in facts if fact.bomb_length is not None}):
        add(next((fact for fact in ordered if fact.bomb_length == length), None))
    for fact in ordered:
        add(fact)
    return tuple(chosen)
