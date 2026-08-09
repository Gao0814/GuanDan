from __future__ import annotations

from copy import deepcopy
import unittest

from integrations.botzone.cards import card_id_for
from integrations.botzone.models import DealRequest, PlayRequest, UnsupportedStage
from integrations.botzone.protocol import (
    ProtocolValidationError,
    parse_action_claim,
    parse_stage_request,
)


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _deal(player: int, cards: list[int]) -> dict[str, object]:
    return {"stage": "deal", "deliver": cards, "your_id": player, "global": _global()}


def _play(
    history: list[dict[str, object]] | None = None,
    *,
    done: list[int] | None = None,
    pass_on: int = -1,
) -> dict[str, object]:
    return {
        "stage": "play",
        "history": [] if history is None else history,
        "done": [] if done is None else done,
        "pass_on": pass_on,
        "global": _global(),
    }


class BotzoneProtocolTests(unittest.TestCase):
    def test_deal_and_play_parse_to_immutable_models(self) -> None:
        deal = parse_stage_request(_deal(2, list(range(54, 81))))
        self.assertIsInstance(deal, DealRequest)
        assert isinstance(deal, DealRequest)
        self.assertEqual(deal.response_json(), [])
        self.assertEqual(deal.deliver[0], 54)

        play = parse_stage_request(_play())
        self.assertIsInstance(play, PlayRequest)
        assert isinstance(play, PlayRequest)
        self.assertEqual(play.history, ())
        self.assertEqual(play.global_state.level, "2")

    def test_pass_and_natural_action_claim_encoding(self) -> None:
        self.assertEqual(parse_action_claim([[], []], level="2").to_json(), [[], []])
        ace_hearts = card_id_for("A", "h")
        natural = parse_action_claim([[ace_hearts], [ace_hearts]], level="2", known_hand_ids=[ace_hearts])
        self.assertEqual(natural.to_json(), [[ace_hearts], [ace_hearts]])
        self.assertTrue(parse_action_claim([[ace_hearts, 1], [1, ace_hearts]], level="2").action)

    def test_single_and_double_wildcard_claims_are_face_based(self) -> None:
        wildcard_one = card_id_for("2", "h", 0)
        wildcard_two = card_id_for("2", "h", 1)
        natural = card_id_for("3", "d")
        declared_one = card_id_for("4", "s", 1)
        declared_two = card_id_for("5", "c", 0)

        one = parse_action_claim(
            [[natural, wildcard_one], [declared_one, natural]],
            level="2",
            known_hand_ids=[natural, wildcard_one],
        )
        self.assertEqual(one.to_json(), [[natural, wildcard_one], [declared_one, natural]])
        two = parse_action_claim(
            [[wildcard_one, wildcard_two], [declared_two, declared_one]],
            level="2",
            known_hand_ids=[wildcard_one, wildcard_two],
        )
        self.assertEqual(two.to_json(), [[wildcard_one, wildcard_two], [declared_two, declared_one]])

    def test_claim_matches_non_wild_faces_across_deck_copies(self) -> None:
        wildcard = card_id_for("2", "h", 0)
        first_copy = card_id_for("3", "d", 0)
        second_copy = card_id_for("3", "d", 1)
        declared = card_id_for("4", "s", 0)
        parsed = parse_action_claim(
            [[first_copy, wildcard], [declared, second_copy]],
            level="2",
            known_hand_ids=[first_copy, wildcard],
        )
        self.assertEqual(parsed.claim, (declared, second_copy))

    def test_claim_fails_closed_for_illegal_semantics(self) -> None:
        wildcard = card_id_for("2", "h")
        natural = card_id_for("3", "d")
        with self.assertRaises(ProtocolValidationError):
            parse_action_claim([[wildcard], [52]], level="2")
        with self.assertRaises(ProtocolValidationError):
            parse_action_claim([[natural], [natural, 1]], level="2")
        with self.assertRaises(ProtocolValidationError):
            parse_action_claim([[natural, natural], [natural, natural]], level="2")
        with self.assertRaises(ProtocolValidationError):
            parse_action_claim([[natural], [natural]], level="2", known_hand_ids=[])
        with self.assertRaises(ProtocolValidationError):
            parse_action_claim([[True], [True]], level="2")

    def test_history_and_requests_fail_as_a_whole_without_mutating_input(self) -> None:
        malformed = _play(history=[{"player": 0, "response": [[0], [0]]}] * 5)
        original = deepcopy(malformed)
        with self.assertRaises(ProtocolValidationError):
            parse_stage_request(malformed)
        self.assertEqual(malformed, original)

        for payload in (
            _deal(0, list(range(26))),
            _play(history=[{"player": True, "response": [[], []]}]),
            _play(done=[0, 0]),
            _play(pass_on=True),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolValidationError):
                    parse_stage_request(payload)

    def test_unsupported_stages_never_make_a_play_response(self) -> None:
        for stage in ("tribute", "return", "other"):
            result = parse_stage_request({"stage": stage})
            with self.subTest(stage=stage):
                self.assertIsInstance(result, UnsupportedStage)
                assert isinstance(result, UnsupportedStage)
                self.assertEqual(result.to_json(), {"error": "unsupported_stage", "stage": stage})
                self.assertFalse(hasattr(result, "response_json"))


if __name__ == "__main__":
    unittest.main()
