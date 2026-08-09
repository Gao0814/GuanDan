from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.__main__ import main


_ALLOWED_STDOUT = {b"preflight_ready\n", b"preflight_ready\r\n"}


def _subprocess_environment() -> dict[str, str]:
    """Build a minimal child environment without copying Botzone variables."""

    names = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP")
    return {name: os.environ[name] for name in names if name in os.environ}


def _assert_binary_result(case: unittest.TestCase, completed: subprocess.CompletedProcess[bytes], state: Path) -> tuple[int, bytes, bytes, tuple[str, ...], bool]:
    case.assertEqual(completed.returncode, 0)
    case.assertEqual(completed.stderr, b"")
    case.assertIn(completed.stdout, _ALLOWED_STDOUT)
    text = completed.stdout.decode("utf-8", "strict")
    normalized = tuple(text.splitlines())
    case.assertEqual(normalized, ("preflight_ready",))
    empty = state.is_dir() and not any(state.iterdir())
    case.assertTrue(empty)
    return completed.returncode, completed.stdout, completed.stderr, normalized, empty


class BotzonePreflightOutputTests(unittest.TestCase):
    def test_direct_main_writes_exact_text_without_constructing_transport(self) -> None:
        with TemporaryDirectory() as root:
            output = StringIO()
            with patch("integrations.botzone.__main__.LocalAIHttpTransport", side_effect=AssertionError("transport_constructed")):
                with redirect_stdout(output):
                    exit_code = main(
                        ["--url", "https://example.invalid", "--state-dir", root, "--preflight-only"],
                        environ={},
                    )
            self.assertEqual(exit_code, 0)
            self.assertEqual(output.getvalue(), "preflight_ready\n")
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_module_binary_capture_is_strict_and_deterministic(self) -> None:
        repository = Path(__file__).parents[1]
        environment = _subprocess_environment()
        self.assertNotIn("PYTHONPATH", environment)
        self.assertFalse(any(name.startswith("BOTZONE_") for name in environment))
        results: list[tuple[int, bytes, bytes, tuple[str, ...], bool]] = []
        for _ in range(2):
            with TemporaryDirectory() as root:
                completed = subprocess.run(
                    [sys.executable, "-m", "integrations.botzone", "--url", "https://example.invalid", "--state-dir", root, "--preflight-only"],
                    cwd=repository,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
                results.append(_assert_binary_result(self, completed, Path(root)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(results[0][2:], results[1][2:])


if __name__ == "__main__":
    unittest.main()
