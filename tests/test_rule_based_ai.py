"""Step-6 tests for baseline rule/experience AI behavior."""

import unittest

from agents.base import AgentContext
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.state import GameState, PlayerState, TableConstraint
from rag.kb_loader import KnowledgeDocument
from rag.retriever import KnowledgeRetriever


def _state_with_hand(hand: tuple[Card, ...], with_table: bool = False) -> GameState:
    players = (
        PlayerState(player_id=0, hand_cards=hand),
        PlayerState(player_id=1, hand_cards=()),
        PlayerState(player_id=2, hand_cards=()),
        PlayerState(player_id=3, hand_cards=()),
    )
    table = TableConstraint()
    if with_table:
        table = TableConstraint(
            leading_action=Action(
                player_id=1,
                action_type=ActionType.PLAY,
                cards=(Card(rank="6", suit="S"),),
                declared_pattern=PatternType.SINGLE,
            ),
            required_pattern=PatternType.SINGLE,
            min_strength_hint=6,
        )
    return GameState(players=players, current_player_id=0, table_constraint=table)


class TestRuleBasedAI(unittest.TestCase):
    def setUp(self) -> None:
        self.ai = RuleBasedAIAgent(player_id=0, name="ai-0")

    def test_a1_fixed_state_action_stable(self) -> None:
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        outputs = [
            self.ai.select_action(state, legal, AgentContext(step_no=i))
            for i in range(10)
        ]
        first = outputs[0]
        self.assertTrue(all(o == first for o in outputs))

    def test_a2_avoid_unnecessary_high_value_bomb(self) -> None:
        hand = (
            Card(rank="4", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="9", suit="C"),
            Card(rank="9", suit="D"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="4", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="9", suit="S"),
                    Card(rank="9", suit="H"),
                    Card(rank="9", suit="C"),
                    Card(rank="9", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )
        chosen = self.ai.select_action(state, legal, AgentContext(step_no=1))
        self.assertEqual(chosen.declared_pattern, PatternType.SINGLE)

    def test_a3_avoid_breaking_basic_group_without_need(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="5", suit="S"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="5", suit="S"),), PatternType.SINGLE),
        )
        chosen = self.ai.select_action(state, legal, AgentContext(step_no=2))
        self.assertEqual(chosen.cards[0].rank, "5")

    def test_a4_choose_from_obviously_reasonable_set(self) -> None:
        hand = (
            Card(rank="4", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
            Card(rank="8", suit="C"),
            Card(rank="8", suit="D"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="4", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="8", suit="S"),
                    Card(rank="8", suit="H"),
                    Card(rank="8", suit="C"),
                    Card(rank="8", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )
        chosen = self.ai.select_action(state, legal, AgentContext(step_no=3))
        better_set = {("single", "4")}
        worse_set = {("bomb", "8")}
        chosen_key = (chosen.declared_pattern.value, chosen.cards[0].rank)
        self.assertIn(chosen_key, better_set)
        self.assertNotIn(chosen_key, worse_set)

    def test_decision_basis_contains_rule_and_experience_references(self) -> None:
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        _ = self.ai.select_action(state, legal, AgentContext(step_no=4))
        self.assertIsNotNone(self.ai.last_decision_record)
        assert self.ai.last_decision_record is not None
        self.assertGreater(len(self.ai.last_decision_record.rule_references), 0)
        self.assertGreater(len(self.ai.last_decision_record.experience_references), 0)

    def test_rejected_conflict_not_in_rule_references_or_executable_basis(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="exp:conflict",
                layer="experience",
                content="经验建议：顺子 lead 优先。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="rule:ok",
                layer="rule",
                content="lead 场景应从合法动作集合中选择。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(docs))
        ai = RuleBasedAIAgent(player_id=0, name="ai-0", rag_advisor=advisor)

        state = _state_with_hand((Card(rank="4", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="4", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        selected = ai.select_action(state, legal, AgentContext(step_no=5))

        # Must always select from legal actions.
        self.assertIn(selected, legal)

        assert ai.last_decision_record is not None
        record = ai.last_decision_record
        self.assertNotIn("exp:conflict", record.rule_references)

        rag_meta = record.metadata.get("rag")
        self.assertIsInstance(rag_meta, dict)
        assert isinstance(rag_meta, dict)
        self.assertIn("rejected_refs", rag_meta)
        self.assertIn("exp:conflict", rag_meta["rejected_refs"])

    def test_rag_metadata_is_structured_for_regression(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:1",
                layer="rule",
                content="single pair triple bomb lead follow",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:1",
                layer="experience",
                content="低价值动作优先",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(docs))
        ai = RuleBasedAIAgent(player_id=0, name="ai-0", rag_advisor=advisor)

        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        _ = ai.select_action(state, legal, AgentContext(step_no=6))

        assert ai.last_decision_record is not None
        rag_meta = ai.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta, dict)
        assert isinstance(rag_meta, dict)
        self.assertIn("rule_refs", rag_meta)
        self.assertIn("experience_refs", rag_meta)
        self.assertIn("rejected_refs", rag_meta)
        self.assertIsInstance(rag_meta["rule_refs"], list)
        self.assertIsInstance(rag_meta["experience_refs"], list)
        self.assertIsInstance(rag_meta["rejected_refs"], list)
