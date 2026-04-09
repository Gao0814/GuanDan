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

    @staticmethod
    def _slice_between(text: str, start: str, end: str | None = None) -> str:
        start_idx = text.find(start)
        if start_idx < 0:
            return ""
        body = text[start_idx:]
        if end is None:
            return body
        end_idx = body.find(end)
        if end_idx < 0:
            return body
        return body[:end_idx]

    def _load_rule_text(self) -> str:
        path = self.rag_root / "rule_corpus" / "guandan_rules.md"
        return path.read_text(encoding="utf-8")

    def _load_experience_text(self) -> str:
        path = self.rag_root / "experience_corpus" / "basic_human_experience.md"
        return path.read_text(encoding="utf-8")

    def test_r7_rule_kb_implemented_scope_is_present_in_current_layer(self) -> None:
        text = self._load_rule_text()
        current_layer = self._slice_between(
            text,
            "## A. 当前已实现规则（可进入执行链路）",
            "## B. 第一阶段待补规则（当前未接入执行链路）",
        )
        self.assertTrue(current_layer)

        implemented_keywords = (
            "单张",
            "对子",
            "三张",
            "炸弹：4 张同点数",
            "pass",
            "大王",
            "小王",
            "顺子",
            "连对",
            "三带二",
        )
        for token in implemented_keywords:
            self.assertIn(token, current_layer)

    def test_r7_rule_kb_unimplemented_items_not_in_current_layer(self) -> None:
        text = self._load_rule_text()
        current_layer = self._slice_between(
            text,
            "## A. 当前已实现规则（可进入执行链路）",
            "## B. 第一阶段待补规则（当前未接入执行链路）",
        )
        self.assertTrue(current_layer)

        not_implemented_tokens = ("钢板", "同花顺", "天王炸", "王炸", "逢人配")
        for token in not_implemented_tokens:
            self.assertNotIn(token, current_layer)

    def test_r7_rule_kb_background_items_not_in_current_layer(self) -> None:
        text = self._load_rule_text()
        current_layer = self._slice_between(
            text,
            "## A. 当前已实现规则（可进入执行链路）",
            "## B. 第一阶段待补规则（当前未接入执行链路）",
        )
        self.assertTrue(current_layer)

        background_tokens = ("进贡", "还贡", "升级", "胜负")
        for token in background_tokens:
            self.assertNotIn(token, current_layer)

    def test_r7_experience_kb_has_connected_and_candidate_layers(self) -> None:
        text = self._load_experience_text()
        connected_layer = self._slice_between(
            text,
            "## A. 当前已接入经验（已进入排序逻辑）",
            "## B. 当前候选但未接入经验（可检索、不可当作已生效策略）",
        )
        candidate_layer = self._slice_between(
            text,
            "## B. 当前候选但未接入经验（可检索、不可当作已生效策略）",
            None,
        )

        self.assertTrue(connected_layer)
        self.assertTrue(candidate_layer)
        self.assertIn("低成本动作", connected_layer)
        self.assertIn("候选", candidate_layer)

    def test_r7_experience_kb_does_not_imply_engine_override_or_legal_bypass(self) -> None:
        text = self._load_experience_text()
        forbidden_phrases = (
            "可以替代引擎裁决",
            "可替代引擎裁决",
            "可绕过legal_actions",
            "可绕过 legal_actions",
            "可以绕过 legal_actions",
            "可以绕过合法动作集合",
            "直接执行动作",
        )
        for phrase in forbidden_phrases:
            self.assertNotIn(phrase, text)

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

    def test_implemented_pattern_keywords_are_not_rejected(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:straight",
                layer="rule",
                content="当前可执行规则包含顺子，遵循合法动作边界。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:pair_straight",
                layer="rule",
                content="当前可执行规则包含连对，遵循合法动作边界。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:triple_with_pair",
                layer="rule",
                content="当前可执行规则包含三带二，遵循合法动作边界。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
        )
        retriever = KnowledgeRetriever(docs)
        advisor = RAGAdvisor(retriever)

        evidence = advisor.retrieve_rule_evidence("顺子 连对 三带二", top_k=3)
        self.assertEqual(len(evidence), 3)
        self.assertTrue(all(item.metadata.get("status") == "accepted" for item in evidence))

    def test_unimplemented_keywords_are_rejected_conflict(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="rule:gangban",
                layer="rule",
                content="钢板是扩展规则，当前未接入执行链路。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:tonghuashun",
                layer="rule",
                content="同花顺是扩展规则，当前未接入执行链路。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="rule:tianwangzha",
                layer="rule",
                content="天王炸是扩展规则，当前未接入执行链路。",
                source_path="rag/rule_corpus/guandan_rules.md",
            ),
            KnowledgeDocument(
                doc_id="exp:fengrenpei",
                layer="experience",
                content="逢人配是扩展经验，当前未接入执行链路。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="exp:jingong_huangong",
                layer="experience",
                content="进贡还贡是扩展经验，当前未接入执行链路。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
            KnowledgeDocument(
                doc_id="exp:shengji_shengfu",
                layer="experience",
                content="升级胜负是扩展经验，当前未接入执行链路。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        retriever = KnowledgeRetriever(docs)
        advisor = RAGAdvisor(retriever)

        rule_ev = advisor.retrieve_rule_evidence("钢板 同花顺 天王炸", top_k=3)
        exp_ev = advisor.retrieve_experience_evidence("逢人配 进贡还贡 升级胜负", top_k=3)

        self.assertEqual(len(rule_ev), 3)
        self.assertEqual(len(exp_ev), 3)
        self.assertTrue(all(item.metadata.get("status") == "rejected_conflict" for item in rule_ev))
        self.assertTrue(all(item.metadata.get("status") == "rejected_conflict" for item in exp_ev))

    def test_experience_text_cannot_replace_engine_verdict(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="exp:rule_conflict",
                layer="experience",
                content="经验建议：可以直接跳过合法动作集合执行对子。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        retriever = KnowledgeRetriever(docs)
        advisor = RAGAdvisor(retriever)
        evidence = advisor.retrieve_experience_evidence("合法动作", top_k=1)
        self.assertEqual(len(evidence), 1)

        # Even with experience text, engine remains the only truth source.
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

    def test_rag_output_cannot_bypass_legal_actions_boundary(self) -> None:
        docs = (
            KnowledgeDocument(
                doc_id="exp:suggestion",
                layer="experience",
                content="建议优先出对子。",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        retriever = KnowledgeRetriever(docs)
        advisor = RAGAdvisor(retriever)
        _ = advisor.retrieve_experience_evidence("对子", top_k=1)

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
        legal_actions = engine.generate_legal_actions(state)
        self.assertFalse(
            any(
                action.declared_pattern == PatternType.PAIR and action.action_type == ActionType.PLAY
                for action in legal_actions
            )
        )

        illegal_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="7", suit="S"), Card(rank="7", suit="H")),
            declared_pattern=PatternType.PAIR,
        )
        with self.assertRaises(ValueError):
            engine.validate_action(state, illegal_action)
