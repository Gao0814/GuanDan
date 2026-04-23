"""Action models for explicit legal-action expansion."""

from dataclasses import dataclass
from enum import Enum
import hashlib

from .cards import Card
from .patterns import PatternType


class ActionType(str, Enum):
    PLAY = "play"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class WildcardInfo:
    carrier_card: Card
    declared_as: Card


@dataclass(frozen=True, slots=True)
class Action:
    player_id: int
    action_type: ActionType
    declared_pattern: PatternType | None = None
    declared_cards: tuple[Card, ...] = ()
    carrier_cards: tuple[Card, ...] = ()
    wildcard_count: int = 0
    wildcard_info: tuple[WildcardInfo, ...] = ()
    display_text: str = ""

    @classmethod
    def make_pass(cls, player_id: int) -> "Action":
        return cls(
            player_id=player_id,
            action_type=ActionType.PASS,
            declared_pattern=None,
            declared_cards=(),
            carrier_cards=(),
            wildcard_count=0,
            wildcard_info=(),
            display_text="pass",
        )


def _card_identity(card: Card) -> tuple[str, str | None]:
    return (card.rank, card.suit)


def stable_action_id(action: Action) -> int:
    identity = (
        action.player_id,
        action.action_type.value,
        action.declared_pattern.value if action.declared_pattern is not None else None,
        tuple(_card_identity(card) for card in action.declared_cards),
        tuple(_card_identity(card) for card in action.carrier_cards),
        action.wildcard_count,
        tuple(
            (
                _card_identity(item.carrier_card),
                _card_identity(item.declared_as),
            )
            for item in action.wildcard_info
        ),
    )
    digest = hashlib.blake2b(repr(identity).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)
