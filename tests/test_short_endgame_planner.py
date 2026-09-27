from __future__ import annotations

from copy import deepcopy
import unittest

from agents.short_endgame_planner import (
    analyze_free_lead_grouping,
    free_lead_grouping_comparison_pairs,
    minimum_group_free_lead_action_ids,
)
from engine.cards import Card
from engine.game import GuanDanGame
from evaluation.short_endgame_scenarios import build_short_endgame_scenarios


def _action(action_id: int, pattern: str, declared: list[str], carriers: list[str]) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": declared,
        "carrier_cards": carriers,
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": f"{pattern}:{','.join(declared)}",
    }


def _observation(hand_cards: list[str]) -> dict[str, object]:
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_cards": hand_cards, "hand_count": len(hand_cards)},
        "current_round": {
            "step_no": 20,
            "round_no": 8,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [],
        "history": {"actions": [], "finish_order": []},
    }


def _six_seven_jack_actions() -> list[dict[str, object]]:
    return [
        _action(1, "single", ["6"], ["6S"]),
        _action(2, "single", ["7"], ["7S"]),
        _action(3, "single", ["J"], ["JH"]),
        _action(4, "single", ["J"], ["JD"]),
        _action(5, "pair", ["J", "J"], ["JH", "JD"]),
    ]


class ShortEndgamePlannerTests(unittest.TestCase):
    def test_pair_jack_exposes_minimum_group_first_actions(self) -> None:
        actions = _six_seven_jack_actions()
        observation = _observation(["6S", "7S", "JH", "JD"])
        self.assertEqual(minimum_group_free_lead_action_ids(observation, actions, 1), (1, 2, 5))

    def test_all_tied_first_actions_do_not_expose_an_opportunity(self) -> None:
        tied_actions = [
            _action(1, "single", ["6"], ["6S"]),
            _action(2, "single", ["7"], ["7S"]),
        ]
        self.assertIsNone(minimum_group_free_lead_action_ids(_observation(["6S", "7S"]), tied_actions, 1))

    def test_after_first_action_counts_only_the_remaining_groups(self) -> None:
        observation = _observation(["6S"])
        actions = [_action(1, "single", ["6"], ["6S"])]
        analysis = analyze_free_lead_grouping(observation, actions, 1)
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.counts_by_action_id(), {1: 0})  # type: ignore[union-attr]

    def test_engine_backed_five_to_eight_card_scenarios_have_bounded_differences(self) -> None:
        scenarios = build_short_endgame_scenarios()
        self.assertEqual(
            tuple(item.name for item in scenarios),
            (
                "group_cleanup",
                "straight_vs_singles",
                "natural_bomb_residual",
                "wildcard_and_natural_groups",
                "urgent_teammate",
                "urgent_opponent",
            ),
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario.name):
                my_info = scenario.observation["my_info"]
                assert isinstance(my_info, dict)
                hand_count = my_info["hand_count"]
                self.assertIn(hand_count, range(5, 9))
                self.assertEqual(len(scenario.legal_actions), len({action["action_id"] for action in scenario.legal_actions}))
                analysis = analyze_free_lead_grouping(scenario.observation, scenario.legal_actions, 1)
                self.assertIsNotNone(analysis)
                assert analysis is not None
                self.assertGreater(analysis.maximum_group_count, analysis.minimum_group_count)
                self.assertEqual(set(analysis.counts_by_action_id()), {action["action_id"] for action in scenario.legal_actions})
                pairs = free_lead_grouping_comparison_pairs(scenario.observation, scenario.legal_actions, 1)
                self.assertGreaterEqual(len(pairs), 1)
                self.assertLessEqual(len(pairs), 2)
                legal_ids = {action["action_id"] for action in scenario.legal_actions}
                self.assertTrue(all(left in legal_ids and right in legal_ids and left != right for left, right in pairs))

    def test_five_to_eight_grouping_remains_fail_closed_outside_free_lead_or_with_bad_actions(self) -> None:
        scenario = next(item for item in build_short_endgame_scenarios() if item.name == "group_cleanup")
        following = deepcopy(scenario.observation)
        current_round = following["current_round"]
        assert isinstance(current_round, dict)
        current_round.update(constraint="single:5", table_action=_action(99, "single", ["5"], ["5S"]))
        self.assertIsNone(analyze_free_lead_grouping(following, scenario.legal_actions, 1))
        malformed = deepcopy(scenario.legal_actions)
        malformed[0]["wildcard_count"] = True
        self.assertIsNone(analyze_free_lead_grouping(scenario.observation, malformed, 1))

    def test_equal_route_hand_does_not_create_a_prompt_comparison(self) -> None:
        def cards(tokens: tuple[str, ...]) -> tuple[Card, ...]:
            return tuple(Card(rank=token[:-1], suit=token[-1]) for token in tokens)

        game = GuanDanGame(
            current_level_rank="2",
            preset_hands={
                1: cards(("3S", "5H", "7C", "9D", "JC")),
                2: cards(("4S", "6H", "8C", "10D")),
                3: cards(("QS", "KH", "AC", "2S")),
                4: cards(("3H", "5C", "7D", "9H")),
            },
            starting_player_id=1,
        )
        observation = game.reset()
        actions = game.legal_actions()
        analysis = analyze_free_lead_grouping(observation, actions, 1)
        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertFalse(analysis.has_route_difference)
        self.assertEqual(len(set(analysis.counts_by_action_id().values())), 1)
        self.assertEqual(free_lead_grouping_comparison_pairs(observation, actions, 1), ())

    def test_multiple_best_actions_are_reported_in_original_canonical_order(self) -> None:
        actions = [
            _action(1, "single", ["6"], ["6S"]),
            _action(2, "single", ["6"], ["6H"]),
            _action(3, "pair", ["6", "6"], ["6S", "6H"]),
            _action(4, "single", ["7"], ["7S"]),
        ]
        result = minimum_group_free_lead_action_ids(_observation(["6S", "6H", "7S"]), actions, 1)
        self.assertEqual(result, (3, 4))

    def test_duplicate_public_tokens_are_counted_as_a_multiset(self) -> None:
        actions = [
            _action(1, "single", ["J"], ["JH"]),
            _action(2, "pair", ["J", "J"], ["JH", "JH"]),
            _action(3, "single", ["6"], ["6S"]),
        ]
        result = minimum_group_free_lead_action_ids(_observation(["JH", "JH", "6S"]), actions, 1)
        self.assertEqual(result, (2, 3))

    def test_incomplete_or_non_target_public_payload_fails_closed(self) -> None:
        observation = _observation(["6S", "7S", "JH", "JD"])
        actions = _six_seven_jack_actions()
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []

        incomplete_hand = deepcopy(observation)
        incomplete_hand["my_info"] = dict(incomplete_hand["my_info"], hand_cards=["6S", "7S", "JH"])
        cases.append((incomplete_hand, actions))

        overlarge = _observation(["3S", "4S", "5S", "6S", "7S"])
        cases.append((overlarge, actions))

        follow = deepcopy(observation)
        follow["current_round"] = dict(follow["current_round"], constraint="single:5", table_action=_action(99, "single", ["5"], ["5S"]))
        cases.append((follow, actions))

        pass_in_free = [_action(9, "pass", [], [])] + actions
        cases.append((observation, pass_in_free))

        bad_carrier = deepcopy(actions)
        bad_carrier[0]["carrier_cards"] = ["AS"]
        cases.append((observation, bad_carrier))

        duplicate_id = deepcopy(actions)
        duplicate_id[1]["action_id"] = 1
        cases.append((observation, duplicate_id))

        bool_id = deepcopy(actions)
        bool_id[1]["action_id"] = True
        cases.append((observation, bool_id))

        missing_display = deepcopy(actions)
        del missing_display[0]["display_text"]
        cases.append((observation, missing_display))

        cannot_cover = actions[:-1]
        cases.append((observation, cannot_cover))

        for payload, legal_actions in cases:
            with self.subTest(payload=payload["current_round"]["constraint"]):
                self.assertIsNone(minimum_group_free_lead_action_ids(payload, legal_actions, 1))


if __name__ == "__main__":
    unittest.main()
