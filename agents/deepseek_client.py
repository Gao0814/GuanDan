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
from typing import Protocol
from urllib import request as urllib_request

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
        if step_no == 0:
            return "opening"
        if hand_count is not None and hand_count < 10:
            return "endgame"
        return "midgame"

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
        action_id = DeepSeekClient._coerce_int(action.get("action_id"), default=-1)
        brief = DeepSeekClient._compact_action_text(
            action,
            current_level_rank,
            str(action.get("declared_pattern", "")) == "straight_flush",
        )
        return f"#{action_id} {brief}" if action_id >= 0 else brief

    @staticmethod
    def _unique_actions_by_brief(actions: list[dict[str, object]]) -> list[dict[str, object]]:
        unique: list[dict[str, object]] = []
        seen: set[str] = set()
        for action in actions:
            brief = DeepSeekClient._action_brief_cn(action)
            if brief in seen:
                continue
            seen.add(brief)
            unique.append(action)
        return unique

    @staticmethod
    def _select_transition_actions(
        actions: list[dict[str, object]],
        constraint: str,
    ) -> list[dict[str, object]]:
        singles = sorted(
            [a for a in actions if str(a.get("declared_pattern", "")) == "single"],
            key=DeepSeekClient._action_sort_key,
        )
        pairs = sorted(
            [a for a in actions if str(a.get("declared_pattern", "")) == "pair"],
            key=DeepSeekClient._action_sort_key,
        )
        passes = [a for a in actions if str(a.get("declared_pattern", "")) == "pass"]

        chosen: list[dict[str, object]] = []

        def add_candidate(action: dict[str, object]) -> None:
            brief = DeepSeekClient._action_brief_cn(action)
            if brief in {DeepSeekClient._action_brief_cn(item) for item in chosen}:
                return
            chosen.append(action)

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

        if not singles and pairs and len(chosen) < 3:
            for action in pairs:
                add_candidate(action)
                if len(chosen) >= 3:
                    break

        return chosen[:3]

    @staticmethod
    def _grouped_legal_actions_summary(
        legal_actions: list[dict[str, object]],
        constraint: str,
        step_no: int,
        hand_count: int | None,
        current_level_rank: str,
    ) -> list[str]:
        phase = DeepSeekClient._phase_from_round(step_no, hand_count)

        buckets: dict[str, list[dict[str, object]]] = {"run": [], "pressure": [], "transition": []}
        for action in legal_actions:
            pattern = str(action.get("declared_pattern", ""))
            tactic = DeepSeekClient._tactic_group(pattern)
            buckets.setdefault(tactic, []).append(action)

        for actions in buckets.values():
            actions.sort(
                key=lambda a: (
                    DeepSeekClient._action_sort_key(a),
                    DeepSeekClient._coerce_int(a.get("action_id"), default=0),
                )
            )

        transition_actions = DeepSeekClient._select_transition_actions(buckets.get("transition", []), constraint)
        if phase == "opening":
            ordered_groups = [
                ("跑牌", buckets.get("run", [])),
                ("压制", buckets.get("pressure", [])),
                ("过渡", transition_actions),
            ]
        elif phase == "endgame":
            ordered_groups = [
                ("压制", buckets.get("pressure", [])),
                ("跑牌", buckets.get("run", [])),
                ("过渡", transition_actions),
            ]
        else:
            ordered_groups = [
                ("跑牌", buckets.get("run", [])),
                ("过渡", transition_actions),
                ("压制", buckets.get("pressure", [])),
            ]

        lines: list[str] = [f"共 {len(legal_actions)} 个动作（已按战术剪枝）"]
        for label, actions in ordered_groups:
            unique_actions = DeepSeekClient._unique_actions_by_brief(actions)
            if not unique_actions:
                continue
            items = [DeepSeekClient._action_summary_entry(action, current_level_rank) for action in unique_actions]
            lines.append(f"{label}：{'、'.join(items)}")

        return lines

    @staticmethod
    def _prune_legal_actions(
        legal_actions: list[dict[str, object]],
        constraint: str,
        step_no: int = 0,
        hand_count: int | None = None,
    ) -> list[dict[str, object]]:
        """Prune redundant actions to reduce context size for the model.

        Preserves all run / pressure actions and keeps a tactical transition subset.
        The order is phase-aware so the prompt can emphasize opening, middle, or
        endgame priorities without changing legality.
        """
        phase = DeepSeekClient._phase_from_round(step_no, hand_count)
        kept: list[dict[str, object]] = []

        group_order: list[list[str]]
        if phase == "opening":
            group_order = [
                ["steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"],
                ["bomb", "straight_flush", "joker_bomb"],
                ["single", "pair", "pass"],
            ]
        elif phase == "endgame":
            group_order = [
                ["bomb", "straight_flush", "joker_bomb"],
                ["steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"],
                ["single", "pair", "pass"],
            ]
        else:
            group_order = [
                ["steel_plate", "straight", "pair_straight", "triple_with_pair", "triple"],
                ["single", "pair", "pass"],
                ["bomb", "straight_flush", "joker_bomb"],
            ]

        def add_unique(action: dict[str, object]) -> None:
            brief = DeepSeekClient._action_brief_cn(action)
            if brief in {DeepSeekClient._action_brief_cn(item) for item in kept}:
                return
            kept.append(action)

        for patterns in group_order:
            if patterns == ["single", "pair", "pass"]:
                transition_actions = [
                    action for action in legal_actions
                    if str(action.get("declared_pattern", "")) in set(patterns)
                ]
                for action in DeepSeekClient._select_transition_actions(transition_actions, constraint):
                    add_unique(action)
                continue

            pattern_set = set(patterns)
            actions = [
                action for action in legal_actions
                if str(action.get("declared_pattern", "")) in pattern_set
            ]
            actions.sort(
                key=lambda a: (
                    DeepSeekClient._action_sort_key(a),
                    DeepSeekClient._coerce_int(a.get("action_id"), default=0),
                )
            )
            for action in DeepSeekClient._unique_actions_by_brief(actions):
                add_unique(action)

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
    def _build_structured_prompt(
        my_info: dict[str, object],
        current_round: dict[str, object],
        other_players: list[dict[str, object]],
        history: dict[str, object],
        legal_actions: list[dict[str, object]],
        rag_context: dict[str, object] | None = None,
        hand_evaluation: dict[str, object] | None = None,
    ) -> str:
        """Build a structured Chinese prompt from the 5 observe() info blocks."""
        lines: list[str] = []

        # --- 【我的手牌】 ---
        hand_cards = [str(t) for t in my_info.get("hand_cards", [])]
        hand_count = len(hand_cards)
        remaining_singles = DeepSeekClient._coerce_int(
            my_info.get("remaining_single_card_count"), default=0
        )
        current_level_rank = str(current_round.get("current_level_rank", ""))
        step_no = DeepSeekClient._coerce_int(current_round.get("step_no"), default=0)

        wildcard_token = f"{current_level_rank}H" if current_level_rank else ""
        wildcard_count = hand_cards.count(wildcard_token) if wildcard_token else 0

        lines.append("【我的手牌】")
        lines.append(f"手牌总数：{hand_count} 张")
        lines.append(f"孤张数：{remaining_singles}")
        lines.append(f"逢人配张数：{wildcard_count}（红桃{current_level_rank}）")
        lines.append(f"完整手牌：{' '.join(_card_for_ai(t, current_level_rank, False) for t in hand_cards)}")
        if hand_evaluation is not None:
            score = DeepSeekClient._coerce_int(hand_evaluation.get("total_score"), default=0)
            label = str(hand_evaluation.get("label", ""))
            comment = str(hand_evaluation.get("comment", ""))
            lines.append(f"手牌评分：{score}（{label}）{comment}")
        lines.append("")

        # --- 【当前桌面/回合】 ---
        table_action = current_round.get("table_action")
        step_no = current_round.get("step_no", 0)
        round_no = current_round.get("round_no", 0)

        lines.append("【当前桌面/回合】")
        lines.append(f"级牌：{current_level_rank}")
        lines.append(f"第 {round_no} 轮 第 {step_no} 步")

        if table_action is None:
            lines.append("出牌限制：自由出牌（新一轮，可任意出牌）")
        else:
            ta = dict(table_action) if isinstance(table_action, dict) else {}
            ta_pattern = str(ta.get("declared_pattern", ""))
            ta_display = str(ta.get("display_text", ta_pattern))
            ta_carrier = [str(t) for t in ta.get("carrier_cards", [])]
            lines.append("出牌限制：跟牌 — 必须打出比桌面牌型更大的牌")
            lines.append(f"桌面牌型：{ta_display}")
            if ta_carrier:
                ta_cards_text = " ".join(
                    _card_for_ai(t, current_level_rank, ta_pattern == "straight_flush")
                    for t in ta_carrier
                )
                lines.append(
                    f"桌面牌组：{ta_cards_text}"
                )
        lines.append("")

        # --- 【其他玩家状态】 ---
        lines.append("【其他玩家状态】")
        my_team = str(my_info.get("team", ""))
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
                lines.append(f"玩家{pid}（{relation}）已完赛 — {label}")
            else:
                lines.append(f"玩家{pid}（{relation}）剩余 {hand_cnt} 张")
        lines.append("")

        # --- 【最近历史】 ---
        lines.append("【最近历史】")
        actions_list = list(history.get("actions", []))
        recent = actions_list[-5:]
        if recent:
            for item in recent:
                step = item.get("step_no", "?")
                pid = item.get("player_id", "?")
                pattern = str(item.get("declared_pattern", "?"))
                cards = [str(t) for t in item.get("declared_cards", [])]
                cards_text = " ".join(cards)
                lines.append(f"第{step}步 玩家{pid}：{pattern} {cards_text}")
        else:
            lines.append("（无历史）")

        finish_order = list(history.get("finish_order", []))
        if finish_order:
            labels = ["头游", "二游", "三游", "末游"]
            parts: list[str] = []
            for i, pid_val in enumerate(finish_order):
                label = labels[i] if i < len(labels) else f"第{i + 1}名"
                parts.append(f"玩家{pid_val}（{label}）")
            lines.append(f"已完赛顺序：{' → '.join(parts)}")
        lines.append("")

        # --- 【我的合法动作】 ---
        lines.append("【我的合法动作】")
        lines.extend(
            DeepSeekClient._grouped_legal_actions_summary(
                legal_actions=legal_actions,
                constraint=str(current_round.get("constraint", "free")),
                step_no=step_no,
                hand_count=hand_count,
                current_level_rank=current_level_rank,
            )
        )

        lines.append("")

        # --- 决策原则 ---
        lines.append("【决策原则（按优先级排序）】")
        lines.append(
            "1. 若为跟牌状态，且合法动作包含炸弹/同花顺/天王炸，"
            "应优先选择最小的跨型压制动作，不轻易 pass。"
        )
        lines.append(
            "2. 自由出牌时，优先打出一次减少最多手牌张数的合法组合"
            "（如钢板、顺子）。"
        )
        lines.append("3. 保留高价值炸弹到关键时刻，不无端消耗。")
        lines.append("4. 手牌少且即将出完时激进；若为队伍最后希望则保守。")
        lines.append(
            "5. 仅从合法动作中选择一个 action_id，"
            '严格按 JSON 返回：{"action_id": <整数>}'
        )

        if rag_context is not None:
            lines.append("")
            lines.append("【RAG 参考知识】")
            lines.append(json.dumps(rag_context, ensure_ascii=False))

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
        rag_context: dict[str, object] | None = None,
        hand_evaluation: dict[str, object] | None = None,
        verbose: bool = False,
        debug_prefix: str = "[DeepSeek]",
    ) -> DeepSeekSuggestion:
        current_round = dict(observation.get("current_round", {}))
        step_no = self._coerce_int(current_round.get("step_no"), default=0)
        current_player_id = self._coerce_int(current_round.get("current_player_id"), default=0)
        current_level_rank = str(current_round.get("current_level_rank", ""))

        my_info = dict(observation.get("my_info", {}))
        other_players = list(observation.get("other_players", []))
        history = dict(observation.get("history", {}))
        hand_count = self._coerce_int(my_info.get("hand_count"), default=0)

        constraint = str(current_round.get("constraint", "free"))
        pruned_actions = self._prune_legal_actions(
            legal_actions,
            constraint,
            step_no=step_no,
            hand_count=hand_count,
        )

        user_message = self._build_structured_prompt(
            my_info=my_info,
            current_round=current_round,
            other_players=other_players,
            history=history,
            legal_actions=pruned_actions,
            rag_context=rag_context,
            hand_evaluation=hand_evaluation,
        )

        if verbose:
            constraint = current_round.get("constraint")
            table_action = current_round.get("table_action")
            me_hand_count = hand_count
            me_remaining_singles = self._coerce_int(my_info.get("remaining_single_card_count"), default=0)

            rag_rule_count = 0
            rag_experience_count = 0
            if isinstance(rag_context, dict):
                rag_rule_count = len(list(rag_context.get("rule", [])))
                rag_experience_count = len(list(rag_context.get("experience", [])))

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
                        "只返回 JSON：{\"action_id\": <整数>}"
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
