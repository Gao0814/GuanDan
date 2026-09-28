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
from .game_evidence import GameEvidenceError, GAME_EVIDENCE_DIRECTORY, prepare_game_evidence
from .rolling_results import (
    RecentResultsError,
    RecentResultsLock,
    ensure_recent_results_directory,
    prepare_recent_results,
    read_recent_results,
    recent_results_paths,
    write_new_batch_marker,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE_ROOT = Path(r"D:\VsCodeProject\BotzoneWorkspace")
DEEPSEEK_MODEL = "deepseek-flash"
DECISION_TIMEOUT_SECONDS = 119
TABLE_TIMEOUT_SECONDS = 120
POLL_TIMEOUT_SECONDS = 30
RECORDING_INCOMPLETE_EXIT = 7

_RUNNER_STOP_REASONS = frozenset(
    {
        "finished_target",
        "interrupted",
        "failure_limit",
        "transport_failure",
        "unsupported_stage",
        "diagnostic_failure",
        "cycle_limit_unfinished",
        "wall_limit_unfinished",
    }
)
_CONNECTOR_COMMAND_LINE_PATTERN = (
    r'(?i)(?:\s-m\s+"?integrations\.botzone"?(?:\s|$)|'
    r'integrations[\\/]botzone[\\/]__main__\.py\b)'
)
_BATCH_LAUNCHER_COMMAND_LINE_PATTERN = r'(?i)\s-m\s+"?integrations\.botzone\.manual_batch"?(?:\s|$)'
_CONNECTOR_SUMMARY = re.compile(
    r"^connector_finished cycles=([0-9]+) finished=([0-9]+) "
    r"history=disabled decision_trace=disabled game_results=(ok|failed) "
    r"game_results_recorded=([0-9]+)(?: game_evidence=(ok|failed))? exit=([0-9]+)$",
    re.MULTILINE,
)
_EVIDENCE_FAILURE = re.compile(r"^evidence_incomplete category=(evidence_[a-z_]+)$", re.MULTILINE)


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
    recent_results: Path
    recent_lock: Path
    game_evidence: Path


@dataclass(frozen=True, slots=True)
class BatchOutcome:
    batch_directory: Path
    retained_capacity: int
    connector_exit_code: int
    stop_reason: str
    confirmed_finished: int | None
    recorded_games: int
    result_counts: tuple[tuple[str, int], ...]
    game_results_status: str
    recent_results_status: str = "ok"
    recent_results_total_games: int = 0
    recent_results_retained_count: int = 0
    recent_results_capacity: int = 0
    game_evidence_status: str = "incomplete"
    game_evidence_error_category: str | None = None

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
        if self.connector_exit_code == 0 and (
            self.game_results_status != "complete"
            or self.recent_results_status != "ok"
            or self.game_evidence_status != "ok"
        ):
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
    parser.add_argument("--games", type=_positive_int, default=10, help="retain the most recent N per-game evidence directories (default: 10)")
    parser.add_argument("--max-cycles", type=_positive_int, help="explicit poll-cycle stop limit")
    parser.add_argument("--max-wall-seconds", type=_positive_int, help="explicit wall-clock stop limit")
    parser.add_argument("--import-from", help="exact legacy manual-batch directory to import on first migration")
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


def _ensure_workspace_child(parent: Path, name: str) -> Path:
    child = parent / name
    if os.path.lexists(child):
        _assert_ordinary_directory(child, category="workspace_path_invalid")
        _assert_inside(parent, child)
        return child
    try:
        child.mkdir()
    except OSError:
        raise BatchLaunchError("workspace_prepare_failed") from None
    _assert_ordinary_directory(child, category="workspace_path_invalid")
    _assert_inside(parent, child)
    return child


def create_batch_workspace(workspace_root: Path = DEFAULT_WORKSPACE_ROOT) -> BatchPaths:
    """Create a versioned internal run directory; visible game data lives under games/."""

    root = Path(workspace_root)
    _assert_ordinary_directory(root.parent, category="workspace_unavailable")
    _assert_ordinary_directory(root, category="workspace_unavailable")
    runtime = _ensure_workspace_child(root, "runtime")
    versioned = _ensure_workspace_child(runtime, "v2")
    runs = _ensure_workspace_child(versioned, "runs")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_root = runs / f"run-{stamp}-{secrets.token_hex(8)}"
    _, recent_results, recent_lock = recent_results_paths(root)
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
            recent_results=recent_results,
            recent_lock=recent_lock,
            game_evidence=root / GAME_EVIDENCE_DIRECTORY,
        )
        write_new_batch_marker(batch_root)
        for directory in (paths.state, paths.audit, paths.stdout.parent):
            directory.mkdir()
            _assert_ordinary_directory(directory, category="workspace_prepare_failed")
            _assert_inside(batch_root, directory)
    except BatchLaunchError as exc:
        raise BatchLaunchError(exc.category, batch_root) from None
    except RecentResultsError as exc:
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
    paths: BatchPaths | None = None,
    run_token: str | None = None,
    max_cycles: int | None = None,
    max_wall_seconds: int | None = None,
    recent_results_capacity: int = 10,
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
    argv.extend(("--continuous",))
    if max_cycles is not None:
        argv.extend(("--max-cycles", str(max_cycles)))
    if max_wall_seconds is not None:
        argv.extend(("--max-wall-seconds", str(max_wall_seconds)))
    argv.extend(
        (
            "--audit-file",
            str(paths.audit / "completion-audit.json"),
            "--game-results-file",
            str(paths.results),
            "--recent-results-file",
            str(paths.recent_results),
            "--recent-results-capacity",
            str(recent_results_capacity),
            "--manual-game-evidence-dir",
            str(paths.game_evidence),
            "--run-token",
            run_token,
            "--stage-trace",
        )
    )
    return argv


def _connector_probe_argv(launcher_pid: int) -> list[str]:
    launcher_parent_pid = os.getppid()
    venv_launcher_path = ""
    if os.name == "nt" and sys.prefix != sys.base_prefix:
        venv_launcher_path = str(Path(sys.prefix) / "Scripts" / "python.exe")
    quoted_venv_launcher_path = "'" + venv_launcher_path.replace("'", "''") + "'"
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$launcherPid = {launcher_pid}; "
        f"$launcherParentPid = {launcher_parent_pid}; "
        f"$venvLauncherPath = {quoted_venv_launcher_path}; "
        "$processes = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop); "
        "$launcherProcess = $processes | Where-Object { $_.ProcessId -eq $launcherPid } | Select-Object -First 1; "
        "$launcherParent = $processes | Where-Object { $_.ProcessId -eq $launcherParentPid } | Select-Object -First 1; "
        "$ownedProcessIds = @($launcherPid); "
        "if ($venvLauncherPath -ne '' -and $null -ne $launcherProcess -and $null -ne $launcherParent -and "
        "$launcherProcess.ParentProcessId -eq $launcherParentPid -and "
        "[System.String]::Equals($launcherParent.ExecutablePath, $venvLauncherPath, "
        "[System.StringComparison]::OrdinalIgnoreCase) -and "
        f"$launcherProcess.CommandLine -match '{_BATCH_LAUNCHER_COMMAND_LINE_PATTERN}' -and "
        f"$launcherParent.CommandLine -match '{_BATCH_LAUNCHER_COMMAND_LINE_PATTERN}') "
        "{ $ownedProcessIds += $launcherParentPid }; "
        "$candidateProcesses = @($processes | Where-Object { $ownedProcessIds -notcontains $_.ProcessId -and "
        "$_.Name -match '(?i)^(python(?:\\d+(?:\\.\\d+)?)?w?|py)(?:\\.exe)?$' }); "
        "$connectorProcesses = @($candidateProcesses | Where-Object { "
        f"$_.CommandLine -match '{_CONNECTOR_COMMAND_LINE_PATTERN}' }}); "
        "$batchLauncherProcesses = @($candidateProcesses | Where-Object { "
        f"$_.CommandLine -match '{_BATCH_LAUNCHER_COMMAND_LINE_PATTERN}' }}); "
        "if ($connectorProcesses.Count -gt 0) { 'connector_running' } "
        "elseif ($batchLauncherProcesses.Count -gt 0) { 'batch_launcher_running' } "
        "else { 'connector_absent' }"
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
        and int(summary.group(6)) == process_exit
        and audit_exit == process_exit
        and len(rows) == finished
        and row_counts == counts
    )
    return (
        stop_reason,
        "complete" if complete else "incomplete",
        finished,
        len(rows),
        tuple(sorted(row_counts.items())),
    )


def _game_evidence_status(path: Path) -> str:
    try:
        output = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "incomplete"
    summaries = list(_CONNECTOR_SUMMARY.finditer(output))
    if len(summaries) != 1:
        return "incomplete"
    return summaries[0].group(5) or "incomplete"


def _game_evidence_error_category(path: Path) -> str | None:
    try:
        output = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "evidence_write_failed"
    match = _EVIDENCE_FAILURE.search(output)
    return match.group(1) if match is not None else None


def run_batch(
    *,
    games: int = 10,
    max_cycles: int | None = None,
    max_wall_seconds: int | None = None,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
    python_executable: str | None = None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    import_from: Path | str | None = None,
    announce: Callable[[str], None] = print,
) -> BatchOutcome:
    if type(games) is not int or games <= 0:
        raise BatchLaunchError("invalid_game_count")
    if max_cycles is not None and (type(max_cycles) is not int or max_cycles <= 0):
        raise BatchLaunchError("invalid_cycle_limit")
    if max_wall_seconds is not None and (type(max_wall_seconds) is not int or max_wall_seconds <= 0):
        raise BatchLaunchError("invalid_wall_limit")
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
    probe_status = process_probe.stdout.splitlines()
    if process_probe.returncode != 0 or probe_status not in (
        ["connector_absent"],
        ["connector_running"],
        ["batch_launcher_running"],
    ):
        raise BatchLaunchError("connector_status_unavailable")
    if probe_status == ["connector_running"]:
        raise BatchLaunchError("connector_already_running")
    if probe_status == ["batch_launcher_running"]:
        raise BatchLaunchError("batch_launcher_already_running")

    paths = create_batch_workspace(workspace_root)
    announce(f"本次运行内部目录：{paths.root}")
    announce(f"逐局留证目录：{paths.game_evidence}")

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
    interrupted = False
    try:
        ensure_recent_results_directory(workspace_root)
        with RecentResultsLock(paths.recent_lock):
            try:
                recent_snapshot = prepare_recent_results(
                    workspace_root,
                    games,
                    import_from=import_from,
                    allow_legacy_scan=False,
                )
            except RecentResultsError as exc:
                raise BatchLaunchError(exc.category, paths.root) from None
            try:
                prepare_game_evidence(
                    paths.game_evidence,
                    games,
                    legacy_recent_results=paths.recent_results,
                )
            except GameEvidenceError as exc:
                raise BatchLaunchError(exc.category, paths.game_evidence) from None
            runtime_argv = _cli_argv(
                paths.state,
                preflight=False,
                max_cycles=max_cycles,
                max_wall_seconds=max_wall_seconds,
                paths=paths,
                run_token=run_token,
                recent_results_capacity=games,
            )
            runtime_argv[0] = executable
            announce("零网络配置预检通过。连接器将在前台持续轮询；请等页面显示“已连接”后手动逐局建桌并开始。")
            announce(
                f"--games {games} 表示滚动记录容量；不会因达到容量停机。按 Ctrl+C 停止，"
                "仅显式运行上限或固定类别故障会提前结束。"
            )
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
    except RecentResultsError as exc:
        raise BatchLaunchError(exc.category, paths.root) from None
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
        process_code,
        interrupted=interrupted,
    )
    recent_status = "ok"
    try:
        recent_snapshot, _ = read_recent_results(paths.recent_results)
    except RecentResultsError:
        recent_status = "failed"
        recent_snapshot = None
    evidence_status = _game_evidence_status(paths.stdout)
    evidence_error_category = _game_evidence_error_category(paths.stdout)
    outcome = BatchOutcome(
        paths.root,
        games,
        process_code,
        stop_reason,
        finished,
        result_count,
        result_counts,
        records_status,
        recent_status,
        0 if recent_snapshot is None else recent_snapshot.total_games,
        0 if recent_snapshot is None else recent_snapshot.retained_count,
        games if recent_snapshot is None else recent_snapshot.capacity,
        evidence_status,
        evidence_error_category,
    )
    confirmed = "unknown" if outcome.confirmed_finished is None else str(outcome.confirmed_finished)
    announce(
        f"batch_result category={outcome.category} exit={outcome.exit_code} "
        f"connector_exit={outcome.connector_exit_code} stop={outcome.stop_reason} "
        f"confirmed_finished={confirmed} "
        f"game_results={outcome.game_results_status} recorded={outcome.recorded_games} "
        f"recent_results={outcome.recent_results_status} retained={outcome.recent_results_retained_count}/"
        f"{outcome.recent_results_capacity} total={outcome.recent_results_total_games} "
        f"game_evidence={outcome.game_evidence_status}"
        f" evidence_error={outcome.game_evidence_error_category or 'none'}"
        f" runtime_directory={outcome.batch_directory} "
        f"games_directory={paths.game_evidence}"
    )
    announce("完整逐局请求与决策证据仅写入 games 子目录；聚合 audit 和普通输出不含手牌或 prompt。")
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
            import_from=arguments.import_from,
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
