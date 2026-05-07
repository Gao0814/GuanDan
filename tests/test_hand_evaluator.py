import unittest

from agents.deepseek_client import DeepSeekClient
from agents.hand_evaluator import evaluate_hand


def _observation(
    *,
    hand_cards: list[str],
    remaining_single_card_count: int,
    current_level_rank: str = "2",
) -> dict[str, object]:
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": hand_cards,
            "hand_count": len(hand_cards),
            "remaining_single_card_count": remaining_single_card_count,
        },
        "current_round": {
            "step_no": 0,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": current_level_rank,
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 8, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 8, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 8, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _legal_actions(pattern_counts: list[tuple[str, int]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    action_id = 1
    for pattern, count in pattern_counts:
        for index in range(count):
            if pattern == "single":
                declared_cards = [f"{3 + index}"]
            elif pattern == "pair":
                declared_cards = [f"{4 + index}", f"{4 + index}"]
            elif pattern == "straight":
                start = 3 + index
                declared_cards = [str(rank) for rank in range(start, start + 5)]
            elif pattern == "pair_straight":
                start = 3 + index
                declared_cards = [str(rank) for rank in (start, start, start + 1, start + 1, start + 2, start + 2)]
            elif pattern == "triple_with_pair":
                start = 6 + index
                declared_cards = [str(start)] * 3 + [str(start + 1)] * 2
            elif pattern == "steel_plate":
                start = 7 + index
                declared_cards = [str(start)] * 3 + [str(start + 1)] * 3
            elif pattern == "bomb":
                declared_cards = [str(8 + index)] * 4
            elif pattern == "straight_flush":
                start = 10 + index
                declared_cards = [f"{rank}H" for rank in range(start, start + 5)]
            elif pattern == "joker_bomb":
                declared_cards = ["SJ", "SJ", "BJ", "BJ"]
            elif pattern == "pass":
                declared_cards = []
            else:
                declared_cards = ["3"]

            actions.append(
                {
                    "action_id": action_id,
                    "declared_pattern": pattern,
                    "declared_cards": declared_cards,
                    "carrier_cards": list(declared_cards),
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            )
            action_id += 1
    return actions


class TestHandEvaluator(unittest.TestCase):
    def test_strong_hand_scores_high_and_is_labeled_extremely_strong(self) -> None:
        observation = _observation(
            hand_cards=[
                "3S", "3H", "3C", "3D",
                "4S", "4H", "4C", "4D",
                "5S", "5H", "5C", "5D",
                "6S", "6H", "6C", "6D",
                "7S", "7H", "7C", "7D",
                "AH", "AS", "SJ", "BJ", "2S", "2H", "2C",
            ],
            remaining_single_card_count=1,
            current_level_rank="2",
        )
        legal_actions = _legal_actions(
            [
                ("steel_plate", 2),
                ("straight", 2),
                ("pair_straight", 2),
                ("triple_with_pair", 2),
                ("bomb", 1),
                ("straight_flush", 1),
                ("single", 2),
            ]
        )

        result = evaluate_hand(observation, legal_actions)

        self.assertGreaterEqual(int(result["total_score"]), 80)
        self.assertEqual(result["label"], "极强")
        self.assertIn("炸弹", str(result["comment"]))

    def test_medium_hand_scores_in_middle_band_and_is_labeled_medium(self) -> None:
        observation = _observation(
            hand_cards=[
                "3S", "4S", "5S", "6S", "7S",
                "8H", "9H", "10H", "JH", "QH",
                "KH", "AH", "2S", "2C", "2D",
                "9S", "9C", "9D", "10S", "10C",
                "5H", "5C", "6H", "6C", "4H", "7H", "8S",
            ],
            remaining_single_card_count=5,
            current_level_rank="2",
        )
        legal_actions = _legal_actions(
            [
                ("single", 2),
                ("pair", 2),
                ("straight", 2),
                ("triple_with_pair", 1),
            ]
        )

        result = evaluate_hand(observation, legal_actions)

        self.assertGreaterEqual(int(result["total_score"]), 40)
        self.assertLessEqual(int(result["total_score"]), 59)
        self.assertEqual(result["label"], "中等")

    def test_weak_hand_scores_low_and_is_labeled_very_weak(self) -> None:
        observation = _observation(
            hand_cards=[
                "3S", "4S", "5S", "6S", "7S",
                "8S", "9S", "10S", "JS", "QS",
                "KS", "3H", "4H", "5H", "6H",
                "7H", "8H", "9H", "10H", "JH",
                "QH", "KH", "3C", "4C", "5C", "6C", "7C",
            ],
            remaining_single_card_count=9,
            current_level_rank="2",
        )
        legal_actions = _legal_actions(
            [
                ("single", 2),
                ("pair", 1),
            ]
        )

        result = evaluate_hand(observation, legal_actions)

        self.assertLess(int(result["total_score"]), 20)
        self.assertEqual(result["label"], "极弱")
        self.assertIn("散牌", str(result["comment"]))

    def test_prompt_includes_hand_score_line_when_provided(self) -> None:
        observation = _observation(
            hand_cards=["BJ", "SJ", "2H", "3S", "4S", "5S", "6S", "7S", "8H"],
            remaining_single_card_count=5,
            current_level_rank="2",
        )
        legal_actions = [
            {
                "action_id": 1,
                "declared_pattern": "straight_flush",
                "declared_cards": ["3", "4", "5", "6", "7"],
                "carrier_cards": ["3S", "4S", "5S", "6S", "7S"],
                "wildcard_count": 0,
                "wildcard_info": [],
            },
            {
                "action_id": 2,
                "declared_pattern": "straight",
                "declared_cards": ["8", "9", "10", "J", "Q"],
                "carrier_cards": ["8S", "9S", "10S", "JS", "2H"],
                "wildcard_count": 1,
                "wildcard_info": [{"carrier_card": "2H", "declared_as": "Q"}],
            },
            {
                "action_id": 3,
                "declared_pattern": "joker_bomb",
                "declared_cards": ["SJ", "SJ", "BJ", "BJ"],
                "carrier_cards": ["SJ", "SJ", "BJ", "BJ"],
                "wildcard_count": 0,
                "wildcard_info": [],
            },
        ]
        hand_evaluation = evaluate_hand(observation, legal_actions)

        prompt = DeepSeekClient._build_structured_prompt(  # noqa: SLF001 - direct prompt regression test
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=legal_actions,
            hand_evaluation=hand_evaluation,
        )

        self.assertIn("【我的手牌】", prompt)
        self.assertIn("手牌评分：", prompt)
        self.assertIn(f"{hand_evaluation['total_score']}（{hand_evaluation['label']}）", prompt)
        self.assertIn("大王", prompt)
        self.assertIn("小王", prompt)
        self.assertIn("♥2(逢人配)", prompt)
        self.assertIn("♠3♠4♠5♠6♠7", prompt)
        self.assertIn("同花顺", prompt)
        self.assertNotIn("BJ", prompt)
        self.assertNotIn("SJ", prompt)


if __name__ == "__main__":
    unittest.main()