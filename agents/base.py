"""Base agent abstractions for action-id selection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def legal_action_ids(legal_actions: list[dict[str, object]]) -> set[int]:
    ids: set[int] = set()
    for action in legal_actions:
        try:
            ids.add(int(action["action_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def require_legal_action_id(action_id: int, legal_actions: list[dict[str, object]]) -> int:
    action_id_int = int(action_id)
    if action_id_int not in legal_action_ids(legal_actions):
        raise ValueError("selected action_id must come from legal_actions")
    return action_id_int


@dataclass(slots=True)
class BaseAgent(ABC):
    player_id: int
    name: str = field(default="base-agent", kw_only=True)

    @abstractmethod
    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        """Return one action_id from the current legal action list."""
