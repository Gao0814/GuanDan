from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest

from agents.action_structure import CandidateStructure, select_candidate_structure_representatives, summarize_candidate_structures
from agents.deepseek_client import DeepSeekClient
from agents.rag_advisor import RAGAdvisor
from agents.strategy_recommendation import build_strategy_recommendation
from engine.cards import Card
from engine.game import GuanDanGame
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
            "constraint": table["display_text"] if follow else "free", "table_action": table,
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

    def test_noncanonical_payloads_fail_closed_and_finished_teammate_does_not_trigger_support(self) -> None:
        observation = _observation(["2H", "3S", "3H"])
        valid = _action(1, "pair", ["2H", "3S"], wildcard_count=1)
        valid["declared_cards"] = ["3", "3"]
        valid["wildcard_info"] = [{"carrier_card": "2H", "declared_as": "3"}]
        bad_payloads = []
        free_pass = _action(2, "pass", [])
        bad_payloads.append((observation, [free_pass]))
        bad_wildcard = dict(valid); bad_wildcard["wildcard_info"] = [{}]
        bad_payloads.append((observation, [bad_wildcard]))
        bad_declared = dict(valid); bad_declared["declared_cards"] = ["not-a-card", "3"]
        bad_payloads.append((observation, [bad_declared]))
        follow = _observation(["4S", "5S"], follow=True)
        follow["current_round"]["constraint"] = "unrelated"
        bad_payloads.append((follow, [_action(3, "single", ["4S"])]))
        bad_player = _observation(["3S", "4S"])
        bad_player["other_players"][0]["player_id"] = 99
        bad_payloads.append((bad_player, [_action(4, "single", ["3S"])]))
        for malformed_observation, actions in bad_payloads:
            self.assertIsNone(summarize_candidate_structures(malformed_observation, actions))
            self.assertEqual(build_strategy_recommendation(malformed_observation, actions).status, "unavailable")

        finished_teammate = _observation(["3S", "4S", "5S", "6S", "7S"])
        finished_teammate["other_players"][1].update({"finished": True, "hand_count": 0, "finish_rank": 1})
        recommendation = build_strategy_recommendation(
            finished_teammate, [_action(5, "single", ["3S"])], strategy_context=SimpleNamespace(intent="run_out")
        )
        self.assertNotIn("teammate_coordination", recommendation.strategy_domains)
        self.assertNotIn("support_teammate", recommendation.objective_codes)

    def test_candidate_and_table_actions_conserve_canonical_declarations(self) -> None:
        table_observation = _observation(["4S", "5S"], follow=True)
        table = table_observation["current_round"]["table_action"]
        assert isinstance(table, dict)
        table.update({
            "declared_cards": ["3"], "carrier_cards": ["2H"], "wildcard_count": 1,
            "wildcard_info": [{}], "display_text": "single:3",
        })
        table_observation["current_round"]["constraint"] = "single:3"
        self.assertIsNone(summarize_candidate_structures(table_observation, [_action(10, "single", ["4S"])]))

        duplicate_wildcard = _action(11, "pair", ["2H", "2H"], wildcard_count=2)
        duplicate_wildcard["declared_cards"] = ["3", "4"]
        duplicate_wildcard["wildcard_info"] = [
            {"carrier_card": "2H", "declared_as": "3"},
            {"carrier_card": "2H", "declared_as": "3"},
        ]
        self.assertIsNone(summarize_candidate_structures(_observation(["2H", "2H", "3S", "4S"]), [duplicate_wildcard]))

        non_wildcard = _action(12, "single", ["3S"])
        non_wildcard["declared_cards"] = ["4"]
        self.assertIsNone(summarize_candidate_structures(_observation(["3S"]), [non_wildcard]))

        natural_level_card = _action(13, "single", ["2H"])
        natural_level_card["declared_cards"] = ["4"]
        self.assertIsNone(summarize_candidate_structures(_observation(["2H"]), [natural_level_card]))

    def test_real_engine_canonical_actions_pass_schema_conservation(self) -> None:
        for seed in (3, 7, 11):
            game = GuanDanGame(seed=seed, current_level_rank="2")
            game.reset()
            for _ in range(12):
                observation = game.observe()
                actions = game.legal_actions()
                self.assertIsNotNone(summarize_candidate_structures(observation, actions))
                game.step(int(actions[0]["action_id"]))

        straight_flush_game = GuanDanGame(
            current_level_rank="2",
            preset_hands={
                1: tuple(Card(rank=rank, suit="S") for rank in ("3", "4", "5", "6")) + (Card(rank="2", suit="H"),),
                2: (Card(rank="8", suit="S"),),
                3: (Card(rank="9", suit="S"),),
                4: (Card(rank="10", suit="S"),),
            },
        )
        observation = straight_flush_game.reset()
        actions = straight_flush_game.legal_actions()
        self.assertTrue(any(action["declared_pattern"] == "straight_flush" for action in actions))
        self.assertTrue(any(action["wildcard_count"] for action in actions))
        self.assertIsNotNone(summarize_candidate_structures(observation, actions))

    def test_bomb_only_lead_has_no_low_cost_probe_and_representatives_survive_overflow(self) -> None:
        observation = _observation(["7S", "7H", "7C", "7D", "7S", "9S"])
        recommendation = build_strategy_recommendation(observation, [
            _action(4, "bomb", ["7S", "7H", "7C", "7D"]),
            _action(5, "bomb", ["7S", "7H", "7C", "7D", "7S"]),
        ])
        self.assertEqual(recommendation.status, "ready")
        self.assertIn("bomb_wildcard_management", recommendation.strategy_domains)
        self.assertNotIn("low_cost_probe", recommendation.objective_codes)

        def fact(action_id: int, **kwargs: object) -> CandidateStructure:
            base = dict(pattern="triple", carrier_count=3, uses_wildcard=False, finishes_hand=False,
                        clears_played_rank_groups=True, residual_singleton_rank_count=1,
                        estimated_remaining_rank_groups=4, fragments_played_rank_group=False,
                        natural_single_rank_value=None, consumes_control_resource=False,
                        bomb_length=None, leaves_bomb_rank_singleton=None, teammate_hand_count=5,
                        teammate_active=True, minimum_opponent_hand_count=5, is_free_lead=True)
            base.update(kwargs)
            return CandidateStructure(action_id=action_id, **base)
        facts = tuple(fact(index) for index in range(1, 15)) + (
            fact(99), fact(100, finishes_hand=True), fact(20, pattern="single", natural_single_rank_value=3),
            fact(21, pattern="pair"), fact(22, consumes_control_resource=True), fact(23, uses_wildcard=True),
            fact(24, fragments_played_rank_group=True), fact(25, pattern="bomb", bomb_length=4),
            fact(26, pattern="bomb", bomb_length=5),
        )
        selected = select_candidate_structure_representatives(facts, recommended_ids=(99,))
        self.assertTrue({99, 100, 20, 21, 22, 23, 24, 25, 26}.issubset({item.action_id for item in selected}))

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
