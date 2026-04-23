"""Card helpers for the single-game GuanDan mainline."""

from dataclasses import dataclass


SMALL_JOKER_RANK = "SJ"
BIG_JOKER_RANK = "BJ"

SUITS: tuple[str, ...] = ("S", "H", "C", "D")
RANKS: tuple[str, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")

_RANK_SORT_ORDER: dict[str, int] = {
    "3": 0,
    "4": 1,
    "5": 2,
    "6": 3,
    "7": 4,
    "8": 5,
    "9": 6,
    "10": 7,
    "J": 8,
    "Q": 9,
    "K": 10,
    "A": 11,
    "2": 12,
    SMALL_JOKER_RANK: 13,
    BIG_JOKER_RANK: 14,
}
_SUIT_SORT_ORDER: dict[str | None, int] = {
    None: 0,
    "S": 1,
    "H": 2,
    "C": 3,
    "D": 4,
}


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str | None = None

    def __post_init__(self) -> None:
        if not self.rank:
            raise ValueError("Card.rank must be non-empty")
        if self.suit is not None and self.suit not in SUITS:
            raise ValueError("Card.suit must be one of S/H/C/D or None")


def is_joker(card: Card) -> bool:
    return card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}


def card_to_token(card: Card) -> str:
    if card.suit is None:
        return card.rank
    return f"{card.rank}{card.suit}"


def cards_to_tokens(cards: tuple[Card, ...]) -> tuple[str, ...]:
    return tuple(card_to_token(card) for card in cards)


def card_sort_key(card: Card) -> tuple[int, int, str]:
    return (
        _RANK_SORT_ORDER.get(card.rank, 999),
        _SUIT_SORT_ORDER.get(card.suit, 999),
        card_to_token(card),
    )


def sort_cards(cards: tuple[Card, ...]) -> tuple[Card, ...]:
    return tuple(sorted(cards, key=card_sort_key))


def build_double_deck() -> list[Card]:
    deck: list[Card] = []
    for _ in range(2):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(Card(rank=rank, suit=suit))
        deck.append(Card(rank=SMALL_JOKER_RANK))
        deck.append(Card(rank=BIG_JOKER_RANK))
    return deck
