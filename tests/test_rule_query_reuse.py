"""Rule query equivalence and request-local resource reuse regressions."""

from collections import Counter
from copy import deepcopy
from itertools import combinations
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient, _ProjectedPromptAction
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.game import GuanDanGame
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from tests.test_suit_resource_projection import _complete_game, _capture_default_factory_request


class RuleQueryReuseTests(unittest.TestCase):
    def test_resource_profile_representatives_preserve_brute_pair_choice(self) -> None:
        # Independent exhaustive pair oracle: repeated carriers, reversed IDs,
        # score ties and natural/declared level use all affect the chosen pair.
        actions = []
        for base in range(8):
            for index in range(24):
                profile = ((('route', index % 3),), (), index % 2, 2 - index % 2)
                actions.append(_ProjectedPromptAction(
                    {'action_id': 1000 - len(actions), 'wildcard_count': index % 2 if base % 2 else 0},
                    prompt_signature=(), prompt_carrier_cards=(), suit_resource_base=(base,),
                    suit_resource_profile=profile, suit_resource_text='',
                ))
        choices = []
        for base in range(8):
            pairs = []
            for first, second in combinations([a for a in actions if a.suit_resource_base == (base,)], 2):
                p, q = first.suit_resource_profile, second.suit_resource_profile
                score = 5 * abs(p[2] - q[2]) + 3 * len(set(p[0]) ^ set(q[0])) + 2 * len(set(p[1]) ^ set(q[1])) + abs(p[3] - q[3])
                if score > 0:
                    pairs.append((-score, tuple(sorted((first['action_id'], second['action_id']))), first, second))
            negative_score, ids, first, second = min(pairs, key=lambda item: item[:2])
            natural = any(a.suit_resource_profile[2] > a['wildcard_count'] for a in (first, second))
            wildcard = any(a.suit_resource_profile[2] > 0 and a['wildcard_count'] > 0 for a in (first, second))
            priority = 3 if natural and wildcard else 2 if natural else 1 if wildcard else 0
            profiles = tuple(sorted((first.suit_resource_profile, second.suit_resource_profile), key=repr))
            choices.append((-priority, negative_score, ids, profiles))
        expected, seen_profiles, seen_special = [], set(), set()
        for negative_priority, _, ids, profiles in sorted(choices):
            if profiles in seen_profiles or (negative_priority and negative_priority in seen_special):
                continue
            expected.append(ids)
            seen_profiles.add(profiles)
            if negative_priority:
                seen_special.add(negative_priority)
            if len(expected) == 2:
                break
        self.assertEqual(DeepSeekClient._prompt_suit_resource_groups(actions), tuple(expected))
        self.assertEqual(DeepSeekClient._prompt_suit_resource_groups(list(reversed(actions))), tuple(expected))

    def test_batch_catalog_matches_separate_binding_queries_at_all_capacities(self) -> None:
        pool = tuple(Card(rank, suit) for rank, suit in (
            ('2', 'H'), ('2', 'H'), ('7', 'S'), ('7', 'C'),
            ('8', 'S'), ('9', 'S'), ('10', 'S'), ('J', 'S'),
            ('9', 'C'), ('9', 'H'), ('9', 'D'),
        )) + (Card('SJ'), Card('SJ'), Card('BJ'), Card('BJ'))
        engine = BaseRuleEngine()
        declarations = (
            (PatternType.SINGLE, ('6',)),
            (PatternType.PAIR, ('6', '6')),
            (PatternType.TRIPLE_WITH_PAIR, ('6', '6', '6', '5', '5')),
            (PatternType.BOMB, ('8',) * 4),
            (PatternType.STRAIGHT_FLUSH, ('3', '4', '5', '6', '7')),
        )
        leads = tuple(Action(
            player_id=player, action_type=ActionType.PLAY, declared_pattern=pattern,
            declared_cards=tuple(Card(rank, 'H' if pattern == PatternType.STRAIGHT_FLUSH else None) for rank in ranks),
            carrier_cards=(),
        ) for player in (1, 2) for pattern, ranks in declarations)
        for capacity in (0, 2, 5, 10):
            with self.subTest(capacity=capacity):
                batch = engine.public_beating_response_summaries(pool, leads, '2', max_cards=capacity)
                for lead, summary in zip(leads, batch):
                    self.assertEqual(summary.requirements, engine.public_beating_response_requirements(pool, lead, '2'))
                    # This API independently enumerates and rebinds each carrier.
                    self.assertEqual(summary.resource_counts, engine.public_beating_response_resource_counts(pool, lead, '2', max_cards=capacity))

    def test_projected_routes_equal_full_regeneration_and_do_not_cross_observations(self) -> None:
        engine = BaseRuleEngine()
        games = [GuanDanGame(seed=0), GuanDanGame(seed=1), GuanDanGame(seed=0, current_level_rank='5')]
        for game in games:
            game.reset()
        games.append(_complete_game(['2H', '2H', '3H', '4H', '6H', '7H', '7S', '7C', '7D']))
        for game in games:
            for observation_index in range(2):
                observation, legal = game.observe(), game.legal_actions()
                saved = deepcopy((observation, legal))
                original = BaseRuleEngine.public_straight_flush_resources
                with patch.object(BaseRuleEngine, 'public_straight_flush_resources', autospec=True,
                                  side_effect=lambda _, hand, level: original(engine, hand, level)) as query:
                    projected = DeepSeekClient._project_prompt_actions(observation, legal)
                self.assertEqual(query.call_count, 1)
                self.assertEqual((observation, legal), saved)
                level = observation['current_round']['current_level_rank']
                hand = Counter(observation['my_info']['hand_cards'])
                checked = {}
                for action in projected:
                    signature = getattr(action, 'prompt_signature', None)
                    if signature is None:
                        continue
                    remaining = hand - Counter(action['carrier_cards'])
                    key = tuple(sorted(remaining.items()))
                    if key not in checked:
                        cards = tuple(DeepSeekClient._physical_card(token) for token in remaining.elements())
                        checked[key] = tuple(sorted({DeepSeekClient._public_flush_resource_key(item)
                                                    for item in engine.public_straight_flush_resources(cards, level)}))
                    self.assertEqual(signature[3], checked[key])
                if observation_index == 0:
                    self.assertTrue(checked)
                game.step(legal[0]['action_id'])

    def test_default_factory_returns_another_displayed_raw_id_with_all_features(self) -> None:
        game = _complete_game(['2H', '2H', '3H', '4H', '6H', '7H', '7S', '7C', '7D'])
        raw = deepcopy(game.legal_actions())
        _, _, first = _capture_default_factory_request(game, raw[0]['action_id'])
        alternate = first.candidate_ids[-1]
        self.assertNotEqual(alternate, first.candidate_ids[0])
        selected, agent, second = _capture_default_factory_request(game, alternate)
        self.assertEqual(selected, alternate)
        self.assertEqual(agent.last_decision_source, 'model')
        self.assertEqual(first.candidate_ids, second.candidate_ids)
        self.assertLessEqual(len(second.candidate_ids), 80)
        self.assertEqual(game.legal_actions(), raw)
        self.assertIn('【同花顺/逢人配花色资源对照】', second.prompt)
