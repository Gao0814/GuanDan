"""Injected-transport state machine. No network transport is provided here."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from .bot_io import BotEnvelopeError, REQUIRED_FIELDS_PROFILES, encode_bot_response, encode_direct_response
from .http_transport import TRANSPORT_CATEGORIES, TransportError
from .models import DealRequest, PlayRequest, UnsupportedStage
from .poll import ENVELOPE_SHAPE_DETAILS, FinishedRow, PollFormatError, PollRequest, WIRE_MODES, parse_poll
from .result_observability import (
    ResultObservabilityError,
    ResultObservabilityRecorder,
    ResultObservabilitySnapshot,
)
from .session import HandlerContext, HandlerResult, PendingDelivery, SessionRecord, SessionStorageError, SessionStore


class Transport(Protocol):
    def poll(self, headers: Mapping[str, bytes]) -> bytes: ...


RequestHandler = Callable[[HandlerContext], HandlerResult]


class HistoryRecorder(Protocol):
    """Optional diagnostic artifact boundary; it cannot affect delivery."""

    failed: bool

    @property
    def status(self) -> str: ...

    def update(self, record: SessionRecord) -> None: ...

    def finish(self, record: SessionRecord, row: FinishedRow) -> None: ...


@dataclass(frozen=True, slots=True)
class ConnectorCycle:
    transport_called: bool
    headers_sent: int
    requests_seen: int
    responses_prepared: int
    finished_seen: int
    finished_qualified: int
    diagnostics: tuple[tuple[str, int], ...]
    diagnostic_details: tuple[tuple[str, int], ...] = ()
    diagnostic_profiles: tuple[tuple[str, int], ...] = ()
    transport_timeouts: int = 0
    transport_failure_categories: tuple[tuple[str, int], ...] = ()
    finished_categories: tuple[tuple[str, int], ...] = ()


TRANSPORT_FAILURE_CATEGORIES = frozenset(TRANSPORT_CATEGORIES - {"timeout"}) | {"unclassified"}
FINISHED_CATEGORIES = frozenset(
    {"aborted", "non_four_player", "four_player_unqualified", "qualified"}
)


class MockConnector:
    """Coordinates pure poll parsing and stored pending responses via injection."""

    def __init__(
        self,
        store: SessionStore,
        transport: Transport,
        handler: RequestHandler,
        result_observability: ResultObservabilityRecorder | None = None,
        history_recorder: HistoryRecorder | None = None,
    ) -> None:
        self._store = store
        self._transport = transport
        self._handler = handler
        self._result_observability = (
            result_observability if result_observability is not None else ResultObservabilityRecorder()
        )
        self._result_observability_failed = False
        self._history_recorder = history_recorder
        self._play_pending: set[str] = set()
        self._play_acknowledged: set[str] = set()
        self._finished_qualified: set[str] = set()

    def cycle(self) -> ConnectorCycle:
        diagnostics: Counter[str] = Counter()
        diagnostic_details: Counter[str] = Counter()
        diagnostic_profiles: Counter[str] = Counter()
        try:
            deliveries = self._store.pending_deliveries()
            headers = MappingProxyType({item.header_name: item.response for item in deliveries})
            self._store.mark_inflight(deliveries)
        except SessionStorageError:
            return _cycle(False, 0, 0, 0, 0, 0, {"session_error": 1})

        try:
            raw_poll = self._transport.poll(headers)
        except TransportError as exc:
            self._store.restore_pending(deliveries)
            if exc.category == "timeout":
                return _cycle(
                    True, len(headers), 0, 0, 0, 0, {"transport_timeout": 1}, transport_timeouts=1
                )
            category = exc.category if exc.category in TRANSPORT_FAILURE_CATEGORIES else "unclassified"
            return _cycle(
                True,
                len(headers),
                0,
                0,
                0,
                0,
                {"transport_failure": 1},
                transport_failure_categories={category: 1},
            )
        except Exception:
            self._store.restore_pending(deliveries)
            return _cycle(
                True,
                len(headers),
                0,
                0,
                0,
                0,
                {"transport_failure": 1},
                transport_failure_categories={"unclassified": 1},
            )
        try:
            acknowledged = self._store.acknowledge(deliveries)
        except SessionStorageError:
            return _cycle(True, len(headers), 0, 0, 0, 0, {"session_error": 1})
        self._play_acknowledged.update(match_id for match_id in acknowledged if match_id in self._play_pending)
        for match_id in acknowledged:
            try:
                record = self._store.load(match_id)
                if record is not None:
                    self._record_history(record)
            except SessionStorageError:
                # The acknowledgement has already committed; diagnostic output
                # must not alter its transaction result.
                if self._history_recorder is not None:
                    self._history_recorder.failed = True

        try:
            batch = parse_poll(raw_poll)
        except PollFormatError:
            return _cycle(True, len(headers), 0, 0, 0, 0, {"poll_malformed": 1})

        prepared = 0
        for request in batch.requests:
            outcome = self._process_request(request)
            diagnostics.update(outcome[1])
            diagnostic_details.update(outcome[2])
            diagnostic_profiles.update(outcome[3])
            prepared += outcome[0]
        qualified = 0
        finished_categories: Counter[str] = Counter()
        for row in batch.finished:
            category = _finished_category(row.player_count)
            self._record_finished_history(row)
            try:
                cleaned = self._store.finish(row)
            except SessionStorageError:
                diagnostics["session_error"] += 1
                cleaned = False
            if (
                cleaned
                and row.player_count == 4
                and row.match_id in self._play_acknowledged
                and row.match_id not in self._finished_qualified
            ):
                self._finished_qualified.add(row.match_id)
                qualified += 1
                category = "qualified"
                try:
                    self._result_observability.record_qualified_finished(row.local_player_id, row.scores)
                except Exception:
                    self._result_observability_failed = True
            finished_categories[category] += 1
            if cleaned:
                try:
                    release_match = getattr(self._handler, "release_match", None)
                    if callable(release_match):
                        release_match(row.match_id)
                except Exception:
                    diagnostics["handler_lifecycle_failure"] += 1
        return _cycle(
            True,
            len(headers),
            len(batch.requests),
            prepared,
            len(batch.finished),
            qualified,
            diagnostics,
            diagnostic_details,
            diagnostic_profiles,
            finished_categories=finished_categories,
        )

    def result_observability_snapshot(self) -> ResultObservabilitySnapshot:
        if self._result_observability_failed:
            raise ResultObservabilityError("observability_unavailable")
        return self._result_observability.snapshot()

    def _process_request(self, request: PollRequest) -> tuple[int, Counter[str], Counter[str], Counter[str]]:
        diagnostics: Counter[str] = Counter()
        details: Counter[str] = Counter()
        profiles: Counter[str] = Counter()
        if request.diagnostic is not None:
            diagnostics[request.diagnostic] += 1
            if (
                request.diagnostic == "envelope_shape_invalid"
                and request.diagnostic_detail in ENVELOPE_SHAPE_DETAILS
            ):
                details[request.diagnostic_detail] += 1
            if (
                request.diagnostic == "envelope_shape_invalid"
                and request.diagnostic_detail == "envelope_required_fields_missing"
                and request.diagnostic_profile in REQUIRED_FIELDS_PROFILES
            ):
                profiles[request.diagnostic_profile] += 1
            return 0, diagnostics, details, profiles
        if isinstance(request.stage, UnsupportedStage):
            diagnostics["unsupported_stage"] += 1
            return 0, diagnostics, details, profiles
        if not isinstance(request.stage, (DealRequest, PlayRequest)):
            diagnostics["malformed_request"] += 1
            return 0, diagnostics, details, profiles
        try:
            record, call_handler = self._store.prepare(request.match_id, request.request_bytes, request.stage, request.replay)
        except SessionStorageError as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            return 0, diagnostics, details, profiles
        if not call_handler:
            return int(record.pending_response is not None), diagnostics, details, profiles
        try:
            record = self._store.reserve_handler(record)
            result = self._handler(self._store.handler_context(record, request.stage))
        except Exception:
            self._store.complete_handler(record, HandlerResult(None))
            diagnostics["handler_failure"] += 1
            return 0, diagnostics, details, profiles
        try:
            if not isinstance(result, HandlerResult):
                raise SessionStorageError("malformed_handler_result")
            if result.response is not None:
                if b"\r" in result.response or b"\n" in result.response:
                    raise SessionStorageError("header_injection")
                if request.wire_mode not in WIRE_MODES:
                    raise SessionStorageError("malformed_handler_result")
                encoded = (
                    encode_bot_response(request.stage, result.response)
                    if request.wire_mode == "bot_envelope"
                    else encode_direct_response(request.stage, result.response)
                )
                result = HandlerResult(encoded, result.effect)
            completed = self._store.complete_handler(record, result)
        except (BotEnvelopeError, SessionStorageError) as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            return 0, diagnostics, details, profiles
        if isinstance(request.stage, PlayRequest) and completed.pending_response:
            self._play_pending.add(request.match_id)
        self._record_history(completed)
        return int(completed.pending_response is not None), diagnostics, details, profiles

    def _record_history(self, record: SessionRecord) -> None:
        """Best-effort diagnostic rendering after normal handler validation."""

        if self._history_recorder is None:
            return
        try:
            self._history_recorder.update(record)
        except Exception:
            # History is intentionally outside pending/ack and audit contracts.
            self._history_recorder.failed = True

    def _record_finished_history(self, row: FinishedRow) -> None:
        if self._history_recorder is None:
            return
        try:
            record = self._store.load(row.match_id)
            if record is not None:
                self._history_recorder.finish(record, row)
        except Exception:
            self._history_recorder.failed = True

    @property
    def history_status(self) -> str:
        return "disabled" if self._history_recorder is None else self._history_recorder.status


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


def _finished_category(player_count: int) -> str:
    if player_count == 0:
        return "aborted"
    if player_count != 4:
        return "non_four_player"
    return "four_player_unqualified"


def _cycle(
    transport_called: bool,
    headers_sent: int,
    requests_seen: int,
    responses_prepared: int,
    finished_seen: int,
    finished_qualified: int,
    diagnostics: Mapping[str, int],
    diagnostic_details: Mapping[str, int] | None = None,
    diagnostic_profiles: Mapping[str, int] | None = None,
    *,
    transport_timeouts: int = 0,
    transport_failure_categories: Mapping[str, int] | None = None,
    finished_categories: Mapping[str, int] | None = None,
) -> ConnectorCycle:
    return ConnectorCycle(
        transport_called=transport_called,
        headers_sent=headers_sent,
        requests_seen=requests_seen,
        responses_prepared=responses_prepared,
        finished_seen=finished_seen,
        finished_qualified=finished_qualified,
        diagnostics=tuple(sorted((name, count) for name, count in diagnostics.items() if count)),
        diagnostic_details=tuple(
            sorted((name, count) for name, count in (diagnostic_details or {}).items() if count)
        ),
        diagnostic_profiles=tuple(
            sorted((name, count) for name, count in (diagnostic_profiles or {}).items() if count)
        ),
        transport_timeouts=transport_timeouts if type(transport_timeouts) is int and transport_timeouts >= 0 else 0,
        transport_failure_categories=tuple(
            sorted(
                (name, count)
                for name, count in (transport_failure_categories or {}).items()
                if name in TRANSPORT_FAILURE_CATEGORIES and type(count) is int and count > 0
            )
        ),
        finished_categories=tuple(
            sorted(
                (name, count)
                for name, count in (finished_categories or {}).items()
                if name in FINISHED_CATEGORIES and type(count) is int and count > 0
            )
        ),
    )
