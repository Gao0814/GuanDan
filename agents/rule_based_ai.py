"""Rule-based selectors that only choose supplied legal action ids."""

from agents.base import BaseAgent
from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id


class FrozenRuleBasedAIAgent(BaseAgent):
    """Frozen pre-pressure-pass static selector used by historical evaluation."""

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


class RuleBasedAIAgent(FrozenRuleBasedAIAgent):
    """Default RuleBased selector with the strictly proven pressure-pass rule."""

    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        pass_id = conditional_pressure_pass_id(observation, legal_actions, self.player_id)
        if pass_id is not None:
            return pass_id
        return super().select_action(observation, legal_actions)
