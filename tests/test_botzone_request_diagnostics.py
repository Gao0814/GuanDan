from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.connector import MockConnector
from integrations.botzone.poll import parse_poll
from integrations.botzone.runner import ForegroundRunner
from integrations.botzone.session import HandlerResult, SessionStore


def _global(*, play: bool = False, level: str = "2") -> dict[str, object]:
    result: dict[str, object] = {"level": level, "tribute": 0, "first": None, "last": None}
    if play:
        result.update({"resist": False, "tribute_cards": {}, "return_cards": {}})
    return result


def _deal() -> dict[str, object]:
    return {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}


def _play(history: list[object] | None = None, *, level: str = "2") -> dict[str, object]:
    events = [] if history is None else history
    return {"stage": "play", "history": ([[]] * (4 - len(events))) + events, "done": [], "pass_on": -1, "global": _global(play=True, level=level)}


def _poll_line(value: object) -> bytes:
    text = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    return ("1 0\ncase\n" + text).encode("utf-8")


def _diagnostic(value: object) -> str | None:
    return parse_poll(_poll_line(value)).requests[0].diagnostic


class _Transport:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        return self._payload


class BotzoneRequestDiagnosticTests(unittest.TestCase):
    def test_json_and_envelope_shape_categories_are_fixed(self) -> None:
        self.assertEqual(_diagnostic("{not-json"), "request_json_invalid")
        for envelope in (
            [],
            {"requests": [], "responses": []},
            {"requests": [_deal()], "responses": [[]]},
            {"requests": [_deal()], "responses": [], "extra": 1},
            {"requests": {}, "responses": []},
        ):
            with self.subTest(envelope_type=type(envelope).__name__):
                self.assertEqual(_diagnostic(envelope), "envelope_shape_invalid")

    def test_inner_and_historical_categories_are_fixed(self) -> None:
        malformed_deal = _deal()
        malformed_deal["deliver"] = list(range(26))
        self.assertEqual(_diagnostic({"requests": [malformed_deal], "responses": []}), "inner_request_invalid")
        malformed_plays: list[dict[str, object]] = []
        malformed_play = _play()
        malformed_play["global"]["tribute_cards"] = {"x": []}
        malformed_plays.append(malformed_play)
        malformed_history = _play()
        malformed_history["history"] = [{}]
        malformed_plays.append(malformed_history)
        malformed_done = _play()
        malformed_done["done"] = [True]
        malformed_plays.append(malformed_done)
        malformed_pass_on = _play()
        malformed_pass_on["pass_on"] = True
        malformed_plays.append(malformed_pass_on)
        malformed_global = _play()
        malformed_global["global"]["resist"] = True
        malformed_plays.append(malformed_global)
        for malformed_play in malformed_plays:
            with self.subTest(play=malformed_play):
                self.assertEqual(
                    _diagnostic({"requests": [_deal(), malformed_play], "responses": [[]]}),
                    "inner_request_invalid",
                )
        for response in ({}, [[99], [99]], [[4], [52]]):
            with self.subTest(response_type=type(response).__name__):
                self.assertEqual(
                    _diagnostic({"requests": [_deal(), _play(), _play()], "responses": [[], response]}),
                    "historical_response_invalid",
                )

    def test_replay_categories_are_fixed(self) -> None:
        self.assertEqual(_diagnostic({"requests": [_play()], "responses": []}), "replay_history_invalid")
        self.assertEqual(_diagnostic({"requests": [_deal(), _deal()], "responses": [[]]}), "replay_history_invalid")
        self.assertEqual(_diagnostic({"requests": [_deal(), _play(level="3")], "responses": [[]]}), "replay_history_invalid")
        first = {"player": 1, "response": [[], []]}
        second = {"player": 2, "response": [[0], [0]]}
        self.assertEqual(
            _diagnostic({"requests": [_deal(), _play([first]), _play([second])], "responses": [[], [[], []]]}),
            "replay_history_invalid",
        )

    def test_unknown_exception_has_no_message_leak_and_connector_stops(self) -> None:
        with patch("integrations.botzone.poll.parse_bot_envelope", side_effect=RuntimeError("private_failure_text")):
            self.assertEqual(_diagnostic({"requests": [_deal()], "responses": []}), "malformed_request")
            with TemporaryDirectory() as root:
                transport = _Transport(_poll_line({"requests": [_deal()], "responses": []}))
                calls: list[object] = []
                cycle = MockConnector(
                    SessionStore(root), transport, lambda context: calls.append(context) or HandlerResult(b"[]")
                ).cycle()
                self.assertEqual(cycle.diagnostics, (("malformed_request", 1),))
                self.assertEqual((cycle.responses_prepared, cycle.headers_sent), (0, 0))
                self.assertEqual(calls, [])
        payload = _poll_line({"requests": [], "responses": []})
        with TemporaryDirectory() as root:
            transport = _Transport(payload)
            calls: list[object] = []
            connector = MockConnector(SessionStore(root), transport, lambda context: calls.append(context) or HandlerResult(b"[]"))
            cycle = connector.cycle()
            self.assertEqual(cycle.diagnostics, (("envelope_shape_invalid", 1),))
            self.assertEqual((cycle.responses_prepared, cycle.headers_sent), (0, 0))
            self.assertEqual(calls, [])
        with TemporaryDirectory() as root:
            runner = ForegroundRunner(
                MockConnector(SessionStore(root), _Transport(payload), lambda _: HandlerResult(b"[]")),
                max_consecutive_failures=1,
                backoff_seconds=1,
                sleep=lambda _: None,
            )
            self.assertEqual(runner.run(max_cycles=2).stopped, "diagnostic_failure")


if __name__ == "__main__":
    unittest.main()
