"""Foreground composition root for the local-AI connector."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import json
import os
import tempfile

from .connector import (
    FINISHED_CATEGORIES,
    TRANSPORT_FAILURE_CATEGORIES,
    ConnectorCycle,
    MockConnector,
    Transport,
)
from .agent_runtime import build_agent_factory
from .play_adapter import NoTributeRuleBasedHandler
from .poll import ENVELOPE_SHAPE_DETAILS, REQUIRED_FIELDS_PROFILES
from .runtime_config import RuntimeConfig
from .session import SessionStore


@dataclass(frozen=True, slots=True)
class RunnerSummary:
    cycles: int
    successful_cycles: int
    transport_failures: int
    headers_sent: int
    requests_seen: int
    responses_prepared: int
    finished_seen: int
    finished_qualified: int
    stopped: str
    diagnostics: tuple[tuple[str, int], ...]
    diagnostic_details: tuple[tuple[str, int], ...] = ()
    diagnostic_profiles: tuple[tuple[str, int], ...] = ()
    transport_timeouts: int = 0
    transport_failure_categories: tuple[tuple[str, int], ...] = ()
    finished_categories: tuple[tuple[str, int], ...] = ()


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

    def run(
        self,
        *,
        max_cycles: int = 100,
        max_wall_seconds: int = 600,
        stop_after_finished: int = 1,
    ) -> RunnerSummary:
        if any(type(value) is not int or value <= 0 for value in (max_cycles, max_wall_seconds, stop_after_finished)):
            raise ValueError("invalid_runner_limit")
        cycles = successes = failures = headers = requests = responses = finished = qualified = timeouts = 0
        consecutive_failures = 0
        diagnostics: Counter[str] = Counter()
        diagnostic_details: Counter[str] = Counter()
        diagnostic_profiles: Counter[str] = Counter()
        transport_failure_categories: Counter[str] = Counter()
        finished_categories: Counter[str] = Counter()
        stopped = "cycle_limit_unfinished"
        started = self._clock()
        try:
            while cycles < max_cycles:
                if self._clock() - started >= max_wall_seconds:
                    stopped = "wall_limit_unfinished"
                    break
                cycle = self._connector.cycle()
                cycles += 1
                diagnostics.update(dict(cycle.diagnostics))
                diagnostic_details.update(
                    {
                        name: count
                        for name, count in cycle.diagnostic_details
                        if name in ENVELOPE_SHAPE_DETAILS and type(count) is int and count > 0
                    }
                )
                diagnostic_profiles.update(
                    {
                        name: count
                        for name, count in cycle.diagnostic_profiles
                        if name in REQUIRED_FIELDS_PROFILES and type(count) is int and count > 0
                    }
                )
                headers += cycle.headers_sent
                requests += cycle.requests_seen
                responses += cycle.responses_prepared
                finished += cycle.finished_seen
                qualified += cycle.finished_qualified
                timeouts += cycle.transport_timeouts
                transport_failure_categories.update(
                    {
                        name: count
                        for name, count in cycle.transport_failure_categories
                        if name in TRANSPORT_FAILURE_CATEGORIES and type(count) is int and count > 0
                    }
                )
                finished_categories.update(
                    {
                        name: count
                        for name, count in cycle.finished_categories
                        if name in FINISHED_CATEGORIES and type(count) is int and count > 0
                    }
                )
                diagnostic_names = {name for name, count in cycle.diagnostics if count}
                if "unsupported_stage" in diagnostic_names:
                    stopped = "unsupported_stage"
                    break
                if diagnostic_names - {"transport_failure", "transport_timeout"}:
                    stopped = "diagnostic_failure"
                    break
                if qualified >= stop_after_finished:
                    stopped = "finished_target"
                    break
                if _has_transport_failure(cycle):
                    failures += 1
                    consecutive_failures += 1
                    if consecutive_failures >= self._max_failures:
                        stopped = "failure_limit"
                        break
                    requested_delay = self._backoff_seconds * (2 ** (consecutive_failures - 1))
                    deadline = self._clock() + requested_delay
                    self._sleep(max(0.0, deadline - self._clock()))
                elif _has_transport_timeout(cycle):
                    # A long-poll timeout is an idle observation, not a
                    # successful payload and not a retryable failure.
                    pass
                else:
                    successes += 1
                    consecutive_failures = 0
                if self._clock() - started >= max_wall_seconds:
                    stopped = "wall_limit_unfinished"
                    break
        except KeyboardInterrupt:
            stopped = "interrupted"
        return RunnerSummary(
            cycles,
            successes,
            failures,
            headers,
            requests,
            responses,
            finished,
            qualified,
            stopped,
            tuple(sorted(diagnostics.items())),
            tuple(sorted(diagnostic_details.items())),
            tuple(sorted(diagnostic_profiles.items())),
            timeouts,
            tuple(sorted(transport_failure_categories.items())),
            tuple(sorted(finished_categories.items())),
        )


def _has_transport_failure(cycle: ConnectorCycle) -> bool:
    return any(name == "transport_failure" and count for name, count in cycle.diagnostics)


def _has_transport_timeout(cycle: ConnectorCycle) -> bool:
    return any(name == "transport_timeout" and count for name, count in cycle.diagnostics)


def build_foreground_runner(
    config: RuntimeConfig,
    transport: Transport,
    *,
    agent_mode: str = "rule",
    agent_factory_builder: Callable[[str], Callable[[int], object]] = build_agent_factory,
    prepared_agent_factory: Callable[[int], object] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ForegroundRunner:
    if agent_mode == "rule":
        handler = NoTributeRuleBasedHandler()
    elif agent_mode == "deepseek":
        handler = NoTributeRuleBasedHandler(
            prepared_agent_factory or agent_factory_builder(agent_mode),
            fallback_to_rule=True,
            cache_agents=True,
        )
    else:
        raise ValueError("invalid_agent_mode")
    connector = MockConnector(SessionStore(config.state_directory), transport, handler)
    return ForegroundRunner(
        connector,
        max_consecutive_failures=config.max_consecutive_failures,
        backoff_seconds=config.backoff_seconds,
        sleep=sleep,
        clock=clock,
    )


def exit_code_for(summary: RunnerSummary) -> int:
    """Stable foreground categories: success, interrupt, transport, protocol, limit."""

    if summary.stopped == "finished_target" and summary.finished_qualified > 0:
        return 0
    if summary.stopped == "interrupted":
        return 130
    if summary.stopped == "failure_limit":
        return 4
    if summary.stopped in {"unsupported_stage", "diagnostic_failure"}:
        return 5
    return 6


def write_audit(path: Path | str, summary: RunnerSummary, exit_code: int) -> None:
    """Atomically write only deterministic, non-sensitive smoke aggregates."""

    target = Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    if not target.is_absolute() or target.is_relative_to(root):
        raise ValueError("invalid_audit_path")
    payload = {
        "schema": "botzone_local_smoke_audit",
        "version": 5,
        "exit_code": exit_code,
        "stop_reason": summary.stopped,
        "cycles": summary.cycles,
        "successful_cycles": summary.successful_cycles,
        "transport_failures": summary.transport_failures,
        "transport_timeouts": summary.transport_timeouts,
        "transport_failure_categories": [[name, count] for name, count in summary.transport_failure_categories],
        "headers_sent": summary.headers_sent,
        "requests_seen": summary.requests_seen,
        "responses_prepared": summary.responses_prepared,
        "finished_seen": summary.finished_seen,
        "finished_qualified": summary.finished_qualified,
        "finished_categories": [[name, count] for name, count in summary.finished_categories],
        "diagnostics": [[name, count] for name, count in summary.diagnostics],
        "diagnostic_details": [[name, count] for name, count in summary.diagnostic_details],
        "diagnostic_profiles": [[name, count] for name, count in summary.diagnostic_profiles],
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        try:
            if "temporary" in locals() and temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        raise ValueError("audit_write_failed") from None
