"""Tests for Step J-C2a public behaviour-event extraction."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
import unittest

from agents.card_belief import build_card_belief
from agents.card_signals import build_public_signal_state


def _action(
    player_id: int,
    pattern: str,
    *,
    step_no: object = 1,
    round_no: object = 1,
    declared_cards: object = None,
    carrier_cards: object = None,
) -> dict[str, object]:
    action: dict[str, object] = {
        "step_no": step_no,
        "round_no": round_no,
        "player_id": player_id,
        "declared_pattern": pattern,
    }
    if declared_cards is not None:
        action["declared_cards"] = declared_cards
    if carrier_cards is not None:
        action["carrier_cards"] = carrier_cards
    return action


def _observation(
    actions: object = None,
    *,
    my_level: object = "5",
    round_level: object = "5",
) -> dict[str, object]:
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": [],
            "hand_count": 0,
            "current_level_rank": my_level,
        },
        "current_round": {"step_no": 0, "current_level_rank": round_level},
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 30, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 30, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 30, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [] if actions is None else actions, "finish_order": []},
    }


def _state(observation: dict[str, object]):
    return build_public_signal_state(observation, build_card_belief(observation))


def _profile(state, player_id: int):
    return next(player for player in state.players if player.player_id == player_id)


class CardSignalsTests(unittest.TestCase):
    def test_lead_follow_and_pass_response_chain(self) -> None:
        state = _state(_observation([
            _action(2, "single", step_no=1, declared_cards=["3"], carrier_cards=["3S"]),
            _action(3, "pass", step_no=2),
            _action(4, "pair", step_no=3, declared_cards=["4", "4"], carrier_cards=["4S", "4H"]),
            _action(2, "pass", step_no=4),
            _action(3, "pass", step_no=5),
        ]))

        self.assertEqual([event.event_type for event in state.events], ["lead", "pass", "follow", "pass", "pass"])
        self.assertEqual([event.response_to_action_index for event in state.events], [None, 0, 0, 2, 2])

    def test_new_round_and_orphan_pass_clear_context(self) -> None:
        state = _state(_observation([
            _action(2, "single", round_no=1, carrier_cards=["3S"]),
            _action(3, "pass", round_no=2),
            _action(4, "single", round_no=2, carrier_cards=["4S"]),
        ]))

        self.assertEqual(state.events[1].response_to_action_index, None)
        self.assertEqual(state.events[2].event_type, "lead")
        self.assertIn("orphan_pass", state.diagnostics)

    def test_invalid_round_is_independent_and_round_regression_resets(self) -> None:
        state = _state(_observation([
            _action(2, "single", round_no=2, carrier_cards=["3S"]),
            _action(3, "single", round_no=True, carrier_cards=["4S"]),
            _action(4, "single", round_no=1, carrier_cards=["5S"]),
        ]))

        self.assertEqual(state.events[1].event_type, "lead")
        self.assertIsNone(state.events[1].response_to_action_index)
        self.assertEqual(state.events[2].event_type, "lead")
        self.assertIn("invalid_round_no", state.diagnostics)
        self.assertIn("round_regression", state.diagnostics)

    def test_bad_history_records_do_not_change_original_action_indexes(self) -> None:
        observation = _observation([
            "not-an-action",
            _action(2, "single", step_no="bad", carrier_cards=["3S"]),
        ])
        state = _state(observation)

        self.assertEqual(len(state.events), 1)
        self.assertEqual(state.events[0].action_index, 1)
        self.assertIsNone(state.events[0].step_no)
        self.assertIn("malformed_action", state.diagnostics)
        self.assertIn("invalid_step_no", state.diagnostics)

    def test_declared_and_carrier_cards_stay_separate_with_public_difference(self) -> None:
        state = _state(_observation([
            _action(2, "single", declared_cards=["J"], carrier_cards=["2H"]),
        ]))
        event = state.events[0]

        self.assertEqual(event.declared_cards, ("J",))
        self.assertEqual(event.carrier_cards, ("2H",))
        self.assertEqual(event.declared_ranks, ("J",))
        self.assertEqual(event.carrier_ranks, ("2",))
        self.assertTrue(event.declaration_differs_from_carrier)
        self.assertNotIn("possible_owners", event.to_dict())

    def test_high_value_releases_use_only_carrier_ranks(self) -> None:
        state = _state(_observation([
            _action(
                2,
                "bomb",
                declared_cards=["3", "3", "3", "3", "3"],
                carrier_cards=["AH", "2S", "SJ", "BJ", "5D"],
            ),
        ]))
        profile = _profile(state, 2)

        self.assertEqual(dict(profile.released_high_value_counts), {"A": 1, "2": 1, "SJ": 1, "BJ": 1, "5": 1})

    def test_level_rank_fallback_mismatch_and_invalid_value(self) -> None:
        observation = _observation([], my_level=None, round_level="6")
        del observation["my_info"]["current_level_rank"]  # type: ignore[index]
        self.assertEqual(_state(observation).current_level_rank, "6")

        mismatched = _state(_observation([], my_level="6", round_level="5"))
        self.assertEqual(mismatched.current_level_rank, "6")
        self.assertIn("level_rank_mismatch", mismatched.diagnostics)

        invalid = _state(_observation([], my_level="X", round_level="5"))
        self.assertIsNone(invalid.current_level_rank)
        self.assertIn("invalid_level_rank", invalid.diagnostics)

    def test_pass_with_cards_and_empty_or_missing_carrier_are_diagnosed(self) -> None:
        state = _state(_observation([
            _action(2, "pass", declared_cards=["A"], carrier_cards=["AS"]),
            _action(3, "single", carrier_cards=[]),
            _action(4, "single"),
        ]))

        self.assertEqual(state.events[0].event_type, "pass")
        self.assertIn("pass_with_cards", state.diagnostics)
        self.assertIn("empty_carrier_cards", state.diagnostics)
        self.assertIn("missing_carrier_cards", state.diagnostics)

    def test_unknown_player_tokens_and_malformed_card_fields_are_diagnosed(self) -> None:
        state = _state(_observation([
            _action(99, "single", declared_cards=["XX"], carrier_cards=["YY"]),
            _action(2, "single", declared_cards="not-a-list", carrier_cards="not-a-list"),
        ]))

        self.assertEqual(state.events[0].relation, "unknown")
        self.assertIn("unknown_player", state.diagnostics)
        self.assertIn("unknown_declared_token", state.diagnostics)
        self.assertIn("unknown_carrier_token", state.diagnostics)
        self.assertIn("malformed_declared_cards", state.diagnostics)
        self.assertIn("malformed_carrier_cards", state.diagnostics)

    def test_profiles_aggregate_actions_patterns_and_passes(self) -> None:
        state = _state(_observation([
            _action(2, "single", carrier_cards=["3S"]),
            _action(3, "pass"),
            _action(2, "pair", carrier_cards=["4S", "4H"]),
            _action(2, "pass"),
        ]))
        player_two = _profile(state, 2)
        player_three = _profile(state, 3)

        self.assertEqual((player_two.action_count, player_two.lead_count, player_two.follow_count, player_two.pass_count), (3, 1, 1, 1))
        self.assertEqual(dict(player_two.pattern_counts), {"single": 1, "pair": 1})
        self.assertEqual(player_three.pass_count, 1)

    def test_j_a_pass_and_played_card_mismatches_are_reported(self) -> None:
        observation = _observation([
            _action(2, "single", carrier_cards=["3S"]),
            _action(2, "pass"),
        ])
        belief = build_card_belief(observation)
        altered_players = tuple(
            replace(player, pass_count=0, played_cards=())
            if player.player_id == 2 else player
            for player in belief.players
        )
        state = build_public_signal_state(
            observation,
            replace(belief, players=altered_players),
        )

        self.assertIn("belief_pass_mismatch", state.diagnostics)
        self.assertIn("belief_played_cards_mismatch", state.diagnostics)

    def test_malformed_history_actions_does_not_create_events(self) -> None:
        observation = _observation("bad-actions")
        state = _state(observation)

        self.assertEqual(state.events, ())
        self.assertIn("malformed_history_actions", state.diagnostics)

    def test_public_output_is_serializable_immutable_and_does_not_leak_inference_fields(self) -> None:
        observation = _observation([_action(2, "single", carrier_cards=["3S"])])
        belief = build_card_belief(observation)
        before_observation = json.loads(json.dumps(observation))
        before_belief = belief.to_dict()
        state = build_public_signal_state(observation, belief)
        payload = state.to_dict()
        serialized = json.dumps(payload)

        for forbidden in ("possible", "likely", "confirmed", "score", "probability", "confidence"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(FrozenInstanceError):
            state.phase = "opening"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            state.players[0].pattern_counts["x"] = 1  # type: ignore[index]
        self.assertEqual(observation, before_observation)
        self.assertEqual(belief.to_dict(), before_belief)

    def test_fixed_input_build_is_deterministic(self) -> None:
        observation = _observation([
            _action(2, "single", carrier_cards=["3S"]),
            _action(3, "pass"),
        ])
        belief = build_card_belief(observation)

        self.assertEqual(
            build_public_signal_state(observation, belief),
            build_public_signal_state(observation, belief),
        )


if __name__ == "__main__":
    unittest.main()
