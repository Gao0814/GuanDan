from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from evaluation.botzone_policy_benchmark import (
    BenchmarkConditions,
    PROFILE_VERSION,
    PolicyAuditSubmission,
    aggregate_policy_audits,
    build_paired_schedule,
)
from integrations.botzone import __main__ as botzone_main
from integrations.botzone.connector import MockConnector
from integrations.botzone.models import DealRequest
from integrations.botzone.poll import FinishedRow
from integrations.botzone.protocol import parse_stage_request
from integrations.botzone.run_provenance import RunProvenanceError, validate_run_token
from integrations.botzone.runner import ForegroundRunner, write_audit
from integrations.botzone.runtime_config import RuntimeConfig
from integrations.botzone.session import HandlerResult, SessionStorageError, SessionStore


TOKEN_A = "0123456789abcdef0123456789abcdef"
TOKEN_B = "fedcba9876543210fedcba9876543210"


def _conditions(*, required: bool) -> BenchmarkConditions:
    return BenchmarkConditions(PROFILE_VERSION, True, True, run_provenance_required=required)


def _audit(strategy: str, token: str) -> dict[str, object]:
    source = "rule_primary" if strategy == "rule" else "model"
    outcomes: list[list[object]] = [] if strategy == "rule" else [["success", 1]]
    attempts = 0 if strategy == "rule" else 1
    return {
        "schema": "botzone_local_smoke_audit", "version": 8, "run_token": token,
        "exit_code": 0, "stop_reason": "finished_target", "cycles": 1, "successful_cycles": 1,
        "transport_failures": 0, "transport_timeouts": 0, "transport_failure_categories": [],
        "headers_sent": 1, "requests_seen": 1, "responses_prepared": 1,
        "finished_seen": 1, "finished_qualified": 1, "finished_categories": [["qualified", 1]],
        "diagnostics": [], "diagnostic_details": [], "diagnostic_profiles": [], "agent_mode": strategy,
        "agent_decision_count": 1, "decision_source_counts": [[source, 1]],
        "model_attempt_count": attempts, "model_outcome_counts": outcomes, "rule_fallback_count": 0,
        "result_category_counts": [["local_team_win", 1]], "normal_result_count": 1,
        "local_team_score_counts": [["score_1", 1]],
    }


class BotzoneRunProvenanceTests(unittest.TestCase):
    def test_token_format_is_exact_and_redacted(self) -> None:
        self.assertEqual(validate_run_token(TOKEN_A), TOKEN_A)
        for value in (None, True, 1, "", TOKEN_A.upper(), " " + TOKEN_A, TOKEN_A[:-1], TOKEN_A[:-1] + "g"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(RunProvenanceError):
                    validate_run_token(value)

    def test_token_session_survives_pending_restart_and_finished_tombstone(self) -> None:
        request = parse_stage_request(
            {"stage": "deal", "deliver": list(range(27)), "your_id": 0,
             "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        )
        self.assertIsInstance(request, DealRequest)
        with TemporaryDirectory() as root:
            store = SessionStore(root, run_token=TOKEN_A)
            record, _ = store.prepare("synthetic-match", b"deal", request)
            stored = json.loads(next(Path(root).iterdir()).read_text(encoding="utf-8"))
            self.assertEqual((stored["version"], stored["run_token"]), (4, TOKEN_A))
            self.assertNotIn(TOKEN_A, repr(record))
            self.assertNotIn("run_token", store.handler_context(record, request).to_json())
            record = store.complete_handler(store.reserve_handler(record), HandlerResult(b"[]"))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries)
            restarted = SessionStore(root, run_token=TOKEN_A)
            restarted.restore_pending(deliveries)
            self.assertEqual(restarted.load("synthetic-match").run_token, TOKEN_A)
            with self.assertRaisesRegex(SessionStorageError, "run_token_mismatch"):
                SessionStore(root, run_token=TOKEN_B).load("synthetic-match")
            with self.assertRaisesRegex(SessionStorageError, "run_token_mismatch"):
                SessionStore(root, run_token=TOKEN_B).pending_deliveries()
            self.assertTrue(restarted.finish(FinishedRow("synthetic-match", 0, 4, (1, 1, 0, 0))))
            tombstone = json.loads(next(Path(root).iterdir()).read_text(encoding="utf-8"))
            self.assertEqual(tombstone, {"schema": "botzone_no_tribute_finished", "version": 4, "finished": True, "run_token": TOKEN_A})
            self.assertIsNone(SessionStore(root, run_token=TOKEN_A).load("synthetic-match"))
            with self.assertRaisesRegex(SessionStorageError, "run_token_mismatch"):
                SessionStore(root).load("synthetic-match")

    def test_default_session_and_audit_versions_remain_compatible(self) -> None:
        with TemporaryDirectory() as root:
            summary = ForegroundRunner(
                MockConnector(
                    SessionStore(root), type("Gateway", (), {"poll": lambda _self, _headers: b"0 0\\n"})(), lambda _context: None
                ), max_consecutive_failures=1, backoff_seconds=0, sleep=lambda _: None,
            ).run(max_cycles=1, max_wall_seconds=1, stop_after_finished=1)
            audit = Path(root).parent / "v7-audit.json"
            write_audit(audit, summary, 6)
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 7)
            self.assertNotIn("run_token", payload)
            token_audit = Path(root).parent / "v8-audit.json"
            write_audit(token_audit, summary, 6, run_token=TOKEN_A)
            token_payload = json.loads(token_audit.read_text(encoding="utf-8"))
            self.assertEqual((token_payload["version"], token_payload["run_token"]), (8, TOKEN_A))

    def test_cli_forwards_token_only_to_runner_and_preflight_ignores_it(self) -> None:
        config = RuntimeConfig("https://example.invalid", Path("C:/tmp/botzone-run-token"))
        runner = type("Runner", (), {"run_token": TOKEN_A, "run": lambda _self, **_kwargs: type("Summary", (), {"cycles": 0, "finished_seen": 0})()})()
        output = StringIO()
        with (
            patch.object(botzone_main, "load_runtime_config", return_value=config),
            patch.object(botzone_main, "preflight_state_directory"),
            patch.object(botzone_main, "prepare_agent_factory", return_value=lambda _seat: object()),
            patch.object(botzone_main, "LocalAIHttpTransport", return_value=object()),
            patch.object(botzone_main, "build_foreground_runner", return_value=runner) as build,
            patch.object(botzone_main, "exit_code_for", return_value=6),
            redirect_stdout(output),
        ):
            self.assertEqual(botzone_main.main(["--run-token", TOKEN_A]), 6)
        self.assertEqual(build.call_args.kwargs["run_token"], TOKEN_A)
        self.assertNotIn(TOKEN_A, output.getvalue())
        preflight_output = StringIO()
        with (
            patch.object(botzone_main, "load_runtime_config", return_value=config),
            patch.object(botzone_main, "preflight_state_directory"),
            patch.object(botzone_main, "prepare_agent_factory", return_value=lambda _seat: object()),
            patch.object(botzone_main, "build_foreground_runner") as preflight_runner,
            redirect_stdout(preflight_output),
        ):
            self.assertEqual(botzone_main.main(["--preflight-only", "--run-token", "invalid"], environ={}), 0)
        self.assertEqual(preflight_output.getvalue(), "preflight_ready\n")
        self.assertEqual(preflight_runner.call_count, 0)

    def test_benchmark_requires_matched_token_audits_and_never_reports_tokens(self) -> None:
        schedule = build_paired_schedule((25003,), _conditions(required=True))
        submissions = (
            PolicyAuditSubmission(25003, 0, "rule", PROFILE_VERSION, _audit("rule", TOKEN_A), TOKEN_A),
            PolicyAuditSubmission(25003, 0, "deepseek", PROFILE_VERSION, _audit("deepseek", TOKEN_B), TOKEN_B),
        )
        report = aggregate_policy_audits(schedule, submissions, _conditions(required=True))
        self.assertEqual((report.valid_pair_count, report.incomplete_pair_count), (1, 3))
        rendered = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn(TOKEN_A, rendered)
        self.assertNotIn(TOKEN_B, rendered)
        mismatch = aggregate_policy_audits(
            schedule,
            (PolicyAuditSubmission(25003, 0, "rule", PROFILE_VERSION, _audit("rule", TOKEN_A), TOKEN_B), submissions[1]),
            _conditions(required=True),
        )
        self.assertEqual(mismatch.invalid_pair_count, 1)
        mixed = aggregate_policy_audits(schedule, submissions, _conditions(required=False))
        self.assertEqual(mixed.invalid_pair_count, 1)


if __name__ == "__main__":
    unittest.main()
