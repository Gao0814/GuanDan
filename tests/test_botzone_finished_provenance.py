from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest
from integrations.botzone.poll import FinishedRow
from integrations.botzone.runner import ForegroundRunner, RunnerSummary, exit_code_for, write_audit
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStorageError, SessionStore


def _deal() -> dict[str, object]:
    return {
        "stage": "deal",
        "deliver": list(range(27)),
        "your_id": 0,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _play() -> dict[str, object]:
    return {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False, "tribute_cards": {}, "return_cards": {}},
    }


def _envelope(*, play: bool) -> str:
    requests: list[dict[str, object]] = [_deal()]
    responses: list[object] = []
    if play:
        requests.append(_play())
        responses.append([])
    return json.dumps({"requests": requests, "responses": responses}, separators=(",", ":"))


def _finished(*, player_count: int = 4) -> bytes:
    scores = "" if player_count == 0 else " " + " ".join(str(index) for index in range(player_count))
    return f"0 1\nunit 0 {player_count}{scores}".encode("utf-8")


class _Transport:
    def __init__(self, polls: list[bytes | Exception]) -> None:
        self._polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        item = self._polls.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _handler(context: HandlerContext) -> HandlerResult:
    if isinstance(context.request, DealRequest):
        return HandlerResult(b"[]")
    return HandlerResult(b"[[0],[0]]", PlayEffect((0,)))


class _FailingFinishStore(SessionStore):
    def finish(self, row: FinishedRow) -> bool:
        raise SessionStorageError("atomic_write_failed")


class BotzoneFinishedProvenanceTests(unittest.TestCase):
    def test_unknown_aborted_and_non_four_finished_are_raw_only(self) -> None:
        with TemporaryDirectory() as root:
            for payload in (
                b"0 1\nunknown 0 4 0 1 2 3",
                _finished(player_count=0),
                _finished(player_count=3),
            ):
                with self.subTest(payload_kind=payload.split(b"\n", 1)[1].split(b" ")[2]):
                    cycle = MockConnector(SessionStore(root), _Transport([payload]), _handler).cycle()
                    self.assertEqual((cycle.finished_seen, cycle.finished_qualified), (1, 0))

    def test_deal_only_and_unsent_or_failed_play_are_not_qualified(self) -> None:
        with TemporaryDirectory() as root:
            deal_only = MockConnector(
                SessionStore(root),
                _Transport([(f"1 0\nunit\n{_envelope(play=False)}").encode(), _finished()]),
                _handler,
            )
            deal_only.cycle()
            cycle = deal_only.cycle()
            self.assertEqual((cycle.headers_sent, cycle.finished_seen, cycle.finished_qualified), (1, 1, 0))
        with TemporaryDirectory() as root:
            pending = MockConnector(
                SessionStore(root),
                _Transport([(f"1 0\nunit\n{_envelope(play=True)}").encode(), RuntimeError("offline")]),
                _handler,
            )
            self.assertEqual(pending.cycle().headers_sent, 0)
            failed = pending.cycle()
            self.assertEqual((failed.headers_sent, failed.finished_qualified, failed.diagnostics), (1, 0, (("transport_failure", 1),)))

    def test_only_same_instance_acked_play_and_cleanup_qualify_once(self) -> None:
        with TemporaryDirectory() as root:
            first = (f"1 0\nunit\n{_envelope(play=True)}").encode()
            mixed_finished = b"0 2\nstale 0 4 0 1 2 3\nunit 0 4 0 1 2 3"
            connector = MockConnector(SessionStore(root), _Transport([first, mixed_finished, _finished()]), _handler)
            connector.cycle()
            qualified = connector.cycle()
            duplicate = connector.cycle()
            self.assertEqual((qualified.finished_seen, qualified.finished_qualified), (2, 1))
            self.assertEqual((duplicate.finished_seen, duplicate.finished_qualified), (1, 0))
            self.assertIsNone(SessionStore(root).load("unit"))

    def test_different_match_and_historical_tombstone_cannot_qualify(self) -> None:
        with TemporaryDirectory() as root:
            first = (f"1 0\nunit\n{_envelope(play=True)}").encode()
            other_finished = b"0 1\nother 0 4 0 1 2 3"
            connector = MockConnector(SessionStore(root), _Transport([first, other_finished]), _handler)
            connector.cycle()
            mixed = connector.cycle()
            self.assertEqual((mixed.headers_sent, mixed.finished_seen, mixed.finished_qualified), (1, 1, 0))
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            MockConnector(store, _Transport([(f"1 0\nunit\n{_envelope(play=False)}").encode()]), _handler).cycle()
            self.assertTrue(store.finish(FinishedRow("unit", 0, 4, (0, 1, 2, 3))))
            historical = MockConnector(store, _Transport([_finished()]), _handler).cycle()
            self.assertEqual((historical.finished_seen, historical.finished_qualified), (1, 0))

    def test_cleanup_failure_stops_runner_before_success(self) -> None:
        with TemporaryDirectory() as root:
            connector = MockConnector(
                _FailingFinishStore(root),
                _Transport([(f"1 0\nunit\n{_envelope(play=True)}").encode(), _finished()]),
                _handler,
            )
            connector.cycle()
            summary = ForegroundRunner(connector, max_consecutive_failures=2, backoff_seconds=1, sleep=lambda _: None).run(
                max_cycles=1, max_wall_seconds=60, stop_after_finished=1
            )
            self.assertEqual((summary.stopped, summary.finished_qualified, exit_code_for(summary)), ("diagnostic_failure", 0, 5))

    def test_runner_and_audit_use_qualified_finished_for_target(self) -> None:
        with TemporaryDirectory() as root:
            summary = ForegroundRunner(
                MockConnector(SessionStore(root), _Transport([b"0 1\nunknown 0 4 0 1 2 3"]), _handler),
                max_consecutive_failures=2,
                backoff_seconds=1,
                sleep=lambda _: None,
            ).run(max_cycles=1, max_wall_seconds=60, stop_after_finished=1)
            self.assertEqual((summary.stopped, summary.finished_seen, summary.finished_qualified, exit_code_for(summary)), ("cycle_limit_unfinished", 1, 0, 6))
            audit = __import__("pathlib").Path(root).parent / "finished-provenance-audit.json"
            write_audit(audit, summary, exit_code_for(summary))
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual((payload["version"], payload["finished_seen"], payload["finished_qualified"]), (2, 1, 0))
            self.assertNotIn("match", json.dumps(payload).lower())
            self.assertNotIn("history", json.dumps(payload).lower())
        impossible = RunnerSummary(1, 1, 0, 0, 0, 0, 1, 0, "finished_target", ())
        self.assertEqual(exit_code_for(impossible), 6)


if __name__ == "__main__":
    unittest.main()
