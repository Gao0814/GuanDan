"""Rules and legal-action generation for the single-game GuanDan mainline."""

from collections import Counter, defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .actions import Action, ActionType, WildcardInfo
from .cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, card_sort_key, is_joker, sort_cards
from .patterns import Pattern, PatternType, detect_pattern
from .sequences import PAIR_STRAIGHT_WINDOWS, STEEL_PLATE_WINDOWS, STRAIGHT_WINDOWS
from .state import GameState


# Only the finite simulation API installs this cooperative generation budget.
# Ordinary engine and M9 calls retain their existing complete generation.
_simulation_budget: ContextVar[object | None] = ContextVar("simulation_budget", default=None)


_NON_JOKER_RANKS: tuple[str, ...] = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
_SUIT_ORDER: tuple[str, ...] = ("S", "H", "C", "D")
_PATTERN_SORT_ORDER: dict[str, int] = {
    "single": 0,
    "pair": 1,
    "triple": 2,
    "triple_with_pair": 3,
    "straight": 4,
    "pair_straight": 5,
    "steel_plate": 6,
    "bomb": 7,
    "straight_flush": 8,
    "joker_bomb": 9,
    "pass": 10,
}
_RANK_STRENGTH_BASE: dict[str, int] = {
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
    "2": 15,
    SMALL_JOKER_RANK: 17,
    BIG_JOKER_RANK: 18,
}


@dataclass(frozen=True, slots=True)
class PublicResponseRequirement:
    """Low-sensitivity summary of a generated response from explicit cards."""

    pattern_type: str
    card_count: int
    wildcard_count: int


@dataclass(frozen=True, slots=True)
class PublicResponseResourceCount:
    """Count of distinct physical carrier multisets for one response family."""

    pattern_type: str
    resource_count: int
    wildcard_resource_count: int


@dataclass(frozen=True, slots=True)
class PublicResponseSummary:
    """Rule-verified response requirements and resource counts for one lead."""

    requirements: tuple[PublicResponseRequirement, ...]
    resource_counts: tuple[PublicResponseResourceCount, ...]


@dataclass(frozen=True, slots=True)
class PublicStraightFlushResource:
    """One rule-generated straight-flush route from an explicit physical hand.

    This read-only resource description contains no action ID or game state and
    cannot be submitted to ``step``.  It lets AI-facing code compare what a
    public, explicit hand would still be able to construct after spending cards
    without duplicating wildcard or sequence rules.
    """

    suit: str
    rank_window: tuple[str, ...]
    carrier_cards: tuple[Card, ...]
    wildcard_count: int
    wildcard_declared_as: tuple[Card, ...]


def _validate_current_level_rank(current_level_rank: str) -> None:
    if current_level_rank not in {"2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"}:
        raise ValueError("current_level_rank must be one of 2-10,J,Q,K,A")


def _is_wildcard(card: Card, current_level_rank: str) -> bool:
    return card.rank == current_level_rank and card.suit == "H"


def _partner_id(player_id: int) -> int:
    return ((player_id + 1) % 4) + 1


def _next_player_ids(start_player_id: int, active_player_ids: Iterable[int]) -> tuple[int, ...]:
    active = tuple(active_player_ids)
    if not active:
        return ()
    ordered: list[int] = []
    current = start_player_id
    for _ in range(4):
        current = (current % 4) + 1
        if current in active:
            ordered.append(current)
    return tuple(ordered)


def _rank_strength(rank: str, current_level_rank: str) -> int:
    if rank == current_level_rank:
        return 16
    return _RANK_STRENGTH_BASE[rank]


def _pattern_signature(action: Action, current_level_rank: str) -> tuple[Pattern, int | None]:
    pattern = detect_pattern(action.declared_cards)
    if pattern.type == PatternType.UNKNOWN:
        raise ValueError("unsupported declared pattern")
    if action.declared_pattern != pattern.type:
        raise ValueError("declared pattern does not match declared cards")
    if pattern.type in {PatternType.SINGLE, PatternType.PAIR, PatternType.TRIPLE, PatternType.BOMB}:
        assert pattern.main_rank is not None
        return pattern, _rank_strength(pattern.main_rank, current_level_rank)
    if pattern.type == PatternType.TRIPLE_WITH_PAIR:
        assert pattern.main_rank is not None
        return pattern, _rank_strength(pattern.main_rank, current_level_rank)
    if pattern.type in {PatternType.STRAIGHT, PatternType.PAIR_STRAIGHT, PatternType.STEEL_PLATE, PatternType.STRAIGHT_FLUSH}:
        assert pattern.sequence_index is not None
        return pattern, pattern.sequence_index
    return pattern, None


def _bomb_cross_type_tier(pattern: Pattern) -> int:
    if pattern.type == PatternType.JOKER_BOMB:
        return 5
    if pattern.type == PatternType.BOMB:
        assert pattern.bomb_length is not None
        if pattern.bomb_length >= 6:
            return 4
        if pattern.bomb_length == 5:
            return 2
        return 1
    if pattern.type == PatternType.STRAIGHT_FLUSH:
        return 3
    return 0


def _can_same_type_beat(candidate: Pattern, candidate_value: int | None, leading: Pattern, leading_value: int | None) -> bool:
    if candidate.type != leading.type:
        return False
    if candidate.type == PatternType.BOMB:
        assert candidate.bomb_length is not None
        assert leading.bomb_length is not None
        if candidate.bomb_length != leading.bomb_length:
            return candidate.bomb_length > leading.bomb_length
        assert candidate_value is not None and leading_value is not None
        return candidate_value > leading_value
    if candidate.type == PatternType.JOKER_BOMB:
        return False
    if candidate.type in {PatternType.STRAIGHT, PatternType.PAIR_STRAIGHT, PatternType.STEEL_PLATE, PatternType.STRAIGHT_FLUSH}:
        if candidate.cards_count != leading.cards_count:
            return False
    assert candidate_value is not None and leading_value is not None
    return candidate_value > leading_value


def _can_beat_patterns(candidate: tuple[Pattern, int | None], leading: tuple[Pattern, int | None]) -> bool:
    candidate_pattern, candidate_value = candidate
    leading_pattern, leading_value = leading
    if _can_same_type_beat(candidate_pattern, candidate_value, leading_pattern, leading_value):
        return True
    candidate_tier = _bomb_cross_type_tier(candidate_pattern)
    return candidate_tier > 0 and candidate_tier > _bomb_cross_type_tier(leading_pattern)


def _public_declared_cards_for_group(rank: str, count: int) -> tuple[Card, ...]:
    return tuple(Card(rank=rank) for _ in range(count))


def _public_declared_cards_for_window(window: tuple[str, ...]) -> tuple[Card, ...]:
    return tuple(Card(rank=rank) for rank in window)


def _public_declared_cards_for_pair_window(window: tuple[str, ...]) -> tuple[Card, ...]:
    cards: list[Card] = []
    for rank in window:
        cards.extend((Card(rank=rank), Card(rank=rank)))
    return tuple(cards)


def _public_declared_cards_for_steel_window(window: tuple[str, ...]) -> tuple[Card, ...]:
    cards: list[Card] = []
    for rank in window:
        cards.extend((Card(rank=rank), Card(rank=rank), Card(rank=rank)))
    return tuple(cards)


def _make_action(
    *,
    player_id: int,
    declared_pattern: PatternType,
    declared_cards: tuple[Card, ...],
    carrier_cards: tuple[Card, ...],
    wildcard_info: tuple[WildcardInfo, ...] = (),
) -> Action:
    display_tokens = ",".join(card.rank if card.suit is None else f"{card.rank}{card.suit}" for card in declared_cards)
    return Action(
        player_id=player_id,
        action_type=ActionType.PLAY,
        declared_pattern=declared_pattern,
        declared_cards=declared_cards,
        carrier_cards=sort_cards(carrier_cards),
        wildcard_count=len(wildcard_info),
        wildcard_info=wildcard_info,
        display_text=f"{declared_pattern.value}:{display_tokens}",
    )


def _action_sort_key(action: Action) -> tuple[object, ...]:
    declared_pattern = action.declared_pattern.value if action.declared_pattern is not None else "pass"
    return (
        _PATTERN_SORT_ORDER.get(declared_pattern, 999),
        action.wildcard_count,
        tuple(card.rank for card in action.declared_cards),
        tuple(card_sort_key(card) for card in action.carrier_cards),
    )


def _action_dedupe_key(action: Action) -> tuple[object, ...]:
    return (
        action.action_type.value,
        action.declared_pattern.value if action.declared_pattern else None,
        tuple((card.rank, card.suit) for card in action.declared_cards),
        tuple((card.rank, card.suit) for card in action.carrier_cards),
        action.wildcard_count,
        tuple(
            (
                (item.carrier_card.rank, item.carrier_card.suit),
                (item.declared_as.rank, item.declared_as.suit),
            )
            for item in action.wildcard_info
        ),
    )


def _group_cards_by_rank(cards: tuple[Card, ...]) -> dict[str, list[Card]]:
    grouped: dict[str, list[Card]] = defaultdict(list)
    for card in sorted(cards, key=card_sort_key):
        grouped[card.rank].append(card)
    return grouped


def _group_cards_by_rank_and_suit(cards: tuple[Card, ...]) -> dict[tuple[str, str], list[Card]]:
    grouped: dict[tuple[str, str], list[Card]] = defaultdict(list)
    for card in sorted(cards, key=card_sort_key):
        if card.suit is None:
            continue
        grouped[(card.rank, card.suit)].append(card)
    return grouped


def _first_wildcard(cards: tuple[Card, ...], current_level_rank: str) -> Card | None:
    wildcards = sorted((card for card in cards if _is_wildcard(card, current_level_rank)), key=card_sort_key)
    return wildcards[0] if wildcards else None


def _declared_card_matches_carrier(
    carrier: Card,
    declared: Card,
    pattern: PatternType,
) -> bool:
    if pattern == PatternType.STRAIGHT_FLUSH:
        return (carrier.rank, carrier.suit) == (declared.rank, declared.suit)
    return carrier.rank == declared.rank


def _can_substitute_for(
    declared: Card,
    pattern: PatternType,
    current_level_rank: str,
) -> bool:
    if declared.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
        return False
    if pattern == PatternType.STRAIGHT_FLUSH:
        return (declared.rank, declared.suit) != (current_level_rank, "H")
    # The official claim permits a level-heart carrier to name another suit
    # of the same level rank; the adapter binds that virtual face away from H.
    return True


def _materialize_declared_actions(
    *,
    player_id: int,
    pattern: PatternType,
    declared_cards: tuple[Card, ...],
    hand_cards: tuple[Card, ...],
    current_level_rank: str,
    first_carrier_only: bool = False,
    stop_after_first: bool = False,
) -> list[Action]:
    """Bind one declared pattern to physical carriers with zero to two wilds.

    Natural matches and substitutions share the same position assignment, so
    two wildcards can fill different positions while another level-heart copy
    remains a natural card. Physical multiplicity is preserved by consuming
    each selected carrier before assigning the next declaration.
    """
    budget = _simulation_budget.get()
    if budget is not None:
        budget.check()
    if len(declared_cards) > len(hand_cards):
        return []
    wildcard = Card(rank=current_level_rank, suit="H")
    available_wildcards = hand_cards.count(wildcard)
    max_wildcards = min(2, available_wildcards, len(declared_cards))
    actions: dict[tuple[object, ...], Action] = {}
    # Reject impossible declarations before exploring position assignments.
    # Suit is part of a flush target; ordinary declarations only require rank.
    def target_key(card: Card) -> tuple[str, str | None]:
        return (card.rank, card.suit if pattern == PatternType.STRAIGHT_FLUSH else None)

    supply = Counter(target_key(card) for card in hand_cards)
    demand = Counter(target_key(card) for card in declared_cards)
    if sum(max(0, count - supply[key]) for key, count in demand.items()) > max_wildcards:
        return []
    ordered_hand = list(sort_cards(hand_cards))

    for wildcard_count in range(max_wildcards + 1):
        seen_targets: set[tuple[Card, ...]] = set()
        for wildcard_positions in combinations(range(len(declared_cards)), wildcard_count):
            substituted = tuple(declared_cards[index] for index in wildcard_positions)
            # Equal declared faces give identical metadata and natural demand.
            # Keep the first position assignment, preserving canonical order.
            if substituted in seen_targets:
                continue
            seen_targets.add(substituted)
            wildcard_position_set = set(wildcard_positions)
            if any(
                not _can_substitute_for(declared_cards[index], pattern, current_level_rank)
                for index in wildcard_positions
            ):
                continue

            natural_demand = demand.copy()
            natural_demand.subtract(target_key(card) for card in substituted)
            natural_supply = supply.copy()
            natural_supply[target_key(wildcard)] -= wildcard_count
            if any(count > natural_supply[key] for key, count in natural_demand.items()):
                continue

            remaining = ordered_hand.copy()
            selected_wildcards: list[Card] = []
            for _ in range(wildcard_count):
                try:
                    remaining.remove(wildcard)
                except ValueError:
                    selected_wildcards = []
                    break
                selected_wildcards.append(wildcard)
            if len(selected_wildcards) != wildcard_count:
                continue
            found_carrier = False

            def bind(
                position: int,
                available: list[Card],
                carriers: list[Card],
                wildcard_info: list[WildcardInfo],
                last_natural_by_target: dict[tuple[str, str | None], Card],
            ) -> None:
                nonlocal found_carrier
                if budget is not None:
                    budget.check()
                if first_carrier_only and found_carrier:
                    return
                if position == len(declared_cards):
                    if (
                        pattern == PatternType.STRAIGHT
                        and wildcard_count == 0
                        and len({card.suit for card in carriers}) == 1
                    ):
                        # Those exact physical faces are a straight flush and
                        # are emitted by its own canonical pattern generator.
                        return
                    action = _make_action(
                        player_id=player_id,
                        declared_pattern=pattern,
                        declared_cards=declared_cards,
                        carrier_cards=tuple(carriers),
                        wildcard_info=tuple(wildcard_info),
                    )
                    actions[_action_dedupe_key(action)] = action
                    found_carrier = True
                    return

                declared = declared_cards[position]
                if position in wildcard_position_set:
                    bind(
                        position + 1,
                        available,
                        carriers + [wildcard],
                        wildcard_info + [WildcardInfo(wildcard, declared)],
                        last_natural_by_target,
                    )
                    return

                target = (
                    declared.rank,
                    declared.suit if pattern == PatternType.STRAIGHT_FLUSH else None,
                )
                last = last_natural_by_target.get(target)
                matches = sorted(
                    {
                        card for card in available
                        if _declared_card_matches_carrier(card, declared, pattern)
                        and (last is None or card_sort_key(card) >= card_sort_key(last))
                    },
                    key=card_sort_key,
                )
                for match in matches:
                    next_available = available.copy()
                    next_available.remove(match)
                    next_last = last_natural_by_target.copy()
                    next_last[target] = match
                    bind(
                        position + 1,
                        next_available,
                        carriers + [match],
                        wildcard_info,
                        next_last,
                    )

            bind(0, remaining, [], [], {})
            if stop_after_first and actions:
                return list(actions.values())
    return list(actions.values())


def _pick_cards(cards: list[Card], count: int) -> tuple[Card, ...]:
    return tuple(sorted(cards[:count], key=card_sort_key))


def _card_key(card: Card) -> tuple[str, str | None]:
    return (card.rank, card.suit)


def _carrier_is_payable(action: Action, hand_cards: tuple[Card, ...]) -> bool:
    if action.action_type != ActionType.PLAY:
        return True
    hand_counter = Counter(_card_key(card) for card in hand_cards)
    carrier_counter = Counter(_card_key(card) for card in action.carrier_cards)
    return all(count <= hand_counter.get(key, 0) for key, count in carrier_counter.items())


def _public_resource_carriers(
    token_counts: Counter[tuple[str, str | None]],
    capacity: int,
    current_level_rank: str,
) -> Iterable[tuple[Card, ...]]:
    """Enumerate bounded carrier multisets for response resource families."""
    card_by_key = {
        key: Card(rank=key[0], suit=key[1])
        for key in token_counts
    }
    token_keys = tuple(sorted(
        card_by_key,
        key=lambda key: card_sort_key(card_by_key[key]),
    ))
    if capacity >= 1:
        for key in token_keys:
            yield (card_by_key[key],)
    if capacity >= 2:
        for first_index, first in enumerate(token_keys):
            for second in token_keys[first_index:]:
                if first == second and token_counts[first] < 2:
                    continue
                yield (card_by_key[first], card_by_key[second])

    by_rank: dict[str, list[Card]] = defaultdict(list)
    for key, count in token_counts.items():
        by_rank[key[0]].extend(card_by_key[key] for _ in range(count))
    if capacity >= 4:
        for rank in _NON_JOKER_RANKS:
            ranked_cards = tuple(sorted(by_rank.get(rank, ()), key=card_sort_key))
            for size in range(4, min(8, capacity, len(ranked_cards)) + 1):
                for subset in combinations(ranked_cards, size):
                    yield tuple(subset)

        wildcard_key = (current_level_rank, "H")
        wildcard = card_by_key.get(wildcard_key)
        if wildcard is not None:
            for rank in _NON_JOKER_RANKS:
                natural_cards = tuple(
                    card for card in by_rank.get(rank, ())
                    if not _is_wildcard(card, current_level_rank)
                )
                for wildcard_count in (1, 2):
                    if token_counts[wildcard_key] < wildcard_count:
                        continue
                    max_size = min(10, capacity, len(natural_cards) + wildcard_count)
                    for size in range(4, max_size + 1):
                        natural_count = size - wildcard_count
                        if natural_count < 1:
                            continue
                        for subset in combinations(natural_cards, natural_count):
                            yield tuple(subset) + (wildcard,) * wildcard_count

        if (
            token_counts.get((SMALL_JOKER_RANK, None), 0) >= 2
            and token_counts.get((BIG_JOKER_RANK, None), 0) >= 2
        ):
            yield (
                Card(rank=SMALL_JOKER_RANK), Card(rank=SMALL_JOKER_RANK),
                Card(rank=BIG_JOKER_RANK), Card(rank=BIG_JOKER_RANK),
            )

    if capacity >= 5:
        wildcard_key = (current_level_rank, "H")
        wildcard_card = card_by_key.get(wildcard_key)
        for suit in _SUIT_ORDER:
            for window in STRAIGHT_WINDOWS:
                target_keys = tuple((rank, suit) for rank in window)
                for wildcard_count in range(3):
                    if wildcard_count > token_counts.get(wildcard_key, 0):
                        continue
                    if wildcard_count and wildcard_card is None:
                        continue
                    for positions in combinations(range(5), wildcard_count):
                        if any(target_keys[position] == wildcard_key for position in positions):
                            continue
                        needed = Counter(
                            target_keys[position]
                            for position in range(5)
                            if position not in positions
                        )
                        if any(count > token_counts.get(key, 0) for key, count in needed.items()):
                            continue
                        if needed.get(wildcard_key, 0) + wildcard_count > token_counts.get(wildcard_key, 0):
                            continue
                        carrier = tuple(
                            card_by_key[key]
                            for key, count in sorted(
                                needed.items(),
                                key=lambda item: card_sort_key(card_by_key[item[0]]),
                            )
                            for _ in range(count)
                        ) + ((wildcard_card,) * wildcard_count if wildcard_count else ())
                        yield carrier


def _resource_response_actions(
    engine: "BaseRuleEngine",
    player_id: int,
    carriers: tuple[Card, ...],
    current_level_rank: str,
    extra_patterns: tuple[str, ...] = (),
    *,
    include_resource_families: bool = True,
) -> tuple[Action, ...]:
    """Generate counted families plus the requested same-shape family."""
    count = len(carriers)
    generated: list[Action] = []
    families = {
        PatternType.SINGLE,
        PatternType.PAIR,
        PatternType.BOMB,
        PatternType.STRAIGHT_FLUSH,
        PatternType.JOKER_BOMB,
    } if include_resource_families else set()
    families.update(PatternType(pattern) for pattern in extra_patterns)
    wildcard_face = (current_level_rank, "H")
    natural_ranks = {
        card.rank for card in carriers
        if card.rank not in {SMALL_JOKER_RANK, BIG_JOKER_RANK}
        and (card.rank, card.suit) != wildcard_face
    }
    group_ranks = (
        tuple(natural_ranks) if len(natural_ranks) == 1
        else _NON_JOKER_RANKS if not natural_ranks
        else ()
    )

    if PatternType.SINGLE in families and count == 1:
        generated.extend(engine._generate_single_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    for family in (PatternType.PAIR, PatternType.TRIPLE):
        if family not in families or count != {PatternType.PAIR: 2, PatternType.TRIPLE: 3}[family]:
            continue
        for rank in group_ranks:
            declared = _public_declared_cards_for_group(rank, count)
            generated.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=family,
                declared_cards=declared,
                hand_cards=carriers,
                current_level_rank=current_level_rank,
                first_carrier_only=True,
            ))
        if family == PatternType.PAIR:
            for rank in (SMALL_JOKER_RANK, BIG_JOKER_RANK):
                declared = _public_declared_cards_for_group(rank, count)
                generated.extend(_materialize_declared_actions(
                    player_id=player_id,
                    pattern=family,
                    declared_cards=declared,
                    hand_cards=carriers,
                    current_level_rank=current_level_rank,
                    first_carrier_only=True,
                ))
    if PatternType.BOMB in families and 4 <= count <= 10:
        for rank in group_ranks:
            declared = _public_declared_cards_for_group(rank, count)
            generated.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=PatternType.BOMB,
                declared_cards=declared,
                hand_cards=carriers,
                current_level_rank=current_level_rank,
                first_carrier_only=True,
            ))
    if PatternType.JOKER_BOMB in families and count == 4:
        declared = (
            Card(rank=SMALL_JOKER_RANK), Card(rank=SMALL_JOKER_RANK),
            Card(rank=BIG_JOKER_RANK), Card(rank=BIG_JOKER_RANK),
        )
        generated.extend(_materialize_declared_actions(
            player_id=player_id,
            pattern=PatternType.JOKER_BOMB,
            declared_cards=declared,
            hand_cards=carriers,
            current_level_rank=current_level_rank,
            first_carrier_only=True,
        ))

    if PatternType.TRIPLE_WITH_PAIR in families and count == 5:
        generated.extend(engine._generate_triple_with_pair_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    if PatternType.STRAIGHT in families and count == 5:
        generated.extend(engine._generate_straight_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    if PatternType.PAIR_STRAIGHT in families and count == 6:
        generated.extend(engine._generate_pair_straight_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    if PatternType.STEEL_PLATE in families and count == 6:
        generated.extend(engine._generate_steel_plate_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    if PatternType.STRAIGHT_FLUSH in families and count == 5:
        generated.extend(engine._generate_straight_flush_actions(
            player_id, carriers, current_level_rank, first_carrier_only=True,
        ))
    expected = Counter(_card_key(card) for card in carriers)
    return tuple(
        action for action in generated
        if action.declared_pattern is not None
        and Counter(_card_key(card) for card in action.carrier_cards) == expected
    )


class BaseRuleEngine:
    def detect_pattern(self, cards: tuple[Card, ...]) -> Pattern:
        return detect_pattern(cards)

    def public_action_bindings(
        self,
        player_id: int,
        declared_pattern: PatternType,
        declared_cards: tuple[Card, ...],
        carrier_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
        first_binding_only: bool = False,
    ) -> tuple[Action, ...]:
        """Return rule-generated bindings for one public action description.

        Histories may expose the declared faces and physical carriers without
        wildcard metadata. This read-only query reconstructs only bindings the
        same canonical generator can produce; it does not create a playable
        action ID or consult hidden state.
        """
        _validate_current_level_rank(current_level_rank)
        if (
            declared_pattern in {PatternType.PASS, PatternType.UNKNOWN}
            or not declared_cards
            or len(declared_cards) != len(carrier_cards)
            or detect_pattern(declared_cards).type != declared_pattern
        ):
            return ()
        physical_counts: Counter[tuple[str, str | None]] = Counter()
        for card in carrier_cards:
            normal = card.rank in _NON_JOKER_RANKS and card.suit in _SUIT_ORDER
            joker = card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and card.suit is None
            if not (normal or joker):
                return ()
            physical_counts[_card_key(card)] += 1
            if physical_counts[_card_key(card)] > 2:
                return ()
        bindings = _materialize_declared_actions(
            player_id=player_id,
            pattern=declared_pattern,
            declared_cards=declared_cards,
            hand_cards=carrier_cards,
            current_level_rank=current_level_rank,
            first_carrier_only=first_carrier_only,
            stop_after_first=first_binding_only,
        )
        requested = Counter(_card_key(card) for card in carrier_cards)
        return tuple(
            action for action in bindings
            if Counter(_card_key(card) for card in action.carrier_cards) == requested
        )

    def public_straight_flush_resources(
        self,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> tuple[PublicStraightFlushResource, ...]:
        """Return rule-generated straight-flush resources for an explicit hand.

        The returned objects are resource facts, not canonical actions: they
        have no player, action ID, or state-transition capability.  Generation
        remains delegated to the same engine routine used by legal actions, so
        wildcard completion and sequence boundaries stay aligned with the
        rules of the current profile.
        """

        _validate_current_level_rank(current_level_rank)
        if not isinstance(hand_cards, tuple):
            raise ValueError("hand_cards must be a tuple of physical cards")

        counts: Counter[tuple[str, str | None]] = Counter()
        for card in hand_cards:
            if not isinstance(card, Card):
                raise ValueError("hand_cards must contain physical Card values")
            is_normal = card.rank in _NON_JOKER_RANKS and card.suit in _SUIT_ORDER
            is_joker_card = card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and card.suit is None
            if not (is_normal or is_joker_card):
                raise ValueError("hand_cards must contain physical cards")
            key = (card.rank, card.suit)
            counts[key] += 1
            if counts[key] > 2:
                raise ValueError("hand_cards exceeds the double-deck token pool")

        generated = self._generate_straight_flush_actions(
            player_id=0,
            hand_cards=hand_cards,
            current_level_rank=current_level_rank,
        )
        resources: dict[tuple[object, ...], PublicStraightFlushResource] = {}
        for action in generated:
            declared_suits = {card.suit for card in action.declared_cards}
            if len(declared_suits) != 1:
                continue
            suit = next(iter(declared_suits))
            if suit not in _SUIT_ORDER or len(action.declared_cards) != 5:
                continue
            key = (
                suit,
                tuple(card.rank for card in action.declared_cards),
                tuple((card.rank, card.suit) for card in action.carrier_cards),
                action.wildcard_count,
                tuple(
                    (item.declared_as.rank, item.declared_as.suit)
                    for item in action.wildcard_info
                ),
            )
            resources[key] = PublicStraightFlushResource(
                suit=suit,
                rank_window=tuple(card.rank for card in action.declared_cards),
                carrier_cards=action.carrier_cards,
                wildcard_count=action.wildcard_count,
                wildcard_declared_as=tuple(item.declared_as for item in action.wildcard_info),
            )

        return tuple(
            resources[key]
            for key in sorted(
                resources,
                key=lambda item: (
                    _SUIT_ORDER.index(str(item[0])),
                    tuple(_RANK_STRENGTH_BASE.get(str(rank), 0) for rank in item[1]),
                    int(item[3]),
                    item[4],
                    item[2],
                ),
            )
        )

    def public_beating_pattern_types(
        self,
        hand_cards: tuple[Card, ...],
        leading_action: Action,
        current_level_rank: str,
    ) -> tuple[str, ...]:
        """Summarize which pattern families in an explicit hand can beat a play.

        This read-only query exposes no generated action, action ID, or state. It
        is intended for consumers that have a uniquely confirmed public hand.
        All pattern generation and comparison still use the engine's rule truth.
        """
        requirements = self.public_beating_response_requirements(
            hand_cards, leading_action, current_level_rank,
        )
        beating = {item.pattern_type for item in requirements}
        return tuple(pattern for pattern in _PATTERN_SORT_ORDER if pattern in beating)

    def public_beating_response_requirements(
        self,
        available_cards: tuple[Card, ...],
        leading_action: Action,
        current_level_rank: str,
    ) -> tuple[PublicResponseRequirement, ...]:
        """Return rule-verified response families and physical card counts.

        ``available_cards`` may be an explicitly known hand or a public pool of
        cards whose owner is unknown. The result contains no card identities,
        generated action, action ID, or game state. Every included response is
        generated and compared by the engine, including ordinary bombs, flush
        bombs, joker bombs, and wildcard declarations.
        """
        _validate_current_level_rank(current_level_rank)
        if leading_action.action_type != ActionType.PLAY:
            return ()

        player_id = leading_action.player_id
        candidates: list[Action] = []
        candidates.extend(self._generate_single_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_group_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_triple_with_pair_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_straight_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_pair_straight_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_steel_plate_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))
        candidates.extend(self._generate_straight_flush_actions(
            player_id, available_cards, current_level_rank, first_carrier_only=True,
        ))

        requirements = {
            PublicResponseRequirement(
                pattern_type=action.declared_pattern.value,
                card_count=len(action.carrier_cards),
                wildcard_count=action.wildcard_count,
            )
            for action in candidates
            if action.declared_pattern is not None
            and _carrier_is_payable(action, available_cards)
            and self.can_beat(action, leading_action, current_level_rank)
        }
        return tuple(sorted(
            requirements,
            key=lambda item: (
                _PATTERN_SORT_ORDER.get(item.pattern_type, 99),
                item.card_count,
                item.wildcard_count,
            ),
        ))

    def public_beating_response_resource_counts(
        self,
        available_cards: tuple[Card, ...],
        leading_action: Action,
        current_level_rank: str,
        *,
        max_cards: int | None = None,
    ) -> tuple[PublicResponseResourceCount, ...]:
        """Count distinct rule-valid response carriers within the card capacity.

        For a public possible-card domain, counts are feasible upper bounds.
        Each physical face multiset is counted once even when it supports
        multiple wildcard declarations or straight-flush windows.
        """
        _validate_current_level_rank(current_level_rank)
        if leading_action.action_type != ActionType.PLAY:
            return ()
        capacity = len(available_cards) if max_cards is None else max_cards
        if type(capacity) is not int or capacity < 0:
            raise ValueError("max_cards must be a non-negative integer")
        capacity = min(capacity, len(available_cards))
        if capacity == 0:
            return ()

        counts: Counter[tuple[str, str | None]] = Counter()
        for card in available_cards:
            is_normal = card.rank in _NON_JOKER_RANKS and card.suit in _SUIT_ORDER
            is_joker_card = card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and card.suit is None
            if not (is_normal or is_joker_card):
                raise ValueError("available_cards must contain physical cards")
            counts[(card.rank, card.suit)] += 1
            if counts[(card.rank, card.suit)] > 2:
                raise ValueError("available_cards exceeds the double-deck token pool")

        def carrier_key(cards: tuple[Card, ...]) -> tuple[tuple[str, str | None], ...]:
            return tuple((card.rank, card.suit) for card in sort_cards(cards))

        families_by_carrier: dict[tuple[tuple[str, str | None], ...], set[str]] = defaultdict(set)
        wildcard_families_by_carrier: dict[tuple[tuple[str, str | None], ...], set[str]] = defaultdict(set)
        visited: set[tuple[tuple[str, str | None], ...]] = set()
        player_id = leading_action.player_id

        for cards in _public_resource_carriers(counts, capacity, current_level_rank):
            if len(cards) > capacity:
                continue
            key = carrier_key(cards)
            if key in visited:
                continue
            visited.add(key)

            for response in _resource_response_actions(
                self,
                player_id,
                cards,
                current_level_rank,
                extra_patterns=(leading_action.declared_pattern.value,),
            ):
                if (
                    response.declared_pattern is None
                    or carrier_key(response.carrier_cards) != key
                    or not self.can_beat(response, leading_action, current_level_rank)
                ):
                    continue
                family = response.declared_pattern.value
                if family not in {
                    "single", "pair", "bomb", "straight_flush", "joker_bomb",
                    leading_action.declared_pattern.value,
                }:
                    continue
                families_by_carrier[key].add(family)
                if response.wildcard_count:
                    wildcard_families_by_carrier[key].add(family)

        leading_pattern = (
            leading_action.declared_pattern.value
            if leading_action.declared_pattern is not None else ""
        )
        category_sets: dict[str, set[tuple[tuple[str, str | None], ...]]] = defaultdict(set)
        wildcard_sets: dict[str, set[tuple[tuple[str, str | None], ...]]] = defaultdict(set)
        for key, families in families_by_carrier.items():
            category = next((
                family for family in (
                    "joker_bomb", "straight_flush", "bomb", leading_pattern, "single", "pair",
                )
                if family in families
            ), None)
            if category not in {
                "single", "pair", "bomb", "straight_flush", "joker_bomb",
                leading_pattern,
            }:
                continue
            category_sets[category].add(key)
            if wildcard_families_by_carrier.get(key):
                wildcard_sets[category].add(key)

        return tuple(
            PublicResponseResourceCount(
                pattern_type=family,
                resource_count=len(category_sets[family]),
                wildcard_resource_count=len(wildcard_sets[family]),
            )
            for family in _PATTERN_SORT_ORDER
            if category_sets.get(family)
        )

    def public_beating_response_summaries(
        self,
        available_cards: tuple[Card, ...],
        leading_actions: tuple[Action, ...],
        current_level_rank: str,
        *,
        max_cards: int | None = None,
    ) -> tuple[PublicResponseSummary, ...]:
        """Summarize many possible leads after generating one response catalog.

        The candidate responses are generated only from ``available_cards``.
        For every lead, response requirements retain the full card-domain view;
        resource counts additionally obey ``max_cards``. The catalog exists only
        for this call and contains no game state or hidden-card access.
        """
        _validate_current_level_rank(current_level_rank)
        leads = tuple(leading_actions)
        capacity = len(available_cards) if max_cards is None else max_cards
        if type(capacity) is not int or capacity < 0:
            raise ValueError("max_cards must be a non-negative integer")
        capacity = min(capacity, len(available_cards))

        token_counts: Counter[tuple[str, str | None]] = Counter()
        for card in available_cards:
            is_normal = card.rank in _NON_JOKER_RANKS and card.suit in {"S", "H", "C", "D"}
            is_joker_card = card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and card.suit is None
            if not (is_normal or is_joker_card):
                raise ValueError("available_cards must contain physical cards")
            token_counts[(card.rank, card.suit)] += 1
            if token_counts[(card.rank, card.suit)] > 2:
                raise ValueError("available_cards exceeds the double-deck token pool")

        player_ids = {
            lead.player_id for lead in leads
            if lead.action_type == ActionType.PLAY and lead.declared_pattern is not None
        }
        if not player_ids or not available_cards:
            return tuple(PublicResponseSummary((), ()) for _ in leads)

        def carrier_key(cards: tuple[Card, ...]) -> tuple[tuple[str, str | None], ...]:
            return tuple((card.rank, card.suit) for card in sort_cards(cards))

        # A GuanDan lead is always made by one player. Keeping catalogs keyed by
        # player also makes this read-only API safe for mixed-player callers.
        candidates_by_player: dict[int, dict[str, list[Action]]] = {}
        resource_candidates_by_player: dict[int, dict[str, list[Action]]] = {}
        leading_patterns_by_player: dict[int, tuple[str, ...]] = {}
        for player_id in player_ids:
            leading_patterns_by_player[player_id] = tuple(sorted({
                lead.declared_pattern.value for lead in leads
                if lead.player_id == player_id
                and lead.action_type == ActionType.PLAY
                and lead.declared_pattern is not None
            }))
            generated: list[Action] = []
            generated.extend(self._generate_single_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_group_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_triple_with_pair_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_straight_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_pair_straight_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_steel_plate_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))
            generated.extend(self._generate_straight_flush_actions(
                player_id, available_cards, current_level_rank, first_carrier_only=True,
            ))

            by_pattern: dict[str, list[Action]] = defaultdict(list)
            seen_actions: set[tuple[object, ...]] = set()
            for response in generated:
                if response.declared_pattern is None or not _carrier_is_payable(response, available_cards):
                    continue
                carrier = tuple(
                    (card.rank, card.suit) for card in sort_cards(response.carrier_cards)
                )
                declared = tuple((card.rank, card.suit) for card in response.declared_cards)
                action_key = (
                    response.declared_pattern.value,
                    carrier,
                    declared,
                    response.wildcard_count,
                )
                if action_key in seen_actions:
                    continue
                seen_actions.add(action_key)
                by_pattern[response.declared_pattern.value].append(response)
            candidates_by_player[player_id] = by_pattern

            # Enumerate one bounded carrier catalog from the public pool; all
            # lead summaries below reuse these rule-generated response routes.
            resource_by_pattern: dict[str, list[Action]] = defaultdict(list)
            visited_carriers: set[tuple[tuple[str, str | None], ...]] = set()
            seen_resource_actions: set[tuple[object, ...]] = set()

            for cards in _public_resource_carriers(token_counts, capacity, current_level_rank):
                if len(cards) > capacity:
                    continue
                carrier = carrier_key(cards)
                if carrier in visited_carriers:
                    continue
                visited_carriers.add(carrier)

                for response in _resource_response_actions(
                    self,
                    player_id,
                    cards,
                    current_level_rank,
                    extra_patterns=tuple(
                        pattern for pattern in leading_patterns_by_player[player_id]
                        if pattern not in {"single", "pair", "bomb", "straight_flush", "joker_bomb"}
                    ),
                    include_resource_families=False,
                ):
                    if (
                        response.declared_pattern is None
                        or carrier_key(response.carrier_cards) != carrier
                    ):
                        continue
                    family = response.declared_pattern.value
                    if family not in {
                        "single", "pair", "bomb", "straight_flush", "joker_bomb",
                        *leading_patterns_by_player[player_id],
                    }:
                        continue
                    declared = tuple((card.rank, card.suit) for card in response.declared_cards)
                    wildcard_info = tuple(
                        (
                            (item.carrier_card.rank, item.carrier_card.suit),
                            (item.declared_as.rank, item.declared_as.suit),
                        )
                        for item in response.wildcard_info
                    )
                    action_key = (family, carrier, declared, response.wildcard_count, wildcard_info)
                    if action_key in seen_resource_actions:
                        continue
                    seen_resource_actions.add(action_key)
                    resource_by_pattern[family].append(response)
            # Bind declarations once against the full explicit pool instead of
            # binding every window again against every possible carrier. Keep
            # the original bounded carrier domain and count classification.
            resource_generated = [
                *self._generate_single_actions(player_id, available_cards, current_level_rank),
                *self._generate_group_actions(player_id, available_cards, current_level_rank),
                *self._generate_straight_flush_actions(player_id, available_cards, current_level_rank),
            ]
            for response in resource_generated:
                if response.declared_pattern not in {
                    PatternType.SINGLE, PatternType.PAIR, PatternType.BOMB,
                    PatternType.STRAIGHT_FLUSH, PatternType.JOKER_BOMB,
                }:
                    continue
                if carrier_key(response.carrier_cards) in visited_carriers:
                    resource_by_pattern[response.declared_pattern.value].append(response)
            resource_candidates_by_player[player_id] = resource_by_pattern

        resource_families = {"single", "pair", "bomb", "straight_flush", "joker_bomb"}
        summaries_by_lead: dict[tuple[object, ...], PublicResponseSummary] = {}
        signatures: dict[tuple[object, ...], tuple[Pattern, int | None] | None] = {}

        def signature(action: Action) -> tuple[Pattern, int | None] | None:
            key = (action.declared_pattern, action.declared_cards)
            if key not in signatures:
                try:
                    signatures[key] = _pattern_signature(action, current_level_rank)
                except ValueError:
                    signatures[key] = None
            return signatures[key]

        def beats(candidate: Action, lead: Action) -> bool:
            candidate_signature, lead_signature = signature(candidate), signature(lead)
            return (candidate_signature is not None and lead_signature is not None
                    and _can_beat_patterns(candidate_signature, lead_signature))

        def lead_key(lead: Action) -> tuple[object, ...]:
            # Response feasibility depends on the rule comparison value, not
            # the lead's physical suit, carrier or wildcard assignment.
            detected = signature(lead)
            comparison_key = None
            if detected is not None:
                pattern, value = detected
                comparison_key = (pattern.type, pattern.cards_count, pattern.bomb_length, value)
            return (
                lead.player_id,
                lead.action_type,
                comparison_key,
            )

        def summarize(lead: Action) -> PublicResponseSummary:
            if lead.action_type != ActionType.PLAY or lead.declared_pattern is None:
                return PublicResponseSummary((), ())
            key = lead_key(lead)
            cached = summaries_by_lead.get(key)
            if cached is not None:
                return cached

            leading_pattern = lead.declared_pattern.value
            if leading_pattern == "joker_bomb":
                possible_patterns: tuple[str, ...] = ()
            elif leading_pattern in {"bomb", "straight_flush"}:
                possible_patterns = ("bomb", "straight_flush", "joker_bomb")
            else:
                possible_patterns = (
                    leading_pattern, "bomb", "straight_flush", "joker_bomb",
                )
            by_pattern = candidates_by_player.get(lead.player_id, {})
            resource_by_pattern = resource_candidates_by_player.get(lead.player_id, {})
            requirements: set[PublicResponseRequirement] = set()
            families_by_carrier: dict[
                tuple[tuple[str, str | None], ...], set[str]
            ] = defaultdict(set)
            wildcard_families_by_carrier: dict[
                tuple[tuple[str, str | None], ...], set[str]
            ] = defaultdict(set)

            for pattern in possible_patterns:
                for response in by_pattern.get(pattern, ()):
                    if not beats(response, lead):
                        continue
                    family = response.declared_pattern.value
                    requirements.add(PublicResponseRequirement(
                        pattern_type=family,
                        card_count=len(response.carrier_cards),
                        wildcard_count=response.wildcard_count,
                    ))
            for pattern in possible_patterns:
                for response in resource_by_pattern.get(pattern, ()):
                    if not beats(response, lead):
                        continue
                    family = response.declared_pattern.value
                    carrier = tuple(
                        (card.rank, card.suit) for card in sort_cards(response.carrier_cards)
                    )
                    families_by_carrier[carrier].add(family)
                    if response.wildcard_count:
                        wildcard_families_by_carrier[carrier].add(family)

            ordered_requirements = tuple(sorted(
                requirements,
                key=lambda item: (
                    _PATTERN_SORT_ORDER.get(item.pattern_type, 99),
                    item.card_count,
                    item.wildcard_count,
                ),
            ))
            category_sets: dict[str, set[tuple[tuple[str, str | None], ...]]] = defaultdict(set)
            wildcard_sets: dict[str, set[tuple[tuple[str, str | None], ...]]] = defaultdict(set)
            for carrier, families in families_by_carrier.items():
                category = next((
                    family for family in (
                        "joker_bomb", "straight_flush", "bomb", leading_pattern, "single", "pair",
                    )
                    if family in families
                ), None)
                if category not in resource_families | {leading_pattern}:
                    continue
                category_sets[category].add(carrier)
                if wildcard_families_by_carrier.get(carrier):
                    wildcard_sets[category].add(carrier)

            resources = tuple(
                PublicResponseResourceCount(
                    pattern_type=family,
                    resource_count=len(category_sets[family]),
                    wildcard_resource_count=len(wildcard_sets[family]),
                )
                for family in _PATTERN_SORT_ORDER
                if category_sets.get(family)
            )
            summary = PublicResponseSummary(ordered_requirements, resources)
            summaries_by_lead[key] = summary
            return summary

        return tuple(summarize(lead) for lead in leads)

    def can_beat(self, candidate: Action, leading_action: Action, current_level_rank: str) -> bool:
        _validate_current_level_rank(current_level_rank)
        if candidate.action_type != ActionType.PLAY or leading_action.action_type != ActionType.PLAY:
            return False
        try:
            candidate_pattern, candidate_value = _pattern_signature(candidate, current_level_rank)
            leading_pattern, leading_value = _pattern_signature(leading_action, current_level_rank)
        except ValueError:
            return False

        return _can_beat_patterns((candidate_pattern, candidate_value), (leading_pattern, leading_value))

    def _generate_single_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions = [
            _make_action(
                player_id=player_id,
                declared_pattern=PatternType.SINGLE,
                declared_cards=(Card(rank=card.rank),),
                carrier_cards=(card,),
            )
            for card in sort_cards(hand_cards)
        ]
        if any(_is_wildcard(card, current_level_rank) for card in hand_cards):
            for rank in _NON_JOKER_RANKS:
                actions.extend(
                    action
                    for action in _materialize_declared_actions(
                        player_id=player_id,
                        pattern=PatternType.SINGLE,
                        declared_cards=(Card(rank=rank),),
                        hand_cards=hand_cards,
                        current_level_rank=current_level_rank,
                        first_carrier_only=first_carrier_only,
                    )
                    if action.wildcard_count
                )
        return actions

    def _generate_group_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        counts = Counter(card.rank for card in hand_cards)
        wildcards = min(2, sum(_is_wildcard(card, current_level_rank) for card in hand_cards))
        for rank in _NON_JOKER_RANKS:
            for pattern, count in (
                (PatternType.PAIR, 2),
                (PatternType.TRIPLE, 3),
            ):
                if counts[rank] + wildcards < count:
                    continue
                declared = _public_declared_cards_for_group(rank, count)
                actions.extend(_materialize_declared_actions(
                    player_id=player_id,
                    pattern=pattern,
                    declared_cards=declared,
                    hand_cards=hand_cards,
                    current_level_rank=current_level_rank,
                    first_carrier_only=first_carrier_only,
                ))
            for count in range(4, 11):
                if counts[rank] + wildcards < count:
                    continue
                declared = _public_declared_cards_for_group(rank, count)
                actions.extend(_materialize_declared_actions(
                    player_id=player_id,
                    pattern=PatternType.BOMB,
                    declared_cards=declared,
                    hand_cards=hand_cards,
                    current_level_rank=current_level_rank,
                    first_carrier_only=first_carrier_only,
                ))

        for joker_rank in (SMALL_JOKER_RANK, BIG_JOKER_RANK):
            declared = _public_declared_cards_for_group(joker_rank, 2)
            actions.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=PatternType.PAIR,
                declared_cards=declared,
                hand_cards=hand_cards,
                current_level_rank=current_level_rank,
                first_carrier_only=first_carrier_only,
            ))

        joker_bomb = (
            Card(rank=SMALL_JOKER_RANK),
            Card(rank=SMALL_JOKER_RANK),
            Card(rank=BIG_JOKER_RANK),
            Card(rank=BIG_JOKER_RANK),
        )
        actions.extend(_materialize_declared_actions(
            player_id=player_id,
            pattern=PatternType.JOKER_BOMB,
            declared_cards=joker_bomb,
            hand_cards=hand_cards,
            current_level_rank=current_level_rank,
            first_carrier_only=first_carrier_only,
        ))
        return actions

    def _generate_triple_with_pair_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        counts = Counter(card.rank for card in hand_cards)
        wildcards = min(2, sum(_is_wildcard(card, current_level_rank) for card in hand_cards))
        pair_ranks = (*_NON_JOKER_RANKS, SMALL_JOKER_RANK, BIG_JOKER_RANK)
        for triple_rank in _NON_JOKER_RANKS:
            if counts[triple_rank] + wildcards < 3:
                continue
            for pair_rank in pair_ranks:
                if pair_rank == triple_rank:
                    continue
                allowance = 0 if pair_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} else wildcards
                if counts[pair_rank] + allowance < 2:
                    continue
                if max(0, 3 - counts[triple_rank]) + max(0, 2 - counts[pair_rank]) > wildcards:
                    continue
                declared = (
                    Card(rank=triple_rank),
                    Card(rank=triple_rank),
                    Card(rank=triple_rank),
                    Card(rank=pair_rank),
                    Card(rank=pair_rank),
                )
                actions.extend(_materialize_declared_actions(
                    player_id=player_id,
                    pattern=PatternType.TRIPLE_WITH_PAIR,
                    declared_cards=declared,
                    hand_cards=hand_cards,
                    current_level_rank=current_level_rank,
                    first_carrier_only=first_carrier_only,
                ))
        return actions

    def _generate_straight_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        for window in STRAIGHT_WINDOWS:
            declared = _public_declared_cards_for_window(window)
            actions.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=PatternType.STRAIGHT,
                declared_cards=declared,
                hand_cards=hand_cards,
                current_level_rank=current_level_rank,
                first_carrier_only=first_carrier_only,
            ))
        return actions

    def _generate_pair_straight_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        for window in PAIR_STRAIGHT_WINDOWS:
            declared = _public_declared_cards_for_pair_window(window)
            actions.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=PatternType.PAIR_STRAIGHT,
                declared_cards=declared,
                hand_cards=hand_cards,
                current_level_rank=current_level_rank,
                first_carrier_only=first_carrier_only,
            ))
        return actions

    def _generate_steel_plate_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        for window in STEEL_PLATE_WINDOWS:
            declared = _public_declared_cards_for_steel_window(window)
            actions.extend(_materialize_declared_actions(
                player_id=player_id,
                pattern=PatternType.STEEL_PLATE,
                declared_cards=declared,
                hand_cards=hand_cards,
                current_level_rank=current_level_rank,
                first_carrier_only=first_carrier_only,
            ))
        return actions

    def _generate_straight_flush_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
        *,
        first_carrier_only: bool = False,
    ) -> list[Action]:
        actions: list[Action] = []
        for suit in _SUIT_ORDER:
            for window in STRAIGHT_WINDOWS:
                declared = tuple(Card(rank=rank, suit=suit) for rank in window)
                actions.extend(_materialize_declared_actions(
                    player_id=player_id,
                    pattern=PatternType.STRAIGHT_FLUSH,
                    declared_cards=declared,
                    hand_cards=hand_cards,
                    current_level_rank=current_level_rank,
                    first_carrier_only=first_carrier_only,
                ))
        return actions

    def generate_legal_actions(self, state: GameState) -> tuple[Action, ...]:
        _validate_current_level_rank(state.current_level_rank)
        if state.is_finished:
            return ()

        player = state.get_player(state.current_player_id)
        if player.is_finished:
            return ()

        actions = []
        actions.extend(self._generate_single_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_group_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_triple_with_pair_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_straight_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_pair_straight_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_steel_plate_actions(player.player_id, player.hand_cards, state.current_level_rank))
        actions.extend(self._generate_straight_flush_actions(player.player_id, player.hand_cards, state.current_level_rank))

        deduped: dict[tuple[object, ...], Action] = {}
        for action in actions:
            if detect_pattern(action.declared_cards).type != action.declared_pattern:
                continue
            deduped[_action_dedupe_key(action)] = action

        # Safety: never expose actions that cannot be executed from the real hand.
        deduped = {
            key: action
            for key, action in deduped.items()
            if _carrier_is_payable(action, player.hand_cards)
        }

        leading_action = state.table_constraint.leading_action
        if leading_action is None:
            return tuple(sorted(deduped.values(), key=_action_sort_key))

        legal_follow = [
            action
            for action in deduped.values()
            if self.can_beat(action, leading_action, state.current_level_rank)
        ]
        legal_follow.append(Action.make_pass(player.player_id))
        return tuple(sorted(legal_follow, key=_action_sort_key))
