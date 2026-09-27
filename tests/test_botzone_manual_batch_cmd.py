from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMMAND = r"scripts\run_manual_botzone_batch.cmd"


@unittest.skipUnless(os.name == "nt", "the batch launcher requires Windows cmd.exe")
class BotzoneManualBatchCommandTests(unittest.TestCase):
    def _command(self, arguments: tuple[str, ...]) -> list[str]:
        executable = os.environ.get("COMSPEC", "cmd.exe")
        command_line = " ".join((COMMAND, *arguments))
        return [executable, "/d", "/c", command_line]

    def test_double_click_mode_waits_for_key_after_exit_and_keeps_zero_exit(self) -> None:
        process = subprocess.Popen(
            self._command(("--help",)),
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            time.sleep(0.25)
            is_waiting = process.poll() is None
            output, _ = process.communicate(input="\r", timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise

        self.assertTrue(is_waiting)
        self.assertEqual(process.returncode, 0)
        self.assertIn("usage: run_manual_botzone_batch", output)
        self.assertIn("batch_window_exit=0", output)
        self.assertIn("Press any key to close this window.", output)

    def test_double_click_mode_keeps_argument_failure_visible_and_returns_two(self) -> None:
        process = subprocess.Popen(
            self._command(("--definitely-invalid",)),
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            time.sleep(0.25)
            is_waiting = process.poll() is None
            output, _ = process.communicate(input="\r", timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise

        self.assertTrue(is_waiting)
        self.assertEqual(process.returncode, 2)
        self.assertIn("unrecognized arguments: --definitely-invalid", output)
        self.assertIn("batch_window_exit=2", output)
        self.assertIn("Press any key to close this window.", output)

    def test_no_pause_is_removed_from_python_arguments_and_exit_code_is_preserved(self) -> None:
        completed = subprocess.run(
            self._command(("--no-pause", "--help")),
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("usage: run_manual_botzone_batch", completed.stdout)
        self.assertNotIn("unrecognized arguments: --no-pause", completed.stdout)
        self.assertNotIn("Press any key to close this window.", completed.stdout)

        failed = subprocess.run(
            self._command(("--no-pause", "--definitely-invalid")),
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        self.assertEqual(failed.returncode, 2)
        self.assertNotIn("unrecognized arguments: --no-pause", failed.stdout)
        self.assertNotIn("Press any key to close this window.", failed.stdout)


if __name__ == "__main__":
    unittest.main()
