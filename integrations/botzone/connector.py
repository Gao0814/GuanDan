"""Injected-transport state machine. No network transport is provided here."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
import time

from decision_deadline import DecisionDeadline
from typing import Protocol

from .bot_io import BotEnvelopeError, REQUIRED_FIELDS_PROFILES, encode_bot_response, encode_direct_response
from .http_transport import TRANSPORT_CATEGORIES, TransportError
from .models import DealRequest, PlayRequest, UnsupportedStage
from .poll import ENVELOPE_SHAPE_DETAILS, FinishedRow, PollFormatError, PollRequest, WIRE_MODES, parse_poll
from .result_observability import (
    ResultObservabilityError,
    ResultObservabilityRecorder,
    ResultObservabilitySnapshot,
    classify_finished_score,
)
from .game_results import GameResultRecorder
from .session import HandlerContext, HandlerResult, PendingDelivery, SessionRecord, SessionStorageError, SessionStore
from .stage_trace import StageTraceSink, record_stage


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
        decision_trace_recorder: HistoryRecorder | None = None,
        stage_trace: StageTraceSink | None = None,
        decision_timeout_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        game_result_recorder: GameResultRecorder | None = None,
    ) -> None:
        self._store = store
        self._transport = transport
        self._handler = handler
        self._result_observability = (
            result_observability if result_observability is not None else ResultObservabilityRecorder()
        )
        self._result_observability_failed = False
        self._history_recorder = history_recorder
        self._decision_trace_recorder = decision_trace_recorder
        self._game_result_recorder = game_result_recorder
        self._stage_trace = stage_trace
        self._decision_timeout_seconds = decision_timeout_seconds
        self._clock = clock
        self._play_pending: set[str] = set()
        self._play_acknowledged: set[str] = set()
        self._finished_qualified: set[str] = set()

    def cycle(self) -> ConnectorCycle:
        diagnostics: Counter[str] = Counter()
        diagnostic_details: Counter[str] = Counter()
        diagnostic_profiles: Counter[str] = Counter()
        self._recover_decision_traces()
        try:
            deliveries = self._store.pending_deliveries()
            headers = MappingProxyType({item.header_name: item.response for item in deliveries})
            self._store.mark_inflight(deliveries)
        except SessionStorageError:
            return _cycle(False, 0, 0, 0, 0, 0, {"session_error": 1})

        self._record_stage("poll_enter", "started")
        if deliveries:
            self._record_stage("response_header_emitted", "pending")
            self._record_stage("response_waiting_ack", "pending")

        try:
            raw_poll = self._transport.poll(headers)
            self._record_stage("poll_returned", "response_received")
        except TransportError as exc:
            self._store.restore_pending(deliveries)
            if exc.category == "timeout":
                self._record_stage("poll_exit", "timeout")
                return _cycle(
                    True, len(headers), 0, 0, 0, 0, {"transport_timeout": 1}, transport_timeouts=1
                )
            category = exc.category if exc.category in TRANSPORT_FAILURE_CATEGORIES else "unclassified"
            self._record_stage("poll_exit", "transport_failure")
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
            self._record_stage("poll_exit", "transport_failure")
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
            if deliveries:
                self._record_stage("response_acknowledged", "failed")
            self._record_stage("poll_exit", "session_error")
            return _cycle(True, len(headers), 0, 0, 0, 0, {"session_error": 1})
        if deliveries:
            if not acknowledged:
                ack_outcome = "not_confirmed"
            elif len(acknowledged) == len(deliveries):
                ack_outcome = "confirmed"
            else:
                ack_outcome = "partial"
            self._record_stage("response_acknowledged", ack_outcome)
        self._play_acknowledged.update(match_id for match_id in acknowledged if match_id in self._play_pending)
        for match_id in acknowledged:
            try:
                record = self._store.load(match_id)
                if record is not None:
                    self._record_history(record)
                    self._record_decision_trace(record)
            except SessionStorageError:
                # The acknowledgement has already committed; diagnostic output
                # must not alter its transaction result.
                if self._history_recorder is not None:
                    self._history_recorder.failed = True
                if self._decision_trace_recorder is not None:
                    self._decision_trace_recorder.failed = True

        try:
            batch = parse_poll(raw_poll)
        except PollFormatError:
            self._record_stage("poll_exit", "malformed")
            return _cycle(True, len(headers), 0, 0, 0, 0, {"poll_malformed": 1})

        poll_outcome = "finished" if batch.finished else ("payload" if batch.requests else "idle")
        self._record_stage("poll_exit", poll_outcome)

        if self._game_result_recorder is not None:
            prepare_poll = getattr(self._game_result_recorder, "prepare_poll", None)
            if callable(prepare_poll):
                try:
                    prepare_poll({row.match_id for row in batch.finished})
                except Exception:
                    self._game_result_recorder.failed = True

        prepared = 0
        for request in batch.requests:
            if isinstance(request.stage, DealRequest) and self._game_result_recorder is not None:
                begin_game = getattr(self._game_result_recorder, "begin_game", None)
                if callable(begin_game):
                    try:
                        begin_game(request.match_id)
                    except Exception:
                        self._game_result_recorder.failed = True
            outcome = self._process_request(request)
            diagnostics.update(outcome[1])
            diagnostic_details.update(outcome[2])
            diagnostic_profiles.update(outcome[3])
            prepared += outcome[0]
        qualified = 0
        finished_categories: Counter[str] = Counter()
        for row in batch.finished:
            category = _finished_category(row.player_count)
            qualified_result: str | None = None
            self._record_finished_history(row)
            self._record_finished_decision_trace(row)
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
                if self._game_result_recorder is not None:
                    try:
                        result_category, _ = classify_finished_score(row.local_player_id, row.scores)
                        record_finished = getattr(self._game_result_recorder, "record_finished", None)
                        if callable(record_finished):
                            record_finished(result_category, row.match_id)
                        else:
                            self._game_result_recorder.record(result_category)
                        qualified_result = result_category
                    except Exception:
                        self._game_result_recorder.failed = True
            if self._game_result_recorder is not None and qualified_result is None:
                finish_unconfirmed = getattr(self._game_result_recorder, "finish_unconfirmed", None)
                if callable(finish_unconfirmed):
                    try:
                        finish_unconfirmed(row.match_id)
                    except Exception:
                        self._game_result_recorder.failed = True
            self._record_stage("finished", category)
            finished_categories[category] += 1
            if cleaned:
                try:
                    release_match = getattr(self._handler, "release_match", None)
                    if callable(release_match):
                        release_match(row.match_id)
                except Exception:
                    diagnostics["handler_lifecycle_failure"] += 1
        if self._game_result_recorder is not None:
            finish_poll = getattr(self._game_result_recorder, "finish_poll", None)
            if callable(finish_poll):
                try:
                    finish_poll()
                except Exception:
                    self._game_result_recorder.failed = True
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

    @property
    def game_results_status(self) -> str:
        return "disabled" if self._game_result_recorder is None else self._game_result_recorder.status

    @property
    def game_results_recorded(self) -> int:
        return 0 if self._game_result_recorder is None else self._game_result_recorder.recorded_count

    @property
    def recent_results_status(self) -> str:
        if self._game_result_recorder is None:
            return "disabled"
        status = getattr(self._game_result_recorder, "recent_status", "disabled")
        return status if status in {"ok", "failed"} else "failed"

    def recent_results_snapshot(self) -> object | None:
        if self._game_result_recorder is None:
            return None
        snapshot = getattr(self._game_result_recorder, "snapshot", None)
        return snapshot() if callable(snapshot) else None

    def close_game_results(self) -> None:
        if self._game_result_recorder is None:
            return
        try:
            self._game_result_recorder.close()
        except Exception:
            self._game_result_recorder.failed = True

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
        if isinstance(request.stage, PlayRequest):
            self._record_stage("play_request_arrived", "received")
            decision_deadline = (
                DecisionDeadline(self._clock() + self._decision_timeout_seconds, clock=self._clock)
                if self._decision_timeout_seconds is not None
                else None
            )
        else:
            decision_deadline = None
        try:
            record, call_handler = self._store.prepare(request.match_id, request.request_bytes, request.stage, request.replay)
        except SessionStorageError as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            return 0, diagnostics, details, profiles
        if not call_handler:
            if record.pending_response is not None:
                self._record_stage("response_waiting_ack", "pending")
            return int(record.pending_response is not None), diagnostics, details, profiles
        try:
            record = self._store.reserve_handler(record)
            result = self._handler(
                self._store.handler_context(
                    record,
                    request.stage,
                    decision_deadline=decision_deadline,
                )
            )
        except Exception:
            self._store.complete_handler(record, HandlerResult(None))
            diagnostics["handler_failure"] += 1
            self._record_stage("response_prepared", "handler_failure")
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
                result = HandlerResult(encoded, result.effect, result.decision_trace, result.decision_trace_failed)
            completed = self._store.complete_handler(record, result)
        except (BotEnvelopeError, SessionStorageError) as exc:
            diagnostics[_normalized_session_error(exc)] += 1
            self._record_stage("response_prepared", "rejected")
            return 0, diagnostics, details, profiles
        self._record_stage(
            "response_prepared",
            "prepared" if completed.pending_response is not None else "no_response",
        )
        if completed.pending_response is not None:
            self._record_stage("response_waiting_ack", "pending")
        if isinstance(request.stage, PlayRequest) and completed.pending_response:
            self._play_pending.add(request.match_id)
        if result.decision_trace_failed and self._decision_trace_recorder is not None:
            self._decision_trace_recorder.failed = True
        self._record_history(completed)
        return int(completed.pending_response is not None), diagnostics, details, profiles

    def _record_stage(self, stage: str, outcome: str) -> None:
        record_stage(self._stage_trace, stage, outcome)

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

    def _record_decision_trace(self, record: SessionRecord) -> None:
        """Render only snapshots that the store has already acknowledged."""

        if self._decision_trace_recorder is None:
            return
        try:
            self._decision_trace_recorder.update(record)
        except Exception:
            self._decision_trace_recorder.failed = True

    def _recover_decision_traces(self) -> None:
        """Recover acknowledged snapshots if a prior process ended after ack."""

        if self._decision_trace_recorder is None or self._decision_trace_recorder.failed:
            return
        try:
            for record in self._store.active_records():
                self._record_decision_trace(record)
        except Exception:
            self._decision_trace_recorder.failed = True

    def _record_finished_decision_trace(self, row: FinishedRow) -> None:
        if self._decision_trace_recorder is None:
            return
        try:
            record = self._store.load(row.match_id)
            if record is not None:
                self._decision_trace_recorder.finish(record, row)
        except Exception:
            self._decision_trace_recorder.failed = True

    @property
    def history_status(self) -> str:
        return "disabled" if self._history_recorder is None else self._history_recorder.status

    @property
    def decision_trace_status(self) -> str:
        return "disabled" if self._decision_trace_recorder is None else self._decision_trace_recorder.status


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
