from __future__ import annotations

import json
import threading
import tempfile
import time
import unittest
from dataclasses import replace
from io import StringIO
from unittest.mock import patch

from decision_deadline import DecisionDeadline
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from integrations.botzone.agent_observability import AgentObservabilityRecorder
from integrations.botzone.agent_runtime import _StrictDeepSeekClient
from integrations.botzone.connector import MockConnector
from integrations.botzone.play_adapter import NoTributeRuleBasedHandler
from integrations.botzone.session import HandlerContext, HandlerResult, SessionStore
from integrations.botzone.stage_trace import StageTrace
from tests.test_botzone_deepseek_agent_runtime import _context
from tests.test_deepseek_step_e import _short_endgame_legal_actions, _short_endgame_observation


def _sse_action(action_id: int) -> list[bytes]:
    payload = {"choices": [{"delta": {"content": json.dumps({"action_id": action_id})}}]}
    return [f"data: {json.dumps(payload)}\n\n".encode(), b"data: [DONE]\n\n"]


class BotzoneDecisionDeadlineTests(unittest.TestCase):
    def test_connector_starts_one_transient_deadline_on_each_new_play_request(self) -> None:
        def poll_request(payload: dict[str, object]) -> bytes:
            return (
                "1 0\nsynthetic-match\n"
                + json.dumps(payload, separators=(",", ":"))
            ).encode()

        deal = {
            "stage": "deal",
            "deliver": list(range(27)),
            "your_id": 0,
            "global": {"level": "2", "tribute": 0, "first": None, "last": None},
        }
        play = {
            "stage": "play",
            "history": [[], [], [], []],
            "done": [],
            "pass_on": -1,
            "global": {
                "level": "2", "tribute": 0, "first": None, "last": None,
                "resist": False, "tribute_cards": {}, "return_cards": {},
            },
        }

        class Polls:
            def __init__(self) -> None:
                self.payloads = [poll_request(deal), poll_request(play)]

            def poll(self, _headers: object) -> bytes:
                return self.payloads.pop(0)

        class Clock:
            now = 100.0

            def __call__(self) -> float:
                return self.now

        seen: list[HandlerContext] = []

        def handler(context: HandlerContext) -> HandlerResult:
            seen.append(context)
            return HandlerResult(b"[]")

        with tempfile.TemporaryDirectory() as root:
            connector = MockConnector(
                SessionStore(root),
                Polls(),
                handler,
                decision_timeout_seconds=80.0,
                clock=Clock(),
            )
            connector.cycle()
            connector.cycle()
        self.assertEqual(len(seen), 2)
        self.assertIsNone(seen[0].decision_deadline)
        self.assertIsNotNone(seen[1].decision_deadline)
        assert seen[1].decision_deadline is not None
        self.assertEqual(seen[1].decision_deadline.deadline_monotonic, 180.0)
        self.assertEqual(seen[1].decision_deadline.remaining(), 80.0)
        self.assertNotIn("decision_deadline", seen[1].to_json())

    def test_strict_client_returns_one_fallback_boundary_and_quarantines_late_worker(self) -> None:
        release = threading.Event()
        entered = threading.Event()
        calls = 0

        class DelayedClient:
            def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
                nonlocal calls
                calls += 1
                entered.set()
                release.wait(2.0)
                return DeepSeekSuggestion(action_id=1, reasoning=None)

        trace_output = StringIO()
        client = _StrictDeepSeekClient(
            DelayedClient(),
            stage_trace=StageTrace(trace_output),
            response_reserve_seconds=0.01,
        )
        client.set_decision_deadline(time.monotonic() + 0.08)
        started = time.monotonic()
        result = client.suggest_action_id(legal_actions=[{"action_id": 1}])
        elapsed = time.monotonic() - started
        self.assertTrue(entered.is_set())
        self.assertIsNone(result.action_id)
        self.assertEqual(client.last_outcome, "timeout")
        self.assertIn('"stage":"model_complete"', trace_output.getvalue())
        self.assertIn('"outcome":"timeout"', trace_output.getvalue())
        self.assertLess(elapsed, 0.2)

        # A late answer cannot be reused and an unresponsive old call cannot
        # cause a second model worker to be started.
        second_deadline = time.monotonic() + 1.0
        client.set_decision_deadline(second_deadline)
        second = client.suggest_action_id(legal_actions=[{"action_id": 1}])
        self.assertIsNone(second.action_id)
        self.assertEqual(client.last_outcome, "timeout")
        self.assertEqual(calls, 1)

        release.set()
        for _ in range(100):
            if not client._worker_active:
                break
            time.sleep(0.005)
        self.assertFalse(client._worker_active)
        self.assertEqual(client.last_outcome, "timeout")
        client.set_decision_deadline(None)

    def test_deepseek_retry_does_not_start_after_the_total_budget_expires(self) -> None:
        calls = 0

        class FakeClock:
            now = 0.0

            def __call__(self) -> float:
                return self.now

        clock = FakeClock()

        def segmented_transport(_request: object, _timeout: float):
            nonlocal calls
            calls += 1

            def lines():
                clock.now += 1.0
                yield from _sse_action(1)

            return lines()

        client = DeepSeekClient(
            api_key="synthetic",
            base_url="https://synthetic.invalid",
            model="synthetic",
            timeout_seconds=30,
            max_retries=3,
            transport=segmented_transport,
        )
        observation = _short_endgame_observation()
        actions = _short_endgame_legal_actions()
        with patch("agents.deepseek_client.MODEL_RESPONSE_RESERVE_SECONDS", 0.005):
            with self.assertRaises(TimeoutError):
                client.suggest_action_id(
                    observation=observation,
                    legal_actions=actions,
                    decision_deadline=DecisionDeadline(0.5, clock=clock),
                )
        self.assertEqual(calls, 1)

    def test_seventy_seconds_of_segmented_sse_can_finish_within_budget(self) -> None:
        class FakeClock:
            now = 0.0

            def __call__(self) -> float:
                return self.now

        clock = FakeClock()
        actions = _short_endgame_legal_actions()
        expected_id = int(actions[0]["action_id"])
        encoded = json.dumps({"action_id": expected_id})
        fragments = [encoded[index:index + 3] for index in range(0, len(encoded), 3)]
        fragments.extend("" for _ in range(7 - len(fragments)))

        def segmented_transport(_request: object, _timeout: float):
            def lines():
                for fragment in fragments:
                    clock.now += 10.0
                    chunk = {"choices": [{"delta": {"content": fragment}}]}
                    yield f"data: {json.dumps(chunk)}\n".encode()
                yield b"data: [DONE]\n"

            return lines()

        client = DeepSeekClient(
            api_key="synthetic",
            base_url="https://synthetic.invalid",
            model="synthetic",
            timeout_seconds=30,
            max_retries=0,
            transport=segmented_transport,
        )
        with patch("agents.deepseek_client.MODEL_RESPONSE_RESERVE_SECONDS", 5.0):
            suggestion = client.suggest_action_id(
                observation=_short_endgame_observation(),
                legal_actions=actions,
                decision_deadline=DecisionDeadline(80.0, clock=clock),
            )
        self.assertEqual(clock.now, 70.0)
        self.assertEqual(suggestion.action_id, expected_id)

    def test_blocked_connection_establishment_isolated_from_handler_deadline(self) -> None:
        release = threading.Event()
        entered = threading.Event()
        self.addCleanup(release.set)
        open_calls = 0

        class Response:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

            def readline(self) -> bytes:
                return b"data: [DONE]\n"

        response = Response()

        def blocked_open(_request: object, *, timeout: float):
            nonlocal open_calls
            open_calls += 1
            entered.set()
            release.wait(2.0)
            return response

        client = DeepSeekClient(
            api_key="synthetic",
            base_url="https://synthetic.invalid",
            model="synthetic",
            timeout_seconds=30,
            max_retries=0,
        )
        strict = _StrictDeepSeekClient(client, response_reserve_seconds=0.01)
        strict.set_decision_deadline(time.monotonic() + 0.08)
        with patch("agents.deepseek_client.MODEL_RESPONSE_RESERVE_SECONDS", 0.005):
            with patch("agents.deepseek_client.urllib_request.urlopen", side_effect=blocked_open):
                suggestion = strict.suggest_action_id(
                    observation=_short_endgame_observation(),
                    legal_actions=_short_endgame_legal_actions(),
                )
        self.assertTrue(entered.is_set())
        self.assertIsNone(suggestion.action_id)
        self.assertEqual(strict.last_outcome, "timeout")
        self.assertEqual(open_calls, 1)
        release.set()
        for _ in range(100):
            if not strict._worker_active:
                break
            time.sleep(0.005)
        self.assertFalse(strict._worker_active)
        self.assertTrue(response.closed)

    def test_blocked_sse_read_is_closed_when_total_budget_expires(self) -> None:
        entered = threading.Event()
        released = threading.Event()
        socket_timeouts: list[float] = []

        class Socket:
            def settimeout(self, value: float) -> None:
                socket_timeouts.append(value)

        class Raw:
            _sock = Socket()

        class Buffered:
            raw = Raw()

        class Response:
            fp = Buffered()

            def __init__(self) -> None:
                self.closed = False

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

            def close(self) -> None:
                self.closed = True
                released.set()

            def readline(self) -> bytes:
                entered.set()
                released.wait(2.0)
                return b"data: [DONE]\n"

        response = Response()
        client = DeepSeekClient(
            api_key="synthetic",
            base_url="https://synthetic.invalid",
            model="synthetic",
            timeout_seconds=30,
            max_retries=0,
        )
        strict = _StrictDeepSeekClient(client, response_reserve_seconds=0.01)
        strict.set_decision_deadline(time.monotonic() + 0.08)
        with patch("agents.deepseek_client.MODEL_RESPONSE_RESERVE_SECONDS", 0.005):
            with patch("agents.deepseek_client.urllib_request.urlopen", return_value=response):
                suggestion = strict.suggest_action_id(
                    observation=_short_endgame_observation(),
                    legal_actions=_short_endgame_legal_actions(),
                )
        self.assertTrue(entered.is_set())
        self.assertIsNone(suggestion.action_id)
        self.assertEqual(strict.last_outcome, "timeout")
        self.assertTrue(response.closed)
        self.assertTrue(released.is_set())
        self.assertTrue(socket_timeouts)

    def test_handler_deadline_is_transient_and_timeout_keeps_a_canonical_response(self) -> None:
        deadline = DecisionDeadline(time.monotonic() + 15.0)
        context = replace(_context(), decision_deadline=deadline)
        self.assertNotIn("decision_deadline", context.to_json())
        seen: list[DecisionDeadline | None] = []

        class DeadlineAwareClient:
            last_outcome = "timeout"

            def set_decision_deadline(self, deadline: DecisionDeadline | None) -> None:
                seen.append(deadline)

            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                return DeepSeekSuggestion(action_id=None, reasoning=None)

        class Agent:
            def __init__(self) -> None:
                self.client = DeadlineAwareClient()
                self.last_decision_source = "model"

            def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
                suggestion = self.client.suggest_action_id(
                    observation=observation,
                    legal_actions=legal_actions,
                )
                if suggestion.action_id is not None:
                    return suggestion.action_id
                self.last_decision_source = "deepseek_rule_fallback"
                from agents.rule_based_ai import FrozenRuleBasedAIAgent

                return FrozenRuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)

        agent = Agent()
        handler = NoTributeRuleBasedHandler(lambda _player: agent, agent_mode="deepseek")
        result = handler(context)
        self.assertIsNotNone(result.response)
        self.assertIsNotNone(result.effect)
        self.assertEqual(seen, [context.decision_deadline, None])

    def test_handler_chain_falls_back_once_and_ignores_the_delayed_model_id(self) -> None:
        release = threading.Event()
        entered = threading.Event()
        transport_calls = 0
        self.addCleanup(release.set)

        class BlockingClient:
            def suggest_action_id(self, **_kwargs: object) -> DeepSeekSuggestion:
                nonlocal transport_calls
                transport_calls += 1
                entered.set()
                release.wait(2.0)
                return DeepSeekSuggestion(action_id=1, reasoning=None)

        strict_client = _StrictDeepSeekClient(BlockingClient(), response_reserve_seconds=0.02)
        observability = AgentObservabilityRecorder()

        class Agent:
            def __init__(self) -> None:
                self.client = strict_client
                self.last_decision_source = "model"

            def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
                suggestion = self.client.suggest_action_id(
                    observation=observation,
                    legal_actions=legal_actions,
                )
                if suggestion.action_id is not None:
                    return suggestion.action_id
                self.last_decision_source = "deepseek_rule_fallback"
                from agents.rule_based_ai import FrozenRuleBasedAIAgent

                return FrozenRuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)

        agent = Agent()
        factory = lambda _player_id: agent

        handler = NoTributeRuleBasedHandler(
            factory,
            fallback_to_rule=True,
            cache_agents=True,
            agent_mode="deepseek",
            observability=observability,
            decision_trace_enabled=True,
        )
        # This test isolates a late model worker. The contiguous default hand
        # now has enough canonical bindings to exhaust 0.6s before entering
        # the client; dense preparation and pre-model expiry have other tests.
        # Keep 27 distinct physical cards and the original timeout assertions.
        context = replace(_context(), own_hand=tuple(range(0, 108, 4)),
                          decision_deadline=DecisionDeadline(time.monotonic() + 0.6))

        started = time.monotonic()
        first = handler(context)
        elapsed = time.monotonic() - started
        self.assertTrue(entered.is_set())
        self.assertIsNotNone(first.response)
        self.assertIsNotNone(first.effect)
        self.assertIsNotNone(first.decision_trace)
        self.assertEqual(strict_client.last_outcome, "timeout")
        self.assertLess(elapsed, 1.2)
        snapshot = observability.snapshot("deepseek")
        self.assertEqual(dict(snapshot.model_outcome_counts), {"timeout": 1})

        # The next delivery may be handled, but a stuck late worker is never
        # duplicated and its eventual suggestion cannot replace the fallback.
        second = handler(replace(context, request_digest="next-request"))
        self.assertIsNotNone(second.response)
        self.assertIsNotNone(second.effect)
        self.assertEqual(transport_calls, 1)
        self.assertEqual(dict(observability.snapshot("deepseek").model_outcome_counts), {"timeout": 2})
        release.set()


if __name__ == "__main__":
    unittest.main()
