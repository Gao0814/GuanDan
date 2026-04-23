import io
from contextlib import redirect_stdout
import re
import unittest

from agents.rule_based_ai import RuleBasedAIAgent
from cli import run_4ai_debug
from engine.cards import Card
from engine.game import GuanDanGame


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


def _render_game(game: GuanDanGame) -> str:
    agents = tuple(RuleBasedAIAgent(player_id=player_id) for player_id in (1, 2, 3, 4))
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_4ai_debug._print_human_replay(game, agents, max_steps=12000)
    return buffer.getvalue()


class TestCliDebugOutput(unittest.TestCase):
    def test_card_tokens_and_hand_cards_are_rendered_in_chinese(self) -> None:
        self.assertEqual(run_4ai_debug._card_token_to_cn("AS"), "♠A")
        self.assertEqual(run_4ai_debug._card_token_to_cn("10H"), "♥10")
        self.assertEqual(run_4ai_debug._card_token_to_cn("SJ"), "小王")
        self.assertEqual(run_4ai_debug._card_token_to_cn("BJ"), "大王")
        self.assertEqual(run_4ai_debug._cards_to_cn(["AH", "AS"]), "【♥A、♠A】")
        self.assertEqual(
            run_4ai_debug._format_hand_cards_cn(["3S", "AH", "BJ", "2H", "SJ"]),
            "【♠3、♥A、♥2、小王、大王】",
        )

    def test_action_names_are_rendered_in_human_readable_chinese(self) -> None:
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "pair",
                    "declared_cards": ["A", "A"],
                    "carrier_cards": ["AH", "AS"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
            "对A【♥A、♠A】",
        )
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "pair",
                    "declared_cards": ["SJ", "SJ"],
                    "carrier_cards": ["SJ", "SJ"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
            "对小王【小王、小王】",
        )
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "pair",
                    "declared_cards": ["BJ", "BJ"],
                    "carrier_cards": ["BJ", "BJ"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
            "对大王【大王、大王】",
        )
        self.assertIn(
            "顺子",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "straight",
                    "declared_cards": ["3", "4", "5", "6", "7"],
                    "carrier_cards": ["3S", "4S", "5S", "6S", "7S"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertIn(
            "连对",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "pair_straight",
                    "declared_cards": ["3", "3", "4", "4", "5", "5"],
                    "carrier_cards": ["3S", "3H", "4S", "4H", "5S", "5H"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertIn(
            "钢板",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "steel_plate",
                    "declared_cards": ["6", "6", "6", "7", "7", "7"],
                    "carrier_cards": ["6S", "6H", "6C", "7S", "7H", "7C"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertIn(
            "4炸",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "bomb",
                    "declared_cards": ["5", "5", "5", "5"],
                    "carrier_cards": ["5S", "5H", "5C", "5D"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertIn(
            "5炸",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "bomb",
                    "declared_cards": ["5", "5", "5", "5", "5"],
                    "carrier_cards": ["5S", "5H", "5C", "5D", "5S"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertIn(
            "同花顺",
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "straight_flush",
                    "declared_cards": ["10H", "JH", "QH", "KH", "AH"],
                    "carrier_cards": ["10H", "JH", "QH", "KH", "AH"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
        )
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "joker_bomb",
                    "declared_cards": ["SJ", "SJ", "BJ", "BJ"],
                    "carrier_cards": ["SJ", "SJ", "BJ", "BJ"],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
            "天王炸【小王、小王、大王、大王】",
        )
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "pass",
                    "declared_cards": [],
                    "carrier_cards": [],
                    "wildcard_count": 0,
                    "wildcard_info": [],
                }
            ),
            "pass",
        )

    def test_wildcard_actions_show_declared_meaning_and_real_carrier_cards(self) -> None:
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "straight",
                    "declared_cards": ["7", "8", "9", "10", "J"],
                    "carrier_cards": ["7S", "8S", "9S", "10S", "2H"],
                    "wildcard_count": 1,
                    "wildcard_info": [{"carrier_card": "2H", "declared_as": "J"}],
                }
            ),
            "顺子【♠7、♠8、♠9、♠10、♥2】（声明：78910J，逢人配当J）",
        )
        self.assertEqual(
            run_4ai_debug._format_action_cn(
                {
                    "declared_pattern": "triple_with_pair",
                    "declared_cards": ["8", "8", "8", "7", "7"],
                    "carrier_cards": ["7S", "7C", "8S", "8C", "2H"],
                    "wildcard_count": 1,
                    "wildcard_info": [{"carrier_card": "2H", "declared_as": "8"}],
                }
            ),
            "三带二【♠7、♣7、♠8、♣8、♥2】（声明：88877，逢人配当8）",
        )

    def test_human_replay_uses_round_headers_once_and_matches_final_summary(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("BJ",),
                    2: ("9S",),
                    3: ("3S", "4S"),
                    4: ("10S",),
                }
            ),
        )

        output = _render_game(game)
        round_titles = re.findall(r"====第(\d+)轮====", output)
        self.assertTrue(round_titles)
        self.assertEqual(round_titles, [str(index) for index in range(1, len(round_titles) + 1)])
        self.assertIn("玩家1剩余手牌：【】", output)
        self.assertIn("====游戏结束====", output)
        self.assertIn("头游：玩家1", output)
        self.assertIn("二游：玩家4", output)
        self.assertIn("三游：玩家2", output)
        self.assertIn("末游：玩家3", output)
        self.assertIn("本局平局", output)

    def test_finish_rank_is_appended_immediately_when_a_player_plays_out(self) -> None:
        game = GuanDanGame(
            current_level_rank="2",
            preset_hands=_hands(
                {
                    1: ("BJ",),
                    2: ("9S",),
                    3: ("3S", "4S"),
                    4: ("10S",),
                }
            ),
        )

        output = _render_game(game)
        self.assertIn("玩家1出牌：单张【大王】（玩家1头游）", output)
        self.assertIn("玩家4出牌：单张【♠10】（玩家4二游）", output)
        self.assertIn("玩家2出牌：单张【♠9】（玩家2三游）", output)


if __name__ == "__main__":
    unittest.main()
