"""Public-information predicate shared by pressure-pass policy users.

This module deliberately contains no Agent fallback or engine access.  It only
answers whether the supplied public payload proves that the original pass
action is the narrow pressure-preservation choice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


_SPECIAL = frozenset(("bomb", "straight_flush", "joker_bomb"))
_TEAM = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _common_action_signature(action: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    pattern = action.get("declared_pattern")
    declared = action.get("declared_cards")
    carriers = action.get("carrier_cards")
    if (
        not isinstance(pattern, str)
        or not isinstance(declared, list)
        or not isinstance(carriers, list)
        or any(not isinstance(card, str) for card in declared + carriers)
    ):
        return None
    return pattern, tuple(declared), tuple(carriers)


def _full_action_signature(action: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    """Validate an original member of the current legal-action collection."""

    signature = _common_action_signature(action)
    action_id = action.get("action_id")
    wildcard_count = action.get("wildcard_count")
    wildcard_info = action.get("wildcard_info")
    display = action.get("display_text")
    if (
        signature is None
        or not _is_int(action_id)
        or not _is_int(wildcard_count)
        or wildcard_count < 0
        or not isinstance(wildcard_info, list)
        or not isinstance(display, str)
    ):
        return None
    return signature


def _table_action_signature(action: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    """Validate the public table-action schema, whose ID is an explicit sentinel."""

    signature = _common_action_signature(action)
    wildcard_count = action.get("wildcard_count")
    wildcard_info = action.get("wildcard_info")
    display = action.get("display_text")
    if (
        signature is None
        or "action_id" not in action
        or action.get("action_id") is not None
        or not _is_int(wildcard_count)
        or wildcard_count < 0
        or not isinstance(wildcard_info, list)
        or not isinstance(display, str)
    ):
        return None
    return signature


def _history_action_signature(action: Mapping[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    if set(action) != {
        "step_no", "round_no", "player_id", "declared_pattern", "declared_cards", "carrier_cards",
    }:
        return None
    return _common_action_signature(action)


def _valid_actions(actions: object) -> tuple[int, tuple[Mapping[str, object], ...]] | None:
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)):
        return None
    pass_ids: list[int] = []
    non_pass: list[Mapping[str, object]] = []
    ids: set[int] = set()
    for action in actions:
        if not isinstance(action, Mapping) or _full_action_signature(action) is None:
            return None
        action_id = action.get("action_id")
        pattern = action.get("declared_pattern")
        if not _is_int(action_id) or action_id in ids or not isinstance(pattern, str):
            return None
        ids.add(action_id)
        if pattern == "pass":
            if action.get("declared_cards") or action.get("carrier_cards"):
                return None
            pass_ids.append(action_id)
        else:
            non_pass.append(action)
    if len(pass_ids) != 1 or not non_pass:
        return None
    return pass_ids[0], tuple(non_pass)


def _pressure_pass_context(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[int, tuple[Mapping[str, object], ...], int, dict[int, Mapping[str, object]], int] | None:
    """Strictly validate the public follow-play payload and identify its leader."""

    if not _is_int(expected_player_id) or expected_player_id not in _TEAM:
        return None
    validated_actions = _valid_actions(legal_actions)
    if validated_actions is None or not isinstance(observation, Mapping):
        return None
    pass_id, non_pass = validated_actions
    my_info = observation.get("my_info")
    others = observation.get("other_players")
    current = observation.get("current_round")
    history = observation.get("history")
    if not isinstance(my_info, Mapping) or not isinstance(others, list) or not isinstance(current, Mapping) or not isinstance(history, Mapping):
        return None
    player = my_info.get("player_id")
    hand_count = my_info.get("hand_count")
    if player != expected_player_id or my_info.get("team") != _TEAM[expected_player_id] or not _is_int(hand_count) or not 1 <= hand_count <= 27:
        return None
    constraint = current.get("constraint")
    if (
        current.get("current_player_id") != expected_player_id
        or not isinstance(constraint, str)
        or not constraint
        or constraint == "free"
    ):
        return None
    round_no = current.get("round_no")
    step_no = current.get("step_no")
    table_action = current.get("table_action")
    actions = history.get("actions")
    if not _is_int(round_no) or round_no <= 0 or not _is_int(step_no) or step_no < 0 or not isinstance(table_action, Mapping):
        return None
    table_signature = _table_action_signature(table_action)
    if (
        table_signature is None
        or table_signature[0] == "pass"
        or constraint != table_action.get("display_text")
        or not isinstance(actions, list)
    ):
        return None

    players: dict[int, Mapping[str, object]] = {}
    for item in others:
        if not isinstance(item, Mapping):
            return None
        item_id, team, count, finished = item.get("player_id"), item.get("team"), item.get("hand_count"), item.get("finished")
        if not _is_int(item_id) or item_id not in _TEAM or item_id == expected_player_id or item_id in players:
            return None
        if team != _TEAM[item_id] or not _is_int(count) or not 0 <= count <= 27 or type(finished) is not bool:
            return None
        if (finished and count != 0) or (not finished and count == 0):
            return None
        players[item_id] = item
    if set(players) != set(_TEAM) - {expected_player_id}:
        return None

    previous_step = 0
    previous_round = 0
    leader: int | None = None
    leader_signature: tuple[str, tuple[str, ...], tuple[str, ...]] | None = None
    for item in actions:
        if not isinstance(item, Mapping):
            return None
        item_signature = _history_action_signature(item)
        if item_signature is None:
            return None
        item_step, item_round, item_player = item.get("step_no"), item.get("round_no"), item.get("player_id")
        if (
            not _is_int(item_step) or item_step <= previous_step or item_step > step_no
            or not _is_int(item_round) or item_round <= 0 or item_round < previous_round or item_round > round_no
            or not _is_int(item_player) or item_player not in _TEAM
        ):
            return None
        previous_step, previous_round = item_step, item_round
        if item_round == round_no and item.get("declared_pattern") != "pass":
            leader = item_player
            leader_signature = item_signature
    if leader is None or leader_signature != table_signature:
        return None
    return pass_id, non_pass, leader, players, hand_count


def _pressure_pass_id(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
    *,
    teammate_leader: bool,
) -> int | None:
    """Return pass only when a specified leader relationship is publicly proved."""

    context = _pressure_pass_context(observation, legal_actions, expected_player_id)
    if context is None:
        return None
    pass_id, non_pass, leader, players, hand_count = context
    if leader == expected_player_id or (_TEAM[leader] == _TEAM[expected_player_id]) != teammate_leader:
        return None
    opponents = [item for player_id, item in players.items() if _TEAM[player_id] != _TEAM[expected_player_id]]
    if any(item["finished"] or item["hand_count"] <= 2 for item in opponents):
        return None
    if any(action.get("declared_pattern") not in _SPECIAL for action in non_pass):
        return None
    if any(len(action["carrier_cards"]) == hand_count for action in non_pass):
        return None
    return pass_id


def conditional_pressure_pass_id(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> int | None:
    """Return pass only for the existing opponent-led pressure opportunity."""

    return _pressure_pass_id(
        observation,
        legal_actions,
        expected_player_id,
        teammate_leader=False,
    )


def teammate_pressure_pass_id(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> int | None:
    """Return pass only when a teammate's lead is safely protected from special-only pressure."""

    return _pressure_pass_id(
        observation,
        legal_actions,
        expected_player_id,
        teammate_leader=True,
    )


def dangerous_opponent_pass_id(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> int | None:
    """Return the original pass id only for a proved opponent near-finish lead."""

    context = _pressure_pass_context(observation, legal_actions, expected_player_id)
    if context is None:
        return None
    pass_id, _non_pass, leader, players, _hand_count = context
    if leader == expected_player_id or _TEAM[leader] == _TEAM[expected_player_id]:
        return None
    leader_public = players[leader]
    if leader_public["finished"] or leader_public["hand_count"] > 2:
        return None
    return pass_id


def teammate_big_joker_pass_id(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
    selected_action_id: int,
) -> int | None:
    """Return pass for the narrow proved case of a model spending big joker on a teammate.

    The initial resource scope is intentionally only the public singleton
    ``BJ`` response to a teammate's singleton ``SJ`` lead.  Other pressure
    patterns remain untouched until independently justified.
    """

    if not _is_int(selected_action_id):
        return None
    context = _pressure_pass_context(observation, legal_actions, expected_player_id)
    if context is None:
        return None
    pass_id, non_pass, leader, players, hand_count = context
    if leader == expected_player_id or _TEAM[leader] != _TEAM[expected_player_id]:
        return None
    if any(
        item["finished"] or item["hand_count"] <= 2
        for player_id, item in players.items()
        if _TEAM[player_id] != _TEAM[expected_player_id]
    ):
        return None
    selected = next((action for action in non_pass if action.get("action_id") == selected_action_id), None)
    if selected is None or len(selected["carrier_cards"]) >= hand_count:
        return None
    if not isinstance(observation, Mapping):
        return None
    current_round = observation.get("current_round")
    if not isinstance(current_round, Mapping):
        return None
    table_action = current_round.get("table_action")
    if not isinstance(table_action, Mapping):
        return None
    leader_signature = _common_action_signature(table_action)
    selected_signature = _common_action_signature(selected)
    if leader_signature != ("single", ("SJ",), ("SJ",)) or selected_signature != ("single", ("BJ",), ("BJ",)):
        return None
    return pass_id
