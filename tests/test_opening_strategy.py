import unittest

from agents.deepseek_ai import DeepSeekAIAgent
from agents.opening_strategy import OpeningFormulaStrategy, normalize_hand_strength


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


if __name__ == "__main__":
    unittest.main()
