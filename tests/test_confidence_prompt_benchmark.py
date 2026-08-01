from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import unittest

from agents.card_confidence_prompt import CardConfidencePromptPayload
from evaluation.confidence_prompt_benchmark import (
    ConfidencePromptBenchmarkReport,
    _BucketAccumulator,
    _expected_on_prompt,
    _external_bucket,
    _overall_bucket,
    run_confidence_prompt_benchmark,
)


def _ready() -> CardConfidencePromptPayload:
    text = "范围：critical_endgame_policy_diverse_v1\n玩家2（余1张）：3[P=1,E=1]"
    return CardConfidencePromptPayload(
        "ready", text, len(text), "physical_assignment_marginal_v1",
        "critical_endgame_policy_diverse_v1", (),
    )


def _omitted() -> CardConfidencePromptPayload:
    return CardConfidencePromptPayload(
        "omitted", "", 0, "none", "none", ("prompt_budget_exceeded:detail",),
    )


class ConfidencePromptBenchmarkTests(unittest.TestCase):
    def test_strict_input_validation(self) -> None:
        invalid_calls = (
            lambda: run_confidence_prompt_benchmark(()),
            lambda: run_confidence_prompt_benchmark("80"),  # type: ignore[arg-type]
            lambda: run_confidence_prompt_benchmark((80, 80)),
            lambda: run_confidence_prompt_benchmark((True,)),
            lambda: run_confidence_prompt_benchmark((80,), strategic_pass_rates=()),
            lambda: run_confidence_prompt_benchmark((80,), strategic_pass_rates=(0, 0)),
            lambda: run_confidence_prompt_benchmark((80,), strategic_pass_rates=(True,)),
            lambda: run_confidence_prompt_benchmark((80,), current_level_rank="SJ"),
            lambda: run_confidence_prompt_benchmark((80,), max_steps=0),
            lambda: run_confidence_prompt_benchmark((80,), max_samples_per_game=True),
            lambda: run_confidence_prompt_benchmark((80,), max_external_cards=13),
            lambda: run_confidence_prompt_benchmark((80,), max_search_nodes=1.5),
            lambda: run_confidence_prompt_benchmark((80,), max_solutions=0),
        )
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()

    def test_bucket_boundaries_and_exact_pair_accounting(self) -> None:
        self.assertEqual([_external_bucket(value) for value in (0, 4, 5, 8, 9, 12)], [
            "external_0_4", "external_0_4", "external_5_8", "external_5_8", "external_9_12", "external_9_12",
        ])
        self.assertIsNone(_external_bucket(13))
        accumulator = _BucketAccumulator()
        confidence = SimpleNamespace(status="available", diagnostics=("one:detail", "one:again"))
        ready = _ready()
        off = "A\n【场景标签】\nB"
        on = _expected_on_prompt(off, ready.text)
        self.assertTrue(accumulator.record(confidence=confidence, payload=ready, off_prompt=off, on_prompt=on))
        bucket = accumulator.freeze()
        self.assertEqual(bucket.sample_count, 1)
        self.assertEqual(bucket.confidence_available_count, 1)
        self.assertEqual(bucket.payload_ready_count, 1)
        self.assertEqual(bucket.ready_exact_insertion_count, 1)
        self.assertEqual(bucket.payload_char_sum, ready.char_count)
        self.assertEqual(bucket.prompt_delta_char_sum, len(on) - len(off))
        self.assertEqual(bucket.diagnostic_counts, MappingProxyType({"one": 1}))

    def test_omitted_and_mismatch_are_fail_closed_and_aggregate_without_averaging(self) -> None:
        omitted_accumulator = _BucketAccumulator()
        unavailable = SimpleNamespace(status="unavailable", diagnostics=("allocation_not_complete",))
        omitted = _omitted()
        self.assertTrue(omitted_accumulator.record(
            confidence=unavailable, payload=omitted, off_prompt="off", on_prompt="off",
        ))
        mismatch_accumulator = _BucketAccumulator()
        self.assertFalse(mismatch_accumulator.record(
            confidence=unavailable, payload=omitted, off_prompt="off", on_prompt="different",
        ))
        combined = _overall_bucket({"a": omitted_accumulator, "b": mismatch_accumulator})
        self.assertEqual(combined.sample_count, 2)
        self.assertEqual(combined.confidence_unavailable_count, 2)
        self.assertEqual(combined.payload_omitted_count, 2)
        self.assertEqual(combined.omitted_prompt_equal_count, 1)
        self.assertEqual(combined.pair_mismatch_count, 1)
        self.assertEqual(combined.diagnostic_counts["prompt_pair_mismatch"], 1)
        self.assertEqual(combined.payload_char_min, 0)
        self.assertEqual(combined.prompt_delta_char_max, 0)

    def test_small_policy_run_is_deterministic_and_auditable(self) -> None:
        kwargs = {
            "strategic_pass_rates": (0, 100),
            "max_steps": 5000,
            "max_samples_per_game": 128,
        }
        first = run_confidence_prompt_benchmark((80,), **kwargs)
        second = run_confidence_prompt_benchmark((80,), **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(tuple(first.by_policy), ("forced_only", "strategic_pass_100"))
        for name, report in first.by_policy.items():
            with self.subTest(policy=name):
                self.assertEqual(report.requested_game_count, 1)
                self.assertEqual(report.completed_game_count, 1)
                self.assertEqual(report.incomplete_game_count, 0)
                self.assertEqual(report.evaluated_sample_count, report.valid_sample_count + report.invalid_sample_count)
                self.assertEqual(report.overall.sample_count, report.evaluated_sample_count)
                self.assertEqual(
                    sum(bucket.sample_count for bucket in report.by_external_count.values()),
                    report.overall.sample_count,
                )
                self.assertEqual(report.overall.pair_mismatch_count, 0)
                self.assertEqual(report.overall.ready_exact_insertion_count, report.overall.payload_ready_count)
                self.assertEqual(report.overall.payload_omitted_count, report.overall.omitted_prompt_equal_count)
                self.assertTrue(all(bucket.sample_count > 0 for bucket in report.by_external_count.values()))
                self.assertTrue(all(bucket.payload_ready_count > 0 for bucket in report.by_external_count.values()))
                self.assertLessEqual(report.strategic_pass_count, report.strategic_pass_opportunity_count)
        self.assertEqual(first.by_policy["forced_only"].strategic_pass_count, 0)
        self.assertEqual(
            first.by_policy["strategic_pass_100"].strategic_pass_count,
            first.by_policy["strategic_pass_100"].strategic_pass_opportunity_count,
        )

    def test_sample_limit_max_steps_report_safety_and_json(self) -> None:
        report = run_confidence_prompt_benchmark(
            (80,), strategic_pass_rates=(0,), max_steps=1, max_samples_per_game=1,
        ).by_policy["forced_only"]
        self.assertEqual(report.completed_game_count, 0)
        self.assertEqual(report.incomplete_game_count, 1)
        self.assertIn("max_steps_reached", report.diagnostic_counts)
        payload = report.to_dict()
        self.assertIsInstance(json.dumps(payload, allow_nan=False), str)
        serialized = json.dumps(payload, ensure_ascii=False)
        for forbidden in ("seed", "sample_id", "observation", "legal_actions", "players", "hands", "off_prompt", "on_prompt"):
            self.assertNotIn(f'"{forbidden}"', serialized)
        self.assertIn("__slots__", ConfidencePromptBenchmarkReport.__dict__)
        with self.assertRaises(FrozenInstanceError):
            report.policy_name = "other"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            report.by_external_count["x"] = report.overall  # type: ignore[index]

        limited = run_confidence_prompt_benchmark(
            (80,), strategic_pass_rates=(0,), max_samples_per_game=1,
        ).by_policy["forced_only"]
        self.assertGreater(limited.sample_limit_skipped_count, 0)
        self.assertIn("sample_limit_reached", limited.diagnostic_counts)

    def test_source_has_no_request_or_hidden_truth_access(self) -> None:
        source = Path("evaluation/confidence_prompt_benchmark.py").read_text(encoding="utf-8")
        for forbidden in (
            "suggest_action_id", "_post_json", "api_key", "ground_truth",
            "game._state", "benchmark_truth",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
