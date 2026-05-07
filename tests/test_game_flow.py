import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

from agents.rule_based_ai import RuleBasedAIAgent
from cli import run_4ai_debug
from engine.actions import Action, ActionType
from engine.cards import BIG_JOKER_RANK, Card
from engine.game import GuanDanGame
from engine.patterns import PatternType


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(rank=token)
    if token[-1] in {"S", "H", "C", "D"}:
        return Card(rank=token[:-1], suit=token[-1])
    return Card(rank=token)


def _hands(mapping: dict[int, tuple[str, ...]]) -> dict[int, tuple[Card, ...]]:
    return {
        player_id: tuple(_card(token) for token in tokens)
        for player_id, tokens in mapping.items()
    }


def _action_id_by_pattern(game: GuanDanGame, pattern: str, declared: tuple[str, ...]) -> int:
    for action in game.legal_actions():
        if action["declared_pattern"] != pattern:
            continue
        if tuple(action["declared_cards"]) == declared:
            return int(action["action_id"])
    raise AssertionError(f"action not found: {pattern} {declared}")


def _pass_id(game: GuanDanGame) -> int:
    for action in game.legal_actions():
        if action["declared_pattern"] == "pass":
            return int(action["action_id"])
    raise AssertionError("pass action not found")


def _table_action(
    player_id: int,
    pattern: PatternType,
    declared_tokens: tuple[str, ...],
    carrier_tokens: tuple[str, ...] | None = None,
) -> Action:
    actual_tokens = carrier_tokens or declared_tokens
    return Action(
        player_id=player_id,
        action_type=ActionType.PLAY,
        declared_pattern=pattern,
        declared_cards=tuple(_card(token) for token in declared_tokens),
        carrier_cards=tuple(_card(token) for token in actual_tokens),
        display_text="preset-table-action",
    )


class TestGameFlow(unittest.TestCase):
    def test_reset_observe_legal_actions_and_step_follow_the_contract(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("3S", "3H", "5S"),
                    2: ("6S",),
                    3: ("7S",),
                    4: ("8S",),
                }
            ),
        )
        game.reset()

        observation = game.observe()
        self.assertEqual(
            set(observation.keys()),
            {"my_info", "current_round", "other_players", "history", "legal_actions"},
        )
        self.assertEqual(observation["my_info"]["remaining_single_card_count"], 1)
        self.assertEqual(observation["current_round"]["current_level_rank"], "2")

        legal_actions = game.legal_actions()
        self.assertGreaterEqual(len(legal_actions), 2)
        self.assertTrue(
            {
                "action_id",
                "declared_pattern",
                "declared_cards",
                "carrier_cards",
                "wildcard_count",
                "wildcard_info",
                "display_text",
            }.issubset(legal_actions[0].keys())
        )

        agent = RuleBasedAIAgent(player_id=1)
        chosen_action_id = agent.select_action(observation, legal_actions)
        self.assertIn(chosen_action_id, {action["action_id"] for action in legal_actions})

        result = game.step(chosen_action_id)
        self.assertIn("state_diff", result)
        self.assertIn("round_ended", result)
        self.assertIn("game_over", result)
        self.assertIn("winner", result)

        with self.assertRaises(ValueError):
            game.step(99999)

    def test_public_legal_actions_preserve_multiple_declarations_for_same_carrier_cards(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("2H", "7S", "7C", "8S", "8C"),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        legal_actions = game.legal_actions()
        triple_with_pair_actions = [
            action
            for action in legal_actions
            if action["declared_pattern"] == "triple_with_pair"
        ]

        self.assertTrue(triple_with_pair_actions)
        for action in triple_with_pair_actions:
            self.assertEqual(
                set(action.keys()),
                {
                    "action_id",
                    "declared_pattern",
                    "declared_cards",
                    "carrier_cards",
                    "wildcard_count",
                    "wildcard_info",
                    "display_text",
                },
            )

        signatures = {
            (
                tuple(action["declared_cards"]),
                tuple(action["carrier_cards"]),
                int(action["wildcard_count"]),
            )
            for action in triple_with_pair_actions
        }
        self.assertIn(
            (("7", "7", "7", "8", "8"), ("7S", "7C", "8S", "8C", "2H"), 1),
            signatures,
        )
        self.assertIn(
            (("8", "8", "8", "7", "7"), ("7S", "7C", "8S", "8C", "2H"), 1),
            signatures,
        )

    def test_legal_actions_are_stable_and_use_sequential_action_ids(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("2H", "7S", "7C", "8S", "8C"),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        first = game.legal_actions()
        second = game.legal_actions()

        first_signatures = [
            (
                int(action["action_id"]),
                action["declared_pattern"],
                tuple(action["declared_cards"]),
                tuple(action["carrier_cards"]),
            )
            for action in first
        ]
        second_signatures = [
            (
                int(action["action_id"]),
                action["declared_pattern"],
                tuple(action["declared_cards"]),
                tuple(action["carrier_cards"]),
            )
            for action in second
        ]

        self.assertEqual(first_signatures, second_signatures)
        self.assertEqual([int(action["action_id"]) for action in first], list(range(1, len(first) + 1)))

        first_multi_decl_ids = {
            tuple(action["declared_cards"]): int(action["action_id"])
            for action in first
            if action["declared_pattern"] == "triple_with_pair"
        }
        second_multi_decl_ids = {
            tuple(action["declared_cards"]): int(action["action_id"])
            for action in second
            if action["declared_pattern"] == "triple_with_pair"
        }
        self.assertEqual(first_multi_decl_ids, second_multi_decl_ids)
        self.assertNotEqual(
            first_multi_decl_ids[("7", "7", "7", "8", "8")],
            first_multi_decl_ids[("8", "8", "8", "7", "7")],
        )

    def test_legal_actions_use_stable_one_based_ids_for_repeated_generation(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("2H", "7S", "7C", "8S", "8C"),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        first = game.legal_actions()
        second = game.legal_actions()

        self.assertEqual(
            [int(action["action_id"]) for action in first],
            [int(action["action_id"]) for action in second],
        )
        self.assertEqual(
            [int(action["action_id"]) for action in first],
            list(range(1, len(first) + 1)),
        )

    def test_step_uses_the_same_action_mapping_after_repeated_legal_action_generation(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=1,
            preset_table_action=_table_action(
                2,
                PatternType.TRIPLE_WITH_PAIR,
                ("7", "7", "7", "9", "9"),
                ("7S", "7H", "7D", "9S", "9H"),
            ),
            preset_hands=_hands(
                {
                    1: ("2H", "7S", "7C", "8S", "8C"),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        first_actions = game.legal_actions()
        chosen_action = next(
            action
            for action in first_actions
            if action["declared_pattern"] == "triple_with_pair"
            and tuple(action["declared_cards"]) == ("8", "8", "8", "7", "7")
        )
        chosen_action_id = int(chosen_action["action_id"])

        game.observe()
        game.legal_actions()
        result = game.step(chosen_action_id)

        self.assertEqual(result["chosen_action"]["action_id"], chosen_action_id)
        self.assertEqual(result["chosen_action"]["declared_cards"], ["8", "8", "8", "7", "7"])
        self.assertEqual(result["chosen_action"]["carrier_cards"], ["7S", "7C", "8S", "8C", "2H"])

    def test_reset_without_preset_hands_deals_108_cards_and_27_each(self) -> None:
        game = GuanDanGame(seed=7, current_level_rank="2")
        game.reset()

        hand_sizes = [len(player.hand_cards) for player in game._state.players]
        self.assertEqual(sum(hand_sizes), 108)
        self.assertEqual(hand_sizes, [27, 27, 27, 27])

    def test_preset_hands_reject_empty_player_hands(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("3S",),
                    2: (),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )

        with self.assertRaisesRegex(ValueError, "preset_hands"):
            game.reset()

    def test_preset_hands_reject_missing_player_entries(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("3S",),
                    2: ("4S",),
                    3: ("5S",),
                }
            ),
        )

        with self.assertRaisesRegex(ValueError, "preset_hands"):
            game.reset()

    def test_catch_wind_gives_next_lead_to_finished_players_teammate(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: (BIG_JOKER_RANK,),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        result = game.step(_pass_id(game))

        self.assertTrue(result["round_ended"])
        self.assertFalse(result["game_over"])
        self.assertEqual(game.observe()["current_round"]["current_player_id"], 3)
        self.assertEqual(game.observe()["history"]["finish_order"], [1])

    def test_finished_players_leave_rotation_after_catch_wind(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: (BIG_JOKER_RANK,),
                    2: ("3S",),
                    3: ("4S", "6S"),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_action_id_by_pattern(game, "single", ("4",)))

        self.assertEqual(game._state.current_player_id, 4)
        self.assertEqual(game._state.table_constraint.pending_player_ids, (4, 2))
        self.assertNotIn(1, game._state.table_constraint.pending_player_ids)

    def test_follow_context_uses_declared_cards_for_comparison_and_carrier_cards_for_discard(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=1,
            preset_table_action=_table_action(
                2,
                PatternType.TRIPLE_WITH_PAIR,
                ("7", "7", "7", "9", "9"),
                ("7S", "7H", "7D", "9S", "9H"),
            ),
            preset_hands=_hands(
                {
                    1: ("2H", "7S", "7C", "8S", "8C"),
                    2: ("3S",),
                    3: ("4S",),
                    4: ("5S",),
                }
            ),
        )
        game.reset()

        legal_actions = game.legal_actions()
        signatures = {
            (
                action["declared_pattern"],
                tuple(action["declared_cards"]),
                tuple(action["carrier_cards"]),
            )
            for action in legal_actions
        }
        self.assertIn(
            ("triple_with_pair", ("8", "8", "8", "7", "7"), ("7S", "7C", "8S", "8C", "2H")),
            signatures,
        )
        self.assertNotIn(
            ("triple_with_pair", ("7", "7", "7", "8", "8"), ("7S", "7C", "8S", "8C", "2H")),
            signatures,
        )

        chosen_action_id = _action_id_by_pattern(game, "triple_with_pair", ("8", "8", "8", "7", "7"))
        result = game.step(chosen_action_id)

        self.assertEqual(result["chosen_action"]["declared_cards"], ["8", "8", "8", "7", "7"])
        self.assertEqual(result["chosen_action"]["carrier_cards"], ["7S", "7C", "8S", "8C", "2H"])
        self.assertEqual(game.observe()["history"]["actions"][-1]["declared_cards"], ["8", "8", "8", "7", "7"])
        self.assertEqual(game._state.get_player(1).hand_cards, ())

    def test_third_finish_ends_the_game_and_assigns_last_place(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=4,
            preset_hands=_hands(
                {
                    1: ("3S",),
                    2: ("4S",),
                    3: ("5S",),
                    4: (BIG_JOKER_RANK,),
                }
            ),
        )
        game.reset()

        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_action_id_by_pattern(game, "single", ("4",)))
        result = game.step(_action_id_by_pattern(game, "single", ("5",)))

        self.assertTrue(result["game_over"])
        self.assertEqual(result["winner"], "team_24")
        self.assertEqual(game.observe()["history"]["finish_order"], [4, 2, 3, 1])
        self.assertIsNone(game._state.table_constraint.leading_action)
        self.assertEqual(game._state.table_constraint.pending_player_ids, ())
        self.assertIsNone(game.observe()["current_round"]["table_action"])

    def test_step_raises_after_game_over(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=4,
            preset_hands=_hands(
                {
                    1: ("3S",),
                    2: ("4S",),
                    3: ("5S",),
                    4: (BIG_JOKER_RANK,),
                }
            ),
        )
        game.reset()

        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_action_id_by_pattern(game, "single", ("4",)))
        result = game.step(_action_id_by_pattern(game, "single", ("5",)))

        self.assertTrue(result["game_over"])
        with self.assertRaisesRegex(ValueError, "already over"):
            game.step(123456)

    def test_catch_wind_ignores_finished_players(self) -> None:
        """接风判断只按仍未出完牌玩家集合；已出完牌玩家不得出现在 pending 中。"""

        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=4,
            preset_hands=_hands(
                {
                    1: (BIG_JOKER_RANK,),
                    2: ("2S", "4S"),
                    3: ("5S",),
                    4: ("9S", "9H"),
                }
            ),
        )
        game.reset()

        # 第 1 轮：玩家 4 出完对子 9 后，其他人只能 pass，接风到其队友玩家 2。
        game.step(_action_id_by_pattern(game, "pair", ("9", "9")))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        result = game.step(_pass_id(game))
        self.assertTrue(result["round_ended"])
        self.assertEqual(game.observe()["history"]["finish_order"], [4])
        self.assertEqual(game.observe()["current_round"]["current_player_id"], 2)

        # 第 2 轮：玩家 2 出单张 2；玩家 3 不能压只能 pass；玩家 1 用大王压并出完。
        game.step(_action_id_by_pattern(game, "single", ("2",)))
        game.step(_pass_id(game))
        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))

        # 玩家 4 已出完牌，不得参与后续 pending。
        self.assertNotIn(4, game._state.table_constraint.pending_player_ids)

        # 其余仍在局中的玩家依次 pass，接风到玩家 1 的队友玩家 3。
        game.step(_pass_id(game))
        end_round = game.step(_pass_id(game))
        self.assertTrue(end_round["round_ended"])
        self.assertEqual(game.observe()["current_round"]["current_player_id"], 3)

    def test_draw_is_declared_when_head_players_teammate_is_last(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: (BIG_JOKER_RANK,),
                    2: ("9S",),
                    3: ("3S", "4S"),
                    4: ("10S",),
                }
            ),
        )
        game.reset()

        game.step(_action_id_by_pattern(game, "single", (BIG_JOKER_RANK,)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        game.step(_action_id_by_pattern(game, "single", ("3",)))
        game.step(_action_id_by_pattern(game, "single", ("10",)))
        game.step(_pass_id(game))
        game.step(_pass_id(game))
        result = game.step(_action_id_by_pattern(game, "single", ("9",)))

        self.assertTrue(result["game_over"])
        self.assertEqual(result["winner"], "draw")
        self.assertEqual(game.observe()["history"]["finish_order"], [1, 4, 2, 3])

    def test_cli_debug_output_contains_replay_fields(self) -> None:
        buffer = io.StringIO()
        with patch(
            "sys.argv",
            ["run_4ai_debug.py", "--seed", "7", "--max-steps", "12000", "--current-level-rank", "2"],
        ):
            with redirect_stdout(buffer):
                exit_code = run_4ai_debug.main()

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("发牌完成：", output)
        self.assertIn("玩家1手牌：【", output)
        self.assertIn("====第1轮====", output)
        self.assertRegex(output, r"玩家[1-4]出牌：")
        self.assertIn("pass", output)
        self.assertRegex(output, r"玩家1剩余手牌：【.*】")
        self.assertIn("====游戏结束====", output)
        self.assertRegex(output, r"头游：玩家[1-4]")
        self.assertRegex(output, r"二游：玩家[1-4]")
        self.assertRegex(output, r"三游：玩家[1-4]")
        self.assertRegex(output, r"末游：玩家[1-4]")
        self.assertRegex(output, r"(队伍1（玩家1，玩家3）获胜|队伍2（玩家2，玩家4）获胜|本局平局)")
        self.assertNotIn("current_player=", output)
        self.assertNotIn("constraint=", output)
        self.assertNotIn("legal_actions=", output)
        self.assertNotIn("chosen_action=", output)
        self.assertNotIn("state_diff=", output)
        self.assertNotIn("round_ended=", output)
        self.assertNotIn("game_over=", output)
        self.assertNotIn("winner=", output)


if __name__ == "__main__":
    unittest.main()
