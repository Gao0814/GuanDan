"""Pattern recognition for the single-game GuanDan mainline."""

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from .cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, is_joker


class PatternType(str, Enum):
    SINGLE = "single"
    PAIR = "pair"
    TRIPLE = "triple"
    TRIPLE_WITH_PAIR = "triple_with_pair"
    STRAIGHT = "straight"
    PAIR_STRAIGHT = "pair_straight"
    STEEL_PLATE = "steel_plate"
    BOMB = "bomb"
    STRAIGHT_FLUSH = "straight_flush"
    JOKER_BOMB = "joker_bomb"
    PASS = "pass"
    UNKNOWN = "unknown"


_STRAIGHT_WINDOWS: tuple[tuple[str, ...], ...] = (
    ("A", "2", "3", "4", "5"),
    ("3", "4", "5", "6", "7"),
    ("4", "5", "6", "7", "8"),
    ("5", "6", "7", "8", "9"),
    ("6", "7", "8", "9", "10"),
    ("7", "8", "9", "10", "J"),
    ("8", "9", "10", "J", "Q"),
    ("9", "10", "J", "Q", "K"),
    ("10", "J", "Q", "K", "A"),
)
_PAIR_STRAIGHT_WINDOWS: tuple[tuple[str, ...], ...] = (
    ("3", "4", "5"),
    ("4", "5", "6"),
    ("5", "6", "7"),
    ("6", "7", "8"),
    ("7", "8", "9"),
    ("8", "9", "10"),
    ("9", "10", "J"),
    ("10", "J", "Q"),
    ("J", "Q", "K"),
    ("Q", "K", "A"),
)
_STEEL_PLATE_WINDOWS: tuple[tuple[str, ...], ...] = (
    ("3", "4"),
    ("4", "5"),
    ("5", "6"),
    ("6", "7"),
    ("7", "8"),
    ("8", "9"),
    ("9", "10"),
    ("10", "J"),
    ("J", "Q"),
    ("Q", "K"),
    ("K", "A"),
)


@dataclass(frozen=True, slots=True)
class Pattern:
    type: PatternType
    cards_count: int
    main_rank: str | None = None
    sequence_index: int | None = None
    bomb_length: int | None = None
    suit: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def _unknown(cards_count: int, reason: str) -> Pattern:
    return Pattern(
        type=PatternType.UNKNOWN,
        cards_count=cards_count,
        metadata={"reason": reason},
    )


def _all_same_rank(cards: tuple[Card, ...]) -> bool:
    return len({card.rank for card in cards}) == 1


def _match_window(ranks: tuple[str, ...], windows: tuple[tuple[str, ...], ...]) -> int | None:
    rank_set = set(ranks)
    for index, window in enumerate(windows):
        if rank_set == set(window):
            return index
    return None


def detect_pattern(cards: tuple[Card, ...]) -> Pattern:
    cards_count = len(cards)
    if cards_count == 0:
        return _unknown(0, "empty_cards_not_supported")

    if cards_count == 1:
        return Pattern(type=PatternType.SINGLE, cards_count=1, main_rank=cards[0].rank)

    rank_counts = Counter(card.rank for card in cards)

    if cards_count == 2:
        if len(rank_counts) != 1:
            return _unknown(cards_count, "pair_requires_identical_rank")
        return Pattern(type=PatternType.PAIR, cards_count=2, main_rank=cards[0].rank)

    if cards_count == 3:
        if len(rank_counts) != 1:
            return _unknown(cards_count, "triple_requires_identical_rank")
        rank = cards[0].rank
        if rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
            return _unknown(cards_count, "joker_triple_not_supported")
        return Pattern(type=PatternType.TRIPLE, cards_count=3, main_rank=rank)

    if cards_count == 4:
        if (
            rank_counts.get(SMALL_JOKER_RANK, 0) == 2
            and rank_counts.get(BIG_JOKER_RANK, 0) == 2
            and len(rank_counts) == 2
        ):
            return Pattern(type=PatternType.JOKER_BOMB, cards_count=4)
        if any(is_joker(card) for card in cards):
            return _unknown(cards_count, "only_tianwang_bomb_is_supported")
        if _all_same_rank(cards):
            return Pattern(
                type=PatternType.BOMB,
                cards_count=4,
                main_rank=cards[0].rank,
                bomb_length=4,
            )
        return _unknown(cards_count, "unsupported_four_card_pattern")

    if cards_count >= 5 and _all_same_rank(cards) and not any(is_joker(card) for card in cards):
        return Pattern(
            type=PatternType.BOMB,
            cards_count=cards_count,
            main_rank=cards[0].rank,
            bomb_length=cards_count,
        )

    if cards_count == 5:
        counts = sorted(rank_counts.values())
        if counts == [2, 3]:
            triple_rank = next(rank for rank, count in rank_counts.items() if count == 3)
            if triple_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
                return _unknown(cards_count, "triple_with_pair_triple_cannot_be_joker")
            pair_rank = next(rank for rank, count in rank_counts.items() if count == 2)
            if pair_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or pair_rank == triple_rank:
                return Pattern(
                    type=PatternType.TRIPLE_WITH_PAIR,
                    cards_count=5,
                    main_rank=triple_rank,
                )
            return Pattern(
                type=PatternType.TRIPLE_WITH_PAIR,
                cards_count=5,
                main_rank=triple_rank,
            )

        if any(is_joker(card) for card in cards):
            return _unknown(cards_count, "jokers_not_allowed_in_straights")

        straight_index = _match_window(tuple(rank_counts.keys()), _STRAIGHT_WINDOWS)
        if straight_index is not None:
            suits = {card.suit for card in cards}
            if len(suits) == 1 and None not in suits:
                suit = next(iter(suits))
                return Pattern(
                    type=PatternType.STRAIGHT_FLUSH,
                    cards_count=5,
                    sequence_index=straight_index,
                    suit=suit,
                )
            return Pattern(
                type=PatternType.STRAIGHT,
                cards_count=5,
                sequence_index=straight_index,
            )
        return _unknown(cards_count, "unsupported_five_card_pattern")

    if cards_count == 6:
        if any(is_joker(card) for card in cards):
            return _unknown(cards_count, "jokers_not_allowed_in_sequence_family")
        if sorted(rank_counts.values()) == [2, 2, 2]:
            sequence_index = _match_window(tuple(rank_counts.keys()), _PAIR_STRAIGHT_WINDOWS)
            if sequence_index is not None:
                return Pattern(
                    type=PatternType.PAIR_STRAIGHT,
                    cards_count=6,
                    sequence_index=sequence_index,
                )
        if sorted(rank_counts.values()) == [3, 3]:
            sequence_index = _match_window(tuple(rank_counts.keys()), _STEEL_PLATE_WINDOWS)
            if sequence_index is not None:
                high_rank = _STEEL_PLATE_WINDOWS[sequence_index][-1]
                return Pattern(
                    type=PatternType.STEEL_PLATE,
                    cards_count=6,
                    main_rank=high_rank,
                    sequence_index=sequence_index,
                )
        return _unknown(cards_count, "unsupported_six_card_pattern")

    return _unknown(cards_count, "unsupported_cards_count")
