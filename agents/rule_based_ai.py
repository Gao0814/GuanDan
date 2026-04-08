"""Rule-based baseline AI skeleton for phase-1."""

from collections import Counter

from agents.base import AgentContext, BaseAgent
from agents.decision_trace import DecisionRecord
from agents.rag_advisor import RAGAdvisor
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
    PatternType.SINGLE: 1,
    PatternType.PAIR: 2,
    PatternType.TRIPLE: 3,
    PatternType.BOMB: 4,
}


def _action_rank_strength(action: Action) -> int:
    if not action.cards:
        return -1
    return _RANK_STRENGTH.get(action.cards[0].rank, -1)


class RuleBasedAIAgent(BaseAgent):
    """Phase-1 baseline AI placeholder.

    Full strategy logic is intentionally deferred after Step 1.
    """

    def __init__(
        self,
        player_id: int,
        name: str = "rule-based-ai",
        rag_advisor: RAGAdvisor | None = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.last_decision_record: DecisionRecord | None = None
        self._rag_advisor = rag_advisor

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

        # Experience 3: prefer lower-strength legal play to conserve control cards.
        strength = _action_rank_strength(action)
        penalty += max(0, strength)
        notes.append("experience:prefer_lower_strength_legal_move")

        if state.table_constraint.leading_action is not None:
            notes.append("rule:follow_context")
        else:
            notes.append("rule:lead_context")

        return penalty, tuple(notes)

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

        retrieved_rule_refs: tuple[str, ...] = ()
        retrieved_exp_refs: tuple[str, ...] = ()
        rejected_refs: tuple[str, ...] = ()
        if self._rag_advisor is not None:
            query = " ".join(
                [
                    " ".join(action.declared_pattern.value for action in legal_actions if action.declared_pattern),
                    "follow" if state.table_constraint.leading_action else "lead",
                ]
            ).strip()
            rule_ev = self._rag_advisor.retrieve_rule_evidence(query=query, top_k=3)
            exp_ev = self._rag_advisor.retrieve_experience_evidence(query=query, top_k=3)
            retrieved_rule_refs = tuple(e.source_id for e in rule_ev)
            retrieved_exp_refs = tuple(e.source_id for e in exp_ev)
            rejected_refs = tuple(
                e.source_id
                for e in (rule_ev + exp_ev)
                if e.metadata.get("status") == "rejected_conflict"
            )

        self.last_decision_record = DecisionRecord(
            step_no=context.step_no,
            player_id=self.player_id,
            legal_actions=legal_actions,
            selected_action=selected,
            rule_references=(
                "rule:select_from_legal_actions_only",
                "rule:pattern_subset_single_pair_triple_bomb",
            ),
            experience_references=tuple(note for note in notes if note.startswith("experience:")),
            notes=notes,
            metadata={
                "selector": "step6_rule_experience_baseline",
                "rag": {
                    "rule_refs": list(retrieved_rule_refs),
                    "experience_refs": list(retrieved_exp_refs),
                    "rejected_refs": list(rejected_refs),
                },
            },
        )
        return selected
