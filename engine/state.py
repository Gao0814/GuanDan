"""State models for the single-game GuanDan mainline."""

from dataclasses import dataclass, replace

from .actions import Action
from .cards import Card


@dataclass(frozen=True, slots=True)
class TableConstraint:
    leading_action: Action | None = None
    leader_player_id: int | None = None
    pending_player_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PlayerState:
    player_id: int
    hand_cards: tuple[Card, ...]
    finish_rank: int | None = None

    @property
    def is_finished(self) -> bool:
        return self.finish_rank is not None

    def with_hand_cards(self, hand_cards: tuple[Card, ...]) -> "PlayerState":
        return replace(self, hand_cards=hand_cards)

    def with_finish_rank(self, finish_rank: int) -> "PlayerState":
        return replace(self, finish_rank=finish_rank)


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    step_no: int
    round_no: int
    player_id: int
    action: Action


@dataclass(frozen=True, slots=True)
class GameState:
    players: tuple[PlayerState, ...]
    current_player_id: int
    current_level_rank: str
    table_constraint: TableConstraint
    step_no: int = 0
    round_no: int = 1
    finish_order: tuple[int, ...] = ()
    history: tuple[HistoryEntry, ...] = ()
    is_finished: bool = False
    winner: str | None = None

    def get_player(self, player_id: int) -> PlayerState:
        for player in self.players:
            if player.player_id == player_id:
                return player
        raise KeyError(f"player not found: {player_id}")

    def unfinished_player_ids(self) -> tuple[int, ...]:
        return tuple(player.player_id for player in self.players if not player.is_finished)
