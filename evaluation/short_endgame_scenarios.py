"""Deterministic engine-backed 5–8 card free-lead examples.

The AI-facing payloads are always obtained from ``observe()`` and the complete
``legal_actions()`` result.  Preset hands are only fixture construction input;
they are not exposed to the Agent beyond its own public observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.cards import Card
from engine.game import GuanDanGame


@dataclass(frozen=True, slots=True)
class ShortEndgameScenario:
    name: str
    observation: dict[str, object]
    legal_actions: list[dict[str, object]]
    game: GuanDanGame = field(repr=False, compare=False)


def _cards(tokens: tuple[str, ...]) -> tuple[Card, ...]:
    return tuple(
        Card(rank=token, suit=None)
        if token in {"SJ", "BJ"}
        else Card(rank=token[:-1], suit=token[-1])
        for token in tokens
    )


def _scenario(
    name: str,
    own_hand: tuple[str, ...],
    *,
    teammate_hand: tuple[str, ...] = ("3C", "4C", "5C", "6C"),
    opponent_a_hand: tuple[str, ...] = ("7D", "8D", "9D", "10D"),
    opponent_b_hand: tuple[str, ...] = ("JC", "QC", "KC", "AC"),
    level_rank: str = "2",
) -> ShortEndgameScenario:
    game = GuanDanGame(
        current_level_rank=level_rank,
        preset_hands={
            1: _cards(own_hand),
            2: _cards(opponent_a_hand),
            3: _cards(teammate_hand),
            4: _cards(opponent_b_hand),
        },
        starting_player_id=1,
    )
    game.reset()
    return ShortEndgameScenario(name, game.observe(), game.legal_actions(), game)


def build_short_endgame_scenarios() -> tuple[ShortEndgameScenario, ...]:
    """Return six distinct public 5–8 card routes, including urgency counterexamples."""

    return (
        _scenario(
            "group_cleanup",
            ("6S", "6H", "6C", "9S", "9H", "10S"),
        ),
        _scenario(
            "straight_vs_singles",
            ("3S", "4H", "5C", "6D", "7S", "9C", "10C"),
        ),
        _scenario(
            "natural_bomb_residual",
            ("9S", "9H", "9C", "9D", "9S", "3S"),
        ),
        _scenario(
            "wildcard_and_natural_groups",
            ("2H", "7S", "7H", "7C", "8S", "8H", "9S"),
        ),
        _scenario(
            "urgent_teammate",
            ("6S", "6H", "6C", "9S", "9H", "10S"),
            teammate_hand=("BJ",),
        ),
        _scenario(
            "urgent_opponent",
            ("3S", "4H", "5C", "6D", "7S", "9C"),
            opponent_a_hand=("BJ",),
        ),
    )
