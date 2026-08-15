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
from .agent_observability import AgentObservabilityRecorder, AgentObservabilitySnapshot
from .agent_runtime import build_agent_factory
from .play_adapter import NoTributeRuleBasedHandler
from .poll import ENVELOPE_SHAPE_DETAILS, REQUIRED_FIELDS_PROFILES
from .result_observability import ResultObservabilitySnapshot
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
    agent_mode: str = "rule"
    agent_decision_count: int = 0
    decision_source_counts: tuple[tuple[str, int], ...] = ()
    model_attempt_count: int = 0
    model_outcome_counts: tuple[tuple[str, int], ...] = ()
    rule_fallback_count: int = 0
    observability_valid: bool = True
    result_category_counts: tuple[tuple[str, int], ...] = ()
    normal_result_count: int = 0
    local_team_score_counts: tuple[tuple[str, int], ...] = ()
    result_observability_valid: bool = True


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
        observability_snapshot: Callable[[], AgentObservabilitySnapshot] | None = None,
        result_observability_snapshot: Callable[[], ResultObservabilitySnapshot] | None = None,
        agent_mode: str = "rule",
    ) -> None:
        self._connector = connector
        self._max_failures = max_consecutive_failures
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._clock = clock
        self._observability_snapshot = observability_snapshot
        connector_result_snapshot = getattr(connector, "result_observability_snapshot", None)
        self._result_observability_snapshot = result_observability_snapshot or (
            connector_result_snapshot if callable(connector_result_snapshot) else None
        )
        self._agent_mode = agent_mode

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
        observability_valid = True
        try:
            snapshot = (
                self._observability_snapshot()
                if self._observability_snapshot is not None
                else AgentObservabilitySnapshot(self._agent_mode, 0, (), 0, (), 0)
            )
        except Exception:
            observability_valid = False
            snapshot = AgentObservabilitySnapshot("rule", 0, (), 0, (), 0)
        result_observability_valid = True
        try:
            result_snapshot = (
                self._result_observability_snapshot()
                if self._result_observability_snapshot is not None
                else ResultObservabilitySnapshot((), 0, ())
            )
            if sum(count for _, count in result_snapshot.result_category_counts) != qualified:
                raise ValueError("invalid_result_observability")
        except Exception:
            result_observability_valid = False
            result_snapshot = ResultObservabilitySnapshot((), 0, ())
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
            snapshot.agent_mode,
            snapshot.agent_decision_count,
            snapshot.decision_source_counts,
            snapshot.model_attempt_count,
            snapshot.model_outcome_counts,
            snapshot.rule_fallback_count,
            observability_valid,
            result_snapshot.result_category_counts,
            result_snapshot.normal_result_count,
            result_snapshot.local_team_score_counts,
            result_observability_valid,
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
    observability = AgentObservabilityRecorder()
    if agent_mode == "rule":
        handler = NoTributeRuleBasedHandler(agent_mode="rule", observability=observability)
    elif agent_mode == "deepseek":
        handler = NoTributeRuleBasedHandler(
            prepared_agent_factory or agent_factory_builder(agent_mode),
            fallback_to_rule=True,
            cache_agents=True,
            agent_mode="deepseek",
            observability=observability,
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
        observability_snapshot=handler.observability_snapshot,
        result_observability_snapshot=connector.result_observability_snapshot,
        agent_mode=agent_mode,
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
    if (
        type(exit_code) is not int
        or type(summary.observability_valid) is not bool
        or not summary.observability_valid
        or type(summary.result_observability_valid) is not bool
        or not summary.result_observability_valid
    ):
        raise ValueError("invalid_audit_summary")
    _validate_v5_aggregates(summary)
    snapshot = AgentObservabilitySnapshot(
        summary.agent_mode,
        summary.agent_decision_count,
        summary.decision_source_counts,
        summary.model_attempt_count,
        summary.model_outcome_counts,
        summary.rule_fallback_count,
    )
    result_snapshot = ResultObservabilitySnapshot(
        summary.result_category_counts,
        summary.normal_result_count,
        summary.local_team_score_counts,
    )
    if sum(count for _, count in result_snapshot.result_category_counts) != summary.finished_qualified:
        raise ValueError("invalid_audit_summary")
    payload = {
        "schema": "botzone_local_smoke_audit",
        "version": 7,
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
        **snapshot.to_json(),
        **result_snapshot.to_json(),
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


def _validate_v5_aggregates(summary: RunnerSummary) -> None:
    """Reject malformed caller-provided aggregates before they reach an audit."""

    scalar_values = (
        summary.cycles,
        summary.successful_cycles,
        summary.transport_failures,
        summary.transport_timeouts,
        summary.headers_sent,
        summary.requests_seen,
        summary.responses_prepared,
        summary.finished_seen,
        summary.finished_qualified,
    )
    if (
        not isinstance(summary.stopped, str)
        or any(type(value) is not int or value < 0 for value in scalar_values)
        or summary.finished_qualified > summary.finished_seen
    ):
        raise ValueError("invalid_audit_summary")
    _validate_pairs(summary.transport_failure_categories, TRANSPORT_FAILURE_CATEGORIES)
    _validate_pairs(summary.finished_categories, FINISHED_CATEGORIES)
    _validate_pairs(summary.diagnostic_details, ENVELOPE_SHAPE_DETAILS)
    _validate_pairs(summary.diagnostic_profiles, REQUIRED_FIELDS_PROFILES)
    _validate_pairs(summary.diagnostics, _AUDIT_DIAGNOSTICS)
    if sum(count for _, count in summary.finished_categories) != summary.finished_seen:
        raise ValueError("invalid_audit_summary")


_AUDIT_DIAGNOSTICS = frozenset(
    {
        "atomic_write_failed",
        "corrupt_session",
        "envelope_shape_invalid",
        "header_injection",
        "handler_failure",
        "handler_lifecycle_failure",
        "history_alignment_failed",
        "historical_response_invalid",
        "inner_request_invalid",
        "invalid_play_effect",
        "malformed_request",
        "malformed_handler_result",
        "missing_provenance",
        "poll_malformed",
        "play_without_state",
        "replay_history_invalid",
        "request_json_invalid",
        "session_error",
        "transport_failure",
        "transport_timeout",
        "unsupported_stage",
    }
)


def _validate_pairs(values: object, allowed: frozenset[str]) -> None:
    if not isinstance(values, tuple):
        raise ValueError("invalid_audit_summary")
    previous = ""
    for item in values:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], str)
            or item[0] not in allowed
            or type(item[1]) is not int
            or item[1] <= 0
            or item[0] <= previous
        ):
            raise ValueError("invalid_audit_summary")
        previous = item[0]
