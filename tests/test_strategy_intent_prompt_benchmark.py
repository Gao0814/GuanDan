from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from agents.strategy_intent_prompt import build_strategy_intent_prompt_payload
from agents.strategy_router import StrategyIntentContext
from evaluation.strategy_intent_prompt_benchmark import (
    StrategyIntentPromptCoverageBucket,
    _BucketAccumulator,
    _record_pair,
    run_strategy_intent_prompt_benchmark,
)


def _intent() -> StrategyIntentContext:
    return StrategyIntentContext(
        status="available", source="public_strategy_router_v1", phase="midgame",
        intent="control", reason_codes=("stable_control",), my_player_id=1,
        my_team="team_13", my_hand_count=5, teammate_player_id=3,
        teammate_hand_count=5, minimum_opponent_hand_count=5, urgent_opponent_ids=(),
        can_finish_now=False, is_free_lead=True, table_leader_player_id=None,
        table_leader_relation=None, table_leader_is_urgent=False,
        hand_strength="non_weak", hand_total_score=50, hand_control_score=10,
        diagnostics=(),
    )


class TestStrategyIntentPromptBenchmark(unittest.TestCase):
    def test_strict_input_validation(self) -> None:
        cases = (
            {"seeds": ()}, {"seeds": (True,)}, {"seeds": (7, 7)}, {"seeds": "7"},
            {"seeds": (7,), "current_level_rank": "SJ"}, {"seeds": (7,), "strategic_pass_rates": ()},
            {"seeds": (7,), "strategic_pass_rates": (0, 0)}, {"seeds": (7,), "strategic_pass_rates": (True,)},
            {"seeds": (7,), "strategic_pass_rates": (101,)}, {"seeds": (7,), "max_steps": 0},
            {"seeds": (7,), "max_steps": True}, {"seeds": (7,), "max_samples_per_phase_per_game": 0},
            {"seeds": (7,), "max_samples_per_phase_per_game": 1.0},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_strategy_intent_prompt_benchmark(**kwargs)  # type: ignore[arg-type]

    def test_ordered_immutable_json_safe_and_repeatable_real_game_report(self) -> None:
        first = run_strategy_intent_prompt_benchmark((7,), strategic_pass_rates=(100, 0, 25))
        second = run_strategy_intent_prompt_benchmark((7,), strategic_pass_rates=(100, 0, 25))
        self.assertEqual(first, second)
        self.assertEqual(
            [(policy.policy_name, policy.strategic_pass_rate) for policy in first.policies],
            [("strategic_pass_100", 100), ("forced_only", 0), ("strategic_pass_25", 25)],
        )
        payload = json.dumps(first.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertNotIn("seed", payload)
        self.assertNotIn("action_id", payload)
        self.assertNotIn("hand_cards", payload)
        self.assertNotIn("prompt_text", payload)
        with self.assertRaises(FrozenInstanceError):
            first.requested_policy_count = 0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            first.policies[0].by_phase["midgame"] = first.policies[0].overall  # type: ignore[index]
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertEqual(digest, hashlib.sha256(json.dumps(second.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest())

    def test_real_policy_boundaries_phase_conservation_and_prompt_cost(self) -> None:
        report = run_strategy_intent_prompt_benchmark((7, 8), strategic_pass_rates=(0, 100))
        forced, always = report.policies
        self.assertEqual(forced.strategic_pass_count, 0)
        self.assertEqual(always.strategic_pass_count, always.strategic_pass_opportunity_count)
        for policy in report.policies:
            overall = policy.overall
            self.assertEqual(policy.observed_turn_count, policy.only_pass_skipped_count + policy.finishing_skipped_count + policy.opening_skipped_count + policy.eligible_sample_count)
            self.assertEqual(policy.eligible_sample_count, policy.duplicate_sample_count + policy.sample_limit_skipped_count + policy.evaluated_sample_count)
            self.assertEqual(overall.sample_count, policy.evaluated_sample_count)
            self.assertEqual(overall.sample_count, overall.router_available_count + overall.router_unavailable_count + overall.router_invalid_count)
            self.assertEqual(overall.router_available_count + overall.router_unavailable_count, overall.payload_ready_count + overall.payload_omitted_count + overall.payload_invalid_count)
            self.assertEqual(overall.payload_ready_count, overall.exact_insertion_count + overall.ready_pair_mismatch_count)
            self.assertEqual(overall.payload_omitted_count, overall.omitted_prompt_equal_count + overall.omitted_pair_mismatch_count)
            self.assertEqual(overall.prompt_pair_mismatch_count, overall.ready_pair_mismatch_count + overall.omitted_pair_mismatch_count)
            self.assertEqual(sum(bucket.sample_count for bucket in policy.by_phase.values()), overall.sample_count)
            self.assertEqual(sum(bucket.payload_char_sum for bucket in policy.by_phase.values()), overall.payload_char_sum)
            self.assertEqual(overall.prompt_delta_char_sum, overall.payload_char_sum + 9 * overall.payload_ready_count)
            self.assertGreater(overall.payload_char_min, 0)
            self.assertLessEqual(overall.payload_char_max, 800)

    def test_malformed_router_and_payload_are_invalid_without_pair_fields(self) -> None:
        with mock.patch("evaluation.strategy_intent_prompt_benchmark.route_strategy_intent", return_value=object()):
            report = run_strategy_intent_prompt_benchmark((7,), strategic_pass_rates=(0,))
        bucket = report.policies[0].overall
        self.assertEqual(bucket.sample_count, bucket.router_invalid_count)
        self.assertEqual((bucket.payload_ready_count, bucket.payload_omitted_count, bucket.payload_invalid_count), (0, 0, 0))
        self.assertEqual(dict(bucket.diagnostic_counts), {"invalid_router_result": bucket.sample_count})

        with mock.patch("evaluation.strategy_intent_prompt_benchmark.build_strategy_intent_prompt_payload", return_value=object()):
            report = run_strategy_intent_prompt_benchmark((7,), strategic_pass_rates=(0,))
        bucket = report.policies[0].overall
        self.assertEqual(bucket.payload_invalid_count, bucket.sample_count)
        self.assertEqual((bucket.payload_ready_count, bucket.payload_omitted_count), (0, 0))
        self.assertEqual(dict(bucket.diagnostic_counts), {"invalid_payload_result": bucket.sample_count})

    def test_exact_ready_and_omitted_pair_rules_and_diagnostics(self) -> None:
        ready = build_strategy_intent_prompt_payload(_intent())
        omitted = build_strategy_intent_prompt_payload(replace(_intent(), status="unavailable", intent=None, reason_codes=(), my_player_id=None, my_team=None, my_hand_count=None, teammate_player_id=None, teammate_hand_count=None, minimum_opponent_hand_count=None, hand_strength=None, hand_total_score=None, hand_control_score=None, diagnostics=("invalid",), is_free_lead=False))
        off = "before\n【场景标签】\nafter"
        on = off.replace("【场景标签】", f"【策略意图】\n{ready.text}\n\n【场景标签】")
        accumulator = _BucketAccumulator()
        hasher = hashlib.sha256()
        _record_pair(accumulator, phase="midgame", payload=ready, off=off, on=on, hasher=hasher)
        self.assertEqual((accumulator.payload_ready_count, accumulator.exact_insertion_count), (1, 1))
        self.assertEqual(accumulator.prompt_delta_char_sum, ready.char_count + 9)
        _record_pair(accumulator, phase="midgame", payload=omitted, off=off, on=off, hasher=hasher)
        self.assertEqual((accumulator.payload_omitted_count, accumulator.omitted_prompt_equal_count), (1, 1))
        _record_pair(accumulator, phase="midgame", payload=ready, off=off, on=off, hasher=hasher)
        self.assertEqual((accumulator.ready_pair_mismatch_count, accumulator.diagnostic_counts["prompt_pair_mismatch"]), (1, 1))

    def test_source_has_no_model_request_or_sensitive_access(self) -> None:
        source = Path("evaluation/strategy_intent_prompt_benchmark.py").read_text(encoding="utf-8")
        for forbidden in ("suggest_action_id", "api_key", "ground_truth", "game._state", "record.txt", "urlopen"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
