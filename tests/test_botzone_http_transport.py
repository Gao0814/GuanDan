from __future__ import annotations

import socket
import unittest
from urllib.error import HTTPError, URLError

from integrations.botzone.http_transport import LocalAIHttpTransport, TransportError


class _Response:
    def __init__(self, payload: bytes, *, status: int = 200, location: str = "https://private.invalid/poll") -> None:
        self._payload = payload
        self.status = status
        self._location = location
        self.closed = False

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]

    def geturl(self) -> str:
        return self._location

    def close(self) -> None:
        self.closed = True


class _Opener:
    def __init__(self, result: object) -> None:
        self.result = result
        self.requests: list[object] = []

    def open(self, request: object, timeout: float) -> object:
        self.requests.append((request, timeout))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class BotzoneHttpTransportTests(unittest.TestCase):
    def test_get_without_body_and_pending_headers_use_injected_opener(self) -> None:
        response = _Response(b"0 0\n")
        opener = _Opener(response)
        transport = LocalAIHttpTransport("https://private.invalid/poll", timeout_seconds=9, opener=opener)
        self.assertEqual(transport.poll({"X-Match-unit": b"[[],[]]"}), b"0 0\n")
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertEqual(timeout, 9)
        self.assertEqual(request.get_header("X-match-unit"), "[[],[]]")
        self.assertTrue(response.closed)

    def test_invalid_headers_responses_and_network_errors_are_normalized(self) -> None:
        transport = LocalAIHttpTransport("https://private.invalid/poll", opener=_Opener(_Response(b"ok")))
        for headers in ({"X-Match-unit\nnext": b"ok"}, {"X-Match-unit": b"bad\r"}, {"X-Match-\u00f1": b"ok"}, {"Other": b"ok"}):
            with self.subTest(headers=headers):
                with self.assertRaisesRegex(TransportError, "invalid_header"):
                    transport.poll(headers)
        for result, category in (
            (_Response(b"ok", status=503), "http_error"),
            (_Response(b"x" * 4), "response_too_large"),
            (_Response(b"ok", location="https://other.invalid/poll"), "redirect_rejected"),
            (socket.timeout(), "timeout"),
            (URLError("offline"), "network_error"),
            (HTTPError("https://private.invalid/poll", 500, "bad", {}, None), "http_error"),
            (RuntimeError("https://private.invalid/secret"), "opener_error"),
        ):
            with self.subTest(category=category):
                candidate = LocalAIHttpTransport(
                    "https://private.invalid/poll", max_response_bytes=2, opener=_Opener(result)
                )
                with self.assertRaisesRegex(TransportError, category):
                    candidate.poll({})
                if isinstance(result, _Response):
                    self.assertTrue(result.closed)

    def test_url_validation_and_repr_do_not_disclose_private_endpoint(self) -> None:
        for value in ("http://private.invalid", "https://user@private.invalid", "https://private.invalid/#x"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TransportError, "invalid_url"):
                    LocalAIHttpTransport(value)
        transport = LocalAIHttpTransport("https://private.invalid/secret", opener=_Opener(_Response(b"ok")))
        self.assertNotIn("private.invalid", repr(transport))


if __name__ == "__main__":
    unittest.main()
