from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.play_adapter import NoTributeRuleBasedHandler
from integrations.botzone.session import SessionStore


def _deal_inner() -> dict[str, object]:
    return {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}


def _deal() -> str:
    return json.dumps({"requests": [_deal_inner()], "responses": []}, separators=(",", ":"))


def _play() -> str:
    return json.dumps(
        {"requests": [_deal_inner(), {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False, "tribute_cards": {}, "return_cards": {}}}], "responses": [[]]},
        separators=(",", ":"),
    )


class _FakeTransport:
    def __init__(self, polls: list[bytes | Exception]) -> None:
        self.polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        result = self.polls.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class BotzoneRuleAgentE2ETests(unittest.TestCase):
    def test_deal_play_failure_restart_and_acknowledgement_are_offline(self) -> None:
        with TemporaryDirectory() as root:
            first = (f"1 0\nunit-a\n{_deal()}").encode()
            second = (f"1 0\nunit-a\n{_play()}").encode()
            transport = _FakeTransport([first, second, RuntimeError("offline"), b"0 0\n"])
            store = SessionStore(root)
            handler = NoTributeRuleBasedHandler()
            connector = MockConnector(store, transport, handler)
            connector.cycle()
            connector.cycle()
            before = store.load("unit-a")
            assert before is not None
            pending = before.pending_response
            effect_size = len(before.pending_effect.action)
            hand_size = len(before.own_hand)
            connector.cycle()
            self.assertEqual(store.load("unit-a").pending_response, pending)
            MockConnector(SessionStore(root), transport, handler).cycle()
            after = SessionStore(root).load("unit-a")
            assert after is not None
            self.assertIsNone(after.pending_response)
            self.assertEqual(len(after.own_hand), hand_size - effect_size)


if __name__ == "__main__":
    unittest.main()
