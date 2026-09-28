"""Public card facts tied to the canonical candidates shown to DeepSeek."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agents.card_belief import (
    CardBeliefState,
    JOKER_RANKS,
    NORMAL_RANKS,
    SUITS,
    build_card_belief,
    build_double_deck_token_pool,
)
from agents.card_constraints import CardConstraintState, build_card_constraints
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine


_RANKS = NORMAL_RANKS + JOKER_RANKS
_CONTROL_RANKS = ("A", "2", "SJ", "BJ")
_ALLOWED_LEVELS = frozenset(NORMAL_RANKS)
_PATTERN_ORDER = (
    "single", "pair", "triple", "straight", "pair_straight",
    "steel_plate", "triple_with_pair", "bomb", "straight_flush", "joker_bomb",
)
_TRACKING_LIMIT = 1_350


def _physical_rank(token: object) -> str | None:
    if not isinstance(token, str):
        return None
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _rank_strength(rank: str, level: str) -> int:
    if rank == level:
        return 16
    if rank == "SJ":
        return 17
    if rank == "BJ":
        return 18
    return NORMAL_RANKS.index(rank) + 3


def _count_text(cards: tuple[str, ...] | list[str]) -> str:
    counts = Counter(_physical_rank(card) for card in cards)
    return ",".join(
        f"{rank}×{counts[rank]}" for rank in _RANKS if counts.get(rank, 0)
    ) or "无"


def _count_groups(cards: Counter[str]) -> str:
    groups = Counter(cards.values())
    return (
        f"孤张{groups.get(1, 0)}/对子{groups.get(2, 0)}/"
        f"三张{groups.get(3, 0)}/四张以上{sum(n for size, n in groups.items() if size >= 4)}"
    )


def _valid_play_card_count(pattern: str, card_count: int) -> bool:
    if pattern == "single":
        return card_count == 1
    if pattern == "pair":
        return card_count == 2
    if pattern == "triple":
        return card_count == 3
    if pattern in {"straight", "triple_with_pair", "straight_flush"}:
        return card_count == 5
    if pattern == "pair_straight":
        return card_count >= 6 and card_count % 2 == 0
    if pattern == "steel_plate":
        return card_count == 6
    if pattern == "bomb":
        return card_count >= 4
    if pattern == "joker_bomb":
        return card_count == 2
    return False


@dataclass(frozen=True, slots=True)
class _ValidatedPublicState:
    belief: CardBeliefState
    constraints: CardConstraintState
    player_rows: dict[int, dict[str, object]]
    my_player_id: int
    my_team: str
    level: str
    my_hand: tuple[str, ...]


def _validated_public_state(observation: object) -> _ValidatedPublicState | None:
    """Accept only a complete physical-card ledger consistent with four 27-card deals."""
    if not isinstance(observation, dict):
        return None
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    other_players = observation.get("other_players")
    history = observation.get("history")
    if not all(isinstance(value, dict) for value in (my_info, current_round, history)):
        return None
    if not isinstance(other_players, list) or len(other_players) != 3:
        return None
    assert isinstance(my_info, dict) and isinstance(current_round, dict) and isinstance(history, dict)

    my_player_id = my_info.get("player_id")
    my_team = my_info.get("team")
    level = current_round.get("current_level_rank")
    hand = my_info.get("hand_cards")
    hand_count = my_info.get("hand_count")
    if (
        type(my_player_id) is not int or my_player_id not in {1, 2, 3, 4}
        or not isinstance(my_team, str) or not my_team
        or not isinstance(level, str) or level not in _ALLOWED_LEVELS
        or current_round.get("current_player_id") != my_player_id
        or not isinstance(hand, list) or type(hand_count) is not int
        or hand_count != len(hand)
    ):
        return None
    my_hand = tuple(hand)
    if any(_physical_rank(card) is None for card in my_hand):
        return None

    rows: dict[int, dict[str, object]] = {
        my_player_id: {
            "player_id": my_player_id, "team": my_team,
            "hand_count": hand_count, "finished": hand_count == 0,
        }
    }
    for raw_player in other_players:
        if not isinstance(raw_player, dict):
            return None
        player_id = raw_player.get("player_id")
        team = raw_player.get("team")
        count = raw_player.get("hand_count")
        finished = raw_player.get("finished")
        if (
            type(player_id) is not int or player_id not in {1, 2, 3, 4}
            or player_id in rows or not isinstance(team, str) or not team
            or type(count) is not int or count < 0 or type(finished) is not bool
            or finished != (count == 0)
        ):
            return None
        rows[player_id] = dict(raw_player)
    if set(rows) != {1, 2, 3, 4}:
        return None
    teams = [str(row["team"]) for row in rows.values()]
    if len(set(teams)) != 2 or any(teams.count(team) != 2 for team in set(teams)):
        return None

    raw_actions = history.get("actions")
    finish_order = history.get("finish_order")
    if not isinstance(raw_actions, list) or not isinstance(finish_order, list):
        return None
    if any(type(player_id) is not int or player_id not in rows for player_id in finish_order):
        return None
    if len(set(finish_order)) != len(finish_order):
        return None
    if {player_id for player_id, row in rows.items() if row.get("finished")} != set(finish_order):
        return None

    played_by_player: Counter[int] = Counter()
    used_tokens: Counter[str] = Counter(my_hand)
    for raw_action in raw_actions:
        if not isinstance(raw_action, dict):
            return None
        player_id = raw_action.get("player_id")
        pattern = raw_action.get("declared_pattern")
        carriers = raw_action.get("carrier_cards")
        if type(player_id) is not int or player_id not in rows or not isinstance(pattern, str):
            return None
        # M3 uses physical carrier cards only. Legacy declared-card fallback is
        # deliberately insufficient for ownership or control comparisons.
        if not isinstance(carriers, list):
            return None
        if pattern != "pass" and not _valid_play_card_count(pattern, len(carriers)):
            return None
        if pattern == "pass":
            if carriers:
                return None
            continue
        if not carriers or any(_physical_rank(card) is None for card in carriers):
            return None
        played_by_player[player_id] += len(carriers)
        used_tokens.update(carriers)
    pool = build_double_deck_token_pool()
    if any(count > pool.get(token, 0) for token, count in used_tokens.items()):
        return None
    if any(played_by_player[player_id] + int(row["hand_count"]) != 27 for player_id, row in rows.items()):
        return None

    belief = build_card_belief(observation)
    if not belief.token_pool_exact:
        return None
    constraints = build_card_constraints(belief)
    if (
        not constraints.token_constraints_exact
        or not constraints.is_consistent
        or sum(belief.unseen_cards_by_token.values()) != belief.external_unknown_count
    ):
        return None
    return _ValidatedPublicState(
        belief=belief,
        constraints=constraints,
        player_rows=rows,
        my_player_id=my_player_id,
        my_team=my_team,
        level=level,
        my_hand=my_hand,
    )


def _action_record(raw: object, hand_counts: Counter[str]) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    action_id = raw.get("action_id")
    pattern = raw.get("declared_pattern")
    declared = raw.get("declared_cards")
    carriers = raw.get("carrier_cards")
    if (
        type(action_id) is not int or not isinstance(pattern, str)
        or pattern not in _PATTERN_ORDER or not isinstance(declared, list)
        or not isinstance(carriers, list) or not carriers
        or type(raw.get("wildcard_count", 0)) is not int
        or raw.get("wildcard_count", 0) < 0
        or len(declared) != len(carriers)
        or not _valid_play_card_count(pattern, len(carriers))
    ):
        return None
    if any(_physical_rank(card) is None for card in carriers):
        return None
    used = Counter(carriers)
    if any(count > hand_counts[token] for token, count in used.items()):
        return None
    if pattern == "pass":
        return None
    if not declared or any(_physical_rank(card) is None and card not in NORMAL_RANKS for card in declared):
        return None
    return raw


def _pattern_action(raw: dict[str, object], player_id: int) -> Action | None:
    try:
        pattern = PatternType(str(raw["declared_pattern"]))
        declared_cards = raw["declared_cards"]
        carrier_cards = raw["carrier_cards"]
        if not isinstance(declared_cards, list) or not isinstance(carrier_cards, list):
            return None
        declared_items = []
        for token in declared_cards:
            rank = _physical_rank(token)
            if rank is None and isinstance(token, str) and token in NORMAL_RANKS:
                rank = token
            if rank is None:
                return None
            suit = str(token)[-1] if isinstance(token, str) and str(token)[-1:] in SUITS else None
            declared_items.append(Card(rank=rank, suit=suit))
        declared = tuple(declared_items)
        carriers = tuple(
            Card(
                rank=_physical_rank(token) or "",
                suit=None if token in JOKER_RANKS else str(token)[-1],
            )
            for token in carrier_cards
        )
        wildcard_count = raw.get("wildcard_count", 0)
        if type(wildcard_count) is not int or wildcard_count < 0:
            return None
        return Action(
            player_id=player_id,
            action_type=ActionType.PLAY,
            declared_pattern=pattern,
            declared_cards=declared,
            carrier_cards=carriers,
            wildcard_count=wildcard_count,
        )
    except (TypeError, ValueError):
        return None


def _choose_action(
    raws: list[object],
    pattern: str,
    hand_counts: Counter[str],
    *,
    low_single: bool = False,
    high_single: bool = False,
    high_pattern: bool = False,
    level: str = "2",
) -> dict[str, object] | None:
    actions = [
        item for item in (_action_record(raw, hand_counts) for raw in raws)
        if item is not None and item["declared_pattern"] == pattern
    ]
    if not actions:
        return None
    actions.sort(key=lambda item: (
        int(item.get("wildcard_count", 0)) > 0,
        (
            min((_rank_strength(str(_physical_rank(card) or card), level) for card in item["declared_cards"]), default=0)
            if low_single
            else -max((_rank_strength(str(_physical_rank(card) or card), level) for card in item["declared_cards"]), default=0)
            if high_single or high_pattern
            else 0
        ),
        int(item["action_id"]),
    ))
    return actions[0]


def _residual_summary(action: dict[str, object], hand_counts: Counter[str], level: str) -> str:
    residual_tokens = hand_counts.copy()
    residual_tokens.subtract(Counter(action["carrier_cards"]))
    if any(count < 0 for count in residual_tokens.values()):
        return "余手校验失败"
    residual = Counter()
    for token, count in residual_tokens.items():
        rank = _physical_rank(token)
        if rank is not None and count > 0:
            residual[rank] += count
    controls = residual
    control_text = ",".join(
        f"{rank}×{controls[rank]}" for rank in dict.fromkeys((*_CONTROL_RANKS, level))
        if controls.get(rank, 0)
    ) or "无"
    return f"余{sum(residual.values())}张/同点结构({_count_groups(residual)})/保留高点候选({control_text})"


def _candidate_display(action: dict[str, object]) -> str:
    pattern = str(action["declared_pattern"])
    cards = [str(card) for card in action["declared_cards"]]
    if pattern not in {"straight_flush"}:
        cards = [str(_physical_rank(card) or card) for card in cards]
    return f"{pattern} {' '.join(cards[:8])}"


def _external_control_note(state: _ValidatedPublicState, action: dict[str, object]) -> str:
    pattern = str(action["declared_pattern"])
    unseen = state.belief.unseen_cards_by_rank
    declared = [_physical_rank(token) or str(token) for token in action["declared_cards"]]
    if pattern == "single" and declared:
        rank = declared[0]
        higher_ranks = [
            other for other in _RANKS
            if unseen.get(other, 0)
            and _rank_strength(other, state.level) > _rank_strength(rank, state.level)
        ]
        count = sum(unseen[other] for other in higher_ranks)
        higher_ranks.sort(key=lambda other: _rank_strength(other, state.level), reverse=True)
        rank_text = "/".join(
            f"{other}×{unseen[other]}" for other in higher_ranks[:5]
        ) or "无"
        relation_note = "已知持牌人" if _exact_single_owner(state) is not None else "归属未知"
        return f"外部仍见更高单张牌池={count}张(较高点数候选={rank_text}；{relation_note})"
    possible_bombs = [rank for rank in _RANKS if rank not in JOKER_RANKS and unseen.get(rank, 0) >= 4]
    return "外部四张同点池=" + ("/".join(possible_bombs[:4]) if possible_bombs else "无") + "(不能确认集中于一人)"


def _has_urgent_opponent(state: _ValidatedPublicState) -> bool:
    return any(
        row.get("team") != state.my_team
        and not bool(row.get("finished"))
        and 0 < int(row.get("hand_count", 0)) <= 2
        for player_id, row in state.player_rows.items()
        if player_id != state.my_player_id
    )


def _candidate_pairs(
    raws: list[object],
    hand_counts: Counter[str],
    *,
    prefer_high_single: bool = False,
    level: str = "2",
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    by_pattern = {
        pattern: _choose_action(
            raws,
            pattern,
            hand_counts,
            low_single=(pattern == "single" and not prefer_high_single),
            high_single=(pattern == "single" and prefer_high_single),
            high_pattern=(pattern == "pair_straight"),
            level=level,
        )
        for pattern in _PATTERN_ORDER
    }
    wanted = (
        ("pair_straight", "single"),
        ("straight", "single"),
        ("triple", "single"),
        ("pair", "single"),
        ("bomb", "pair_straight"),
        ("bomb", "single"),
    )
    result: list[tuple[dict[str, object], dict[str, object]]] = []
    seen: set[tuple[int, int]] = set()
    for first_pattern, second_pattern in wanted:
        first = by_pattern.get(first_pattern)
        second = by_pattern.get(second_pattern)
        if first is None or second is None:
            continue
        pair = (int(first["action_id"]), int(second["action_id"]))
        if pair in seen:
            continue
        seen.add(pair)
        result.append((first, second))
        if len(result) == 2:
            break
    return tuple(result)


def _exact_single_owner(state: _ValidatedPublicState):
    external = [
        player for player in state.constraints.players
        if player.relation != "self" and player.remaining_capacity > 0
    ]
    if len(external) != 1:
        return None
    player = external[0]
    if len(player.confirmed_cards) != player.remaining_capacity:
        return None
    if len(player.confirmed_cards) != state.belief.external_unknown_count:
        return None
    return player


def _next_active_player(state: _ValidatedPublicState) -> int | None:
    active = {
        player_id for player_id, row in state.player_rows.items()
        if not bool(row.get("finished")) and int(row.get("hand_count", 0)) > 0
    }
    current = state.my_player_id
    for _ in range(4):
        current = (current % 4) + 1
        if current in active:
            return current
    return None


def _known_hand_response_line(
    state: _ValidatedPublicState,
    candidates: list[object],
    hand_counts: Counter[str],
) -> str | None:
    owner = _exact_single_owner(state)
    if owner is None or _next_active_player(state) != owner.player_id:
        return None
    candidate = None
    urgent = _has_urgent_opponent(state)
    for pattern in ("pair_straight", "straight", "single", "pair", "triple", "bomb", "straight_flush"):
        candidate = _choose_action(
            candidates,
            pattern,
            hand_counts,
            low_single=(pattern == "single" and not urgent),
            high_single=(pattern == "single" and urgent),
            high_pattern=(pattern == "pair_straight"),
            level=state.level,
        )
        if candidate is not None:
            break
    if candidate is None:
        return None
    known_hand = tuple(
        Card(rank=_physical_rank(token) or "", suit=None if token in JOKER_RANKS else token[-1])
        for token in owner.confirmed_cards
    )
    compared = [candidate]
    for pair in _candidate_pairs(
        candidates,
        hand_counts,
        prefer_high_single=urgent,
        level=state.level,
    ):
        if int(candidate["action_id"]) in {int(pair[0]["action_id"]), int(pair[1]["action_id"])}:
            alternative = pair[1] if int(pair[0]["action_id"]) == int(candidate["action_id"]) else pair[0]
            if int(alternative["action_id"]) != int(candidate["action_id"]):
                compared.append(alternative)
            break

    engine = BaseRuleEngine()
    response_notes = []
    for action in compared:
        leading = _pattern_action(action, state.my_player_id)
        if leading is None:
            continue
        try:
            response_types = engine.public_beating_pattern_types(known_hand, leading, state.level)
        except (TypeError, ValueError):
            continue
        response_text = ",".join(response_types) if response_types else "无"
        response_notes.append(
            f"action_id={action['action_id']}({_candidate_display(action)})可立即压过牌型={response_text}"
        )
    if not response_notes:
        return None
    row = state.player_rows[int(owner.player_id)]
    relation = "队友" if row.get("team") == state.my_team else "对手"
    known_high = Counter(_physical_rank(token) for token in owner.confirmed_cards)
    high_text = ",".join(
        f"{rank}×{known_high[rank]}" for rank in dict.fromkeys((*_CONTROL_RANKS, state.level))
        if known_high.get(rank, 0)
    ) or "无"
    return (
        f"M3唯一归属核验 {'；'.join(response_notes)}：下一位{relation}的公开守恒手牌"
        f"余{owner.remaining_capacity}张；已知高点资源({high_text})。"
        f"本家候选后余牌分别为{'；'.join(_residual_summary(action, hand_counts, state.level) for action in compared)}；"
        "此项仅说明立即接管牌型可行性，不推出胜负或后续牌权。"
    )


def build_card_tracking_summary(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    *,
    current_level_rank: str | None = None,
) -> str:
    """Return concise public card facts and comparisons of displayed canonical actions."""
    state = _validated_public_state(observation)
    if state is None or (current_level_rank is not None and current_level_rank != state.level):
        return "【记牌信息】\n证据级=E0（公开历史或容量未能验证）；省略隐藏牌归属、炸弹与候选牌权推断。"

    my_counts = Counter(state.my_hand)
    played_count = sum(len(player.played_cards) for player in state.belief.players)
    external_count = state.belief.external_unknown_count
    active_external = [
        player for player in state.constraints.players
        if player.relation != "self" and player.remaining_capacity > 0
    ]
    teammate_capacity = sum(
        player.remaining_capacity for player in active_external
        if state.player_rows[int(player.player_id)].get("team") == state.my_team
    )
    opponent_capacity = sum(
        player.remaining_capacity for player in active_external
        if state.player_rows[int(player.player_id)].get("team") != state.my_team
    )
    owner = _exact_single_owner(state)
    urgent_opponents = [
        int(row["hand_count"])
        for player_id, row in state.player_rows.items()
        if player_id != state.my_player_id
        and row.get("team") != state.my_team
        and not bool(row.get("finished"))
        and type(row.get("hand_count")) is int
        and 0 < int(row["hand_count"]) <= 2
    ]
    evidence = "E2唯一归属" if owner is not None else "E1精确牌池/多人未分配"
    lines = [
        f"证据级={evidence}；实体牌守恒108张：已出{played_count}、本家持有{len(state.my_hand)}、外部未见{external_count}。",
    ]
    if owner is not None:
        row = state.player_rows[int(owner.player_id)]
        relation = "队友" if row.get("team") == state.my_team else "对手"
        lines.append(f"已确认持有人={relation}玩家{owner.player_id}，手牌点数={_count_text(list(owner.confirmed_cards))}。")
    else:
        possible_roles = []
        if opponent_capacity:
            possible_roles.append(f"对手余{opponent_capacity}张可能持有")
        if teammate_capacity:
            possible_roles.append(f"队友余{teammate_capacity}张可能持有")
        possible_holders = []
        for player in sorted(active_external, key=lambda item: int(item.player_id)):
            role = (
                "队友"
                if state.player_rows[int(player.player_id)].get("team") == state.my_team
                else "对手"
            )
            possible_holders.append(
                f"玩家{player.player_id}({role},余{player.remaining_capacity}张)"
            )
        lines.append(
            "外部归属未确认：" + ("、".join(possible_roles) if possible_roles else "无活动外部持牌人")
            + ("；可能持牌人=" + "、".join(possible_holders) if possible_holders else "")
            + "；具体牌归属未知，不能视为单家手牌。"
        )
    lines.append(
        "公开紧迫对手最少余="
        + (f"{min(urgent_opponents)}张；比较高单阻断时核对外部响应牌池" if urgent_opponents else "无1–2张对手")
        + "，不把紧迫度当作其具体持牌事实。"
    )

    bomb_ranks = [
        rank for rank in NORMAL_RANKS
        if state.belief.unseen_cards_by_rank.get(rank, 0) >= 4
    ]
    lines.append(
        "外部同点炸弹线索="
        + ("未见池仍有至少4张的点数:" + "/".join(bomb_ranks[:5]) if bomb_ranks else "未见池无4张同点集中")
        + "（不证明同一家持有）；同花顺是独立炸弹类别，同点数统计不能排除它。"
    )

    comparisons = _candidate_pairs(
        list(legal_actions),
        my_counts,
        prefer_high_single=_has_urgent_opponent(state),
        level=state.level,
    )
    urgent_opponent = _has_urgent_opponent(state)
    for first, second in comparisons:
        notes = [_external_control_note(state, first)]
        if first["declared_pattern"] != second["declared_pattern"]:
            notes.append(_external_control_note(state, second))
        if "pair_straight" in {first["declared_pattern"], second["declared_pattern"]}:
            route_context = (
                "当前有公开紧迫对手：将实际高单候选的即时拦截价值与连对清理并列比较；"
                "只按可核验牌型和外部响应池衡量，未分配牌的持有人仍未知。"
                if urgent_opponent
                else "当前无公开1–2张对手；若自然连对出后仍保留高点候选且余组更轻，可考虑先清组合；"
                "小单保组路线仍须比较，不把牌数优势当作固定指令。"
            )
        else:
            route_context = "结合队友/对手余牌、可能接管资源和余组比较；不固定偏向任一路线。"
        lines.append(
            f"M3候选对照 action_id={first['action_id']}({ _candidate_display(first) }) vs "
            f"action_id={second['action_id']}({ _candidate_display(second) })："
            f"本次出牌张数={len(first['carrier_cards'])}/{len(second['carrier_cards'])}；"
            f"出后资源={_residual_summary(first, my_counts, state.level)}；"
            f"另一候选出后={_residual_summary(second, my_counts, state.level)}；"
            f"{'；'.join(notes)}。"
            + route_context
        )

    unique_line = _known_hand_response_line(state, list(legal_actions), my_counts)
    if unique_line:
        lines.append(unique_line)

    summary = "【记牌信息】\n" + "\n".join(lines)
    if len(summary) <= _TRACKING_LIMIT:
        return summary
    return summary[:_TRACKING_LIMIT - 1].rstrip() + "…"


class CardTracker:
    """Stateful compatibility wrapper; facts are rebuilt from each public observation."""

    def __init__(self, current_level_rank: str):
        self.current_level_rank = current_level_rank
        self._summary = "【记牌信息】\n证据级=E0（缺少完整公开观测）；不推断外部牌归属。"

    def update(
        self,
        history_actions: list[dict[str, object]],
        my_hand: list[str],
        *,
        observation: dict[str, object] | None = None,
        legal_actions: list[dict[str, object]] | None = None,
    ) -> None:
        del history_actions, my_hand
        if observation is None:
            self._summary = "【记牌信息】\n证据级=E0（缺少完整公开观测）；不推断外部牌归属。"
        else:
            self._summary = build_card_tracking_summary(
                observation,
                legal_actions or [],
                current_level_rank=self.current_level_rank,
            )

    def get_summary(self, my_hand: list[str]) -> str:
        del my_hand
        return self._summary
