from __future__ import annotations

import json
import os
import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from integrations.botzone.live_preflight import (
    EXIT_AUDIT,
    EXIT_CONFIG,
    EXIT_IMPORT,
    EXIT_INTERRUPT,
    EXIT_STATE,
    AuditWriteError,
    run_instrumented_preflight,
)
from integrations.botzone.runtime_config import RuntimeConfigError


STAGES = ("resolve", "boundary_checked", "directory_ready", "temporary_opened", "written", "flushed", "synced", "replaced", "cleaned")


class _Runtime:
    def __init__(self, *, config_error: Exception | None = None) -> None:
        self.config_error = config_error

    def load_runtime_config(self) -> object:
        if self.config_error is not None:
            raise self.config_error
        return object()

    def preflight_state_directory(self, _: object, *, stage_callback: object) -> None:
        for stage in STAGES:
            stage_callback(stage)  # type: ignore[operator]


def _argv(root: Path) -> tuple[str, str]:
    return "--audit-file", str(root / "audit.json")


class BotzoneInstrumentedPreflightTests(unittest.TestCase):
    def test_bootstrap_audit_precedes_loader_and_records_every_stage(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = StringIO()

            def loader() -> _Runtime:
                self.assertTrue((root / "audit.json").exists())
                return _Runtime()

            self.assertEqual(run_instrumented_preflight(_argv(root), loader=loader, stdout=output), 0)
            payload = json.loads((root / "audit.json").read_text(encoding="utf-8"))
            self.assertEqual(output.getvalue(), "instrumented_preflight_ready\n")
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["stages"], ["runtime_loaded", "config_loaded", *STAGES, "state_preflight_completed"])
            self.assertEqual(payload["counts"], {"request": 0, "get": 0, "network": 0, "connector": 0})

    def test_import_config_state_callback_interrupt_and_writer_failures_are_normalized(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(run_instrumented_preflight(_argv(root), loader=lambda: (_ for _ in ()).throw(ImportError())), EXIT_IMPORT)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(run_instrumented_preflight(_argv(root), loader=lambda: _Runtime(config_error=RuntimeConfigError())), EXIT_CONFIG)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            def broken(_: object, *, stage_callback: object) -> None:
                stage_callback("resolve")  # type: ignore[operator]
                raise RuntimeError()
            self.assertEqual(run_instrumented_preflight(_argv(root), loader=_Runtime, prober=broken), EXIT_STATE)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            def interrupted(_: object, *, stage_callback: object) -> None:
                raise KeyboardInterrupt()
            self.assertEqual(run_instrumented_preflight(_argv(root), loader=_Runtime, prober=interrupted), EXIT_INTERRUPT)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            def failing_writer(_: Path, __: object) -> None:
                raise AuditWriteError()
            self.assertEqual(run_instrumented_preflight(_argv(root), loader=_Runtime, writer=failing_writer), EXIT_AUDIT)

    def test_audit_path_validation_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(run_instrumented_preflight(("--audit-file", "relative"), loader=_Runtime), EXIT_AUDIT)
            existing = root / "existing.json"
            existing.write_text("{}", encoding="utf-8")
            with redirect_stdout(output):
                self.assertEqual(run_instrumented_preflight(("--audit-file", str(existing)), loader=_Runtime), EXIT_AUDIT)
            with redirect_stdout(output):
                self.assertEqual(run_instrumented_preflight(("--url", "x"), loader=_Runtime), EXIT_AUDIT)
            self.assertEqual(output.getvalue(), "instrumented_preflight_audit_error\n" * 3)

    def test_callback_default_is_off_and_callback_failure_cleans_temp_files(self) -> None:
        from integrations.botzone.runtime_config import RuntimeConfig, preflight_state_directory

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = RuntimeConfig("https://offline.invalid/preflight", root)
            preflight_state_directory(config)
            self.assertEqual(list(root.iterdir()), [])
            with self.assertRaises(RuntimeError):
                preflight_state_directory(config, stage_callback=lambda stage: (_ for _ in ()).throw(RuntimeError()) if stage == "written" else None)
            self.assertEqual(list(root.iterdir()), [])

    def test_synthetic_module_subprocess_has_fixed_output_and_no_state_residue(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            audit = root / "audit.json"
            environment = {"BOTZONE_LOCAL_AI_URL": "https://offline.invalid/preflight", "BOTZONE_STATE_DIR": str(state)}
            completed = subprocess.run(
                [sys.executable, "-m", "integrations.botzone.live_preflight", "--audit-file", str(audit)],
                cwd=Path(__file__).parents[1], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10, check=False,
            )
            self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, "instrumented_preflight_ready\n", ""))
            self.assertEqual(list(state.iterdir()), [])
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertNotIn("offline.invalid", audit.read_text(encoding="utf-8"))

    def test_source_boundary_has_no_transport_or_secret_dependencies(self) -> None:
        source = (Path(__file__).parents[1] / "integrations" / "botzone" / "live_preflight.py").read_text(encoding="utf-8").lower()
        for marker in ("dotenv", "deepseek", "runmatch", "api_key", "cookie", "urllib", "socket"):
            self.assertNotIn(marker, source)
        self.assertIsNone(re.search(r"(?m)^\s*(?:from|import)\s+.*(?:transport|runner|connector|session|adapter|agent)", source))


if __name__ == "__main__":
    unittest.main()
