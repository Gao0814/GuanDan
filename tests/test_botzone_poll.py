from __future__ import annotations

import json
import unittest

from integrations.botzone.models import DealRequest
from integrations.botzone.poll import MAX_POLL_BYTES, PollFormatError, parse_poll


def _deal(player: int = 0) -> dict[str, object]:
    return {
        "stage": "deal",
        "deliver": list(range(player * 27, (player + 1) * 27)),
        "your_id": player,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _envelope(*requests: dict[str, object], responses: list[object] | None = None) -> str:
    return json.dumps({"requests": list(requests), "responses": [] if responses is None else responses}, separators=(",", ":"))


class BotzonePollTests(unittest.TestCase):
    def test_single_and_multi_match_preserve_input_order(self) -> None:
        body = ("2 2\nunit-a\n" + _envelope(_deal(0)) + "\nunit-b\n" + _envelope(_deal(1)) + "\nunit-c 1 0\nunit-d 2 4 1 2 3 4\n").encode()
        batch = parse_poll(body)
        self.assertEqual([item.match_id for item in batch.requests], ["unit-a", "unit-b"])
        self.assertTrue(all(isinstance(item.stage, DealRequest) for item in batch.requests))
        self.assertEqual([row.match_id for row in batch.finished], ["unit-c", "unit-d"])
        self.assertTrue(batch.finished[0].is_aborted)
        self.assertEqual(batch.finished[1].scores, (1, 2, 3, 4))

    def test_crlf_and_empty_tail_line_are_accepted(self) -> None:
        body = ("1 0\r\nunit-a\r\n" + _envelope(_deal()) + "\r\n\r\n").encode()
        self.assertEqual(len(parse_poll(body).requests), 1)

    def test_malformed_request_isolated_from_other_match(self) -> None:
        body = ("2 0\nunit-a\n{not-json}\nunit-b\n" + _envelope(_deal(1))).encode()
        batch = parse_poll(body)
        self.assertEqual(batch.requests[0].diagnostic, "malformed_request")
        self.assertIsNotNone(batch.requests[1].stage)

    def test_structural_errors_fail_closed(self) -> None:
        invalid_bodies = (
            b"1 0\nunit-a\n{}\nextra",
            b"2 0\nunit-a\n{}\nunit-a\n{}",
            b"1 0\nunit\x00a\n{}",
            b"1 0\nunit-a\n{}\n\ninside",
            b"1 0\nunit-a\n\xff",
            b"1 0\nunit-a\n{}\r\ninjected",
        )
        for body in invalid_bodies:
            with self.subTest(body=body[:8]):
                with self.assertRaises(PollFormatError):
                    parse_poll(body)
        with self.assertRaises(PollFormatError):
            parse_poll(b"x" * (MAX_POLL_BYTES + 1))

    def test_finished_row_counts_and_scores_are_strict(self) -> None:
        for line in ("unit-a 0 2 1", "unit-a 4 0", "unit-a 0 0 1", "unit-a 0 1 score"):
            with self.subTest(line=line):
                with self.assertRaises(PollFormatError):
                    parse_poll(("0 1\n" + line).encode())


if __name__ == "__main__":
    unittest.main()
