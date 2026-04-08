"""Step-5 integration tests for four-AI auto-play game flow."""

import unittest

from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import FourAIGameRunner, build_initial_state
from engine.logging_utils import DebugLogger
from engine.rules import BaseRuleEngine


def _build_runner(max_steps: int = 5000) -> tuple[FourAIGameRunner, DebugLogger]:
    logger = DebugLogger()
    runner = FourAIGameRunner(
        rule_engine=BaseRuleEngine(),
        agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
        debug_logger=logger,
        max_steps=max_steps,
    )
    return runner, logger


class TestGameFlow(unittest.TestCase):
    def test_i1_four_ai_full_game_finishes(self) -> None:
        runner, logger = _build_runner(max_steps=12000)
        final_state = runner.run_one_game(build_initial_state(seed=7))

        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)
        self.assertGreater(len(logger.events), 0)

    def test_i2_multi_game_stability_no_dead_loop(self) -> None:
        for seed in (1, 2, 3):
            runner, _ = _build_runner(max_steps=12000)
            final_state = runner.run_one_game(build_initial_state(seed=seed))
            self.assertTrue(final_state.is_finished)
            self.assertLessEqual(final_state.step_no, 12000)

    def test_i3_debug_output_contains_required_fields(self) -> None:
        runner, logger = _build_runner(max_steps=12000)
        _ = runner.run_one_game(build_initial_state(seed=11))

        self.assertGreater(len(logger.events), 0)
        payload = logger.events[0].payload

        required_fields = {
            "step_id",
            "current_player_id",
            "all_hands",
            "table_constraint",
            "legal_actions",
            "chosen_action",
            "decision_basis",
            "state_before",
            "state_after",
            "remaining_hand_counts",
            "round_ended",
            "game_over",
            "winner",
        }
        self.assertTrue(required_fields.issubset(payload.keys()))

        before = payload["state_before"]
        after = payload["state_after"]
        for snapshot in (before, after):
            self.assertIn("current_player_id", snapshot)
            self.assertIn("table_constraint", snapshot)
            self.assertIn("remaining_hand_counts", snapshot)
            self.assertIn("recent_success_player", snapshot)
            self.assertIn("phase", snapshot)
