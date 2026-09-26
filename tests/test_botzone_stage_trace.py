from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from integrations.botzone import __main__ as botzone_main
from integrations.botzone.agent_runtime import _StrictDeepSeekClient
from integrations.botzone.connector import MockConnector
from integrations.botzone.http_transport import TransportError
from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.runner import ForegroundRunner
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStore
from integrations.botzone.stage_trace import (
    MAX_ELAPSED_MILLISECONDS,
    STAGE_OUTCOMES,
    STAGE_TRACE_PREFIX,
    StageTrace,
    record_stage,
)


def _direct_poll(request: dict[str, object] | None, *, compact: bool = True) -> bytes:
    if request is None:
        return b"0 0\n"
    separators = (",", ":") if compact else (", ", ": ")
    body = json.dumps(request, separators=separators)
    return f"1 0\nsynthetic-match\n{body}".encode("utf-8")


def _deal_request() -> dict[str, object]:
    return {
        "stage": "deal",
        "deliver": list(range(27)),
        "your_id": 0,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _play_request() -> dict[str, object]:
    return {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": {
            "level": "2",
            "tribute": 0,
            "first": None,
            "last": None,
            "resist": False,
            "tribute_cards": {},
            "return_cards": {},
        },
    }


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _BadSink:
    def emit(self, _stage: str, _outcome: str) -> None:
        raise OSError("synthetic sink failure")


class _PollTransport:
    def __init__(self, polls: list[bytes | BaseException]) -> None:
        self.polls = list(polls)
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))  # type: ignore[arg-type]
        result = self.polls.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _SyntheticDeepSeek:
    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        actions = kwargs.get("legal_actions")
        assert isinstance(actions, list) and actions
        return DeepSeekSuggestion(action_id=actions[0]["action_id"], reasoning="private synthetic text")  # type: ignore[index]


class BotzoneStageTraceTests(unittest.TestCase):
    def test_stage_trace_is_fixed_low_sensitivity_flushed_and_bounded(self) -> None:
        clock = _Clock()

        class _CountingStream(io.StringIO):
            flush_calls = 0

            def flush(self) -> None:
                self.flush_calls += 1
                super().flush()

        stream = _CountingStream()
        trace = StageTrace(stream, clock=clock)
        trace.emit("poll_enter", "started")
        clock.now = 1.25
        trace.emit("model_complete", "success")
        trace.emit("model_complete", "private synthetic text")
        trace.emit("unregistered", "started")
        events = [json.loads(line[len(STAGE_TRACE_PREFIX):]) for line in stream.getvalue().splitlines()]
        self.assertEqual(stream.flush_calls, 2)
        self.assertEqual([event["seq"] for event in events], [1, 2])
        self.assertEqual([event["elapsed_ms"] for event in events], [0, 1250])
        self.assertEqual(set(events[0]), {"stage", "seq", "elapsed_ms", "outcome"})
        self.assertEqual(events[1]["outcome"], "success")
        self.assertTrue(all(event["stage"] in STAGE_OUTCOMES for event in events))
        self.assertNotIn("private synthetic text", stream.getvalue())

        bounded = io.StringIO()
        clock_values = iter((0.0, MAX_ELAPSED_MILLISECONDS / 1000 + 1))
        bounded_trace = StageTrace(bounded, clock=lambda: next(clock_values))
        bounded_trace.emit("connector_start", "started")
        event = json.loads(bounded.getvalue()[len(STAGE_TRACE_PREFIX):])
        self.assertEqual(event["elapsed_ms"], MAX_ELAPSED_MILLISECONDS)
        record_stage(_BadSink(), "poll_enter", "started")

    def test_five_acknowledged_model_decisions_leave_an_idle_poll_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            polls = [_direct_poll(_deal_request())]
            polls.extend(_direct_poll(_play_request(), compact=index % 2 == 0) for index in range(5))
            polls.append(_direct_poll(None))
            transport = _PollTransport(polls)
            clock = _Clock()
            stream = io.StringIO()
            trace = StageTrace(stream, clock=clock)
            client = _StrictDeepSeekClient(_SyntheticDeepSeek(), stage_trace=trace)
            play_calls = 0

            def handler(context: HandlerContext) -> HandlerResult:
                nonlocal play_calls
                if isinstance(context.request, DealRequest):
                    return HandlerResult(b"[]")
                assert isinstance(context.request, PlayRequest)
                play_calls += 1
                physical_id = context.own_hand[0]
                suggestion = client.suggest_action_id(
                    observation={},
                    legal_actions=[{"action_id": physical_id}],
                )
                self.assertEqual(suggestion.action_id, physical_id)
                action = (physical_id,)
                return HandlerResult(
                    json.dumps([list(action), list(action)]).encode("utf-8"),
                    PlayEffect(action, action),
                )

            connector = MockConnector(SessionStore(Path(root) / "state"), transport, handler, stage_trace=trace)
            runner = ForegroundRunner(
                connector,
                max_consecutive_failures=2,
                backoff_seconds=0,
                sleep=lambda _seconds: None,
                stage_trace=trace,
            )
            summary = runner.run(max_cycles=7, max_wall_seconds=60)

            self.assertEqual(summary.cycles, 7)
            self.assertEqual(summary.requests_seen, 6)  # one deal plus five plays
            self.assertEqual(summary.responses_prepared, 6)
            self.assertEqual(summary.stopped, "cycle_limit_unfinished")
            self.assertEqual(play_calls, 5)
            self.assertEqual(len(transport.headers), 7)
            events = [json.loads(line[len(STAGE_TRACE_PREFIX):]) for line in stream.getvalue().splitlines()]
            self.assertTrue(events)
            self.assertEqual([event["seq"] for event in events], list(range(1, len(events) + 1)))
            self.assertEqual([event["elapsed_ms"] for event in events], sorted(event["elapsed_ms"] for event in events))
            counts: dict[tuple[str, str], int] = {}
            for event in events:
                key = (event["stage"], event["outcome"])
                counts[key] = counts.get(key, 0) + 1
                self.assertEqual(set(event), {"stage", "seq", "elapsed_ms", "outcome"})
            self.assertEqual(counts[("play_request_arrived", "received")], 5)
            self.assertEqual(counts[("model_enter", "started")], 5)
            self.assertEqual(counts[("model_complete", "success")], 5)
            self.assertEqual(counts[("response_acknowledged", "confirmed")], 6)
            self.assertEqual(counts[("poll_returned", "response_received")], 7)
            self.assertEqual(counts[("poll_exit", "idle")], 1)
            self.assertEqual(counts[("runner_exit", "cycle_limit_unfinished")], 1)
            first_ack = next(index for index, event in enumerate(events) if event["stage"] == "response_acknowledged")
            self.assertEqual(events[first_ack - 1]["stage"], "poll_returned")
            self.assertNotIn("synthetic-match", stream.getvalue())
            self.assertNotIn("private synthetic text", stream.getvalue())
            self.assertNotIn("action_id", stream.getvalue())

    def test_stage_sink_failure_does_not_change_ack_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            transport = _PollTransport(
                [_direct_poll(_deal_request()), _direct_poll(_play_request()), _direct_poll(None)]
            )
            calls = 0

            def handler(context: HandlerContext) -> HandlerResult:
                nonlocal calls
                calls += 1
                if isinstance(context.request, DealRequest):
                    return HandlerResult(b"[]")
                physical_id = context.own_hand[0]
                action = (physical_id,)
                return HandlerResult(
                    json.dumps([list(action), list(action)]).encode("utf-8"),
                    PlayEffect(action, action),
                )

            store = SessionStore(Path(root) / "state")
            connector = MockConnector(store, transport, handler, stage_trace=_BadSink())
            connector.cycle()
            connector.cycle()
            connector.cycle()
            records = store.active_records()
            self.assertEqual(calls, 2)
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0].pending_response)
            self.assertEqual(records[0].own_hand, tuple(range(1, 27)))

    def test_failed_poll_leaves_header_response_waiting_for_ack(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            stream = io.StringIO()
            trace = StageTrace(stream)
            transport = _PollTransport([_direct_poll(_deal_request()), TransportError("timeout")])
            store = SessionStore(Path(root) / "state")
            connector = MockConnector(
                store,
                transport,
                lambda _context: HandlerResult(b"[]"),
                stage_trace=trace,
            )
            first = connector.cycle()
            second = connector.cycle()
            record = store.active_records()[0]
            events = [json.loads(line[len(STAGE_TRACE_PREFIX):]) for line in stream.getvalue().splitlines()]
            self.assertEqual(first.responses_prepared, 1)
            self.assertEqual(second.transport_timeouts, 1)
            self.assertEqual(record.delivery_state, "pending")
            self.assertEqual(record.pending_response, b"[]")
            self.assertIn(("response_header_emitted", "pending"), [(event["stage"], event["outcome"]) for event in events])
            self.assertIn(("response_waiting_ack", "pending"), [(event["stage"], event["outcome"]) for event in events])
            self.assertIn(("poll_exit", "timeout"), [(event["stage"], event["outcome"]) for event in events])
            self.assertNotIn("response_acknowledged", [event["stage"] for event in events])
            self.assertEqual([event["stage"] for event in events].count("poll_returned"), 1)

    def test_finished_poll_emits_finished_category(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            stream = io.StringIO()
            trace = StageTrace(stream)
            transport = _PollTransport([b"0 1\nsynthetic-match 0 0\n"])
            connector = MockConnector(
                SessionStore(Path(root) / "state"),
                transport,
                lambda _context: HandlerResult(None),
                stage_trace=trace,
            )
            cycle = connector.cycle()
            events = [json.loads(line[len(STAGE_TRACE_PREFIX):]) for line in stream.getvalue().splitlines()]
            self.assertEqual(cycle.finished_seen, 1)
            self.assertEqual((events[-2]["stage"], events[-2]["outcome"]), ("poll_exit", "finished"))
            self.assertEqual((events[-1]["stage"], events[-1]["outcome"]), ("finished", "aborted"))

    def test_slow_segmented_sse_reports_whole_call_duration_beyond_per_read_timeout(self) -> None:
        clock = _Clock()
        stream = io.StringIO()
        trace = StageTrace(stream, clock=clock)
        timeouts: list[float] = []

        class _SlowLines:
            def __init__(self) -> None:
                self.lines = [
                    b'data: {"choices":[{"delta":{"reasoning_content":"x"}}]}\n',
                    b'data: {"choices":[{"delta":{"content":"{\\"action_id\\":1}"}}]}\n',
                    b"data: [DONE]\n",
                ]

            def __iter__(self):
                return self

            def __next__(self) -> bytes:
                if not self.lines:
                    raise StopIteration
                clock.now += 12.0
                return self.lines.pop(0)

            def close(self) -> None:
                pass

        def fake_transport(_request: object, timeout: float) -> _SlowLines:
            timeouts.append(timeout)
            return _SlowLines()

        client = DeepSeekClient(
            "synthetic-key",
            "https://synthetic.invalid",
            "synthetic-model",
            timeout_seconds=30,
            max_retries=0,
            transport=fake_transport,
        )
        strict_client = _StrictDeepSeekClient(client, stage_trace=trace)
        suggestion = strict_client.suggest_action_id(
            observation={"synthetic": True},
            legal_actions=[{"action_id": 1}],
        )
        events = [json.loads(line[len(STAGE_TRACE_PREFIX):]) for line in stream.getvalue().splitlines()]
        self.assertEqual(suggestion.action_id, 1)
        self.assertEqual(strict_client.last_outcome, "success")
        self.assertEqual(timeouts, [30])
        self.assertEqual(events[0]["stage"], "model_enter")
        self.assertEqual(events[-1]["stage"], "model_complete")
        self.assertEqual(events[-1]["elapsed_ms"], 36_000)

    def test_cli_trace_is_opt_in_and_never_emitted_for_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            config = SimpleNamespace(
                local_ai_url="https://synthetic.invalid/poll",
                timeout_seconds=30,
                max_response_bytes=1024,
                state_directory=Path(root),
            )

            class _Runner:
                run_token = None

                def run(self, **_kwargs: object) -> object:
                    return SimpleNamespace(
                        cycles=1,
                        finished_seen=0,
                        stopped="cycle_limit_unfinished",
                        history_status="disabled",
                        decision_trace_status="disabled",
                    )

            with (
                patch.object(botzone_main, "load_runtime_config", return_value=config),
                patch.object(botzone_main, "preflight_state_directory"),
                patch.object(botzone_main, "prepare_agent_factory", return_value=None),
                patch.object(botzone_main, "build_foreground_runner", return_value=_Runner()),
                patch.object(botzone_main, "exit_code_for", return_value=6),
            ):
                default_output = io.StringIO()
                with redirect_stdout(default_output):
                    self.assertEqual(botzone_main.main(["--agent", "rule"], environ={}), 6)
                self.assertNotIn(STAGE_TRACE_PREFIX, default_output.getvalue())

                enabled_output = io.StringIO()
                with redirect_stdout(enabled_output):
                    self.assertEqual(botzone_main.main(["--agent", "rule", "--stage-trace"], environ={}), 6)
                self.assertIn(STAGE_TRACE_PREFIX, enabled_output.getvalue())

                preflight_output = io.StringIO()
                with redirect_stdout(preflight_output):
                    self.assertEqual(
                        botzone_main.main(
                            ["--agent", "rule", "--stage-trace", "--preflight-only"],
                            environ={},
                        ),
                        0,
                    )
                self.assertEqual(preflight_output.getvalue(), "preflight_ready\n")


if __name__ == "__main__":
    unittest.main()
