"""Windows-safe foreground launcher with in-process stream redirection."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path


LAUNCHER_CONFIGURATION_EXIT = 64
LAUNCHER_ENTRYPOINT_EXIT = 70
LAUNCHER_INTERRUPT_EXIT = 130
_PROBE_MODE = "CODEX_LAUNCHER_OFFLINE_PROBE"
_SENTINEL = "CODEX_LAUNCH_SENTINEL"
_EXPECTED_CWD = "CODEX_LAUNCH_EXPECTED_CWD"


class LauncherError(ValueError):
    """Stable, non-sensitive launcher configuration error."""


@dataclass(frozen=True, slots=True)
class LauncherConfig:
    timeout_seconds: int
    max_cycles: int
    max_wall_seconds: int
    stop_after_finished: int
    audit_file: Path
    stdout_file: Path
    stderr_file: Path


def _positive(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise LauncherError("invalid_argument")
    return value


def _parse_positive(value: object) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise LauncherError("invalid_argument")
    return _positive(int(value))


def _external_file(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise LauncherError("invalid_path")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise LauncherError("invalid_path")
    resolved = candidate.resolve()
    project_root = Path(__file__).resolve().parents[2]
    if resolved.is_relative_to(project_root):
        raise LauncherError("invalid_path")
    return resolved


def parse_launcher_args(argv: Sequence[object]) -> LauncherConfig:
    """Accept exactly the bounded connector arguments plus private stream paths."""

    items = tuple(argv)
    expected = {
        "--timeout-seconds",
        "--max-cycles",
        "--max-wall-seconds",
        "--stop-after-finished",
        "--audit-file",
        "--stdout-file",
        "--stderr-file",
    }
    if len(items) != len(expected) * 2:
        raise LauncherError("invalid_argument")
    values: dict[str, object] = {}
    for index in range(0, len(items), 2):
        name, value = items[index], items[index + 1]
        if not isinstance(name, str) or name not in expected or name in values:
            raise LauncherError("invalid_argument")
        values[name] = value
    if set(values) != expected:
        raise LauncherError("invalid_argument")
    config = LauncherConfig(
        timeout_seconds=_parse_positive(values["--timeout-seconds"]),
        max_cycles=_parse_positive(values["--max-cycles"]),
        max_wall_seconds=_parse_positive(values["--max-wall-seconds"]),
        stop_after_finished=_parse_positive(values["--stop-after-finished"]),
        audit_file=_external_file(values["--audit-file"]),
        stdout_file=_external_file(values["--stdout-file"]),
        stderr_file=_external_file(values["--stderr-file"]),
    )
    paths = (config.audit_file, config.stdout_file, config.stderr_file)
    if len(set(paths)) != len(paths) or config.stdout_file.parent != config.stderr_file.parent:
        raise LauncherError("invalid_path")
    stream_directory = config.stdout_file.parent
    if not stream_directory.is_dir() or any(stream_directory.iterdir()):
        raise LauncherError("invalid_stream_directory")
    if any(path.exists() for path in paths):
        raise LauncherError("output_exists")
    return config


def connector_argv(config: LauncherConfig) -> tuple[str, ...]:
    return (
        "--timeout-seconds", str(config.timeout_seconds),
        "--max-cycles", str(config.max_cycles),
        "--max-wall-seconds", str(config.max_wall_seconds),
        "--stop-after-finished", str(config.stop_after_finished),
        "--audit-file", str(config.audit_file),
    )


def run_launcher(config: LauncherConfig, entrypoint: Callable[[list[str]], int]) -> int:
    """Create streams once, invoke one entrypoint, and always close both streams."""

    try:
        stdout_handle = config.stdout_file.open("x", encoding="utf-8", newline="\n")
        try:
            stderr_handle = config.stderr_file.open("x", encoding="utf-8", newline="\n")
        except OSError:
            stdout_handle.close()
            config.stdout_file.unlink(missing_ok=True)
            raise LauncherError("stream_open_failed") from None
    except OSError:
        raise LauncherError("stream_open_failed") from None
    try:
        with redirect_stdout(stdout_handle), redirect_stderr(stderr_handle):
            try:
                result = entrypoint(list(connector_argv(config)))
            except KeyboardInterrupt:
                return LAUNCHER_INTERRUPT_EXIT
            except Exception:
                print("launcher_entrypoint_failure", file=sys.stderr)
                return LAUNCHER_ENTRYPOINT_EXIT
            if type(result) is not int:
                print("launcher_entrypoint_failure", file=sys.stderr)
                return LAUNCHER_ENTRYPOINT_EXIT
            return result
    finally:
        try:
            stdout_handle.flush()
            stderr_handle.flush()
        finally:
            stdout_handle.close()
            stderr_handle.close()


def _connector_main(argv: list[str]) -> int:
    from .__main__ import main

    return main(argv)


def _offline_probe_entrypoint(_: list[str]) -> int:
    print("launcher_probe_stdout")
    print("launcher_probe_stderr", file=sys.stderr)
    expected = os.environ.get(_EXPECTED_CWD)
    inherited = os.environ.get(_SENTINEL) == "synthetic-ok"
    return 17 if inherited and expected == os.getcwd() else 18


def main(argv: Sequence[object] | None = None) -> int:
    try:
        config = parse_launcher_args(sys.argv[1:] if argv is None else argv)
    except LauncherError:
        print("launcher_configuration_error")
        return LAUNCHER_CONFIGURATION_EXIT
    entrypoint = _offline_probe_entrypoint if os.environ.get(_PROBE_MODE) == "1" else _connector_main
    return run_launcher(config, entrypoint)


if __name__ == "__main__":
    raise SystemExit(main())
