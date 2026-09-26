"""Explicit foreground entry point for a manually configured local-AI URL."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
import sys

from .agent_runtime import prepare_agent_factory
from .http_transport import LocalAIHttpTransport
from .runner import build_foreground_runner, exit_code_for, write_audit
from .run_provenance import RunProvenanceError, validate_run_token
from .runtime_config import RuntimeConfigError, load_runtime_config, preflight_state_directory
from .stage_trace import StageTrace, record_stage


_RUNTIME_PREFLIGHT_OUTPUTS = {
    "missing_configuration": "preflight_runtime_config_missing",
    "invalid_configuration": "preflight_runtime_config_url_invalid",
    "invalid_timeout": "preflight_runtime_config_timeout_invalid",
    "invalid_response_limit": "preflight_runtime_config_response_limit_invalid",
    "invalid_failure_limit": "preflight_runtime_config_failure_limit_invalid",
    "invalid_backoff": "preflight_runtime_config_backoff_invalid",
    "decision_budget_pair_required": "preflight_decision_budget_pair_required",
    "decision_budget_requires_deepseek": "preflight_decision_budget_requires_deepseek",
    "invalid_decision_timeout": "preflight_decision_timeout_invalid",
    "invalid_table_timeout": "preflight_table_timeout_invalid",
    "decision_table_margin_insufficient": "preflight_decision_table_margin_insufficient",
}


def _paths_overlap(first: Path, second: Path | None) -> bool:
    return second is not None and (
        first == second or first.is_relative_to(second) or second.is_relative_to(first)
    )


def _history_path(
    value: str | None,
    *,
    state_directory: Path,
    audit_file: str | None,
    other_file: Path | None = None,
) -> Path | None:
    """Preserve the established direct-CLI history path interpretation."""

    if value is None:
        return None
    target = Path(value).resolve()
    project_root = Path(__file__).resolve().parents[2]
    audit_target = Path(audit_file).resolve() if audit_file is not None else None
    if (
        target.is_relative_to(project_root)
        or target.is_relative_to(state_directory.resolve())
        or target == audit_target
        or _paths_overlap(target, other_file)
    ):
        raise ValueError("invalid_history_path")
    return target


def _decision_trace_path(
    value: str | None,
    *,
    state_directory: Path,
    audit_file: str | None,
    history_file: Path | None,
) -> Path | None:
    """Require the new private trace artifact to use an explicit external path."""

    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError("invalid_decision_trace_path")
    target = candidate.resolve()
    project_root = Path(__file__).resolve().parents[2]
    audit_target = Path(audit_file).resolve() if audit_file is not None else None
    if (
        target.is_relative_to(project_root)
        or target.is_relative_to(state_directory.resolve())
        or _paths_overlap(target, audit_target)
        or _paths_overlap(target, history_file)
    ):
        raise ValueError("invalid_decision_trace_path")
    return target


def _configuration_output(*, preflight_only: bool, stage: str, error: BaseException) -> str:
    """Return a fixed public category without exposing exception text."""

    if not preflight_only:
        return "configuration_error"
    if stage == "runtime_config" and isinstance(error, RuntimeConfigError):
        return _RUNTIME_PREFLIGHT_OUTPUTS.get(error.category, "preflight_configuration_error")
    if stage == "state_preflight" and isinstance(error, RuntimeConfigError):
        if error.category == "invalid_state_directory":
            return "preflight_state_directory_invalid"
        if error.category == "state_preflight_failed":
            return "preflight_state_operation_failed"
    if stage == "agent_composition":
        return "preflight_agent_composition_failed"
    return "preflight_configuration_error"


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m integrations.botzone",
        description="Exit codes: 0 finished/preflight, 2 configuration, 4 transport, 5 protocol, 6 limit, 130 interrupt.",
    )
    parser.add_argument("--url")
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout-seconds", default=30)
    parser.add_argument(
        "--decision-timeout-seconds",
        help="optional end-to-end DeepSeek decision budget, bounded separately from poll read timeout",
    )
    parser.add_argument(
        "--table-timeout-seconds",
        help="table turn limit used to validate the decision budget's one-second gap",
    )
    parser.add_argument("--agent", choices=("rule", "deepseek", "conditional_pressure_pass"), default="rule")
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-wall-seconds", type=int, default=600)
    parser.add_argument("--stop-after-finished", type=int, default=1)
    parser.add_argument("--audit-file")
    parser.add_argument("--history-file", help="optional UTF-8 connector-observed history artifact")
    parser.add_argument("--decision-trace-file", help="optional acknowledged-local-decision JSON artifact")
    parser.add_argument("--run-token")
    parser.add_argument("--preflight-only", action="store_true", help="validate configuration and storage without polling")
    parser.add_argument(
        "--stage-trace",
        action="store_true",
        help="emit fixed low-sensitivity connector stages to stdout",
    )
    arguments = parser.parse_args(argv)
    stage_trace = StageTrace(sys.stdout) if arguments.stage_trace and not arguments.preflight_only else None
    if stage_trace is not None:
        record_stage(stage_trace, "connector_start", "started")
    stage = "runtime_config"
    try:
        run_token = None
        if not arguments.preflight_only and arguments.run_token is not None:
            try:
                run_token = validate_run_token(arguments.run_token)
            except RunProvenanceError as exc:
                raise ValueError("invalid_run_token") from exc
        if (
            arguments.decision_timeout_seconds is not None
            or arguments.table_timeout_seconds is not None
        ) and arguments.agent != "deepseek":
            raise RuntimeConfigError("decision_budget_requires_deepseek")
        config = load_runtime_config(
            local_ai_url=arguments.url,
            state_directory=arguments.state_dir,
            timeout_seconds=arguments.timeout_seconds,
            decision_timeout_seconds=arguments.decision_timeout_seconds,
            table_timeout_seconds=arguments.table_timeout_seconds,
            environ=environ,
        )
        stage = "state_preflight"
        preflight_state_directory(config)
        stage = "agent_composition"
        prepared_agent_factory = prepare_agent_factory(arguments.agent, stage_trace=stage_trace)
        if arguments.preflight_only:
            print("preflight_ready")
            return 0
        history_file = _history_path(
            arguments.history_file,
            state_directory=config.state_directory,
            audit_file=arguments.audit_file,
        )
        decision_trace_file = _decision_trace_path(
            arguments.decision_trace_file,
            state_directory=config.state_directory,
            audit_file=arguments.audit_file,
            history_file=history_file,
        )
        if decision_trace_file is not None and decision_trace_file.exists():
            raise ValueError("decision_trace_output_exists")
        runner = build_foreground_runner(
            config,
            LocalAIHttpTransport(
                config.local_ai_url,
                timeout_seconds=config.timeout_seconds,
                max_response_bytes=config.max_response_bytes,
            ),
            agent_mode=arguments.agent,
            prepared_agent_factory=prepared_agent_factory,
            run_token=run_token,
            history_file=history_file,
            decision_trace_file=decision_trace_file,
            stage_trace=stage_trace,
        )
        summary = runner.run(
            max_cycles=arguments.max_cycles,
            max_wall_seconds=arguments.max_wall_seconds,
            stop_after_finished=arguments.stop_after_finished,
        )
        exit_code = exit_code_for(summary)
        if arguments.audit_file is not None:
            if runner.run_token != run_token:
                raise ValueError("run_token_mismatch")
            write_audit(arguments.audit_file, summary, exit_code, run_token=run_token)
        record_stage(stage_trace, "connector_exit", getattr(summary, "stopped", "diagnostic_failure"))
    except (RuntimeConfigError, ValueError) as error:
        record_stage(stage_trace, "connector_exit", "configuration_error")
        print(_configuration_output(preflight_only=arguments.preflight_only, stage=stage, error=error))
        return 2
    print(
        f"connector_finished cycles={summary.cycles} finished={summary.finished_seen} "
        f"history={getattr(summary, 'history_status', 'disabled')} "
        f"decision_trace={getattr(summary, 'decision_trace_status', 'disabled')} exit={exit_code}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
