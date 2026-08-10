"""Injected-transport state machine. No network transport is provided here."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from .bot_io import BotEnvelopeError, encode_bot_response
from .models import DealRequest, PlayRequest, UnsupportedStage
from .poll import PollFormatError, PollRequest, parse_poll
from .session import HandlerContext, HandlerResult, PendingDelivery, SessionStorageError, SessionStore


class Transport(Protocol):
    def poll(self, headers: Mapping[str, bytes]) -> bytes: ...


RequestHandler = Callable[[HandlerContext], HandlerResult]


@dataclass(frozen=True, slots=True)
class ConnectorCycle:
    transport_called: bool
    headers_sent: int
    requests_seen: int
    responses_prepared: int
    finished_seen: int
    finished_qualified: int
    diagnostics: tuple[tuple[str, int], ...]


class MockConnector:
    """Coordinates pure poll parsing and stored pending responses via injection."""

    def __init__(self, store: SessionStore, transport: Transport, handler: RequestHandler) -> None:
        self._store = store
        self._transport = transport
        self._handler = handler
        self._play_pending: set[str] = set()
        self._play_acknowledged: set[str] = set()
        self._finished_qualified: set[str] = set()

    def cycle(self) -> ConnectorCycle:
        diagnostics: Counter[str] = Counter()
        try:
            deliveries = self._store.pending_deliveries()
            headers = MappingProxyType({item.header_name: item.response for item in deliveries})
            self._store.mark_inflight(deliveries)
        except SessionStorageError:
            return _cycle(False, 0, 0, 0, 0, 0, {"session_error": 1})

        try:
            raw_poll = self._transport.poll(headers)
        except Exception:
            self._store.restore_pending(deliveries)
            return _cycle(True, len(headers), 0, 0, 0, 0, {"transport_failure": 1})
        try:
            acknowledged = self._store.acknowledge(deliveries)
        except SessionStorageError:
            return _cycle(True, len(headers), 0, 0, 0, 0, {"session_error": 1})
        self._play_acknowledged.update(match_id for match_id in acknowledged if match_id in self._play_pending)

        try:
            batch = parse_poll(raw_poll)
        except PollFormatError:
            return _cycle(True, len(headers), 0, 0, 0, 0, {"poll_malformed": 1})

        prepared = 0
        for request in batch.requests:
            outcome = self._process_request(request)
            diagnostics.update(outcome[1])
            prepared += outcome[0]
        qualified = 0
        for row in batch.finished:
            try:
                cleaned = self._store.finish(row)
            except SessionStorageError:
                diagnostics["session_error"] += 1
                continue
            if (
                cleaned
                and row.player_count == 4
                and row.match_id in self._play_acknowledged
                and row.match_id not in self._finished_qualified
            ):
                self._finished_qualified.add(row.match_id)
                qualified += 1
        return _cycle(True, len(headers), len(batch.requests), prepared, len(batch.finished), qualified, diagnostics)

    def _process_request(self, request: PollRequest) -> tuple[int, Counter[str]]:
        diagnostics: Counter[str] = Counter()
        if request.diagnostic is not None:
            diagnostics[request.diagnostic] += 1
            return 0, diagnostics
        if isinstance(request.stage, UnsupportedStage):
            diagnostics["unsupported_stage"] += 1
            return 0, diagnostics
        if not isinstance(request.stage, (DealRequest, PlayRequest)):
            diagnostics["malformed_request"] += 1
            return 0, diagnostics
        try:
            record, call_handler = self._store.prepare(request.match_id, request.request_bytes, request.stage, request.replay)
        except SessionStorageError as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            return 0, diagnostics
        if not call_handler:
            return int(record.pending_response is not None), diagnostics
        try:
            record = self._store.reserve_handler(record)
            result = self._handler(self._store.handler_context(record, request.stage))
        except Exception:
            self._store.complete_handler(record, HandlerResult(None))
            diagnostics["handler_failure"] += 1
            return 0, diagnostics
        try:
            if not isinstance(result, HandlerResult):
                raise SessionStorageError("malformed_handler_result")
            if result.response is not None:
                if b"\r" in result.response or b"\n" in result.response:
                    raise SessionStorageError("header_injection")
                result = HandlerResult(encode_bot_response(request.stage, result.response), result.effect)
            completed = self._store.complete_handler(record, result)
        except (BotEnvelopeError, SessionStorageError) as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            return 0, diagnostics
        if isinstance(request.stage, PlayRequest) and completed.pending_response:
            self._play_pending.add(request.match_id)
        return int(completed.pending_response is not None), diagnostics


def _normalized_session_error(error: SessionStorageError) -> str:
    known = {
        "play_without_state",
        "atomic_write_failed",
        "header_injection",
        "corrupt_session",
        "history_alignment_failed",
        "invalid_play_effect",
        "malformed_handler_result",
    }
    return str(error) if str(error) in known else "session_error"


def _cycle(
    transport_called: bool,
    headers_sent: int,
    requests_seen: int,
    responses_prepared: int,
    finished_seen: int,
    finished_qualified: int,
    diagnostics: Mapping[str, int],
) -> ConnectorCycle:
    return ConnectorCycle(
        transport_called=transport_called,
        headers_sent=headers_sent,
        requests_seen=requests_seen,
        responses_prepared=responses_prepared,
        finished_seen=finished_seen,
        finished_qualified=finished_qualified,
        diagnostics=tuple(sorted((name, count) for name, count in diagnostics.items() if count)),
    )
