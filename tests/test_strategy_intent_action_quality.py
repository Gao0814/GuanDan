"""Contract tests for the aggregate-only strategy-intent rollout proxy."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

from agents.deepseek_client import DeepSeekSuggestion
from engine.game import GuanDanGame
from evaluation.strategy_intent_action_ablation import run_strategy_intent_action_ablation
from evaluation.strategy_intent_action_quality import (
    RuleRolloutOutcome,
    _compare_quality,
    _normalize_terminal,
    _rollout,
    run_strategy_intent_action_quality,
)


def _provider(**kwargs: object) -> DeepSeekSuggestion:
    actions = kwargs["prompt_actions"]
    assert isinstance(actions, list)
    index = -1 if "strategy_intent_prompt" in kwargs else 0
    return DeepSeekSuggestion(action_id=actions[index]["action_id"], reasoning=None)


def _same_provider(**kwargs: object) -> DeepSeekSuggestion:
    actions = kwargs["prompt_actions"]
    assert isinstance(actions, list)
    return DeepSeekSuggestion(action_id=actions[0]["action_id"], reasoning=None)


class StrategyIntentActionQualityTests(unittest.TestCase):
    def test_strict_rollout_limit_validation(self) -> None:
        for bad in (True, False, 0, -1, 1.5, "5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    run_strategy_intent_action_quality((1,), suggestion_provider=_provider, max_rollout_steps=bad)  # type: ignore[arg-type]

    def test_deepcopy_is_publicly_equivalent_and_independent(self) -> None:
        game = GuanDanGame(seed=500, current_level_rank="2")
        game.reset()
        clone = copy.deepcopy(game)
        self.assertEqual(game.observe(), clone.observe())
        self.assertEqual(game.legal_actions(), clone.legal_actions())
        action = clone.legal_actions()[0]["action_id"]
        clone.step(action)
        self.assertNotEqual(game.observe(), clone.observe())

    def test_terminal_normalization_and_quality_dictionary_order(self) -> None:
        terminal = {"history": {"finish_order": [1, 2, 3]}}
        outcome = _normalize_terminal(terminal, "team_13", 1, 7)
        self.assertTrue(outcome.complete)
        self.assertEqual((outcome.team_outcome, outcome.team_placement_sum), ("win", 4))
        self.assertFalse(_normalize_terminal({"history": {"finish_order": [1, 1, 2]}}, "team_13", 1, 1).complete)
        self.assertFalse(_normalize_terminal(terminal, "invalid", 1, 1).complete)
        off = RuleRolloutOutcome("draw", 1, 3, 1, True, ())
        on = RuleRolloutOutcome("draw", 1, 4, 999, True, ())
        self.assertEqual(_compare_quality(off, on), "off_better")
        self.assertEqual(_compare_quality(off, RuleRolloutOutcome("win", 2, 8, 2, True, ())), "on_better")
        self.assertEqual(_compare_quality(off, RuleRolloutOutcome("draw", 1, 3, 200, True, ())), "tie")

    def test_same_action_rollout_is_one_complete_branch(self) -> None:
        game = GuanDanGame(seed=501, current_level_rank="2")
        game.reset()
        observation = game.observe()
        player = observation["my_info"]["player_id"]
        outcome = _rollout(copy.deepcopy(game), game.legal_actions()[0]["action_id"], player, 5000)
        self.assertTrue(outcome.complete)
        self.assertGreaterEqual(outcome.rollout_step_count, 1)
        limited = _rollout(copy.deepcopy(game), game.legal_actions()[0]["action_id"], player, 1)
        self.assertFalse(limited.complete)
        self.assertEqual(limited.diagnostics, ("rollout_step_limit_reached",))

    def test_same_action_pair_reuses_one_branch_with_symmetric_outcomes(self) -> None:
        report = run_strategy_intent_action_quality((500, 501), suggestion_provider=_same_provider, samples_per_phase=2)
        for policy in report.policies:
            overall = policy.overall
            self.assertEqual(overall.same_action_count, overall.both_valid_pair_count)
            self.assertEqual(overall.same_action_reused_rollout_count, overall.same_action_count)
            self.assertEqual(overall.rollout_branch_attempted_count, overall.same_action_count)
            self.assertEqual(overall.rollout_branch_completed_count, overall.rollout_branch_attempted_count)
            self.assertEqual(overall.off_win_count, overall.on_win_count)
            self.assertEqual(overall.off_draw_count, overall.on_draw_count)
            self.assertEqual(overall.off_loss_count, overall.on_loss_count)

    def test_real_collection_is_deterministic_and_compatible_with_ablation(self) -> None:
        kwargs = dict(suggestion_provider=_provider, samples_per_phase=2, max_steps=5000, max_samples_per_phase_per_game=128, max_rollout_steps=5000)
        first = run_strategy_intent_action_quality((500, 501), **kwargs)
        second = run_strategy_intent_action_quality((500, 501), **kwargs)
        payload = json.dumps(first.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(first, second)
        self.assertEqual(payload, json.dumps(second.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
        self.assertEqual(len(hashlib.sha256(payload.encode()).hexdigest()), 64)
        baseline = run_strategy_intent_action_ablation((500, 501), suggestion_provider=_provider, samples_per_phase=2)
        for prior, current in zip(baseline.policies, first.policies):
            for phase in ("midgame", "endgame", "near_open_endgame", "critical_endgame"):
                before, after = prior.by_phase[phase], current.by_phase[phase]
                self.assertEqual(before.selected_sample_count, after.selected_sample_count)
                self.assertEqual(before.prompt_pair_sha256, after.prompt_pair_sha256)
                self.assertEqual(before.off_first_pair_count, after.off_first_pair_count)
                self.assertEqual(before.on_first_pair_count, after.on_first_pair_count)
            self.assertEqual(current.overall.rollout_branch_attempted_count, current.overall.rollout_branch_completed_count)
            self.assertEqual(current.overall.quality_evaluable_pair_count, current.overall.both_valid_pair_count)
            self.assertEqual(current.overall.on_better_count + current.overall.off_better_count + current.overall.tie_count, current.overall.quality_evaluable_pair_count)
        with self.assertRaises(TypeError):
            first.policies[0].by_phase["midgame"] = first.policies[0].overall  # type: ignore[index]

    def test_source_boundary(self) -> None:
        source = Path("evaluation/strategy_intent_action_quality.py").read_text(encoding="utf-8")
        for forbidden in ("game._" + "state", "ground_" + "truth", "AppConfig", ".env", "api_key", "record.txt", "urlopen"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("strategy_intent_action_quality", Path("agents/deepseek_ai.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
