"""Game orchestration skeleton for four-AI debug runs."""

from dataclasses import dataclass
import random

from agents.base import AgentContext, BaseAgent
from engine.actions import Action
from engine.logging_utils import DebugLogger
from engine.rules import RuleEngine
from engine.cards import Card
from engine.state import GameState, PlayerState, TableConstraint


_RANKS: tuple[str, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
_SUITS: tuple[str, ...] = ("S", "H", "C", "D")


def _action_to_dict(action: Action) -> dict[str, object]:
    return {
        "player_id": action.player_id,
        "action_type": action.action_type.value,
        "declared_pattern": action.declared_pattern.value if action.declared_pattern else None,
        "cards": [f"{card.rank}{card.suit or ''}" for card in action.cards],
    }


def _state_snapshot(state: GameState) -> dict[str, object]:
    recent_success_player = (
        state.table_constraint.leading_action.player_id
        if state.table_constraint.leading_action is not None
        else None
    )
    return {
        "current_player_id": state.current_player_id,
        "table_constraint": {
            "required_pattern": (
                state.table_constraint.required_pattern.value
                if state.table_constraint.required_pattern is not None
                else None
            ),
            "min_strength_hint": state.table_constraint.min_strength_hint,
            "leading_action": (
                _action_to_dict(state.table_constraint.leading_action)
                if state.table_constraint.leading_action is not None
                else None
            ),
        },
        "remaining_hand_counts": {
            player.player_id: len(player.hand_cards) for player in state.players
        },
        "recent_success_player": recent_success_player,
        "phase": "lead" if state.table_constraint.leading_action is None else "follow",
        "round_no": state.round_no,
    }


def build_initial_state(seed: int | None = None) -> GameState:
    """Create a dealt initial game state for four AI players.

    Uses two standard decks without extra joker-specific logic to stay within phase-1 subset.
    """

    rng = random.Random(seed)
    deck: list[Card] = []
    for _ in range(2):
        for suit in _SUITS:
            for rank in _RANKS:
                deck.append(Card(rank=rank, suit=suit))
    rng.shuffle(deck)

    players: list[PlayerState] = []
    chunk = len(deck) // 4
    for player_id in range(4):
        start = player_id * chunk
        end = start + chunk
        hand = tuple(deck[start:end])
        players.append(PlayerState(player_id=player_id, hand_cards=hand))

    return GameState(
        players=tuple(players),
        current_player_id=0,
        table_constraint=TableConstraint(),
        round_no=1,
    )


@dataclass(slots=True)
class FourAIGameRunner:
    """Coordinates game loop dependencies without implementing full flow yet."""

    rule_engine: RuleEngine
    agents: tuple[BaseAgent, BaseAgent, BaseAgent, BaseAgent]
    debug_logger: DebugLogger
    max_steps: int = 5000

    def run_one_game(self, initial_state: GameState) -> GameState:
        """Run one full game from initial state.

        Raises RuntimeError on non-terminating progression.
        """

        state = initial_state
        while not state.is_finished:
            if state.step_no >= self.max_steps:
                raise RuntimeError("game did not finish within max_steps")
            state, _ = self.step(state)
        return state

    def step(self, state: GameState) -> tuple[GameState, Action]:
        """Advance exactly one action step.

        Emits one full-information debug event aligned with I3 fields.
        """

        state_before = _state_snapshot(state)
        player_id = state.current_player_id
        legal_actions = self.rule_engine.generate_legal_actions(state)
        if not legal_actions:
            raise RuntimeError("no legal actions generated for current state")

        agent = self.agents[player_id]
        chosen_action = agent.select_action(
            state=state,
            legal_actions=legal_actions,
            context=AgentContext(step_no=state.step_no),
        )

        decision_basis: dict[str, object] = {
            "rule": ["rule:select_from_legal_actions_only"],
            "experience": [],
        }
        if hasattr(agent, "last_decision_record"):
            record = getattr(agent, "last_decision_record")
            if record is not None:
                decision_basis = {
                    "rule": list(record.rule_references),
                    "experience": list(record.experience_references),
                }

        # Explicit legality check before state update.
        self.rule_engine.validate_action(state, chosen_action)
        next_state = self.rule_engine.apply_action(state, chosen_action)
        state_after = _state_snapshot(next_state)

        round_ended = (
            next_state.round_no > state.round_no
            and next_state.table_constraint.leading_action is None
        )

        all_hands = {
            player.player_id: [f"{card.rank}{card.suit or ''}" for card in player.hand_cards]
            for player in state.players
        }
        all_hands_after = {
            player.player_id: [f"{card.rank}{card.suit or ''}" for card in player.hand_cards]
            for player in next_state.players
        }

        self.debug_logger.record(
            event_type="step",
            payload={
                "step_id": next_state.step_no,
                "current_player_id": player_id,
                "all_hands": all_hands,
                "all_hands_after": all_hands_after,
                "table_constraint": state_before["table_constraint"],
                "legal_actions": [_action_to_dict(action) for action in legal_actions],
                "chosen_action": _action_to_dict(chosen_action),
                "decision_basis": decision_basis,
                "state_before": state_before,
                "state_after": state_after,
                "remaining_hand_counts": state_after["remaining_hand_counts"],
                "round_ended": round_ended,
                "game_over": next_state.is_finished,
                "winner": next_state.winner_player_id,
            },
        )

        return next_state, chosen_action
