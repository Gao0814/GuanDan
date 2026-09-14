from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.connector import MockConnector
from integrations.botzone.decision_trace import ConnectorDecisionTrace
from integrations.botzone.agent_observability import AgentObservabilityRecorder
from integrations.botzone.models import DealRequest, GlobalState, PlayRequest
from integrations.botzone.play_adapter import NoTributeRuleBasedHandler, project_decision
from integrations.botzone.protocol import parse_stage_request
from integrations.botzone.session import DecisionTracePayload, HandlerContext, HandlerResult, PlayEffect, SessionRecord, SessionStorageError, SessionStore, decision_trace_payload


_BINDING_A = "0123456789abcdef0123456789abcdef"
_BINDING_B = "fedcba9876543210fedcba9876543210"


def _global(*, play: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {"level": "2", "tribute": 0, "first": None, "last": None}
    if play:
        payload.update({"resist": False, "tribute_cards": {}, "return_cards": {}})
    return payload


def _stage(stage: dict[str, object], match: str = "unit-a") -> bytes:
    return (f"1 0\n{match}\n" + json.dumps(stage, separators=(",", ":"))).encode()


def _deal(match: str = "unit-a") -> bytes:
    return _stage({"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}, match)


def _play(match: str = "unit-a") -> bytes:
    return _stage(
        {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global(play=True)},
        match,
    )


def _context() -> HandlerContext:
    global_state = GlobalState("2", 0, None, None, False)
    return HandlerContext(
        match_key="unit-a",
        request_digest="digest",
        request=PlayRequest((), (), -1, global_state),
        local_player_id=0,
        own_hand=tuple(range(27)),
        history=(),
        latest_window=(),
        global_state=global_state,
        finished=False,
    )


class _Transport:
    def __init__(self, items: list[bytes | Exception]) -> None:
        self.items = items
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _trace(selected_action_id: int = 2, *, source: str = "rule_primary") -> DecisionTracePayload:
    actions = [
        {
            "action_id": 1,
            "declared_pattern": "pass",
            "declared_cards": [],
            "carrier_cards": [],
            "wildcard_count": 0,
            "wildcard_info": [],
            "display_text": "pass",
        },
        {
            "action_id": 2,
            "declared_pattern": "single",
            "declared_cards": ["7"],
            "carrier_cards": ["H2"],
            "wildcard_count": 1,
            "wildcard_info": [{"carrier_card": "H2", "declared_as": "7"}],
            "display_text": "single:7",
        },
    ]
    selected = next(action for action in actions if action["action_id"] == selected_action_id)
    return decision_trace_payload(
        {
            "my_info": {"player_id": 1, "hand_cards": ["H2"], "hand_count": 1},
            "current_round": {"constraint": "single:6", "table_action": {"action_id": None}},
            "history": {"actions": []},
            "legal_actions": actions,
        },
        actions,
        selected_action_id,
        selected,
        source,
    )


def _handler(context: HandlerContext) -> HandlerResult:
    if isinstance(context.request, DealRequest):
        return HandlerResult(b"[]")
    return HandlerResult(b"[[0],[0]]", PlayEffect((0,), (0,)), _trace())


class _MutatingAgent:
    def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
        selected = legal_actions[0]["action_id"]
        observation["history"]["actions"].append({"mutated": True})  # type: ignore[index]
        observation["legal_actions"][0]["display_text"] = "mutated"  # type: ignore[index]
        del legal_actions[0]["declared_cards"]
        legal_actions[-1]["wildcard_info"].append({"mutated": True})
        legal_actions[-1]["display_text"] = "mutated"
        return selected


class _SourceAgent:
    def __init__(self, source: str, *, outcome: str | None = None) -> None:
        self.last_decision_source = source
        self.client = type("Client", (), {"last_outcome": outcome})()

    def select_action(self, _: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
        return legal_actions[0]["action_id"]


def _record(
    trace: tuple[DecisionTracePayload, ...],
    *,
    match_id: str = "unit-a",
    binding: object = _BINDING_A,
) -> SessionRecord:
    return SessionRecord(
        match_id=match_id,
        request_digest="digest",
        stage="play",
        global_state=GlobalState("2", 0, None, None, False),
        own_hand=tuple(range(27)),
        local_player_id=0,
        history=(),
        latest_window=(),
        pending_response=None,
        pending_effect=None,
        delivery_state="idle",
        handler_completed=True,
        cached_response=None,
        cached_response_digest=None,
        decision_trace_binding=binding,  # type: ignore[arg-type]
        confirmed_decision_traces=trace,
    )


class BotzoneDecisionTraceTests(unittest.TestCase):
    def test_trace_rejects_free_text_source_and_private_fields(self) -> None:
        with self.assertRaises(SessionStorageError):
            _trace(source="model reasoning text")
        with self.assertRaises(SessionStorageError):
            decision_trace_payload(
                {"my_info": {}, "prompt": "private"},
                [{"action_id": 1}],
                1,
                {"action_id": 1},
                "rule_primary",
            )

    def test_retired_model_rewrite_traces_remain_read_compatible(self) -> None:
        for source in ("teammate_control_block", "danger_opponent_block", "short_endgame_plan"):
            with self.subTest(source=source), TemporaryDirectory() as root:
                store = SessionStore(root)
                store.save(_record((_trace(source=source),)))
                restored = store.load("unit-a")
            assert restored is not None
            self.assertEqual(restored.confirmed_decision_traces[0].decision_source, source)

    def test_trace_requires_observation_legal_actions_to_match_canonical_actions(self) -> None:
        source = _trace()
        payload = source.to_json()
        actions = deepcopy(payload["legal_actions"])
        selected = deepcopy(payload["selected_action"])
        base_observation = deepcopy(payload["observation"])
        for label, observation in (
            ("missing", {key: value for key, value in base_observation.items() if key != "legal_actions"}),
            ("none", {**base_observation, "legal_actions": None}),
            ("non_list", {**base_observation, "legal_actions": {}}),
        ):
            with self.subTest(label=label), self.assertRaises(SessionStorageError):
                decision_trace_payload(observation, actions, 2, selected, "rule_primary")

        action_id_mismatch = deepcopy(base_observation)
        action_id_mismatch["legal_actions"][0]["action_id"] = 999
        reordered = deepcopy(base_observation)
        reordered["legal_actions"] = list(reversed(reordered["legal_actions"]))
        wildcard_mismatch = deepcopy(base_observation)
        wildcard_mismatch["legal_actions"][1]["wildcard_info"].append({"carrier_card": "H2", "declared_as": "8"})
        for label, observation in (
            ("action_id", action_id_mismatch),
            ("order", reordered),
            ("wildcard_info", wildcard_mismatch),
        ):
            with self.subTest(label=label), self.assertRaises(SessionStorageError):
                decision_trace_payload(observation, actions, 2, selected, "rule_primary")

        accepted = decision_trace_payload(deepcopy(base_observation), actions, 2, selected, "rule_primary")
        self.assertEqual(accepted.to_json()["observation"]["legal_actions"], accepted.to_json()["legal_actions"])

    def test_tampered_persisted_observation_actions_fail_to_reload(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            store.save(_record((_trace(),)))
            path = next(Path(root).glob("*.json"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["confirmed_decision_traces"][0]["observation"]["legal_actions"][1]["wildcard_info"].append(
                {"carrier_card": "H2", "declared_as": "8"}
            )
            path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(SessionStorageError):
                SessionStore(root).load("unit-a")

    def test_ack_only_real_handler_snapshot_retains_exact_public_fields(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            transport = _Transport([_deal(), _play(), b"0 0\n"])
            connector = MockConnector(
                SessionStore(Path(root) / "state", decision_trace_enabled=True),
                transport,
                NoTributeRuleBasedHandler(decision_trace_enabled=True),
                decision_trace_recorder=ConnectorDecisionTrace(path),
            )
            connector.cycle()
            connector.cycle()
            self.assertFalse(path.exists(), "pending local action is not evidence")
            connector.cycle()
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "botzone_acknowledged_local_decision_trace")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["scope"], "acknowledged_local_decisions_only")
        decision = payload["decisions"]
        self.assertEqual(len(decision), 1)
        item = decision[0]
        self.assertEqual(item["sequence"], 1)
        self.assertEqual(item["selected_action_id"], item["selected_action"]["action_id"])
        self.assertEqual(
            item["selected_action"],
            next(action for action in item["legal_actions"] if action["action_id"] == item["selected_action_id"]),
        )
        self.assertEqual(item["decision_source"], "rule_primary")
        self.assertIn("observation", item)
        self.assertEqual(item["selected_action"].get("wildcard_info"), next(
            action["wildcard_info"] for action in item["legal_actions"] if action["action_id"] == item["selected_action_id"]
        ))
        self.assertTrue(all(key not in json.dumps(payload).lower() for key in ("match_id", "run_token", "request_digest", "cookie", "prompt", "reasoning")))

    def test_timeout_restart_replay_and_finished_ack_do_not_duplicate(self) -> None:
        with TemporaryDirectory() as root:
            base = Path(root)
            path = base / "trace.json"
            first_transport = _Transport([_deal(), _play(), RuntimeError("offline")])
            first = MockConnector(
                SessionStore(base / "state", decision_trace_enabled=True), first_transport, _handler, decision_trace_recorder=ConnectorDecisionTrace(path)
            )
            first.cycle()
            first.cycle()
            self.assertFalse(path.exists())
            restarted_transport = _Transport([_play(), b"0 1\nunit-a 0 4 1 0 1 0"])
            restarted = MockConnector(
                SessionStore(base / "state", decision_trace_enabled=True), restarted_transport, _handler, decision_trace_recorder=ConnectorDecisionTrace(path)
            )
            restarted.cycle()  # acknowledges once, then direct-stage replay re-pends cached bytes only.
            restarted.cycle()  # duplicate cached delivery carries no pending trace, plus finished.
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["decisions"]), 1)
        self.assertEqual(payload["decisions"][0]["sequence"], 1)

    def test_writer_preserves_last_valid_file_on_atomic_failure_and_rejects_second_match(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            recorder = ConnectorDecisionTrace(path)
            one = _record((_trace(),))
            recorder.update(one)
            original = path.read_bytes()
            with patch("integrations.botzone.decision_trace.os.replace", side_effect=OSError("synthetic")):
                recorder.update(replace(one, confirmed_decision_traces=(_trace(), _trace(1))))
            self.assertTrue(recorder.failed)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(root).iterdir()), [path])

        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            recorder = ConnectorDecisionTrace(path)
            recorder.update(_record((_trace(),)))
            original = path.read_bytes()
            recorder.update(_record((_trace(),), match_id="unit-b", binding=_BINDING_B))
            self.assertTrue(recorder.failed)
            self.assertEqual(path.read_bytes(), original)

    def test_session_persists_pending_trace_until_acknowledgement(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root, decision_trace_enabled=True)
            deal, _ = store.prepare("unit-a", b"deal", __import__("integrations.botzone.protocol", fromlist=["parse_stage_request"]).parse_stage_request({"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}))
            store.complete_handler(store.reserve_handler(deal), HandlerResult(b"[]"))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            stage = __import__("integrations.botzone.protocol", fromlist=["parse_stage_request"]).parse_stage_request({"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global(play=True)})
            play, _ = store.prepare("unit-a", b"play", stage)
            store.complete_handler(store.reserve_handler(play), HandlerResult(b"play", PlayEffect((0,), (0,)), _trace()))
            restored = SessionStore(root)
            pending = restored.load("unit-a")
            assert pending is not None
            self.assertIsNotNone(pending.pending_decision_trace)
            deliveries = restored.pending_deliveries()
            restored.mark_inflight(deliveries)
            restored.acknowledge(deliveries)
            acknowledged = restored.load("unit-a")
            assert acknowledged is not None
            self.assertIsNone(acknowledged.pending_decision_trace)
            self.assertEqual(acknowledged.confirmed_decision_traces, (_trace(),))

    def test_restart_after_committed_ack_recovers_durable_trace_before_poll(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root, decision_trace_enabled=True)
            deal_stage = parse_stage_request({"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()})
            deal, _ = store.prepare("unit-a", b"deal", deal_stage)
            store.complete_handler(store.reserve_handler(deal), HandlerResult(b"[]"))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            play_stage = parse_stage_request({"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global(play=True)})
            play, _ = store.prepare("unit-a", b"play", play_stage)
            store.complete_handler(store.reserve_handler(play), HandlerResult(b"play", PlayEffect((0,), (0,)), _trace()))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            path = Path(root) / "trace.json"
            self.assertFalse(path.exists())
            recovered = MockConnector(
                SessionStore(root), _Transport([b"0 0\n"]), _handler, decision_trace_recorder=ConnectorDecisionTrace(path)
            )
            recovered.cycle()
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["decisions"]), 1)

    def test_recreated_recorder_accepts_only_same_persisted_binding_and_prefix(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            one = _record((_trace(),))
            ConnectorDecisionTrace(path).update(one)
            resumed = ConnectorDecisionTrace(path)
            resumed.update(replace(one, confirmed_decision_traces=(_trace(), _trace(1))))
            self.assertEqual(resumed.status, "ok")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["binding_id"], _BINDING_A)
            self.assertEqual([entry["sequence"] for entry in payload["decisions"]], [1, 2])

            original = path.read_bytes()
            different_match = ConnectorDecisionTrace(path)
            different_match.update(_record((_trace(), _trace(1)), match_id="unit-b", binding=_BINDING_B))
            self.assertEqual(different_match.status, "failed")
            self.assertEqual(path.read_bytes(), original)

    def test_malformed_or_mismatched_persisted_binding_fails_closed(self) -> None:
        with TemporaryDirectory() as root:
            base = Path(root)
            for label, mutation in (
                ("missing", lambda value: value.pop("binding_id")),
                ("none", lambda value: value.__setitem__("binding_id", None)),
                ("bool", lambda value: value.__setitem__("binding_id", True)),
                ("malformed", lambda value: value.__setitem__("binding_id", "not-a-binding")),
                ("mismatch", lambda value: value.__setitem__("binding_id", _BINDING_B)),
            ):
                with self.subTest(label=label):
                    path = base / f"{label}.json"
                    ConnectorDecisionTrace(path).update(_record((_trace(),)))
                    content = json.loads(path.read_text(encoding="utf-8"))
                    mutation(content)
                    path.write_text(json.dumps(content, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
                    original = path.read_bytes()
                    recovered = ConnectorDecisionTrace(path)
                    recovered.update(_record((_trace(),)))
                    self.assertEqual(recovered.status, "failed")
                    self.assertEqual(path.read_bytes(), original)

        with TemporaryDirectory() as root:
            recorder = ConnectorDecisionTrace(Path(root) / "trace.json")
            recorder.update(_record((_trace(),), binding=True))
            self.assertEqual(recorder.status, "failed")

    def test_agent_mutation_cannot_change_pre_call_canonical_trace(self) -> None:
        context = _context()
        projection = project_decision(context)
        expected_actions = deepcopy([dict(action) for action in projection.legal_actions])
        expected_observation = deepcopy(dict(projection.observation))
        expected_observation["legal_actions"] = deepcopy(expected_actions)

        result = NoTributeRuleBasedHandler(
            agent_factory=lambda _: _MutatingAgent(),
            decision_trace_enabled=True,
        )(context)
        assert result.decision_trace is not None
        trace = result.decision_trace.to_json()
        self.assertEqual(trace["observation"], expected_observation)
        self.assertEqual(trace["legal_actions"], expected_actions)
        self.assertEqual(trace["observation"]["legal_actions"], trace["legal_actions"])
        self.assertEqual(
            trace["selected_action"],
            next(action for action in expected_actions if action["action_id"] == trace["selected_action_id"]),
        )

    def test_pass_and_wildcard_fields_are_preserved_from_original_actions(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "trace.json"
            original = (_trace(1), _trace(2))
            ConnectorDecisionTrace(path).update(_record(original))
            decisions = json.loads(path.read_text(encoding="utf-8"))["decisions"]
        for trace, decision in zip(original, decisions, strict=True):
            expected = trace.to_json()
            self.assertEqual(decision["selected_action_id"], expected["selected_action_id"])
            self.assertEqual(decision["selected_action"], expected["selected_action"])
            self.assertEqual(decision["legal_actions"], expected["legal_actions"])
        self.assertEqual(decisions[0]["selected_action"]["declared_pattern"], "pass")
        wildcard = decisions[1]["selected_action"]
        self.assertEqual(wildcard["declared_cards"], ["7"])
        self.assertEqual(wildcard["carrier_cards"], ["H2"])
        self.assertEqual(wildcard["wildcard_info"], [{"carrier_card": "H2", "declared_as": "7"}])
        self.assertEqual(wildcard["display_text"], "single:7")

    def test_all_agent_modes_trace_the_existing_low_cardinality_source(self) -> None:
        cases = (
            ("rule", None, "rule_primary", None),
            ("deepseek", _SourceAgent("model", outcome="success"), "model", "success"),
            ("conditional_pressure_pass", _SourceAgent("conditional_rule_based"), "conditional_rule_based", None),
        )
        for mode, supplied_agent, source, outcome in cases:
            with self.subTest(mode=mode):
                recorder = AgentObservabilityRecorder()
                handler = NoTributeRuleBasedHandler(
                    agent_factory=(None if supplied_agent is None else lambda _, agent=supplied_agent: agent),
                    agent_mode=mode,
                    observability=recorder,
                    decision_trace_enabled=True,
                )
                result = handler(_context())
                assert result.decision_trace is not None
                trace = result.decision_trace.to_json()
                self.assertEqual(trace["decision_source"], source)
                self.assertEqual(
                    trace["selected_action"],
                    next(action for action in trace["legal_actions"] if action["action_id"] == trace["selected_action_id"]),
                )
                snapshot = recorder.snapshot(mode)
                self.assertEqual(snapshot.agent_decision_count, 1)
                self.assertEqual(dict(snapshot.decision_source_counts), {source: 1})
                self.assertEqual(snapshot.model_attempt_count, 0 if outcome is None else 1)
                self.assertEqual(dict(snapshot.model_outcome_counts), {} if outcome is None else {outcome: 1})


if __name__ == "__main__":
    unittest.main()
