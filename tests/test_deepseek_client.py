"""Tests for minimal DeepSeek client call chain and fallback behavior."""

import json
import unittest

from agents.base import AgentContext
from agents.deepseek_client import DeepSeekClient
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.state import GameState, PlayerState, TableConstraint


def _state_with_hand(hand: tuple[Card, ...]) -> GameState:
    players = (
        PlayerState(player_id=0, hand_cards=hand),
        PlayerState(player_id=1, hand_cards=()),
        PlayerState(player_id=2, hand_cards=()),
        PlayerState(player_id=3, hand_cards=()),
    )
    return GameState(players=players, current_player_id=0, table_constraint=TableConstraint())


class TestDeepSeekClient(unittest.TestCase):
    def test_calls_transport_and_parses_legal_suggestion(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            body = request.data.decode("utf-8") if request.data else ""
            captured["body"] = json.loads(body)
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "suggested_action": {
                                            "action_type": "play",
                                            "declared_pattern": "single",
                                            "cards": ["7S"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                }
            )

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            timeout_seconds=3.5,
            transport=transport,
        )
        state = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),
            Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE),
        )

        suggestion = client.suggest_action(state, legal, AgentContext(step_no=1))

        self.assertIsInstance(suggestion, dict)
        assert isinstance(suggestion, dict)
        self.assertEqual(suggestion.get("action_type"), "play")
        self.assertEqual(suggestion.get("declared_pattern"), "single")
        self.assertEqual(suggestion.get("cards"), ["7S"])

        self.assertEqual(captured.get("url"), "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured.get("auth"), "Bearer test-key")
        self.assertEqual(captured.get("timeout"), 3.5)
        self.assertIsInstance(captured.get("body"), dict)

    def test_returns_none_on_empty_response(self) -> None:
        def transport(request, timeout: float) -> str:
            return json.dumps({"choices": [{"message": {"content": ""}}]})

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )
        state = _state_with_hand((Card(rank="7", suit="S"),))
        legal = (Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),)

        suggestion = client.suggest_action(state, legal, AgentContext(step_no=2))
        self.assertIsNone(suggestion)

    def test_suggest_action_includes_rag_context_in_request_payload(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else ""
            captured["body"] = json.loads(body)
            return json.dumps({"choices": [{"message": {"content": "{}"}}]})

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )

        state = _state_with_hand((Card(rank="7", suit="S"),))
        legal = (Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),)

        rag_context = {
            "rule": [{"doc_id": "rule:1", "snippet": "lead single"}],
            "experience": [{"doc_id": "exp:1", "snippet": "safe opening"}],
        }
        _ = client.suggest_action(
            state,
            legal,
            AgentContext(step_no=5),
            rag_context=rag_context,
        )

        body = captured.get("body")
        self.assertIsInstance(body, dict)
        assert isinstance(body, dict)
        messages = body.get("messages")
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        self.assertGreaterEqual(len(messages), 2)
        user_content = messages[1].get("content") if isinstance(messages[1], dict) else None
        self.assertIsInstance(user_content, str)
        assert isinstance(user_content, str)
        user_payload = json.loads(user_content)
        self.assertIn("rag_context", user_payload)
        self.assertEqual(user_payload["rag_context"], rag_context)

    def test_prompt_emphasizes_compound_patterns_and_legal_boundary(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else ""
            captured["body"] = json.loads(body)
            return json.dumps({"choices": [{"message": {"content": "{}"}}]})

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )

        state = _state_with_hand(
            (
                Card(rank="3", suit="S"),
                Card(rank="4", suit="S"),
                Card(rank="5", suit="S"),
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="3", suit="S"),
                    Card(rank="4", suit="S"),
                    Card(rank="5", suit="S"),
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                ),
                PatternType.STRAIGHT,
            ),
        )
        _ = client.suggest_action(state, legal, AgentContext(step_no=6))

        body = captured.get("body")
        self.assertIsInstance(body, dict)
        assert isinstance(body, dict)
        messages = body.get("messages")
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        self.assertGreaterEqual(len(messages), 2)
        system_content = messages[0].get("content") if isinstance(messages[0], dict) else None
        self.assertIsInstance(system_content, str)
        assert isinstance(system_content, str)

        self.assertIn("legal_actions", system_content)
        self.assertIn("复合牌型", system_content)
        self.assertIn("避免无意义单张", system_content)
        self.assertIn("有合理非炸弹动作时不要先炸", system_content)
        self.assertIn("不要为了出顺子而拆更高价值组合", system_content)
        self.assertIn("不要为了平滑出牌牺牲明显更优的保组动作", system_content)
        self.assertIn("少破组、少浪费、组合完整", system_content)

    def test_user_payload_contains_action_focus_hints(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            body = request.data.decode("utf-8") if request.data else ""
            captured["body"] = json.loads(body)
            return json.dumps({"choices": [{"message": {"content": "{}"}}]})

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=transport,
        )

        state = _state_with_hand(
            (
                Card(rank="4", suit="S"),
                Card(rank="4", suit="H"),
                Card(rank="5", suit="S"),
                Card(rank="5", suit="H"),
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="Q", suit="S"),
                Card(rank="Q", suit="H"),
                Card(rank="Q", suit="C"),
                Card(rank="Q", suit="D"),
            )
        )
        legal = (
            Action(0, ActionType.PLAY, (Card(rank="4", suit="S"),), PatternType.SINGLE),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="4", suit="S"),
                    Card(rank="4", suit="H"),
                    Card(rank="5", suit="S"),
                    Card(rank="5", suit="H"),
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                ),
                PatternType.PAIR_STRAIGHT,
            ),
            Action(
                0,
                ActionType.PLAY,
                (
                    Card(rank="Q", suit="S"),
                    Card(rank="Q", suit="H"),
                    Card(rank="Q", suit="C"),
                    Card(rank="Q", suit="D"),
                ),
                PatternType.BOMB,
            ),
        )
        _ = client.suggest_action(state, legal, AgentContext(step_no=7))

        body = captured.get("body")
        self.assertIsInstance(body, dict)
        assert isinstance(body, dict)
        messages = body.get("messages")
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        user_content = messages[1].get("content") if isinstance(messages[1], dict) else None
        self.assertIsInstance(user_content, str)
        assert isinstance(user_content, str)
        user_payload = json.loads(user_content)

        self.assertIn("action_focus", user_payload)
        focus = user_payload["action_focus"]
        self.assertIsInstance(focus, dict)
        self.assertIn("preferred_patterns", focus)
        self.assertIn("avoid_unnecessary_bomb", focus)
        self.assertIn("avoid_low_value_single_when_compound_exists", focus)
        self.assertIn("pair_straight", focus.get("preferred_patterns", []))

    def test_raises_timeout_error_and_runtime_error_passthrough(self) -> None:
        def timeout_transport(request, timeout: float) -> str:
            raise TimeoutError("simulated timeout")

        timeout_client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=timeout_transport,
        )
        state = _state_with_hand((Card(rank="7", suit="S"),))
        legal = (Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),)
        with self.assertRaises(TimeoutError):
            timeout_client.suggest_action(state, legal, AgentContext(step_no=3))

        def error_transport(request, timeout: float) -> str:
            raise RuntimeError("simulated client error")

        error_client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=error_transport,
        )
        with self.assertRaises(RuntimeError):
            error_client.suggest_action(state, legal, AgentContext(step_no=4))

    def test_timeout_is_retried_once_then_success(self) -> None:
        calls = {"n": 0}

        def flaky_transport(request, timeout: float) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError("simulated timeout")
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "suggested_action": {
                                            "action_type": "play",
                                            "declared_pattern": "single",
                                            "cards": ["7S"],
                                        }
                                    }
                                )
                            }
                        }
                    ]
                }
            )

        client = DeepSeekClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            transport=flaky_transport,
        )
        state = _state_with_hand((Card(rank="7", suit="S"),))
        legal = (Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE),)

        suggestion = client.suggest_action(state, legal, AgentContext(step_no=8))
        self.assertIsInstance(suggestion, dict)
        self.assertEqual(calls["n"], 2)
