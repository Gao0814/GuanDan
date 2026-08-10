"""Strict, offline parser for local-AI poll text."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .bot_io import BotEnvelope, BotEnvelopeError, BotReplay, parse_bot_envelope
from .models import DealRequest, PlayRequest, UnsupportedStage


MAX_POLL_BYTES = 1_048_576
MAX_POLL_LINE_BYTES = 131_072
MAX_MATCHES_PER_POLL = 1_024


_ENVELOPE_DIAGNOSTICS = {
    "envelope_shape": "envelope_shape_invalid",
    "inner_request": "inner_request_invalid",
    "historical_response": "historical_response_invalid",
    "replay_history": "replay_history_invalid",
}


class PollFormatError(ValueError):
    """A poll body is not structurally safe to consume."""


@dataclass(frozen=True, slots=True)
class PollRequest:
    """One request line pair, with a normalized per-match parse result."""

    match_id: str
    request_bytes: bytes
    stage: DealRequest | PlayRequest | UnsupportedStage | None
    replay: BotReplay | None = None
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class FinishedRow:
    match_id: str
    local_player_id: int
    player_count: int
    scores: tuple[int, ...]

    @property
    def is_aborted(self) -> bool:
        return self.player_count == 0


@dataclass(frozen=True, slots=True)
class PollBatch:
    requests: tuple[PollRequest, ...]
    finished: tuple[FinishedRow, ...]


def _validate_match_id(value: str) -> str:
    if (
        not value
        or len(value) > 256
        or "\r" in value
        or "\n" in value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise PollFormatError("invalid_match_id")
    return value


def _parse_count_line(line: str) -> tuple[int, int]:
    parts = line.split(" ")
    if len(parts) != 2 or any(not part.isascii() or not part.isdecimal() for part in parts):
        raise PollFormatError("invalid_count_line")
    try:
        request_count, finished_count = (int(part) for part in parts)
    except ValueError as exc:
        raise PollFormatError("invalid_count_line") from exc
    if request_count > MAX_MATCHES_PER_POLL or finished_count > MAX_MATCHES_PER_POLL:
        raise PollFormatError("poll_count_too_large")
    return request_count, finished_count


def _parse_request(match_id: str, request_line: str) -> PollRequest:
    raw = request_line.encode("utf-8")
    try:
        payload = json.loads(request_line)
    except (TypeError, ValueError, json.JSONDecodeError):
        return PollRequest(match_id=match_id, request_bytes=raw, stage=None, diagnostic="request_json_invalid")
    except Exception:
        return PollRequest(match_id=match_id, request_bytes=raw, stage=None, diagnostic="malformed_request")
    try:
        envelope: BotEnvelope = parse_bot_envelope(payload)
    except BotEnvelopeError as exc:
        return PollRequest(
            match_id=match_id,
            request_bytes=raw,
            stage=None,
            diagnostic=_ENVELOPE_DIAGNOSTICS.get(exc.code, "malformed_request"),
        )
    except Exception:
        return PollRequest(match_id=match_id, request_bytes=raw, stage=None, diagnostic="malformed_request")
    return PollRequest(match_id=match_id, request_bytes=raw, stage=envelope.current_request, replay=envelope.replay)


def _parse_finished(line: str) -> FinishedRow:
    parts = line.split(" ")
    if len(parts) < 3 or any(part == "" for part in parts):
        raise PollFormatError("invalid_finished_row")
    match_id = _validate_match_id(parts[0])
    try:
        local_player_id = int(parts[1])
        player_count = int(parts[2])
        scores = tuple(int(score) for score in parts[3:])
    except ValueError as exc:
        raise PollFormatError("invalid_finished_row") from exc
    if not 0 <= local_player_id <= 3 or not 0 <= player_count <= 4:
        raise PollFormatError("invalid_finished_row")
    if len(scores) != player_count:
        raise PollFormatError("invalid_finished_row")
    return FinishedRow(match_id, local_player_id, player_count, scores)


def parse_poll(payload: object) -> PollBatch:
    """Parse a UTF-8 poll response, preserving request and finished-row order."""

    if not isinstance(payload, bytes):
        raise PollFormatError("poll_must_be_bytes")
    if len(payload) > MAX_POLL_BYTES:
        raise PollFormatError("poll_too_large")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PollFormatError("invalid_utf8") from exc
    lines = text.splitlines()
    while lines and lines[-1] == "":
        lines.pop()
    if not lines or any(not line or len(line.encode("utf-8")) > MAX_POLL_LINE_BYTES for line in lines):
        raise PollFormatError("invalid_poll_lines")
    request_count, finished_count = _parse_count_line(lines[0])
    expected_lines = 1 + 2 * request_count + finished_count
    if len(lines) != expected_lines:
        raise PollFormatError("poll_line_count_mismatch")

    requests: list[PollRequest] = []
    cursor = 1
    seen_ids: set[str] = set()
    for _ in range(request_count):
        match_id = _validate_match_id(lines[cursor])
        if match_id in seen_ids:
            raise PollFormatError("duplicate_match_id")
        seen_ids.add(match_id)
        requests.append(_parse_request(match_id, lines[cursor + 1]))
        cursor += 2

    finished: list[FinishedRow] = []
    for line in lines[cursor:]:
        row = _parse_finished(line)
        if row.match_id in seen_ids:
            raise PollFormatError("duplicate_match_id")
        seen_ids.add(row.match_id)
        finished.append(row)
    return PollBatch(tuple(requests), tuple(finished))
