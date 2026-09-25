"""Minimal DeepSeek client for legal-action selection support.

Step D boundary:
- This client must NOT depend on engine internal state objects.
- It only consumes the public payloads returned by `observe()` and `legal_actions()`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import time
from typing import TYPE_CHECKING, Callable, Protocol
from urllib import request as urllib_request

from agents.action_structure import (
    CANDIDATE_RELATION_KINDS,
    CandidateContrast,
    CandidateStructure,
    FreeLeadResidualStructure,
    representative_candidate_contrasts,
    select_candidate_structure_representatives,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
    summarize_free_lead_residual_structures,
)
from agents.game_phase import GamePhaseContext, classify_game_phase, is_endgame_phase
from agents.opening_strategy import MAX_OPENING_FORMULA_CONTRASTS

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
        "bomb_residual",
    }
)

# Prompt limits are deliberately centralized so context growth stays auditable.
PROMPT_MAX_CANDIDATE_ACTIONS = 80
PROMPT_MAX_ACTION_DISPLAY_CHARS = 96
PROMPT_MAX_ACTION_CARRIER_CHARS = 160
PROMPT_MAX_WILDCARD_INFO_CHARS = 160
PROMPT_MAX_RAG_HITS_PER_LAYER = 3
PROMPT_MAX_RAG_TITLE_CHARS = 60
PROMPT_MAX_RAG_BODY_CHARS = 180
PROMPT_MAX_CARD_TRACKING_CHARS = 600

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

    def __call__(self, request: urllib_request.Request, timeout: float) -> str:
        ...


def _default_transport(req: urllib_request.Request, timeout: float) -> str:
    with urllib_request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


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
    ) -> str:
        action_id = action.get("action_id")
        brief = DeepSeekClient._compact_action_text(
            action,
            current_level_rank,
            str(action.get("declared_pattern", "")) == "straight_flush",
        )
        pattern = str(action.get("declared_pattern", ""))
        wildcard_count = DeepSeekClient._coerce_int(action.get("wildcard_count"), default=0)
        display_text = DeepSeekClient._bounded_text(
            str(action.get("display_text", brief)),
            PROMPT_MAX_ACTION_DISPLAY_CHARS,
        )
        carrier_text = DeepSeekClient._bounded_text(
            DeepSeekClient._compact_json(action.get("carrier_cards", [])),
            PROMPT_MAX_ACTION_CARRIER_CHARS,
        )
        action_id_text = DeepSeekClient._compact_json(action_id)
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
    ) -> tuple[dict[str, object], ...]:
        """Resolve a small, exact canonical protection set or fail closed.

        A recommendation may name only original action IDs.  This helper is
        deliberately stricter than the display limiter: malformed IDs, a
        duplicate canonical ID, or a missing action disable protection rather
        than allowing a caller to smuggle a replacement action into the prompt.
        """
        if (
            type(protected_action_ids) is not tuple
            or len(protected_action_ids) > 3
            or len(set(protected_action_ids)) != len(protected_action_ids)
            or any(type(action_id) is not int for action_id in protected_action_ids)
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
        protected_actions = list(protected) + [
            action for action in relation_actions if action not in protected
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
    ) -> list[dict[str, object]]:
        """Return a bounded, representative prompt view of canonical actions.

        The final display layer has a stricter contract than first-pass pruning:
        it never exceeds the prompt budget.  Free leads reserve the smallest
        natural single and pair before allocating the remaining budget.  This
        prevents a large run, pressure, or wildcard group from hiding the
        transition choices that the model needs to compare.  The remaining
        slots are allocated deterministically by category: finishing actions,
        pressure actions, wildcard actions, then ordinary actions.  A category
        may therefore be represented rather than copied in full during an
        overflow; source order is retained in the returned view.
        """

        protected_actions = DeepSeekClient._protected_actions_by_id(
            actions,
            protected_action_ids,
        )
        relation_actions = DeepSeekClient._relation_actions_by_groups(
            actions,
            protected_relation_groups,
        )
        protected_display_actions = list(protected_actions) + [
            action for action in relation_actions if action not in protected_actions
        ]
        unique_actions = DeepSeekClient._prefer_protected_actions(
            actions,
            tuple(protected_display_actions),
        )
        if len(unique_actions) <= PROMPT_MAX_CANDIDATE_ACTIONS:
            return unique_actions

        selected: set[tuple[object, ...]] = set()

        def reserve(action: dict[str, object]) -> None:
            if len(selected) < PROMPT_MAX_CANDIDATE_ACTIONS:
                selected.add(DeepSeekClient._action_signature(action))

        # Keep the first-pass transition recall meaningful in the final prompt.
        # These are representatives, not a new legality or strategy selector.
        if constraint == "free":
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
        else:
            passes = sorted(
                [action for action in unique_actions if DeepSeekClient._is_pass_action(action)],
                key=DeepSeekClient._prune_sort_key,
            )
            if passes:
                reserve(passes[0])

        # A validated model-before recommendation names at most three original
        # canonical actions.  Reserve those exact IDs before the established
        # bounded category fill, without changing the overall 80-action cap.
        # This is a candidate-visibility guarantee, not an action selector.
        for action in protected_display_actions:
            reserve(action)

        def add_category(predicate: Callable[[dict[str, object]], bool]) -> None:
            for action in sorted(unique_actions, key=DeepSeekClient._prune_sort_key):
                if len(selected) >= PROMPT_MAX_CANDIDATE_ACTIONS:
                    return
                if predicate(action):
                    reserve(action)

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
        )

    @staticmethod
    def _prompt_candidate_contrasts(
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
    ) -> tuple[CandidateContrast, ...] | None:
        """Merge bounded, validated local-formula blockers with display contrasts.

        The opening formula evaluates the complete relation set, while the
        ordinary prompt uses a smaller representative subset. If a complete
        relation was the reason a local action was deferred, carry that exact
        canonical contrast into candidate protection and the final prompt.
        """

        full_contrasts = summarize_candidate_contrasts(observation, legal_actions)
        representatives = representative_candidate_contrasts(observation, legal_actions)
        if full_contrasts is None or representatives is None:
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

        merged: list[CandidateContrast] = []
        seen: set[tuple[str, tuple[int, int]]] = set()
        for contrast in (*opening_formula_contrasts, *representatives):
            key = (contrast.kind, contrast.action_ids)
            if key in seen:
                continue
            seen.add(key)
            merged.append(contrast)
        return tuple(merged)

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
            )
            if observation is not None
            else ()
        )
        protected_relation_groups = (
            tuple(item.action_ids for item in contrasts)
            if contrasts is not None
            else ()
        )
        first_pass = DeepSeekClient._prune_legal_actions(
            legal_actions,
            constraint,
            step_no=step_no,
            hand_count=hand_count,
            phase_context=phase_context,
            protected_action_ids=protected_ids,
            protected_relation_groups=protected_relation_groups,
        )
        return DeepSeekClient._limit_prompt_actions(
            first_pass,
            constraint=constraint,
            hand_count=hand_count,
            protected_action_ids=protected_ids,
            protected_relation_groups=protected_relation_groups,
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
    def _format_card_tracking_summary(card_tracking_summary: str | None) -> list[str]:
        if not card_tracking_summary:
            return ["（无）"]
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
        )
        available_ids = {
            action.get("action_id")
            for action in legal_actions
            if type(action.get("action_id")) is int
        }
        prompt_relation_groups = tuple(
            item.action_ids
            for item in (representative_contrasts or ())
            if set(item.action_ids).issubset(available_ids)
        )
        prompt_actions = DeepSeekClient._limit_prompt_actions(
            legal_actions,
            constraint=constraint,
            hand_count=hand_count,
            protected_action_ids=(
                raw_validated_recommendation.action_ids
                if raw_validated_recommendation is not None
                else ()
            ),
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
        lines.extend(DeepSeekClient._format_card_tracking_summary(card_tracking_summary))
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
        if validated_recommendation is not None:
            lines.append("【模型前建议】")
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
            lines.append("")

        if visible_contrasts:
            lines.append("【公开关系对照】")
            if any(item.kind in _RESIDUAL_USE_RELATION_KINDS for item in visible_contrasts):
                lines.append(
                    "留牌边际判据：少出留下的牌只有在当前可识别的自然组合、可能回手/控制资源或公开协同用途足以抵消余组/孤张与资源成本时，才构成保留理由；"
                    "组合线索可能重叠、需拆别组或无后续牌权，并不自动等于高价值。若没有可证用途且留牌增加负担，另一侧又不损更高价值结构/控制资源，可有条件倾向一并打出；"
                    "价值不明时只比较当前可证成本，不断言未来无用、必然可走或能取得牌权，也不保证未来牌权。"
                )
            for contrast in visible_contrasts:
                first_id, second_id = contrast.action_ids
                if contrast.kind == "bomb_strength_resource":
                    lines.append(
                        f"自然炸弹强度/资源对照：action_id={first_id} 是较弱的自然炸弹，action_id={second_id} 是较强的自然炸弹；"
                        "比较少出留下的牌是否值得保留、炸弹强度/牌权机会与资源成本；不规定先出小炸或大炸。"
                        "一次出完、公开紧急性、队友/对手牌权和整体结构都可改变取舍。"
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
                    lines.append(
                        f"三带二携带对子梯度：action_id={first_id} 与 action_id={second_id} 使用同一自然三张主组、不同自然对子；"
                        "比较带走中间对子后保留大小对子路线与当前余组，不把固定大小顺序当公式。"
                        "出后结构、立即出完、公开紧急性及回手价值都可推翻该可撤回假设。"
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
                elif contrast.kind == "teammate_control_resource":
                    lines.append(
                        f"队友控桌对照：action_id={first_id} 为pass，action_id={second_id} 消耗控制资源争夺牌权；"
                        f"队友公开剩余{contrast.teammate_hand_count}张，比较让队友继续与本家争取牌权，"
                        "不能推断队友暗牌；公开危险对手或本家走牌计划可推翻。"
                    )
                elif contrast.kind == "teammate_table_choice":
                    lines.append(
                        f"队友控桌对照：action_id={first_id} 为pass，action_id={second_id} 是本家可合法接牌；"
                        f"队友公开剩余{contrast.teammate_hand_count}张，比较让队友继续与本家接牌，"
                        "不能推断队友暗牌；公开危险对手或本家走牌计划可推翻。"
                    )
                elif contrast.kind == "danger_block_resource":
                    lines.append(
                        f"危险对手对照：action_id={first_id} 为pass，action_id={second_id} 消耗控制资源尝试阻断；"
                        "按公开剩余张数比较阻断收益和控制成本，不保证压住后续牌权，队友更紧急或代价过高可推翻。"
                    )
                elif contrast.kind == "danger_block_choice":
                    lines.append(
                        f"危险对手对照：action_id={first_id} 为pass，action_id={second_id} 是本家可合法压制候选；"
                        "比较公开阻断机会与牌型/结构成本，不保证后续牌权，队友更紧急或代价过高可推翻。"
                    )
                if contrast.kind in {
                    "natural_pair_single", "natural_group_single", "natural_sequence_single", "sequence_structure_loss",
                    "triple_split_repartition", "straight_flush_bomb_fragment",
                    "straight_strength", "steel_plate_strength", "triple_pair_kicker_gradient",
                    "natural_single_cost", "single_control_resource", "wildcard_resource",
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

    def _stream_sse(self, req: urllib_request.Request, timeout: float) -> tuple[str, str]:
        """Send a streaming request and accumulate content + reasoning_content from SSE chunks.

        Returns (content, reasoning_content).  Both are concatenated from all deltas.
        """
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        response_text = self._transport(req, timeout)
        if isinstance(response_text, bytes):
            response_text = response_text.decode("utf-8")

        for raw_line in str(response_text).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
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
        phase_context: GamePhaseContext | None = None,
        verbose: bool = False,
        debug_prefix: str = "[DeepSeek]",
        card_confidence_prompt: "CardConfidencePromptPayload | None" = None,
        strategy_intent_prompt: "StrategyIntentPromptPayload | None" = None,
        strategy_recommendation: "StrategyRecommendation | None" = None,
        opening_formula_contrasts: tuple[CandidateContrast, ...] = (),
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
            )
            relation_groups = (
                tuple(item.action_ids for item in contrasts)
                if contrasts is not None
                else ()
            )
            protected_actions = self._protected_actions_by_id(
                legal_actions,
                protected_ids,
            )
            relation_actions = self._relation_actions_by_groups(legal_actions, relation_groups)
            present_ids = {int(action["action_id"]) for action in supplied_actions}
            candidate_actions = supplied_actions + [
                action for action in protected_actions
                if int(action["action_id"]) not in present_ids
            ]
            present_ids.update(int(action["action_id"]) for action in protected_actions)
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

        # --- streaming request with retry ---
        last_error: Exception | None = None
        content: str = ""
        reasoning_text: str | None = None
        max_attempts = 1 + self._max_retries
        for attempt in range(max_attempts):
            try:
                content, raw_reasoning = self._stream_sse(req, self._timeout_seconds)
                reasoning_text = raw_reasoning.strip() if raw_reasoning.strip() else None
                break
            except (TimeoutError, OSError) as exc:
                last_error = exc
                if attempt + 1 < max_attempts:
                    if verbose:
                        print(
                            f"{debug_prefix} 请求失败({exc.__class__.__name__})，2秒后重试"
                            f"({attempt + 1}/{max_attempts})...",
                            flush=True,
                        )
                    time.sleep(2)
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("deepseek streaming request returned no response")

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
