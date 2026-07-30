import json
import unittest

from agents.card_belief import build_card_belief


def _action(
    player_id: int,
    pattern: str,
    *,
    carrier_cards: list[str] | None = None,
    declared_cards: list[str] | None = None,
) -> dict[str, object]:
    action: dict[str, object] = {
        "player_id": player_id,
        "declared_pattern": pattern,
    }
    if carrier_cards is not None:
        action["carrier_cards"] = carrier_cards
    if declared_cards is not None:
        action["declared_cards"] = declared_cards
    return action


def _observation(
    *,
    my_cards: list[str] | None = None,
    other_counts: tuple[int, int, int] = (36, 36, 36),
    history_actions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    cards = [] if my_cards is None else my_cards
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": cards,
            "hand_count": len(cards),
        },
        "current_round": {"step_no": len(history_actions or [])},
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": other_counts[0], "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": other_counts[1], "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": other_counts[2], "finished": False, "finish_rank": None},
        ],
        "history": {"actions": history_actions or [], "finish_order": []},
    }


def _player(state, player_id: int):
    return next(player for player in state.players if player.player_id == player_id)


class TestCardBelief(unittest.TestCase):
    def test_base_pool_has_108_cards(self) -> None:
        state = build_card_belief(_observation())
        self.assertEqual(sum(state.unseen_cards_by_token.values()), 108)
        self.assertEqual(sum(state.unseen_cards_by_rank.values()), 108)

    def test_normal_tokens_and_jokers_each_have_two_copies(self) -> None:
        state = build_card_belief(_observation())
        self.assertEqual(state.unseen_cards_by_token["3S"], 2)
        self.assertEqual(state.unseen_cards_by_token["10H"], 2)
        self.assertEqual(state.unseen_cards_by_token["SJ"], 2)
        self.assertEqual(state.unseen_cards_by_token["BJ"], 2)

    def test_my_hand_is_deducted_from_exact_pool(self) -> None:
        state = build_card_belief(_observation(my_cards=["3S", "3S"], other_counts=(35, 35, 36)))
        self.assertEqual(state.unseen_cards_by_token["3S"], 0)
        self.assertEqual(state.unseen_cards_by_rank["3"], 6)
        self.assertNotIn("external_count_mismatch", " ".join(state.diagnostics))

    def test_history_carrier_cards_are_deducted(self) -> None:
        history = [_action(2, "single", carrier_cards=["4H"], declared_cards=["4"])]
        state = build_card_belief(_observation(other_counts=(35, 35, 35), history_actions=history))
        self.assertEqual(state.unseen_cards_by_token["4H"], 1)
        self.assertEqual(state.unseen_cards_by_rank["4"], 7)

    def test_wildcard_history_deducts_real_carrier_not_declared_as(self) -> None:
        history = [_action(2, "single", carrier_cards=["2H"], declared_cards=["J"])]
        state = build_card_belief(_observation(other_counts=(35, 36, 36), history_actions=history))
        self.assertEqual(state.unseen_cards_by_token["2H"], 1)
        self.assertEqual(state.unseen_cards_by_rank["J"], 8)

    def test_played_cards_are_recorded_by_player_id(self) -> None:
        history = [_action(2, "pair", carrier_cards=["4S", "4H"])]
        state = build_card_belief(_observation(other_counts=(35, 35, 36), history_actions=history))
        self.assertEqual(_player(state, 2).played_cards, ("4S", "4H"))

    def test_pass_only_increments_pass_count(self) -> None:
        state = build_card_belief(_observation(history_actions=[_action(3, "pass")]))
        player = _player(state, 3)
        self.assertEqual(player.pass_count, 1)
        self.assertEqual(player.played_cards, ())
        self.assertEqual(sum(state.unseen_cards_by_rank.values()), 108)

    def test_other_remaining_counts_are_public_facts(self) -> None:
        state = build_card_belief(_observation(other_counts=(40, 30, 38)))
        self.assertEqual(_player(state, 2).remaining_count, 40)
        self.assertEqual(_player(state, 3).remaining_count, 30)
        self.assertEqual(_player(state, 4).remaining_count, 38)

    def test_legacy_declared_cards_fallback_is_used_when_carrier_is_missing(self) -> None:
        history = [_action(2, "pair", declared_cards=["AS", "AH"])]
        state = build_card_belief(_observation(other_counts=(35, 35, 36), history_actions=history))
        self.assertEqual(state.unseen_cards_by_token["AS"], 1)
        self.assertEqual(state.unseen_cards_by_token["AH"], 1)
        self.assertTrue(any(item.startswith("legacy_declared_cards") for item in state.diagnostics))

    def test_rank_only_legacy_fallback_marks_token_pool_inexact(self) -> None:
        history = [_action(2, "single", declared_cards=["A"])]
        state = build_card_belief(_observation(other_counts=(35, 36, 36), history_actions=history))
        self.assertFalse(state.token_pool_exact)
        self.assertEqual(state.unseen_cards_by_rank["A"], 7)
        self.assertEqual(state.unseen_cards_by_token["AS"], 2)
        self.assertTrue(any(item.startswith("rank_only_fallback") for item in state.diagnostics))

    def test_overdraw_diagnostic_never_creates_negative_counts(self) -> None:
        history = [_action(2, "single", carrier_cards=["3S"]) for _ in range(3)]
        state = build_card_belief(_observation(other_counts=(35, 35, 35), history_actions=history))
        self.assertEqual(state.unseen_cards_by_token["3S"], 0)
        self.assertFalse(state.token_pool_exact)
        self.assertGreaterEqual(min(state.unseen_cards_by_token.values()), 0)
        self.assertTrue(any(item.startswith("overdraw") for item in state.diagnostics))

    def test_unknown_token_creates_diagnostic(self) -> None:
        history = [_action(2, "single", carrier_cards=["XX"])]
        state = build_card_belief(_observation(other_counts=(35, 36, 36), history_actions=history))
        self.assertFalse(state.token_pool_exact)
        self.assertTrue(any(item.startswith("unknown_token") for item in state.diagnostics))

    def test_external_capacity_mismatch_creates_diagnostic(self) -> None:
        state = build_card_belief(_observation(other_counts=(20, 20, 20)))
        self.assertTrue(any(item.startswith("external_count_mismatch") for item in state.diagnostics))

    def test_to_dict_is_json_serializable(self) -> None:
        state = build_card_belief(_observation())
        payload = json.loads(json.dumps(state.to_dict()))
        self.assertEqual(payload["unseen_cards_by_token"]["BJ"], 2)
        self.assertIn("players", payload)

    def test_j_a_never_confirms_or_assigns_likely_hidden_cards(self) -> None:
        state = build_card_belief(_observation(history_actions=[_action(2, "pass")]))
        for player in state.players:
            self.assertEqual(player.confirmed_cards, ())
            self.assertEqual(player.likely_ranks, ())
            self.assertEqual(player.confidence, 0)


if __name__ == "__main__":
    unittest.main()
