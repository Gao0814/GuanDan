"""Step-5 integration tests for four-AI auto-play game flow."""

import unittest

from agents.rule_based_ai import RuleBasedAIAgent
from engine.actions import Action, ActionType
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK
from engine.game import FourAIGameRunner, build_initial_state
from engine.logging_utils import DebugLogger
from engine.patterns import PatternType
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


def _build_runner_with_agents(
    agents: tuple[RuleBasedAIAgent, RuleBasedAIAgent, RuleBasedAIAgent, RuleBasedAIAgent],
    max_steps: int = 5000,
) -> tuple[FourAIGameRunner, DebugLogger]:
    logger = DebugLogger()
    runner = FourAIGameRunner(
        rule_engine=BaseRuleEngine(),
        agents=agents,
        debug_logger=logger,
        max_steps=max_steps,
    )
    return runner, logger


class TestGameFlow(unittest.TestCase):
    def test_u11_initial_deal_total_cards_108_and_each_player_27(self) -> None:
        state = build_initial_state(seed=23)

        hand_sizes = [len(player.hand_cards) for player in state.players]
        self.assertEqual(sum(hand_sizes), 108)
        self.assertEqual(hand_sizes, [27, 27, 27, 27])

    def test_u11_initial_deal_contains_all_four_jokers(self) -> None:
        state = build_initial_state(seed=31)

        all_ranks = [card.rank for player in state.players for card in player.hand_cards]
        self.assertEqual(all_ranks.count(SMALL_JOKER_RANK), 2)
        self.assertEqual(all_ranks.count(BIG_JOKER_RANK), 2)

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

    def test_i2_multi_game_illegal_action_rate_zero(self) -> None:
        for seed in range(1, 11):
            runner, logger = _build_runner(max_steps=12000)
            _ = runner.run_one_game(build_initial_state(seed=seed))

            step_events = [event for event in logger.events if event.event_type == "step"]
            self.assertGreater(len(step_events), 0)

            # chosen_action must always come from legal_actions.
            for event in step_events:
                payload = event.payload
                self.assertIn(payload.get("chosen_action"), payload.get("legal_actions", []))

    def test_i4_multi_game_stability_with_new_patterns_and_jokers(self) -> None:
        for seed in range(20, 30):
            runner, logger = _build_runner(max_steps=12000)
            final_state = runner.run_one_game(build_initial_state(seed=seed))

            self.assertTrue(final_state.is_finished)
            self.assertIsNotNone(final_state.winner_player_id)
            self.assertLessEqual(final_state.step_no, 12000)
            self.assertGreater(len(logger.events), 0)

    def test_i5_api_not_enabled_mainline_still_stable(self) -> None:
        class CountingAdvisor:
            def __init__(self) -> None:
                self.calls = 0

            def suggest_action(self, state, legal_actions, context):
                self.calls += 1
                return legal_actions[-1] if legal_actions else None

        advisors = [CountingAdvisor() for _ in range(4)]
        agents = tuple(
            RuleBasedAIAgent(
                player_id=i,
                name=f"ai-{i}",
                deepseek_enabled=False,
                deepseek_action_advisor=advisors[i],
            )
            for i in range(4)
        )
        runner, logger = _build_runner_with_agents(agents=agents, max_steps=12000)

        final_state = runner.run_one_game(build_initial_state(seed=202))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)
        self.assertGreater(len(logger.events), 0)

        # API disabled: should remain on local heuristic chain and never call advisor.
        self.assertTrue(all(advisor.calls == 0 for advisor in advisors))
        for agent in agents:
            self.assertIsNotNone(agent.last_decision_record)
            assert agent.last_decision_record is not None
            model_meta = agent.last_decision_record.metadata.get("model")
            self.assertIsInstance(model_meta, dict)
            assert isinstance(model_meta, dict)
            self.assertEqual(model_meta.get("status"), "disabled")

    def test_r8_api_failure_fallback_still_finishes_and_illegal_rate_zero(self) -> None:
        class FailingAdvisor:
            def __init__(self, mode: str) -> None:
                self.mode = mode

            def suggest_action(self, state, legal_actions, context):
                if self.mode == "timeout":
                    raise TimeoutError("simulated timeout")
                if self.mode == "error":
                    raise RuntimeError("simulated api error")
                if self.mode == "empty":
                    return None
                raise ValueError("unsupported mode")

        for mode in ("timeout", "error", "empty"):
            with self.subTest(mode=mode):
                agents = tuple(
                    RuleBasedAIAgent(
                        player_id=i,
                        name=f"ai-{i}",
                        deepseek_enabled=True,
                        deepseek_action_advisor=FailingAdvisor(mode=mode),
                    )
                    for i in range(4)
                )
                runner, logger = _build_runner_with_agents(agents=agents, max_steps=12000)
                final_state = runner.run_one_game(build_initial_state(seed=300 + len(mode)))

                self.assertTrue(final_state.is_finished)
                self.assertIsNotNone(final_state.winner_player_id)

                step_events = [event for event in logger.events if event.event_type == "step"]
                self.assertGreater(len(step_events), 0)
                for event in step_events:
                    payload = event.payload
                    self.assertIn(payload.get("chosen_action"), payload.get("legal_actions", []))

                for agent in agents:
                    self.assertIsNotNone(agent.last_decision_record)
                    assert agent.last_decision_record is not None
                    model_meta = agent.last_decision_record.metadata.get("model")
                    self.assertIsInstance(model_meta, dict)
                    assert isinstance(model_meta, dict)
                    if mode in {"timeout", "error"}:
                        self.assertEqual(model_meta.get("status"), "fallback_error")
                    else:
                        self.assertEqual(model_meta.get("status"), "empty_response_fallback")

    def test_r1_legal_actions_are_state_machine_acceptable_through_game(self) -> None:
        runner, _ = _build_runner(max_steps=12000)
        state = build_initial_state(seed=41)

        while not state.is_finished:
            legal_actions = runner.rule_engine.generate_legal_actions(state)
            self.assertGreater(len(legal_actions), 0)
            for action in legal_actions:
                runner.rule_engine.validate_action(state, action)
            state, _ = runner.step(state)

    def test_r2_illegal_action_rejected_without_state_pollution(self) -> None:
        engine = BaseRuleEngine()
        state = build_initial_state(seed=99)
        player = state.get_player(state.current_player_id)

        # Force an illegal action by declaring wrong pattern for a single card.
        illegal_action = Action(
            player_id=state.current_player_id,
            action_type=ActionType.PLAY,
            cards=(player.hand_cards[0],),
            declared_pattern=PatternType.PAIR,
        )

        before_hands = tuple(tuple(p.hand_cards) for p in state.players)
        before_step = state.step_no

        with self.assertRaises(ValueError):
            engine.apply_action(state, illegal_action)

        after_hands = tuple(tuple(p.hand_cards) for p in state.players)
        self.assertEqual(before_hands, after_hands)
        self.assertEqual(before_step, state.step_no)

    def test_r4_logs_are_sufficient_for_step_replay_checks(self) -> None:
        runner, logger = _build_runner(max_steps=12000)
        _ = runner.run_one_game(build_initial_state(seed=17))

        step_events = [event for event in logger.events if event.event_type == "step"]
        self.assertGreater(len(step_events), 0)

        for event in step_events:
            payload = event.payload
            self.assertIn("legal_actions", payload)
            self.assertIn("chosen_action", payload)
            self.assertIn("state_before", payload)
            self.assertIn("state_after", payload)
            self.assertIn("all_hands", payload)
            self.assertIn("all_hands_after", payload)
            self.assertTrue(len(payload["legal_actions"]) > 0)

    def test_i4_state_consistency_no_pollution_in_logged_snapshots(self) -> None:
        runner, logger = _build_runner(max_steps=12000)
        _ = runner.run_one_game(build_initial_state(seed=29))

        for event in logger.events:
            if event.event_type != "step":
                continue
            payload = event.payload
            all_hands = payload["all_hands"]
            all_hands_after = payload["all_hands_after"]
            chosen = payload["chosen_action"]

            before_counts = {pid: len(cards) for pid, cards in all_hands.items()}
            after_counts = {pid: len(cards) for pid, cards in all_hands_after.items()}

            current_player = chosen["player_id"]
            action_type = chosen["action_type"]
            played_cards_count = len(chosen.get("cards", []))

            if action_type == "pass":
                self.assertEqual(before_counts, after_counts)
            else:
                for pid in before_counts:
                    if pid == current_player:
                        self.assertEqual(
                            after_counts[pid],
                            before_counts[pid] - played_cards_count,
                        )
                    else:
                        self.assertEqual(after_counts[pid], before_counts[pid])

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
