"""Owner-only per-game evidence and rolling directory retention.

This module is only enabled by the continuous manual batch entry point. It
stores connector-observed decision evidence under a managed ``games`` folder;
it never stores platform identifiers, response headers, full model responses, or
credentials. Only the authorized bounded JSON reason accompanies a model ID.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Callable, Mapping

from .agent_observability import DECISION_SOURCES
from .rolling_results import RecentResultsError, RecentResultsLock, read_recent_results


GAME_EVIDENCE_DIRECTORY = "games"
GAME_EVIDENCE_INDEX = "index.json"
GAME_EVIDENCE_LOCK = ".writer.lock"
GAME_EVIDENCE_SCHEMA = "botzone_manual_game_evidence"
GAME_EVIDENCE_VERSION = 1
GAME_EVIDENCE_EVENT_SCHEMA = "botzone_manual_game_event"
GAME_EVIDENCE_EVENT_VERSION = 1
GAME_EVIDENCE_ROW_SCHEMA = "botzone_manual_game_record"
GAME_EVIDENCE_ROW_VERSION = 1
_GAME_NAME = re.compile(r"^[0-9]{4}_[0-9]{1,2}_[0-9]{1,2}_[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{6,}$")
_REQUEST_NAME = re.compile(r"^request_([0-9]{6,})\.json$")
_SAFE_CATEGORIES = frozenset(
    {
        "evidence_write_failed",
        "evidence_schema_invalid",
        "evidence_unknown_entry",
        "evidence_link_rejected",
        "evidence_active_capacity",
        "evidence_legacy_summary_invalid",
        "evidence_storage_unavailable",
        "evidence_rotation_failed",
    }
)
_STATUSES = frozenset(
    {"in_progress", "finished", "finished_unconfirmed", "interrupted", "stopped_at_limit", "summary_only"}
)
_RESULTS = frozenset(
    {
        "local_team_win",
        "local_team_loss",
        "draw",
        "platform_error",
        "invalid_score_shape",
        "four_player_unqualified",
        "non_four_player",
        "aborted",
        "result_unconfirmed",
    }
)
_MAX_ACTIVE = 128
_ROOT_ITEMS = frozenset({GAME_EVIDENCE_INDEX, GAME_EVIDENCE_LOCK})
_GAME_FILES = frozenset({"manifest.json", "deal.json", "observations.jsonl", "decisions.jsonl", "timeline.jsonl", "requests"})
_GAME_EVENTS = {
    "deal_observed": {"game_no"},
    "connector_resumed": {"game_no"},
    "public_observation": {"scope"},
    "decision_started": {"decision_no"},
    "request_prepared": {"request_no", "decision_no", "sha256"},
    "model_enter": {"decision_no", "outcome"},
    "model_complete": {"decision_no", "outcome", "selected_action_id", "reason", "reason_truncated"},
    "action_computed": {"selected_action_id", "source"},
    "header_pending": {"selected_action_id", "source"},
    "ack_confirmed": {"ack", "selected_action_id", "source"},
    "handler_failure": {"category"},
    "poll": {"outcome"},
    "platform_result": {"result"},
    "platform_finish_unconfirmed": {"result"},
    "interrupted": {"stop_reason", "status"},
    "stopped_at_limit": {"stop_reason", "status"},
}


class GameEvidenceError(ValueError):
    """A fixed-category failure in the managed game evidence store."""

    __slots__ = ("category",)

    def __init__(self, category: str) -> None:
        self.category = category if category in _SAFE_CATEGORIES else "evidence_storage_unavailable"
        super().__init__(self.category)


def _is_reparse(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _ordinary(path: Path, kind: str) -> None:
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        raise GameEvidenceError("evidence_storage_unavailable") from None
    if _is_reparse(info):
        raise GameEvidenceError("evidence_link_rejected")
    if kind == "directory" and not stat.S_ISDIR(info.st_mode):
        raise GameEvidenceError("evidence_schema_invalid")
    if kind == "file" and not stat.S_ISREG(info.st_mode):
        raise GameEvidenceError("evidence_schema_invalid")
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(resolved)):
        raise GameEvidenceError("evidence_link_rejected")


def _utc(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.astimezone()
    return now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _local_metadata(now: datetime) -> tuple[str, str, dict[str, str], str]:
    local = now.astimezone() if now.tzinfo is None else now.astimezone()
    offset = local.utcoffset()
    seconds = 0 if offset is None else int(offset.total_seconds())
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    offset_text = f"{sign}{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"
    zone_name = local.tzname() or "UTC"
    safe = f"{local.year}_{local.month}_{local.day}_{local.hour:02d}-{local.minute:02d}-{local.second:02d}"
    display = f"{local.year}_{local.month}_{local.day}_{local.hour:02d}:{local.minute:02d}:{local.second:02d}"
    return safe, display, {"name": zone_name, "offset": offset_text}, _utc(local)


def _json_bytes(value: object) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        raise GameEvidenceError("evidence_schema_invalid") from None


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        raise GameEvidenceError("evidence_write_failed") from None


def _read_json(path: Path) -> object:
    _ordinary(path, "file")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise GameEvidenceError("evidence_schema_invalid") from None


def _validate_timezone(value: object, *, allow_none: bool = False) -> bool:
    if value is None:
        return allow_none
    return (
        isinstance(value, dict)
        and set(value) == {"name", "offset"}
        and isinstance(value.get("name"), str)
        and bool(value["name"])
        and isinstance(value.get("offset"), str)
        and re.fullmatch(r"[+-][0-9]{2}:[0-9]{2}", value["offset"]) is not None
    )


def _valid_entry(entry: object) -> bool:
    if not isinstance(entry, dict) or set(entry) != {
        "game_no", "directory", "kind", "status", "result", "local_time", "local_timezone",
        "started_utc", "match_digest", "evidence_incomplete", "error_category",
    }:
        return False
    if type(entry.get("game_no")) is not int or entry["game_no"] <= 0:
        return False
    directory = entry.get("directory")
    kind = entry.get("kind")
    status = entry.get("status")
    result = entry.get("result")
    if (
        not isinstance(kind, str) or kind not in {"full", "summary_only"}
        or not isinstance(status, str) or status not in _STATUSES
        or not isinstance(result, str) or result not in _RESULTS
    ):
        return False
    if type(entry.get("evidence_incomplete")) is not bool:
        return False
    category = entry.get("error_category")
    if category is not None and (not isinstance(category, str) or category not in _SAFE_CATEGORIES):
        return False
    if kind == "full":
        if not isinstance(directory, str) or _GAME_NAME.fullmatch(directory) is None:
            return False
        if not isinstance(entry.get("local_time"), str) or not isinstance(entry.get("started_utc"), str):
            return False
        if not _validate_timezone(entry.get("local_timezone")):
            return False
        digest = entry.get("match_digest")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return False
    else:
        if directory is not None or status != "summary_only" or entry.get("match_digest") is not None:
            return False
        if entry.get("started_utc") is not None:
            return False
        if not isinstance(entry.get("local_time"), str) or not _validate_timezone(entry.get("local_timezone"), allow_none=True):
            return False
    return True


def _validate_index(value: object, *, allow_retired_bindings: bool = False) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "schema", "version", "capacity", "next_game_no", "entries", "bindings", "imports", "rotation_pending",
    }:
        raise GameEvidenceError("evidence_schema_invalid")
    if (
        value.get("schema") != GAME_EVIDENCE_SCHEMA
        or type(value.get("version")) is not int or value["version"] != GAME_EVIDENCE_VERSION
        or type(value.get("capacity")) is not int or value["capacity"] <= 0
        or type(value.get("next_game_no")) is not int or value["next_game_no"] < 0
        or not isinstance(value.get("entries"), list)
        or not isinstance(value.get("bindings"), list)
        or not isinstance(value.get("imports"), list)
    ):
        raise GameEvidenceError("evidence_schema_invalid")
    entries = value["entries"]
    if len(entries) > value["capacity"] + _MAX_ACTIVE:
        raise GameEvidenceError("evidence_schema_invalid")
    seen_numbers: set[int] = set()
    seen_directories: set[str] = set()
    last_no = 0
    for entry in entries:
        if not _valid_entry(entry) or entry["game_no"] <= last_no or entry["game_no"] in seen_numbers:
            raise GameEvidenceError("evidence_schema_invalid")
        last_no = entry["game_no"]
        seen_numbers.add(entry["game_no"])
        if entry["directory"] is not None:
            if entry["directory"] in seen_directories:
                raise GameEvidenceError("evidence_schema_invalid")
            seen_directories.add(entry["directory"])
    if value["next_game_no"] < last_no:
        raise GameEvidenceError("evidence_schema_invalid")
    bindings = value["bindings"]
    seen_hashes: set[str] = set()
    for binding in bindings:
        if (
            not isinstance(binding, dict) or set(binding) != {"match_digest", "game_no"}
            or not isinstance(binding.get("match_digest"), str)
            or re.fullmatch(r"[0-9a-f]{64}", binding["match_digest"]) is None
            or type(binding.get("game_no")) is not int or binding["game_no"] <= 0
            or binding["match_digest"] in seen_hashes
        ):
            raise GameEvidenceError("evidence_schema_invalid")
        entry = next((item for item in entries if item["game_no"] == binding["game_no"]), None)
        if entry is None:
            # Rotation removes an oldest prefix, never a middle/future row.
            # Validate the binding before allowing this narrowly scoped repair.
            if (
                not allow_retired_bindings or not entries
                or binding["game_no"] >= entries[0]["game_no"]
                or any(item["match_digest"] == binding["match_digest"] for item in entries)
            ):
                raise GameEvidenceError("evidence_schema_invalid")
            seen_hashes.add(binding["match_digest"])
            continue
        if entry["kind"] != "full" or entry["match_digest"] != binding["match_digest"]:
            raise GameEvidenceError("evidence_schema_invalid")
        seen_hashes.add(binding["match_digest"])
    pending = value.get("rotation_pending")
    if pending is not None:
        pending_entry = next((item for item in entries if item["game_no"] == pending), None) if type(pending) is int else None
        if (
            pending_entry is None
            or not entries
            or len(entries) <= value["capacity"]
            or entries[0]["game_no"] != pending
            or pending_entry["kind"] != "full"
            or pending_entry["status"] == "in_progress"
        ):
            raise GameEvidenceError("evidence_schema_invalid")
    imports = value["imports"]
    seen_imports: set[str] = set()
    for imported in imports:
        if (
            not isinstance(imported, dict) or set(imported) != {"content_sha256", "row_count"}
            or not isinstance(imported.get("content_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", imported["content_sha256"]) is None
            or type(imported.get("row_count")) is not int or imported["row_count"] < 0
            or imported["content_sha256"] in seen_imports
        ):
            raise GameEvidenceError("evidence_schema_invalid")
        seen_imports.add(imported["content_sha256"])
    return value


def _manifest(entry: Mapping[str, object], *, last_stage: str) -> dict[str, object]:
    return {
        "schema": GAME_EVIDENCE_SCHEMA,
        "version": GAME_EVIDENCE_VERSION,
        "game_no": entry["game_no"],
        "directory": entry["directory"],
        "local_time": entry["local_time"],
        "local_timezone": entry["local_timezone"],
        "started_utc": entry["started_utc"],
        "status": entry["status"],
        "result": entry["result"],
        "history_scope": "connector_observed_only",
        "last_stage": last_stage,
        "evidence_incomplete": entry["evidence_incomplete"],
        "error_category": entry["error_category"],
    }


def _validate_manifest(directory: Path, entry: Mapping[str, object]) -> dict[str, object]:
    manifest = _read_json(directory / "manifest.json")
    expected = _manifest(entry, last_stage=manifest.get("last_stage", "")) if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {
            "schema", "version", "game_no", "directory", "local_time", "local_timezone", "started_utc",
            "status", "result", "history_scope", "last_stage", "evidence_incomplete", "error_category",
        }
        or manifest.get("schema") != GAME_EVIDENCE_SCHEMA
        or type(manifest.get("version")) is not int or manifest["version"] != GAME_EVIDENCE_VERSION
        or manifest.get("game_no") != entry["game_no"]
        or manifest.get("directory") != entry["directory"]
        or manifest.get("history_scope") != "connector_observed_only"
        or manifest.get("status") != entry["status"]
        or manifest.get("result") != entry["result"]
        or manifest.get("evidence_incomplete") != entry["evidence_incomplete"]
        or manifest.get("error_category") != entry["error_category"]
        or manifest.get("local_time") != entry["local_time"]
        or manifest.get("local_timezone") != entry["local_timezone"]
        or manifest.get("started_utc") != entry["started_utc"]
        or not isinstance(manifest.get("last_stage"), str)
        or expected is None
    ):
        raise GameEvidenceError("evidence_schema_invalid")
    return manifest


def _valid_public_history(value: object) -> bool:
    if not isinstance(value, list):
        return False
    return all(
        isinstance(item, dict)
        and set(item) == {"player", "response"}
        and type(item.get("player")) is int
        and 0 <= item["player"] <= 3
        and isinstance(item.get("response"), list)
        and len(item["response"]) == 2
        and all(isinstance(cards, list) and all(type(card) is int for card in cards) for cards in item["response"])
        for item in value
    )


def _valid_observation_row(data: object) -> bool:
    if not isinstance(data, dict) or set(data) != {
        "observation_scope", "stage", "player_id", "own_hand", "global", "observed_history",
        "session_history", "session_latest_window", "done", "pass_on",
    }:
        return False
    return (
        data.get("observation_scope") == "connector_observed_only"
        and data.get("stage") == "play"
        and type(data.get("player_id")) is int
        and 0 <= data["player_id"] <= 3
        and isinstance(data.get("own_hand"), list)
        and all(type(card) is int for card in data["own_hand"])
        and isinstance(data.get("global"), dict)
        and _valid_public_history(data.get("observed_history"))
        and _valid_public_history(data.get("session_history"))
        and _valid_public_history(data.get("session_latest_window"))
        and isinstance(data.get("done"), list)
        and all(type(player) is int and 0 <= player <= 3 for player in data["done"])
        and type(data.get("pass_on")) is int
    )


def _valid_decision_row(data: object) -> bool:
    if not isinstance(data, dict) or set(data) not in (
        {"observation", "legal_actions", "selected_action_id", "selected_action", "decision_source"},
        {"observation", "legal_actions", "selected_action_id", "selected_action", "decision_source", "evidence_decision_no"},
    ):
        return False
    actions = data.get("legal_actions")
    selected_id = data.get("selected_action_id")
    selected = data.get("selected_action")
    source = data.get("decision_source")
    if (
        not isinstance(data.get("observation"), dict)
        or not isinstance(actions, list)
        or not actions
        or type(selected_id) is not int
        or not isinstance(selected, dict)
        or type(selected.get("action_id")) is not int
        or selected.get("action_id") != selected_id
        or not isinstance(source, str)
        or source not in DECISION_SOURCES
    ):
        return False
    action_ids = [action.get("action_id") for action in actions if isinstance(action, dict)]
    if len(action_ids) != len(actions) or any(type(action_id) is not int for action_id in action_ids):
        return False
    if selected_id not in action_ids:
        return False
    decision_no = data.get("evidence_decision_no")
    return decision_no is None or (type(decision_no) is int and decision_no > 0)


def _valid_model_complete(data: Mapping[str, object]) -> bool:
    fields = {"selected_action_id", "reason", "reason_truncated"}
    if not fields.intersection(data):
        return True  # Existing records have no short explanation: unknown.
    if not fields.issubset(data) or data.get("outcome") != "success":
        return False
    if type(data.get("selected_action_id")) is not int or type(data.get("reason_truncated")) is not bool:
        return False
    from agents.deepseek_client import normalize_model_reason

    reason = data.get("reason")
    if reason is None:
        return data["reason_truncated"] is False
    return isinstance(reason, str) and normalize_model_reason(reason) == (reason, False)


def _parse_jsonl(path: Path, schema: str) -> None:
    _ordinary(path, "file")
    try:
        for line in path.read_bytes().splitlines():
            row = json.loads(line.decode("utf-8"))
            if not isinstance(row, dict) or type(row.get("version")) is not int:
                raise ValueError
            if schema == GAME_EVIDENCE_EVENT_SCHEMA:
                data = row.get("data")
                event = row.get("event")
                if (
                    set(row) != {"schema", "version", "time_utc", "event", "data"}
                    or row.get("schema") != schema
                    or row["version"] != GAME_EVIDENCE_EVENT_VERSION
                    or not isinstance(row.get("time_utc"), str)
                    or not isinstance(event, str)
                    or event not in _GAME_EVENTS
                    or not isinstance(data, dict)
                    or not set(data).issubset(_GAME_EVENTS[event])
                    or (event == "model_complete" and not _valid_model_complete(data))
                ):
                    raise ValueError
            else:
                data = row.get("data")
                if (
                    set(row) != {"schema", "version", "data"}
                    or row.get("schema") != schema
                    or row["version"] != GAME_EVIDENCE_ROW_VERSION
                    or not isinstance(data, dict)
                ):
                    raise ValueError
                if path.name == "observations.jsonl" and not _valid_observation_row(data):
                    raise ValueError
                if path.name == "decisions.jsonl" and not _valid_decision_row(data):
                    raise ValueError
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise GameEvidenceError("evidence_schema_invalid") from None


def _validate_game_tree(root: Path, entry: Mapping[str, object]) -> None:
    path = root / str(entry["directory"])
    _ordinary(path, "directory")
    _validate_manifest(path, entry)
    try:
        children = {item.name: item for item in path.iterdir()}
    except OSError:
        raise GameEvidenceError("evidence_storage_unavailable") from None
    if set(children) != _GAME_FILES:
        raise GameEvidenceError("evidence_unknown_entry")
    for name in _GAME_FILES - {"requests"}:
        _ordinary(path / name, "file")
    deal = _read_json(path / "deal.json")
    if (
        not isinstance(deal, dict)
        or set(deal) != {"schema", "version", "data"}
        or deal.get("schema") != GAME_EVIDENCE_ROW_SCHEMA
        or deal.get("version") != GAME_EVIDENCE_ROW_VERSION
        or not isinstance(deal.get("data"), dict)
        or deal["data"].get("observation_scope") != "connector_observed_only"
        or not isinstance(deal["data"].get("initial_hand"), list)
    ):
        raise GameEvidenceError("evidence_schema_invalid")
    _parse_jsonl(path / "observations.jsonl", GAME_EVIDENCE_ROW_SCHEMA)
    _parse_jsonl(path / "decisions.jsonl", GAME_EVIDENCE_ROW_SCHEMA)
    _parse_jsonl(path / "timeline.jsonl", GAME_EVIDENCE_EVENT_SCHEMA)
    request_dir = path / "requests"
    _ordinary(request_dir, "directory")
    request_bodies: dict[int, bytes] = {}
    request_metadata: dict[int, dict[str, object]] = {}
    try:
        for request in request_dir.iterdir():
            _ordinary(request, "file")
            if request.name.endswith(".meta.json"):
                if re.fullmatch(r"request_[0-9]{6,}\.meta\.json", request.name) is None:
                    raise GameEvidenceError("evidence_unknown_entry")
                metadata = _read_json(request)
                if (
                    not isinstance(metadata, dict)
                    or set(metadata) != {"schema", "version", "data"}
                    or metadata.get("schema") != GAME_EVIDENCE_ROW_SCHEMA
                    or metadata.get("version") != GAME_EVIDENCE_ROW_VERSION
                    or not isinstance(metadata.get("data"), dict)
                ):
                    raise GameEvidenceError("evidence_schema_invalid")
                number = int(request.name[len("request_"):-len(".meta.json")])
                request_metadata[number] = metadata["data"]
            else:
                match = _REQUEST_NAME.fullmatch(request.name)
                if match is None:
                    raise GameEvidenceError("evidence_unknown_entry")
                body = _read_json(request)
                if (
                    not isinstance(body, dict)
                    or set(body) != {"model", "messages", "temperature", "stream"}
                    or not isinstance(body.get("model"), str)
                    or not isinstance(body.get("messages"), list)
                ):
                    raise GameEvidenceError("evidence_schema_invalid")
                number = int(match.group(1))
                request_bodies[number] = request.read_bytes()
    except OSError:
        raise GameEvidenceError("evidence_storage_unavailable") from None
    if set(request_bodies) != set(request_metadata):
        raise GameEvidenceError("evidence_schema_invalid")
    for number, body in request_bodies.items():
        metadata = request_metadata[number]
        if (
            set(metadata) != {
                "request_no", "decision_no", "sha256", "model", "candidate_action_ids",
                "recommended_action_ids", "relation_references",
            }
            or type(metadata.get("decision_no")) is not int
            or metadata["decision_no"] <= 0
            or metadata.get("request_no") != number
            or not isinstance(metadata.get("sha256"), str)
            or metadata["sha256"] != hashlib.sha256(body).hexdigest()
            or not isinstance(metadata.get("candidate_action_ids"), list)
            or not isinstance(metadata.get("recommended_action_ids"), list)
            or not isinstance(metadata.get("relation_references"), list)
        ):
            raise GameEvidenceError("evidence_schema_invalid")


def _append_restart_event(root: Path, entry: Mapping[str, object], now: datetime) -> None:
    path = root / str(entry["directory"]) / "timeline.jsonl"
    _ordinary(path, "file")
    row = {
        "schema": GAME_EVIDENCE_EVENT_SCHEMA,
        "version": GAME_EVIDENCE_EVENT_VERSION,
        "time_utc": _utc(now),
        "event": "interrupted",
        "data": {"stop_reason": "process_restart_recovery", "status": "interrupted"},
    }
    try:
        with path.open("ab") as stream:
            stream.write(_json_bytes(row))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise GameEvidenceError("evidence_write_failed") from None


def _index_write(path: Path, state: dict[str, object]) -> None:
    _atomic_write(path, _json_bytes(state))


def _root_children(root: Path) -> tuple[str, ...]:
    try:
        names = []
        for item in root.iterdir():
            info = item.lstat()
            if _is_reparse(info):
                raise GameEvidenceError("evidence_link_rejected")
            if item.name in _ROOT_ITEMS:
                if item.name == GAME_EVIDENCE_INDEX and not stat.S_ISREG(info.st_mode):
                    raise GameEvidenceError("evidence_schema_invalid")
                if item.name == GAME_EVIDENCE_LOCK and not stat.S_ISREG(info.st_mode):
                    raise GameEvidenceError("evidence_schema_invalid")
            elif _GAME_NAME.fullmatch(item.name) is not None and stat.S_ISDIR(info.st_mode):
                pass
            else:
                raise GameEvidenceError("evidence_unknown_entry")
            names.append(item.name)
        return tuple(names)
    except GameEvidenceError:
        raise
    except OSError:
        raise GameEvidenceError("evidence_storage_unavailable") from None


def _new_index(capacity: int) -> dict[str, object]:
    return {
        "schema": GAME_EVIDENCE_SCHEMA,
        "version": GAME_EVIDENCE_VERSION,
        "capacity": capacity,
        "next_game_no": 0,
        "entries": [],
        "bindings": [],
        "imports": [],
        "rotation_pending": None,
    }


def _retain_entry_bindings(state: dict[str, object]) -> None:
    """Drop only bindings whose entry has been retired; preserve order/identity."""
    retained = {entry["game_no"] for entry in state["entries"]}
    state["bindings"] = [binding for binding in state["bindings"] if binding["game_no"] in retained]


def _load_index(root: Path, *, repair_retired_bindings: bool = False) -> dict[str, object]:
    path = root / GAME_EVIDENCE_INDEX
    if not os.path.lexists(path):
        raise GameEvidenceError("evidence_schema_invalid")
    state = _validate_index(_read_json(path), allow_retired_bindings=repair_retired_bindings)
    if repair_retired_bindings:
        _retain_entry_bindings(state)
        _validate_index(state)
    return state


def _safe_remove(root: Path, entry: Mapping[str, object]) -> None:
    if entry["kind"] == "summary_only":
        return
    path = root / str(entry["directory"])
    try:
        resolved_root = root.resolve(strict=True)
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        raise GameEvidenceError("evidence_rotation_failed") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or _is_reparse(info)
        or resolved.parent != resolved_root
        or resolved.name != entry["directory"]
    ):
        raise GameEvidenceError("evidence_link_rejected")
    _validate_game_tree(root, entry)
    try:
        shutil.rmtree(resolved)
    except OSError:
        raise GameEvidenceError("evidence_rotation_failed") from None


def _trim(root: Path, index_path: Path, state: dict[str, object]) -> None:
    entries = state["entries"]
    while len(entries) > state["capacity"]:
        oldest = entries[0]
        if oldest["status"] == "in_progress":
            raise GameEvidenceError("evidence_active_capacity")
        if oldest["kind"] == "summary_only":
            del entries[0]
            _retain_entry_bindings(state)
            _index_write(index_path, state)
            continue
        state["rotation_pending"] = oldest["game_no"]
        _index_write(index_path, state)
        _safe_remove(root, oldest)
        del entries[0]
        _retain_entry_bindings(state)
        state["rotation_pending"] = None
        _index_write(index_path, state)


def _recover_rotation(root: Path, index_path: Path, state: dict[str, object]) -> None:
    pending = state["rotation_pending"]
    if pending is None:
        return
    entry = next((item for item in state["entries"] if item["game_no"] == pending), None)
    if entry is None:
        raise GameEvidenceError("evidence_schema_invalid")
    if entry["status"] == "in_progress":
        raise GameEvidenceError("evidence_active_capacity")
    if entry["kind"] == "full" and os.path.lexists(root / str(entry["directory"])):
        _safe_remove(root, entry)
    state["entries"].remove(entry)
    _retain_entry_bindings(state)
    state["rotation_pending"] = None
    _index_write(index_path, state)


def prepare_game_evidence(
    games_directory: Path | str,
    capacity: int,
    *,
    legacy_recent_results: Path | str | None = None,
) -> tuple[int, int]:
    """Create/validate the new rolling index and import one existing summary snapshot."""

    if type(capacity) is not int or capacity <= 0:
        raise GameEvidenceError("evidence_schema_invalid")
    root = Path(games_directory)
    try:
        parent = root.parent
        _ordinary(parent, "directory")
        if os.path.lexists(root):
            _ordinary(root, "directory")
        else:
            root.mkdir()
    except GameEvidenceError:
        raise
    except OSError:
        raise GameEvidenceError("evidence_storage_unavailable") from None
    lock_path = root / GAME_EVIDENCE_LOCK
    try:
        with RecentResultsLock(lock_path):
            names = _root_children(root)
            index_path = root / GAME_EVIDENCE_INDEX
            if GAME_EVIDENCE_INDEX in names:
                state = _load_index(root, repair_retired_bindings=True)
                # No repair, recovery or capacity change is persisted until the
                # whole existing store is checked. A pending deletion may
                # already have removed exactly its own directory.
                indexed = {entry["directory"] for entry in state["entries"] if entry["directory"] is not None}
                present = {name for name in names if _GAME_NAME.fullmatch(name)}
                pending_entry = next((entry for entry in state["entries"]
                                      if entry["game_no"] == state["rotation_pending"]), None)
                missing = {pending_entry["directory"]} if pending_entry is not None else set()
                if present != indexed and present != indexed - missing:
                    raise GameEvidenceError("evidence_unknown_entry")
                for entry in state["entries"]:
                    if entry["kind"] == "full" and entry["directory"] in present:
                        _validate_game_tree(root, entry)
                _recover_rotation(root, index_path, state)
                recovered = False
                for entry in state["entries"]:
                    if entry["kind"] != "full" or entry["status"] != "in_progress":
                        continue
                    # The process guard and workspace lock have already
                    # established that this launch is the only writer. Any
                    # still-active entry is therefore a prior crash/close and
                    # remains an unconfirmed result, never an implied win/loss.
                    entry["status"] = "interrupted"
                    entry["result"] = "result_unconfirmed"
                    now = datetime.now().astimezone()
                    _append_restart_event(root, entry, now)
                    _atomic_write(
                        root / str(entry["directory"]) / "manifest.json",
                        _json_bytes(_manifest(entry, last_stage="recovered_after_restart")),
                    )
                    recovered = True
                if recovered:
                    _index_write(index_path, state)
            else:
                if any(_GAME_NAME.fullmatch(name) for name in names):
                    raise GameEvidenceError("evidence_unknown_entry")
                state = _new_index(capacity)
                if legacy_recent_results is not None and os.path.lexists(legacy_recent_results):
                    try:
                        _ordinary(Path(legacy_recent_results), "file")
                        raw = Path(legacy_recent_results).read_bytes()
                        snapshot, records = read_recent_results(legacy_recent_results)
                    except (OSError, RecentResultsError):
                        raise GameEvidenceError("evidence_legacy_summary_invalid") from None
                    digest = hashlib.sha256(raw).hexdigest()
                    state["imports"].append({"content_sha256": digest, "row_count": len(records)})
                    state["next_game_no"] = snapshot.total_games
                    for record in records:
                        entry = {
                            "game_no": record["game_no"],
                            "directory": None,
                            "kind": "summary_only",
                            "status": "summary_only",
                            "result": record["result"],
                            "local_time": record["display_time"] or "时间未知",
                            "local_timezone": record["local_timezone"],
                            "started_utc": None,
                            "match_digest": None,
                            "evidence_incomplete": False,
                            "error_category": None,
                        }
                        state["entries"].append(entry)
                    state["entries"] = state["entries"][-capacity:]
                state["capacity"] = capacity
                _index_write(index_path, state)
            state["capacity"] = capacity
            _index_write(index_path, state)
            _trim(root, index_path, state)
            names = _root_children(root)
            indexed = {entry["directory"] for entry in state["entries"] if entry["directory"] is not None}
            present = {name for name in names if _GAME_NAME.fullmatch(name)}
            if present != indexed:
                raise GameEvidenceError("evidence_unknown_entry")
            return state["next_game_no"], len(state["entries"])
    except GameEvidenceError:
        raise
    except RecentResultsError as error:
        raise GameEvidenceError("evidence_storage_unavailable") from error


class ManualGameEvidenceRecorder:
    """Best-effort connector observer; evidence errors never affect ACK/action flow."""

    __slots__ = ("root", "failed", "error_category", "_closed", "_clock", "_active_decisions")

    def __init__(self, games_directory: Path | str, *, clock: Callable[[], datetime] = datetime.now) -> None:
        self.root = Path(games_directory)
        self.failed = False
        self.error_category: str | None = None
        self._closed = False
        self._clock = clock
        self._active_decisions: dict[str, int] = {}
        try:
            state = _load_index(self.root)
            for entry in state["entries"]:
                if entry["kind"] == "full":
                    _validate_game_tree(self.root, entry)
        except GameEvidenceError as error:
            raise error

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    def _locked_state(self) -> tuple[RecentResultsLock, dict[str, object]]:
        lock = RecentResultsLock(self.root / GAME_EVIDENCE_LOCK)
        lock.__enter__()
        try:
            state = _load_index(self.root)
            names = _root_children(self.root)
            indexed = {entry["directory"] for entry in state["entries"] if entry["directory"] is not None}
            present = {name for name in names if _GAME_NAME.fullmatch(name)}
            if present != indexed:
                raise GameEvidenceError("evidence_unknown_entry")
            return lock, state
        except BaseException:
            lock.__exit__(None, None, None)
            raise

    def _guard(self, operation: Callable[[], object]) -> object | None:
        if self._closed or self.failed:
            return None
        try:
            return operation()
        except GameEvidenceError as error:
            self._mark_failed(error.category)
        except Exception:
            self._mark_failed("evidence_write_failed")
        return None

    def _mark_failed(self, category: str) -> None:
        self.failed = True
        self.error_category = category if category in _SAFE_CATEGORIES else "evidence_write_failed"
        # Mark an active dossier when the store is still writable. This is a
        # best-effort follow-up only: a diagnostic failure never reaches back
        # into the action, response, or ACK transaction.
        try:
            lock, state = self._locked_state()
            try:
                changed = False
                for entry in state["entries"]:
                    if entry["kind"] != "full" or entry["status"] != "in_progress":
                        continue
                    entry["evidence_incomplete"] = True
                    entry["error_category"] = self.error_category
                    self._write_manifest(entry, "evidence_incomplete")
                    changed = True
                if changed:
                    _index_write(self.root / GAME_EVIDENCE_INDEX, state)
            finally:
                lock.__exit__(None, None, None)
        except Exception:
            pass

    def _digest(self, match_key: str) -> str:
        if not isinstance(match_key, str) or not match_key:
            raise GameEvidenceError("evidence_schema_invalid")
        return hashlib.sha256(match_key.encode("utf-8")).hexdigest()

    def _entry_for(self, state: dict[str, object], match_key: str) -> dict[str, object] | None:
        digest = self._digest(match_key)
        binding = next((item for item in state["bindings"] if item["match_digest"] == digest), None)
        if binding is None:
            return None
        return next((item for item in state["entries"] if item["game_no"] == binding["game_no"]), None)

    def _write_manifest(self, entry: dict[str, object], last_stage: str) -> None:
        path = self.root / str(entry["directory"]) / "manifest.json"
        _atomic_write(path, _json_bytes(_manifest(entry, last_stage=last_stage)))

    def _append(self, entry: Mapping[str, object], filename: str, schema: str, data: dict[str, object]) -> None:
        if not isinstance(data, dict):
            raise GameEvidenceError("evidence_schema_invalid")
        path = self.root / str(entry["directory"]) / filename
        _ordinary(path, "file")
        row = {"schema": schema, "version": GAME_EVIDENCE_ROW_VERSION, "data": data}
        try:
            with path.open("ab") as stream:
                stream.write(_json_bytes(row))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            raise GameEvidenceError("evidence_write_failed") from None

    def _event(self, entry: Mapping[str, object], name: str, data: dict[str, object]) -> None:
        if name == "model_complete" and (
            not set(data).issubset(_GAME_EVENTS[name]) or not _valid_model_complete(data)
        ):
            raise GameEvidenceError("evidence_schema_invalid")
        path = self.root / str(entry["directory"]) / "timeline.jsonl"
        _ordinary(path, "file")
        row = {"schema": GAME_EVIDENCE_EVENT_SCHEMA, "version": GAME_EVIDENCE_EVENT_VERSION,
               "time_utc": _utc(self._clock()), "event": name, "data": data}
        try:
            with path.open("ab") as stream:
                stream.write(_json_bytes(row))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            raise GameEvidenceError("evidence_write_failed") from None
        self._write_manifest(dict(entry), name)

    def begin_game(
        self,
        match_key: str,
        *,
        own_hand: tuple[int, ...] | list[int],
        player_id: int,
        global_state: object,
        initial_hand_observed: bool = True,
    ) -> None:
        def work() -> object:
            digest = self._digest(match_key)
            lock, state = self._locked_state()
            try:
                existing = self._entry_for(state, match_key)
                if existing is not None:
                    if existing["status"] in {"interrupted", "stopped_at_limit"}:
                        existing["status"] = "in_progress"
                        _index_write(self.root / GAME_EVIDENCE_INDEX, state)
                        self._write_manifest(existing, "reconnected")
                        self._event(existing, "connector_resumed", {"game_no": existing["game_no"]})
                        return existing["game_no"]
                    if existing["status"] != "in_progress":
                        return existing["game_no"]
                    self._event(existing, "deal_observed", {"game_no": existing["game_no"]})
                    return existing["game_no"]
                now = self._clock()
                safe_time, local_time, timezone_value, utc = _local_metadata(now)
                game_no = int(state["next_game_no"]) + 1
                directory_name = f"{safe_time}_{game_no:06d}"
                game_path = self.root / directory_name
                try:
                    game_path.mkdir()
                    (game_path / "requests").mkdir()
                    for name in ("observations.jsonl", "decisions.jsonl", "timeline.jsonl"):
                        (game_path / name).open("xb").close()
                    (game_path / "deal.json").open("xb").close()
                except OSError:
                    raise GameEvidenceError("evidence_write_failed") from None
                entry: dict[str, object] = {
                    "game_no": game_no, "directory": directory_name, "kind": "full", "status": "in_progress",
                    "result": "result_unconfirmed", "local_time": local_time, "local_timezone": timezone_value,
                    "started_utc": utc, "match_digest": digest, "evidence_incomplete": False, "error_category": None,
                }
                _atomic_write(game_path / "manifest.json", _json_bytes(_manifest(entry, last_stage="deal_observed")))
                deal = {"schema": GAME_EVIDENCE_ROW_SCHEMA, "version": GAME_EVIDENCE_ROW_VERSION,
                        "data": {"player_id": player_id,
                                 "initial_hand": list(own_hand) if initial_hand_observed else [],
                                 "current_hand_at_first_observation": None if initial_hand_observed else list(own_hand),
                                 "deal_observed": initial_hand_observed,
                                 "global": global_state.to_json(), "observation_scope": "connector_observed_only"}}
                _atomic_write(game_path / "deal.json", _json_bytes(deal))
                state["entries"].append(entry)
                state["next_game_no"] = game_no
                state["bindings"].append({"match_digest": digest, "game_no": game_no})
                _index_write(self.root / GAME_EVIDENCE_INDEX, state)
                self._event(entry, "deal_observed", {"game_no": game_no})
                _trim(self.root, self.root / GAME_EVIDENCE_INDEX, state)
                return game_no
            finally:
                lock.__exit__(None, None, None)
        self._guard(work)

    def _ensure_from_record(self, match_key: str, record: object) -> dict[str, object] | None:
        lock, state = self._locked_state()
        try:
            entry = self._entry_for(state, match_key)
            if entry is not None and entry["status"] == "in_progress":
                return dict(entry)
        finally:
            lock.__exit__(None, None, None)
        # A process may resume after a restart whose first observed request is a play.
        global_state = record.global_state
        self.begin_game(
            match_key,
            own_hand=record.own_hand,
            player_id=record.local_player_id,
            global_state=global_state,
            initial_hand_observed=False,
        )
        lock, state = self._locked_state()
        try:
            entry = self._entry_for(state, match_key)
            return None if entry is None else dict(entry)
        finally:
            lock.__exit__(None, None, None)

    def record_observation(self, match_key: str, record: object, request_stage: object) -> None:
        def work() -> object:
            entry = self._ensure_from_record(match_key, record)
            if entry is None:
                return None
            if getattr(record, "stage", None) == "deal":
                return None
            stage_history = getattr(request_stage, "history", ())
            data = {
                "observation_scope": "connector_observed_only",
                "stage": "play",
                "player_id": record.local_player_id,
                "own_hand": list(record.own_hand),
                "global": record.global_state.to_json(),
                # Keep the wire-observed history distinct from the session's
                # ACK-aligned view. The latter can include an ACK-confirmed
                # local action before it is echoed by a later poll.
                "observed_history": [item.to_json() for item in stage_history],
                "session_history": [item.to_json() for item in record.history],
                "session_latest_window": [item.to_json() for item in record.latest_window],
                "done": list(getattr(request_stage, "done", ())),
                "pass_on": getattr(request_stage, "pass_on", None),
            }
            lock, state = self._locked_state()
            try:
                current = self._entry_for(state, match_key)
                if current is not None and current["status"] == "in_progress":
                    self._append(current, "observations.jsonl", GAME_EVIDENCE_ROW_SCHEMA, data)
                    self._event(current, "public_observation", {"scope": "connector_observed_only"})
            finally:
                lock.__exit__(None, None, None)
            return None
        self._guard(work)

    def begin_decision(self, match_key: str) -> int | None:
        def work() -> object:
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is None:
                    return None
                game_no = int(entry["game_no"])
                event_path = self.root / str(entry["directory"]) / "timeline.jsonl"
                try:
                    old_events = [json.loads(line.decode("utf-8")) for line in event_path.read_bytes().splitlines()]
                    old_numbers = [
                        item["data"].get("decision_no", 0)
                        for item in old_events
                        if isinstance(item, dict) and item.get("event") == "decision_started"
                        and isinstance(item.get("data"), dict)
                    ]
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                    raise GameEvidenceError("evidence_schema_invalid") from None
                previous_no = max((number for number in old_numbers if type(number) is int), default=0)
                decision_no = max(self._active_decisions.get(match_key, 0), previous_no) + 1
                self._active_decisions[match_key] = decision_no
                self._event(entry, "decision_started", {"decision_no": decision_no})
                return decision_no
            finally:
                lock.__exit__(None, None, None)
        result = self._guard(work)
        return result if type(result) is int else None

    def agent_sink(self, match_key: str, decision_no: int) -> Callable[[str, dict[str, object]], None]:
        def emit(event: str, data: dict[str, object]) -> None:
            self.record_agent_event(match_key, decision_no, event, data)
        return emit

    def record_agent_event(self, match_key: str, decision_no: int, event: str, data: dict[str, object]) -> None:
        def work() -> object:
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is None:
                    return None
                if self._active_decisions.get(match_key) != decision_no or entry["status"] != "in_progress":
                    return None
                if event == "request_prepared":
                    body = data.get("body")
                    metadata = data.get("metadata")
                    if not isinstance(body, bytes) or not isinstance(metadata, dict):
                        raise GameEvidenceError("evidence_schema_invalid")
                    request_dir = self.root / str(entry["directory"]) / "requests"
                    numbers = [int(match.group(1)) for child in request_dir.iterdir()
                               if (match := _REQUEST_NAME.fullmatch(child.name)) is not None]
                    request_no = max(numbers, default=0) + 1
                    request_path = request_dir / f"request_{request_no:06d}.json"
                    metadata_path = request_dir / f"request_{request_no:06d}.meta.json"
                    try:
                        with request_path.open("xb") as stream:
                            stream.write(body)
                            stream.flush()
                            os.fsync(stream.fileno())
                    except OSError:
                        raise GameEvidenceError("evidence_write_failed") from None
                    meta = {
                        "schema": GAME_EVIDENCE_ROW_SCHEMA,
                        "version": GAME_EVIDENCE_ROW_VERSION,
                        "data": {
                            "request_no": request_no,
                            "decision_no": decision_no,
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "model": metadata.get("model", "unknown"),
                            "candidate_action_ids": metadata.get("candidate_action_ids", []),
                            "recommended_action_ids": metadata.get("recommended_action_ids", []),
                            "relation_references": metadata.get("relation_references", []),
                        },
                    }
                    _atomic_write(metadata_path, _json_bytes(meta))
                    self._event(entry, "request_prepared", {"request_no": request_no, "decision_no": decision_no,
                                                             "sha256": hashlib.sha256(body).hexdigest()})
                    return request_no
                if event not in {"model_enter", "model_complete"}:
                    raise GameEvidenceError("evidence_schema_invalid")
                self._event(entry, event, {**data, "decision_no": decision_no})
                return None
            finally:
                lock.__exit__(None, None, None)
        self._guard(work)

    def record_action_pending(self, match_key: str, trace: object) -> None:
        def work() -> object:
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is None:
                    return None
                payload = trace.to_json() if callable(getattr(trace, "to_json", None)) else None
                if not isinstance(payload, dict):
                    raise GameEvidenceError("evidence_schema_invalid")
                payload = dict(payload)
                decision_no = self._active_decisions.get(match_key)
                if decision_no is not None:
                    payload["evidence_decision_no"] = decision_no
                self._append(entry, "decisions.jsonl", GAME_EVIDENCE_ROW_SCHEMA, payload)
                selected_id = payload.get("selected_action_id")
                source = payload.get("decision_source")
                self._event(entry, "action_computed", {"selected_action_id": selected_id, "source": source})
                self._event(entry, "header_pending", {"selected_action_id": selected_id, "source": source})
                return None
            finally:
                lock.__exit__(None, None, None)
        self._guard(work)

    def record_acknowledged(self, match_key: str, trace: object | None) -> None:
        def work() -> object:
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is None:
                    return None
                data: dict[str, object] = {"ack": "confirmed"}
                if trace is not None:
                    payload = trace.to_json() if callable(getattr(trace, "to_json", None)) else None
                    if isinstance(payload, dict):
                        data["selected_action_id"] = payload.get("selected_action_id")
                        data["source"] = payload.get("decision_source")
                self._event(entry, "ack_confirmed", data)
                return None
            finally:
                lock.__exit__(None, None, None)
        self._guard(work)

    def record_handler_failure(self, match_key: str) -> None:
        def work() -> object:
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is not None:
                    self._event(entry, "handler_failure", {"category": "fixed_internal_failure"})
            finally:
                lock.__exit__(None, None, None)
            return None
        self._guard(work)

    def record_poll(self, category: str) -> None:
        if category not in {"idle", "payload", "finished", "timeout", "transport_failure", "malformed"}:
            category = "transport_failure"
        def work() -> object:
            lock, state = self._locked_state()
            try:
                for entry in state["entries"]:
                    if entry["kind"] == "full" and entry["status"] == "in_progress":
                        self._event(entry, "poll", {"outcome": category})
            finally:
                lock.__exit__(None, None, None)
            return None
        self._guard(work)

    def record_finished(self, match_key: str, result: str | None, *, platform_finished: bool) -> None:
        def work() -> object:
            digest = self._digest(match_key)
            lock, state = self._locked_state()
            try:
                entry = self._entry_for(state, match_key)
                if entry is None:
                    return None
                if result not in _RESULTS or result in {"result_unconfirmed"}:
                    status = "finished_unconfirmed"
                    result_value = "result_unconfirmed"
                    event = "platform_finish_unconfirmed"
                elif platform_finished:
                    status = "finished"
                    result_value = result
                    event = "platform_result"
                else:
                    status = "finished_unconfirmed"
                    result_value = "result_unconfirmed"
                    event = "platform_finish_unconfirmed"
                entry["status"] = status
                entry["result"] = result_value
                self._write_manifest(entry, event)
                self._event(entry, event, {"result": result_value})
                state["bindings"] = [item for item in state["bindings"] if item["match_digest"] != digest]
                _index_write(self.root / GAME_EVIDENCE_INDEX, state)
                _trim(self.root, self.root / GAME_EVIDENCE_INDEX, state)
                return None
            finally:
                lock.__exit__(None, None, None)
        self._guard(work)

    def record_unconfirmed(self, match_key: str) -> None:
        self.record_finished(match_key, None, platform_finished=False)

    def finish_poll(self) -> None:
        return

    def close(self, stop_reason: str = "interrupted") -> None:
        if self._closed:
            return
        self._closed = True
        status = "interrupted" if stop_reason == "interrupted" else (
            "stopped_at_limit" if stop_reason in {"cycle_limit_unfinished", "wall_limit_unfinished"}
            else "interrupted"
        )
        try:
            lock, state = self._locked_state()
            try:
                for entry in state["entries"]:
                    if entry["kind"] != "full" or entry["status"] != "in_progress":
                        continue
                    entry["status"] = status
                    entry["result"] = "result_unconfirmed"
                    self._write_manifest(entry, stop_reason)
                    self._event(entry, status, {"stop_reason": stop_reason, "status": status})
                _index_write(self.root / GAME_EVIDENCE_INDEX, state)
            finally:
                lock.__exit__(None, None, None)
        except GameEvidenceError as error:
            self._mark_failed(error.category)
        except Exception:
            self._mark_failed("evidence_write_failed")
