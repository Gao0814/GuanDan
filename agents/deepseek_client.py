"""Minimal DeepSeek client for legal-action selection support.

Step D boundary:
- This client must NOT depend on engine internal state objects.
- It only consumes the public payloads returned by `observe()` and `legal_actions()`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import json
import re
import time
from typing import TYPE_CHECKING, Callable, Protocol
from urllib import request as urllib_request

from decision_deadline import (
    DecisionDeadline,
    DecisionDeadlineExceeded,
    MODEL_RESPONSE_RESERVE_SECONDS,
)
from agents.action_structure import (
    CANDIDATE_RELATION_KINDS,
    CandidateContrast,
    CandidateStructure,
    FreeLeadResidualStructure,
    candidate_response_net_effect,
    representative_candidate_contrasts,
    select_candidate_structure_representatives,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
    summarize_free_lead_residual_structures,
)
from agents.game_phase import GamePhaseContext, classify_game_phase, is_endgame_phase
from agents.opening_strategy import MAX_OPENING_FORMULA_CONTRASTS
from agents.short_endgame_planner import (
    analyze_free_lead_grouping,
    free_lead_grouping_comparison_pairs,
)

if TYPE_CHECKING:
    from agents.card_confidence_prompt import CardConfidencePromptPayload
    from agents.strategy_intent_prompt import StrategyIntentPromptPayload
    from agents.strategy_recommendation import StrategyRecommendation


_STRATEGY_INTENT_PROMPT_SOURCE = "strategy_intent_prompt_v1"
_STRATEGY_INTENT_ROUTER_SOURCE = "public_strategy_router_v1"
_STRATEGY_INTENT_PHASES = ("opening", "midgame", "endgame", "near_open_endgame", "critical_endgame")
_STRATEGY_INTENT_TEXT = {
    "run_out": "加速走牌",
    "block_opponent": "阻断对手",
    "support_teammate": "支援队友",
    "control": "控制牌权",
}
_STRATEGY_INTENT_REASON_TEXTS = {
    "run_out": (
        "本次可直接出完",
        "手牌偏弱，优先减少手数",
        "本家仅1–4张且当前自由出牌，完整canonical动作证明不同首手会导致不同的最少剩余分组数；优先选择使全部手牌所需分组数最少的首手，避免无谓拆散已有组合",
        "本家仅5–8张且当前自由出牌，完整canonical动作证明不同首手的余手存在不同最少后续分组数；仅描述假设以后重新取得自由领牌时的手牌结构，不保证取得牌权或必然走完",
    ),
    "block_opponent": (
        "紧急对手当前控桌",
        "对手威胁更紧迫",
        "双方同样紧迫，优先阻断对手",
        "对手接近出完",
    ),
    "support_teammate": (
        "队友当前控桌",
        "队友已用小王控桌，pass合法；大王不能直接出完且无紧急阻断对手的公开需要。优先考虑让队友保持牌权并保留大王这一高价值控制资源",
        "队友跑牌更紧迫",
        "队友接近出完",
    ),
    "control": ("手牌控制力稳定",),
}
_STRATEGY_INTENT_BOUNDARY = "边界：这是公开局面下的策略偏好，不是隐藏牌事实或合法性结论；只能从候选动作中选择。"

_SUIT_DISPLAY: dict[str, str] = {"S": "♠", "H": "♥", "C": "♣", "D": "♦"}

_PATTERN_FULL: dict[str, str] = {
    "pass": "pass",
    "single": "单张",
    "pair": "对子",
    "triple": "三张",
    "triple_with_pair": "三带二",
    "straight": "顺子",
    "pair_straight": "连对",
    "steel_plate": "钢板",
    "straight_flush": "同花顺",
    "bomb": "炸弹",
    "joker_bomb": "天王炸",
}

_FINISH_LABELS: dict[int, str] = {1: "头游", 2: "二游", 3: "三游", 4: "末游"}

_RANK_ORDER: dict[str, int] = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15, "SJ": 16, "BJ": 17,
}
_PRESSURE_PATTERNS = {"bomb", "straight_flush", "joker_bomb"}
_RESIDUAL_USE_RELATION_KINDS = frozenset(
    {
        "natural_pair_single", "natural_group_single", "natural_sequence_single", "sequence_structure_loss",
        "triple_split_repartition", "straight_flush_bomb_fragment", "straight_strength",
        "steel_plate_strength", "triple_pair_kicker_gradient", "natural_single_cost",
        "single_control_resource", "wildcard_resource", "bomb_strength_resource",
        "bomb_residual", "triple_bomb_split", "bomb_wildcard_strength",
        "opponent_single_control_cost",
        "follow_response_net_tradeoff",
    }
)

# Prompt limits are deliberately centralized so context growth stays auditable.
PROMPT_MAX_CANDIDATE_ACTIONS = 80
MAX_OPENING_PATTERN_REPRESENTATIVES = 20
MAX_OPENING_ACTIONS_PER_PATTERN_FAMILY = 8
MAX_PROMPT_RELATION_PAIRS = 24
MAX_PROMPT_RELATIONS_PER_KIND = 2
MAX_PROMPT_RELATION_EXTRA_ACTIONS = 36
_OPENING_PATTERN_ORDER = (
    "single",
    "pair",
    "triple",
    "straight",
    "triple_with_pair",
    "pair_straight",
    "steel_plate",
    "bomb",
    "straight_flush",
    "joker_bomb",
)
_PROMPT_RELATION_KIND_ORDER = (
    "danger_block_resource", "danger_block_choice",
    "teammate_control_resource", "teammate_table_choice",
    "follow_response_net_tradeoff",
    "opponent_single_control_cost",
    "triple_bomb_split", "bomb_wildcard_strength",
    "bomb_residual", "bomb_strength_resource", "straight_flush_bomb_fragment",
    "wildcard_resource", "triple_split_repartition", "sequence_structure_loss",
    "triple_pair_kicker_gradient", "natural_pair_single", "natural_group_single",
    "natural_sequence_single", "straight_strength", "steel_plate_strength",
    "natural_single_cost", "single_control_resource",
)
_PROMPT_RELATION_SOURCE_IDS = {
    "natural_single_cost": frozenset({"exp_soft_single_cost_probe_001", "exp_lead_opening_strong_001"}),
    "single_control_resource": frozenset({"exp_lead_opening_strong_001", "exp_midgame_control_001"}),
    "natural_pair_single": frozenset({"exp_soft_pair_probe_001", "exp_lead_opening_medium_001", "exp_lead_opening_shape_001"}),
    "natural_group_single": frozenset({"exp_soft_pair_probe_001", "exp_lead_opening_medium_001", "exp_lead_opening_shape_001"}),
    "natural_sequence_single": frozenset({"exp_lead_opening_shape_001", "exp_lead_opening_weak_001"}),
    "sequence_structure_loss": frozenset({"exp_lead_opening_shape_001", "exp_lead_opening_weak_001"}),
    "straight_strength": frozenset({"exp_lead_opening_shape_001", "exp_soft_straight_strength_001"}),
    "steel_plate_strength": frozenset({"exp_lead_opening_shape_001", "exp_soft_steel_plate_strength_001"}),
    "triple_split_repartition": frozenset({"exp_soft_triple_repartition_001"}),
    "triple_pair_kicker_gradient": frozenset({"exp_soft_triple_pair_gradient_001"}),
    "straight_flush_bomb_fragment": frozenset({"exp_soft_straight_flush_bomb_cost_001", "exp_bomb_wildcard_001"}),
    "bomb_residual": frozenset({"exp_bomb_wildcard_001"}),
    "bomb_strength_resource": frozenset({"exp_bomb_wildcard_001", "exp_midgame_control_001"}),
    "triple_bomb_split": frozenset({"exp_bomb_wildcard_001"}),
    "bomb_wildcard_strength": frozenset({"exp_bomb_wildcard_001"}),
    "wildcard_resource": frozenset({"exp_bomb_wildcard_001"}),
    "teammate_control_resource": frozenset({"exp_midgame_teammate_001"}),
    "teammate_table_choice": frozenset({"exp_midgame_teammate_001"}),
    "danger_block_resource": frozenset({"exp_midgame_block_001"}),
    "danger_block_choice": frozenset({"exp_midgame_block_001"}),
    "opponent_single_control_cost": frozenset({"exp_midgame_control_001"}),
    # The general pass/response comparison is derived from public actions;
    # no experience source is required to establish it.
    "follow_response_net_tradeoff": frozenset(),
}
PROMPT_MAX_ACTION_DISPLAY_CHARS = 96
PROMPT_MAX_ACTION_CARRIER_CHARS = 160
PROMPT_MAX_WILDCARD_INFO_CHARS = 160
PROMPT_MAX_RAG_HITS_PER_LAYER = 3
PROMPT_MAX_RAG_TITLE_CHARS = 60
PROMPT_MAX_RAG_BODY_CHARS = 180
PROMPT_MAX_CARD_TRACKING_CHARS = 1_400
PROMPT_MAX_PUBLIC_ENDGAME_CHARS = 720

_SCENE_TAG_ORDER = (
    "scene",
    "phase",
    "hand_strength",
    "action_context",
    "has_bomb",
    "has_wildcard",
    "has_joker_control",
    "can_play_out_all",
    "can_bomb_response",
    "wildcard_action_present",
    "strategy_intent",
    "strategy_domains",
    "candidate_relation_kinds",
)


def _rank_of(token: str) -> str:
    """Extract rank from a card token, stripping suit if present."""
    if token in {"SJ", "BJ"}:
        return token
    if len(token) >= 2 and token[-1] in _SUIT_DISPLAY:
        return token[:-1]
    return token


def _card_for_ai(token: str, current_level_rank: str, is_flush_context: bool) -> str:
    """Convert a card token into the compact AI-facing display form."""
    if token == "SJ":
        return "小王"
    if token == "BJ":
        return "大王"

    rank = token[:-1] if len(token) >= 2 and token[-1] in _SUIT_DISPLAY else token
    suit = token[-1] if len(token) >= 2 and token[-1] in _SUIT_DISPLAY else None

    if suit == "H" and rank == current_level_rank:
        return f"♥{rank}(逢人配)"
    if is_flush_context and suit is not None:
        return f"{_SUIT_DISPLAY[suit]}{rank}"
    return rank


def _cards_for_ai(
    tokens: list[str],
    current_level_rank: str,
    *,
    is_flush_context: bool = False,
    separator: str = "",
) -> str:
    return separator.join(
        _card_for_ai(token, current_level_rank, is_flush_context) for token in tokens
    )


@dataclass(slots=True)
class DeepSeekSuggestion:
    """Result from DeepSeek API: action_id and optional reasoning trace."""

    action_id: int | None
    reasoning: str | None


class DeepSeekTransport(Protocol):
    """Transport protocol for dependency-injected HTTP calls in tests."""

    def __call__(
        self,
        request: urllib_request.Request,
        timeout: float,
    ) -> str | bytes | Iterable[str | bytes]:
        ...


def _default_transport(
    req: urllib_request.Request,
    timeout: float,
    *,
    decision_deadline: DecisionDeadline | None = None,
) -> Iterator[bytes]:
    """Yield SSE lines and release the response as soon as its terminal event arrives."""

    effective_timeout = timeout
    if decision_deadline is not None:
        decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
        effective_timeout = min(
            effective_timeout,
            decision_deadline.remaining(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS),
        )
    with urllib_request.urlopen(req, timeout=effective_timeout) as response:
        unregister = (
            decision_deadline.register_cancel_callback(response.close)
            if decision_deadline is not None
            else lambda: None
        )
        try:
            while True:
                if decision_deadline is not None:
                    decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
                    socket_timeout = min(
                        timeout,
                        decision_deadline.remaining(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS),
                    )
                    response_file = getattr(response, "fp", None)
                    raw = getattr(response_file, "raw", None)
                    sock = getattr(raw, "_sock", None)
                    settimeout = getattr(sock, "settimeout", None)
                    if not callable(settimeout):
                        raise DecisionDeadlineExceeded("decision_deadline_socket_unavailable")
                    settimeout(socket_timeout)
                line = response.readline()
                if decision_deadline is not None:
                    decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
                if not line:
                    return
                yield line
                if line.strip() == b"data: [DONE]":
                    return
        finally:
            unregister()


class DeepSeekClient:
    """Minimal one-shot client for DeepSeek chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        transport: DeepSeekTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("deepseek api key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._transport: DeepSeekTransport = transport or _default_transport

    @staticmethod
    def _coerce_int(value: object, default: int = 0) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_json(content: str) -> object | None:
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_action_id(payload: object) -> int | None:
        if isinstance(payload, int):
            return payload
        if isinstance(payload, str):
            try:
                return int(payload)
            except ValueError:
                return None
        if not isinstance(payload, dict):
            return None

        direct_keys = ("action_id", "suggested_action_id")
        for key in direct_keys:
            if key in payload:
                value = payload.get(key)
                try:
                    return int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None

        suggested = payload.get("suggested_action")
        if isinstance(suggested, dict) and "action_id" in suggested:
            try:
                return int(suggested.get("action_id"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        return None

    @staticmethod
    def _match_action_id_by_signature(
        payload: object,
        legal_actions: list[dict[str, object]],
    ) -> int | None:
        if not isinstance(payload, dict):
            return None

        candidate: object = payload.get("suggested_action", payload)
        if not isinstance(candidate, dict):
            return None

        declared_pattern = candidate.get("declared_pattern")
        declared_cards = candidate.get("declared_cards")
        if declared_pattern is None or declared_cards is None:
            return None

        try:
            declared_cards_tuple = tuple(str(token) for token in declared_cards)  # type: ignore[arg-type]
        except TypeError:
            return None

        matches: list[int] = []
        for action in legal_actions:
            if str(action.get("declared_pattern")) != str(declared_pattern):
                continue
            if tuple(str(token) for token in action.get("declared_cards", [])) != declared_cards_tuple:
                continue
            try:
                matches.append(int(action["action_id"]))
            except (KeyError, TypeError, ValueError):
                continue

        if not matches:
            return None
        return sorted(matches)[0]

    @staticmethod
    def _action_sort_key(action: dict[str, object]) -> int:
        declared = [str(t) for t in action.get("declared_cards", [])]
        if not declared:
            return 0
        return _RANK_ORDER.get(_rank_of(declared[0]), 0)

    @staticmethod
    def _phase_from_round(step_no: int, hand_count: int | None) -> str:
        """Adapt legacy pruning arguments through the unified classifier.

        Normal callers provide ``GamePhaseContext``.  This preserves the
        historical static helper for callers that only have these two public
        fields, without reintroducing phase thresholds in the pruning module.
        """
        return classify_game_phase(
            {
                "my_info": {"hand_count": hand_count if hand_count is not None else 27},
                "current_round": {"step_no": step_no},
                "other_players": [
                    {"hand_count": 27, "finished": False},
                    {"hand_count": 27, "finished": False},
                    {"hand_count": 27, "finished": False},
                ],
                "history": {"actions": [], "finish_order": []},
            }
        ).phase

    @staticmethod
    def _tactic_group(pattern: str) -> str:
        if pattern in {"steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"}:
            return "run"
        if pattern in {"bomb", "straight_flush", "joker_bomb"}:
            return "pressure"
        return "transition"

    @staticmethod
    def _rank_range_text(ranks: list[str]) -> str:
        if not ranks:
            return ""
        unique = sorted(set(ranks), key=lambda rank: _RANK_ORDER.get(rank, 0))
        if not unique:
            return ""
        if len(unique) == 1:
            return unique[0]
        return f"{unique[0]}~{unique[-1]}"

    @staticmethod
    def _rank_repeat_text(rank: str, count: int) -> str:
        if not rank or count <= 0:
            return ""
        if rank in {"10", "J", "Q", "K", "A", "2"}:
            return rank * count
        return f"{rank}×{count}"

    @staticmethod
    def _action_brief_cn(action: dict[str, object]) -> str:
        pattern = str(action.get("declared_pattern", ""))
        if pattern == "pass":
            return "pass"

        declared = [str(token) for token in action.get("declared_cards", [])]
        ranks = [_rank_of(token) for token in declared]

        if pattern == "single":
            return f"单{ranks[0]}" if ranks else "单"
        if pattern == "pair":
            return f"对{ranks[0]}" if ranks else "对"
        if pattern == "triple":
            return f"三{ranks[0]}" if ranks else "三"
        if pattern == "triple_with_pair":
            counts = Counter(ranks)
            triple_rank = next((rank for rank, count in sorted(counts.items(), key=lambda item: _RANK_ORDER.get(item[0], 0), reverse=True) if count == 3), "")
            pair_rank = next((rank for rank, count in sorted(counts.items(), key=lambda item: _RANK_ORDER.get(item[0], 0), reverse=True) if count == 2), "")
            if triple_rank and pair_rank:
                return f"三带二({DeepSeekClient._rank_repeat_text(triple_rank, 3)}+{DeepSeekClient._rank_repeat_text(pair_rank, 2)})"
            return "三带二"
        if pattern in {"straight", "pair_straight", "steel_plate", "straight_flush"}:
            label = {
                "straight": "顺子",
                "pair_straight": "连对",
                "steel_plate": "钢板",
                "straight_flush": "同花顺",
            }.get(pattern, pattern)
            range_text = DeepSeekClient._rank_range_text(ranks)
            return f"{label}({range_text})" if range_text else label
        if pattern == "bomb":
            main_rank = _rank_of(declared[0]) if declared else ""
            return f"{len(declared)}炸{main_rank}"
        if pattern == "joker_bomb":
            return "天王炸"
        return pattern

    @staticmethod
    def _action_summary_entry(
        action: dict[str, object],
        current_level_rank: str,
        residual_structure: FreeLeadResidualStructure | None = None,
        *,
        compact_opening: bool = False,
    ) -> str:
        action_id = action.get("action_id")
        pattern = str(action.get("declared_pattern", ""))
        wildcard_count = DeepSeekClient._coerce_int(action.get("wildcard_count"), default=0)
        carrier_text = DeepSeekClient._bounded_text(
            DeepSeekClient._compact_json(action.get("carrier_cards", [])),
            PROMPT_MAX_ACTION_CARRIER_CHARS,
        )
        action_id_text = DeepSeekClient._compact_json(action_id)
        if compact_opening:
            # Opening candidates are already printed in canonical order. The
            # engine display repeats the carrier and pattern, so keep the
            # structured fields and omit that duplicate prose. A wildcard
            # declaration is retained explicitly because its declared cards
            # need not match its physical carriers.
            fields = [
                f"action_id={action_id_text}",
                f"pattern={pattern}",
                f"carrier_cards={carrier_text}",
            ]
            if wildcard_count:
                fields.append(
                    "declared_cards="
                    + DeepSeekClient._bounded_text(
                        DeepSeekClient._compact_json(action.get("declared_cards", [])),
                        PROMPT_MAX_ACTION_CARRIER_CHARS,
                    )
                )
            fields.append(f"wildcard_count={wildcard_count}")
        else:
            brief = DeepSeekClient._compact_action_text(
                action,
                current_level_rank,
                pattern == "straight_flush",
            )
            display_text = DeepSeekClient._bounded_text(
                str(action.get("display_text", brief)),
                PROMPT_MAX_ACTION_DISPLAY_CHARS,
            )
            fields = [
                f"action_id={action_id_text}",
                f"display={display_text}",
                f"declared_pattern={pattern}",
                f"carrier_cards={carrier_text}",
                f"wildcard_count={wildcard_count}",
            ]
        wildcard_info = action.get("wildcard_info", [])
        if wildcard_info:
            fields.append(
                "wildcard_info="
                + DeepSeekClient._bounded_text(
                    DeepSeekClient._compact_json(wildcard_info),
                    PROMPT_MAX_WILDCARD_INFO_CHARS,
                )
            )
        if residual_structure is not None:
            if compact_opening:
                fields.append(
                    "after=clear_groups:"
                    f"{str(residual_structure.clears_played_rank_groups).lower()},"
                    f"singletons:{residual_structure.residual_singleton_rank_count},"
                    f"groups_est:{residual_structure.estimated_remaining_rank_groups}"
                )
            else:
                clears = "是" if residual_structure.clears_played_rank_groups else "否"
                fields.append(
                    "残余结构="
                    f"清空所出点数组:{clears},"
                    f"残余孤张点数:{residual_structure.residual_singleton_rank_count},"
                    f"估计剩余点数组:{residual_structure.estimated_remaining_rank_groups}"
                )
        prefix = f"#{action_id} " if action_id is not None else ""
        return prefix + " | ".join(fields)

    @staticmethod
    def _format_residual_use(fact: CandidateStructure | None) -> str:
        """Describe only current, potentially overlapping natural-use cues."""
        if fact is None or fact.residual_rank_uses is None or fact.residual_hand_natural_pattern_kinds is None:
            return "未知（通配/声明或公开结构信息不足）"
        pattern_labels = {
            "pair": "对子",
            "triple": "三张",
            "bomb": "自然炸弹",
            "triple_with_pair": "三带二",
            "straight": "顺子点数结构",
            "pair_straight": "连对点数结构",
            "steel_plate": "钢板点数结构",
        }
        rank_parts: list[str] = []
        for item in fact.residual_rank_uses:
            if item.remaining_count == 0 and item.wildcard_count == 0:
                rank_parts.append(f"{item.rank}点清空")
                continue
            uses = "、".join(pattern_labels[kind] for kind in item.natural_pattern_kinds)
            natural_part = (
                f"{item.rank}点余{item.remaining_count}张自然牌"
                + (f"可组成{uses}" if uses else "未识别同点组合")
            )
            if item.wildcard_count:
                natural_part += f"；另留通配{item.wildcard_count}张"
            rank_parts.append(natural_part)
        parts = [f"余手{fact.residual_card_count}张"] if fact.residual_card_count is not None else []
        if rank_parts:
            parts.append("所出点残留=" + "/".join(rank_parts))
        hand_uses = "、".join(
            pattern_labels[kind] for kind in fact.residual_hand_natural_pattern_kinds
        )
        if hand_uses:
            parts.append(f"余手结构线索={hand_uses}")
        parts.append(
            f"余组≈{fact.estimated_remaining_rank_groups}/孤张={fact.residual_singleton_rank_count}"
        )
        if fact.residual_natural_control_resource_count is not None:
            parts.append(f"自然控制牌候选={fact.residual_natural_control_resource_count}")
        return "；".join(parts)

    @staticmethod
    def _residual_use_contrast_text(
        first_id: int,
        second_id: int,
        candidate_facts: dict[int, CandidateStructure],
    ) -> str:
        first_fact = candidate_facts.get(first_id)
        second_fact = candidate_facts.get(second_id)
        if first_fact is None or second_fact is None:
            return (
                f"留牌事实：候选{first_id}/{second_id}的出后结构无法完整核实，具体用途未知。"
            )

        first = DeepSeekClient._format_residual_use(first_fact)
        second = DeepSeekClient._format_residual_use(second_fact)
        carrier_delta = abs(first_fact.carrier_count - second_fact.carrier_count)
        retained_id = (
            first_id if first_fact.carrier_count < second_fact.carrier_count
            else second_id if second_fact.carrier_count < first_fact.carrier_count
            else None
        )
        retained_text = (
            f"候选{retained_id}少出{carrier_delta}张、多留{carrier_delta}张实体牌；"
            if retained_id is not None and carrier_delta > 0
            else "两侧出牌张数相同；"
        )
        public_context: list[str] = []
        teammate_count = first_fact.teammate_hand_count
        if first_fact.teammate_active and teammate_count is not None and teammate_count <= 2:
            public_context.append(f"队友公开剩余{teammate_count}张")
        opponent_count = first_fact.minimum_opponent_hand_count
        if opponent_count is not None and opponent_count <= 2:
            public_context.append(f"对手公开最少剩余{opponent_count}张")
        context_text = f"公开局势={'/'.join(public_context)}；" if public_context else ""
        return (
            f"留牌事实：{retained_text}候选{first_id}[{first}]；候选{second_id}[{second}]。{context_text}"
        )

    @staticmethod
    def _follow_order_context(contrast: CandidateContrast) -> str:
        """Format only the validated public leader and next-seat facts."""
        parts: list[str] = []
        if contrast.table_leader_relation in {"teammate", "opponent"}:
            relation = "队友" if contrast.table_leader_relation == "teammate" else "对手"
            count_text = (
                f"公开余{contrast.table_leader_hand_count}张"
                if contrast.table_leader_hand_count is not None
                else "公开余牌数未知"
            )
            parts.append(f"当前桌面由{relation}领出（{count_text}）")
        if (
            contrast.next_active_player_id is not None
            and contrast.next_active_player_relation in {"teammate", "opponent"}
        ):
            relation = "队友" if contrast.next_active_player_relation == "teammate" else "对手"
            count_text = (
                f"公开余{contrast.next_active_player_hand_count}张"
                if contrast.next_active_player_hand_count is not None
                else "公开余牌数未知"
            )
            parts.append(
                f"本家出后座位顺序下一名仍在局玩家为玩家{contrast.next_active_player_id}（{relation}，{count_text}）"
            )
        if parts:
            return "行动顺序/当前压制：" + "；".join(parts) + "；下一席能否接牌及后续牌权仍未知。"
        return "行动顺序/当前压制的公开归属不足；不推断后续牌权。"

    @staticmethod
    def _response_net_tradeoff_text(
        contrast: CandidateContrast,
        candidate_facts_by_id: dict[int, CandidateStructure],
    ) -> str:
        """Render the public cost and immediate effect of one response/pass pair."""
        pass_fact = candidate_facts_by_id.get(contrast.action_ids[0])
        response_fact = candidate_facts_by_id.get(contrast.action_ids[1])
        if pass_fact is None or response_fact is None:
            return ""
        effect = candidate_response_net_effect(pass_fact, response_fact)
        if effect is None:
            return ""
        relation_label = (
            "队友控桌对照" if contrast.table_leader_relation == "teammate"
            else "危险对手对照"
            if contrast.table_leader_relation == "opponent"
            and contrast.table_leader_hand_count is not None
            and contrast.table_leader_hand_count <= 2
            else "应手/让牌对照"
        )
        response_name = _PATTERN_FULL.get(response_fact.pattern, "合法牌型")
        pass_count = pass_fact.residual_card_count
        retained = f"保留当前全部{pass_count}张手牌" if pass_count is not None else "不消耗手牌"
        costs: list[str] = []
        if effect.spends_control_resource:
            costs.append("消耗可识别的控制牌")
        if effect.uses_wildcard:
            costs.append("使用逢人配")
        if effect.fragments_rank_group:
            costs.append("拆动已识别同点组")
        if effect.singleton_rank_delta > 0:
            costs.append(f"余手孤张点数增加{effect.singleton_rank_delta}")
        elif effect.singleton_rank_delta < 0:
            costs.append(f"余手孤张点数减少{-effect.singleton_rank_delta}")
        if effect.lost_natural_uses:
            use_labels = {
                "pair": "对子", "triple": "三张", "bomb": "炸弹",
                "triple_with_pair": "三带二", "straight": "顺子",
                "pair_straight": "连对", "steel_plate": "钢板",
            }
            lost_labels = "、".join(
                use_labels.get(kind, "组牌") for kind in effect.lost_natural_uses
            )
            costs.append(f"出后不再保有部分当前可识别的{lost_labels}线索")
        if effect.rank_group_delta > 0:
            costs.append(f"余手点数类增加{effect.rank_group_delta}")
        elif effect.rank_group_delta < 0:
            costs.append(f"余手点数类减少{-effect.rank_group_delta}")
        if effect.control_resource_delta is not None and effect.control_resource_delta > 0 and not effect.spends_control_resource:
            costs.append(f"余手可识别控制资源减少{effect.control_resource_delta}")
        cost_text = "；".join(costs) if costs else "未显示上述控制牌或同点组损耗"
        finish_text = "并可立即出完" if effect.finishes_hand else ""
        teammate_route = (
            "当前领出为队友，pass保留其当前领出机会（若后续无人改写桌面）；"
            if contrast.table_leader_relation == "teammate"
            else ""
        )
        opponent_route = (
            "当前领出为对手，pass后由后续玩家继续应对；若无人再接，对手可能保持本轮领出优势；"
            if contrast.table_leader_relation == "opponent"
            else ""
        )
        urgency_route = (
            "公开紧迫对手或本家立即出完可能使当前应手收益高于保留资源；"
            if (
                contrast.table_leader_relation == "opponent"
                and contrast.table_leader_hand_count is not None
                and contrast.table_leader_hand_count <= 2
            ) or effect.finishes_hand
            else ""
        )
        return (
            f"{relation_label}：action_id={contrast.action_ids[0]} 为pass，{retained}且保留当前可识别余手结构，"
            f"但放弃本家这次应手；action_id={contrast.action_ids[1]} 是当前合法{response_name}应手，"
            f"即时以本家这手替换当前桌面并清理{effect.cards_played}张{finish_text}。可见代价：{cost_text}。"
            f"{teammate_route}{opponent_route}{urgency_route}pass不消耗这些资源，但其他行动者仍可能接牌；"
            "后续若有人要改写桌面，需出合法更强牌并消耗实体牌，是否持有未知；"
            "任何一侧都不保证最终控桌。"
        )

    @staticmethod
    def _compact_json(value: object) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _bounded_text(value: str, max_chars: int) -> str:
        compact = " ".join(value.split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max(0, max_chars - 1)].rstrip() + "…"

    @staticmethod
    def _unique_actions_by_brief(actions: list[dict[str, object]]) -> list[dict[str, object]]:
        return DeepSeekClient._unique_actions_by_signature(actions)

    @staticmethod
    def _action_signature(action: dict[str, object]) -> tuple[object, ...]:
        wildcard_info = action.get("wildcard_info", [])
        try:
            wildcard_info_text = json.dumps(wildcard_info, ensure_ascii=False, sort_keys=True)
        except TypeError:
            wildcard_info_text = str(wildcard_info)
        return (
            str(action.get("declared_pattern", "")),
            tuple(str(token) for token in action.get("declared_cards", [])),
            tuple(str(token) for token in action.get("carrier_cards", [])),
            DeepSeekClient._coerce_int(action.get("wildcard_count"), default=0),
            wildcard_info_text,
        )

    @staticmethod
    def _unique_actions_by_signature(actions: list[dict[str, object]]) -> list[dict[str, object]]:
        unique: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()
        for action in actions:
            signature = DeepSeekClient._action_signature(action)
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(action)
        return unique

    @staticmethod
    def _protected_actions_by_id(
        legal_actions: list[dict[str, object]],
        protected_action_ids: tuple[int, ...],
        *,
        max_count: int = 3,
    ) -> tuple[dict[str, object], ...]:
        """Resolve a small, exact canonical protection set or fail closed.

        A recommendation may name only original action IDs.  This helper is
        deliberately stricter than the display limiter: malformed IDs, a
        duplicate canonical ID, or a missing action disable protection rather
        than allowing a caller to smuggle a replacement action into the prompt.
        """
        if (
            type(protected_action_ids) is not tuple
            or type(max_count) is not int
            or max_count < 0
            or len(protected_action_ids) > max_count
            or any(type(action_id) is not int for action_id in protected_action_ids)
            or len(set(protected_action_ids)) != len(protected_action_ids)
        ):
            return ()
        by_id: dict[int, dict[str, object]] = {}
        for action in legal_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return ()
            action_id = int(action["action_id"])
            if action_id in by_id:
                return ()
            by_id[action_id] = action
        try:
            return tuple(by_id[action_id] for action_id in protected_action_ids)
        except KeyError:
            return ()

    @staticmethod
    def _relation_actions_by_groups(
        legal_actions: list[dict[str, object]],
        groups: tuple[tuple[int, int], ...],
    ) -> tuple[dict[str, object], ...]:
        if type(groups) is not tuple:
            return ()
        by_id: dict[int, dict[str, object]] = {}
        for action in legal_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return ()
            action_id = int(action["action_id"])
            if action_id in by_id:
                return ()
            by_id[action_id] = action
        selected: list[dict[str, object]] = []
        for group in groups:
            if (
                type(group) is not tuple
                or len(group) != 2
                or any(type(action_id) is not int for action_id in group)
                or group[0] == group[1]
                or any(action_id not in by_id for action_id in group)
            ):
                return ()
            selected.extend(by_id[action_id] for action_id in group)
        return tuple(selected)

    @staticmethod
    def _prefer_protected_actions(
        actions: list[dict[str, object]],
        protected_actions: tuple[dict[str, object], ...],
    ) -> list[dict[str, object]]:
        """Deduplicate signatures while preserving an explicitly protected ID."""
        if not protected_actions:
            return DeepSeekClient._unique_actions_by_signature(actions)
        protected_ids = {int(action["action_id"]) for action in protected_actions}
        selected: dict[tuple[object, ...], dict[str, object]] = {}
        for action in actions:
            signature = DeepSeekClient._action_signature(action)
            existing = selected.get(signature)
            if existing is None:
                selected[signature] = action
                continue
            if (
                type(action.get("action_id")) is int
                and int(action["action_id"]) in protected_ids
                and int(existing.get("action_id", -1)) not in protected_ids
            ):
                selected[signature] = action
        return [
            action
            for action in actions
            if selected.get(DeepSeekClient._action_signature(action)) is action
        ]

    @staticmethod
    def _ensure_protected_actions(
        actions: list[dict[str, object]],
        canonical_actions: list[dict[str, object]],
        protected_action_ids: tuple[int, ...],
        protected_relation_groups: tuple[tuple[int, int], ...] = (),
        protected_opening_action_ids: tuple[int, ...] = (),
    ) -> list[dict[str, object]]:
        """Keep protected original actions through an unbounded first pass."""
        protected = DeepSeekClient._protected_actions_by_id(
            canonical_actions,
            protected_action_ids,
        )
        relation_actions = DeepSeekClient._relation_actions_by_groups(
            canonical_actions,
            protected_relation_groups,
        )
        opening_actions = DeepSeekClient._protected_actions_by_id(
            canonical_actions,
            protected_opening_action_ids,
            max_count=MAX_OPENING_PATTERN_REPRESENTATIVES,
        )
        protected_actions = list(protected) + list(opening_actions) + [
            action for action in relation_actions if action not in protected and action not in opening_actions
        ]
        if not protected_actions:
            return actions
        protected_ids = {int(action["action_id"]) for action in protected_actions}
        by_signature: dict[tuple[object, ...], dict[str, object]] = {}
        ordered_signatures: list[tuple[object, ...]] = []
        for action in actions + protected_actions:
            signature = DeepSeekClient._action_signature(action)
            existing = by_signature.get(signature)
            if existing is None:
                by_signature[signature] = action
                ordered_signatures.append(signature)
            elif (
                type(action.get("action_id")) is int
                and int(action["action_id"]) in protected_ids
                and int(existing.get("action_id", -1)) not in protected_ids
            ):
                by_signature[signature] = action
        return [by_signature[signature] for signature in ordered_signatures]

    @staticmethod
    def _canonical_subset_actions(
        canonical_actions: list[dict[str, object]],
        candidate_actions: list[dict[str, object]],
    ) -> list[dict[str, object]] | None:
        """Return canonical originals for an exact candidate subset or None."""
        by_id: dict[int, dict[str, object]] = {}
        for action in canonical_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return None
            action_id = int(action["action_id"])
            if action_id in by_id:
                return None
            by_id[action_id] = action
        result: list[dict[str, object]] = []
        seen_ids: set[int] = set()
        for action in candidate_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return None
            action_id = int(action["action_id"])
            canonical = by_id.get(action_id)
            if canonical is None or action_id in seen_ids or action != canonical:
                return None
            seen_ids.add(action_id)
            result.append(canonical)
        return result

    @staticmethod
    def _is_pass_action(action: dict[str, object]) -> bool:
        return str(action.get("declared_pattern", "")) == "pass"

    @staticmethod
    def _is_pressure_action(action: dict[str, object]) -> bool:
        return str(action.get("declared_pattern", "")) in _PRESSURE_PATTERNS

    @staticmethod
    def _is_finishing_action(action: dict[str, object], hand_count: int | None) -> bool:
        if hand_count is None or hand_count <= 0:
            return False
        if DeepSeekClient._is_pass_action(action):
            return False
        return len(list(action.get("carrier_cards", []))) == hand_count

    @staticmethod
    def _opening_pattern_representative_ids(
        observation: object,
        legal_actions: list[dict[str, object]],
        phase_context: GamePhaseContext | None = None,
    ) -> tuple[int, ...]:
        """Choose one stable public representative per opening pattern/resource family.

        This only preserves real canonical alternatives in the model's bounded
        view. It does not evaluate or select the action for play.
        """
        if not isinstance(observation, dict):
            return ()
        current_round = observation.get("current_round")
        if not isinstance(current_round, dict):
            return ()
        try:
            context = phase_context or classify_game_phase(observation)
        except Exception:
            return ()
        if (
            not isinstance(context, GamePhaseContext)
            or context.phase != "opening"
            or current_round.get("constraint") != "free"
            or current_round.get("table_action") is not None
        ):
            return ()
        facts = summarize_candidate_structures(observation, legal_actions)
        if facts is None:
            return ()
        actions_by_id: dict[int, dict[str, object]] = {}
        for action in legal_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return ()
            action_id = int(action["action_id"])
            if action_id in actions_by_id:
                return ()
            actions_by_id[action_id] = action
        if any(fact.action_id not in actions_by_id for fact in facts):
            return ()

        by_family: dict[tuple[str, bool], list[CandidateStructure]] = {}
        for fact in facts:
            if fact.pattern not in _OPENING_PATTERN_ORDER:
                continue
            by_family.setdefault((fact.pattern, fact.uses_wildcard), []).append(fact)

        def representative_key(fact: CandidateStructure) -> tuple[object, ...]:
            action = actions_by_id[fact.action_id]
            declared = action.get("declared_cards")
            carriers = action.get("carrier_cards")
            declared_ranks = tuple(sorted(
                (_RANK_ORDER.get(_rank_of(str(card)), 0) for card in declared)
            )) if isinstance(declared, list) else ()
            carrier_ranks = tuple(sorted(
                (_RANK_ORDER.get(_rank_of(str(card)), 0) for card in carriers)
            )) if isinstance(carriers, list) else ()
            # Prefer an intact, natural, structurally compact example; ranks
            # and the final canonical ID only stabilize equivalent display
            # representatives and never select the play itself.
            return (
                fact.finishes_hand,
                fact.fragments_played_rank_group,
                fact.consumes_control_resource,
                fact.estimated_remaining_rank_groups,
                fact.residual_singleton_rank_count,
                declared_ranks,
                carrier_ranks,
                fact.action_id,
            )

        selected: list[int] = []
        for pattern in _OPENING_PATTERN_ORDER:
            for uses_wildcard in (False, True):
                family = by_family.get((pattern, uses_wildcard), ())
                if family:
                    selected.append(int(min(family, key=representative_key).action_id))
        if len(selected) > MAX_OPENING_PATTERN_REPRESENTATIVES:
            return ()
        return tuple(selected)

    @staticmethod
    def _has_wildcard(action: dict[str, object]) -> bool:
        return DeepSeekClient._coerce_int(action.get("wildcard_count"), default=0) > 0

    @staticmethod
    def _prune_sort_key(action: dict[str, object]) -> tuple[int, int, int, int]:
        return (
            DeepSeekClient._coerce_int(action.get("wildcard_count"), default=0),
            DeepSeekClient._action_sort_key(action),
            -len(list(action.get("carrier_cards", []))),
            DeepSeekClient._coerce_int(action.get("action_id"), default=10**9),
        )

    @staticmethod
    def _append_unique(
        target: list[dict[str, object]],
        seen: set[tuple[object, ...]],
        action: dict[str, object],
    ) -> None:
        signature = DeepSeekClient._action_signature(action)
        if signature in seen:
            return
        seen.add(signature)
        target.append(action)

    @staticmethod
    def _select_transition_actions(
        actions: list[dict[str, object]],
        constraint: str,
    ) -> list[dict[str, object]]:
        singles = sorted(
            [a for a in actions if str(a.get("declared_pattern", "")) == "single"],
            key=DeepSeekClient._prune_sort_key,
        )
        pairs = sorted(
            [a for a in actions if str(a.get("declared_pattern", "")) == "pair"],
            key=DeepSeekClient._prune_sort_key,
        )
        passes = [a for a in actions if str(a.get("declared_pattern", "")) == "pass"]

        chosen: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()

        def add_candidate(action: dict[str, object]) -> None:
            DeepSeekClient._append_unique(chosen, seen, action)

        if singles:
            add_candidate(singles[0])
            if len(singles) > 1:
                add_candidate(singles[-1])
        elif pairs:
            add_candidate(pairs[0])
            if len(pairs) > 1:
                add_candidate(pairs[-1])

        natural_pairs = [action for action in pairs if not DeepSeekClient._has_wildcard(action)]
        if singles and natural_pairs:
            add_candidate(natural_pairs[0])

        if constraint != "free" and passes:
            add_candidate(passes[0])

        for action in sorted(actions, key=DeepSeekClient._prune_sort_key):
            if DeepSeekClient._has_wildcard(action):
                add_candidate(action)

        if not singles and pairs and len(chosen) < 3:
            for action in pairs:
                add_candidate(action)
                if len(chosen) >= 3:
                    break

        return chosen

    @staticmethod
    def _grouped_legal_actions_summary(
        legal_actions: list[dict[str, object]],
        constraint: str,
        step_no: int,
        hand_count: int | None,
        current_level_rank: str,
        residual_structures: dict[int, FreeLeadResidualStructure] | None = None,
        compact_opening: bool = False,
    ) -> list[str]:
        scene = "lead" if constraint == "free" else "follow"
        buckets: dict[str, list[dict[str, object]]] = {
            "regular": [],
            "wildcard": [],
            "pressure": [],
            "pass": [],
        }
        for action in legal_actions:
            if DeepSeekClient._is_pass_action(action):
                buckets["pass"].append(action)
            elif DeepSeekClient._is_pressure_action(action):
                buckets["pressure"].append(action)
            elif DeepSeekClient._has_wildcard(action):
                buckets["wildcard"].append(action)
            else:
                buckets["regular"].append(action)

        for actions in buckets.values():
            actions.sort(key=DeepSeekClient._prune_sort_key)

        if scene == "lead":
            ordered_groups = [
                ("首出推荐动作", buckets.get("regular", [])),
                ("逢人配动作", buckets.get("wildcard", [])),
                ("炸弹/同花顺/天王炸", buckets.get("pressure", [])),
                ("pass", buckets.get("pass", [])),
            ]
        else:
            ordered_groups = [
                ("跟牌可压动作", buckets.get("regular", [])),
                ("逢人配动作", buckets.get("wildcard", [])),
                ("炸弹/同花顺/天王炸", buckets.get("pressure", [])),
                ("pass", buckets.get("pass", [])),
            ]

        lines: list[str] = [f"共 {len(legal_actions)} 个动作（已按战术剪枝）"]
        for label, actions in ordered_groups:
            unique_actions = DeepSeekClient._unique_actions_by_signature(actions)
            if not unique_actions:
                continue
            items = []
            for action in unique_actions:
                action_id = action.get("action_id")
                residual_structure = (
                    residual_structures.get(action_id)
                    if residual_structures is not None and isinstance(action_id, int)
                    else None
                )
                items.append(
                    DeepSeekClient._action_summary_entry(
                        action,
                        current_level_rank,
                        residual_structure,
                        compact_opening=compact_opening,
                    )
                )
            lines.append(f"{label}：{'、'.join(items)}")

        return lines

    @staticmethod
    def _limit_prompt_actions(
        actions: list[dict[str, object]],
        *,
        constraint: str,
        hand_count: int | None,
        protected_action_ids: tuple[int, ...] = (),
        protected_relation_groups: tuple[tuple[int, int], ...] = (),
        protected_opening_action_ids: tuple[int, ...] = (),
    ) -> list[dict[str, object]]:
        """Return a bounded, representative prompt view of canonical actions.

        The final display layer has a stricter contract than first-pass pruning:
        it never exceeds the prompt budget.  Free leads reserve the smallest
        natural single and pair before allocating the remaining budget.  This
        prevents a large run, pressure, or wildcard group from hiding the
        transition choices that the model needs to compare.  Full-deal opening
        overflow is allocated in stable rounds across pattern/resource
        families, after finishes, advice, family representatives, and complete
        relation pairs.  This bounds dense families without changing legality.
        """

        protected_actions = DeepSeekClient._protected_actions_by_id(
            actions,
            protected_action_ids,
        )
        opening_actions = DeepSeekClient._protected_actions_by_id(
            actions,
            protected_opening_action_ids,
            max_count=MAX_OPENING_PATTERN_REPRESENTATIVES,
        )
        relation_actions = DeepSeekClient._relation_actions_by_groups(
            actions,
            protected_relation_groups,
        )
        protected_display_actions = list(protected_actions) + list(opening_actions) + [
            action for action in relation_actions
            if action not in protected_actions and action not in opening_actions
        ]
        unique_actions = DeepSeekClient._prefer_protected_actions(
            actions,
            tuple(protected_display_actions),
        )
        if len(unique_actions) <= PROMPT_MAX_CANDIDATE_ACTIONS:
            return unique_actions

        selected: set[tuple[object, ...]] = set()
        selected_family_counts: Counter[tuple[str, bool]] = Counter()

        def reserve(action: dict[str, object]) -> None:
            signature = DeepSeekClient._action_signature(action)
            if signature in selected or len(selected) >= PROMPT_MAX_CANDIDATE_ACTIONS:
                return
            selected.add(signature)
            family = (
                str(action.get("declared_pattern", "")),
                DeepSeekClient._has_wildcard(action),
            )
            selected_family_counts[family] += 1

        def add_category(predicate: Callable[[dict[str, object]], bool]) -> None:
            for action in sorted(unique_actions, key=DeepSeekClient._prune_sort_key):
                if len(selected) >= PROMPT_MAX_CANDIDATE_ACTIONS:
                    return
                if predicate(action):
                    reserve(action)

        def reserve_relation_group(group: tuple[int, int]) -> None:
            group_actions = DeepSeekClient._relation_actions_by_groups(unique_actions, (group,))
            if len(group_actions) != 2:
                return
            signatures = tuple(DeepSeekClient._action_signature(action) for action in group_actions)
            if len(set(signatures)) != 2:
                return
            missing = {signature for signature in signatures if signature not in selected}
            if len(selected) + len(missing) <= PROMPT_MAX_CANDIDATE_ACTIONS:
                for action in group_actions:
                    reserve(action)

        protected_relation_endpoint_ids = {
            int(action["action_id"])
            for group in protected_relation_groups
            for action in DeepSeekClient._relation_actions_by_groups(
                unique_actions, (group,),
            )
            if type(action.get("action_id")) is int
        }

        def add_opening_family_rounds(predicate: Callable[[dict[str, object]], bool]) -> None:
            family_order = tuple(
                (pattern, uses_wildcard)
                for pattern in _OPENING_PATTERN_ORDER
                for uses_wildcard in (False, True)
            )
            family_actions: dict[tuple[str, bool], list[dict[str, object]]] = {}
            # Relation endpoints are admitted by the earlier atomic-pair
            # reservation only.  If that pair did not fit, a later family
            # round must not accidentally restore just one side.
            for action in unique_actions:
                action_id = action.get("action_id")
                family = (
                    str(action.get("declared_pattern", "")),
                    DeepSeekClient._has_wildcard(action),
                )
                if (
                    family[0] not in _OPENING_PATTERN_ORDER
                    or not predicate(action)
                    or (
                        type(action_id) is int
                        and action_id in protected_relation_endpoint_ids
                    )
                ):
                    continue
                family_actions.setdefault(family, []).append(action)
            for actions_in_family in family_actions.values():
                actions_in_family.sort(key=DeepSeekClient._prune_sort_key)

            while len(selected) < PROMPT_MAX_CANDIDATE_ACTIONS:
                progressed = False
                for family in family_order:
                    if selected_family_counts[family] >= MAX_OPENING_ACTIONS_PER_PATTERN_FAMILY:
                        continue
                    next_action = next(
                        (
                            action for action in family_actions.get(family, ())
                            if DeepSeekClient._action_signature(action) not in selected
                        ),
                        None,
                    )
                    if next_action is None:
                        continue
                    reserve(next_action)
                    progressed = True
                    if len(selected) >= PROMPT_MAX_CANDIDATE_ACTIONS:
                        break
                if not progressed:
                    break

        # Keep the first-pass transition recall meaningful in the final prompt.
        # These are representatives, not a new legality or strategy selector.
        if constraint == "free":
            if protected_opening_action_ids:
                # Full-deal opening family representation is part of this
                # branch. Urgency, valid advice, family coverage and the
                # ordinary transition pair are reserved before relation pairs.
                add_category(lambda action: DeepSeekClient._is_finishing_action(action, hand_count))
                for action in protected_actions:
                    reserve(action)
                for action in opening_actions:
                    reserve(action)
            natural_singles = sorted(
                [
                    action
                    for action in unique_actions
                    if str(action.get("declared_pattern", "")) == "single"
                    and not DeepSeekClient._has_wildcard(action)
                ],
                key=DeepSeekClient._prune_sort_key,
            )
            natural_pairs = sorted(
                [
                    action
                    for action in unique_actions
                    if str(action.get("declared_pattern", "")) == "pair"
                    and not DeepSeekClient._has_wildcard(action)
                ],
                key=DeepSeekClient._prune_sort_key,
            )
            if natural_singles:
                reserve(natural_singles[0])
            if natural_pairs:
                reserve(natural_pairs[0])
            if protected_opening_action_ids:
                for group in protected_relation_groups:
                    reserve_relation_group(group)
                # Preserve the established finishing/pressure/wildcard
                # priority, but share each tier across actual opening pattern
                # families.  A dense triple-with-pair family can no longer
                # consume every unreserved ordinary slot by canonical order.
                add_opening_family_rounds(
                    lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
                    and DeepSeekClient._is_pressure_action(action)
                )
                add_opening_family_rounds(
                    lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
                    and not DeepSeekClient._is_pressure_action(action)
                    and DeepSeekClient._has_wildcard(action)
                )
                add_opening_family_rounds(
                    lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
                    and not DeepSeekClient._is_pressure_action(action)
                    and not DeepSeekClient._has_wildcard(action)
                )
                return [
                    action for action in unique_actions
                    if DeepSeekClient._action_signature(action) in selected
                ]
            if not protected_opening_action_ids:
                # Outside full-deal openings, preserve the established order:
                # minimum natural lead representatives precede advice/relations.
                for action in protected_actions:
                    reserve(action)
                for group in protected_relation_groups:
                    reserve_relation_group(group)
        else:
            passes = sorted(
                [action for action in unique_actions if DeepSeekClient._is_pass_action(action)],
                key=DeepSeekClient._prune_sort_key,
            )
            if passes:
                reserve(passes[0])
            add_category(lambda action: DeepSeekClient._is_finishing_action(action, hand_count))
            for action in protected_actions:
                reserve(action)
            # Keep one real representative of each pressure family before
            # relation pairs consume overflow slots. Remaining pressure actions
            # continue to compete in the regular bounded pressure tier below.
            for pattern in ("bomb", "straight_flush", "joker_bomb"):
                representative = next(
                    (
                        action for action in sorted(unique_actions, key=DeepSeekClient._prune_sort_key)
                        if str(action.get("declared_pattern", "")) == pattern
                    ),
                    None,
                )
                if representative is not None:
                    reserve(representative)
            for group in protected_relation_groups:
                reserve_relation_group(group)

        # The predicates are mutually exclusive so each slot has one auditable
        # priority.  Representatives reserved above remain protected.
        add_category(lambda action: DeepSeekClient._is_finishing_action(action, hand_count))
        add_category(
            lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
            and DeepSeekClient._is_pressure_action(action)
        )
        add_category(
            lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
            and not DeepSeekClient._is_pressure_action(action)
            and DeepSeekClient._has_wildcard(action)
        )
        add_category(
            lambda action: not DeepSeekClient._is_finishing_action(action, hand_count)
            and not DeepSeekClient._is_pressure_action(action)
            and not DeepSeekClient._has_wildcard(action)
        )

        return [
            action
            for action in unique_actions
            if DeepSeekClient._action_signature(action) in selected
        ]

    @staticmethod
    def _lead_pruned_actions(legal_actions: list[dict[str, object]], phase: str) -> list[dict[str, object]]:
        kept: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()

        pattern_groups = (
            ["steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"],
            ["single", "pair", "pass"],
            ["bomb", "straight_flush", "joker_bomb"],
        )
        if is_endgame_phase(phase):
            pattern_groups = (
                ["bomb", "straight_flush", "joker_bomb"],
                ["steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"],
                ["single", "pair", "pass"],
            )

        for patterns in pattern_groups:
            pattern_set = set(patterns)
            actions = [
                action for action in legal_actions
                if str(action.get("declared_pattern", "")) in pattern_set
            ]
            if patterns == ["single", "pair", "pass"]:
                for action in DeepSeekClient._select_transition_actions(actions, "free"):
                    DeepSeekClient._append_unique(kept, seen, action)
                continue
            for action in DeepSeekClient._unique_actions_by_signature(
                sorted(actions, key=DeepSeekClient._prune_sort_key)
            ):
                DeepSeekClient._append_unique(kept, seen, action)

        return kept

    @staticmethod
    def _follow_pruned_actions(legal_actions: list[dict[str, object]], hand_count: int | None) -> list[dict[str, object]]:
        kept: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()

        passes = [action for action in legal_actions if DeepSeekClient._is_pass_action(action)]
        pressure = [action for action in legal_actions if DeepSeekClient._is_pressure_action(action)]
        finishing = [
            action for action in legal_actions
            if DeepSeekClient._is_finishing_action(action, hand_count)
        ]
        regular = [
            action for action in legal_actions
            if not DeepSeekClient._is_pass_action(action)
            and not DeepSeekClient._is_pressure_action(action)
            and not DeepSeekClient._is_finishing_action(action, hand_count)
        ]
        wildcard_regular = [action for action in regular if DeepSeekClient._has_wildcard(action)]
        ordinary_regular = [action for action in regular if not DeepSeekClient._has_wildcard(action)]

        for action in passes:
            DeepSeekClient._append_unique(kept, seen, action)
        for action in DeepSeekClient._unique_actions_by_signature(sorted(ordinary_regular, key=DeepSeekClient._prune_sort_key))[:12]:
            DeepSeekClient._append_unique(kept, seen, action)
        for action in DeepSeekClient._unique_actions_by_signature(sorted(wildcard_regular, key=DeepSeekClient._prune_sort_key)):
            DeepSeekClient._append_unique(kept, seen, action)
        for action in DeepSeekClient._unique_actions_by_signature(sorted(pressure, key=DeepSeekClient._prune_sort_key)):
            DeepSeekClient._append_unique(kept, seen, action)
        for action in finishing:
            DeepSeekClient._append_unique(kept, seen, action)

        return kept

    @staticmethod
    def _prune_legal_actions(
        legal_actions: list[dict[str, object]],
        constraint: str,
        step_no: int = 0,
        hand_count: int | None = None,
        phase_context: GamePhaseContext | None = None,
        protected_action_ids: tuple[int, ...] = (),
        protected_relation_groups: tuple[tuple[int, int], ...] = (),
        protected_opening_action_ids: tuple[int, ...] = (),
    ) -> list[dict[str, object]]:
        """Prune redundant actions to reduce context size for the model.

        Preserves all run / pressure actions and keeps a tactical transition subset.
        The order is phase-aware so the prompt can emphasize opening, middle, or
        endgame priorities without changing legality.
        """
        # The optional legacy fields retain compatibility for callers that do
        # not have an observation payload.  All normal decision paths provide
        # the shared context instead.
        phase = phase_context.phase if phase_context is not None else DeepSeekClient._phase_from_round(step_no, hand_count)
        if constraint == "free":
            kept = DeepSeekClient._lead_pruned_actions(legal_actions, phase)
        else:
            kept = DeepSeekClient._follow_pruned_actions(legal_actions, hand_count)

        seen = {DeepSeekClient._action_signature(action) for action in kept}
        for action in legal_actions:
            if DeepSeekClient._is_finishing_action(action, hand_count):
                DeepSeekClient._append_unique(kept, seen, action)
            if constraint != "free" and (
                DeepSeekClient._is_pass_action(action)
                or DeepSeekClient._is_pressure_action(action)
            ):
                DeepSeekClient._append_unique(kept, seen, action)

        kept = kept or list(legal_actions)
        return DeepSeekClient._ensure_protected_actions(
            kept,
            legal_actions,
            protected_action_ids,
            protected_relation_groups,
            protected_opening_action_ids,
        )

    @staticmethod
    def _prompt_candidate_contrasts(
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
        *,
        strategy_recommendation: "StrategyRecommendation | None" = None,
        rag_context: dict[str, object] | None = None,
    ) -> tuple[CandidateContrast, ...] | None:
        """Select useful complete relations without changing formula eligibility.

        Relation detection keeps its complete canonical denominator.  This
        separate bounded view selects prompt comparisons using active source
        evidence, public residual differences, recommendation/family overlap,
        and the incremental candidate cost of each complete pair.
        """
        full_contrasts = summarize_candidate_contrasts(observation, legal_actions)
        if full_contrasts is None:
            return None
        if (
            type(opening_formula_contrasts) is not tuple
            or len(opening_formula_contrasts) > MAX_OPENING_FORMULA_CONTRASTS
            or any(
                type(item) is not CandidateContrast
                or item.kind not in CANDIDATE_RELATION_KINDS
                or type(item.action_ids) is not tuple
                or len(item.action_ids) != 2
                or any(type(action_id) is not int for action_id in item.action_ids)
                or item.action_ids[0] == item.action_ids[1]
                or item not in full_contrasts
                for item in opening_formula_contrasts
            )
        ):
            opening_formula_contrasts = ()

        by_id = {
            int(action["action_id"]): action
            for action in legal_actions
            if isinstance(action, dict) and type(action.get("action_id")) is int
        }
        if len(by_id) != len(legal_actions):
            return None
        facts = summarize_candidate_structures(observation, legal_actions)
        if facts is None:
            return None
        facts_by_id = {fact.action_id: fact for fact in facts}
        if len(facts_by_id) != len(by_id):
            return None

        validated_recommendation = DeepSeekClient._validated_strategy_recommendation(
            strategy_recommendation, legal_actions,
        )
        recommendation_ids = (
            validated_recommendation.action_ids
            if validated_recommendation is not None
            else ()
        )
        try:
            phase_context = classify_game_phase(observation)
        except Exception:
            phase_context = None
        opening_ids = DeepSeekClient._opening_pattern_representative_ids(
            observation, legal_actions, phase_context,
        ) if phase_context is not None else ()

        # Candidate slots needed independently of any relation: urgent
        # finishes, exact recommendation IDs, opening-family representatives,
        # the ordinary transition representatives, pass, and one representative
        # for each available pressure family.
        baseline_ids: set[int] = set(recommendation_ids) | set(opening_ids)
        baseline_ids.update(
            fact.action_id for fact in facts if fact.finishes_hand
        )
        current_round = observation.get("current_round")
        constraint = (
            str(current_round.get("constraint", ""))
            if isinstance(current_round, dict)
            else ""
        )
        if constraint == "free":
            natural_singles = sorted(
                (
                    fact for fact in facts
                    if fact.pattern == "single" and not fact.uses_wildcard
                ),
                key=lambda fact: DeepSeekClient._prune_sort_key(by_id[fact.action_id]),
            )
            natural_pairs = sorted(
                (
                    fact for fact in facts
                    if fact.pattern == "pair" and not fact.uses_wildcard
                ),
                key=lambda fact: DeepSeekClient._prune_sort_key(by_id[fact.action_id]),
            )
            baseline_ids.update(fact.action_id for fact in natural_singles[:1])
            baseline_ids.update(fact.action_id for fact in natural_pairs[:1])
        else:
            baseline_ids.update(
                fact.action_id for fact in facts if fact.pattern == "pass"
            )
            for pattern in ("bomb", "straight_flush", "joker_bomb"):
                pressure_facts = sorted(
                    (fact for fact in facts if fact.pattern == pattern),
                    key=lambda fact: DeepSeekClient._prune_sort_key(by_id[fact.action_id]),
                )
                baseline_ids.update(fact.action_id for fact in pressure_facts[:1])

        baseline_signatures = {
            DeepSeekClient._action_signature(by_id[action_id])
            for action_id in baseline_ids
            if action_id in by_id
        }
        relation_extra_budget = min(
            MAX_PROMPT_RELATION_EXTRA_ACTIONS,
            max(0, PROMPT_MAX_CANDIDATE_ACTIONS - len(baseline_signatures)),
        )
        if relation_extra_budget == 0:
            return ()

        source_ids: set[str] = set()
        if isinstance(rag_context, dict):
            hits = rag_context.get("experience_hits")
            if isinstance(hits, list):
                source_ids = {
                    str(hit["source_id"])
                    for hit in hits
                    if isinstance(hit, dict) and isinstance(hit.get("source_id"), str)
                }

        formula_keys = {
            (item.kind, item.action_ids) for item in opening_formula_contrasts
        }
        candidates: list[CandidateContrast] = []
        seen: set[tuple[str, tuple[int, int]]] = set()
        for contrast in (*opening_formula_contrasts, *full_contrasts):
            key = (contrast.kind, contrast.action_ids)
            if key in seen:
                continue
            seen.add(key)
            first, second = contrast.action_ids
            if first not in by_id or second not in by_id or first == second:
                continue
            first_signature = DeepSeekClient._action_signature(by_id[first])
            second_signature = DeepSeekClient._action_signature(by_id[second])
            if first_signature == second_signature:
                continue
            candidates.append(contrast)

        kind_order = {
            kind: index for index, kind in enumerate(_PROMPT_RELATION_KIND_ORDER)
        }

        def endpoint_key(action_id: int) -> tuple[object, ...]:
            action = by_id[action_id]
            fact = facts_by_id[action_id]
            carrier = action.get("carrier_cards")
            ranks = tuple(sorted(
                _RANK_ORDER.get(_rank_of(str(card)), 0)
                for card in carrier
            )) if isinstance(carrier, list) else ()
            return (
                fact.pattern,
                fact.uses_wildcard,
                fact.carrier_count,
                ranks,
                fact.finishes_hand,
                fact.residual_singleton_rank_count,
                fact.estimated_remaining_rank_groups,
                action_id,
            )

        def residual_difference(contrast: CandidateContrast) -> int:
            first = facts_by_id[contrast.action_ids[0]]
            second = facts_by_id[contrast.action_ids[1]]
            return (
                abs(first.residual_singleton_rank_count - second.residual_singleton_rank_count) * 3
                + abs(first.estimated_remaining_rank_groups - second.estimated_remaining_rank_groups) * 2
                + abs((first.residual_card_count or 0) - (second.residual_card_count or 0))
                + 2 * int(first.clears_played_rank_groups != second.clears_played_rank_groups)
                + 2 * int(first.fragments_played_rank_group != second.fragments_played_rank_group)
                + 2 * int(first.consumes_control_resource != second.consumes_control_resource)
                + 2 * int(first.uses_wildcard != second.uses_wildcard)
                + len(set(first.residual_hand_natural_pattern_kinds or ()) ^ set(second.residual_hand_natural_pattern_kinds or ()))
            )

        def priority_key(contrast: CandidateContrast) -> tuple[object, ...]:
            kind = contrast.kind
            expected_sources = _PROMPT_RELATION_SOURCE_IDS.get(kind, frozenset())
            source_applicable = bool(expected_sources & source_ids)
            urgent = kind.startswith(("danger_block", "teammate_")) or (
                kind == "opponent_single_control_cost"
                and contrast.table_leader_hand_count is not None
                and contrast.table_leader_hand_count <= 2
            ) or (
                kind == "follow_response_net_tradeoff"
                and (
                    contrast.table_leader_relation == "teammate"
                    or (
                        contrast.table_leader_relation == "opponent"
                        and contrast.table_leader_hand_count is not None
                        and contrast.table_leader_hand_count <= 2
                    )
                    or (
                        contrast.next_active_player_relation == "opponent"
                        and contrast.next_active_player_hand_count is not None
                        and contrast.next_active_player_hand_count <= 2
                    )
                )
            )
            recommendation_overlap = sum(
                action_id in recommendation_ids for action_id in contrast.action_ids
            )
            opening_overlap = sum(
                action_id in opening_ids for action_id in contrast.action_ids
            )
            endpoint_families = tuple(
                (
                    facts_by_id[action_id].pattern,
                    facts_by_id[action_id].uses_wildcard,
                )
                for action_id in contrast.action_ids
            )
            cross_family = endpoint_families[0] != endpoint_families[1]
            response_information = 0
            response_finisher = 0
            if kind == "follow_response_net_tradeoff":
                effect = candidate_response_net_effect(
                    facts_by_id[contrast.action_ids[0]],
                    facts_by_id[contrast.action_ids[1]],
                )
                if effect is not None:
                    response_information = effect.comparison_information
                    response_finisher = int(effect.finishes_hand)
            return (
                0 if (kind, contrast.action_ids) in formula_keys else 1,
                0 if urgent else 1,
                0 if source_applicable else 1,
                -recommendation_overlap,
                -opening_overlap,
                -response_finisher,
                -response_information,
                -int(cross_family),
                -residual_difference(contrast),
                kind_order.get(kind, len(kind_order)),
                endpoint_key(contrast.action_ids[0]),
                endpoint_key(contrast.action_ids[1]),
                contrast.action_ids,
            )

        def missing_signatures(contrast: CandidateContrast, selected: set[tuple[object, ...]]) -> set[tuple[object, ...]]:
            return {
                DeepSeekClient._action_signature(by_id[action_id])
                for action_id in contrast.action_ids
            } - selected

        def response_selection_lane(contrast: CandidateContrast) -> str | None:
            if contrast.kind != "follow_response_net_tradeoff":
                return None
            response = facts_by_id[contrast.action_ids[1]]
            effect = candidate_response_net_effect(
                facts_by_id[contrast.action_ids[0]], response,
            )
            if effect is None:
                return None
            uses_high_cost_route = (
                response.pattern in _PRESSURE_PATTERNS
                or effect.uses_wildcard
                or effect.spends_control_resource
            )
            return "resource" if uses_high_cost_route else "ordinary"

        selected_contrasts: list[CandidateContrast] = []
        selected_keys: set[tuple[str, tuple[int, int]]] = set()
        selected_kind_counts: Counter[str] = Counter()
        selected_signatures = set(baseline_signatures)

        def try_add(contrast: CandidateContrast) -> bool:
            key = (contrast.kind, contrast.action_ids)
            if (
                key in selected_keys
                or len(selected_contrasts) >= MAX_PROMPT_RELATION_PAIRS
                or selected_kind_counts[contrast.kind] >= MAX_PROMPT_RELATIONS_PER_KIND
            ):
                return False
            missing = missing_signatures(contrast, selected_signatures)
            if len(selected_signatures - baseline_signatures) + len(missing) > relation_extra_budget:
                return False
            selected_keys.add(key)
            selected_contrasts.append(contrast)
            selected_kind_counts[contrast.kind] += 1
            selected_signatures.update(missing)
            return True

        ordered_candidates = sorted(candidates, key=priority_key)
        # First secure one pair per relation kind, but let the same stable
        # relevance ordering choose which kinds spend the scarce first-round
        # slots. In particular, an active source match or public urgency must
        # outrank a merely earlier enum entry when many kinds compete.
        for contrast in ordered_candidates:
            if selected_kind_counts[contrast.kind] == 0:
                try_add(contrast)
        # Spend remaining pair/endpoint budget greedily: shared endpoints are
        # cheaper, while source-applicable and structurally informative pairs
        # still lead otherwise-equivalent choices.
        remaining = [
            item for item in ordered_candidates
            if (
                (item.kind, item.action_ids) not in selected_keys
                and selected_kind_counts[item.kind] < MAX_PROMPT_RELATIONS_PER_KIND
            )
        ]
        while remaining and len(selected_contrasts) < MAX_PROMPT_RELATION_PAIRS:
            feasible: list[tuple[int, tuple[object, ...], CandidateContrast]] = []
            for contrast in remaining:
                cost = len(missing_signatures(contrast, selected_signatures))
                if len(selected_signatures - baseline_signatures) + cost <= relation_extra_budget:
                    feasible.append((cost, priority_key(contrast), contrast))
            if not feasible:
                break
            if selected_kind_counts["follow_response_net_tradeoff"] == 1:
                selected_response = next(
                    item for item in selected_contrasts
                    if item.kind == "follow_response_net_tradeoff"
                )
                selected_lane = response_selection_lane(selected_response)
                if selected_lane is not None:
                    same_lane = [
                        item for item in feasible
                        if item[2].kind == "follow_response_net_tradeoff"
                        and response_selection_lane(item[2]) == selected_lane
                    ]
                    other_lane = [
                        item for item in feasible
                        if item[2].kind == "follow_response_net_tradeoff"
                        and response_selection_lane(item[2]) not in {None, selected_lane}
                    ]
                    if other_lane:
                        best_same_priority = min(
                            (item[1][:6] for item in same_lane), default=None,
                        )
                        best_other_priority = min(item[1][:6] for item in other_lane)
                        # Keep urgency, recommendation, opening priority, and
                        # finishing actions ahead of representational balance.
                        # When those are tied, reserve the second slot for a
                        # different response-cost family if one fits the same
                        # endpoint budget.
                        if best_same_priority is None or best_other_priority <= best_same_priority:
                            feasible = [
                                item for item in feasible
                                if item[2].kind != "follow_response_net_tradeoff"
                                or response_selection_lane(item[2]) != selected_lane
                            ]
            _cost, _priority, chosen = min(feasible, key=lambda item: (item[0], item[1]))
            try_add(chosen)
            remaining.remove(chosen)

        return tuple(selected_contrasts)

    @staticmethod
    def prepare_prompt_actions(
        legal_actions: list[dict[str, object]],
        *,
        constraint: str,
        step_no: int,
        hand_count: int | None,
        phase_context: GamePhaseContext | None = None,
        strategy_recommendation: "StrategyRecommendation | None" = None,
        observation: dict[str, object] | None = None,
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
        rag_context: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        """Build the one bounded canonical candidate set used by the model.

        Strategy knowledge is derived from the full action set elsewhere.  If
        that derived payload validates against the same full canonical set, its
        exact original IDs survive both display pruning stages.  Invalid advice
        receives no protection and cannot alter the candidate set.
        """
        validated = DeepSeekClient._validated_strategy_recommendation(
            strategy_recommendation,
            legal_actions,
        )
        protected_ids = validated.action_ids if validated is not None else ()
        contrasts = (
            DeepSeekClient._prompt_candidate_contrasts(
                observation,
                legal_actions,
                opening_formula_contrasts,
                strategy_recommendation=strategy_recommendation,
                rag_context=rag_context,
            )
            if observation is not None
            else ()
        )
        protected_relation_groups = (
            tuple(item.action_ids for item in contrasts)
            if contrasts is not None
            else ()
        )
        if observation is not None:
            route_my_info = observation.get("my_info")
            grouping_pairs = free_lead_grouping_comparison_pairs(
                observation,
                legal_actions,
                DeepSeekClient._coerce_int(
                    route_my_info.get("player_id") if isinstance(route_my_info, dict) else None,
                    default=0,
                ),
            )
            protected_relation_groups = tuple(dict.fromkeys(protected_relation_groups + grouping_pairs))
        protected_opening_action_ids = DeepSeekClient._opening_pattern_representative_ids(
            observation,
            legal_actions,
            phase_context,
        ) if observation is not None else ()
        first_pass = DeepSeekClient._prune_legal_actions(
            legal_actions,
            constraint,
            step_no=step_no,
            hand_count=hand_count,
            phase_context=phase_context,
            protected_action_ids=protected_ids,
            protected_relation_groups=protected_relation_groups,
            protected_opening_action_ids=protected_opening_action_ids,
        )
        return DeepSeekClient._limit_prompt_actions(
            first_pass,
            constraint=constraint,
            hand_count=hand_count,
            protected_action_ids=protected_ids,
            protected_relation_groups=protected_relation_groups,
            protected_opening_action_ids=protected_opening_action_ids,
        )

    @staticmethod
    def _compact_action_text(
        action: dict[str, object],
        current_level_rank: str,
        has_straight_flush: bool,
    ) -> str:
        """Build a compact action description with minimal suit info."""
        pattern = str(action.get("declared_pattern", ""))
        if pattern == "pass":
            return "pass"

        carrier = [str(t) for t in action.get("carrier_cards", [])]
        declared = [str(t) for t in action.get("declared_cards", [])]
        wc = int(action.get("wildcard_count", 0))

        cards_text = _cards_for_ai(
            carrier,
            current_level_rank,
            is_flush_context=has_straight_flush and pattern == "straight_flush",
        )

        if pattern == "bomb":
            main_rank = _rank_of(declared[0]) if declared else ""
            label = f"{len(carrier)}炸{main_rank}"
        elif pattern == "single":
            label = "单"
        elif pattern == "pair":
            main_rank = _rank_of(declared[0]) if declared else ""
            label = f"对{main_rank}"
        elif pattern == "triple":
            main_rank = _rank_of(declared[0]) if declared else ""
            label = f"三{main_rank}"
        elif pattern == "triple_with_pair":
            label = "三带二"
        elif pattern == "straight":
            label = "顺"
        elif pattern == "pair_straight":
            label = "连对"
        elif pattern == "steel_plate":
            label = "钢板"
        elif pattern == "straight_flush":
            label = "同花顺"
        elif pattern == "joker_bomb":
            label = "天王炸"
        else:
            label = pattern

        return f"{cards_text}（{label}）"

    @staticmethod
    def _rag_items(rag_context: dict[str, object] | None, key: str) -> list[dict[str, object]]:
        if not isinstance(rag_context, dict):
            return []
        raw_items = rag_context.get(key, [])
        if not isinstance(raw_items, list):
            return []
        return [item for item in raw_items if isinstance(item, dict)]

    @staticmethod
    def _format_scene_tags(rag_context: dict[str, object] | None) -> list[str]:
        if not isinstance(rag_context, dict):
            return ["（无）"]
        tags = rag_context.get("scene_tags", {})
        if not isinstance(tags, dict) or not tags:
            return ["（无）"]
        lines: list[str] = []
        for key in _SCENE_TAG_ORDER:
            if key not in tags:
                continue
            value = tags.get(key)
            if value is None or value == "":
                continue
            lines.append(f"{key}: {value}")
        return lines or ["（无）"]

    @staticmethod
    def _rag_title_and_body(item: dict[str, object]) -> tuple[str, str]:
        snippet_lines = str(item.get("snippet", "")).splitlines()
        title = ""
        body_lines: list[str] = []
        for raw_line in snippet_lines:
            line = raw_line.strip()
            if not line:
                continue
            if not title and line.startswith("#"):
                title = line.lstrip("#").strip()
                continue
            body_lines.append(line)
        title = DeepSeekClient._bounded_text(title or "知识条目", PROMPT_MAX_RAG_TITLE_CHARS)
        body = DeepSeekClient._bounded_text(" ".join(body_lines), PROMPT_MAX_RAG_BODY_CHARS)
        return title, body

    @staticmethod
    def _format_rag_hits(items: list[dict[str, object]]) -> list[str]:
        if not items:
            return ["（无）"]
        lines: list[str] = []
        for item in items[:PROMPT_MAX_RAG_HITS_PER_LAYER]:
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            topic = str(metadata.get("topic", ""))
            domain = str(metadata.get("strategy_domain", ""))
            guidance_mode = str(metadata.get("guidance_mode", ""))
            title, body = DeepSeekClient._rag_title_and_body(item)
            topic_text = f"；topic={topic}" if topic else ""
            domain_text = f"；domain={domain}" if domain else ""
            body_text = f"：{body}" if body else ""
            suffix_parts = (topic_text + domain_text).lstrip("；")
            suffix = f"（{suffix_parts}）" if suffix_parts else ""
            prefix = "- 可撤回软假设：" if guidance_mode == "soft_hypothesis" else "- "
            lines.append(f"{prefix}{title}{suffix}{body_text}")
        return lines

    @staticmethod
    def _opening_cross_pattern_guidance(
        *,
        current_round: dict[str, object],
        phase_context: GamePhaseContext | None,
        candidate_facts: tuple[CandidateStructure, ...] | None,
        rag_context: dict[str, object] | None,
    ) -> str | None:
        """Return a compact opening guide only when public evidence supports it.

        This is model-before guidance, not a local selector.  It is tied to the
        actual bounded candidate set and to accepted opening RAG evidence. A
        C-tier hit remains visibly retractable in the evidence section; this
        summary never turns it into a local decision or fixed ranking.
        """
        if (
            not isinstance(phase_context, GamePhaseContext)
            or phase_context.phase != "opening"
            or current_round.get("constraint") != "free"
            or current_round.get("table_action") is not None
            or candidate_facts is None
            or not isinstance(rag_context, dict)
        ):
            return None
        scene_tags = rag_context.get("scene_tags")
        if (
            not isinstance(scene_tags, dict)
            or scene_tags.get("scene") != "lead_opening"
            or scene_tags.get("phase") != "opening"
            or scene_tags.get("action_context") != "free_lead"
        ):
            return None

        has_opening_source_principle = False
        for item in DeepSeekClient._rag_items(rag_context, "experience_hits"):
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                continue
            domains = metadata.get("strategy_domain")
            domain_values = (
                {part.strip() for part in domains.split(",") if part.strip()}
                if isinstance(domains, str)
                else set()
            )
            if (
                metadata.get("guidance_mode") == "source_principle"
                and "opening_free_lead" in domain_values
            ):
                has_opening_source_principle = True
                break
        if not has_opening_source_principle:
            return None

        pattern_labels = {
            "single": "单张",
            "pair": "对子",
            "triple": "三张",
            "straight": "顺子",
        }
        visible_patterns = {
            fact.pattern
            for fact in candidate_facts
            if fact.pattern in pattern_labels and not fact.uses_wildcard
        }
        if len(visible_patterns) < 2:
            return None
        visible_text = "、".join(
            pattern_labels[pattern]
            for pattern in ("single", "pair", "triple", "straight")
            if pattern in visible_patterns
        )
        return (
            f"开局跨牌型取舍（展示含{visible_text}）：比较出后余组/孤张与拆组成本；"
            "结构安全小单可低成本试探，成组牌/顺子可清理牌型但无固定牌型先后。"
            "可证回手/控制或公开协同/紧急性可推翻局部优势；未知用途按未知，不推断未来牌权。"
        )

    @staticmethod
    def _format_hand_evaluation(hand_evaluation: dict[str, object] | None) -> list[str]:
        if not isinstance(hand_evaluation, dict):
            return ["（无）"]
        ordered_fields = (
            "total_score",
            "structure_score",
            "control_score",
            "potential_score",
            "label",
        )
        parts = [
            f"{key}={hand_evaluation[key]}"
            for key in ordered_fields
            if key in hand_evaluation and hand_evaluation[key] not in (None, "")
        ]
        lines = [", ".join(parts)] if parts else []
        comment = hand_evaluation.get("comment")
        if comment not in (None, ""):
            lines.append(
                "comment="
                + DeepSeekClient._bounded_text(str(comment), PROMPT_MAX_ACTION_DISPLAY_CHARS)
            )
        return lines or ["（无）"]

    @staticmethod
    def _format_card_tracking_summary(
        card_tracking_summary: str | None,
        *,
        candidate_action_ids: set[int] | None = None,
    ) -> list[str]:
        if not card_tracking_summary:
            return ["（无）"]
        if candidate_action_ids is not None:
            filtered_lines = []
            for line in card_tracking_summary.splitlines():
                if line.startswith("M3候选对照") or line.startswith("M3唯一归属核验"):
                    referenced = [int(value) for value in re.findall(r"action_id=(\d+)", line)]
                    if not referenced or not all(value in candidate_action_ids for value in referenced):
                        continue
                filtered_lines.append(line)
            card_tracking_summary = "\n".join(filtered_lines)
        lines = [
            line.strip()
            for line in card_tracking_summary.splitlines()
            if line.strip()
            and line.strip() != "【记牌信息】"
            and not line.strip().startswith("[CardTracker Mode:")
        ]
        compact = DeepSeekClient._bounded_text("；".join(lines), PROMPT_MAX_CARD_TRACKING_CHARS)
        return [compact] if compact else ["（无）"]

    @staticmethod
    def _format_public_endgame_summary(
        summary: str | None,
        *,
        candidate_action_ids: set[int] | None = None,
    ) -> list[str]:
        if not summary:
            return ["（无）"]
        if candidate_action_ids is not None:
            kept = []
            for line in summary.splitlines():
                if line.startswith("M5公开残局对照"):
                    referenced = [int(value) for value in re.findall(r"action_id=(\d+)", line)]
                    if not referenced or not all(value in candidate_action_ids for value in referenced):
                        continue
                kept.append(line)
            summary = "\n".join(kept)
        lines = [line.strip() for line in summary.splitlines() if line.strip()]
        compact = DeepSeekClient._bounded_text(
            "；".join(lines),
            PROMPT_MAX_PUBLIC_ENDGAME_CHARS,
        )
        return [compact] if compact else ["（无）"]

    @staticmethod
    def _validated_card_confidence_prompt(
        payload: object,
    ) -> "CardConfidencePromptPayload | None":
        if payload is None:
            return None
        try:
            from agents.card_confidence_prompt import (
                CARD_CONFIDENCE_PROMPT_MAX_CHARS,
                CardConfidencePromptPayload,
            )
        except Exception:
            return None
        if not isinstance(payload, CardConfidencePromptPayload):
            return None
        if (
            payload.status != "ready"
            or payload.source != "physical_assignment_marginal_v1"
            or payload.calibration_scope != "critical_endgame_policy_diverse_v1"
            or not isinstance(payload.diagnostics, tuple)
            or payload.diagnostics
            or not isinstance(payload.text, str)
            or not payload.text
            or not isinstance(payload.char_count, int)
            or isinstance(payload.char_count, bool)
            or payload.char_count <= 0
            or payload.char_count != len(payload.text)
            or payload.char_count > CARD_CONFIDENCE_PROMPT_MAX_CHARS
        ):
            return None
        return payload

    @staticmethod
    def _validated_strategy_intent_prompt(
        payload: object,
    ) -> "StrategyIntentPromptPayload | None":
        if payload is None:
            return None
        try:
            from agents.strategy_intent_prompt import StrategyIntentPromptPayload
        except Exception:
            return None
        if type(payload) is not StrategyIntentPromptPayload:
            return None
        if (
            payload.status != "ready"
            or payload.source != _STRATEGY_INTENT_PROMPT_SOURCE
            or payload.router_source != _STRATEGY_INTENT_ROUTER_SOURCE
            or type(payload.phase) is not str
            or payload.phase not in _STRATEGY_INTENT_PHASES
            or type(payload.intent) is not str
            or payload.intent not in _STRATEGY_INTENT_TEXT
            or type(payload.diagnostics) is not tuple
            or payload.diagnostics != ()
            or type(payload.text) is not str
            or not payload.text
            or type(payload.char_count) is not int
            or payload.char_count <= 0
            or payload.char_count != len(payload.text)
            or payload.char_count > 800
            or type(payload.candidate_relation_kinds) is not tuple
        ):
            return None
        from agents.action_structure import CANDIDATE_RELATION_KINDS
        from agents.strategy_intent_prompt import RELATION_PROMPT_TEXT

        relation_kinds = payload.candidate_relation_kinds
        if (
            any(type(kind) is not str or kind not in CANDIDATE_RELATION_KINDS for kind in relation_kinds)
            or len(set(relation_kinds)) != len(relation_kinds)
            or tuple(kind for kind in CANDIDATE_RELATION_KINDS if kind in relation_kinds) != relation_kinds
        ):
            return None
        lines = payload.text.split("\n")
        if len(lines) != (5 if relation_kinds else 4):
            return None
        if lines[0] != f"范围：{payload.phase}":
            return None
        if lines[1] != f"策略意图：{_STRATEGY_INTENT_TEXT[payload.intent]}":
            return None
        if lines[2] not in {
            f"公开依据：{reason_text}"
            for reason_text in _STRATEGY_INTENT_REASON_TEXTS[payload.intent]
        }:
            return None
        if lines[3] != _STRATEGY_INTENT_BOUNDARY:
            return None
        if relation_kinds and lines[4] != "公开候选关系：" + "；".join(
            RELATION_PROMPT_TEXT[kind] for kind in relation_kinds
        ):
            return None
        return payload

    @staticmethod
    def _validated_strategy_recommendation(payload: object, legal_actions: list[dict[str, object]]) -> "StrategyRecommendation | None":
        if payload is None:
            return None
        try:
            from agents.strategy_recommendation import StrategyRecommendation
        except Exception:
            return None
        if type(payload) is not StrategyRecommendation or payload.status != "ready" or payload.source != "public_strategy_recommendation_v2":
            return None
        if (
            type(payload.action_ids) is not tuple
            or type(payload.objective_codes) is not tuple
            or type(payload.countercheck_codes) is not tuple
            or type(payload.strategy_domains) is not tuple
        ):
            return None
        legal_ids: set[int] = set()
        for action in legal_actions:
            if not isinstance(action, dict) or type(action.get("action_id")) is not int:
                return None
            action_id = int(action["action_id"])
            if action_id in legal_ids:
                return None
            legal_ids.add(action_id)
        try:
            from agents.strategy_recommendation import (
                COUNTERCHECK_CODES,
                MAX_RECOMMENDATION_OBJECTIVES,
                OBJECTIVE_CODES,
                STRATEGY_DOMAINS,
            )
        except Exception:
            return None
        if (len(payload.action_ids) > 3 or len(set(payload.action_ids)) != len(payload.action_ids)
                or any(type(action_id) is not int or action_id not in legal_ids for action_id in payload.action_ids)
                or not payload.objective_codes or len(payload.objective_codes) > MAX_RECOMMENDATION_OBJECTIVES
                or not payload.countercheck_codes or len(payload.countercheck_codes) > 5
                or not payload.strategy_domains or len(payload.strategy_domains) > len(STRATEGY_DOMAINS)
                or tuple(item for item in OBJECTIVE_CODES if item in payload.objective_codes) != payload.objective_codes
                or tuple(item for item in COUNTERCHECK_CODES if item in payload.countercheck_codes) != payload.countercheck_codes
                or tuple(item for item in STRATEGY_DOMAINS if item in payload.strategy_domains) != payload.strategy_domains):
            return None
        return payload

    @staticmethod
    def _build_structured_prompt(
        my_info: dict[str, object],
        current_round: dict[str, object],
        other_players: list[dict[str, object]],
        history: dict[str, object],
        legal_actions: list[dict[str, object]],
        rag_context: dict[str, object] | None = None,
        hand_evaluation: dict[str, object] | None = None,
        card_tracking_summary: str | None = None,
        public_endgame_summary: str | None = None,
        phase_context: GamePhaseContext | None = None,
        card_confidence_prompt: "CardConfidencePromptPayload | None" = None,
        strategy_intent_prompt: "StrategyIntentPromptPayload | None" = None,
        strategy_recommendation: "StrategyRecommendation | None" = None,
        residual_structure_source_actions: list[dict[str, object]] | None = None,
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
    ) -> str:
        """Build the final Step-H structured prompt from public payloads."""
        lines: list[str] = []

        hand_cards = [str(t) for t in my_info.get("hand_cards", [])]
        hand_count = DeepSeekClient._coerce_int(my_info.get("hand_count"), default=len(hand_cards))
        current_level_rank = str(current_round.get("current_level_rank", ""))
        step_no = DeepSeekClient._coerce_int(current_round.get("step_no"), default=0)
        table_action = current_round.get("table_action")
        round_no = current_round.get("round_no", 0)
        constraint = str(current_round.get("constraint", "free"))
        raw_validated_recommendation = DeepSeekClient._validated_strategy_recommendation(
            strategy_recommendation,
            legal_actions,
        )
        contrast_source_actions = (
            residual_structure_source_actions
            if residual_structure_source_actions is not None
            else legal_actions
        )
        representative_contrasts = DeepSeekClient._prompt_candidate_contrasts(
            {"my_info": my_info, "current_round": current_round, "other_players": other_players, "history": history},
            contrast_source_actions,
            opening_formula_contrasts,
            strategy_recommendation=strategy_recommendation,
            rag_context=rag_context,
        )
        route_my_player_id = my_info.get("player_id")
        grouping_analysis = analyze_free_lead_grouping(
            {"my_info": my_info, "current_round": current_round},
            contrast_source_actions,
            route_my_player_id if type(route_my_player_id) is int else 0,
        )
        grouping_pairs = free_lead_grouping_comparison_pairs(
            {"my_info": my_info, "current_round": current_round},
            contrast_source_actions,
            route_my_player_id if type(route_my_player_id) is int else 0,
        )
        available_ids = {
            action.get("action_id")
            for action in legal_actions
            if type(action.get("action_id")) is int
        }
        card_tracking_action_ids: set[int] = set()
        card_tracking_relation_groups: list[tuple[int, int]] = []
        if card_tracking_summary:
            for line in card_tracking_summary.splitlines():
                if not (line.startswith("M3候选对照") or line.startswith("M3唯一归属核验")):
                    continue
                referenced = [int(value) for value in re.findall(r"action_id=(\d+)", line)]
                if referenced and set(referenced).issubset(available_ids):
                    card_tracking_action_ids.update(referenced)
                    if line.startswith("M3候选对照") and len(referenced) == 2:
                        card_tracking_relation_groups.append((referenced[0], referenced[1]))
        public_endgame_relation_groups: list[tuple[int, int]] = []
        if public_endgame_summary:
            for line in public_endgame_summary.splitlines():
                if not line.startswith("M5公开残局对照"):
                    continue
                referenced = [int(value) for value in re.findall(r"action_id=(\d+)", line)]
                if len(referenced) == 2 and set(referenced).issubset(available_ids):
                    public_endgame_relation_groups.append((referenced[0], referenced[1]))
                    card_tracking_action_ids.update(referenced)
        prompt_relation_groups = tuple(
            card_tracking_relation_groups
        ) + tuple(
            public_endgame_relation_groups
        ) + tuple(
            item.action_ids
            for item in (representative_contrasts or ())
            if set(item.action_ids).issubset(available_ids)
        ) + tuple(group for group in grouping_pairs if set(group).issubset(available_ids))
        recommendation_action_ids = (
            raw_validated_recommendation.action_ids
            if raw_validated_recommendation is not None
            else ()
        )
        protected_prompt_action_ids = tuple(dict.fromkeys(
            (*recommendation_action_ids, *sorted(card_tracking_action_ids))
        ))
        prompt_actions = DeepSeekClient._limit_prompt_actions(
            legal_actions,
            constraint=constraint,
            hand_count=hand_count,
            protected_action_ids=protected_prompt_action_ids,
            protected_relation_groups=prompt_relation_groups,
        )
        residual_facts = summarize_free_lead_residual_structures(
            {"my_info": my_info, "current_round": current_round},
            residual_structure_source_actions
            if residual_structure_source_actions is not None
            else prompt_actions,
        )
        residual_structures = (
            {item.action_id: item for item in residual_facts}
            if residual_facts is not None
            else None
        )
        candidate_facts = summarize_candidate_structures(
            {"my_info": my_info, "current_round": current_round, "other_players": other_players},
            prompt_actions,
        )
        candidate_facts_by_id = (
            {item.action_id: item for item in candidate_facts}
            if candidate_facts is not None
            else {}
        )
        opening_cross_pattern_guidance = DeepSeekClient._opening_cross_pattern_guidance(
            current_round=current_round,
            phase_context=phase_context,
            candidate_facts=candidate_facts,
            rag_context=rag_context,
        )
        all_contrasts = representative_contrasts
        prompt_action_ids = {
            action.get("action_id")
            for action in prompt_actions
            if type(action.get("action_id")) is int
        }
        visible_contrasts = []
        if all_contrasts is not None:
            # Keep bounded, complete comparisons. Bomb residuals may use two
            # representatives; no comparison is described unless both
            # original actions survived into the actual model candidate set.
            visible_contrasts.extend(
                item for item in all_contrasts
                if set(item.action_ids).issubset(prompt_action_ids)
            )

        lines.append("【任务与硬约束】")
        lines.append("- legal_actions 是唯一合法动作来源，只能从【候选动作】中选择一个 action_id。")
        lines.append("- 不得构造新动作、修改牌型、补充未知牌或假设隐藏信息。")
        lines.append("- 规则库只解释本项目规则口径，经验库只提供策略参考，均不能替代 legal_actions。")
        lines.append("")

        lines.append("【当前局面】")
        lines.append(
            f"当前玩家：{current_round.get('current_player_id', '?')}；"
            f"我的玩家ID：{my_info.get('player_id', '?')}；级牌：{current_level_rank}"
        )
        lines.append(f"第{round_no}轮第{step_no}步；我的剩余手牌：{hand_count}张")
        if phase_context is not None:
            lines.append(f"统一局面阶段：{phase_context.phase}")

        if table_action is None:
            lines.append("动作场景：首出/新一轮领出；桌面约束：无")
        else:
            ta = dict(table_action) if isinstance(table_action, dict) else {}
            ta_pattern = str(ta.get("declared_pattern", ""))
            ta_display = str(ta.get("display_text", ta_pattern))
            ta_carrier = [str(t) for t in ta.get("carrier_cards", [])]
            lines.append(f"动作场景：跟牌；桌面牌型：{ta_display}")
            if ta_carrier:
                ta_cards_text = " ".join(
                    _card_for_ai(t, current_level_rank, ta_pattern == "straight_flush")
                    for t in ta_carrier
                )
                lines.append(
                    f"桌面牌组：{ta_cards_text}"
                )
        my_team = str(my_info.get("team", ""))
        player_parts: list[str] = []
        for p in other_players:
            pid = p.get("player_id", "?")
            team = str(p.get("team", ""))
            hand_cnt = p.get("hand_count", 0)
            finished = bool(p.get("finished", False))
            finish_rank = p.get("finish_rank")

            relation = "队友" if team == my_team else "对手"

            if finished:
                rank_int = int(finish_rank) if finish_rank is not None else 0
                label = _FINISH_LABELS.get(rank_int, str(finish_rank))
                player_parts.append(f"玩家{pid}（{relation}）已完赛-{label}")
            else:
                player_parts.append(f"玩家{pid}（{relation}）剩余{hand_cnt}张")
        if player_parts:
            lines.append(f"队友/对手状态：{'；'.join(player_parts)}")
        lines.append("")

        lines.append("【手牌评估】")
        lines.extend(DeepSeekClient._format_hand_evaluation(hand_evaluation))
        lines.append("")

        lines.append("【记牌信息】")
        lines.extend(
            DeepSeekClient._format_card_tracking_summary(
                card_tracking_summary,
                candidate_action_ids={
                    int(action["action_id"])
                    for action in prompt_actions
                    if type(action.get("action_id")) is int
                },
            )
        )
        lines.append("")

        if public_endgame_summary:
            lines.append("【公开残局推演】")
            lines.extend(
                DeepSeekClient._format_public_endgame_summary(
                    public_endgame_summary,
                    candidate_action_ids={
                        int(action["action_id"])
                        for action in prompt_actions
                        if type(action.get("action_id")) is int
                    },
                )
            )
            lines.append("")

        validated_confidence = DeepSeekClient._validated_card_confidence_prompt(card_confidence_prompt)
        if validated_confidence is not None:
            lines.append("【残局牌面信念】")
            lines.append(validated_confidence.text)
            lines.append("")

        validated_recommendation = DeepSeekClient._validated_strategy_recommendation(
            strategy_recommendation, prompt_actions,
        )
        candidate_representatives = select_candidate_structure_representatives(
            candidate_facts,
            recommended_ids=validated_recommendation.action_ids if validated_recommendation is not None else (),
            contrast_action_id_groups=tuple(item.action_ids for item in visible_contrasts),
        ) if candidate_facts is not None else ()
        opening_cross_pattern_guidance_rendered = False
        if validated_recommendation is not None or opening_cross_pattern_guidance is not None:
            lines.append("【模型前建议】")
            if validated_recommendation is not None:
                if validated_recommendation.action_ids:
                    lines.append("优先核验候选 action_id：" + ", ".join(str(item) for item in validated_recommendation.action_ids))
                lines.append("策略域：" + "、".join(validated_recommendation.strategy_domains))
                objective_text = {
                    "finish_now": "核对一次出完", "protect_structure": "减少结构拆分",
                    "low_cost_probe": "降低试探成本", "preserve_control": "保留控制资源",
                    "contest_follow": "比较跟牌牌权", "support_teammate": "支援队友",
                    "block_opponent": "阻断危险对手", "manage_bomb_wildcard": "管理炸弹与通配",
                    "plan_endgame": "规划残局分组",
                }
                check_text = {
                    "check_public_urgency": "公开剩余张数和紧急性", "check_trick_ownership": "牌权计划",
                    "check_structure_loss": "组合与拆分损失", "check_control_cost": "控制资源消耗",
                    "check_rule_pressure": "规则压制关系",
                }
                lines.append("目标：" + "；".join(objective_text[item] for item in validated_recommendation.objective_codes))
                lines.append("反例检查：" + "；".join(check_text[item] for item in validated_recommendation.countercheck_codes))
            if opening_cross_pattern_guidance is not None:
                lines.append(opening_cross_pattern_guidance)
                opening_cross_pattern_guidance_rendered = True
            lines.append("")

        if visible_contrasts:
            lines.append("【公开关系对照】")
            if (
                not opening_cross_pattern_guidance_rendered
                and any(item.kind in _RESIDUAL_USE_RELATION_KINDS for item in visible_contrasts)
            ):
                lines.append(
                    "留牌边际判据：少出留下的牌只有在当前可识别的自然组合、可能回手/控制资源或公开协同用途足以抵消余组/孤张与资源成本时，才构成保留理由；"
                    "组合线索可能重叠、需拆别组或无后续牌权，并不自动等于高价值。若没有可证用途且留牌增加负担，另一侧又不损更高价值结构/控制资源，可有条件倾向一并打出；"
                    "价值不明时只比较当前可证成本，不断言未来无用、必然可走或能取得牌权，也不保证未来牌权。"
                )
            rendered_response_pairs: set[tuple[int, int]] = set()
            rendered_follow_contexts: set[tuple[object, ...]] = set()

            def append_follow_context(contrast: CandidateContrast) -> None:
                context_key = (
                    contrast.table_leader_relation,
                    contrast.table_leader_hand_count,
                    contrast.next_active_player_id,
                    contrast.next_active_player_relation,
                    contrast.next_active_player_hand_count,
                )
                if context_key not in rendered_follow_contexts:
                    rendered_follow_contexts.add(context_key)
                    lines.append(DeepSeekClient._follow_order_context(contrast))

            response_relation_kinds = {
                "follow_response_net_tradeoff",
                "teammate_control_resource", "teammate_table_choice",
                "danger_block_resource", "danger_block_choice",
            }
            for contrast in visible_contrasts:
                first_id, second_id = contrast.action_ids
                if contrast.kind in response_relation_kinds:
                    pair_key = tuple(sorted((first_id, second_id)))
                    if pair_key in rendered_response_pairs:
                        continue
                    rendered_response_pairs.add(pair_key)
                    tradeoff_text = DeepSeekClient._response_net_tradeoff_text(
                        contrast, candidate_facts_by_id,
                    )
                    if tradeoff_text:
                        lines.append(tradeoff_text)
                        append_follow_context(contrast)
                elif contrast.kind == "bomb_strength_resource":
                    lines.append(
                        f"自然炸弹强度/资源对照：action_id={first_id} 是较弱的自然炸弹，action_id={second_id} 是较强的自然炸弹；"
                        "比较少出留下的牌是否值得保留、炸弹强度/牌权机会与资源成本；不规定先出小炸或大炸。"
                        "一次出完、公开紧急性、队友/对手牌权和整体结构都可改变取舍。"
                        + DeepSeekClient._residual_use_contrast_text(first_id, second_id, candidate_facts_by_id)
                    )
                elif contrast.kind == "triple_bomb_split":
                    triple_rank, kicker_rank = (
                        contrast.rank_labels
                        if len(contrast.rank_labels) == 2
                        else ("未知", "未知")
                    )
                    bomb_fact = candidate_facts_by_id.get(second_id)
                    bomb_length = bomb_fact.bomb_length if bomb_fact is not None else None
                    length_text = f"{bomb_length}张" if bomb_length is not None else "多张"
                    lines.append(
                        f"三带二拆自然炸/对子成本：action_id={first_id} 是自然三带二，消耗三张{triple_rank}并带走一对{kicker_rank}；"
                        f"action_id={second_id} 是同点数{triple_rank}的当前合法{length_text}自然炸弹，不消耗{kicker_rank}对子，"
                        "并以炸弹牌型获得高于普通三带二的即时压制层级。三带二留下的同点余牌按下面当前余手线索核对；"
                        "不能据此保证以后能走或取得牌权。炸弹多花同点实体牌，三带二消耗所带对子；一次出完、公开紧急阻断、队友控桌和余组结构都可推翻局部倾向。"
                        + DeepSeekClient._residual_use_contrast_text(first_id, second_id, candidate_facts_by_id)
                    )
                elif contrast.kind == "bomb_wildcard_strength":
                    rank = contrast.rank_labels[0] if contrast.rank_labels else "目标点数"
                    natural_fact = candidate_facts_by_id.get(first_id)
                    wildcard_fact = candidate_facts_by_id.get(second_id)
                    natural_length = natural_fact.bomb_length if natural_fact is not None else None
                    wildcard_length = wildcard_fact.bomb_length if wildcard_fact is not None else None
                    natural_length_text = f"{natural_length}张" if natural_length is not None else "较短"
                    wildcard_length_text = f"{wildcard_length}张" if wildcard_length is not None else "更长"
                    lines.append(
                        f"自然炸/通配加长炸对照：action_id={first_id} 为{rank}点{natural_length_text}自然炸弹，"
                        f"action_id={second_id} 为{rank}点{wildcard_length_text}炸弹，多用一张逢人配换取更长炸弹的较强即时压制；"
                        "前者保留逢人配的其他合法用途，后者消耗该通配资源。只比较当前压制层级与出后实体余牌，不假定未来必然牌权；"
                        "急需更强压制、公开危险对手或本次出完可以支持花配，队友已控桌、结构损失和其他后续资源也可推翻。"
                        + DeepSeekClient._residual_use_contrast_text(first_id, second_id, candidate_facts_by_id)
                    )
                elif contrast.kind == "bomb_residual":
                    first_fact = candidate_facts_by_id.get(first_id)
                    second_fact = candidate_facts_by_id.get(second_id)
                    length_delta = (
                        abs(first_fact.bomb_length - second_fact.bomb_length)
                        if first_fact is not None and second_fact is not None
                        and first_fact.bomb_length is not None and second_fact.bomb_length is not None
                        else None
                    )
                    spend_text = f"少出{length_delta}张" if length_delta is not None else "少出若干张"
                    lines.append(
                        f"同点数自然炸弹残余用途对照：action_id={first_id} 与 action_id={second_id} 是不同长度的当前合法自然炸弹；"
                        f"较短侧{spend_text}；比较少出留下的牌是否值得保留，与多出牌的结构/资源成本及炸弹强度/牌权机会。"
                        + DeepSeekClient._residual_use_contrast_text(first_id, second_id, candidate_facts_by_id)
                        + "一次出完、公开紧急性、队友/对手协同、回手计划或更高价值结构均可改变取舍。"
                    )
                elif contrast.kind == "natural_pair_single":
                    teammate_text = (
                        f"队友公开剩余{contrast.teammate_hand_count}张"
                        if contrast.teammate_hand_count is not None
                        else "队友公开剩余张数未知"
                    )
                    lines.append(
                        f"同点数对子/单张对照：action_id={first_id} 的自然对子一次清理两张，"
                        f"action_id={second_id} 的单张会留下同点孤张；{teammate_text}，"
                        "结合传递牌型与清理低价值牌的取舍比较，不能推断队友暗牌。"
                        "立即出完、阻断或回手目标可以推翻这一对照。"
                    )
                elif contrast.kind == "natural_group_single":
                    teammate_text = (
                        f"队友公开剩余{contrast.teammate_hand_count}张"
                        if contrast.teammate_hand_count is not None
                        else "队友公开剩余张数未知"
                    )
                    lines.append(
                        f"自然组牌/普通单张对照：action_id={first_id} 是不拆已识别同点组合的自然对子或三张，"
                        f"action_id={second_id} 是其他点数的自然单张；比较该组牌的清理、单张成本与整体余组变化，{teammate_text}。"
                        "顺子等其他组合、立即出完、公开紧急性、协同或回手计划可推翻此比较；不把对子/三张设为固定先手。"
                    )
                elif contrast.kind == "natural_sequence_single":
                    lines.append(
                        f"自然顺子/其中单张对照：action_id={first_id} 是当前合法的自然顺子，"
                        f"action_id={second_id} 是该顺子所含点数之一的自然单张；比较一次清理完整顺子与低成本试探的取舍，"
                        "不因一张牌能参与顺子就自动保留，也不因顺子一次出牌更多就必然优先。"
                        "若顺子拆对子/三张、损害控制/回手、队友协同或公开紧急性要求，均可改变选择。"
                    )
                elif contrast.kind == "sequence_structure_loss":
                    lines.append(
                        f"自然顺子/连组与同点组对照：action_id={first_id} 会从一个仍可组成对子或三张的点数组取牌，"
                        f"action_id={second_id} 是该点数的自然整组候选；比较顺子清理、残余组数与后续组合，"
                        "不要只按当前张数下结论。立即出完、公开紧急性或更好的回手路线可以推翻局部保组倾向。"
                    )
                elif contrast.kind == "triple_split_repartition":
                    lines.append(
                        f"三张拆分/三带二对照：action_id={first_id} 从自然三张中出单张，公开余牌留下另一对子并仍有两组三张，"
                        f"可比较后续重组为两组三带二的结构空间；action_id={second_id} 是当前合法的自然三带二路线。"
                        "后续结构不保证取得牌权或一定形成，立即出完、公开紧急性和实际余组可推翻该软假设。"
                    )
                elif contrast.kind == "straight_flush_bomb_fragment":
                    lines.append(
                        f"同花顺/炸弹结构对照：action_id={first_id} 会拆动至少两个仍可组成自然炸弹的同点数组，"
                        f"action_id={second_id} 是其中一个当前合法的自然四炸。比较同花顺压制价值、拆组损失与一次消耗一组炸弹的代价；"
                        "不要求保留炸弹，立即出完、危险阻断和实际牌权需求可推翻。"
                    )
                elif contrast.kind == "straight_strength":
                    lines.append(
                        f"自然顺子强弱对照：action_id={first_id} 与 action_id={second_id} 是不同公开强度的自然顺子；"
                        "比较较小顺子的清理价值与较大顺子可能保留的后续压制路线，同时检查出后余组。"
                        "不推断对手持有何种顺子；立即出完、队友/对手紧急性、回手和整体结构均可改变顺序。"
                    )
                elif contrast.kind == "steel_plate_strength":
                    lines.append(
                        f"自然钢板强弱对照：action_id={first_id} 与 action_id={second_id} 是不同强度的自然钢板；"
                        "比较先清理较小钢板与保留较大钢板作为可能的后续压制，同时核对出后余组。"
                        "不据此推断对手持有小钢板；立即出完、队友/对手紧急性、回手和整体结构均可改变顺序。"
                    )
                elif contrast.kind == "triple_pair_kicker_gradient":
                    triple_rank, lower_pair_rank, higher_pair_rank = (
                        contrast.rank_labels
                        if len(contrast.rank_labels) == 3
                        else ("同一", "较低", "较高")
                    )
                    lines.append(
                        f"三带二携带对子成本：action_id={first_id} 使用较低自然对子{lower_pair_rank}，"
                        f"action_id={second_id} 使用较高自然对子{higher_pair_rank}；两侧共用{triple_rank}点自然三张主组。"
                        f"较低对子路线保留手中可核验的{higher_pair_rank}自然对子，较高对子路线会消耗它；"
                        "比较高对子带走后的剩余强组、实际余组与清理张数，不把固定大小顺序当公式。"
                        "出后结构、立即出完、公开紧急性、队友/对手牌权及回手价值都可推翻该可撤回假设。"
                    )
                elif contrast.kind == "natural_single_cost":
                    lines.append(
                        f"自然单张成本对照：action_id={first_id} 是较低且不拆已识别同点组的自然单张，"
                        f"action_id={second_id} 是较高的自然单张；比较清理成本与保留试探/回手路线，"
                        "仍须核对顺子等整体余组变化，不按固定点数排序，也不推断对手暗牌。队友或危险对手紧急、无回手资源或整体牌权计划可推翻此软比较。"
                    )
                elif contrast.kind == "single_control_resource":
                    lines.append(
                        f"单张资源对照：action_id={first_id} 清理结构安全自然小单，"
                        f"action_id={second_id} 消耗一张公开可识别的控制资源；比较低成本与争取/保留后续牌权，"
                        "不能保证夺回牌权，队友控桌、危险对手或回手计划可以推翻。"
                    )
                elif contrast.kind == "wildcard_resource":
                    lines.append(
                        f"通配资源对照：action_id={first_id} 与 action_id={second_id} 可形成相同公开声明牌型；"
                        "自然路线保留逢人配，通配路线可能改善余牌结构；比较资源成本与结构收益，"
                        "不把保留通配当硬规则，一次出完、阻断或牌权需求可以推翻。"
                    )
                elif contrast.kind == "opponent_single_control_cost":
                    low_rank, high_rank = (
                        contrast.rank_labels
                        if len(contrast.rank_labels) == 2
                        else ("普通单张", "控制单张")
                    )
                    leader_count = (
                        f"对手领出后公开余{contrast.table_leader_hand_count}张"
                        if contrast.table_leader_hand_count is not None
                        else "对手领出后的公开余张未知"
                    )
                    lines.append(
                        f"对手单张低/高跟牌成本：action_id={first_id} 是自然普通单张{low_rank}，"
                        f"action_id={second_id} 是控制资源自然单张{high_rank}；两者均是当前合法应手。{leader_count}，"
                        "较低应手保留控制牌，较高应手可能提高本轮争取牌权的力度但付出控制资源。"
                        "若对手公开接近走完，可值得花控制牌阻断；下一席顺序和队友状态也要核对，压住当前单张不保证后续牌权。"
                        "队友控桌、余手结构或控制资源另有可见用途时可反向选择。"
                    )
                if contrast.kind in {
                    "opponent_single_control_cost",
                }:
                    append_follow_context(contrast)
                if contrast.kind in {
                    "natural_pair_single", "natural_group_single", "natural_sequence_single", "sequence_structure_loss",
                    "triple_split_repartition", "straight_flush_bomb_fragment",
                    "straight_strength", "steel_plate_strength", "triple_pair_kicker_gradient",
                    "natural_single_cost", "single_control_resource", "wildcard_resource",
                    "triple_bomb_split", "bomb_wildcard_strength",
                    "opponent_single_control_cost",
                }:
                    lines.append(
                        DeepSeekClient._residual_use_contrast_text(
                            first_id, second_id, candidate_facts_by_id,
                        )
                    )
            lines.append("边界：这些是公开条件下的可撤回比较，不是动作指令。")
            lines.append("")

        validated_strategy_intent = DeepSeekClient._validated_strategy_intent_prompt(
            strategy_intent_prompt,
        )
        if validated_strategy_intent is not None:
            lines.append("【策略意图】")
            lines.append(validated_strategy_intent.text)
            lines.append("")

        lines.append("【场景标签】")
        lines.extend(DeepSeekClient._format_scene_tags(rag_context))
        lines.append("")

        lines.append("【候选动作】")
        if residual_structures is not None:
            lines.append(
                "出后用途仅按当前公开手牌与canonical carrier归纳；自然结构可重叠，未识别不等于无未来用途；"
                "不推断暗牌、未来合法出牌或牌权，估计余组不是动作指令。"
            )
        if len(prompt_actions) < len(legal_actions):
            lines.append(
                f"剪枝结果共{len(legal_actions)}个；按展示上限保留{len(prompt_actions)}个，关键动作优先保留。"
            )
        lines.extend(
            DeepSeekClient._grouped_legal_actions_summary(
                legal_actions=prompt_actions,
                constraint=constraint,
                step_no=step_no,
                hand_count=hand_count,
                current_level_rank=current_level_rank,
                residual_structures=residual_structures,
                compact_opening=(
                    constraint == "free"
                    and table_action is None
                    and phase_context is not None
                    and phase_context.phase == "opening"
                ),
            )
        )
        if candidate_facts is not None:
            compact_facts: list[str] = []
            for fact in candidate_representatives:
                if fact.pattern == "pass":
                    continue
                parts = [f"id={fact.action_id}", f"张数={fact.carrier_count}", f"余组≈{fact.estimated_remaining_rank_groups}", f"孤张={fact.residual_singleton_rank_count}"]
                if fact.finishes_hand:
                    parts.append("一次出完")
                if fact.fragments_played_rank_group:
                    parts.append("同点拆分")
                if fact.consumes_control_resource:
                    parts.append("消耗控制")
                if fact.bomb_length is not None:
                    parts.append(f"炸弹长度={fact.bomb_length}")
                compact_facts.append("；".join(parts))
            if compact_facts:
                lines.append("候选公开结构：" + " | ".join(compact_facts))

        visible_grouping_pairs = tuple(
            pair for pair in grouping_pairs
            if set(pair).issubset(prompt_action_ids)
        )
        visible_grouping_ids = tuple(dict.fromkeys(
            action_id for pair in visible_grouping_pairs for action_id in pair
        ))
        grouping_counts = grouping_analysis.counts_by_action_id() if grouping_analysis is not None else {}
        visible_group_counts = {
            action_id: grouping_counts[action_id]
            for action_id in visible_grouping_ids
            if action_id in grouping_counts
        }
        if (
            5 <= hand_count <= 8
            and constraint == "free"
            and table_action is None
            and grouping_analysis is not None
            and grouping_analysis.has_route_difference
            and visible_grouping_pairs
            and len(visible_group_counts) >= 2
        ):
            action_by_id = {
                action.get("action_id"): action
                for action in prompt_actions
                if type(action.get("action_id")) is int
            }
            pattern_labels = {
                "single": "单张", "pair": "对子", "triple": "三张",
                "triple_with_pair": "三带二", "straight": "顺子",
                "pair_straight": "连对", "steel_plate": "钢板", "bomb": "炸弹",
                "straight_flush": "同花顺", "joker_bomb": "天王炸",
            }
            lines.append("【残局出后分组路线】")
            lines.append(
                "假设此后重新取得自由领牌，按当前完整canonical动作可组成的本家余手路线，"
                "列出少量真实展示首手的后续最少动作组数；这只描述手牌可分组性，不保证取得牌权或必然走完。"
            )
            for action_id in visible_grouping_ids:
                action = action_by_id.get(action_id)
                fact = candidate_facts_by_id.get(action_id)
                if not isinstance(action, dict):
                    continue
                pattern = str(action.get("declared_pattern", ""))
                carrier = action.get("carrier_cards")
                carrier_count = len(carrier) if isinstance(carrier, list) else 0
                parts = [
                    f"action_id={action_id}",
                    f"首手={pattern_labels.get(pattern, pattern)}({carrier_count}张)",
                    f"出后剩余手牌最少后续组数={visible_group_counts[action_id]}",
                ]
                if fact is not None:
                    parts.append(f"残余孤张点数={fact.residual_singleton_rank_count}")
                    if fact.residual_hand_natural_pattern_kinds:
                        kinds = "/".join(fact.residual_hand_natural_pattern_kinds[:4])
                        parts.append(f"可识别自然结构线索={kinds}(可能重叠)")
                    if fact.consumes_control_resource:
                        parts.append("消耗控制资源")
                    if fact.uses_wildcard:
                        parts.append("消耗逢人配")
                    if fact.bomb_length is not None:
                        parts.append(f"消耗{fact.bomb_length}张炸弹")
                lines.append("；".join(parts))
            lines.append(
                "分组少不自动优先：一次出完、队友或危险对手公开紧急、可说明的控制/回手资源与结构代价均可推翻；"
                "自然组合线索可重叠，未知未来牌权保持未知。"
            )

        lines.append("")

        rule_hits = DeepSeekClient._rag_items(rag_context, "rule_hits")
        experience_hits = DeepSeekClient._rag_items(rag_context, "experience_hits")
        lines.append("【规则库依据】")
        lines.append("仅用于解释本项目规则口径，不能替代 legal_actions 或扩展候选动作。")
        lines.extend(DeepSeekClient._format_rag_hits(rule_hits))
        lines.append("")

        lines.append("【经验库依据】")
        lines.append("仅作为策略倾向参考，不是强制命令，不能覆盖规则或候选动作。")
        lines.extend(DeepSeekClient._format_rag_hits(experience_hits))
        lines.append("")

        lines.append("【输出格式】")
        lines.append('只输出 JSON：{"action_id": <候选动作中的 action_id 原值>, "reason": "<20字以内理由>"}')
        lines.append('示例：{"action_id": 123, "reason": "保留控制牌并减少手数"}')
        lines.append("不要输出候选列表以外的 action_id。")

        return "\n".join(lines)

    @staticmethod
    def _pattern_counts_summary(legal_actions: list[dict[str, object]], *, max_items: int = 10) -> str:
        counter = Counter(str(action.get("declared_pattern")) for action in legal_actions)
        if not counter:
            return "(none)"

        items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        parts = [f"{name}×{count}" for name, count in items[:max_items]]
        if len(items) > max_items:
            parts.append(f"...+{len(items) - max_items}")
        return ", ".join(parts)

    def _stream_sse(
        self,
        req: urllib_request.Request,
        timeout: float,
        *,
        decision_deadline: DecisionDeadline | None = None,
    ) -> tuple[str, str]:
        """Send a streaming request and accumulate content + reasoning_content from SSE chunks.

        Returns (content, reasoning_content).  Both are concatenated from all deltas.
        """
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        if decision_deadline is not None:
            decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
            timeout = min(
                timeout,
                decision_deadline.remaining(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS),
            )
        if self._transport is _default_transport:
            response_stream = self._transport(  # type: ignore[call-arg]
                req,
                timeout,
                decision_deadline=decision_deadline,
            )
        else:
            response_stream = self._transport(req, timeout)
        if isinstance(response_stream, bytes):
            lines: Iterable[str | bytes] = response_stream.decode("utf-8").splitlines()
        elif isinstance(response_stream, str):
            lines = response_stream.splitlines()
        else:
            lines = response_stream

        iterator = iter(lines)
        terminal_received = False
        try:
            for raw_line in iterator:
                if decision_deadline is not None:
                    decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8")
                elif not isinstance(raw_line, str):
                    raise RuntimeError("deepseek streaming transport returned an invalid line")
                if decision_deadline is not None:
                    decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
                line = raw_line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    terminal_received = True
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices or not isinstance(choices[0], dict):
                    continue
                delta = choices[0].get("delta")
                if not isinstance(delta, dict):
                    continue
                rc = delta.get("reasoning_content")
                if isinstance(rc, str):
                    reasoning_parts.append(rc)
                c = delta.get("content")
                if isinstance(c, str):
                    content_parts.append(c)
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                close()

        if not terminal_received:
            raise RuntimeError("deepseek streaming response ended without its terminal event")
        return ("".join(content_parts), "".join(reasoning_parts))

    def suggest_action_id(
        self,
        *,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        prompt_actions: list[dict[str, object]] | None = None,
        rag_context: dict[str, object] | None = None,
        hand_evaluation: dict[str, object] | None = None,
        card_tracking_summary: str | None = None,
        public_endgame_summary: str | None = None,
        phase_context: GamePhaseContext | None = None,
        verbose: bool = False,
        debug_prefix: str = "[DeepSeek]",
        card_confidence_prompt: "CardConfidencePromptPayload | None" = None,
        strategy_intent_prompt: "StrategyIntentPromptPayload | None" = None,
        strategy_recommendation: "StrategyRecommendation | None" = None,
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
        decision_deadline: DecisionDeadline | None = None,
        request_evidence_observer: Callable[[bytes, dict[str, object]], None] | None = None,
    ) -> DeepSeekSuggestion:
        current_round = dict(observation.get("current_round", {}))
        step_no = self._coerce_int(current_round.get("step_no"), default=0)
        current_player_id = self._coerce_int(current_round.get("current_player_id"), default=0)
        current_level_rank = str(current_round.get("current_level_rank", ""))

        my_info = dict(observation.get("my_info", {}))
        other_players = list(observation.get("other_players", []))
        history = dict(observation.get("history", {}))
        hand_count = self._coerce_int(my_info.get("hand_count"), default=0)
        phase_context = phase_context or classify_game_phase(observation)

        constraint = str(current_round.get("constraint", "free"))
        if prompt_actions is None:
            pruned_actions = self.prepare_prompt_actions(
                legal_actions,
                constraint=constraint,
                step_no=step_no,
                hand_count=hand_count,
                phase_context=phase_context,
                strategy_recommendation=strategy_recommendation,
                observation=observation,
                opening_formula_contrasts=opening_formula_contrasts,
                rag_context=rag_context,
            )
        else:
            supplied_actions = self._canonical_subset_actions(
                legal_actions,
                list(prompt_actions),
            )
            if supplied_actions is None:
                return DeepSeekSuggestion(action_id=None, reasoning=None)
            validated_recommendation = self._validated_strategy_recommendation(
                strategy_recommendation,
                legal_actions,
            )
            protected_ids = (
                validated_recommendation.action_ids
                if validated_recommendation is not None
                else ()
            )
            contrasts = self._prompt_candidate_contrasts(
                observation,
                legal_actions,
                opening_formula_contrasts,
                strategy_recommendation=strategy_recommendation,
                rag_context=rag_context,
            )
            relation_groups = (
                tuple(item.action_ids for item in contrasts)
                if contrasts is not None
                else ()
            )
            relation_groups = tuple(dict.fromkeys(
                relation_groups
                + free_lead_grouping_comparison_pairs(
                    observation,
                    legal_actions,
                    self._coerce_int(my_info.get("player_id"), default=0),
                )
            ))
            if public_endgame_summary:
                legal_ids = {
                    int(action["action_id"])
                    for action in legal_actions
                    if type(action.get("action_id")) is int
                }
                public_endgame_groups = []
                for line in public_endgame_summary.splitlines():
                    if not line.startswith("M5公开残局对照"):
                        continue
                    referenced = [
                        int(value) for value in re.findall(r"action_id=(\d+)", line)
                    ]
                    if len(referenced) == 2 and set(referenced).issubset(legal_ids):
                        public_endgame_groups.append((referenced[0], referenced[1]))
                relation_groups = tuple(dict.fromkeys(
                    relation_groups + tuple(public_endgame_groups)
                ))
            opening_route_ids = self._opening_pattern_representative_ids(
                observation,
                legal_actions,
                phase_context,
            )
            protected_actions = self._protected_actions_by_id(
                legal_actions,
                protected_ids,
            )
            opening_route_actions = self._protected_actions_by_id(
                legal_actions,
                opening_route_ids,
                max_count=MAX_OPENING_PATTERN_REPRESENTATIVES,
            )
            relation_actions = self._relation_actions_by_groups(legal_actions, relation_groups)
            present_ids = {int(action["action_id"]) for action in supplied_actions}
            candidate_actions = supplied_actions + [
                action for action in protected_actions
                if int(action["action_id"]) not in present_ids
            ]
            present_ids.update(int(action["action_id"]) for action in protected_actions)
            candidate_actions.extend([
                action for action in opening_route_actions
                if int(action["action_id"]) not in present_ids
            ])
            present_ids.update(int(action["action_id"]) for action in opening_route_actions)
            candidate_actions.extend([
                action for action in relation_actions
                if int(action["action_id"]) not in present_ids
            ])
            pruned_actions = self._limit_prompt_actions(
                candidate_actions,
                constraint=constraint,
                hand_count=hand_count,
                protected_action_ids=protected_ids,
                protected_relation_groups=relation_groups,
                protected_opening_action_ids=opening_route_ids,
            )

        user_message = self._build_structured_prompt(
            my_info=my_info,
            current_round=current_round,
            other_players=other_players,
            history=history,
            legal_actions=pruned_actions,
            rag_context=rag_context,
            hand_evaluation=hand_evaluation,
            card_tracking_summary=card_tracking_summary,
            public_endgame_summary=public_endgame_summary,
            phase_context=phase_context,
            card_confidence_prompt=card_confidence_prompt,
            strategy_intent_prompt=strategy_intent_prompt,
            strategy_recommendation=strategy_recommendation,
            residual_structure_source_actions=legal_actions,
            opening_formula_contrasts=opening_formula_contrasts,
        )

        if verbose:
            constraint = current_round.get("constraint")
            table_action = current_round.get("table_action")
            me_hand_count = hand_count
            me_remaining_singles = self._coerce_int(my_info.get("remaining_single_card_count"), default=0)

            rag_rule_count = 0
            rag_experience_count = 0
            if isinstance(rag_context, dict):
                rule_items = rag_context.get("rule_hits", [])
                experience_items = rag_context.get("experience_hits", [])
                rag_rule_count = len(list(rule_items))
                rag_experience_count = len(list(experience_items))

            print(
                f"{debug_prefix} 请求: url={self._base_url}/chat/completions model={self._model} "
                f"step_no={step_no} current_player_id={current_player_id} level={current_level_rank}",
                flush=True,
            )
            print(
                f"{debug_prefix} 请求摘要: constraint={constraint} table_action={table_action} "
                f"hand_count={me_hand_count} remaining_single_card_count={me_remaining_singles} "
                f"legal_actions={len(legal_actions)}→剪枝后={len(pruned_actions)} "
                f"patterns=({self._pattern_counts_summary(legal_actions)}) "
                f"rag(rule={rag_rule_count}, exp={rag_experience_count})",
                flush=True,
            )
            summary_lines = self._grouped_legal_actions_summary(
                pruned_actions,
                str(current_round.get("constraint", "free")),
                step_no,
                hand_count,
                current_level_rank,
            )
            for line in summary_lines:
                print(f"{debug_prefix} {line}", flush=True)

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是掼蛋智能体，根据给定的牌局信息选择最优合法动作。"
                        "只返回 JSON：{\"action_id\": <候选 action_id 原值>, \"reason\": <简短字符串>}"
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "temperature": 0,
            "stream": True,
        }

        req = urllib_request.Request(
            url=f"{self._base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        visible_prompt_ids = {
            action.get("action_id") for action in pruned_actions
            if type(action.get("action_id")) is int
        }
        request_metadata = {
            "model": self._model,
            "candidate_action_ids": [
                action.get("action_id") for action in pruned_actions
                if type(action.get("action_id")) is int
            ],
            "recommended_action_ids": [
                action_id for action_id in getattr(strategy_recommendation, "action_ids", ())
                if type(action_id) is int and action_id in visible_prompt_ids
            ],
            "relation_references": self._prompt_relation_references(user_message, pruned_actions),
        }

        # --- streaming request with retry ---
        last_error: Exception | None = None
        content: str = ""
        reasoning_text: str | None = None
        max_attempts = 1 + self._max_retries
        stream_completed = False
        for attempt in range(max_attempts):
            try:
                if decision_deadline is not None:
                    decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)
                if request_evidence_observer is not None and isinstance(req.data, bytes):
                    try:
                        request_evidence_observer(req.data, request_metadata)
                    except Exception:
                        # Owner evidence is best effort and must not alter the
                        # existing model/fallback/action or ACK transaction.
                        pass
                if decision_deadline is None:
                    # Keep the longstanding two-argument override contract for
                    # test transports and client subclasses.  The deadline
                    # keyword is only needed by the opt-in bounded path.
                    content, raw_reasoning = self._stream_sse(
                        req,
                        self._timeout_seconds,
                    )
                else:
                    content, raw_reasoning = self._stream_sse(
                        req,
                        self._timeout_seconds,
                        decision_deadline=decision_deadline,
                    )
                reasoning_text = raw_reasoning.strip() if raw_reasoning.strip() else None
                stream_completed = True
                break
            except (TimeoutError, OSError) as exc:
                last_error = exc
                retry_window_open = (
                    decision_deadline is None
                    or decision_deadline.remaining(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS) > 2.0
                )
                if attempt + 1 < max_attempts and retry_window_open:
                    if verbose:
                        print(
                            f"{debug_prefix} 请求失败({exc.__class__.__name__})，2秒后重试"
                            f"({attempt + 1}/{max_attempts})...",
                            flush=True,
                        )
                    time.sleep(2)
        if not stream_completed:
            if last_error is not None:
                raise last_error
            raise RuntimeError("deepseek streaming request returned no response")

        if decision_deadline is not None:
            decision_deadline.check(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS)

        if verbose and reasoning_text:
            print(f"{debug_prefix} 推理过程: {reasoning_text}", flush=True)

        if verbose:
            print(f"{debug_prefix} 模型输出(content): {content}", flush=True)

        # --- parse action_id from accumulated content ---
        parsed = self._extract_json(content)
        action_id = self._extract_action_id(parsed)
        if action_id is None:
            action_id = self._match_action_id_by_signature(parsed, legal_actions)

        if action_id is None:
            if verbose:
                print(f"{debug_prefix} 未能从模型输出解析出 action_id", flush=True)
            return DeepSeekSuggestion(action_id=None, reasoning=reasoning_text)

        legal_ids = {
            self._coerce_int(action.get("action_id"), default=-1)
            for action in pruned_actions
        }
        if int(action_id) not in legal_ids:
            if verbose:
                print(f"{debug_prefix} action_id={action_id} 不在 prompt candidates 中，忽略", flush=True)
            return DeepSeekSuggestion(action_id=None, reasoning=reasoning_text)

        if verbose:
            print(f"{debug_prefix} 解析得到 action_id={int(action_id)} (合法)", flush=True)
        return DeepSeekSuggestion(action_id=int(action_id), reasoning=reasoning_text)

    @staticmethod
    def _prompt_relation_references(
        user_message: str,
        prompt_actions: list[dict[str, object]],
    ) -> list[list[int]]:
        """Return only action-ID references actually printed in prompt relation lines."""

        visible = {
            action["action_id"] for action in prompt_actions
            if type(action.get("action_id")) is int
        }
        references: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()
        for line in user_message.splitlines():
            ids = tuple(dict.fromkeys(
                int(match.group(1))
                for match in re.finditer(r"action_id=([0-9]+)", line)
                if int(match.group(1)) in visible
            ))
            if len(ids) < 2 or ids in seen:
                continue
            seen.add(ids)
            references.append(list(ids))
        return references
