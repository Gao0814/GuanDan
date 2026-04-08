"""Base agent abstractions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from engine.actions import Action
from engine.state import GameState


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Context passed to agent at decision time."""

    step_no: int
    retrieved_rule_refs: tuple[str, ...] = ()
    retrieved_experience_refs: tuple[str, ...] = ()


@dataclass(slots=True)
class BaseAgent(ABC):
    """Base class for all non-human agents."""

    player_id: int
    name: str = field(default="base-agent")

    @abstractmethod
    def select_action(
        self,
        state: GameState,
        legal_actions: tuple[Action, ...],
        context: AgentContext,
    ) -> Action:
        """Select one action from legal actions only."""
