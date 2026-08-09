from __future__ import annotations

from pathlib import Path
import re
import unittest

from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.protocol import (
    ProtocolValidationError,
    parse_stage_request,
    validate_no_tribute_opening,
)


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _deal(player: int, cards: list[int]) -> dict[str, object]:
    return {"stage": "deal", "deliver": cards, "your_id": player, "global": _global()}


def _first_play() -> dict[str, object]:
    return {"stage": "play", "history": [], "done": [], "pass_on": -1, "global": _global()}


class BotzoneNoTributeProfileTests(unittest.TestCase):
    def test_four_deals_then_player_zero_play_is_a_valid_fixture(self) -> None:
        deals: list[DealRequest] = []
        for player in range(4):
            parsed = parse_stage_request(_deal(player, list(range(player * 27, (player + 1) * 27))))
            self.assertIsInstance(parsed, DealRequest)
            assert isinstance(parsed, DealRequest)
            deals.append(parsed)
        first_play = parse_stage_request(_first_play())
        self.assertIsInstance(first_play, PlayRequest)
        assert isinstance(first_play, PlayRequest)
        validate_no_tribute_opening(deals, first_play, first_player_id=0)

    def test_profile_rejects_nonzero_tribute_and_nonempty_prior_state(self) -> None:
        malformed = _first_play()
        malformed["global"] = {"level": "2", "tribute": 1, "first": None, "last": None}
        with self.assertRaises(ProtocolValidationError):
            parse_stage_request(malformed)

        play = parse_stage_request(_first_play())
        assert isinstance(play, PlayRequest)
        deals = [
            parse_stage_request(_deal(player, list(range(player * 27, (player + 1) * 27))))
            for player in range(4)
        ]
        typed_deals = [deal for deal in deals if isinstance(deal, DealRequest)]
        with self.assertRaises(ProtocolValidationError):
            validate_no_tribute_opening(typed_deals, play, first_player_id=1)

    def test_protocol_package_has_no_runtime_or_secret_dependencies(self) -> None:
        package = Path(__file__).parents[1] / "integrations" / "botzone"
        source = "\n".join(
            (package / filename).read_text(encoding="utf-8")
            for filename in ("cards.py", "models.py", "protocol.py")
        )
        forbidden_imports = re.compile(
            r"(?m)^\s*(?:from|import)\s+(?:os|urllib|requests|socket|dotenv|engine|agents)\b"
        )
        self.assertIsNone(forbidden_imports.search(source))
        for marker in (".env", "api_key"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source.lower())


if __name__ == "__main__":
    unittest.main()
