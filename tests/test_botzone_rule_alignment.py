from __future__ import annotations

import itertools
import random
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from engine.actions import ActionType
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, build_double_deck
from engine.game import GuanDanGame
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint
from integrations.botzone.cards import card_id_for, card_from_id


_OFFICIAL_TO_ENGINE = {
    "single": "single",
    "pair": "pair",
    "three": "triple",
    "set": "triple_with_pair",
    "straight": "straight",
    "triple_pairs": "pair_straight",
    "three_straight": "steel_plate",
    "bomb": "bomb",
    "straight_flush": "straight_flush",
    "rocket": "joker_bomb",
}
_RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
_SUITS = ("h", "d", "s", "c")


def _reference_namespace() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "docs" / "BOTZONE_REFEREE_EXCERPTS.md"
    source = path.read_text(encoding="utf-8")
    match = re.search(r"```python\s*(.*?)```", source, flags=re.DOTALL)
    if match is None:
        raise AssertionError("official referee excerpt code block is missing")

    def reject(*_args: object) -> None:
        raise ValueError("official referee rejected claim")

    namespace: dict[str, object] = {"Counter": Counter, "setError": reject}
    exec(compile(match.group(1), str(path), "exec"), namespace)
    return namespace


def _card(token: str) -> Card:
    if token in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
        return Card(token)
    return Card(token[:-1], token[-1])


def _official_id(card: Card, *, suit: str | None = None, copy_index: int = 0) -> int:
    if card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
        return card_id_for(card.rank, None, copy_index)
    actual_suit = card.suit if suit is None else suit.upper()
    if actual_suit is None:
        raise AssertionError("ordinary referee card requires a suit")
    return card_id_for(card.rank, actual_suit.lower(), copy_index)


def _carrier_key(cards: tuple[Card, ...]) -> tuple[tuple[tuple[str, str | None], int], ...]:
    return tuple(sorted(Counter((card.rank, card.suit) for card in cards).items()))


def _declared_key(action: object) -> tuple[object, ...]:
    pattern = action.declared_pattern.value
    if pattern == "straight_flush":
        counts = Counter((card.rank, card.suit) for card in action.declared_cards)
    else:
        counts = Counter(card.rank for card in action.declared_cards)
    return pattern, tuple(sorted(counts.items()))


def _representative_suit(rank: str, level: str) -> str:
    return "D" if rank == level else "S"


def _generated_signatures(actions: tuple[object, ...]) -> set[tuple[object, ...]]:
    return {
        (_carrier_key(action.carrier_cards), *_declared_key(action), action.wildcard_count)
        for action in actions
        if action.action_type == ActionType.PLAY
    }


def _hand_state(hand: tuple[Card, ...]) -> GameState:
    return GameState(
        players=(
            PlayerState(1, hand),
            PlayerState(2, ()),
            PlayerState(3, ()),
            PlayerState(4, ()),
        ),
        current_player_id=1,
        current_level_rank="2",
        table_constraint=TableConstraint(),
    )


def _complete_deal_with_target_hand(tokens: tuple[str, ...]) -> GuanDanGame:
    deck = build_double_deck()
    target: list[Card] = []
    for token in tokens:
        card = _card(token)
        try:
            index = deck.index(card)
        except ValueError as exc:
            raise AssertionError(f"target hand exceeds the physical deck: {token}") from exc
        target.append(deck.pop(index))
    random.Random(151).shuffle(deck)
    target.extend(deck[:27 - len(target)])
    rest = deck[27 - len(tokens):]
    hands = {
        1: tuple(target),
        2: tuple(rest[:27]),
        3: tuple(rest[27:54]),
        4: tuple(rest[54:81]),
    }
    if [len(hands[player_id]) for player_id in range(1, 5)] != [27] * 4:
        raise AssertionError("complete deal must contain four 27-card hands")
    if Counter(card for hand in hands.values() for card in hand) != Counter(build_double_deck()):
        raise AssertionError("complete deal must preserve the 108-card deck")
    game = GuanDanGame(current_level_rank="2", preset_hands=hands)
    game.reset()
    return game


def _official_action_claim(
    action: object,
    hand: tuple[Card, ...],
    reference: dict[str, object],
) -> tuple[list[int], list[int]]:
    pools: dict[tuple[str, str | None], list[int]] = defaultdict(list)
    face_copies: Counter[tuple[str, str | None]] = Counter()
    for card in hand:
        face = (card.rank, card.suit)
        copy_index = face_copies[face]
        face_copies[face] += 1
        pools[face].append(_official_id(card, copy_index=copy_index))
    action_ids = [pools[(card.rank, card.suit)].pop(0) for card in action.carrier_cards]
    wildcard_indexes = [
        index for index, card in enumerate(action.carrier_cards)
        if card.rank == "2" and card.suit == "H"
    ][:action.wildcard_count]
    if len(wildcard_indexes) != len(action.wildcard_info):
        raise AssertionError("wildcard metadata does not bind to physical carriers")
    natural_claims = [
        card_id for index, card_id in enumerate(action_ids)
        if index not in set(wildcard_indexes)
    ]
    suit_choices: list[tuple[str, ...]] = []
    for item in action.wildcard_info:
        target = item.declared_as
        if target.suit is not None:
            suit_choices.append((target.suit,))
        elif target.rank == "2":
            suit_choices.append(("D", "S", "C"))
        else:
            suit_choices.append(("H", "D", "S", "C"))
    for suits in itertools.product(*suit_choices):
        claim_ids = natural_claims + [
            _official_id(item.declared_as, suit=suit)
            for item, suit in zip(action.wildcard_info, suits)
        ]
        try:
            reference["isLegalClaim"](action_ids, claim_ids, "2", 0)
            official_pattern, _points = reference["checkPokerType"](claim_ids)
        except (ValueError, IndexError):
            continue
        if _OFFICIAL_TO_ENGINE.get(official_pattern) == action.declared_pattern.value:
            return action_ids, claim_ids
    raise AssertionError("canonical action has no official claim representation")


def _assert_generated_action_officially_valid(
    testcase: unittest.TestCase,
    reference: dict[str, object],
    action: object,
    hand: tuple[Card, ...],
) -> None:
    action_ids, claim_ids = _official_action_claim(action, hand, reference)
    reference["isLegalClaim"](action_ids, claim_ids, "2", 0)
    official_pattern, _points = reference["checkPokerType"](claim_ids)
    expected = action.declared_pattern.value
    testcase.assertEqual(_OFFICIAL_TO_ENGINE.get(official_pattern), expected)
    if expected == "straight_flush":
        claimed = Counter(
            (card_from_id(card_id).rank, card_from_id(card_id).suit.upper())
            for card_id in claim_ids
        )
        testcase.assertEqual(claimed, Counter((card.rank, card.suit) for card in action.declared_cards))
    else:
        testcase.assertEqual(
            Counter(card_from_id(card_id).rank for card_id in claim_ids),
            Counter(card.rank for card in action.declared_cards),
        )


class BotzoneRuleAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = _reference_namespace()

    def test_official_referee_claims_are_exhaustively_represented_for_small_carriers(self) -> None:
        # Every carrier subset of this bounded physical hand is paired with all
        # zero-, one-, and two-wild declarations over the ordinary face domain.
        hand = tuple(_card(token) for token in (
            "AS", "AH", "2S", "2C", "2H", "2H", "3S", "3C",
        ))
        generated = BaseRuleEngine().generate_legal_actions(_hand_state(hand))
        available = _generated_signatures(generated)
        face_copies: Counter[tuple[str, str | None]] = Counter()
        physical_ids: list[int] = []
        for card in hand:
            face = (card.rank, card.suit)
            physical_ids.append(_official_id(card, copy_index=face_copies[face]))
            face_copies[face] += 1
        target_faces = tuple((rank, suit) for rank in _RANKS for suit in _SUITS)
        wild_indices = tuple(index for index, card in enumerate(hand) if (card.rank, card.suit) == ("2", "H"))

        for carrier_count in range(1, len(hand) + 1):
            for indices in itertools.combinations(range(len(hand)), carrier_count):
                selected_wild_indices = tuple(index for index in indices if index in wild_indices)
                for wildcard_count in range(min(2, len(selected_wild_indices)) + 1):
                    natural_indices = list(indices)
                    for index in selected_wild_indices[:wildcard_count]:
                        natural_indices.remove(index)
                    target_sets = (
                        itertools.combinations_with_replacement(target_faces, wildcard_count)
                        if wildcard_count else ((),)
                    )
                    for replacements in target_sets:
                        action_ids = [physical_ids[index] for index in indices]
                        claim_ids = [physical_ids[index] for index in natural_indices]
                        claim_ids.extend(
                            card_id_for(rank, suit, 0) for rank, suit in replacements
                        )
                        try:
                            self.reference["isLegalClaim"](action_ids, claim_ids, "2", 0)
                            official_pattern, _points = self.reference["checkPokerType"](claim_ids)
                        except (ValueError, IndexError):
                            continue
                        engine_pattern = _OFFICIAL_TO_ENGINE.get(official_pattern)
                        if engine_pattern is None:
                            continue
                        effective_wildcards = sum(face != ("2", "H") for face in replacements)
                        carrier = tuple((hand[index].rank, hand[index].suit) for index in indices)
                        if engine_pattern == "straight_flush":
                            declared_counts = Counter(
                                (card_from_id(card_id).rank, card_from_id(card_id).suit.upper())
                                for card_id in claim_ids
                            )
                            declared = tuple(sorted(declared_counts.items()))
                        else:
                            declared = tuple(sorted(Counter(card_from_id(card_id).rank for card_id in claim_ids).items()))
                        signature = (
                            tuple(sorted(Counter(carrier).items())),
                            engine_pattern,
                            declared,
                            effective_wildcards,
                        )
                        self.assertIn(signature, available, (indices, wildcard_count, replacements, engine_pattern))

    def test_full_hand_actions_match_official_claim_and_comparison_rules(self) -> None:
        cases = (
            ("AS", "AH", "2S", "2C", "3S", "3C", "2H", "2H"),
            ("7S", "7C", "8S", "2H", "2H"),
            ("7S", "7H", "7C", "7D", "7S", "7H", "7C", "7D", "2H", "2H"),
            ("AH", "2H", "2H", "3H", "4H", "5H"),
        )
        engine = BaseRuleEngine()
        all_actions: list[tuple[object, ...]] = []
        for tokens in cases:
            hand = tuple(_card(token) for token in tokens)
            actions = engine.generate_legal_actions(_hand_state(hand))
            self.assertTrue(actions)
            for action in actions:
                with self.subTest(hand=tokens, pattern=action.declared_pattern):
                    self.assertLessEqual(action.wildcard_count, 2)
                    self.assertEqual(action.wildcard_count, len(action.wildcard_info))
                    self.assertLessEqual(Counter(action.carrier_cards), Counter(hand))
                    _assert_generated_action_officially_valid(self, self.reference, action, hand)
            all_actions.append(actions)

        self.assertTrue(any(
            action.declared_pattern == PatternType.STEEL_PLATE and action.wildcard_count == 2
            and {item.declared_as.rank for item in action.wildcard_info} == {"A", "2"}
            for action in all_actions[0]
        ))
        self.assertTrue(any(
            action.declared_pattern == PatternType.TRIPLE_WITH_PAIR and action.wildcard_count == 2
            and {item.declared_as.rank for item in action.wildcard_info} == {"7", "8"}
            for action in all_actions[1]
        ))
        self.assertTrue(any(
            action.declared_pattern == PatternType.BOMB and len(action.declared_cards) == 10
            and action.wildcard_count == 2
            for action in all_actions[2]
        ))
        self.assertTrue(any(
            action.declared_pattern == PatternType.STRAIGHT_FLUSH and action.wildcard_count == 1
            and Counter(action.carrier_cards)[_card("2H")] == 2
            for action in all_actions[3]
        ))

    def test_complete_deck_deal_contains_low_high_and_two_wildcard_routes(self) -> None:
        game = _complete_deal_with_target_hand((
            "AS", "AH", "AC", "AD",
            "2S", "2C", "2D", "2H", "2H",
            "3S", "3C", "3H", "4S", "4C",
            "7S", "7C", "QS", "QH", "KS", "KH",
        ))
        actions = game.legal_actions()
        signatures = {
            (
                action["declared_pattern"],
                tuple(sorted(Counter(
                    token[:-1] if token.endswith(("S", "H", "C", "D")) else token
                    for token in action["declared_cards"]
                ).items())),
                _carrier_key(tuple(_card(token) for token in action["carrier_cards"])),
                action["wildcard_count"],
            )
            for action in actions
        }
        required = (
            ("pair_straight", tuple(sorted(Counter({"A": 2, "2": 2, "3": 2}).items())), _carrier_key(tuple(_card(token) for token in ("AS", "AH", "2S", "2C", "3S", "3C"))), 0),
            ("pair_straight", tuple(sorted(Counter({"2": 2, "3": 2, "4": 2}).items())), _carrier_key(tuple(_card(token) for token in ("2S", "2C", "3S", "3C", "4S", "4C"))), 0),
            ("pair_straight", tuple(sorted(Counter({"Q": 2, "K": 2, "A": 2}).items())), _carrier_key(tuple(_card(token) for token in ("QS", "QH", "KS", "KH", "AS", "AH"))), 0),
            ("steel_plate", tuple(sorted(Counter({"A": 3, "2": 3}).items())), _carrier_key(tuple(_card(token) for token in ("AS", "AH", "AC", "2S", "2C", "2D"))), 0),
            ("steel_plate", tuple(sorted(Counter({"2": 3, "3": 3}).items())), _carrier_key(tuple(_card(token) for token in ("2S", "2C", "2D", "3S", "3C", "3H"))), 0),
            ("bomb", tuple(sorted(Counter({"7": 4}).items())), _carrier_key(tuple(_card(token) for token in ("7S", "7C", "2H", "2H"))), 2),
        )
        for expected in required:
            self.assertIn(expected, signatures)

    def test_official_bomb_hierarchy_matches_engine_can_beat(self) -> None:
        hand = tuple(_card(token) for token in (
            "3S", "3S", "3H", "3C", "3D",
            "5S", "6S", "7S", "8S", "9S",
            "4S", "4S", "4H", "4H", "4C", "4D",
        ))
        actions = BaseRuleEngine().generate_legal_actions(_hand_state(hand))
        chosen: dict[tuple[str, int], object] = {}
        for action in actions:
            if action.declared_pattern == PatternType.BOMB:
                chosen.setdefault(("bomb", len(action.declared_cards)), action)
            elif action.declared_pattern == PatternType.STRAIGHT_FLUSH:
                chosen.setdefault(("straight_flush", len(action.declared_cards)), action)
        self.assertTrue({("bomb", 5), ("straight_flush", 5), ("bomb", 6)}.issubset(chosen))

        for weaker_key, stronger_key in (
            (("bomb", 5), ("straight_flush", 5)),
            (("straight_flush", 5), ("bomb", 6)),
            (("bomb", 5), ("bomb", 6)),
        ):
            weaker = chosen[weaker_key]
            stronger = chosen[stronger_key]
            _weak_ids, weak_claim = _official_action_claim(weaker, hand, self.reference)
            _strong_ids, strong_claim = _official_action_claim(stronger, hand, self.reference)
            weak_type, weak_points = self.reference["checkPokerType"](weak_claim)
            strong_type, strong_points = self.reference["checkPokerType"](strong_claim)
            official = self.reference["checkBigger"](weak_type, weak_points, strong_type, strong_points)
            self.assertIs(official, True)
            self.assertTrue(BaseRuleEngine().can_beat(stronger, weaker, "2"))

    def test_twenty_complete_deals_and_generated_midgame_candidates_are_payable(self) -> None:
        engine = BaseRuleEngine()
        for seed in range(20):
            game = GuanDanGame(current_level_rank="2", seed=seed)
            game.reset()
            for generated_step in range(4):
                actions = game.legal_actions()
                observation = game.observe()
                hand = tuple(_card(token) for token in observation["my_info"]["hand_cards"])
                physical_pool = Counter(hand)
                self.assertTrue(actions)
                for action in actions:
                    carriers = tuple(_card(token) for token in action["carrier_cards"])
                    self.assertLessEqual(Counter(carriers), physical_pool)
                    self.assertLessEqual(action["wildcard_count"], 2)
                    self.assertEqual(action["wildcard_count"], len(action["wildcard_info"]))
                if generated_step == 3:
                    break
                # Advance only through canonical engine actions to create fresh
                # public midgame states; no network or policy is involved.
                game.step(int(actions[0]["action_id"]))


if __name__ == "__main__":
    unittest.main()
