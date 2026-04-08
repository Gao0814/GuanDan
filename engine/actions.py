"""Action models for game interaction."""

from dataclasses import dataclass
from enum import Enum

from .cards import Card
from .patterns import PatternType


class ActionType(str, Enum):
    """Supported action categories in phase-1."""

    PLAY = "play"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class Action:
    """An action selected by a player."""

    player_id: int
    action_type: ActionType
    cards: tuple[Card, ...] = ()
    declared_pattern: PatternType | None = None
    trace_id: str | None = None

    @staticmethod
    def make_pass(player_id: int) -> "Action":
        return Action(player_id=player_id, action_type=ActionType.PASS)
