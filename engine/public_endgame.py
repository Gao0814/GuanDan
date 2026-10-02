"""Bounded perfect-information search from a fully public, validated position.

This module is an engine-side simulation boundary. Callers provide only an
observation, its canonical legal actions, and an explicit public hand
assignment. The assignment is checked against the complete 108-card ledger
before any rule-engine state is constructed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic
from typing import Mapping, Sequence

from .actions import Action, ActionType
from .cards import (
    BIG_JOKER_RANK,
    SMALL_JOKER_RANK,
    Card,
    build_double_deck,
    card_to_token,
    sort_cards,
)
from .game import GuanDanGame, _action_to_public_dict
from .patterns import PatternType, detect_pattern
from .rules import BaseRuleEngine
from .state import GameState, HistoryEntry, PlayerState, TableConstraint


PUBLIC_ENDGAME_MAX_NODES = 5_000
PUBLIC_ENDGAME_MAX_SECONDS = 0.035
PUBLIC_ENDGAME_MAX_CARDS = 12
PUBLIC_ENDGAME_MAX_HAND = 8

_NORMAL_RANKS = frozenset(
    {"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"}
)
_SUITS = frozenset({"S", "H", "C", "D"})
_JOKERS = frozenset({SMALL_JOKER_RANK, BIG_JOKER_RANK})


@dataclass(frozen=True, slots=True)
class PublicEndgameAnalysis:
    """Exact root profiles, a completed winning-root proof, or a fail-closed reason."""

    status: str
    action_values: tuple[tuple[int, int], ...] = ()
    action_reachable_values: tuple[tuple[int, tuple[int, ...]], ...] = ()
    best_action_ids: tuple[int, ...] = ()
    unique_best_action_id: int | None = None
    nodes: int = 0
    elapsed_seconds: float = 0.0
    reason: str = ""
    proven_action_id: int | None = None


class _SearchBudgetExceeded(Exception):
    pass


class _InvalidPosition(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _SearchProfile:
    guaranteed_value: int
    reachable_values: tuple[int, ...]


@dataclass(slots=True)
class _SearchContext:
    deadline: float
    max_nodes: int
    nodes: int = 0
    cache: dict[tuple[object, ...], _SearchProfile] = field(default_factory=dict)
    legal_cache: dict[
        tuple[object, ...], tuple[tuple[int, Action], ...]
    ] = field(default_factory=dict)


def _card_from_token(value: object, *, declared: bool = False) -> Card:
    if not isinstance(value, str):
        raise _InvalidPosition
    if value in _JOKERS:
        return Card(value)
    if value in _NORMAL_RANKS and declared:
        return Card(value)
    if len(value) >= 2 and value[-1] in _SUITS and value[:-1] in _NORMAL_RANKS:
        return Card(value[:-1], value[-1])
    raise _InvalidPosition


def _action_from_public(raw: object, player_id: int, level: str) -> Action:
    if not isinstance(raw, dict):
        raise _InvalidPosition
    pattern_value = raw.get("declared_pattern")
    if pattern_value == "pass":
        carriers = raw.get("carrier_cards", [])
        declared = raw.get("declared_cards", [])
        if carriers not in ([], ()) or declared not in ([], ()):
            raise _InvalidPosition
        return Action.make_pass(player_id)
    if not isinstance(pattern_value, str):
        raise _InvalidPosition
    try:
        pattern = PatternType(pattern_value)
    except ValueError as exc:
        raise _InvalidPosition from exc
    if pattern in {PatternType.PASS, PatternType.UNKNOWN}:
        raise _InvalidPosition
    declared_raw = raw.get("declared_cards")
    carrier_raw = raw.get("carrier_cards")
    if not isinstance(declared_raw, (list, tuple)) or not isinstance(carrier_raw, (list, tuple)):
        raise _InvalidPosition
    declared = tuple(_card_from_token(token, declared=True) for token in declared_raw)
    carriers = tuple(_card_from_token(token) for token in carrier_raw)
    metadata_count_present = "wildcard_count" in raw
    metadata_info_present = "wildcard_info" in raw
    if metadata_count_present != metadata_info_present:
        raise _InvalidPosition
    wildcard_token = f"{level}H"
    if (
        not metadata_count_present
        and all(card_to_token(card) != wildcard_token for card in carriers)
    ):
        if detect_pattern(declared).type != pattern:
            raise _InvalidPosition
        face_key = lambda card: (
            card.rank,
            card.suit if pattern == PatternType.STRAIGHT_FLUSH else None,
        )
        if Counter(map(face_key, declared)) != Counter(map(face_key, carriers)):
            raise _InvalidPosition
        binding = Action(
            player_id=player_id,
            action_type=ActionType.PLAY,
            declared_pattern=pattern,
            declared_cards=declared,
            carrier_cards=carriers,
            display_text=str(raw.get("display_text", pattern_value)),
        )
        return binding
    bindings = BaseRuleEngine().public_action_bindings(
        player_id,
        pattern,
        declared,
        carriers,
        level,
        first_carrier_only=not metadata_count_present,
        first_binding_only=not metadata_count_present,
    )
    if not bindings:
        raise _InvalidPosition
    if metadata_count_present:
        wildcard_count = raw.get("wildcard_count")
        wildcard_raw = raw.get("wildcard_info")
        if (
            type(wildcard_count) is not int or not 0 <= wildcard_count <= 2
            or not isinstance(wildcard_raw, (list, tuple))
        ):
            raise _InvalidPosition
        supplied_info = []
        for item in wildcard_raw:
            if not isinstance(item, dict):
                raise _InvalidPosition
            supplied_info.append((
                _card_from_token(item.get("carrier_card")),
                _card_from_token(item.get("declared_as"), declared=True),
            ))
        binding = next((
            candidate for candidate in bindings
            if candidate.wildcard_count == wildcard_count
            and tuple((item.carrier_card, item.declared_as) for item in candidate.wildcard_info)
            == tuple(supplied_info)
        ), None)
        if binding is None:
            raise _InvalidPosition
    else:
        # Observation history intentionally carries only canonical pattern,
        # claim and physical carriers. Reconstruct an accepted binding through
        # the engine rather than treating those carriers as an ordinary natural
        # action or duplicating wildcard legality here.
        binding = bindings[0]
    return Action(
        player_id=player_id,
        action_type=ActionType.PLAY,
        declared_pattern=pattern,
        declared_cards=declared,
        carrier_cards=carriers,
        wildcard_count=binding.wildcard_count,
        wildcard_info=binding.wildcard_info,
        display_text=str(raw.get("display_text", pattern_value)),
    )


def _action_signature(raw: object) -> tuple[object, ...]:
    if not isinstance(raw, dict):
        raise _InvalidPosition
    return (
        raw.get("declared_pattern"),
        tuple(raw.get("declared_cards", ())) if isinstance(raw.get("declared_cards", ()), (list, tuple)) else None,
        tuple(raw.get("carrier_cards", ())) if isinstance(raw.get("carrier_cards", ()), (list, tuple)) else None,
        raw.get("wildcard_count", 0),
        tuple(
            (item.get("carrier_card"), item.get("declared_as"))
            for item in raw.get("wildcard_info", ())
            if isinstance(item, dict)
        ) if isinstance(raw.get("wildcard_info", ()), (list, tuple)) else None,
    )


def _clockwise_after(player_id: int, active_ids: set[int]) -> tuple[int, ...]:
    ordered = []
    for offset in range(1, 5):
        candidate = ((player_id + offset - 1) % 4) + 1
        if candidate in active_ids and candidate != player_id:
            ordered.append(candidate)
    return tuple(ordered)


def _rebuild_public_game(
    observation: object,
    legal_actions: object,
    hands_by_player: object,
    *,
    deadline: float,
    max_cards: int,
    max_hand: int,
) -> GuanDanGame:
    """Shared rule reconstruction, with no inference or proof semantics.

    M9 supplies its fixed small-position limits through _build_public_game;
    the separate finite simulation API supplies hypothetical current hands.
    """
    if not isinstance(observation, dict) or not isinstance(legal_actions, list):
        raise _InvalidPosition
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    other_players = observation.get("other_players")
    history = observation.get("history")
    if not all(isinstance(item, dict) for item in (my_info, current_round, history)):
        raise _InvalidPosition
    if not isinstance(other_players, list) or not isinstance(history, dict):
        raise _InvalidPosition
    assert isinstance(my_info, dict) and isinstance(current_round, dict)
    player_id = my_info.get("player_id")
    level = current_round.get("current_level_rank")
    if type(player_id) is not int or player_id not in {1, 2, 3, 4}:
        raise _InvalidPosition
    if not isinstance(level, str) or level not in _NORMAL_RANKS:
        raise _InvalidPosition
    if current_round.get("current_player_id") != player_id:
        raise _InvalidPosition

    raw_hand = my_info.get("hand_cards")
    if not isinstance(raw_hand, list) or my_info.get("hand_count") != len(raw_hand):
        raise _InvalidPosition
    rows: dict[int, dict[str, object]] = {
        player_id: {
            "player_id": player_id,
            "team": my_info.get("team"),
            "hand_count": len(raw_hand),
            "finished": False,
        }
    }
    for raw_player in other_players:
        if not isinstance(raw_player, dict):
            raise _InvalidPosition
        other_id = raw_player.get("player_id")
        count = raw_player.get("hand_count")
        finished = raw_player.get("finished")
        team = raw_player.get("team")
        if (
            type(other_id) is not int or other_id not in {1, 2, 3, 4}
            or other_id in rows or type(count) is not int or count < 0
            or type(finished) is not bool or finished != (count == 0)
            or not isinstance(team, str)
        ):
            raise _InvalidPosition
        rows[other_id] = raw_player
    if set(rows) != {1, 2, 3, 4}:
        raise _InvalidPosition
    teams = [str(row.get("team", "")) for row in rows.values()]
    if set(teams) != {"team_13", "team_24"} or any(teams.count(team) != 2 for team in set(teams)):
        raise _InvalidPosition

    raw_finish_order = history.get("finish_order")
    raw_history = history.get("actions")
    step_no = current_round.get("step_no")
    round_no = current_round.get("round_no")
    if (
        not isinstance(raw_finish_order, list) or not isinstance(raw_history, list)
        or type(step_no) is not int or step_no != len(raw_history)
        or type(round_no) is not int or round_no < 1
        or len(raw_finish_order) > 2
        or any(type(item) is not int or item not in rows for item in raw_finish_order)
        or len(set(raw_finish_order)) != len(raw_finish_order)
    ):
        raise _InvalidPosition
    finish_order = tuple(raw_finish_order)
    if (
        len(finish_order) == 2
        and rows[finish_order[0]].get("team") == rows[finish_order[1]].get("team")
    ):
        # A same-team top two is terminal.  It has no legal continuation for
        # the endgame search, even though the remaining hands are still hidden.
        raise _InvalidPosition
    finished_ids = set(finish_order)
    if {key for key, row in rows.items() if bool(row.get("finished"))} != finished_ids:
        raise _InvalidPosition

    supplied_hands = hands_by_player
    if not isinstance(supplied_hands, Mapping) or set(supplied_hands) != {1, 2, 3, 4}:
        raise _InvalidPosition
    current_hands: dict[int, tuple[Card, ...]] = {}
    played_by_player: Counter[int] = Counter()
    full_deck_counts = Counter(card_to_token(card) for card in build_double_deck())
    known_pool: Counter[str] = Counter()
    history_entries: list[HistoryEntry] = []
    previous_round = 0
    for index, raw_action in enumerate(raw_history):
        if monotonic() > deadline:
            raise _SearchBudgetExceeded
        if not isinstance(raw_action, dict):
            raise _InvalidPosition
        raw_step = raw_action.get("step_no")
        raw_round = raw_action.get("round_no")
        history_player = raw_action.get("player_id")
        if (
            type(raw_step) is not int or raw_step != index + 1
            or type(raw_round) is not int or raw_round < 1
            or raw_round < previous_round or raw_round > previous_round + 1
            or type(history_player) is not int or history_player not in rows
        ):
            raise _InvalidPosition
        previous_round = raw_round
        action = _action_from_public(raw_action, history_player, level)
        history_entries.append(
            HistoryEntry(step_no=raw_step, round_no=raw_round, player_id=history_player, action=action)
        )
        if action.action_type == ActionType.PLAY:
            played_by_player[history_player] += len(action.carrier_cards)
            known_pool.update(card_to_token(card) for card in action.carrier_cards)

    if raw_history and round_no not in {previous_round, previous_round + 1}:
        raise _InvalidPosition

    for owner_id in (1, 2, 3, 4):
        raw_cards = supplied_hands[owner_id]
        if not isinstance(raw_cards, (list, tuple)):
            raise _InvalidPosition
        cards = tuple(sort_cards(tuple(_card_from_token(token) for token in raw_cards)))
        if len(cards) != int(rows[owner_id].get("hand_count", -1)):
            raise _InvalidPosition
        if bool(rows[owner_id].get("finished")) != (len(cards) == 0):
            raise _InvalidPosition
        if len(cards) + played_by_player[owner_id] != 27:
            raise _InvalidPosition
        current_hands[owner_id] = cards
        known_pool.update(card_to_token(card) for card in cards)
    if known_pool != full_deck_counts:
        raise _InvalidPosition
    if tuple(card_to_token(card) for card in current_hands[player_id]) != tuple(raw_hand):
        # Card sorting must not silently reinterpret the caller's own public hand.
        if Counter(card_to_token(card) for card in current_hands[player_id]) != Counter(raw_hand):
            raise _InvalidPosition

    active_ids = {owner for owner, hand in current_hands.items() if hand}
    if len(active_ids) < 2 or player_id not in active_ids:
        raise _InvalidPosition
    active_card_count = sum(len(current_hands[owner]) for owner in active_ids)
    if active_card_count > max_cards or any(
        len(current_hands[owner]) > max_hand for owner in active_ids
    ):
        raise _InvalidPosition

    rows_by_finish = {owner: index + 1 for index, owner in enumerate(finish_order)}
    players = tuple(
        PlayerState(
            player_id=owner,
            hand_cards=current_hands[owner],
            finish_rank=rows_by_finish.get(owner),
        )
        for owner in (1, 2, 3, 4)
    )

    table_action_raw = current_round.get("table_action")
    table_constraint = TableConstraint()
    if table_action_raw is not None:
        lead_index = next(
            (
                index for index in range(len(raw_history) - 1, -1, -1)
                if raw_history[index].get("round_no") == round_no
                and raw_history[index].get("declared_pattern") != "pass"
            ),
            None,
        )
        if lead_index is None:
            raise _InvalidPosition
        lead_raw = raw_history[lead_index]
        leader_id = int(lead_raw["player_id"])
        lead_action = _action_from_public(table_action_raw, leader_id, level)
        if _action_signature(table_action_raw)[:3] != _action_signature(lead_raw)[:3]:
            raise _InvalidPosition
        if (
            lead_action.action_type != ActionType.PLAY
            or lead_action.declared_pattern is None
            or _action_to_public_dict(lead_action)["declared_pattern"] != lead_raw.get("declared_pattern")
        ):
            raise _InvalidPosition
        passed_ids: set[int] = set()
        for raw_after in raw_history[lead_index + 1:]:
            if raw_after.get("round_no") != round_no or raw_after.get("declared_pattern") != "pass":
                raise _InvalidPosition
            passed_ids.add(int(raw_after["player_id"]))
        responder_order = _clockwise_after(leader_id, active_ids)
        if not passed_ids.issubset(set(responder_order)):
            raise _InvalidPosition
        pending = tuple(owner for owner in responder_order if owner not in passed_ids)
        if not pending or pending[0] != player_id:
            raise _InvalidPosition
        table_constraint = TableConstraint(
            leading_action=lead_action,
            leader_player_id=leader_id,
            pending_player_ids=pending,
        )
    elif not raw_history and step_no != 0:
        raise _InvalidPosition

    game = GuanDanGame(current_level_rank=level)
    game._state = GameState(
        players=players,
        current_player_id=player_id,
        current_level_rank=level,
        table_constraint=table_constraint,
        step_no=step_no,
        round_no=round_no,
        finish_order=finish_order,
        history=tuple(history_entries),
    )
    game._invalidate_legal_actions_cache()
    generated_actions = game.legal_actions()
    if generated_actions != legal_actions:
        raise _InvalidPosition
    observation_actions = observation.get("legal_actions")
    if isinstance(observation_actions, list) and generated_actions != observation_actions:
        raise _InvalidPosition
    return game


def _build_public_game(observation: object, legal_actions: object,
                       known_hands_by_player: object, *, deadline: float) -> GuanDanGame:
    """M9's unchanged confirmed-position size boundary."""
    return _rebuild_public_game(
        observation, legal_actions, known_hands_by_player, deadline=deadline,
        max_cards=PUBLIC_ENDGAME_MAX_CARDS, max_hand=PUBLIC_ENDGAME_MAX_HAND,
    )


def _copy_game(game: GuanDanGame) -> GuanDanGame:
    clone = GuanDanGame(current_level_rank=game._current_level_rank)
    clone._state = game._require_state()
    # The parent already generated these actions for this exact immutable
    # state. step() validates against that same cache; its invalidation replaces
    # the containers rather than mutating them, so siblings remain isolated.
    if game._legal_actions_state is clone._state:
        clone._legal_actions_state = game._legal_actions_state
        clone._legal_action_map = game._legal_action_map
        clone._ordered_legal_actions = game._ordered_legal_actions
    return clone


def _terminal_value(game: GuanDanGame, root_team: str) -> int:
    winner = game._require_state().winner
    if winner == "draw":
        return 0
    if winner == root_team:
        return 1
    if winner in {"team_13", "team_24"}:
        return -1
    raise _InvalidPosition


def _position_key(game: GuanDanGame) -> tuple[object, ...]:
    state = game._require_state()
    # Step/round counters and history do not affect future legal transitions or
    # terminal ranking. Omitting them lets equivalent continuations reached by
    # different action orders share an exact search result.
    return (
        state.players,
        state.current_player_id,
        state.current_level_rank,
        state.table_constraint,
        state.finish_order,
        state.is_finished,
        state.winner,
    )


def _search_action_ids(game: GuanDanGame, context: _SearchContext) -> tuple[int, ...]:
    """Reuse complete rule generation within this one confirmed search.

    Pending responders, history and ranks of other players affect transitions,
    but not this player's generated actions. Keep the complete player, level
    and exact leading Action (including carrier/suit/wildcard declaration).
    The original step still validates and advances each branch.
    """
    state = game._require_state()
    key = (
        state.get_player(state.current_player_id),
        state.current_level_rank,
        state.table_constraint.leading_action,
    )
    ordered = context.legal_cache.get(key)
    if ordered is None:
        ordered = game._build_action_cache(state)
        # At most one entry per visited node plus the root; no cross-call cache.
        if len(context.legal_cache) <= context.max_nodes:
            context.legal_cache[key] = ordered
    else:
        game._legal_actions_state = state
        game._ordered_legal_actions = ordered
        game._legal_action_map = dict(ordered)
    return tuple(action_id for action_id, _ in ordered)


def _search_profile(
    game: GuanDanGame,
    root_team: str,
    context: _SearchContext,
) -> _SearchProfile:
    if monotonic() > context.deadline:
        raise _SearchBudgetExceeded
    state = game._require_state()
    if state.is_finished:
        value = _terminal_value(game, root_team)
        return _SearchProfile(value, (value,))

    key = _position_key(game)
    cached = context.cache.get(key)
    if cached is not None:
        return cached
    if context.nodes >= context.max_nodes:
        raise _SearchBudgetExceeded
    context.nodes += 1
    current_team = "team_13" if state.current_player_id in {1, 3} else "team_24"
    maximizing = current_team == root_team
    actions = _search_action_ids(game, context)
    if not actions:
        raise _InvalidPosition
    child_profiles: list[_SearchProfile] = []
    reachable_values: set[int] = set()
    for action_id in actions:
        if monotonic() > context.deadline:
            raise _SearchBudgetExceeded
        child = _copy_game(game)
        result = child.step(action_id)
        if bool(result["game_over"]):
            value = _terminal_value(child, root_team)
            profile = _SearchProfile(value, (value,))
        else:
            profile = _search_profile(child, root_team, context)
        child_profiles.append(profile)
        reachable_values.update(profile.reachable_values)

    guarantees = [profile.guaranteed_value for profile in child_profiles]
    guaranteed_value = max(guarantees) if maximizing else min(guarantees)
    result = _SearchProfile(guaranteed_value, tuple(sorted(reachable_values)))
    context.cache[key] = result
    return result


def analyze_public_endgame(
    observation: object,
    legal_actions: object,
    known_hands_by_player: object,
    *,
    max_nodes: int = PUBLIC_ENDGAME_MAX_NODES,
    max_seconds: float = PUBLIC_ENDGAME_MAX_SECONDS,
) -> PublicEndgameAnalysis:
    """Search an exact public position using the real ``GuanDanGame.step``.

    Any ambiguity, inconsistent ledger, or exhausted budget returns without
    partial values. The API never accepts a hidden ``GameState`` from agents.
    """
    if type(max_nodes) is not int or max_nodes <= 0:
        raise ValueError("max_nodes must be a positive integer")
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)):
        raise ValueError("max_seconds must be finite and positive")
    if not isfinite(float(max_seconds)) or max_seconds <= 0:
        raise ValueError("max_seconds must be finite and positive")
    max_nodes = min(max_nodes, PUBLIC_ENDGAME_MAX_NODES)
    max_seconds = min(float(max_seconds), PUBLIC_ENDGAME_MAX_SECONDS)
    started = monotonic()
    deadline = started + max_seconds
    context = _SearchContext(deadline=deadline, max_nodes=max_nodes)
    try:
        game = _build_public_game(
            observation,
            legal_actions,
            known_hands_by_player,
            deadline=deadline,
        )
        state = game._require_state()
        root_player_id = state.current_player_id
        root_team = "team_13" if root_player_id in {1, 3} else "team_24"
        values: list[tuple[int, int]] = []
        reachable_values: list[tuple[int, tuple[int, ...]]] = []
        for action_id in _search_action_ids(game, context):
            if monotonic() > context.deadline:
                raise _SearchBudgetExceeded
            branch = _copy_game(game)
            result = branch.step(action_id)
            if bool(result["game_over"]):
                value = _terminal_value(branch, root_team)
                profile = _SearchProfile(value, (value,))
            else:
                profile = _search_profile(branch, root_team, context)
            if profile.guaranteed_value == 1:
                # _search_profile only returns after every legal continuation
                # below this root action has been evaluated. A completed proof
                # for this route cannot be invalidated by another root move.
                return PublicEndgameAnalysis(
                    status="proven_win",
                    proven_action_id=action_id,
                    nodes=context.nodes,
                    elapsed_seconds=monotonic() - started,
                )
            values.append((action_id, profile.guaranteed_value))
            reachable_values.append((action_id, profile.reachable_values))
        best = max(value for _, value in values)
        best_ids = tuple(action_id for action_id, value in values if value == best)
        return PublicEndgameAnalysis(
            status="solved",
            action_values=tuple(values),
            action_reachable_values=tuple(reachable_values),
            best_action_ids=best_ids,
            unique_best_action_id=best_ids[0] if len(best_ids) == 1 else None,
            nodes=context.nodes,
            elapsed_seconds=monotonic() - started,
        )
    except _SearchBudgetExceeded:
        return PublicEndgameAnalysis(
            status="budget_exceeded",
            nodes=context.nodes,
            elapsed_seconds=monotonic() - started,
            reason="search_limit",
        )
    except (
        AttributeError,
        IndexError,
        KeyError,
        OverflowError,
        TypeError,
        ValueError,
        _InvalidPosition,
    ):
        return PublicEndgameAnalysis(
            status="ineligible",
            nodes=context.nodes,
            elapsed_seconds=monotonic() - started,
            reason="public_position_unverified",
        )
