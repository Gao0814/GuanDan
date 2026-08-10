"""Standalone Botzone GuanDan bot for the Python 3.6.5 compiler.

The upload profile is intentionally narrow: traditional JSON interaction,
no tribute/return, no external dependencies, and natural-card actions only.
It reconstructs the local hand from Botzone's requests/responses envelope and
uses a deterministic rule policy over a legal natural-card subset.
"""

import json
import sys
from collections import Counter


RANKS_BY_ID = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS_BY_ID = ("h", "d", "s", "c")
NORMAL_RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
STRAIGHT_WINDOWS = (
    ("A", "2", "3", "4", "5"),
    ("2", "3", "4", "5", "6"),
    ("3", "4", "5", "6", "7"),
    ("4", "5", "6", "7", "8"),
    ("5", "6", "7", "8", "9"),
    ("6", "7", "8", "9", "10"),
    ("7", "8", "9", "10", "J"),
    ("8", "9", "10", "J", "Q"),
    ("9", "10", "J", "Q", "K"),
    ("10", "J", "Q", "K", "A"),
)
PAIR_WINDOWS = (
    ("3", "4", "5"), ("4", "5", "6"), ("5", "6", "7"),
    ("6", "7", "8"), ("7", "8", "9"), ("8", "9", "10"),
    ("9", "10", "J"), ("10", "J", "Q"), ("J", "Q", "K"),
    ("Q", "K", "A"),
)
STEEL_WINDOWS = (
    ("3", "4"), ("4", "5"), ("5", "6"), ("6", "7"),
    ("7", "8"), ("8", "9"), ("9", "10"), ("10", "J"),
    ("J", "Q"), ("Q", "K"), ("K", "A"),
)
BASE_STRENGTH = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13,
    "A": 14, "2": 15, "SJ": 17, "BJ": 18,
}


class InputError(Exception):
    pass


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _card(card_id):
    if not _is_int(card_id) or card_id < 0 or card_id >= 108:
        raise InputError("invalid_card_id")
    offset = card_id % 54
    if offset == 52:
        return ("SJ", None)
    if offset == 53:
        return ("BJ", None)
    rank_index, suit_index = divmod(offset, 4)
    return (RANKS_BY_ID[rank_index], SUITS_BY_ID[suit_index])


def _rank_strength(rank, level):
    if rank == level:
        return 16
    return BASE_STRENGTH[rank]


def _card_sort_key(card_id, level):
    rank, suit = _card(card_id)
    suit_value = 4 if suit is None else SUITS_BY_ID.index(suit)
    return (_rank_strength(rank, level), suit_value, card_id)


def _require_level(value):
    if value not in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"):
        raise InputError("invalid_level")
    return value


def _require_global(value, expected_level=None):
    if not isinstance(value, dict):
        raise InputError("invalid_global")
    level = _require_level(value.get("level"))
    if expected_level is not None and level != expected_level:
        raise InputError("level_changed")
    if value.get("tribute") != 0:
        raise InputError("tribute_not_supported")
    if "tribute_cards" in value and value.get("tribute_cards") != {}:
        raise InputError("tribute_not_supported")
    if "return_cards" in value and value.get("return_cards") != {}:
        raise InputError("tribute_not_supported")
    return level


def _require_id_list(value, unique):
    if not isinstance(value, list):
        raise InputError("invalid_card_list")
    result = []
    for item in value:
        _card(item)
        result.append(item)
    if unique and len(set(result)) != len(result):
        raise InputError("duplicate_physical_card")
    return result


def _parse_action_claim(value, known_hand=None):
    if not isinstance(value, list) or len(value) != 2:
        raise InputError("invalid_action_claim")
    action = _require_id_list(value[0], True)
    claim = _require_id_list(value[1], False)
    if len(action) != len(claim):
        raise InputError("action_claim_length")
    if (not action) != (not claim):
        raise InputError("invalid_pass")
    if known_hand is not None and not set(action).issubset(set(known_hand)):
        raise InputError("action_not_in_hand")
    return action, claim


def _parse_envelope(value):
    if not isinstance(value, dict):
        raise InputError("invalid_envelope")
    requests = value.get("requests")
    responses = value.get("responses")
    if not isinstance(requests, list) or not isinstance(responses, list):
        raise InputError("invalid_envelope")
    if not requests or len(requests) != len(responses) + 1:
        raise InputError("invalid_envelope_length")

    deal = requests[0]
    if not isinstance(deal, dict) or deal.get("stage") != "deal":
        raise InputError("missing_deal")
    level = _require_global(deal.get("global"))
    hand = _require_id_list(deal.get("deliver"), True)
    if len(hand) != 27:
        raise InputError("invalid_deal_size")
    player_id = deal.get("your_id")
    if not _is_int(player_id) or player_id < 0 or player_id > 3:
        raise InputError("invalid_player_id")

    for index, response in enumerate(responses):
        request = requests[index]
        if not isinstance(request, dict):
            raise InputError("invalid_request")
        stage = request.get("stage")
        _require_global(request.get("global"), level)
        if stage == "deal":
            if index != 0 or response != [] or not isinstance(response, list):
                raise InputError("invalid_deal_response")
        elif stage == "play":
            action, unused_claim = _parse_action_claim(response, hand)
            del unused_claim
            used = set(action)
            hand = [card_id for card_id in hand if card_id not in used]
        else:
            raise InputError("unsupported_stage")

    current = requests[-1]
    if not isinstance(current, dict):
        raise InputError("invalid_request")
    _require_global(current.get("global"), level)
    return current, hand, player_id, level


def _history_entries(value):
    if not isinstance(value, list) or len(value) != 4:
        raise InputError("invalid_history")
    entries = []
    seen_real = False
    for slot in value:
        if slot == [] and isinstance(slot, list):
            if seen_real:
                raise InputError("misplaced_empty_history")
            continue
        seen_real = True
        if not isinstance(slot, dict) or set(slot.keys()) != set(("player", "response")):
            raise InputError("invalid_history_entry")
        player = slot.get("player")
        if not _is_int(player) or player < 0 or player > 3:
            raise InputError("invalid_history_player")
        action, claim = _parse_action_claim(slot.get("response"))
        entries.append((player, action, claim))
    return entries


def _table_leader(current, player_id):
    entries = _history_entries(current.get("history"))
    for player, action, claim in reversed(entries):
        if player == player_id:
            break
        if action:
            return claim
    return None


def _window_index(ranks, windows):
    rank_set = set(ranks)
    if len(rank_set) != len(ranks):
        return None
    for index, window in enumerate(windows):
        if rank_set == set(window):
            return index
    return None


def _pattern(card_ids, level):
    if not card_ids:
        return {"type": "pass", "count": 0, "value": None, "bomb_length": None}
    faces = [_card(card_id) for card_id in card_ids]
    ranks = [face[0] for face in faces]
    count = len(card_ids)
    counts = Counter(ranks)
    result = {"type": "unknown", "count": count, "value": None, "bomb_length": None}
    if count == 1:
        result.update(type="single", value=_rank_strength(ranks[0], level))
    elif count == 2 and len(counts) == 1:
        result.update(type="pair", value=_rank_strength(ranks[0], level))
    elif count == 3 and len(counts) == 1 and ranks[0] not in ("SJ", "BJ"):
        result.update(type="triple", value=_rank_strength(ranks[0], level))
    elif count == 4 and counts.get("SJ", 0) == 2 and counts.get("BJ", 0) == 2:
        result.update(type="joker_bomb")
    elif count >= 4 and len(counts) == 1 and ranks[0] not in ("SJ", "BJ"):
        result.update(type="bomb", value=_rank_strength(ranks[0], level), bomb_length=count)
    elif count == 5 and sorted(counts.values()) == [2, 3]:
        triple_rank = [rank for rank in counts if counts[rank] == 3][0]
        if triple_rank not in ("SJ", "BJ"):
            result.update(type="triple_with_pair", value=_rank_strength(triple_rank, level))
    elif count == 5 and "SJ" not in counts and "BJ" not in counts:
        index = _window_index(ranks, STRAIGHT_WINDOWS)
        if index is not None:
            suits = set(face[1] for face in faces)
            result.update(type="straight_flush" if len(suits) == 1 else "straight", value=index)
    elif count == 6 and "SJ" not in counts and "BJ" not in counts:
        if sorted(counts.values()) == [2, 2, 2]:
            index = _window_index(list(counts.keys()), PAIR_WINDOWS)
            if index is not None:
                result.update(type="pair_straight", value=index)
        elif sorted(counts.values()) == [3, 3]:
            index = _window_index(list(counts.keys()), STEEL_WINDOWS)
            if index is not None:
                result.update(type="steel_plate", value=index)
    return result


def _bomb_tier(pattern):
    if pattern["type"] == "joker_bomb":
        return 5
    if pattern["type"] == "straight_flush":
        return 3
    if pattern["type"] == "bomb":
        length = pattern["bomb_length"]
        if length >= 6:
            return 4
        if length == 5:
            return 2
        return 1
    return 0


def _can_beat(candidate, leading):
    if candidate["type"] == leading["type"]:
        if candidate["type"] == "joker_bomb":
            return False
        if candidate["type"] == "bomb":
            if candidate["bomb_length"] != leading["bomb_length"]:
                return candidate["bomb_length"] > leading["bomb_length"]
        if candidate["type"] in ("straight", "pair_straight", "steel_plate", "straight_flush"):
            if candidate["count"] != leading["count"]:
                return False
        return candidate["value"] is not None and leading["value"] is not None and candidate["value"] > leading["value"]
    candidate_tier = _bomb_tier(candidate)
    if candidate_tier == 0:
        return False
    return candidate_tier > _bomb_tier(leading)


def _make_action(pattern_type, cards, level):
    ordered = sorted(cards, key=lambda item: _card_sort_key(item, level))
    detected = _pattern(ordered, level)
    if detected["type"] != pattern_type:
        return None
    return {"pattern": detected, "cards": ordered, "claim": list(ordered)}


def _ordinary_straight_cards(window, by_rank):
    selected = [by_rank[rank][0] for rank in window]
    if len(set(_card(card_id)[1] for card_id in selected)) != 1:
        return selected
    for index, rank in enumerate(window):
        first_suit = _card(selected[0])[1]
        for candidate in by_rank[rank][1:]:
            if _card(candidate)[1] != first_suit:
                changed = list(selected)
                changed[index] = candidate
                return changed
    return None


def _generate_actions(hand, level):
    by_rank = {}
    by_rank_suit = {}
    for card_id in sorted(hand, key=lambda item: _card_sort_key(item, level)):
        rank, suit = _card(card_id)
        by_rank.setdefault(rank, []).append(card_id)
        by_rank_suit.setdefault((rank, suit), []).append(card_id)

    actions = []

    def add(pattern_type, cards):
        action = _make_action(pattern_type, cards, level)
        if action is not None:
            actions.append(action)

    for rank in sorted(by_rank, key=lambda item: _rank_strength(item, level)):
        cards = by_rank[rank]
        add("single", cards[:1])
        if len(cards) >= 2:
            add("pair", cards[:2])
        if len(cards) >= 3 and rank not in ("SJ", "BJ"):
            add("triple", cards[:3])
        if rank not in ("SJ", "BJ"):
            for length in range(4, len(cards) + 1):
                add("bomb", cards[:length])

    triple_ranks = [rank for rank in by_rank if len(by_rank[rank]) >= 3 and rank not in ("SJ", "BJ")]
    pair_ranks = [rank for rank in by_rank if len(by_rank[rank]) >= 2]
    for triple_rank in triple_ranks:
        for pair_rank in pair_ranks:
            if pair_rank != triple_rank:
                add("triple_with_pair", by_rank[triple_rank][:3] + by_rank[pair_rank][:2])

    for window in STRAIGHT_WINDOWS:
        if all(rank in by_rank for rank in window):
            cards = _ordinary_straight_cards(window, by_rank)
            if cards is not None:
                add("straight", cards)
        for suit in SUITS_BY_ID:
            if all((rank, suit) in by_rank_suit for rank in window):
                add("straight_flush", [by_rank_suit[(rank, suit)][0] for rank in window])

    for window in PAIR_WINDOWS:
        if all(len(by_rank.get(rank, ())) >= 2 for rank in window):
            add("pair_straight", sum((by_rank[rank][:2] for rank in window), []))
    for window in STEEL_WINDOWS:
        if all(len(by_rank.get(rank, ())) >= 3 for rank in window):
            add("steel_plate", sum((by_rank[rank][:3] for rank in window), []))
    if len(by_rank.get("SJ", ())) >= 2 and len(by_rank.get("BJ", ())) >= 2:
        add("joker_bomb", by_rank["SJ"][:2] + by_rank["BJ"][:2])

    unique = {}
    for action in actions:
        key = (action["pattern"]["type"], tuple(action["cards"]), tuple(action["claim"]))
        unique[key] = action
    return list(unique.values())


def _choose_action(hand, level, leading_claim):
    actions = _generate_actions(hand, level)
    if leading_claim is not None:
        leading = _pattern(leading_claim, level)
        if leading["type"] == "unknown":
            return [[], []]
        actions = [action for action in actions if _can_beat(action["pattern"], leading)]
        if not actions:
            return [[], []]
    if not actions:
        if leading_claim is not None:
            return [[], []]
        raise InputError("no_lead_action")
    chosen = sorted(
        actions,
        key=lambda action: (
            -len(action["cards"]),
            action["pattern"]["type"],
            tuple(_card(card_id)[0] for card_id in action["claim"]),
            tuple(action["cards"]),
        ),
    )[0]
    return [chosen["cards"], chosen["claim"]]


def decide(payload):
    current, hand, player_id, level = _parse_envelope(payload)
    stage = current.get("stage")
    if stage == "deal":
        return []
    if stage != "play":
        raise InputError("unsupported_stage")
    leading_claim = _table_leader(current, player_id)
    return _choose_action(hand, level, leading_claim)


def _fallback(raw):
    try:
        requests = raw.get("requests") if isinstance(raw, dict) else None
        current = requests[-1] if isinstance(requests, list) and requests else None
        if isinstance(current, dict) and current.get("stage") == "play":
            return [[], []]
    except Exception:
        pass
    return []


def main():
    raw = None
    try:
        line = sys.stdin.readline()
        if not line:
            raise InputError("missing_input")
        raw = json.loads(line)
        response = decide(raw)
        output = {"response": response}
    except Exception:
        output = {"response": _fallback(raw), "debug": "input_invalid_or_unsupported"}
    sys.stdout.write(json.dumps(output, separators=(",", ":"), ensure_ascii=True) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
