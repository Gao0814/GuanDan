"""Card-related data structures for phase-1.

This module intentionally keeps card representation minimal for Step 1.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Card:
    """A single card entity.

    The exact ranking/comparison semantics are not implemented in Step 1.
    """

    rank: str
    suit: str | None = None

    def __post_init__(self) -> None:
        if not self.rank:
            raise ValueError("Card.rank must be a non-empty string.")
