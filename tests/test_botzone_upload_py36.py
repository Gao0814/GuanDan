import ast
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "botzone_upload_py36" / "__main__.py"
ARCHIVE = ROOT / "dist" / "guandan_rule_ai_py36.zip"


def _deal(hand, player_id=0):
    return {
        "stage": "deal",
        "deliver": hand,
        "your_id": player_id,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _play(history=None):
    slots = list(history or [])
    slots = [[]] * (4 - len(slots)) + slots
    return {
        "stage": "play",
        "global": {
            "level": "2",
            "tribute": 0,
            "first": None,
            "last": None,
            "tribute_cards": {},
            "return_cards": {},
            "resist": False,
        },
        "history": slots,
        "done": [],
        "pass_on": -1,
    }


def _run(payload):
    completed = subprocess.run(
        [sys.executable, str(SOURCE)],
        input=json.dumps(payload, separators=(",", ":")) + "\n",
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    lines = completed.stdout.splitlines()
    if len(lines) != 1:
        raise AssertionError("Bot must emit exactly one JSON line")
    return json.loads(lines[0]), completed.stderr


class BotzonePython36UploadTests(unittest.TestCase):
    def setUp(self):
        self.hand = list(range(27))

    @staticmethod
    def _hand_without_bombs_or_straight_flushes():
        hand = []
        for rank_index in range(13):
            suit_index = rank_index % 4
            first_copy = rank_index * 4 + suit_index
            hand.extend((first_copy, first_copy + 54))
        hand.append(1)
        return hand

    def test_source_uses_python_36_grammar_and_standard_library(self):
        source = SOURCE.read_text(encoding="utf-8")
        ast.parse(source, filename=str(SOURCE), feature_version=(3, 6))
        self.assertNotIn("from __future__ import annotations", source)
        self.assertNotIn("dataclass", source)
        self.assertNotIn("dotenv", source)

    def test_deal_uses_canonical_outer_response(self):
        output, stderr = _run({"requests": [_deal(self.hand)], "responses": []})
        self.assertEqual(output, {"response": []})
        self.assertEqual(stderr, "")

    def test_free_lead_returns_natural_legal_action(self):
        payload = {"requests": [_deal(self.hand), _play()], "responses": [[]]}
        output, stderr = _run(payload)
        action, claim = output["response"]
        self.assertTrue(action)
        self.assertEqual(action, claim)
        self.assertTrue(set(action).issubset(self.hand))
        self.assertEqual(stderr, "")

    def test_follows_single_with_smallest_available_beating_card(self):
        # ID 8 is rank 3; this hand has no bomb or straight flush override.
        hand = self._hand_without_bombs_or_straight_flushes()
        history = [{"player": 1, "response": [[8], [8]]}]
        payload = {"requests": [_deal(hand), _play(history)], "responses": [[]]}
        output, unused_stderr = _run(payload)
        action, claim = output["response"]
        self.assertEqual(action, claim)
        self.assertEqual(len(action), 1)
        self.assertIn(action[0], hand)
        self.assertNotEqual(action[0] // 4, 2)

    def test_passes_on_non_single_when_no_natural_beating_action(self):
        hand = self._hand_without_bombs_or_straight_flushes()
        history = [{"player": 1, "response": [[4, 58], [4, 58]]}]
        payload = {"requests": [_deal(hand), _play(history)], "responses": [[]]}
        output, unused_stderr = _run(payload)
        self.assertEqual(output, {"response": [[], []]})

    def test_replay_removes_previously_played_physical_cards(self):
        first_play = _play()
        second_play = _play([{"player": 0, "response": [[8], [8]]}])
        payload = {
            "requests": [_deal(self.hand), first_play, second_play],
            "responses": [[], [[8], [8]]],
        }
        output, unused_stderr = _run(payload)
        action = output["response"][0]
        self.assertNotIn(8, action)

    def test_archive_has_main_at_root_and_is_under_upload_limit(self):
        self.assertTrue(ARCHIVE.is_file())
        self.assertLessEqual(ARCHIVE.stat().st_size, 4 * 1024 * 1024)
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertEqual(archive.namelist(), ["__main__.py"])
            archived = archive.read("__main__.py").decode("utf-8")
        self.assertEqual(archived, SOURCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
