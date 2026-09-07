import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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


def _danger_observation(*, opponent_count: int) -> dict[str, object]:
    table = {
        "action_id": 99,
        "declared_pattern": "single",
        "declared_cards": ["8"],
        "carrier_cards": ["8S"],
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": "single:8",
    }
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_cards": ["9S", "JH"], "hand_count": 2},
        "current_round": {
            "step_no": 7, "round_no": 2, "current_player_id": 1,
            "current_level_rank": "2", "constraint": "single:8", "table_action": table,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": opponent_count, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": 8, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": 8, "finished": False, "finish_rank": None},
        ],
        "history": {
            "actions": [{
                "step_no": 7, "round_no": 2, "player_id": 2,
                "declared_pattern": "single", "declared_cards": ["8"], "carrier_cards": ["8S"],
            }],
            "finish_order": [],
        },
    }


def _danger_legal_actions() -> list[dict[str, object]]:
    return [
        {"action_id": 1, "declared_pattern": "pass", "declared_cards": [], "carrier_cards": [], "wildcard_count": 0, "wildcard_info": [], "display_text": "pass"},
        {"action_id": 2, "declared_pattern": "single", "declared_cards": ["9"], "carrier_cards": ["9S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:9"},
        {"action_id": 3, "declared_pattern": "single", "declared_cards": ["J"], "carrier_cards": ["JH"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:J"},
    ]


def _short_endgame_observation() -> dict[str, object]:
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_cards": ["6S", "7S", "JH", "JD"], "hand_count": 4},
        "current_round": {
            "step_no": 20, "round_no": 8, "current_player_id": 1,
            "current_level_rank": "2", "constraint": "free", "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 5, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": 6, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": 4, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _short_endgame_legal_actions() -> list[dict[str, object]]:
    return [
        {"action_id": 1, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
        {"action_id": 2, "declared_pattern": "single", "declared_cards": ["7"], "carrier_cards": ["7S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:7"},
        {"action_id": 3, "declared_pattern": "single", "declared_cards": ["J"], "carrier_cards": ["JH"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:J"},
        {"action_id": 4, "declared_pattern": "single", "declared_cards": ["J"], "carrier_cards": ["JD"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:J"},
        {"action_id": 5, "declared_pattern": "pair", "declared_cards": ["J", "J"], "carrier_cards": ["JH", "JD"], "wildcard_count": 0, "wildcard_info": [], "display_text": "pair:J,J"},
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
    def test_successful_model_single_jack_is_replaced_by_shorter_free_lead_plan(self) -> None:
        class SingleJackClient:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                self.calls += 1
                return DeepSeekSuggestion(action_id=3, reasoning="ignored")

        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            client = SingleJackClient()
            actions = _short_endgame_legal_actions()
            agent = DeepSeekAIAgent(1, client, rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
            chosen = agent.select_action(_short_endgame_observation(), actions)
        self.assertEqual(chosen, 5)
        self.assertIn(chosen, {action["action_id"] for action in actions})
        self.assertEqual(agent.last_decision_source, "short_endgame_plan")
        self.assertEqual(client.calls, 1)

    def test_successful_model_best_or_tied_free_lead_is_not_overridden(self) -> None:
        class FixedClient:
            def __init__(self, action_id: int) -> None:
                self.action_id = action_id

            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                return DeepSeekSuggestion(action_id=self.action_id, reasoning="ignored")

        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(1, FixedClient(5), rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
            self.assertEqual(agent.select_action(_short_endgame_observation(), _short_endgame_legal_actions()), 5)
        self.assertEqual(agent.last_decision_source, "model")

    def test_short_endgame_plan_uses_frozen_tie_break_only_after_strict_improvement(self) -> None:
        class FixedClient:
            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                return DeepSeekSuggestion(action_id=1, reasoning="ignored")

        observation = _short_endgame_observation()
        observation["my_info"] = dict(observation["my_info"], hand_cards=["6S", "6H", "7S"], hand_count=3)
        actions = [
            {"action_id": 1, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
            {"action_id": 2, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6H"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
            {"action_id": 3, "declared_pattern": "pair", "declared_cards": ["6", "6"], "carrier_cards": ["6S", "6H"], "wildcard_count": 0, "wildcard_info": [], "display_text": "pair:6,6"},
            {"action_id": 4, "declared_pattern": "single", "declared_cards": ["7"], "carrier_cards": ["7S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:7"},
        ]
        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(1, FixedClient(), rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
            chosen = agent.select_action(observation, actions)
        self.assertEqual(chosen, 3)
        self.assertIn(chosen, {action["action_id"] for action in actions})
        self.assertEqual(agent.last_decision_source, "short_endgame_plan")

    def test_short_endgame_plan_preserves_model_selection_outside_verified_scope(self) -> None:
        class FixedClient:
            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                return DeepSeekSuggestion(action_id=3, reasoning="ignored")

        base = _short_endgame_observation()
        actions = _short_endgame_legal_actions()
        oversized = _short_endgame_observation()
        oversized["my_info"] = dict(oversized["my_info"], hand_cards=["3S", "4S", "5S", "6S", "7S"], hand_count=5)
        follow = _short_endgame_observation()
        follow["current_round"] = dict(follow["current_round"], constraint="single:5", table_action={"action_id": 99, "declared_pattern": "single", "declared_cards": ["5"], "carrier_cards": ["5S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:5"})
        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        for observation, candidates in ((oversized, actions), (follow, actions), (base, [actions[2]])):
            with self.subTest(constraint=observation["current_round"]["constraint"], action_count=len(candidates)), patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
                agent = DeepSeekAIAgent(1, FixedClient(), rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
                self.assertEqual(agent.select_action(observation, candidates), 3)
                self.assertEqual(agent.last_decision_source, "model")

    def test_successful_model_pass_is_blocked_for_proved_one_or_two_card_opponent(self) -> None:
        class PassClient:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                self.calls += 1
                return DeepSeekSuggestion(action_id=1, reasoning="ignored")

        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        for opponent_count in (1, 2):
            with self.subTest(opponent_count=opponent_count), patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
                client = PassClient()
                agent = DeepSeekAIAgent(1, client, rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
                actions = _danger_legal_actions()
                chosen = agent.select_action(_danger_observation(opponent_count=opponent_count), actions)
                self.assertEqual(chosen, 2)
                self.assertIn(chosen, {action["action_id"] for action in actions})
                self.assertEqual(agent.last_decision_source, "danger_opponent_block")
                self.assertEqual(client.calls, 1)

    def test_successful_model_pass_remains_unchanged_when_opponent_has_three_cards(self) -> None:
        class PassClient:
            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                return DeepSeekSuggestion(action_id=1, reasoning="ignored")

        config = SimpleNamespace(hand_evaluation_enabled=False, opening_formula_enabled=False, card_tracking_enabled=False)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(1, PassClient(), rag_advisor=None, verbose=False, hand_evaluation_enabled=False, opening_formula_enabled=False)
            self.assertEqual(agent.select_action(_danger_observation(opponent_count=3), _danger_legal_actions()), 1)
        self.assertEqual(agent.last_decision_source, "model")

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

    def test_agent_falls_back_when_client_returns_no_action_id(self) -> None:
        class MissingActionClient:
            def suggest_action_id(self, **_kwargs):
                return DeepSeekSuggestion(action_id=None, reasoning=None)

        agent = DeepSeekAIAgent(player_id=1, client=MissingActionClient(), rag_advisor=None, verbose=False)
        chosen = agent.select_action(_observation(), _legal_actions())

        expected = RuleBasedAIAgent(player_id=1).select_action(_observation(), _legal_actions())
        self.assertEqual(chosen, expected)

    def test_client_returns_no_action_id_for_unparseable_response(self) -> None:
        def transport(_request, _timeout: float) -> str:
            return 'data: {"choices":[{"delta":{"content":"not-json"}}]}\ndata: [DONE]\n'

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )

        suggestion = client.suggest_action_id(
            observation=_observation(),
            legal_actions=_legal_actions(),
        )

        self.assertIsNone(suggestion.action_id)

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
