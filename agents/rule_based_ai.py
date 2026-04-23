"""Minimal rule-based AI that only selects an action_id from legal actions."""

from agents.base import BaseAgent


class RuleBasedAIAgent(BaseAgent):
    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        if not legal_actions:
            raise ValueError("legal_actions must not be empty")

        non_pass_actions = [action for action in legal_actions if action.get("declared_pattern") != "pass"]
        candidates = non_pass_actions or legal_actions
        chosen = sorted(
            candidates,
            key=lambda action: (
                int(action.get("wildcard_count", 0)),
                -len(action.get("carrier_cards", [])),
                str(action.get("declared_pattern")),
                tuple(str(token) for token in action.get("declared_cards", [])),
                int(action["action_id"]),
            ),
        )[0]
        return int(chosen["action_id"])
