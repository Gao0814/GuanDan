from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

from evaluation.botzone_policy_benchmark import (
    BenchmarkConditions,
    PROFILE_VERSION,
    PolicyAuditSubmission,
    PolicyBenchmarkError,
    ScheduledPair,
    aggregate_policy_audits,
    build_paired_schedule,
)


def _conditions(*, confirmed: bool = True, opponents_confirmed: bool = True) -> BenchmarkConditions:
    return BenchmarkConditions(PROFILE_VERSION, confirmed, opponents_confirmed)


def _audit(
    strategy: str,
    outcome: str,
    bucket: str,
    *,
    source: str | None = None,
    model_outcome: str | None = None,
) -> dict[str, object]:
    if strategy == "rule":
        sources = [["rule_primary", 1]]
        outcomes: list[list[object]] = []
        model_attempts = fallback_count = 0
    else:
        source = source or "model"
        sources = [[source, 1]]
        if source == "model":
            outcomes = [[model_outcome or "success", 1]]
            model_attempts = 1
            fallback_count = 0
        elif source == "deepseek_rule_fallback":
            outcomes = [[model_outcome or "timeout", 1]]
            model_attempts = 1
            fallback_count = 1
        elif source == "adapter_rule_fallback":
            outcomes = []
            model_attempts = 0
            fallback_count = 1
        else:
            outcomes = []
            model_attempts = fallback_count = 0
    return {
        "schema": "botzone_local_smoke_audit",
        "version": 7,
        "exit_code": 0,
        "stop_reason": "finished_target",
        "cycles": 2,
        "successful_cycles": 2,
        "transport_failures": 0,
        "transport_timeouts": 0,
        "transport_failure_categories": [],
        "headers_sent": 2,
        "requests_seen": 2,
        "responses_prepared": 2,
        "finished_seen": 1,
        "finished_qualified": 1,
        "finished_categories": [["qualified", 1]],
        "diagnostics": [],
        "diagnostic_details": [],
        "diagnostic_profiles": [],
        "agent_mode": strategy,
        "agent_decision_count": 1,
        "decision_source_counts": sources,
        "model_attempt_count": model_attempts,
        "model_outcome_counts": outcomes,
        "rule_fallback_count": fallback_count,
        "result_category_counts": [["local_team_" + outcome, 1]],
        "normal_result_count": 1,
        "local_team_score_counts": [[bucket, 1]],
    }


def _submission(seed: int, seat: int, strategy: str, audit: dict[str, object]) -> PolicyAuditSubmission:
    return PolicyAuditSubmission(seed, seat, strategy, PROFILE_VERSION, audit)


class BotzonePolicyBenchmarkTests(unittest.TestCase):
    def test_conditions_and_seed_inputs_are_strict(self) -> None:
        with self.assertRaises(PolicyBenchmarkError):
            build_paired_schedule((1,), _conditions(confirmed=False))
        with self.assertRaises(PolicyBenchmarkError):
            build_paired_schedule((1,), _conditions(opponents_confirmed=False))
        with self.assertRaises(PolicyBenchmarkError):
            BenchmarkConditions(PROFILE_VERSION, True, True, current_level_rank=True)
        with self.assertRaises(PolicyBenchmarkError):
            build_paired_schedule((1, True), _conditions())
        with self.assertRaises(PolicyBenchmarkError):
            build_paired_schedule((1, 1), _conditions())
        with self.assertRaises(PolicyBenchmarkError):
            ScheduledPair(1, 4, "rule", "deepseek")

    def test_schedule_is_exact_cross_product_deterministic_and_seat_balanced(self) -> None:
        schedule_a = build_paired_schedule((13, 5, 9), _conditions())
        schedule_b = build_paired_schedule((9, 13, 5), _conditions())
        self.assertEqual(schedule_a, schedule_b)
        self.assertEqual(len(schedule_a), 12)
        self.assertEqual({(entry.seed, entry.local_seat) for entry in schedule_a}, {(seed, seat) for seed in (5, 9, 13) for seat in range(4)})
        for seat in range(4):
            first = [entry.first_strategy for entry in schedule_a if entry.local_seat == seat]
            self.assertLessEqual(abs(first.count("rule") - first.count("deepseek")), 1)
        self.assertNotIn("5", repr(schedule_a[0]))

    def test_valid_pairs_aggregate_scores_fractions_model_paths_and_seats(self) -> None:
        schedule = build_paired_schedule((7,), _conditions())
        audits = [
            _submission(7, 0, "rule", _audit("rule", "loss", "score_0")),
            _submission(7, 0, "deepseek", _audit("deepseek", "win", "score_3")),
            _submission(7, 1, "rule", _audit("rule", "win", "score_1")),
            _submission(7, 1, "deepseek", _audit("deepseek", "loss", "score_0", source="deepseek_rule_fallback")),
            _submission(7, 2, "rule", _audit("rule", "win", "score_2")),
            _submission(7, 2, "deepseek", _audit("deepseek", "win", "score_2", source="local_shortcut")),
            _submission(7, 3, "rule", _audit("rule", "win", "score_3")),
            _submission(7, 3, "deepseek", _audit("deepseek", "win", "score_1", source="adapter_rule_fallback")),
        ]
        report = aggregate_policy_audits(schedule, audits, _conditions())
        payload = report.to_dict()
        self.assertEqual((report.requested_pair_count, report.valid_pair_count, report.invalid_pair_count, report.incomplete_pair_count), (4, 4, 0, 0))
        self.assertEqual((report.deepseek_score_better, report.rule_score_better, report.equal_score), (1, 2, 1))
        self.assertEqual(payload["rule_score_counts"], [["score_0", 1], ["score_1", 1], ["score_2", 1], ["score_3", 1]])
        self.assertEqual(payload["deepseek_score_counts"], [["score_0", 1], ["score_1", 1], ["score_2", 1], ["score_3", 1]])
        self.assertEqual(payload["rule_score_mean"], [3, 2])
        self.assertEqual(payload["deepseek_score_mean"], [3, 2])
        self.assertEqual(payload["paired_score_delta_mean"], [0, 1])
        self.assertEqual(payload["deepseek_model_exposed_game_count"], 2)
        self.assertEqual(payload["deepseek_model_attempt_count"], 2)
        self.assertEqual(payload["deepseek_model_outcome_counts"], [["success", 1], ["timeout", 1]])
        self.assertEqual(payload["deepseek_decision_source_counts"], [["adapter_rule_fallback", 1], ["deepseek_rule_fallback", 1], ["local_shortcut", 1], ["model", 1]])
        self.assertEqual(payload["deepseek_rule_fallback_count"], 2)
        self.assertEqual(sum(item["valid_pair_count"] for item in payload["seat_summaries"]), 4)
        self.assertEqual(report.ab_pair_count + report.ba_pair_count, 4)
        with self.assertRaises(FrozenInstanceError):
            report.valid_pair_count = 0  # type: ignore[misc]

    def test_invalid_incomplete_duplicate_and_unknown_inputs_fail_closed(self) -> None:
        schedule = build_paired_schedule((3,), _conditions())
        invalid_rule = _audit("rule", "win", "score_1")
        invalid_rule["model_attempt_count"] = 1
        invalid_rule["model_outcome_counts"] = [["success", 1]]
        audits = [
            _submission(3, 0, "rule", invalid_rule),
            _submission(3, 0, "deepseek", _audit("deepseek", "win", "score_1")),
            _submission(3, 1, "rule", _audit("rule", "win", "score_1")),
            _submission(3, 1, "rule", _audit("rule", "win", "score_1")),
            _submission(3, 1, "deepseek", _audit("deepseek", "win", "score_1")),
            _submission(99, 0, "rule", _audit("rule", "win", "score_1")),
        ]
        report = aggregate_policy_audits(schedule, audits, _conditions())
        self.assertEqual((report.valid_pair_count, report.invalid_pair_count, report.incomplete_pair_count), (0, 2, 2))
        self.assertEqual(report.duplicate_pair_count, 1)
        self.assertEqual(report.rule_score_counts, ())
        self.assertEqual(report.deepseek_model_attempt_count, 0)
        self.assertEqual(report.diagnostics, (("audit_invalid", 1), ("duplicate_side", 1), ("missing_side", 2), ("unknown_condition", 1)))

    def test_mode_profile_transport_and_non_normal_results_are_excluded(self) -> None:
        schedule = build_paired_schedule((3,), _conditions())
        cases: list[PolicyAuditSubmission] = []
        wrong_mode = _audit("rule", "win", "score_1")
        wrong_mode["agent_mode"] = "deepseek"
        cases.extend((_submission(3, 0, "rule", wrong_mode), _submission(3, 0, "deepseek", _audit("deepseek", "win", "score_1"))))
        transport = _audit("rule", "win", "score_1")
        transport["transport_timeouts"] = 1
        cases.extend((_submission(3, 1, "rule", transport), _submission(3, 1, "deepseek", _audit("deepseek", "win", "score_1"))))
        platform = _audit("rule", "win", "score_1")
        platform["result_category_counts"] = [["platform_error", 1]]
        cases.extend((_submission(3, 2, "rule", platform), _submission(3, 2, "deepseek", _audit("deepseek", "win", "score_1"))))
        bad_profile = _submission(3, 3, "rule", _audit("rule", "win", "score_1"))
        cases.extend((bad_profile, PolicyAuditSubmission(3, 3, "deepseek", "other", _audit("deepseek", "win", "score_1"))))
        report = aggregate_policy_audits(schedule, cases, _conditions())
        self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (0, 4))
        self.assertEqual(report.diagnostics, (("audit_invalid", 2), ("condition_mismatch", 1), ("strategy_mismatch", 1)))

    def test_deepseek_observability_conservation_and_invalid_score_shape_are_excluded(self) -> None:
        schedule = build_paired_schedule((4,), _conditions())
        malformed_deepseek = _audit("deepseek", "win", "score_1")
        malformed_deepseek["model_attempt_count"] = 0
        invalid_score = _audit("rule", "win", "score_1")
        invalid_score["result_category_counts"] = [["invalid_score_shape", 1]]
        audits = (
            _submission(4, 0, "rule", _audit("rule", "win", "score_1")),
            _submission(4, 0, "deepseek", malformed_deepseek),
            _submission(4, 1, "rule", invalid_score),
            _submission(4, 1, "deepseek", _audit("deepseek", "win", "score_1")),
        )
        report = aggregate_policy_audits(schedule, audits, _conditions())
        self.assertEqual((report.valid_pair_count, report.invalid_pair_count, report.incomplete_pair_count), (0, 2, 2))
        self.assertEqual(report.diagnostics, (("audit_invalid", 2), ("missing_side", 2)))

    def test_empty_schedule_has_exact_zero_fractions_and_order_is_irrelevant(self) -> None:
        empty = aggregate_policy_audits(build_paired_schedule((), _conditions()), (), _conditions())
        self.assertEqual(empty.to_dict()["rule_score_mean"], [0, 1])
        schedule = build_paired_schedule((5,), _conditions())
        audits = [
            _submission(5, seat, strategy, _audit(strategy, "win", "score_1"))
            for seat in range(4)
            for strategy in ("rule", "deepseek")
        ]
        first = aggregate_policy_audits(schedule, audits, _conditions()).to_dict()
        second = aggregate_policy_audits(tuple(reversed(schedule)), tuple(reversed(audits)), _conditions()).to_dict()
        self.assertEqual(first, second)
        serialized = json.dumps(first, sort_keys=True, separators=(",", ":"))
        self.assertEqual(serialized, json.dumps(second, sort_keys=True, separators=(",", ":")))
        self.assertNotIn("nan", serialized.lower())
        self.assertNotIn("infinity", serialized.lower())

    def test_reports_do_not_serialize_pair_identifiers_or_payloads_and_module_stays_offline(self) -> None:
        schedule = build_paired_schedule((17,), _conditions())
        audit = _audit("rule", "win", "score_1")
        submission = _submission(17, 0, "rule", audit)
        self.assertIsNot(submission.audit, audit)
        with self.assertRaises(TypeError):
            submission.audit["cycles"] = 9  # type: ignore[index]
        report = aggregate_policy_audits(schedule, (submission,), _conditions())
        text = json.dumps(report.to_dict(), sort_keys=True)
        for marker in ("seed", "audit", "match", "player", "hand", "history", "prompt", "reasoning", "url", "key"):
            self.assertNotIn(marker, text.lower())
        source = Path("evaluation/botzone_policy_benchmark.py").read_text(encoding="utf-8")
        for marker in ("integrations.botzone.connector", "integrations.botzone.runner", "http_transport", "deepseek_client", "config", "socket", "urllib"):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
