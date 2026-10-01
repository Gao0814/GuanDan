"""Real complete-deal terminal consumption without invented personal ranks."""

import unittest

from agents.rule_based_ai import FrozenRuleBasedAIAgent, RuleBasedAIAgent
from engine.cards import build_double_deck
from engine.game import GuanDanGame
from evaluation.conditional_pressure_pass import _terminal as pressure_terminal
from evaluation.conditional_pressure_pass_runtime_trial import _normalize_terminal as trial_terminal
from evaluation.terminal import terminal_team_facts


def _finish_game(game, agent_type):
    """A complete public-method replay verifies terminal consumers, not quality."""
    for steps in range(1, 5001):
        observation, legal = game.observe(), game.legal_actions()
        player = observation['my_info']['player_id']
        action = agent_type(player_id=player).select_action(observation, legal)
        result = game.step(action)
        if result['game_over']:
            return result['winner'], steps
    raise AssertionError('fixture_did_not_finish')


class DoubleDownEvaluationTests(unittest.TestCase):
    def test_complete_seed6_rule_rollout_and_rotated_team_views(self) -> None:
        original = GuanDanGame(seed=6)
        original.reset()
        hands = {player.player_id: player.hand_cards for player in original._state.players}
        from collections import Counter
        self.assertEqual(Counter(card for hand in hands.values() for card in hand), Counter(build_double_deck()))
        for offset in (0, 1):
            game = GuanDanGame(preset_hands={((player - 1 + offset) % 4) + 1: hand for player, hand in hands.items()},
                               starting_player_id=1 + offset)
            game.reset()
            winner, steps = _finish_game(game, RuleBasedAIAgent)
            terminal = game.observe()
            expected_order = [((player - 1 + offset) % 4) + 1 for player in (3, 1)]
            self.assertEqual(terminal['history']['finish_order'], expected_order)
            self.assertEqual(steps, 83)
            self.assertEqual(winner, 'team_13' if offset == 0 else 'team_24')
            for observer in (1, 2, 3, 4):
                expected_win = (observer % 2) == ((1 + offset) % 2)
                outcome, score, placement, diagnostic = terminal_team_facts(terminal, winner, observer)
                self.assertIsNone(diagnostic)
                self.assertEqual((outcome, score, placement),
                                 ('win', 2, 3) if expected_win else ('loss', 0, 7))
                self.assertEqual(pressure_terminal(game, winner, observer, 83).team_placement_sum, placement)
            trial = trial_terminal(terminal, winner, 'team_13', 83, ())
            self.assertTrue(trial.complete)
            self.assertEqual(trial.candidate_placement_sum + trial.baseline_placement_sum, 10)
            self.assertEqual(terminal['history']['finish_order'], expected_order)
            for player in terminal['other_players']:
                if player['player_id'] not in expected_order:
                    self.assertIsNone(player['finish_rank'])

        winner, steps = _finish_game(original, FrozenRuleBasedAIAgent)
        self.assertEqual(original.observe()['history']['finish_order'], [2, 4])
        self.assertEqual(terminal_team_facts(original.observe(), winner, 1), ('loss', 0, 7, None))

    def test_invalid_pair_and_inconsistent_winner_fail_closed_and_rule_draw_survives(self) -> None:
        for order, winner in (([1, 2], 'team_13'), ([1, 3], 'draw'), ([2, 4], 'team_13'),
                              ([1, 1], 'team_13'), ([True, 3], 'team_13'), ([1], 'team_13')):
            with self.subTest(order=order, winner=winner):
                self.assertIsNotNone(terminal_team_facts({'history': {'finish_order': order}}, winner, 1)[3])
        terminal = {'history': {'finish_order': [1, 2, 4]}}
        self.assertEqual(terminal_team_facts(terminal, 'draw', 1), ('draw', 1, 5, None))
        self.assertIsNotNone(terminal_team_facts(terminal, 'team_13', 1)[3])
        double_down = {'history': {'finish_order': [1, 3]}}
        self.assertEqual(terminal_team_facts(double_down, 'team_13', 1), ('win', 2, 3, None))
        self.assertEqual(terminal_team_facts(double_down, 'team_13', 2), ('loss', 0, 7, None))
