"""Rule engine interfaces for phase-1.

Concrete rule logic is intentionally deferred beyond Step 1 skeleton setup.
"""

from itertools import combinations
from collections import Counter
from dataclasses import replace
from typing import Protocol

from .actions import Action, ActionType
from .cards import Card
from .patterns import Pattern, PatternType, detect_pattern
from .state import GameState, TableConstraint


_RANK_STRENGTH: dict[str, int] = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


def _action_strength(action: Action) -> int:
    if action.action_type != ActionType.PLAY or not action.cards:
        return -1
    # Step 3 subset uses identical-rank sets for pair/triple/bomb.
    return _RANK_STRENGTH.get(action.cards[0].rank, -1)


def _supported_play_patterns() -> set[PatternType]:
    return {
        PatternType.SINGLE,
        PatternType.PAIR,
        PatternType.TRIPLE,
        PatternType.BOMB,
    }


def _next_player_id(state: GameState, player_id: int) -> int:
    player_ids = [player.player_id for player in state.players]
    if player_id not in player_ids:
        raise ValueError(f"current player id not found in players: {player_id}")
    idx = player_ids.index(player_id)
    return player_ids[(idx + 1) % len(player_ids)]


def _cards_subset_of_hand(cards: tuple[Card, ...], hand_cards: tuple[Card, ...]) -> bool:
    need = Counter(cards)
    have = Counter(hand_cards)
    for card, count in need.items():
        if have[card] < count:
            return False
    return True


def _table_action_is_self_consistent(table_action: Action) -> bool:
    if table_action.action_type != ActionType.PLAY:
        return False
    if table_action.declared_pattern not in _supported_play_patterns():
        return False
    detected = detect_pattern(table_action.cards)
    return detected.type == table_action.declared_pattern


def _action_dedupe_key(action: Action) -> tuple[str, str, tuple[str, ...]]:
    declared = action.declared_pattern.value if action.declared_pattern is not None else "none"
    ranks = tuple(sorted(card.rank for card in action.cards))
    return action.action_type.value, declared, ranks


def _build_supported_play_actions(player_id: int, hand_cards: tuple[Card, ...]) -> tuple[Action, ...]:
    candidates: list[Action] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    for size in (1, 2, 3, 4):
        for combo in combinations(hand_cards, size):
            pattern = detect_pattern(combo)
            if pattern.type not in _supported_play_patterns():
                continue

            action = Action(
                player_id=player_id,
                action_type=ActionType.PLAY,
                cards=combo,
                declared_pattern=pattern.type,
            )
            key = _action_dedupe_key(action)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(action)

    return tuple(candidates)


def _filter_follow_actions(
    all_play_actions: tuple[Action, ...],
    table_action: Action,
) -> tuple[Action, ...]:
    table_pattern = table_action.declared_pattern
    if table_pattern not in {
        PatternType.SINGLE,
        PatternType.PAIR,
        PatternType.TRIPLE,
        PatternType.BOMB,
    }:
        return ()

    table_strength = _action_strength(table_action)
    filtered: list[Action] = []

    for action in all_play_actions:
        action_pattern = action.declared_pattern
        if action_pattern is None:
            continue

        if table_pattern in {PatternType.SINGLE, PatternType.PAIR, PatternType.TRIPLE}:
            if action_pattern == table_pattern and _action_strength(action) > table_strength:
                filtered.append(action)
                continue
            if action_pattern == PatternType.BOMB:
                filtered.append(action)
                continue

        if table_pattern == PatternType.BOMB:
            if action_pattern == PatternType.BOMB and _action_strength(action) > table_strength:
                filtered.append(action)

    return tuple(filtered)


class RuleEngine(Protocol):
    """Protocol for rule-engine responsibilities."""

    def detect_pattern(self, cards: tuple) -> Pattern:
        """Detect pattern of given cards."""

    def generate_legal_actions(self, state: GameState) -> tuple[Action, ...]:
        """Generate legal actions for current player."""

    def validate_action(self, state: GameState, action: Action) -> None:
        """Validate action against current rules; raise on invalid action."""

    def apply_action(self, state: GameState, action: Action) -> GameState:
        """Apply a validated action and return next state."""


class BaseRuleEngine:
    """Base class placeholder for future concrete rule engine."""

    def detect_pattern(self, cards: tuple) -> Pattern:
        return detect_pattern(cards)

    def generate_legal_actions(self, state: GameState) -> tuple[Action, ...]:
        player = state.get_player(state.current_player_id)
        play_actions = _build_supported_play_actions(player.player_id, player.hand_cards)

        table_action = state.table_constraint.leading_action
        # Active play: no table constraint, pass is not legal.
        if table_action is None:
            return play_actions

        follow_actions = list(_filter_follow_actions(play_actions, table_action))
        follow_actions.append(Action.make_pass(player.player_id))
        return tuple(follow_actions)

    def validate_action(self, state: GameState, action: Action) -> None:
        if state.is_finished:
            raise ValueError("game already finished")

        if action.player_id != state.current_player_id:
            raise ValueError("action player_id must match current_player_id")

        table_action = state.table_constraint.leading_action

        if action.action_type == ActionType.PASS:
            if table_action is None:
                raise ValueError("pass is not allowed in active play")
            if not _table_action_is_self_consistent(table_action):
                raise ValueError("dirty table constraint action")
            return

        if action.action_type != ActionType.PLAY:
            raise ValueError("unsupported action type")

        player = state.get_player(state.current_player_id)
        if not action.cards:
            raise ValueError("play action must contain cards")
        if not _cards_subset_of_hand(action.cards, player.hand_cards):
            raise ValueError("action cards are not a subset of player hand")

        detected = detect_pattern(action.cards)
        if detected.type not in _supported_play_patterns():
            raise ValueError("action cards do not form a supported pattern")

        if action.declared_pattern is None:
            raise ValueError("play action must provide declared_pattern")
        if action.declared_pattern != detected.type:
            raise ValueError("declared_pattern does not match detected pattern")

        if table_action is None:
            return

        if not _table_action_is_self_consistent(table_action):
            raise ValueError("dirty table constraint action")

        table_pattern = table_action.declared_pattern
        table_strength = _action_strength(table_action)
        action_strength = _action_strength(action)

        if table_pattern in {PatternType.SINGLE, PatternType.PAIR, PatternType.TRIPLE}:
            legal_same_type = action.declared_pattern == table_pattern and action_strength > table_strength
            legal_bomb = action.declared_pattern == PatternType.BOMB
            if not (legal_same_type or legal_bomb):
                raise ValueError("play action cannot beat current table action")
            return

        if table_pattern == PatternType.BOMB:
            legal_bomb_over_bomb = (
                action.declared_pattern == PatternType.BOMB and action_strength > table_strength
            )
            if not legal_bomb_over_bomb:
                raise ValueError("only a bigger bomb can beat current bomb")
            return

        raise ValueError("unsupported table pattern")

    def apply_action(self, state: GameState, action: Action) -> GameState:
        self.validate_action(state, action)

        step_no = state.step_no + 1
        players = list(state.players)
        current_player = state.get_player(state.current_player_id)

        if action.action_type == ActionType.PASS:
            # Follow-play pass only. Round ends after other players all pass.
            next_consecutive_passes = state.consecutive_passes + 1
            leading_action = state.table_constraint.leading_action
            assert leading_action is not None

            if next_consecutive_passes >= len(state.players) - 1:
                return replace(
                    state,
                    current_player_id=leading_action.player_id,
                    table_constraint=TableConstraint(),
                    step_no=step_no,
                    round_no=state.round_no + 1,
                    consecutive_passes=0,
                )

            return replace(
                state,
                current_player_id=_next_player_id(state, state.current_player_id),
                step_no=step_no,
                consecutive_passes=next_consecutive_passes,
            )

        detected = detect_pattern(action.cards)

        remaining_hand = list(current_player.hand_cards)
        for card in action.cards:
            remaining_hand.remove(card)

        updated_player = current_player.with_hand_cards(tuple(remaining_hand))
        for idx, player in enumerate(players):
            if player.player_id == current_player.player_id:
                players[idx] = updated_player
                break

        if len(updated_player.hand_cards) == 0:
            return replace(
                state,
                players=tuple(players),
                step_no=step_no,
                is_finished=True,
                winner_player_id=current_player.player_id,
                consecutive_passes=0,
                table_constraint=TableConstraint(
                    leading_action=action,
                    required_pattern=detected.type,
                    min_strength_hint=_action_strength(action),
                ),
            )

        return replace(
            state,
            players=tuple(players),
            current_player_id=_next_player_id(state, state.current_player_id),
            table_constraint=TableConstraint(
                leading_action=action,
                required_pattern=detected.type,
                min_strength_hint=_action_strength(action),
            ),
            step_no=step_no,
            consecutive_passes=0,
        )
