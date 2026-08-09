from __future__ import annotations

import unittest

from engine.actions import ActionType
from engine.cards import Card
from engine.game import GuanDanGame
from engine.patterns import PatternType

from integrations.botzone.cards import ALL_CARDS, card_id_for
from integrations.botzone.models import ActionClaim, GlobalState, HistoryEntry, PlayRequest
from integrations.botzone.play_adapter import (
    botzone_id_to_engine_card,
    encode_action_claim,
    project_decision,
    team_for_engine_player,
)
from integrations.botzone.session import HandlerContext


def _request(history: tuple[HistoryEntry, ...] = ()) -> PlayRequest:
    return PlayRequest(history=history, done=(), pass_on=-1, global_state=GlobalState("2", 0, None, None, False))


def _context(hand: tuple[int, ...], history: tuple[HistoryEntry, ...] = (), *, local: int = 0) -> HandlerContext:
    return HandlerContext(
        match_key="unit",
        request_digest="digest",
        request=_request(history),
        local_player_id=local,
        own_hand=hand,
        history=history,
        latest_window=history[-4:],
        global_state=GlobalState("2", 0, None, None, False),
        finished=False,
    )


class BotzonePlayAdapterTests(unittest.TestCase):
    def test_108_ids_and_teams_map_without_losing_card_faces(self) -> None:
        self.assertEqual(len(ALL_CARDS), 108)
        for source in ALL_CARDS:
            converted = botzone_id_to_engine_card(source.card_id)
            with self.subTest(card_id=source.card_id):
                self.assertEqual(converted.rank, source.rank)
                self.assertEqual(converted.suit, None if source.suit is None else source.suit.upper())
        self.assertEqual([team_for_engine_player(player) for player in (1, 2, 3, 4)], ["team_13", "team_24", "team_13", "team_24"])

    def test_free_projection_is_stable_and_binds_lowest_duplicate_identity(self) -> None:
        hand = (card_id_for("3", "h", 1), card_id_for("3", "h", 0), card_id_for("4", "d", 0))
        projection = project_decision(_context(hand))
        self.assertTrue(projection.table_view_free)
        pair = next(
            action for action_id, action in projection.provenance.items()
            if action.action_type == ActionType.PLAY and action.declared_pattern == PatternType.PAIR
        )
        encoded = encode_action_claim(pair, hand, "2")
        self.assertEqual(encoded.action, tuple(sorted(hand[:2])))
        self.assertEqual(encoded.action, encoded.claim)
        self.assertEqual([action["action_id"] for action in projection.legal_actions], list(range(1, len(projection.legal_actions) + 1)))

    def test_follow_projection_includes_pass_and_preserves_leader_constraint(self) -> None:
        leader = HistoryEntry(player_id=1, response=ActionClaim((card_id_for("3", "h"),), (card_id_for("3", "h"),)))
        projection = project_decision(_context((card_id_for("4", "d"),), (leader,)))
        self.assertFalse(projection.table_view_free)
        self.assertEqual(projection.observation["current_round"]["constraint"], "single")
        self.assertIn("pass", [action["declared_pattern"] for action in projection.legal_actions])

    def test_wildcard_straight_claim_avoids_accidental_straight_flush(self) -> None:
        hand = (
            card_id_for("2", "h"),
            card_id_for("3", "h"),
            card_id_for("4", "h"),
            card_id_for("5", "h"),
            card_id_for("6", "h"),
        )
        projection = project_decision(_context(hand))
        straight = next(
            action for action in projection.provenance.values()
            if action.declared_pattern == PatternType.STRAIGHT and action.wildcard_count == 1
        )
        encoded = encode_action_claim(straight, hand, "2")
        self.assertEqual(len(encoded.action), 5)
        self.assertNotEqual(len({botzone_id_to_engine_card(card_id).suit for card_id in encoded.claim}), 1)

    def test_public_legal_actions_match_a_constructed_public_engine_fixture(self) -> None:
        hand = (card_id_for("3", "h", 1), card_id_for("3", "h", 0), card_id_for("4", "d", 0))
        projection = project_decision(_context(hand))
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=1,
            preset_hands={
                1: tuple(botzone_id_to_engine_card(card_id) for card_id in hand),
                2: (Card("5", "S"),),
                3: (Card("6", "S"),),
                4: (Card("7", "S"),),
            },
        )
        game.reset()
        self.assertEqual([dict(action) for action in projection.legal_actions], game.legal_actions())


if __name__ == "__main__":
    unittest.main()
