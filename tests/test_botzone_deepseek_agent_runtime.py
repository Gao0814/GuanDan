from __future__ import annotations

import json
import io
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekSuggestion
from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent
from agents.rule_based_ai import RuleBasedAIAgent
from integrations.botzone.agent_runtime import AgentRuntimeError, _StrictDeepSeekClient, build_agent_factory, prepare_agent_factory
from integrations.botzone.cards import card_id_for
from integrations.botzone.connector import MockConnector
from integrations.botzone.models import GlobalState, PlayRequest
from integrations.botzone.play_adapter import AdapterError, NoTributeRuleBasedHandler
from integrations.botzone.runner import build_foreground_runner
from integrations.botzone.runtime_config import RuntimeConfig
from integrations.botzone.session import HandlerContext, SessionStore
from tests.test_deepseek_step_e import (
    _short_endgame_legal_actions,
    _short_endgame_observation,
    _teammate_joker_legal_actions,
    _teammate_joker_observation,
)


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


def _strategy_action(action_id: int, pattern: str, cards: list[str]) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else [card[:-1] for card in cards],
        "carrier_cards": [] if pattern == "pass" else list(cards),
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": "pass" if pattern == "pass" else pattern,
    }


def _teammate_control_observation(*, leader_id: int | None = 3, malformed: bool = False) -> dict[str, object]:
    table_action = None
    history_actions: list[dict[str, object]] = [
        {
            "step_no": step,
            "round_no": 1,
            "player_id": ((step - 1) % 4) + 1,
            "declared_pattern": "pass",
            "declared_cards": [],
            "carrier_cards": [],
        }
        for step in range(1, 9)
    ]
    if leader_id is not None:
        table_action = {
            "action_id": None,
            "declared_pattern": "single",
            "declared_cards": ["9"],
            "carrier_cards": ["9S"],
            "display_text": "single:9",
        }
        history_action = dict(table_action)
        history_action.pop("action_id")
        if malformed:
            history_action["declared_cards"] = ["8"]
        history_action.update({"step_no": 9, "round_no": 2, "player_id": leader_id})
        history_actions.append(history_action)
    return {
        "my_info": {
            "player_id": 1,
            "team": "team_13",
            "hand_cards": ["3S", "3H", "4S", "4H", "5S", "5H", "6S", "6H"],
            "hand_count": 8,
            "remaining_single_card_count": 4,
        },
        "current_round": {
            "step_no": 9,
            "round_no": 2,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "single:9" if table_action is not None else "free",
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 8, "finished": False},
            {"player_id": 3, "team": "team_13", "hand_count": 8, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": 8, "finished": False},
        ],
        "history": {"actions": history_actions, "finish_order": []},
    }


def _deepseek_handler(raw: _RawClient) -> NoTributeRuleBasedHandler:
    factory = build_agent_factory(
        "deepseek",
        config_loader=lambda: _config(),
        client_factory=lambda **_: raw,
        deepseek_agent_factory=_ClientDrivenAgent,
        rag_factory=lambda: None,
    )
    return NoTributeRuleBasedHandler(factory, fallback_to_rule=True, cache_agents=True, agent_mode="deepseek")


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

    def test_conditional_mode_composes_without_deepseek_configuration_and_is_cached_by_runner(self) -> None:
        calls: list[str] = []

        def unavailable() -> object:
            calls.append("config")
            raise AssertionError("must not load configuration")

        factory = build_agent_factory("conditional_pressure_pass", config_loader=unavailable)
        self.assertIsInstance(factory(1), ConditionalPressurePassAIAgent)
        self.assertEqual(calls, [])
        prepared = prepare_agent_factory("conditional_pressure_pass")
        self.assertIsNotNone(prepared)
        assert prepared is not None
        self.assertIsInstance(prepared(1), ConditionalPressurePassAIAgent)
        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
            runner = build_foreground_runner(
                config,
                _Transport([b"0 0\n"]),
                agent_mode="conditional_pressure_pass",
                prepared_agent_factory=factory,
                sleep=lambda _: None,
            )
            handler = runner._connector._handler
            self.assertFalse(handler._fallback_to_rule)
            self.assertTrue(handler._cache_agents)
            self.assertEqual(handler._agent_mode, "conditional_pressure_pass")

    def test_deepseek_fallback_has_distinct_failure_categories_and_single_attempts(self) -> None:
        from integrations.botzone.play_adapter import project_decision

        invalid_action_id = max(
            int(action["action_id"])
            for action in project_decision(_context()).legal_actions
        ) + 1

        class _Fallback:
            calls = 0
            answer: object = 1

            def __init__(self, *, player_id: int) -> None:
                del player_id

            def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
                del observation, legal_actions
                _Fallback.calls += 1
                if isinstance(_Fallback.answer, BaseException):
                    raise _Fallback.answer
                return _Fallback.answer

        cases = (
            (RuntimeError("synthetic"), 1, None),
            (RuntimeError("synthetic"), RuntimeError("synthetic"), "rule_fallback_failure"),
            (True, True, "invalid_rule_fallback_action_id"),
            (True, invalid_action_id, "invalid_rule_fallback_action_id"),
        )
        for primary, fallback, expected_error in cases:
            with self.subTest(primary=type(primary).__name__, fallback=type(fallback).__name__):
                raw = _RawClient(primary)
                _Fallback.calls = 0
                _Fallback.answer = fallback
                with patch("integrations.botzone.play_adapter.FrozenRuleBasedAIAgent", _Fallback):
                    if expected_error is None:
                        result = _deepseek_handler(raw)(_context())
                        self.assertEqual(result.effect.action, tuple(json.loads(result.response)[0]))
                    else:
                        with self.assertRaisesRegex(AdapterError, "^" + expected_error + "$"):
                            _deepseek_handler(raw)(_context())
                self.assertEqual(len(raw.calls), 1)
                self.assertEqual(_Fallback.calls, 1)

        class _ExplodingAgent:
            def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
                del observation, legal_actions
                raise RuntimeError("synthetic")

        _Fallback.calls = 0
        _Fallback.answer = 1
        with patch("integrations.botzone.play_adapter.RuleBasedAIAgent", _Fallback):
            result = NoTributeRuleBasedHandler(
                lambda _: _ExplodingAgent(), fallback_to_rule=True
            )(_context())
        self.assertEqual(result.effect.action, tuple(json.loads(result.response)[0]))
        self.assertEqual(_Fallback.calls, 1)

    def test_deepseek_fallback_preserves_missing_provenance(self) -> None:
        from dataclasses import replace
        from types import MappingProxyType
        from integrations.botzone.play_adapter import project_decision

        context = _context()
        projection = replace(project_decision(context), provenance=MappingProxyType({}))
        raw = _RawClient(True)
        with patch("integrations.botzone.play_adapter.project_decision", return_value=projection):
            with self.assertRaisesRegex(AdapterError, "^missing_provenance$"):
                _deepseek_handler(raw)(context)
        self.assertEqual(len(raw.calls), 1)

    def test_deepseek_preflight_composition_and_failure_precede_transport(self) -> None:
        from integrations.botzone import __main__ as botzone_main

        constructed: list[int] = []

        def builder(mode: str) -> object:
            self.assertEqual(mode, "deepseek")

            def factory(player_id: int) -> object:
                constructed.append(player_id)
                return object()

            return factory

        self.assertIsNotNone(prepare_agent_factory("deepseek", agent_factory_builder=builder))
        self.assertEqual(constructed, [1])
        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
            output = io.StringIO()
            with (
                patch.object(botzone_main, "load_runtime_config", return_value=config),
                patch.object(botzone_main, "preflight_state_directory"),
                patch.object(botzone_main, "prepare_agent_factory", return_value=builder("deepseek")) as prepare,
                patch.object(botzone_main, "LocalAIHttpTransport", side_effect=AssertionError("transport_constructed")),
                redirect_stdout(output),
            ):
                self.assertEqual(botzone_main.main(["--agent", "deepseek", "--preflight-only"]), 0)
            self.assertEqual(output.getvalue(), "preflight_ready\n")
            self.assertEqual(prepare.call_count, 1)
        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
            output = io.StringIO()
            with (
                patch.object(botzone_main, "load_runtime_config", return_value=config),
                patch.object(botzone_main, "preflight_state_directory"),
                patch.object(botzone_main, "prepare_agent_factory", side_effect=AgentRuntimeError("synthetic")),
                patch.object(botzone_main, "LocalAIHttpTransport") as transport,
                patch.object(botzone_main, "build_foreground_runner") as runner,
                redirect_stdout(output),
            ):
                self.assertEqual(botzone_main.main(["--agent", "deepseek", "--preflight-only"]), 2)
            self.assertEqual(output.getvalue(), "preflight_agent_composition_failed\n")
            self.assertEqual(transport.call_count, 0)
            self.assertEqual(runner.call_count, 0)

    def test_conditional_preflight_composition_precedes_transport_without_configuration(self) -> None:
        from integrations.botzone import __main__ as botzone_main

        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://example.invalid", state_directory=Path(root))
            output = io.StringIO()
            with (
                patch.object(botzone_main, "load_runtime_config", return_value=config),
                patch.object(botzone_main, "preflight_state_directory"),
                patch.object(botzone_main, "LocalAIHttpTransport") as transport,
                patch.object(botzone_main, "build_foreground_runner") as runner,
                redirect_stdout(output),
            ):
                self.assertEqual(botzone_main.main(["--agent", "conditional_pressure_pass", "--preflight-only"]), 0)
            self.assertEqual(output.getvalue(), "preflight_ready\n")
            self.assertEqual(transport.call_count, 0)
            self.assertEqual(runner.call_count, 0)

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            botzone_main.main(["--agent", "conditional-pressure-pass", "--preflight-only"])

    def test_cli_passes_only_explicit_agent_mode_to_composition_root(self) -> None:
        from integrations.botzone import __main__ as botzone_main

        for mode in ("rule", "deepseek", "conditional_pressure_pass"):
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

    def test_deepseek_factory_passes_short_endgame_minimum_groups_prompt(self) -> None:
        raw = _RawClient(3)
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()):
            factory = build_agent_factory(
                "deepseek",
                config_loader=lambda: _config(),
                client_factory=lambda **_: raw,
            )
            agent = factory(1)
            self.assertEqual(
                agent.select_action(_short_endgame_observation(), _short_endgame_legal_actions()),
                3,
            )

        self.assertEqual(len(raw.calls), 1)
        prompt = raw.calls[0].get("strategy_intent_prompt")
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertEqual(
            (agent.last_strategy_intent.status, agent.last_strategy_intent.intent, agent.last_strategy_intent.reason_codes),
            ("available", "run_out", ("short_endgame_minimum_groups",)),
        )
        self.assertEqual((prompt.status, prompt.intent, prompt.diagnostics), ("ready", "run_out", ()))
        self.assertIn("最少剩余分组", prompt.text)
        self.assertIn("避免无谓拆散已有组合", prompt.text)
        rag_context = raw.calls[0].get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)
        scene_tags = rag_context.get("scene_tags")
        self.assertIsInstance(scene_tags, dict)
        assert isinstance(scene_tags, dict)
        self.assertEqual(
            tuple(scene_tags.get(key) for key in ("scene", "phase", "action_context")),
            ("endgame", "near_open_endgame", "endgame"),
        )
        self.assertEqual(agent.last_decision_source, "model")

    def test_deepseek_factory_enables_validated_teammate_control_prompt_without_rewriting_model_choice(self) -> None:
        actions = [
            _strategy_action(1, "pass", []),
            _strategy_action(2, "bomb", ["9S", "9H", "9C", "9D"]),
        ]
        for selected in (1, 2):
            with self.subTest(selected=selected):
                raw = _RawClient(selected)
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()):
                    factory = build_agent_factory(
                        "deepseek",
                        config_loader=lambda: _config(),
                        client_factory=lambda **_: raw,
                        rag_factory=lambda: None,
                    )
                    agent = factory(1)
                    self.assertIsInstance(agent, DeepSeekAIAgent)
                    assert isinstance(agent, DeepSeekAIAgent)
                    self.assertTrue(agent.strategy_router_shadow_enabled)
                    self.assertTrue(agent.strategy_intent_prompt_enabled)
                    self.assertEqual(agent.select_action(_teammate_control_observation(), actions), selected)

                self.assertEqual(len(raw.calls), 1)
                prompt = raw.calls[0].get("strategy_intent_prompt")
                self.assertIsNotNone(prompt)
                assert prompt is not None
                self.assertEqual(
                    (prompt.status, prompt.intent, prompt.diagnostics),
                    ("ready", "support_teammate", ()),
                )
                self.assertIn("队友当前控桌", prompt.text)
                self.assertEqual(agent.last_decision_source, "model")

    def test_deepseek_factory_passes_special_big_joker_preservation_prompt(self) -> None:
        for selected, expected_action, expected_source in (
            (1, 1, "model"),
            (2, 2, "model"),
        ):
            with self.subTest(selected=selected):
                raw = _RawClient(selected)
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()):
                    factory = build_agent_factory(
                        "deepseek",
                        config_loader=lambda: _config(),
                        client_factory=lambda **_: raw,
                        rag_factory=lambda: None,
                    )
                    agent = factory(4)
                    self.assertIsInstance(agent, DeepSeekAIAgent)
                    assert isinstance(agent, DeepSeekAIAgent)
                    self.assertEqual(
                        agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions()),
                        expected_action,
                    )

                self.assertEqual(len(raw.calls), 1)
                prompt = raw.calls[0].get("strategy_intent_prompt")
                self.assertIsNotNone(prompt)
                assert prompt is not None
                self.assertEqual(
                    (agent.last_strategy_intent.status, agent.last_strategy_intent.reason_codes),
                    ("available", ("teammate_big_joker_preservation",)),
                )
                self.assertEqual((prompt.status, prompt.intent, prompt.diagnostics), ("ready", "support_teammate", ()))
                self.assertIn("保留大王这一高价值控制资源", prompt.text)
                self.assertEqual(agent.last_decision_source, expected_source)
                self.assertEqual(agent.client.last_outcome, "success")

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

    def test_strict_short_reason_passes_only_with_current_valid_id_in_both_paths(self) -> None:
        for with_deadline in (False, True):
            raw = SimpleNamespace(suggest_action_id=lambda **_: SimpleNamespace(
                action_id=1, reasoning="long-forbidden", reason="短\n" + "🙂" * 121))
            client = _StrictDeepSeekClient(raw)
            if with_deadline:
                client.set_decision_deadline(time.monotonic() + 20)
            result = client.suggest_action_id(legal_actions=[{"action_id": 1}])
            self.assertEqual(result.action_id, 1)
            self.assertEqual(result.reason, "短 " + "🙂" * 118)
            self.assertTrue(result.reason_truncated)
            self.assertIsNone(result.reasoning)
            raw.suggest_action_id = lambda **_: DeepSeekSuggestion(999, None, reason="invalid-short")
            invalid = client.suggest_action_id(legal_actions=[{"action_id": 1}])
            self.assertIsNone(invalid.reason)
            self.assertEqual(client.last_outcome, "invalid_suggestion")

    def test_cached_agent_does_not_reuse_reason_on_failure_local_or_disabled_sink(self) -> None:
        answer = DeepSeekSuggestion(1, None, reason="synthetic-contradictory-finish-claim")

        def suggest(**_):
            if isinstance(answer, Exception):
                raise answer
            return answer

        raw = SimpleNamespace(suggest_action_id=suggest)
        events = []
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()):
            agent = build_agent_factory("deepseek", config_loader=_config,
                client_factory=lambda **_: raw, rag_factory=lambda: None)(4)
            agent.set_evidence_sink(lambda event, data: events.append((event, data)))
            self.assertEqual(agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions()), 1)
            self.assertEqual(events[-1][1]["reason"], answer.reason)
            answer = DeepSeekSuggestion(999, None, reason="invalid-forbidden-reason")
            agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions())
            self.assertEqual(events[-1], ("model_complete", {"outcome": "invalid_suggestion"}))
            answer = RuntimeError("exception-forbidden-body")
            agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions())
            self.assertEqual(events[-1], ("model_complete", {"outcome": "exception"}))
            previous = len(events)
            self.assertEqual(agent.select_action(_teammate_joker_observation(own_count=1),
                                                _teammate_joker_legal_actions()), 2)
            self.assertEqual(len(events), previous)
            agent.set_evidence_sink(None)
            answer = DeepSeekSuggestion(1, None, reason="disabled-forbidden-reason")
            self.assertEqual(agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions()), 1)
            self.assertEqual(len(events), previous)
            agent.set_evidence_sink(lambda *_: (_ for _ in ()).throw(OSError("write-failure")))
            self.assertEqual(agent.select_action(_teammate_joker_observation(), _teammate_joker_legal_actions()), 1)


    def test_model_faults_and_invalid_ids_fallback_to_rule_action(self) -> None:
        from integrations.botzone.play_adapter import project_decision

        invalid_action_id = max(
            int(action["action_id"])
            for action in project_decision(_context()).legal_actions
        ) + 1
        expected = NoTributeRuleBasedHandler()(_context()).response
        for answer in (RuntimeError("synthetic"), None, True, "1", 1.0, -1, invalid_action_id):
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
