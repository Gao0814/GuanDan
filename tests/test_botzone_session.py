from __future__ import annotations

from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.protocol import parse_stage_request
from integrations.botzone.poll import FinishedRow
from integrations.botzone.session import HandlerResult, PlayEffect, SessionStorageError, SessionStore


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _deal(player: int) -> DealRequest:
    parsed = parse_stage_request(
        {"stage": "deal", "deliver": list(range(player * 27, (player + 1) * 27)), "your_id": player, "global": _global()}
    )
    assert isinstance(parsed, DealRequest)
    return parsed


def _play() -> PlayRequest:
    global_state = _global()
    global_state["resist"] = False
    parsed = parse_stage_request({"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": global_state})
    assert isinstance(parsed, PlayRequest)
    return parsed


class BotzoneSessionTests(unittest.TestCase):
    def test_pending_failure_restart_and_acknowledgement_transaction(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            record, call_handler = store.prepare("unit-a", b'{"request":1}', _deal(0))
            self.assertTrue(call_handler)
            record = store.reserve_handler(record)
            stored = store.complete_handler(record, HandlerResult(b'{"response":1}'))
            self.assertEqual(stored.delivery_state, "pending")
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.restore_pending(deliveries)

            restarted = SessionStore(root)
            restored = restarted.load("unit-a")
            assert restored is not None
            self.assertEqual(restored.pending_response, b'{"response":1}')
            deliveries = restarted.pending_deliveries()
            restarted.mark_inflight(deliveries)
            restarted.acknowledge(deliveries)
            acknowledged = restarted.load("unit-a")
            assert acknowledged is not None
            self.assertIsNone(acknowledged.pending_response)
            self.assertEqual(acknowledged.delivery_state, "idle")

    def test_duplicate_digest_reuses_the_cached_response_without_new_handler(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            record, first_call = store.prepare("unit-a", b"same", _deal(0))
            record = store.complete_handler(store.reserve_handler(record), HandlerResult(b"ok"))
            self.assertTrue(first_call)
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            duplicate, call_handler = store.prepare("unit-a", b"same", _deal(0))
            self.assertFalse(call_handler)
            self.assertEqual(duplicate.pending_response, b"ok")

    def test_sessions_keep_hands_history_and_pending_state_isolated(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            first, _ = store.prepare("unit-a", b"deal-a", _deal(0))
            second, _ = store.prepare("unit-b", b"deal-b", _deal(1))
            first = store.complete_handler(store.reserve_handler(first), HandlerResult(b"a"))
            second = store.complete_handler(store.reserve_handler(second), HandlerResult(b"b"))
            self.assertEqual(store.load("unit-a").pending_response, b"a")
            self.assertEqual(store.load("unit-b").pending_response, b"b")
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            changed, _ = store.prepare("unit-a", b"play-a", _play())
            self.assertEqual(changed.history, ())
            self.assertEqual(store.load("unit-b").own_hand, second.own_hand)
            self.assertIsNone(store.load("unit-b").pending_response)
            self.assertEqual(store.load("unit-a").own_hand, first.own_hand)

    def test_missing_or_corrupt_state_and_atomic_failure_fail_closed(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            with self.assertRaises(SessionStorageError):
                store.prepare("unit-a", b"play", _play())
            record, _ = store.prepare("unit-a", b"deal", _deal(0))
            path = next(Path(root).glob("*.json"))
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(SessionStorageError):
                store.load("unit-a")
            with TemporaryDirectory() as atomic_root:
                atomic_store = SessionStore(atomic_root)
                with patch("integrations.botzone.session.os.replace", side_effect=OSError("denied")):
                    with self.assertRaises(SessionStorageError):
                        atomic_store.save(record)

    def test_pending_play_effect_deducts_once_only_after_acknowledgement(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            deal, _ = store.prepare("unit-a", b"deal", _deal(0))
            deal = store.complete_handler(store.reserve_handler(deal), HandlerResult(b"deal"))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            before = store.load("unit-a")
            assert before is not None
            play, _ = store.prepare("unit-a", b"play", _play())
            play = store.complete_handler(
                store.reserve_handler(play),
                HandlerResult(b"play", PlayEffect((before.own_hand[0],))),
            )
            self.assertEqual(store.load("unit-a").own_hand, before.own_hand)
            restarted = SessionStore(root)
            deliveries = restarted.pending_deliveries()
            restarted.mark_inflight(deliveries)
            restarted.restore_pending(deliveries)
            restarted.mark_inflight(deliveries)
            restarted.acknowledge(deliveries)
            after = restarted.load("unit-a")
            assert after is not None
            self.assertEqual(after.own_hand, before.own_hand[1:])
            restarted.acknowledge(deliveries)
            self.assertEqual(restarted.load("unit-a").own_hand, before.own_hand[1:])

    def test_history_windows_merge_only_a_verifiable_suffix(self) -> None:
        def play(history: list[dict[str, object]], done: list[int] | None = None) -> PlayRequest:
            global_state = _global()
            global_state["resist"] = False
            slots: list[object] = [[]] * (4 - len(history)) + history
            parsed = parse_stage_request(
                {"stage": "play", "history": slots, "done": [] if done is None else done, "pass_on": -1, "global": global_state}
            )
            assert isinstance(parsed, PlayRequest)
            return parsed

        one = {"player": 0, "response": [[0], [0]]}
        two = {"player": 1, "response": [[], []]}
        three = {"player": 2, "response": [[1], [1]]}
        four = {"player": 3, "response": [[], []]}
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            store.prepare("unit-a", b"deal", _deal(0))
            original_history = [dict(one), dict(two)]
            first, _ = store.prepare("unit-a", b"p1", play([one, two]))
            repeated, _ = store.prepare("unit-a", b"p2", play([one, two]))
            sliding, _ = store.prepare("unit-a", b"p3", play([two, three]))
            skipped, _ = store.prepare("unit-a", b"p4", play([three, four], done=[0]))
            self.assertEqual(first.history, repeated.history)
            self.assertEqual(len(sliding.history), 3)
            self.assertEqual(len(skipped.history), 4)
            self.assertEqual([one, two], original_history)
            with self.assertRaisesRegex(SessionStorageError, "history_alignment_failed"):
                store.prepare("unit-a", b"p5", play([one]))

    def test_unauthorized_effect_and_finished_pending_effect_fail_closed(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            deal, _ = store.prepare("unit-a", b"deal", _deal(0))
            deal = store.complete_handler(store.reserve_handler(deal), HandlerResult(b"deal"))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            store.acknowledge(deliveries)
            play, _ = store.prepare("unit-a", b"play", _play())
            with self.assertRaises(SessionStorageError):
                store.complete_handler(store.reserve_handler(play), HandlerResult(b"play", PlayEffect((107,))))
            valid, _ = store.prepare("unit-a", b"play-2", _play())
            before = valid.own_hand
            store.complete_handler(store.reserve_handler(valid), HandlerResult(b"play", PlayEffect((before[0],))))
            store.finish(FinishedRow("unit-a", 0, 0, ()))
            self.assertIsNone(store.load("unit-a"))
            snapshot = json.loads(next(Path(root).glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(snapshot, {"schema": "botzone_no_tribute_finished", "version": 3, "finished": True})

    def test_local_seat_persists_and_conflicting_deal_or_old_schema_fails_closed(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            for player in range(4):
                record, _ = store.prepare(f"unit-{player}", f"deal-{player}".encode(), _deal(player))
                context = store.handler_context(record, _deal(player))
                self.assertEqual(context.local_player_id, player)
                self.assertEqual(context.to_json()["local_player_id"], player)
                self.assertEqual(SessionStore(root).load(f"unit-{player}").local_player_id, player)
            with self.assertRaises(SessionStorageError):
                store.prepare("unit-0", b"conflicting-deal", _deal(1))

            path = next(Path(root).glob("*.json"))
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            snapshot["version"] = 2
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaises(SessionStorageError):
                store.load(snapshot["match_id"])

    def test_malformed_persisted_local_seat_fails_closed(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            store.prepare("unit-a", b"deal", _deal(0))
            path = next(Path(root).glob("*.json"))
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            snapshot["local_player_id"] = True
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaises(SessionStorageError):
                store.load("unit-a")


if __name__ == "__main__":
    unittest.main()
