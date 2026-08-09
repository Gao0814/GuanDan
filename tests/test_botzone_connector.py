from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStore


def _deal(player: int = 0) -> str:
    return json.dumps(
        {
            "stage": "deal",
            "deliver": list(range(player * 27, (player + 1) * 27)),
            "your_id": player,
            "global": {"level": "2", "tribute": 0, "first": None, "last": None},
        },
        separators=(",", ":"),
    )


def _play() -> str:
    return json.dumps(
        {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False}},
        separators=(",", ":"),
    )


class _FakeTransport:
    def __init__(self, responses: list[bytes | Exception]) -> None:
        self.responses = responses
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class BotzoneConnectorTests(unittest.TestCase):
    def test_pending_response_survives_transport_failure_then_acknowledges(self) -> None:
        with TemporaryDirectory() as root:
            transport = _FakeTransport([(f"1 0\nunit-a\n{_deal()}").encode(), RuntimeError("offline"), b"0 0\n"])
            calls: list[object] = []
            connector = MockConnector(SessionStore(root), transport, lambda context: calls.append(context) or HandlerResult(b'{"reply":1}'))
            first = connector.cycle()
            failed = connector.cycle()
            recovered = MockConnector(SessionStore(root), transport, lambda context: calls.append(context) or HandlerResult(b'{"reply":1}')).cycle()
            self.assertEqual(first.responses_prepared, 1)
            self.assertEqual(failed.diagnostics, (("transport_failure", 1),))
            self.assertEqual(recovered.headers_sent, 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(transport.headers[1]), 1)

    def test_duplicate_request_calls_handler_once_and_reuses_identical_bytes(self) -> None:
        with TemporaryDirectory() as root:
            request = (f"1 0\nunit-a\n{_deal()}").encode()
            transport = _FakeTransport([request, request, b"0 0\n"])
            calls = 0

            def handler(_: HandlerContext) -> HandlerResult:
                nonlocal calls
                calls += 1
                return HandlerResult(b'{"reply":1}')

            connector = MockConnector(SessionStore(root), transport, handler)
            connector.cycle()
            connector.cycle()
            connector.cycle()
            self.assertEqual(calls, 1)
            self.assertEqual(len(transport.headers[1]), 1)
            self.assertEqual(len(transport.headers[2]), 1)

    def test_malformed_unsupported_and_handler_failure_are_isolated(self) -> None:
        with TemporaryDirectory() as root:
            body = ("4 0\nunit-a\n{bad}\nunit-b\n" + _deal(1) + "\nunit-c\n{\"stage\":\"tribute\"}\nunit-d\n" + _deal(2)).encode()
            calls: list[int] = []

            def handler(request: HandlerContext) -> HandlerResult:
                calls.append(1)
                if len(calls) == 2:
                    raise RuntimeError("handler")
                return HandlerResult(b"ok")

            cycle = MockConnector(SessionStore(root), _FakeTransport([body]), handler).cycle()
            self.assertEqual(cycle.responses_prepared, 1)
            self.assertEqual(cycle.diagnostics, (("handler_failure", 1), ("malformed_request", 1), ("unsupported_stage", 1)))
            self.assertEqual(len(calls), 2)

    def test_finished_row_clears_only_the_finished_session(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            first = MockConnector(store, _FakeTransport([(f"1 0\nunit-a\n{_deal(0)}").encode()]), lambda _: HandlerResult(b"a"))
            first.cycle()
            second = MockConnector(store, _FakeTransport([(f"1 1\nunit-b\n{_deal(1)}\nunit-a 0 0").encode()]), lambda _: HandlerResult(b"b"))
            cycle = second.cycle()
            self.assertEqual(cycle.finished_seen, 1)
            self.assertEqual(store.load("unit-a").delivery_state, "finished")
            self.assertEqual(store.load("unit-b").pending_response, b"b")

    def test_handler_context_is_match_isolated_and_play_effect_commits_once(self) -> None:
        with TemporaryDirectory() as root:
            first_poll = (f"2 0\nunit-a\n{_deal(0)}\nunit-b\n{_deal(1)}").encode()
            second_poll = (f"2 0\nunit-a\n{_play()}\nunit-b\n{_play()}").encode()
            transport = _FakeTransport([first_poll, second_poll, RuntimeError("offline"), b"0 0\n", b"0 0\n"])
            contexts: list[HandlerContext] = []

            def handler(context: HandlerContext) -> HandlerResult:
                contexts.append(context)
                if isinstance(context.request, DealRequest):
                    return HandlerResult(b"deal")
                return HandlerResult(b"play", PlayEffect((context.own_hand[0],)))

            store = SessionStore(root)
            connector = MockConnector(store, transport, handler)
            connector.cycle()
            connector.cycle()
            play_contexts = [context for context in contexts if isinstance(context.request, PlayRequest)]
            self.assertEqual(len(play_contexts), 2)
            self.assertNotEqual(play_contexts[0].own_hand, play_contexts[1].own_hand)
            self.assertNotEqual(play_contexts[0].local_player_id, play_contexts[1].local_player_id)
            before_failure = store.load("unit-a").own_hand
            connector.cycle()
            self.assertEqual(store.load("unit-a").own_hand, before_failure)
            MockConnector(SessionStore(root), transport, handler).cycle()
            after_ack = SessionStore(root).load("unit-a").own_hand
            self.assertEqual(len(after_ack), len(before_failure) - 1)
            MockConnector(SessionStore(root), transport, handler).cycle()
            self.assertEqual(SessionStore(root).load("unit-a").own_hand, after_ack)

    def test_invalid_handler_results_and_header_injection_fail_closed(self) -> None:
        with TemporaryDirectory() as root:
            poll = (f"1 0\nunit-a\n{_deal()}").encode()
            malformed = MockConnector(SessionStore(root), _FakeTransport([poll]), lambda _: b"not-a-result").cycle()
            self.assertEqual(malformed.diagnostics, (("malformed_handler_result", 1),))
        with TemporaryDirectory() as root:
            poll = (f"1 0\nunit-a\n{_deal()}").encode()
            injected = MockConnector(SessionStore(root), _FakeTransport([poll]), lambda _: HandlerResult(b"bad\r\nvalue")).cycle()
            self.assertEqual(injected.diagnostics, (("header_injection", 1),))

    def test_connector_sources_have_no_runtime_network_or_secret_imports(self) -> None:
        package = Path(__file__).parents[1] / "integrations" / "botzone"
        source = "\n".join(
            (package / filename).read_text(encoding="utf-8")
            for filename in ("poll.py", "session.py", "connector.py")
        )
        forbidden_imports = re.compile(
            r"(?m)^\s*(?:from|import)\s+(?:urllib|requests|socket|dotenv|engine|agents|cli)\b"
        )
        self.assertIsNone(forbidden_imports.search(source))
        for marker in (".env", "api_key", "http://", "https://"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source.lower())


if __name__ == "__main__":
    unittest.main()
