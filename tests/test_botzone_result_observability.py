from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest
from integrations.botzone.poll import FinishedRow
from integrations.botzone.result_observability import (
    ResultObservabilityError,
    ResultObservabilityRecorder,
    ResultObservabilitySnapshot,
    classify_finished_score,
)
from integrations.botzone.runner import ForegroundRunner, RunnerSummary, write_audit
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStore


def _normal_scores(local_seat: int, local_wins: bool, score: int) -> tuple[int, int, int, int]:
    values = [0, 0, 0, 0]
    local_team = (local_seat, (local_seat + 2) % 4)
    target = local_team if local_wins else tuple(seat for seat in range(4) if seat not in local_team)
    for seat in target:
        values[seat] = score
    return tuple(values)  # type: ignore[return-value]


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None}


def _play_envelope() -> str:
    deal = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": _global()}
    play = {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": dict(_global(), resist=False, tribute_cards={}, return_cards={}),
    }
    return json.dumps({"requests": [deal, play], "responses": [[]]}, separators=(",", ":"))


class _Transport:
    def __init__(self, polls: list[bytes]) -> None:
        self._polls = polls
        self.calls = 0

    def poll(self, _: object) -> bytes:
        self.calls += 1
        return self._polls.pop(0)


def _handler(context: HandlerContext) -> HandlerResult:
    if isinstance(context.request, DealRequest):
        return HandlerResult(b"[]")
    return HandlerResult(b"[[0],[0]]", PlayEffect((0,)))


class BotzoneResultObservabilityTests(unittest.TestCase):
    def test_normal_scores_cover_all_local_seats_and_buckets(self) -> None:
        for local_seat in range(4):
            for score in (1, 2, 3):
                with self.subTest(local_seat=local_seat, score=score, outcome="win"):
                    self.assertEqual(
                        classify_finished_score(local_seat, _normal_scores(local_seat, True, score)),
                        ("local_team_win", "score_{}".format(score)),
                    )
                with self.subTest(local_seat=local_seat, score=score, outcome="loss"):
                    self.assertEqual(
                        classify_finished_score(local_seat, _normal_scores(local_seat, False, score)),
                        ("local_team_loss", "score_0"),
                    )

    def test_exact_platform_error_shape_covers_all_offender_positions(self) -> None:
        for offender in range(4):
            scores = [1, 1, 1, 1]
            scores[offender] = -2
            scores[(offender + 2) % 4] = 0
            with self.subTest(offender=offender):
                self.assertEqual(classify_finished_score(0, tuple(scores)), ("platform_error", None))

    def test_malformed_scores_and_non_strict_values_fail_closed(self) -> None:
        malformed = (
            (True, (0, 1, 0, 1)),
            (0, (0, 1, 0)),
            (0, (0, 1, 0, True)),
            (0, (1, 1, 1, 1)),
            (0, (0, 0, 0, 0)),
            (0, (1, 1, 2, 2)),
            (0, (-2, 0, 0, 1)),
            (0, (4, 0, 4, 0)),
        )
        for local_seat, scores in malformed:
            with self.subTest(kind=type(local_seat).__name__, size=len(scores)):
                self.assertEqual(classify_finished_score(local_seat, scores), ("invalid_score_shape", None))

    def test_snapshot_is_frozen_canonical_and_conserved(self) -> None:
        recorder = ResultObservabilityRecorder()
        recorder.record_qualified_finished(0, _normal_scores(0, True, 3))
        recorder.record_qualified_finished(1, _normal_scores(1, False, 2))
        recorder.record_qualified_finished(2, (-2, 1, 0, 1))
        recorder.record_qualified_finished(0, (0, 0, 0, 0))
        snapshot = recorder.snapshot()
        self.assertEqual(
            snapshot.to_json(),
            {
                "result_category_counts": [
                    ["invalid_score_shape", 1],
                    ["local_team_loss", 1],
                    ["local_team_win", 1],
                    ["platform_error", 1],
                ],
                "normal_result_count": 2,
                "local_team_score_counts": [["score_0", 1], ["score_3", 1]],
            },
        )
        self.assertTrue(hasattr(snapshot, "__slots__"))
        with self.assertRaises(FrozenInstanceError):
            snapshot.normal_result_count = 0  # type: ignore[misc]
        with self.assertRaises(ResultObservabilityError):
            ResultObservabilitySnapshot((("local_team_win", 1), ("local_team_win", 1)), 1, (("score_1", 1),))
        with self.assertRaises(ResultObservabilityError):
            ResultObservabilitySnapshot((("local_team_win", 1),), True, (("score_1", 1),))

    def test_only_qualified_finished_rows_record_once(self) -> None:
        play = ("1 0\nsynthetic\n" + _play_envelope()).encode("utf-8")
        finished = b"0 1\nsynthetic 0 4 2 0 2 0\n"
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), _Transport([play, finished, finished]), _handler)
            connector.cycle()
            qualified = connector.cycle()
            duplicate = connector.cycle()
            snapshot = connector.result_observability_snapshot()
        self.assertEqual((qualified.finished_qualified, duplicate.finished_qualified), (1, 0))
        self.assertEqual(snapshot.result_category_counts, (("local_team_win", 1),))
        self.assertEqual(snapshot.local_team_score_counts, (("score_2", 1),))

    def test_unqualified_and_failed_recorder_do_not_change_finished_semantics(self) -> None:
        class _FailingRecorder:
            def record_qualified_finished(self, _: object, __: object) -> None:
                raise RuntimeError("synthetic")

            def snapshot(self) -> ResultObservabilitySnapshot:
                raise ResultObservabilityError("synthetic")

        play = ("1 0\nsynthetic\n" + _play_envelope()).encode("utf-8")
        finished = b"0 1\nsynthetic 0 4 1 0 1 0\n"
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), _Transport([play, finished]), _handler, _FailingRecorder())  # type: ignore[arg-type]
            connector.cycle()
            cycle = connector.cycle()
            self.assertEqual(cycle.finished_qualified, 1)
            with self.assertRaises(ResultObservabilityError):
                connector.result_observability_snapshot()
            self.assertIsNone(SessionStore(root).load("synthetic"))
        with TemporaryDirectory() as root:
            raw = MockConnector(
                SessionStore(root),
                _Transport([b"0 1\nunknown 0 4 1 0 1 0\n"]),
                _handler,
            ).cycle()
            self.assertEqual(raw.finished_qualified, 0)

    def test_runner_keeps_result_aggregate_after_cache_cleanup_and_v7_audit_fails_closed(self) -> None:
        play = ("1 0\nsynthetic\n" + _play_envelope()).encode("utf-8")
        finished = b"0 1\nsynthetic 0 4 1 0 1 0\n"
        with TemporaryDirectory() as root:
            connector = MockConnector(SessionStore(root), _Transport([play, finished]), _handler)
            summary = ForegroundRunner(connector, max_consecutive_failures=1, backoff_seconds=1, sleep=lambda _: None).run(
                max_cycles=2, max_wall_seconds=60, stop_after_finished=1
            )
            self.assertEqual(summary.result_category_counts, (("local_team_win", 1),))
            self.assertEqual(summary.local_team_score_counts, (("score_1", 1),))
            audit = Path(root).parent / "result-observability-audit.json"
            write_audit(audit, summary, 0)
            payload = json.loads(audit.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 7)
        self.assertEqual(payload["result_category_counts"], [["local_team_win", 1]])
        self.assertEqual(payload["local_team_score_counts"], [["score_1", 1]])
        self.assertEqual(payload["normal_result_count"], 1)
        for marker in ("match", "player", "history", "action", "prompt", "reasoning"):
            self.assertNotIn(marker, json.dumps(payload).lower())
        with TemporaryDirectory() as root:
            invalid = replace(summary, result_category_counts=(("platform_error", 1),), normal_result_count=1)
            with self.assertRaises(ValueError):
                write_audit(Path(root).parent / "invalid-result-audit.json", invalid, 0)


if __name__ == "__main__":
    unittest.main()
