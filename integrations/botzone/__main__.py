"""Explicit foreground entry point for a manually configured local-AI URL."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import os
from pathlib import Path
import re
import stat
import sys

from .agent_runtime import prepare_agent_factory
from .game_evidence import GameEvidenceError
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


def _is_reparse_point(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


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


def _game_results_path(
    value: str | None,
    *,
    state_directory: Path,
    audit_file: str | None,
    history_file: Path | None,
    decision_trace_file: Path | None,
) -> Path | None:
    """Validate the optional append-only batch result path."""

    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError("invalid_game_results_path")
    if os.path.lexists(candidate):
        raise ValueError("invalid_game_results_path")
    target = candidate.resolve()
    project_root = Path(__file__).resolve().parents[2]
    audit_target = Path(audit_file).resolve() if audit_file is not None else None
    if (
        os.path.normcase(os.path.abspath(candidate)) != os.path.normcase(str(target))
        or target.is_relative_to(project_root)
        or target.is_relative_to(state_directory.resolve())
        or _paths_overlap(target, audit_target)
        or _paths_overlap(target, history_file)
        or _paths_overlap(target, decision_trace_file)
        or target.exists()
    ):
        raise ValueError("invalid_game_results_path")
    return target


def _recent_results_path(
    value: str | None,
    *,
    recent_results_capacity: int | None,
    state_directory: Path,
    audit_file: str | None,
    history_file: Path | None,
    decision_trace_file: Path | None,
    game_results_file: Path | None,
) -> Path | None:
    if value is None:
        if recent_results_capacity is not None:
            raise ValueError("invalid_recent_results_path")
        return None
    if type(recent_results_capacity) is not int or recent_results_capacity <= 0:
        raise ValueError("invalid_recent_results_capacity")
    candidate = Path(value)
    if not candidate.is_absolute() or not os.path.lexists(candidate):
        raise ValueError("invalid_recent_results_path")
    try:
        info = candidate.lstat()
        target = candidate.resolve(strict=True)
    except OSError:
        raise ValueError("invalid_recent_results_path") from None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag):
        raise ValueError("invalid_recent_results_path")
    project_root = Path(__file__).resolve().parents[2]
    audit_target = Path(audit_file).resolve() if audit_file is not None else None
    others = (audit_target, history_file, decision_trace_file, game_results_file)
    if (
        os.path.normcase(os.path.abspath(candidate)) != os.path.normcase(str(target))
        or target.is_relative_to(project_root)
        or target.is_relative_to(state_directory.resolve())
        or any(_paths_overlap(target, other) for other in others)
    ):
        raise ValueError("invalid_recent_results_path")
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
    parser.add_argument("--max-cycles", type=int)
    parser.add_argument("--max-wall-seconds", type=int)
    parser.add_argument("--stop-after-finished", type=int)
    parser.add_argument("--continuous", action="store_true", help="poll until interruption, explicit limit, or fixed-category failure")
    parser.add_argument("--audit-file")
    parser.add_argument("--history-file", help="optional UTF-8 connector-observed history artifact")
    parser.add_argument("--decision-trace-file", help="optional acknowledged-local-decision JSON artifact")
    parser.add_argument("--game-results-file", help="optional low-sensitivity per-finished-game JSONL artifact")
    parser.add_argument("--recent-results-file", help="managed rolling results state file")
    parser.add_argument("--recent-results-capacity", type=int, help="number of newest result records to retain")
    parser.add_argument(
        "--manual-game-evidence-dir",
        help="owner batch only: managed per-game evidence directory under the fixed workspace",
    )
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
        game_results_file = _game_results_path(
            arguments.game_results_file,
            state_directory=config.state_directory,
            audit_file=arguments.audit_file,
            history_file=history_file,
            decision_trace_file=decision_trace_file,
        )
        recent_results_file = _recent_results_path(
            arguments.recent_results_file,
            recent_results_capacity=arguments.recent_results_capacity,
            state_directory=config.state_directory,
            audit_file=arguments.audit_file,
            history_file=history_file,
            decision_trace_file=decision_trace_file,
            game_results_file=game_results_file,
        )
        game_evidence_directory = _manual_game_evidence_path(
            arguments.manual_game_evidence_dir,
            agent=arguments.agent,
            continuous=arguments.continuous,
            recent_results_file=recent_results_file,
            state_directory=config.state_directory,
            audit_file=arguments.audit_file,
            history_file=history_file,
            game_results_file=game_results_file,
        )
        game_evidence_recorder = None
        if game_evidence_directory is not None:
            from .game_evidence import ManualGameEvidenceRecorder

            game_evidence_recorder = ManualGameEvidenceRecorder(game_evidence_directory)
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
            game_results_file=game_results_file,
            recent_results_file=recent_results_file,
            recent_results_capacity=arguments.recent_results_capacity if recent_results_file is not None else None,
            game_evidence_recorder=game_evidence_recorder,
            stage_trace=stage_trace,
        )
        max_cycles = arguments.max_cycles if arguments.continuous or arguments.max_cycles is not None else 100
        max_wall_seconds = arguments.max_wall_seconds if arguments.continuous or arguments.max_wall_seconds is not None else 600
        stop_after_finished = (
            arguments.stop_after_finished
            if arguments.continuous or arguments.stop_after_finished is not None
            else 1
        )
        summary = runner.run(
            max_cycles=max_cycles,
            max_wall_seconds=max_wall_seconds,
            stop_after_finished=stop_after_finished,
            retry_network_failures=arguments.continuous,
        )
        exit_code = exit_code_for(summary)
        if exit_code == 0 and getattr(summary, "game_evidence_status", "disabled") == "failed":
            exit_code = 7
        if arguments.audit_file is not None:
            if runner.run_token != run_token:
                raise ValueError("run_token_mismatch")
            write_audit(arguments.audit_file, summary, exit_code, run_token=run_token)
        record_stage(stage_trace, "connector_exit", getattr(summary, "stopped", "diagnostic_failure"))
    except GameEvidenceError as error:
        record_stage(stage_trace, "connector_exit", "evidence_incomplete")
        print(f"evidence_incomplete category={error.category}")
        return 7
    except (RuntimeConfigError, ValueError) as error:
        record_stage(stage_trace, "connector_exit", "configuration_error")
        print(_configuration_output(preflight_only=arguments.preflight_only, stage=stage, error=error))
        return 2
    print(
        f"connector_finished cycles={summary.cycles} finished={summary.finished_seen} "
        f"history={getattr(summary, 'history_status', 'disabled')} "
        f"decision_trace={getattr(summary, 'decision_trace_status', 'disabled')}"
        f"{_game_results_summary(summary)}{_game_evidence_summary(summary)} exit={exit_code}"
    )
    return exit_code


def _game_results_summary(summary: object) -> str:
    status = getattr(summary, "game_results_status", "disabled")
    if status not in {"ok", "failed"}:
        return ""
    count = getattr(summary, "game_results_recorded", 0)
    if type(count) is not int or count < 0:
        count = 0
    return f" game_results={status} game_results_recorded={count}"


def _game_evidence_summary(summary: object) -> str:
    status = getattr(summary, "game_evidence_status", "disabled")
    if status not in {"ok", "failed"}:
        return ""
    if status == "failed":
        category = getattr(summary, "game_evidence_error_category", None)
        if not isinstance(category, str) or re.fullmatch(r"evidence_[a-z_]+", category) is None:
            category = "evidence_write_failed"
        print(f"evidence_incomplete category={category}")
    return f" game_evidence={status}"


def _manual_game_evidence_path(
    value: str | None,
    *,
    agent: str,
    continuous: bool,
    recent_results_file: Path | None,
    state_directory: Path,
    audit_file: str | None,
    history_file: Path | None,
    game_results_file: Path | None,
) -> Path | None:
    """Constrain full-request evidence to the explicit continuous batch layout."""

    if value is None:
        return None
    if agent != "deepseek" or not continuous or recent_results_file is None:
        raise ValueError("invalid_manual_game_evidence_mode")
    # This option is deliberately narrower than the ordinary CLI artifacts:
    # only the owner batch's fixed workspace may receive complete model bodies.
    from .manual_batch import DEFAULT_WORKSPACE_ROOT

    candidate = Path(value)
    if not candidate.is_absolute() or candidate.name != "games" or not os.path.lexists(candidate):
        raise ValueError("invalid_manual_game_evidence_path")
    try:
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        workspace_candidate = Path(DEFAULT_WORKSPACE_ROOT)
        workspace_info = workspace_candidate.lstat()
        workspace_root = workspace_candidate.resolve(strict=True)
        results_root = recent_results_file.parent.parent.resolve(strict=True)
        candidate_absolute = Path(os.path.abspath(candidate))
        expected_recent_results = workspace_root / "manual-batch-records" / "recent-games.json"
        actual_recent_results = recent_results_file.resolve(strict=True)
    except OSError:
        raise ValueError("invalid_manual_game_evidence_path") from None
    project_root = Path(__file__).resolve().parents[2]
    audit_target = Path(audit_file).resolve() if audit_file is not None else None
    if (
        not stat.S_ISDIR(info.st_mode)
        or _is_reparse_point(info)
        or not stat.S_ISDIR(workspace_info.st_mode)
        or _is_reparse_point(workspace_info)
        or os.path.normcase(str(candidate_absolute)) != os.path.normcase(str(resolved))
        or results_root != workspace_root
        or actual_recent_results != expected_recent_results
        or resolved.parent != workspace_root
        or resolved.is_relative_to(project_root)
        or resolved.is_relative_to(state_directory.resolve())
        or _paths_overlap(resolved, audit_target)
        or _paths_overlap(resolved, history_file)
        or _paths_overlap(resolved, game_results_file)
    ):
        raise ValueError("invalid_manual_game_evidence_path")
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
