"""DeepSeek-backed agent that selects an action_id strictly from legal actions.

Boundary guarantees (Step D):
- Decision logic only uses `observe()` + `legal_actions()` public payloads.
- The agent MUST return an `action_id` that exists in the given legal_actions list.
- RAG is used only as optional knowledge support (never as legality source).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json

from agents.base import BaseAgent, require_legal_action_id
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.rag_advisor import RAGAdvisor, RAGEvidence
from agents.rule_based_ai import RuleBasedAIAgent


_OPENING_RANK_ORDER: tuple[str, ...] = (
    "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2", "SJ", "BJ"
)
_RANK_SORT_ORDER: dict[str, int] = {rank: index for index, rank in enumerate(_OPENING_RANK_ORDER)}


def _rank_sort_value(rank: str) -> int:
    return _RANK_SORT_ORDER.get(rank, 999)


def _action_declared_ranks(action: dict[str, object]) -> list[str]:
    declared_cards = [str(token) for token in action.get("declared_cards", [])]
    return [_token_rank(token) for token in declared_cards]


def _ranks_range_text(ranks: list[str]) -> str:
    if not ranks:
        return ""
    unique = sorted(set(ranks), key=_rank_sort_value)
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]
    return f"{unique[0]}~{unique[-1]}"


def _triple_with_pair_main_rank(ranks: list[str]) -> str | None:
    if not ranks:
        return None
    counts = Counter(ranks)
    triples = [rank for rank, count in counts.items() if count == 3]
    if not triples:
        return None
    return sorted(triples, key=_rank_sort_value)[-1]


def _action_opening_score(action: dict[str, object]) -> int:
    pattern = str(action.get("declared_pattern", ""))
    ranks = _action_declared_ranks(action)
    if not ranks:
        return -1

    if pattern == "triple_with_pair":
        main = _triple_with_pair_main_rank(ranks)
        return _rank_sort_value(main) if main else max(_rank_sort_value(r) for r in ranks)

    if pattern in {"straight", "pair_straight", "steel_plate"}:
        return max(_rank_sort_value(r) for r in ranks)

    return _rank_sort_value(ranks[0])


def _action_opening_brief(action: dict[str, object]) -> str:
    pattern = str(action.get("declared_pattern", ""))
    ranks = _action_declared_ranks(action)

    if pattern in {"straight", "pair_straight", "steel_plate"}:
        return _ranks_range_text(ranks)

    if pattern == "triple_with_pair":
        counts = Counter(ranks)
        triple_rank = _triple_with_pair_main_rank(ranks)
        pair_ranks = [rank for rank, count in counts.items() if count == 2]
        pair_rank = sorted(pair_ranks, key=_rank_sort_value)[-1] if pair_ranks else None
        if triple_rank and pair_rank:
            return f"{triple_rank}带{pair_rank}"
        if triple_rank:
            return triple_rank
        return _ranks_range_text(ranks)

    if ranks:
        return ranks[0]
    return ""


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _token_rank(token: str) -> str:
    if token and token[-1] in {"S", "H", "C", "D"}:
        return token[:-1]
    return token


_PATTERN_CN: dict[str, str] = {
    "pass": "pass",
    "single": "单",
    "pair": "对",
    "triple": "三",
    "triple_with_pair": "三带二",
    "straight": "顺",
    "pair_straight": "连对",
    "steel_plate": "钢板",
    "straight_flush": "同花顺",
    "bomb": "炸",
    "joker_bomb": "王炸",
}

_PATTERN_CN_LONG: dict[str, str] = {
    "pass": "pass",
    "single": "单张",
    "pair": "对",
    "triple": "三张",
    "triple_with_pair": "三带二",
    "straight": "顺子",
    "pair_straight": "连对",
    "steel_plate": "钢板",
    "straight_flush": "同花顺",
    "bomb": "炸弹",
    "joker_bomb": "天王炸",
}

_SUIT_SYMBOLS: dict[str, str] = {"S": "♠", "H": "♥", "C": "♣", "D": "♦"}


def _card_token_display(token: str) -> str:
    """Convert a card token (e.g. '3S', '4H', 'SJ') to human-readable Chinese."""
    if token == "SJ":
        return "小王"
    if token == "BJ":
        return "大王"
    if len(token) >= 2 and token[-1] in _SUIT_SYMBOLS:
        suit = token[-1]
        rank = token[:-1]
        return f"{_SUIT_SYMBOLS[suit]}{rank}"
    return token


def _cards_display_cn(tokens: list[str]) -> str:
    return "".join(_card_token_display(t) for t in tokens)


def _action_brief_cn(action: dict[str, object]) -> str:
    pattern = str(action.get("declared_pattern"))
    if pattern == "pass":
        return "pass"

    declared_cards = [str(token) for token in action.get("declared_cards", [])]
    ranks = [_token_rank(token) for token in declared_cards]
    if pattern == "single":
        return f"单{ranks[0]}" if ranks else "单"
    if pattern == "pair":
        return f"对{ranks[0]}" if ranks else "对"
    if pattern == "triple":
        return f"三{ranks[0]}" if ranks else "三"
    if pattern == "bomb":
        main = ranks[0] if ranks else ""
        return f"{len(ranks)}炸{main}"
    if pattern == "joker_bomb":
        return "王炸"
    if pattern in {"straight", "straight_flush"}:
        return f"{_PATTERN_CN.get(pattern, pattern)}{''.join(ranks)}"

    label = _PATTERN_CN.get(pattern, pattern)
    ranks_text = "".join(ranks)
    return f"{label}{ranks_text}" if ranks_text else label


def _action_display_cn(action: dict[str, object]) -> str:
    """Format the final chosen action for display: e.g. '♠2（单张）', '♠5♣5（对5）'."""
    pattern = str(action.get("declared_pattern"))
    if pattern == "pass":
        return "pass"

    carrier_cards = [str(t) for t in action.get("carrier_cards", [])]
    declared_cards = [str(t) for t in action.get("declared_cards", [])]
    cards_display = _cards_display_cn(carrier_cards)

    if pattern == "bomb":
        main = _token_rank(declared_cards[0]) if declared_cards else ""
        label = f"{len(carrier_cards)}炸{main}"
    elif pattern == "pair":
        main = _token_rank(declared_cards[0]) if declared_cards else ""
        label = f"对{main}"
    elif pattern == "single":
        label = "单张"
    else:
        label = _PATTERN_CN_LONG.get(pattern, pattern)

    return f"{cards_display}（{label}）"


def _summarize_hand(observation: dict[str, object]) -> str:
    current_round = dict(observation.get("current_round", {}))
    my_info = dict(observation.get("my_info", {}))

    current_level_rank = str(current_round.get("current_level_rank", ""))
    hand_count = _coerce_int(my_info.get("hand_count"), default=0)
    remaining_singles = _coerce_int(my_info.get("remaining_single_card_count"), default=0)
    hand_cards = [str(token) for token in my_info.get("hand_cards", [])]

    wildcard_token = f"{current_level_rank}H" if current_level_rank else ""
    wildcard_count = hand_cards.count(wildcard_token) if wildcard_token else 0
    wildcard_text = f"，逢人配×{wildcard_count}" if wildcard_count else ""
    return f"手牌摘要：{hand_count}张，孤张数{remaining_singles}{wildcard_text}"


def _summarize_legal_actions(
    legal_actions: list[dict[str, object]],
) -> tuple[str, str]:
    counter = Counter(str(action.get("declared_pattern")) for action in legal_actions)
    count_parts: list[str] = []
    for pattern, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        count_parts.append(f"{_PATTERN_CN_LONG.get(pattern, pattern)}×{count}")

    counts_text = "，".join(count_parts)

    examples: list[str] = []
    seen: set[str] = set()
    for action in legal_actions:
        brief = _action_brief_cn(action)
        if brief in seen:
            continue
        seen.add(brief)
        examples.append(brief)

    total_unique = len(examples)
    if total_unique > 10:
        examples = examples[:8]
        examples.append("…")

    examples_text = "、".join(examples)
    return (f"合法动作摘要：共{len(legal_actions)}个，类型：{counts_text}", examples_text)


def _estimate_prompt_tokens(prompt_text: str) -> int:
    return max(1, len(prompt_text) // 2)


def _action_by_id(legal_actions: list[dict[str, object]], action_id: int) -> dict[str, object] | None:
    for action in legal_actions:
        try:
            if int(action.get("action_id")) == int(action_id):
                return action
        except (TypeError, ValueError):
            continue
    return None


def _build_rag_context(
    *,
    rule_evidence: tuple[RAGEvidence, ...],
    experience_evidence: tuple[RAGEvidence, ...],
) -> dict[str, object]:
    def pack(evidence: RAGEvidence) -> dict[str, object]:
        return {
            "source_id": evidence.source_id,
            "layer": evidence.layer,
            "snippet": evidence.snippet,
            "metadata": dict(evidence.metadata),
        }

    accepted_rules = [pack(item) for item in rule_evidence if item.metadata.get("status") == "accepted"]
    accepted_experience = [
        pack(item) for item in experience_evidence if item.metadata.get("status") == "accepted"
    ]
    return {
        "rule": accepted_rules,
        "experience": accepted_experience,
    }


def _rag_query_from_observation(observation: dict[str, object]) -> str:
    current_round = dict(observation.get("current_round", {}))
    my_info = dict(observation.get("my_info", {}))

    constraint = current_round.get("constraint")
    table_action = current_round.get("table_action")
    current_level_rank = current_round.get("current_level_rank")

    hand_cards = my_info.get("hand_cards")
    remaining_singles = my_info.get("remaining_single_card_count")

    return (
        f"掼蛋 出牌建议 级牌 {current_level_rank} "
        f"桌面约束 {constraint} "
        f"桌面 {table_action} "
        f"手牌 {hand_cards} "
        f"孤张数 {remaining_singles}"
    )


def _print_rag_summary(
    rule_evidence: tuple[RAGEvidence, ...],
    experience_evidence: tuple[RAGEvidence, ...],
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    rag_context: dict[str, object] | None,
) -> None:
    """Print RAG retrieval summary for --show-thinking mode."""
    total = len(rule_evidence) + len(experience_evidence)

    if rag_context is None or total == 0:
        print("[DeepSeek 思考] RAG：未触发或无匹配结果", flush=True)
        return

    print(f"[DeepSeek 思考] RAG 检索结果：共 {total} 条", flush=True)

    # Rule evidence
    accepted_rules = [e for e in rule_evidence if e.metadata.get("status") == "accepted"]
    rejected_rules = [e for e in rule_evidence if e.metadata.get("status") != "accepted"]

    if accepted_rules:
        parts: list[str] = []
        for ev in accepted_rules:
            preview = ev.snippet[:100].replace("\n", " ").strip()
            if len(ev.snippet) > 100:
                preview += "…"
            parts.append(preview)
        print(f"[DeepSeek 思考] 规则建议：{'；'.join(parts)}", flush=True)

    if rejected_rules:
        for ev in rejected_rules:
            reason = ev.metadata.get("reason", "unknown")
            print(f"[DeepSeek 思考] 规则建议（已拒绝）：[{reason}] ...", flush=True)

    # Experience evidence
    accepted_exp = [e for e in experience_evidence if e.metadata.get("status") == "accepted"]
    rejected_exp = [e for e in experience_evidence if e.metadata.get("status") != "accepted"]

    if accepted_exp:
        parts = []
        for ev in accepted_exp:
            preview = ev.snippet[:100].replace("\n", " ").strip()
            if len(ev.snippet) > 100:
                preview += "…"
            parts.append(preview)
        print(f"[DeepSeek 思考] 经验建议：{'；'.join(parts)}", flush=True)

    if rejected_exp:
        for ev in rejected_exp:
            reason = ev.metadata.get("reason", "unknown")
            print(f"[DeepSeek 思考] 经验建议（已拒绝）：[{reason}] ...", flush=True)


@dataclass(slots=True)
class DeepSeekAIAgent(BaseAgent):
    client: DeepSeekClient
    rag_advisor: RAGAdvisor | None = None
    rag_top_k: int = 1
    verbose: bool = False

    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        if not legal_actions:
            raise ValueError("legal_actions must not be empty")

        my_info = dict(observation.get("my_info", {}))
        other_players = list(observation.get("other_players", []))
        history = dict(observation.get("history", {}))
        player_id = _coerce_int(my_info.get("player_id"), default=self.player_id)
        is_primary = player_id == 1
        verbose = bool(self.verbose and is_primary)

        # Prune for display (same logic the client uses for the model)
        current_round = dict(observation.get("current_round", {}))
        display_constraint = str(current_round.get("constraint", "free"))
        step_no = _coerce_int(current_round.get("step_no"), default=0)
        pruned = DeepSeekClient._prune_legal_actions(legal_actions, display_constraint)

        # --- pre-request verbose output (player 1 only) ---
        if verbose:
            table_action = current_round.get("table_action")
            level_rank = current_round.get("current_level_rank", "")
            step_no = current_round.get("step_no", 0)
            round_no = current_round.get("round_no", 0)

            print(f"[DeepSeek 思考] {_summarize_hand(observation)}", flush=True)

            if table_action is None:
                print(
                    f"[DeepSeek 思考] 局面：第{round_no}轮第{step_no}步 "
                    f"级牌{level_rank}，自由出牌",
                    flush=True,
                )
            else:
                ta = dict(table_action) if isinstance(table_action, dict) else {}
                ta_display = str(ta.get("display_text", str(table_action)))
                print(
                    f"[DeepSeek 思考] 局面：第{round_no}轮第{step_no}步 "
                    f"级牌{level_rank}，跟牌（桌面：{ta_display}）",
                    flush=True,
                )

            other_players = list(observation.get("other_players", []))
            my_team = str(my_info.get("team", ""))
            player_parts: list[str] = []
            for p in other_players:
                pid = p.get("player_id", "?")
                team = str(p.get("team", ""))
                hand_cnt = p.get("hand_count", 0)
                finished = bool(p.get("finished", False))
                relation = "队友" if team == my_team else "对手"
                if finished:
                    player_parts.append(f"玩家{pid}({relation})已完赛")
                else:
                    player_parts.append(f"玩家{pid}({relation})余{hand_cnt}张")
            print(f"[DeepSeek 思考] 其他玩家：{'，'.join(player_parts)}", flush=True)

            counts_line, examples_line = _summarize_legal_actions(pruned)
            print(f"[DeepSeek 思考] {counts_line}", flush=True)
            print(f"[DeepSeek 思考] 动作示例：{examples_line}", flush=True)
            print(
                f"[DeepSeek 思考] 传入模型：{len(pruned)} 个动作"
                f"（原始 {len(legal_actions)} 个已剪枝）",
                flush=True,
            )

        # --- RAG context ---
        rag_context: dict[str, object] | None = None
        rule_evidence: tuple[RAGEvidence, ...] = ()
        experience_evidence: tuple[RAGEvidence, ...] = ()
        if self.rag_advisor is not None:
            query = _rag_query_from_observation(observation)
            rule_evidence = self.rag_advisor.retrieve_rule_evidence(query, top_k=self.rag_top_k)
            experience_evidence = self.rag_advisor.retrieve_experience_evidence(query, top_k=self.rag_top_k)
            rag_context = _build_rag_context(
                rule_evidence=rule_evidence,
                experience_evidence=experience_evidence,
            )

        if verbose:
            _print_rag_summary(
                rule_evidence, experience_evidence,
                observation, pruned, rag_context,
            )

        # --- pass-only shortcut (no API call) ---
        if len(pruned) == 1 and (
            str(pruned[0].get("declared_pattern")) == "pass"
            or str(pruned[0].get("display_text", "")).lower() == "pass"
        ):
            chosen = _coerce_int(pruned[0].get("action_id"), default=-1)
            chosen = require_legal_action_id(chosen, legal_actions)

            if verbose:
                print("[DeepSeek 思考] 合法动作仅剩 pass，跳过模型推理", flush=True)
                print("[DeepSeek 思考] 玩家1 模型选择：pass", flush=True)
                print("[DeepSeek 思考] 本次上下文长度：约 0 tokens（仅剩 pass，未调用 API）", flush=True)

            return chosen

        # --- opening local intercept (no API call) ---
        if display_constraint == "free" and step_no == 0:
            analysis = self._analyze_opening_hand(observation, legal_actions)
            opening_pruned = self._prune_opening_actions(pruned, legal_actions)
            chosen = self._select_best_opening_action(analysis, opening_pruned)
            chosen = require_legal_action_id(int(chosen), legal_actions)

            if verbose:
                point_distribution = analysis.get("point_distribution", {})
                if not isinstance(point_distribution, dict):
                    point_distribution = {}

                wildcard_text = analysis.get("wildcard_text", "")
                long_combo_text = analysis.get("long_combo_text", "")
                single_count = analysis.get("single_count", 0)
                hand_type = analysis.get("hand_type", "")

                dist_parts: list[str] = []
                for rank in _OPENING_RANK_ORDER:
                    count = point_distribution.get(rank)
                    if isinstance(count, int) and count > 0:
                        dist_parts.append(f"{rank}×{count}")
                dist_summary = " ".join(dist_parts) if dist_parts else "（无）"

                print(
                    "[DeepSeek 思考] 手牌分析："
                    f"点数分布：{dist_summary}；"
                    f"{wildcard_text}；"
                    f"长套可选：{long_combo_text}；"
                    f"散牌{single_count}张；"
                    f"手牌类型：{hand_type}",
                    flush=True,
                )

                infer_text = self._infer_opponents(observation, point_distribution)
                print(f"[DeepSeek 思考] 对手推测：{infer_text}", flush=True)

                action = _action_by_id(legal_actions, chosen)
                opening_display = self._opening_action_display_cn(action) if action is not None else "(unknown)"
                print(f"[DeepSeek 思考] 开局使用公式化出牌：{opening_display}", flush=True)
                print("[DeepSeek 思考] 本次上下文长度：约 0 tokens（开局本地决策，未调用 API）", flush=True)

            return chosen

        if verbose:
            user_message = DeepSeekClient._build_structured_prompt(
                my_info=my_info,
                current_round=current_round,
                other_players=other_players,
                history=history,
                legal_actions=pruned,
                rag_context=rag_context,
            )
            payload = {
                "model": self.client._model,
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
            prompt_text = json.dumps(payload, ensure_ascii=False)
            print(f"[DeepSeek 思考] 本次上下文长度：约 {_estimate_prompt_tokens(prompt_text)} tokens", flush=True)

        # --- call DeepSeek API ---
        failure_reason: str | None = None
        reasoning: str | None = None
        try:
            suggestion = self.client.suggest_action_id(
                observation=observation,
                legal_actions=legal_actions,
                rag_context=rag_context,
                verbose=False,  # agent handles all printing
                debug_prefix=f"[DeepSeek] 玩家{player_id}",
            )
        except Exception as exc:
            suggestion = DeepSeekSuggestion(action_id=None, reasoning=None)
            failure_reason = f"请求异常：{exc.__class__.__name__}: {exc}"

        reasoning = suggestion.reasoning
        suggested = suggestion.action_id

        # --- validate and apply suggestion ---
        if suggested is not None:
            try:
                chosen = require_legal_action_id(int(suggested), legal_actions)
            except Exception as exc:
                chosen = None
                failure_reason = f"返回 action_id 非法：{exc}"
            else:
                if verbose:
                    action = _action_by_id(legal_actions, chosen)
                    display = _action_display_cn(action) if action is not None else "(unknown)"
                    print(f"[DeepSeek 思考] 玩家1 模型思考过程：", flush=True)
                    if reasoning:
                        print(reasoning, flush=True)
                    else:
                        print("（无）", flush=True)
                    print(f"[DeepSeek 思考] 玩家1 模型选择：{display}", flush=True)
                return chosen

        # --- fallback to rule-based AI ---
        if failure_reason is None:
            failure_reason = "未返回有效 action_id"

        fallback = RuleBasedAIAgent(player_id=self.player_id)
        chosen = fallback.select_action(observation, legal_actions)
        chosen = require_legal_action_id(chosen, legal_actions)

        if verbose:
            action = _action_by_id(legal_actions, chosen)
            display = _action_display_cn(action) if action is not None else "(unknown)"
            print(f"[DeepSeek 思考] 玩家1 回退规则AI，原因：{failure_reason}", flush=True)
            print(f"[DeepSeek 思考] 玩家1 回退选择：{display}", flush=True)
        else:
            # Other players stay silent unless fallback happens.
            if not is_primary:
                if failure_reason.startswith("请求异常"):
                    print(f"[DeepSeek] 玩家{player_id} 请求异常，回退规则AI", flush=True)
                else:
                    print(f"[DeepSeek] 玩家{player_id} 无有效action_id，回退规则AI", flush=True)

        return chosen

    @staticmethod
    def _opening_action_display_cn(action: dict[str, object]) -> str:
        pattern = str(action.get("declared_pattern"))
        if pattern == "pass":
            return "pass"

        carrier_cards = [str(t) for t in action.get("carrier_cards", [])]
        label = _PATTERN_CN_LONG.get(pattern, pattern)
        return f"{label} {_cards_display_cn(carrier_cards)}"

    @staticmethod
    def _prune_opening_actions(
        pruned_actions: list[dict[str, object]],
        raw_legal_actions: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Further prune for opening: exclude bombs/straight_flush/joker_bomb.

        `pruned_actions` is the existing pruning result; if filtering makes it empty,
        fall back to a lightweight recompute from the raw legal actions.
        """

        excluded = {"bomb", "straight_flush", "joker_bomb"}
        filtered = [
            a
            for a in pruned_actions
            if str(a.get("declared_pattern", "")) not in excluded
        ]
        if filtered:
            return filtered

        # Fallback: keep a small, balanced subset (no bombs) from raw actions.
        allowed = {
            "steel_plate",
            "straight",
            "pair_straight",
            "triple_with_pair",
            "triple",
            "pair",
            "single",
            "pass",
        }
        groups: dict[str, list[dict[str, object]]] = {}
        for action in raw_legal_actions:
            pattern = str(action.get("declared_pattern", ""))
            if pattern not in allowed:
                continue
            groups.setdefault(pattern, []).append(action)

        def pick_top(pattern: str, *, limit: int) -> list[dict[str, object]]:
            items = groups.get(pattern, [])
            items = sorted(
                items,
                key=lambda a: (
                    _action_opening_score(a),
                    _coerce_int(a.get("action_id"), default=0),
                ),
                reverse=True,
            )
            return items[:limit]

        kept: list[dict[str, object]] = []
        kept.extend(pick_top("steel_plate", limit=5))
        kept.extend(pick_top("straight", limit=5))
        kept.extend(pick_top("pair_straight", limit=5))
        kept.extend(pick_top("triple_with_pair", limit=5))
        kept.extend(pick_top("triple", limit=4))
        kept.extend(pick_top("pair", limit=6))
        kept.extend(pick_top("single", limit=8))

        # Keep order stable-ish by action_id to improve reproducibility.
        kept.sort(key=lambda a: _coerce_int(a.get("action_id"), default=0))
        return kept or raw_legal_actions

    @staticmethod
    def _analyze_opening_hand(
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> dict[str, object]:
        current_round = dict(observation.get("current_round", {}))
        my_info = dict(observation.get("my_info", {}))

        current_level_rank = str(
            current_round.get("current_level_rank")
            or my_info.get("current_level_rank")
            or ""
        )
        hand_cards = [str(token) for token in my_info.get("hand_cards", [])]
        single_count = _coerce_int(my_info.get("remaining_single_card_count"), default=0)

        wildcard_token = f"{current_level_rank}H" if current_level_rank else ""
        wildcard_count = hand_cards.count(wildcard_token) if wildcard_token else 0
        wildcard_text = (
            f"逢人配♥{current_level_rank}×{wildcard_count}"
            if current_level_rank
            else f"逢人配×{wildcard_count}"
        )

        ranks = [_token_rank(token) for token in hand_cards]
        counts = Counter(ranks)
        point_distribution: dict[str, int] = {}
        for rank in _OPENING_RANK_ORDER:
            count = counts.get(rank, 0)
            if count > 0:
                point_distribution[rank] = int(count)
        # Include any unknown ranks at the end (should be rare).
        for rank, count in counts.items():
            if rank not in point_distribution and count > 0:
                point_distribution[str(rank)] = int(count)

        allowed_patterns = (
            "steel_plate",
            "straight",
            "pair_straight",
            "triple_with_pair",
            "triple",
            "pair",
            "single",
        )
        candidates: dict[str, list[dict[str, object]]] = {p: [] for p in allowed_patterns}
        for action in legal_actions:
            pattern = str(action.get("declared_pattern", ""))
            if pattern in candidates:
                candidates[pattern].append(action)

        combos: dict[str, list[str]] = {}
        for pattern, items in candidates.items():
            if not items:
                continue
            ranked = sorted(
                items,
                key=lambda a: (
                    _action_opening_score(a),
                    _coerce_int(a.get("action_id"), default=0),
                ),
                reverse=True,
            )
            top = ranked[:2]
            combos[pattern] = [_action_opening_brief(a) for a in top if _action_opening_brief(a)]

        has_long_combo = any(combos.get(p) for p in ("steel_plate", "straight", "pair_straight", "triple_with_pair"))
        hand_type = "整齐型" if (single_count <= 3 and has_long_combo) else "散乱型"
        recommended_opening = "主动跑长套" if hand_type == "整齐型" else "出小单张试探"

        long_parts: list[str] = []
        if combos.get("steel_plate"):
            long_parts.append(f"钢板({', '.join(combos['steel_plate'])})")
        if combos.get("straight"):
            long_parts.append(f"顺子({', '.join(combos['straight'])})")
        if combos.get("pair_straight"):
            long_parts.append(f"连对({', '.join(combos['pair_straight'])})")
        if combos.get("triple_with_pair"):
            long_parts.append(f"三带二({', '.join(combos['triple_with_pair'])})")
        long_combo_text = "；".join(long_parts) if long_parts else "（无）"

        return {
            "point_distribution": point_distribution,
            "single_count": single_count,
            "wildcard_count": wildcard_count,
            "wildcard_token": wildcard_token,
            "wildcard_text": wildcard_text,
            "combos": combos,
            "hand_type": hand_type,
            "recommended_opening": recommended_opening,
            "long_combo_text": long_combo_text,
        }

    @staticmethod
    def _infer_opponents(
        observation: dict[str, object],
        point_distribution: dict[str, int],
    ) -> str:
        my_info = dict(observation.get("my_info", {}))
        single_count = _coerce_int(my_info.get("remaining_single_card_count"), default=0)

        parts: list[str] = []

        heavy_ranks = [
            rank
            for rank, count in point_distribution.items()
            if isinstance(count, int) and count >= 3
        ]
        heavy_ranks = sorted(heavy_ranks, key=_rank_sort_value, reverse=True)
        for rank in heavy_ranks[:2]:
            count = point_distribution.get(rank, 0)
            parts.append(
                f"我多持有点数{rank}×{count}，对手形成对应炸弹或对子的概率较低。"
            )

        if single_count <= 3:
            parts.append("我散牌少，开局主动性高，可主动跑长套。")
        elif single_count >= 5:
            parts.append("我散牌偏多，开局更适合先出小单张试探并保留关键牌。")

        return "；".join(parts) if parts else "暂无强信号，仅供参考。"

    @staticmethod
    def _select_best_opening_action(
        analysis: dict[str, object],
        pruned_actions: list[dict[str, object]],
    ) -> int:
        hand_type = str(analysis.get("hand_type", ""))
        wildcard_token = str(analysis.get("wildcard_token", ""))

        def is_wildcard_carrier(action: dict[str, object]) -> bool:
            if not wildcard_token:
                return False
            carrier = [str(t) for t in action.get("carrier_cards", [])]
            return wildcard_token in carrier

        def best_of(pattern: str, *, prefer_10jqka: bool = False) -> dict[str, object] | None:
            items = [a for a in pruned_actions if str(a.get("declared_pattern")) == pattern]
            if not items:
                return None
            if prefer_10jqka and pattern == "straight":
                for a in items:
                    ranks = _action_declared_ranks(a)
                    unique = sorted(set(ranks), key=_rank_sort_value)
                    if unique == ["10", "J", "Q", "K", "A"]:
                        return a
            return sorted(
                items,
                key=lambda a: (
                    _action_opening_score(a),
                    _coerce_int(a.get("action_id"), default=0),
                ),
                reverse=True,
            )[0]

        def smallest_single_excluding_wildcard() -> dict[str, object] | None:
            singles = [a for a in pruned_actions if str(a.get("declared_pattern")) == "single"]
            if not singles:
                return None

            def sort_key(a: dict[str, object]) -> tuple[int, int]:
                ranks = _action_declared_ranks(a)
                rank_val = _rank_sort_value(ranks[0]) if ranks else 999
                return (rank_val, _coerce_int(a.get("action_id"), default=0))

            ordered = sorted(singles, key=sort_key)
            for a in ordered:
                if not is_wildcard_carrier(a):
                    return a
            return ordered[0]

        # --- tidy hand: prefer long combos ---
        if hand_type == "整齐型":
            for pattern in ("steel_plate",):
                chosen = best_of(pattern)
                if chosen is not None:
                    return int(chosen.get("action_id"))

            chosen = best_of("straight", prefer_10jqka=True)
            if chosen is not None:
                return int(chosen.get("action_id"))

            chosen = best_of("pair_straight")
            if chosen is not None:
                return int(chosen.get("action_id"))

            chosen = best_of("triple_with_pair")
            if chosen is not None:
                return int(chosen.get("action_id"))

            single_choice = smallest_single_excluding_wildcard()
            if single_choice is not None:
                return int(single_choice.get("action_id"))

        # --- messy hand: play smallest single (exclude wildcard) ---
        single_choice = smallest_single_excluding_wildcard()
        if single_choice is not None:
            return int(single_choice.get("action_id"))

        # --- edge cases ---
        for action in pruned_actions:
            if str(action.get("declared_pattern")) == "pass":
                return int(action.get("action_id"))

        if pruned_actions:
            return int(pruned_actions[0].get("action_id"))

        return 0
