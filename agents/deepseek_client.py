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
from typing import TYPE_CHECKING, Protocol
from urllib import request as urllib_request

from agents.game_phase import GamePhaseContext, classify_game_phase, is_endgame_phase

if TYPE_CHECKING:
    from agents.card_confidence_prompt import CardConfidencePromptPayload

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
    def _action_summary_entry(action: dict[str, object], current_level_rank: str) -> str:
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
        prefix = f"#{action_id} " if action_id is not None else ""
        return prefix + " | ".join(fields)

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
            items = [DeepSeekClient._action_summary_entry(action, current_level_rank) for action in unique_actions]
            lines.append(f"{label}：{'、'.join(items)}")

        return lines

    @staticmethod
    def _limit_prompt_actions(
        actions: list[dict[str, object]],
        *,
        constraint: str,
        hand_count: int | None,
    ) -> list[dict[str, object]]:
        """Bound ordinary prompt candidates while retaining every critical action."""

        if len(actions) <= PROMPT_MAX_CANDIDATE_ACTIONS:
            return list(actions)

        critical_indexes = {
            index
            for index, action in enumerate(actions)
            if DeepSeekClient._is_finishing_action(action, hand_count)
            or DeepSeekClient._is_pressure_action(action)
            or DeepSeekClient._has_wildcard(action)
            or (constraint != "free" and DeepSeekClient._is_pass_action(action))
        }
        if len(critical_indexes) >= PROMPT_MAX_CANDIDATE_ACTIONS:
            return [action for index, action in enumerate(actions) if index in critical_indexes]

        ordinary_budget = PROMPT_MAX_CANDIDATE_ACTIONS - len(critical_indexes)
        selected_indexes = set(critical_indexes)
        for index in range(len(actions)):
            if index in selected_indexes:
                continue
            selected_indexes.add(index)
            ordinary_budget -= 1
            if ordinary_budget == 0:
                break
        return [action for index, action in enumerate(actions) if index in selected_indexes]

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

        return kept or list(legal_actions)

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
        source = str(item.get("source_id", "unknown"))
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
        title = DeepSeekClient._bounded_text(title or source, PROMPT_MAX_RAG_TITLE_CHARS)
        body = DeepSeekClient._bounded_text(" ".join(body_lines), PROMPT_MAX_RAG_BODY_CHARS)
        return title, body

    @staticmethod
    def _format_rag_hits(items: list[dict[str, object]]) -> list[str]:
        if not items:
            return ["（无）"]
        lines: list[str] = []
        for item in items[:PROMPT_MAX_RAG_HITS_PER_LAYER]:
            source = str(item.get("source_id", "unknown"))
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            topic = str(metadata.get("topic", ""))
            title, body = DeepSeekClient._rag_title_and_body(item)
            topic_text = f"；topic={topic}" if topic else ""
            body_text = f"：{body}" if body else ""
            lines.append(f"- {title}（id={source}{topic_text}）{body_text}")
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
        prompt_actions = DeepSeekClient._limit_prompt_actions(
            legal_actions,
            constraint=constraint,
            hand_count=hand_count,
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

        lines.append("【场景标签】")
        lines.extend(DeepSeekClient._format_scene_tags(rag_context))
        lines.append("")

        lines.append("【候选动作】")
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
            )
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
            pruned_actions = self._prune_legal_actions(
                legal_actions,
                constraint,
                step_no=step_no,
                hand_count=hand_count,
                phase_context=phase_context,
            )
        else:
            pruned_actions = list(prompt_actions)

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
            for action in legal_actions
        }
        if int(action_id) not in legal_ids:
            if verbose:
                print(f"{debug_prefix} action_id={action_id} 不在 legal_actions 中，忽略", flush=True)
            return DeepSeekSuggestion(action_id=None, reasoning=reasoning_text)

        if verbose:
            print(f"{debug_prefix} 解析得到 action_id={int(action_id)} (合法)", flush=True)
        return DeepSeekSuggestion(action_id=int(action_id), reasoning=reasoning_text)
