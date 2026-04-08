"""Step-2 unit tests for phase-1 pattern recognition subset."""

import unittest

from engine.cards import Card
from engine.patterns import PatternType, detect_pattern


class TestPatterns(unittest.TestCase):
    def test_u1_single_recognized(self) -> None:
        pattern = detect_pattern((Card(rank="A"),))
        self.assertEqual(pattern.type, PatternType.SINGLE)

    def test_u1_pair_recognized(self) -> None:
        pattern = detect_pattern((Card(rank="9"), Card(rank="9")))
        self.assertEqual(pattern.type, PatternType.PAIR)

    def test_u1_triple_recognized(self) -> None:
        pattern = detect_pattern((Card(rank="7"), Card(rank="7"), Card(rank="7")))
        self.assertEqual(pattern.type, PatternType.TRIPLE)

    def test_u1_bomb_recognized_four_same_rank(self) -> None:
        pattern = detect_pattern(
            (Card(rank="Q"), Card(rank="Q"), Card(rank="Q"), Card(rank="Q"))
        )
        self.assertEqual(pattern.type, PatternType.BOMB)

    def test_u2_illegal_empty_cards(self) -> None:
        pattern = detect_pattern(())
        self.assertEqual(pattern.type, PatternType.UNKNOWN)
        self.assertEqual(pattern.metadata.get("reason"), "empty_cards_not_supported")

    def test_u2_illegal_mixed_ranks(self) -> None:
        pattern = detect_pattern((Card(rank="9"), Card(rank="10")))
        self.assertEqual(pattern.type, PatternType.UNKNOWN)
        self.assertEqual(pattern.metadata.get("reason"), "ranks_not_identical")

    def test_u2_illegal_five_of_kind_not_phase2_subset(self) -> None:
        pattern = detect_pattern(
            (Card(rank="5"), Card(rank="5"), Card(rank="5"), Card(rank="5"), Card(rank="5"))
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)
        self.assertEqual(pattern.metadata.get("reason"), "unsupported_cards_count")
