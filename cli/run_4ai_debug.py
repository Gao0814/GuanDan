"""Run a human-readable four-AI debug game on the single-game mainline."""

from argparse import ArgumentParser
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.rule_based_ai import RuleBasedAIAgent
from engine.cards import BIG_JOKER_RANK, SMALL_JOKER_RANK, Card, card_sort_key, card_to_token
from engine.game import GuanDanGame


_SUIT_SYMBOLS: dict[str, str] = {
    "S": "♠",
    "H": "♥",
    "C": "♣",
    "D": "♦",
}
_PATTERN_LABELS: dict[str, str] = {
    "single": "单张",
    "pair": "对",
    "triple": "三张",
    "triple_with_pair": "三带二",
    "straight": "顺子",
    "pair_straight": "连对",
    "steel_plate": "钢板",
    "straight_flush": "同花顺",
    "joker_bomb": "天王炸",
}
_TEAM_WINNER_TEXT: dict[str, str] = {
    "team_13": "队伍1（玩家1，玩家3）获胜",
    "team_24": "队伍2（玩家2，玩家4）获胜",
    "draw": "本局平局",
}
_FINISH_LABELS: tuple[str, ...] = ("头游", "二游", "三游", "末游")


def _ensure_utf8_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def _token_to_card(token: str) -> Card:
    if token in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
        return Card(rank=token)
    if token and token[-1] in _SUIT_SYMBOLS:
        return Card(rank=token[:-1], suit=token[-1])
    return Card(rank=token)


def _card_token_to_cn(token: str) -> str:
    card = _token_to_card(token)
    if card.rank == SMALL_JOKER_RANK:
        return "小王"
    if card.rank == BIG_JOKER_RANK:
        return "大王"
    if card.suit is None:
        return card.rank
    return f"{_SUIT_SYMBOLS[card.suit]}{card.rank}"


def _cards_to_cn(tokens: list[str]) -> str:
    if not tokens:
        return "【】"
    return "【" + "、".join(_card_token_to_cn(token) for token in tokens) + "】"


def _format_hand_cards_cn(tokens: list[str]) -> str:
    ordered_tokens = sorted(tokens, key=lambda token: card_sort_key(_token_to_card(token)))
    return _cards_to_cn(ordered_tokens)


def _compact_declared_cards_cn(tokens: list[str]) -> str:
    parts: list[str] = []
    for token in tokens:
        card = _token_to_card(token)
        if card.rank in {SMALL_JOKER_RANK, BIG_JOKER_RANK}:
            parts.append(_card_token_to_cn(token))
        elif card.suit is not None:
            parts.append(_card_token_to_cn(token))
        else:
            parts.append(card.rank)
    return "".join(parts)


def _pattern_label_cn(action: dict[str, object]) -> str:
    declared_pattern = str(action.get("declared_pattern"))
    declared_cards = [str(token) for token in action.get("declared_cards", [])]

    if declared_pattern == "pair":
        main_rank = declared_cards[0] if declared_cards else ""
        return f"对{_card_token_to_cn(main_rank)}"
    if declared_pattern == "bomb":
        return f"{len(declared_cards)}炸"
    return _PATTERN_LABELS.get(declared_pattern, declared_pattern)


def _wildcard_suffix_cn(action: dict[str, object]) -> str:
    wildcard_count = int(action.get("wildcard_count", 0))
    wildcard_info = list(action.get("wildcard_info", []))
    if wildcard_count != 1 or not wildcard_info:
        return ""

    declared_cards = [str(token) for token in action.get("declared_cards", [])]
    declared_text = _compact_declared_cards_cn(declared_cards)
    declared_as = str(wildcard_info[0]["declared_as"])
    declared_as_text = _card_token_to_cn(declared_as)
    return f"（声明：{declared_text}，逢人配当{declared_as_text}）"


def _format_action_cn(action: dict[str, object]) -> str:
    declared_pattern = str(action.get("declared_pattern"))
    if declared_pattern == "pass":
        return "pass"

    carrier_cards = [str(token) for token in action.get("carrier_cards", [])]
    return f"{_pattern_label_cn(action)}{_cards_to_cn(carrier_cards)}{_wildcard_suffix_cn(action)}"


def _finish_suffix_cn(result: dict[str, object]) -> str:
    state_diff = dict(result.get("state_diff", {}))
    player_id = int(state_diff.get("current_player_before", 0))
    finish_order_before = [int(item) for item in state_diff.get("finish_order_before", [])]
    finish_order_after = [int(item) for item in state_diff.get("finish_order_after", [])]

    if player_id not in finish_order_after or player_id in finish_order_before:
        return ""

    rank_index = finish_order_after.index(player_id)
    return f"（玩家{player_id}{_FINISH_LABELS[rank_index]}）"


def _print_initial_hands(game: GuanDanGame) -> None:
    print("发牌完成：")
    for player in game._state.players:  # noqa: SLF001 - debug CLI needs full-information replay
        hand_tokens = [card_to_token(card) for card in player.hand_cards]
        print(f"玩家{player.player_id}手牌：{_format_hand_cards_cn(hand_tokens)}")


def _print_remaining_hands(game: GuanDanGame) -> None:
    for player in game._state.players:  # noqa: SLF001 - debug CLI needs full-information replay
        hand_tokens = [card_to_token(card) for card in player.hand_cards]
        print(f"玩家{player.player_id}剩余手牌：{_format_hand_cards_cn(hand_tokens)}")


def _print_final_summary(game: GuanDanGame) -> None:
    finish_order = game._state.finish_order  # noqa: SLF001 - debug CLI needs final ranks
    winner = game._state.winner  # noqa: SLF001 - debug CLI needs final outcome

    print("====游戏结束====")
    for label, player_id in zip(_FINISH_LABELS, finish_order):
        print(f"{label}：玩家{player_id}")
    print(_TEAM_WINNER_TEXT[winner])


def _print_human_replay(
    game: GuanDanGame,
    agents: tuple[object, object, object, object],
    *,
    max_steps: int,
) -> int:
    game.reset()
    _print_initial_hands(game)
    print(f"====第{game._state.round_no}轮====")  # noqa: SLF001 - debug CLI needs round truth

    while not game._state.is_finished:  # noqa: SLF001 - debug CLI needs full replay
        if game._state.step_no >= max_steps:  # noqa: SLF001 - debug CLI needs full replay
            print(f"\n[警告] 游戏在 max_steps={max_steps} 限制内未结束，终止运行。")
            return 0

        observation = game.observe()
        legal_actions = game.legal_actions()
        current_player = int(observation["current_round"]["current_player_id"])
        chosen_action_id = agents[current_player - 1].select_action(observation, legal_actions)
        result = game.step(chosen_action_id)

        print(f"玩家{current_player}出牌：{_format_action_cn(result['chosen_action'])}{_finish_suffix_cn(result)}")

        if result["round_ended"]:
            print()
            _print_remaining_hands(game)
            if not result["game_over"]:
                print(f"====第{game._state.round_no}轮====")  # noqa: SLF001 - debug CLI needs round truth

    print()
    _print_final_summary(game)
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run a four-AI GuanDan debug session.")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed.")
    parser.add_argument("--max-steps", type=int, default=12000, help="Safety cap for one game.")
    parser.add_argument("--current-level-rank", type=str, default="2", help="Current level rank for this game.")
    parser.add_argument(
        "--agent",
        type=str,
        default="rule",
        choices=("rule", "deepseek"),
        help="Agent type for all 4 players (default: rule).",
    )
    parser.add_argument(
        "--show-thinking",
        action="store_true",
        default=False,
        help="Show player 1 DeepSeek thinking process (only effective with --agent deepseek).",
    )
    return parser


def main() -> int:
    _ensure_utf8_stdio()
    args = build_parser().parse_args()
    game = GuanDanGame(seed=args.seed, current_level_rank=args.current_level_rank)

    if args.agent == "deepseek":
        from config import AppConfig
        from agents.deepseek_ai import DeepSeekAIAgent
        from agents.deepseek_client import DeepSeekClient
        from agents.rag_advisor import RAGAdvisor
        from rag.kb_loader import KnowledgeBaseLoader
        from rag.retriever import KnowledgeRetriever

        config = AppConfig.from_env()
        if not config.deepseek_api_key:
            print("DEEPSEEK_API_KEY is required for --agent deepseek", file=sys.stderr)
            return 2

        client = DeepSeekClient(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model=config.deepseek_model,
            timeout_seconds=config.deepseek_timeout,
            max_retries=config.deepseek_max_retries,
        )
        loader = KnowledgeBaseLoader((PROJECT_ROOT / "rag").resolve())
        retriever = KnowledgeRetriever(loader.load_all_documents())
        rag_advisor = RAGAdvisor(retriever)
        agents = tuple(
            DeepSeekAIAgent(
                player_id=player_id,
                client=client,
                rag_advisor=rag_advisor,
                verbose=(player_id == 1 and args.show_thinking),
            )
            for player_id in (1, 2, 3, 4)
        )
    else:
        agents = tuple(RuleBasedAIAgent(player_id=player_id) for player_id in (1, 2, 3, 4))
    return _print_human_replay(game, agents, max_steps=args.max_steps)


if __name__ == "__main__":
    raise SystemExit(main())
