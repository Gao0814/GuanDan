"""Rules and legal-action generation for the single-game GuanDan mainline."""

from collections import Counter, defaultdict
from itertools import combinations
from typing import Iterable

from .actions import Action, ActionType, WildcardInfo
from .cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, card_sort_key, is_joker, sort_cards
from .patterns import Pattern, PatternType, detect_pattern
from .state import GameState


_NON_JOKER_RANKS: tuple[str, ...] = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
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


def _pick_cards(cards: list[Card], count: int) -> tuple[Card, ...]:
    return tuple(sorted(cards[:count], key=card_sort_key))


class BaseRuleEngine:
    def detect_pattern(self, cards: tuple[Card, ...]) -> Pattern:
        return detect_pattern(cards)

    def can_beat(self, candidate: Action, leading_action: Action, current_level_rank: str) -> bool:
        _validate_current_level_rank(current_level_rank)
        if candidate.action_type != ActionType.PLAY or leading_action.action_type != ActionType.PLAY:
            return False
        try:
            candidate_pattern, candidate_value = _pattern_signature(candidate, current_level_rank)
            leading_pattern, leading_value = _pattern_signature(leading_action, current_level_rank)
        except ValueError:
            return False

        if _can_same_type_beat(candidate_pattern, candidate_value, leading_pattern, leading_value):
            return True

        leading_tier = _bomb_cross_type_tier(leading_pattern)
        candidate_tier = _bomb_cross_type_tier(candidate_pattern)
        if candidate_tier == 0:
            return False
        return candidate_tier > leading_tier

    def _generate_single_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        wildcard = _first_wildcard(hand_cards, current_level_rank)
        for card in sort_cards(hand_cards):
            if is_joker(card):
                declared_cards = (Card(rank=card.rank),)
            else:
                declared_cards = (Card(rank=card.rank),)
            actions.append(
                _make_action(
                    player_id=player_id,
                    declared_pattern=PatternType.SINGLE,
                    declared_cards=declared_cards,
                    carrier_cards=(card,),
                )
            )

        if wildcard is not None:
            for rank in _NON_JOKER_RANKS:
                if rank == current_level_rank:
                    continue
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.SINGLE,
                        declared_cards=(Card(rank=rank),),
                        carrier_cards=(wildcard,),
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=rank)),),
                    )
                )
        return actions

    def _generate_group_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        all_by_rank = _group_cards_by_rank(hand_cards)
        non_wild_cards = tuple(card for card in hand_cards if not _is_wildcard(card, current_level_rank))
        non_wild_by_rank = _group_cards_by_rank(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        for rank, cards in all_by_rank.items():
            if len(cards) >= 2:
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.PAIR,
                        declared_cards=_public_declared_cards_for_group(rank, 2),
                        carrier_cards=_pick_cards(cards, 2),
                    )
                )
            if rank not in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and len(cards) >= 3:
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.TRIPLE,
                        declared_cards=_public_declared_cards_for_group(rank, 3),
                        carrier_cards=_pick_cards(cards, 3),
                    )
                )
            if rank not in {SMALL_JOKER_RANK, BIG_JOKER_RANK} and len(cards) >= 4:
                for length in range(4, len(cards) + 1):
                    actions.append(
                        _make_action(
                            player_id=player_id,
                            declared_pattern=PatternType.BOMB,
                            declared_cards=_public_declared_cards_for_group(rank, length),
                            carrier_cards=_pick_cards(cards, length),
                        )
                    )

        if (
            len(all_by_rank.get(SMALL_JOKER_RANK, [])) >= 2
            and len(all_by_rank.get(BIG_JOKER_RANK, [])) >= 2
        ):
            actions.append(
                _make_action(
                    player_id=player_id,
                    declared_pattern=PatternType.JOKER_BOMB,
                    declared_cards=(
                        Card(rank=SMALL_JOKER_RANK),
                        Card(rank=SMALL_JOKER_RANK),
                        Card(rank=BIG_JOKER_RANK),
                        Card(rank=BIG_JOKER_RANK),
                    ),
                    carrier_cards=(
                        all_by_rank[SMALL_JOKER_RANK][0],
                        all_by_rank[SMALL_JOKER_RANK][1],
                        all_by_rank[BIG_JOKER_RANK][0],
                        all_by_rank[BIG_JOKER_RANK][1],
                    ),
                )
            )

        if wildcard is None:
            return actions

        for rank, cards in non_wild_by_rank.items():
            if rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
                continue
            if len(cards) >= 1:
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.PAIR,
                        declared_cards=_public_declared_cards_for_group(rank, 2),
                        carrier_cards=_pick_cards(cards, 1) + (wildcard,),
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=rank)),),
                    )
                )
            if len(cards) >= 2:
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.TRIPLE,
                        declared_cards=_public_declared_cards_for_group(rank, 3),
                        carrier_cards=_pick_cards(cards, 2) + (wildcard,),
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=rank)),),
                    )
                )
            if len(cards) >= 3:
                for length in range(4, len(cards) + 2):
                    actions.append(
                        _make_action(
                            player_id=player_id,
                            declared_pattern=PatternType.BOMB,
                            declared_cards=_public_declared_cards_for_group(rank, length),
                            carrier_cards=_pick_cards(cards, length - 1) + (wildcard,),
                            wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=rank)),),
                        )
                    )
        return actions

    def _generate_triple_with_pair_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        all_by_rank = _group_cards_by_rank(hand_cards)
        non_wild_cards = tuple(card for card in hand_cards if not _is_wildcard(card, current_level_rank))
        non_wild_by_rank = _group_cards_by_rank(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        def natural_pair_ranks() -> list[str]:
            result: list[str] = []
            for rank, cards in all_by_rank.items():
                if len(cards) < 2:
                    continue
                if rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or rank in _NON_JOKER_RANKS:
                    result.append(rank)
            return result

        for triple_rank, triple_cards in all_by_rank.items():
            if triple_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or len(triple_cards) < 3:
                continue
            for pair_rank in natural_pair_ranks():
                if pair_rank == triple_rank:
                    continue
                pair_cards = all_by_rank[pair_rank]
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.TRIPLE_WITH_PAIR,
                        declared_cards=(
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=pair_rank),
                            Card(rank=pair_rank),
                        ),
                        carrier_cards=_pick_cards(triple_cards, 3) + _pick_cards(pair_cards, 2),
                    )
                )

        if wildcard is None:
            return actions

        for triple_rank, triple_cards in non_wild_by_rank.items():
            if triple_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or len(triple_cards) < 2:
                continue
            for pair_rank, pair_cards in all_by_rank.items():
                if pair_rank == triple_rank or len(pair_cards) < 2:
                    continue
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.TRIPLE_WITH_PAIR,
                        declared_cards=(
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=pair_rank),
                            Card(rank=pair_rank),
                        ),
                        carrier_cards=_pick_cards(triple_cards, 2) + _pick_cards(pair_cards, 2) + (wildcard,),
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=triple_rank)),),
                    )
                )

        for triple_rank, triple_cards in all_by_rank.items():
            if triple_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or len(triple_cards) < 3:
                continue
            for pair_rank, pair_cards in non_wild_by_rank.items():
                if pair_rank == triple_rank or pair_rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK} or len(pair_cards) < 1:
                    continue
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.TRIPLE_WITH_PAIR,
                        declared_cards=(
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=triple_rank),
                            Card(rank=pair_rank),
                            Card(rank=pair_rank),
                        ),
                        carrier_cards=_pick_cards(triple_cards, 3) + _pick_cards(pair_cards, 1) + (wildcard,),
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=pair_rank)),),
                    )
                )
        return actions

    def _generate_straight_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        all_by_rank = _group_cards_by_rank(tuple(card for card in hand_cards if not is_joker(card)))
        non_wild_cards = tuple(
            card for card in hand_cards if not is_joker(card) and not _is_wildcard(card, current_level_rank)
        )
        non_wild_by_rank = _group_cards_by_rank(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        for window in _STRAIGHT_WINDOWS:
            if all(all_by_rank.get(rank) for rank in window):
                carrier_cards = tuple(all_by_rank[rank][0] for rank in window)
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.STRAIGHT,
                        declared_cards=_public_declared_cards_for_window(window),
                        carrier_cards=carrier_cards,
                    )
                )
            if wildcard is not None:
                missing = [rank for rank in window if not non_wild_by_rank.get(rank)]
                if len(missing) != 1:
                    continue
                if any(not non_wild_by_rank.get(rank) for rank in window if rank != missing[0]):
                    continue
                carrier_cards = tuple(non_wild_by_rank[rank][0] for rank in window if rank != missing[0]) + (wildcard,)
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.STRAIGHT,
                        declared_cards=_public_declared_cards_for_window(window),
                        carrier_cards=carrier_cards,
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=missing[0])),),
                    )
                )
        return actions

    def _generate_pair_straight_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        all_by_rank = _group_cards_by_rank(tuple(card for card in hand_cards if not is_joker(card)))
        non_wild_cards = tuple(
            card for card in hand_cards if not is_joker(card) and not _is_wildcard(card, current_level_rank)
        )
        non_wild_by_rank = _group_cards_by_rank(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        for window in _PAIR_STRAIGHT_WINDOWS:
            if all(len(all_by_rank.get(rank, [])) >= 2 for rank in window):
                carrier_cards = tuple(card for rank in window for card in all_by_rank[rank][:2])
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.PAIR_STRAIGHT,
                        declared_cards=_public_declared_cards_for_pair_window(window),
                        carrier_cards=carrier_cards,
                    )
                )
            if wildcard is None:
                continue
            missing = [rank for rank in window if len(non_wild_by_rank.get(rank, [])) < 2]
            if len(missing) != 1:
                continue
            shortage_rank = missing[0]
            if len(non_wild_by_rank.get(shortage_rank, [])) != 1:
                continue
            if any(len(non_wild_by_rank.get(rank, [])) < 2 for rank in window if rank != shortage_rank):
                continue
            carrier_cards = tuple(card for rank in window if rank != shortage_rank for card in non_wild_by_rank[rank][:2])
            carrier_cards += (non_wild_by_rank[shortage_rank][0], wildcard)
            actions.append(
                _make_action(
                    player_id=player_id,
                    declared_pattern=PatternType.PAIR_STRAIGHT,
                    declared_cards=_public_declared_cards_for_pair_window(window),
                    carrier_cards=carrier_cards,
                    wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=shortage_rank)),),
                )
            )
        return actions

    def _generate_steel_plate_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        all_by_rank = _group_cards_by_rank(tuple(card for card in hand_cards if not is_joker(card)))
        non_wild_cards = tuple(
            card for card in hand_cards if not is_joker(card) and not _is_wildcard(card, current_level_rank)
        )
        non_wild_by_rank = _group_cards_by_rank(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        for window in _STEEL_PLATE_WINDOWS:
            if all(len(all_by_rank.get(rank, [])) >= 3 for rank in window):
                carrier_cards = tuple(card for rank in window for card in all_by_rank[rank][:3])
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.STEEL_PLATE,
                        declared_cards=_public_declared_cards_for_steel_window(window),
                        carrier_cards=carrier_cards,
                    )
                )
            if wildcard is None:
                continue
            missing = [rank for rank in window if len(non_wild_by_rank.get(rank, [])) < 3]
            if len(missing) != 1:
                continue
            shortage_rank = missing[0]
            if len(non_wild_by_rank.get(shortage_rank, [])) != 2:
                continue
            if any(len(non_wild_by_rank.get(rank, [])) < 3 for rank in window if rank != shortage_rank):
                continue
            carrier_cards = tuple(card for rank in window if rank != shortage_rank for card in non_wild_by_rank[rank][:3])
            carrier_cards += tuple(non_wild_by_rank[shortage_rank][:2]) + (wildcard,)
            actions.append(
                _make_action(
                    player_id=player_id,
                    declared_pattern=PatternType.STEEL_PLATE,
                    declared_cards=_public_declared_cards_for_steel_window(window),
                    carrier_cards=carrier_cards,
                    wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=shortage_rank)),),
                )
            )
        return actions

    def _generate_straight_flush_actions(
        self,
        player_id: int,
        hand_cards: tuple[Card, ...],
        current_level_rank: str,
    ) -> list[Action]:
        actions: list[Action] = []
        non_jokers = tuple(card for card in hand_cards if not is_joker(card))
        all_by_rank_suit = _group_cards_by_rank_and_suit(non_jokers)
        non_wild_cards = tuple(
            card for card in non_jokers if not _is_wildcard(card, current_level_rank)
        )
        non_wild_by_rank_suit = _group_cards_by_rank_and_suit(non_wild_cards)
        wildcard = _first_wildcard(hand_cards, current_level_rank)

        for suit in _SUIT_ORDER:
            for window in _STRAIGHT_WINDOWS:
                if all(all_by_rank_suit.get((rank, suit)) for rank in window):
                    carrier_cards = tuple(all_by_rank_suit[(rank, suit)][0] for rank in window)
                    declared_cards = tuple(Card(rank=rank, suit=suit) for rank in window)
                    actions.append(
                        _make_action(
                            player_id=player_id,
                            declared_pattern=PatternType.STRAIGHT_FLUSH,
                            declared_cards=declared_cards,
                            carrier_cards=carrier_cards,
                        )
                    )
                if wildcard is None:
                    continue
                missing = [rank for rank in window if not non_wild_by_rank_suit.get((rank, suit))]
                if len(missing) != 1:
                    continue
                if any(not non_wild_by_rank_suit.get((rank, suit)) for rank in window if rank != missing[0]):
                    continue
                carrier_cards = tuple(
                    non_wild_by_rank_suit[(rank, suit)][0] for rank in window if rank != missing[0]
                ) + (wildcard,)
                declared_cards = tuple(Card(rank=rank, suit=suit) for rank in window)
                actions.append(
                    _make_action(
                        player_id=player_id,
                        declared_pattern=PatternType.STRAIGHT_FLUSH,
                        declared_cards=declared_cards,
                        carrier_cards=carrier_cards,
                        wildcard_info=(WildcardInfo(carrier_card=wildcard, declared_as=Card(rank=missing[0], suit=suit)),),
                    )
                )
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
