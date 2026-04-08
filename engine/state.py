"""Core state models for players, table constraints, and game session."""

from dataclasses import dataclass, replace

from .actions import Action
from .cards import Card
from .patterns import PatternType


@dataclass(frozen=True, slots=True)
class TableConstraint:
    """Current round/table constraint snapshot."""

    leading_action: Action | None = None
    required_pattern: PatternType | None = None
    min_strength_hint: int | None = None


@dataclass(frozen=True, slots=True)
class PlayerState:
    """Immutable player state container."""

    player_id: int
    hand_cards: tuple[Card, ...]

    def with_hand_cards(self, hand_cards: tuple[Card, ...]) -> "PlayerState":
        return replace(self, hand_cards=hand_cards)


@dataclass(frozen=True, slots=True)
class GameState:
    """Immutable top-level game state."""

    players: tuple[PlayerState, ...]
    current_player_id: int
    table_constraint: TableConstraint
    step_no: int = 0
    round_no: int = 1
    consecutive_passes: int = 0
    is_finished: bool = False
    winner_player_id: int | None = None

    def get_player(self, player_id: int) -> PlayerState:
        for player in self.players:
            if player.player_id == player_id:
                return player
        raise KeyError(f"Player not found: {player_id}")
