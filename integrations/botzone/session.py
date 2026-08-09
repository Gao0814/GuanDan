"""Atomic, match-isolated state storage for the mock connector."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from .cards import RANKS
from .models import ActionClaim, DealRequest, GlobalState, HistoryEntry, PlayRequest
from .poll import FinishedRow
from .protocol import ProtocolValidationError, parse_action_claim


SESSION_SCHEMA: Final[str] = "botzone_no_tribute_session"
SESSION_VERSION: Final[int] = 1


class SessionStorageError(ValueError):
    """Stored state is unavailable, invalid, or cannot be written atomically."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    match_id: str
    request_digest: str
    stage: str
    global_state: GlobalState
    own_hand: tuple[int, ...]
    history: tuple[HistoryEntry, ...]
    pending_response: bytes | None
    delivery_state: str
    handler_completed: bool
    cached_response: bytes | None
    cached_response_digest: str | None
    finished: FinishedRow | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "schema": SESSION_SCHEMA,
            "version": SESSION_VERSION,
            "match_id": self.match_id,
            "request_digest": self.request_digest,
            "stage": self.stage,
            "global": self.global_state.to_json(),
            "own_hand": list(self.own_hand),
            "history": [entry.to_json() for entry in self.history],
            "pending_response": _encode_bytes(self.pending_response),
            "delivery_state": self.delivery_state,
            "handler_completed": self.handler_completed,
            "cached_response": _encode_bytes(self.cached_response),
            "cached_response_digest": self.cached_response_digest,
            "finished": _finished_to_json(self.finished),
        }


@dataclass(frozen=True, slots=True)
class PendingDelivery:
    match_id: str
    header_name: str
    response: bytes


def request_digest(request_bytes: bytes) -> str:
    return hashlib.sha256(request_bytes).hexdigest()


def _validate_match_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or "\r" in value
        or "\n" in value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise SessionStorageError("invalid_match_id")
    return value


def _encode_bytes(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def _decode_bytes(value: object, label: str) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SessionStorageError(f"invalid_{label}")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise SessionStorageError(f"invalid_{label}") from exc


def _finished_to_json(value: FinishedRow | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "match_id": value.match_id,
        "local_player_id": value.local_player_id,
        "player_count": value.player_count,
        "scores": list(value.scores),
    }


def _parse_global(value: object) -> GlobalState:
    if not isinstance(value, dict) or set(value) != {"level", "tribute", "first", "last"}:
        raise SessionStorageError("invalid_global")
    level = value["level"]
    tribute = value["tribute"]
    if not isinstance(level, str) or level not in RANKS or type(tribute) is not int or tribute != 0:
        raise SessionStorageError("invalid_global")
    if value["first"] is not None or value["last"] is not None:
        raise SessionStorageError("invalid_global")
    return GlobalState(level, 0, None, None)


def _parse_history(value: object, level: str) -> tuple[HistoryEntry, ...]:
    if not isinstance(value, list) or len(value) > 4:
        raise SessionStorageError("invalid_history")
    history: list[HistoryEntry] = []
    try:
        for item in value:
            if not isinstance(item, dict) or set(item) != {"player", "response"}:
                raise SessionStorageError("invalid_history")
            player = item["player"]
            if type(player) is not int or not 0 <= player <= 3:
                raise SessionStorageError("invalid_history")
            history.append(HistoryEntry(player, parse_action_claim(item["response"], level=level)))
    except ProtocolValidationError as exc:
        raise SessionStorageError("invalid_history") from exc
    return tuple(history)


def _parse_finished(value: object) -> FinishedRow | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"match_id", "local_player_id", "player_count", "scores"}:
        raise SessionStorageError("invalid_finished")
    match_id = value["match_id"]
    seat = value["local_player_id"]
    count = value["player_count"]
    scores = value["scores"]
    if (
        not isinstance(match_id, str)
        or type(seat) is not int
        or type(count) is not int
        or not isinstance(scores, list)
        or any(type(score) is not int for score in scores)
        or not 0 <= seat <= 3
        or not 0 <= count <= 4
        or len(scores) != count
    ):
        raise SessionStorageError("invalid_finished")
    return FinishedRow(match_id, seat, count, tuple(scores))


def _record_from_json(value: object) -> SessionRecord:
    if not isinstance(value, dict):
        raise SessionStorageError("invalid_session")
    expected = {
        "schema", "version", "match_id", "request_digest", "stage", "global", "own_hand", "history",
        "pending_response", "delivery_state", "handler_completed", "cached_response",
        "cached_response_digest", "finished",
    }
    if (
        set(value) != expected
        or value["schema"] != SESSION_SCHEMA
        or type(value["version"]) is not int
        or value["version"] != SESSION_VERSION
    ):
        raise SessionStorageError("incompatible_session")
    match_id = value["match_id"]
    digest = value["request_digest"]
    stage = value["stage"]
    own_hand = value["own_hand"]
    delivery_state = value["delivery_state"]
    completed = value["handler_completed"]
    cached_digest = value["cached_response_digest"]
    if (
        not isinstance(match_id, str)
        or not isinstance(digest, str)
        or not isinstance(stage, str)
        or not isinstance(own_hand, list)
        or any(type(card_id) is not int or not 0 <= card_id <= 107 for card_id in own_hand)
        or len(set(own_hand)) != len(own_hand)
        or delivery_state not in {"idle", "pending", "inflight", "finished"}
        or type(completed) is not bool
        or cached_digest is not None and not isinstance(cached_digest, str)
    ):
        raise SessionStorageError("invalid_session")
    _validate_match_id(match_id)
    pending = _decode_bytes(value["pending_response"], "pending_response")
    cached = _decode_bytes(value["cached_response"], "cached_response")
    if stage == "deal" and len(own_hand) != 27:
        raise SessionStorageError("invalid_session")
    if pending is not None and delivery_state not in {"pending", "inflight"}:
        raise SessionStorageError("invalid_session")
    if cached is None and cached_digest is not None:
        raise SessionStorageError("invalid_session")
    finished = _parse_finished(value["finished"])
    if finished is not None and finished.match_id != match_id:
        raise SessionStorageError("session_key_mismatch")
    return SessionRecord(
        match_id=match_id,
        request_digest=digest,
        stage=stage,
        global_state=_parse_global(value["global"]),
        own_hand=tuple(own_hand),
        history=_parse_history(value["history"], _parse_global(value["global"]).level),
        pending_response=pending,
        delivery_state=delivery_state,
        handler_completed=completed,
        cached_response=cached,
        cached_response_digest=cached_digest,
        finished=finished,
    )


class SessionStore:
    """Disk-backed store; all persisted files are namespaced by a hashed key."""

    def __init__(self, state_directory: Path | str) -> None:
        self._root = Path(state_directory)

    def _path(self, match_id: str) -> Path:
        match_id = _validate_match_id(match_id)
        digest = hashlib.sha256(match_id.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"

    def load(self, match_id: str) -> SessionRecord | None:
        path = self._path(match_id)
        if not path.exists():
            return None
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SessionStorageError("corrupt_session") from exc
        record = _record_from_json(decoded)
        if record.match_id != match_id:
            raise SessionStorageError("session_key_mismatch")
        if record.delivery_state == "inflight" and record.pending_response is not None:
            record = replace(record, delivery_state="pending")
            self.save(record)
        return record

    def save(self, record: SessionRecord) -> None:
        path = self._path(record.match_id)
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(record.to_json(), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
            with tempfile.NamedTemporaryFile(dir=self._root, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            try:
                if "temporary" in locals() and temporary.exists():
                    temporary.unlink()
            except OSError:
                pass
            raise SessionStorageError("atomic_write_failed") from exc

    def prepare(self, match_id: str, request_bytes: bytes, stage: DealRequest | PlayRequest) -> tuple[SessionRecord, bool]:
        digest = request_digest(request_bytes)
        record = self.load(match_id)
        if record is not None and record.finished is not None:
            raise SessionStorageError("finished_session")
        if record is not None and record.request_digest == digest:
            if record.pending_response is None and record.cached_response_digest == digest and record.cached_response is not None:
                record = replace(record, pending_response=record.cached_response, delivery_state="pending")
                self.save(record)
            return record, not record.handler_completed
        if record is not None and record.pending_response is not None:
            raise SessionStorageError("pending_response_exists")
        if isinstance(stage, PlayRequest) and record is None:
            raise SessionStorageError("play_without_state")
        own_hand = stage.deliver if isinstance(stage, DealRequest) else record.own_hand
        history = () if isinstance(stage, DealRequest) else stage.history
        global_state = stage.global_state
        prepared = SessionRecord(
            match_id=match_id,
            request_digest=digest,
            stage="deal" if isinstance(stage, DealRequest) else "play",
            global_state=global_state,
            own_hand=own_hand,
            history=history,
            pending_response=None,
            delivery_state="idle",
            handler_completed=False,
            cached_response=None,
            cached_response_digest=None,
        )
        self.save(prepared)
        return prepared, True

    def complete_handler(self, record: SessionRecord, response: bytes | None) -> SessionRecord:
        if response is not None and not isinstance(response, bytes):
            raise SessionStorageError("handler_response_not_bytes")
        if response is not None and (b"\r" in response or b"\n" in response):
            raise SessionStorageError("header_injection")
        next_record = replace(
            record,
            pending_response=response,
            delivery_state="pending" if response is not None else "idle",
            handler_completed=True,
            cached_response=response,
            cached_response_digest=record.request_digest if response is not None else None,
        )
        self.save(next_record)
        return next_record

    def reserve_handler(self, record: SessionRecord) -> SessionRecord:
        if record.handler_completed:
            return record
        reserved = replace(record, handler_completed=True)
        self.save(reserved)
        return reserved

    def pending_deliveries(self) -> tuple[PendingDelivery, ...]:
        if not self._root.exists():
            return ()
        deliveries: list[PendingDelivery] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                record = _record_from_json(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, SessionStorageError) as exc:
                raise SessionStorageError("corrupt_session") from exc
            if record.pending_response is not None and record.delivery_state in {"pending", "inflight"}:
                header_name = f"X-Match-{record.match_id}"
                if "\r" in header_name or "\n" in header_name or b"\r" in record.pending_response or b"\n" in record.pending_response:
                    raise SessionStorageError("header_injection")
                deliveries.append(PendingDelivery(record.match_id, header_name, record.pending_response))
        return tuple(deliveries)

    def mark_inflight(self, deliveries: tuple[PendingDelivery, ...]) -> None:
        for delivery in deliveries:
            record = self.load(delivery.match_id)
            if record is None or record.pending_response != delivery.response:
                raise SessionStorageError("pending_state_changed")
            self.save(replace(record, delivery_state="inflight"))

    def restore_pending(self, deliveries: tuple[PendingDelivery, ...]) -> None:
        for delivery in deliveries:
            record = self.load(delivery.match_id)
            if record is not None and record.pending_response == delivery.response and record.finished is None:
                self.save(replace(record, delivery_state="pending"))

    def acknowledge(self, deliveries: tuple[PendingDelivery, ...]) -> None:
        for delivery in deliveries:
            record = self.load(delivery.match_id)
            if record is not None and record.pending_response == delivery.response and record.finished is None:
                self.save(replace(record, pending_response=None, delivery_state="idle"))

    def finish(self, row: FinishedRow) -> None:
        record = self.load(row.match_id)
        if record is None:
            return
        self.save(replace(record, pending_response=None, delivery_state="finished", finished=row))
