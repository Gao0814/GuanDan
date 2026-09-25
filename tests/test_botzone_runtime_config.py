from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
from unittest.mock import patch

from integrations.botzone.runtime_config import RuntimeConfigError, load_runtime_config
from integrations.botzone.__main__ import main


class BotzoneRuntimeConfigTests(unittest.TestCase):
    def test_runtime_timeout_defaults_to_thirty_seconds(self) -> None:
        config = load_runtime_config(
            local_ai_url="https://synthetic.invalid/poll",
            state_directory="state",
            environ={},
        )
        self.assertEqual(config.timeout_seconds, 30)

    def test_cli_uses_thirty_second_timeout_when_option_is_omitted(self) -> None:
        observed: dict[str, object] = {}

        def fake_load_runtime_config(**kwargs: object) -> object:
            observed.update(kwargs)
            return object()

        output = StringIO()
        with (
            patch("integrations.botzone.__main__.load_runtime_config", side_effect=fake_load_runtime_config),
            patch("integrations.botzone.__main__.preflight_state_directory"),
            patch("integrations.botzone.__main__.prepare_agent_factory"),
            redirect_stdout(output),
        ):
            status = main(
                ["--preflight-only", "--agent", "deepseek", "--state-dir", "synthetic-state"],
                environ={"BOTZONE_LOCAL_AI_URL": "https://synthetic.invalid/poll"},
            )

        self.assertEqual(status, 0)
        self.assertEqual(observed.get("timeout_seconds"), 30)
        self.assertEqual(output.getvalue(), "preflight_ready\n")

    def test_runtime_config_error_has_only_fixed_category(self) -> None:
        self.assertEqual(RuntimeConfigError("invalid_timeout").category, "invalid_timeout")
        self.assertEqual(RuntimeConfigError("synthetic-secret").category, "invalid_configuration")

    def test_explicit_values_win_and_repr_redacts_url(self) -> None:
        config = load_runtime_config(
            local_ai_url="https://private.invalid/secret",
            state_directory="state",
            timeout_seconds="12",
            environ={"BOTZONE_LOCAL_AI_URL": "https://ignored.invalid", "BOTZONE_STATE_DIR": "ignored"},
        )
        self.assertEqual(config.state_directory, Path("state"))
        self.assertEqual(config.timeout_seconds, 12)
        self.assertNotIn("private.invalid", repr(config))

    def test_missing_invalid_and_boolean_values_fail_without_echoing_values(self) -> None:
        with self.assertRaisesRegex(RuntimeConfigError, "missing_configuration"):
            load_runtime_config(environ={})
        for timeout in (True, 0, "0", "12x"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(RuntimeConfigError):
                    load_runtime_config(
                        local_ai_url="https://private.invalid/path",
                        state_directory="state",
                        timeout_seconds=timeout,
                    )
        with self.assertRaisesRegex(RuntimeConfigError, "invalid_configuration") as caught:
            load_runtime_config(local_ai_url="http://private.invalid/secret", state_directory="state")
        self.assertNotIn("private.invalid", str(caught.exception))

    def test_module_has_no_dotenv_or_root_configuration_dependency(self) -> None:
        source = Path(__file__).parents[1].joinpath("integrations", "botzone", "runtime_config.py").read_text(encoding="utf-8")
        for marker in ("dotenv", "config.py", "load_dotenv"):
            self.assertNotIn(marker, source)
        self.assertIsNone(re.search(r"Path\([^\n]*\.env|open\([^\n]*\.env", source))

    def test_entrypoint_reports_configuration_failure_without_reading_process_values(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            status = main([], environ={})
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "configuration_error\n")


if __name__ == "__main__":
    unittest.main()
