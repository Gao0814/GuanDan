"""Base agent abstractions for action-id selection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class BaseAgent(ABC):
    player_id: int
    name: str = field(default="base-agent")

    @abstractmethod
    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        """Return one action_id from the current legal action list."""
