"""Model-before, public-only strategy recommendations.

This module intentionally produces a short list rather than an action.  The
DeepSeek response remains the sole strategy selection whenever a local opening
shortcut has not already met its deliberately narrow gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from agents.action_structure import CandidateStructure, summarize_candidate_structures


_SOURCE = "public_strategy_recommendation_v1"
_MAX_IDS = 3


@dataclass(frozen=True, slots=True)
class StrategyRecommendation:
    status: str
    source: str
    action_ids: tuple[int, ...]
    reasons: tuple[str, ...]
    counterchecks: tuple[str, ...]
    strategy_domains: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source": self.source,
            "action_ids": list(self.action_ids),
            "reasons": list(self.reasons),
            "counterchecks": list(self.counterchecks),
            "strategy_domains": list(self.strategy_domains),
        }


def _unavailable() -> StrategyRecommendation:
    return StrategyRecommendation("unavailable", _SOURCE, (), (), (), ())


def build_strategy_recommendation(
    observation: object,
    legal_actions: object,
    *,
    strategy_context: object = None,
) -> StrategyRecommendation:
    """Suggest inspect-first canonical IDs without filtering their action space."""
    if not isinstance(observation, Mapping) or not isinstance(legal_actions, Sequence) or isinstance(legal_actions, (str, bytes)):
        return _unavailable()
    facts = summarize_candidate_structures(observation, legal_actions)
    if facts is None:
        return _unavailable()
    ids = {fact.action_id for fact in facts}
    # Stable, public preference for a structurally safe natural low single.
    safe_singles = [
        fact for fact in facts
        if fact.is_free_lead and fact.pattern == "single" and not fact.uses_wildcard
        and not fact.fragments_played_rank_group and not fact.consumes_control_resource
        and fact.natural_single_rank_value is not None
    ]
    safe_singles.sort(key=lambda fact: (fact.natural_single_rank_value or 99, fact.action_id))
    pairs = [
        fact for fact in facts
        if fact.is_free_lead and fact.pattern == "pair" and not fact.fragments_played_rank_group
    ]
    pairs.sort(key=lambda fact: (fact.residual_singleton_rank_count, fact.action_id))
    finishers = [fact for fact in facts if fact.finishes_hand]
    finishers.sort(key=lambda fact: fact.action_id)

    selected: list[int] = []
    for fact in finishers + safe_singles + pairs:
        if fact.action_id not in selected:
            selected.append(fact.action_id)
        if len(selected) == _MAX_IDS:
            break
    if not selected:
        return _unavailable()
    if any(action_id not in ids for action_id in selected):
        return _unavailable()

    domains = ["overall_priority", "hand_structure", "uncertainty_probe"]
    reasons: list[str] = []
    if finishers:
        reasons.append("存在一次出完候选，应先核对其是否直接结束本家手牌。")
        domains.append("endgame_planning")
    if safe_singles:
        reasons.append("自然低单张不拆同点组合且不消耗明确控制资源，可作为低成本试探/清理候选。")
        domains.extend(["opening_free_lead", "control_return_resource"])
    if pairs:
        reasons.append("自然对子可一次处理两张；与单张相比请核对残余孤张和后续组合损失。")
    context_intent = getattr(strategy_context, "intent", None)
    if context_intent == "support_teammate":
        domains.append("teammate_coordination")
    elif context_intent == "block_opponent":
        domains.append("danger_opponent_block")
    counterchecks = (
        "请检查队友/对手公开剩余张数、当前牌权与紧急性是否推翻该比较。",
        "请检查是否破坏连续牌型、炸弹、通配牌或回手资源；这些事实不能由建议替代。",
    )
    return StrategyRecommendation(
        "ready", _SOURCE, tuple(selected), tuple(reasons[:3]), counterchecks,
        tuple(dict.fromkeys(domains)),
    )
