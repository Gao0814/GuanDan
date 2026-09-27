from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.game_results import GAME_RESULT_SCHEMA
from integrations.botzone.manual_batch import (
    BatchLaunchError,
    build_argument_parser,
    main,
    _read_jsonl_results,
    run_batch,
)


def _option(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def _write_fake_evidence(
    argv: list[str],
    stdout: object,
    *,
    results: tuple[str, ...],
    stop_reason: str,
    exit_code: int,
) -> None:
    result_path = Path(_option(argv, "--game-results-file"))
    audit_path = Path(_option(argv, "--audit-file"))
    result_path.write_text(
        "".join(
            json.dumps(
                {"game_no": number, "result": result, "schema": GAME_RESULT_SCHEMA, "version": 1},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for number, result in enumerate(results, start=1)
        ),
        encoding="utf-8",
    )
    counts = Counter(results)
    audit = {
        "schema": "botzone_local_smoke_audit",
        "exit_code": exit_code,
        "stop_reason": stop_reason,
        "finished_qualified": len(results),
        "result_category_counts": [[name, count] for name, count in sorted(counts.items())],
    }
    audit_path.write_text(json.dumps(audit, separators=(",", ":")), encoding="utf-8")
    summary = (
        f"connector_finished cycles=12 finished={len(results)} history=disabled "
        f"decision_trace=disabled game_results=ok game_results_recorded={len(results)} exit={exit_code}\n"
    )
    stdout.write(summary)  # type: ignore[attr-defined]


class BotzoneManualBatchTests(unittest.TestCase):
    def test_defaults_and_custom_positive_game_count(self) -> None:
        parser = build_argument_parser()
        defaults = parser.parse_args([])
        custom = parser.parse_args(["--games", "3", "--max-cycles", "1234", "--max-wall-seconds", "5678"])
        self.assertEqual((defaults.games, defaults.max_cycles, defaults.max_wall_seconds), (10, None, None))
        self.assertEqual((custom.games, custom.max_cycles, custom.max_wall_seconds), (3, 1234, 5678))
        for value in ("0", "-1", "ten", "1.5"):
            with self.subTest(value=value), self.assertRaises(SystemExit), redirect_stderr(StringIO()):
                parser.parse_args(["--games", value])

    def test_malformed_result_category_is_rejected_without_raising(self) -> None:
        with TemporaryDirectory() as temporary:
            results = Path(temporary) / "games.jsonl"
            results.write_text(
                json.dumps(
                    {"game_no": 1, "result": [], "schema": GAME_RESULT_SCHEMA, "version": 1},
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertIsNone(_read_jsonl_results(results))

    def test_one_foreground_connector_records_three_games_and_preserves_old_workspace_evidence(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "BotzoneWorkspace"
            workspace.mkdir()
            old_batch = workspace / "old-batch"
            old_batch.mkdir()
            old_evidence = old_batch / "sentinel.json"
            old_bytes = b"old evidence stays byte-for-byte\n"
            old_evidence.write_bytes(old_bytes)
            calls: list[tuple[list[str], dict[str, object]]] = []
            runtime_count = 0

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal runtime_count
                calls.append((argv, kwargs))
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                runtime_count += 1
                _write_fake_evidence(
                    argv,
                    kwargs["stdout"],
                    results=("local_team_win", "local_team_loss", "platform_error"),
                    stop_reason="cycle_limit_unfinished",
                    exit_code=6,
                )
                return subprocess.CompletedProcess(argv, 6, "", "")

            messages: list[str] = []
            outcome = run_batch(
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=messages.append,
            )

            batch_directories = [path for path in workspace.iterdir() if path.is_dir() and path != old_batch]
            batch = batch_directories[0]
            old_after = old_evidence.read_bytes()
            batch_files_exist = all(
                (batch / relative).is_file()
                for relative in (
                    Path("game-results.jsonl"),
                    Path("audit") / "completion-audit.json",
                    Path("streams") / "stdout.txt",
                    Path("streams") / "stderr.txt",
                )
            )

        self.assertEqual(len(batch_directories), 1)
        self.assertEqual(runtime_count, 1)
        self.assertEqual(len(calls), 3)  # process guard, zero-network preflight, one connector
        self.assertEqual(old_after, old_bytes)
        self.assertEqual(outcome.requested_games, 10)
        self.assertEqual(outcome.connector_exit_code, 6)
        self.assertEqual(outcome.game_results_status, "complete")
        self.assertEqual(outcome.confirmed_finished, 3)
        self.assertEqual(outcome.recorded_games, 3)
        self.assertEqual(outcome.result_counts, (("local_team_loss", 1), ("local_team_win", 1), ("platform_error", 1)))
        self.assertTrue(any(message.startswith("batch_result category=configured_limit_reached exit=6") for message in messages))
        self.assertEqual(_option(calls[2][0], "--stop-after-finished"), "10")
        self.assertEqual(_option(calls[2][0], "--max-cycles"), "10000")
        self.assertEqual(_option(calls[2][0], "--max-wall-seconds"), "36000")
        self.assertIn("--stage-trace", calls[2][0])
        self.assertEqual(_option(calls[2][0], "--agent"), "deepseek")
        self.assertEqual(_option(calls[2][0], "--timeout-seconds"), "30")
        self.assertEqual(calls[1][0][0], calls[2][0][0])
        self.assertIn("--preflight-only", calls[1][0])
        self.assertNotIn("--preflight-only", calls[2][0])
        self.assertNotIn("--history-file", calls[2][0])
        self.assertNotIn("--decision-trace-file", calls[2][0])
        self.assertEqual([kwargs["env"]["DEEPSEEK_MODEL"] for _, kwargs in calls[1:]], ["deepseek-flash", "deepseek-flash"])
        self.assertEqual([kwargs["cwd"] for _, kwargs in calls], [base, base, base])
        self.assertIn("请等页面显示“已连接”", "\n".join(messages))
        self.assertEqual(len(messages), 5)  # startup notices and final summary only
        self.assertTrue(batch_files_exist)

    def test_custom_target_and_limits_reach_same_single_connector_process(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            runtime: list[list[str]] = []
            messages: list[str] = []

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                runtime.append(argv)
                _write_fake_evidence(
                    argv,
                    kwargs["stdout"],
                    results=("local_team_win", "local_team_loss", "invalid_score_shape"),
                    stop_reason="finished_target",
                    exit_code=0,
                )
                return subprocess.CompletedProcess(argv, 0, "", "")

            outcome = run_batch(
                games=3,
                max_cycles=1234,
                max_wall_seconds=5678,
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=messages.append,
            )

        self.assertEqual(len(runtime), 1)
        self.assertEqual(_option(runtime[0], "--stop-after-finished"), "3")
        self.assertEqual(_option(runtime[0], "--max-cycles"), "1234")
        self.assertEqual(_option(runtime[0], "--max-wall-seconds"), "5678")
        self.assertEqual(_option(runtime[0], "--decision-timeout-seconds"), "119")
        self.assertEqual(_option(runtime[0], "--table-timeout-seconds"), "120")
        self.assertEqual(outcome.game_results_status, "complete")
        self.assertEqual(outcome.category, "target_reached")
        self.assertTrue(any(message.startswith("batch_result category=target_reached exit=0") for message in messages))

    def test_manual_stop_preserves_already_recorded_result(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            runtime_call = 0

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal runtime_call
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                runtime_call += 1
                _write_fake_evidence(
                    argv,
                    kwargs["stdout"],
                    results=("platform_error",),
                    stop_reason="interrupted",
                    exit_code=130,
                )
                return subprocess.CompletedProcess(argv, 130, "", "")

            outcome = run_batch(
                games=10,
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=lambda _message: None,
            )
            recorded = (outcome.batch_directory / "game-results.jsonl").read_text(encoding="utf-8")
            batch_retained = outcome.batch_directory.exists()

        self.assertEqual(runtime_call, 1)
        self.assertEqual(outcome.connector_exit_code, 130)
        self.assertEqual(outcome.game_results_status, "complete")
        self.assertEqual(outcome.confirmed_finished, 1)
        self.assertIn('"result":"platform_error"', recorded)
        self.assertTrue(batch_retained)
        self.assertEqual(outcome.category, "user_interrupted")

    def test_preflight_failure_uses_fixed_category_and_does_not_touch_old_files(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            sentinel = workspace / "prior-evidence.json"
            sentinel.write_text("keep", encoding="utf-8")
            calls = 0

            def fake_process(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal calls
                calls += 1
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                return subprocess.CompletedProcess(argv, 2, "private output", "private error")

            messages: list[str] = []
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    [],
                    process_runner=fake_process,
                    announce=messages.append,
                    workspace_root=workspace,
                    repository_root=base,
                )

            batch_dirs = [path for path in workspace.iterdir() if path.is_dir()]
            sentinel_after = sentinel.read_text(encoding="utf-8")
            streams_created = (batch_dirs[0] / "streams" / "stdout.txt").exists()

        self.assertEqual(exit_code, 2)
        self.assertIn("batch_error category=preflight_failed exit=2", stderr.getvalue())
        self.assertIn(str(batch_dirs[0]), stderr.getvalue())
        self.assertNotIn("private", stderr.getvalue())
        self.assertEqual(calls, 2)
        self.assertEqual(sentinel_after, "keep")
        self.assertEqual(len(batch_dirs), 1)
        self.assertFalse(streams_created)

    def test_existing_connector_stops_before_creating_batch_directory(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            sentinel = workspace / "old.json"
            sentinel.write_text("old", encoding="utf-8")
            calls = 0

            def fake_process(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal calls
                calls += 1
                return subprocess.CompletedProcess(argv, 0, "connector_running\n", "")

            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    [],
                    process_runner=fake_process,
                    announce=lambda _message: None,
                    workspace_root=workspace,
                    repository_root=base,
                )
            entries = list(workspace.iterdir())

        self.assertEqual(exit_code, 2)
        self.assertIn("batch_error category=connector_already_running exit=2", stderr.getvalue())
        self.assertEqual(calls, 1)
        self.assertEqual(entries, [sentinel])

    def test_process_probe_failure_is_classified_without_leaking_output_or_creating_a_batch(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            old_evidence = workspace / "old.json"
            old_evidence.write_text("keep", encoding="utf-8")

            def failed_probe(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(argv, 5, "private url", "private error")

            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    [],
                    process_runner=failed_probe,
                    announce=lambda _message: None,
                    workspace_root=workspace,
                    repository_root=base,
                )
            entries = list(workspace.iterdir())

        self.assertEqual(exit_code, 2)
        self.assertIn("batch_error category=connector_status_unavailable exit=2", stderr.getvalue())
        self.assertNotIn("private", stderr.getvalue())
        self.assertEqual(entries, [old_evidence])

    def test_workspace_prepare_failure_has_a_fixed_category(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "missing-parent" / "workspace"
            calls = 0

            def fake_process(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal calls
                calls += 1
                return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")

            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    [],
                    process_runner=fake_process,
                    announce=lambda _message: None,
                    workspace_root=workspace,
                    repository_root=base,
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("batch_error category=workspace_unavailable exit=2", stderr.getvalue())
        self.assertEqual(calls, 1)
        self.assertFalse(workspace.parent.exists())

    def test_runtime_early_exit_reports_fixed_category_and_preserves_process_exit(self) -> None:
        for output, return_code, category in (
            ("configuration_error\n", 2, "connector_configuration_error"),
            ("", 9, "connector_early_exit"),
        ):
            with self.subTest(category=category), TemporaryDirectory() as temporary:
                base = Path(temporary)
                workspace = base / "workspace"
                workspace.mkdir()

                def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                    if argv[0] == "powershell.exe":
                        return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                    if "--preflight-only" in argv:
                        return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                    kwargs["stdout"].write(output)  # type: ignore[attr-defined]
                    kwargs["stderr"].write("private runtime detail")  # type: ignore[attr-defined]
                    return subprocess.CompletedProcess(argv, return_code, "", "")

                messages: list[str] = []
                outcome = run_batch(
                    workspace_root=workspace,
                    repository_root=base,
                    process_runner=fake_process,
                    announce=messages.append,
                )

            self.assertEqual(outcome.category, category)
            self.assertEqual(outcome.exit_code, return_code)
            self.assertIsNone(outcome.confirmed_finished)
            self.assertEqual(outcome.game_results_status, "incomplete")
            self.assertTrue(any(message.startswith(f"batch_result category={category} exit={return_code}") for message in messages))
            self.assertNotIn("private runtime detail", "\n".join(messages))

    def test_keyboard_interrupt_during_foreground_runtime_is_visible_and_returns_130(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                result_path = Path(_option(argv, "--game-results-file"))
                result_path.write_text(
                    json.dumps(
                        {"game_no": 1, "result": "local_team_win", "schema": GAME_RESULT_SCHEMA, "version": 1},
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
                raise KeyboardInterrupt

            messages: list[str] = []
            batch_retained = False
            outcome = run_batch(
                games=2,
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=messages.append,
            )
            batch_retained = outcome.batch_directory.exists()

        self.assertEqual(outcome.category, "user_interrupted")
        self.assertEqual(outcome.exit_code, 130)
        self.assertEqual(outcome.recorded_games, 1)
        self.assertIsNone(outcome.confirmed_finished)
        self.assertTrue(batch_retained)
        self.assertTrue(any("confirmed_finished=unknown/2" in message for message in messages))

    def test_incomplete_result_recording_reports_the_partial_count(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")
                result_path = Path(_option(argv, "--game-results-file"))
                audit_path = Path(_option(argv, "--audit-file"))
                result_path.write_text(
                    json.dumps(
                        {"game_no": 1, "result": "local_team_win", "schema": GAME_RESULT_SCHEMA, "version": 1},
                        separators=(",", ":"),
                    ) + "\n",
                    encoding="utf-8",
                )
                audit_path.write_text(
                    json.dumps(
                        {
                            "schema": "botzone_local_smoke_audit",
                            "exit_code": 0,
                            "stop_reason": "finished_target",
                            "finished_qualified": 2,
                            "result_category_counts": [["local_team_win", 2]],
                        },
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
                kwargs["stdout"].write(  # type: ignore[attr-defined]
                    "connector_finished cycles=5 finished=2 history=disabled decision_trace=disabled "
                    "game_results=failed game_results_recorded=1 exit=0\n"
                )
                return subprocess.CompletedProcess(argv, 0, "", "")

            outcome = run_batch(
                games=2,
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=lambda _message: None,
            )

        self.assertEqual(outcome.game_results_status, "incomplete")
        self.assertEqual(outcome.confirmed_finished, 2)
        self.assertEqual(outcome.recorded_games, 1)
        self.assertEqual(outcome.result_counts, (("local_team_win", 1),))
        self.assertEqual(outcome.exit_code, 7)


if __name__ == "__main__":
    unittest.main()
