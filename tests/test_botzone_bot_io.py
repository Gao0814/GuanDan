from __future__ import annotations

from copy import deepcopy
import json
import unittest

from integrations.botzone.bot_io import BotEnvelopeError, encode_bot_response, parse_bot_envelope
from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.protocol import parse_stage_request


def _global(*, play: bool = False) -> dict[str, object]:
    value: dict[str, object] = {"level": "2", "tribute": 0, "first": None, "last": None}
    if play:
        value.update({"resist": False, "tribute_cards": {}, "return_cards": {}})
    return value


def _deal() -> dict[str, object]:
    return {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}


def _play(history: list[object] | None = None) -> dict[str, object]:
    entries = [] if history is None else history
    return {"stage": "play", "history": ([[]] * (4 - len(entries))) + entries, "done": [], "pass_on": -1, "global": _global(play=True)}


def _envelope(requests: list[dict[str, object]], responses: list[object], **optional: object) -> dict[str, object]:
    return {"requests": requests, "responses": responses, **optional}


class BotJsonEnvelopeTests(unittest.TestCase):
    def test_deal_play_envelope_replays_current_hand_and_optional_fields(self) -> None:
        payload = _envelope([_deal(), _play()], [[]], data="", globaldata="", time_limit="", memory_limit="")
        parsed = parse_bot_envelope(payload)
        self.assertIsInstance(parsed.current_request, PlayRequest)
        self.assertEqual(parsed.replay.local_player_id, 0)
        self.assertEqual(parsed.replay.own_hand, tuple(range(27)))
        self.assertEqual(parsed.replay.history, ())
        self.assertEqual(parsed.replay.latest_window, ())
        self.assertEqual(len(parsed.requests), 2)

    def test_outer_shape_and_inner_errors_fail_closed_without_mutation(self) -> None:
        invalid = (
            _envelope([], []),
            _envelope([_deal()], [[]]),
            {"requests": [_deal()], "responses": [], "unknown": 1},
            {"requests": (), "responses": []},
            _envelope([{"stage": "play"}], []),
        )
        for payload in invalid:
            original = deepcopy(payload)
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaises(BotEnvelopeError):
                    parse_bot_envelope(payload)
            self.assertEqual(payload, original)

    def test_replay_deducts_pass_natural_and_single_wildcard_once(self) -> None:
        natural = [[0], [0]]
        wildcard = [[4], [0]]
        requests = [
            _deal(),
            _play(),
            _play([{"player": 0, "response": natural}]),
            _play([{"player": 0, "response": natural}, {"player": 0, "response": wildcard}]),
            _play([{"player": 0, "response": natural}, {"player": 0, "response": wildcard}, {"player": 0, "response": [[], []]}]),
        ]
        parsed = parse_bot_envelope(_envelope(requests, [[], natural, wildcard, [[], []]]))
        self.assertEqual(parsed.replay.own_hand, tuple(card for card in range(27) if card not in {0, 4}))
        self.assertEqual(len(parsed.replay.history), 3)
        self.assertEqual(parsed.replay.latest_window, parsed.replay.history)

    def test_replay_rejects_response_and_profile_drift(self) -> None:
        bad_responses = (
            [[], [[99], [99]]],
            [[], [[0, 0], [0, 0]]],
            [[], [[4], [52]]],
        )
        for responses in bad_responses:
            with self.subTest(responses=responses):
                with self.assertRaises(BotEnvelopeError):
                    parse_bot_envelope(_envelope([_deal(), _play(), _play()], responses))
        drift = _play()
        drift["global"] = _global(play=True)
        drift["global"]["level"] = "3"
        with self.assertRaises(BotEnvelopeError):
            parse_bot_envelope(_envelope([_deal(), drift], [[]]))

    def test_response_wrapper_is_canonical_for_deal_pass_natural_and_wildcard(self) -> None:
        deal = parse_stage_request(_deal())
        play = parse_stage_request(_play())
        assert isinstance(deal, DealRequest) and isinstance(play, PlayRequest)
        cases = ((deal, b"[]", b'{"response":[]}'), (play, b"[[],[]]", b'{"response":[[],[]]}'),
                 (play, b"[[0],[0]]", b'{"response":[[0],[0]]}'), (play, b"[[4],[0]]", b'{"response":[[4],[0]]}'))
        for stage, response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(encode_bot_response(stage, response), expected)
        with self.assertRaises(BotEnvelopeError):
            encode_bot_response(deal, b"[[],[]]")


if __name__ == "__main__":
    unittest.main()
