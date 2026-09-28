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

    def test_pass_has_no_beating_pattern_and_level_is_validated(self) -> None:
        self.assertEqual(
            BaseRuleEngine().public_beating_pattern_types((), Action.make_pass(1), "2"),
            (),
        )
        with self.assertRaises(ValueError):
            BaseRuleEngine().public_beating_pattern_types((), Action.make_pass(1), "invalid")


if __name__ == "__main__":
    unittest.main()
