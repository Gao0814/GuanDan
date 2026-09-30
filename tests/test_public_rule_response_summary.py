from __future__ import annotations

import unittest

from engine.actions import Action, ActionType
from engine.cards import Card
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine


class PublicRuleResponseSummaryTests(unittest.TestCase):
    def test_explicit_public_hand_returns_only_beating_pattern_types(self) -> None:
        leading = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            declared_pattern=PatternType.SINGLE,
            declared_cards=(Card("5"),),
            carrier_cards=(Card("5", "S"),),
        )

        result = BaseRuleEngine().public_beating_pattern_types(
            (Card("7", "S"), Card("9", "S")),
            leading,
            "2",
        )

        self.assertEqual(result, ("single",))
        self.assertTrue(all(isinstance(pattern, str) for pattern in result))

    def test_known_natural_bomb_uses_engine_cross_pattern_rules(self) -> None:
        leading = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            declared_pattern=PatternType.TRIPLE_WITH_PAIR,
            declared_cards=(Card("5"), Card("5"), Card("5"), Card("4"), Card("4")),
            carrier_cards=(
                Card("5", "S"), Card("5", "H"), Card("5", "C"), Card("4", "S"), Card("4", "H"),
            ),
        )

        result = BaseRuleEngine().public_beating_pattern_types(
            (Card("9", "S"), Card("9", "H"), Card("9", "C"), Card("9", "D")),
            leading,
            "2",
        )

        self.assertEqual(result, ("bomb",))

    def test_four_joker_bomb_has_no_immediate_public_response_pattern(self) -> None:
        leading = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            declared_pattern=PatternType.JOKER_BOMB,
            declared_cards=(Card("SJ"), Card("SJ"), Card("BJ"), Card("BJ")),
            carrier_cards=(Card("SJ"), Card("SJ"), Card("BJ"), Card("BJ")),
        )

        result = BaseRuleEngine().public_beating_pattern_types(
            (Card("2", "S"), Card("2", "H"), Card("BJ")),
            leading,
            "2",
        )

        self.assertEqual(result, ())

    def test_resource_query_accepts_a_public_pool_without_level_heart(self) -> None:
        leading = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            declared_pattern=PatternType.STRAIGHT,
            declared_cards=tuple(Card(rank) for rank in ("3", "4", "5", "6", "7")),
            carrier_cards=(Card("3", "S"), Card("4", "H"), Card("5", "C"), Card("6", "D"), Card("7", "S")),
        )
        available = tuple(Card(rank, "S") for rank in ("6", "7", "8", "9", "10"))

        rules = BaseRuleEngine()
        result = rules.public_beating_response_resource_counts(
            available,
            leading,
            "2",
            max_cards=5,
        )
        batched = rules.public_beating_response_summaries(
            available,
            (leading,),
            "2",
            max_cards=5,
        )[0]

        self.assertIn(
            "straight_flush",
            {item.pattern_type for item in result},
        )
        self.assertIn(
            "straight_flush",
            {item.pattern_type for item in batched.resource_counts},
        )

    def test_pass_has_no_beating_pattern_and_level_is_validated(self) -> None:
        self.assertEqual(
            BaseRuleEngine().public_beating_pattern_types((), Action.make_pass(1), "2"),
            (),
        )
        with self.assertRaises(ValueError):
            BaseRuleEngine().public_beating_pattern_types((), Action.make_pass(1), "invalid")


if __name__ == "__main__":
    unittest.main()
