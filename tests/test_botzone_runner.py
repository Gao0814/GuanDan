from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest
from integrations.botzone.runner import ForegroundRunner, build_foreground_runner
from integrations.botzone.runtime_config import RuntimeConfig, load_runtime_config
from integrations.botzone.session import HandlerResult, SessionStore


def _deal() -> bytes:
    payload = json.dumps(
        {"requests": [{"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}], "responses": []},
        separators=(",", ":"),
    )
    return f"1 0\nunit\n{payload}".encode()


class _Transport:
    def __init__(self, polls: list[bytes | Exception]) -> None:
        self.polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        next_poll = self.polls.pop(0)
        if isinstance(next_poll, BaseException):
            raise next_poll
        return next_poll


class BotzoneRunnerTests(unittest.TestCase):
    def test_failure_backoff_resets_after_success_and_stops_at_cycle_limit(self) -> None:
        with TemporaryDirectory() as root:
            transport = _Transport([RuntimeError("offline"), b"0 0\n", RuntimeError("offline"), b"0 0\n"])
            connector = MockConnector(SessionStore(root), transport, lambda _: HandlerResult(b"[]"))
            sleeps: list[float] = []
            clock_calls: list[int] = []
            summary = ForegroundRunner(
                connector,
                max_consecutive_failures=3,
                backoff_seconds=2,
                sleep=sleeps.append,
                clock=lambda: clock_calls.append(1) or 100,
            ).run(max_cycles=4)
        self.assertEqual(summary.stopped, "cycle_limit_unfinished")
        self.assertEqual((summary.cycles, summary.successful_cycles, summary.transport_failures), (4, 2, 2))
        self.assertEqual(sleeps, [2, 2])
        self.assertGreaterEqual(len(clock_calls), 4)

    def test_failure_limit_and_keyboard_interrupt_are_clean(self) -> None:
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), _Transport([RuntimeError("offline"), RuntimeError("offline")]), lambda _: HandlerResult(b"[]"))
            summary = ForegroundRunner(connector, max_consecutive_failures=2, backoff_seconds=1, sleep=lambda _: None).run(max_cycles=3)
            self.assertEqual(summary.stopped, "failure_limit")
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), _Transport([KeyboardInterrupt()]), lambda _: HandlerResult(b"[]"))
            summary = ForegroundRunner(connector, max_consecutive_failures=2, backoff_seconds=1, sleep=lambda _: None).run(max_cycles=1)
            self.assertEqual(summary.stopped, "interrupted")

    def test_fake_gateway_restart_resends_pending_and_acknowledges_once(self) -> None:
        with TemporaryDirectory() as root:
            config = load_runtime_config(local_ai_url="https://private.invalid/secret", state_directory=root)
            transport = _Transport([_deal(), RuntimeError("offline"), b"0 0\n"])
            first = build_foreground_runner(config, transport, sleep=lambda _: None)
            first.run(max_cycles=2)
            before = SessionStore(root).load("unit")
            assert before is not None
            self.assertEqual(before.pending_response, b'{"response":[]}')
            build_foreground_runner(config, transport, sleep=lambda _: None).run(max_cycles=1)
            after = SessionStore(root).load("unit")
            assert after is not None
            self.assertIsNone(after.pending_response)
            self.assertEqual(len(transport.headers[2]), 1)

    def test_runtime_config_object_is_sufficient_for_injected_transport(self) -> None:
        with TemporaryDirectory() as root:
            config = RuntimeConfig("https://private.invalid/secret", state_directory=__import__("pathlib").Path(root))
            runner = build_foreground_runner(config, _Transport([b"0 0\n"]), sleep=lambda _: None)
            self.assertEqual(runner.run(max_cycles=1).cycles, 1)


if __name__ == "__main__":
    unittest.main()
