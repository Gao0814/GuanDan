"""Monotonic decision-budget primitive shared by AI and connector layers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


MODEL_RESPONSE_RESERVE_SECONDS = 5.0


class DecisionDeadlineExceeded(TimeoutError):
    """The configured end-to-end decision budget expired or was cancelled."""


class DecisionDeadline:
    """Monotonic per-decision deadline with best-effort active-I/O cancellation."""

    def __init__(self, deadline_monotonic: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.deadline_monotonic = float(deadline_monotonic)
        self._clock = clock
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._next_callback = 0
        self._callbacks: dict[int, Callable[[], None]] = {}

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def remaining(self, *, reserve_seconds: float = 0.0) -> float:
        if self.cancelled:
            return 0.0
        try:
            return max(0.0, self.deadline_monotonic - self._clock() - reserve_seconds)
        except Exception:
            return 0.0

    def is_expired(self, *, reserve_seconds: float = 0.0) -> bool:
        return self.remaining(reserve_seconds=reserve_seconds) <= 0.0

    def check(self, *, reserve_seconds: float = 0.0) -> None:
        if self.is_expired(reserve_seconds=reserve_seconds):
            raise DecisionDeadlineExceeded("decision_deadline_exceeded")

    def register_cancel_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a resource closer and return a best-effort unregister function."""

        if not callable(callback):
            raise TypeError("cancel_callback_invalid")
        with self._lock:
            if self._cancelled.is_set():
                callback_now = True
                callback_id = -1
            else:
                callback_now = False
                callback_id = self._next_callback
                self._next_callback += 1
                self._callbacks[callback_id] = callback
        if callback_now:
            self._close_safely(callback)

        def unregister() -> None:
            if callback_id >= 0:
                with self._lock:
                    self._callbacks.pop(callback_id, None)

        return unregister

    def cancel(self) -> None:
        """Signal cancellation and close any currently registered network response."""

        with self._lock:
            if self._cancelled.is_set():
                return
            self._cancelled.set()
            callbacks = tuple(self._callbacks.values())
            self._callbacks.clear()
        for callback in callbacks:
            self._close_safely(callback)

    @staticmethod
    def _close_safely(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            pass
