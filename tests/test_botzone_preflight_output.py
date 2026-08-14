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
from integrations.botzone.runtime_config import RuntimeConfig, RuntimeConfigError


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
    def _assert_preflight_failure(
        self,
        *,
        load_error: BaseException | None = None,
        state_error: BaseException | None = None,
        agent_error: BaseException | None = None,
        expected: str,
    ) -> None:
        from integrations.botzone import __main__ as botzone_main

        with TemporaryDirectory() as root:
            output = StringIO()
            config = RuntimeConfig("https://example.invalid", Path(root))
            with (
                patch.object(botzone_main, "load_runtime_config", side_effect=load_error) if load_error is not None else patch.object(botzone_main, "load_runtime_config", return_value=config),
                patch.object(botzone_main, "preflight_state_directory", side_effect=state_error) if state_error is not None else patch.object(botzone_main, "preflight_state_directory"),
                patch.object(botzone_main, "prepare_agent_factory", side_effect=agent_error) if agent_error is not None else patch.object(botzone_main, "prepare_agent_factory"),
                patch.object(botzone_main, "LocalAIHttpTransport", side_effect=AssertionError("transport_constructed")) as transport,
                redirect_stdout(output),
            ):
                self.assertEqual(main(["--preflight-only"], environ={}), 2)
            self.assertEqual(output.getvalue(), expected + "\n")
            self.assertEqual(transport.call_count, 0)

    def test_preflight_runtime_categories_have_fixed_stdout(self) -> None:
        cases = {
            "missing_configuration": "preflight_runtime_config_missing",
            "invalid_configuration": "preflight_runtime_config_url_invalid",
            "invalid_timeout": "preflight_runtime_config_timeout_invalid",
            "invalid_response_limit": "preflight_runtime_config_response_limit_invalid",
            "invalid_failure_limit": "preflight_runtime_config_failure_limit_invalid",
            "invalid_backoff": "preflight_runtime_config_backoff_invalid",
        }
        for category, expected in cases.items():
            with self.subTest(category=category):
                self._assert_preflight_failure(load_error=RuntimeConfigError(category), expected=expected)

    def test_preflight_state_agent_and_unknown_categories_are_safe(self) -> None:
        class _UnknownCategory(RuntimeConfigError):
            @property
            def category(self) -> str:
                return "unknown"

        self._assert_preflight_failure(
            state_error=RuntimeConfigError("invalid_state_directory"),
            expected="preflight_state_directory_invalid",
        )
        self._assert_preflight_failure(
            state_error=RuntimeConfigError("state_preflight_failed"),
            expected="preflight_state_operation_failed",
        )
        self._assert_preflight_failure(
            agent_error=ValueError("synthetic-secret"),
            expected="preflight_agent_composition_failed",
        )
        self._assert_preflight_failure(
            load_error=ValueError("synthetic-secret"),
            expected="preflight_configuration_error",
        )
        self._assert_preflight_failure(
            load_error=_UnknownCategory(),
            expected="preflight_configuration_error",
        )

    def test_non_preflight_keeps_generic_configuration_output(self) -> None:
        from integrations.botzone import __main__ as botzone_main

        output = StringIO()
        with patch.object(botzone_main, "load_runtime_config", side_effect=RuntimeConfigError("invalid_timeout")):
            with redirect_stdout(output):
                self.assertEqual(main([], environ={}), 2)
        self.assertEqual(output.getvalue(), "configuration_error\n")

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
