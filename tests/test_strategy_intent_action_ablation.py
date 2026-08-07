from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from agents.deepseek_client import DeepSeekSuggestion
from agents.strategy_intent_prompt import StrategyIntentPromptPayload
from agents.strategy_router import StrategyIntentContext
from evaluation.strategy_intent_action_ablation import (
    StrategyIntentActionAblationBucket,
    _classify,
    _priority,
    run_strategy_intent_action_ablation,
)


def _deterministic_provider(**kwargs: object) -> DeepSeekSuggestion:
    actions = kwargs["prompt_actions"]
    assert isinstance(actions, list)
    index = -1 if "strategy_intent_prompt" in kwargs else 0
    return DeepSeekSuggestion(action_id=actions[index]["action_id"], reasoning=None)


class TestStrategyIntentActionAblation(unittest.TestCase):
    def test_strict_input_validation(self) -> None:
        cases = (
            {"seeds": ()},
            {"seeds": (True,)},
            {"seeds": (1, 1)},
            {"seeds": "1"},
            {"seeds": (1,), "suggestion_provider": None},
            {"seeds": (1,), "strategic_pass_rates": ()},
            {"seeds": (1,), "strategic_pass_rates": (0, 0)},
            {"seeds": (1,), "strategic_pass_rates": (True,)},
            {"seeds": (1,), "strategic_pass_rates": (101,)},
            {"seeds": (1,), "samples_per_phase": 0},
            {"seeds": (1,), "samples_per_phase": 3},
            {"seeds": (1,), "samples_per_phase": True},
            {"seeds": (1,), "current_level_rank": "SJ"},
            {"seeds": (1,), "max_steps": 0},
            {"seeds": (1,), "max_samples_per_phase_per_game": 1.0},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                args = {"suggestion_provider": _deterministic_provider}
                args.update(kwargs)
                with self.assertRaises(ValueError):
                    run_strategy_intent_action_ablation(**args)  # type: ignore[arg-type]

    def test_priority_and_provider_result_classification_are_strict(self) -> None:
        first = _priority("forced_only", "midgame", 7, 10, 1)
        self.assertEqual(first, _priority("forced_only", "midgame", 7, 10, 1))
        self.assertNotEqual(first, _priority("forced_only", "midgame", 8, 10, 1))
        legal = {
            1: {"action_id": 1, "declared_pattern": "single"},
            2: {"action_id": 2, "declared_pattern": "pass"},
        }
        prompt_ids = frozenset({1})
        cases = (
            (object(), "malformed_result"),
            (DeepSeekSuggestion(action_id=None, reasoning=None), "no_action"),
            (DeepSeekSuggestion(action_id=True, reasoning=None), "invalid_action_type"),
            (DeepSeekSuggestion(action_id="1", reasoning=None), "invalid_action_type"),  # type: ignore[arg-type]
            (DeepSeekSuggestion(action_id=3, reasoning=None), "outside_legal"),
            (DeepSeekSuggestion(action_id=2, reasoning=None), "outside_prompt"),
            (DeepSeekSuggestion(action_id=1, reasoning=None), "valid"),
        )
        for result, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(_classify(result, legal, prompt_ids)[0], expected)

    def test_real_public_collection_pairs_only_differ_by_ready_payload(self) -> None:
        calls: list[dict[str, object]] = []

        def provider(**kwargs: object) -> DeepSeekSuggestion:
            calls.append(dict(kwargs))
            return _deterministic_provider(**kwargs)

        report = run_strategy_intent_action_ablation(
            (7,),
            suggestion_provider=provider,
            strategic_pass_rates=(0,),
            samples_per_phase=2,
        )
        policy = report.policies[0]
        self.assertEqual((policy.requested_game_count, policy.completed_game_count, policy.incomplete_game_count), (1, 1, 0))
        self.assertEqual(policy.strategic_pass_count, 0)
        self.assertEqual(len(calls), 16)
        off = [item for item in calls if "strategy_intent_prompt" not in item]
        on = [item for item in calls if "strategy_intent_prompt" in item]
        self.assertEqual((len(off), len(on)), (8, 8))
        for off_kwargs, on_kwargs in zip(off, on):
            self.assertEqual(set(on_kwargs) - set(off_kwargs), {"strategy_intent_prompt"})
            self.assertEqual(set(off_kwargs) - set(on_kwargs), set())
            for key in off_kwargs:
                self.assertIs(on_kwargs[key], off_kwargs[key])
        for bucket in policy.by_phase.values():
            self.assertEqual(
                (
                    bucket.selected_sample_count,
                    bucket.off_first_pair_count,
                    bucket.on_first_pair_count,
                    bucket.off_attempted_call_count,
                    bucket.on_attempted_call_count,
                    bucket.both_valid_pair_count,
                    bucket.changed_action_count,
                ),
                (2, 1, 1, 2, 2, 2, 2),
            )
        overall = policy.overall
        self.assertEqual((overall.selected_sample_count, overall.off_attempted_call_count, overall.on_attempted_call_count), (8, 8, 8))
        self.assertEqual((overall.same_action_count, overall.changed_action_count), (0, 8))

    def test_first_side_exception_still_calls_second_side_and_counts_are_conserved(self) -> None:
        calls: list[str] = []

        def provider(**kwargs: object) -> DeepSeekSuggestion:
            condition = "on" if "strategy_intent_prompt" in kwargs else "off"
            calls.append(condition)
            if condition == "off":
                raise RuntimeError("expected test failure")
            return _deterministic_provider(**kwargs)

        report = run_strategy_intent_action_ablation(
            (7,),
            suggestion_provider=provider,
            strategic_pass_rates=(0,),
            samples_per_phase=2,
        )
        bucket = report.policies[0].overall
        self.assertEqual((bucket.off_attempted_call_count, bucket.on_attempted_call_count), (8, 8))
        self.assertEqual((bucket.off_exception_count, bucket.on_valid_response_count), (8, 8))
        self.assertEqual((bucket.only_on_valid_count, bucket.only_off_valid_count, bucket.neither_valid_count), (8, 0, 0))
        self.assertEqual(len(calls), 16)

    def test_router_payload_candidate_and_pair_failures_do_not_call_provider(self) -> None:
        calls: list[object] = []

        def provider(**kwargs: object) -> DeepSeekSuggestion:
            calls.append(kwargs)
            return _deterministic_provider(**kwargs)

        with mock.patch(
            "evaluation.strategy_intent_action_ablation.route_strategy_intent",
            return_value=object(),
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].overall.router_invalid_skip_count, 0)

        omitted = StrategyIntentPromptPayload(
            status="omitted",
            source="strategy_intent_prompt_v1",
            router_source=None,
            phase=None,
            intent=None,
            text="",
            char_count=0,
            diagnostics=("context_unavailable",),
        )
        with mock.patch(
            "evaluation.strategy_intent_action_ablation.build_strategy_intent_prompt_payload",
            return_value=omitted,
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].overall.payload_omitted_skip_count, 0)

        with mock.patch(
            "evaluation.strategy_intent_action_ablation._prompt_actions",
            side_effect=lambda observation, actions, phase: actions[:1],
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].overall.insufficient_prompt_candidates_count, 0)

        with mock.patch(
            "evaluation.strategy_intent_action_ablation._exact_prompt_pair",
            return_value=False,
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].overall.prompt_mismatch_count, 0)

    def test_shortcuts_and_router_unavailable_never_call_provider(self) -> None:
        calls: list[object] = []

        def provider(**kwargs: object) -> DeepSeekSuggestion:
            calls.append(kwargs)
            return _deterministic_provider(**kwargs)

        with mock.patch(
            "evaluation.strategy_intent_action_ablation._only_pass",
            return_value=True,
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].observed_turn_count, 0)

        unavailable = StrategyIntentContext(
            status="unavailable", source="public_strategy_router_v1", phase="midgame",
            intent=None, reason_codes=(), my_player_id=None, my_team=None,
            my_hand_count=None, teammate_player_id=None, teammate_hand_count=None,
            minimum_opponent_hand_count=None, urgent_opponent_ids=(),
            can_finish_now=False, is_free_lead=False, table_leader_player_id=None,
            table_leader_relation=None, table_leader_is_urgent=False,
            hand_strength=None, hand_total_score=None, hand_control_score=None,
            diagnostics=("synthetic",),
        )
        with mock.patch(
            "evaluation.strategy_intent_action_ablation.route_strategy_intent",
            return_value=unavailable,
        ):
            report = run_strategy_intent_action_ablation(
                (7,),
                suggestion_provider=provider,
                strategic_pass_rates=(0,),
                samples_per_phase=2,
            )
        self.assertEqual(calls, [])
        self.assertGreater(report.policies[0].overall.router_unavailable_skip_count, 0)

    def test_report_is_immutable_json_safe_and_repeatable(self) -> None:
        first = run_strategy_intent_action_ablation(
            (7, 8),
            suggestion_provider=_deterministic_provider,
            strategic_pass_rates=(100, 0, 25),
            samples_per_phase=2,
        )
        second = run_strategy_intent_action_ablation(
            (7, 8),
            suggestion_provider=_deterministic_provider,
            strategic_pass_rates=(100, 0, 25),
            samples_per_phase=2,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            [(policy.policy_name, policy.strategic_pass_rate) for policy in first.policies],
            [("strategic_pass_100", 100), ("forced_only", 0), ("strategic_pass_25", 25)],
        )
        payload = json.dumps(
            first.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        self.assertEqual(
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            hashlib.sha256(
                json.dumps(second.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest(),
        )
        for forbidden in ("seed", "sample_id", "observation", "history", "action_id", "hand_cards", "reasoning"):
            self.assertNotIn(forbidden, payload)
        with self.assertRaises(FrozenInstanceError):
            first.requested_policy_count = 0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            first.policies[0].by_phase["midgame"] = first.policies[0].overall  # type: ignore[index]

    def test_source_has_no_network_configuration_or_runtime_reverse_import(self) -> None:
        source = Path("evaluation/strategy_intent_action_ablation.py").read_text(encoding="utf-8")
        for forbidden in (
            "AppConfig",
            ".env",
            "api_key",
            "ground_truth",
            "game._state",
            "record.txt",
            "suggest_action_id",
            "urlopen",
            "http.client",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        runtime_sources = (
            "agents/deepseek_ai.py",
            "agents/deepseek_client.py",
            "agents/rag_advisor.py",
            "config.py",
        )
        for path in runtime_sources:
            with self.subTest(path=path):
                self.assertNotIn(
                    "strategy_intent_action_ablation",
                    Path(path).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
