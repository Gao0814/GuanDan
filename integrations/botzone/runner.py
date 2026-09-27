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
from .history import ConnectorObservedHistory
from .decision_trace import ConnectorDecisionTrace
from .game_results import GameResultRecorder
from .rolling_results import CompositeGameResultRecorder, RollingGameResultRecorder
from .rolling_results import RECENT_RESULT_CATEGORIES
from .agent_observability import AgentObservabilityRecorder, AgentObservabilitySnapshot
from .agent_runtime import build_agent_factory
from .play_adapter import NoTributeRuleBasedHandler
from .poll import ENVELOPE_SHAPE_DETAILS, REQUIRED_FIELDS_PROFILES
from .result_observability import ResultObservabilitySnapshot
from .runtime_config import RuntimeConfig
from .run_provenance import RunProvenanceError, TOKEN_AUDIT_VERSION, validate_run_token
from .session import SessionStore
from .stage_trace import StageTraceSink, record_stage


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
    history_status: str = "disabled"
    decision_trace_status: str = "disabled"
    game_results_status: str = "disabled"
    game_results_recorded: int = 0
    recent_results_status: str = "disabled"
    recent_results_capacity: int = 0
    recent_results_total_games: int = 0
    recent_results_retained_count: int = 0
    recent_results_category_counts: tuple[tuple[str, int], ...] = ()
    recent_results_snapshot_valid: bool = True


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
        run_token: str | None = None,
        stage_trace: StageTraceSink | None = None,
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
        self._stage_trace = stage_trace
        try:
            self._run_token = None if run_token is None else validate_run_token(run_token)
        except RunProvenanceError as exc:
            raise ValueError("invalid_run_token") from exc

    @property
    def run_token(self) -> str | None:
        return self._run_token

    def run(
        self,
        *,
        max_cycles: int | None = 100,
        max_wall_seconds: int | None = 600,
        stop_after_finished: int | None = 1,
        retry_network_failures: bool = False,
    ) -> RunnerSummary:
        if any(
            value is not None and (type(value) is not int or value <= 0)
            for value in (max_cycles, max_wall_seconds, stop_after_finished)
        ) or type(retry_network_failures) is not bool:
            raise ValueError("invalid_runner_limit")
        cycles = successes = failures = headers = requests = responses = finished = qualified = timeouts = 0
        consecutive_failures = 0
        diagnostics: Counter[str] = Counter()
        diagnostic_details: Counter[str] = Counter()
        diagnostic_profiles: Counter[str] = Counter()
        transport_failure_categories: Counter[str] = Counter()
        finished_categories: Counter[str] = Counter()
        stopped = "cycle_limit_unfinished" if max_cycles is not None else "interrupted"
        started = self._clock()
        try:
            while max_cycles is None or cycles < max_cycles:
                if max_wall_seconds is not None and self._clock() - started >= max_wall_seconds:
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
                if stop_after_finished is not None and qualified >= stop_after_finished:
                    stopped = "finished_target"
                    break
                if _has_transport_failure(cycle):
                    failures += 1
                    consecutive_failures += 1
                    if retry_network_failures:
                        transport_categories = {name for name, count in cycle.transport_failure_categories if count}
                        if not transport_categories or transport_categories - {"network_error"}:
                            stopped = "transport_failure"
                            break
                        if max_cycles is not None and cycles >= max_cycles:
                            stopped = "cycle_limit_unfinished"
                            break
                        if max_wall_seconds is not None and self._clock() - started >= max_wall_seconds:
                            stopped = "wall_limit_unfinished"
                            break
                        requested_delay = min(self._backoff_seconds * (2 ** min(consecutive_failures - 1, 6)), 60)
                        deadline = self._clock() + requested_delay
                        self._sleep(max(0.0, deadline - self._clock()))
                        continue
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
                if max_wall_seconds is not None and self._clock() - started >= max_wall_seconds:
                    stopped = "wall_limit_unfinished"
                    break
        except KeyboardInterrupt:
            stopped = "interrupted"
        self._close_game_results()
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
        recent_status = self._recent_results_status()
        recent_snapshot_valid = True
        try:
            recent_snapshot = self._recent_results_snapshot()
            recent_capacity = getattr(recent_snapshot, "capacity", 0) if recent_snapshot is not None else 0
            recent_total = getattr(recent_snapshot, "total_games", 0) if recent_snapshot is not None else 0
            recent_retained = getattr(recent_snapshot, "retained_count", 0) if recent_snapshot is not None else 0
            recent_counts = getattr(recent_snapshot, "result_category_counts", ()) if recent_snapshot is not None else ()
            if recent_snapshot is None and recent_status != "disabled":
                raise ValueError("recent_results_unavailable")
            if recent_snapshot is not None and (
                type(recent_capacity) is not int
                or recent_capacity <= 0
                or type(recent_total) is not int
                or recent_total < 0
                or type(recent_retained) is not int
                or recent_retained < 0
                or recent_retained > recent_capacity
                or recent_total < recent_retained
                or not isinstance(recent_counts, tuple)
                or sum(count for _, count in recent_counts) != recent_retained
            ):
                raise ValueError("recent_results_invalid")
        except Exception:
            recent_snapshot_valid = False
            recent_capacity = recent_total = recent_retained = 0
            recent_counts = ()
        summary = RunnerSummary(
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
            self._history_status(),
            self._decision_trace_status(),
            self._game_results_status(qualified),
            self._game_results_recorded(),
            recent_status,
            recent_capacity,
            recent_total,
            recent_retained,
            recent_counts,
            recent_snapshot_valid,
        )
        record_stage(self._stage_trace, "runner_exit", summary.stopped)
        return summary

    def _history_status(self) -> str:
        status = getattr(self._connector, "history_status", "disabled")
        return status if status in {"disabled", "ok", "failed"} else "failed"

    def _decision_trace_status(self) -> str:
        status = getattr(self._connector, "decision_trace_status", "disabled")
        return status if status in {"disabled", "ok", "failed"} else "failed"

    def _close_game_results(self) -> None:
        close = getattr(self._connector, "close_game_results", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _game_results_recorded(self) -> int:
        value = getattr(self._connector, "game_results_recorded", 0)
        return value if type(value) is int and value >= 0 else 0

    def _recent_results_status(self) -> str:
        status = getattr(self._connector, "recent_results_status", "disabled")
        return status if status in {"disabled", "ok", "failed"} else "failed"

    def _recent_results_snapshot(self) -> object | None:
        snapshot = getattr(self._connector, "recent_results_snapshot", None)
        return snapshot() if callable(snapshot) else None

    def _game_results_status(self, qualified: int) -> str:
        status = getattr(self._connector, "game_results_status", "disabled")
        if status not in {"disabled", "ok", "failed"}:
            return "failed"
        if status == "ok" and self._game_results_recorded() != qualified:
            return "failed"
        return status


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
    run_token: str | None = None,
    history_file: Path | str | None = None,
    decision_trace_file: Path | str | None = None,
    game_results_file: Path | str | None = None,
    recent_results_file: Path | str | None = None,
    recent_results_capacity: int | None = None,
    stage_trace: StageTraceSink | None = None,
) -> ForegroundRunner:
    observability = AgentObservabilityRecorder()
    if agent_mode == "rule":
        handler = NoTributeRuleBasedHandler(
            agent_mode="rule",
            observability=observability,
            decision_trace_enabled=decision_trace_file is not None,
        )
    elif agent_mode == "deepseek":
        if prepared_agent_factory is not None:
            agent_factory = prepared_agent_factory
        elif stage_trace is not None and agent_factory_builder is build_agent_factory:
            agent_factory = agent_factory_builder(agent_mode, stage_trace=stage_trace)
        else:
            agent_factory = agent_factory_builder(agent_mode)
        handler = NoTributeRuleBasedHandler(
            agent_factory,
            fallback_to_rule=True,
            cache_agents=True,
            agent_mode="deepseek",
            observability=observability,
            decision_trace_enabled=decision_trace_file is not None,
        )
    elif agent_mode == "conditional_pressure_pass":
        handler = NoTributeRuleBasedHandler(
            prepared_agent_factory or agent_factory_builder(agent_mode),
            fallback_to_rule=False,
            cache_agents=True,
            agent_mode="conditional_pressure_pass",
            observability=observability,
            decision_trace_enabled=decision_trace_file is not None,
        )
    else:
        raise ValueError("invalid_agent_mode")
    recorder = ConnectorObservedHistory(history_file) if history_file is not None else None
    decision_trace_recorder = ConnectorDecisionTrace(decision_trace_file) if decision_trace_file is not None else None
    if (recent_results_file is None) != (recent_results_capacity is None):
        raise ValueError("invalid_recent_results_configuration")
    game_result_recorder = GameResultRecorder(game_results_file) if game_results_file is not None else None
    if recent_results_file is not None and recent_results_capacity is not None:
        recent_recorder = RollingGameResultRecorder(recent_results_file, recent_results_capacity)
        if game_result_recorder is not None:
            game_result_recorder = CompositeGameResultRecorder(game_result_recorder, recent_recorder)
        else:
            game_result_recorder = recent_recorder
    connector = MockConnector(
        SessionStore(
            config.state_directory,
            run_token=run_token,
            decision_trace_enabled=decision_trace_file is not None,
        ),
        transport,
        handler,
        history_recorder=recorder,
        decision_trace_recorder=decision_trace_recorder,
        game_result_recorder=game_result_recorder,
        stage_trace=stage_trace,
        decision_timeout_seconds=getattr(config, "decision_timeout_seconds", None),
        clock=clock,
    )
    return ForegroundRunner(
        connector,
        max_consecutive_failures=config.max_consecutive_failures,
        backoff_seconds=config.backoff_seconds,
        sleep=sleep,
        clock=clock,
        observability_snapshot=handler.observability_snapshot,
        result_observability_snapshot=connector.result_observability_snapshot,
        agent_mode=agent_mode,
        run_token=run_token,
        stage_trace=stage_trace,
    )


def exit_code_for(summary: RunnerSummary) -> int:
    """Stable foreground categories: success, interrupt, transport, protocol, limit."""

    if summary.stopped == "finished_target" and summary.finished_qualified > 0:
        return 0
    if summary.stopped == "interrupted":
        return 130
    if summary.stopped in {"failure_limit", "transport_failure"}:
        return 4
    if summary.stopped in {"unsupported_stage", "diagnostic_failure"}:
        return 5
    return 6


def write_audit(path: Path | str, summary: RunnerSummary, exit_code: int, *, run_token: str | None = None) -> None:
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
    _validate_recent_results(summary)
    try:
        validated_token = None if run_token is None else validate_run_token(run_token)
    except RunProvenanceError as exc:
        raise ValueError("invalid_run_token") from exc
    payload = {
        "schema": "botzone_local_smoke_audit",
        "version": TOKEN_AUDIT_VERSION if validated_token is not None else 7,
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
        "result_category_scope": "current_run_cumulative",
        "diagnostics": [[name, count] for name, count in summary.diagnostics],
        "diagnostic_details": [[name, count] for name, count in summary.diagnostic_details],
        "diagnostic_profiles": [[name, count] for name, count in summary.diagnostic_profiles],
        **snapshot.to_json(),
        **result_snapshot.to_json(),
    }
    if summary.recent_results_status != "disabled":
        recent_window: dict[str, object] = {
            "scope": "retained_window",
            "status": summary.recent_results_status,
            "valid": summary.recent_results_snapshot_valid,
        }
        if summary.recent_results_snapshot_valid:
            recent_window.update(
                {
                    "capacity": summary.recent_results_capacity,
                    "total_games": summary.recent_results_total_games,
                    "retained_count": summary.recent_results_retained_count,
                    "result_category_counts": [
                        [name, count] for name, count in summary.recent_results_category_counts
                    ],
                }
            )
        payload["recent_results_window"] = recent_window
    if validated_token is not None:
        payload["run_token"] = validated_token
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


def _validate_recent_results(summary: RunnerSummary) -> None:
    if summary.recent_results_status not in {"disabled", "ok", "failed"}:
        raise ValueError("invalid_audit_summary")
    if type(summary.recent_results_snapshot_valid) is not bool:
        raise ValueError("invalid_audit_summary")
    if summary.recent_results_status == "disabled":
        if (
            summary.recent_results_capacity != 0
            or summary.recent_results_total_games != 0
            or summary.recent_results_retained_count != 0
            or summary.recent_results_category_counts
            or not summary.recent_results_snapshot_valid
        ):
            raise ValueError("invalid_audit_summary")
        return
    if not summary.recent_results_snapshot_valid:
        if summary.recent_results_category_counts:
            raise ValueError("invalid_audit_summary")
        return
    if (
        type(summary.recent_results_capacity) is not int
        or summary.recent_results_capacity <= 0
        or type(summary.recent_results_total_games) is not int
        or summary.recent_results_total_games < 0
        or type(summary.recent_results_retained_count) is not int
        or not 0 <= summary.recent_results_retained_count <= summary.recent_results_capacity
        or summary.recent_results_total_games < summary.recent_results_retained_count
    ):
        raise ValueError("invalid_audit_summary")
    _validate_pairs(summary.recent_results_category_counts, RECENT_RESULT_CATEGORIES)
    if sum(count for _, count in summary.recent_results_category_counts) != summary.recent_results_retained_count:
        if summary.recent_results_retained_count != 0 or summary.recent_results_category_counts:
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
