"""Ack-only structured public-decision evidence for the Botzone connector.

This is an optional diagnostic artifact.  It consumes only the durable
acknowledged snapshots in ``SessionRecord`` and never participates in the
transport, pending-delivery, or audit transactions.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .poll import FinishedRow

if TYPE_CHECKING:
    from .session import SessionRecord


TRACE_SCHEMA = "botzone_acknowledged_local_decision_trace"
TRACE_VERSION = 1
TRACE_SCOPE = "acknowledged_local_decisions_only"
_BINDING_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


class DecisionTraceWriteError(ValueError):
    """The optional decision artifact cannot be safely replaced."""


@dataclass(slots=True)
class ConnectorDecisionTrace:
    """Atomic, single-match writer for acknowledged local decisions only."""

    path: Path | str
    failed: bool = False
    _bound_match: str | None = None
    _binding_id: str | None = None

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    def update(self, record: "SessionRecord") -> None:
        if self.failed or not record.confirmed_decision_traces:
            return
        try:
            payload = self._payload(record)
            self._bind(record.match_id, payload["binding_id"], payload["decisions"])
            self._write(payload)
        except (DecisionTraceWriteError, OSError):
            self.failed = True

    def finish(self, record: "SessionRecord", row: FinishedRow) -> None:
        # The row contains no decision evidence; it only establishes the last
        # opportunity to render before the session becomes a tombstone.
        self.update(record)

    def _payload(self, record: "SessionRecord") -> dict[str, object]:
        binding = record.decision_trace_binding
        if type(binding) is not str or _BINDING_PATTERN.fullmatch(binding) is None:
            raise DecisionTraceWriteError("decision_trace_binding_invalid")
        decisions: list[dict[str, object]] = []
        for sequence, trace in enumerate(record.confirmed_decision_traces, start=1):
            decision = {"sequence": sequence}
            decision.update(trace.to_json())
            decisions.append(decision)
        return {
            "schema": TRACE_SCHEMA,
            "version": TRACE_VERSION,
            "scope": TRACE_SCOPE,
            "binding_id": binding,
            "decisions": decisions,
        }

    def _bind(self, match_id: str, binding_id: object, decisions: object) -> None:
        if type(binding_id) is not str or _BINDING_PATTERN.fullmatch(binding_id) is None:
            raise DecisionTraceWriteError("decision_trace_binding_invalid")
        if self._bound_match is not None:
            if self._bound_match != match_id or self._binding_id != binding_id:
                raise DecisionTraceWriteError("decision_trace_match_conflict")
            return
        target = Path(self.path)
        if target.exists():
            try:
                previous = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DecisionTraceWriteError("decision_trace_existing_invalid") from exc
            if (
                not isinstance(previous, dict)
                or set(previous) != {"schema", "version", "scope", "binding_id", "decisions"}
                or previous.get("schema") != TRACE_SCHEMA
                or previous.get("version") != TRACE_VERSION
                or previous.get("scope") != TRACE_SCOPE
                or type(previous.get("binding_id")) is not str
                or _BINDING_PATTERN.fullmatch(previous["binding_id"]) is None
                or previous["binding_id"] != binding_id
                or not isinstance(previous.get("decisions"), list)
                or not isinstance(decisions, list)
                or previous["decisions"] != decisions[:len(previous["decisions"])]
            ):
                raise DecisionTraceWriteError("decision_trace_match_conflict")
        self._bound_match = match_id
        self._binding_id = binding_id

    def _write(self, payload: dict[str, object]) -> None:
        target = Path(self.path)
        temporary: Path | None = None
        try:
            encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
