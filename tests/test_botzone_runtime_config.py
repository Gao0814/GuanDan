from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re

from integrations.botzone.runtime_config import RuntimeConfigError, load_runtime_config
from integrations.botzone.__main__ import main


class BotzoneRuntimeConfigTests(unittest.TestCase):
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
