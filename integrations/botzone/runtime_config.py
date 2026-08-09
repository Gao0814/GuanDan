"""Explicit runtime configuration without project-level configuration loading."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .http_transport import DEFAULT_MAX_RESPONSE_BYTES, DEFAULT_TIMEOUT_SECONDS, TransportError, validate_https_url


class RuntimeConfigError(ValueError):
    """Configuration failure whose text contains no private value."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    local_ai_url: str
    state_directory: Path
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_consecutive_failures: int = 5
    backoff_seconds: int = 1

    def __repr__(self) -> str:
        return (
            "RuntimeConfig(local_ai_url=<redacted>, "
            f"state_directory={self.state_directory!r}, timeout_seconds={self.timeout_seconds}, "
            f"max_response_bytes={self.max_response_bytes}, "
            f"max_consecutive_failures={self.max_consecutive_failures}, backoff_seconds={self.backoff_seconds})"
        )


def _positive_int(value: object, category: str) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        result = int(value)
    else:
        raise RuntimeConfigError(category)
    if result <= 0:
        raise RuntimeConfigError(category)
    return result


def _required(explicit: str | None, environment: Mapping[str, str], name: str) -> str:
    value = explicit if explicit is not None else environment.get(name)
    if not isinstance(value, str) or not value:
        raise RuntimeConfigError("missing_configuration")
    return value


def load_runtime_config(
    *,
    local_ai_url: str | None = None,
    state_directory: str | Path | None = None,
    timeout_seconds: object = DEFAULT_TIMEOUT_SECONDS,
    max_response_bytes: object = DEFAULT_MAX_RESPONSE_BYTES,
    max_consecutive_failures: object = 5,
    backoff_seconds: object = 1,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Read only the two named process variables; explicit arguments win."""

    environment = os.environ if environ is None else environ
    url = _required(local_ai_url, environment, "BOTZONE_LOCAL_AI_URL")
    raw_state = state_directory if state_directory is not None else environment.get("BOTZONE_STATE_DIR")
    if not isinstance(raw_state, (str, Path)) or not str(raw_state):
        raise RuntimeConfigError("missing_configuration")
    try:
        private_url = validate_https_url(url)
    except TransportError:
        raise RuntimeConfigError("invalid_configuration") from None
    return RuntimeConfig(
        local_ai_url=private_url,
        state_directory=Path(raw_state),
        timeout_seconds=_positive_int(timeout_seconds, "invalid_timeout"),
        max_response_bytes=_positive_int(max_response_bytes, "invalid_response_limit"),
        max_consecutive_failures=_positive_int(max_consecutive_failures, "invalid_failure_limit"),
        backoff_seconds=_positive_int(backoff_seconds, "invalid_backoff"),
    )


def preflight_state_directory(
    config: RuntimeConfig,
    *,
    stage_callback: Callable[[str], None] | None = None,
) -> None:
    """Check a repository-external state directory without opening a transport."""

    def stage(name: str) -> None:
        if stage_callback is not None:
            stage_callback(name)

    state_dir = config.state_directory.resolve()
    stage("resolve")
    project_root = Path(__file__).resolve().parents[2]
    if not state_dir.is_absolute() or state_dir.is_relative_to(project_root):
        raise RuntimeConfigError("invalid_state_directory")
    stage("boundary_checked")
    probe: Path | None = None
    replacement: Path | None = None
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        stage("directory_ready")
        with tempfile.NamedTemporaryFile(dir=state_dir, delete=False) as handle:
            probe = Path(handle.name)
            stage("temporary_opened")
            handle.write(b"probe")
            stage("written")
            handle.flush()
            stage("flushed")
            os.fsync(handle.fileno())
            stage("synced")
        replacement = probe.with_name(probe.name + ".replace")
        os.replace(probe, replacement)
        stage("replaced")
        replacement.unlink()
        replacement = None
        stage("cleaned")
    except OSError:
        try:
            if probe is not None and probe.exists():
                probe.unlink()
            if replacement is not None and replacement.exists():
                replacement.unlink()
        except OSError:
            pass
        raise RuntimeConfigError("state_preflight_failed") from None
    except Exception:
        try:
            if probe is not None and probe.exists():
                probe.unlink()
            if replacement is not None and replacement.exists():
                replacement.unlink()
        except OSError:
            pass
        raise
