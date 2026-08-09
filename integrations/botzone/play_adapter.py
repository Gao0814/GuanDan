"""Offline RuleBasedAI adapter for the Botzone no-tribute play subset."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.rule_based_ai import RuleBasedAIAgent
from engine.actions import Action, ActionType, public_action_id
from engine.cards import Card, card_to_token, sort_cards
from engine.patterns import PatternType, detect_pattern
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint

from .cards import BotzoneCard, card_from_id, card_id_for
from .models import ActionClaim, DealRequest, HistoryEntry, PlayRequest
from .profile import require_no_tribute_context
from .protocol import (
    ProtocolValidationError,
    botzone_player_to_engine_player,
    parse_action_claim,
    resolve_table_view,
)
from .session import HandlerContext, HandlerResult, PlayEffect


_BOTZONE_TO_ENGINE_SUIT = {"h": "H", "d": "D", "s": "S", "c": "C"}
_ENGINE_TO_BOTZONE_SUIT = {value: key for key, value in _BOTZONE_TO_ENGINE_SUIT.items()}
_VIRTUAL_SUIT_ORDER = ("h", "d", "s", "c")


class AdapterError(ValueError):
    """A public context cannot be safely projected into the supported subset."""


@dataclass(frozen=True, slots=True)
class DecisionProjection:
    observation: Mapping[str, object]
    legal_actions: tuple[Mapping[str, object], ...]
    provenance: Mapping[int, Action]
    table_view_free: bool


def botzone_card_to_engine(card: BotzoneCard) -> Card:
    if card.suit is None:
        return Card(rank=card.rank)
    return Card(rank=card.rank, suit=_BOTZONE_TO_ENGINE_SUIT[card.suit])


def botzone_id_to_engine_card(card_id: object) -> Card:
    return botzone_card_to_engine(card_from_id(card_id))


def team_for_engine_player(player_id: int) -> str:
    return "team_13" if player_id in {1, 3} else "team_24"


def project_decision(context: HandlerContext) -> DecisionProjection:
    request = require_no_tribute_context(context)
    _validate_context(context, request)
    if not isinstance(request, PlayRequest):
        raise AdapterError("deal_has_no_decision")
    if context.finished:
        raise AdapterError("finished_session")
    if context.local_player_id in request.done:
        raise AdapterError("local_player_finished")
    local_player_id = botzone_player_to_engine_player(context.local_player_id)
    own_hand = sort_cards(tuple(botzone_id_to_engine_card(card_id) for card_id in context.own_hand))
    if len(own_hand) != len(context.own_hand):
        raise AdapterError("invalid_hand")

    table_view = resolve_table_view(
        local_player_id=context.local_player_id,
        latest_window=context.latest_window,
        done=request.done,
        pass_on=request.pass_on,
    )
    leading_action: Action | None = None
    if not table_view.free_lead:
        assert table_view.table_leader is not None
        leading_action = _history_entry_to_action(table_view.table_leader, context.global_state.level)
    table_constraint = TableConstraint(
        leading_action=leading_action,
        leader_player_id=leading_action.player_id if leading_action is not None else None,
        pending_player_ids=(),
    )
    player = PlayerState(player_id=local_player_id, hand_cards=own_hand)
    replay = _replay_rounds(context.history)
    current_round = 1 if not replay else replay[-1][1] + (1 if table_view.free_lead else 0)
    state = GameState(
        players=(player,),
        current_player_id=local_player_id,
        current_level_rank=context.global_state.level,
        table_constraint=table_constraint,
        step_no=len(context.history),
        round_no=current_round,
        finish_order=tuple(botzone_player_to_engine_player(player_id) for player_id in request.done),
    )
    engine_actions = BaseRuleEngine().generate_legal_actions(state)
    if not engine_actions:
        raise AdapterError("no_legal_actions")
    provenance = MappingProxyType({public_action_id(index): action for index, action in enumerate(engine_actions)})
    if len(provenance) != len(engine_actions):
        raise AdapterError("action_id_collision")
    public_actions = tuple(_public_action(action, action_id) for action_id, action in provenance.items())
    observation = _public_observation(context, request, state, public_actions, leading_action, replay)
    return DecisionProjection(
        observation=MappingProxyType(observation),
        legal_actions=tuple(MappingProxyType(dict(action)) for action in public_actions),
        provenance=provenance,
        table_view_free=table_view.free_lead,
    )


class NoTributeRuleBasedHandler:
    """Connector callable using RuleBasedAI by default and no hidden game state."""

    def __init__(self, agent_factory: Callable[[int], object] | None = None) -> None:
        self._agent_factory = agent_factory or (lambda player_id: RuleBasedAIAgent(player_id=player_id))

    def __call__(self, context: HandlerContext) -> HandlerResult:
        request = require_no_tribute_context(context)
        _validate_context(context, request)
        if isinstance(request, DealRequest):
            return HandlerResult(b"[]")
        projection = project_decision(context)
        agent_actions = [dict(action) for action in projection.legal_actions]
        agent_observation = copy.deepcopy(dict(projection.observation))
        agent_observation["legal_actions"] = agent_actions
        agent = self._agent_factory(botzone_player_to_engine_player(context.local_player_id))
        try:
            selected = agent.select_action(agent_observation, agent_actions)
        except Exception as exc:
            raise AdapterError("agent_failure") from exc
        if type(selected) is not int:
            raise AdapterError("invalid_agent_action_id")
        canonical_actions = [dict(action) for action in projection.legal_actions]
        try:
            selected_id = require_legal_action_id(selected, canonical_actions)
        except (TypeError, ValueError) as exc:
            raise AdapterError("invalid_agent_action_id") from exc
        action = projection.provenance.get(selected_id)
        if action is None:
            raise AdapterError("missing_provenance")
        action_claim = encode_action_claim(action, context.own_hand, context.global_state.level)
        response = json.dumps(action_claim.to_json(), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return HandlerResult(response, PlayEffect(action_claim.action))


def encode_action_claim(action: Action, own_hand: Sequence[int], level: str) -> ActionClaim:
    """Bind a selected engine action to stable physical IDs and a safe claim."""

    if action.action_type == ActionType.PASS:
        return ActionClaim.pass_action()
    action_ids = _bind_carriers(action.carrier_cards, own_hand)
    if action.wildcard_count == 0:
        claim_ids = action_ids
    else:
        claim_ids = _encode_wildcard_claim(action, action_ids, own_hand)
    wire = [list(action_ids), list(claim_ids)]
    try:
        parsed = parse_action_claim(wire, level=level, known_hand_ids=own_hand)
    except ProtocolValidationError as exc:
        raise AdapterError("encoded_claim_invalid") from exc
    if _pattern_for_ids(parsed.claim) != action.declared_pattern:
        raise AdapterError("encoded_pattern_mismatch")
    return parsed


def _bind_carriers(carriers: Sequence[Card], own_hand: Sequence[int]) -> tuple[int, ...]:
    pools: dict[tuple[str, str | None], list[int]] = defaultdict(list)
    for card_id in sorted(own_hand):
        card = botzone_id_to_engine_card(card_id)
        pools[(card.rank, card.suit)].append(card_id)
    bound: list[int] = []
    for card in carriers:
        pool = pools[(card.rank, card.suit)]
        if not pool:
            raise AdapterError("carrier_not_in_hand")
        bound.append(pool.pop(0))
    if len(set(bound)) != len(bound):
        raise AdapterError("duplicate_carrier")
    return tuple(bound)


def _encode_wildcard_claim(action: Action, action_ids: tuple[int, ...], own_hand: Sequence[int]) -> tuple[int, ...]:
    wildcard_carriers = Counter((item.carrier_card.rank, item.carrier_card.suit) for item in action.wildcard_info)
    natural_by_key: dict[tuple[str, str | None], list[int]] = defaultdict(list)
    for card, card_id in zip(action.carrier_cards, action_ids):
        key = (card.rank, card.suit)
        if wildcard_carriers[key]:
            wildcard_carriers[key] -= 1
        else:
            natural_by_key[key].append(card_id)
    for ids in natural_by_key.values():
        ids.sort()

    claim: list[int | None] = []
    virtual_positions: list[int] = []
    for declared in action.declared_cards:
        candidates = natural_by_key[(declared.rank, declared.suit)]
        if not candidates and declared.suit is None:
            matching = [ids for (rank, _suit), ids in natural_by_key.items() if rank == declared.rank and ids]
            candidates = min(matching, key=lambda ids: ids[0]) if matching else []
        if candidates:
            claim.append(candidates.pop(0))
        else:
            claim.append(None)
            virtual_positions.append(len(claim) - 1)
    if len(virtual_positions) != action.wildcard_count:
        raise AdapterError("wildcard_claim_alignment_failed")

    for candidate_suits in _virtual_suit_assignments(action, claim, virtual_positions):
        candidate_claim = list(claim)
        for position, suit in zip(virtual_positions, candidate_suits):
            declared = action.declared_cards[position]
            if declared.rank in {"SJ", "BJ"}:
                raise AdapterError("wildcard_declares_joker")
            candidate_claim[position] = card_id_for(declared.rank, suit, 0)
        resolved = tuple(card_id for card_id in candidate_claim if card_id is not None)
        if len(resolved) == len(claim) and _pattern_for_ids(resolved) == action.declared_pattern:
            return resolved
    raise AdapterError("wildcard_claim_pattern_failed")


def _virtual_suit_assignments(action: Action, claim: Sequence[int | None], positions: Sequence[int]) -> tuple[tuple[str, ...], ...]:
    if not positions:
        return ((),)
    # The current engine supports exactly one wildcard; retain a tuple API so
    # the boundary remains explicit if that engine contract changes later.
    if len(positions) != 1:
        return ()
    return tuple((suit,) for suit in _VIRTUAL_SUIT_ORDER)


def _history_entry_to_action(entry: HistoryEntry, level: str) -> Action:
    if entry.response.is_pass:
        return Action.make_pass(botzone_player_to_engine_player(entry.player_id))
    try:
        parsed = parse_action_claim(
            [list(entry.response.action), list(entry.response.claim)],
            level=level,
        )
    except ProtocolValidationError as exc:
        raise AdapterError("invalid_table_action") from exc
    carrier_cards = sort_cards(tuple(botzone_id_to_engine_card(card_id) for card_id in parsed.action))
    raw_declared = sort_cards(tuple(botzone_id_to_engine_card(card_id) for card_id in parsed.claim))
    pattern = detect_pattern(raw_declared)
    if pattern.type in {PatternType.UNKNOWN, PatternType.PASS}:
        raise AdapterError("unsupported_table_action")
    declared_cards = _canonical_declared_cards(raw_declared, pattern.type)
    wildcard_info = _rebuild_wildcard_info(carrier_cards, raw_declared, level, pattern.type)
    return Action(
        player_id=botzone_player_to_engine_player(entry.player_id),
        action_type=ActionType.PLAY,
        declared_pattern=pattern.type,
        declared_cards=declared_cards,
        carrier_cards=carrier_cards,
        wildcard_count=len(wildcard_info),
        wildcard_info=wildcard_info,
        display_text=_display_text(pattern.type, declared_cards),
    )


def _pattern_for_ids(card_ids: Sequence[int]) -> PatternType | None:
    if not card_ids:
        return None
    return detect_pattern(tuple(botzone_id_to_engine_card(card_id) for card_id in card_ids)).type


def _public_action(action: Action, action_id: int | None) -> dict[str, object]:
    pattern = action.declared_pattern.value if action.declared_pattern is not None else "pass"
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [_declared_token(card) for card in action.declared_cards],
        "carrier_cards": [card_to_token(card) for card in action.carrier_cards],
        "wildcard_count": action.wildcard_count,
        "wildcard_info": [
            {"carrier_card": card_to_token(item.carrier_card), "declared_as": _declared_token(item.declared_as)}
            for item in action.wildcard_info
        ],
        "display_text": action.display_text if action.display_text else pattern,
    }


def _declared_token(card: Card) -> str:
    return card.rank if card.suit is None else card_to_token(card)


def _public_observation(
    context: HandlerContext,
    request: PlayRequest,
    state: GameState,
    legal_actions: Sequence[Mapping[str, object]],
    leading_action: Action | None,
    replay: Sequence[tuple[HistoryEntry, int]],
) -> dict[str, object]:
    local = state.current_player_id
    played_counts = Counter(entry.player_id for entry in context.history for _ in entry.response.action)
    other_players: list[dict[str, object]] = []
    for botzone_player in range(4):
        engine_player = botzone_player_to_engine_player(botzone_player)
        if engine_player == local:
            continue
        finished = botzone_player in request.done
        count = 27 - played_counts[botzone_player]
        if count < 0 or (finished and count != 0):
            raise AdapterError("public_count_inconsistent")
        other_players.append(
            {
                "player_id": engine_player,
                "team": team_for_engine_player(engine_player),
                "hand_count": count,
                "finished": finished,
                "finish_rank": (request.done.index(botzone_player) + 1) if finished else None,
            }
        )
    history_actions: list[dict[str, object]] = []
    for index, (entry, round_no) in enumerate(replay, start=1):
        action = _history_entry_to_action(entry, context.global_state.level)
        history_actions.append(
            {
                "step_no": index,
                "round_no": round_no,
                "player_id": action.player_id,
                "declared_pattern": action.declared_pattern.value if action.declared_pattern is not None else "pass",
                "declared_cards": [_declared_token(card) for card in action.declared_cards],
                "carrier_cards": [card_to_token(card) for card in action.carrier_cards],
            }
        )
    hand_counts = Counter(card.rank for card in state.get_player(local).hand_cards)
    return {
        "my_info": {
            "player_id": local,
            "team": team_for_engine_player(local),
            "current_level_rank": context.global_state.level,
            "hand_cards": [card_to_token(card) for card in state.get_player(local).hand_cards],
            "hand_count": len(state.get_player(local).hand_cards),
            "remaining_single_card_count": sum(1 for card in state.get_player(local).hand_cards if hand_counts[card.rank] == 1),
        },
        "current_round": {
            "step_no": state.step_no,
            "round_no": state.round_no,
            "current_player_id": local,
            "current_level_rank": context.global_state.level,
            "table_action": _public_action(leading_action, None) if leading_action is not None else None,
            "constraint": "free" if leading_action is None else leading_action.display_text,
        },
        "other_players": other_players,
        "history": {"actions": history_actions, "finish_order": list(state.finish_order)},
        "legal_actions": [dict(action) for action in legal_actions],
    }


def _canonical_declared_cards(cards: Sequence[Card], pattern: PatternType) -> tuple[Card, ...]:
    if pattern == PatternType.STRAIGHT_FLUSH:
        return sort_cards(tuple(cards))
    return sort_cards(tuple(Card(rank=card.rank) for card in cards))


def _rebuild_wildcard_info(
    carrier_cards: Sequence[Card],
    declared_cards: Sequence[Card],
    level: str,
    pattern: PatternType,
) -> tuple[object, ...]:
    from engine.actions import WildcardInfo

    wildcards = tuple(card for card in carrier_cards if card.rank == level and card.suit == "H")
    if not wildcards:
        return ()
    natural_faces = Counter((card.rank, card.suit) for card in carrier_cards if card not in wildcards)
    declared_faces = Counter((card.rank, card.suit) for card in declared_cards)
    if any(declared_faces[face] < count for face, count in natural_faces.items()):
        raise AdapterError("wildcard_claim_alignment_failed")
    declared_faces.subtract(natural_faces)
    remainders = [
        Card(rank=rank, suit=suit if pattern == PatternType.STRAIGHT_FLUSH else None)
        for (rank, suit), count in declared_faces.items()
        for _ in range(count)
        if count > 0
    ]
    if len(remainders) != len(wildcards) or any(card.rank in {"SJ", "BJ"} for card in remainders):
        raise AdapterError("wildcard_claim_alignment_failed")
    return tuple(WildcardInfo(carrier_card=carrier, declared_as=declared) for carrier, declared in zip(wildcards, remainders))


def _display_text(pattern: PatternType, cards: Sequence[Card]) -> str:
    return f"{pattern.value}:{','.join(_declared_token(card) for card in cards)}"


def _is_free_before(events: Sequence[HistoryEntry], player_id: int) -> bool:
    for entry in reversed(events[-4:]):
        if entry.player_id == player_id:
            break
        if not entry.response.is_pass:
            return False
    return True


def _replay_rounds(history: Sequence[HistoryEntry]) -> tuple[tuple[HistoryEntry, int], ...]:
    replayed: list[tuple[HistoryEntry, int]] = []
    round_no = 0
    for entry in history:
        free = _is_free_before(tuple(item for item, _round in replayed), entry.player_id)
        if entry.response.is_pass and free:
            raise AdapterError("invalid_history_pass")
        if free:
            round_no += 1
        if round_no == 0:
            raise AdapterError("invalid_history_round")
        replayed.append((entry, round_no))
    return tuple(replayed)


def _validate_context(context: HandlerContext, request: DealRequest | PlayRequest) -> None:
    if context.global_state != request.global_state:
        raise AdapterError("context_global_mismatch")
    if type(context.local_player_id) is not int or not 0 <= context.local_player_id <= 3:
        raise AdapterError("context_local_player_invalid")
    if (
        any(type(card_id) is not int or not 0 <= card_id <= 107 for card_id in context.own_hand)
        or len(set(context.own_hand)) != len(context.own_hand)
    ):
        raise AdapterError("context_hand_invalid")
    if isinstance(request, DealRequest):
        if context.local_player_id != request.your_id:
            raise AdapterError("context_local_player_mismatch")
        return
    if context.latest_window != request.history:
        raise AdapterError("context_latest_window_mismatch")
    if bool(context.history) != bool(context.latest_window):
        raise AdapterError("context_history_mismatch")
    if len(context.latest_window) > len(context.history) or (
        context.latest_window and context.history[-len(context.latest_window):] != context.latest_window
    ):
        raise AdapterError("context_history_mismatch")
    if context.finished or context.local_player_id in request.done:
        raise AdapterError("context_finished_mismatch")
    seen: dict[int, int] = {}
    played_by_player: Counter[int] = Counter()
    for entry in context.history:
        for card_id in entry.response.action:
            if card_id in seen:
                raise AdapterError("duplicate_public_entity")
            seen[card_id] = entry.player_id
            played_by_player[entry.player_id] += 1
    if set(context.own_hand) & set(seen):
        raise AdapterError("own_hand_contains_played_entity")
    if len(context.own_hand) + played_by_player[context.local_player_id] != 27:
        raise AdapterError("local_hand_conservation_failed")
    for player_id in range(4):
        remaining = 27 - played_by_player[player_id]
        if not 0 <= remaining <= 27:
            raise AdapterError("public_capacity_invalid")
        if player_id in request.done and remaining != 0:
            raise AdapterError("done_capacity_invalid")
        if player_id not in request.done and remaining == 0:
            raise AdapterError("unfinished_zero_capacity")
