from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from agents.deepseek_client import DeepSeekSuggestion
from evaluation.confidence_action_ablation import (
    ActionAblationBucket,
    ConfidenceActionAblationReport,
    _Accumulator,
    _classify_result,
    _external_bucket,
    _priority,
    _record_condition,
    run_confidence_action_ablation,
)


class DeterministicProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> DeepSeekSuggestion:
        self.calls.append(dict(kwargs))
        candidates = kwargs["prompt_actions"]
        self.assert_candidate_shape(candidates)
        actions = list(candidates)  # type: ignore[arg-type]
        action_id = actions[-1]["action_id"] if "card_confidence_prompt" in kwargs else actions[0]["action_id"]
        return DeepSeekSuggestion(action_id=action_id, reasoning=None)

    @staticmethod
    def assert_candidate_shape(candidates: object) -> None:
        if not isinstance(candidates, list) or not candidates:
            raise AssertionError("provider received no prompt candidates")


def _provider() -> DeterministicProvider:
    return DeterministicProvider()


class ConfidenceActionAblationTests(unittest.TestCase):
    def test_strict_input_validation(self) -> None:
        provider = _provider()
        invalid = (
            lambda: run_confidence_action_ablation((), suggestion_provider=provider),
            lambda: run_confidence_action_ablation("120", suggestion_provider=provider),  # type: ignore[arg-type]
            lambda: run_confidence_action_ablation((120, 120), suggestion_provider=provider),
            lambda: run_confidence_action_ablation((True,), suggestion_provider=provider),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=None),  # type: ignore[arg-type]
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, strategic_pass_rates=()),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, strategic_pass_rates=(0, 0)),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, strategic_pass_rates=(True,)),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, samples_per_bucket=0),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, max_steps=True),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, max_external_cards=13),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, max_search_nodes=1.5),
            lambda: run_confidence_action_ablation((120,), suggestion_provider=provider, current_level_rank="SJ"),
        )
        for call in invalid:
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()

    def test_bucket_priority_and_fail_closed_result_categories(self) -> None:
        self.assertEqual(
            [_external_bucket(value) for value in (0, 4, 5, 8, 9, 12)],
            ["external_0_4", "external_0_4", "external_5_8", "external_5_8", "external_9_12", "external_9_12"],
        )
        self.assertIsNone(_external_bucket(13))
        first = _priority("forced_only", "external_0_4", 120, 5, 1)
        self.assertEqual(first, _priority("forced_only", "external_0_4", 120, 5, 1))
        self.assertNotEqual(first, _priority("forced_only", "external_0_4", 121, 5, 1))
        self.assertEqual(len(first), 64)

        legal = {1: {"action_id": 1, "declared_pattern": "single"}, 2: {"action_id": 2, "declared_pattern": "bomb"}}
        prompt_ids = frozenset({1})
        categories = (
            (object(), "malformed_result"),
            (DeepSeekSuggestion(None, None), "no_action"),
            (DeepSeekSuggestion(True, None), "invalid_action_type"),
            (DeepSeekSuggestion("1", None), "invalid_action_type"),  # type: ignore[arg-type]
            (DeepSeekSuggestion(3, None), "outside_legal"),
            (DeepSeekSuggestion(2, None), "outside_prompt"),
            (DeepSeekSuggestion(1, None), "valid"),
        )
        for result, expected in categories:
            with self.subTest(expected=expected):
                self.assertEqual(_classify_result(result, legal, prompt_ids)[0], expected)

    def test_exception_does_not_prevent_other_condition_and_counting_is_conserved(self) -> None:
        accumulator = _Accumulator()
        legal = {1: {"action_id": 1, "declared_pattern": "pass"}, 2: {"action_id": 2, "declared_pattern": "bomb"}}
        self.assertFalse(_record_condition(accumulator, "off", "exception", None, legal))
        self.assertTrue(_record_condition(accumulator, "on", "valid", 2, legal))
        bucket = accumulator.freeze()
        self.assertEqual(bucket.off_attempted_call_count, 1)
        self.assertEqual(bucket.off_exception_count, 1)
        self.assertEqual(bucket.on_attempted_call_count, 1)
        self.assertEqual(bucket.on_valid_response_count, 1)
        self.assertEqual(bucket.on_pressure_selection_count, 1)
        self.assertEqual(bucket.off_pass_selection_count, 0)

    def test_small_run_is_deterministic_balanced_and_keeps_only_aggregate_data(self) -> None:
        provider_one = _provider()
        kwargs = {
            "suggestion_provider": provider_one,
            "strategic_pass_rates": (0, 100),
            "samples_per_bucket": 1,
            "max_steps": 5000,
            "max_samples_per_game": 128,
        }
        first = run_confidence_action_ablation((120,), **kwargs)
        provider_two = _provider()
        second = run_confidence_action_ablation(
            (120,),
            **{**kwargs, "suggestion_provider": provider_two},
        )
        self.assertEqual(first, second)
        self.assertEqual(tuple(first.by_policy), ("forced_only", "strategic_pass_100"))
        self.assertGreater(len(provider_one.calls), 0)
        for report in first.by_policy.values():
            with self.subTest(policy=report.policy_name):
                self.assertEqual((report.requested_game_count, report.completed_game_count, report.incomplete_game_count), (1, 1, 0))
                overall = report.overall
                self.assertEqual(overall.off_attempted_call_count, overall.selected_sample_count)
                self.assertEqual(overall.on_attempted_call_count, overall.selected_sample_count)
                self.assertEqual(overall.off_first_pair_count + overall.on_first_pair_count, overall.selected_sample_count)
                self.assertEqual(
                    overall.both_valid_pair_count + overall.only_off_valid_count + overall.only_on_valid_count + overall.neither_valid_count,
                    overall.selected_sample_count,
                )
                self.assertEqual(overall.same_action_count + overall.changed_action_count, overall.both_valid_pair_count)
                self.assertEqual(overall.off_exception_count + overall.on_exception_count, 0)
                self.assertEqual(overall.off_malformed_result_count + overall.on_malformed_result_count, 0)
                self.assertEqual(
                    sum(bucket.selected_sample_count for bucket in report.by_external_count.values()),
                    overall.selected_sample_count,
                )
                self.assertTrue(all(bucket.selected_sample_count <= 1 for bucket in report.by_external_count.values()))

        for index in range(0, len(provider_one.calls), 2):
            off_kwargs, on_kwargs = provider_one.calls[index:index + 2]
            keys = set(off_kwargs) ^ set(on_kwargs)
            self.assertEqual(keys, {"card_confidence_prompt"})
            common = set(off_kwargs) & set(on_kwargs)
            self.assertTrue(all(off_kwargs[key] == on_kwargs[key] for key in common))

        payload = first.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        for forbidden in ("seed", "sample_id", "observation", "history", "prompt_actions", "legal_actions", "action_id", "reasoning", "hand"):
            self.assertNotIn(f'"{forbidden}"', serialized)
        self.assertIn("__slots__", ConfidenceActionAblationReport.__dict__)
        with self.assertRaises(FrozenInstanceError):
            first.requested_policy_count = 99  # type: ignore[misc]
        with self.assertRaises(TypeError):
            first.by_policy["other"] = next(iter(first.by_policy.values()))  # type: ignore[index]

    def test_report_bucket_is_json_friendly(self) -> None:
        bucket = ActionAblationBucket(
            **{name: 0 for name in ActionAblationBucket.__dataclass_fields__ if name not in {"prompt_pair_sha256", "diagnostic_counts"}},
            prompt_pair_sha256=hashlib.sha256().hexdigest(),
            diagnostic_counts=MappingProxyType({}),
        )
        self.assertEqual(json.loads(json.dumps(bucket.to_dict(), allow_nan=False))["selected_sample_count"], 0)

    def test_source_has_no_runtime_configuration_or_hidden_truth_access(self) -> None:
        source = Path("evaluation/confidence_action_ablation.py").read_text(encoding="utf-8")
        for forbidden in ("AppConfig", ".env", "api_key", "ground_truth", "game._state", "suggest_action_id", "urlopen"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
