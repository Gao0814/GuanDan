import unittest

from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card
from engine.patterns import PatternType, detect_pattern


def _cards(*tokens: str) -> tuple[Card, ...]:
    cards: list[Card] = []
    for token in tokens:
        if token in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
            cards.append(Card(rank=token))
            continue
        if len(token) >= 2 and token[-1] in {"S", "H", "C", "D"}:
            cards.append(Card(rank=token[:-1], suit=token[-1]))
            continue
        cards.append(Card(rank=token))
    return tuple(cards)


class TestPatterns(unittest.TestCase):
    def test_joker_patterns_follow_the_whitelist_only(self) -> None:
        self.assertEqual(detect_pattern(_cards(SMALL_JOKER_RANK)).type, PatternType.SINGLE)
        self.assertEqual(detect_pattern(_cards(BIG_JOKER_RANK)).type, PatternType.SINGLE)
        self.assertEqual(
            detect_pattern(_cards(SMALL_JOKER_RANK, SMALL_JOKER_RANK)).type,
            PatternType.PAIR,
        )
        self.assertEqual(
            detect_pattern(_cards(BIG_JOKER_RANK, BIG_JOKER_RANK)).type,
            PatternType.PAIR,
        )
        self.assertEqual(
            detect_pattern(
                _cards(
                    SMALL_JOKER_RANK,
                    SMALL_JOKER_RANK,
                    BIG_JOKER_RANK,
                    BIG_JOKER_RANK,
                )
            ).type,
            PatternType.JOKER_BOMB,
        )

        invalid_cases = (
            _cards(SMALL_JOKER_RANK, SMALL_JOKER_RANK, SMALL_JOKER_RANK, BIG_JOKER_RANK),
            _cards(SMALL_JOKER_RANK, BIG_JOKER_RANK, BIG_JOKER_RANK, BIG_JOKER_RANK),
            _cards(SMALL_JOKER_RANK, SMALL_JOKER_RANK, SMALL_JOKER_RANK, SMALL_JOKER_RANK),
            _cards(BIG_JOKER_RANK, BIG_JOKER_RANK, BIG_JOKER_RANK, BIG_JOKER_RANK),
        )
        for cards in invalid_cases:
            with self.subTest(cards=cards):
                self.assertEqual(detect_pattern(cards).type, PatternType.UNKNOWN)

    def test_straight_boundaries_allow_a2345_23456_and_10jqka(self) -> None:
        self.assertEqual(
            detect_pattern(_cards("AS", "2H", "3C", "4D", "5S")).type,
            PatternType.STRAIGHT,
        )
        self.assertEqual(
            detect_pattern(_cards("2S", "3H", "4C", "5D", "6S")).type,
            PatternType.STRAIGHT,
        )
        self.assertEqual(
            detect_pattern(_cards("10S", "JH", "QC", "KD", "AS")).type,
            PatternType.STRAIGHT,
        )
        self.assertEqual(
            detect_pattern(_cards("JS", "QH", "KC", "AD", "2S")).type,
            PatternType.UNKNOWN,
        )

    def test_pair_straight_and_steel_plate_respect_length_and_boundary(self) -> None:
        self.assertEqual(
            detect_pattern(_cards("6S", "6H", "7S", "7H", "8S", "8H")).type,
            PatternType.PAIR_STRAIGHT,
        )
        self.assertEqual(
            detect_pattern(_cards("AS", "AH", "2S", "2H", "3S", "3H")).type,
            PatternType.UNKNOWN,
        )
        self.assertEqual(
            detect_pattern(_cards("6S", "6H", "6C", "7S", "7H", "7C")).type,
            PatternType.STEEL_PLATE,
        )
        self.assertEqual(
            detect_pattern(_cards("AS", "AH", "AC", "2S", "2H", "2C")).type,
            PatternType.UNKNOWN,
        )

    def test_straight_flush_uses_the_same_sequence_boundary(self) -> None:
        self.assertEqual(
            detect_pattern(_cards("AH", "2H", "3H", "4H", "5H")).type,
            PatternType.STRAIGHT_FLUSH,
        )
        self.assertEqual(
            detect_pattern(_cards("2H", "3H", "4H", "5H", "6H")).type,
            PatternType.STRAIGHT_FLUSH,
        )
        # 反例：不满足同花时，不应被识别为同花顺。
        self.assertEqual(
            detect_pattern(_cards("2H", "3H", "4H", "5H", "6S")).type,
            PatternType.STRAIGHT,
        )
        self.assertEqual(
            detect_pattern(_cards("10H", "JH", "QH", "KH", "AH")).type,
            PatternType.STRAIGHT_FLUSH,
        )
        self.assertEqual(
            detect_pattern(_cards("JH", "QH", "KH", "AH", "2H")).type,
            PatternType.UNKNOWN,
        )

    def test_triple_with_pair_is_strict_three_plus_two_and_can_carry_joker_pair(self) -> None:
        self.assertEqual(
            detect_pattern(_cards("7S", "7H", "7C", SMALL_JOKER_RANK, SMALL_JOKER_RANK)).type,
            PatternType.TRIPLE_WITH_PAIR,
        )
        self.assertEqual(
            detect_pattern(_cards("7S", "7H", "7C", "8S", "9H")).type,
            PatternType.UNKNOWN,
        )
        self.assertEqual(
            detect_pattern(_cards("7S", "7H", "8C", "8S", "8H")).type,
            PatternType.TRIPLE_WITH_PAIR,
        )


if __name__ == "__main__":
    unittest.main()
