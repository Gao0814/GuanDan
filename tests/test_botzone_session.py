from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.protocol import parse_stage_request
from integrations.botzone.session import SessionStorageError, SessionStore


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _deal(player: int) -> DealRequest:
    parsed = parse_stage_request(
        {"stage": "deal", "deliver": list(range(player * 27, (player + 1) * 27)), "your_id": player, "global": _global()}
    )
    assert isinstance(parsed, DealRequest)
    return parsed


def _play() -> PlayRequest:
    parsed = parse_stage_request({"stage": "play", "history": [], "done": [], "pass_on": -1, "global": _global()})
    assert isinstance(parsed, PlayRequest)
    return parsed


class BotzoneSessionTests(unittest.TestCase):
    def test_pending_failure_restart_and_acknowledgement_transaction(self) -> None:
        with TemporaryDirectory() as root:
            store = SessionStore(root)
            record, call_handler = store.prepare("unit-a", b'{"request":1}', _deal(0))
            self.assertTrue(call_handler)
            record = store.reserve_handler(record)
            stored = store.complete_handler(record, b'{"response":1}')
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
            record = store.complete_handler(store.reserve_handler(record), b"ok")
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
            first = store.complete_handler(store.reserve_handler(first), b"a")
            second = store.complete_handler(store.reserve_handler(second), b"b")
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


if __name__ == "__main__":
    unittest.main()
