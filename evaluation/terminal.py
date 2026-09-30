"""Conservative public terminal facts shared by offline rollout consumers."""

from collections.abc import Mapping


def terminal_team_facts(
    observation: object, winner: object, observer: object,
) -> tuple[str, int, int, str | None]:
    """Return outcome, score, team rank sum and an optional fixed failure code.

    Double-down exposes just the two finished players. Its rank sums are
    aggregate facts (3/7), without assigning ranks to the unfinished players.
    """
    if not isinstance(winner, str) or winner not in {"team_13", "team_24", "draw"}:
        return "", 0, 0, "invalid_terminal_winner"
    if type(observer) is not int or not 1 <= observer <= 4 or not isinstance(observation, Mapping):
        return "", 0, 0, "invalid_finish_order"
    history = observation.get("history")
    order = history.get("finish_order") if isinstance(history, Mapping) else None
    if (not isinstance(order, list) or len(order) not in (2, 3, 4)
            or any(type(player) is not int or not 1 <= player <= 4 for player in order)
            or len(set(order)) != len(order)):
        return "", 0, 0, "invalid_finish_order"
    team = lambda player: "team_13" if player in (1, 3) else "team_24"
    partner = lambda player: ((player + 1) % 4) + 1
    if len(order) == 2:
        if order[1] != partner(order[0]):
            return "", 0, 0, "invalid_finish_order"
        expected = team(order[0])
        placement = 3 if team(observer) == expected else 7
    else:
        if len(order) == 3:
            order = [*order, next(player for player in (1, 2, 3, 4) if player not in order)]
        expected = "draw" if order[-1] == partner(order[0]) else team(order[0])
        placement = order.index(observer) + order.index(partner(observer)) + 2
    if winner != expected:
        return "", 0, 0, "invalid_terminal_winner"
    outcome = "draw" if winner == "draw" else "win" if winner == team(observer) else "loss"
    return outcome, {"loss": 0, "draw": 1, "win": 2}[outcome], placement, None
