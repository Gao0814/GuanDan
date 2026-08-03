from copy import deepcopy
import unittest

from agents.deepseek_ai import DeepSeekAIAgent
from agents.game_phase import OPENING, classify_game_phase
from agents.hand_evaluator import evaluate_hand
from agents.opening_strategy import OpeningFormulaStrategy, _rank_of, normalize_hand_strength
from engine.cards import Card
from engine.game import GuanDanGame


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(rank=token)
    return Card(rank=token[:-1], suit=token[-1])


def _record_initial_game() -> GuanDanGame:
    player_tokens = {
        1: "3S 3H 5S 5H 5D 7S 8C 8C 8D 9C 10H 10D 10D JH JC JD QS QC KH KH AH AC AC 2S 2H 2C BJ".split(),
        2: "4S 4S 4D 5S 5C 6S 6C 6D 7C 7D 8S 9S 9H 9C 10S 10H 10C 10C JS JD QH QD KS AS AD SJ SJ".split(),
        3: "3C 3D 3D 4H 4C 5D 6H 6H 7S 7H 7C 7D 8H 8D 9D JH JC QH QC QD KC KC KD AH AD 2H 2D".split(),
        4: "3S 3H 3C 4H 4C 4D 5H 5C 6S 6C 6D 7H 8S 8H 9S 9H 9D 10S JS QS KS KD AS 2S 2C 2D BJ".split(),
    }
    return GuanDanGame(
        current_level_rank="2",
        starting_player_id=1,
        preset_hands={player_id: tuple(_card(token) for token in tokens) for player_id, tokens in player_tokens.items()},
    )


def _observation(
    *,
    hand_cards: list[str] | None = None,
    hand_count: int = 20,
    remaining_single_card_count: int = 4,
    table_action: dict[str, object] | None = None,
    constraint: str = "free",
    history_count: int = 0,
    other_hand_count: int = 20,
) -> dict[str, object]:
    cards = hand_cards or ["3S"] * hand_count
    return {
        "my_info": {
            "player_id": 1,
            "team": "team_13",
            "hand_cards": cards,
            "hand_count": hand_count,
            "remaining_single_card_count": remaining_single_card_count,
        },
        "current_round": {
            "step_no": history_count,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": constraint,
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": other_hand_count, "finished": False, "finish_rank": None},
        ],
        "history": {
            "actions": [
                {
                    "step_no": index + 1,
                    "round_no": 1,
                    "player_id": (index % 4) + 1,
                    "declared_pattern": "single",
                    "declared_cards": ["3"],
                    "carrier_cards": ["3S"],
                }
                for index in range(history_count)
            ],
            "finish_order": [],
        },
    }


def _action(
    action_id: object,
    pattern: str,
    declared_cards: list[str],
    carrier_cards: list[str] | None = None,
    *,
    wildcard_count: int = 0,
    wildcard_info: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": declared_cards,
        "carrier_cards": carrier_cards or list(declared_cards),
        "wildcard_count": wildcard_count,
        "wildcard_info": wildcard_info or [],
        "display_text": f"{pattern}:{','.join(declared_cards)}" if declared_cards else "pass",
    }


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def suggest_action_id(self, **_kwargs):
        self.calls += 1
        raise AssertionError("DeepSeek client should not be called")


class CountingRAGAdvisor:
    def __init__(self) -> None:
        self.rule_calls = 0
        self.experience_calls = 0

    def retrieve_rule_evidence(self, query: str, top_k: int = 3):
        self.rule_calls += 1
        return ()

    def retrieve_experience_evidence(self, query: str, top_k: int = 3):
        self.experience_calls += 1
        return ()


class TestOpeningFormulaStrategy(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = OpeningFormulaStrategy()

    def test_normalize_hand_strength_maps_labels_and_score_fallback(self) -> None:
        self.assertEqual(normalize_hand_strength({"label": "极强"}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "较强"}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "中等"}), "medium")
        self.assertEqual(normalize_hand_strength({"label": "偏弱"}), "weak")
        self.assertEqual(normalize_hand_strength({"label": "极弱"}), "weak")
        self.assertEqual(normalize_hand_strength({"label": "strong"}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "weak"}), "weak")
        self.assertEqual(normalize_hand_strength({"label": "", "total_score": 65}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "", "total_score": 19}), "weak")
        self.assertEqual(normalize_hand_strength(None), "medium")

    def test_non_lead_follow_context_returns_none(self) -> None:
        observation = _observation(
            table_action=_action(99, "single", ["8"], ["8S"]),
            constraint="single:8",
        )
        legal_actions = [_action(1, "pair", ["9", "9"], ["9S", "9H"])]

        self.assertIsNone(self.strategy.select_action(observation, legal_actions, {"label": "中等"}))

    def test_only_pass_is_not_handled_by_opening_strategy(self) -> None:
        observation = _observation()
        legal_actions = [_action(1, "pass", [], [])]

        self.assertIsNone(self.strategy.select_action(observation, legal_actions, {"label": "中等"}))

    def test_agent_finishing_shortcut_has_priority_over_opening_formula(self) -> None:
        observation = _observation(hand_count=20)
        legal_actions = [
            _action(1, "pair", ["7", "7"], ["7S", "7H"]),
            _action(9, "straight", ["3", "4", "5", "6", "7"], ["3S"] * 20),
        ]
        client = CountingClient()
        rag = CountingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )

        chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 9)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_strong_hand_does_not_open_with_bomb_when_safe_action_exists(self) -> None:
        observation = _observation(hand_cards=["BJ", "SJ", "AS"] + ["3S"] * 17)
        legal_actions = [
            _action(1, "bomb", ["8", "8", "8", "8"], ["8S", "8H", "8C", "8D"]),
            _action(2, "single", ["9"], ["9S"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "极强", "control_score": 24})

        self.assertEqual(chosen, 2)

    def test_strong_hand_with_joker_uses_plain_single_probe_not_joker(self) -> None:
        observation = _observation(hand_cards=["BJ", "AS"] + ["3S"] * 18)
        legal_actions = [
            _action(1, "single", ["BJ"], ["BJ"]),
            _action(2, "single", ["9"], ["9S"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "极强", "control_score": 22})

        self.assertEqual(chosen, 2)

    def test_medium_unclear_hand_prefers_pair_probe(self) -> None:
        observation = _observation()
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "pair", ["7", "7"], ["7S", "7H"]),
            _action(3, "straight", ["3", "4", "5", "6", "7"], ["3S", "4S", "5S", "6S", "7S"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "中等", "control_score": 6})

        self.assertEqual(chosen, 2)

    def test_no_joker_natural_triple_with_pair_gets_priority(self) -> None:
        observation = _observation(hand_cards=["3S"] * 20)
        legal_actions = [
            _action(1, "pair", ["7", "7"], ["7S", "7H"]),
            _action(2, "triple_with_pair", ["6", "6", "6", "9", "9"], ["6S", "6H", "6C", "9S", "9H"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "中等", "control_score": 4})

        self.assertEqual(chosen, 2)

    def test_weak_hand_avoids_obvious_low_single(self) -> None:
        observation = _observation(remaining_single_card_count=8)
        legal_actions = [
            _action(1, "single", ["4"], ["4S"]),
            _action(2, "single", ["9"], ["9S"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "偏弱", "control_score": 2})

        self.assertEqual(chosen, 2)

    def test_same_kind_prefers_lower_wildcard_count(self) -> None:
        observation = _observation()
        legal_actions = [
            _action(
                1,
                "pair",
                ["7", "7"],
                ["7S", "2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "7"}],
            ),
            _action(2, "pair", ["7", "7"], ["7S", "7H"], wildcard_count=0),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "中等", "control_score": 6})

        self.assertEqual(chosen, 2)

    def test_same_brief_different_carrier_actions_are_scored_separately(self) -> None:
        observation = _observation()
        legal_actions = [
            _action(
                1,
                "single",
                ["9"],
                ["2H"],
                wildcard_count=1,
                wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
            ),
            _action(2, "single", ["9"], ["9S"], wildcard_count=0),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "极强", "control_score": 20})

        self.assertEqual(chosen, 2)

    def test_returns_original_action_id_value_from_legal_actions(self) -> None:
        observation = _observation()
        legal_actions = [
            _action("single-raw", "single", ["9"], ["9S"]),
            _action("pair-raw", "pair", ["7", "7"], ["7S", "7H"]),
        ]

        chosen = self.strategy.select_action(observation, legal_actions, {"label": "中等", "control_score": 5})

        self.assertEqual(chosen, "pair-raw")
        self.assertIn(chosen, {action["action_id"] for action in legal_actions})

    def test_deepseek_agent_opening_formula_hit_skips_rag_and_client(self) -> None:
        observation = _observation()
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "pair", ["7", "7"], ["7S", "7H"]),
        ]
        client = CountingClient()
        rag = CountingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )

        chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 2)
        self.assertEqual(agent.last_decision_source, "local_opening_formula")
        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.rule_calls, 0)
        self.assertEqual(rag.experience_calls, 0)

    def test_record_public_fixture_prefers_natural_single_without_mutating_inputs(self) -> None:
        game = _record_initial_game()
        observation = game.reset()
        legal_actions = game.legal_actions()
        hand_eval = evaluate_hand(observation, legal_actions)
        phase = classify_game_phase(observation)
        before = (deepcopy(observation), deepcopy(legal_actions), phase, deepcopy(hand_eval))

        context = self.strategy._context(observation, legal_actions, hand_eval)
        selected_actions = {
            "K": next(action for action in legal_actions if action["carrier_cards"] == ["KH"]),
            "Q": next(action for action in legal_actions if action["carrier_cards"] == ["QS"]),
            "J": next(action for action in legal_actions if action["carrier_cards"] == ["JH"]),
            "10": next(action for action in legal_actions if action["carrier_cards"] == ["10H"]),
            "9": next(action for action in legal_actions if action["carrier_cards"] == ["9C"]),
            "steel": next(
                action
                for action in legal_actions
                if action["carrier_cards"] == ["10H", "10D", "10D", "JH", "JC", "JD"]
            ),
        }
        scores = {
            name: self.strategy._score_action(action, context, True)
            for name, action in selected_actions.items()
        }
        chosen = self.strategy.select_action(observation, legal_actions, hand_eval, phase)

        self.assertEqual(phase.phase, OPENING)
        self.assertEqual(observation["current_round"]["current_level_rank"], "2")
        self.assertEqual(observation["current_round"]["current_player_id"], 1)
        self.assertEqual(observation["my_info"]["remaining_single_card_count"], 3)
        self.assertEqual(
            {key: hand_eval[key] for key in ("total_score", "structure_score", "control_score", "potential_score")},
            {"total_score": 97, "structure_score": 40, "control_score": 27, "potential_score": 30},
        )
        self.assertEqual(hand_eval["label"], "极强")
        self.assertEqual(
            {name: scores[name] for name in ("K", "Q", "J", "10", "9", "steel")},
            {"K": 65, "Q": 65, "J": 56, "10": 55, "9": 86, "steel": 72},
        )
        self.assertEqual(selected_actions["9"]["carrier_cards"], ["9C"])
        self.assertEqual(chosen, selected_actions["9"]["action_id"])
        self.assertIn(chosen, {action["action_id"] for action in legal_actions})
        self.assertEqual((observation, legal_actions, phase, hand_eval), before)

    def test_residual_cost_protects_partial_pair_triple_and_four_plus(self) -> None:
        observation = _observation(
            hand_cards=["7S", "7H", "8S", "8H", "8C", "9S", "9H", "9C", "9D"],
            hand_count=9,
            other_hand_count=9,
        )
        actions = [
            _action(1, "single", ["7"], ["7S"]),
            _action(2, "single", ["8"], ["8S"]),
            _action(3, "single", ["9"], ["9S"]),
            _action(4, "pair", ["8", "8"], ["8S", "8H"]),
            _action(5, "triple", ["9", "9", "9"], ["9S", "9H", "9C"]),
        ]
        context = self.strategy._context(observation, actions, {"label": "medium"})

        self.assertEqual(self.strategy._residual_structure_cost(actions[0], context), 24)
        self.assertGreaterEqual(self.strategy._residual_structure_cost(actions[1], context), 32)
        self.assertGreater(self.strategy._residual_structure_cost(actions[2], context), 32)
        self.assertGreaterEqual(self.strategy._residual_structure_cost(actions[3], context), 32)
        self.assertGreater(self.strategy._residual_structure_cost(actions[4], context), 32)

        duplicate_token_observation = _observation(
            hand_cards=["6S", "6S", "9C"], hand_count=3, other_hand_count=3
        )
        duplicate_token_action = _action(6, "single", ["6"], ["6S"])
        duplicate_context = self.strategy._context(
            duplicate_token_observation, [duplicate_token_action], {"label": "medium"}
        )
        self.assertEqual(self.strategy._residual_structure_cost(duplicate_token_action, duplicate_context), 24)

    def test_residual_cost_does_not_penalize_complete_rank_consumption(self) -> None:
        observation = _observation(
            hand_cards=["7S", "7H", "8S", "8H", "8C", "10S", "SJ", "BJ"],
            hand_count=8,
            other_hand_count=8,
        )
        actions = [
            _action(1, "pair", ["7", "7"], ["7S", "7H"]),
            _action(2, "triple", ["8", "8", "8"], ["8S", "8H", "8C"]),
            _action(3, "straight", ["10", "SJ", "BJ"], ["10S", "SJ", "BJ"]),
        ]
        context = self.strategy._context(observation, actions, {"label": "medium"})

        self.assertEqual([self.strategy._residual_structure_cost(action, context) for action in actions], [0, 0, 0])
        self.assertEqual([_rank_of(token) for token in ["10S", "SJ", "BJ"]], ["10", "SJ", "BJ"])

    def test_residual_cost_uses_carriers_not_declared_cards_for_wildcards_and_composites(self) -> None:
        observation = _observation(
            hand_cards=["2S", "2H", "2C", "7S", "7H", "8S", "8H"],
            hand_count=7,
            other_hand_count=7,
        )
        action = _action(
            1,
            "triple_with_pair",
            ["9", "9", "9", "7", "7"],
            ["2S", "2H", "2C", "7S", "7H"],
            wildcard_count=3,
        )
        context = self.strategy._context(observation, [action], {"label": "medium"})

        self.assertEqual(self.strategy._residual_structure_cost(action, context), 0)

    def test_composite_partial_groups_sum_carrier_rank_costs(self) -> None:
        observation = _observation(
            hand_cards=["6S", "6H", "7S", "7H", "7C", "8S"],
            hand_count=6,
            other_hand_count=6,
        )
        action = _action(
            1,
            "straight",
            ["3", "4", "5"],
            ["6S", "7S", "8S"],
        )
        context = self.strategy._context(observation, [action], {"label": "medium"})

        self.assertEqual(self.strategy._residual_structure_cost(action, context), 24 + 32)

    def test_malformed_carriers_are_conservative_and_do_not_mutate_inputs(self) -> None:
        observation = _observation(hand_cards=["7S", "7H", "9C"], hand_count=3, other_hand_count=3)
        malformed = [
            _action(1, "single", ["7"], ["AS"]),
            _action(2, "pair", ["7", "7"], ["7S", "7S"]),
            {**_action(3, "single", ["9"], ["9C"]), "carrier_cards": "9C"},
        ]
        before = (deepcopy(observation), deepcopy(malformed))
        context = self.strategy._context(observation, malformed, {"label": "strong", "control_score": 22})

        for action in malformed:
            self.assertGreaterEqual(self.strategy._residual_structure_cost(action, context), 80)
            self.assertIsInstance(self.strategy._score_action(action, context, True), int)
        self.assertEqual((observation, malformed), before)

    def test_unknown_hand_and_carrier_tokens_fail_closed_without_mutation(self) -> None:
        invalid_tokens: list[object] = ["ZZ", "A", "10X", "", " 9C", 9, True, None]
        for token in invalid_tokens:
            with self.subTest(token=repr(token)):
                valid_observation = _observation(hand_cards=["7S", "7H", "9C"], hand_count=3, other_hand_count=3)
                invalid_hand_observation = deepcopy(valid_observation)
                invalid_hand_observation["my_info"]["hand_cards"] = ["7S", "7H", token]
                invalid_carrier_action = _action(1, "single", ["9"], ["9C"])
                invalid_carrier_action["carrier_cards"] = [token]
                both_invalid_action = deepcopy(invalid_carrier_action)
                before = (
                    deepcopy(valid_observation),
                    deepcopy(invalid_hand_observation),
                    deepcopy(invalid_carrier_action),
                    deepcopy(both_invalid_action),
                )

                valid_context = self.strategy._context(valid_observation, [invalid_carrier_action], {"label": "medium"})
                invalid_hand_context = self.strategy._context(
                    invalid_hand_observation, [invalid_carrier_action], {"label": "medium"}
                )
                both_invalid_context = self.strategy._context(
                    invalid_hand_observation, [both_invalid_action], {"label": "medium"}
                )

                self.assertEqual(self.strategy._residual_structure_cost(invalid_carrier_action, valid_context), 80)
                self.assertEqual(self.strategy._residual_structure_cost(_action(2, "single", ["9"], ["9C"]), invalid_hand_context), 80)
                self.assertEqual(self.strategy._residual_structure_cost(both_invalid_action, both_invalid_context), 80)
                self.assertIsInstance(self.strategy._score_action(invalid_carrier_action, valid_context, True), int)
                self.assertEqual(
                    (valid_observation, invalid_hand_observation, invalid_carrier_action, both_invalid_action), before
                )

    def test_identical_valid_candidates_keep_stable_action_id_tie_break(self) -> None:
        observation = _observation(hand_cards=["9S", "9H"] + ["3S"] * 18, hand_count=20, other_hand_count=20)
        legal_actions = [
            _action(9, "single", ["9"], ["9S"]),
            _action(3, "single", ["9"], ["9H"]),
        ]

        self.assertEqual(self.strategy.select_action(observation, legal_actions, {"label": "medium"}), 3)


if __name__ == "__main__":
    unittest.main()
