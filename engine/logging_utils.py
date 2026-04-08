"""Debug logging and trace models for phase-1 observability."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .actions import Action


class EvidenceLayer(str, Enum):
    """Decision evidence classification."""

    RULE = "rule"
    EXPERIENCE = "experience"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Minimal decision trace required for phase-1 debugging."""

    step_no: int
    player_id: int
    legal_actions: tuple[Action, ...]
    selected_action: Action
    evidence_layer: EvidenceLayer
    evidence_notes: tuple[str, ...] = ()
    evidence_sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StateDelta:
    """Captures state-change summary before/after an action."""

    before: dict[str, Any]
    after: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DebugEvent:
    """A structured debug event record."""

    event_type: str
    payload: dict[str, Any]


@dataclass(slots=True)
class DebugLogger:
    """In-memory debug logger skeleton.

    Persistent logging/output formatting is deferred after Step 1.
    """

    events: list[DebugEvent] = field(default_factory=list)

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append(DebugEvent(event_type=event_type, payload=payload))
