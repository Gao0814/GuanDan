"""Pattern data structures for phase-1 supported types."""

from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

from .cards import Card


class PatternType(str, Enum):
    """Pattern types frozen for phase-1 scope."""

    SINGLE = "single"
    PAIR = "pair"
    TRIPLE = "triple"
    STRAIGHT = "straight"
    PAIR_STRAIGHT = "pair_straight"
    TRIPLE_WITH_PAIR = "triple_with_pair"
    BOMB = "bomb"
    PASS = "pass"
    UNKNOWN = "unknown"


_SEQUENCE_RANKS: tuple[str, ...] = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
_SEQUENCE_INDEX: dict[str, int] = {rank: idx for idx, rank in enumerate(_SEQUENCE_RANKS)}


def _are_consecutive(ranks: tuple[str, ...]) -> bool:
    if not ranks:
        return False
    try:
        indices = sorted(_SEQUENCE_INDEX[rank] for rank in ranks)
    except KeyError:
        return False
    return all(indices[i + 1] - indices[i] == 1 for i in range(len(indices) - 1))


@dataclass(frozen=True, slots=True)
class Pattern:
    """Represents identified pattern information.

    NOTE: Full pattern recognition is intentionally not implemented in Step 1.
    """

    type: PatternType
    cards_count: int
    strength_hint: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def detect_pattern(cards: tuple[Card, ...]) -> Pattern:
    """Detect phase-1 supported pattern from input cards.

    Supported in Step 2 only:
    - single: 1 card
    - pair: 2 cards with same rank
    - triple: 3 cards with same rank
    - bomb: 4 cards with same rank

    Any other combination returns PatternType.UNKNOWN with a failure reason.
    """

    cards_count = len(cards)
    if cards_count == 0:
        return Pattern(
            type=PatternType.UNKNOWN,
            cards_count=0,
            metadata={"reason": "empty_cards_not_supported"},
        )

    if cards_count == 1:
        return Pattern(type=PatternType.SINGLE, cards_count=1)

    rank_counts = Counter(card.rank for card in cards)

    # straight: >=5 distinct consecutive ranks, no 2/jokers.
    if cards_count >= 5 and len(rank_counts) == cards_count and _are_consecutive(tuple(rank_counts.keys())):
        return Pattern(type=PatternType.STRAIGHT, cards_count=cards_count)

    if cards_count == 5:
        # triple_with_pair: exactly 3 + 2 with distinct ranks.
        counts = sorted(rank_counts.values())
        if counts == [2, 3]:
            return Pattern(type=PatternType.TRIPLE_WITH_PAIR, cards_count=5)

        return Pattern(
            type=PatternType.UNKNOWN,
            cards_count=5,
            metadata={"reason": "unsupported_cards_count"},
        )

    if cards_count >= 6 and cards_count % 2 == 0:
        # pair_straight: >=3 consecutive pairs, no 2/jokers.
        if len(rank_counts) >= 3 and all(count == 2 for count in rank_counts.values()):
            if _are_consecutive(tuple(rank_counts.keys())):
                return Pattern(type=PatternType.PAIR_STRAIGHT, cards_count=cards_count)
        return Pattern(
            type=PatternType.UNKNOWN,
            cards_count=cards_count,
            metadata={"reason": "unsupported_even_cards_combination"},
        )

    if cards_count not in (2, 3, 4):
        return Pattern(
            type=PatternType.UNKNOWN,
            cards_count=cards_count,
            metadata={"reason": "unsupported_cards_count"},
        )

    ranks = {card.rank for card in cards}
    if len(ranks) != 1:
        return Pattern(
            type=PatternType.UNKNOWN,
            cards_count=cards_count,
            metadata={"reason": "ranks_not_identical"},
        )

    if cards_count == 2:
        return Pattern(type=PatternType.PAIR, cards_count=2)
    if cards_count == 3:
        return Pattern(type=PatternType.TRIPLE, cards_count=3)

    return Pattern(type=PatternType.BOMB, cards_count=4)
