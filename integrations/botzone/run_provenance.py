"""Strict, non-sensitive local run provenance tokens."""

from __future__ import annotations

import re
from typing import Final


RUN_TOKEN_LENGTH: Final[int] = 32
TOKEN_SESSION_VERSION: Final[int] = 4
TOKEN_AUDIT_VERSION: Final[int] = 8
_RUN_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{32}\Z")


class RunProvenanceError(ValueError):
    """A caller supplied an invalid or incompatible local provenance token."""


def validate_run_token(value: object) -> str:
    """Accept only the fixed local token format, without deriving or logging it."""

    if type(value) is not str or _RUN_TOKEN_PATTERN.fullmatch(value) is None:
        raise RunProvenanceError("invalid_run_token")
    return value
