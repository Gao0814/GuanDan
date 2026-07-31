"""Narrow offline-only access to engine truth for evaluation benchmarks."""

from __future__ import annotations

from engine.cards import card_to_token
from engine.game import GuanDanGame


def extract_ground_truth_hands(
    game: GuanDanGame,
    observer_player_id: object,
) -> dict[object, tuple[str, ...]]:
    """Return active opponents' exact hands for an already-built evaluation.

    Callers must finish all public-only inference before invoking this helper.
    The returned mapping is intentionally ephemeral and must not be placed in
    any public inference state or serialized report.
    """

    state = game._state
    if state is None or state.current_player_id != observer_player_id:
        raise ValueError("offline truth observer must match the current game player")
    return {
        player.player_id: tuple(card_to_token(card) for card in player.hand_cards)
        for player in state.players
        if (
            player.player_id != observer_player_id
            and not player.is_finished
            and player.hand_cards
        )
    }
