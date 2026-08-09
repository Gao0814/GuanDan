"""Strict Botzone Bot JSON envelope parsing and response wrapping.

This module knows the outer Bot interaction envelope only.  GuanDan card and
stage semantics stay delegated to ``protocol.py``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .models import ActionClaim, DealRequest, HistoryEntry, PlayRequest, UnsupportedStage
from .protocol import ProtocolValidationError, parse_action_claim, parse_stage_request


class BotEnvelopeError(ValueError):
    """The complete Bot JSON interaction cannot be safely replayed."""


StageRequest = DealRequest | PlayRequest | UnsupportedStage


@dataclass(frozen=True, slots=True)
class BotReplay:
    """Public/current state rebuilt solely from the Bot interaction history."""

    local_player_id: int
    own_hand: tuple[int, ...]
    history: tuple[HistoryEntry, ...]
    latest_window: tuple[HistoryEntry, ...]
    current_request: StageRequest


@dataclass(frozen=True, slots=True)
class BotEnvelope:
    """Validated outer Bot JSON input and its cold-start replay result."""

    requests: tuple[StageRequest, ...]
    responses: tuple[ActionClaim | None, ...]
    replay: BotReplay

    @property
    def current_request(self) -> StageRequest:
        return self.replay.current_request


def _json_compatible(value: object) -> bool:
    if value is None or type(value) in {bool, int, float, str}:
        return True
    if isinstance(value, list):
        return all(_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _json_compatible(item) for key, item in value.items())
    return False


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise BotEnvelopeError(f"{label}_must_be_list")
    return value


def _merge_history(
    latest_window: tuple[HistoryEntry, ...],
    accumulated: tuple[HistoryEntry, ...],
    incoming_window: tuple[HistoryEntry, ...],
) -> tuple[tuple[HistoryEntry, ...], tuple[HistoryEntry, ...]]:
    """Pure replay equivalent of the durable session's verified merge rule."""

    if not latest_window and not accumulated:
        return incoming_window, incoming_window
    if not latest_window or len(accumulated) < len(latest_window) or accumulated[-len(latest_window):] != latest_window:
        raise BotEnvelopeError("history_alignment_failed")
    if incoming_window == latest_window:
        return incoming_window, accumulated
    maximum_overlap = min(len(latest_window), len(incoming_window))
    for overlap in range(maximum_overlap, 0, -1):
        if latest_window[-overlap:] == incoming_window[:overlap]:
            return incoming_window, accumulated + incoming_window[overlap:]
    raise BotEnvelopeError("history_alignment_failed")


def _parse_historical_response(stage: DealRequest | PlayRequest, value: object, own_hand: tuple[int, ...]) -> ActionClaim | None:
    if isinstance(stage, DealRequest):
        if value != [] or type(value) is not list:
            raise BotEnvelopeError("deal_response_invalid")
        return None
    try:
        action_claim = parse_action_claim(value, level=stage.global_state.level, known_hand_ids=own_hand)
    except ProtocolValidationError as exc:
        raise BotEnvelopeError("play_response_invalid") from exc
    return action_claim


def _deduct(own_hand: tuple[int, ...], action: ActionClaim) -> tuple[int, ...]:
    action_ids = set(action.action)
    if not action_ids.issubset(own_hand):
        raise BotEnvelopeError("response_action_outside_hand")
    return tuple(card_id for card_id in own_hand if card_id not in action_ids)


def parse_bot_envelope(value: object) -> BotEnvelope:
    """Validate/replay the standard Bot JSON input without a session dependency."""

    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise BotEnvelopeError("envelope_must_be_object")
    allowed = {"requests", "responses", "data", "globaldata", "time_limit", "memory_limit"}
    if set(value) - allowed or not {"requests", "responses"}.issubset(value):
        raise BotEnvelopeError("envelope_fields_invalid")
    if any(not _json_compatible(value[field]) for field in set(value) - {"requests", "responses"}):
        raise BotEnvelopeError("envelope_optional_value_invalid")
    raw_requests = _require_list(value["requests"], "requests")
    raw_responses = _require_list(value["responses"], "responses")
    if not raw_requests or len(raw_requests) != len(raw_responses) + 1:
        raise BotEnvelopeError("envelope_history_length_invalid")
    try:
        stages = tuple(parse_stage_request(item) for item in raw_requests)
    except ProtocolValidationError as exc:
        raise BotEnvelopeError("inner_request_invalid") from exc
    if not isinstance(stages[0], DealRequest):
        raise BotEnvelopeError("first_request_must_be_deal")
    deal = stages[0]
    own_hand = deal.deliver
    latest_window: tuple[HistoryEntry, ...] = ()
    accumulated: tuple[HistoryEntry, ...] = ()
    historical: list[ActionClaim | None] = []
    for index, stage in enumerate(stages):
        paired = index < len(raw_responses)
        if isinstance(stage, UnsupportedStage):
            if paired or index != len(stages) - 1:
                raise BotEnvelopeError("unsupported_history_stage")
            break
        if stage.global_state.level != deal.global_state.level:
            raise BotEnvelopeError("global_level_drift")
        if isinstance(stage, DealRequest):
            if index != 0:
                raise BotEnvelopeError("duplicate_deal")
        else:
            latest_window, accumulated = _merge_history(latest_window, accumulated, stage.history)
        if paired:
            response = _parse_historical_response(stage, raw_responses[index], own_hand)
            historical.append(response)
            if response is not None:
                own_hand = _deduct(own_hand, response)
    current = stages[-1]
    current_window = current.history if isinstance(current, PlayRequest) else ()
    return BotEnvelope(
        requests=stages,
        responses=tuple(historical),
        replay=BotReplay(
            local_player_id=deal.your_id,
            own_hand=own_hand,
            history=accumulated,
            latest_window=current_window,
            current_request=current,
        ),
    )


def encode_bot_response(stage: DealRequest | PlayRequest, response: bytes) -> bytes:
    """Canonicalize an inner GuanDan reply into the outer Bot response object."""

    if not isinstance(response, bytes):
        raise BotEnvelopeError("response_must_be_bytes")
    try:
        decoded = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BotEnvelopeError("response_not_json") from exc
    if isinstance(stage, DealRequest):
        if decoded != [] or type(decoded) is not list:
            raise BotEnvelopeError("deal_response_invalid")
        payload: object = []
    else:
        try:
            payload = parse_action_claim(decoded, level=stage.global_state.level).to_json()
        except ProtocolValidationError as exc:
            raise BotEnvelopeError("play_response_invalid") from exc
    return json.dumps({"response": payload}, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
