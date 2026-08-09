"""Auditable, no-network preflight entry point for a future live launcher."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "botzone_instrumented_live_preflight"
VERSION = 1
COUNTS = {"request": 0, "get": 0, "network": 0, "connector": 0}
EXIT_CONFIG = 2
EXIT_AUDIT = 3
EXIT_STATE = 4
EXIT_IMPORT = 5
EXIT_UNEXPECTED = 70
EXIT_INTERRUPT = 130


class AuditWriteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreflightAudit:
    status: str
    stages: tuple[str, ...]
    exit_code: int | None
    diagnostic: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "status": self.status,
            "stages": list(self.stages),
            "exit_code": self.exit_code,
            "diagnostic": self.diagnostic,
            "counts": dict(COUNTS),
        }


def _audit_path(argv: Sequence[object]) -> Path:
    values = tuple(argv)
    if len(values) != 2 or values[0] != "--audit-file" or not isinstance(values[1], str) or not values[1]:
        raise ValueError("invalid_arguments")
    path = Path(values[1])
    if not path.is_absolute():
        raise ValueError("invalid_audit_path")
    resolved = path.resolve()
    project_root = Path(__file__).resolve().parents[2]
    if resolved.is_relative_to(project_root) or resolved.exists() or resolved.is_dir():
        raise ValueError("invalid_audit_path")
    return resolved


def _atomic_writer(path: Path, audit: PreflightAudit) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(audit.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            if "temporary" in locals() and temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        raise AuditWriteError("audit_write_failed") from None


def run_instrumented_preflight(
    argv: Sequence[object],
    *,
    loader: Callable[[], Any] | None = None,
    prober: Callable[..., None] | None = None,
    writer: Callable[[Path, PreflightAudit], None] = _atomic_writer,
    stdout: Any | None = None,
) -> int:
    sink = sys.stdout if stdout is None else stdout
    try:
        audit_path = _audit_path(argv)
        audit = PreflightAudit("bootstrapping", (), None)
        writer(audit_path, audit)
    except (ValueError, AuditWriteError):
        print("instrumented_preflight_audit_error", file=sink)
        return EXIT_AUDIT

    def update(status: str, stages: tuple[str, ...], exit_code: int | None, diagnostic: str | None = None) -> None:
        writer(audit_path, PreflightAudit(status, stages, exit_code, diagnostic))

    stages: tuple[str, ...] = ()
    if loader is None:
        def loader() -> Any:
            from . import runtime_config as runtime

            return runtime
    try:
        runtime = loader()
        stages = ("runtime_loaded",)
        update("running", stages, None)
    except KeyboardInterrupt:
        try:
            update("interrupted", stages, EXIT_INTERRUPT, "interrupted")
        except AuditWriteError:
            return EXIT_AUDIT
        return EXIT_INTERRUPT
    except AuditWriteError:
        return EXIT_AUDIT
    except Exception:
        try:
            update("failed", stages, EXIT_IMPORT, "runtime_import_error")
        except AuditWriteError:
            return EXIT_AUDIT
        return EXIT_IMPORT
    try:
        config = runtime.load_runtime_config()
        stages += ("config_loaded",)
        update("running", stages, None)
    except KeyboardInterrupt:
        try:
            update("interrupted", stages, EXIT_INTERRUPT, "interrupted")
        except AuditWriteError:
            return EXIT_AUDIT
        return EXIT_INTERRUPT
    except AuditWriteError:
        return EXIT_AUDIT
    except Exception as exc:
        code = EXIT_CONFIG if type(exc).__name__ == "RuntimeConfigError" else EXIT_UNEXPECTED
        diagnostic = "config_error" if code == EXIT_CONFIG else "unexpected_error"
        try:
            update("failed", stages, code, diagnostic)
        except AuditWriteError:
            return EXIT_AUDIT
        return code

    def stage_callback(stage: str) -> None:
        nonlocal stages
        stages += (stage,)
        update("running", stages, None)

    try:
        (prober or runtime.preflight_state_directory)(config, stage_callback=stage_callback)
    except KeyboardInterrupt:
        try:
            update("interrupted", stages, EXIT_INTERRUPT, "interrupted")
        except AuditWriteError:
            pass
        return EXIT_INTERRUPT
    except AuditWriteError:
        return EXIT_AUDIT
    except Exception:
        try:
            update("failed", stages, EXIT_STATE, "state_preflight_error")
        except AuditWriteError:
            return EXIT_AUDIT
        return EXIT_STATE
    try:
        stages += ("state_preflight_completed",)
        update("completed", stages, 0)
    except AuditWriteError:
        return EXIT_AUDIT
    print("instrumented_preflight_ready", file=sink)
    return 0


def main(argv: Sequence[object] | None = None) -> int:
    return run_instrumented_preflight(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
