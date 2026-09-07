"""Explicit opt-in public-information pass-preservation Agent."""

from __future__ import annotations

from dataclasses import dataclass

from agents.base import BaseAgent
from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id
from agents.rule_based_ai import FrozenRuleBasedAIAgent


@dataclass(slots=True)
class ConditionalPressurePassAIAgent(BaseAgent):
    """Opt-in candidate that preserves special pressure resources when proven safe."""

    opportunity_count: int = 0
    conditional_pass_count: int = 0
    last_decision_source: str | None = None

    def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
        pass_id = conditional_pressure_pass_id(observation, legal_actions, self.player_id)
        if pass_id is not None:
            self.opportunity_count += 1
            self.conditional_pass_count += 1
            self.last_decision_source = "conditional_pressure_pass"
            return pass_id
        self.last_decision_source = "conditional_rule_based"
        return FrozenRuleBasedAIAgent(player_id=self.player_id).select_action(observation, legal_actions)
