"""HTTPS local-AI transport with an injectable opener.

The transport deliberately keeps the connection URL private: all public errors
are stable categories and never interpolate the configured endpoint.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Mapping
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576


class TransportError(RuntimeError):
    """Normalized, non-sensitive transport failure."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class HttpOpener(Protocol):
    def open(self, request: Request, timeout: float): ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def validate_https_url(value: object) -> str:
    """Validate a private endpoint without ever echoing it back."""

    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise TransportError("invalid_url")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise TransportError("invalid_url") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise TransportError("invalid_url")
    return value


def _safe_headers(headers: Mapping[str, bytes]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for name, value in headers.items():
        if (
            not isinstance(name, str)
            or not name.startswith("X-Match-")
            or not name[8:]
            or any(ord(char) < 33 or ord(char) == 127 for char in name)
            or not isinstance(value, bytes)
            or not value
            or any(byte < 32 or byte == 127 for byte in value)
        ):
            raise TransportError("invalid_header")
        try:
            encoded[name] = value.decode("ascii")
        except UnicodeDecodeError:
            raise TransportError("invalid_header") from None
    return encoded


class LocalAIHttpTransport:
    """One GET poll; retries remain the session/runner responsibility."""

    def __init__(
        self,
        local_ai_url: str,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        opener: HttpOpener | None = None,
    ) -> None:
        self._url = validate_https_url(local_ai_url)
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise TransportError("invalid_timeout")
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise TransportError("invalid_response_limit")
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._opener = opener or build_opener(_RejectRedirects())

    def __repr__(self) -> str:
        return "LocalAIHttpTransport(<redacted>)"

    def poll(self, headers: Mapping[str, bytes]) -> bytes:
        safe_headers = _safe_headers(headers)
        request = Request(self._url, headers=safe_headers, method="GET")
        try:
            response = self._opener.open(request, timeout=self._timeout_seconds)
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            redirected_to = response.geturl() if hasattr(response, "geturl") else self._url
            if redirected_to != self._url:
                raise TransportError("redirect_rejected")
            if type(status) is not int or status != 200:
                raise TransportError("http_error")
            payload = response.read(self._max_response_bytes + 1)
            if not isinstance(payload, bytes):
                raise TransportError("invalid_response")
            if len(payload) > self._max_response_bytes:
                raise TransportError("response_too_large")
            return payload
        except TransportError:
            raise
        except (socket.timeout, TimeoutError):
            raise TransportError("timeout") from None
        except ssl.SSLError:
            raise TransportError("tls_error") from None
        except HTTPError:
            raise TransportError("http_error") from None
        except URLError:
            raise TransportError("network_error") from None
        except OSError:
            raise TransportError("network_error") from None
