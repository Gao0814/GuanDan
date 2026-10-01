"""Shared-world progression and actual model request boundary regressions."""

from collections import Counter
from copy import deepcopy
from time import monotonic
import unittest
from unittest.mock import patch

from agents.bounded_continuation import (analyze_continuations, public_hypotheses,
                                        continuation_action, POLICIES)
from agents.card_belief import build_double_deck_token_pool
from engine.public_simulation import SimulationBudget, rebuild_hypothetical_position
from decision_deadline import DecisionDeadline
from tests.test_m9_public_endgame_opportunities import _rollout_to_step
from tests.test_suit_resource_projection import _capture_default_factory_request


class BoundedContinuationTests(unittest.TestCase):
    def test_common_assignments_conserve_entities_capacities_and_ignore_pass_signals(self):
        game, obs, actions = _rollout_to_step(7, 32)
        original = deepcopy((obs, actions))
        worlds = public_hypotheses(obs, SimulationBudget(monotonic() + 2))
        self.assertEqual(worlds, public_hypotheses(obs, SimulationBudget(monotonic() + 2)))
        counts = {obs['my_info']['player_id']: obs['my_info']['hand_count'],
                  **{p['player_id']: p['hand_count'] for p in obs['other_players']}}
        played = Counter(t for a in obs['history']['actions'] for t in a['carrier_cards'])
        for world in worlds:
            self.assertEqual({p: len(cards) for p, cards in world.items()}, counts)
            self.assertEqual(Counter(t for hand in world.values() for t in hand) + played,
                             Counter(build_double_deck_token_pool()))
            self.assertEqual(Counter(world[obs['my_info']['player_id']]), Counter(obs['my_info']['hand_cards']))
        self.assertEqual((obs, actions), original)
        self.assertNotEqual(continuation_action(obs, actions, POLICIES[0]),
                            continuation_action(obs, actions, POLICIES[1]))
        # Hypotheses do not modify possible/confirmed domains or observations.
        report = analyze_continuations(obs, actions, actions)
        self.assertEqual(report.status, 'ready')
        self.assertEqual(report.steps, report.scenarios * 2 * len(report.root_ids) * report.depth)
        self.assertIn('未终局', report.text)
        self.assertNotIn('confirmed', report.text)

    def test_simulation_matches_independent_engine_and_work_budget_restores_generator(self):
        game, obs, actions = _rollout_to_step(7, 32)
        hands = {p.player_id: tuple((c.rank + (c.suit or '')) for c in p.hand_cards)
                 for p in game._state.players}  # Engine oracle only, never runtime AI.
        budget = SimulationBudget(monotonic() + 2)
        sim = rebuild_hypothetical_position(obs, actions, hands, budget=budget)
        for _ in range(8):
            self.assertEqual(sim.observe(), game.observe())
            self.assertEqual(sim.legal_actions(), game.legal_actions())
            action_id = continuation_action(sim.observe(), sim.legal_actions(), POLICIES[1])
            first, second = sim.step(action_id), game.step(action_id)
            self.assertEqual(first, second)
            if first['game_over']:
                break
        with self.assertRaises(TimeoutError):
            rebuild_hypothetical_position(obs, actions, hands,
                                          budget=SimulationBudget(monotonic() + 2, max_work=1))
        self.assertEqual(_rollout_to_step(7, 32)[2], actions)
        mutated = deepcopy(actions)
        mutated[0]['action_id'] += 1000
        with self.assertRaises(ValueError):
            rebuild_hypothetical_position(obs, mutated, hands, budget=SimulationBudget(monotonic() + 2))
        game, obs, actions = _rollout_to_step(6, 81)
        hands = {p.player_id: tuple(c.rank + (c.suit or '') for c in p.hand_cards) for p in game._state.players}
        sim = rebuild_hypothetical_position(obs, actions, hands, budget=SimulationBudget(monotonic() + 2))
        while True:
            obs = sim.observe()
            action_id = continuation_action(obs, sim.legal_actions(), POLICIES[0])
            first, second = sim.step(action_id), game.step(action_id)
            self.assertEqual(first, second)
            if first['game_over']:
                break
        self.assertEqual(game.observe()['history']['finish_order'], [3, 1])
        self.assertEqual(first['winner'], 'team_13')

    def test_default_factory_request_closes_original_ids_and_model_keeps_other_choice(self):
        game, obs, actions = _rollout_to_step(7, 32)
        _, agent, transport = _capture_default_factory_request(game, actions[0]['action_id'])
        report = agent.client._delegate.last_bounded_continuation
        self.assertEqual(report.status, 'ready')
        self.assertIn(report.text, transport.prompt)
        self.assertLessEqual(len(report.text), 1800)
        self.assertTrue(set(report.root_ids).issubset(transport.candidate_ids))
        self.assertLessEqual(len(transport.candidate_ids), 80)
        alternate = transport.candidate_ids[-1]
        selected, second_agent, second = _capture_default_factory_request(game, alternate)
        self.assertEqual(selected, alternate)
        self.assertEqual(second_agent.last_decision_source, 'model')
        self.assertEqual(second.candidate_ids, transport.candidate_ids)
        self.assertEqual(game.legal_actions(), actions)

    def test_incomplete_and_budgeted_blocks_return_no_partial_comparison(self):
        _, obs, actions = _rollout_to_step(7, 32)
        incomplete = deepcopy(obs)
        incomplete['history']['actions'] = incomplete['history']['actions'][1:]
        self.assertFalse(analyze_continuations(incomplete, actions, actions).text)
        report = analyze_continuations(obs, actions, actions,
                                       decision_deadline=DecisionDeadline(monotonic() + 5))
        self.assertEqual(report.status, 'budget_insufficient')
        self.assertFalse(report.text)
        with patch('agents.bounded_continuation._advance', side_effect=TimeoutError):
            report = analyze_continuations(obs, actions, actions)
        self.assertEqual((report.status, report.text, report.root_ids), ('budget_exhausted', '', ()))
        with patch('agents.bounded_continuation.relevant_public_passes', side_effect=TimeoutError):
            report = analyze_continuations(obs, actions, actions)
        self.assertEqual((report.status, report.text, report.root_ids), ('budget_exhausted', '', ()))


if __name__ == '__main__':
    unittest.main()
