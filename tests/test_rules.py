"""Step-3 unit tests for legal action generation."""

import unittest

from engine.actions import Action, ActionType
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint


def _build_state(
    current_player_hand: tuple[Card, ...],
    table_action: Action | None,
) -> GameState:
    players = (
        PlayerState(player_id=0, hand_cards=current_player_hand),
        PlayerState(player_id=1, hand_cards=()),
        PlayerState(player_id=2, hand_cards=()),
        PlayerState(player_id=3, hand_cards=()),
    )
    return GameState(
        players=players,
        current_player_id=0,
        table_constraint=TableConstraint(leading_action=table_action),
    )


def _to_signature(action: Action) -> tuple[str, str | None, tuple[str, ...]]:
    return (
        action.action_type.value,
        action.declared_pattern.value if action.declared_pattern else None,
        tuple(sorted(card.rank for card in action.cards)),
    )


class TestRules(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BaseRuleEngine()

    def test_u3_generate_legal_actions_active_play_no_pass(self) -> None:
        hand = (
            Card(rank="3", suit="S"),
            Card(rank="3", suit="H"),
            Card(rank="4", suit="S"),
            Card(rank="4", suit="H"),
            Card(rank="4", suit="C"),
            Card(rank="4", suit="D"),
        )
        state = _build_state(hand, table_action=None)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertTrue(all(action.action_type == ActionType.PLAY for action in actions))
        self.assertEqual(len(actions), len(signatures), "legal action set must not contain duplicates")

        self.assertIn(("play", "single", ("3",)), signatures)
        self.assertIn(("play", "single", ("4",)), signatures)
        self.assertIn(("play", "pair", ("3", "3")), signatures)
        self.assertIn(("play", "pair", ("4", "4")), signatures)
        self.assertIn(("play", "triple", ("4", "4", "4")), signatures)
        self.assertIn(("play", "bomb", ("4", "4", "4", "4")), signatures)

    def test_u4_follow_single_allows_bigger_same_type_or_bomb_or_pass(self) -> None:
        hand = (
            Card(rank="5", suit="S"),
            Card(rank="7", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="9", suit="C"),
            Card(rank="9", suit="D"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="6", suit="H"),),
            declared_pattern=PatternType.SINGLE,
        )
        state = _build_state(hand, table_action=table_action)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertIn(("pass", None, ()), signatures)
        self.assertIn(("play", "single", ("7",)), signatures)
        self.assertIn(("play", "single", ("9",)), signatures)
        self.assertIn(("play", "bomb", ("9", "9", "9", "9")), signatures)
        self.assertNotIn(("play", "single", ("5",)), signatures)

    def test_u4_follow_bomb_allows_only_bigger_bomb_or_pass(self) -> None:
        hand = (
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
            Card(rank="8", suit="C"),
            Card(rank="8", suit="D"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="9", suit="C"),
            Card(rank="9", suit="D"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="8", suit="C"),
                Card(rank="8", suit="D"),
            ),
            declared_pattern=PatternType.BOMB,
        )
        state = _build_state(hand, table_action=table_action)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertIn(("pass", None, ()), signatures)
        self.assertIn(("play", "bomb", ("9", "9", "9", "9")), signatures)
        self.assertNotIn(("play", "bomb", ("8", "8", "8", "8")), signatures)
        self.assertNotIn(("play", "single", ("9",)), signatures)

    def test_u11_jokers_appear_in_legal_actions_active_play(self) -> None:
        hand = (
            Card(rank=SMALL_JOKER_RANK),
            Card(rank=BIG_JOKER_RANK),
            Card(rank="4", suit="S"),
        )
        state = _build_state(hand, table_action=None)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertIn(("play", "single", (SMALL_JOKER_RANK,)), signatures)
        self.assertIn(("play", "single", (BIG_JOKER_RANK,)), signatures)

    def test_u12_follow_single_allows_small_joker_over_ace(self) -> None:
        hand = (Card(rank=SMALL_JOKER_RANK), Card(rank="3", suit="S"))
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="A", suit="H"),),
            declared_pattern=PatternType.SINGLE,
        )
        state = _build_state(hand, table_action=table_action)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertIn(("play", "single", (SMALL_JOKER_RANK,)), signatures)
        self.assertNotIn(("play", "single", ("3",)), signatures)

    def test_u12_follow_single_allows_big_joker_over_small_joker(self) -> None:
        hand = (Card(rank=BIG_JOKER_RANK), Card(rank="K", suit="S"))
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank=SMALL_JOKER_RANK),),
            declared_pattern=PatternType.SINGLE,
        )
        state = _build_state(hand, table_action=table_action)

        actions = self.engine.generate_legal_actions(state)
        signatures = {_to_signature(action) for action in actions}

        self.assertIn(("play", "single", (BIG_JOKER_RANK,)), signatures)
        self.assertNotIn(("play", "single", ("K",)), signatures)

    def test_u16_legacy_subset_not_broken_after_joker_integration(self) -> None:
        hand = (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="7", suit="C"),
            Card(rank="7", suit="D"),
        )
        active_state = _build_state(hand, table_action=None)

        active_actions = self.engine.generate_legal_actions(active_state)
        active_signatures = {_to_signature(action) for action in active_actions}
        self.assertIn(("play", "single", ("6",)), active_signatures)
        self.assertIn(("play", "pair", ("6", "6")), active_signatures)
        self.assertIn(("play", "triple", ("7", "7", "7")), active_signatures)
        self.assertIn(("play", "bomb", ("7", "7", "7", "7")), active_signatures)
        self.assertNotIn(("pass", None, ()), active_signatures)

        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="6", suit="C"),),
            declared_pattern=PatternType.SINGLE,
        )
        follow_state = _build_state(hand, table_action=table_action)
        follow_actions = self.engine.generate_legal_actions(follow_state)
        follow_signatures = {_to_signature(action) for action in follow_actions}
        self.assertIn(("pass", None, ()), follow_signatures)

    # Straight
    def test_straight_generated_in_active_play(self) -> None:
        hand = (
            Card(rank="6", suit="S"),
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
        )
        state = _build_state(hand, table_action=None)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "straight", ("10", "6", "7", "8", "9")), signatures)

    def test_straight_follow_requires_same_length_and_higher_top(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="J", suit="S"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="H"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="H"),
                Card(rank="10", suit="H"),
            ),
            declared_pattern=PatternType("straight"),
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "straight", ("10", "7", "8", "9", "J")), signatures)
        self.assertIn(("pass", None, ()), signatures)

    def test_straight_cannot_beat_different_length_straight(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="J", suit="S"),
            Card(rank="Q", suit="S"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="H"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="H"),
                Card(rank="10", suit="H"),
            ),
            declared_pattern=PatternType.STRAIGHT,
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertNotIn(("play", "straight", ("10", "7", "8", "9", "J", "Q")), signatures)

    # Pair-straight
    def test_pair_straight_generated_in_active_play(self) -> None:
        hand = (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
        )
        state = _build_state(hand, table_action=None)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "pair_straight", ("6", "6", "7", "7", "8", "8")), signatures)

    def test_pair_straight_follow_requires_same_pair_count_and_higher_top(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="C"),
                Card(rank="6", suit="D"),
                Card(rank="7", suit="C"),
                Card(rank="7", suit="D"),
                Card(rank="8", suit="C"),
                Card(rank="8", suit="D"),
            ),
            declared_pattern=PatternType("pair_straight"),
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "pair_straight", ("7", "7", "8", "8", "9", "9")), signatures)
        self.assertIn(("pass", None, ()), signatures)

    def test_pair_straight_cannot_beat_different_pair_count(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="10", suit="S"),
            Card(rank="10", suit="H"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="C"),
                Card(rank="6", suit="D"),
                Card(rank="7", suit="C"),
                Card(rank="7", suit="D"),
                Card(rank="8", suit="C"),
                Card(rank="8", suit="D"),
            ),
            declared_pattern=PatternType.PAIR_STRAIGHT,
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertNotIn(
            ("play", "pair_straight", ("10", "10", "7", "7", "8", "8", "9", "9")),
            signatures,
        )

    # Triple-with-pair
    def test_triple_with_pair_generated_in_active_play(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="7", suit="C"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
        )
        state = _build_state(hand, table_action=None)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "triple_with_pair", ("7", "7", "7", "9", "9")), signatures)

    def test_triple_with_pair_follow_compares_triple_rank(self) -> None:
        hand = (
            Card(rank="8", suit="S"),
            Card(rank="8", suit="H"),
            Card(rank="8", suit="C"),
            Card(rank="3", suit="S"),
            Card(rank="3", suit="H"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="A", suit="S"),
                Card(rank="A", suit="H"),
            ),
            declared_pattern=PatternType("triple_with_pair"),
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertIn(("play", "triple_with_pair", ("3", "3", "8", "8", "8")), signatures)
        self.assertIn(("pass", None, ()), signatures)

    def test_triple_with_pair_follow_ignores_pair_rank_when_triple_weaker(self) -> None:
        hand = (
            Card(rank="7", suit="S"),
            Card(rank="7", suit="H"),
            Card(rank="7", suit="C"),
            Card(rank="A", suit="S"),
            Card(rank="A", suit="H"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="8", suit="C"),
                Card(rank="3", suit="S"),
                Card(rank="3", suit="H"),
            ),
            declared_pattern=PatternType.TRIPLE_WITH_PAIR,
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}
        self.assertNotIn(("play", "triple_with_pair", ("7", "7", "7", "A", "A")), signatures)

    def test_bomb_can_beat_straight_pair_straight_and_triple_with_pair(self) -> None:
        bomb_hand = (
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="9", suit="C"),
            Card(rank="9", suit="D"),
        )

        straight_state = _build_state(
            bomb_hand,
            table_action=Action(
                player_id=1,
                action_type=ActionType.PLAY,
                cards=(
                    Card(rank="6", suit="S"),
                    Card(rank="7", suit="S"),
                    Card(rank="8", suit="S"),
                    Card(rank="9", suit="S"),
                    Card(rank="10", suit="S"),
                ),
                declared_pattern=PatternType.STRAIGHT,
            ),
        )
        pair_straight_state = _build_state(
            bomb_hand,
            table_action=Action(
                player_id=1,
                action_type=ActionType.PLAY,
                cards=(
                    Card(rank="6", suit="S"),
                    Card(rank="6", suit="H"),
                    Card(rank="7", suit="S"),
                    Card(rank="7", suit="H"),
                    Card(rank="8", suit="S"),
                    Card(rank="8", suit="H"),
                ),
                declared_pattern=PatternType.PAIR_STRAIGHT,
            ),
        )
        triple_with_pair_state = _build_state(
            bomb_hand,
            table_action=Action(
                player_id=1,
                action_type=ActionType.PLAY,
                cards=(
                    Card(rank="7", suit="S"),
                    Card(rank="7", suit="H"),
                    Card(rank="7", suit="C"),
                    Card(rank="3", suit="S"),
                    Card(rank="3", suit="H"),
                ),
                declared_pattern=PatternType.TRIPLE_WITH_PAIR,
            ),
        )

        straight_signatures = {
            _to_signature(action) for action in self.engine.generate_legal_actions(straight_state)
        }
        pair_straight_signatures = {
            _to_signature(action) for action in self.engine.generate_legal_actions(pair_straight_state)
        }
        triple_with_pair_signatures = {
            _to_signature(action)
            for action in self.engine.generate_legal_actions(triple_with_pair_state)
        }

        expected_bomb = ("play", "bomb", ("9", "9", "9", "9"))
        self.assertIn(expected_bomb, straight_signatures)
        self.assertIn(expected_bomb, pair_straight_signatures)
        self.assertIn(expected_bomb, triple_with_pair_signatures)

    def test_straight_pair_straight_and_triple_with_pair_cannot_beat_bomb(self) -> None:
        hand = (
            Card(rank="6", suit="S"),
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="7", suit="H"),
            Card(rank="8", suit="H"),
            Card(rank="7", suit="C"),
            Card(rank="3", suit="S"),
            Card(rank="3", suit="H"),
        )
        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="8", suit="C"),
                Card(rank="8", suit="D"),
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
            ),
            declared_pattern=PatternType.BOMB,
        )
        state = _build_state(hand, table_action=table_action)
        signatures = {_to_signature(action) for action in self.engine.generate_legal_actions(state)}

        self.assertNotIn(("play", "straight", ("10", "6", "7", "8", "9")), signatures)
        self.assertNotIn(("play", "pair_straight", ("6", "6", "7", "7", "8", "8")), signatures)
        self.assertNotIn(("play", "triple_with_pair", ("3", "3", "7", "7", "7")), signatures)

    def test_apply_action_for_new_patterns_reduces_hand_count_correctly(self) -> None:
        # straight consumes 5 cards
        straight_state = _build_state(
            (
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
                Card(rank="A", suit="S"),
            ),
            table_action=None,
        )
        straight_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
            ),
            declared_pattern=PatternType.STRAIGHT,
        )
        straight_next = self.engine.apply_action(straight_state, straight_action)
        self.assertEqual(len(straight_next.get_player(0).hand_cards), 1)

        # pair_straight consumes 6 cards
        pair_straight_state = _build_state(
            (
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="A", suit="S"),
            ),
            table_action=None,
        )
        pair_straight_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
            ),
            declared_pattern=PatternType.PAIR_STRAIGHT,
        )
        pair_straight_next = self.engine.apply_action(pair_straight_state, pair_straight_action)
        self.assertEqual(len(pair_straight_next.get_player(0).hand_cards), 1)

        # triple_with_pair consumes 5 cards
        triple_with_pair_state = _build_state(
            (
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
                Card(rank="A", suit="S"),
            ),
            table_action=None,
        )
        triple_with_pair_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
            ),
            declared_pattern=PatternType.TRIPLE_WITH_PAIR,
        )
        triple_with_pair_next = self.engine.apply_action(triple_with_pair_state, triple_with_pair_action)
        self.assertEqual(len(triple_with_pair_next.get_player(0).hand_cards), 1)

    def test_validate_action_does_not_mutate_hand_before_execution(self) -> None:
        state = _build_state(
            (
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
            ),
            table_action=None,
        )
        action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(
                Card(rank="6", suit="S"),
                Card(rank="7", suit="S"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="S"),
            ),
            declared_pattern=PatternType.STRAIGHT,
        )

        before = state.get_player(0).hand_cards
        self.engine.validate_action(state, action)
        after = state.get_player(0).hand_cards
        self.assertEqual(before, after)

    def test_u5_validate_action_legal_and_illegal(self) -> None:
        active_hand = (Card(rank="7", suit="S"), Card(rank="7", suit="H"))
        active_state = _build_state(active_hand, table_action=None)
        legal_play = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="7", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        self.engine.validate_action(active_state, legal_play)

        illegal_pass = Action.make_pass(0)
        with self.assertRaises(ValueError):
            self.engine.validate_action(active_state, illegal_pass)

        table_action = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="9", suit="H"),),
            declared_pattern=PatternType.SINGLE,
        )
        follow_state = _build_state((Card(rank="8", suit="S"),), table_action=table_action)
        illegal_follow = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="8", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        with self.assertRaises(ValueError):
            self.engine.validate_action(follow_state, illegal_follow)

    def test_u6_state_transition_updates_hand_correctly(self) -> None:
        state = _build_state(
            (
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="9", suit="S"),
            ),
            table_action=None,
        )
        action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="6", suit="S"), Card(rank="6", suit="H")),
            declared_pattern=PatternType.PAIR,
        )

        next_state = self.engine.apply_action(state, action)
        next_player = next_state.get_player(0)

        self.assertEqual(next_player.hand_cards, (Card(rank="9", suit="S"),))
        self.assertEqual(next_state.current_player_id, 1)
        self.assertEqual(next_state.table_constraint.required_pattern, PatternType.PAIR)

    def test_u7_state_transition_pass_and_round_end(self) -> None:
        table_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="10", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        players = (
            PlayerState(player_id=0, hand_cards=(Card(rank="3", suit="S"),)),
            PlayerState(player_id=1, hand_cards=(Card(rank="4", suit="S"),)),
            PlayerState(player_id=2, hand_cards=(Card(rank="5", suit="S"),)),
            PlayerState(player_id=3, hand_cards=(Card(rank="6", suit="S"),)),
        )
        # Already had 2 consecutive passes; this pass should end the round.
        state = GameState(
            players=players,
            current_player_id=3,
            table_constraint=TableConstraint(leading_action=table_action),
            consecutive_passes=2,
            round_no=1,
        )
        pass_action = Action.make_pass(3)

        next_state = self.engine.apply_action(state, pass_action)

        self.assertEqual(next_state.current_player_id, 0)
        self.assertIsNone(next_state.table_constraint.leading_action)
        self.assertEqual(next_state.consecutive_passes, 0)
        self.assertEqual(next_state.round_no, 2)

    def test_u8_terminal_judgement_and_no_further_normal_play(self) -> None:
        state = _build_state((Card(rank="A", suit="S"),), table_action=None)
        finishing_action = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="A", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        terminal_state = self.engine.apply_action(state, finishing_action)

        self.assertTrue(terminal_state.is_finished)
        self.assertEqual(terminal_state.winner_player_id, 0)

        next_play = Action(
            player_id=0,
            action_type=ActionType.PLAY,
            cards=(Card(rank="A", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        with self.assertRaises(ValueError):
            self.engine.validate_action(terminal_state, next_play)
