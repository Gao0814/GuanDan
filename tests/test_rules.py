import unittest
from collections import Counter

from engine.actions import Action, ActionType
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card
from engine.game import GuanDanGame
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


def _pass_id(game: GuanDanGame) -> int:
    for action in game.legal_actions():
        if action["declared_pattern"] == "pass":
            return int(action["action_id"])
    raise AssertionError("pass action not found")


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

    def test_bomb_comparison_same_length_uses_rank(self) -> None:
        bomb5_k = _action(2, PatternType.BOMB, ("K", "K", "K", "K", "K"))
        bomb5_a = _action(1, PatternType.BOMB, ("A", "A", "A", "A", "A"))

        self.assertTrue(self.rules.can_beat(bomb5_a, bomb5_k, current_level_rank="2"))
        self.assertFalse(self.rules.can_beat(bomb5_k, bomb5_a, current_level_rank="2"))

    def test_round_end_resets_table_constraint_to_free(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=3,
            preset_table_action=_action(
                2,
                PatternType.SINGLE,
                (BIG_JOKER_RANK,),
                (BIG_JOKER_RANK,),
            ),
            preset_hands={
                1: _cards("3S"),
                2: _cards("6S"),
                3: _cards("4S"),
                4: _cards("5S"),
            },
        )
        game.reset()

        self.assertNotEqual(game.observe()["current_round"]["constraint"], "free")

        game.step(_pass_id(game))
        game.step(_pass_id(game))
        result = game.step(_pass_id(game))

        self.assertTrue(result["round_ended"])
        observation = game.observe()
        self.assertEqual(observation["current_round"]["constraint"], "free")
        self.assertIsNone(observation["current_round"]["table_action"])
        self.assertEqual(observation["current_round"]["current_player_id"], 2)

    def test_generated_actions_carrier_cards_are_payable_from_hand(self) -> None:
        state = _state(
            hand_tokens=(
                "2H",  # wildcard (current_level_rank is 2)
                "2S",
                "9S",
                "9H",
                "10C",
                "JD",
            ),
            current_level_rank="2",
        )

        actions = self.rules.generate_legal_actions(state)
        hand_counter = Counter((card.rank, card.suit) for card in state.get_player(1).hand_cards)

        for action in actions:
            if action.action_type != ActionType.PLAY:
                continue
            carrier_counter = Counter((card.rank, card.suit) for card in action.carrier_cards)
            with self.subTest(action=action):
                for key, count in carrier_counter.items():
                    self.assertLessEqual(count, hand_counter.get(key, 0))

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

    def test_follow_constraint_allows_wildcard_bomb_cross_type_suppression(self) -> None:
        """Regression: wildcard bombs must appear when following a non-bomb pattern."""
        table_action = _action(
            2,
            PatternType.TRIPLE_WITH_PAIR,
            ("9", "9", "9", "10", "10"),
            ("9S", "9H", "9C", "10S", "10C"),
        )
        # Hand: 3 natural fives + 3 natural eights + 1 wildcard + fillers
        state = _state(
            hand_tokens=(
                "5S", "5C", "5D",  # 3 fives → wildcard 4-bomb-5
                "8S", "8C", "8D",  # 3 eights → wildcard 4-bomb-8
                "2H",  # wildcard (红桃级牌, current_level_rank=2)
                # filler cards to make 27
                "3S", "4S", "6S", "7S", "9S", "10S", "JS", "QS", "KS", "AS",
                "3C", "4C", "6C", "7C", "9C", "10C", "JC", "QC", "KC", "AC",
            ),
            table_action=table_action,
            current_level_rank="2",
        )

        actions = self.rules.generate_legal_actions(state)
        bomb_actions = [a for a in actions if a.declared_pattern == PatternType.BOMB]
        bomb_signatures = {
            (
                tuple(c.rank for c in a.declared_cards),
                a.wildcard_count,
            )
            for a in bomb_actions
        }

        # Both wildcard bombs must be present
        self.assertIn((("5", "5", "5", "5"), 1), bomb_signatures)
        self.assertIn((("8", "8", "8", "8"), 1), bomb_signatures)

        # Pass must always be present
        pass_actions = [a for a in actions if a.action_type == ActionType.PASS]
        self.assertEqual(len(pass_actions), 1)


if __name__ == "__main__":
    unittest.main()
