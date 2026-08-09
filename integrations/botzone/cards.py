"""The fixed, offline 108-card GuanDan identity codec."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


RANKS: Final[tuple[str, ...]] = (
    "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"
)
SUITS: Final[tuple[str, ...]] = ("h", "d", "s", "c")
SMALL_JOKER: Final[str] = "SJ"
BIG_JOKER: Final[str] = "BJ"
CARDS_PER_DECK: Final[int] = 54
TOTAL_CARDS: Final[int] = 108


@dataclass(frozen=True, slots=True)
class CardFace:
    """A declared face; it intentionally has no physical-copy identity."""

    rank: str
    suit: str | None

    @property
    def is_joker(self) -> bool:
        return self.rank in (SMALL_JOKER, BIG_JOKER)

    def to_json(self) -> dict[str, str | None]:
        return {"rank": self.rank, "suit": self.suit}


@dataclass(frozen=True, slots=True)
class BotzoneCard:
    """One physical card, including the first/second-deck identity."""

    card_id: int
    copy_index: int
    face: CardFace

    @property
    def rank(self) -> str:
        return self.face.rank

    @property
    def suit(self) -> str | None:
        return self.face.suit

    @property
    def is_joker(self) -> bool:
        return self.face.is_joker

    def is_wildcard(self, level: str) -> bool:
        return self.rank == level and self.suit == "h"

    def to_json(self) -> dict[str, int | str | None]:
        return {
            "id": self.card_id,
            "copy": self.copy_index,
            "rank": self.rank,
            "suit": self.suit,
        }


def _require_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def _require_card_id(card_id: object) -> int:
    value = _require_int(card_id, "card_id")
    if not 0 <= value < TOTAL_CARDS:
        raise ValueError("card_id outside 0..107")
    return value


def card_from_id(card_id: object) -> BotzoneCard:
    """Decode one physical ID without discarding its duplicate-deck identity."""

    value = _require_card_id(card_id)
    copy_index, offset = divmod(value, CARDS_PER_DECK)
    if offset == 52:
        face = CardFace(SMALL_JOKER, None)
    elif offset == 53:
        face = CardFace(BIG_JOKER, None)
    else:
        rank_index, suit_index = divmod(offset, len(SUITS))
        face = CardFace(RANKS[rank_index], SUITS[suit_index])
    return BotzoneCard(value, copy_index, face)


def card_id_for(rank: object, suit: object, copy_index: object = 0) -> int:
    """Encode a physical card ID from its face and deck-copy index."""

    copy = _require_int(copy_index, "copy_index")
    if copy not in (0, 1):
        raise ValueError("copy_index must be 0 or 1")
    if not isinstance(rank, str):
        raise ValueError("rank must be a string")

    if rank == SMALL_JOKER:
        if suit is not None:
            raise ValueError("small joker has no suit")
        offset = 52
    elif rank == BIG_JOKER:
        if suit is not None:
            raise ValueError("big joker has no suit")
        offset = 53
    else:
        if rank not in RANKS or suit not in SUITS:
            raise ValueError("invalid ordinary card face")
        offset = RANKS.index(rank) * len(SUITS) + SUITS.index(suit)
    return copy * CARDS_PER_DECK + offset


ALL_CARDS: Final[tuple[BotzoneCard, ...]] = tuple(card_from_id(card_id) for card_id in range(TOTAL_CARDS))
CARD_BY_ID: Final[MappingProxyType[int, BotzoneCard]] = MappingProxyType(
    {card.card_id: card for card in ALL_CARDS}
)
