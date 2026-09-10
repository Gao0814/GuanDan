from __future__ import annotations

import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.live_launcher import (
    LAUNCHER_CONFIGURATION_EXIT,
    LAUNCHER_ENTRYPOINT_EXIT,
    LauncherError,
    connector_argv,
    main,
    parse_launcher_args,
    run_launcher,
)


TOKEN = "0123456789abcdef0123456789abcdef"


def _argv(root: Path, *, agent: str = "rule", token: object = TOKEN) -> tuple[object, ...]:
    state = root / "state"
    streams = root / "streams"
    state.mkdir(exist_ok=True)
    streams.mkdir(exist_ok=True)
    return (
        "--agent", agent,
        "--state-dir", str(state),
        "--run-token", token,
        "--timeout-seconds", "30",
        "--max-cycles", "100",
        "--max-wall-seconds", "600",
        "--stop-after-finished", "1",
        "--audit-file", str(root / "audit.json"),
        "--stdout-file", str(streams / "stdout.txt"),
        "--stderr-file", str(streams / "stderr.txt"),
    )


class BotzoneLiveLauncherTests(unittest.TestCase):
    def test_in_process_launcher_separates_streams_and_preserves_bounded_arguments(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = _argv(root)
            config = parse_launcher_args(original)
            received: list[str] = []

            def entrypoint(argv: list[str]) -> int:
                received.extend(argv)
                print("synthetic_stdout")
                print("synthetic_stderr", file=__import__("sys").stderr)
                return 23

            self.assertEqual(run_launcher(config, entrypoint), 23)
            self.assertEqual(config.agent, "rule")
            self.assertEqual(tuple(received), connector_argv(config))
            self.assertEqual(tuple(received[:6]), ("--agent", "rule", "--state-dir", str(root / "state"), "--run-token", TOKEN))
            self.assertEqual((root / "streams" / "stdout.txt").read_text(encoding="utf-8"), "synthetic_stdout\n")
            self.assertEqual((root / "streams" / "stderr.txt").read_text(encoding="utf-8"), "synthetic_stderr\n")
            self.assertNotIn(TOKEN, repr(config))
            self.assertNotIn(TOKEN, (root / "streams" / "stdout.txt").read_text(encoding="utf-8"))
            self.assertNotIn(TOKEN, (root / "streams" / "stderr.txt").read_text(encoding="utf-8"))
            (root / "streams" / "stdout.txt").rename(root / "streams" / "stdout-closed.txt")
            (root / "streams" / "stderr.txt").rename(root / "streams" / "stderr-closed.txt")

    def test_optional_private_artifacts_are_forwarded_without_changing_default_arguments(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments = _argv(root) + ("--history-file", str(root / "history.txt"), "--decision-trace-file", str(root / "trace.json"))
            config = parse_launcher_args(arguments)
            self.assertEqual(config.history_file, root / "history.txt")
            self.assertEqual(config.decision_trace_file, root / "trace.json")
            self.assertIn("--history-file", connector_argv(config))
            self.assertIn("--decision-trace-file", connector_argv(config))
            default_root = root / "default"
            default_root.mkdir()
            default = parse_launcher_args(_argv(default_root))
            self.assertIsNone(default.history_file)
            self.assertIsNone(default.decision_trace_file)
            self.assertNotIn("--history-file", connector_argv(default))
            self.assertNotIn("--decision-trace-file", connector_argv(default))

    def test_existing_decision_trace_is_rejected_before_streams_or_connector_start(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = root / "trace.json"
            original = b'{"existing":"trace"}\n'
            trace.write_bytes(original)
            with self.assertRaises(LauncherError):
                parse_launcher_args(_argv(root) + ("--decision-trace-file", str(trace)))
            self.assertEqual(trace.read_bytes(), original)
            self.assertFalse((root / "streams" / "stdout.txt").exists())
            self.assertFalse((root / "streams" / "stderr.txt").exists())

    def test_history_file_cannot_share_state_or_stream_artifact_directories(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_args = _argv(root) + ("--history-file", str(root / "state" / "history.txt"))
            with self.assertRaises(LauncherError):
                parse_launcher_args(state_args)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            stream_args = _argv(root) + ("--history-file", str(root / "streams" / "history.txt"))
            with self.assertRaises(LauncherError):
                parse_launcher_args(stream_args)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            same_args = _argv(root) + ("--history-file", str(root / "same.json"), "--decision-trace-file", str(root / "same.json"))
            with self.assertRaises(LauncherError):
                parse_launcher_args(same_args)
            state_args = _argv(root) + ("--decision-trace-file", str(root / "state" / "trace.json"))
            with self.assertRaises(LauncherError):
                parse_launcher_args(state_args)

    def test_entrypoint_failure_is_normalized_and_both_streams_close(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = parse_launcher_args(_argv(root))
            self.assertEqual(run_launcher(config, lambda _: (_ for _ in ()).throw(RuntimeError("synthetic"))), LAUNCHER_ENTRYPOINT_EXIT)
            self.assertEqual((root / "streams" / "stdout.txt").read_text(encoding="utf-8"), "")
            self.assertEqual((root / "streams" / "stderr.txt").read_text(encoding="utf-8"), "launcher_entrypoint_failure\n")
            (root / "streams" / "stdout.txt").unlink()
            (root / "streams" / "stderr.txt").unlink()

    def test_paths_existing_outputs_unknown_flags_and_bool_like_values_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = list(_argv(root))
            invalid[5] = True  # type: ignore[list-item]
            with self.assertRaises(LauncherError):
                parse_launcher_args(invalid)
            for flag in ("--url", "--preflight-only", "--unknown"):
                with self.subTest(flag=flag):
                    with self.assertRaises(LauncherError):
                        parse_launcher_args(_argv(root) + (flag, "x"))
            (root / "streams" / "stdout.txt").write_text("existing", encoding="utf-8")
            with self.assertRaises(LauncherError):
                parse_launcher_args(_argv(root))
        with self.assertRaises(LauncherError):
            parse_launcher_args(("--agent", "rule", "--state-dir", "relative", "--run-token", TOKEN, "--timeout-seconds", "30", "--max-cycles", "100", "--max-wall-seconds", "600", "--stop-after-finished", "1", "--audit-file", "relative", "--stdout-file", "relative", "--stderr-file", "relative"))

    def test_token_agent_and_state_are_strict_and_streams_never_contain_token(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for agent in ("rule", "deepseek", "conditional_pressure_pass"):
                with self.subTest(agent=agent):
                    case_root = root / agent
                    case_root.mkdir()
                    config = parse_launcher_args(_argv(case_root, agent=agent))
                    self.assertEqual(config.agent, agent)
            invalid_agent_root = root / "invalid-agent"
            invalid_agent_root.mkdir()
            with self.assertRaises(LauncherError):
                parse_launcher_args(_argv(invalid_agent_root, agent="conditional-pressure-pass"))
            for token in (TOKEN.upper(), TOKEN[:-1], TOKEN[:-1] + "g", True, 1):
                with self.subTest(token_type=type(token).__name__):
                    case_root = root / ("token-" + str(len(list(root.iterdir()))))
                    case_root.mkdir()
                    with self.assertRaises(LauncherError):
                        parse_launcher_args(_argv(case_root, token=token))
            missing_root = root / "missing"
            missing_root.mkdir()
            arguments = list(_argv(missing_root))
            del arguments[0:2]
            with self.assertRaises(LauncherError):
                parse_launcher_args(arguments)
            missing_token_root = root / "missing-token"
            missing_token_root.mkdir()
            arguments = list(_argv(missing_token_root))
            del arguments[4:6]
            with self.assertRaises(LauncherError):
                parse_launcher_args(arguments)

    def test_main_has_a_fixed_configuration_failure(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--unknown", "x"]), LAUNCHER_CONFIGURATION_EXIT)
        self.assertEqual(output.getvalue(), "launcher_configuration_error\n")

    def test_stream_open_failure_has_the_same_fixed_configuration_exit(self) -> None:
        with TemporaryDirectory() as temporary:
            output = StringIO()
            with patch("pathlib.Path.open", side_effect=OSError("synthetic")), redirect_stdout(output):
                self.assertEqual(main(_argv(Path(temporary))), LAUNCHER_CONFIGURATION_EXIT)
            self.assertEqual(output.getvalue(), "launcher_configuration_error\n")

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell regression")
    def test_windows_powershell_starts_module_twice_without_powershell_redirects(self) -> None:
        project = Path(__file__).parents[1]
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            outcomes: list[tuple[int, dict[str, str]]] = []
            for index in range(2):
                root = base / f"run-{index}"
                root.mkdir()
                args = _argv(root)
                quoted = ",".join("'" + str(value).replace("'", "''") + "'" for value in ("-m", "integrations.botzone.live_launcher", *args))
                project_text = str(project).replace("'", "''")
                command = (
                    "$env:CODEX_LAUNCHER_OFFLINE_PROBE='1';"
                    "$env:CODEX_LAUNCH_SENTINEL='synthetic-ok';"
                    f"$env:CODEX_LAUNCH_EXPECTED_CWD='{project_text}';"
                    f"$p=Start-Process -FilePath 'python' -ArgumentList @({quoted}) -WorkingDirectory '{project_text}' -WindowStyle Hidden -PassThru -Wait;"
                    "exit $p.ExitCode"
                )
                self.assertNotIn("RedirectStandard", command)
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                outcomes.append((completed.returncode, {
                    "stdout": (root / "streams" / "stdout.txt").read_text(encoding="utf-8"),
                    "stderr": (root / "streams" / "stderr.txt").read_text(encoding="utf-8"),
                }))
            self.assertEqual([code for code, _ in outcomes], [17, 17])
            self.assertEqual([streams for _, streams in outcomes], [
                {"stdout": "launcher_probe_stdout\n", "stderr": "launcher_probe_stderr\n"},
                {"stdout": "launcher_probe_stdout\n", "stderr": "launcher_probe_stderr\n"},
            ])


if __name__ == "__main__":
    unittest.main()
