"""Step-6 tests for baseline rule/experience AI behavior."""

from pathlib import Path
import json
import unittest
from unittest.mock import patch

from agents.base import AgentContext
from agents.deepseek_client import DeepSeekClient
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint
from rag.kb_loader import KnowledgeBaseLoader, KnowledgeDocument
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
                content="经验建议：同花顺 lead 优先。",
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

    def test_a5_new_patterns_context_selection_remains_stable(self) -> None:
        state = _state_with_hand(
            (
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="H"),
                Card(rank="10", suit="H"),
                Card(rank="J", suit="H"),
            )
        )
        legal = (
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="S"),
                    Card(rank="9", suit="S"),
                    Card(rank="10", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="7", suit="H"),
                    Card(rank="8", suit="H"),
                    Card(rank="9", suit="H"),
                    Card(rank="10", suit="H"),
                    Card(rank="J", suit="H"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        outputs = [
            self.ai.select_action(state, legal, AgentContext(step_no=100 + i))
            for i in range(10)
        ]
        first = outputs[0]
        self.assertTrue(all(o == first for o in outputs))
        self.assertEqual(first, legal[0])

    def test_prefers_straight_over_scattered_singles_when_leading(self) -> None:
        hand = (
            Card(rank="3", suit="S"),
            Card(rank="4", suit="S"),
            Card(rank="5", suit="S"),
            Card(rank="6", suit="S"),
            Card(rank="7", suit="S"),
            Card(rank="9", suit="H"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="H"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        chosen = self.ai.select_action(state, legal, AgentContext(step_no=200))
        self.assertEqual(chosen.declared_pattern, PatternType.STRAIGHT)

    def test_prefers_pair_straight_over_splitting_into_pairs(self) -> None:
        hand = (
            Card(rank="4", suit="S"),
            Card(rank="4", suit="H"),
            Card(rank="5", suit="S"),
            Card(rank="5", suit="H"),
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="9", suit="C"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="4", suit="S"),
                    Card(rank="4", suit="H"),
                ),
                PatternType.PAIR,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                ),
                PatternType.PAIR,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="4", suit="S"),
                    Card(rank="4", suit="H"),
                    Card(rank="5", suit="S"),
                    Card(rank="5", suit="H"),
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                ),
                PatternType.PAIR_STRAIGHT,
            ),
        )

        chosen = self.ai.select_action(state, legal, AgentContext(step_no=201))
        self.assertEqual(chosen.declared_pattern, PatternType.PAIR_STRAIGHT)

    def test_prefers_triple_with_pair_over_plain_triple(self) -> None:
        hand = (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="6", suit="D"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="Q", suit="C"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                    Card(rank="6", suit="D"),
                ),
                PatternType.TRIPLE,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="9", suit="S"),
                    Card(rank="9", suit="H"),
                ),
                PatternType.PAIR,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                    Card(rank="6", suit="D"),
                    Card(rank="9", suit="S"),
                    Card(rank="9", suit="H"),
                ),
                PatternType.TRIPLE_WITH_PAIR,
            ),
        )

        chosen = self.ai.select_action(state, legal, AgentContext(step_no=202))
        self.assertEqual(chosen.declared_pattern, PatternType.TRIPLE_WITH_PAIR)

    def test_new_pattern_context_does_not_use_unnecessary_bomb(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="J", suit="S"),
            Card(rank="Q", suit="S"),
            Card(rank="Q", suit="H"),
            Card(rank="Q", suit="C"),
            Card(rank="Q", suit="D"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="S"),
                    Card(rank="9", suit="S"),
                    Card(rank="10", suit="S"),
                    Card(rank="J", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="Q", suit="S"),
                    Card(rank="Q", suit="H"),
                    Card(rank="Q", suit="C"),
                    Card(rank="Q", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )

        chosen = self.ai.select_action(state, legal, AgentContext(step_no=203))
        self.assertNotEqual(chosen.declared_pattern, PatternType.BOMB)

    def test_i6_model_legal_suggestion_still_within_legal_actions(self) -> None:
        class LegalSuggestionAdvisor:
            def suggest_action(self, state, legal_actions, context):
                return legal_actions[0]

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=LegalSuggestionAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=300))
        self.assertIn(chosen, legal)
        self.assertEqual(chosen, legal[0])

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "accepted_legal_suggestion")

    def test_i6_illegal_model_suggestion_rejected_and_engine_truth_preserved(self) -> None:
        illegal_suggestion = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="8", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )

        class IllegalSuggestionAdvisor:
            def suggest_action(self, state, legal_actions, context):
                return illegal_suggestion

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=IllegalSuggestionAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=301))
        self.assertIn(chosen, legal)
        self.assertNotEqual(chosen, illegal_suggestion)

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "rejected_non_legal_suggestion")

        # Even if a model proposes an illegal action, engine remains final truth.
        engine = BaseRuleEngine()
        before_hands = tuple(tuple(player.hand_cards) for player in state.players)
        before_step = state.step_no
        with self.assertRaises(ValueError):
            engine.apply_action(state, illegal_suggestion)
        self.assertEqual(before_hands, tuple(tuple(player.hand_cards) for player in state.players))
        self.assertEqual(before_step, state.step_no)

    def test_i6_enabled_with_key_calls_replaceable_advisor(self) -> None:
        class CountingAdvisor:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action(self, state, legal_actions, context):
                self.calls += 1
                return {
                    "action_type": "play",
                    "declared_pattern": "single",
                    "cards": ["7S"],
                }

        advisor = CountingAdvisor()
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_ENABLED": "true",
                "DEEPSEEK_API_KEY": "test-key",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=False,
        ):
            ai = RuleBasedAIAgent(
                player_id=0,
                name="ai-0",
                deepseek_action_advisor=advisor,
            )

        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        chosen = ai.select_action(state, legal, AgentContext(step_no=302))

        self.assertEqual(advisor.calls, 1)
        self.assertIn(chosen, legal)
        self.assertEqual(chosen, legal[0])
        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "accepted_legal_suggestion")

    def test_i5_missing_key_does_not_call_model_even_if_enabled(self) -> None:
        class CountingAdvisor:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action(self, state, legal_actions, context):
                self.calls += 1
                return legal_actions[-1]

        advisor = CountingAdvisor()
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_ENABLED": "true",
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=False,
        ):
            ai = RuleBasedAIAgent(
                player_id=0,
                name="ai-0",
                deepseek_action_advisor=advisor,
            )

        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        chosen = ai.select_action(state, legal, AgentContext(step_no=303))

        self.assertEqual(advisor.calls, 0)
        self.assertIn(chosen, legal)
        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "disabled")

    def test_effect_compare_deepseek_enabled_is_better_or_not_worse(self) -> None:
        # Baseline chooses local heuristic result from legal_actions.
        base_ai = RuleBasedAIAgent(player_id=0, name="ai-0", deepseek_enabled=False)

        # Model suggests a reasonable stronger structure in the same legal set.
        class BetterSuggestionAdvisor:
            def suggest_action(self, state, legal_actions, context):
                return {
                    "action_type": "play",
                    "declared_pattern": "straight",
                    "cards": ["3S", "4S", "5S", "6S", "7S"],
                }

        model_ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=BetterSuggestionAdvisor(),
        )

        state = _state_with_hand(
            (
                Card(rank="3", suit="S"),
                Card(rank="4", suit="S"),
                Card(rank="5", suit="S"),
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="H"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        base_chosen = base_ai.select_action(state, legal, AgentContext(step_no=400))
        model_chosen = model_ai.select_action(state, legal, AgentContext(step_no=400))

        reasonable_set = {legal[2]}
        self.assertIn(base_chosen, legal)
        self.assertIn(model_chosen, legal)
        self.assertIn(model_chosen, reasonable_set)

        assert model_ai.last_decision_record is not None
        model_meta = model_ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "accepted_legal_suggestion")

    def test_effect_guard_rejects_legal_but_worse_bomb_suggestion(self) -> None:
        class WorseBombAdvisor:
            def suggest_action(self, state, legal_actions, context):
                return {
                    "action_type": "play",
                    "declared_pattern": "bomb",
                    "cards": ["QH", "QS", "QC", "QD"],
                }

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=WorseBombAdvisor(),
        )
        state = _state_with_hand(
            (
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
                Card(rank="J", suit="S"),
                Card(rank="Q", suit="S"),
                Card(rank="Q", suit="H"),
                Card(rank="Q", suit="C"),
                Card(rank="Q", suit="D"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="S"),
                    Card(rank="9", suit="S"),
                    Card(rank="10", suit="S"),
                    Card(rank="J", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="Q", suit="H"),
                    Card(rank="Q", suit="S"),
                    Card(rank="Q", suit="C"),
                    Card(rank="Q", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=401))
        self.assertIn(chosen, legal)
        self.assertNotEqual(chosen.declared_pattern, PatternType.BOMB)

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "rejected_degradation_fallback")

    def test_effect_guard_keeps_new_pattern_usage_not_regressed(self) -> None:
        class RegressiveSingleAdvisor:
            def suggest_action(self, state, legal_actions, context):
                return {
                    "action_type": "play",
                    "declared_pattern": "single",
                    "cards": ["3S"],
                }

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=RegressiveSingleAdvisor(),
        )

        state = _state_with_hand(
            (
                Card(rank="3", suit="S"),
                Card(rank="4", suit="S"),
                Card(rank="5", suit="S"),
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="H"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=402))
        self.assertEqual(chosen.declared_pattern, PatternType.STRAIGHT)

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "rejected_degradation_fallback")

    def test_effect_stability_with_fluctuating_model_output_stays_reasonable(self) -> None:
        class FluctuatingAdvisor:
            def __init__(self) -> None:
                self.i = 0

            def suggest_action(self, state, legal_actions, context):
                seq = [
                    {"action_type": "play", "declared_pattern": "single", "cards": ["3S"]},
                    {"action_type": "play", "declared_pattern": "bomb", "cards": ["QH", "QS", "QC", "QD"]},
                    {"action_type": "play", "declared_pattern": "straight", "cards": ["7S", "8S", "9S", "10S", "JS"]},
                ]
                out = seq[self.i % len(seq)]
                self.i += 1
                return out

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            deepseek_enabled=True,
            deepseek_action_advisor=FluctuatingAdvisor(),
        )
        state = _state_with_hand(
            (
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
                Card(rank="J", suit="S"),
                Card(rank="Q", suit="S"),
                Card(rank="Q", suit="H"),
                Card(rank="Q", suit="C"),
                Card(rank="Q", suit="D"),
                Card(rank="3", suit="S"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="S"),
                    Card(rank="9", suit="S"),
                    Card(rank="10", suit="S"),
                    Card(rank="J", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="Q", suit="H"),
                    Card(rank="Q", suit="S"),
                    Card(rank="Q", suit="C"),
                    Card(rank="Q", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )

        reasonable_set = {legal[1]}  # straight only
        outputs = [
            ai.select_action(state, legal, AgentContext(step_no=500 + i))
            for i in range(9)
        ]
        self.assertTrue(all(output in legal for output in outputs))
        self.assertTrue(all(output in reasonable_set for output in outputs))

    def test_rag_context_injected_to_model_when_rag_hits(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:hit",
                layer="rule",
                content="先手 单张 保组 规则参考",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:hit",
                layer="experience",
                content="先手 单张 少破组 经验参考",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        rag_advisor = RAGAdvisor(KnowledgeRetriever(docs))

        captured: dict[str, object] = {}

        class CaptureAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                captured["rag_context"] = rag_context
                return legal_actions[0]

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=rag_advisor,
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=600))
        self.assertIn(chosen, legal)

        rag_context = captured.get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)
        self.assertGreaterEqual(len(rag_context.get("rule", [])), 1)
        self.assertGreaterEqual(len(rag_context.get("experience", [])), 1)

        assert ai.last_decision_record is not None
        rag_meta = ai.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta, dict)
        assert isinstance(rag_meta, dict)
        self.assertEqual(rag_meta.get("context_status"), "rag_injected")

    def test_without_rag_advisor_keeps_original_chain(self) -> None:
        class CaptureAdvisor:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action(self, state, legal_actions, context, rag_context=None):
                self.calls += 1
                return legal_actions[0]

        advisor = CaptureAdvisor()
        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=None,
            deepseek_enabled=True,
            deepseek_action_advisor=advisor,
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=601))
        self.assertEqual(advisor.calls, 1)
        self.assertIn(chosen, legal)

        assert ai.last_decision_record is not None
        rag_meta = ai.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta, dict)
        assert isinstance(rag_meta, dict)
        self.assertEqual(rag_meta.get("context_status"), "no_rag")

    def test_rag_no_hit_does_not_break_mainline(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:miss",
                layer="rule",
                content="完全不相关内容xyz",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:miss",
                layer="experience",
                content="完全不相关经验abc",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        rag_advisor = RAGAdvisor(KnowledgeRetriever(docs))

        captured: dict[str, object] = {}

        class CaptureAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                captured["rag_context"] = rag_context
                return legal_actions[0]

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=rag_advisor,
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=602))
        self.assertIn(chosen, legal)

        assert ai.last_decision_record is not None
        rag_meta = ai.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta, dict)
        assert isinstance(rag_meta, dict)
        self.assertEqual(rag_meta.get("context_status"), "rag_no_hit")
        self.assertIsNone(captured.get("rag_context"))

    def test_rag_context_is_bounded_and_separated_without_full_text_injection(self) -> None:
        long_rule = "顺子 连对 三带二 保组 " + ("R" * 400)
        long_exp = "保组 少破组 复合牌型优先 避免无意义炸弹 " + ("E" * 420)
        docs = (
            KnowledgeDocument(
                doc_id="rule:1",
                layer="rule",
                content=long_rule,
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:2",
                layer="rule",
                content="先手 单张 保组 规则2",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:3",
                layer="rule",
                content="先手 单张 复合牌型优先 规则3",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:4",
                layer="rule",
                content="先手 单张 规则4 应被上限裁剪",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:1",
                layer="experience",
                content=long_exp,
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="exp:2",
                layer="experience",
                content="先手 单张 少破组 经验2",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="exp:3",
                layer="experience",
                content="先手 单张 避免无意义炸弹 经验3",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="exp:4",
                layer="experience",
                content="先手 单张 经验4 应被上限裁剪",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        rag_advisor = RAGAdvisor(KnowledgeRetriever(docs))

        captured: dict[str, object] = {}

        class CaptureAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                captured["rag_context"] = rag_context
                return legal_actions[0]

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=rag_advisor,
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=607))
        self.assertIn(chosen, legal)

        rag_context = captured.get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)

        rule_items = rag_context.get("rule")
        exp_items = rag_context.get("experience")
        self.assertIsInstance(rule_items, list)
        self.assertIsInstance(exp_items, list)
        assert isinstance(rule_items, list)
        assert isinstance(exp_items, list)

        # 1) count must be bounded
        self.assertLessEqual(len(rule_items), 3)
        self.assertLessEqual(len(exp_items), 3)

        # 2) each snippet length must be bounded
        self.assertTrue(all(len(str(item.get("snippet", ""))) <= 160 for item in rule_items))
        self.assertTrue(all(len(str(item.get("snippet", ""))) <= 160 for item in exp_items))

        # 3) do not inject full corpus text
        self.assertNotIn(long_rule, [str(item.get("snippet", "")) for item in rule_items])
        self.assertNotIn(long_exp, [str(item.get("snippet", "")) for item in exp_items])

        # 4) rule evidence and experience evidence must stay distinguishable
        self.assertTrue(all(str(item.get("doc_id", "")).startswith("rule:") for item in rule_items))
        self.assertTrue(all(str(item.get("doc_id", "")).startswith("exp:") for item in exp_items))

    def test_with_rag_context_final_action_still_bounded_by_legal_actions(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:hit",
                layer="rule",
                content="先手 单张 保组 规则参考",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
        )
        rag_advisor = RAGAdvisor(KnowledgeRetriever(docs))

        class IllegalSuggestionAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                return {
                    "action_type": "play",
                    "declared_pattern": "single",
                    "cards": ["8S"],
                }

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=rag_advisor,
            deepseek_enabled=True,
            deepseek_action_advisor=IllegalSuggestionAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=603))
        self.assertIn(chosen, legal)

    def test_decision_trace_distinguishes_rag_states(self) -> None:
        class CaptureAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                return legal_actions[0]

        # no_rag
        ai_no_rag = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=None,
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )
        _ = ai_no_rag.select_action(state, legal, AgentContext(step_no=604))
        assert ai_no_rag.last_decision_record is not None
        rag_meta_no = ai_no_rag.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta_no, dict)
        assert isinstance(rag_meta_no, dict)
        self.assertEqual(rag_meta_no.get("context_status"), "no_rag")

        # rag_no_hit
        docs_no_hit = (
            KnowledgeDocument(
                doc_id="rule:miss",
                layer="rule",
                content="zzz_only_ascii_no_overlap",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
        )
        ai_no_hit = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=RAGAdvisor(KnowledgeRetriever(docs_no_hit)),
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        _ = ai_no_hit.select_action(state, legal, AgentContext(step_no=605))
        assert ai_no_hit.last_decision_record is not None
        rag_meta_miss = ai_no_hit.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta_miss, dict)
        assert isinstance(rag_meta_miss, dict)
        self.assertEqual(rag_meta_miss.get("context_status"), "rag_no_hit")

        # rag_injected
        docs_hit = (
            KnowledgeDocument(
                doc_id="rule:hit",
                layer="rule",
                content="先手 单张 保组 规则参考",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
        )
        ai_hit = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=RAGAdvisor(KnowledgeRetriever(docs_hit)),
            deepseek_enabled=True,
            deepseek_action_advisor=CaptureAdvisor(),
        )
        _ = ai_hit.select_action(state, legal, AgentContext(step_no=606))
        assert ai_hit.last_decision_record is not None
        rag_meta_hit = ai_hit.last_decision_record.metadata.get("rag")
        self.assertIsInstance(rag_meta_hit, dict)
        assert isinstance(rag_meta_hit, dict)
        self.assertEqual(rag_meta_hit.get("context_status"), "rag_injected")

    def test_prompt_and_focus_can_raise_accepted_and_reduce_rejected_degradation(self) -> None:
        # weak advisor: always suggests low-value single, should be rejected by degradation guard.
        class WeakSingleAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                return {
                    "action_type": "play",
                    "declared_pattern": "single",
                    "cards": ["3S"],
                }

        # focus-aware deepseek client: chooses first preferred compound pattern from action_focus.
        def focus_transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else ""
            payload = json.loads(body)
            messages = payload.get("messages", [])
            user_content = messages[1].get("content") if len(messages) > 1 else "{}"
            user_payload = json.loads(user_content)
            preferred = user_payload.get("action_focus", {}).get("preferred_patterns", [])
            legal = user_payload.get("legal_actions", [])

            chosen = None
            for pattern_name in preferred:
                for action in legal:
                    if action.get("declared_pattern") == pattern_name:
                        chosen = action
                        break
                if chosen is not None:
                    break
            if chosen is None and legal:
                chosen = legal[0]

            return json.dumps({"choices": [{"message": {"content": json.dumps(chosen or {})}}]})

        weak_ai = RuleBasedAIAgent(
            player_id=0,
            name="weak-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=WeakSingleAdvisor(),
        )
        improved_ai = RuleBasedAIAgent(
            player_id=0,
            name="improved-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=DeepSeekClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=focus_transport,
            ),
        )

        state = _state_with_hand(
            (
                Card(rank="3", suit="S"),
                Card(rank="4", suit="S"),
                Card(rank="5", suit="S"),
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="H"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        _ = weak_ai.select_action(state, legal, AgentContext(step_no=1001))
        _ = improved_ai.select_action(state, legal, AgentContext(step_no=1002))

        weak_counts = weak_ai.get_model_status_counts()
        improved_counts = improved_ai.get_model_status_counts()

        self.assertGreaterEqual(
            improved_counts.get("accepted_legal_suggestion", 0),
            weak_counts.get("accepted_legal_suggestion", 0),
        )
        self.assertLessEqual(
            improved_counts.get("rejected_degradation_fallback", 0),
            weak_counts.get("rejected_degradation_fallback", 0),
        )

    def test_timeout_retry_can_smooth_fallback_error_to_empty_response_fallback(self) -> None:
        calls = {"n": 0}

        def timeout_then_empty_transport(request, timeout: float) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError("simulated timeout")
            return json.dumps({"choices": [{"message": {"content": ""}}]})

        ai = RuleBasedAIAgent(
            player_id=0,
            name="retry-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=DeepSeekClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=timeout_then_empty_transport,
            ),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=1003))
        self.assertIn(chosen, legal)
        self.assertEqual(calls["n"], 2)

        counts = ai.get_model_status_counts()
        self.assertEqual(counts.get("fallback_error", 0), 0)
        self.assertGreaterEqual(counts.get("empty_response_fallback", 0), 1)

    def test_rag_query_is_chinese_deduplicated_and_not_english_stack(self) -> None:
        lead_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="6", suit="S"), Card(rank="6", suit="H")),
            declared_pattern=PatternType.PAIR,
        )
        state = GameState(
            players=(
                PlayerState(
                    player_id=0,
                    hand_cards=(
                        Card(rank="3", suit="S"),
                        Card(rank="4", suit="S"),
                        Card(rank="5", suit="S"),
                        Card(rank="6", suit="S"),
                        Card(rank="7", suit="S"),
                        Card(rank="7", suit="H"),
                        Card(rank="7", suit="D"),
                        Card(rank="9", suit="C"),
                        Card(rank="9", suit="H"),
                        Card(rank="Q", suit="S"),
                        Card(rank="Q", suit="H"),
                        Card(rank="Q", suit="C"),
                        Card(rank="Q", suit="D"),
                    ),
                ),
                PlayerState(player_id=1, hand_cards=()),
                PlayerState(player_id=2, hand_cards=()),
                PlayerState(player_id=3, hand_cards=()),
            ),
            current_player_id=0,
            table_constraint=TableConstraint(
                leading_action=lead_action,
                required_pattern=PatternType.PAIR,
                min_strength_hint=6,
            ),
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (Card(rank="9", suit="C"), Card(rank="9", suit="H")),
                PatternType.PAIR,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="7", suit="S"),
                    Card(rank="7", suit="H"),
                    Card(rank="7", suit="D"),
                ),
                PatternType.TRIPLE,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="Q", suit="S"),
                    Card(rank="Q", suit="H"),
                    Card(rank="Q", suit="C"),
                    Card(rank="Q", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )

        query = RuleBasedAIAgent._build_rag_query(state, legal)

        self.assertIsInstance(query, str)
        self.assertIn("单张", query)
        self.assertIn("对子", query)
        self.assertIn("三张", query)
        self.assertIn("顺子", query)
        self.assertIn("炸弹", query)
        self.assertIn("跟牌", query)
        self.assertIn("压牌", query)
        self.assertIn("要求牌型对子", query)
        self.assertIn("最小强度6", query)
        self.assertIn("当前领牌对子", query)
        self.assertIn("保组", query)
        self.assertIn("少破组", query)
        self.assertIn("复合牌型优先", query)
        self.assertIn("避免无意义炸弹", query)

        self.assertNotIn("straight", query)
        self.assertNotIn("pair_straight", query)
        self.assertNotIn("triple_with_pair", query)
        self.assertNotIn("lead", query)
        self.assertNotIn("follow", query)

        # Query should stay compressed: each pattern keyword appears at most once.
        self.assertEqual(query.count("顺子"), 1)
        self.assertLessEqual(query.count("炸弹"), 2)

    def test_rag_query_improves_hit_counts_over_old_query_in_typical_scenarios(self) -> None:
        loader = KnowledgeBaseLoader(Path(__file__).resolve().parents[1] / "rag")
        retriever = KnowledgeRetriever(loader.load_all_documents())

        def old_query(state: GameState, legal_actions: tuple[Action, ...]) -> str:
            return " ".join(
                [
                    " ".join(action.declared_pattern.value for action in legal_actions if action.declared_pattern),
                    "follow" if state.table_constraint.leading_action else "lead",
                ]
            ).strip()

        scenarios: list[tuple[GameState, tuple[Action, ...]]] = []

        # Scenario 1: lead with compound patterns and bomb.
        scenarios.append(
            (
                _state_with_hand(
                    (
                        Card(rank="3", suit="S"),
                        Card(rank="4", suit="S"),
                        Card(rank="5", suit="S"),
                        Card(rank="6", suit="S"),
                        Card(rank="7", suit="S"),
                        Card(rank="8", suit="S"),
                        Card(rank="8", suit="H"),
                        Card(rank="9", suit="S"),
                        Card(rank="9", suit="H"),
                        Card(rank="Q", suit="S"),
                        Card(rank="Q", suit="H"),
                        Card(rank="Q", suit="C"),
                        Card(rank="Q", suit="D"),
                    )
                ),
                (
                    Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="3", suit="S"),
                            Card(rank="4", suit="S"),
                            Card(rank="5", suit="S"),
                            Card(rank="6", suit="S"),
                            Card(rank="7", suit="S"),
                        ),
                        PatternType.STRAIGHT,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="8", suit="S"),
                            Card(rank="8", suit="H"),
                            Card(rank="9", suit="S"),
                            Card(rank="9", suit="H"),
                        ),
                        PatternType.PAIR_STRAIGHT,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="Q", suit="S"),
                            Card(rank="Q", suit="H"),
                            Card(rank="Q", suit="C"),
                            Card(rank="Q", suit="D"),
                        ),
                        PatternType.BOMB,
                    ),
                ),
            )
        )

        # Scenario 2: lead with triple_with_pair choices.
        scenarios.append(
            (
                _state_with_hand(
                    (
                        Card(rank="6", suit="S"),
                        Card(rank="6", suit="H"),
                        Card(rank="6", suit="D"),
                        Card(rank="9", suit="S"),
                        Card(rank="9", suit="H"),
                        Card(rank="3", suit="S"),
                        Card(rank="4", suit="S"),
                        Card(rank="5", suit="S"),
                        Card(rank="7", suit="S"),
                    )
                ),
                (
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="6", suit="S"),
                            Card(rank="6", suit="H"),
                            Card(rank="6", suit="D"),
                            Card(rank="9", suit="S"),
                            Card(rank="9", suit="H"),
                        ),
                        PatternType.TRIPLE_WITH_PAIR,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="3", suit="S"),
                            Card(rank="4", suit="S"),
                            Card(rank="5", suit="S"),
                            Card(rank="6", suit="S"),
                            Card(rank="7", suit="S"),
                        ),
                        PatternType.STRAIGHT,
                    ),
                ),
            )
        )

        # Scenario 3: follow with explicit table constraints.
        lead_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="7", suit="S"), Card(rank="7", suit="H")),
            declared_pattern=PatternType.PAIR,
        )
        scenarios.append(
            (
                GameState(
                    players=(
                        PlayerState(
                            player_id=0,
                            hand_cards=(
                                Card(rank="7", suit="C"),
                                Card(rank="7", suit="D"),
                                Card(rank="8", suit="S"),
                                Card(rank="8", suit="H"),
                                Card(rank="9", suit="S"),
                                Card(rank="9", suit="H"),
                            ),
                        ),
                        PlayerState(player_id=1, hand_cards=()),
                        PlayerState(player_id=2, hand_cards=()),
                        PlayerState(player_id=3, hand_cards=()),
                    ),
                    current_player_id=0,
                    table_constraint=TableConstraint(
                        leading_action=lead_action,
                        required_pattern=PatternType.PAIR,
                        min_strength_hint=7,
                    ),
                ),
                (
                    Action(
                        0,
                        ActionType.PLAY,
                        (Card(rank="7", suit="C"), Card(rank="7", suit="D")),
                        PatternType.PAIR,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (Card(rank="8", suit="S"), Card(rank="8", suit="H")),
                        PatternType.PAIR,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="7", suit="C"),
                            Card(rank="7", suit="D"),
                            Card(rank="8", suit="S"),
                            Card(rank="8", suit="H"),
                            Card(rank="9", suit="S"),
                            Card(rank="9", suit="H"),
                        ),
                        PatternType.PAIR_STRAIGHT,
                    ),
                ),
            )
        )

        improved_rule_cases = 0
        improved_exp_cases = 0
        old_rule_total = 0
        old_exp_total = 0
        new_rule_total = 0
        new_exp_total = 0

        for state, legal in scenarios:
            old_q = old_query(state, legal)
            new_q = RuleBasedAIAgent._build_rag_query(state, legal)

            old_rule_hits = retriever.retrieve(old_q, "rule", top_k=3)
            old_exp_hits = retriever.retrieve(old_q, "experience", top_k=3)
            new_rule_hits = retriever.retrieve(new_q, "rule", top_k=3)
            new_exp_hits = retriever.retrieve(new_q, "experience", top_k=3)

            old_rule_total += len(old_rule_hits)
            old_exp_total += len(old_exp_hits)
            new_rule_total += len(new_rule_hits)
            new_exp_total += len(new_exp_hits)

            self.assertGreaterEqual(len(new_rule_hits), len(old_rule_hits))
            self.assertGreaterEqual(len(new_exp_hits), len(old_exp_hits))
            if len(new_rule_hits) > len(old_rule_hits):
                improved_rule_cases += 1
            if len(new_exp_hits) > len(old_exp_hits):
                improved_exp_cases += 1

        self.assertGreaterEqual(improved_rule_cases, 2)
        self.assertGreaterEqual(improved_exp_cases, 2)
        self.assertGreater(new_rule_total, old_rule_total)
        self.assertGreater(new_exp_total, old_exp_total)

    def test_new_rag_query_does_not_change_legal_actions_boundary(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:1",
                layer="rule",
                content="顺子、连对、三带二都应在合法动作集合内选择。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:1",
                layer="experience",
                content="保组、少破组，避免无意义炸弹。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        rag_advisor = RAGAdvisor(KnowledgeRetriever(docs))

        class IllegalSuggestionAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                return {
                    "action_type": "play",
                    "declared_pattern": "single",
                    "cards": ["8S"],
                }

        ai = RuleBasedAIAgent(
            player_id=0,
            name="ai-0",
            rag_advisor=rag_advisor,
            deepseek_enabled=True,
            deepseek_action_advisor=IllegalSuggestionAdvisor(),
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=1401))
        self.assertIn(chosen, legal)

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "rejected_non_legal_suggestion")

    def test_prompt_guided_client_avoids_mechanical_straight_when_triple_with_pair_exists(self) -> None:
        chosen_patterns: list[str | None] = []

        def prompt_sensitive_transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else "{}"
            payload = json.loads(body)
            messages = payload.get("messages", [])
            system_content = messages[0].get("content", "") if messages else ""
            user_content = messages[1].get("content", "{}") if len(messages) > 1 else "{}"
            user_payload = json.loads(user_content)
            legal = user_payload.get("legal_actions", [])

            has_strong_guard = (
                "不要为了出顺子而拆更高价值组合" in system_content
                and "少破组、少浪费、组合完整" in system_content
            )

            chosen = None
            if has_strong_guard:
                for preferred in ("triple_with_pair", "pair_straight", "straight"):
                    for action in legal:
                        if action.get("declared_pattern") == preferred:
                            chosen = action
                            break
                    if chosen is not None:
                        break
            else:
                for action in legal:
                    if action.get("declared_pattern") == "straight":
                        chosen = action
                        break

            if chosen is None and legal:
                chosen = legal[0]

            chosen_patterns.append(chosen.get("declared_pattern") if isinstance(chosen, dict) else None)
            return json.dumps({"choices": [{"message": {"content": json.dumps(chosen or {})}}]})

        ai = RuleBasedAIAgent(
            player_id=0,
            name="prompt-guided-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=DeepSeekClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=prompt_sensitive_transport,
            ),
        )

        hand = (
            Card(rank="3", suit="S"),
            Card(rank="4", suit="H"),
            Card(rank="5", suit="C"),
            Card(rank="6", suit="C"),
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="7", suit="S"),
            Card(rank="4", suit="S"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="C"),
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                    Card(rank="4", suit="H"),
                    Card(rank="4", suit="S"),
                ),
                PatternType.TRIPLE_WITH_PAIR,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="H"),
                    Card(rank="5", suit="C"),
                    Card(rank="6", suit="C"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=1101))
        self.assertIn(chosen, legal)
        self.assertEqual(chosen.declared_pattern, PatternType.TRIPLE_WITH_PAIR)
        self.assertTrue(chosen_patterns)
        self.assertEqual(chosen_patterns[-1], "triple_with_pair")

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "accepted_legal_suggestion")

    def test_prompt_guided_client_avoids_mechanical_straight_when_pair_straight_exists(self) -> None:
        chosen_patterns: list[str | None] = []

        def prompt_sensitive_transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else "{}"
            payload = json.loads(body)
            messages = payload.get("messages", [])
            system_content = messages[0].get("content", "") if messages else ""
            user_content = messages[1].get("content", "{}") if len(messages) > 1 else "{}"
            user_payload = json.loads(user_content)
            legal = user_payload.get("legal_actions", [])

            has_strong_guard = (
                "不要为了出顺子而拆更高价值组合" in system_content
                and "少破组、少浪费、组合完整" in system_content
            )

            chosen = None
            if has_strong_guard:
                for preferred in ("pair_straight", "triple_with_pair", "straight"):
                    for action in legal:
                        if action.get("declared_pattern") == preferred:
                            chosen = action
                            break
                    if chosen is not None:
                        break
            else:
                for action in legal:
                    if action.get("declared_pattern") == "straight":
                        chosen = action
                        break

            if chosen is None and legal:
                chosen = legal[0]

            chosen_patterns.append(chosen.get("declared_pattern") if isinstance(chosen, dict) else None)
            return json.dumps({"choices": [{"message": {"content": json.dumps(chosen or {})}}]})

        ai = RuleBasedAIAgent(
            player_id=0,
            name="prompt-guided-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=DeepSeekClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=prompt_sensitive_transport,
            ),
        )

        hand = (
            Card(rank="5", suit="C"),
            Card(rank="5", suit="S"),
            Card(rank="6", suit="S"),
            Card(rank="6", suit="C"),
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="8", suit="C"),
            Card(rank="9", suit="D"),
            Card(rank="10", suit="H"),
        )
        state = _state_with_hand(hand)
        legal = (
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="5", suit="C"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="C"),
                    Card(rank="7", suit="S"),
                    Card(rank="7", suit="H"),
                ),
                PatternType.PAIR_STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="C"),
                    Card(rank="9", suit="D"),
                    Card(rank="10", suit="H"),
                ),
                PatternType.STRAIGHT,
            ),
        )

        chosen = ai.select_action(state, legal, AgentContext(step_no=1102))
        self.assertIn(chosen, legal)
        self.assertEqual(chosen.declared_pattern, PatternType.PAIR_STRAIGHT)
        self.assertTrue(chosen_patterns)
        self.assertEqual(chosen_patterns[-1], "pair_straight")

        assert ai.last_decision_record is not None
        model_meta = ai.last_decision_record.metadata.get("model")
        self.assertIsInstance(model_meta, dict)
        assert isinstance(model_meta, dict)
        self.assertEqual(model_meta.get("status"), "accepted_legal_suggestion")

    def test_prompt_guided_client_improves_accept_and_reduces_straight_rejected(self) -> None:
        class StraightOnlyAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                for action in legal_actions:
                    if action.declared_pattern == PatternType.STRAIGHT:
                        return {
                            "action_type": action.action_type.value,
                            "declared_pattern": "straight",
                            "cards": [f"{c.rank}{c.suit or ''}" for c in action.cards],
                        }
                return legal_actions[0]

        prompt_chosen_patterns: list[str | None] = []

        def prompt_sensitive_transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else "{}"
            payload = json.loads(body)
            messages = payload.get("messages", [])
            system_content = messages[0].get("content", "") if messages else ""
            user_content = messages[1].get("content", "{}") if len(messages) > 1 else "{}"
            user_payload = json.loads(user_content)
            legal = user_payload.get("legal_actions", [])

            has_strong_guard = (
                "不要为了出顺子而拆更高价值组合" in system_content
                and "少破组、少浪费、组合完整" in system_content
            )

            chosen = None
            if has_strong_guard:
                for preferred in ("triple_with_pair", "pair_straight", "straight"):
                    for action in legal:
                        if action.get("declared_pattern") == preferred:
                            chosen = action
                            break
                    if chosen is not None:
                        break
            else:
                for action in legal:
                    if action.get("declared_pattern") == "straight":
                        chosen = action
                        break

            if chosen is None and legal:
                chosen = legal[0]

            prompt_chosen_patterns.append(chosen.get("declared_pattern") if isinstance(chosen, dict) else None)
            return json.dumps({"choices": [{"message": {"content": json.dumps(chosen or {})}}]})

        weak_ai = RuleBasedAIAgent(
            player_id=0,
            name="weak-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=StraightOnlyAdvisor(),
        )
        prompt_ai = RuleBasedAIAgent(
            player_id=0,
            name="prompt-ai",
            deepseek_enabled=True,
            deepseek_action_advisor=DeepSeekClient(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=prompt_sensitive_transport,
            ),
        )

        scenarios = [
            (
                _state_with_hand(
                    (
                        Card(rank="3", suit="S"),
                        Card(rank="4", suit="H"),
                        Card(rank="5", suit="C"),
                        Card(rank="6", suit="C"),
                        Card(rank="6", suit="S"),
                        Card(rank="6", suit="H"),
                        Card(rank="7", suit="S"),
                        Card(rank="4", suit="S"),
                    )
                ),
                (
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="6", suit="C"),
                            Card(rank="6", suit="S"),
                            Card(rank="6", suit="H"),
                            Card(rank="4", suit="H"),
                            Card(rank="4", suit="S"),
                        ),
                        PatternType.TRIPLE_WITH_PAIR,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="3", suit="S"),
                            Card(rank="4", suit="H"),
                            Card(rank="5", suit="C"),
                            Card(rank="6", suit="C"),
                            Card(rank="7", suit="S"),
                        ),
                        PatternType.STRAIGHT,
                    ),
                ),
            ),
            (
                _state_with_hand(
                    (
                        Card(rank="5", suit="C"),
                        Card(rank="5", suit="S"),
                        Card(rank="6", suit="S"),
                        Card(rank="6", suit="C"),
                        Card(rank="7", suit="S"),
                        Card(rank="7", suit="H"),
                        Card(rank="8", suit="C"),
                        Card(rank="9", suit="D"),
                        Card(rank="10", suit="H"),
                    )
                ),
                (
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="5", suit="C"),
                            Card(rank="5", suit="S"),
                            Card(rank="6", suit="S"),
                            Card(rank="6", suit="C"),
                            Card(rank="7", suit="S"),
                            Card(rank="7", suit="H"),
                        ),
                        PatternType.PAIR_STRAIGHT,
                    ),
                    Action(
                        0,
                        ActionType.PLAY,
                        (
                            Card(rank="6", suit="S"),
                            Card(rank="7", suit="S"),
                            Card(rank="8", suit="C"),
                            Card(rank="9", suit="D"),
                            Card(rank="10", suit="H"),
                        ),
                        PatternType.STRAIGHT,
                    ),
                ),
            ),
        ]

        weak_rejected = 0
        weak_rejected_straight = 0
        prompt_rejected = 0
        prompt_rejected_straight = 0

        for i, (state, legal) in enumerate(scenarios):
            weak_chosen = weak_ai.select_action(state, legal, AgentContext(step_no=1200 + i))
            self.assertIn(weak_chosen, legal)
            assert weak_ai.last_decision_record is not None
            weak_model = weak_ai.last_decision_record.metadata.get("model", {})
            if weak_model.get("status") == "rejected_degradation_fallback":
                weak_rejected += 1
                weak_rejected_straight += 1

            prompt_chosen = prompt_ai.select_action(state, legal, AgentContext(step_no=1300 + i))
            self.assertIn(prompt_chosen, legal)
            assert prompt_ai.last_decision_record is not None
            prompt_model = prompt_ai.last_decision_record.metadata.get("model", {})
            suggested_pattern = prompt_chosen_patterns[-1] if prompt_chosen_patterns else None
            if prompt_model.get("status") == "rejected_degradation_fallback":
                prompt_rejected += 1
                if suggested_pattern == "straight":
                    prompt_rejected_straight += 1

        weak_counts = weak_ai.get_model_status_counts()
        prompt_counts = prompt_ai.get_model_status_counts()

        self.assertGreaterEqual(
            prompt_counts.get("accepted_legal_suggestion", 0),
            weak_counts.get("accepted_legal_suggestion", 0),
        )
        self.assertLessEqual(prompt_rejected, weak_rejected)
        self.assertLess(prompt_rejected_straight, weak_rejected_straight)
