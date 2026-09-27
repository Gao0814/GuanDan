"""Owner-operated, continuous Botzone batch launcher.

This module only prepares an isolated workspace and starts one foreground
connector process.  It never controls the Botzone page or rotates old evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from typing import Callable, Sequence

from .result_observability import RESULT_CATEGORIES


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE_ROOT = Path(r"D:\VsCodeProject\BotzoneWorkspace")
DEEPSEEK_MODEL = "deepseek-flash"
DECISION_TIMEOUT_SECONDS = 119
TABLE_TIMEOUT_SECONDS = 120
POLL_TIMEOUT_SECONDS = 30
CYCLES_PER_GAME = 1_000
WALL_SECONDS_PER_GAME = 3_600
RECORDING_INCOMPLETE_EXIT = 7

_RUNNER_STOP_REASONS = frozenset(
    {
        "finished_target",
        "interrupted",
        "failure_limit",
        "unsupported_stage",
        "diagnostic_failure",
        "cycle_limit_unfinished",
        "wall_limit_unfinished",
    }
)
_CONNECTOR_SUMMARY = re.compile(
    r"^connector_finished cycles=([0-9]+) finished=([0-9]+) "
    r"history=disabled decision_trace=disabled game_results=(ok|failed) "
    r"game_results_recorded=([0-9]+) exit=([0-9]+)$",
    re.MULTILINE,
)


class BatchLaunchError(ValueError):
    """A fixed, low-sensitivity launcher failure with an optional batch path."""

    __slots__ = ("category", "batch_directory", "exit_code")

    def __init__(
        self,
        category: str,
        batch_directory: Path | None = None,
        *,
        exit_code: int = 2,
    ) -> None:
        self.category = category if re.fullmatch(r"[a-z_]+", category) else "launcher_failed"
        self.batch_directory = batch_directory
        self.exit_code = exit_code if type(exit_code) is int else 2
        super().__init__(self.category)


@dataclass(frozen=True, slots=True)
class BatchPaths:
    root: Path
    state: Path
    audit: Path
    results: Path
    stdout: Path
    stderr: Path


@dataclass(frozen=True, slots=True)
class BatchOutcome:
    batch_directory: Path
    requested_games: int
    connector_exit_code: int
    stop_reason: str
    confirmed_finished: int | None
    recorded_games: int
    result_counts: tuple[tuple[str, int], ...]
    game_results_status: str

    @property
    def category(self) -> str:
        if self.stop_reason == "finished_target":
            return "target_reached" if self.game_results_status == "complete" else "target_evidence_incomplete"
        if self.stop_reason == "interrupted":
            return "user_interrupted"
        if self.stop_reason in {"cycle_limit_unfinished", "wall_limit_unfinished"}:
            return "configured_limit_reached"
        return self.stop_reason

    @property
    def exit_code(self) -> int:
        if self.connector_exit_code == 0 and self.game_results_status != "complete":
            return RECORDING_INCOMPLETE_EXIT
        return self.connector_exit_code


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_manual_botzone_batch",
        description=(
            "Start one continuous DeepSeek connector for owner-operated Botzone games. "
            "Wait for the page to show connected, then create and start each table manually."
        ),
    )
    parser.add_argument("--games", type=_positive_int, default=10, help="stop after this many ACK-confirmed four-player finishes (default: 10)")
    parser.add_argument("--max-cycles", type=_positive_int, help="poll-cycle cap (default: 1000 per requested game)")
    parser.add_argument("--max-wall-seconds", type=_positive_int, help="wall-clock cap (default: 3600 seconds per requested game)")
    return parser


def _is_reparse_point(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _assert_ordinary_directory(path: Path, *, category: str) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise BatchLaunchError(category) from None
    if not stat.S_ISDIR(info.st_mode) or _is_reparse_point(info):
        raise BatchLaunchError(category)
    try:
        absolute = Path(os.path.abspath(path))
        resolved = path.resolve(strict=True)
    except OSError:
        raise BatchLaunchError(category) from None
    if os.path.normcase(str(absolute)) != os.path.normcase(str(resolved)):
        raise BatchLaunchError(category)


def _assert_inside(root: Path, child: Path) -> None:
    try:
        resolved_root = root.resolve(strict=True)
        resolved_child = child.resolve(strict=True)
        if not resolved_child.is_relative_to(resolved_root):
            raise BatchLaunchError("workspace_path_invalid")
    except OSError:
        raise BatchLaunchError("workspace_path_invalid") from None


def create_batch_workspace(workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> BatchPaths:
    """Create one fresh child without enumerating or changing existing evidence."""

    root = Path(workspace_root)
    _assert_ordinary_directory(root.parent, category="workspace_unavailable")
    _assert_ordinary_directory(root, category="workspace_unavailable")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_root = root / f"manual-batch-{stamp}-{secrets.token_hex(8)}"
    try:
        batch_root.mkdir()
    except FileExistsError:
        raise BatchLaunchError("workspace_occupied", batch_root) from None
    except OSError:
        raise BatchLaunchError("workspace_prepare_failed", batch_root) from None
    try:
        _assert_ordinary_directory(batch_root, category="workspace_path_invalid")
        _assert_inside(root, batch_root)
        paths = BatchPaths(
            root=batch_root,
            state=batch_root / "state",
            audit=batch_root / "audit",
            results=batch_root / "game-results.jsonl",
            stdout=batch_root / "streams" / "stdout.txt",
            stderr=batch_root / "streams" / "stderr.txt",
        )
        for directory in (paths.state, paths.audit, paths.stdout.parent):
            directory.mkdir()
            _assert_ordinary_directory(directory, category="workspace_prepare_failed")
            _assert_inside(batch_root, directory)
    except BatchLaunchError as exc:
        raise BatchLaunchError(exc.category, batch_root) from None
    except KeyboardInterrupt:
        raise BatchLaunchError("user_interrupted", batch_root, exit_code=130) from None
    except OSError:
        raise BatchLaunchError("workspace_prepare_failed", batch_root) from None
    return paths


def _cli_argv(
    state_directory: Path,
    *,
    preflight: bool,
    games: int = 10,
    max_cycles: int = 0,
    max_wall_seconds: int = 0,
    paths: BatchPaths | None = None,
    run_token: str | None = None,
) -> list[str]:
    argv = [
        sys.executable,
        "-B",
        "-m",
        "integrations.botzone",
        "--agent",
        "deepseek",
        "--state-dir",
        str(state_directory),
        "--timeout-seconds",
        str(POLL_TIMEOUT_SECONDS),
        "--decision-timeout-seconds",
        str(DECISION_TIMEOUT_SECONDS),
        "--table-timeout-seconds",
        str(TABLE_TIMEOUT_SECONDS),
    ]
    if preflight:
        argv.append("--preflight-only")
        return argv
    if paths is None or run_token is None:
        raise BatchLaunchError("launcher_configuration_error")
    argv.extend(
        (
            "--max-cycles",
            str(max_cycles),
            "--max-wall-seconds",
            str(max_wall_seconds),
            "--stop-after-finished",
            str(games),
            "--audit-file",
            str(paths.audit / "completion-audit.json"),
            "--game-results-file",
            str(paths.results),
            "--run-token",
            run_token,
            "--stage-trace",
        )
    )
    return argv


def _connector_probe_argv(launcher_pid: int) -> list[str]:
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$launcherPid = {launcher_pid}; "
        "$connectorProcesses = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop | "
        "Where-Object { $_.ProcessId -ne $launcherPid -and "
        "$_.Name -match '(?i)^(python(?:\\d+(?:\\.\\d+)?)?w?|py)(?:\\.exe)?$' -and "
        "$_.CommandLine -match '(?i)(?:\\s-m\\s+integrations\\.botzone\\b|integrations[\\\\/]botzone[\\\\/]__main__\\.py\\b)' }); "
        "if ($connectorProcesses.Count -gt 0) { 'connector_running' } else { 'connector_absent' }"
    )
    return ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]


def _read_jsonl_results(path: Path) -> tuple[tuple[int, str], ...] | None:
    try:
        info = path.lstat()
        if _is_reparse_point(info) or not stat.S_ISREG(info.st_mode):
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    rows: list[tuple[int, str]] = []
    for expected_no, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            return None
        if (
            not isinstance(record, dict)
            or set(record) != {"game_no", "result", "schema", "version"}
            or type(record.get("game_no")) is not int
            or record["game_no"] != expected_no
            or record.get("schema") != "botzone_manual_batch_game_result"
            or type(record.get("version")) is not int
            or record["version"] != 1
            or not isinstance(record.get("result"), str)
            or record.get("result") not in RESULT_CATEGORIES
        ):
            return None
        rows.append((expected_no, record["result"]))
    return tuple(rows)


def _inspect_batch(
    paths: BatchPaths,
    requested_games: int,
    process_exit: int,
    *,
    interrupted: bool = False,
) -> tuple[str, str, int | None, int, tuple[tuple[str, int], ...]]:
    """Compare this batch's result lines, aggregate audit, and fixed CLI footer."""

    rows = _read_jsonl_results(paths.results)
    recorded = 0 if rows is None else len(rows)
    row_counts = Counter(result for _, result in rows) if rows is not None else Counter()
    try:
        stream_info = paths.stdout.lstat()
        if _is_reparse_point(stream_info) or not stat.S_ISREG(stream_info.st_mode):
            raise OSError
        output = paths.stdout.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        output = ""
    output_lines = set(output.splitlines())
    summaries = list(_CONNECTOR_SUMMARY.finditer(output))

    try:
        audit_path = paths.audit / "completion-audit.json"
        audit_info = audit_path.lstat()
        if _is_reparse_point(audit_info) or not stat.S_ISREG(audit_info.st_mode):
            raise ValueError
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if not isinstance(audit, dict) or audit.get("schema") != "botzone_local_smoke_audit":
            raise ValueError
        finished = audit.get("finished_qualified")
        stop_reason = audit.get("stop_reason")
        audit_exit = audit.get("exit_code")
        if (
            type(finished) is not int
            or finished < 0
            or stop_reason not in _RUNNER_STOP_REASONS
            or type(audit_exit) is not int
        ):
            raise ValueError
        raw_counts = audit.get("result_category_counts")
        if not isinstance(raw_counts, list):
            raise ValueError
        counts: Counter[str] = Counter()
        for pair in raw_counts:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or pair[0] not in RESULT_CATEGORIES
                or type(pair[1]) is not int
                or pair[1] <= 0
            ):
                raise ValueError
            counts[pair[0]] += pair[1]
        if sum(counts.values()) != finished:
            raise ValueError
    except (OSError, ValueError, TypeError):
        if interrupted:
            stop_reason = "interrupted"
        elif "configuration_error" in output_lines:
            stop_reason = "connector_configuration_error"
        elif not summaries:
            stop_reason = "connector_early_exit"
        else:
            stop_reason = "runtime_evidence_unavailable"
        return stop_reason, "incomplete", None, recorded, tuple(sorted(row_counts.items()))

    if rows is None or len(summaries) != 1:
        return stop_reason, "incomplete", finished, recorded, tuple(sorted(row_counts.items()))
    summary = summaries[0]
    summary_status = summary.group(3)
    summary_recorded = int(summary.group(4))
    row_counts = Counter(result for _, result in rows)
    complete = (
        summary_status == "ok"
        and summary_recorded == len(rows)
        and int(summary.group(5)) == process_exit
        and audit_exit == process_exit
        and len(rows) == finished
        and row_counts == counts
        and (process_exit != 0 or (stop_reason == "finished_target" and finished == requested_games))
    )
    return (
        stop_reason,
        "complete" if complete else "incomplete",
        finished,
        len(rows),
        tuple(sorted(row_counts.items())),
    )


def run_batch(
    *,
    games: int = 10,
    max_cycles: int | None = None,
    max_wall_seconds: int | None = None,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
    python_executable: str | None = None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    announce: Callable[[str], None] = print,
) -> BatchOutcome:
    if type(games) is not int or games <= 0:
        raise BatchLaunchError("invalid_game_count")
    if max_cycles is not None and (type(max_cycles) is not int or max_cycles <= 0):
        raise BatchLaunchError("invalid_cycle_limit")
    if max_wall_seconds is not None and (type(max_wall_seconds) is not int or max_wall_seconds <= 0):
        raise BatchLaunchError("invalid_wall_limit")
    cycle_limit = max_cycles if max_cycles is not None else games * CYCLES_PER_GAME
    wall_limit = max_wall_seconds if max_wall_seconds is not None else games * WALL_SECONDS_PER_GAME
    runner = process_runner or subprocess.run
    executable = python_executable or sys.executable
    environment = os.environ.copy()
    environment["DEEPSEEK_MODEL"] = DEEPSEEK_MODEL

    try:
        process_probe = runner(
            _connector_probe_argv(os.getpid()),
            cwd=repository_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except KeyboardInterrupt:
        raise BatchLaunchError("user_interrupted", exit_code=130) from None
    except Exception:
        raise BatchLaunchError("connector_status_unavailable") from None
    if process_probe.returncode != 0 or process_probe.stdout.splitlines() not in (["connector_absent"], ["connector_running"]):
        raise BatchLaunchError("connector_status_unavailable")
    if process_probe.stdout.splitlines() == ["connector_running"]:
        raise BatchLaunchError("connector_already_running")

    paths = create_batch_workspace(workspace_root)
    announce(f"批次目录：{paths.root}")

    preflight_argv = _cli_argv(paths.state, preflight=True)
    preflight_argv[0] = executable
    try:
        preflight = runner(
            preflight_argv,
            cwd=repository_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except KeyboardInterrupt:
        raise BatchLaunchError("user_interrupted", paths.root, exit_code=130) from None
    except Exception:
        raise BatchLaunchError("preflight_failed", paths.root) from None
    if preflight.returncode != 0 or preflight.stdout.splitlines() != ["preflight_ready"]:
        raise BatchLaunchError("preflight_failed", paths.root)

    run_token = secrets.token_hex(16)
    runtime_argv = _cli_argv(
        paths.state,
        preflight=False,
        games=games,
        max_cycles=cycle_limit,
        max_wall_seconds=wall_limit,
        paths=paths,
        run_token=run_token,
    )
    runtime_argv[0] = executable
    announce("零网络配置预检通过。连接器将在前台连续运行；请等页面显示“已连接”后手动逐局建桌并开始。")
    announce("达到局数上限后自动退出；需要提前停止时按 Ctrl+C，已产生的证据会保留。")
    interrupted = False
    try:
        audit_target = paths.audit / "completion-audit.json"
        expected_outputs = (audit_target, paths.results, paths.stdout, paths.stderr)
        if any(os.path.lexists(path) for path in expected_outputs):
            raise BatchLaunchError("workspace_outputs_occupied", paths.root)
        with audit_target.open("x", encoding="utf-8", newline="\n"):
            pass
        with paths.stdout.open("x", encoding="utf-8", newline="\n") as stdout, paths.stderr.open(
            "x", encoding="utf-8", newline="\n"
        ) as stderr:
            try:
                process = runner(
                    runtime_argv,
                    cwd=repository_root,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    check=False,
                )
            except KeyboardInterrupt:
                interrupted = True
                process_code = 130
            except Exception:
                raise BatchLaunchError("connector_launch_failed", paths.root) from None
    except KeyboardInterrupt:
        interrupted = True
        process_code = 130
    except BatchLaunchError:
        raise
    except FileExistsError:
        raise BatchLaunchError("workspace_outputs_occupied", paths.root) from None
    except OSError:
        raise BatchLaunchError("stream_output_unavailable", paths.root) from None
    except Exception:
        raise BatchLaunchError("connector_launch_failed", paths.root) from None
    else:
        if not interrupted:
            process_code = process.returncode if type(process.returncode) is int else 2

    stop_reason, records_status, finished, result_count, result_counts = _inspect_batch(
        paths,
        games,
        process_code,
        interrupted=interrupted,
    )
    outcome = BatchOutcome(paths.root, games, process_code, stop_reason, finished, result_count, result_counts, records_status)
    confirmed = "unknown" if outcome.confirmed_finished is None else str(outcome.confirmed_finished)
    announce(
        f"batch_result category={outcome.category} exit={outcome.exit_code} "
        f"connector_exit={outcome.connector_exit_code} stop={outcome.stop_reason} "
        f"confirmed_finished={confirmed}/{outcome.requested_games} "
        f"game_results={outcome.game_results_status} recorded={outcome.recorded_games} "
        f"batch_directory={outcome.batch_directory}"
    )
    announce("history.txt 与 decision-trace.json 未启用；保留逐局低敏结果、聚合 audit 和阶段 trace。")
    return outcome


def main(
    argv: Sequence[str] | None = None,
    *,
    process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    announce: Callable[[str], None] = print,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
) -> int:
    parser = build_argument_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        outcome = run_batch(
            games=arguments.games,
            max_cycles=arguments.max_cycles,
            max_wall_seconds=arguments.max_wall_seconds,
            workspace_root=workspace_root,
            repository_root=repository_root,
            process_runner=process_runner,
            announce=announce,
        )
        return outcome.exit_code
    except BatchLaunchError as exc:
        batch_path = f" batch_directory={exc.batch_directory}" if exc.batch_directory is not None else ""
        print(f"batch_error category={exc.category} exit={exc.exit_code}{batch_path}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("batch_error category=user_interrupted exit=130", file=sys.stderr)
        return 130
    except Exception:
        print("batch_error category=launcher_failed exit=2", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
