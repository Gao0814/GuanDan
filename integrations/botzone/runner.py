"""Foreground composition root for the local-AI connector."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from .connector import ConnectorCycle, MockConnector, Transport
from .play_adapter import NoTributeRuleBasedHandler
from .runtime_config import RuntimeConfig
from .session import SessionStore


@dataclass(frozen=True, slots=True)
class RunnerSummary:
    cycles: int
    successful_cycles: int
    transport_failures: int
    stopped: str
    diagnostics: tuple[tuple[str, int], ...]


class ForegroundRunner:
    """Finite-testable foreground loop; it never starts a background process."""

    def __init__(
        self,
        connector: MockConnector,
        *,
        max_consecutive_failures: int,
        backoff_seconds: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._connector = connector
        self._max_failures = max_consecutive_failures
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._clock = clock

    def run(self, *, max_cycles: int | None = None) -> RunnerSummary:
        if max_cycles is not None and (type(max_cycles) is not int or max_cycles <= 0):
            raise ValueError("invalid_cycle_limit")
        cycles = successes = failures = 0
        consecutive_failures = 0
        diagnostics: Counter[str] = Counter()
        stopped = "cycle_limit"
        try:
            while max_cycles is None or cycles < max_cycles:
                cycle = self._connector.cycle()
                cycles += 1
                diagnostics.update(dict(cycle.diagnostics))
                if _has_transport_failure(cycle):
                    failures += 1
                    consecutive_failures += 1
                    if consecutive_failures >= self._max_failures:
                        stopped = "failure_limit"
                        break
                    requested_delay = self._backoff_seconds * (2 ** (consecutive_failures - 1))
                    deadline = self._clock() + requested_delay
                    self._sleep(max(0.0, deadline - self._clock()))
                else:
                    successes += 1
                    consecutive_failures = 0
        except KeyboardInterrupt:
            stopped = "interrupted"
        return RunnerSummary(cycles, successes, failures, stopped, tuple(sorted(diagnostics.items())))


def _has_transport_failure(cycle: ConnectorCycle) -> bool:
    return any(name == "transport_failure" and count for name, count in cycle.diagnostics)


def build_foreground_runner(
    config: RuntimeConfig,
    transport: Transport,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ForegroundRunner:
    connector = MockConnector(SessionStore(config.state_directory), transport, NoTributeRuleBasedHandler())
    return ForegroundRunner(
        connector,
        max_consecutive_failures=config.max_consecutive_failures,
        backoff_seconds=config.backoff_seconds,
        sleep=sleep,
        clock=clock,
    )
