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
    teammate_active: bool
    minimum_opponent_hand_count: int | None
    is_free_lead: bool


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


_RANK_VALUES = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15,
    "SJ": 16, "BJ": 17,
}
_TEAM_BY_PLAYER = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}
CANDIDATE_RELATION_KINDS = (
    "natural_single_cost",
    "single_control_resource",
    "natural_pair_single",
    "natural_group_single",
    "bomb_residual",
    "wildcard_resource",
    "teammate_control_resource",
    "teammate_table_choice",
    "danger_block_resource",
    "danger_block_choice",
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
            results.append(CandidateStructure(
                action_id, pattern, 0, False, False, False, 0, len({_rank_of(card) for card in hand}),
                False, None, False, None, None, teammate_count, teammate_active,
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
            teammate_count, teammate_active, min(opponent_counts) if opponent_counts else None,
            current_round.get("constraint") == "free",
        ))
        seen.add(action_id)
    return tuple(results)


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

    bombs_by_rank: dict[str, dict[int, CandidateStructure]] = {}
    pairs_by_rank: dict[str, CandidateStructure] = {}
    singles_by_rank: dict[str, CandidateStructure] = {}
    all_singles: list[CandidateStructure] = []
    for fact in facts:
        action = actions_by_id.get(fact.action_id)
        if action is None or not fact.is_free_lead:
            continue
        if fact.pattern == "bomb" and fact.bomb_length in {4, 5}:
            rank = _natural_same_rank(action, count=fact.bomb_length)
            if rank is not None:
                bombs_by_rank.setdefault(rank, {}).setdefault(fact.bomb_length, fact)
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
    for rank in sorted(bombs_by_rank, key=lambda item: _RANK_VALUES[item]):
        choices = bombs_by_rank[rank]
        four = choices.get(4)
        five = choices.get(5)
        if (
            four is not None
            and five is not None
            and four.leaves_bomb_rank_singleton is True
            and five.clears_played_rank_groups is True
        ):
            contrasts.append(
                CandidateContrast(
                    "bomb_residual",
                    (four.action_id, five.action_id),
                    four.teammate_hand_count,
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
            leader_id = leaders[-1].get("player_id") if leaders else None
            my_team = observation_map.get("my_info", {}).get("team") if isinstance(observation_map.get("my_info"), Mapping) else None
            player_by_id = {
                item.get("player_id"): item
                for item in observation_map.get("other_players", [])
                if isinstance(item, Mapping)
            } if isinstance(observation_map.get("other_players"), list) else {}
            leader = player_by_id.get(leader_id)
            is_teammate_leader = isinstance(leader, Mapping) and leader.get("team") == my_team
            is_urgent_opponent = (
                isinstance(leader, Mapping)
                and leader.get("team") != my_team
                and _is_int(leader.get("hand_count"))
                and 0 < int(leader["hand_count"]) <= 2
            )
            pass_fact = next((fact for fact in facts if fact.pattern == "pass"), None)
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
            if pass_fact is not None and (resource_facts or nonpass_facts):
                if is_teammate_leader:
                    kind = "teammate_control_resource" if resource_facts else "teammate_table_choice"
                elif is_urgent_opponent:
                    kind = "danger_block_resource" if resource_facts else "danger_block_choice"
                else:
                    kind = None
                if kind is not None:
                    selected_action = resource_facts[0] if resource_facts else nonpass_facts[0]
                    contrasts.append(
                        CandidateContrast(
                            kind,
                            (pass_fact.action_id, selected_action.action_id),
                            pass_fact.teammate_hand_count,
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
    """Return the first complete, stable contrast of each public relation kind."""
    contrasts = summarize_candidate_contrasts(observation, legal_actions)
    if contrasts is None:
        return None
    representatives: list[CandidateContrast] = []
    seen: set[str] = set()
    for contrast in contrasts:
        if contrast.kind not in seen:
            representatives.append(contrast)
            seen.add(contrast.kind)
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
