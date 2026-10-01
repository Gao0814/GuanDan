"""Model-facing summaries for publicly confirmed, bounded endgame searches."""

from __future__ import annotations

from itertools import combinations
from typing import Mapping

from engine.public_endgame import (
    PUBLIC_ENDGAME_MAX_CARDS,
    PUBLIC_ENDGAME_MAX_HAND,
    PUBLIC_ENDGAME_MAX_NODES,
    PUBLIC_ENDGAME_MAX_SECONDS,
    PublicEndgameAnalysis,
)


_OUTCOME_TEXT = {
    1: "本队胜",
    0: "规则平",
    -1: "负局",
}


def _valid_reachable_values(values: object) -> bool:
    return (
        isinstance(values, tuple)
        and bool(values)
        and all(type(value) is int and value in _OUTCOME_TEXT for value in values)
        and tuple(sorted(set(values))) == values
    )


def format_confirmed_public_hands(
    observation: object,
    known_hands_by_player: object,
) -> str | None:
    """Render a unique, current public hand assignment with its evidence limit."""
    if not isinstance(observation, dict) or not isinstance(known_hands_by_player, Mapping):
        return None
    if set(known_hands_by_player) != {1, 2, 3, 4}:
        return None
    my_info = observation.get("my_info")
    other_players = observation.get("other_players")
    if not isinstance(my_info, dict) or not isinstance(other_players, list):
        return None
    my_id = my_info.get("player_id")
    my_team = my_info.get("team")
    if type(my_id) is not int or my_id not in {1, 2, 3, 4} or not isinstance(my_team, str):
        return None

    rows: dict[int, dict[str, object]] = {
        my_id: {
            "team": my_team,
            "hand_count": my_info.get("hand_count"),
            "finished": my_info.get("hand_count") == 0,
        }
    }
    for row in other_players:
        if not isinstance(row, dict) or type(row.get("player_id")) is not int:
            return None
        player_id = int(row["player_id"])
        if player_id in rows or player_id not in {1, 2, 3, 4}:
            return None
        rows[player_id] = row
    if set(rows) != {1, 2, 3, 4}:
        return None

    active_external: list[tuple[int, tuple[str, ...], str]] = []
    for player_id, row in rows.items():
        cards = known_hands_by_player.get(player_id)
        count = row.get("hand_count")
        team = row.get("team")
        finished = row.get("finished")
        if (
            not isinstance(cards, (list, tuple))
            or any(not isinstance(card, str) or not card or len(card) > 3 for card in cards)
            or type(count) is not int
            or len(cards) != count
            or type(finished) is not bool
            or finished != (count == 0)
            or not isinstance(team, str)
        ):
            return None
        if player_id != my_id and count > 0:
            relation = "队友" if team == my_team else "对手"
            active_external.append((player_id, tuple(cards), relation))
    if len(active_external) != 1:
        return None

    player_id, cards, relation = active_external[0]
    cards_text = " ".join(cards)
    return (
        f"玩家{player_id}（{relation}）当前实体手牌已唯一确证：{cards_text}。"
        "证据边界：依赖本家当前手牌、完整公开出牌carrier_cards、公开余牌容量和108张实体牌守恒；"
        "仅描述此观察时点，不含概率、未来抽牌或未公开事实。"
    )


def select_proven_endgame_action(
    analysis: PublicEndgameAnalysis,
    legal_actions: list[dict[str, object]],
    route_signatures: Mapping[int, object],
) -> int | None:
    """Choose a completed guaranteed route, then apply full-profile shortcuts.

    The M8 signature keeps suit-flush and wildcard resource differences apart.
    It is used only for non-guaranteed full-profile comparisons; a guaranteed
    raw route is selected directly and never merged with another route. All
    returned IDs are original legal IDs.
    """
    if not legal_actions:
        return None
    legal_ids = [
        int(action["action_id"])
        for action in legal_actions
        if isinstance(action, dict) and type(action.get("action_id")) is int
    ]
    if (
        len(legal_ids) != len(legal_actions)
        or len(set(legal_ids)) != len(legal_ids)
    ):
        return None

    if analysis.status == "proven_win":
        proven_id = analysis.proven_action_id
        if type(proven_id) is int and proven_id in legal_ids:
            return proven_id
        return None
    if analysis.status != "solved":
        return None

    guarantees = dict(analysis.action_values)
    reachable = dict(analysis.action_reachable_values)
    if (
        set(guarantees) != set(legal_ids)
        or set(reachable) != set(legal_ids)
        or any(type(value) is not int or value not in _OUTCOME_TEXT for value in guarantees.values())
        or any(not _valid_reachable_values(values) for values in reachable.values())
    ):
        return None

    # Full analyses remain selectable if constructed by another bounded
    # producer. Do not require route uniqueness: one completed guarantee is
    # sufficient, and distinct M8 signatures stay as distinct raw routes.
    guaranteed_ids = [action_id for action_id in legal_ids if guarantees[action_id] == 1]
    if guaranteed_ids:
        return guaranteed_ids[0]

    routes: dict[tuple[object, ...], list[int]] = {}
    route_by_action: dict[int, tuple[object, ...]] = {}
    for action_id in legal_ids:
        signature = route_signatures.get(action_id, ("raw-action", action_id))
        try:
            hash(signature)
        except TypeError:
            signature = ("raw-action", action_id)
        route = (signature, guarantees[action_id], reachable[action_id])
        routes.setdefault(route, []).append(action_id)
        route_by_action[action_id] = route

    def representative(route: tuple[object, ...]) -> int:
        # Legal action order is stable and matches the M8 projection's first
        # surviving representative for equivalent ordinary actions.
        return next(action_id for action_id in legal_ids if route_by_action[action_id] == route)

    reachable_win_routes = {
        route for route in routes if 1 in route[2]
    }
    if len(reachable_win_routes) == 1:
        return representative(next(iter(reachable_win_routes)))
    if reachable_win_routes:
        return None

    best_floor = max(int(route[1]) for route in routes)
    best_routes = {route for route in routes if route[1] == best_floor}
    has_strictly_worse_route = any(int(route[1]) < best_floor for route in routes)
    if len(best_routes) == 1 and has_strictly_worse_route:
        return representative(next(iter(best_routes)))
    return None


def describe_proven_endgame_choice(
    analysis: PublicEndgameAnalysis,
    action_id: int,
) -> str | None:
    """Explain the exact bounded-search basis for a local original action ID."""
    if type(action_id) is not int:
        return None
    if analysis.status == "proven_win":
        if analysis.proven_action_id != action_id:
            return None
        return (
            f"公开确证残局本地选择 action_id={action_id}："
            "该首手的完整引擎续局证明显示按队伍最优应对可保底本队胜。"
        )
    if analysis.status != "solved":
        return None
    guarantee = dict(analysis.action_values).get(action_id)
    reachable = dict(analysis.action_reachable_values).get(action_id)
    if guarantee not in _OUTCOME_TEXT or not _valid_reachable_values(reachable):
        return None
    if guarantee == 1:
        return (
            f"公开确证残局本地选择 action_id={action_id}："
            "该策略路线可保底本队胜。"
        )
    if 1 in reachable:
        return (
            f"公开确证残局本地选择 action_id={action_id}："
            "这是唯一存在合法本队胜局续线的策略路线；"
            f"保底为{_OUTCOME_TEXT[guarantee]}，不保证获胜。"
        )
    return (
        f"公开确证残局本地选择 action_id={action_id}："
        f"这是无可达本队胜局续线时唯一严格更优的保底路线，"
        f"保底为{_OUTCOME_TEXT[guarantee]}。"
    )


def format_public_endgame_comparisons(
    analysis: PublicEndgameAnalysis,
    displayed_actions: list[dict[str, object]],
    *,
    legal_actions: list[dict[str, object]] | None = None,
    preferred_action_ids: tuple[int, ...] = (),
    max_pairs: int = 2,
) -> str | None:
    """Compare visible profiles, or report equality after full raw-ID coverage."""
    if analysis.status != "solved" or type(max_pairs) is not int or max_pairs <= 0:
        return None
    guarantees = dict(analysis.action_values)
    reachable = dict(analysis.action_reachable_values)
    if (
        any(type(value) is not int or value not in _OUTCOME_TEXT for value in guarantees.values())
        or any(not _valid_reachable_values(values) for values in reachable.values())
    ):
        return None
    if legal_actions is not None:
        legal_ids = [a.get("action_id") for a in legal_actions if isinstance(a, dict)]
        complete = (
            bool(legal_ids) and len(legal_ids) == len(legal_actions)
            and all(type(i) is int for i in legal_ids)
            and len(set(legal_ids)) == len(legal_ids)
            and len(analysis.action_values) == len(legal_ids)
            and len(analysis.action_reachable_values) == len(legal_ids)
            and all(type(i) is int for i, _ in analysis.action_values)
            and all(type(i) is int for i, _ in analysis.action_reachable_values)
            and set(guarantees) == set(reachable) == set(legal_ids)
            and all(guarantees[i] in reachable[i] for i in legal_ids)
            and bool(displayed_actions)
            and all(isinstance(a, dict) and a in legal_actions for a in displayed_actions)
        )
        if not complete:
            return None
        if len(set(guarantees.values())) == len(set(reachable.values())) == 1:
            floor = guarantees[legal_ids[0]]
            outcomes = reachable[legal_ids[0]]
            no_win = "无可达本队胜局" if 1 not in outcomes else ""
            return (
                "【公开残局推演】已用公开确证手牌与引擎完整核对全部原始合法首手："
                f"均保底{_OUTCOME_TEXT[floor]}、可达{{{','.join(_OUTCOME_TEXT[v] for v in outcomes)}}}"
                f"{'，' + no_win if no_win else ''}；当前队伍胜平负指标未区分首手优劣。"
                "可达仅表示存在合法路径，不表示对手配合或保证；牌权、资源与其他策略价值仍需判断。"
            )
    visible = [
        action for action in displayed_actions
        if type(action.get("action_id")) is int
        and int(action["action_id"]) in guarantees
        and int(action["action_id"]) in reachable
    ]
    preferred = set(preferred_action_ids)
    pairs = []
    for first, second in combinations(visible, 2):
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        first_floor = guarantees[first_id]
        second_floor = guarantees[second_id]
        first_reachable = reachable[first_id]
        second_reachable = reachable[second_id]
        if first_floor == second_floor and first_reachable == second_reachable:
            continue
        anchored = int(first_id in preferred) + int(second_id in preferred)
        opportunity_difference = int((1 in first_reachable) != (1 in second_reachable))
        pairs.append((
            (
                anchored,
                opportunity_difference,
                abs(first_floor - second_floor),
                len(set(first_reachable) ^ set(second_reachable)),
            ),
            first,
            second,
        ))
    pairs.sort(key=lambda item: (
        item[0],
        -min(int(item[1]["action_id"]), int(item[2]["action_id"])),
        -max(int(item[1]["action_id"]), int(item[2]["action_id"])),
    ), reverse=True)

    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    used_ids: set[int] = set()
    for _, first, second in pairs:
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        if first_id in used_ids or second_id in used_ids:
            continue
        selected.append((first, second))
        used_ids.update((first_id, second_id))
        if len(selected) >= max_pairs:
            break
    if not selected:
        return None

    lines = [
        "【公开残局推演】使用完整公开手牌、引擎合法动作与终局真值；"
        f"活动余牌不超过{PUBLIC_ENDGAME_MAX_CARDS}张、单家不超过{PUBLIC_ENDGAME_MAX_HAND}张，"
        f"搜索上限{PUBLIC_ENDGAME_MAX_NODES}节点/{PUBLIC_ENDGAME_MAX_SECONDS * 1000:.0f}毫秒。"
        "保底是双方按队伍目标应对时的终局值；可达只表示存在一条合法续局，不表示对手会配合、概率或保证。"
    ]
    for first, second in selected:
        entries = []
        for action in (first, second):
            action_id = int(action["action_id"])
            label = str(action.get("display_text", action.get("declared_pattern", "")))[:48]
            opportunity = (
                "有合法本队胜局续线（非保胜）"
                if 1 in reachable[action_id] and guarantees[action_id] != 1
                else "可保底本队胜"
                if guarantees[action_id] == 1
                else "无可达本队胜局续线"
            )
            outcomes = ",".join(_OUTCOME_TEXT[value] for value in reachable[action_id])
            entries.append(
                f"action_id={action_id}({label})=保底{_OUTCOME_TEXT[guarantees[action_id]]}"
                f"/{opportunity}/可达{{{outcomes}}}"
            )
        lines.append(
            "M5公开残局对照 " + " vs ".join(entries)
            + "；可达结果是条件性合法路径，不是胜率预测。"
        )
    return "\n".join(lines)
