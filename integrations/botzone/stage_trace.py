"""Opt-in low-sensitivity connector stage events for the personal launcher."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Protocol, TextIO


STAGE_OUTCOMES = {
    "connector_start": frozenset({"started"}),
    "poll_enter": frozenset({"started"}),
    "poll_returned": frozenset({"response_received"}),
    "poll_exit": frozenset(
        {"payload", "idle", "finished", "timeout", "transport_failure", "session_error", "malformed"}
    ),
    "play_request_arrived": frozenset({"received"}),
    "model_enter": frozenset({"started"}),
    "model_complete": frozenset({"success", "timeout", "exception", "invalid_suggestion"}),
    "response_prepared": frozenset({"prepared", "no_response", "handler_failure", "rejected"}),
    "response_header_emitted": frozenset({"pending"}),
    "response_waiting_ack": frozenset({"pending"}),
    "response_acknowledged": frozenset({"confirmed", "partial", "not_confirmed", "failed"}),
    "finished": frozenset({"qualified", "aborted", "non_four_player", "four_player_unqualified"}),
    "runner_exit": frozenset(
        {
            "finished_target",
            "interrupted",
            "failure_limit",
            "unsupported_stage",
            "diagnostic_failure",
            "cycle_limit_unfinished",
            "wall_limit_unfinished",
        }
    ),
    "connector_exit": frozenset(
        {
            "finished_target",
            "interrupted",
            "failure_limit",
            "unsupported_stage",
            "diagnostic_failure",
            "cycle_limit_unfinished",
            "wall_limit_unfinished",
            "configuration_error",
        }
    ),
}
MAX_STAGE_EVENTS = 20_000
MAX_ELAPSED_MILLISECONDS = 86_400_000
STAGE_TRACE_PREFIX = "BOTZONE_STAGE "


class StageTraceSink(Protocol):
    def emit(self, stage: str, outcome: str) -> None: ...


def record_stage(trace: StageTraceSink | None, stage: str, outcome: str) -> None:
    """Best-effort observation: a broken diagnostic sink never affects play."""

    if trace is None:
        return
    try:
        trace.emit(stage, outcome)
    except Exception:
        pass


class StageTrace:
    """Write a fixed-schema event line and flush it immediately to the given stream."""

    def __init__(self, stream: TextIO, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._stream = stream
        self._clock = clock
        try:
            self._started = clock()
        except Exception:
            self._started = 0.0
        self._sequence = 0
        self._disabled = False

    def emit(self, stage: str, outcome: str) -> None:
        if self._disabled or stage not in STAGE_OUTCOMES or outcome not in STAGE_OUTCOMES[stage]:
            return
        if self._sequence >= MAX_STAGE_EVENTS:
            self._disabled = True
            return
        try:
            now = self._clock()
            elapsed = int((now - self._started) * 1000)
            elapsed = max(0, min(MAX_ELAPSED_MILLISECONDS, elapsed))
            self._sequence += 1
            event = {
                "stage": stage,
                "seq": self._sequence,
                "elapsed_ms": elapsed,
                "outcome": outcome,
            }
            self._stream.write(STAGE_TRACE_PREFIX + json.dumps(event, separators=(",", ":")) + "\n")
            self._stream.flush()
        except Exception:
            self._disabled = True
