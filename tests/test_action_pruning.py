import json
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, PROMPT_MAX_CANDIDATE_ACTIONS
from agents.strategy_recommendation import StrategyRecommendation


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


def _observation(*, hand_count: int = 20, constraint: str = "free") -> dict[str, object]:
    table_action = None
    if constraint != "free":
        table_action = _action(99, "single", ["8"], ["8S"])
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": ["3S"] * hand_count,
            "hand_count": hand_count,
            "remaining_single_card_count": 4,
        },
        "current_round": {
            "step_no": 0,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": constraint,
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


class RaisingClient:
    def __init__(self) -> None:
        self.calls = 0

    def suggest_action_id(self, **_kwargs):
        self.calls += 1
        raise AssertionError("client should not be called")


class CountingRAGAdvisor:
    def __init__(self) -> None:
        self.rule_calls = 0
        self.experience_calls = 0

    def retrieve_rule_evidence(self, query: str, top_k: int = 3):
        self.rule_calls += 1
        return ()

    def retrieve_experience_evidence(self, query: str, top_k: int = 3):
        self.experience_calls += 1
        return ()


class TestActionPruning(unittest.TestCase):
    def test_follow_context_always_keeps_pass(self) -> None:
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "pass", [], []),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "single:8", step_no=3, hand_count=10)

        self.assertIn(2, {action["action_id"] for action in pruned})

    def test_follow_context_always_keeps_pressure_actions(self) -> None:
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "bomb", ["7", "7", "7", "7"], ["7S", "7H", "7C", "7D"]),
            _action(3, "straight_flush", ["9", "10", "J", "Q", "K"], ["9S", "10S", "JS", "QS", "KS"]),
            _action(4, "joker_bomb", ["SJ", "SJ", "BJ", "BJ"], ["SJ", "SJ", "BJ", "BJ"]),
            _action(5, "pass", [], []),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "single:8", step_no=3, hand_count=10)

        self.assertTrue({2, 3, 4}.issubset({action["action_id"] for action in pruned}))

    def test_finishing_action_is_always_kept(self) -> None:
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "straight", ["3", "4", "5", "6", "7"], ["3S", "4S", "5S", "6S", "7S"]),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "single:8", step_no=12, hand_count=5)

        self.assertIn(2, {action["action_id"] for action in pruned})

    def test_same_brief_with_different_carrier_cards_is_not_merged(self) -> None:
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "single", ["9"], ["9H"]),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "free", step_no=0, hand_count=20)

        self.assertEqual({1, 2}, {action["action_id"] for action in pruned})

    def test_same_brief_with_different_wildcard_count_is_not_merged(self) -> None:
        legal_actions = [
            _action(
                1,
                "pair",
                ["9", "9"],
                ["9S", "2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
            ),
            _action(2, "pair", ["9", "9"], ["9S", "9H"], wildcard_count=0),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "free", step_no=0, hand_count=20)

        self.assertEqual({1, 2}, {action["action_id"] for action in pruned})

    def test_natural_action_is_summarized_before_wildcard_action(self) -> None:
        legal_actions = [
            _action(
                1,
                "pair",
                ["9", "9"],
                ["9S", "2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
            ),
            _action(2, "pair", ["9", "9"], ["9S", "9H"], wildcard_count=0),
        ]

        lines = DeepSeekClient._grouped_legal_actions_summary(legal_actions, "free", 0, 20, "2")
        joined = "\n".join(lines)

        self.assertLess(joined.index("#2 "), joined.index("#1 "))

    def test_follow_context_keeps_wildcard_actions_even_after_regular_limit(self) -> None:
        legal_actions = [
            _action(index, "single", [str(index + 2)], [f"{index + 2}S"])
            for index in range(1, 16)
        ]
        legal_actions.append(
            _action(
                20,
                "single",
                ["A"],
                ["2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "A"}],
            )
        )
        legal_actions.append(_action(30, "pass", [], []))

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "single:8", step_no=3, hand_count=20)

        self.assertIn(20, {action["action_id"] for action in pruned})

    def test_lead_and_follow_contexts_use_different_pruning(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["9"], ["9S"]),
            _action(3, "pass", [], []),
        ]

        lead = DeepSeekClient._prune_legal_actions(legal_actions, "free", step_no=0, hand_count=20)
        follow = DeepSeekClient._prune_legal_actions(legal_actions, "single:8", step_no=2, hand_count=20)

        self.assertNotIn(3, {action["action_id"] for action in lead})
        self.assertIn(3, {action["action_id"] for action in follow})

    def test_free_lead_singles_still_keep_smallest_natural_pair(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["K"], ["KS"]),
            _action(3, "pair", ["9", "9"], ["9S", "9H"]),
            _action(4, "pair", ["4", "4"], ["4S", "4H"]),
            _action(
                5,
                "pair",
                ["3", "3"],
                ["3H", "2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "3H"}],
            ),
        ]

        pruned = DeepSeekClient._prune_legal_actions(
            legal_actions,
            "free",
            step_no=8,
            hand_count=20,
        )
        ids = [action["action_id"] for action in pruned]

        self.assertEqual(ids[:3], [1, 2, 4])
        self.assertIn(5, ids)
        self.assertNotIn(3, ids)
        self.assertTrue(set(ids).issubset({1, 2, 3, 4, 5}))
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=pruned,
        )
        self.assertIn("action_id=1", prompt)
        self.assertIn("action_id=2", prompt)
        self.assertIn("action_id=4", prompt)

    def test_final_free_lead_limit_preserves_natural_transition_representatives(self) -> None:
        runs = [
            _action(index, "straight", [f"run-{index}"], [f"run-{index}S"])
            for index in range(1, PROMPT_MAX_CANDIDATE_ACTIONS + 21)
        ]
        legal_actions = runs + [
            _action(1001, "single", ["3"], ["3S"]),
            _action(1002, "single", ["K"], ["KS"]),
            _action(1003, "pair", ["9", "9"], ["9S", "9H"]),
            _action(1004, "pair", ["4", "4"], ["4S", "4H"]),
            _action(1005, "pair", ["4", "4"], ["4S", "4H"]),
        ]

        first_pass = DeepSeekClient._prune_legal_actions(
            legal_actions,
            "free",
            step_no=8,
            hand_count=20,
        )
        final_one = DeepSeekClient._limit_prompt_actions(
            first_pass,
            constraint="free",
            hand_count=20,
        )
        final_two = DeepSeekClient._limit_prompt_actions(
            first_pass,
            constraint="free",
            hand_count=20,
        )
        final_ids = [action["action_id"] for action in final_one]

        self.assertGreater(len(first_pass), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertLessEqual(len(final_one), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertIn(1001, final_ids)
        self.assertIn(1004, final_ids)
        self.assertEqual(final_ids, [action["action_id"] for action in final_two])
        self.assertTrue(set(final_ids).issubset({action["action_id"] for action in legal_actions}))
        signatures = [DeepSeekClient._action_signature(action) for action in final_one]
        self.assertEqual(len(signatures), len(set(signatures)))
        observation = _observation()
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=first_pass,
        )
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        self.assertEqual(candidate_section.count("action_id="), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertIn("action_id=1001", candidate_section)
        self.assertIn("action_id=1004", candidate_section)

    def test_final_limit_bounds_wildcard_overflow_without_evicting_free_lead_pair(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "pair", ["4", "4"], ["4S", "4H"]),
        ]
        legal_actions.extend(
            _action(
                100 + index,
                "single",
                [f"wild-{index}"],
                [f"2H-{index}"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": f"2H-{index}", "declared_as": f"wild-{index}"}],
            )
            for index in range(PROMPT_MAX_CANDIDATE_ACTIONS + 10)
        )

        final_actions = DeepSeekClient._limit_prompt_actions(
            legal_actions,
            constraint="free",
            hand_count=20,
        )
        final_ids = {action["action_id"] for action in final_actions}

        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue({1, 2}.issubset(final_ids))
        self.assertEqual(
            sum(int(action["wildcard_count"]) for action in final_actions),
            PROMPT_MAX_CANDIDATE_ACTIONS - 2,
        )

    def test_final_limit_prioritizes_finishing_then_pressure_before_wildcard_overflow(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "pair", ["4", "4"], ["4S", "4H"]),
        ]
        legal_actions.extend(
            _action(10 + index, "straight", [f"finish-{index}"] * 5, [f"finish-{index}S"] * 5)
            for index in range(8)
        )
        legal_actions.extend(
            _action(100 + index, "bomb", [f"pressure-{index}"] * 4, [f"pressure-{index}S"] * 4)
            for index in range(20)
        )
        legal_actions.extend(
            _action(
                200 + index,
                "single",
                [f"wild-{index}"],
                [f"2H-{index}"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": f"2H-{index}", "declared_as": f"wild-{index}"}],
            )
            for index in range(PROMPT_MAX_CANDIDATE_ACTIONS)
        )

        final_actions = DeepSeekClient._limit_prompt_actions(
            legal_actions,
            constraint="free",
            hand_count=5,
        )
        final_ids = {action["action_id"] for action in final_actions}

        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue({1, 2}.issubset(final_ids))
        self.assertTrue(set(range(10, 18)).issubset(final_ids))
        self.assertTrue(set(range(100, 120)).issubset(final_ids))
        self.assertEqual(len(final_ids & set(range(200, 280))), 50)

    def test_valid_recommendation_reserves_exact_original_ids_within_existing_budget(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "pair", ["4", "4"], ["4S", "4H"]),
        ]
        legal_actions.extend(
            _action(10 + index, "straight", [f"finish-{index}"] * 5, [f"finish-{index}S"] * 5)
            for index in range(8)
        )
        legal_actions.extend(
            _action(100 + index, "bomb", [f"pressure-{index}"] * 4, [f"pressure-{index}S"] * 4)
            for index in range(30)
        )
        legal_actions.extend(
            _action(
                200 + index, "single", [f"wild-{index}"], [f"2H-{index}"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": f"2H-{index}", "declared_as": f"wild-{index}"}],
            )
            for index in range(PROMPT_MAX_CANDIDATE_ACTIONS)
        )
        legal_actions.append(_action(999, "triple", ["9", "9", "9"], ["9S", "9H", "9C"]))
        recommendation = StrategyRecommendation(
            "ready", "public_strategy_recommendation_v2", (999,),
            ("protect_structure",), ("check_public_urgency",), ("overall_priority",),
        )

        final_actions = DeepSeekClient.prepare_prompt_actions(
            legal_actions,
            constraint="free",
            step_no=0,
            hand_count=5,
            strategy_recommendation=recommendation,
        )
        final_ids = {int(action["action_id"]) for action in final_actions}

        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue({1, 2, 999}.issubset(final_ids))
        self.assertTrue(set(range(10, 18)).issubset(final_ids))
        self.assertTrue(set(range(100, 130)).issubset(final_ids))
        self.assertTrue(final_ids & set(range(200, 280)))
        self.assertEqual(
            [action["action_id"] for action in final_actions],
            [action["action_id"] for action in DeepSeekClient.prepare_prompt_actions(
                legal_actions, constraint="free", step_no=0, hand_count=5,
                strategy_recommendation=recommendation,
            )],
        )

    def test_pruned_action_ids_all_come_from_original_legal_actions(self) -> None:
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "pair", ["9", "9"], ["9S", "9H"]),
            _action(3, "bomb", ["7", "7", "7", "7"], ["7S", "7H", "7C", "7D"]),
        ]

        pruned = DeepSeekClient._prune_legal_actions(legal_actions, "free", step_no=0, hand_count=20)

        self.assertTrue({action["action_id"] for action in pruned}.issubset({1, 2, 3}))

    def test_opening_formula_uses_raw_legal_actions_even_if_prune_hides_action(self) -> None:
        observation = _observation(hand_count=20)
        observation["my_info"]["hand_cards"] = ["3S", "9S", "SJ", "BJ"] + [
            card
            for rank in ("4", "5", "6", "7", "8", "10", "J", "Q")
            for card in (f"{rank}S", f"{rank}H")
        ]
        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["9"], ["9S"]),
            _action(3, "single", ["SJ"], ["SJ"]),
        ]
        client = RaisingClient()
        rag = CountingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )

        with mock.patch.object(
            DeepSeekClient,
            "_prune_legal_actions",
            return_value=[legal_actions[1]],
        ) as prune_mock, mock.patch(
            "agents.deepseek_ai.evaluate_hand",
            return_value={"label": "strong", "control_score": 24},
        ):
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 1)
        self.assertEqual(agent.last_decision_source, "local_opening_formula")
        prune_mock.assert_not_called()
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_deepseek_response_must_use_the_prompt_candidate_subset(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else {}
            return (
                "data: {\"choices\":[{\"delta\":{\"content\":\"{\\\"action_id\\\": 3}\"}}]}\n"
                "data: [DONE]\n"
            )

        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["4"], ["4S"]),
            _action(3, "single", ["5"], ["5S"]),
            _action(4, "single", ["6"], ["6S"]),
            _action(5, "single", ["7"], ["7S"]),
        ]
        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )

        suggestion = client.suggest_action_id(
            observation=_observation(hand_count=20),
            legal_actions=legal_actions,
        )

        body = captured["body"]
        assert isinstance(body, dict)
        messages = body["messages"]
        prompt = messages[1]["content"]
        self.assertNotIn("#3 ", prompt)
        self.assertIsNone(suggestion.action_id)


if __name__ == "__main__":
    unittest.main()
