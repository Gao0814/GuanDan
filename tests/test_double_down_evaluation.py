"""Real complete-deal terminal consumption without invented personal ranks."""

from copy import deepcopy
import unittest

from agents.game_phase import classify_game_phase
from agents.rule_based_ai import FrozenRuleBasedAIAgent, RuleBasedAIAgent
from engine.cards import build_double_deck
from engine.game import GuanDanGame
from evaluation.action_quality_proxy import ReplayableQualitySample, _branch_quality
from evaluation.action_quality_calibration import calibrate_sample_candidates, CalibrationStatus, _valid_rollout_outcome
from evaluation.action_quality_sensitivity import _frozen_rollout
from evaluation.confidence_action_quality import _normalize_terminal as confidence_terminal
from evaluation.conditional_pressure_pass import _terminal as pressure_terminal
from evaluation.conditional_pressure_pass_runtime_trial import _normalize_terminal as trial_terminal
from evaluation.strategy_intent_action_quality import _normalize_terminal, _compare_quality, _rollout


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
            observation = game.observe()
            first = RuleBasedAIAgent(player_id=1 + offset).select_action(observation, game.legal_actions())
            outcome = _rollout(game, first, 1 + offset, 5000)
            terminal = game.observe()
            expected_order = [((player - 1 + offset) % 4) + 1 for player in (3, 1)]
            self.assertEqual(terminal['history']['finish_order'], expected_order)
            self.assertEqual(outcome.rollout_step_count, 83)
            winner = 'team_13' if offset == 0 else 'team_24'
            for observer in (1, 2, 3, 4):
                expected_win = (observer % 2) == ((1 + offset) % 2)
                result = _normalize_terminal(terminal, winner, observer, 83)
                self.assertTrue(result.complete)
                self.assertEqual((result.team_outcome, result.team_placement_sum),
                                 ('win', 3) if expected_win else ('loss', 7))
                self.assertIsNone(_valid_rollout_outcome(result))
                branch = _branch_quality(result)
                self.assertEqual(branch.team_rank_sum, result.team_placement_sum)
                self.assertEqual(confidence_terminal(terminal, winner, observer, 83).to_dict(), result.to_dict())
                self.assertEqual(pressure_terminal(game, winner, observer, 83).team_placement_sum, result.team_placement_sum)
            trial = trial_terminal(terminal, winner, 'team_13', 83, ())
            self.assertTrue(trial.complete)
            self.assertEqual(trial.candidate_placement_sum + trial.baseline_placement_sum, 10)
            self.assertEqual(terminal['history']['finish_order'], expected_order)
            for player in terminal['other_players']:
                if player['player_id'] not in expected_order:
                    self.assertIsNone(player['finish_rank'])

        frozen = deepcopy(original)
        first = FrozenRuleBasedAIAgent(player_id=1).select_action(frozen.observe(), frozen.legal_actions())
        outcome, _ = _frozen_rollout(frozen, first, 1)
        self.assertTrue(outcome.complete)
        self.assertEqual(frozen.observe()['history']['finish_order'], [2, 4])
        self.assertEqual((outcome.team_outcome, outcome.team_placement_sum), ('loss', 7))

    def test_real_seed6_late_state_candidate_calibration_completes(self) -> None:
        game = GuanDanGame(seed=6)
        game.reset()
        sample_game = None
        for _ in range(100):
            observation, legal = game.observe(), game.legal_actions()
            player = observation['my_info']['player_id']
            if observation['current_round']['step_no'] >= 60 and len(legal) >= 2:
                sample_game = deepcopy(game)
            action = RuleBasedAIAgent(player_id=player).select_action(observation, legal)
            if game.step(action)['game_over']:
                break
        self.assertIsNotNone(sample_game)
        observation, legal = sample_game.observe(), sample_game.legal_actions()
        player = observation['my_info']['player_id']
        reference = RuleBasedAIAgent(player_id=player).select_action(observation, legal)
        branch = deepcopy(sample_game)
        self.assertTrue(_rollout(branch, reference, player, 5000).complete)
        self.assertEqual(len(branch.observe()['history']['finish_order']), 2)
        ids = tuple(dict.fromkeys([reference, *(action['action_id'] for action in legal)]))
        sample = ReplayableQualitySample('seed6-late', classify_game_phase(observation).phase,
                                        len(legal), len(ids), observation, legal, sample_game,
                                        source_seed=6, final_candidate_ids=ids)
        result = calibrate_sample_candidates(sample)
        self.assertEqual(result.status, CalibrationStatus.READY)
        self.assertEqual(result.completed_candidate_count, len(ids))
        self.assertEqual(result.better_than_reference + result.tie_with_reference + result.worse_than_reference, len(ids))

    def test_invalid_pair_and_inconsistent_winner_fail_closed_and_rule_draw_survives(self) -> None:
        for order, winner in (([1, 2], 'team_13'), ([1, 3], 'draw'), ([2, 4], 'team_13'),
                              ([1, 1], 'team_13'), ([True, 3], 'team_13'), ([1], 'team_13')):
            with self.subTest(order=order, winner=winner):
                self.assertFalse(_normalize_terminal({'history': {'finish_order': order}}, winner, 1, 1).complete)
        terminal = {'history': {'finish_order': [1, 2, 4]}}
        draw = _normalize_terminal(terminal, 'draw', 1, 90)
        self.assertEqual((draw.complete, draw.team_outcome, draw.team_placement_sum), (True, 'draw', 5))
        self.assertFalse(_normalize_terminal(terminal, 'team_13', 1, 90).complete)
        win = _normalize_terminal({'history': {'finish_order': [1, 3]}}, 'team_13', 1, 1)
        loss = _normalize_terminal({'history': {'finish_order': [1, 3]}}, 'team_13', 2, 1)
        self.assertEqual(_compare_quality(loss, win), 'on_better')
        self.assertEqual(_compare_quality(win, win), 'tie')
