from __future__ import annotations

import unittest

from integrations.botzone.cards import card_from_id, card_id_for
from integrations.botzone.models import ActionClaim, GlobalState, HistoryEntry, PlayRequest
from integrations.botzone.play_adapter import AdapterError, project_decision
from integrations.botzone.session import HandlerContext


def _hand(excluded: set[int]) -> tuple[int, ...]:
    return tuple(card_id for card_id in range(108) if card_id not in excluded)[:27]


def _context(
    local: int,
    history: tuple[HistoryEntry, ...],
    *,
    latest: tuple[HistoryEntry, ...] | None = None,
    done: tuple[int, ...] = (),
) -> HandlerContext:
    played = {card_id for entry in history for card_id in entry.response.action}
    request = PlayRequest(history if latest is None else latest, done, -1, GlobalState("2", 0, None, None, False))
    return HandlerContext(
        match_key="unit",
        request_digest="digest",
        request=request,
        local_player_id=local,
        own_hand=_hand(played),
        history=history,
        latest_window=history[-4:] if latest is None else latest,
        global_state=GlobalState("2", 0, None, None, False),
        finished=False,
    )


def _play(player: int, card_id: int) -> HistoryEntry:
    return HistoryEntry(player, ActionClaim((card_id,), (card_id,)))


def _pass(player: int) -> HistoryEntry:
    return HistoryEntry(player, ActionClaim.pass_action())


class BotzoneAdapterObservationTests(unittest.TestCase):
    def test_follow_actions_stay_in_the_same_round_and_use_exact_public_keys(self) -> None:
        history = (_play(0, card_id_for("3", "h")), _play(1, card_id_for("4", "d")))
        projection = project_decision(_context(2, history))
        current = projection.observation["current_round"]
        actions = projection.observation["history"]["actions"]
        self.assertEqual(current["round_no"], 1)
        self.assertEqual([action["round_no"] for action in actions], [1, 1])
        self.assertIsNone(current["table_action"]["action_id"])
        self.assertEqual(
            set(actions[0]),
            {"step_no", "round_no", "player_id", "declared_pattern", "declared_cards", "carrier_cards"},
        )
        self.assertIn("wildcard_count", current["table_action"])
        self.assertIn("display_text", current["table_action"])

    def test_multi_round_replay_handles_passes_and_new_free_lead(self) -> None:
        history = (
            _play(0, card_id_for("3", "h")),
            _pass(1),
            _pass(2),
            _pass(3),
            _play(0, card_id_for("4", "h")),
        )
        projection = project_decision(_context(1, history, latest=history[-4:]))
        self.assertEqual([item["round_no"] for item in projection.observation["history"]["actions"]], [1, 1, 1, 1, 2])
        self.assertEqual(projection.observation["current_round"]["round_no"], 2)

    def test_external_two_wildcard_table_action_rebuilds_wildcard_info(self) -> None:
        natural = tuple(card_id_for("3", suit, copy) for copy in (0, 1) for suit in ("h", "d", "s", "c"))
        wildcards = (card_id_for("2", "h", 0), card_id_for("2", "h", 1))
        claim = natural + (card_id_for("3", "h"), card_id_for("3", "h"))
        leader = HistoryEntry(1, ActionClaim(natural + wildcards, claim))
        projection = project_decision(_context(0, (leader,)))
        table = projection.observation["current_round"]["table_action"]
        self.assertEqual(table["declared_pattern"], "bomb")
        self.assertEqual(table["wildcard_count"], 2)
        self.assertEqual(len(table["wildcard_info"]), 2)

    def test_external_single_wildcard_uses_canonical_declared_tokens(self) -> None:
        natural = (card_id_for("3", "h"), card_id_for("3", "d"))
        wildcard = card_id_for("2", "h")
        claim = natural + (card_id_for("3", "s"),)
        leader = HistoryEntry(1, ActionClaim(natural + (wildcard,), claim))
        projection = project_decision(_context(0, (leader,)))
        table = projection.observation["current_round"]["table_action"]
        self.assertEqual(table["declared_pattern"], "triple")
        self.assertEqual(table["declared_cards"], ["3", "3", "3"])
        self.assertEqual(table["wildcard_count"], 1)
        self.assertEqual(table["wildcard_info"][0]["declared_as"], "3")

    def test_entity_conservation_and_context_mismatch_fail_closed(self) -> None:
        card_id = card_id_for("3", "h")
        duplicate = (_play(0, card_id), _play(1, card_id))
        with self.assertRaises(AdapterError):
            project_decision(_context(2, duplicate))

        history = (_play(0, card_id),)
        bad_own = _context(1, history)
        bad_own = HandlerContext(
            match_key=bad_own.match_key,
            request_digest=bad_own.request_digest,
            request=bad_own.request,
            local_player_id=bad_own.local_player_id,
            own_hand=(card_id,) + bad_own.own_hand[1:],
            history=bad_own.history,
            latest_window=bad_own.latest_window,
            global_state=bad_own.global_state,
            finished=False,
        )
        with self.assertRaises(AdapterError):
            project_decision(bad_own)

        mismatch = _context(1, history, latest=())
        with self.assertRaises(AdapterError):
            project_decision(mismatch)


if __name__ == "__main__":
    unittest.main()
