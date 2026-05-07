"""Single-game GuanDan environment with action-id based interaction."""

from dataclasses import replace
import random

from .actions import Action, ActionType, public_action_id
from .cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, build_double_deck, card_to_token, sort_cards
from .logging_utils import DebugLogger
from .rules import BaseRuleEngine
from .state import GameState, HistoryEntry, PlayerState, TableConstraint


def _partner_id(player_id: int) -> int:
    return ((player_id + 1) % 4) + 1


def _next_player_ids(start_player_id: int, active_player_ids: tuple[int, ...]) -> tuple[int, ...]:
    if not active_player_ids:
        return ()
    ordered: list[int] = []
    current = start_player_id
    for _ in range(4):
        current = (current % 4) + 1
        if current in active_player_ids:
            ordered.append(current)
    return tuple(ordered)


def _token_for_declared(card: Card) -> str:
    return card.rank if card.suit is None else card_to_token(card)


def _action_to_public_dict(action: Action, action_id: int | None = None) -> dict[str, object]:
    declared_pattern = action.declared_pattern.value if action.declared_pattern is not None else "pass"
    payload = {
        "action_id": action_id,
        "declared_pattern": declared_pattern,
        "declared_cards": [_token_for_declared(card) for card in action.declared_cards],
        "carrier_cards": [card_to_token(card) for card in action.carrier_cards],
        "wildcard_count": action.wildcard_count,
        "wildcard_info": [
            {
                "carrier_card": card_to_token(item.carrier_card),
                "declared_as": _token_for_declared(item.declared_as),
            }
            for item in action.wildcard_info
        ],
        "display_text": action.display_text if action.display_text else declared_pattern,
    }
    return payload


def _remaining_single_card_count(hand_cards: tuple[Card, ...]) -> int:
    counts: dict[str, int] = {}
    for card in hand_cards:
        counts[card.rank] = counts.get(card.rank, 0) + 1
    return sum(1 for card in hand_cards if counts.get(card.rank, 0) == 1)


def _state_counts(state: GameState) -> dict[int, int]:
    return {player.player_id: len(player.hand_cards) for player in state.players}


def _resolve_winner(finish_order: tuple[int, ...]) -> str:
    head_player_id = finish_order[0]
    if finish_order[-1] == _partner_id(head_player_id):
        return "draw"
    return "team_13" if head_player_id in {1, 3} else "team_24"


class GuanDanGame:
    def __init__(
        self,
        *,
        seed: int | None = None,
        current_level_rank: str = "2",
        preset_hands: dict[int, tuple[Card, ...]] | None = None,
        starting_player_id: int = 1,
        preset_table_action: Action | None = None,
    ) -> None:
        self._seed = seed
        self._current_level_rank = current_level_rank
        self._preset_hands = preset_hands
        self._starting_player_id = starting_player_id
        self._preset_table_action = preset_table_action
        self._rules = BaseRuleEngine()
        self._state: GameState | None = None
        self._legal_action_map: dict[int, Action] = {}
        self._legal_actions_state: GameState | None = None
        self._ordered_legal_actions: tuple[tuple[int, Action], ...] = ()

    def _invalidate_legal_actions_cache(self) -> None:
        self._legal_action_map = {}
        self._legal_actions_state = None
        self._ordered_legal_actions = ()

    def _validate_preset_hands(self) -> None:
        if self._preset_hands is None:
            return

        expected_player_ids = {1, 2, 3, 4}
        actual_player_ids = set(self._preset_hands.keys())
        if actual_player_ids != expected_player_ids:
            raise ValueError("preset_hands must define non-empty hands for players 1, 2, 3, and 4")

        for player_id in (1, 2, 3, 4):
            if not self._preset_hands[player_id]:
                raise ValueError("preset_hands must not contain empty player hands")

    def _build_players(self) -> tuple[PlayerState, ...]:
        if self._preset_hands is not None:
            self._validate_preset_hands()
            players: list[PlayerState] = []
            for player_id in (1, 2, 3, 4):
                hand_cards = sort_cards(tuple(self._preset_hands[player_id]))
                players.append(PlayerState(player_id=player_id, hand_cards=hand_cards))
            return tuple(players)

        deck = build_double_deck()
        rng = random.Random(self._seed)
        rng.shuffle(deck)
        players: list[PlayerState] = []
        for index, player_id in enumerate((1, 2, 3, 4)):
            start = index * 27
            players.append(
                PlayerState(
                    player_id=player_id,
                    hand_cards=sort_cards(tuple(deck[start : start + 27])),
                )
            )
        return tuple(players)

    def reset(self) -> dict[str, object]:
        players = self._build_players()
        table_constraint = TableConstraint()
        if self._preset_table_action is not None:
            unfinished = tuple(player.player_id for player in players if player.player_id != self._preset_table_action.player_id)
            table_constraint = TableConstraint(
                leading_action=self._preset_table_action,
                leader_player_id=self._preset_table_action.player_id,
                pending_player_ids=_next_player_ids(self._preset_table_action.player_id, unfinished),
            )
        self._state = GameState(
            players=players,
            current_player_id=self._starting_player_id,
            current_level_rank=self._current_level_rank,
            table_constraint=table_constraint,
        )
        self._invalidate_legal_actions_cache()
        return self.observe()

    def _require_state(self) -> GameState:
        if self._state is None:
            raise RuntimeError("game has not been reset")
        return self._state

    def _build_action_cache(self, state: GameState) -> tuple[tuple[int, Action], ...]:
        if self._legal_actions_state is state:
            return self._ordered_legal_actions

        ordered_actions: list[tuple[int, Action]] = []
        action_map: dict[int, Action] = {}
        for index, action in enumerate(self._rules.generate_legal_actions(state)):
            action_id = public_action_id(index)
            existing = action_map.get(action_id)
            if existing is not None and existing != action:
                raise RuntimeError("action_id collision detected for legal actions")
            action_map[action_id] = action
            ordered_actions.append((action_id, action))

        self._legal_actions_state = state
        self._legal_action_map = action_map
        self._ordered_legal_actions = tuple(ordered_actions)
        return self._ordered_legal_actions

    def legal_actions(self) -> list[dict[str, object]]:
        state = self._require_state()
        ordered_actions = self._build_action_cache(state)
        return [
            _action_to_public_dict(action, action_id=action_id)
            for action_id, action in ordered_actions
        ]

    def observe(self) -> dict[str, object]:
        state = self._require_state()
        current_player = state.get_player(state.current_player_id)
        public_actions = self.legal_actions()
        return {
            "my_info": {
                "player_id": state.current_player_id,
                "team": "team_13" if state.current_player_id in {1, 3} else "team_24",
                "current_level_rank": state.current_level_rank,
                "hand_cards": [card_to_token(card) for card in current_player.hand_cards],
                "hand_count": len(current_player.hand_cards),
                "remaining_single_card_count": _remaining_single_card_count(current_player.hand_cards),
            },
            "current_round": {
                "step_no": state.step_no,
                "round_no": state.round_no,
                "current_player_id": state.current_player_id,
                "current_level_rank": state.current_level_rank,
                "table_action": (
                    _action_to_public_dict(state.table_constraint.leading_action)
                    if state.table_constraint.leading_action is not None
                    else None
                ),
                "constraint": "free" if state.table_constraint.leading_action is None else state.table_constraint.leading_action.display_text,
            },
            "other_players": [
                {
                    "player_id": player.player_id,
                    "team": "team_13" if player.player_id in {1, 3} else "team_24",
                    "hand_count": len(player.hand_cards),
                    "finished": player.is_finished,
                    "finish_rank": player.finish_rank,
                }
                for player in state.players
                if player.player_id != state.current_player_id
            ],
            "history": {
                "actions": [
                    {
                        "step_no": item.step_no,
                        "round_no": item.round_no,
                        "player_id": item.player_id,
                        "declared_pattern": (
                            item.action.declared_pattern.value if item.action.declared_pattern is not None else "pass"
                        ),
                        "declared_cards": [_token_for_declared(card) for card in item.action.declared_cards],
                    }
                    for item in state.history
                ],
                "finish_order": list(state.finish_order),
            },
            "legal_actions": public_actions,
        }

    def _update_player_after_play(self, player_id: int, action: Action) -> tuple[tuple[PlayerState, ...], bool]:
        state = self._require_state()
        players = list(state.players)
        finished_now = False
        for index, player in enumerate(players):
            if player.player_id != player_id:
                continue
            remaining = list(player.hand_cards)
            for card in action.carrier_cards:
                remaining.remove(card)
            updated = player.with_hand_cards(sort_cards(tuple(remaining)))
            if not updated.hand_cards:
                updated = updated.with_finish_rank(len(state.finish_order) + 1)
                finished_now = True
            players[index] = updated
            break
        return tuple(players), finished_now

    def _apply_game_over_if_needed(self, state: GameState, players: tuple[PlayerState, ...], finish_order: tuple[int, ...]) -> GameState | None:
        if len(finish_order) < 3:
            return None
        remaining_player_id = next(player.player_id for player in players if player.finish_rank is None)
        final_players = tuple(
            player.with_finish_rank(4) if player.player_id == remaining_player_id else player
            for player in players
        )
        final_order = finish_order + (remaining_player_id,)
        return replace(
            state,
            players=final_players,
            finish_order=final_order,
            is_finished=True,
            table_constraint=TableConstraint(),
            winner=_resolve_winner(final_order),
        )

    def _resolve_next_round_leader(self, leader_player_id: int, players: tuple[PlayerState, ...]) -> int:
        unfinished = tuple(player.player_id for player in players if not player.is_finished)
        if leader_player_id in unfinished:
            return leader_player_id
        partner_id = _partner_id(leader_player_id)
        if partner_id in unfinished:
            return partner_id
        ordered = _next_player_ids(leader_player_id, unfinished)
        if not ordered:
            return leader_player_id
        return ordered[0]

    def step(self, action_id: int) -> dict[str, object]:
        state = self._require_state()
        if state.is_finished:
            raise ValueError("game is already over")

        self._build_action_cache(state)
        if action_id not in self._legal_action_map:
            raise ValueError("action_id is not in current legal_actions")

        selected = self._legal_action_map[action_id]
        before_counts = _state_counts(state)

        players = state.players
        finish_order = state.finish_order
        round_ended = False

        if selected.action_type == ActionType.PLAY:
            players, finished_now = self._update_player_after_play(state.current_player_id, selected)
            if finished_now:
                finish_order = finish_order + (state.current_player_id,)

            history = state.history + (
                HistoryEntry(
                    step_no=state.step_no + 1,
                    round_no=state.round_no,
                    player_id=state.current_player_id,
                    action=selected,
                ),
            )
            next_state = replace(
                state,
                players=players,
                step_no=state.step_no + 1,
                history=history,
                finish_order=finish_order,
            )
            game_over_state = self._apply_game_over_if_needed(next_state, players, finish_order)
            if game_over_state is not None:
                self._state = game_over_state
            else:
                unfinished = tuple(
                    player.player_id for player in players if not player.is_finished and player.player_id != state.current_player_id
                )
                pending = _next_player_ids(state.current_player_id, unfinished)
                if not pending:
                    round_ended = True
                    self._state = replace(
                        next_state,
                        current_player_id=self._resolve_next_round_leader(state.current_player_id, players),
                        round_no=state.round_no + 1,
                        table_constraint=TableConstraint(),
                    )
                else:
                    self._state = replace(
                        next_state,
                        current_player_id=pending[0],
                        table_constraint=TableConstraint(
                            leading_action=selected,
                            leader_player_id=state.current_player_id,
                            pending_player_ids=pending,
                        ),
                    )
        else:
            leader_player_id = state.table_constraint.leader_player_id
            if leader_player_id is None:
                raise ValueError("pass is not legal without an active table constraint")
            remaining_pending = tuple(
                player_id
                for player_id in state.table_constraint.pending_player_ids
                if player_id != state.current_player_id
            )
            history = state.history + (
                HistoryEntry(
                    step_no=state.step_no + 1,
                    round_no=state.round_no,
                    player_id=state.current_player_id,
                    action=selected,
                ),
            )
            next_state = replace(
                state,
                step_no=state.step_no + 1,
                history=history,
            )
            if not remaining_pending:
                round_ended = True
                self._state = replace(
                    next_state,
                    current_player_id=self._resolve_next_round_leader(leader_player_id, state.players),
                    round_no=state.round_no + 1,
                    table_constraint=TableConstraint(),
                )
            else:
                self._state = replace(
                    next_state,
                    current_player_id=remaining_pending[0],
                    table_constraint=TableConstraint(
                        leading_action=state.table_constraint.leading_action,
                        leader_player_id=leader_player_id,
                        pending_player_ids=remaining_pending,
                    ),
                )

        after_state = self._require_state()
        after_counts = _state_counts(after_state)
        self._invalidate_legal_actions_cache()
        state_diff = {
            "current_player_before": state.current_player_id,
            "current_player_after": after_state.current_player_id,
            "counts_before": before_counts,
            "counts_after": after_counts,
            "finish_order_before": list(state.finish_order),
            "finish_order_after": list(after_state.finish_order),
            "table_cleared": round_ended,
        }
        return {
            "step": after_state.step_no,
            "round": after_state.round_no,
            "current_player": after_state.current_player_id,
            "chosen_action": _action_to_public_dict(selected, action_id=action_id),
            "state_diff": state_diff,
            "remaining_hand_counts": after_counts,
            "round_ended": round_ended,
            "game_over": after_state.is_finished,
            "winner": after_state.winner,
        }


class FourAIGameRunner:
    def __init__(
        self,
        *,
        game: GuanDanGame,
        agents: tuple[object, object, object, object],
        debug_logger: DebugLogger | None = None,
        max_steps: int = 12000,
    ) -> None:
        self.game = game
        self.agents = agents
        self.debug_logger = debug_logger or DebugLogger()
        self.max_steps = max_steps

    def run_one_game(self) -> dict[str, object]:
        self.game.reset()
        while not self.game._state.is_finished:  # noqa: SLF001 - local debug runner
            if self.game._state.step_no >= self.max_steps:  # noqa: SLF001 - local debug runner
                raise RuntimeError("game did not finish within max_steps")
            observation = self.game.observe()
            legal_actions = self.game.legal_actions()
            player_id = int(observation["my_info"]["player_id"])
            chosen_action_id = self.agents[player_id - 1].select_action(observation, legal_actions)
            result = self.game.step(chosen_action_id)
            self.debug_logger.record("step", result)
        return {
            "winner": self.game._state.winner,  # noqa: SLF001 - local debug runner
            "step_no": self.game._state.step_no,  # noqa: SLF001 - local debug runner
            "round_no": self.game._state.round_no,  # noqa: SLF001 - local debug runner
        }
