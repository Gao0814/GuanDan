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
        return card_count == 6
    if pattern == "steel_plate":
        return card_count == 6
    if pattern == "bomb":
        return card_count >= 4
    if pattern == "joker_bomb":
        return card_count == 4
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


def _candidate_display(action: dict[str, object]) -> str:
    pattern = str(action["declared_pattern"])
    cards = [str(card) for card in action["declared_cards"]]
    if pattern not in {"straight_flush"}:
        cards = [str(_physical_rank(card) or card) for card in cards]
    return f"{pattern} {' '.join(cards[:8])}"


def _has_urgent_opponent(state: _ValidatedPublicState) -> bool:
    return any(
        row.get("team") != state.my_team
        and not bool(row.get("finished"))
        and 0 < int(row.get("hand_count", 0)) <= 2
        for player_id, row in state.player_rows.items()
        if player_id != state.my_player_id
    )


_SHORT_PATTERN = {
    "single": "单", "pair": "对", "triple": "三", "triple_with_pair": "三带二",
    "straight": "顺", "pair_straight": "连对", "steel_plate": "钢板",
    "bomb": "同点炸", "straight_flush": "同花顺", "joker_bomb": "天王",
}
_BOMB_PATTERNS = ("bomb", "straight_flush", "joker_bomb")


def _control_cost(action: dict[str, object], level: str) -> int:
    return sum(
        1 for token in action["carrier_cards"]
        if _physical_rank(token) in {*_CONTROL_RANKS, level}
    )


def _residual_facts(
    action: dict[str, object], hand_counts: Counter[str], level: str,
) -> tuple[int, tuple[int, int, int, int], str]:
    residual_tokens = hand_counts.copy()
    residual_tokens.subtract(Counter(action["carrier_cards"]))
    if any(count < 0 for count in residual_tokens.values()):
        return 0, (0, 0, 0, 0), "校验失败"
    ranks = Counter()
    for token, count in residual_tokens.items():
        rank = _physical_rank(token)
        if rank is not None and count > 0:
            ranks[rank] += count
    groups = Counter(ranks.values())
    group_counts = (
        groups.get(1, 0), groups.get(2, 0), groups.get(3, 0),
        sum(count for size, count in groups.items() if size >= 4),
    )
    controls = ",".join(
        f"{rank}×{ranks[rank]}" for rank in dict.fromkeys((*_CONTROL_RANKS, level))
        if ranks.get(rank, 0)
    ) or "无"
    total = sum(ranks.values())
    return total, group_counts, (
        f"余{total}/组{group_counts[0]},{group_counts[1]},{group_counts[2]},"
        f"{group_counts[3]}/留{controls}"
    )


def _declared_strength(action: dict[str, object], level: str) -> tuple[int, ...]:
    ranks = [_physical_rank(card) or str(card) for card in action["declared_cards"]]
    strengths = [_rank_strength(rank, level) for rank in ranks if rank in _RANKS]
    return tuple(sorted(strengths))


def _candidate_difference(
    first: dict[str, object],
    second: dict[str, object],
    hand_counts: Counter[str],
    level: str,
) -> int:
    if int(first["action_id"]) == int(second["action_id"]):
        return 0
    difference = (
        abs(len(first["carrier_cards"]) - len(second["carrier_cards"])) * 2
        + abs(_control_cost(first, level) - _control_cost(second, level)) * 4
        + abs(int(first.get("wildcard_count", 0)) - int(second.get("wildcard_count", 0))) * 3
        + sum(abs(a - b) for a, b in zip(
            _residual_facts(first, hand_counts, level)[1],
            _residual_facts(second, hand_counts, level)[1],
        ))
        + abs(sum(_declared_strength(first, level)) - sum(_declared_strength(second, level)))
    )
    if first["declared_pattern"] != second["declared_pattern"]:
        difference += 2
    return difference


def _candidate_pairs(
    raws: list[object],
    hand_counts: Counter[str],
    *,
    prefer_high_single: bool = False,
    preferred_action_ids: tuple[int, ...] = (),
    level: str = "2",
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    valid_by_id: dict[int, dict[str, object]] = {}
    by_pattern: dict[str, list[dict[str, object]]] = {pattern: [] for pattern in _PATTERN_ORDER}
    for raw in raws:
        action = _action_record(raw, hand_counts)
        if action is None:
            continue
        action_id = int(action["action_id"])
        if action_id in valid_by_id:
            continue
        valid_by_id[action_id] = action
        by_pattern[str(action["declared_pattern"])].append(action)

    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    seen: set[frozenset[int]] = set()

    def add_pair(first: dict[str, object] | None, second: dict[str, object] | None) -> None:
        if first is None or second is None or _candidate_difference(first, second, hand_counts, level) <= 0:
            return
        key = frozenset((int(first["action_id"]), int(second["action_id"])))
        if key in seen or len(selected) >= 2:
            return
        seen.add(key)
        selected.append((first, second))

    preferred = [valid_by_id[action_id] for action_id in preferred_action_ids if action_id in valid_by_id]
    preferred_pairs: list[tuple[int, dict[str, object], dict[str, object]]] = []
    if len(preferred) >= 2:
        for index, first in enumerate(preferred):
            for second in preferred[index + 1:]:
                preferred_pairs.append((_candidate_difference(first, second, hand_counts, level), first, second))
    elif len(preferred) == 1:
        first = preferred[0]
        preferred_pairs.extend(
            (_candidate_difference(first, second, hand_counts, level), first, second)
            for second in valid_by_id.values()
            if int(second["action_id"]) != int(first["action_id"])
        )
    if preferred_pairs:
        _, first, second = max(
            preferred_pairs,
            key=lambda item: (item[0], -int(item[1]["action_id"]), -int(item[2]["action_id"])),
        )
        add_pair(first, second)

    route_pairs: list[tuple[int, dict[str, object], dict[str, object]]] = []
    for priority, (first_pattern, second_pattern) in enumerate((
        ("pair_straight", "single"), ("straight", "single"),
        ("triple", "single"), ("pair", "single"),
        ("bomb", "pair_straight"), ("bomb", "single"),
    )):
        first = _choose_action(
            raws, first_pattern, hand_counts,
            high_pattern=(first_pattern == "pair_straight"), level=level,
        )
        second = _choose_action(
            raws, second_pattern, hand_counts,
            low_single=(second_pattern == "single" and not prefer_high_single),
            high_single=(second_pattern == "single" and prefer_high_single),
            level=level,
        )
        if first is not None and second is not None:
            route_pairs.append((priority, first, second))
    route_pairs.sort(key=lambda item: (item[0], -_candidate_difference(item[1], item[2], hand_counts, level)))
    for _, first, second in route_pairs:
        add_pair(first, second)
        if selected:
            # Reserve the other slot for a same-pattern control-resource
            # contrast when one exists, instead of spending both on cross routes.
            break

    same_pattern_pairs: list[tuple[int, int, dict[str, object], dict[str, object]]] = []
    for pattern, actions in by_pattern.items():
        if len(actions) < 2:
            continue
        ordered = sorted(actions, key=lambda item: (
            _control_cost(item, level), int(item.get("wildcard_count", 0)),
            _declared_strength(item, level), int(item["action_id"]),
        ))
        first, second = ordered[0], ordered[-1]
        score = _candidate_difference(first, second, hand_counts, level)
        if score > 0:
            pattern_priority = 0 if pattern in {"single", "pair"} else 1
            same_pattern_pairs.append((pattern_priority, score, first, second))
    same_pattern_pairs.sort(key=lambda item: (item[0], -item[1]))
    for _, _, first, second in same_pattern_pairs:
        add_pair(first, second)
    return tuple(selected)


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


def _cards_from_tokens(tokens: tuple[str, ...] | list[str]) -> tuple[Card, ...] | None:
    cards: list[Card] = []
    for token in tokens:
        rank = _physical_rank(token)
        if rank is None:
            return None
        cards.append(Card(rank=rank, suit=None if token in JOKER_RANKS else token[-1]))
    return tuple(cards)


def _active_external_order(state: _ValidatedPublicState):
    active = [
        player for player in state.constraints.players
        if player.relation != "self" and player.remaining_capacity > 0
        and not bool(state.player_rows[int(player.player_id)].get("finished"))
    ]
    clockwise = {
        ((state.my_player_id + offset - 1) % 4) + 1: offset
        for offset in range(1, 5)
    }
    return tuple(sorted(active, key=lambda player: clockwise[int(player.player_id)]))


def _possible_cards_for_player(
    state: _ValidatedPublicState,
    possible_tokens: tuple[str, ...],
) -> tuple[Card, ...] | None:
    token_set = set(possible_tokens)
    cards: list[Card] = []
    for token, count in state.belief.unseen_cards_by_token.items():
        if token not in token_set:
            continue
        rank = _physical_rank(token)
        if rank is None:
            return None
        cards.extend(
            Card(rank=rank, suit=None if token in JOKER_RANKS else token[-1])
            for _ in range(count)
        )
    return tuple(cards)


def _response_requirements(
    engine: BaseRuleEngine,
    action: dict[str, object],
    cards: tuple[Card, ...],
    state: _ValidatedPublicState,
    cache: dict[tuple[tuple[tuple[str, str | None], ...], int], tuple[object, ...] | None],
) -> tuple[object, ...] | None:
    leading = _pattern_action(action, state.my_player_id)
    if leading is None:
        return None
    hand_key = tuple(sorted((card.rank, card.suit) for card in cards))
    cache_key = (hand_key, int(action["action_id"]))
    if cache_key not in cache:
        try:
            cache[cache_key] = engine.public_beating_response_requirements(cards, leading, state.level)
        except (TypeError, ValueError):
            cache[cache_key] = None
    return cache[cache_key]


def _response_pattern_text(requirements: tuple[object, ...], leading_pattern: str) -> str:
    patterns = {str(getattr(requirement, "pattern_type", "")) for requirement in requirements}
    ordered = [pattern for pattern in _PATTERN_ORDER if pattern in patterns]
    chosen = list(dict.fromkeys((
        *([leading_pattern] if leading_pattern in patterns else []),
        *[pattern for pattern in ordered if pattern in _BOMB_PATTERNS],
        *[pattern for pattern in ordered if pattern not in _BOMB_PATTERNS][:3],
    )))
    return "/".join(_SHORT_PATTERN[pattern] for pattern in chosen if pattern in _SHORT_PATTERN) or "应手"


def _player_response_text(
    state: _ValidatedPublicState,
    player: object,
    action: dict[str, object],
    engine: BaseRuleEngine,
    cache: dict[tuple[tuple[tuple[str, str | None], ...], int], tuple[object, ...] | None],
    owner: object | None,
) -> str:
    player_id = int(getattr(player, "player_id"))
    capacity = int(getattr(player, "remaining_capacity"))
    row = state.player_rows[player_id]
    relation = "友" if row.get("team") == state.my_team else "敌"
    is_next = _next_active_player(state) == player_id
    label = f"{('*' if is_next else '')}P{player_id}{relation}余{capacity}"

    if owner is not None and int(getattr(owner, "player_id")) == player_id:
        cards = _cards_from_tokens(tuple(getattr(owner, "confirmed_cards")))
        confirmed = True
    else:
        constraint = next(item for item in state.constraints.players if int(item.player_id) == player_id)
        cards = _possible_cards_for_player(state, constraint.possible_tokens)
        confirmed = False
    if cards is None:
        return f"{label}未知"
    requirements = _response_requirements(engine, action, cards, state, cache)
    if requirements is None:
        return f"{label}未知(规则核验)"
    if confirmed:
        if requirements:
            return f"{label}确认能接[{_response_pattern_text(requirements, str(action['declared_pattern']))}]"
        return f"{label}已知不能接"

    viable = tuple(
        requirement for requirement in requirements
        if int(getattr(requirement, "card_count", 0)) <= capacity
    )
    if viable:
        wildcard = "+配" if any(int(getattr(item, "wildcard_count", 0)) for item in viable) else ""
        return f"{label}可能[{_response_pattern_text(viable, str(action['declared_pattern']))}{wildcard}]"
    if requirements:
        minimum = min(int(getattr(item, "card_count", 0)) for item in requirements)
        return f"{label}不能接(容量<{minimum})"
    return f"{label}不能接(未见池无应手)"


def _candidate_comparison_line(
    state: _ValidatedPublicState,
    first: dict[str, object],
    second: dict[str, object],
    hand_counts: Counter[str],
    engine: BaseRuleEngine,
    response_cache: dict[tuple[tuple[tuple[str, str | None], ...], int], tuple[object, ...] | None],
    owner: object | None,
    *,
    recommendation_anchored: bool,
) -> str:
    players = _active_external_order(state)
    first_residual = _residual_facts(first, hand_counts, state.level)[2]
    second_residual = _residual_facts(second, hand_counts, state.level)[2]
    first_responses = ";".join(
        _player_response_text(state, player, first, engine, response_cache, owner)
        for player in players
    ) or "无活动外部玩家"
    second_responses = ";".join(
        _player_response_text(state, player, second, engine, response_cache, owner)
        for player in players
    ) or "无活动外部玩家"
    recommendation_note = "含公开推荐候选；" if recommendation_anchored else ""
    return (
        f"M3候选对照 action_id={first['action_id']}({_candidate_display(first)}) vs "
        f"action_id={second['action_id']}({_candidate_display(second)})："
        f"出后余手A={first_residual}/B={second_residual}；"
        f"逐家即时应手A[{first_responses}] B[{second_responses}]；"
        f"{recommendation_note}E1未分配仅报可能/容量排除，E2只认守恒唯一手牌；"
        "不能立即接不等于之后安全或必胜。"
    )


def _known_hand_response_line(
    state: _ValidatedPublicState,
    candidates: list[object],
    hand_counts: Counter[str],
    owner: object,
    engine: BaseRuleEngine,
    response_cache: dict[tuple[tuple[tuple[str, str | None], ...], int], tuple[object, ...] | None],
    preferred_action_ids: tuple[int, ...],
) -> str | None:
    candidate = None
    for action_id in preferred_action_ids:
        candidate = next(
            (item for item in candidates if isinstance(item, dict) and item.get("action_id") == action_id),
            None,
        )
        if candidate is not None:
            break
    if candidate is None:
        for pattern in ("single", "pair", "pair_straight", "straight", "triple", "bomb", "straight_flush"):
            candidate = _choose_action(candidates, pattern, hand_counts, level=state.level)
            if candidate is not None:
                break
    if candidate is None:
        return None
    player = next(
        item for item in state.constraints.players
        if int(item.player_id) == int(getattr(owner, "player_id"))
    )
    response = _player_response_text(state, player, candidate, engine, response_cache, owner)
    residual = _residual_facts(candidate, hand_counts, state.level)[2]
    return (
        f"M3唯一归属核验 action_id={candidate['action_id']}({_candidate_display(candidate)})；"
        f"逐家即时应手={response}；出后{residual}；"
        "只判断已确认手牌能否立即接，不推出后续牌权或胜负。"
    )


def build_card_tracking_summary(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    *,
    current_level_rank: str | None = None,
    preferred_action_ids: tuple[int, ...] = (),
) -> str:
    """Return concise public card facts and comparisons of displayed canonical actions."""
    state = _validated_public_state(observation)
    if state is None or (current_level_rank is not None and current_level_rank != state.level):
        return "【记牌信息】\n证据级=E0（公开历史或容量未能验证）；省略隐藏牌归属、炸弹与候选牌权推断。"

    my_counts = Counter(state.my_hand)
    played_count = sum(len(player.played_cards) for player in state.belief.players)
    external_count = state.belief.external_unknown_count
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
        f"证据级={evidence}；守恒108张：已出{played_count}、本家{len(state.my_hand)}、外部未见{external_count}。",
    ]
    if owner is not None:
        row = state.player_rows[int(owner.player_id)]
        relation = "队友" if row.get("team") == state.my_team else "对手"
        lines.append(f"已确认持有人={relation}P{owner.player_id}余{owner.remaining_capacity}；仅由公开守恒确认。")
    else:
        player_facts = []
        for player in _active_external_order(state):
            role = "友" if state.player_rows[int(player.player_id)].get("team") == state.my_team else "敌"
            next_marker = "*" if int(player.player_id) == _next_active_player(state) else ""
            player_facts.append(f"{next_marker}P{player.player_id}{role}余{player.remaining_capacity}")
        lines.append(
            "外部归属未确认；行动顺序=" + ("/".join(player_facts) or "无活动外部持牌人")
            + "；pass不证明无牌，未见牌不指派给单家。"
        )
    if urgent_opponents:
        lines.append(f"公开紧迫对手最少余{min(urgent_opponents)}张；这不是具体持牌事实。")

    comparisons = _candidate_pairs(
        list(legal_actions),
        my_counts,
        prefer_high_single=_has_urgent_opponent(state),
        preferred_action_ids=preferred_action_ids,
        level=state.level,
    )
    engine = BaseRuleEngine()
    response_cache: dict[
        tuple[tuple[tuple[str, str | None], ...], int], tuple[object, ...] | None
    ] = {}
    for first, second in comparisons:
        lines.append(_candidate_comparison_line(
            state, first, second, my_counts, engine, response_cache, owner,
            recommendation_anchored=(
                int(first["action_id"]) in preferred_action_ids
                or int(second["action_id"]) in preferred_action_ids
            ),
        ))
    if not comparisons and owner is not None:
        unique_line = _known_hand_response_line(
            state, list(legal_actions), my_counts, owner, engine, response_cache,
            preferred_action_ids,
        )
        if unique_line:
            lines.append(unique_line)

    prefix = "【记牌信息】\n"
    summary = prefix + "\n".join(lines)
    while len(summary) > _TRACKING_LIMIT and len(lines) > (3 if owner is not None else 2):
        lines.pop()
        summary = prefix + "\n".join(lines)
    return summary


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
        preferred_action_ids: tuple[int, ...] = (),
    ) -> None:
        del history_actions, my_hand
        if observation is None:
            self._summary = "【记牌信息】\n证据级=E0（缺少完整公开观测）；不推断外部牌归属。"
        else:
            self._summary = build_card_tracking_summary(
                observation,
                legal_actions or [],
                current_level_rank=self.current_level_rank,
                preferred_action_ids=preferred_action_ids,
            )

    def get_summary(self, my_hand: list[str]) -> str:
        del my_hand
        return self._summary
