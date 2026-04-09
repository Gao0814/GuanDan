"""Rule-based baseline AI skeleton for phase-1."""

from collections import Counter
from typing import Protocol

from agents.base import AgentContext, BaseAgent
from agents.decision_trace import DecisionRecord
from agents.deepseek_client import DeepSeekClient
from agents.rag_advisor import RAGAdvisor, RAGEvidence
from config import AppConfig
from engine.actions import Action
from engine.patterns import PatternType
from engine.state import GameState


_RANK_STRENGTH: dict[str, int] = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


_PATTERN_PRIORITY: dict[PatternType, int] = {
    PatternType.STRAIGHT: 1,
    PatternType.PAIR_STRAIGHT: 1,
    PatternType.TRIPLE_WITH_PAIR: 1,
    PatternType.SINGLE: 2,
    PatternType.PAIR: 3,
    PatternType.TRIPLE: 4,
    PatternType.BOMB: 5,
}


_PATTERN_CN: dict[PatternType, str] = {
    PatternType.SINGLE: "单张",
    PatternType.PAIR: "对子",
    PatternType.TRIPLE: "三张",
    PatternType.BOMB: "炸弹",
    PatternType.STRAIGHT: "顺子",
    PatternType.PAIR_STRAIGHT: "连对",
    PatternType.TRIPLE_WITH_PAIR: "三带二",
}


def _action_rank_strength(action: Action) -> int:
    if not action.cards:
        return -1
    return _RANK_STRENGTH.get(action.cards[0].rank, -1)


class DeepSeekActionAdvisor(Protocol):
    """Optional model-support interface for legal-actions-only guidance."""

    def suggest_action(
        self,
        state: GameState,
        legal_actions: tuple[Action, ...],
        context: AgentContext,
        rag_context: dict[str, list[dict[str, str]]] | None = None,
    ) -> object:
        """Return an optional action suggestion; must never bypass legal boundaries."""


class RuleBasedAIAgent(BaseAgent):
    """Phase-1 baseline AI placeholder.

    Full strategy logic is intentionally deferred after Step 1.
    """

    def __init__(
        self,
        player_id: int,
        name: str = "rule-based-ai",
        rag_advisor: RAGAdvisor | None = None,
        deepseek_enabled: bool | None = None,
        deepseek_action_advisor: DeepSeekActionAdvisor | None = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.last_decision_record: DecisionRecord | None = None
        self._model_status_counts: Counter[str] = Counter()
        self._rag_advisor = rag_advisor
        config = AppConfig.from_env()
        enabled_from_config = bool(config.deepseek_enabled and config.deepseek_api_key)
        self._deepseek_enabled = enabled_from_config if deepseek_enabled is None else deepseek_enabled
        self._deepseek_action_advisor = deepseek_action_advisor
        if self._deepseek_action_advisor is None and self._deepseek_enabled and config.deepseek_api_key:
            self._deepseek_action_advisor = DeepSeekClient(
                api_key=config.deepseek_api_key,
                base_url=config.deepseek_base_url,
                model=config.deepseek_model,
            )

    @staticmethod
    def _action_cards_signature(cards: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        return tuple(sorted(cards))

    @staticmethod
    def _legal_action_signature(action: Action) -> tuple[str, str | None, tuple[str, ...]]:
        return (
            action.action_type.value,
            action.declared_pattern.value if action.declared_pattern else None,
            RuleBasedAIAgent._action_cards_signature(
                [f"{card.rank}{card.suit or ''}" for card in action.cards]
            ),
        )

    @staticmethod
    def _resolve_model_suggestion(
        suggested: object,
        legal_actions: tuple[Action, ...],
    ) -> Action | None:
        if isinstance(suggested, Action):
            return suggested if suggested in legal_actions else None
        if isinstance(suggested, dict):
            action_type = suggested.get("action_type")
            declared_pattern = suggested.get("declared_pattern")
            cards = suggested.get("cards")
            if not isinstance(action_type, str) or not isinstance(cards, list):
                return None

            card_tokens: list[str] = []
            for card in cards:
                if not isinstance(card, str):
                    return None
                card_tokens.append(card)

            target_signature = (
                action_type,
                declared_pattern if isinstance(declared_pattern, str) or declared_pattern is None else None,
                RuleBasedAIAgent._action_cards_signature(card_tokens),
            )
            for action in legal_actions:
                if RuleBasedAIAgent._legal_action_signature(action) == target_signature:
                    return action
        return None

    @staticmethod
    def _rank_counter(cards: tuple) -> Counter[str]:
        return Counter(card.rank for card in cards)

    def _experience_penalty(
        self,
        state: GameState,
        action: Action,
        legal_actions: tuple[Action, ...],
    ) -> tuple[int, tuple[str, ...]]:
        notes: list[str] = []

        if action.action_type.value == "pass":
            if len(legal_actions) > 1:
                return 1000, ("experience:avoid_pass_when_play_exists",)
            return 0, ("experience:pass_only_choice",)

        penalty = 0
        hand_counts = self._rank_counter(state.get_player(self.player_id).hand_cards)
        used_counts = self._rank_counter(action.cards)

        # Experience 1: preserve high-value control cards unless necessary.
        if action.declared_pattern == PatternType.BOMB:
            non_bomb_options = [
                a
                for a in legal_actions
                if a.action_type.value != "pass" and a.declared_pattern != PatternType.BOMB
            ]
            if non_bomb_options:
                penalty += 240
                notes.append("experience:avoid_unnecessary_bomb")

        # Experience 2: avoid breaking useful groups if a non-breaking move exists.
        for rank, used in used_counts.items():
            original = hand_counts.get(rank, 0)
            remaining = original - used
            if original >= 2 and remaining > 0:
                penalty += 80
                notes.append("experience:avoid_breaking_group")

        # Experience 2.5: when leading, prefer complete compound patterns over scattered plays.
        if state.table_constraint.leading_action is None:
            compound_patterns = {
                PatternType.STRAIGHT,
                PatternType.PAIR_STRAIGHT,
                PatternType.TRIPLE_WITH_PAIR,
            }
            has_simple_option = any(
                a.action_type.value != "pass"
                and a.declared_pattern in {PatternType.SINGLE, PatternType.PAIR, PatternType.TRIPLE}
                for a in legal_actions
            )
            if action.declared_pattern in compound_patterns and has_simple_option:
                penalty -= 120
                notes.append("experience:prefer_compound_pattern_on_lead")

        # Experience 3: prefer lower-strength legal play to conserve control cards.
        strength = _action_rank_strength(action)
        penalty += max(0, strength)
        notes.append("experience:prefer_lower_strength_legal_move")

        if state.table_constraint.leading_action is not None:
            notes.append("rule:follow_context")
        else:
            notes.append("rule:lead_context")

        return penalty, tuple(notes)

    @staticmethod
    def _build_rag_context(
        rule_evidence: tuple[RAGEvidence, ...],
        experience_evidence: tuple[RAGEvidence, ...],
        *,
        max_items_per_layer: int = 3,
        max_snippet_chars: int = 160,
    ) -> dict[str, list[dict[str, str]]]:
        def _to_items(evidence: tuple[RAGEvidence, ...]) -> list[dict[str, str]]:
            items: list[dict[str, str]] = []
            for item in evidence:
                snippet = item.snippet.strip().replace("\n", " ")
                if len(snippet) > max_snippet_chars:
                    snippet = snippet[: max_snippet_chars - 3].rstrip() + "..."
                items.append({"doc_id": item.source_id, "snippet": snippet})
                if len(items) >= max_items_per_layer:
                    break
            return items

        return {
            "rule": _to_items(rule_evidence),
            "experience": _to_items(experience_evidence),
        }

    @staticmethod
    def _build_action_focus(legal_actions: tuple[Action, ...]) -> dict[str, object]:
        preferred_patterns: list[str] = []
        for pattern_name in ("straight", "pair_straight", "triple_with_pair"):
            if any(
                action.declared_pattern is not None and action.declared_pattern.value == pattern_name
                for action in legal_actions
            ):
                preferred_patterns.append(pattern_name)

        has_bomb = any(
            action.declared_pattern is not None and action.declared_pattern.value == "bomb"
            for action in legal_actions
        )
        has_non_bomb_play = any(
            action.action_type.value == "play"
            and (action.declared_pattern is None or action.declared_pattern.value != "bomb")
            for action in legal_actions
        )

        return {
            "preferred_patterns": preferred_patterns[:3],
            "avoid_low_value_single_when_compound_exists": bool(preferred_patterns),
            "avoid_unnecessary_bomb": bool(has_bomb and has_non_bomb_play),
        }

    @staticmethod
    def _pattern_to_cn(pattern: PatternType | None) -> str | None:
        if pattern is None:
            return None
        return _PATTERN_CN.get(pattern)

    @staticmethod
    def _build_rag_query(
        state: GameState,
        legal_actions: tuple[Action, ...],
    ) -> str:
        parts: list[str] = []
        seen: set[str] = set()

        def _push(token: str | None) -> None:
            if token is None:
                return
            clean = token.strip()
            if not clean or clean in seen:
                return
            seen.add(clean)
            parts.append(clean)

        if state.table_constraint.leading_action is None:
            _push("先手")
            _push("主动出牌")
        else:
            _push("跟牌")
            _push("压牌")

        for action in legal_actions:
            _push(RuleBasedAIAgent._pattern_to_cn(action.declared_pattern))

        required_cn = RuleBasedAIAgent._pattern_to_cn(state.table_constraint.required_pattern)
        if required_cn is not None:
            _push(f"要求牌型{required_cn}")

        if state.table_constraint.min_strength_hint is not None:
            _push(f"最小强度{state.table_constraint.min_strength_hint}")

        leading = state.table_constraint.leading_action
        if leading is not None:
            leading_cn = RuleBasedAIAgent._pattern_to_cn(leading.declared_pattern)
            if leading_cn is not None:
                _push(f"当前领牌{leading_cn}")

        _push("保组")
        _push("少破组")
        _push("复合牌型优先")
        _push("避免无意义炸弹")

        return " ".join(parts)

    def select_action(
        self,
        state: GameState,
        legal_actions: tuple[Action, ...],
        context: AgentContext,
    ) -> Action:
        if not legal_actions:
            raise ValueError("legal_actions must not be empty")

        scored: list[tuple[int, tuple[int, int, int], Action, tuple[str, ...]]] = []
        for action in legal_actions:
            exp_penalty, notes = self._experience_penalty(state, action, legal_actions)
            if action.action_type.value == "pass":
                tie = (99, 99, 99)
            else:
                tie = (
                    _PATTERN_PRIORITY.get(action.declared_pattern or PatternType.BOMB, 99),
                    _action_rank_strength(action),
                    len(action.cards),
                )
            scored.append((exp_penalty, tie, action, notes))

        scored.sort(key=lambda item: (item[0], item[1]))
        _, _, selected, notes = scored[0]
        baseline_selected = selected
        baseline_score = (scored[0][0], scored[0][1])
        action_scores = {
            action: (penalty, tie)
            for penalty, tie, action, _ in scored
        }
        notes_list = list(notes)

        retrieved_rule_refs: tuple[str, ...] = ()
        retrieved_exp_refs: tuple[str, ...] = ()
        rejected_refs: tuple[str, ...] = ()
        rag_context_for_model: dict[str, list[dict[str, str]]] | None = None
        rag_context_status = "no_rag"
        if self._rag_advisor is not None:
            query = self._build_rag_query(state, legal_actions)
            rule_ev = self._rag_advisor.retrieve_rule_evidence(query=query, top_k=3)
            exp_ev = self._rag_advisor.retrieve_experience_evidence(query=query, top_k=3)
            retrieved_rule_refs = tuple(e.source_id for e in rule_ev)
            retrieved_exp_refs = tuple(e.source_id for e in exp_ev)
            rejected_refs = tuple(
                e.source_id
                for e in (rule_ev + exp_ev)
                if e.metadata.get("status") == "rejected_conflict"
            )
            rag_context_for_model = self._build_rag_context(rule_ev, exp_ev)
            if rag_context_for_model["rule"] or rag_context_for_model["experience"]:
                rag_context_for_model["action_focus"] = self._build_action_focus(legal_actions)
                rag_context_status = "rag_injected"
            else:
                rag_context_status = "rag_no_hit"
                rag_context_for_model = None

        model_meta: dict[str, object] = {
            "enabled": bool(self._deepseek_enabled),
            "status": "disabled",
            "rag_context_status": rag_context_status,
        }
        if self._deepseek_enabled and self._deepseek_action_advisor is not None:
            model_meta["status"] = "enabled"
            try:
                try:
                    suggested = self._deepseek_action_advisor.suggest_action(
                        state=state,
                        legal_actions=legal_actions,
                        context=context,
                        rag_context=rag_context_for_model,
                    )
                except TypeError:
                    suggested = self._deepseek_action_advisor.suggest_action(
                        state=state,
                        legal_actions=legal_actions,
                        context=context,
                    )
                resolved = self._resolve_model_suggestion(suggested, legal_actions)
                if resolved is not None:
                    resolved_score = action_scores.get(resolved)
                    if resolved_score is not None and resolved_score <= baseline_score:
                        selected = resolved
                        model_meta["status"] = "accepted_legal_suggestion"
                        notes_list.append("model:accepted_legal_suggestion")
                    else:
                        selected = baseline_selected
                        model_meta["status"] = "rejected_degradation_fallback"
                        notes_list.append("model:rejected_degradation_fallback")
                elif suggested is None:
                    model_meta["status"] = "empty_response_fallback"
                    notes_list.append("model:empty_response_fallback")
                else:
                    model_meta["status"] = "rejected_non_legal_suggestion"
                    notes_list.append("model:rejected_non_legal_suggestion")
            except Exception as exc:  # pragma: no cover - exercised by R8 tests
                model_meta["status"] = "fallback_error"
                model_meta["error_type"] = type(exc).__name__
                notes_list.append("model:fallback_error")
        elif self._deepseek_enabled and self._deepseek_action_advisor is None:
            model_meta["status"] = "enabled_without_adapter_fallback"
            notes_list.append("model:enabled_without_adapter_fallback")

        self.last_decision_record = DecisionRecord(
            step_no=context.step_no,
            player_id=self.player_id,
            legal_actions=legal_actions,
            selected_action=selected,
            rule_references=(
                "rule:select_from_legal_actions_only",
                "rule:pattern_subset_single_pair_triple_bomb_straight_pair_straight_triple_with_pair",
            ),
            experience_references=tuple(
                note for note in notes_list if note.startswith("experience:")
            ),
            notes=tuple(notes_list),
            metadata={
                "selector": "step6_rule_experience_baseline",
                "rag": {
                    "context_status": rag_context_status,
                    "rule_refs": list(retrieved_rule_refs),
                    "experience_refs": list(retrieved_exp_refs),
                    "rejected_refs": list(rejected_refs),
                },
                "model": model_meta,
            },
        )
        status = model_meta.get("status")
        if isinstance(status, str):
            self._model_status_counts[status] += 1
        return selected

    def get_model_status_counts(self) -> dict[str, int]:
        return dict(self._model_status_counts)
