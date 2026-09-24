from copy import deepcopy
from collections import Counter
from dataclasses import replace
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekSuggestion
from agents.game_phase import classify_game_phase
from agents.action_structure import representative_candidate_contrasts, summarize_candidate_structures
from agents.hand_evaluator import evaluate_hand
from agents.opening_strategy import OpeningFormulaStrategy, normalize_hand_strength
from engine.game import GuanDanGame


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
        "carrier_cards": carrier_cards if carrier_cards is not None else list(declared_cards),
        "wildcard_count": wildcard_count,
        "wildcard_info": wildcard_info or [],
        "display_text": f"{pattern}:{','.join(declared_cards)}" if declared_cards else "pass",
    }


def _observation(
    hand_cards: list[object],
    *,
    constraint: str = "free",
    table_action: dict[str, object] | None = None,
) -> dict[str, object]:
    if constraint != "free" and table_action is None:
        table_action = _action(99, "single", ["8"], ["8S"])
    return {
        "my_info": {
            "player_id": 1,
            "team": "team_13",
            "hand_cards": hand_cards,
            "hand_count": len(hand_cards),
            "remaining_single_card_count": 2,
        },
        "current_round": {
            "step_no": 0,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": constraint,
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "team_13", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "team_24", "hand_count": 20, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _strong_fixture() -> tuple[dict[str, object], list[dict[str, object]]]:
    observation = _observation(
        ["4S", "QS", "QH", "AS", "AH", "SJ", "7S", "7H", "7C"]
        + ["6H", "6C", "6D", "8S", "8H", "8C", "8D", "9S", "9H", "10S", "10H"]
    )
    actions = [
        _action(11, "single", ["Q"], ["QS"]),
        _action(7, "single", ["4"], ["4S"]),
        _action(13, "single", ["A"], ["AS"]),
        _action(14, "single", ["SJ"], ["SJ"]),
        _action(20, "pair", ["A", "A"], ["AS", "AH"]),
        _action(21, "triple", ["7", "7", "7"], ["7S", "7H", "7C"]),
    ]
    return observation, actions


class RecordingClient:
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self.calls = 0

    def suggest_action_id(self, **_kwargs):
        self.calls += 1
        return DeepSeekSuggestion(action_id=self.action_id, reasoning="test")


class RecordingRAGAdvisor:
    def __init__(self) -> None:
        self.calls = 0

    def get_rag_context(self, **_kwargs):
        self.calls += 1
        return {"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""}


def _public_formula_target_id(
    observation: dict[str, object], actions: list[dict[str, object]]
) -> int | None:
    """Mirror only the public target predicate for a multi-seed conflict assertion."""

    my_info = observation["my_info"]
    round_context = observation["current_round"]
    assert isinstance(my_info, dict) and isinstance(round_context, dict)
    hand = Counter(
        card if card in {"SJ", "BJ"} else str(card)[:-1]
        for card in my_info["hand_cards"]
    )
    rank_order = {rank: index for index, rank in enumerate(("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"), start=3)}
    level_rank = str(round_context["current_level_rank"])
    structured = {
        card
        for action in actions
        if action["wildcard_count"] == 0 and len(action["carrier_cards"]) > 1
        for card in action["carrier_cards"]
    }
    safe: list[tuple[int, int]] = []
    for action in actions:
        carrier = action["carrier_cards"]
        declared = action["declared_cards"]
        if action["declared_pattern"] != "single" or action["wildcard_count"] != 0 or len(carrier) != 1 or len(declared) != 1:
            continue
        token = str(carrier[0])
        rank = token if token in {"SJ", "BJ"} else token[:-1]
        declared_rank = str(declared[0])
        declared_rank = declared_rank if declared_rank in rank_order else declared_rank[:-1]
        if (
            declared_rank == rank and rank not in {"A", "2", "SJ", "BJ"}
            and rank != level_rank and hand.get(rank) == 1 and token not in structured
        ):
            safe.append((rank_order[rank], int(action["action_id"])))
    if not safe:
        return None
    lowest = min(rank for rank, _ in safe)
    targets = [action_id for rank, action_id in safe if rank == lowest]
    return targets[0] if len(targets) == 1 else None


class TestOpeningFormulaStrategy(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = OpeningFormulaStrategy()

    def test_normalize_hand_strength_preserves_public_mapping(self) -> None:
        self.assertEqual(normalize_hand_strength({"label": "极强"}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "中等"}), "medium")
        self.assertEqual(normalize_hand_strength({"label": "偏弱"}), "weak")
        self.assertEqual(normalize_hand_strength({"label": "", "total_score": 65}), "strong")
        self.assertEqual(normalize_hand_strength({"label": "", "total_score": 19}), "weak")
        self.assertEqual(normalize_hand_strength(None), "medium")

    def test_strong_opening_with_group_vs_single_conflict_is_left_to_model(self) -> None:
        observation, actions = _strong_fixture()
        before = (deepcopy(observation), deepcopy(actions))

        chosen = self.strategy.select_action(
            observation,
            actions,
            {"label": "strong", "control_score": 24},
            classify_game_phase(observation),
        )

        self.assertIsNone(chosen)
        self.assertEqual((observation, actions), before)

    def test_full_engine_openings_keep_formula_live_only_when_relations_do_not_touch_target(self) -> None:
        direct_count = 0
        relevant_conflict_count = 0
        unrelated_relation_count = 0
        state_count = 200
        for seed in range(state_count):
            game = GuanDanGame(seed=seed, current_level_rank="2")
            observation = game.reset()
            actions = game.legal_actions()
            my_info = observation["my_info"]
            other_players = observation["other_players"]
            current_round = observation["current_round"]
            assert isinstance(my_info, dict) and isinstance(other_players, list)
            assert isinstance(current_round, dict)
            player_hand_counts = [int(my_info["hand_count"])] + [
                int(player["hand_count"]) for player in other_players
            ]
            self.assertEqual(player_hand_counts, [27, 27, 27, 27])
            self.assertEqual(sum(player_hand_counts), 108)
            self.assertEqual(current_round["step_no"], 0)
            hand_eval = evaluate_hand(observation, actions)
            if normalize_hand_strength(hand_eval) != "strong":
                continue
            facts = summarize_candidate_structures(observation, actions)
            contrasts = representative_candidate_contrasts(observation, actions)
            self.assertIsNotNone(facts)
            self.assertIsNotNone(contrasts)
            assert facts is not None and contrasts is not None
            target_id = _public_formula_target_id(observation, actions)
            if target_id is None or any(fact.finishes_hand for fact in facts):
                continue
            if self.strategy._has_public_urgency(observation) or not self.strategy._has_return_resource(observation, actions):
                continue
            target_is_in_visible_relation = any(target_id in contrast.action_ids for contrast in contrasts)
            selected = self.strategy.select_action(observation, actions, hand_eval)
            if target_is_in_visible_relation:
                relevant_conflict_count += 1
                self.assertIsNone(selected)
            else:
                self.assertTrue(contrasts)
                unrelated_relation_count += 1
                self.assertEqual(selected, target_id)
                direct_count += 1
                self.assertFalse(any(selected in contrast.action_ids for contrast in contrasts))

        self.assertGreater(direct_count, 0)
        self.assertGreater(relevant_conflict_count, 0)
        self.assertGreater(unrelated_relation_count, 0)

    def test_joker_level_wildcard_and_partial_groups_are_not_formula_targets(self) -> None:
        observation = _observation(["4S", "4H", "QS", "2S", "2H", "SJ"])
        actions = [
            _action(1, "single", ["4"], ["4S"]),
            _action(2, "single", ["Q"], ["QS"]),
            _action(3, "single", ["2"], ["2S"]),
            _action(4, "single", ["SJ"], ["SJ"]),
            _action(5, "single", ["8"], ["2H"], wildcard_count=1, wildcard_info=[{"carrier_card": "2H", "declared_as": "8S"}]),
        ]

        self.assertIsNone(
            self.strategy.select_action(observation, actions, {"label": "strong", "control_score": 24})
        )

    def test_wildcard_tradeoff_is_left_to_model_before_path(self) -> None:
        observation, actions = _strong_fixture()
        observation["my_info"]["hand_cards"].extend(["2H", "2H"])
        observation["my_info"]["hand_count"] += 2
        actions.append(
            _action(
                30,
                "pair",
                ["8", "8"],
                ["2H", "2H"],
                wildcard_count=2,
                wildcard_info=[
                    {"carrier_card": "2H", "declared_as": "8S"},
                    {"carrier_card": "2H", "declared_as": "8H"},
                ],
            )
        )
        actions.append(_action(31, "pair", ["8", "8"], ["8S", "8H"]))

        self.assertIsNone(
            self.strategy.select_action(observation, actions, {"label": "strong", "control_score": 24})
        )

    def test_single_used_by_natural_sequence_is_not_formula_target(self) -> None:
        observation = _observation(
            ["3S", "4H", "5C", "6D", "7S", "QS", "KS", "SJ"]
            + ["8S", "8H", "9S", "9H", "10S", "10H", "JS", "JH", "AS", "AH", "2S", "2C"]
        )
        actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["Q"], ["QS"]),
            _action(3, "single", ["K"], ["KS"]),
            _action(4, "single", ["SJ"], ["SJ"]),
            _action(5, "straight", ["3", "4", "5", "6", "7"], ["3S", "4H", "5C", "6D", "7S"]),
        ]

        self.assertIsNone(
            self.strategy.select_action(observation, actions, {"label": "strong", "control_score": 24})
        )
        actions = [action for action in actions if action["action_id"] != 3]
        # Removing one alternative still leaves a public low-cost-vs-sequence
        # role conflict; the new C-tier soft comparison is model-before only.
        self.assertIsNone(
            self.strategy.select_action(observation, actions, {"label": "strong", "control_score": 24}),
        )

    def test_medium_weak_or_missing_return_resource_is_not_formulaized(self) -> None:
        observation, actions = _strong_fixture()
        self.assertIsNone(self.strategy.select_action(observation, actions, {"label": "medium", "control_score": 10}))
        self.assertIsNone(self.strategy.select_action(observation, actions, {"label": "medium", "control_score": 30}))
        self.assertIsNone(self.strategy.select_action(observation, actions, {"label": "weak", "control_score": 2}))

        no_return = _observation(["4S", "QS", "7S", "7H"])
        no_return_actions = [
            _action(1, "single", ["4"], ["4S"]),
            _action(2, "single", ["Q"], ["QS"]),
            _action(3, "pair", ["7", "7"], ["7S", "7H"]),
        ]
        self.assertIsNone(
            self.strategy.select_action(no_return, no_return_actions, {"label": "strong", "control_score": 24})
        )

    def test_follow_only_pass_and_phase_mismatch_return_none(self) -> None:
        observation, actions = _strong_fixture()
        follow = deepcopy(observation)
        follow["current_round"]["constraint"] = "single:8"
        follow["current_round"]["table_action"] = _action(99, "single", ["8"], ["8S"])
        self.assertIsNone(self.strategy.select_action(follow, actions, {"label": "strong", "control_score": 24}))
        self.assertIsNone(self.strategy.select_action(observation, [_action(1, "pass", [], [])], {"label": "strong"}))

        inconsistent_phase = replace(classify_game_phase(observation), phase="midgame")
        self.assertIsNone(
            self.strategy.select_action(observation, actions, {"label": "strong", "control_score": 24}, inconsistent_phase)
        )

    def test_malformed_public_payloads_fail_closed(self) -> None:
        observation, actions = _strong_fixture()
        mutations: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        bad_hand = deepcopy(observation)
        bad_hand["my_info"]["hand_cards"][0] = "ZZ"
        mutations.append((bad_hand, deepcopy(actions)))
        bad_count = deepcopy(observation)
        bad_count["my_info"]["hand_count"] = 99
        mutations.append((bad_count, deepcopy(actions)))
        bad_carrier = deepcopy(actions)
        bad_carrier[0]["carrier_cards"] = ["KD"]
        mutations.append((deepcopy(observation), bad_carrier))
        duplicate_id = deepcopy(actions)
        duplicate_id[1]["action_id"] = duplicate_id[0]["action_id"]
        mutations.append((deepcopy(observation), duplicate_id))
        non_integer_id = deepcopy(actions)
        non_integer_id[0]["action_id"] = "11"
        mutations.append((deepcopy(observation), non_integer_id))
        unknown_pattern = deepcopy(actions)
        unknown_pattern[0]["declared_pattern"] = "mystery"
        mutations.append((deepcopy(observation), unknown_pattern))
        mismatched_declared = deepcopy(actions)
        mismatched_declared[0]["declared_cards"] = ["4", "4"]
        mutations.append((deepcopy(observation), mismatched_declared))
        malformed_wildcard_info = deepcopy(actions)
        malformed_wildcard_info[0]["wildcard_count"] = 1
        malformed_wildcard_info[0]["wildcard_info"] = ["not-a-mapping"]
        mutations.append((deepcopy(observation), malformed_wildcard_info))
        blank_display = deepcopy(actions)
        blank_display[0]["display_text"] = ""
        mutations.append((deepcopy(observation), blank_display))

        for bad_observation, bad_actions in mutations:
            with self.subTest(payload=(bad_observation, bad_actions)):
                self.assertIsNone(
                    self.strategy.select_action(
                        bad_observation,
                        bad_actions,
                        {"label": "strong", "control_score": 24},
                    )
                )

    def test_finishing_shortcut_still_precedes_opening_formula(self) -> None:
        observation = _observation(["7S", "7H"])
        actions = [
            _action(1, "single", ["7"], ["7S"]),
            _action(9, "pair", ["7", "7"], ["7S", "7H"]),
        ]
        client = RecordingClient(1)
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=RecordingRAGAdvisor(),
            hand_evaluation_enabled=False,
            opening_formula_enabled=True,
        )

        self.assertEqual(agent.select_action(observation, actions), 9)
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(client.calls, 0)

    def test_ambiguous_opening_flows_through_rag_and_preserves_model_action(self) -> None:
        observation = _observation(["4S", "QS", "7S", "7H"])
        actions = [
            _action(1, "single", ["4"], ["4S"]),
            _action(2, "single", ["Q"], ["QS"]),
            _action(3, "pair", ["7", "7"], ["7S", "7H"]),
        ]
        client = RecordingClient(2)
        rag = RecordingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=True,
            opening_formula_enabled=True,
        )

        with mock.patch("agents.deepseek_ai.evaluate_hand", return_value={"label": "medium", "control_score": 5}):
            chosen = agent.select_action(observation, actions)

        self.assertEqual(chosen, 2)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertEqual(client.calls, 1)
        self.assertEqual(rag.calls, 1)


if __name__ == "__main__":
    unittest.main()
