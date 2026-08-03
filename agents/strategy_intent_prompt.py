"""Fail-closed serialization for public strategy-intent context."""

from __future__ import annotations

from dataclasses import dataclass

from agents.strategy_router import StrategyIntentContext


_SOURCE = "strategy_intent_prompt_v1"
_ROUTER_SOURCE = "public_strategy_router_v1"
_PHASES = ("midgame", "endgame", "near_open_endgame", "critical_endgame")
_INTENT_TEXT = {
    "run_out": "加速走牌",
    "block_opponent": "阻断对手",
    "support_teammate": "支援队友",
    "control": "控制牌权",
}
_REASON_DETAILS = {
    "can_finish_now": ("run_out", "本次可直接出完"),
    "weak_hand": ("run_out", "手牌偏弱，优先减少手数"),
    "stable_control": ("control", "手牌控制力稳定"),
    "teammate_controls_table": ("support_teammate", "队友当前控桌"),
    "urgent_opponent_controls_table": ("block_opponent", "紧急对手当前控桌"),
    "teammate_more_urgent": ("support_teammate", "队友跑牌更紧迫"),
    "opponent_more_urgent": ("block_opponent", "对手威胁更紧迫"),
    "urgency_tie_block_opponent": ("block_opponent", "双方同样紧迫，优先阻断对手"),
    "opponent_urgent": ("block_opponent", "对手接近出完"),
    "teammate_urgent": ("support_teammate", "队友接近出完"),
}
_TEAM_BY_PLAYER = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}
_TEAMMATE_BY_PLAYER = {1: 3, 2: 4, 3: 1, 4: 2}
_DIAGNOSTIC_ORDER = (
    "invalid_context_type",
    "context_unavailable",
    "invalid_router_source",
    "invalid_phase",
    "invalid_intent_reason",
    "invalid_context_fields",
    "prompt_budget_exceeded",
)


@dataclass(frozen=True, slots=True)
class StrategyIntentPromptPayload:
    """A bounded prompt fragment derived from a validated intent context."""

    status: str
    source: str
    router_source: str | None
    phase: str | None
    intent: str | None
    text: str
    char_count: int
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source": self.source,
            "router_source": self.router_source,
            "phase": self.phase,
            "intent": self.intent,
            "text": self.text,
            "char_count": self.char_count,
            "diagnostics": list(self.diagnostics),
        }


def _is_int(value: object, *, minimum: int, maximum: int | None = None) -> bool:
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def _ordered_diagnostics(codes: set[str]) -> tuple[str, ...]:
    return tuple(code for code in _DIAGNOSTIC_ORDER if code in codes)


def _omitted(codes: set[str]) -> StrategyIntentPromptPayload:
    ordered = _ordered_diagnostics(codes)
    if not ordered:
        ordered = ("invalid_context_fields",)
    return StrategyIntentPromptPayload(
        status="omitted",
        source=_SOURCE,
        router_source=None,
        phase=None,
        intent=None,
        text="",
        char_count=0,
        diagnostics=ordered,
    )


def _valid_player_fields(context: StrategyIntentContext) -> bool:
    my_player = context.my_player_id
    teammate = context.teammate_player_id
    if not _is_int(my_player, minimum=1, maximum=4):
        return False
    if not _is_int(teammate, minimum=1, maximum=4):
        return False
    if teammate != _TEAMMATE_BY_PLAYER[my_player]:
        return False
    if type(context.my_team) is not str or context.my_team != _TEAM_BY_PLAYER[my_player]:
        return False
    if context.my_hand_count is None or not _is_int(context.my_hand_count, minimum=1):
        return False
    if context.teammate_hand_count is None or not _is_int(
        context.teammate_hand_count, minimum=0
    ):
        return False
    if context.minimum_opponent_hand_count is not None and not _is_int(
        context.minimum_opponent_hand_count, minimum=1
    ):
        return False
    if type(context.urgent_opponent_ids) is not tuple:
        return False
    opponents = {player_id for player_id in _TEAM_BY_PLAYER if player_id not in {my_player, teammate}}
    seen_opponents: set[int] = set()
    for player_id in context.urgent_opponent_ids:
        if not _is_int(player_id, minimum=1, maximum=4) or player_id not in opponents:
            return False
        if player_id in seen_opponents:
            return False
        seen_opponents.add(player_id)
    minimum = context.minimum_opponent_hand_count
    if minimum is None:
        if context.urgent_opponent_ids:
            return False
    elif minimum <= 2:
        if not context.urgent_opponent_ids:
            return False
    elif context.urgent_opponent_ids:
        return False
    if not _is_int(context.hand_total_score, minimum=0, maximum=100):
        return False
    if not _is_int(context.hand_control_score, minimum=0, maximum=30):
        return False
    if context.hand_control_score > context.hand_total_score:
        return False
    expected_strength = "weak" if context.hand_total_score < 40 else "non_weak"
    return context.hand_strength == expected_strength


def _valid_table_fields(context: StrategyIntentContext) -> bool:
    relation = context.table_leader_relation
    leader = context.table_leader_player_id
    if relation is not None and (type(relation) is not str or relation not in ("teammate", "opponent")):
        return False
    if relation is None:
        if leader is not None or context.table_leader_is_urgent is not False:
            return False
        return context.is_free_lead is True
    if context.is_free_lead is not False or not _is_int(leader, minimum=1, maximum=4):
        return False
    if relation == "teammate":
        if leader != context.teammate_player_id:
            return False
        return context.table_leader_is_urgent is (
            context.teammate_hand_count is not None and 0 < context.teammate_hand_count <= 2
        )
    if leader in {context.my_player_id, context.teammate_player_id}:
        return False
    minimum = context.minimum_opponent_hand_count
    if leader in context.urgent_opponent_ids and context.table_leader_is_urgent is not True:
        return False
    if context.table_leader_is_urgent is True and (minimum is None or minimum > 2):
        return False
    if (minimum is None or minimum > 2) and context.table_leader_is_urgent is not False:
        return False
    return True


def _expected_reason(context: StrategyIntentContext) -> str:
    """Apply the router's fixed priority using only validated context fields."""

    if context.can_finish_now:
        return "can_finish_now"
    if context.table_leader_relation == "teammate":
        return "teammate_controls_table"
    if (
        context.table_leader_relation == "opponent"
        and context.table_leader_is_urgent
    ):
        return "urgent_opponent_controls_table"
    teammate_is_urgent = 0 < context.teammate_hand_count <= 2
    has_urgent_opponent = bool(context.urgent_opponent_ids)
    if teammate_is_urgent and has_urgent_opponent:
        if context.teammate_hand_count < context.minimum_opponent_hand_count:
            return "teammate_more_urgent"
        if context.teammate_hand_count > context.minimum_opponent_hand_count:
            return "opponent_more_urgent"
        return "urgency_tie_block_opponent"
    if has_urgent_opponent:
        return "opponent_urgent"
    if teammate_is_urgent:
        return "teammate_urgent"
    if context.hand_strength == "weak":
        return "weak_hand"
    return "stable_control"


def build_strategy_intent_prompt_payload(
    context: StrategyIntentContext,
    *,
    max_chars: int = 800,
) -> StrategyIntentPromptPayload:
    """Build one fixed, bounded prompt fragment or omit it entirely."""

    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive non-bool integer")
    if type(context) is not StrategyIntentContext:
        return _omitted({"invalid_context_type"})

    diagnostics: set[str] = set()
    if context.status != "available":
        diagnostics.add("context_unavailable")
    if context.source != _ROUTER_SOURCE:
        diagnostics.add("invalid_router_source")
    if type(context.phase) is not str or context.phase not in _PHASES:
        diagnostics.add("invalid_phase")
    if type(context.diagnostics) is not tuple or context.diagnostics != ():
        diagnostics.add("invalid_context_fields")
    if type(context.reason_codes) is not tuple or len(context.reason_codes) != 1:
        diagnostics.add("invalid_intent_reason")
        reason: str | None = None
    else:
        reason = context.reason_codes[0]
        if type(reason) is not str or not reason or reason not in _REASON_DETAILS:
            diagnostics.add("invalid_intent_reason")
    if type(context.intent) is not str or context.intent not in _INTENT_TEXT:
        diagnostics.add("invalid_intent_reason")
    elif type(reason) is str and reason in _REASON_DETAILS and _REASON_DETAILS[reason][0] != context.intent:
        diagnostics.add("invalid_intent_reason")

    if (
        type(context.can_finish_now) is not bool
        or type(context.is_free_lead) is not bool
        or type(context.table_leader_is_urgent) is not bool
        or not _valid_player_fields(context)
        or not _valid_table_fields(context)
    ):
        diagnostics.add("invalid_context_fields")
    if not diagnostics and type(reason) is str:
        expected_reason = _expected_reason(context)
        if reason != expected_reason:
            diagnostics.add("invalid_intent_reason")
    if diagnostics:
        return _omitted(diagnostics)

    assert reason is not None
    _, reason_text = _REASON_DETAILS[reason]
    text = "\n".join(
        (
            f"范围：{context.phase}",
            f"策略意图：{_INTENT_TEXT[context.intent]}",
            f"公开依据：{reason_text}",
            "边界：这是公开局面下的策略偏好，不是隐藏牌事实或合法性结论；只能从候选动作中选择。",
        )
    )
    if len(text) > max_chars:
        return _omitted({"prompt_budget_exceeded"})
    return StrategyIntentPromptPayload(
        status="ready",
        source=_SOURCE,
        router_source=_ROUTER_SOURCE,
        phase=context.phase,
        intent=context.intent,
        text=text,
        char_count=len(text),
        diagnostics=(),
    )
