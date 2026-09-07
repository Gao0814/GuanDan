from __future__ import annotations

from copy import deepcopy
import unittest

from agents.short_endgame_planner import strictly_better_free_lead_action_ids


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
    def test_pair_jack_strictly_beats_model_single_jack(self) -> None:
        actions = _six_seven_jack_actions()
        result = strictly_better_free_lead_action_ids(_observation(["6S", "7S", "JH", "JD"]), actions, 1, 3)
        self.assertEqual(result, (1, 2, 5))

    def test_best_or_tied_model_action_is_preserved(self) -> None:
        actions = _six_seven_jack_actions()
        self.assertIsNone(
            strictly_better_free_lead_action_ids(_observation(["6S", "7S", "JH", "JD"]), actions, 1, 5)
        )
        tied_actions = [
            _action(1, "single", ["6"], ["6S"]),
            _action(2, "single", ["7"], ["7S"]),
        ]
        self.assertIsNone(strictly_better_free_lead_action_ids(_observation(["6S", "7S"]), tied_actions, 1, 1))

    def test_multiple_best_actions_are_reported_in_original_canonical_order(self) -> None:
        actions = [
            _action(1, "single", ["6"], ["6S"]),
            _action(2, "single", ["6"], ["6H"]),
            _action(3, "pair", ["6", "6"], ["6S", "6H"]),
            _action(4, "single", ["7"], ["7S"]),
        ]
        result = strictly_better_free_lead_action_ids(_observation(["6S", "6H", "7S"]), actions, 1, 1)
        self.assertEqual(result, (3, 4))

    def test_duplicate_public_tokens_are_counted_as_a_multiset(self) -> None:
        actions = [
            _action(1, "single", ["J"], ["JH"]),
            _action(2, "pair", ["J", "J"], ["JH", "JH"]),
            _action(3, "single", ["6"], ["6S"]),
        ]
        result = strictly_better_free_lead_action_ids(_observation(["JH", "JH", "6S"]), actions, 1, 1)
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
                self.assertIsNone(strictly_better_free_lead_action_ids(payload, legal_actions, 1, 3))

    def test_selected_action_must_be_an_original_action_id(self) -> None:
        self.assertIsNone(
            strictly_better_free_lead_action_ids(
                _observation(["6S", "7S", "JH", "JD"]),
                _six_seven_jack_actions(),
                1,
                999,
            )
        )


if __name__ == "__main__":
    unittest.main()
