"""Explicit runtime configuration without project-level configuration loading."""

from __future__ import annotations

import os
from collections.abc import Mapping
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
