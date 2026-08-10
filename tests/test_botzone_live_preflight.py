from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest
from integrations.botzone.runner import ForegroundRunner, exit_code_for, write_audit
from integrations.botzone.runtime_config import RuntimeConfig, RuntimeConfigError, preflight_state_directory
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStore


class _Gateway:
    def __init__(self, polls: list[bytes]) -> None:
        self.polls = polls
        self.calls = 0
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.calls += 1
        self.headers.append(dict(headers))
        return self.polls.pop(0)


class BotzoneLivePreflightTests(unittest.TestCase):
    def test_finished_target_stops_before_another_poll_and_aggregates_counts(self) -> None:
        deal = json.dumps(
            {"requests": [{"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}], "responses": []},
            separators=(",", ":"),
        )
        play = json.dumps(
            {
                "requests": [
                    {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}},
                    {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False, "tribute_cards": {}, "return_cards": {}}},
                ],
                "responses": [[]],
            },
            separators=(",", ":"),
        )
        with TemporaryDirectory() as root:
            gateway = _Gateway([f"1 0\nunit\n{deal}".encode(), f"1 0\nunit\n{play}".encode(), b"0 1\nunit 0 4 1 2 3 4", b"0 0\n"])

            def handler(context: HandlerContext) -> HandlerResult:
                if isinstance(context.request, DealRequest):
                    return HandlerResult(b"[]")
                return HandlerResult(b"[[0],[0]]", PlayEffect((0,)))

            runner = ForegroundRunner(
                MockConnector(SessionStore(root), gateway, handler),
                max_consecutive_failures=2,
                backoff_seconds=1,
                sleep=lambda _: None,
            )
            summary = runner.run(max_cycles=4, max_wall_seconds=60, stop_after_finished=1)
            self.assertEqual(summary.stopped, "finished_target")
            self.assertEqual(
                (summary.cycles, summary.headers_sent, summary.requests_seen, summary.responses_prepared, summary.finished_seen, summary.finished_qualified),
                (3, 2, 2, 2, 1, 1),
            )
            self.assertEqual(gateway.calls, 3)
            self.assertEqual(exit_code_for(summary), 0)
            self.assertIsNone(SessionStore(root).load("unit"))

    def test_protocol_diagnostics_fail_closed_with_stable_exit_class(self) -> None:
        with TemporaryDirectory() as root:
            gateway = _Gateway([b'1 0\nunit\n{"requests":[{"stage":"deal","deliver":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26],"your_id":0,"global":{"level":"2","tribute":0,"first":null,"last":null}},{"stage":"tribute"}],"responses":[[]]}'])
            runner = ForegroundRunner(
                MockConnector(SessionStore(root), gateway, lambda _: HandlerResult(b"[]")),
                max_consecutive_failures=2,
                backoff_seconds=1,
                sleep=lambda _: None,
            )
            summary = runner.run(max_cycles=2, max_wall_seconds=60, stop_after_finished=1)
            self.assertEqual(summary.stopped, "unsupported_stage")
            self.assertEqual(exit_code_for(summary), 5)
            self.assertEqual(gateway.calls, 1)

    def test_preflight_uses_no_gateway_and_rejects_relative_or_repository_paths(self) -> None:
        with TemporaryDirectory() as root:
            preflight_state_directory(RuntimeConfig("https://private.invalid/secret", Path(root)))
            self.assertEqual(list(Path(root).iterdir()), [])
        with self.assertRaisesRegex(RuntimeConfigError, "invalid_state_directory"):
            preflight_state_directory(RuntimeConfig("https://private.invalid/secret", Path("relative")))
        project_path = Path(__file__).parents[1] / "logs" / "botzone-state"
        with self.assertRaisesRegex(RuntimeConfigError, "invalid_state_directory"):
            preflight_state_directory(RuntimeConfig("https://private.invalid/secret", project_path))

    def test_audit_is_deterministic_and_has_only_aggregate_fields(self) -> None:
        with TemporaryDirectory() as root:
            summary = ForegroundRunner(
                MockConnector(SessionStore(root), _Gateway([b"0 0\n"]), lambda _: HandlerResult(b"[]")),
                max_consecutive_failures=2,
                backoff_seconds=1,
                sleep=lambda _: None,
            ).run(max_cycles=1, max_wall_seconds=60, stop_after_finished=1)
            audit = Path(root).parent / "smoke-audit.json"
            write_audit(audit, summary, exit_code_for(summary))
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "botzone_local_smoke_audit")
            self.assertEqual(payload["version"], 2)
            self.assertEqual(payload["finished_qualified"], 0)
            self.assertNotIn("url", json.dumps(payload).lower())
            self.assertNotIn("match", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
