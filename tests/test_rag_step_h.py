from pathlib import Path
import unittest

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from agents.deepseek_client import DeepSeekSuggestion
from agents.rag_advisor import RAGAdvisor
from rag.kb_loader import KnowledgeBaseLoader, KnowledgeDocument
from rag.retriever import KnowledgeRetriever


def _action(
    action_id: int,
    pattern: str,
    declared_cards: list[str],
    carrier_cards: list[str] | None = None,
    *,
    wildcard_count: int = 0,
    wildcard_info: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": declared_cards,
        "carrier_cards": carrier_cards if carrier_cards is not None else list(declared_cards),
        "wildcard_count": wildcard_count,
        "wildcard_info": wildcard_info or [],
        "display_text": f"{pattern}:{','.join(declared_cards)}" if declared_cards else "pass",
    }


def _observation(
    *,
    hand_count: int = 20,
    hand_cards: list[str] | None = None,
    constraint: str = "free",
    table_action: dict[str, object] | None = None,
    step_no: int = 0,
    other_hand_count: int = 20,
) -> dict[str, object]:
    if constraint != "free" and table_action is None:
        table_action = _action(99, "single", ["8"], ["8S"])
    cards = hand_cards if hand_cards is not None else ["3S"] * hand_count
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": cards,
            "hand_count": hand_count,
            "remaining_single_card_count": 4,
        },
        "current_round": {
            "step_no": step_no,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": constraint,
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _real_advisor() -> RAGAdvisor:
    loader = KnowledgeBaseLoader(Path("rag"))
    retriever = KnowledgeRetriever(loader.load_all_documents())
    return RAGAdvisor(retriever)


def _hit_ids(context: dict[str, object], key: str) -> list[str]:
    return [str(item.get("source_id")) for item in context.get(key, [])]  # type: ignore[union-attr]


class CountingClient:
    def __init__(self, action_id: int | None = 1) -> None:
        self.calls = 0
        self.last_rag_context: dict[str, object] | None = None
        self.action_id = action_id

    def suggest_action_id(self, **kwargs):
        self.calls += 1
        self.last_rag_context = kwargs.get("rag_context")
        return DeepSeekSuggestion(action_id=self.action_id, reasoning="test")


class CountingRAGAdvisor:
    def __init__(self) -> None:
        self.calls = 0

    def get_rag_context(self, **_kwargs):
        self.calls += 1
        return {
            "scene_tags": {"scene": "test"},
            "rule_hits": [],
            "experience_hits": [],
            "query": "scene:test",
        }


class RaisingRAGAdvisor:
    def __init__(self) -> None:
        self.calls = 0

    def get_rag_context(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("simulated rag failure")


class TestRAGStepH(unittest.TestCase):
    def test_front_matter_tags_are_parsed_from_markdown(self) -> None:
        docs = KnowledgeBaseLoader(Path("rag")).load_all_documents()
        required = {"id", "corpus", "scene", "phase", "hand_strength", "action_context", "topic", "priority", "keywords_cn"}

        self.assertGreater(len(docs), 10)
        for doc in docs:
            self.assertTrue(required.issubset(set(doc.metadata)))
            for key in ("scene", "phase", "hand_strength", "action_context", "topic", "priority"):
                value = doc.metadata[key]
                self.assertTrue(value)
                self.assertTrue(all(ord(ch) < 128 for ch in value))
            self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in doc.content))

    def test_tagged_retrieval_hits_lead_follow_and_endgame_experience(self) -> None:
        advisor = _real_advisor()

        lead_context = advisor.get_rag_context(
            observation=_observation(),
            legal_actions=[_action(1, "pair", ["7", "7"], ["7S", "7H"])],
            hand_eval={"label": "weak"},
            top_k=3,
        )
        follow_context = advisor.get_rag_context(
            observation=_observation(constraint="single:8", step_no=4),
            legal_actions=[_action(1, "single", ["9"], ["9S"]), _action(2, "pass", [], [])],
            hand_eval={"label": "medium"},
            top_k=3,
        )
        endgame_context = advisor.get_rag_context(
            observation=_observation(hand_count=4, step_no=18),
            legal_actions=[_action(1, "pair", ["9", "9"], ["9S", "9H"])],
            hand_eval={"label": "medium"},
            top_k=3,
        )

        self.assertIn("exp_lead_opening_weak_001", _hit_ids(lead_context, "experience_hits"))
        self.assertIn("exp_follow_response_basic_001", _hit_ids(follow_context, "experience_hits"))
        self.assertIn("exp_endgame_run_out_001", _hit_ids(endgame_context, "experience_hits"))

    def test_rule_topics_hit_wildcard_bomb_and_pass(self) -> None:
        advisor = _real_advisor()

        wildcard_context = advisor.get_rag_context(
            observation=_observation(hand_cards=["2H"] + ["3S"] * 19),
            legal_actions=[
                _action(
                    1,
                    "pair",
                    ["9", "9"],
                    ["9S", "2H"],
                    wildcard_count=1,
                    wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
                )
            ],
            hand_eval={"label": "medium"},
            top_k=3,
        )
        bomb_context = advisor.get_rag_context(
            observation=_observation(constraint="single:8", step_no=4),
            legal_actions=[
                _action(1, "single", ["9"], ["9S"]),
                _action(2, "bomb", ["6", "6", "6", "6"], ["6S", "6H", "6C", "6D"]),
                _action(3, "pass", [], []),
            ],
            hand_eval={"label": "medium"},
            top_k=3,
        )
        pass_context = advisor.get_rag_context(
            observation=_observation(constraint="single:8", step_no=4),
            legal_actions=[_action(1, "single", ["9"], ["9S"]), _action(2, "pass", [], [])],
            hand_eval={"label": "medium"},
            top_k=3,
        )

        self.assertIn("rule_wildcard_boundary_001", _hit_ids(wildcard_context, "rule_hits"))
        self.assertIn("rule_bomb_hierarchy_001", _hit_ids(bomb_context, "rule_hits"))
        self.assertIn("rule_pass_follow_001", _hit_ids(pass_context, "rule_hits"))

    def test_scene_tags_cover_lead_follow_and_endgame(self) -> None:
        lead_tags = RAGAdvisor._scene_tags(
            _observation(step_no=0),
            [_action(1, "single", ["9"], ["9S"])],
            {"label": "中等"},
        )
        follow_tags = RAGAdvisor._scene_tags(
            _observation(constraint="single:8", step_no=3),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "pass", [], [])],
            {"label": "中等"},
        )
        endgame_tags = RAGAdvisor._scene_tags(
            _observation(hand_count=5, step_no=12),
            [_action(1, "single", ["9"], ["9S"])],
            {"label": "中等"},
        )

        self.assertEqual(lead_tags["scene"], "lead_opening")
        self.assertEqual(follow_tags["scene"], "follow_response")
        self.assertEqual(endgame_tags["scene"], "endgame")

    def test_hand_strength_uses_unified_mapping(self) -> None:
        tags = RAGAdvisor._scene_tags(
            _observation(),
            [_action(1, "single", ["9"], ["9S"])],
            {"label": "较强", "total_score": 65},
        )

        self.assertEqual(tags["hand_strength"], "strong")

    def test_rag_context_separates_rule_and_experience_hits(self) -> None:
        advisor = _real_advisor()
        context = advisor.get_rag_context(
            observation=_observation(hand_cards=["2H"] + ["3S"] * 19),
            legal_actions=[
                _action(
                    1,
                    "pair",
                    ["9", "9"],
                    ["9S", "2H"],
                    wildcard_count=1,
                    wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
                )
            ],
            hand_eval={"label": "中等"},
            top_k=3,
        )

        self.assertIn("scene_tags", context)
        self.assertIn("rule_hits", context)
        self.assertIn("experience_hits", context)
        self.assertIsInstance(context["rule_hits"], list)
        self.assertIsInstance(context["experience_hits"], list)

    def test_tag_match_ranks_above_generic_keyword_match(self) -> None:
        documents = (
            KnowledgeDocument(
                doc_id="exp:any",
                layer="experience",
                content="开局 首出 弱牌 孤张 脱手 经验 候选 action_id。",
                source_path="rag/experience_corpus/basic_human_experience.md",
                metadata={
                    "id": "exp:any",
                    "corpus": "experience",
                    "scene": "any",
                    "phase": "any",
                    "hand_strength": "any",
                    "action_context": "any",
                    "topic": "opening",
                    "priority": "high",
                    "keywords_cn": "开局,首出,弱牌,孤张,脱手,经验",
                },
            ),
            KnowledgeDocument(
                doc_id="exp:exact",
                layer="experience",
                content="弱牌早期首出只作为策略参考，最终选择候选 action_id。",
                source_path="rag/experience_corpus/basic_human_experience.md",
                metadata={
                    "id": "exp:exact",
                    "corpus": "experience",
                    "scene": "lead_opening",
                    "phase": "opening",
                    "hand_strength": "weak",
                    "action_context": "free_lead",
                    "topic": "opening",
                    "priority": "low",
                    "keywords_cn": "弱牌,开局",
                },
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(documents))

        context = advisor.get_rag_context(
            observation=_observation(),
            legal_actions=[_action(1, "pair", ["7", "7"], ["7S", "7H"])],
            hand_eval={"label": "weak"},
            top_k=2,
        )

        self.assertEqual(_hit_ids(context, "experience_hits")[0], "exp:exact")

    def test_any_tag_is_fallback_but_lower_than_exact(self) -> None:
        documents = (
            KnowledgeDocument(
                doc_id="exp:any",
                layer="experience",
                content="通用经验只作兜底，最终选择候选 action_id。",
                source_path="rag/experience_corpus/basic_human_experience.md",
                metadata={
                    "id": "exp:any",
                    "corpus": "experience",
                    "scene": "any",
                    "phase": "any",
                    "hand_strength": "any",
                    "action_context": "any",
                    "topic": "control",
                    "priority": "high",
                    "keywords_cn": "通用,经验",
                },
            ),
            KnowledgeDocument(
                doc_id="exp:exact",
                layer="experience",
                content="跟牌经验只作策略参考，最终选择候选 action_id。",
                source_path="rag/experience_corpus/basic_human_experience.md",
                metadata={
                    "id": "exp:exact",
                    "corpus": "experience",
                    "scene": "follow_response",
                    "phase": "midgame",
                    "hand_strength": "any",
                    "action_context": "follow",
                    "topic": "follow_response",
                    "priority": "low",
                    "keywords_cn": "跟牌",
                },
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(documents))

        context = advisor.get_rag_context(
            observation=_observation(constraint="single:8", step_no=4),
            legal_actions=[_action(1, "single", ["9"], ["9S"]), _action(2, "pass", [], [])],
            hand_eval={"label": "medium"},
            top_k=2,
        )

        self.assertEqual(_hit_ids(context, "experience_hits"), ["exp:exact", "exp:any"])


    def test_query_contains_scene_phase_and_hand_strength(self) -> None:
        advisor = _real_advisor()
        context = advisor.get_rag_context(
            observation=_observation(),
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            hand_eval={"label": "偏弱"},
            top_k=1,
        )

        query = str(context["query"])
        self.assertIn("scene:lead_opening", query)
        self.assertIn("phase:opening", query)
        self.assertIn("hand_strength:weak", query)

    def test_local_shortcuts_skip_get_rag_context(self) -> None:
        rag = CountingRAGAdvisor()
        client = CountingClient()

        only_pass_agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )
        chosen = only_pass_agent.select_action(
            _observation(constraint="single:8"),
            [_action(7, "pass", [], [])],
        )
        self.assertEqual(chosen, 7)

        finish_agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )
        chosen = finish_agent.select_action(
            _observation(hand_count=2),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "pair", ["9", "9"], ["9S", "9H"])],
        )
        self.assertEqual(chosen, 2)

        opening_agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )
        chosen = opening_agent.select_action(
            _observation(hand_count=20),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "pair", ["7", "7"], ["7S", "7H"])],
        )
        self.assertEqual(chosen, 2)

        self.assertEqual(rag.calls, 0)
        self.assertEqual(client.calls, 0)

    def test_rag_exception_downgrades_to_empty_context(self) -> None:
        client = CountingClient(action_id=1)
        rag = RaisingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
        )

        chosen = agent.select_action(
            _observation(step_no=5),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "single", ["10"], ["10S"])],
        )

        self.assertEqual(chosen, 1)
        self.assertEqual(rag.calls, 1)
        self.assertEqual(client.last_rag_context, {"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""})

    def test_rag_does_not_override_legal_action_validation(self) -> None:
        client = CountingClient(action_id=999)
        rag = CountingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
        )

        chosen = agent.select_action(
            _observation(step_no=5),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "single", ["10"], ["10S"])],
        )

        self.assertIn(chosen, {1, 2})
        self.assertNotEqual(chosen, 999)
        self.assertEqual(rag.calls, 1)

    def test_rag_context_does_not_mutate_legal_actions(self) -> None:
        advisor = _real_advisor()
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "pass", [], []),
        ]
        before = [dict(action) for action in legal_actions]

        advisor.get_rag_context(
            observation=_observation(constraint="single:8", step_no=4),
            legal_actions=legal_actions,
            hand_eval={"label": "medium"},
            top_k=3,
        )

        self.assertEqual(legal_actions, before)

    def test_out_of_scope_content_is_not_accepted(self) -> None:
        documents = (
            KnowledgeDocument(
                doc_id="exp:test",
                layer="experience",
                content="MCTS 自博弈 强化学习 概率建模 风格识别 多局经验",
                source_path="rag/experience_corpus/basic_human_experience.md",
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(documents))

        context = advisor.get_rag_context(
            observation=_observation(),
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            hand_eval={"label": "中等"},
            top_k=3,
        )

        self.assertEqual(context["experience_hits"], [])

    def test_no_matching_tags_returns_empty_hits(self) -> None:
        documents = (
            KnowledgeDocument(
                doc_id="exp:follow-only",
                layer="experience",
                content="跟牌经验只作为候选动作排序参考。",
                source_path="rag/experience_corpus/basic_human_experience.md",
                metadata={
                    "id": "exp:follow-only",
                    "corpus": "experience",
                    "scene": "follow_response",
                    "phase": "midgame",
                    "hand_strength": "strong",
                    "action_context": "follow",
                    "topic": "follow_response",
                    "priority": "high",
                    "keywords_cn": "跟牌",
                },
            ),
        )
        advisor = RAGAdvisor(KnowledgeRetriever(documents))

        context = advisor.get_rag_context(
            observation=_observation(),
            legal_actions=[_action(1, "pair", ["7", "7"], ["7S", "7H"])],
            hand_eval={"label": "weak"},
            top_k=3,
        )

        self.assertEqual(context["experience_hits"], [])

    def test_rag_prompt_section_contains_tags_rules_and_experience(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info={
                "player_id": 1,
                "team": "1&3",
                "hand_cards": ["7S", "7H"],
                "hand_count": 2,
                "remaining_single_card_count": 0,
            },
            current_round={
                "step_no": 3,
                "round_no": 1,
                "current_player_id": 1,
                "current_level_rank": "2",
                "constraint": "single:8",
                "table_action": _action(99, "single", ["8"], ["8S"]),
            },
            other_players=[],
            history={"actions": [], "finish_order": []},
            legal_actions=[_action(1, "pair", ["7", "7"], ["7S", "7H"])],
            rag_context={
                "scene_tags": {"scene": "follow_response", "phase": "midgame"},
                "rule_hits": [
                    {
                        "source_id": "rule_pass_follow_001",
                        "snippet": "pass 规则只说明规则口径，不能替代 legal_actions。",
                        "metadata": {"priority": "high", "topic": "pass,follow_response"},
                    }
                ],
                "experience_hits": [
                    {
                        "source_id": "exp_follow_response_basic_001",
                        "snippet": "跟牌压制先看收益，最终选择候选 action_id。",
                        "metadata": {"priority": "high", "topic": "follow_response"},
                    }
                ],
                "query": "scene:follow_response phase:midgame",
            },
        )

        self.assertIn("【场景标签】", prompt)
        self.assertIn("scene: follow_response", prompt)
        self.assertIn("【规则库依据】", prompt)
        self.assertIn("rule_pass_follow_001", prompt)
        self.assertIn("【经验库依据】", prompt)
        self.assertIn("exp_follow_response_basic_001", prompt)
        self.assertIn("不能替代 legal_actions", prompt)


if __name__ == "__main__":
    unittest.main()
