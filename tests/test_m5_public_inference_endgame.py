from __future__ import annotations

import json
import random
import re
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.card_tracker import (
    _candidate_comparison_line,
    _candidate_pairs,
    _public_pass_evidence,
    _validated_public_state,
    build_card_tracking_summary,
    exact_public_hand_assignment,
    relevant_public_passes,
    relevant_public_carried_pairs,
    terminal_pass_signal,
    _pass_behavior_text,
    _pattern_action,
)
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from agents.rule_based_ai import RuleBasedAIAgent, FrozenRuleBasedAIAgent
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame
from engine.public_endgame import PublicEndgameAnalysis, analyze_public_endgame
from engine.rules import BaseRuleEngine
from integrations.botzone.agent_runtime import build_agent_factory


def _rollout_to_step(seed: int, target_step: int) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]]]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    game.reset()
    while game.observe()["current_round"]["step_no"] < target_step:
        observation = game.observe()
        actions = game.legal_actions()
        player_id = int(observation["my_info"]["player_id"])
        game.step(RuleBasedAIAgent(player_id).select_action(observation, actions))
        if game._state.is_finished:  # noqa: SLF001 - deterministic test rollout
            raise AssertionError("seeded game ended before requested observation")
    return game, game.observe(), game.legal_actions()


def _clone_game(game: GuanDanGame) -> GuanDanGame:
    clone = GuanDanGame(current_level_rank=game._current_level_rank)  # noqa: SLF001
    clone._state = game._require_state()  # noqa: SLF001 - test-only perfect-information oracle
    clone._invalidate_legal_actions_cache()  # noqa: SLF001
    return clone


def _reference_team_value(
    game: GuanDanGame,
    root_team: str,
    trace: Counter[str],
) -> int:
    state = game._require_state()  # noqa: SLF001 - test-only perfect-information oracle
    if state.is_finished:
        if state.winner == "draw":
            return 0
        return 1 if state.winner == root_team else -1
    player_team = "team_13" if state.current_player_id in {1, 3} else "team_24"
    maximize = player_team == root_team
    values = []
    for action in game.legal_actions():
        child = _clone_game(game)
        result = child.step(int(action["action_id"]))
        if action["declared_pattern"] == "pass":
            trace["pass"] += 1
        if result["round_ended"]:
            trace["round_reset"] += 1
        if result["game_over"]:
            trace["terminal"] += 1
        values.append(_reference_team_value(child, root_team, trace))
    if not values:
        raise AssertionError("engine returned no legal actions in nonterminal reference state")
    return max(values) if maximize else min(values)


def _reference_root_values(
    game: GuanDanGame,
) -> tuple[tuple[tuple[int, int], ...], Counter[str]]:
    current_id = game._require_state().current_player_id  # noqa: SLF001
    root_team = "team_13" if current_id in {1, 3} else "team_24"
    trace: Counter[str] = Counter()
    values = []
    for action in game.legal_actions():
        child = _clone_game(game)
        result = child.step(int(action["action_id"]))
        if action["declared_pattern"] == "pass":
            trace["pass"] += 1
        if result["round_ended"]:
            trace["round_reset"] += 1
        if result["game_over"]:
            trace["terminal"] += 1
        values.append((
            int(action["action_id"]),
            _reference_team_value(child, root_team, trace),
        ))
    return tuple(values), trace


def _shuffled_hands(seed: int) -> dict[int, tuple[object, ...]]:
    deck = build_double_deck()
    random.Random(seed).shuffle(deck)
    return {
        player_id: tuple(deck[(player_id - 1) * 27:player_id * 27])
        for player_id in range(1, 5)
    }


def _select_action(
    actions: list[dict[str, object]],
    predicate,
) -> dict[str, object]:
    return next(action for action in actions if predicate(action))


class M5PublicPassEvidenceTests(unittest.TestCase):
    @staticmethod
    def _repeated_lead_fixture(first, second, pattern, starting=1, second_pattern=None):
        """Two free leads and actual passes from a complete physical deal."""
        cards = lambda tokens: tuple(Card(t) if t in ('SJ', 'BJ') else Card(t[:-1], t[-1]) for t in tokens)
        deck = build_double_deck()
        reserved = cards(first + second)
        replies = cards(('SJ', 'SJ', 'BJ', 'BJ'))
        for card in reserved + replies:
            deck.remove(card)
        random.Random(121).shuffle(deck)
        next_player = starting % 4 + 1
        hands = {}
        cursor = 0
        for player in (starting, next_player, *[p for p in range(1, 5) if p not in (starting, next_player)]):
            base = reserved if player == starting else replies if player == next_player else ()
            needed = 27 - len(base)
            hands[player] = base + tuple(deck[cursor:cursor + needed])
            cursor += needed
        assert all(len(hand) == 27 for hand in hands.values())
        assert Counter(card for hand in hands.values() for card in hand) == Counter(build_double_deck())
        game = GuanDanGame(preset_hands=hands, current_level_rank='2', starting_player_id=starting)
        game.reset()
        def play(tokens, kind):
            action = _select_action(game.legal_actions(), lambda item:
                item['declared_pattern'] == kind and Counter(item['carrier_cards']) == Counter(tokens)
                and (kind != 'triple_with_pair' or item['declared_cards'].count(tokens[0][:-1]) == 3))
            game.step(action['action_id'])
        play(first, pattern)
        for _ in range(3):
            game.step(_select_action(game.legal_actions(), lambda item: item['declared_pattern'] == 'pass')['action_id'])
        play(second, second_pattern or pattern)
        return game, game.observe(), game.legal_actions()

    @staticmethod
    def _carried_pair_choice_fixture(starting=1, triple='9', carried='7', reply_triple='J', reply_pair='6', lead='8', wildcard=False):
        """A real deal: a teammate's triple lead is overtaken, then a pair lead."""
        groups = (
            (triple+'S', triple+'H', triple+'C', *(('BJ', 'BJ') if carried == 'BJ' else (carried+'S', '2H' if wildcard else carried+'C'))),
            (reply_triple+'S', reply_triple+'H', reply_triple+'C', reply_pair+'S', reply_pair+'C', lead+'S', lead+'C'),
            ('AS', 'AC', 'SJ', 'SJ', *(() if carried == 'BJ' else ('BJ', 'BJ'))),
            (),
        )
        deck = build_double_deck()
        reserved = [tuple(Card(t) if t in ('SJ', 'BJ') else Card(t[:-1], t[-1]) for t in group) for group in groups]
        for group in reserved:
            for card in group:
                deck.remove(card)
        random.Random(121).shuffle(deck)
        hands = {}
        for offset, group in enumerate(reserved):
            needed = 27 - len(group)
            hands[(starting + offset - 1) % 4 + 1] = group + tuple(deck[:needed])
            del deck[:needed]
        assert not deck
        assert Counter(card for hand in hands.values() for card in hand) == Counter(build_double_deck())
        game = GuanDanGame(preset_hands=hands, current_level_rank='2', starting_player_id=starting)
        game.reset()
        def play(pattern, tokens):
            action = _select_action(game.legal_actions(), lambda item: item['declared_pattern'] == pattern
                and Counter(item['carrier_cards']) == Counter(tokens))
            game.step(action['action_id'])
        play('triple_with_pair', groups[0])
        play('triple_with_pair', groups[1][:5])
        for _ in range(3):
            play('pass', ())
        play('pair', groups[1][5:])
        return game, game.observe(), game.legal_actions()

    def test_external_carried_pairs_update_without_hard_inference(self) -> None:
        for first, second, expected in (
            (('9S', '9H', '9C', '7S', '7C'), ('5S', '5C'), '后出更小对子'),
            (('9S', '9H', '9C', '7S', '2H'), ('8S', '8C'), '后续实体已扣除'),
        ):
            game, observation, actions = self._repeated_lead_fixture(first, second, 'triple_with_pair', second_pattern='pair')
            original = deepcopy((observation, actions))
            constraints = _validated_public_state(observation).constraints.to_dict()
            evidence = relevant_public_carried_pairs(observation, actions)
            if '2H' in first:
                self.assertEqual(evidence, ())
                self.assertNotIn('历史携带软线索', build_card_tracking_summary(observation, actions))
                self.assertEqual((observation, actions), original)
                self.assertEqual(_validated_public_state(observation).constraints.to_dict(), constraints)
                continue
            self.assertEqual(len(evidence), 1)
            self.assertNotEqual(evidence[0].player_id % 2, observation['my_info']['player_id'] % 2)
            self.assertEqual(evidence[0].later_carriers, tuple(Card(t[:-1], t[-1]) for t in second))
            summary = build_card_tracking_summary(observation, actions)
            self.assertIn(expected, summary)
            self.assertNotIn('可弱支持留较大对路线', summary)
            self.assertEqual((observation, actions), original)
            self.assertEqual(_validated_public_state(observation).constraints.to_dict(), constraints)
            incomplete = deepcopy(observation)
            incomplete['history']['actions'].pop(0)
            self.assertEqual(relevant_public_carried_pairs(incomplete, actions), ())
            self.assertEqual(relevant_public_carried_pairs(observation, [actions[-1]]), ())

    def test_carried_pair_wildcard_and_terminal_pass_priority(self) -> None:
        _, observation, actions = self._carried_pair_choice_fixture(wildcard=True)
        evidence = relevant_public_carried_pairs(observation, actions)
        event = next(item for item in evidence if item.player_id == 1)
        self.assertEqual(event.binding_kind, '通配参与携带')
        summary = build_card_tracking_summary(observation, actions)
        self.assertIn('声明不等于自然实体对子', summary)
        self.assertNotIn('可弱支持留较大对路线', summary)
        _, observation, actions = self._carried_pair_choice_fixture(carried='BJ')
        event = relevant_public_carried_pairs(observation, actions)[0]
        self.assertEqual(event.pair_rank, 'BJ')
        self.assertFalse(event.larger_pair_possible)
        summary = build_card_tracking_summary(observation, actions)
        self.assertIn('当前牌池/容量无可行更大对子', summary)
        self.assertNotIn('可弱支持留较大对路线', summary)
        # Reuse a live legal replay with a terminal pass, without treating the
        # earlier carried pair as an independent reason to expect a response.
        game = GuanDanGame(seed=4, current_level_rank='2')
        game.reset()
        for _ in range(74):
            obs = game.observe()
            game.step(FrozenRuleBasedAIAgent(obs['my_info']['player_id']).select_action(obs, game.legal_actions()))
        observation, actions = game.observe(), game.legal_actions()
        strong = {item.player_id for item in relevant_public_passes(observation) if terminal_pass_signal(item)}
        self.assertTrue(strong)
        self.assertFalse(strong & {item.player_id for item in relevant_public_carried_pairs(observation, actions)})

    def test_external_carried_pair_choices_reach_factory_for_both_roles(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _config, _fake_response_transport
        for params in ({}, dict(starting=2, triple='Q', carried='4', reply_triple='K', reply_pair='5', lead='6'), {'later_lower': True}):
            if params.get('later_lower'):
                _, observation, actions = self._repeated_lead_fixture(
                    ('9S', '9H', '9C', '7S', '7C'), ('5S', '5C'), 'triple_with_pair', second_pattern='pair')
            else:
                _, observation, actions = self._carried_pair_choice_fixture(**params)
            original = deepcopy((observation, actions))
            constraints = _validated_public_state(observation).constraints.to_dict()
            evidence = relevant_public_carried_pairs(observation, actions)
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].player_id % 2 == observation['my_info']['player_id'] % 2, not params.get('later_lower', False))
            captured = []
            agent = build_agent_factory('deepseek', config_loader=_config,
                client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=_fake_response_transport(captured)))(observation['my_info']['player_id'])
            chosen = agent.select_action(observation, actions)
            prompt = captured[0]['messages'][1]['content']
            for phrase in ('历史携带软线索', '备选未知', '确证与末手pass优先', '不保证胜负。'):
                self.assertIn(phrase, prompt)
            if params.get('later_lower'):
                self.assertIn('后出更小对子，否定此前必带最小对', prompt)
                self.assertNotIn('可弱支持留较大对路线', prompt)
            else:
                self.assertIn('可弱支持留较大对路线', prompt)
            self.assertNotIn('url_or_bibliography', prompt)
            self.assertNotIn('a5xk3dpl', prompt)
            section = prompt.split('【候选动作】', 1)[1].split('【规则库依据】', 1)[0]
            visible = [int(item) for item in re.findall(r'#(\d+)\s+action_id=', section)]
            self.assertEqual(chosen, visible[-1])
            self.assertIn(chosen, [item['action_id'] for item in actions])
            self.assertEqual(agent.last_decision_source, 'model')
            self.assertLessEqual(len(visible), 80)
            self.assertLessEqual(len(build_card_tracking_summary(observation, actions)), 1350)
            self.assertEqual((observation, actions), original)
            self.assertEqual(_validated_public_state(observation).constraints.to_dict(), constraints)
            get_context = agent.rag_advisor.get_rag_context
            def without_behavior(**kwargs):
                context = get_context(**kwargs)
                self.assertTrue(context['behavior_experience_hits'])
                self.assertNotIn('exp_soft_triple_pair_gradient_001',
                    [item['source_id'] for item in context['behavior_experience_hits']])
                context.pop('behavior_experience_hits')
                return context
            agent.rag_advisor.get_rag_context = without_behavior
            self.assertEqual(agent.select_action(observation, actions), chosen)
            second = captured[1]['messages'][1]['content'].split('【候选动作】', 1)[1].split('【规则库依据】', 1)[0]
            self.assertEqual([int(item) for item in re.findall(r'#(\d+)\s+action_id=', second)], visible)

    def test_rule_strength_pass_matching_preserves_distinct_declarations_and_bindings(self) -> None:
        triple = ('9S', '9H', '9C', '7S', '7C')
        equal = ('9S', '9H', '9D', '8S', '8C')
        cases = (
            (triple, equal, 'triple_with_pair', 1, None, 2),
            (triple, ('JS', 'JH', 'JC', '8S', '8C'), 'triple_with_pair', 1, None, 2),
            (triple, ('8S', '8H', '8C', 'JS', 'JC'), 'triple_with_pair', 1, None, 0),
            (('3S', '4S', '5S', '6S', '7S'), ('3C', '4C', '5C', '6C', '7C'), 'straight_flush', 1, None, 2),
            (('QS', 'QH', 'QC', '5S', '5C'), ('QS', 'QH', 'QD', '6S', '6C'), 'triple_with_pair', 3, None, 2),
            (triple, ('9S', '9H', '2H', '8S', '8C'), 'triple_with_pair', 1, None, 2),
            (('9S', '9H', '2H', '7S', '7C'), equal, 'triple_with_pair', 1, None, 2),
            (triple, ('3S', '4C', '5S', '6D', '7H'), 'triple_with_pair', 1, 'straight', 0),
        )
        for first, second, pattern, starting, second_pattern, count in cases:
            with self.subTest(pattern=pattern, starting=starting, second=second):
                _, observation, actions = self._repeated_lead_fixture(first, second, pattern, starting, second_pattern)
                state = _validated_public_state(observation)
                self.assertIsNotNone(state)
                engine = BaseRuleEngine()
                evidence = _public_pass_evidence(observation, state, engine)
                self.assertEqual(len(evidence), 3)
                current = _pattern_action(observation['current_round']['table_action'], state.my_player_id)
                old = evidence[0].lead_action
                if count and first[0][:-1] == second[0][:-1]:
                    self.assertNotEqual(current.declared_cards, old.declared_cards)
                    self.assertFalse(engine.can_beat(current, old, '2'))
                    self.assertFalse(engine.can_beat(old, current, '2'))
                elif current.declared_pattern == old.declared_pattern:
                    self.assertEqual(engine.can_beat(current, old, '2'), count == 2)
                    self.assertEqual(engine.can_beat(old, current, '2'), count == 0)
                else:
                    self.assertFalse(engine.can_beat(current, old, '2'))
                    self.assertFalse(engine.can_beat(old, current, '2'))
                constraints = state.constraints.to_dict()
                original = deepcopy((observation, actions))
                self.assertEqual(len(relevant_public_passes(observation)), count)
                self.assertEqual(_validated_public_state(observation).constraints.to_dict(), constraints)
                self.assertEqual((observation, actions), original)
                for field, value in (('declared_pattern', 'unknown'), ('carrier_cards', [])):
                    invalid = deepcopy(observation)
                    invalid['current_round']['table_action'][field] = value
                    self.assertEqual(relevant_public_passes(invalid), ())
                incomplete = deepcopy(observation)
                incomplete['history']['actions'].pop(0)
                self.assertEqual(relevant_public_passes(incomplete), ())

    def test_equal_strength_pass_reaches_default_factory_with_original_model_id(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _config, _fake_response_transport
        _, observation, actions = self._repeated_lead_fixture(
            ('QS', 'QH', 'QC', '5S', '5C'), ('QS', 'QH', 'QD', '6S', '6C'), 'triple_with_pair', 3)
        original = deepcopy((observation, actions))
        captured = []
        agent = build_agent_factory('deepseek', config_loader=_config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=_fake_response_transport(captured)))(4)
        chosen = agent.select_action(observation, actions)
        prompt = captured[0]['messages'][1]['content']
        self.assertIn('历史软pass：P2友 step4', prompt)
        self.assertIn('P1敌 step3', prompt)
        self.assertIn('不确定信息与试探成本', prompt)
        self.assertNotIn('公开检索返回', prompt)
        section = prompt.split('【候选动作】', 1)[1].split('【规则库依据】', 1)[0]
        visible = [int(item) for item in re.findall(r'#(\d+)\s+action_id=', section)]
        self.assertEqual(chosen, visible[-1])
        self.assertIn(chosen, [action['action_id'] for action in actions])
        self.assertEqual(agent.last_decision_source, 'model')
        self.assertLessEqual(len(visible), 80)
        self.assertLessEqual(len(build_card_tracking_summary(observation, actions)), 1350)
        self.assertEqual((observation, actions), original)

    def test_single_response_behavior_reaches_factory_for_both_roles_without_rewriting_choice(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _config, _fake_response_transport
        for seed, step, role in ((1, 62, 'opponent'), (4, 74, 'teammate')):
            with self.subTest(role=role):
                game = GuanDanGame(seed=seed, current_level_rank='2')
                game.reset()
                for _ in range(step):
                    obs = game.observe()
                    game.step(FrozenRuleBasedAIAgent(obs['my_info']['player_id']).select_action(obs, game.legal_actions()))
                observation, actions = game.observe(), game.legal_actions()
                self.assertEqual(len(actions), 2)
                events = relevant_public_passes(observation)
                strong = next(item for item in events if terminal_pass_signal(item))
                same_team = strong.player_id % 2 == observation['my_info']['player_id'] % 2
                self.assertEqual(same_team, role == 'teammate')
                leader = next(item['player_id'] for item in reversed(observation['history']['actions'])
                              if item['declared_pattern'] != 'pass')
                if role == 'opponent':
                    # Teammate controls the table: an opponent's terminal pass
                    # does not turn support into a mandatory response.
                    self.assertEqual(leader % 2, observation['my_info']['player_id'] % 2)
                state = _validated_public_state(observation)
                before = state.constraints.to_dict()
                original = deepcopy((observation, actions))
                summary = build_card_tracking_summary(observation, actions)
                self.assertIn('末手若能同型接即可出完却让', summary)
                self.assertLessEqual(len(summary), 1350)
                captured = []
                agent = build_agent_factory('deepseek', config_loader=_config,
                    client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=_fake_response_transport(captured)))(observation['my_info']['player_id'])
                chosen = agent.select_action(observation, actions)
                prompt = captured[0]['messages'][1]['content']
                self.assertIn('末手若能同型接即可出完却让', prompt)
                self.assertIn('不默认支援=pass', prompt)
                self.assertIn('不确定信息与试探成本', prompt)
                self.assertIn('行为不改硬牌域、不赋概率、不保证胜负。', prompt)
                self.assertNotIn('corroborating_source_ids', prompt)
                self.assertNotIn('10706126', prompt)
                self.assertEqual(chosen, actions[-1]['action_id'])
                self.assertEqual(agent.last_decision_source, 'model')
                report = agent.client._delegate.last_bounded_continuation
                self.assertEqual(report.status, 'ready')
                self.assertEqual(report.scenarios, 2)
                self.assertEqual(report.steps, 2 * 2 * len(actions) * 8)
                self.assertIn('历史末手能接即走行为不相称=', prompt)
                self.assertIn('仍保留全部共同场景', prompt)
                self.assertEqual((observation, actions), original)
                self.assertEqual(_validated_public_state(observation).constraints.to_dict(), before)
                incomplete = deepcopy(observation)
                incomplete['history']['actions'].pop(0)
                self.assertEqual(relevant_public_passes(incomplete), ())

    def _pass_observation(self) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]], dict[int, bool]]:
        game = GuanDanGame(
            preset_hands=_shuffled_hands(694),
            current_level_rank="2",
            starting_player_id=1,
        )
        game.reset()
        lead = _select_action(
            game.legal_actions(),
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["SJ"],
        )
        game.step(int(lead["action_id"]))

        actual_had_response: dict[int, bool] = {}
        player_two_actions = game.legal_actions()
        self.assertTrue(any(
            action["declared_pattern"] == "single"
            and action["carrier_cards"] == ["BJ"]
            for action in player_two_actions
        ))
        actual_had_response[2] = any(
            action["declared_pattern"] != "pass" for action in player_two_actions
        )
        game.step(int(_select_action(player_two_actions, lambda item: item["declared_pattern"] == "pass")["action_id"]))

        player_three_actions = game.legal_actions()
        self.assertEqual(
            [action["declared_pattern"] for action in player_three_actions],
            ["pass"],
        )
        actual_had_response[3] = any(
            action["declared_pattern"] != "pass" for action in player_three_actions
        )
        game.step(int(player_three_actions[0]["action_id"]))

        player_four_actions = game.legal_actions()
        game.step(int(_select_action(player_four_actions, lambda item: item["declared_pattern"] == "pass")["action_id"]))
        observation = game.observe()
        return game, observation, game.legal_actions(), actual_had_response

    def test_pass_is_soft_candidate_specific_and_later_public_play_confirms_only_what_it_proves(self) -> None:
        game, observation, actions, actual_had_response = self._pass_observation()
        self.assertEqual(observation["my_info"]["player_id"], 1)
        state = _validated_public_state(observation)
        self.assertIsNotNone(state)
        assert state is not None
        original_constraints = state.constraints.to_dict()
        evidence = _public_pass_evidence(observation, state, BaseRuleEngine())
        pass_by_player = {item.player_id: item for item in evidence}
        self.assertIsNone(pass_by_player[2].response_confirmed_step_no)
        self.assertIsNone(pass_by_player[3].response_confirmed_step_no)
        self.assertTrue(actual_had_response[2])
        self.assertFalse(actual_had_response[3])
        self.assertTrue(pass_by_player[2].opponent_led)
        self.assertFalse(terminal_pass_signal(pass_by_player[2]))
        self.assertFalse(terminal_pass_signal(pass_by_player[3]))
        self.assertFalse(pass_by_player[3].opponent_led)
        self.assertIn('护组合', _pass_behavior_text(pass_by_player[3], state))

        low_single = _select_action(
            actions,
            lambda item: item["declared_pattern"] == "single"
            and item["declared_cards"][0] not in {"SJ", "BJ"},
        )
        high_single = _select_action(
            actions,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["BJ"],
        )
        profiles: dict[int, tuple[dict[str, object], ...]] = {}
        facts = {}
        pairs = _candidate_pairs(
            [low_single, high_single],
            Counter(observation["my_info"]["hand_cards"]),
            state=state,
            engine=BaseRuleEngine(),
            owner=None,
            profile_cache=profiles,
            facts_cache=facts,
            pass_evidence=evidence,
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(
            {int(pairs[0][0]["action_id"]), int(pairs[0][1]["action_id"])},
            {int(low_single["action_id"]), int(high_single["action_id"])},
        )
        low_profile = next(item for item in profiles[int(low_single["action_id"])] if item["relation"] == "敌")
        high_profile = next(item for item in profiles[int(high_single["action_id"])] if item["relation"] == "敌")
        self.assertEqual(low_profile["pass_signature"], ())
        self.assertEqual(high_profile["pass_signature"], (("single", "ambiguous"),))
        line = _candidate_comparison_line(
            low_single,
            high_single,
            profiles,
            facts,
            recommendation_anchored=False,
        )
        self.assertIn("历史软pass", line)
        self.assertIn("当时无应手或策略让牌无法区分", line)

        summary = build_card_tracking_summary(observation, actions)
        after_summary_state = _validated_public_state(observation)
        self.assertIsNotNone(after_summary_state)
        assert after_summary_state is not None
        self.assertEqual(after_summary_state.constraints.to_dict(), original_constraints)
        self.assertIn("历史软pass", summary)
        self.assertIn("pass不证明无牌", summary)

        # P1 leads a smaller single; P2's later public BJ play proves it held a
        # beating carrier at the earlier pass. The old event changes to a
        # confirmed historical fact, while P3's no-response pass stays ambiguous.
        game.step(int(low_single["action_id"]))
        p2_actions = game.legal_actions()
        later_bj = _select_action(
            p2_actions,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["BJ"],
        )
        game.step(int(later_bj["action_id"]))
        later_observation = game.observe()
        later_state = _validated_public_state(later_observation)
        self.assertIsNotNone(later_state)
        assert later_state is not None
        later_events = {
            item.player_id: item
            for item in _public_pass_evidence(later_observation, later_state, BaseRuleEngine())
        }
        self.assertEqual(later_events[2].response_confirmed_step_no, 6)
        self.assertGreater(later_events[2].cards_played_since, 0)
        self.assertFalse(terminal_pass_signal(later_events[2]))
        self.assertIn('不确证拆牌', _pass_behavior_text(later_events[2], later_state))
        self.assertIsNone(later_events[3].response_confirmed_step_no)
        self.assertFalse(actual_had_response[3])

        incomplete = deepcopy(later_observation)
        incomplete["history"]["actions"].pop(0)
        self.assertEqual(
            _public_pass_evidence(
                incomplete,
                later_state,
                BaseRuleEngine(),
            ),
            (),
        )

    def test_multi_seed_pass_signal_has_no_false_confirmations_and_keeps_both_ambiguous_outcomes(self) -> None:
        actual_had_response: dict[tuple[int, int], bool] = {}
        latest_inference: dict[tuple[int, int], bool] = {}
        for seed in (0, 2, 4, 6, 8):
            rng = random.Random(seed * 17 + 4)
            game = GuanDanGame(seed=seed, current_level_rank="2")
            game.reset()
            for _ in range(1_500):
                observation = game.observe()
                actions = game.legal_actions()
                player_id = int(observation["my_info"]["player_id"])
                step_no = int(observation["current_round"]["step_no"]) + 1
                plays = [action for action in actions if action["declared_pattern"] != "pass"]
                pass_action = next(
                    (action for action in actions if action["declared_pattern"] == "pass"),
                    None,
                )
                if (
                    pass_action is not None
                    and observation["current_round"]["table_action"] is not None
                    and rng.random() < 0.35
                ):
                    chosen = pass_action
                    actual_had_response[(seed, step_no)] = bool(plays)
                elif plays:
                    ordered = sorted(
                        plays,
                        key=lambda action: (-len(action["carrier_cards"]), action["action_id"]),
                    )
                    chosen = rng.choice(ordered[:min(8, len(ordered))])
                elif pass_action is not None:
                    chosen = pass_action
                    actual_had_response[(seed, step_no)] = False
                else:
                    self.fail("engine returned no legal action")
                game.step(int(chosen["action_id"]))
                if game._state.is_finished:  # noqa: SLF001 - test rollout boundary
                    break
                current = game.observe()
                state = _validated_public_state(current)
                if state is None:
                    continue
                for event in _public_pass_evidence(current, state, BaseRuleEngine()):
                    key = (seed, event.step_no)
                    latest_inference[key] = event.response_confirmed_step_no is not None

        self.assertGreater(len(latest_inference), 100)
        confirmed = [key for key, value in latest_inference.items() if value]
        ambiguous = [key for key, value in latest_inference.items() if not value]
        self.assertTrue(confirmed)
        self.assertTrue(ambiguous)
        self.assertTrue(all(actual_had_response[key] for key in confirmed))
        self.assertTrue(any(actual_had_response[key] for key in ambiguous))
        self.assertTrue(any(not actual_had_response[key] for key in ambiguous))


class M5PublicEndgameTests(unittest.TestCase):
    def test_frozen_search_anchor_fails_closed_when_public_hands_are_not_unique(self) -> None:
        game, observation, actions = _rollout_to_step(10, 86)
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNone(assignment)
        analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "ineligible")
        self.assertEqual(analysis.action_values, ())
        self.assertEqual(analysis.action_reachable_values, ())
        self.assertIsNone(analysis.proven_action_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["declared_pattern"], "pass")
        self.assertEqual(analysis.nodes, 0)

        truncated = deepcopy(observation)
        truncated["history"]["actions"].pop()
        truncated_assignment = exact_public_hand_assignment(truncated)
        self.assertIsNone(truncated_assignment)
        self.assertEqual(
            analyze_public_endgame(truncated, actions, truncated_assignment).status,
            "ineligible",
        )
        self.assertEqual(
            analyze_public_endgame(observation, actions, {}).status,
            "ineligible",
        )

    def test_partner_pass_resets_to_active_leader_and_search_matches_engine(self) -> None:
        game = GuanDanGame(seed=12, current_level_rank="2")
        game.reset()
        while game.observe()["current_round"]["step_no"] < 87 and not game._state.is_finished:
            observation = game.observe()
            actions = game.legal_actions()
            player_id = int(observation["my_info"]["player_id"])
            game.step(RuleBasedAIAgent(player_id).select_action(observation, actions))
        state = game._require_state()  # noqa: SLF001 - fixed anchor verification
        self.assertTrue(state.is_finished)
        self.assertEqual(len(state.finish_order), 4)
        self.assertEqual(
            [player.player_id for player in sorted(
                (item for item in state.players if item.finish_rank is not None),
                key=lambda item: item.finish_rank or 99,
            )],
            list(state.finish_order),
        )
        self.assertEqual(game.legal_actions(), [])

    def test_default_factory_sends_endgame_relations_and_preserves_model_action(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _public_endgame_fixture

        _, observation, actions = _public_endgame_fixture(
            current_hands={3: ("6S", "7S"), 4: ("8S",)},
            finish_order=(1, 2),
            current_player_id=3,
            leading_token="5S",
            leader_player_id=4,
        )
        captured: list[dict[str, object]] = []

        def fake_transport(request, _timeout):
            payload = json.loads(request.data.decode("utf-8"))
            captured.append(payload)
            section = payload["messages"][1]["content"].split("【候选动作】", 1)[1]
            candidate_section = section.split("【规则库依据】", 1)[0]
            match = re.search(r"action_id=(\d+)", candidate_section)
            assert match is not None
            answer = int(match.group(1))
            event = json.dumps({
                "choices": [{
                    "delta": {
                        "content": json.dumps({"action_id": answer, "reason": "synthetic"})
                    }
                }]
            })
            return f"data: {event}\n\ndata: [DONE]\n\n"

        config = SimpleNamespace(
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://example.invalid",
            deepseek_model="synthetic-model",
            deepseek_timeout=2.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
            card_tracking_enabled=True,
        )
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_transport),
            rag_factory=lambda: None,
        )
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch(
                "engine.public_endgame.analyze_public_endgame",
                return_value=PublicEndgameAnalysis(
                    status="budget_exceeded",
                    reason="search_limit",
                ),
            ),
        ):
            agent = factory(3)
            selected = agent.select_action(observation, actions)

        self.assertEqual(len(captured), 1)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertEqual(agent.last_public_endgame_analysis.status, "budget_exceeded")
        prompt = captured[0]["messages"][1]["content"]
        self.assertIn("【公开确证手牌】", prompt)
        self.assertIn("守恒", prompt)
        self.assertNotIn("M5公开残局对照", prompt)
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        displayed = {
            int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)
        }
        self.assertLessEqual(len(displayed), 80)

    def test_completed_proven_winning_root_shortcuts_before_model(self) -> None:
        from tests.test_m9_public_endgame_opportunities import _public_endgame_fixture

        _, observation, actions = _public_endgame_fixture(
            current_hands={1: ("3S", "3C", "4S", "4C"), 2: ("5H",)},
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        assert assignment is not None
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "proven_win")
        self.assertIsNotNone(analysis.proven_action_id)

        class _NoCallClient:
            calls = 0

            def suggest_action_id(self, **_kwargs):
                self.calls += 1
                raise AssertionError("proven unique win should not call the model")

        config = SimpleNamespace(
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
            card_tracking_enabled=False,
        )
        client = _NoCallClient()
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch("engine.public_endgame.monotonic", return_value=0.0),
        ):
            agent = DeepSeekAIAgent(
                player_id=int(observation["my_info"]["player_id"]),
                client=client,  # type: ignore[arg-type]
                hand_evaluation_enabled=False,
                opening_formula_enabled=False,
            )
            selected = agent.select_action(observation, actions)
        self.assertEqual(selected, analysis.proven_action_id)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
