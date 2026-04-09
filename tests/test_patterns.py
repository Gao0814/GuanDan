"""Step-2 unit tests for phase-1 pattern recognition subset."""

import unittest

from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card
from engine.patterns import PatternType, detect_pattern


class TestPatterns(unittest.TestCase):
    # Straight
    def test_straight_recognized_min_length_five(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="6", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="C"),
                Card(rank="9", suit="D"),
                Card(rank="10", suit="S"),
            )
        )
        self.assertEqual(pattern.type.value, "straight")

    def test_straight_rejects_with_rank_2(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="10", suit="S"),
                Card(rank="J", suit="H"),
                Card(rank="Q", suit="C"),
                Card(rank="K", suit="D"),
                Card(rank="2", suit="S"),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_straight_rejects_with_small_joker(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="7", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="C"),
                Card(rank="10", suit="D"),
                Card(rank=SMALL_JOKER_RANK),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_straight_rejects_with_big_joker(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="7", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="C"),
                Card(rank="10", suit="D"),
                Card(rank=BIG_JOKER_RANK),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    # Pair-straight
    def test_pair_straight_recognized_min_length_three_pairs(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
            )
        )
        self.assertEqual(pattern.type.value, "pair_straight")

    def test_pair_straight_rejects_non_consecutive_pairs(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="6", suit="S"),
                Card(rank="6", suit="H"),
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_pair_straight_rejects_with_rank_2(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="10", suit="S"),
                Card(rank="10", suit="H"),
                Card(rank="J", suit="S"),
                Card(rank="J", suit="H"),
                Card(rank="2", suit="S"),
                Card(rank="2", suit="H"),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_pair_straight_rejects_with_small_joker_pair(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
                Card(rank=SMALL_JOKER_RANK),
                Card(rank=SMALL_JOKER_RANK),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_pair_straight_rejects_with_big_joker_pair(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="8", suit="S"),
                Card(rank="8", suit="H"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
                Card(rank=BIG_JOKER_RANK),
                Card(rank=BIG_JOKER_RANK),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    # Triple-with-pair
    def test_triple_with_pair_recognized(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="9", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        self.assertEqual(pattern.type.value, "triple_with_pair")

    def test_triple_with_pair_rejects_when_pair_missing(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="9", suit="S"),
                Card(rank="10", suit="H"),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_triple_with_pair_rejects_two_kickers_not_a_pair(self) -> None:
        pattern = detect_pattern(
            (
                Card(rank="7", suit="S"),
                Card(rank="7", suit="H"),
                Card(rank="7", suit="C"),
                Card(rank="8", suit="S"),
                Card(rank="9", suit="H"),
            )
        )
        self.assertEqual(pattern.type, PatternType.UNKNOWN)

    def test_u11_jokers_can_be_modeled_as_cards(self) -> None:
        small_joker = Card(rank=SMALL_JOKER_RANK)
        big_joker = Card(rank=BIG_JOKER_RANK)

        self.assertNotEqual(small_joker.rank, big_joker.rank)
        self.assertIsNone(small_joker.suit)
        self.assertIsNone(big_joker.suit)

    def test_u11_jokers_enter_pattern_pipeline_as_single(self) -> None:
        small_pattern = detect_pattern((Card(rank=SMALL_JOKER_RANK),))
        big_pattern = detect_pattern((Card(rank=BIG_JOKER_RANK),))

        self.assertEqual(small_pattern.type, PatternType.SINGLE)
        self.assertEqual(big_pattern.type, PatternType.SINGLE)

    def test_u12_joker_pair_recognized_when_identical_rank(self) -> None:
        pattern = detect_pattern((Card(rank=SMALL_JOKER_RANK), Card(rank=SMALL_JOKER_RANK)))
        self.assertEqual(pattern.type, PatternType.PAIR)

    def test_u12_mixed_jokers_rejected_in_current_subset(self) -> None:
        pattern = detect_pattern((Card(rank=SMALL_JOKER_RANK), Card(rank=BIG_JOKER_RANK)))
        self.assertEqual(pattern.type, PatternType.UNKNOWN)
        self.assertEqual(pattern.metadata.get("reason"), "ranks_not_identical")

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
