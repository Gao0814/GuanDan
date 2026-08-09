"""Strict no-tribute profile guard for the offline adapter."""

from __future__ import annotations

from .models import DealRequest, PlayRequest
from .session import HandlerContext


class ProfileError(ValueError):
    """A context is outside the supported no-tribute play subset."""


def require_no_tribute_context(context: HandlerContext) -> DealRequest | PlayRequest:
    request = context.request
    global_state = request.global_state
    if global_state.tribute != 0 or global_state.first is not None or global_state.last is not None:
        raise ProfileError("profile_mismatch")
    if isinstance(request, DealRequest):
        if global_state.resist is not None or context.local_player_id != request.your_id:
            raise ProfileError("profile_mismatch")
        return request
    if isinstance(request, PlayRequest):
        if global_state.resist is not False:
            raise ProfileError("profile_mismatch")
        return request
    raise ProfileError("unsupported_request")
