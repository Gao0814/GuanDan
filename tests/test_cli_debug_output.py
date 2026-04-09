"""Tests for human-readable debug output in run_4ai_debug."""

from contextlib import redirect_stdout
import io
import unittest

from agents.rule_based_ai import RuleBasedAIAgent
from cli.run_4ai_debug import _cards_to_cn, _format_play_cn, _print_events_human
from engine.game import FourAIGameRunner, build_initial_state
from engine.logging_utils import DebugLogger
from engine.rules import BaseRuleEngine


def _build_events(step_count: int = 3) -> list[object]:
    logger = DebugLogger()
    runner = FourAIGameRunner(
        rule_engine=BaseRuleEngine(),
        agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
        debug_logger=logger,
        max_steps=12000,
    )
    state = build_initial_state(seed=13)
    for _ in range(step_count):
        state, _ = runner.step(state)
    return logger.events


def _render_human(events: list[object], verbose_debug: bool = False) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        _print_events_human(events, verbose_debug=verbose_debug)
    return buffer.getvalue()


class TestCliDebugOutput(unittest.TestCase):
    def test_default_output_is_concise_replay_friendly(self) -> None:
        output = _render_human(_build_events(step_count=4), verbose_debug=False)

        self.assertIn("发牌完成", output)
        self.assertIn("======第", output)
        self.assertIn("玩家1出牌：", output)
        self.assertIn("玩家1剩余手牌：", output)

        # Default mode should hide verbose internals.
        self.assertNotIn("当前步数：", output)
        self.assertNotIn("当前约束：", output)
        self.assertNotIn("可选动作（共", output)
        self.assertNotIn("已选动作：", output)
        self.assertNotIn("状态变化：", output)
        self.assertNotIn("本轮是否结束：", output)
        self.assertNotIn("对局是否结束：", output)

    def test_verbose_output_contains_detailed_debug_fields(self) -> None:
        output = _render_human(_build_events(step_count=3), verbose_debug=True)

        self.assertIn("当前步数：", output)
        self.assertIn("当前玩家：", output)
        self.assertIn("当前约束：", output)
        self.assertIn("可选动作（共", output)
        self.assertIn("按牌型分组", output)
        self.assertIn("已选动作：", output)
        self.assertIn("状态变化：", output)
        self.assertIn("本轮是否结束：", output)
        self.assertIn("对局是否结束：", output)
        self.assertIn("胜者：", output)

    def test_verbose_legal_actions_grouped_and_truncated(self) -> None:
        output = _render_human(_build_events(step_count=1), verbose_debug=True)

        self.assertIn("可选动作（共", output)
        self.assertIn("按牌型分组", output)
        self.assertIn("省略", output)

    def test_human_readability_shows_jokers_in_chinese(self) -> None:
        cards_text = _cards_to_cn(["AS", "SJ", "BJ"])
        self.assertIn("小王", cards_text)
        self.assertIn("大王", cards_text)

    def test_human_readability_shows_new_pattern_names(self) -> None:
        straight_text = _format_play_cn(
            {
                "action_type": "play",
                "cards": ["3S", "4S", "5S", "6S", "7S"],
                "declared_pattern": "straight",
            }
        )
        pair_straight_text = _format_play_cn(
            {
                "action_type": "play",
                "cards": ["3S", "3H", "4S", "4H", "5S", "5H"],
                "declared_pattern": "pair_straight",
            }
        )
        triple_with_pair_text = _format_play_cn(
            {
                "action_type": "play",
                "cards": ["6S", "6H", "6D", "9S", "9H"],
                "declared_pattern": "triple_with_pair",
            }
        )

        self.assertIn("顺子", straight_text)
        self.assertIn("连对", pair_straight_text)
        self.assertIn("三带二", triple_with_pair_text)
