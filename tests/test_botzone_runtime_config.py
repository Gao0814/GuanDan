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
        self.assertIsNone(observed.get("decision_timeout_seconds"))
        self.assertIsNone(observed.get("table_timeout_seconds"))
        self.assertEqual(output.getvalue(), "preflight_ready\n")

    def test_opt_in_119_second_decision_budget_is_separate_from_poll_timeout(self) -> None:
        config = load_runtime_config(
            local_ai_url="https://synthetic.invalid/poll",
            state_directory="state",
            timeout_seconds=30,
            decision_timeout_seconds="119",
            table_timeout_seconds="120",
            environ={},
        )
        self.assertEqual(config.timeout_seconds, 30)
        self.assertEqual(config.decision_timeout_seconds, 119.0)
        self.assertEqual(config.table_timeout_seconds, 120.0)

    def test_decision_budget_rejects_missing_pair_invalid_values_and_insufficient_margin(self) -> None:
        common = {"local_ai_url": "https://synthetic.invalid/poll", "state_directory": "state", "environ": {}}
        with self.assertRaisesRegex(RuntimeConfigError, "decision_budget_pair_required"):
            load_runtime_config(**common, decision_timeout_seconds="80")
        for value in (0, -1, True, "NaN", "Infinity", "80x", 5):
            with self.subTest(value=value), self.assertRaises(RuntimeConfigError):
                load_runtime_config(
                    **common,
                    decision_timeout_seconds=value,
                    table_timeout_seconds=120,
                )
        with self.assertRaisesRegex(RuntimeConfigError, "decision_table_margin_insufficient"):
            load_runtime_config(
                **common,
                decision_timeout_seconds=120,
                table_timeout_seconds=120,
            )
        with self.assertRaisesRegex(RuntimeConfigError, "decision_table_margin_insufficient"):
            load_runtime_config(
                **common,
                decision_timeout_seconds=119.01,
                table_timeout_seconds=120,
            )
        with self.assertRaisesRegex(RuntimeConfigError, "invalid_table_timeout"):
            load_runtime_config(
                **common,
                decision_timeout_seconds=119,
                table_timeout_seconds="NaN",
            )

    def test_cli_preflight_validates_budget_before_state_and_agent_preflight(self) -> None:
        output = StringIO()
        with (
            patch("integrations.botzone.__main__.preflight_state_directory") as state_preflight,
            patch("integrations.botzone.__main__.prepare_agent_factory") as agent_preflight,
            redirect_stdout(output),
        ):
            status = main(
                [
                    "--preflight-only", "--agent", "deepseek", "--state-dir", "synthetic-state",
                    "--decision-timeout-seconds", "119", "--table-timeout-seconds", "120",
                ],
                environ={"BOTZONE_LOCAL_AI_URL": "https://synthetic.invalid/poll"},
            )
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "preflight_ready\n")
        state_preflight.assert_called_once()
        agent_preflight.assert_called_once()

        output = StringIO()
        with redirect_stdout(output):
            status = main(
                [
                    "--preflight-only", "--agent", "deepseek", "--state-dir", "synthetic-state",
                    "--decision-timeout-seconds", "120", "--table-timeout-seconds", "120",
                ],
                environ={"BOTZONE_LOCAL_AI_URL": "https://synthetic.invalid/poll"},
            )
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "preflight_decision_table_margin_insufficient\n")

    def test_decision_budget_is_deepseek_only_and_does_not_change_rule_default(self) -> None:
        output = StringIO()
        state_preflight = patch("integrations.botzone.__main__.preflight_state_directory")
        with state_preflight as preflight, redirect_stdout(output):
            status = main(
                [
                    "--preflight-only", "--agent", "rule", "--state-dir", "synthetic-state",
                    "--decision-timeout-seconds", "119", "--table-timeout-seconds", "120",
                ],
                environ={"BOTZONE_LOCAL_AI_URL": "https://synthetic.invalid/poll"},
            )
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "preflight_decision_budget_requires_deepseek\n")
        preflight.assert_not_called()

        config = load_runtime_config(
            local_ai_url="https://synthetic.invalid/poll",
            state_directory="state",
            environ={},
        )
        self.assertIsNone(config.decision_timeout_seconds)
        self.assertIsNone(config.table_timeout_seconds)

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
