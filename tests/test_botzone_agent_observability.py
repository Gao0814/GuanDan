from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekSuggestion
from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent
from integrations.botzone.agent_observability import (
    AgentObservabilityError,
    AgentObservabilityRecorder,
    AgentObservabilitySnapshot,
)
from integrations.botzone.agent_runtime import _StrictDeepSeekClient
from integrations.botzone.cards import ALL_CARDS, card_id_for
from integrations.botzone.connector import MockConnector
from integrations.botzone.models import ActionClaim, GlobalState, HistoryEntry, PlayRequest
from integrations.botzone.play_adapter import AdapterError, NoTributeRuleBasedHandler, project_decision
from integrations.botzone.runner import ForegroundRunner, RunnerSummary, write_audit
from integrations.botzone.session import HandlerContext, SessionStore


def _context() -> HandlerContext:
    hand = (card_id_for("3", "h"), card_id_for("4", "d"))
    hand = hand + tuple(card_id for card_id in range(108) if card_id not in hand)[:25]
    state = GlobalState("2", 0, None, None, False)
    return HandlerContext(
        match_key="synthetic",
        request_digest="synthetic",
        request=PlayRequest((), (), -1, state),
        local_player_id=0,
        own_hand=hand,
        history=(),
        latest_window=(),
        global_state=state,
        finished=False,
    )


def _conditional_pass_context() -> HandlerContext:
    leader_card = card_id_for("BJ", None)
    leader = HistoryEntry(1, ActionClaim((leader_card,), (leader_card,)))
    own_hand = tuple(card.card_id for card in ALL_CARDS if card.rank not in {"SJ", "BJ"})[:27]
    state = GlobalState("2", 0, None, None, False)
    return HandlerContext(
        match_key="conditional-source",
        request_digest="synthetic",
        request=PlayRequest((leader,), (), -1, state),
        local_player_id=0,
        own_hand=own_hand,
        history=(leader,),
        latest_window=(leader,),
        global_state=state,
        finished=False,
    )


class _Delegate:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.calls = 0

    def suggest_action_id(self, **_: object) -> DeepSeekSuggestion:
        self.calls += 1
        if isinstance(self.answer, BaseException):
            raise self.answer
        return DeepSeekSuggestion(action_id=self.answer, reasoning="discarded")


class _ModelAgent:
    def __init__(self, client: _StrictDeepSeekClient) -> None:
        self.client = client
        self.last_decision_source = "model"

    def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        suggestion = self.client.suggest_action_id(observation=observation, legal_actions=legal_actions)
        if suggestion.action_id is not None:
            return suggestion.action_id
        # This deliberately models only the existing agent's internal rule fallback.
        return legal_actions[0]["action_id"]


class _DangerBlockAgent:
    last_decision_source = "danger_opponent_block"

    def __init__(self) -> None:
        self.client = _StrictDeepSeekClient(_Delegate(1))

    def select_action(self, _: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        self.client.suggest_action_id(observation={}, legal_actions=legal_actions)
        return legal_actions[0]["action_id"]


class _ShortEndgamePlanAgent:
    last_decision_source = "short_endgame_plan"

    def __init__(self) -> None:
        self.client = _StrictDeepSeekClient(_Delegate(1))

    def select_action(self, _: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        self.client.suggest_action_id(observation={}, legal_actions=legal_actions)
        return legal_actions[0]["action_id"]


class _ShortcutAgent:
    last_decision_source = "local"

    def select_action(self, _: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        return legal_actions[0]["action_id"]


class _ExplodingAgent:
    def select_action(self, _: dict[str, object], __: list[dict[str, object]]) -> object:
        raise RuntimeError("synthetic")


class _Transport:
    def __init__(self, polls: list[bytes | BaseException]) -> None:
        self._polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        result = self._polls.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class BotzoneAgentObservabilityTests(unittest.TestCase):
    def test_snapshot_is_frozen_canonical_and_rejects_malformed_counts(self) -> None:
        recorder = AgentObservabilityRecorder()
        recorder.record_decision_source("model")
        recorder.record_model_outcome("success")
        snapshot = recorder.snapshot("deepseek")
        self.assertEqual(
            snapshot.to_json(),
            {
                "agent_mode": "deepseek",
                "agent_decision_count": 1,
                "decision_source_counts": [["model", 1]],
                "model_attempt_count": 1,
                "model_outcome_counts": [["success", 1]],
                "rule_fallback_count": 0,
            },
        )
        self.assertTrue(hasattr(snapshot, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            snapshot.agent_mode = "rule"  # type: ignore[misc]
        for source in (True, "unknown", None):
            with self.subTest(source=type(source).__name__):
                with self.assertRaises(AgentObservabilityError):
                    recorder.record_decision_source(source)
        with self.assertRaises(AgentObservabilityError):
            AgentObservabilitySnapshot("deepseek", 1, (("model", 1), ("model", 1)), 1, (("success", 1),), 0)
        with self.assertRaises(AgentObservabilityError):
            AgentObservabilitySnapshot("deepseek", True, (("model", 1),), 1, (("success", 1),), 0)

    def test_conditional_mode_sources_are_low_cardinality_and_model_free(self) -> None:
        recorder = AgentObservabilityRecorder()
        recorder.record_decision_source("conditional_pressure_pass")
        recorder.record_decision_source("conditional_rule_based")
        snapshot = recorder.snapshot("conditional_pressure_pass")
        self.assertEqual(snapshot.agent_decision_count, 2)
        self.assertEqual(
            snapshot.decision_source_counts,
            (("conditional_pressure_pass", 1), ("conditional_rule_based", 1)),
        )
        self.assertEqual((snapshot.model_attempt_count, snapshot.model_outcome_counts, snapshot.rule_fallback_count), (0, (), 0))
        with self.assertRaises(AgentObservabilityError):
            AgentObservabilitySnapshot("conditional_pressure_pass", 1, (("rule_primary", 1),), 0, (), 0)

    def test_strict_client_classifies_only_fixed_outcomes(self) -> None:
        cases = (
            (1, "success"),
            (TimeoutError(), "timeout"),
            (RuntimeError("synthetic"), "exception"),
            (None, "invalid_suggestion"),
            (True, "invalid_suggestion"),
            ("1", "invalid_suggestion"),
            (1.0, "invalid_suggestion"),
            (-1, "invalid_suggestion"),
            (2, "invalid_suggestion"),
        )
        for answer, expected in cases:
            with self.subTest(expected=expected, answer_type=type(answer).__name__):
                client = _StrictDeepSeekClient(_Delegate(answer))
                client.suggest_action_id(observation={}, legal_actions=[{"action_id": 1}])
                self.assertEqual(client.last_outcome, expected)
                self.assertNotIn("synthetic", repr(client.last_outcome))

    def test_decision_sources_separate_primary_shortcut_and_internal_fallback(self) -> None:
        cases = (
            ("rule", lambda: _ShortcutAgent(), False, "rule_primary", (), ()),
            ("deepseek", lambda: _ShortcutAgent(), False, "local_shortcut", (), ()),
            (
                "deepseek",
                lambda: _ModelAgent(_StrictDeepSeekClient(_Delegate(1))),
                False,
                "model",
                (("success", 1),),
                (),
            ),
            (
                "deepseek",
                lambda: _ModelAgent(_StrictDeepSeekClient(_Delegate(TimeoutError()))),
                False,
                "deepseek_rule_fallback",
                (("timeout", 1),),
                ("deepseek_rule_fallback",),
            ),
            (
                "deepseek",
                lambda: _ModelAgent(_StrictDeepSeekClient(_Delegate(None))),
                False,
                "deepseek_rule_fallback",
                (("invalid_suggestion", 1),),
                ("deepseek_rule_fallback",),
            ),
            ("deepseek", _DangerBlockAgent, False, "danger_opponent_block", (("success", 1),), ()),
            ("deepseek", _ShortEndgamePlanAgent, False, "short_endgame_plan", (("success", 1),), ()),
            ("deepseek", lambda: _ExplodingAgent(), True, "adapter_rule_fallback", (), ("adapter_rule_fallback",)),
        )
        for mode, factory, outer_fallback, expected, outcomes, fallbacks in cases:
            with self.subTest(source=expected):
                recorder = AgentObservabilityRecorder()
                handler = NoTributeRuleBasedHandler(
                    lambda _: factory(),
                    fallback_to_rule=outer_fallback,
                    agent_mode=mode,
                    observability=recorder,
                )
                result = handler(_context())
                self.assertEqual(result.effect.action, tuple(json.loads(result.response)[0]))
                snapshot = handler.observability_snapshot()
                self.assertEqual(snapshot.agent_decision_count, 1)
                self.assertEqual(snapshot.decision_source_counts, ((expected, 1),))
                self.assertEqual(snapshot.model_outcome_counts, outcomes)
                self.assertEqual(snapshot.rule_fallback_count, len(fallbacks))

    def test_conditional_agent_uses_public_projection_and_distinguishes_both_sources(self) -> None:
        recorder = AgentObservabilityRecorder()
        handler = NoTributeRuleBasedHandler(
            lambda player_id: ConditionalPressurePassAIAgent(player_id=player_id),
            fallback_to_rule=False,
            cache_agents=True,
            agent_mode="conditional_pressure_pass",
            observability=recorder,
        )
        regular = handler(_context())
        pressure = handler(_conditional_pass_context())
        self.assertNotEqual(json.loads(regular.response)[0], [])
        self.assertEqual(json.loads(pressure.response)[0], [])
        self.assertEqual(pressure.effect.action, ())
        snapshot = handler.observability_snapshot()
        self.assertEqual(snapshot.agent_decision_count, 2)
        self.assertEqual(
            snapshot.decision_source_counts,
            (("conditional_pressure_pass", 1), ("conditional_rule_based", 1)),
        )
        self.assertEqual((snapshot.model_attempt_count, snapshot.rule_fallback_count), (0, 0))

    def test_failed_fallback_or_missing_provenance_never_records_a_completed_decision(self) -> None:
        recorder = AgentObservabilityRecorder()

        class _RuleFallbackFailure:
            def __init__(self, *, player_id: int) -> None:
                del player_id

            def select_action(self, _: dict[str, object], __: list[dict[str, object]]) -> object:
                raise RuntimeError("synthetic")

        with patch("integrations.botzone.play_adapter.FrozenRuleBasedAIAgent", _RuleFallbackFailure):
            with self.assertRaisesRegex(AdapterError, "^rule_fallback_failure$"):
                NoTributeRuleBasedHandler(
                    lambda _: _ExplodingAgent(),
                    fallback_to_rule=True,
                    agent_mode="deepseek",
                    observability=recorder,
                )(_context())
        self.assertEqual(recorder.snapshot("deepseek").agent_decision_count, 0)

    def test_deal_resend_ack_and_finished_do_not_duplicate_a_play_decision(self) -> None:
        raw = _Delegate(1)
        recorder = AgentObservabilityRecorder()
        handler = NoTributeRuleBasedHandler(
            lambda _: _ModelAgent(_StrictDeepSeekClient(raw)),
            fallback_to_rule=True,
            cache_agents=True,
            agent_mode="deepseek",
            observability=recorder,
        )
        state = {"level": "2", "tribute": 0, "first": None, "last": None}
        deal = json.dumps({"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": state})
        play = json.dumps(
            {
                "stage": "play",
                "history": [[], [], [], []],
                "done": [],
                "pass_on": -1,
                "global": dict(state, resist=False, tribute_cards={}, return_cards={}),
            }
        )
        transport = _Transport(
            [
                ("1 0\nsynthetic\n" + deal).encode("utf-8"),
                ("1 0\nsynthetic\n" + play).encode("utf-8"),
                RuntimeError("synthetic"),
                b"0 0\n",
                b"0 1\nsynthetic 0 4 0 0 0 0\n",
            ]
        )
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), transport, handler)
            for _ in range(5):
                connector.cycle()
        snapshot = handler.observability_snapshot()
        self.assertEqual(raw.calls, 1)
        self.assertEqual(snapshot.agent_decision_count, 1)
        self.assertEqual(snapshot.model_attempt_count, 1)
        self.assertEqual(handler._agents, {})

        context = _context()
        projection = replace(project_decision(context), provenance=MappingProxyType({}))
        recorder = AgentObservabilityRecorder()
        with patch("integrations.botzone.play_adapter.project_decision", return_value=projection):
            with self.assertRaisesRegex(AdapterError, "^missing_provenance$"):
                NoTributeRuleBasedHandler(
                    lambda _: _ShortcutAgent(), agent_mode="deepseek", observability=recorder
                )(context)
        self.assertEqual(recorder.snapshot("deepseek").agent_decision_count, 0)

    def test_conditional_mode_pending_replay_ack_and_release_do_not_duplicate_decisions(self) -> None:
        recorder = AgentObservabilityRecorder()
        handler = NoTributeRuleBasedHandler(
            lambda player_id: ConditionalPressurePassAIAgent(player_id=player_id),
            fallback_to_rule=False,
            cache_agents=True,
            agent_mode="conditional_pressure_pass",
            observability=recorder,
        )
        state = {"level": "2", "tribute": 0, "first": None, "last": None}
        deal = json.dumps({"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": state})
        play = json.dumps(
            {
                "stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1,
                "global": dict(state, resist=False, tribute_cards={}, return_cards={}),
            }
        )
        transport = _Transport(
            [
                ("1 0\nsynthetic\n" + deal).encode("utf-8"),
                ("1 0\nsynthetic\n" + play).encode("utf-8"),
                RuntimeError("synthetic"), b"0 0\n", b"0 1\nsynthetic 0 4 0 0 0 0\n",
            ]
        )
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), transport, handler)
            for _ in range(5):
                connector.cycle()
        snapshot = handler.observability_snapshot()
        self.assertEqual(snapshot.agent_decision_count, 1)
        self.assertEqual(snapshot.decision_source_counts, (("conditional_rule_based", 1),))
        self.assertEqual((snapshot.model_attempt_count, snapshot.rule_fallback_count), (0, 0))
        self.assertEqual(handler._agents, {})

    def test_v7_audit_preserves_agent_aggregates_and_rejects_inconsistent_snapshot(self) -> None:
        summary = RunnerSummary(
            1,
            1,
            0,
            0,
            1,
            1,
            0,
            0,
            "cycle_limit_unfinished",
            (),
            agent_mode="deepseek",
            agent_decision_count=1,
            decision_source_counts=(("model", 1),),
            model_attempt_count=1,
            model_outcome_counts=(("success", 1),),
            rule_fallback_count=0,
        )
        with TemporaryDirectory() as root:
            target = Path(root).parent / "agent-observability-audit.json"
            write_audit(target, summary, 6)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 7)
            self.assertEqual(payload["decision_source_counts"], [["model", 1]])
            self.assertEqual(payload["model_outcome_counts"], [["success", 1]])
            self.assertEqual(payload["result_category_counts"], [])
            for marker in ("match", "history", "prompt", "reasoning", "action_id"):
                self.assertNotIn(marker, json.dumps(payload).lower())
            with self.assertRaises(ValueError):
                write_audit(target, replace(summary, model_attempt_count=0), 6)

    def test_v7_audit_accepts_conditional_mode_without_schema_or_version_change(self) -> None:
        summary = RunnerSummary(
            1, 1, 0, 0, 1, 1, 0, 0, "cycle_limit_unfinished", (),
            agent_mode="conditional_pressure_pass",
            agent_decision_count=2,
            decision_source_counts=(("conditional_pressure_pass", 1), ("conditional_rule_based", 1)),
            model_attempt_count=0,
            model_outcome_counts=(),
            rule_fallback_count=0,
        )
        with TemporaryDirectory() as root:
            target = Path(root).parent / "conditional-agent-observability-audit.json"
            write_audit(target, summary, 6)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 7)
        self.assertEqual(payload["agent_mode"], "conditional_pressure_pass")
        self.assertEqual(
            payload["decision_source_counts"],
            [["conditional_pressure_pass", 1], ["conditional_rule_based", 1]],
        )
        self.assertEqual((payload["model_attempt_count"], payload["rule_fallback_count"]), (0, 0))

    def test_unavailable_snapshot_fails_closed_without_changing_connector_summary(self) -> None:
        class _EmptyConnector:
            def cycle(self) -> object:
                from integrations.botzone.connector import ConnectorCycle

                return ConnectorCycle(True, 0, 0, 0, 0, 0, ())

        def unavailable() -> AgentObservabilitySnapshot:
            raise AgentObservabilityError("synthetic")

        summary = ForegroundRunner(
            _EmptyConnector(),  # type: ignore[arg-type]
            max_consecutive_failures=1,
            backoff_seconds=1,
            sleep=lambda _: None,
            observability_snapshot=unavailable,
            agent_mode="deepseek",
        ).run(max_cycles=1)
        self.assertEqual((summary.cycles, summary.requests_seen, summary.responses_prepared), (1, 0, 0))
        self.assertFalse(summary.observability_valid)
        with TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                write_audit(Path(root).parent / "invalid-observability-audit.json", summary, 6)


if __name__ == "__main__":
    unittest.main()
