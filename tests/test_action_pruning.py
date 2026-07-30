import json
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient


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
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "pair", ["7", "7"], ["7S", "7H"]),
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

        with mock.patch.object(DeepSeekClient, "_prune_legal_actions", return_value=[legal_actions[0]]) as prune_mock:
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 2)
        self.assertEqual(agent.last_decision_source, "local_opening_formula")
        prune_mock.assert_not_called()
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_deepseek_prompt_uses_pruned_candidates_but_validation_uses_raw_actions(self) -> None:
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
        self.assertEqual(suggestion.action_id, 3)


if __name__ == "__main__":
    unittest.main()
