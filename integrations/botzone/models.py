"""Immutable, JSON-friendly protocol values with no runtime behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlobalState:
    level: str
    tribute: int
    first: int | None
    last: int | None

    def to_json(self) -> dict[str, str | int | None]:
        return {
            "level": self.level,
            "tribute": self.tribute,
            "first": self.first,
            "last": self.last,
        }


@dataclass(frozen=True, slots=True)
class ActionClaim:
    """A validated wire response. Tuples keep the model immutable."""

    action: tuple[int, ...]
    claim: tuple[int, ...]

    @property
    def is_pass(self) -> bool:
        return not self.action and not self.claim

    @classmethod
    def pass_action(cls) -> "ActionClaim":
        return cls((), ())

    def to_json(self) -> list[list[int]]:
        return [list(self.action), list(self.claim)]


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    player_id: int
    response: ActionClaim

    def to_json(self) -> dict[str, int | list[list[int]]]:
        return {"player": self.player_id, "response": self.response.to_json()}


@dataclass(frozen=True, slots=True)
class DealRequest:
    deliver: tuple[int, ...]
    your_id: int
    global_state: GlobalState

    def response_json(self) -> list[object]:
        return []


@dataclass(frozen=True, slots=True)
class PlayRequest:
    history: tuple[HistoryEntry, ...]
    done: tuple[int, ...]
    pass_on: int
    global_state: GlobalState


@dataclass(frozen=True, slots=True)
class UnsupportedStage:
    """A non-executable result for stages outside the no-tribute profile."""

    stage: str
    error: str = "unsupported_stage"

    def to_json(self) -> dict[str, str]:
        return {"error": self.error, "stage": self.stage}
