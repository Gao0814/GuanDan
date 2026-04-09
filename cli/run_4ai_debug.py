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
    "SJ": 13,
    "BJ": 14,
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
    "straight": "顺子",
    "pair_straight": "连对",
    "triple_with_pair": "三带二",
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
    if token == "SJ":
        return "小王"
    if token == "BJ":
        return "大王"
    suit = token[-1]
    rank = token[:-1]
    if suit in _SUIT_CN and rank:
        return f"{_SUIT_CN[suit]}{rank}"
    return token


def _card_sort_key(token: object) -> tuple[int, int, str]:
    if not isinstance(token, str) or not token:
        return (999, 999, str(token))
    if token in _RANK_ORDER:
        return (_RANK_ORDER[token], 999, token)
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
        return "过牌"
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


def _format_constraint(constraint: object) -> str:
    if not isinstance(constraint, dict):
        return "未知约束"
    required = constraint.get("required_pattern")
    required_cn = _PATTERN_CN.get(str(required), str(required) if required is not None else "无")
    min_hint = constraint.get("min_strength_hint")
    leading = constraint.get("leading_action")
    leading_text = "无"
    if isinstance(leading, dict):
        leading_text = _format_play_cn(leading)
    if required is None and leading is None:
        return "自由出牌"
    hint_text = f"（点数 > {min_hint}）" if min_hint is not None else ""
    return f"当前需压：{required_cn}{hint_text}；基准动作：{leading_text}"


def _format_remaining_counts(counts: object) -> str:
    if not isinstance(counts, dict):
        return "-"
    items: list[str] = []
    for player_id in sorted((k for k in counts.keys() if isinstance(k, int))):
        items.append(f"{_player_label(player_id)}={counts[player_id]}")
    return " ".join(items)


def _bool_cn(flag: object) -> str:
    return "是" if flag is True else "否"


def _phase_cn(phase: object) -> str:
    if phase == "lead":
        return "领出"
    if phase == "follow":
        return "跟牌"
    return str(phase)


def _player_value_cn(player_id: object) -> str:
    if isinstance(player_id, int):
        return _player_label(player_id)
    if player_id is None:
        return "无"
    return str(player_id)


def _format_legal_actions(legal_actions: object) -> str:
    if not isinstance(legal_actions, list):
        return "  - 无"

    grouped: dict[str, list[str]] = {}
    for action in legal_actions:
        if not isinstance(action, dict):
            continue
        key = str(action.get("declared_pattern") or action.get("action_type") or "unknown")
        key_cn = _PATTERN_CN.get(key, key)
        grouped.setdefault(key_cn, []).append(_format_play_cn(action))

    if not grouped:
        return "  - 无"

    max_groups = 6
    max_items_per_group = 3
    lines: list[str] = []
    group_items = list(grouped.items())
    group_items.sort(key=lambda item: (item[0] != "过牌", item[0]))

    for index, (group_name, actions) in enumerate(group_items):
        if index >= max_groups:
            lines.append(f"  - 其余{len(group_items) - max_groups}种牌型省略")
            break
        shown = actions[:max_items_per_group]
        omitted = len(actions) - len(shown)
        suffix = f"；其余{omitted}项省略" if omitted > 0 else ""
        lines.append(
            f"  - {group_name}({len(actions)}项)："
            f"{'；'.join(shown)}{suffix}"
        )
    return "\n".join(lines)


def _format_state_diff(state_before: object, state_after: object) -> str:
    if not isinstance(state_before, dict) or not isinstance(state_after, dict):
        return "无"

    parts: list[str] = []
    before_player = state_before.get("current_player_id")
    after_player = state_after.get("current_player_id")
    if before_player != after_player:
        parts.append(
            f"当前玩家：{_player_value_cn(before_player)} -> {_player_value_cn(after_player)}"
        )

    before_phase = state_before.get("phase")
    after_phase = state_after.get("phase")
    if before_phase != after_phase:
        parts.append(f"阶段：{_phase_cn(before_phase)} -> {_phase_cn(after_phase)}")

    before_recent = state_before.get("recent_success_player")
    after_recent = state_after.get("recent_success_player")
    if before_recent != after_recent:
        parts.append(
            f"最近成功出牌者：{_player_value_cn(before_recent)} -> {_player_value_cn(after_recent)}"
        )

    before_round = state_before.get("round_no")
    after_round = state_after.get("round_no")
    if before_round != after_round:
        parts.append(f"轮次：第{before_round}轮 -> 第{after_round}轮")

    before_constraint = state_before.get("table_constraint")
    after_constraint = state_after.get("table_constraint")
    if before_constraint != after_constraint:
        parts.append(
            "约束变化："
            f"{_format_constraint(before_constraint)}"
            f"->{_format_constraint(after_constraint)}"
        )

    before_counts = state_before.get("remaining_hand_counts")
    after_counts = state_after.get("remaining_hand_counts")
    if isinstance(before_counts, dict) and isinstance(after_counts, dict):
        changed_count_parts: list[str] = []
        for player_id in sorted(
            set(k for k in before_counts.keys() if isinstance(k, int))
            | set(k for k in after_counts.keys() if isinstance(k, int))
        ):
            if before_counts.get(player_id) != after_counts.get(player_id):
                changed_count_parts.append(
                    f"{_player_label(player_id)}:{before_counts.get(player_id)}->{after_counts.get(player_id)}"
                )
        if changed_count_parts:
            parts.append("手牌数量变化：" + "，".join(changed_count_parts))

    return "；".join(parts) if parts else "无关键变化"


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


def _print_all_hands_human(all_hands: object, suffix: str = "手牌") -> None:
    if not isinstance(all_hands, dict):
        return

    sorted_player_ids: list[int] = []
    for player_id in all_hands.keys():
        if isinstance(player_id, int):
            sorted_player_ids.append(player_id)
    sorted_player_ids.sort()

    for player_id in sorted_player_ids:
        cards = all_hands.get(player_id, [])
        print(f"{_player_label(player_id)}{suffix}：{_cards_to_cn(cards)}")


def _print_events_human(events: list[object], verbose_debug: bool = False) -> None:
    last_round = None
    should_print_initial_hands = True
    pending_play_lines: list[str] = []
    pending_hands_after: object = None

    for event in events:
        event_type = getattr(event, "event_type", None)
        payload = getattr(event, "payload", None)
        if event_type != "step" or not isinstance(payload, dict):
            continue

        if should_print_initial_hands:
            print("\n发牌完成")
            _print_all_hands_human(payload.get("all_hands", {}))
            should_print_initial_hands = False

        round_no = _get_round_no(payload)
        if round_no != last_round:
            print(f"\n======第{round_no}轮======")
            last_round = round_no

        step_id = payload.get("step_id")
        current_player = payload.get("current_player_id")
        legal_actions = payload.get("legal_actions", [])
        chosen_action = payload.get("chosen_action", {})
        table_constraint = payload.get("table_constraint")
        state_before = payload.get("state_before")
        state_after = payload.get("state_after")
        remaining_counts = payload.get("remaining_hand_counts")
        round_ended = payload.get("round_ended")
        game_over = payload.get("game_over")
        winner = payload.get("winner")

        if verbose_debug:
            print(f"当前步数：{step_id}")
            print(f"当前玩家：{_player_label(current_player)}")
            print(f"当前约束：{_format_constraint(table_constraint)}")
            legal_count = len(legal_actions) if isinstance(legal_actions, list) else 0
            print(f"可选动作（共{legal_count}项，按牌型分组）：")
            print(_format_legal_actions(legal_actions))
            if isinstance(chosen_action, dict):
                print(f"已选动作：{_format_play_cn(chosen_action)}")
            else:
                print("已选动作：无")
            print(f"状态变化：{_format_state_diff(state_before, state_after)}")
            print(f"剩余手牌数：{_format_remaining_counts(remaining_counts)}")

            winner_text = _player_label(winner) if isinstance(winner, int) else "无"
            print(f"本轮是否结束：{_bool_cn(round_ended)}")
            print(f"对局是否结束：{_bool_cn(game_over)}")
            print(f"胜者：{winner_text}")

        step_line = _format_step_human(payload)
        if step_line:
            pending_play_lines.append(step_line)
        pending_hands_after = payload.get("all_hands_after", {})

        if round_ended:
            for line in pending_play_lines:
                print(line)
            _print_all_hands_human(pending_hands_after, suffix="剩余手牌")
            pending_play_lines = []

        state_after = payload.get("state_after", {})
        next_player_id = None
        if isinstance(state_after, dict):
            next_player_id = state_after.get("current_player_id")
        if round_ended and isinstance(next_player_id, int):
            print(f"\n本轮结束，下轮首出：{_player_label(next_player_id)}（本轮最大）")

    if pending_play_lines:
        for line in pending_play_lines:
            print(line)
        if pending_hands_after is not None:
            _print_all_hands_human(pending_hands_after, suffix="剩余手牌")


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
    parser.add_argument(
        "--verbose-debug",
        action="store_true",
        help="Show verbose per-step debug details in human-readable mode.",
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
                _print_events_human(logger.events, verbose_debug=args.verbose_debug)
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
            _print_events_human(logger.events, verbose_debug=args.verbose_debug)

    winner_text = (
        f"玩家{final_state.winner_player_id + 1}"
        if final_state.winner_player_id is not None
        else "无"
    )
    print(
        f"\n对局结束：胜者={winner_text} 步数={final_state.step_no} 轮次={final_state.round_no}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
