"""Tests for baseline comparison evaluation framework."""

import json
from unittest.mock import patch
import unittest

from cli.evaluate_baselines import (
    evaluate_humanlikeness_compare,
    evaluate_humanlikeness_fixed_scenarios,
    run_deepseek_call_verification,
    evaluate_modes,
)
from agents.deepseek_client import DeepSeekClient


class TestEvaluationFramework(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patcher = patch.dict(
            "os.environ",
            {
                "DEEPSEEK_ENABLED": "false",
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()

    def test_local_mode_outputs_required_metrics(self) -> None:
        summary = evaluate_modes(
            games=1,
            seed_start=800,
            max_steps=12000,
            modes=("local_rule_based",),
        )

        self.assertIn("local_rule_based", summary)
        local = summary["local_rule_based"]

        required_fields = {
            "total_games",
            "wins",
            "illegal_action_rate",
            "average_steps",
            "deepseek_accepted_count",
            "deepseek_rejected_count",
            "fallback_count",
            "fallback_breakdown",
        }
        self.assertTrue(required_fields.issubset(local.keys()))
        self.assertEqual(local["total_games"], 1)
        self.assertGreaterEqual(local["average_steps"], 1)
        self.assertGreaterEqual(local["illegal_action_rate"], 0.0)

    def test_deepseek_rag_mode_collects_accept_reject_and_fallback_counts(self) -> None:
        class CycleAdvisor:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action(self, state, legal_actions, context):
                self.calls += 1
                mode = self.calls % 4
                if mode == 1:
                    first = legal_actions[0]
                    return {
                        "action_type": first.action_type.value,
                        "declared_pattern": first.declared_pattern.value if first.declared_pattern else None,
                        "cards": [f"{card.rank}{card.suit or ''}" for card in first.cards],
                    }
                if mode == 2:
                    return {
                        "action_type": "play",
                        "declared_pattern": "single",
                        "cards": ["ZZ"],
                    }
                if mode == 3:
                    return None
                raise TimeoutError("simulated timeout")

        def advisor_factory(_player_id: int):
            return CycleAdvisor()

        summary = evaluate_modes(
            games=1,
            seed_start=900,
            max_steps=12000,
            modes=("deepseek_rag_baseline",),
            deepseek_advisor_factory=advisor_factory,
        )

        self.assertIn("deepseek_rag_baseline", summary)
        deepseek = summary["deepseek_rag_baseline"]

        self.assertEqual(deepseek["total_games"], 1)
        self.assertGreaterEqual(deepseek["deepseek_accepted_count"], 1)
        self.assertGreaterEqual(deepseek["deepseek_rejected_count"], 1)
        self.assertGreaterEqual(deepseek["fallback_count"], 1)
        self.assertGreaterEqual(deepseek["illegal_action_rate"], 0.0)

        fallback_breakdown = deepseek["fallback_breakdown"]
        self.assertIn("empty_response_fallback", fallback_breakdown)
        self.assertIn("fallback_error", fallback_breakdown)
        self.assertIn("rejected_degradation_fallback", fallback_breakdown)

    def test_compare_two_modes_produces_side_by_side_summary(self) -> None:
        summary = evaluate_modes(
            games=1,
            seed_start=950,
            max_steps=12000,
            modes=("local_rule_based", "deepseek_rag_baseline"),
            deepseek_advisor_factory=lambda _pid: None,
        )

        self.assertIn("local_rule_based", summary)
        self.assertIn("deepseek_rag_baseline", summary)

        local = summary["local_rule_based"]
        deepseek = summary["deepseek_rag_baseline"]
        self.assertEqual(local["total_games"], deepseek["total_games"])
        self.assertEqual(sum(local["wins"].values()), local["total_games"])
        self.assertEqual(sum(deepseek["wins"].values()), deepseek["total_games"])

    def test_humanlikeness_fixed_scenarios_have_required_structure(self) -> None:
        summary = evaluate_humanlikeness_fixed_scenarios(mode="local_rule_based")

        self.assertEqual(summary["mode"], "local_rule_based")
        self.assertGreaterEqual(summary["total_scenarios"], 6)
        self.assertIn("overall_better_hit_rate", summary)
        self.assertIn("overall_worse_hit_rate", summary)
        self.assertIn("all_in_better_set_scenarios", summary)
        self.assertIn("stable_scenarios", summary)
        self.assertIn("scenarios", summary)

        scenario_names = set(summary["scenarios"].keys())
        required = {
            "prefer_straight_over_scattered_singles",
            "prefer_pair_straight_over_split_pairs",
            "prefer_triple_with_pair_over_plain_triple",
            "avoid_unnecessary_bomb_when_safe_alternatives_exist",
            "endgame_follow_prefers_lower_cost_control",
            "fixed_state_stability_or_reasonable_set",
        }
        self.assertTrue(required.issubset(scenario_names))

    def test_humanlikeness_local_mode_baseline_is_stable_or_in_better_set(self) -> None:
        summary = evaluate_humanlikeness_fixed_scenarios(mode="local_rule_based")

        # 每个固定场景应满足“稳定”或“始终命中更合理集合”。
        for result in summary["scenarios"].values():
            self.assertTrue(
                result["stable_output"] or result["all_in_better_set"],
            )

    def test_humanlikeness_compare_can_show_deepseek_rag_improvement_on_targeted_cases(self) -> None:
        class HumanLikeAdvisor:
            def suggest_action(self, state, legal_actions, context, rag_context=None):
                # 在固定场景中优先建议复合牌型与非炸弹动作。
                def pick(pattern: str):
                    for action in legal_actions:
                        if action.declared_pattern and action.declared_pattern.value == pattern:
                            return {
                                "action_type": action.action_type.value,
                                "declared_pattern": action.declared_pattern.value,
                                "cards": [f"{card.rank}{card.suit or ''}" for card in action.cards],
                            }
                    return None

                for target in ("straight", "pair_straight", "triple_with_pair"):
                    found = pick(target)
                    if found is not None:
                        return found

                # 避免无意义炸弹：优先非炸弹中最前项。
                for action in legal_actions:
                    if action.declared_pattern is not None and action.declared_pattern.value != "bomb":
                        return {
                            "action_type": action.action_type.value,
                            "declared_pattern": action.declared_pattern.value,
                            "cards": [f"{card.rank}{card.suit or ''}" for card in action.cards],
                        }
                return None

        results = evaluate_humanlikeness_compare(
            deepseek_advisor_factory=lambda _pid: HumanLikeAdvisor(),
        )

        local = results["local_rule_based"]
        deepseek = results["deepseek_rag_baseline"]

        self.assertGreaterEqual(
            deepseek["overall_better_hit_rate"],
            local["overall_better_hit_rate"],
        )
        self.assertLessEqual(
            deepseek["overall_worse_hit_rate"],
            local["overall_worse_hit_rate"],
        )

    def test_humanlikeness_compare_reports_rule_gap_candidates(self) -> None:
        results = evaluate_humanlikeness_compare(
            deepseek_advisor_factory=lambda _pid: None,
        )
        self.assertIn("rule_gap_likely_scenarios", results["local_rule_based"])
        self.assertIn("rule_gap_likely_scenarios", results["deepseek_rag_baseline"])

    def test_verify_deepseek_call_without_key_reports_fallback_block_reason(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_ENABLED": "false",
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=False,
        ):
            result = run_deepseek_call_verification(
                games=1,
                seed_start=1234,
                max_steps=200,
                deepseek_advisor_factory=None,
            )

        self.assertEqual(result["mode"], "deepseek_rag_baseline")
        self.assertTrue(result["deepseek_enabled_requested"])
        self.assertFalse(result["has_api_key"])
        self.assertEqual(result["deepseek_client_created_count"], 0)
        self.assertEqual(result["suggest_action_calls"], 0)
        self.assertEqual(result["transport_calls"], 0)
        self.assertIn("missing_api_key", result["blocked_reasons"])
        self.assertGreater(result["model_status_counts"].get("enabled_without_adapter_fallback", 0), 0)

    def test_verify_deepseek_call_with_client_hits_suggest_and_transport(self) -> None:
        transport_calls = {"count": 0}

        def fake_transport(request, timeout: float) -> str:
            transport_calls["count"] += 1
            return json.dumps({"choices": [{"message": {"content": ""}}]})

        def advisor_factory(_player_id: int):
            return DeepSeekClient(
                api_key="dummy-key",
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                transport=fake_transport,
            )

        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_ENABLED": "true",
                "DEEPSEEK_API_KEY": "dummy-key",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL": "deepseek-chat",
            },
            clear=False,
        ):
            result = run_deepseek_call_verification(
                games=1,
                seed_start=1235,
                max_steps=200,
                deepseek_advisor_factory=advisor_factory,
            )

        self.assertTrue(result["has_api_key"])
        self.assertGreater(result["deepseek_client_created_count"], 0)
        self.assertGreater(result["suggest_action_calls"], 0)
        self.assertGreater(result["transport_calls"], 0)
        self.assertEqual(transport_calls["count"], result["transport_calls"])
        self.assertGreater(result["model_status_counts"].get("empty_response_fallback", 0), 0)
