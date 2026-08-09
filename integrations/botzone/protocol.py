"""Fail-closed parsers and validators for offline GuanDan messages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from .cards import RANKS, BotzoneCard, card_from_id
from .models import (
    ActionClaim,
    DealRequest,
    GlobalState,
    HistoryEntry,
    PlayRequest,
    UnsupportedStage,
)


class ProtocolValidationError(ValueError):
    """The complete message is invalid; callers must discard it as a whole."""


def _integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise ProtocolValidationError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise ProtocolValidationError(f"{label} outside allowed range")
    return value


def _player_id(value: object, label: str) -> int:
    return _integer(value, label, minimum=0, maximum=3)


def _id_sequence(value: object, label: str, *, unique: bool = True) -> tuple[int, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ProtocolValidationError(f"{label} must be an array")
    ids = tuple(_integer(item, label, minimum=0, maximum=107) for item in value)
    if unique and len(set(ids)) != len(ids):
        raise ProtocolValidationError(f"{label} contains duplicate physical IDs")
    return ids


def _mapping(value: object, label: str, required: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProtocolValidationError(f"{label} must be an object")
    keys = set(value)
    if keys != required:
        raise ProtocolValidationError(f"{label} has unsupported or missing fields")
    if not all(isinstance(key, str) for key in value):
        raise ProtocolValidationError(f"{label} keys must be strings")
    return value


def _global_state(value: object) -> GlobalState:
    data = _mapping(value, "global", frozenset({"level", "tribute", "first", "last"}))
    level = data["level"]
    if not isinstance(level, str) or level not in RANKS:
        raise ProtocolValidationError("global.level must be a rank")
    tribute = _integer(data["tribute"], "global.tribute", minimum=0, maximum=0)
    first = data["first"]
    last = data["last"]
    if first is not None or last is not None:
        raise ProtocolValidationError("no-tribute profile requires null first and last")
    return GlobalState(level=level, tribute=tribute, first=None, last=None)


def parse_action_claim(
    value: object,
    *,
    level: str,
    known_hand_ids: Sequence[int] | None = None,
) -> ActionClaim:
    """Validate a response without relying on permissive referee behavior."""

    if level not in RANKS:
        raise ProtocolValidationError("level must be a rank")
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) != 2:
        raise ProtocolValidationError("response must be [action, claim]")
    action = _id_sequence(value[0], "action")
    claim = _id_sequence(value[1], "claim")
    if not action and not claim:
        return ActionClaim.pass_action()
    if not action or not claim:
        raise ProtocolValidationError("pass must be [[], []]")
    if len(action) != len(claim):
        raise ProtocolValidationError("action and claim lengths differ")

    if known_hand_ids is not None:
        known_hand = _id_sequence(known_hand_ids, "known_hand_ids")
        if not set(action).issubset(known_hand):
            raise ProtocolValidationError("action contains a card outside the known hand")

    action_cards = tuple(card_from_id(card_id) for card_id in action)
    claim_cards = tuple(card_from_id(card_id) for card_id in claim)
    wildcard_count = sum(card.is_wildcard(level) for card in action_cards)
    if wildcard_count > 2:
        raise ProtocolValidationError("more than two wildcards are impossible in the physical pool")

    if wildcard_count == 0:
        if set(action) != set(claim):
            raise ProtocolValidationError("natural action and claim must use the same physical IDs")
        return ActionClaim(action, claim)

    non_wild_faces = Counter(_face(card) for card in action_cards if not card.is_wildcard(level))
    claim_faces = Counter(_face(card) for card in claim_cards)
    if any(claim_faces[face] < count for face, count in non_wild_faces.items()):
        raise ProtocolValidationError("non-wild action faces are absent from claim")
    claim_faces.subtract(non_wild_faces)
    remaining = tuple(face for face, count in claim_faces.items() for _ in range(count) if count > 0)
    if len(remaining) != wildcard_count:
        raise ProtocolValidationError("claim remainder does not equal wildcard count")
    if any(face[0] in {"SJ", "BJ"} for face in remaining):
        raise ProtocolValidationError("wildcards cannot be declared as jokers")
    return ActionClaim(action, claim)


def _face(card: BotzoneCard) -> tuple[str, str | None]:
    return card.rank, card.suit


def _history(value: object, level: str) -> tuple[HistoryEntry, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ProtocolValidationError("history must be an array")
    if len(value) > 4:
        raise ProtocolValidationError("history may contain at most four entries")
    entries: list[HistoryEntry] = []
    for index, raw_entry in enumerate(value):
        entry = _mapping(raw_entry, f"history[{index}]", frozenset({"player", "response"}))
        entries.append(
            HistoryEntry(
                player_id=_player_id(entry["player"], f"history[{index}].player"),
                response=parse_action_claim(entry["response"], level=level),
            )
        )
    return tuple(entries)


def _done(value: object) -> tuple[int, ...]:
    done = _id_sequence(value, "done")
    if any(player > 3 for player in done):
        raise ProtocolValidationError("done must contain player IDs")
    return done


def _play_request(data: Mapping[str, object]) -> PlayRequest:
    expected = frozenset({"stage", "history", "done", "pass_on", "global"})
    payload = _mapping(data, "play request", expected)
    global_state = _global_state(payload["global"])
    return PlayRequest(
        history=_history(payload["history"], global_state.level),
        done=tuple(_player_id(player, "done") for player in _done(payload["done"])),
        pass_on=_integer(payload["pass_on"], "pass_on", minimum=-1, maximum=3),
        global_state=global_state,
    )


def _deal_request(data: Mapping[str, object]) -> DealRequest:
    expected = frozenset({"stage", "deliver", "your_id", "global"})
    payload = _mapping(data, "deal request", expected)
    deliver = _id_sequence(payload["deliver"], "deliver")
    if len(deliver) != 27:
        raise ProtocolValidationError("deliver must contain exactly 27 cards")
    return DealRequest(
        deliver=deliver,
        your_id=_player_id(payload["your_id"], "your_id"),
        global_state=_global_state(payload["global"]),
    )


def parse_stage_request(value: object) -> DealRequest | PlayRequest | UnsupportedStage:
    """Parse a complete request or return a non-executable unsupported result."""

    if not isinstance(value, Mapping):
        raise ProtocolValidationError("request must be an object")
    stage = value.get("stage")
    if not isinstance(stage, str):
        raise ProtocolValidationError("stage must be a string")
    if stage in {"tribute", "return"}:
        return UnsupportedStage(stage)
    if stage == "deal":
        return _deal_request(value)
    if stage == "play":
        return _play_request(value)
    return UnsupportedStage(stage)


def validate_no_tribute_opening(
    deals: Sequence[DealRequest],
    first_play: PlayRequest,
    *,
    first_player_id: object,
) -> None:
    """Validate the offline fixture: four deals followed by player 0's play."""

    if _player_id(first_player_id, "first_player_id") != 0:
        raise ProtocolValidationError("first no-tribute play must belong to player 0")
    if len(deals) != 4:
        raise ProtocolValidationError("opening requires exactly four deal requests")
    if {deal.your_id for deal in deals} != {0, 1, 2, 3}:
        raise ProtocolValidationError("deal requests must cover players 0..3 exactly once")
    all_dealt = tuple(card_id for deal in deals for card_id in deal.deliver)
    if len(set(all_dealt)) != 108:
        raise ProtocolValidationError("opening deals must preserve all 108 physical cards")
    if first_play.history or first_play.done or first_play.pass_on != -1:
        raise ProtocolValidationError("first play fixture contains prior play state")
