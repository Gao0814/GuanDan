"""Pattern data structures for phase-1 supported types."""

from dataclasses import dataclass, field
from enum import Enum

from .cards import Card


class PatternType(str, Enum):
    """Pattern types frozen for phase-1 scope."""

    SINGLE = "single"
    PAIR = "pair"
    TRIPLE = "triple"
    BOMB = "bomb"
    PASS = "pass"
    UNKNOWN = "unknown"


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
