import unittest

from agents.action_structure import summarize_candidate_structures
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekSuggestion
from agents.strategy_recommendation import build_strategy_recommendation


def _action(action_id: int, pattern: str, cards: list[str]) -> dict[str, object]:
    return {
        "action_id": action_id, "declared_pattern": pattern,
        "declared_cards": list(cards), "carrier_cards": list(cards),
        "wildcard_count": 0, "wildcard_info": [], "display_text": f"{pattern}:{cards}",
    }


def _observation() -> dict[str, object]:
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_count": 4, "hand_cards": ["3S", "4S", "7S", "7H"]},
        "current_round": {"current_player_id": 1, "current_level_rank": "2", "constraint": "free", "table_action": None},
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 7, "finished": False},
            {"player_id": 3, "team": "team_13", "hand_count": 2, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": 6, "finished": False},
        ],
    }


class StrategyRecommendationTests(unittest.TestCase):
    def test_candidate_structure_and_recommendation_are_public_and_non_prescriptive(self) -> None:
        observation = _observation()
        actions = [_action(1, "single", ["3S"]), _action(2, "single", ["4S"]), _action(3, "pair", ["7S", "7H"])]
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        self.assertEqual((facts[0].natural_single_rank_value, facts[2].carrier_count, facts[2].residual_singleton_rank_count), (3, 2, 2))
        recommendation = build_strategy_recommendation(observation, actions)
        self.assertEqual(recommendation.status, "ready")
        self.assertIn(1, recommendation.action_ids)
        self.assertTrue(set(recommendation.action_ids).issubset({1, 2, 3}))
        self.assertIn("check_public_urgency", recommendation.countercheck_codes)
        self.assertIn("opening_free_lead", recommendation.strategy_domains)

    def test_malformed_action_fails_closed(self) -> None:
        observation = _observation()
        self.assertIsNone(summarize_candidate_structures(observation, [{"action_id": 1}]))
        self.assertEqual(build_strategy_recommendation(observation, [{"action_id": 1}]).status, "unavailable")

    def test_agent_passes_recommendation_before_model_and_keeps_model_id(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.kwargs: dict[str, object] = {}

            def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
                self.kwargs = kwargs
                return DeepSeekSuggestion(action_id=2, reasoning=None)

        observation = _observation()
        actions = [_action(1, "single", ["3S"]), _action(2, "single", ["4S"]), _action(3, "pair", ["7S", "7H"])]
        client = Client()
        agent = DeepSeekAIAgent(1, client, rag_advisor=None, hand_evaluation_enabled=False, opening_formula_enabled=False)
        self.assertEqual(agent.select_action(observation, actions), 2)
        self.assertEqual(agent.last_decision_source, "model")
        recommendation = client.kwargs.get("strategy_recommendation")
        self.assertIsNotNone(recommendation)
        self.assertTrue(set(recommendation.action_ids).issubset({1, 2, 3}))


if __name__ == "__main__":
    unittest.main()
