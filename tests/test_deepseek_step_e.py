import json
import unittest

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.rule_based_ai import RuleBasedAIAgent


def _observation() -> dict[str, object]:
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": ["3S", "4S"],
            "hand_count": 2,
            "remaining_single_card_count": 2,
        },
        "current_round": {
            "step_no": 1,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 5, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 5, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 5, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _legal_actions() -> list[dict[str, object]]:
    return [
        {
            "action_id": 1,
            "declared_pattern": "single",
            "declared_cards": ["3"],
            "carrier_cards": ["3S"],
            "wildcard_count": 0,
            "wildcard_info": [],
        },
        {
            "action_id": 2,
            "declared_pattern": "pair",
            "declared_cards": ["4", "4"],
            "carrier_cards": ["4S", "4H"],
            "wildcard_count": 0,
            "wildcard_info": [],
        },
    ]


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def suggest_action_id(self, **_kwargs):
        self.calls += 1
        raise AssertionError("DeepSeek client should not be called")


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


def _agent_with_counting_dependencies() -> tuple[DeepSeekAIAgent, CountingClient, CountingRAGAdvisor]:
    client = CountingClient()
    rag = CountingRAGAdvisor()
    agent = DeepSeekAIAgent(
        player_id=1,
        client=client,
        rag_advisor=rag,
        verbose=False,
        hand_evaluation_enabled=False,
    )
    return agent, client, rag


class TestDeepSeekStepE(unittest.TestCase):
    def test_client_uses_injected_transport_and_parses_action_id(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else {}
            return (
                "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"先看最小合法动作。\","
                "\"content\":\"{\\\"action_id\\\": 2}\"}}]}\n"
                "data: [DONE]\n"
            )

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            timeout_seconds=3.5,
            transport=transport,
        )

        suggestion = client.suggest_action_id(
            observation=_observation(),
            legal_actions=_legal_actions(),
        )

        self.assertEqual(suggestion.action_id, 2)
        self.assertEqual(suggestion.reasoning, "先看最小合法动作。")
        self.assertEqual(captured.get("url"), "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured.get("auth"), "Bearer test-key")
        self.assertEqual(captured.get("timeout"), 3.5)
        body = captured.get("body")
        self.assertIsInstance(body, dict)
        assert isinstance(body, dict)
        self.assertEqual(body.get("model"), "deepseek-chat")
        self.assertEqual(body.get("stream"), True)

    def test_agent_falls_back_when_client_raises(self) -> None:
        class RaisingClient:
            def suggest_action_id(self, **_kwargs):
                raise RuntimeError("simulated api failure")

        agent = DeepSeekAIAgent(player_id=1, client=RaisingClient(), rag_advisor=None, verbose=False)
        chosen = agent.select_action(_observation(), _legal_actions())

        expected = RuleBasedAIAgent(player_id=1).select_action(_observation(), _legal_actions())
        self.assertEqual(chosen, expected)

    def test_agent_falls_back_when_client_returns_invalid_action_id(self) -> None:
        class InvalidClient:
            def suggest_action_id(self, **_kwargs):
                return DeepSeekSuggestion(action_id=999, reasoning="invalid choice")

        agent = DeepSeekAIAgent(player_id=1, client=InvalidClient(), rag_advisor=None, verbose=False)
        chosen = agent.select_action(_observation(), _legal_actions())

        expected = RuleBasedAIAgent(player_id=1).select_action(_observation(), _legal_actions())
        self.assertEqual(chosen, expected)

    def test_agent_forces_pair_finish_from_raw_legal_actions_without_rag_or_client(self) -> None:
        observation = _observation()
        legal_actions = [
            {
                "action_id": 1,
                "declared_pattern": "single",
                "declared_cards": ["4"],
                "carrier_cards": ["4S"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "single:4",
            },
            {
                "action_id": 2,
                "declared_pattern": "single",
                "declared_cards": ["4"],
                "carrier_cards": ["4H"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "single:4",
            },
            {
                "action_id": 3,
                "declared_pattern": "pair",
                "declared_cards": ["4", "4"],
                "carrier_cards": ["4S", "4H"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "pair:4,4",
            },
        ]
        agent, client, rag = _agent_with_counting_dependencies()

        chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 3)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_agent_forces_triple_finish_from_raw_legal_actions_without_rag_or_client(self) -> None:
        observation = _observation()
        observation["my_info"]["hand_cards"] = ["5S", "5H", "5C"]
        observation["my_info"]["hand_count"] = 3
        legal_actions = [
            {
                "action_id": 1,
                "declared_pattern": "single",
                "declared_cards": ["5"],
                "carrier_cards": ["5S"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "single:5",
            },
            {
                "action_id": 2,
                "declared_pattern": "pair",
                "declared_cards": ["5", "5"],
                "carrier_cards": ["5S", "5H"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "pair:5,5",
            },
            {
                "action_id": 3,
                "declared_pattern": "triple",
                "declared_cards": ["5", "5", "5"],
                "carrier_cards": ["5S", "5H", "5C"],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "triple:5,5,5",
            },
        ]
        agent, client, rag = _agent_with_counting_dependencies()

        chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 3)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_agent_keeps_pass_shortcut_without_rag_or_client(self) -> None:
        observation = _observation()
        observation["current_round"]["constraint"] = "single:8"
        observation["current_round"]["table_action"] = {
            "declared_pattern": "single",
            "declared_cards": ["8"],
            "carrier_cards": ["8S"],
            "wildcard_count": 0,
            "wildcard_info": [],
            "display_text": "single:8",
        }
        legal_actions = [
            {
                "action_id": 7,
                "declared_pattern": "pass",
                "declared_cards": [],
                "carrier_cards": [],
                "wildcard_count": 0,
                "wildcard_info": [],
                "display_text": "pass",
            }
        ]
        agent, client, rag = _agent_with_counting_dependencies()

        chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 7)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)


if __name__ == "__main__":
    unittest.main()
