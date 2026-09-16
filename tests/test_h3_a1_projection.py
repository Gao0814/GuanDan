from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest

from agents.action_structure import summarize_candidate_structures
from agents.deepseek_client import DeepSeekClient
from agents.rag_advisor import RAGAdvisor
from agents.strategy_recommendation import build_strategy_recommendation
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _action(action_id: int, pattern: str, cards: list[str], *, wildcard_count: int = 0) -> dict[str, object]:
    return {
        "action_id": action_id, "declared_pattern": pattern,
        "declared_cards": [card[:-1] if card not in {"SJ", "BJ"} else card for card in cards],
        "carrier_cards": list(cards), "wildcard_count": wildcard_count,
        "wildcard_info": [{}] * wildcard_count, "display_text": f"{pattern}:{action_id}",
    }


def _observation(cards: list[str], *, follow: bool = False) -> dict[str, object]:
    table = _action(90, "single", ["3H"]) if follow else None
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_count": len(cards), "hand_cards": cards},
        "current_round": {
            "step_no": 1, "round_no": 1, "current_player_id": 1, "current_level_rank": "2",
            "constraint": "single" if follow else "free", "table_action": table,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 6, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": 2, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": 7, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


class H3A1ProjectionTests(unittest.TestCase):
    def test_canonical_candidate_parser_rejects_missing_and_inconsistent_fields(self) -> None:
        observation = _observation(["3S", "4S"])
        action = _action(1, "single", ["3S"])
        for key in ("declared_cards", "wildcard_info", "display_text"):
            malformed = dict(action)
            malformed.pop(key)
            self.assertIsNone(summarize_candidate_structures(observation, [malformed]))
        malformed_pass = _action(2, "pass", ["3S"])
        self.assertIsNone(summarize_candidate_structures(observation, [malformed_pass]))

    def test_domains_drive_rag_query_and_reach_final_prompt(self) -> None:
        cases = [
            (_observation(["3S", "4S", "7S", "7H"]), [_action(1, "single", ["3S"]), _action(2, "pair", ["7S", "7H"]), _action(6, "single", ["7S"])]),
            (_observation(["AS", "4S"], follow=True), [_action(3, "single", ["AS"])]),
            (_observation(["7S", "7H", "7C", "7D"]), [_action(4, "bomb", ["7S", "7H", "7C", "7D"])]),
            (_observation(["3S"]), [_action(5, "single", ["3S"])]),
        ]
        domains: set[str] = set()
        recommendations = []
        for observation, actions in cases:
            recommendation = build_strategy_recommendation(observation, actions, strategy_context=SimpleNamespace(intent="support_teammate"))
            self.assertEqual(recommendation.status, "ready")
            domains.update(recommendation.strategy_domains)
            recommendations.append((observation, actions, recommendation))
        blocked = build_strategy_recommendation(*cases[1], strategy_context=SimpleNamespace(intent="block_opponent"))
        domains.update(blocked.strategy_domains)
        self.assertEqual(domains, {
            "overall_priority", "opening_free_lead", "hand_structure", "control_return_resource",
            "follow_control", "teammate_coordination", "danger_opponent_block",
            "bomb_wildcard_management", "endgame_planning", "uncertainty_probe",
        })
        observation, actions, recommendation = recommendations[0]
        advisor = RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents()))
        context = advisor.get_rag_context(observation=observation, legal_actions=actions, hand_eval={"label": "medium"}, strategy_recommendation=recommendation, top_k=10)
        self.assertIn("strategy_domains:", context["query"])
        self.assertEqual(context["scene_tags"]["strategy_domains"], ",".join(recommendation.strategy_domains))
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"],
            other_players=observation["other_players"], history=observation["history"],
            legal_actions=actions, rag_context=context, strategy_recommendation=recommendation,
        )
        self.assertIn("策略域：overall_priority、opening_free_lead", prompt)
        self.assertIn("strategy_domains:", prompt)

    def test_card_memory_is_retrievable_with_public_not_hidden_boundary(self) -> None:
        observation = _observation(["SJ", "AS", "10S", "5S", "3S"])
        actions = [_action(1, "single", ["3S"]), _action(2, "single", ["AS"])]
        advisor = RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents()))
        context = advisor.get_rag_context(observation=observation, legal_actions=actions, hand_eval={"label": "medium"}, top_k=20)
        hit = next(item for item in context["experience_hits"] if item["source_id"] == "exp_card_memory_001")
        self.assertIn("王、级牌、A、10、5", hit["snippet"])
        self.assertIn("不能当作炸弹或持牌事实", hit["snippet"])
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"],
            other_players=observation["other_players"], history=observation["history"], legal_actions=actions, rag_context=context,
        )
        self.assertIn("不能当作炸弹或持牌事实", prompt)

    def test_guidance_validation_rejects_unknown_and_preserves_four_five_bomb_comparison(self) -> None:
        observation = _observation(["7S", "7H", "7C", "7D", "7S", "9S"])
        actions = [_action(4, "bomb", ["7S", "7H", "7C", "7D"]), _action(5, "bomb", ["7S", "7H", "7C", "7D", "7S"]), _action(9, "single", ["9S"])]
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        self.assertEqual([(fact.action_id, fact.bomb_length, fact.clears_played_rank_groups) for fact in facts[:2]], [(4, 4, False), (5, 5, True)])
        recommendation = build_strategy_recommendation(observation, actions)
        self.assertIsNone(DeepSeekClient._validated_strategy_recommendation(replace(recommendation, strategy_domains=("unknown",)), actions))
        self.assertIsNone(DeepSeekClient._validated_strategy_recommendation(replace(recommendation, objective_codes=("unknown",)), actions))
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"], other_players=observation["other_players"],
            history=observation["history"], legal_actions=actions, strategy_recommendation=recommendation,
        )
        self.assertIn("炸弹长度=4", prompt)
        self.assertIn("炸弹长度=5", prompt)


if __name__ == "__main__":
    unittest.main()
