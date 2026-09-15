from copy import deepcopy
import unittest

from agents.action_structure import summarize_free_lead_residual_structures
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion


def _action(action_id: object, pattern: str, carriers: list[str]) -> dict[str, object]:
    ranks = [card if card in {"SJ", "BJ"} else card[:-1] for card in carriers]
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": ranks,
        "carrier_cards": carriers,
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": f"{pattern}:{','.join(ranks)}",
    }


def _fixture() -> tuple[dict[str, object], list[dict[str, object]]]:
    hand = ["7S", "7H", "7C", "7D", "7S", "9C"]
    observation = {
        "my_info": {
            "player_id": 1,
            "team": "team_13",
            "hand_cards": hand,
            "hand_count": len(hand),
            "remaining_single_card_count": 1,
        },
        "current_round": {
            "step_no": 8,
            "round_no": 3,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 10, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": 10, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": 10, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }
    actions = [
        _action(40, "bomb", ["7S", "7H", "7C", "7D"]),
        _action(50, "bomb", ["7S", "7H", "7C", "7D", "7S"]),
        _action(90, "single", ["9C"]),
    ]
    return observation, actions


class RecordingClient:
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self.calls: list[dict[str, object]] = []

    def suggest_action_id(self, **kwargs):
        self.calls.append(kwargs)
        return DeepSeekSuggestion(action_id=self.action_id, reasoning="test")


class EmptyRAG:
    def get_rag_context(self, **_kwargs):
        return {"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""}


class TestActionStructure(unittest.TestCase):
    def test_four_and_five_bombs_have_distinct_public_residual_facts(self) -> None:
        observation, actions = _fixture()
        before = (deepcopy(observation), deepcopy(actions))

        summaries = summarize_free_lead_residual_structures(observation, actions)

        self.assertIsNotNone(summaries)
        assert summaries is not None
        by_id = {item.action_id: item for item in summaries}
        self.assertFalse(by_id[40].clears_played_rank_groups)
        self.assertEqual(by_id[40].residual_singleton_rank_count, 2)
        self.assertEqual(by_id[40].estimated_remaining_rank_groups, 2)
        self.assertTrue(by_id[50].clears_played_rank_groups)
        self.assertEqual(by_id[50].residual_singleton_rank_count, 1)
        self.assertEqual(by_id[50].estimated_remaining_rank_groups, 1)
        self.assertEqual((observation, actions), before)

    def test_two_wildcard_canonical_action_is_supported(self) -> None:
        observation, actions = _fixture()
        observation["my_info"]["hand_cards"].extend(["2H", "2H"])
        observation["my_info"]["hand_count"] += 2
        actions.append(
            {
                "action_id": 60,
                "declared_pattern": "pair",
                "declared_cards": ["8", "8"],
                "carrier_cards": ["2H", "2H"],
                "wildcard_count": 2,
                "wildcard_info": [
                    {"carrier_card": "2H", "declared_as": "8S"},
                    {"carrier_card": "2H", "declared_as": "8H"},
                ],
                "display_text": "pair:8,8",
            }
        )

        summaries = summarize_free_lead_residual_structures(observation, actions)

        self.assertIsNotNone(summaries)
        assert summaries is not None
        self.assertIn(60, {item.action_id for item in summaries})

    def test_final_prompt_keeps_both_ids_and_exposes_non_prescriptive_difference(self) -> None:
        observation, actions = _fixture()
        pruned = DeepSeekClient._prune_legal_actions(actions, "free", step_no=8, hand_count=6)
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=pruned,
        )

        self.assertIn("action_id=40", prompt)
        self.assertIn("action_id=50", prompt)
        self.assertIn("不是动作指令，也不保证后续牌权", prompt)
        line_40 = next(line for line in prompt.splitlines() if "action_id=40" in line)
        line_50 = next(line for line in prompt.splitlines() if "action_id=50" in line)
        self.assertIn("清空所出点数组:否", line_40)
        self.assertIn("残余孤张点数:2", line_40)
        self.assertIn("估计剩余点数组:2", line_40)
        self.assertIn("清空所出点数组:是", line_50)
        self.assertIn("残余孤张点数:1", line_50)
        self.assertIn("估计剩余点数组:1", line_50)
        self.assertNotIn("应选择", line_40 + line_50)

    def test_model_may_return_either_bomb_without_post_model_override(self) -> None:
        observation, actions = _fixture()
        for action_id in (40, 50):
            with self.subTest(action_id=action_id):
                client = RecordingClient(action_id)
                agent = DeepSeekAIAgent(
                    player_id=1,
                    client=client,
                    rag_advisor=EmptyRAG(),
                    hand_evaluation_enabled=False,
                    opening_formula_enabled=False,
                )
                self.assertEqual(agent.select_action(observation, actions), action_id)
                self.assertEqual(agent.last_decision_source, "model")
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(
                    [action["action_id"] for action in client.calls[0]["prompt_actions"]],
                    [50, 40, 90],
                )

    def test_malformed_or_non_free_payloads_fail_closed_without_prompt_summary(self) -> None:
        observation, actions = _fixture()
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        bad_hand = deepcopy(observation)
        bad_hand["my_info"]["hand_cards"][0] = "ZZ"
        cases.append((bad_hand, deepcopy(actions)))
        bad_carrier = deepcopy(actions)
        bad_carrier[0]["carrier_cards"] = ["AS"]
        cases.append((deepcopy(observation), bad_carrier))
        duplicate = deepcopy(actions)
        duplicate[1]["action_id"] = 40
        cases.append((deepcopy(observation), duplicate))
        follow = deepcopy(observation)
        follow["current_round"]["constraint"] = "single:6"
        follow["current_round"]["table_action"] = _action(99, "single", ["6S"])
        cases.append((follow, deepcopy(actions)))

        for bad_observation, bad_actions in cases:
            with self.subTest(case=(bad_observation, bad_actions)):
                self.assertIsNone(summarize_free_lead_residual_structures(bad_observation, bad_actions))
                prompt = DeepSeekClient._build_structured_prompt(
                    my_info=bad_observation["my_info"],
                    current_round=bad_observation["current_round"],
                    other_players=bad_observation["other_players"],
                    history=bad_observation["history"],
                    legal_actions=bad_actions,
                )
                self.assertNotIn("残余结构=", prompt)


if __name__ == "__main__":
    unittest.main()
