from __future__ import annotations

import unittest

from integrations.botzone.cards import (
    ALL_CARDS,
    BIG_JOKER,
    RANKS,
    SMALL_JOKER,
    SUITS,
    card_from_id,
    card_id_for,
)


class BotzoneCardCodecTests(unittest.TestCase):
    def test_all_108_physical_ids_round_trip(self) -> None:
        self.assertEqual(len(ALL_CARDS), 108)
        self.assertEqual(
            [card_id_for(card.rank, card.suit, card.copy_index) for card in ALL_CARDS],
            list(range(108)),
        )

    def test_rank_suit_and_second_deck_boundaries(self) -> None:
        self.assertEqual(card_from_id(0).face.to_json(), {"rank": "A", "suit": "h"})
        self.assertEqual(card_from_id(4).face.to_json(), {"rank": "2", "suit": "h"})
        self.assertEqual(card_from_id(51).face.to_json(), {"rank": "K", "suit": "c"})
        self.assertEqual(card_from_id(52).rank, SMALL_JOKER)
        self.assertEqual(card_from_id(53).rank, BIG_JOKER)
        self.assertEqual(card_from_id(54).copy_index, 1)
        self.assertEqual(card_from_id(107).copy_index, 1)

    def test_every_ordinary_face_has_both_physical_copies(self) -> None:
        for rank in RANKS:
            for suit in SUITS:
                first = card_id_for(rank, suit, 0)
                second = card_id_for(rank, suit, 1)
                self.assertEqual(second, first + 54)
                self.assertEqual(card_from_id(first).face, card_from_id(second).face)
                self.assertNotEqual(card_from_id(first).card_id, card_from_id(second).card_id)

    def test_invalid_ids_and_bool_are_rejected(self) -> None:
        for value in (-1, 108, True, "0"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    card_from_id(value)
        with self.assertRaises(ValueError):
            card_id_for("A", "h", True)


if __name__ == "__main__":
    unittest.main()
