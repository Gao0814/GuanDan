from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from agents.deepseek_client import DeepSeekSuggestion
from engine.game import GuanDanGame
from evaluation.confidence_action_quality import (
    ActionQualityBucket, ConfidenceActionQualityReport, RuleRolloutOutcome,
    _compare, _normalize_terminal, _rollout, run_confidence_action_quality,
)


class Provider:
    def __call__(self, **kwargs: object) -> DeepSeekSuggestion:
        actions = kwargs["prompt_actions"]
        action = actions[-1] if "card_confidence_prompt" in kwargs else actions[0]  # type: ignore[index]
        return DeepSeekSuggestion(action_id=action["action_id"], reasoning=None)  # type: ignore[index]


class SameProvider:
    def __call__(self, **kwargs: object) -> DeepSeekSuggestion:
        return DeepSeekSuggestion(action_id=kwargs["prompt_actions"][0]["action_id"], reasoning=None)  # type: ignore[index]


class QualityHarnessTests(unittest.TestCase):
    def test_strict_validation_and_clone_public_independence(self) -> None:
        provider = Provider()
        with self.assertRaises(ValueError):
            run_confidence_action_quality((140,), suggestion_provider=provider, max_rollout_steps=True)
        with self.assertRaises(ValueError):
            run_confidence_action_quality((140,), suggestion_provider=provider, max_rollout_steps=0)
        game = GuanDanGame(seed=140, current_level_rank="2"); game.reset(); clone = copy.deepcopy(game)
        self.assertEqual(game.observe(), clone.observe()); self.assertEqual(game.legal_actions(), clone.legal_actions())
        action = clone.legal_actions()[0]["action_id"]; clone.step(action)
        self.assertNotEqual(game.observe(), clone.observe())

    def test_terminal_normalization_and_lexicographic_comparison(self) -> None:
        observation = {"history": {"finish_order": [1, 2, 3]}}
        outcome = _normalize_terminal(observation, "team_13", 1, 9)
        self.assertTrue(outcome.complete); self.assertEqual((outcome.team_outcome, outcome.team_outcome_score, outcome.team_placement_sum), ("win", 2, 4))
        self.assertFalse(_normalize_terminal({"history": {"finish_order": [1, 1, 2]}}, "team_13", 1, 1).complete)
        self.assertFalse(_normalize_terminal(observation, "bad", 1, 1).complete)
        off = RuleRolloutOutcome("win", 2, 5, 1, True, ())
        on = RuleRolloutOutcome("loss", 0, 2, 99, True, ())
        self.assertEqual(_compare(off, on), "off_better")
        self.assertEqual(_compare(RuleRolloutOutcome("draw", 1, 6, 1, True, ()), RuleRolloutOutcome("draw", 1, 4, 999, True, ())), "on_better")
        self.assertEqual(_compare(off, RuleRolloutOutcome("win", 2, 5, 999, True, ())), "tie")

    def test_small_deterministic_quality_run_and_safe_report(self) -> None:
        kwargs = dict(suggestion_provider=Provider(), strategic_pass_rates=(0, 100), samples_per_bucket=1, max_rollout_steps=5000)
        first = run_confidence_action_quality((140,), **kwargs)
        second = run_confidence_action_quality((140,), suggestion_provider=Provider(), strategic_pass_rates=(0, 100), samples_per_bucket=1, max_rollout_steps=5000)
        self.assertEqual(first, second)
        for policy in first.by_policy.values():
            overall = policy.overall
            self.assertEqual(overall.same_action_count + overall.changed_action_count, overall.both_valid_pair_count)
            self.assertEqual(overall.quality_evaluable_pair_count + overall.quality_unevaluable_pair_count, overall.both_valid_pair_count)
            self.assertEqual(overall.on_better_count + overall.off_better_count + overall.tie_count, overall.quality_evaluable_pair_count)
            self.assertEqual(overall.rollout_branch_completed_count + overall.rollout_branch_failed_count, overall.rollout_branch_attempted_count)
        text = json.dumps(first.to_dict(), allow_nan=False)
        for forbidden in ("seed", "observation", "history", "action_id", "prompt", "hand", "reasoning"):
            self.assertNotIn(f'"{forbidden}"', text)
        with self.assertRaises(FrozenInstanceError): first.requested_policy_count = 9  # type: ignore[misc]
        with self.assertRaises(TypeError): first.by_policy["x"] = next(iter(first.by_policy.values()))  # type: ignore[index]

    def test_rollout_limit_and_source_boundary(self) -> None:
        game = GuanDanGame(seed=141, current_level_rank="2"); game.reset()
        self.assertFalse(_rollout(copy.deepcopy(game), game.legal_actions()[0]["action_id"], 1, 1).complete)
        source = Path("evaluation/confidence_action_quality.py").read_text(encoding="utf-8")
        for forbidden in ("game._state", "ground_truth", "AppConfig", ".env", "api_key", "urlopen"):
            self.assertNotIn(forbidden, source)

    def test_same_action_reuses_one_rollout(self) -> None:
        report = run_confidence_action_quality(
            (142,), suggestion_provider=SameProvider(), strategic_pass_rates=(0,),
            samples_per_bucket=1, max_rollout_steps=5000,
        ).by_policy["forced_only"]
        overall = report.overall
        self.assertEqual(overall.same_action_count, overall.both_valid_pair_count)
        self.assertEqual(overall.same_action_reused_rollout_count, overall.both_valid_pair_count)
        self.assertEqual(overall.rollout_branch_attempted_count, overall.both_valid_pair_count)


if __name__ == "__main__": unittest.main()
