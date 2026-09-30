"""Shared natural sequence windows used by rules, detection and public analysis.

The duplicated Ace is intentional: the first occurrence is low for A-2-3
windows and the last is high for Q-K-A / 10-J-Q-K-A.  There is no edge from
the final Ace back to 2, so K-A-2 cannot wrap around.
"""

_ACE_LOW_HIGH_RANKS = (
    "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A",
)


def _windows(size: int) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(_ACE_LOW_HIGH_RANKS[index:index + size])
        for index in range(len(_ACE_LOW_HIGH_RANKS) - size + 1)
    )


STRAIGHT_WINDOWS = _windows(5)
PAIR_STRAIGHT_WINDOWS = _windows(3)
STEEL_PLATE_WINDOWS = _windows(2)
