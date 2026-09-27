"""Durable, low-sensitivity rolling results for owner-operated Botzone batches."""

from __future__ import annotations

from collections import Counter
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable

from .result_observability import RESULT_CATEGORIES


RECENT_RESULTS_DIRECTORY = "manual-batch-records"
RECENT_RESULTS_FILENAME = "recent-games.json"
RECENT_RESULTS_LOCK_FILENAME = ".writer.lock"
RECENT_RESULTS_SCHEMA = "botzone_manual_batch_recent_results"
RECENT_RESULTS_VERSION = 1
RESULT_UNCONFIRMED = "result_unconfirmed"
RECENT_RESULT_CATEGORIES = RESULT_CATEGORIES | {RESULT_UNCONFIRMED}
LEGACY_RESULT_SCHEMA = "botzone_manual_batch_game_result"
LEGACY_RESULT_VERSION = 1
NEW_BATCH_MARKER = "batch-format.json"
NEW_BATCH_SCHEMA = "botzone_manual_batch_run"
NEW_BATCH_VERSION = 2
_MAX_ACTIVE_GAMES = 1024


class RecentResultsError(ValueError):
    """Fixed-category error for managed rolling-result storage."""

    __slots__ = ("category",)

    def __init__(self, category: str) -> None:
        self.category = category if re.fullmatch(r"[a-z_]+", category) else "recent_results_failed"
        super().__init__(self.category)


@dataclass(frozen=True, slots=True)
class RecentResultsSnapshot:
    capacity: int
    total_games: int
    retained_count: int
    result_category_counts: tuple[tuple[str, int], ...]


def recent_results_paths(workspace_root: Path | str) -> tuple[Path, Path, Path]:
    root = Path(workspace_root)
    directory = root / RECENT_RESULTS_DIRECTORY
    return directory, directory / RECENT_RESULTS_FILENAME, directory / RECENT_RESULTS_LOCK_FILENAME


def ensure_recent_results_directory(workspace_root: Path | str) -> Path:
    root = Path(workspace_root)
    _ordinary_directory(root, "workspace_unavailable")
    directory, _, _ = recent_results_paths(root)
    if os.path.lexists(directory):
        _ordinary_directory(directory, "recent_results_directory_invalid")
        return directory
    try:
        directory.mkdir()
    except OSError:
        raise RecentResultsError("recent_results_directory_invalid") from None
    _ordinary_directory(directory, "recent_results_directory_invalid")
    return directory


def write_new_batch_marker(batch_directory: Path) -> None:
    marker = batch_directory / NEW_BATCH_MARKER
    try:
        with marker.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"schema": NEW_BATCH_SCHEMA, "version": NEW_BATCH_VERSION}, sort_keys=True))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise RecentResultsError("workspace_prepare_failed") from None


def _is_reparse_point(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _ordinary_directory(path: Path, category: str) -> None:
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        raise RecentResultsError(category) from None
    if not stat.S_ISDIR(info.st_mode) or _is_reparse_point(info) or os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(resolved)):
        raise RecentResultsError(category)


def _strict_int(value: object, *, minimum: int = 0, maximum: int | None = None) -> bool:
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def _valid_record(record: object, expected_game_no: int) -> bool:
    if not isinstance(record, dict) or set(record) != {
        "game_no",
        "record_key",
        "display_time",
        "local_timezone",
        "timestamp_kind",
        "result",
        "source",
        "source_game_no",
    }:
        return False
    if (
        not _strict_int(record.get("game_no"), minimum=1)
        or record["game_no"] != expected_game_no
        or not isinstance(record.get("record_key"), str)
        or not record["record_key"]
        or not isinstance(record.get("result"), str)
        or record["result"] not in RECENT_RESULT_CATEGORIES
        or not isinstance(record.get("source"), str)
        or record["source"] not in {"connector", "legacy_import"}
        or not isinstance(record.get("timestamp_kind"), str)
        or record["timestamp_kind"] not in {"completed_at", "recorded_at", "unknown"}
    ):
        return False
    display_time = record.get("display_time")
    timezone_value = record.get("local_timezone")
    source_game_no = record.get("source_game_no")
    if display_time is None:
        if timezone_value is not None or record.get("timestamp_kind") != "unknown":
            return False
    elif (
        not isinstance(display_time, str)
        or re.fullmatch(r"[0-9]{4}_[0-9]{1,2}_[0-9]{1,2}_[0-9]{2}:[0-9]{2}", display_time) is None
        or not isinstance(timezone_value, dict)
        or set(timezone_value) != {"name", "offset"}
        or not isinstance(timezone_value.get("name"), str)
        or not timezone_value["name"]
        or not isinstance(timezone_value.get("offset"), str)
        or re.fullmatch(r"[+-][0-9]{2}:[0-9]{2}", timezone_value["offset"]) is None
        or record.get("timestamp_kind") == "unknown"
    ):
        return False
    if source_game_no is not None and not _strict_int(source_game_no, minimum=1):
        return False
    if record.get("source") == "legacy_import" and (source_game_no is None or display_time is not None):
        return False
    if record.get("source") == "connector" and source_game_no is not None:
        return False
    return True


def _validate_state(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != {
        "schema",
        "version",
        "capacity",
        "total_games",
        "active_games",
        "records",
        "imports",
    }:
        raise RecentResultsError("recent_results_invalid")
    if (
        payload.get("schema") != RECENT_RESULTS_SCHEMA
        or not _strict_int(payload.get("version"), minimum=RECENT_RESULTS_VERSION, maximum=RECENT_RESULTS_VERSION)
        or not _strict_int(payload.get("capacity"), minimum=1)
        or not _strict_int(payload.get("total_games"), minimum=0)
        or not _strict_int(payload.get("active_games"), minimum=0, maximum=_MAX_ACTIVE_GAMES)
        or not isinstance(payload.get("records"), list)
        or not isinstance(payload.get("imports"), list)
    ):
        raise RecentResultsError("recent_results_invalid")
    records = payload["records"]
    capacity = payload["capacity"]
    total_games = payload["total_games"]
    if len(records) > capacity or len(records) > total_games:
        raise RecentResultsError("recent_results_invalid")
    first_game_no = total_games - len(records) + 1
    seen_keys: set[str] = set()
    for index, record in enumerate(records):
        if not _valid_record(record, first_game_no + index) or record["record_key"] in seen_keys:
            raise RecentResultsError("recent_results_invalid")
        seen_keys.add(record["record_key"])
    seen_sources: set[str] = set()
    for imported in payload["imports"]:
        if (
            not isinstance(imported, dict)
            or set(imported) != {"source_key", "content_sha256", "fingerprint", "row_count"}
            or any(
                not isinstance(imported.get(key), str)
                or re.fullmatch(r"[0-9a-f]{64}", imported[key]) is None
                for key in ("source_key", "content_sha256", "fingerprint")
            )
            or not _strict_int(imported.get("row_count"), minimum=0)
            or imported["source_key"] in seen_sources
        ):
            raise RecentResultsError("recent_results_invalid")
        seen_sources.add(imported["source_key"])
    return payload


def _load_state(path: Path) -> dict[str, object]:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or _is_reparse_point(info):
            raise RecentResultsError("recent_results_invalid")
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except RecentResultsError:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise RecentResultsError("recent_results_invalid") from None
    return _validate_state(payload)


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        raise RecentResultsError("recent_results_write_failed") from None


def _parse_legacy_bytes(raw: bytes) -> tuple[tuple[int, str], ...]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError:
        raise RecentResultsError("legacy_results_invalid") from None
    rows: list[tuple[int, str]] = []
    for expected_no, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            raise RecentResultsError("legacy_results_invalid") from None
        if (
            not isinstance(record, dict)
            or set(record) != {"game_no", "result", "schema", "version"}
            or not _strict_int(record.get("game_no"), minimum=1)
            or record["game_no"] != expected_no
            or record.get("schema") != LEGACY_RESULT_SCHEMA
            or not _strict_int(record.get("version"), minimum=LEGACY_RESULT_VERSION, maximum=LEGACY_RESULT_VERSION)
            or not isinstance(record.get("result"), str)
            or record["result"] not in RESULT_CATEGORIES
        ):
            raise RecentResultsError("legacy_results_invalid")
        rows.append((expected_no, record["result"]))
    return tuple(rows)


def _candidate_directories(workspace_root: Path) -> tuple[Path, ...]:
    try:
        candidates: list[Path] = []
        for child in workspace_root.iterdir():
            if not child.name.startswith("manual-batch-"):
                continue
            try:
                info = child.lstat()
            except OSError:
                raise RecentResultsError("legacy_import_scan_failed") from None
            if _is_reparse_point(info):
                raise RecentResultsError("legacy_import_source_invalid")
            if not stat.S_ISDIR(info.st_mode):
                continue
            _ordinary_directory(child, "legacy_import_source_invalid")
            marker = child / NEW_BATCH_MARKER
            if os.path.lexists(marker):
                try:
                    marker_info = marker.lstat()
                    if not stat.S_ISREG(marker_info.st_mode) or _is_reparse_point(marker_info):
                        raise RecentResultsError("legacy_import_source_invalid")
                    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
                except RecentResultsError:
                    raise
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                    raise RecentResultsError("legacy_import_source_invalid") from None
                if marker_payload != {"schema": NEW_BATCH_SCHEMA, "version": NEW_BATCH_VERSION}:
                    raise RecentResultsError("legacy_import_source_invalid")
                continue
            result_path = child / "game-results.jsonl"
            if not os.path.lexists(result_path):
                continue
            try:
                result_info = result_path.lstat()
                if not stat.S_ISREG(result_info.st_mode) or _is_reparse_point(result_info):
                    raise RecentResultsError("legacy_import_source_invalid")
                raw = result_path.read_bytes()
            except RecentResultsError:
                raise
            except OSError:
                raise RecentResultsError("legacy_import_source_invalid") from None
            rows = _parse_legacy_bytes(raw)
            if rows:
                candidates.append(child)
        return tuple(candidates)
    except RecentResultsError:
        raise
    except OSError:
        raise RecentResultsError("legacy_import_scan_failed") from None


def _resolve_source(workspace_root: Path, import_from: Path | str | None) -> Path | None:
    if import_from is None:
        candidates = _candidate_directories(workspace_root)
        if len(candidates) > 1:
            raise RecentResultsError("legacy_import_ambiguous")
        return candidates[0] if candidates else None
    candidate = Path(import_from)
    if not candidate.is_absolute():
        if candidate.name != str(candidate) or not candidate.name.startswith("manual-batch-"):
            raise RecentResultsError("legacy_import_source_invalid")
        candidate = workspace_root / candidate
    try:
        candidate_info = candidate.lstat()
        if not stat.S_ISDIR(candidate_info.st_mode) or _is_reparse_point(candidate_info):
            raise RecentResultsError("legacy_import_source_invalid")
        absolute = Path(os.path.abspath(candidate))
        resolved_root = workspace_root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if (
            os.path.normcase(str(absolute)) != os.path.normcase(str(resolved))
            or resolved.parent != resolved_root
            or not resolved.name.startswith("manual-batch-")
        ):
            raise RecentResultsError("legacy_import_source_invalid")
        _ordinary_directory(resolved, "legacy_import_source_invalid")
    except OSError:
        raise RecentResultsError("legacy_import_source_invalid") from None
    if os.path.lexists(resolved / NEW_BATCH_MARKER):
        raise RecentResultsError("legacy_import_source_invalid")
    result_path = resolved / "game-results.jsonl"
    try:
        result_info = result_path.lstat()
        if not stat.S_ISREG(result_info.st_mode) or _is_reparse_point(result_info):
            raise RecentResultsError("legacy_import_source_invalid")
    except RecentResultsError:
        raise
    except OSError:
        raise RecentResultsError("legacy_import_source_invalid") from None
    return resolved


def _source_metadata(source: Path, raw: bytes) -> dict[str, object]:
    source_key = hashlib.sha256(source.name.casefold().encode("utf-8")).hexdigest()
    content_hash = hashlib.sha256(raw).hexdigest()
    fingerprint = hashlib.sha256((source_key + content_hash).encode("ascii")).hexdigest()
    return {
        "source_key": source_key,
        "content_sha256": content_hash,
        "fingerprint": fingerprint,
    }


def _read_legacy_source(source: Path) -> tuple[bytes, tuple[tuple[int, str], ...]]:
    try:
        result_path = source / "game-results.jsonl"
        info = result_path.lstat()
        if not stat.S_ISREG(info.st_mode) or _is_reparse_point(info):
            raise RecentResultsError("legacy_import_source_invalid")
        raw = result_path.read_bytes()
    except RecentResultsError:
        raise
    except OSError:
        raise RecentResultsError("legacy_import_source_invalid") from None
    return raw, _parse_legacy_bytes(raw)


def _legacy_record(game_no: int, source_game_no: int, fingerprint: str, result: str) -> dict[str, object]:
    return {
        "game_no": game_no,
        "record_key": f"legacy-{fingerprint[:16]}-{source_game_no:06d}",
        "display_time": None,
        "local_timezone": None,
        "timestamp_kind": "unknown",
        "result": result,
        "source": "legacy_import",
        "source_game_no": source_game_no,
    }


def prepare_recent_results(
    workspace_root: Path | str,
    capacity: int,
    *,
    import_from: Path | str | None = None,
) -> RecentResultsSnapshot:
    """Prepare the managed store, importing one exact legacy source at most once."""

    if type(capacity) is not int or capacity <= 0:
        raise RecentResultsError("invalid_recent_results_capacity")
    root = Path(workspace_root)
    _ordinary_directory(root, "workspace_unavailable")
    directory, state_path, _ = recent_results_paths(root)
    ensure_recent_results_directory(root)

    if os.path.lexists(state_path):
        state = _load_state(state_path)
        if import_from is not None:
            source = _resolve_source(root, import_from)
            if source is None:
                raise RecentResultsError("legacy_import_source_invalid")
            raw, rows = _read_legacy_source(source)
            metadata = _source_metadata(source, raw)
            imports = state["imports"]
            matching_key = next((item for item in imports if item["source_key"] == metadata["source_key"]), None)
            if matching_key is not None:
                if matching_key["fingerprint"] != metadata["fingerprint"]:
                    raise RecentResultsError("legacy_import_source_changed")
                if matching_key["row_count"] != len(rows):
                    raise RecentResultsError("legacy_import_source_changed")
            elif state["total_games"] != 0 or state["active_games"] != 0:
                raise RecentResultsError("legacy_import_not_initial")
            else:
                _append_import(state, metadata, rows)
        elif state["total_games"] == 0 and not state["imports"]:
            source = _resolve_source(root, None)
            if source is not None:
                raw, rows = _read_legacy_source(source)
                _append_import(state, _source_metadata(source, raw), rows)
        state["capacity"] = capacity
        state["records"] = state["records"][-capacity:]
        _atomic_write(state_path, state)
    else:
        source = _resolve_source(root, import_from)
        state = {
            "schema": RECENT_RESULTS_SCHEMA,
            "version": RECENT_RESULTS_VERSION,
            "capacity": capacity,
            "total_games": 0,
            "active_games": 0,
            "records": [],
            "imports": [],
        }
        if source is not None:
            raw, rows = _read_legacy_source(source)
            _append_import(state, _source_metadata(source, raw), rows)
        _atomic_write(state_path, state)
    return snapshot_from_state(state)


def _append_import(
    state: dict[str, object],
    metadata: dict[str, object],
    rows: tuple[tuple[int, str], ...],
) -> None:
    imports = state["imports"]
    if any(item["source_key"] == metadata["source_key"] for item in imports):
        raise RecentResultsError("legacy_import_source_changed")
    state["imports"].append({**metadata, "row_count": len(rows)})
    for source_game_no, result in rows:
        next_game_no = state["total_games"] + 1
        state["records"].append(_legacy_record(next_game_no, source_game_no, metadata["fingerprint"], result))
        state["total_games"] = next_game_no
    state["records"] = state["records"][-state["capacity"]:]


def snapshot_from_state(state: dict[str, object]) -> RecentResultsSnapshot:
    counts = Counter(record["result"] for record in state["records"])
    return RecentResultsSnapshot(
        capacity=state["capacity"],
        total_games=state["total_games"],
        retained_count=len(state["records"]),
        result_category_counts=tuple(sorted(counts.items())),
    )


def read_recent_results(path: Path | str) -> tuple[RecentResultsSnapshot, tuple[dict[str, object], ...]]:
    state = _load_state(Path(path))
    return snapshot_from_state(state), tuple(dict(item) for item in state["records"])


def _local_timestamp(now: datetime) -> tuple[str, dict[str, str], str]:
    local = now.astimezone()
    offset = local.utcoffset()
    if offset is None:
        offset_text = "+00:00"
    else:
        seconds = int(offset.total_seconds())
        sign = "+" if seconds >= 0 else "-"
        seconds = abs(seconds)
        offset_text = f"{sign}{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"
    zone_name = local.tzname() or "UTC"
    display = f"{local.year}_{local.month}_{local.day}_{local.hour:02d}:{local.minute:02d}"
    safe = f"{local.year}_{local.month}_{local.day}_{local.hour:02d}-{local.minute:02d}"
    return display, {"name": zone_name, "offset": offset_text}, safe


class RollingGameResultRecorder:
    """Persist only fixed result categories and a count of observed active games."""

    __slots__ = (
        "path",
        "capacity",
        "failed",
        "_active_tokens",
        "_closed_tokens",
        "_terminal_tokens",
        "_recorded",
        "_closed",
        "_clock",
    )

    def __init__(self, path: Path | str, capacity: int, *, clock: Callable[[], datetime] = datetime.now) -> None:
        self.path = Path(path)
        self.capacity = capacity
        self.failed = False
        self._active_tokens: dict[str, None] = {}
        self._closed_tokens: set[str] = set()
        self._terminal_tokens: set[str] = set()
        self._recorded = 0
        self._closed = False
        self._clock = clock
        try:
            state = _load_state(self.path)
            if type(capacity) is not int or capacity <= 0 or state["capacity"] != capacity:
                raise RecentResultsError("recent_results_invalid")
            if state["active_games"]:
                for _ in range(state["active_games"]):
                    self._append_record(state, RESULT_UNCONFIRMED, "recorded_at")
                state["active_games"] = 0
                _atomic_write(self.path, state)
        except RecentResultsError:
            raise
        except Exception:
            raise RecentResultsError("recent_results_invalid") from None

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        try:
            _load_state(self.path)
        except RecentResultsError:
            self.failed = True
            return "failed"
        return "ok"

    @property
    def recorded_count(self) -> int:
        return self._recorded

    def snapshot(self) -> RecentResultsSnapshot:
        return snapshot_from_state(_load_state(self.path))

    def begin_game(self, match_key: str) -> None:
        if self._closed or match_key in self._active_tokens or match_key in self._closed_tokens:
            return
        for previous_match in tuple(self._active_tokens):
            if previous_match != match_key and previous_match not in self._terminal_tokens:
                self.finish_unconfirmed(previous_match)
        self._active_tokens[match_key] = None
        try:
            state = _load_state(self.path)
            if state["active_games"] >= _MAX_ACTIVE_GAMES:
                raise RecentResultsError("recent_results_invalid")
            state["active_games"] += 1
            _atomic_write(self.path, state)
        except Exception:
            self.failed = True

    def prepare_poll(self, terminal_match_keys: set[str]) -> None:
        self._terminal_tokens = set(terminal_match_keys)

    def finish_poll(self) -> None:
        self._terminal_tokens.clear()

    def record_finished(self, category: str, match_key: str | None = None) -> None:
        if self._closed or not isinstance(category, str) or category not in RESULT_CATEGORIES:
            self.failed = True
            return
        was_active = match_key is not None and match_key in self._active_tokens
        if match_key is not None:
            self._active_tokens.pop(match_key, None)
            self._closed_tokens.add(match_key)
            self._terminal_tokens.discard(match_key)
        self._record(category, "completed_at", increment_run=True, decrement_active=was_active)

    def record(self, category: str) -> None:
        self.record_finished(category)

    def finish_unconfirmed(self, match_key: str) -> None:
        if self._closed or match_key not in self._active_tokens:
            return
        self._active_tokens.pop(match_key, None)
        self._closed_tokens.add(match_key)
        self._terminal_tokens.discard(match_key)
        self._record(RESULT_UNCONFIRMED, "recorded_at", decrement_active=True)

    def close(self) -> None:
        if self._closed:
            return
        for match_key in tuple(self._active_tokens):
            self.finish_unconfirmed(match_key)
        self._closed = True

    def _record(self, category: str, timestamp_kind: str, *, increment_run: bool = False, decrement_active: bool = False) -> None:
        try:
            state = _load_state(self.path)
            if decrement_active:
                if state["active_games"] <= 0:
                    raise RecentResultsError("recent_results_invalid")
                state["active_games"] -= 1
            self._append_record(state, category, timestamp_kind)
            _atomic_write(self.path, state)
            if increment_run:
                self._recorded += 1
        except Exception:
            self.failed = True

    def _append_record(self, state: dict[str, object], category: str, timestamp_kind: str) -> None:
        now = self._clock().astimezone()
        display, timezone_value, safe_stamp = _local_timestamp(now)
        game_no = state["total_games"] + 1
        record = {
            "game_no": game_no,
            "record_key": f"{safe_stamp}-{game_no:06d}",
            "display_time": display,
            "local_timezone": timezone_value,
            "timestamp_kind": timestamp_kind,
            "result": category,
            "source": "connector",
            "source_game_no": None,
        }
        if not _valid_record(record, game_no):
            raise RecentResultsError("recent_results_invalid")
        state["total_games"] = game_no
        state["records"].append(record)
        state["records"] = state["records"][-state["capacity"]:]


class CompositeGameResultRecorder:
    """Keep per-run evidence and the rolling window in one non-blocking interface."""

    __slots__ = ("_run_recorder", "_recent_recorder", "failed", "_run_failed", "_recent_failed")

    def __init__(self, run_recorder: object, recent_recorder: RollingGameResultRecorder) -> None:
        self._run_recorder = run_recorder
        self._recent_recorder = recent_recorder
        self.failed = False
        self._run_failed = False
        self._recent_failed = False

    @property
    def status(self) -> str:
        if self.failed or self._run_failed or self._run_recorder.status != "ok":
            return "failed"
        return "ok"

    @property
    def recent_status(self) -> str:
        return "failed" if self.failed or self._recent_failed else self._recent_recorder.status

    @property
    def recorded_count(self) -> int:
        return self._run_recorder.recorded_count

    def snapshot(self) -> RecentResultsSnapshot:
        return self._recent_recorder.snapshot()

    def begin_game(self, match_key: str) -> None:
        try:
            self._recent_recorder.begin_game(match_key)
        except Exception:
            self._recent_failed = True

    def prepare_poll(self, terminal_match_keys: set[str]) -> None:
        try:
            self._recent_recorder.prepare_poll(terminal_match_keys)
        except Exception:
            self._recent_failed = True

    def finish_poll(self) -> None:
        try:
            self._recent_recorder.finish_poll()
        except Exception:
            self._recent_failed = True

    def record_finished(self, category: str, match_key: str | None = None) -> None:
        try:
            self._run_recorder.record(category)
        except Exception:
            self._run_failed = True
        try:
            self._recent_recorder.record_finished(category, match_key)
        except Exception:
            self._recent_failed = True

    def record(self, category: str) -> None:
        self.record_finished(category)

    def finish_unconfirmed(self, match_key: str) -> None:
        try:
            self._recent_recorder.finish_unconfirmed(match_key)
        except Exception:
            self._recent_failed = True

    def close(self) -> None:
        try:
            self._run_recorder.close()
        except Exception:
            self._run_failed = True
        try:
            self._recent_recorder.close()
        except Exception:
            self._recent_failed = True


class RecentResultsLock(AbstractContextManager["RecentResultsLock"]):
    """Advisory process lock held by the launcher while its connector runs."""

    __slots__ = ("path", "_stream", "_locked")

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._stream = None
        self._locked = False

    def __enter__(self) -> "RecentResultsLock":
        try:
            _ordinary_directory(self.path.parent, "recent_results_directory_invalid")
            if os.path.lexists(self.path):
                info = self.path.lstat()
                if not stat.S_ISREG(info.st_mode) or _is_reparse_point(info):
                    raise RecentResultsError("recent_results_lock_unavailable")
            self._stream = self.path.open("a+b")
            self._stream.seek(0, os.SEEK_END)
            if self._stream.tell() == 0:
                self._stream.write(b"0")
                self._stream.flush()
            self._stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locked = True
            return self
        except RecentResultsError:
            self.__exit__(None, None, None)
            raise
        except OSError:
            self.__exit__(None, None, None)
            raise RecentResultsError("recent_results_in_use") from None

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        stream, self._stream = self._stream, None
        if stream is None:
            return False
        try:
            if self._locked:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            stream.close()
        except OSError:
            pass
        self._locked = False
        return False
