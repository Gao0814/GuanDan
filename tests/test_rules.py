import unittest

from engine.actions import Action, ActionType
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint


def _card(token: str) -> Card:
    if token in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
        return Card(rank=token)
    if token[-1] in {"S", "H", "C", "D"}:
        return Card(rank=token[:-1], suit=token[-1])
    return Card(rank=token)


def _cards(*tokens: str) -> tuple[Card, ...]:
    return tuple(_card(token) for token in tokens)


def _action(
    player_id: int,
    declared_pattern: PatternType,
    declared_tokens: tuple[str, ...],
    carrier_tokens: tuple[str, ...] | None = None,
) -> Action:
    return Action(
        player_id=player_id,
        action_type=ActionType.PLAY,
        declared_pattern=declared_pattern,
        declared_cards=_cards(*declared_tokens),
        carrier_cards=_cards(*(carrier_tokens or declared_tokens)),
        display_text="test-action",
    )


def _state(
    *,
    hand_tokens: tuple[str, ...],
    table_action: Action | None = None,
    current_level_rank: str = "2",
) -> GameState:
    return GameState(
        players=(
            PlayerState(player_id=1, hand_cards=_cards(*hand_tokens)),
            PlayerState(player_id=2, hand_cards=()),
            PlayerState(player_id=3, hand_cards=()),
            PlayerState(player_id=4, hand_cards=()),
        ),
        current_player_id=1,
        current_level_rank=current_level_rank,
        table_constraint=TableConstraint(leading_action=table_action),
    )


class TestRules(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = BaseRuleEngine()

    def test_same_carrier_cards_expand_into_multiple_canonical_declarations(self) -> None:
        state = _state(hand_tokens=("2H", "7S", "7C", "8S", "8C"))

        actions = self.rules.generate_legal_actions(state)
        triple_with_pair_actions = [
            action
            for action in actions
            if action.declared_pattern == PatternType.TRIPLE_WITH_PAIR
        ]

        signatures = {
            (
                tuple(card.rank for card in action.declared_cards),
                tuple(f"{card.rank}{card.suit or ''}" for card in action.carrier_cards),
                action.wildcard_count,
            )
            for action in triple_with_pair_actions
        }

        self.assertIn(
            (("7", "7", "7", "8", "8"), ("7S", "7C", "8S", "8C", "2H"), 1),
            signatures,
        )
        self.assertIn(
            (("8", "8", "8", "7", "7"), ("7S", "7C", "8S", "8C", "2H"), 1),
            signatures,
        )

    def test_legal_actions_expand_explicit_wildcard_declarations(self) -> None:
        state = _state(hand_tokens=("2H", "7S", "8S", "9S", "10S"))

        actions = self.rules.generate_legal_actions(state)
        expanded = {
            (
                action.declared_pattern.value if action.declared_pattern else None,
                tuple(card.rank for card in action.declared_cards),
                tuple(sorted(f"{card.rank}{card.suit or ''}" for card in action.carrier_cards)),
                action.wildcard_count,
            )
            for action in actions
            if action.wildcard_count == 1
        }

        self.assertIn(
            ("straight", ("6", "7", "8", "9", "10"), ("10S", "2H", "7S", "8S", "9S"), 1),
            expanded,
        )
        self.assertIn(
            ("straight", ("7", "8", "9", "10", "J"), ("10S", "2H", "7S", "8S", "9S"), 1),
            expanded,
        )

    def test_wildcard_cannot_participate_in_any_joker_pattern(self) -> None:
        state = _state(hand_tokens=("2H", SMALL_JOKER_RANK))

        actions = self.rules.generate_legal_actions(state)
        for action in actions:
            if action.wildcard_count == 0:
                continue
            with self.subTest(action=action):
                self.assertNotEqual(action.declared_pattern, PatternType.JOKER_BOMB)
                self.assertTrue(
                    all(card.rank not in {SMALL_JOKER_RANK, BIG_JOKER_RANK} for card in action.declared_cards)
                )

    def test_no_action_uses_more_than_one_wildcard_substitution(self) -> None:
        state = _state(hand_tokens=("2H", "2H", "7S", "7C", "8S", "8C"))

        actions = self.rules.generate_legal_actions(state)
        for action in actions:
            with self.subTest(action=action):
                self.assertIn(action.wildcard_count, {0, 1})

    def test_same_type_pressure_requires_a_stronger_action(self) -> None:
        weaker = _action(2, PatternType.SINGLE, ("9",), ("9S",))
        stronger = _action(1, PatternType.SINGLE, ("10",), ("10S",))
        equal = _action(1, PatternType.SINGLE, ("9",), ("9H",))

        self.assertTrue(self.rules.can_beat(stronger, weaker, current_level_rank="2"))
        self.assertFalse(self.rules.can_beat(equal, weaker, current_level_rank="2"))

    def test_cross_type_hierarchy_is_fixed(self) -> None:
        bomb4 = _action(2, PatternType.BOMB, ("9", "9", "9", "9"), ("9S", "9H", "9C", "9D"))
        bomb5 = _action(
            1,
            PatternType.BOMB,
            ("10", "10", "10", "10", "10"),
            ("10S", "10H", "10C", "10D", "2H"),
        )
        bomb6 = _action(
            1,
            PatternType.BOMB,
            ("8", "8", "8", "8", "8", "8"),
            ("8S", "8H", "8C", "8D", "8S", "2H"),
        )
        straight_flush = _action(
            1,
            PatternType.STRAIGHT_FLUSH,
            ("6H", "7H", "8H", "9H", "10H"),
        )
        joker_bomb = _action(
            1,
            PatternType.JOKER_BOMB,
            (SMALL_JOKER_RANK, SMALL_JOKER_RANK, BIG_JOKER_RANK, BIG_JOKER_RANK),
        )

        self.assertTrue(self.rules.can_beat(bomb5, bomb4, current_level_rank="2"))
        self.assertTrue(self.rules.can_beat(straight_flush, bomb5, current_level_rank="2"))
        self.assertFalse(self.rules.can_beat(straight_flush, bomb6, current_level_rank="2"))
        self.assertTrue(self.rules.can_beat(bomb6, straight_flush, current_level_rank="2"))
        self.assertTrue(self.rules.can_beat(joker_bomb, bomb6, current_level_rank="2"))

    def test_follow_context_only_exposes_beating_actions_or_pass(self) -> None:
        table_action = _action(2, PatternType.PAIR, ("9", "9"), ("9S", "9H"))
        state = _state(
            hand_tokens=("8S", "8H", "10S", "10H", "JS", "QH"),
            table_action=table_action,
        )

        actions = self.rules.generate_legal_actions(state)
        signatures = {
            (
                action.action_type.value,
                action.declared_pattern.value if action.declared_pattern else None,
                tuple(card.rank for card in action.declared_cards),
            )
            for action in actions
        }

        self.assertIn(("play", "pair", ("10", "10")), signatures)
        self.assertIn(("pass", None, ()), signatures)
        self.assertNotIn(("play", "pair", ("8", "8")), signatures)

    def test_follow_context_keeps_only_the_beating_declaration_for_same_carrier_group(self) -> None:
        table_action = _action(
            2,
            PatternType.TRIPLE_WITH_PAIR,
            ("7", "7", "7", "9", "9"),
            ("7S", "7H", "7D", "9S", "9H"),
        )
        state = _state(
            hand_tokens=("2H", "7S", "7C", "8S", "8C"),
            table_action=table_action,
        )

        actions = self.rules.generate_legal_actions(state)
        signatures = {
            (
                action.action_type.value,
                action.declared_pattern.value if action.declared_pattern else None,
                tuple(card.rank for card in action.declared_cards),
                tuple(f"{card.rank}{card.suit or ''}" for card in action.carrier_cards),
            )
            for action in actions
        }

        self.assertIn(
            ("play", "triple_with_pair", ("8", "8", "8", "7", "7"), ("7S", "7C", "8S", "8C", "2H")),
            signatures,
        )
        self.assertIn(("pass", None, (), ()), signatures)
        self.assertNotIn(
            ("play", "triple_with_pair", ("7", "7", "7", "8", "8"), ("7S", "7C", "8S", "8C", "2H")),
            signatures,
        )


if __name__ == "__main__":
    unittest.main()
