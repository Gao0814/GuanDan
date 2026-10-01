"""Public card facts tied to the canonical candidates shown to DeepSeek."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

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
_ResponseSignature = tuple[str, tuple[tuple[str, str | None], ...]]


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
        return 4 <= card_count <= 10
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


@dataclass(frozen=True, slots=True)
class _CandidateFacts:
    residual: tuple[int, tuple[int, int, int, int], str]
    control_cost: int
    carrier_count: int
    wildcard_count: int
    declared_strength: int
    pattern: str


@dataclass(frozen=True, slots=True)
class _PublicPassEvidence:
    player_id: int
    step_no: int
    lead_action: Action
    lead_pattern: str
    response_confirmed_step_no: int | None
    leader_id: int
    hand_count: int
    cards_played_since: int
    opponent_led: bool


@dataclass(frozen=True, slots=True)
class _PublicPlayEvidence:
    step_no: int
    player_id: int
    action: Action
    hand_count_after: int
    urgent_response: bool


@dataclass(frozen=True, slots=True)
class PublicCarriedPairEvidence:
    player_id: int
    step_no: int
    triple_rank: str
    pair_rank: str
    hand_count_after: int
    later_carriers: tuple[Card, ...]
    binding_kind: str
    later_lower_pair: bool
    urgent_response: bool
    larger_pair_possible: bool | None


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
        or not 0 <= raw.get("wildcard_count", 0) <= 2
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


_SHORT_PATTERN = {
    "single": "单", "pair": "对", "triple": "三", "triple_with_pair": "三带二",
    "straight": "顺", "pair_straight": "连对", "steel_plate": "钢板",
    "bomb": "同点炸", "straight_flush": "同花顺", "joker_bomb": "天王",
}
_SHORT_RESOURCE = {
    "single": "单", "pair": "对", "bomb": "炸",
    "straight_flush": "同花", "joker_bomb": "天王",
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
    first_facts: _CandidateFacts,
    second_facts: _CandidateFacts,
) -> int:
    if int(first["action_id"]) == int(second["action_id"]):
        return 0
    difference = (
        abs(first_facts.carrier_count - second_facts.carrier_count) * 2
        + abs(first_facts.control_cost - second_facts.control_cost) * 4
        + abs(first_facts.wildcard_count - second_facts.wildcard_count) * 3
        + sum(abs(a - b) for a, b in zip(first_facts.residual[1], second_facts.residual[1]))
        + abs(first_facts.declared_strength - second_facts.declared_strength)
    )
    if first_facts.pattern != second_facts.pattern:
        difference += 2
    return difference


def _candidate_pairs(
    raws: list[object],
    hand_counts: Counter[str],
    *,
    state: _ValidatedPublicState,
    engine: BaseRuleEngine,
    owner: object | None,
    profile_cache: dict[int, tuple[dict[str, object], ...]],
    facts_cache: dict[int, _CandidateFacts],
    preferred_action_ids: tuple[int, ...] = (),
    pass_evidence: tuple[_PublicPassEvidence, ...] = (),
    level: str = "2",
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    valid_by_id: dict[int, dict[str, object]] = {}
    for raw in raws:
        action = _action_record(raw, hand_counts)
        if action is None:
            continue
        action_id = int(action["action_id"])
        if action_id in valid_by_id:
            continue
        valid_by_id[action_id] = action

    profile_cache.update(_candidate_response_profiles(
        state, tuple(valid_by_id.values()), engine, owner, pass_evidence,
    ))
    for action_id, action in valid_by_id.items():
        residual = _residual_facts(action, hand_counts, level)
        facts_cache[action_id] = _CandidateFacts(
            residual=residual,
            control_cost=_control_cost(action, level),
            carrier_count=len(action["carrier_cards"]),
            wildcard_count=int(action.get("wildcard_count", 0)),
            declared_strength=sum(_declared_strength(action, level)),
            pattern=str(action["declared_pattern"]),
        )

    def pass_difference(
        first_profiles: tuple[dict[str, object], ...],
        second_profiles: tuple[dict[str, object], ...],
    ) -> int:
        score = 0
        for first_profile, second_profile in zip(first_profiles, second_profiles):
            enemy = first_profile["relation"] == "敌"
            next_player = bool(first_profile["is_next"])
            urgent = bool(first_profile["urgent"])
            weight = 8 if enemy and next_player else 6 if enemy and urgent else 4 if enemy else 3 if next_player else 2
            if first_profile.get("pass_signature") != second_profile.get("pass_signature"):
                score += weight * 2
        return score

    def response_difference(
        first_profiles: tuple[dict[str, object], ...],
        second_profiles: tuple[dict[str, object], ...],
    ) -> int:
        score = 0
        for first_profile, second_profile in zip(first_profiles, second_profiles):
            enemy = first_profile["relation"] == "敌"
            next_player = bool(first_profile["is_next"])
            urgent = bool(first_profile["urgent"])
            weight = 8 if enemy and next_player else 6 if enemy and urgent else 4 if enemy else 3 if next_player else 2
            if first_profile["status"] != second_profile["status"]:
                score += weight * 3
            first_patterns = set(first_profile["patterns"])
            second_patterns = set(second_profile["patterns"])
            score += weight * len(first_patterns ^ second_patterns)

            first_resources = dict(first_profile["resource_signature"])
            second_resources = dict(second_profile["resource_signature"])
            for family in first_resources.keys() | second_resources.keys():
                first_tier, first_wild = first_resources.get(family, (0, False))
                second_tier, second_wild = second_resources.get(family, (0, False))
                score += weight * min(3, abs(int(first_tier) - int(second_tier)))
                if first_wild != second_wild:
                    score += weight
        return score

    def pair_priority(
        first: dict[str, object], second: dict[str, object],
    ) -> tuple[int, int, int, int, int, int] | None:
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        first_profiles = profile_cache[first_id]
        second_profiles = profile_cache[second_id]
        response_score = response_difference(first_profiles, second_profiles)
        pass_score = pass_difference(first_profiles, second_profiles)
        first_facts = facts_cache[first_id]
        second_facts = facts_cache[second_id]
        structure_score = _candidate_structure_difference(first, second, first_facts, second_facts)
        if response_score == 0 and pass_score == 0 and structure_score == 0:
            return None
        preferred_count = int(
            int(first["action_id"]) in preferred_action_ids
        ) + int(
            int(second["action_id"]) in preferred_action_ids
        )
        return (
            preferred_count,
            response_score,
            pass_score,
            structure_score,
            _candidate_difference(first, second, first_facts, second_facts),
            -min(int(first["action_id"]), int(second["action_id"])),
        )

    scored: list[
        tuple[tuple[int, int, int, int, int, int], dict[str, object], dict[str, object]]
    ] = []
    candidates = list(valid_by_id.values())
    for index, first in enumerate(candidates):
        for second in candidates[index + 1:]:
            priority = pair_priority(first, second)
            if priority is not None:
                scored.append((priority, first, second))
    scored.sort(key=lambda item: (
        item[0], -max(int(item[1]["action_id"]), int(item[2]["action_id"])),
    ), reverse=True)

    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    seen: set[frozenset[int]] = set()

    def add_pair(item: tuple[tuple[int, int, int, int, int, int], dict[str, object], dict[str, object]]) -> None:
        _, first, second = item
        key = frozenset((int(first["action_id"]), int(second["action_id"])))
        if key in seen or len(selected) >= 2:
            return
        seen.add(key)
        selected.append((first, second))

    if scored:
        add_pair(scored[0])
    # Reserve one of the two bounded explanation slots for a pair whose
    # candidate-specific risk actually differs because of a public pass event.
    selected_pass_sensitive = any(
        priority[2] > 0
        and frozenset((int(first["action_id"]), int(second["action_id"]))) in seen
        for priority, first, second in scored
    )
    if len(selected) < 2 and not selected_pass_sensitive:
        for item in sorted(scored, key=lambda value: (
            value[0][2], value[0][0], value[0][1], value[0][3],
            value[0][4], value[0][5],
        ), reverse=True):
            if item[0][2] > 0:
                add_pair(item)
                break
    if len(selected) < 2:
        for item in scored:
            add_pair(item)
            if len(selected) == 2:
                break
    return tuple(selected)


def _candidate_structure_difference(
    first: dict[str, object],
    second: dict[str, object],
    first_facts: _CandidateFacts,
    second_facts: _CandidateFacts,
) -> int:
    if int(first["action_id"]) == int(second["action_id"]):
        return 0
    first_groups = first_facts.residual[1]
    second_groups = second_facts.residual[1]
    first_controls = first_facts.residual[2].rsplit("/留", 1)[-1]
    second_controls = second_facts.residual[2].rsplit("/留", 1)[-1]
    return (
        abs(first_facts.control_cost - second_facts.control_cost) * 4
        + abs(first_facts.wildcard_count - second_facts.wildcard_count) * 3
        + abs(first_facts.carrier_count - second_facts.carrier_count) * 2
        + sum(abs(a - b) for a, b in zip(first_groups, second_groups))
        + (2 if first_controls != second_controls else 0)
        + (1 if first_facts.pattern != second_facts.pattern else 0)
    )


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


def _history_clock_is_complete(observation: object) -> bool:
    if not isinstance(observation, dict):
        return False
    current_round = observation.get("current_round")
    history = observation.get("history")
    if not isinstance(current_round, dict) or not isinstance(history, dict):
        return False
    actions = history.get("actions")
    step_no = current_round.get("step_no")
    round_no = current_round.get("round_no")
    if (
        not isinstance(actions, list)
        or type(step_no) is not int
        or step_no != len(actions)
        or type(round_no) is not int
        or round_no < 1
    ):
        return False
    previous_round = 0
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            return False
        action_step = action.get("step_no")
        action_round = action.get("round_no")
        if (
            type(action_step) is not int
            or action_step != index + 1
            or type(action_round) is not int
            or action_round < 1
            or action_round < previous_round
            or action_round > previous_round + 1
        ):
            return False
        previous_round = action_round
    if not actions:
        return step_no == 0 and round_no == 1
    return round_no in {previous_round, previous_round + 1}


def exact_public_hand_assignment(
    observation: object,
) -> dict[int, tuple[str, ...]] | None:
    """Return all current hands only when public conservation proves them.

    The caller receives no hidden state. External cards are exposed here only
    when one external player's confirmed hand accounts for the full unseen
    pool; finished players are exactly empty. Ambiguous or malformed payloads
    return None.
    """
    state = _validated_public_state(observation)
    if state is None or not _history_clock_is_complete(observation):
        return None
    owner = _exact_single_owner(state)
    if owner is None:
        return None
    assigned: dict[int, tuple[str, ...]] = {}
    for player_id, row in state.player_rows.items():
        if player_id == state.my_player_id:
            assigned[player_id] = tuple(state.my_hand)
        elif bool(row.get("finished")):
            assigned[player_id] = ()
        elif player_id == int(owner.player_id):
            assigned[player_id] = tuple(owner.confirmed_cards)
        else:
            return None
    if sum(len(cards) for cards in assigned.values()) != sum(
        int(row.get("hand_count", 0)) for row in state.player_rows.values()
    ):
        return None
    return assigned


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


def _response_signature(action: dict[str, object]) -> _ResponseSignature:
    declared = action.get("declared_cards")
    declared_signature = tuple(
        (
            _physical_rank(card) or str(card),
            str(card)[-1] if isinstance(card, str) and str(card)[-1:] in SUITS else None,
        )
        for card in declared
    ) if isinstance(declared, list) else ()
    return str(action.get("declared_pattern", "")), declared_signature


def _response_pattern_text(requirements: tuple[object, ...], leading_pattern: str) -> str:
    patterns = {str(getattr(requirement, "pattern_type", "")) for requirement in requirements}
    ordered = [pattern for pattern in _PATTERN_ORDER if pattern in patterns]
    chosen = list(dict.fromkeys((
        *([leading_pattern] if leading_pattern in patterns else []),
        *[pattern for pattern in ordered if pattern in _BOMB_PATTERNS],
        *[pattern for pattern in ordered if pattern not in _BOMB_PATTERNS][:3],
    )))
    return "/".join(_SHORT_PATTERN[pattern] for pattern in chosen if pattern in _SHORT_PATTERN) or "应手"


def _resource_tier(count: int) -> tuple[str, int]:
    if count <= 0:
        return "0", 0
    if count == 1:
        return "1", 1
    if count <= 3:
        return "2-3", 2
    if count <= 7:
        return "4-7", 3
    if count <= 15:
        return "8-15", 4
    return "16+", 5


def _resource_text(
    counts: tuple[object, ...] | None,
    *,
    confirmed: bool,
    leading_pattern: str,
) -> tuple[str, tuple[tuple[str, tuple[int, bool]], ...]]:
    if counts is None:
        return "资源未知", ()
    by_family = {
        str(getattr(item, "pattern_type", "")): item
        for item in counts
    }
    families: list[str] = []
    if leading_pattern in {"single", "pair"}:
        families.append(leading_pattern)
    families.extend(
        family for family in _BOMB_PATTERNS
        if family in by_family and family not in families
    )
    signature: list[tuple[str, tuple[int, bool]]] = []
    rendered: list[str] = []
    for family in families:
        item = by_family.get(family)
        count = int(getattr(item, "resource_count", 0)) if item is not None else 0
        wildcard_count = int(getattr(item, "wildcard_resource_count", 0)) if item is not None else 0
        bucket, tier = _resource_tier(count)
        signature.append((family, (tier, wildcard_count > 0)))
        value = f"{_SHORT_RESOURCE[family]}{bucket}"
        if wildcard_count:
            wild_bucket, _ = _resource_tier(wildcard_count)
            value += f"(配{wild_bucket})"
        if count or family == leading_pattern:
            rendered.append(value)
    prefix = "确资源" if confirmed else "上界"
    return f"{prefix}{'、'.join(rendered) if rendered else '0'}", tuple(signature)


def _player_response_profile(
    state: _ValidatedPublicState,
    player: object,
    action: dict[str, object],
    response_summary: object | None,
    confirmed: bool,
    *,
    unknown_reason: str = "未知(规则核验)",
) -> dict[str, object]:
    player_id = int(getattr(player, "player_id"))
    capacity = int(getattr(player, "remaining_capacity"))
    row = state.player_rows[player_id]
    relation = "友" if row.get("team") == state.my_team else "敌"
    is_next = _next_active_player(state) == player_id
    label = f"{('*' if is_next else '')}P{player_id}{relation}余{capacity}"
    urgent = relation == "敌" and 0 < capacity <= 2

    def unknown(text: str) -> dict[str, object]:
        return {
            "text": f"{label}{text}", "status": "unknown", "patterns": (),
            "resource_signature": (), "relation": relation,
            "is_next": is_next, "urgent": urgent, "pass_signature": (),
        }

    if response_summary is None:
        return unknown(unknown_reason)
    requirements = getattr(response_summary, "requirements", None)
    resource_counts = getattr(response_summary, "resource_counts", None)
    if not isinstance(requirements, tuple) or not isinstance(resource_counts, tuple):
        return unknown(unknown_reason)
    leading_pattern = str(action["declared_pattern"])
    resource_text, resource_signature = _resource_text(
        resource_counts, confirmed=confirmed, leading_pattern=leading_pattern,
    )
    viable = tuple(
        requirement for requirement in requirements
        if confirmed or int(getattr(requirement, "card_count", 0)) <= capacity
    )
    resource_families = tuple(
        str(getattr(item, "pattern_type", "")) for item in (resource_counts or ())
    )
    patterns = tuple(dict.fromkeys((
        *(str(getattr(item, "pattern_type", "")) for item in viable),
        *resource_families,
    )))
    can_respond = bool(viable or resource_families)

    if confirmed:
        if can_respond:
            status = "confirmed_can"
            response = f"确认能接[{_response_pattern_text(viable, leading_pattern)}]"
        else:
            status = "confirmed_cannot"
            response = "已知不能接"
    elif can_respond:
        status = "possible"
        wildcard = "+配" if any(int(getattr(item, "wildcard_count", 0)) for item in viable) else ""
        response = f"可能[{_response_pattern_text(viable, leading_pattern)}{wildcard}]"
    elif requirements:
        status = "capacity_excluded"
        minimum = min(int(getattr(item, "card_count", 0)) for item in requirements)
        response = f"不能接(容量<{minimum})"
    else:
        status = "pool_excluded"
        response = "不能接(未见池无应手)"
    return {
        "text": f"{label}{response}{resource_text}", "status": status,
        "patterns": patterns, "resource_signature": resource_signature,
        "relation": relation, "is_next": is_next, "urgent": urgent,
        "pass_signature": (),
    }


def _validated_public_history(
    observation: dict[str, object],
    state: _ValidatedPublicState,
    engine: BaseRuleEngine,
) -> tuple[tuple[_PublicPassEvidence, ...], tuple[_PublicPlayEvidence, ...]] | None:
    """Validate the shared public clock/turn/count history for behavior evidence.

    A later public action that beats the passed-over lead proves its carrier
    cards were in that player's hand at the earlier pass. Otherwise the event
    remains ambiguous: it may have been no response or a strategic pass. Neither
    outcome changes a hard card domain.
    """
    history = observation.get("history")
    current_round = observation.get("current_round")
    if not isinstance(history, dict) or not isinstance(current_round, dict):
        return None
    actions = history.get("actions")
    step_no = current_round.get("step_no")
    current_round_no = current_round.get("round_no")
    if (
        not isinstance(actions, list)
        or type(step_no) is not int or step_no != len(actions)
        or type(current_round_no) is not int or current_round_no < 1
    ):
        return None

    remaining = {player_id: 27 for player_id in state.player_rows}
    finished_order: list[int] = []
    expected_player: int | None = None
    round_no = 1
    lead: Action | None = None
    lead_raw: dict[str, object] | None = None
    leader_id: int | None = None
    pending: tuple[int, ...] = ()
    passes: list[tuple[int, int, int, Action, int, int]] = []
    parsed_plays: list[_PublicPlayEvidence] = []

    def active_players() -> set[int]:
        return {player_id for player_id, count in remaining.items() if count > 0}

    def clockwise_after(player_id: int, active: set[int]) -> tuple[int, ...]:
        ordered = []
        for offset in range(1, 5):
            candidate = ((player_id + offset - 1) % 4) + 1
            if candidate in active and candidate != player_id:
                ordered.append(candidate)
        return tuple(ordered)

    def next_round_leader(player_id: int, active: set[int]) -> int | None:
        if player_id in active:
            return player_id
        partner = ((player_id + 1) % 4) + 1
        if partner in active:
            return partner
        ordered = clockwise_after(player_id, active)
        return ordered[0] if ordered else None

    def reset_after_round(played_by: int) -> bool:
        nonlocal lead, lead_raw, leader_id, pending, expected_player, round_no
        next_player = next_round_leader(played_by, active_players())
        if next_player is None:
            return False
        lead = None
        lead_raw = None
        leader_id = None
        pending = ()
        expected_player = next_player
        round_no += 1
        return True

    for index, raw in enumerate(actions):
        if not isinstance(raw, dict):
            return None
        item_step = raw.get("step_no")
        item_round = raw.get("round_no")
        player_id = raw.get("player_id")
        pattern = raw.get("declared_pattern")
        if (
            type(item_step) is not int or item_step != index + 1
            or type(item_round) is not int or item_round != round_no
            or type(player_id) is not int or player_id not in state.player_rows
            or not isinstance(pattern, str)
            or remaining.get(player_id, 0) <= 0
            or (expected_player is not None and player_id != expected_player)
        ):
            return None

        if pattern == "pass":
            if (
                lead is None or leader_id is None or player_id not in pending
                or raw.get("carrier_cards") != []
                or raw.get("declared_cards") != []
            ):
                return None
            passes.append((item_step, round_no, player_id, lead, leader_id, remaining[player_id]))
            pending = tuple(item for item in pending if item != player_id)
            if pending:
                expected_player = pending[0]
            elif not reset_after_round(leader_id):
                return None
            continue

        action = _pattern_action(raw, player_id)
        if (
            action is None or action.declared_pattern is None
            or len(action.declared_cards) != len(action.carrier_cards)
            or not action.carrier_cards
        ):
            return None
        try:
            detected = engine.detect_pattern(action.declared_cards)
        except (TypeError, ValueError):
            return None
        if detected.type != action.declared_pattern:
            return None
        if lead is not None and not engine.can_beat(action, lead, state.level):
            return None
        carrier_count = len(action.carrier_cards)
        if carrier_count > remaining[player_id]:
            return None
        remaining[player_id] -= carrier_count
        if remaining[player_id] == 0:
            finished_order.append(player_id)
            # A live observation cannot follow a double-down or the third finisher.
            if len(finished_order) >= 3 or (
                len(finished_order) == 2
                and state.player_rows[finished_order[0]].get("team")
                == state.player_rows[finished_order[1]].get("team")
            ):
                return None
        urgent_response = (lead is not None and leader_id is not None
            and state.player_rows[player_id].get('team') != state.player_rows[leader_id].get('team')
            and 0 < remaining[leader_id] <= 2)
        parsed_plays.append(_PublicPlayEvidence(item_step, player_id, action, remaining[player_id], urgent_response))
        lead = action
        lead_raw = raw
        leader_id = player_id
        pending = clockwise_after(player_id, active_players())
        if pending:
            expected_player = pending[0]
        elif not reset_after_round(player_id):
            return None

    if current_round_no != round_no:
        return None
    if not actions and (
        current_round_no != 1
        or current_round.get("table_action") is not None
    ):
        return None
    if expected_player is None:
        # The initial observation has not recorded an action yet.
        expected_player = state.my_player_id
    if current_round.get("current_player_id") != expected_player:
        return None
    if any(
        int(state.player_rows[player_id].get("hand_count", -1)) != count
        for player_id, count in remaining.items()
    ):
        return None
    if history.get("finish_order") != finished_order:
        return None
    current_table = current_round.get("table_action")
    if lead is None:
        if current_table is not None:
            return None
    elif (
        not isinstance(current_table, dict)
        or lead_raw is None
        or _response_signature(current_table) != _response_signature(lead_raw)
        or pending[:1] != (expected_player,)
    ):
        return None

    evidence: list[_PublicPassEvidence] = []
    for step, _pass_round, player_id, passed_lead, passed_leader, count in passes:
        proving_step: int | None = None
        for play in parsed_plays:
            if play.step_no <= step or play.player_id != player_id:
                continue
            if engine.can_beat(play.action, passed_lead, state.level):
                proving_step = play.step_no
                break
        evidence.append(
            _PublicPassEvidence(
                player_id=player_id,
                step_no=step,
                lead_action=passed_lead,
                lead_pattern=(
                    passed_lead.declared_pattern.value
                    if passed_lead.declared_pattern is not None else ""
                ),
                response_confirmed_step_no=proving_step,
                leader_id=passed_leader,
                hand_count=count,
                cards_played_since=count - remaining[player_id],
                opponent_led=state.player_rows[player_id].get('team') != state.player_rows[passed_leader].get('team'),
            )
        )
    return tuple(evidence), tuple(parsed_plays)


def _public_pass_evidence(
    observation: dict[str, object], state: _ValidatedPublicState, engine: BaseRuleEngine,
) -> tuple[_PublicPassEvidence, ...]:
    history = _validated_public_history(observation, state, engine)
    return history[0] if history is not None else ()


def _has_public_pair_choice(legal_actions: list[dict[str, object]]) -> bool:
    return len(legal_actions) >= 2 and any(item.get('declared_pattern') == 'pair' for item in legal_actions)


def relevant_public_carried_pairs(
    observation: dict[str, object], legal_actions: list[dict[str, object]],
) -> tuple[PublicCarriedPairEvidence, ...]:
    """Rule-bound public behavior, only for an actual pair-related choice.

    No inferred pair is assigned to a hand or removed from a hard domain.
    The same complete clock/turn/count validation as pass evidence is reused.
    """
    if not _has_public_pair_choice(legal_actions):
        return ()
    state = _validated_public_state(observation)
    if state is None or _exact_single_owner(state) is not None:
        return ()
    engine = BaseRuleEngine()
    history = _validated_public_history(observation, state, engine)
    if history is None:
        return ()
    return _relevant_public_carried_pairs(state, engine, history)


def _public_carried_pair_action(action: Action, engine: BaseRuleEngine, level: str) -> Action | None:
    ranks = Counter(card.rank for card in action.declared_cards)
    pair_cards = tuple(card for card in action.declared_cards if ranks[card.rank] == 2)
    for carriers in combinations(action.carrier_cards, 2):
        bindings = engine.public_action_bindings(action.player_id, PatternType.PAIR, pair_cards,
            carriers, level, first_carrier_only=True, first_binding_only=True)
        if bindings:
            return bindings[0]
    return None


def _larger_public_pair_possible(
    state: _ValidatedPublicState, player_id: int, lead: Action, engine: BaseRuleEngine,
) -> bool | None:
    constraint = next(item for item in state.constraints.players if item.player_id == player_id)
    possible = _possible_cards_for_player(state, constraint.possible_tokens)
    if possible is None:
        return None
    # At most 15 ranks and 45 two-card bindings per rank; no wide pressure
    # resource query. These are feasibility queries, never executable IDs.
    for rank in _RANKS:
        carriers = tuple(card for card in possible if card.rank == rank
                         or (card.rank == state.level and card.suit == 'H'))
        for pair in combinations(carriers, 2):
            bindings = engine.public_action_bindings(player_id, PatternType.PAIR,
                (Card(rank), Card(rank)), pair, state.level,
                first_carrier_only=True, first_binding_only=True)
            if bindings:
                if engine.can_beat(bindings[0], lead, state.level):
                    return True
                # All valid bindings of this same two-card declaration have
                # the same comparison strength; costs remain separate facts.
                break
    return False


def _relevant_public_carried_pairs(
    state: _ValidatedPublicState, engine: BaseRuleEngine,
    history: tuple[tuple[_PublicPassEvidence, ...], tuple[_PublicPlayEvidence, ...]],
) -> tuple[PublicCarriedPairEvidence, ...]:
    passes, plays = history
    latest_plays = {play.player_id: play for play in plays
                    if play.action.declared_pattern == PatternType.TRIPLE_WITH_PAIR}
    latest: dict[int, PublicCarriedPairEvidence] = {}
    for play in latest_plays.values():
        player_id, action = play.player_id, play.action
        row = state.player_rows[player_id]
        if (player_id == state.my_player_id or row.get('finished')
                or int(row['hand_count']) < 2
                or action.declared_pattern != PatternType.TRIPLE_WITH_PAIR
                or play.hand_count_after <= 2):
            continue
        # A terminal response signal outranks a weak historical habit.
        if any(event.player_id == player_id and terminal_pass_signal(event) for event in passes):
            continue
        bindings = engine.public_action_bindings(
            player_id, action.declared_pattern, action.declared_cards,
            action.carrier_cards, state.level,
        )
        if not bindings:
            continue
        ranks = Counter(card.rank for card in action.declared_cards)
        triple = next(rank for rank, count in ranks.items() if count == 3)
        pair = next(rank for rank, count in ranks.items() if count == 2)
        # Binding membership, not a physical-rank guess, determines whether
        # the publicly declared pair includes a wildcard substitute.
        pair_substitutions = {
            tuple(sorted((item.carrier_card.rank, item.carrier_card.suit,
                          item.declared_as.rank, item.declared_as.suit)
                         for item in binding.wildcard_info if item.declared_as.rank == pair))
            for binding in bindings
        }
        kind = ('承载解释不唯一' if len(pair_substitutions) != 1
                else '通配参与携带' if any(pair_substitutions)
                else '自然携带（主组用配）' if any(binding.wildcard_count for binding in bindings) else '自然携带')
        pair_action = _public_carried_pair_action(action, engine, state.level)
        if pair_action is None:
            continue
        later = tuple(item for item in plays if item.player_id == player_id and item.step_no > play.step_no)
        lower = any(
            item.action.declared_pattern == PatternType.PAIR
            and engine.public_action_bindings(player_id, item.action.declared_pattern,
                item.action.declared_cards, item.action.carrier_cards, state.level,
                first_binding_only=True)
            and engine.can_beat(pair_action, item.action, state.level)
            for item in later
        )
        # Ordinary subsequent plays make this weak habit stale. Keep only
        # an explicit counterexample; do not accumulate old clues as samples.
        if later and not lower:
            continue
        larger_possible = (
            _larger_public_pair_possible(state, player_id, pair_action, engine)
            if not later and kind == '自然携带' and not play.urgent_response else None
        )
        latest[player_id] = PublicCarriedPairEvidence(player_id, play.step_no, triple, pair,
            play.hand_count_after, tuple(card for item in later for card in item.action.carrier_cards),
            kind, lower, play.urgent_response, larger_possible)
    return tuple(sorted(latest.values(), key=lambda item: (not item.later_lower_pair, -item.step_no)))[:1]


def _carried_pair_behavior_text(event: PublicCarriedPairEvidence, state: _ValidatedPublicState) -> str:
    role = '友' if state.player_rows[event.player_id].get('team') == state.my_team else '敌'
    fact = (f'P{event.player_id}{role} step{event.step_no}三{event.triple_rank}带对{event.pair_rank}'
            f'（{event.binding_kind}），出后余{event.hand_count_after}、后出{len(event.later_carriers)}张'
            f'、现余{state.player_rows[event.player_id]["hand_count"]}；')
    if event.later_lower_pair:
        return fact + '后出更小对子，否定此前必带最小对；已出实体已扣除，不证当前仍有对子。'
    if event.urgent_response:
        return fact + '当时应手阻断公开少牌对手，紧急争权可解释携带，不按清小对习惯推剩余对子。'
    if event.binding_kind == '自然携带（主组用配）':
        return fact + '主组有通配成本，不按清小对习惯推剩余对子大小。'
    if event.binding_kind != '自然携带':
        return fact + '声明不等于自然实体对子，通配/拆组成本可解释，不据此推剩余对子大小。'
    if event.larger_pair_possible is False:
        return fact + '当前牌池/容量无可行更大对子，旧习惯不支持该回手路线。'
    if event.larger_pair_possible is None:
        return fact + '更大对子路线未核验，不据旧习惯判断剩余对子。'
    return fact + '若按清小对习惯，可弱支持留较大对路线；仅此一对/带中间对留大小回手/拆组亦可解释，备选未知。'


def relevant_public_passes(observation: dict[str, object]) -> tuple[_PublicPassEvidence, ...]:
    """Latest same-family evidence per seat, validated against the full public ledger."""
    state = _validated_public_state(observation)
    if state is None:
        return ()
    raw = observation['current_round'].get('table_action')
    if not isinstance(raw, dict):
        return ()
    current = _pattern_action(raw, state.my_player_id)
    if current is None:
        return ()
    engine = BaseRuleEngine()
    valid_bindings: dict[Action, bool] = {}

    def valid(action: Action) -> bool:
        if action not in valid_bindings:
            valid_bindings[action] = bool(engine.public_action_bindings(
                action.player_id, action.declared_pattern,
                action.declared_cards, action.carrier_cards, state.level,
                first_carrier_only=True, first_binding_only=True,
            ))
        return valid_bindings[action]

    if not valid(current):
        return ()
    latest = {}
    for event in _public_pass_evidence(observation, state, engine):
        if event.player_id == state.my_player_id or state.player_rows[event.player_id].get('finished'):
            continue
        # Valid same-type actions have an engine ordering even when their
        # kickers, suits or physical wildcard bindings differ. Neither an
        # invalid action nor a different ordinary type may imply equality.
        if (event.lead_action.declared_pattern == current.declared_pattern
                and valid(event.lead_action)
                and not engine.can_beat(event.lead_action, current, state.level)):
            latest[event.player_id] = event
    return tuple(sorted(latest.values(), key=lambda item: -item.step_no))


def _pass_behavior_text(event: _PublicPassEvidence, state: _ValidatedPublicState) -> str:
    role = '友' if state.player_rows[event.player_id].get('team') == state.my_team else '敌'
    opponent_led = event.opponent_led
    strength = '/'.join(dict.fromkeys(card.rank for card in event.lead_action.declared_cards))
    text = (f"P{event.player_id}{role} step{event.step_no}余{event.hand_count}，"
            f"对P{event.leader_id}{'对手' if opponent_led else '队友'}的"
            f"{_SHORT_PATTERN.get(event.lead_pattern, event.lead_pattern)}{strength} pass；"
            f"此后已出{event.cards_played_since}张。")
    if event.response_confirmed_step_no is not None:
        return text + f"step{event.response_confirmed_step_no}后接证实此前能接仍让；不确证拆牌，当前牌已变化。"
    if terminal_pass_signal(event):
        return text + "末手若能同型接即可出完却让，当前同型不弱且未换牌：降低依赖其接牌收尾；不是缺牌确证。"
    return text + "当时无应手或策略让牌无法区分；可能护组合，后接也不必然拆牌；变化后旧线索减弱。"


def terminal_pass_signal(event: _PublicPassEvidence) -> bool:
    return (event.opponent_led and event.response_confirmed_step_no is None
            and event.hand_count == len(event.lead_action.carrier_cards)
            and event.cards_played_since == 0)


def _candidate_response_profiles(
    state: _ValidatedPublicState,
    candidates: tuple[dict[str, object], ...],
    engine: BaseRuleEngine,
    owner: object | None,
    pass_evidence: tuple[_PublicPassEvidence, ...] = (),
) -> dict[int, tuple[dict[str, object], ...]]:
    profiles_by_action: dict[int, list[dict[str, object]]] = {
        int(action["action_id"]): [] for action in candidates
    }
    lead_by_signature: dict[_ResponseSignature, Action] = {}
    signature_by_action: dict[int, _ResponseSignature] = {}
    invalid_leads: set[int] = set()
    for action in candidates:
        action_id = int(action["action_id"])
        signature = _response_signature(action)
        signature_by_action[action_id] = signature
        if signature in lead_by_signature:
            continue
        lead = _pattern_action(action, state.my_player_id)
        if lead is None:
            invalid_leads.add(action_id)
        else:
            lead_by_signature[signature] = lead

    constraints_by_player = {
        int(item.player_id): item for item in state.constraints.players
    }
    batch_cache: dict[
        tuple[tuple[tuple[str, str | None], ...], int],
        dict[_ResponseSignature, object] | None,
    ] = {}
    for player in _active_external_order(state):
        player_id = int(getattr(player, "player_id"))
        confirmed = owner is not None and int(getattr(owner, "player_id")) == player_id
        if confirmed:
            cards = _cards_from_tokens(tuple(getattr(owner, "confirmed_cards")))
        else:
            constraint = constraints_by_player[player_id]
            cards = _possible_cards_for_player(state, constraint.possible_tokens)

        summaries_by_signature: dict[_ResponseSignature, object] = {}
        if cards is not None and lead_by_signature:
            capacity = int(getattr(player, "remaining_capacity"))
            card_domain = tuple(sorted((card.rank, card.suit) for card in cards))
            batch_key = (card_domain, capacity)
            if batch_key not in batch_cache:
                try:
                    leads = tuple(lead_by_signature.values())
                    summaries = engine.public_beating_response_summaries(
                        cards,
                        leads,
                        state.level,
                        max_cards=capacity,
                    )
                    batch_cache[batch_key] = dict(zip(lead_by_signature, summaries))
                except (TypeError, ValueError):
                    batch_cache[batch_key] = None
            summaries_by_signature = batch_cache[batch_key] or {}

        for action in candidates:
            action_id = int(action["action_id"])
            if cards is None:
                profile = _player_response_profile(
                    state, player, action, None, confirmed, unknown_reason="未知",
                )
            elif action_id in invalid_leads:
                profile = _player_response_profile(state, player, action, None, confirmed)
            else:
                profile = _player_response_profile(
                    state,
                    player,
                    action,
                    summaries_by_signature.get(signature_by_action[action_id]),
                    confirmed,
                )
            candidate_action = lead_by_signature.get(signature_by_action[action_id])
            matching_passes = tuple(
                item for item in pass_evidence
                if item.player_id == player_id
                and candidate_action is not None
                and engine.can_beat(candidate_action, item.lead_action, state.level)
            )
            if matching_passes:
                latest = max(matching_passes, key=lambda item: item.step_no)
                terminal_relevant = (
                    terminal_pass_signal(latest)
                    and action['declared_pattern'] == latest.lead_pattern
                )
                pass_state = (
                    "confirmed_selective"
                    if latest.response_confirmed_step_no is not None
                    else "terminal_pass" if terminal_relevant
                    else "ambiguous"
                )
                profile["pass_signature"] = ((latest.lead_pattern, pass_state),)
                lead_name = _SHORT_PATTERN.get(latest.lead_pattern, "牌型")
                if terminal_relevant:
                    pass_text = "历史软pass：" + _pass_behavior_text(latest, state)
                elif latest.response_confirmed_step_no is None:
                    pass_text = (
                        f"历史软pass：曾对本候选可压的{lead_name}领出选择pass，"
                        "当时无应手或策略让牌无法区分"
                    )
                else:
                    pass_text = (
                        f"历史软pass：后续公开牌证实曾持有可压该{lead_name}的应手仍pass；"
                        "仅说明当时选择，当前持牌仍按公开上界"
                    )
                profile["text"] = f"{profile['text']}；{pass_text}"
            profiles_by_action[action_id].append(profile)

    return {action_id: tuple(profiles) for action_id, profiles in profiles_by_action.items()}


def _candidate_comparison_line(
    first: dict[str, object],
    second: dict[str, object],
    profile_cache: dict[int, tuple[dict[str, object], ...]],
    facts_cache: dict[int, _CandidateFacts],
    *,
    recommendation_anchored: bool,
) -> str:
    first_id = int(first["action_id"])
    second_id = int(second["action_id"])
    first_residual = facts_cache[first_id].residual[2]
    second_residual = facts_cache[second_id].residual[2]
    first_profiles = profile_cache[first_id]
    second_profiles = profile_cache[second_id]
    first_responses = ";".join(str(profile["text"]) for profile in first_profiles) or "无活动外部玩家"
    second_responses = ";".join(str(profile["text"]) for profile in second_profiles) or "无活动外部玩家"
    recommendation_note = "含公开推荐候选；" if recommendation_anchored else ""
    return (
        f"M3候选对照 action_id={first['action_id']}({_candidate_display(first)}) vs "
        f"action_id={second['action_id']}({_candidate_display(second)})："
        f"出后余手A={first_residual}/B={second_residual}；"
        f"逐家即时应手A[{first_responses}] B[{second_responses}]；"
        f"{recommendation_note}未分配仅报可能/容量排除，E2仅用守恒唯一手牌；"
        "不能立即接不等于之后安全或必胜。"
    )


def _known_hand_response_line(
    state: _ValidatedPublicState,
    candidates: list[object],
    hand_counts: Counter[str],
    owner: object,
    profile_cache: dict[int, tuple[dict[str, object], ...]],
    facts_cache: dict[int, _CandidateFacts],
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
    action_id = int(candidate["action_id"])
    confirmed_profile = profile_cache[action_id][0] if profile_cache[action_id] else None
    response = str(confirmed_profile["text"] if confirmed_profile else "资源未知")
    residual = facts_cache[action_id].residual[2]
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
        lines.append(
            "资源档位是去重的实体承载多重集上界并按各家余牌容量过滤；不同组可重叠用牌，括号“配”是子集，不代表实持数。"
        )
    if urgent_opponents:
        lines.append(f"公开紧迫对手最少余{min(urgent_opponents)}张；这不是具体持牌事实。")

    engine = BaseRuleEngine()
    public_history = _validated_public_history(observation, state, engine)
    pass_evidence = public_history[0] if public_history is not None else ()
    if pass_evidence:
        lines.append(
            f"公开软线索={len(pass_evidence)}次可还原pass；只描述候选相关的历史持牌/让牌，"
            "不改变未见牌归属或当前硬牌域。"
        )
    profile_cache: dict[int, tuple[dict[str, object], ...]] = {}
    facts_cache: dict[int, _CandidateFacts] = {}
    comparisons = _candidate_pairs(
        list(legal_actions),
        my_counts,
        state=state,
        engine=engine,
        owner=owner,
        profile_cache=profile_cache,
        facts_cache=facts_cache,
        preferred_action_ids=preferred_action_ids,
        pass_evidence=pass_evidence,
        level=state.level,
    )
    relevant = relevant_public_passes(observation)
    if relevant:
        lines.insert(1, '历史软pass：' + ' '.join(_pass_behavior_text(item, state) for item in relevant[:3]))
        lines.insert(2, '应手取舍：队友少牌不证明能接；对手控桌时，本家低成本压制也可服务协同，比较其清牌/余组与让后对手续领代价，不默认支援=pass。')
    carried_pairs = (
        _relevant_public_carried_pairs(state, engine, public_history)
        if public_history is not None and owner is None and _has_public_pair_choice(legal_actions)
        else ()
    )
    if carried_pairs:
        index = 3 if relevant else 1
        lines.insert(index, '历史携带软线索：' + ' '.join(_carried_pair_behavior_text(item, state) for item in carried_pairs))
        lines.insert(index + 1, '对子取舍：先看逐家容量/可行应手与本家清牌、资源成本；行为不证仍有大对，不承诺送达或回手，末手pass/确证优先。')
    for first, second in comparisons:
        lines.append(_candidate_comparison_line(
            first, second, profile_cache, facts_cache,
            recommendation_anchored=(
                int(first["action_id"]) in preferred_action_ids
                or int(second["action_id"]) in preferred_action_ids
            ),
        ))
    if not comparisons and owner is not None:
        unique_line = _known_hand_response_line(
            state, list(legal_actions), my_counts, owner, profile_cache, facts_cache,
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
