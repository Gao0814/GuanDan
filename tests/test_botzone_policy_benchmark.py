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
    build_selected_paired_schedule,
)
from integrations.botzone.agent_observability import SUCCESSFUL_MODEL_DECISION_SOURCES
from integrations.botzone.run_provenance import TOKEN_AUDIT_VERSION


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
        if source in SUCCESSFUL_MODEL_DECISION_SOURCES:
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


def _submission(
    seed: int,
    seat: int,
    strategy: str,
    audit: dict[str, object],
    run_token: str | None = None,
) -> PolicyAuditSubmission:
    return PolicyAuditSubmission(seed, seat, strategy, PROFILE_VERSION, audit, run_token)


def _with_idle_timeout(audit: dict[str, object], count: int) -> dict[str, object]:
    audit["transport_timeouts"] = count
    audit["diagnostics"] = [["transport_timeout", count]]
    return audit


def _tokenized_audit(audit: dict[str, object], run_token: str) -> dict[str, object]:
    audit["version"] = TOKEN_AUDIT_VERSION
    audit["run_token"] = run_token
    return audit


class BotzonePolicyBenchmarkTests(unittest.TestCase):
    def test_successful_model_rewrite_sources_are_accepted_and_aggregated(self) -> None:
        for source in (
            "teammate_control_block",
            "danger_opponent_block",
            "short_endgame_plan",
        ):
            with self.subTest(source=source):
                schedule = build_selected_paired_schedule((31,), (0,), _conditions())
                report = aggregate_policy_audits(
                    schedule,
                    (
                        _submission(31, 0, "rule", _audit("rule", "loss", "score_0")),
                        _submission(31, 0, "deepseek", _audit("deepseek", "win", "score_1", source=source)),
                    ),
                    _conditions(),
                )
                self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (1, 0))
                self.assertEqual(report.deepseek_model_attempt_count, 1)
                self.assertEqual(report.deepseek_decision_source_counts, ((source, 1),))

    def test_legacy_control_v8_audits_remain_read_compatible(self) -> None:
        for source in ("teammate_control_block", "danger_opponent_block"):
            with self.subTest(source=source):
                conditions = BenchmarkConditions(PROFILE_VERSION, True, True, run_provenance_required=True)
                schedule = build_selected_paired_schedule((37,), (0,), conditions)
                report = aggregate_policy_audits(
                    schedule,
                    (
                        _submission(
                            37,
                            0,
                            "rule",
                            _tokenized_audit(_audit("rule", "loss", "score_0"), "3" * 32),
                            "3" * 32,
                        ),
                        _submission(
                            37,
                            0,
                            "deepseek",
                            _tokenized_audit(
                                _audit("deepseek", "win", "score_1", source=source),
                                "4" * 32,
                            ),
                            "4" * 32,
                        ),
                    ),
                    conditions,
                )
                self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (1, 0))

    def test_successful_model_rewrite_sources_fail_closed_on_count_or_outcome_mismatch(self) -> None:
        schedule = build_selected_paired_schedule((41,), (0,), _conditions())
        for source in ("teammate_control_block", "danger_opponent_block"):
            for label, mutate in (
                ("missing_attempt", lambda audit: audit.update(model_attempt_count=0)),
                ("extra_attempt", lambda audit: audit.update(model_attempt_count=2, model_outcome_counts=[["success", 2]])),
                ("non_success_outcome", lambda audit: audit.update(model_outcome_counts=[["timeout", 1]])),
            ):
                with self.subTest(source=source, label=label):
                    deepseek = _audit("deepseek", "win", "score_1", source=source)
                    mutate(deepseek)
                    report = aggregate_policy_audits(
                        schedule,
                        (
                            _submission(41, 0, "rule", _audit("rule", "loss", "score_0")),
                            _submission(41, 0, "deepseek", deepseek),
                        ),
                        _conditions(),
                    )
                    self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (0, 1))

    def test_nonformal_or_unknown_sources_remain_rejected(self) -> None:
        schedule = build_selected_paired_schedule((43,), (0,), _conditions())
        for source in ("conditional_pressure_pass", "unknown_source"):
            with self.subTest(source=source):
                deepseek = _audit("deepseek", "win", "score_1")
                deepseek["decision_source_counts"] = [[source, 1]]
                deepseek["model_attempt_count"] = 0
                deepseek["model_outcome_counts"] = []
                report = aggregate_policy_audits(
                    schedule,
                    (
                        _submission(43, 0, "rule", _audit("rule", "loss", "score_0")),
                        _submission(43, 0, "deepseek", deepseek),
                    ),
                    _conditions(),
                )
                self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (0, 1))
    def test_opt_in_conditional_audit_is_not_admitted_to_rule_deepseek_formal_comparison(self) -> None:
        audit = _audit("deepseek", "win", "score_2")
        audit["agent_mode"] = "conditional_pressure_pass"
        audit["decision_source_counts"] = [["conditional_pressure_pass", 1]]
        audit["model_attempt_count"] = 0
        audit["model_outcome_counts"] = []
        report = aggregate_policy_audits(
            build_selected_paired_schedule((1,), (0,), _conditions()),
            (_submission(1, 0, "conditional_pressure_pass", audit),),
            _conditions(),
        )
        self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (0, 1))

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

    def test_selected_schedule_is_explicit_ordered_subset_of_formal_schedule(self) -> None:
        conditions = _conditions()
        selected = build_selected_paired_schedule((13, 5), (3, 1), conditions)
        formal = {
            (pair.seed, pair.local_seat): pair
            for pair in build_paired_schedule((13, 5), conditions)
        }
        self.assertEqual(
            [(pair.seed, pair.local_seat) for pair in selected],
            [(13, 3), (13, 1), (5, 3), (5, 1)],
        )
        self.assertEqual(selected, tuple(formal[(pair.seed, pair.local_seat)] for pair in selected))
        self.assertEqual(
            build_selected_paired_schedule((13, 5), (3, 1), conditions),
            selected,
        )
        self.assertEqual(
            [pair.first_strategy for pair in selected],
            [formal[(pair.seed, pair.local_seat)].first_strategy for pair in selected],
        )

    def test_selected_schedule_rejects_non_tuple_empty_or_invalid_seats(self) -> None:
        for seats in ((), [0], (True,), (0, 0), (4,), (-1,)):  # type: ignore[list-item]
            with self.subTest(seats=seats):
                with self.assertRaises(PolicyBenchmarkError):
                    build_selected_paired_schedule((1,), seats, _conditions())  # type: ignore[arg-type]

    def test_selected_single_seat_requests_only_its_declared_pair(self) -> None:
        schedule = build_selected_paired_schedule((11,), (0,), _conditions())
        report = aggregate_policy_audits(
            schedule,
            (
                _submission(11, 0, "rule", _audit("rule", "win", "score_1")),
                _submission(11, 0, "deepseek", _audit("deepseek", "loss", "score_0")),
            ),
            _conditions(),
        )
        self.assertEqual(
            (report.requested_pair_count, report.valid_pair_count, report.invalid_pair_count, report.incomplete_pair_count),
            (1, 1, 0, 0),
        )
        self.assertEqual(sum(item.valid_pair_count for item in report.seat_summaries), 1)

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

    def test_matching_idle_timeout_diagnostics_are_accepted(self) -> None:
        conditions = BenchmarkConditions(PROFILE_VERSION, True, True, run_provenance_required=True)
        schedule = build_selected_paired_schedule((19,), (0,), conditions)
        rule_token = "1" * 32
        deepseek_token = "2" * 32
        report = aggregate_policy_audits(
            schedule,
            (
                _submission(
                    19,
                    0,
                    "rule",
                    _tokenized_audit(_with_idle_timeout(_audit("rule", "win", "score_1"), 1), rule_token),
                    rule_token,
                ),
                _submission(
                    19,
                    0,
                    "deepseek",
                    _tokenized_audit(_with_idle_timeout(_audit("deepseek", "loss", "score_0"), 2), deepseek_token),
                    deepseek_token,
                ),
            ),
            conditions,
        )
        self.assertEqual((report.valid_pair_count, report.invalid_pair_count, report.incomplete_pair_count), (1, 0, 0))

    def test_idle_timeout_contract_rejects_any_mismatch_or_transport_failure(self) -> None:
        schedule = build_selected_paired_schedule((23,), (0,), _conditions())

        def report_for(rule_audit: dict[str, object]) -> object:
            return aggregate_policy_audits(
                schedule,
                (
                    _submission(23, 0, "rule", rule_audit),
                    _submission(23, 0, "deepseek", _audit("deepseek", "loss", "score_0")),
                ),
                _conditions(),
            )

        cases: tuple[tuple[str, dict[str, object]], ...] = (
            ("timeout_without_diagnostic", dict(_audit("rule", "win", "score_1"), transport_timeouts=1)),
            (
                "timeout_diagnostic_count_mismatch",
                dict(_with_idle_timeout(_audit("rule", "win", "score_1"), 2), diagnostics=[["transport_timeout", 1]]),
            ),
            ("zero_timeout_with_diagnostic", dict(_audit("rule", "win", "score_1"), diagnostics=[["transport_timeout", 1]])),
            (
                "timeout_with_other_diagnostic",
                dict(
                    _with_idle_timeout(_audit("rule", "win", "score_1"), 1),
                    diagnostics=[["transport_timeout", 1], ["unsupported_stage", 1]],
                ),
            ),
            ("transport_failure", dict(_audit("rule", "win", "score_1"), transport_failures=1)),
            (
                "failure_category",
                dict(_audit("rule", "win", "score_1"), transport_failure_categories=[["unclassified", 1]]),
            ),
            ("bool_timeout", dict(_audit("rule", "win", "score_1"), transport_timeouts=True)),
            ("negative_timeout", dict(_audit("rule", "win", "score_1"), transport_timeouts=-1)),
            ("wrong_timeout_type", dict(_audit("rule", "win", "score_1"), transport_timeouts=[])),
            ("unknown_diagnostic", dict(_audit("rule", "win", "score_1"), diagnostics=[["unknown", 1]])),
        )
        for name, audit in cases:
            with self.subTest(name=name):
                report = report_for(audit)
                self.assertEqual((report.valid_pair_count, report.invalid_pair_count), (0, 1))
                self.assertEqual(report.diagnostics, (("audit_invalid", 1),))

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
