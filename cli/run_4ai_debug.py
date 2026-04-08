"""Four-AI debug runner entrypoint skeleton for phase-1."""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


# Support both "python -m cli.run_4ai_debug" and direct script execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import FourAIGameRunner, build_initial_state
from engine.logging_utils import DebugLogger
from engine.rules import BaseRuleEngine


_SUIT_CN = {
    "S": "♠",
    "C": "♣",
    "D": "♦",
    "H": "♥",
}

_RANK_ORDER = {
    "2": 0,
    "3": 1,
    "4": 2,
    "5": 3,
    "6": 4,
    "7": 5,
    "8": 6,
    "9": 7,
    "10": 8,
    "J": 9,
    "Q": 10,
    "K": 11,
    "A": 12,
}

_SUIT_ORDER = {
    "S": 0,
    "C": 1,
    "D": 2,
    "H": 3,
}

_PATTERN_CN = {
    "single": "单张",
    "pair": "对子",
    "triple": "三张",
    "bomb": "炸弹",
    "pass": "过牌",
    "unknown": "未知",
}


def _player_label(player_id: object) -> str:
    if isinstance(player_id, int):
        return f"玩家{player_id + 1}"
    return "玩家?"


def _card_to_cn(token: object) -> str:
    if not isinstance(token, str) or not token:
        return str(token)
    suit = token[-1]
    rank = token[:-1]
    if suit in _SUIT_CN and rank:
        return f"{_SUIT_CN[suit]}{rank}"
    return token


def _card_sort_key(token: object) -> tuple[int, int, str]:
    if not isinstance(token, str) or not token:
        return (999, 999, str(token))
    suit = token[-1]
    rank = token[:-1]
    rank_idx = _RANK_ORDER.get(rank, 999)
    suit_idx = _SUIT_ORDER.get(suit, 999)
    return (rank_idx, suit_idx, token)


def _cards_to_cn(cards: object) -> str:
    if not isinstance(cards, list):
        return "[]"
    sorted_cards = sorted(cards, key=_card_sort_key)
    converted = [_card_to_cn(card) for card in sorted_cards]
    return f"[{ '，'.join(converted) }]"


def _format_play_cn(action: dict[str, object]) -> str:
    action_type = action.get("action_type")
    if action_type == "pass":
        return "pass"
    cards = action.get("cards", [])
    if not isinstance(cards, list):
        cards = []
    cards_cn = "，".join(_card_to_cn(card) for card in cards)
    pattern = action.get("declared_pattern")
    pattern_cn = _PATTERN_CN.get(str(pattern), str(pattern) if pattern is not None else "未知")
    return f"{cards_cn}({pattern_cn})"


def _format_action(action: dict[str, object]) -> str:
    cards = action.get("cards", [])
    cards_text = " ".join(str(card) for card in cards) if cards else "-"
    return (
        f"player={action.get('player_id')} type={action.get('action_type')} "
        f"pattern={action.get('declared_pattern')} cards=[{cards_text}]"
    )


def _get_round_no(payload: dict[str, object]) -> object:
    state_before = payload.get("state_before", {})
    if isinstance(state_before, dict):
        return state_before.get("round_no")
    return None


def _format_step_human(payload: dict[str, object]) -> str:
    chosen_action = payload.get("chosen_action")
    if not isinstance(chosen_action, dict):
        return ""

    player_id = chosen_action.get("player_id")
    player_name = _player_label(player_id)
    return f"{player_name}出牌：{_format_play_cn(chosen_action)}"


def _print_all_hands_human(all_hands: object) -> None:
    if not isinstance(all_hands, dict):
        return

    sorted_player_ids: list[int] = []
    for player_id in all_hands.keys():
        if isinstance(player_id, int):
            sorted_player_ids.append(player_id)
    sorted_player_ids.sort()

    for player_id in sorted_player_ids:
        cards = all_hands.get(player_id, [])
        print(f"{_player_label(player_id)}手牌：{_cards_to_cn(cards)}")


def _print_events_human(events: list[object]) -> None:
    last_round = None
    should_print_initial_hands = True
    played_steps_since_last_hands = 0
    pending_play_lines: list[str] = []

    for event in events:
        event_type = getattr(event, "event_type", None)
        payload = getattr(event, "payload", None)
        if event_type != "step" or not isinstance(payload, dict):
            continue

        if should_print_initial_hands:
            print("\n===发牌后4名玩家手牌===")
            _print_all_hands_human(payload.get("all_hands", {}))
            should_print_initial_hands = False

        round_no = _get_round_no(payload)
        if round_no != last_round:
            print(f"\n===第{round_no}轮===")
            last_round = round_no

        step_line = _format_step_human(payload)
        if step_line:
            pending_play_lines.append(step_line)
        played_steps_since_last_hands += 1

        if played_steps_since_last_hands == 4:
            print("\n---出牌记录---")
            for line in pending_play_lines:
                print(line)
            print("\n---手牌概览---")
            _print_all_hands_human(payload.get("all_hands_after", {}))
            played_steps_since_last_hands = 0
            pending_play_lines = []

        state_after = payload.get("state_after", {})
        next_player_id = None
        if isinstance(state_after, dict):
            next_player_id = state_after.get("current_player_id")
        if payload.get("round_ended") and isinstance(next_player_id, int):
            # If this round ended before reaching a 4-step print block,
            # flush pending play lines first to avoid misleading ordering.
            if pending_play_lines:
                print("\n---出牌记录---")
                for line in pending_play_lines:
                    print(line)
                pending_play_lines = []
            print(f"\n本轮结束，下轮首出：{_player_label(next_player_id)}（本轮最大）")

    if pending_play_lines:
        print("\n---出牌记录---")
        for line in pending_play_lines:
            print(line)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run 4-AI GuanDan debug session (skeleton).")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed.")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=12000,
        help="Max step guard for one game (default: 12000).",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print final summary without per-step debug events.",
    )
    parser.add_argument(
        "--json-lines",
        action="store_true",
        help="Print per-step debug events as JSON lines.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    rule_engine = BaseRuleEngine()
    agents = tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4))
    logger = DebugLogger()
    runner = FourAIGameRunner(
        rule_engine=rule_engine,
        agents=agents,
        debug_logger=logger,
        max_steps=args.max_steps,
    )

    try:
        final_state = runner.run_one_game(build_initial_state(seed=args.seed))
    except Exception as exc:
        if not args.summary_only:
            if args.json_lines:
                for event in logger.events:
                    if event.event_type == "step":
                        print(json.dumps(event.payload, ensure_ascii=False))
            else:
                _print_events_human(logger.events)
        print(f"run_error={type(exc).__name__}: {exc}")
        if isinstance(exc, RuntimeError) and "max_steps" in str(exc):
            suggested = max(args.max_steps * 2, 12000)
            print(f"建议：使用更大的步数上限重试，例如 --max-steps {suggested}")
        return 1

    if not args.summary_only:
        if args.json_lines:
            for event in logger.events:
                if event.event_type == "step":
                    print(json.dumps(event.payload, ensure_ascii=False))
        else:
            _print_events_human(logger.events)

    winner_text = (
        f"玩家{final_state.winner_player_id + 1}"
        if final_state.winner_player_id is not None
        else "无"
    )
    print(
        f"\n对局结束：是否结束={final_state.is_finished} 胜者={winner_text} "
        f"步数={final_state.step_no} 轮次={final_state.round_no} 事件数={len(logger.events)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
