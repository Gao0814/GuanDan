"""Bounded public-only model-before strategy guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from agents.action_structure import summarize_candidate_structures


_SOURCE = "public_strategy_recommendation_v2"
STRATEGY_DOMAINS = (
    "overall_priority", "opening_free_lead", "hand_structure",
    "control_return_resource", "follow_control", "teammate_coordination",
    "danger_opponent_block", "bomb_wildcard_management", "endgame_planning",
    "uncertainty_probe",
)
OBJECTIVE_CODES = (
    "finish_now", "protect_structure", "low_cost_probe", "preserve_control",
    "contest_follow", "support_teammate", "block_opponent", "manage_bomb_wildcard",
    "plan_endgame",
)
COUNTERCHECK_CODES = (
    "check_public_urgency", "check_trick_ownership", "check_structure_loss",
    "check_control_cost", "check_rule_pressure",
)


@dataclass(frozen=True, slots=True)
class StrategyRecommendation:
    status: str
    source: str
    action_ids: tuple[int, ...]
    objective_codes: tuple[str, ...]
    countercheck_codes: tuple[str, ...]
    strategy_domains: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status, "source": self.source,
            "action_ids": list(self.action_ids),
            "objective_codes": list(self.objective_codes),
            "countercheck_codes": list(self.countercheck_codes),
            "strategy_domains": list(self.strategy_domains),
        }


def _ordered(values: set[str], order: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in order if value in values)


def _unavailable() -> StrategyRecommendation:
    return StrategyRecommendation("unavailable", _SOURCE, (), (), (), ())


def build_strategy_recommendation(
    observation: object,
    legal_actions: object,
    *,
    strategy_context: object = None,
) -> StrategyRecommendation:
    """Return stable guidance codes and, only when clear, a canonical shortlist."""
    if not isinstance(observation, Mapping) or not isinstance(legal_actions, Sequence) or isinstance(legal_actions, (str, bytes)):
        return _unavailable()
    facts = summarize_candidate_structures(observation, legal_actions)
    if facts is None:
        return _unavailable()
    domains = {"overall_priority"}
    objectives: set[str] = set()
    checks = {"check_public_urgency", "check_structure_loss", "check_control_cost"}
    is_free = bool(facts and facts[0].is_free_lead)
    if is_free:
        domains.add("opening_free_lead"); objectives.add("low_cost_probe")
    else:
        domains.add("follow_control"); objectives.add("contest_follow"); checks.add("check_rule_pressure")
    if any(fact.fragments_played_rank_group for fact in facts):
        domains.add("hand_structure"); objectives.add("protect_structure")
    if any(fact.consumes_control_resource for fact in facts):
        domains.add("control_return_resource"); objectives.add("preserve_control")
    if any(fact.uses_wildcard or fact.bomb_length is not None for fact in facts):
        domains.add("bomb_wildcard_management"); objectives.add("manage_bomb_wildcard")
    hand_count = observation.get("my_info", {}).get("hand_count") if isinstance(observation.get("my_info"), Mapping) else None
    if any(fact.finishes_hand for fact in facts) or (type(hand_count) is int and 0 < hand_count <= 4):
        domains.add("endgame_planning"); objectives.add("plan_endgame")
    intent = getattr(strategy_context, "intent", None)
    if intent == "support_teammate" or any(fact.teammate_hand_count is not None and fact.teammate_hand_count <= 2 for fact in facts):
        domains.add("teammate_coordination"); objectives.add("support_teammate")
    if intent == "block_opponent" or any(fact.minimum_opponent_hand_count is not None and fact.minimum_opponent_hand_count <= 2 for fact in facts):
        domains.add("danger_opponent_block"); objectives.add("block_opponent")
    if is_free and any(fact.natural_single_rank_value is not None for fact in facts):
        domains.add("uncertainty_probe")

    finishers = sorted((fact for fact in facts if fact.finishes_hand), key=lambda fact: fact.action_id)
    safe_singles = sorted(
        (fact for fact in facts if is_free and fact.pattern == "single" and not fact.uses_wildcard
         and not fact.fragments_played_rank_group and not fact.consumes_control_resource
         and fact.natural_single_rank_value is not None),
        key=lambda fact: (fact.natural_single_rank_value or 99, fact.action_id),
    )
    pairs = sorted(
        (fact for fact in facts if is_free and fact.pattern == "pair" and not fact.fragments_played_rank_group),
        key=lambda fact: (fact.residual_singleton_rank_count, fact.action_id),
    )
    selected: list[int] = []
    for fact in finishers + safe_singles + pairs:
        if fact.action_id not in selected:
            selected.append(fact.action_id)
        if len(selected) == 3:
            break
    if finishers:
        objectives.add("finish_now")
    return StrategyRecommendation(
        "ready", _SOURCE, tuple(selected), _ordered(objectives, OBJECTIVE_CODES),
        _ordered(checks, COUNTERCHECK_CODES), _ordered(domains, STRATEGY_DOMAINS),
    )
