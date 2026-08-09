from __future__ import annotations

import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.live_launcher import (
    LAUNCHER_CONFIGURATION_EXIT,
    LAUNCHER_ENTRYPOINT_EXIT,
    LauncherError,
    connector_argv,
    main,
    parse_launcher_args,
    run_launcher,
)


def _argv(root: Path) -> tuple[str, ...]:
    return (
        "--timeout-seconds", "30",
        "--max-cycles", "100",
        "--max-wall-seconds", "600",
        "--stop-after-finished", "1",
        "--audit-file", str(root / "audit.json"),
        "--stdout-file", str(root / "stdout.txt"),
        "--stderr-file", str(root / "stderr.txt"),
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
            self.assertEqual(original, _argv(root))
            self.assertEqual(tuple(received), connector_argv(config))
            self.assertEqual((root / "stdout.txt").read_text(encoding="utf-8"), "synthetic_stdout\n")
            self.assertEqual((root / "stderr.txt").read_text(encoding="utf-8"), "synthetic_stderr\n")
            (root / "stdout.txt").rename(root / "stdout-closed.txt")
            (root / "stderr.txt").rename(root / "stderr-closed.txt")

    def test_entrypoint_failure_is_normalized_and_both_streams_close(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = parse_launcher_args(_argv(root))
            self.assertEqual(run_launcher(config, lambda _: (_ for _ in ()).throw(RuntimeError("synthetic"))), LAUNCHER_ENTRYPOINT_EXIT)
            self.assertEqual((root / "stdout.txt").read_text(encoding="utf-8"), "")
            self.assertEqual((root / "stderr.txt").read_text(encoding="utf-8"), "launcher_entrypoint_failure\n")
            (root / "stdout.txt").unlink()
            (root / "stderr.txt").unlink()

    def test_paths_existing_outputs_unknown_flags_and_bool_like_values_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = list(_argv(root))
            invalid[1] = True  # type: ignore[list-item]
            with self.assertRaises(LauncherError):
                parse_launcher_args(invalid)
            for flag in ("--url", "--state-dir", "--preflight-only", "--unknown"):
                with self.subTest(flag=flag):
                    with self.assertRaises(LauncherError):
                        parse_launcher_args(_argv(root) + (flag, "x"))
            (root / "stdout.txt").write_text("existing", encoding="utf-8")
            with self.assertRaises(LauncherError):
                parse_launcher_args(_argv(root))
        with self.assertRaises(LauncherError):
            parse_launcher_args(("--timeout-seconds", "30", "--max-cycles", "100", "--max-wall-seconds", "600", "--stop-after-finished", "1", "--audit-file", "relative", "--stdout-file", "relative", "--stderr-file", "relative"))

    def test_main_has_a_fixed_configuration_failure(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--unknown", "x"]), LAUNCHER_CONFIGURATION_EXIT)
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
                quoted = ",".join("'" + value.replace("'", "''") + "'" for value in ("-m", "integrations.botzone.live_launcher", *args))
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
                    "stdout": (root / "stdout.txt").read_text(encoding="utf-8"),
                    "stderr": (root / "stderr.txt").read_text(encoding="utf-8"),
                }))
            self.assertEqual([code for code, _ in outcomes], [17, 17])
            self.assertEqual([streams for _, streams in outcomes], [
                {"stdout": "launcher_probe_stdout\n", "stderr": "launcher_probe_stderr\n"},
                {"stdout": "launcher_probe_stdout\n", "stderr": "launcher_probe_stderr\n"},
            ])


if __name__ == "__main__":
    unittest.main()
