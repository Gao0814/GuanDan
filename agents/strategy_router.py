"""Public-only deterministic strategy-intent routing.

The router derives no hidden-card or behavioral signal.  It validates the
caller-provided public snapshot before returning one coarse intent; it never
scores, filters, or selects an action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from agents.game_phase import CRITICAL_ENDGAME, ENDGAME, MIDGAME, NEAR_OPEN_ENDGAME, OPENING, GamePhaseContext


RUN_OUT = "run_out"
BLOCK_OPPONENT = "block_opponent"
SUPPORT_TEAMMATE = "support_teammate"
CONTROL = "control"

_SOURCE = "public_strategy_router_v1"
_VALID_PHASES = frozenset({OPENING, MIDGAME, ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME})
_TEAM_BY_PLAYER = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}
_WEAK_LABELS = frozenset({"极弱", "偏弱"})
_HAND_LABELS = ("极弱", "偏弱", "中等", "较强", "极强")
_DIAGNOSTIC_ORDER = (
    "invalid_observation",
    "invalid_legal_actions",
    "invalid_phase_context",
    "phase_mismatch",
    "opening_not_routed",
    "invalid_player_id",
    "invalid_team",
    "player_set_mismatch",
    "duplicate_player",
    "invalid_hand_count",
    "invalid_finished_flag",
    "relationship_mismatch",
    "external_count_mismatch",
    "history_count_mismatch",
    "finished_count_mismatch",
    "invalid_hand_evaluation",
    "hand_label_mismatch",
    "malformed_action",
    "invalid_round_context",
    "malformed_current_round_history",
    "table_leader_mismatch",
)


@dataclass(frozen=True, slots=True)
class StrategyIntentContext:
    """A serializable public strategy intent, or a whole-result failure."""

    status: str
    source: str
    phase: str | None
    intent: str | None
    reason_codes: tuple[str, ...]
    my_player_id: int | None
    my_team: str | None
    my_hand_count: int | None
    teammate_player_id: int | None
    teammate_hand_count: int | None
    minimum_opponent_hand_count: int | None
    urgent_opponent_ids: tuple[int, ...]
    can_finish_now: bool
    is_free_lead: bool
    table_leader_player_id: int | None
    table_leader_relation: str | None
    table_leader_is_urgent: bool
    hand_strength: str | None
    hand_total_score: int | None
    hand_control_score: int | None
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source": self.source,
            "phase": self.phase,
            "intent": self.intent,
            "reason_codes": list(self.reason_codes),
            "my_player_id": self.my_player_id,
            "my_team": self.my_team,
            "my_hand_count": self.my_hand_count,
            "teammate_player_id": self.teammate_player_id,
            "teammate_hand_count": self.teammate_hand_count,
            "minimum_opponent_hand_count": self.minimum_opponent_hand_count,
            "urgent_opponent_ids": list(self.urgent_opponent_ids),
            "can_finish_now": self.can_finish_now,
            "is_free_lead": self.is_free_lead,
            "table_leader_player_id": self.table_leader_player_id,
            "table_leader_relation": self.table_leader_relation,
            "table_leader_is_urgent": self.table_leader_is_urgent,
            "hand_strength": self.hand_strength,
            "hand_total_score": self.hand_total_score,
            "hand_control_score": self.hand_control_score,
            "diagnostics": list(self.diagnostics),
        }


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _diagnostics(*codes: str) -> tuple[str, ...]:
    present = set(codes)
    return tuple(code for code in _DIAGNOSTIC_ORDER if code in present)


def _unavailable(phase: str | None, *codes: str) -> StrategyIntentContext:
    return StrategyIntentContext(
        status="unavailable",
        source=_SOURCE,
        phase=phase,
        intent=None,
        reason_codes=(),
        my_player_id=None,
        my_team=None,
        my_hand_count=None,
        teammate_player_id=None,
        teammate_hand_count=None,
        minimum_opponent_hand_count=None,
        urgent_opponent_ids=(),
        can_finish_now=False,
        is_free_lead=False,
        table_leader_player_id=None,
        table_leader_relation=None,
        table_leader_is_urgent=False,
        hand_strength=None,
        hand_total_score=None,
        hand_control_score=None,
        diagnostics=_diagnostics(*codes),
    )


def _expected_label(total_score: int) -> str:
    if total_score >= 80:
        return "极强"
    if total_score >= 60:
        return "较强"
    if total_score >= 40:
        return "中等"
    if total_score >= 20:
        return "偏弱"
    return "极弱"


def _validate_phase_context(value: object) -> tuple[bool, str | None]:
    """Validate every immutable phase field before using it in comparisons."""
    if not isinstance(value, GamePhaseContext):
        return False, None
    if not isinstance(value.phase, str) or value.phase not in _VALID_PHASES:
        return False, None
    if not _is_int(value.my_hand_count) or value.my_hand_count < 0:
        return False, None
    if (
        not isinstance(value.other_hand_counts, tuple)
        or len(value.other_hand_counts) != 3
        or any(not _is_int(count) or count < 0 for count in value.other_hand_counts)
    ):
        return False, None
    if not _is_int(value.external_unknown_count) or value.external_unknown_count < 0:
        return False, None
    if not _is_int(value.history_action_count) or value.history_action_count < 0:
        return False, None
    if not _is_int(value.finished_player_count) or not 0 <= value.finished_player_count <= 3:
        return False, None
    return True, value.phase


def _action_signature(action: Mapping[str, object]) -> tuple[object, object, object] | None:
    pattern = action.get("declared_pattern")
    declared_cards = action.get("declared_cards")
    carrier_cards = action.get("carrier_cards")
    if not isinstance(pattern, str) or not pattern or not isinstance(declared_cards, list) or not isinstance(carrier_cards, list):
        return None
    return (pattern, declared_cards, carrier_cards)


def _validate_legal_actions(legal_actions: object) -> bool:
    if not isinstance(legal_actions, list) or not legal_actions:
        return False
    return all(isinstance(action, dict) and _action_signature(action) is not None for action in legal_actions)


def _round_and_leader(
    current_round: Mapping[str, object],
    history_actions: list[object],
    current_player_id: int,
) -> tuple[bool, bool, int | None, str | None]:
    """Return validity, free-lead fact, leader id, and failure diagnostic."""
    step_no = current_round.get("step_no")
    round_no = current_round.get("round_no")
    round_player_id = current_round.get("current_player_id")
    constraint = current_round.get("constraint")
    table_action = current_round.get("table_action")
    if (
        not _is_int(step_no)
        or step_no < 0
        or not _is_int(round_no)
        or round_no <= 0
        or round_player_id != current_player_id
        or not isinstance(constraint, str)
        or (table_action is not None and not isinstance(table_action, dict))
    ):
        return False, False, None, "invalid_round_context"
    if table_action is not None and _action_signature(table_action) is None:
        return False, False, None, "invalid_round_context"

    previous_step = 0
    current_round_actions: list[dict[str, object]] = []
    for item in history_actions:
        if not isinstance(item, dict):
            return False, False, None, "malformed_current_round_history"
        item_step = item.get("step_no")
        item_round = item.get("round_no")
        item_player = item.get("player_id")
        if (
            not _is_int(item_step)
            or item_step <= previous_step
            or item_step > step_no
            or not _is_int(item_round)
            or item_round <= 0
            or item_round > round_no
            or not _is_int(item_player)
            or item_player not in _TEAM_BY_PLAYER
            or _action_signature(item) is None
        ):
            return False, False, None, "malformed_current_round_history"
        previous_step = item_step
        if item_round == round_no:
            current_round_actions.append(item)

    non_pass_actions = [
        action for action in current_round_actions if action["declared_pattern"] != "pass"
    ]
    if table_action is None:
        if constraint != "free" or non_pass_actions:
            return False, False, None, "malformed_current_round_history"
        return True, True, None, None
    if constraint == "free" or not non_pass_actions:
        return False, False, None, "malformed_current_round_history"
    leader_action = non_pass_actions[-1]
    if _action_signature(leader_action) != _action_signature(table_action):
        return False, False, None, "table_leader_mismatch"
    leader_id = leader_action["player_id"]
    if leader_id == current_player_id:
        return False, False, None, "table_leader_mismatch"
    return True, False, leader_id, None


def route_strategy_intent(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    *,
    phase_context: GamePhaseContext,
    hand_evaluation: dict[str, object],
) -> StrategyIntentContext:
    """Route a validated public snapshot without consuming any hidden signal."""
    diagnostics: list[str] = []
    phase_is_valid, phase = _validate_phase_context(phase_context)
    if not phase_is_valid:
        diagnostics.append("invalid_phase_context")
    if not _validate_legal_actions(legal_actions):
        diagnostics.append("invalid_legal_actions" if not isinstance(legal_actions, list) or not legal_actions else "malformed_action")
    if not isinstance(observation, dict):
        return _unavailable(phase, *diagnostics, "invalid_observation")
    if phase_is_valid and phase == OPENING:
        return _unavailable(phase, *diagnostics, "opening_not_routed")

    my_info = observation.get("my_info")
    other_players = observation.get("other_players")
    current_round = observation.get("current_round")
    history = observation.get("history")
    if not isinstance(my_info, dict):
        diagnostics.append("invalid_observation")
    if not isinstance(other_players, list):
        diagnostics.append("invalid_observation")
    if not isinstance(current_round, dict):
        diagnostics.append("invalid_observation")
    if not isinstance(history, dict):
        diagnostics.append("invalid_observation")
    history_actions = history.get("actions") if isinstance(history, dict) else None
    if not isinstance(history_actions, list):
        diagnostics.append("invalid_observation")

    if not isinstance(my_info, dict) or not isinstance(other_players, list) or not isinstance(current_round, dict) or not isinstance(history_actions, list):
        if isinstance(hand_evaluation, dict):
            total_score = hand_evaluation.get("total_score")
            control_score = hand_evaluation.get("control_score")
            label = hand_evaluation.get("label")
            if (
                not _is_int(total_score)
                or not 0 <= total_score <= 100
                or not _is_int(control_score)
                or not 0 <= control_score <= 30
                or not isinstance(label, str)
                or label not in _HAND_LABELS
            ):
                diagnostics.append("invalid_hand_evaluation")
            elif label != _expected_label(total_score):
                diagnostics.append("hand_label_mismatch")
        else:
            diagnostics.append("invalid_hand_evaluation")
        return _unavailable(phase, *diagnostics)

    my_player_id = my_info.get("player_id")
    my_team = my_info.get("team")
    my_hand_count = my_info.get("hand_count")
    my_player_is_valid = _is_int(my_player_id) and my_player_id in _TEAM_BY_PLAYER
    my_team_is_valid = my_player_is_valid and my_team == _TEAM_BY_PLAYER[my_player_id]
    my_hand_is_valid = _is_int(my_hand_count) and my_hand_count > 0
    if not my_player_is_valid:
        diagnostics.append("invalid_player_id")
    if my_player_is_valid and not my_team_is_valid:
        diagnostics.append("invalid_team")
    if not my_hand_is_valid:
        diagnostics.append("invalid_hand_count")

    player_by_id: dict[int, dict[str, object]] = {}
    player_records_are_safe = len(other_players) == 3
    other_counts_are_safe = True
    for player in other_players:
        if not isinstance(player, dict):
            diagnostics.append("player_set_mismatch")
            player_records_are_safe = False
            other_counts_are_safe = False
            continue
        player_id = player.get("player_id")
        player_id_is_valid = _is_int(player_id) and player_id in _TEAM_BY_PLAYER
        if not player_id_is_valid:
            diagnostics.append("invalid_player_id")
            player_records_are_safe = False
        elif player_id in player_by_id or (my_player_is_valid and player_id == my_player_id):
            diagnostics.append("duplicate_player")
            player_records_are_safe = False
        if player_id_is_valid and player.get("team") != _TEAM_BY_PLAYER[player_id]:
            diagnostics.append("invalid_team")
        hand_count = player.get("hand_count")
        finished = player.get("finished")
        hand_count_is_valid = _is_int(hand_count) and hand_count >= 0
        if not hand_count_is_valid:
            diagnostics.append("invalid_hand_count")
            other_counts_are_safe = False
        if type(finished) is not bool:
            diagnostics.append("invalid_finished_flag")
            other_counts_are_safe = False
        elif hand_count_is_valid and ((finished and hand_count != 0) or (not finished and hand_count <= 0)):
            diagnostics.append("invalid_finished_flag")
            other_counts_are_safe = False
        if player_id_is_valid and player_id not in player_by_id:
            player_by_id[player_id] = player
    expected_other_ids = set(_TEAM_BY_PLAYER) - {my_player_id} if my_player_is_valid else set()
    if not my_player_is_valid or set(player_by_id) != expected_other_ids:
        diagnostics.append("player_set_mismatch")
        player_records_are_safe = False

    relationships_are_safe = player_records_are_safe and my_team_is_valid
    teammate_ids: list[int] = []
    opponent_ids: list[int] = []
    if relationships_are_safe:
        teammate_ids = [player_id for player_id in player_by_id if _TEAM_BY_PLAYER[player_id] == my_team]
        opponent_ids = [player_id for player_id in player_by_id if _TEAM_BY_PLAYER[player_id] != my_team]
        if len(teammate_ids) != 1 or len(opponent_ids) != 2:
            diagnostics.append("relationship_mismatch")
            relationships_are_safe = False

    if phase_is_valid and my_hand_is_valid and player_records_are_safe and other_counts_are_safe:
        observed_other_counts = tuple(player["hand_count"] for player in other_players)
        unfinished_other_counts = tuple(player["hand_count"] for player in other_players if not player["finished"])
        finished_count = sum(1 for player in other_players if player["finished"])
        if (
            phase_context.my_hand_count != my_hand_count
            or phase_context.other_hand_counts != observed_other_counts
            or phase_context.external_unknown_count != sum(unfinished_other_counts)
        ):
            diagnostics.append("external_count_mismatch")
        current_step_no = current_round.get("step_no")
        if not _is_int(current_step_no) or phase_context.history_action_count != max(len(history_actions), current_step_no):
            diagnostics.append("history_count_mismatch")
        if phase_context.finished_player_count != finished_count:
            diagnostics.append("finished_count_mismatch")

    total_score: object = None
    control_score: object = None
    label: object = None
    if not isinstance(hand_evaluation, dict):
        diagnostics.append("invalid_hand_evaluation")
    else:
        total_score = hand_evaluation.get("total_score")
        control_score = hand_evaluation.get("control_score")
        label = hand_evaluation.get("label")
        if (
            not _is_int(total_score)
            or not 0 <= total_score <= 100
            or not _is_int(control_score)
            or not 0 <= control_score <= 30
            or not isinstance(label, str)
            or label not in _HAND_LABELS
        ):
            diagnostics.append("invalid_hand_evaluation")
        elif label != _expected_label(total_score):
            diagnostics.append("hand_label_mismatch")

    valid_round = False
    is_free_lead = False
    table_leader_id: int | None = None
    if my_player_is_valid:
        valid_round, is_free_lead, table_leader_id, round_diagnostic = _round_and_leader(
            current_round,
            history_actions,
            my_player_id,
        )
        if not valid_round:
            diagnostics.append(round_diagnostic or "invalid_round_context")

    if diagnostics:
        return _unavailable(phase, *diagnostics)

    teammate_id = teammate_ids[0]
    teammate = player_by_id[teammate_id]
    teammate_hand_count = teammate["hand_count"]

    can_finish_now = any(
        action["declared_pattern"] != "pass" and len(action["carrier_cards"]) == my_hand_count
        for action in legal_actions
    )
    active_opponent_ids = sorted(
        player_id for player_id in opponent_ids if not player_by_id[player_id]["finished"]
    )
    minimum_opponent_hand_count = (
        min(player_by_id[player_id]["hand_count"] for player_id in active_opponent_ids)
        if active_opponent_ids
        else None
    )
    urgent_opponent_ids = (
        tuple(
            player_id
            for player_id in active_opponent_ids
            if player_by_id[player_id]["hand_count"] == minimum_opponent_hand_count
        )
        if minimum_opponent_hand_count is not None and minimum_opponent_hand_count <= 2
        else ()
    )
    teammate_is_urgent = not teammate["finished"] and teammate_hand_count <= 2
    table_leader_relation = (
        "teammate" if table_leader_id == teammate_id else "opponent" if table_leader_id is not None else None
    )
    table_leader_is_urgent = bool(
        table_leader_id is not None
        and not player_by_id[table_leader_id]["finished"]
        and player_by_id[table_leader_id]["hand_count"] <= 2
    )
    hand_strength = "weak" if label in _WEAK_LABELS else "non_weak"

    if can_finish_now:
        intent, reason_codes = RUN_OUT, ("can_finish_now",)
    elif table_leader_relation == "teammate":
        intent, reason_codes = SUPPORT_TEAMMATE, ("teammate_controls_table",)
    elif table_leader_relation == "opponent" and table_leader_is_urgent:
        intent, reason_codes = BLOCK_OPPONENT, ("urgent_opponent_controls_table",)
    elif teammate_is_urgent and urgent_opponent_ids:
        if teammate_hand_count < minimum_opponent_hand_count:
            intent, reason_codes = SUPPORT_TEAMMATE, ("teammate_more_urgent",)
        elif teammate_hand_count > minimum_opponent_hand_count:
            intent, reason_codes = BLOCK_OPPONENT, ("opponent_more_urgent",)
        else:
            intent, reason_codes = BLOCK_OPPONENT, ("urgency_tie_block_opponent",)
    elif urgent_opponent_ids:
        intent, reason_codes = BLOCK_OPPONENT, ("opponent_urgent",)
    elif teammate_is_urgent:
        intent, reason_codes = SUPPORT_TEAMMATE, ("teammate_urgent",)
    elif hand_strength == "weak":
        intent, reason_codes = RUN_OUT, ("weak_hand",)
    else:
        intent, reason_codes = CONTROL, ("stable_control",)

    return StrategyIntentContext(
        status="available",
        source=_SOURCE,
        phase=phase,
        intent=intent,
        reason_codes=reason_codes,
        my_player_id=my_player_id,
        my_team=my_team,
        my_hand_count=my_hand_count,
        teammate_player_id=teammate_id,
        teammate_hand_count=teammate_hand_count,
        minimum_opponent_hand_count=minimum_opponent_hand_count,
        urgent_opponent_ids=urgent_opponent_ids,
        can_finish_now=can_finish_now,
        is_free_lead=is_free_lead,
        table_leader_player_id=table_leader_id,
        table_leader_relation=table_leader_relation,
        table_leader_is_urgent=table_leader_is_urgent,
        hand_strength=hand_strength,
        hand_total_score=total_score,
        hand_control_score=control_score,
        diagnostics=(),
    )
