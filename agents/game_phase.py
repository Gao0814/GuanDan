"""Public-observation game-phase classification for AI consumers.

The engine remains the source of rule truth.  This module only derives a
stable, serializable strategy context from the observation payload shared with
agents.
"""

from __future__ import annotations

from dataclasses import dataclass


OPENING = "opening"
MIDGAME = "midgame"
ENDGAME = "endgame"
NEAR_OPEN_ENDGAME = "near_open_endgame"
CRITICAL_ENDGAME = "critical_endgame"

ENDGAME_PHASES = frozenset({ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME})


@dataclass(frozen=True, slots=True)
class GamePhaseContext:
    """Immutable phase facts derived exclusively from public observation."""

    phase: str
    my_hand_count: int
    other_hand_counts: tuple[int, ...]
    external_unknown_count: int
    history_action_count: int
    finished_player_count: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for prompts and tests."""
        return {
            "phase": self.phase,
            "my_hand_count": self.my_hand_count,
            "other_hand_counts": list(self.other_hand_counts),
            "external_unknown_count": self.external_unknown_count,
            "history_action_count": self.history_action_count,
            "finished_player_count": self.finished_player_count,
        }


def _coerce_nonnegative_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _finished_player_count(history: dict[str, object], other_players: list[object]) -> int:
    marked_finished = sum(
        1
        for player in other_players
        if isinstance(player, dict) and bool(player.get("finished", False))
    )
    finish_order = history.get("finish_order", [])
    history_finished = len(finish_order) if isinstance(finish_order, list) else 0
    return max(marked_finished, history_finished)


def is_endgame_phase(phase: str) -> bool:
    """Whether a phase uses endgame consumer behavior."""
    return phase in ENDGAME_PHASES


def phase_matches(phase: str, candidate: str) -> bool:
    """Match a knowledge tag, including the endgame parent relationship."""
    return phase == candidate or (candidate == ENDGAME and is_endgame_phase(phase))


def classify_game_phase(observation: dict[str, object]) -> GamePhaseContext:
    """Classify a public observation using the Step-I priority order.

    History snapshots can lag or be truncated.  Taking the larger of the
    visible history length and ``current_round.step_no`` prevents stale input
    from incorrectly reopening the opening phase.
    """
    my_info = dict(observation.get("my_info", {}))
    current_round = dict(observation.get("current_round", {}))
    history = dict(observation.get("history", {}))
    other_players = list(observation.get("other_players", []))

    my_hand_count = _coerce_nonnegative_int(my_info.get("hand_count"))
    history_actions = history.get("actions", [])
    history_length = len(history_actions) if isinstance(history_actions, list) else 0
    step_no = _coerce_nonnegative_int(current_round.get("step_no"))
    history_action_count = max(history_length, step_no)

    other_hand_counts = tuple(
        _coerce_nonnegative_int(player.get("hand_count"))
        for player in other_players
        if isinstance(player, dict)
    )
    unfinished_other_counts = tuple(
        _coerce_nonnegative_int(player.get("hand_count"))
        for player in other_players
        if isinstance(player, dict) and not bool(player.get("finished", False))
    )
    external_unknown_count = sum(unfinished_other_counts)
    finished_player_count = _finished_player_count(history, other_players)

    normal_endgame = (
        my_hand_count < 10
        or any(count < 6 for count in unfinished_other_counts)
        or finished_player_count > 0
    )
    opening = (
        history_action_count <= 8
        and my_hand_count >= 18
        and finished_player_count == 0
        and len(unfinished_other_counts) == 3
        and all(count >= 16 for count in unfinished_other_counts)
    )

    if external_unknown_count <= 12:
        phase = CRITICAL_ENDGAME
    elif external_unknown_count <= 20:
        phase = NEAR_OPEN_ENDGAME
    elif normal_endgame:
        phase = ENDGAME
    elif opening:
        phase = OPENING
    else:
        phase = MIDGAME

    return GamePhaseContext(
        phase=phase,
        my_hand_count=my_hand_count,
        other_hand_counts=other_hand_counts,
        external_unknown_count=external_unknown_count,
        history_action_count=history_action_count,
        finished_player_count=finished_player_count,
    )
