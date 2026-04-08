"""Step-7 tests for local RAG boundary and traceability constraints."""

from pathlib import Path
import unittest

from agents.rag_advisor import RAGAdvisor
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint
from rag.kb_loader import KnowledgeBaseLoader, KnowledgeDocument
from rag.retriever import KnowledgeRetriever


class TestRAGConstraints(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.rag_root = self.repo_root / "rag"
        self.loader = KnowledgeBaseLoader(self.rag_root)

    def test_u10_retrieval_boundary_only_two_corpora(self) -> None:
        docs = self.loader.load_all_documents()
        sources = {doc.source_path for doc in docs}
        self.assertEqual(
            sources,
            {
                "rag/rule_corpus/guandan_rules.md",
                "rag/experience_corpus/basic_human_experience.md",
            },
        )

    def test_u10_results_include_source_and_layer(self) -> None:
        docs = self.loader.load_all_documents()
        retriever = KnowledgeRetriever(docs)

        rule_hits = retriever.retrieve(query="炸弹 比较", layer="rule", top_k=3)
        exp_hits = retriever.retrieve(query="拆组", layer="experience", top_k=3)

        self.assertGreater(len(rule_hits), 0)
        self.assertGreater(len(exp_hits), 0)
        self.assertTrue(all(hit.source_path.endswith("guandan_rules.md") for hit in rule_hits))
        self.assertTrue(all(hit.layer == "rule" for hit in rule_hits))
        self.assertTrue(all(hit.source_path.endswith("basic_human_experience.md") for hit in exp_hits))
        self.assertTrue(all(hit.layer == "experience" for hit in exp_hits))

    def test_r3_no_other_game_rules_in_retrieval(self) -> None:
        docs = self.loader.load_all_documents()
        retriever = KnowledgeRetriever(docs)
        hits = retriever.retrieve(query="规则", layer="rule", top_k=10)

        banned_tokens = ("德州扑克", "斗地主", "UNO")
        for hit in hits:
            for token in banned_tokens:
                self.assertNotIn(token.lower(), hit.snippet.lower())

    def test_conflict_knowledge_marked_rejected_and_not_rule_truth(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="exp:1",
                layer="experience",
                content="经验建议：顺子优先出牌。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        retriever = KnowledgeRetriever(docs)
        advisor = RAGAdvisor(retriever)
        evidence = advisor.retrieve_experience_evidence("顺子", top_k=1)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].metadata.get("status"), "rejected_conflict")

        # Even if conflicting knowledge exists, rule engine remains the only truth source.
        engine = BaseRuleEngine()
        state = GameState(
            players=(
                PlayerState(player_id=0, hand_cards=(Card(rank="7", suit="S"),)),
                PlayerState(player_id=1, hand_cards=()),
                PlayerState(player_id=2, hand_cards=()),
                PlayerState(player_id=3, hand_cards=()),
            ),
            current_player_id=0,
            table_constraint=TableConstraint(),
        )
        illegal_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="7", suit="S"), Card(rank="7", suit="H")),
            declared_pattern=PatternType.PAIR,
        )
        with self.assertRaises(ValueError):
            engine.validate_action(state, illegal_action)
