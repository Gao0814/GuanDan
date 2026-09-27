from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.rolling_results import (
    RECENT_RESULTS_FILENAME,
    RESULT_UNCONFIRMED,
    RecentResultsError,
    RollingGameResultRecorder,
    prepare_recent_results,
    read_recent_results,
    recent_results_paths,
)


def _legacy_batch(root: Path, name: str, results: tuple[str, ...]) -> tuple[Path, bytes]:
    batch = root / name
    batch.mkdir()
    raw = "".join(
        json.dumps(
            {
                "game_no": index,
                "result": result,
                "schema": "botzone_manual_batch_game_result",
                "version": 1,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for index, result in enumerate(results, start=1)
    ).encode("utf-8")
    (batch / "game-results.jsonl").write_bytes(raw)
    return batch, raw


class BotzoneRollingResultsTests(unittest.TestCase):
    def test_capacity_ten_continues_from_seven_to_twelve_without_renumbering(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.mkdir(exist_ok=True)
            _, state_path, _ = recent_results_paths(root)
            prepare_recent_results(root, 10)
            first = RollingGameResultRecorder(state_path, 10)
            for _ in range(7):
                first.record_finished("local_team_win")
            first.close()

            prepare_recent_results(root, 10)
            second = RollingGameResultRecorder(state_path, 10)
            for _ in range(5):
                second.record_finished("local_team_loss")
            second.close()
            snapshot, records = read_recent_results(state_path)

        self.assertEqual(snapshot.total_games, 12)
        self.assertEqual(snapshot.retained_count, 10)
        self.assertEqual([record["game_no"] for record in records], list(range(3, 13)))
        self.assertEqual([record["result"] for record in records[:5]], ["local_team_win"] * 5)
        self.assertEqual([record["result"] for record in records[5:]], ["local_team_loss"] * 5)

    def test_same_minute_record_names_are_unique_and_keep_display_time_and_timezone(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, state_path, _ = recent_results_paths(root)
            prepare_recent_results(root, 10)
            now = datetime(2026, 9, 27, 23, 33, tzinfo=timezone.utc)
            recorder = RollingGameResultRecorder(state_path, 10, clock=lambda: now)
            for _ in range(3):
                recorder.record_finished("local_team_win")
            recorder.close()
            _, records = read_recent_results(state_path)

        self.assertEqual(len({record["record_key"] for record in records}), 3)
        self.assertTrue(all("_" in record["record_key"] and ":" not in record["record_key"] for record in records))
        self.assertEqual(len({record["display_time"] for record in records}), 1)
        self.assertTrue(all(isinstance(record["local_timezone"], dict) for record in records))
        self.assertTrue(all(record["timestamp_kind"] == "completed_at" for record in records))

    def test_first_legacy_import_is_idempotent_and_keeps_source_bytes_unchanged(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy, original = _legacy_batch(root, "manual-batch-legacy-a", ("local_team_win", "platform_error"))
            result_path = legacy / "game-results.jsonl"
            prepare_recent_results(root, 10)
            first_snapshot, first_records = read_recent_results(recent_results_paths(root)[1])
            prepare_recent_results(root, 10)
            second_snapshot, second_records = read_recent_results(recent_results_paths(root)[1])
            after = result_path.read_bytes()

        self.assertEqual(first_snapshot.total_games, 2)
        self.assertEqual(second_snapshot.total_games, 2)
        self.assertEqual(first_records, second_records)
        self.assertEqual([record["game_no"] for record in second_records], [1, 2])
        self.assertEqual([record["source_game_no"] for record in second_records], [1, 2])
        self.assertTrue(all(record["display_time"] is None for record in second_records))
        self.assertTrue(all(record["timestamp_kind"] == "unknown" for record in second_records))
        self.assertEqual(after, original)

    def test_ambiguous_old_batches_require_an_exact_source(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, first_bytes = _legacy_batch(root, "manual-batch-first", ("local_team_win",))
            second, second_bytes = _legacy_batch(root, "manual-batch-second", ("local_team_loss",))
            with self.assertRaises(RecentResultsError) as raised:
                prepare_recent_results(root, 10)
            self.assertEqual(raised.exception.category, "legacy_import_ambiguous")
            prepare_recent_results(root, 10, import_from=first.name)
            _, records = read_recent_results(recent_results_paths(root)[1])
            first_after = (first / "game-results.jsonl").read_bytes()
            second_after = (second / "game-results.jsonl").read_bytes()

        self.assertEqual([record["result"] for record in records], ["local_team_win"])
        self.assertEqual(first_after, first_bytes)
        self.assertEqual(second_after, second_bytes)

    def test_unconfirmed_games_are_recorded_on_shutdown_or_next_start_without_match_ids(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, state_path, _ = recent_results_paths(root)
            prepare_recent_results(root, 10)
            interrupted = RollingGameResultRecorder(state_path, 10)
            interrupted.begin_game("private-match-id")

            recovered = RollingGameResultRecorder(state_path, 10)
            recovered.close()
            snapshot, records = read_recent_results(state_path)
            serialized = state_path.read_text(encoding="utf-8")

        self.assertEqual(snapshot.total_games, 1)
        self.assertEqual(records[0]["result"], RESULT_UNCONFIRMED)
        self.assertEqual(records[0]["timestamp_kind"], "recorded_at")
        self.assertNotIn("private-match-id", serialized)

    def test_new_deal_and_process_close_finalize_unconfirmed_games(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, state_path, _ = recent_results_paths(root)
            prepare_recent_results(root, 10)
            recorder = RollingGameResultRecorder(state_path, 10)
            recorder.begin_game("first-private-match")
            recorder.begin_game("second-private-match")
            recorder.close()
            _, records = read_recent_results(state_path)

        self.assertEqual([record["result"] for record in records], [RESULT_UNCONFIRMED, RESULT_UNCONFIRMED])

    def test_invalid_store_and_write_failure_are_fixed_and_non_throwing_for_recording(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, state_path, _ = recent_results_paths(root)
            prepare_recent_results(root, 3)
            recorder = RollingGameResultRecorder(state_path, 3)
            with patch("integrations.botzone.rolling_results._atomic_write", side_effect=RecentResultsError("recent_results_write_failed")):
                recorder.record_finished("local_team_win")
            self.assertEqual(recorder.status, "failed")
            recorder.close()

            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["records"] = [{"result": "private text"}]
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(RecentResultsError) as raised:
                read_recent_results(state_path)

        self.assertEqual(raised.exception.category, "recent_results_invalid")

    def test_window_path_is_separate_from_per_run_batch_outputs(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, state_path, _ = recent_results_paths(root)
            self.assertEqual(state_path.name, RECENT_RESULTS_FILENAME)
            self.assertEqual(directory.name, "manual-batch-records")
            self.assertNotEqual(directory, root / "manual-batch-current" / "state")


if __name__ == "__main__":
    unittest.main()
