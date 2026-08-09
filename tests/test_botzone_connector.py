from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.session import SessionStore


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
            connector = MockConnector(SessionStore(root), transport, lambda request: calls.append(request) or b'{"reply":1}')
            first = connector.cycle()
            failed = connector.cycle()
            recovered = MockConnector(SessionStore(root), transport, lambda request: calls.append(request) or b'{"reply":1}').cycle()
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

            def handler(_: DealRequest | PlayRequest) -> bytes:
                nonlocal calls
                calls += 1
                return b'{"reply":1}'

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

            def handler(request: DealRequest | PlayRequest) -> bytes:
                calls.append(1)
                if len(calls) == 2:
                    raise RuntimeError("handler")
                return b"ok"

            cycle = MockConnector(SessionStore(root), _FakeTransport([body]), handler).cycle()
            self.assertEqual(cycle.responses_prepared, 1)
            self.assertEqual(cycle.diagnostics, (("handler_failure", 1), ("malformed_request", 1), ("unsupported_stage", 1)))
            self.assertEqual(len(calls), 2)

    def test_finished_row_clears_only_the_finished_session(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            first = MockConnector(store, _FakeTransport([(f"1 0\nunit-a\n{_deal(0)}").encode()]), lambda _: b"a")
            first.cycle()
            second = MockConnector(store, _FakeTransport([(f"1 1\nunit-b\n{_deal(1)}\nunit-a 0 0").encode()]), lambda _: b"b")
            cycle = second.cycle()
            self.assertEqual(cycle.finished_seen, 1)
            self.assertEqual(store.load("unit-a").delivery_state, "finished")
            self.assertEqual(store.load("unit-b").pending_response, b"b")

    def test_connector_sources_have_no_runtime_network_or_secret_imports(self) -> None:
        package = Path(__file__).parents[1] / "integrations" / "botzone"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
        forbidden_imports = re.compile(
            r"(?m)^\s*(?:from|import)\s+(?:urllib|requests|socket|dotenv|engine|agents|cli)\b"
        )
        self.assertIsNone(forbidden_imports.search(source))
        for marker in (".env", "api_key", "http://", "https://"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source.lower())


if __name__ == "__main__":
    unittest.main()
