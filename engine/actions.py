"""Action models for explicit legal-action expansion."""

from dataclasses import dataclass
from enum import Enum

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


def public_action_id(index: int) -> int:
    if index < 0:
        raise ValueError("action index must be non-negative")
    return index + 1
