from __future__ import annotations

import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekSuggestion
from agents.rule_based_ai import RuleBasedAIAgent
from integrations.botzone.agent_runtime import AgentRuntimeError, _StrictDeepSeekClient, build_agent_factory
from integrations.botzone.cards import card_id_for
from integrations.botzone.connector import MockConnector
from integrations.botzone.models import GlobalState, PlayRequest
from integrations.botzone.play_adapter import NoTributeRuleBasedHandler
from integrations.botzone.runner import build_foreground_runner
from integrations.botzone.runtime_config import RuntimeConfig
from integrations.botzone.session import HandlerContext, SessionStore


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _deal_inner() -> dict[str, object]:
    return {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}


def _envelope(requests: list[dict[str, object]], responses: list[object]) -> str:
    return json.dumps({"requests": requests, "responses": responses}, separators=(",", ":"))


def _play_envelope() -> str:
    play = {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": dict(_global(), resist=False, tribute_cards={}, return_cards={}),
    }
    return _envelope([_deal_inner(), play], [[]])


def _context() -> HandlerContext:
    hand = (card_id_for("3", "h"), card_id_for("4", "d"))
    hand = hand + tuple(card_id for card_id in range(108) if card_id not in hand)[:25]
    state = GlobalState("2", 0, None, None, False)
    return HandlerContext(
        match_key="synthetic-session",
        request_digest="synthetic-digest",
        request=PlayRequest((), (), -1, state),
        local_player_id=0,
        own_hand=hand,
        history=(),
        latest_window=(),
        global_state=state,
        finished=False,
    )


class _Transport:
    def __init__(self, polls: list[bytes | BaseException]) -> None:
        self.polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        result = self.polls.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _RawClient:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.calls: list[dict[str, object]] = []

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.calls.append(dict(kwargs))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return DeepSeekSuggestion(action_id=self.answer, reasoning="ignored")


class _ClientDrivenAgent:
    def __init__(self, *, client: object, **_: object) -> None:
        self._client = client

    def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        return self._client.suggest_action_id(observation=observation, legal_actions=legal_actions).action_id  # type: ignore[attr-defined]


def _config(key: str | None = "synthetic-credential") -> object:
    return SimpleNamespace(
        deepseek_api_key=key,
        deepseek_base_url="https://example.invalid",
        deepseek_model="synthetic-model",
        deepseek_timeout=1,
        deepseek_max_retries=0,
        hand_evaluation_enabled=False,
        opening_formula_enabled=False,
        card_tracking_enabled=False,
    )


def _deepseek_handler(raw: _RawClient) -> NoTributeRuleBasedHandler:
    factory = build_agent_factory(
        "deepseek",
        config_loader=lambda: _config(),
        client_factory=lambda **_: raw,
        deepseek_agent_factory=_ClientDrivenAgent,
        rag_factory=lambda: None,
    )
    return NoTributeRuleBasedHandler(factory, fallback_to_rule=True, cache_agents=True)


class BotzoneDeepSeekAgentRuntimeTests(unittest.TestCase):
    def test_rule_mode_never_loads_deepseek_configuration_or_factory(self) -> None:
        calls: list[str] = []

        def unavailable() -> object:
            calls.append("config")
            raise AssertionError("must not load configuration")

        factory = build_agent_factory("rule", config_loader=unavailable)
        self.assertIsInstance(factory(1), RuleBasedAIAgent)
        self.assertEqual(calls, [])
        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
            runner = build_foreground_runner(
                config,
                _Transport([b"0 0\n"]),
                agent_factory_builder=lambda _: unavailable(),
                sleep=lambda _: None,
            )
            self.assertEqual(runner.run(max_cycles=1).cycles, 1)
        self.assertEqual(calls, [])

    def test_deepseek_mode_requires_key_before_transport_or_client(self) -> None:
        client_calls: list[object] = []
        with self.assertRaises(AgentRuntimeError):
            build_agent_factory(
                "deepseek",
                config_loader=lambda: _config(None),
                client_factory=lambda **kwargs: client_calls.append(kwargs),
                rag_factory=lambda: None,
            )
        self.assertEqual(client_calls, [])

    def test_cli_passes_only_explicit_agent_mode_to_composition_root(self) -> None:
        from integrations.botzone import __main__ as botzone_main

        for mode in ("rule", "deepseek"):
            with self.subTest(mode=mode), TemporaryDirectory() as root:
                config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
                runner = SimpleNamespace(run=lambda **_: SimpleNamespace(cycles=1, finished_seen=0))
                output = io.StringIO()
                with (
                    patch.object(botzone_main, "load_runtime_config", return_value=config),
                    patch.object(botzone_main, "preflight_state_directory"),
                    patch.object(botzone_main, "LocalAIHttpTransport", return_value=object()) as transport,
                    patch.object(botzone_main, "build_foreground_runner", return_value=runner) as build,
                    patch.object(botzone_main, "exit_code_for", return_value=6),
                    redirect_stdout(output),
                ):
                    result = botzone_main.main(["--agent", mode])
                self.assertEqual(result, 6)
                self.assertEqual(build.call_args.kwargs["agent_mode"], mode)
                self.assertEqual(transport.call_count, 1)

    def test_deepseek_factory_composes_existing_agent_without_real_configuration(self) -> None:
        raw = _RawClient(1)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()):
            factory = build_agent_factory(
                "deepseek",
                config_loader=lambda: _config(),
                client_factory=lambda **_: raw,
                rag_factory=lambda: None,
            )
            agent = factory(1)
        self.assertIsInstance(agent, DeepSeekAIAgent)
        self.assertEqual(raw.calls, [])

    def test_valid_model_id_uses_provenance_and_public_payload_only(self) -> None:
        raw = _RawClient(1)
        result = _deepseek_handler(raw)(_context())
        self.assertEqual(result.effect.action, tuple(json.loads(result.response)[0]))
        self.assertEqual(len(raw.calls), 1)
        observed = raw.calls[0]["observation"]
        self.assertIsInstance(observed, dict)
        assert isinstance(observed, dict)
        self.assertNotIn("match_key", observed)
        self.assertNotIn("request_digest", observed)
        self.assertNotIn("own_hand", observed)
        self.assertNotIn("session", repr(observed).lower())
        self.assertTrue(all(isinstance(card, str) for card in observed["my_info"]["hand_cards"]))

    def test_client_wrapper_discards_free_form_model_text(self) -> None:
        raw = _RawClient(1)
        suggestion = _StrictDeepSeekClient(raw).suggest_action_id(
            observation={}, legal_actions=[{"action_id": 1}]
        )
        self.assertEqual(suggestion.action_id, 1)
        self.assertIsNone(suggestion.reasoning)

    def test_model_faults_and_invalid_ids_fallback_to_rule_action(self) -> None:
        expected = NoTributeRuleBasedHandler()(_context()).response
        for answer in (RuntimeError("synthetic"), None, True, "1", 1.0, -1, 999):
            with self.subTest(answer_type=type(answer).__name__):
                raw = _RawClient(answer)
                self.assertEqual(_deepseek_handler(raw)(_context()).response, expected)
                self.assertEqual(len(raw.calls), 1)

    def test_pending_resend_does_not_repeat_model_and_finished_releases_cache(self) -> None:
        raw = _RawClient(1)
        handler = _deepseek_handler(raw)
        with TemporaryDirectory() as root:
            deal = ("1 0\nsynthetic-session\n" + _envelope([_deal_inner()], [])).encode("utf-8")
            play = ("1 0\nsynthetic-session\n" + _play_envelope()).encode("utf-8")
            finished = b"0 1\nsynthetic-session 0 4 0 0 0 0\n"
            transport = _Transport([deal, play, RuntimeError("synthetic"), b"0 0\n", finished])
            connector = MockConnector(SessionStore(root), transport, handler)
            connector.cycle()
            connector.cycle()
            connector.cycle()
            MockConnector(SessionStore(root), transport, handler).cycle()
            cycle = MockConnector(SessionStore(root), transport, handler).cycle()
        self.assertEqual(len(raw.calls), 1)
        self.assertEqual(cycle.finished_qualified, 0)
        self.assertEqual(handler._agents, {})

    def test_deepseek_agents_are_scoped_by_match_and_player(self) -> None:
        raw = _RawClient(1)
        handler = _deepseek_handler(raw)
        first = _context()
        second = HandlerContext(
            match_key="synthetic-other-session",
            request_digest=first.request_digest,
            request=first.request,
            local_player_id=first.local_player_id,
            own_hand=first.own_hand,
            history=first.history,
            latest_window=first.latest_window,
            global_state=first.global_state,
            finished=first.finished,
        )
        handler(first)
        handler(second)
        self.assertEqual(len(handler._agents), 2)
        handler.release_match(first.match_key)
        self.assertEqual(len(handler._agents), 1)


if __name__ == "__main__":
    unittest.main()
