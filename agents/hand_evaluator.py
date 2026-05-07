"""Hand strength evaluation helpers for opening strategy and DeepSeek context."""

from __future__ import annotations


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _token_rank(token: str) -> str:
    if token and token[-1] in {"S", "H", "C", "D"}:
        return token[:-1]
    return token


def _structure_base_score(remaining_single_card_count: int) -> int:
    if remaining_single_card_count <= 1:
        return 40
    if remaining_single_card_count <= 3:
        return 35
    if remaining_single_card_count <= 5:
        return 28
    if remaining_single_card_count <= 7:
        return 20
    return 10


def _count_pattern(legal_actions: list[dict[str, object]], pattern: str) -> int:
    return sum(1 for action in legal_actions if str(action.get("declared_pattern")) == pattern)


def _round_half_up(value: float) -> int:
    return int(value + 0.5)


def _label_from_total(total_score: int) -> str:
    if total_score >= 80:
        return "极强"
    if total_score >= 60:
        return "较强"
    if total_score >= 40:
        return "中等"
    if total_score >= 20:
        return "偏弱"
    return "极弱"


def _structure_comment(
    remaining_single_card_count: int,
    *,
    steel_plate_count: int,
    straight_count: int,
    pair_straight_count: int,
    triple_with_pair_count: int,
) -> str:
    if remaining_single_card_count <= 1:
        base = "结构佳"
    elif remaining_single_card_count <= 3:
        base = "结构较整齐"
    elif remaining_single_card_count <= 5:
        base = "结构一般"
    elif remaining_single_card_count <= 7:
        base = "散牌偏多"
    else:
        base = "散牌很多"

    extras: list[str] = []
    if steel_plate_count > 0:
        extras.append("钢板丰富")
    if straight_count > 1:
        extras.append("顺子多样")
    if pair_straight_count > 1:
        extras.append("连对成型")
    if triple_with_pair_count > 1:
        extras.append("三带二灵活")

    if extras:
        return f"{base}，{'，'.join(extras)}"
    return base


def _control_comment(bomb_score: int, control_points_score: int) -> str:
    if bomb_score >= 10 or control_points_score >= 12:
        return "炸弹充足，控制力强"
    if bomb_score >= 6 or control_points_score >= 8:
        return "控制力尚可"
    return "控制力偏弱"


def _potential_comment(wildcard_count: int, diversity_count: int) -> str:
    if wildcard_count > 0 and diversity_count >= 4:
        return "逢人配灵活，牌型多样"
    if wildcard_count > 0:
        return "逢人配灵活"
    if diversity_count >= 4:
        return "牌型多样"
    return "牌型变化有限"


def evaluate_hand(observation: dict[str, object], legal_actions: list[dict[str, object]]) -> dict[str, object]:
    """Evaluate a hand using the published hand-evaluation spec."""

    my_info = dict(observation.get("my_info", {}))
    current_round = dict(observation.get("current_round", {}))

    hand_cards = [str(token) for token in my_info.get("hand_cards", [])]
    remaining_single_card_count = _coerce_int(my_info.get("remaining_single_card_count"), default=0)
    current_level_rank = str(current_round.get("current_level_rank", ""))

    steel_plate_count = _count_pattern(legal_actions, "steel_plate")
    straight_count = _count_pattern(legal_actions, "straight")
    pair_straight_count = _count_pattern(legal_actions, "pair_straight")
    triple_with_pair_count = _count_pattern(legal_actions, "triple_with_pair")

    structure_score = _structure_base_score(remaining_single_card_count)
    structure_score += min(5, 5 if steel_plate_count > 0 else 0)
    structure_score += min(6, max(0, straight_count - 1) * 2)
    structure_score += min(4, max(0, pair_straight_count - 1) * 2)
    structure_score += min(3, max(0, triple_with_pair_count - 1) * 1)
    structure_score = min(40, structure_score)

    bomb_score_raw = 0
    for action in legal_actions:
        pattern = str(action.get("declared_pattern"))
        declared_cards = [str(token) for token in action.get("declared_cards", [])]
        card_count = len(declared_cards)

        if pattern == "bomb":
            if card_count >= 6:
                bomb_score_raw += 8
            elif card_count == 5:
                bomb_score_raw += 5
            elif card_count == 4:
                bomb_score_raw += 3
        elif pattern == "straight_flush":
            bomb_score_raw += 8
        elif pattern == "joker_bomb":
            bomb_score_raw += 10

    bomb_score = min(15, bomb_score_raw)

    control_points_score = 0.0
    for token in hand_cards:
        rank = _token_rank(token)
        if rank == "A":
            control_points_score += 1.0
        elif rank == current_level_rank:
            control_points_score += 1.5
        elif rank == "SJ":
            control_points_score += 3.0
        elif rank == "BJ":
            control_points_score += 4.0

    control_points_score = min(15.0, control_points_score)
    control_score = bomb_score + _round_half_up(control_points_score)
    control_score = min(30, control_score)

    wildcard_token = f"{current_level_rank}H" if current_level_rank else ""
    wildcard_count = hand_cards.count(wildcard_token) if wildcard_token else 0
    diversity_count = len({str(action.get("declared_pattern")) for action in legal_actions})

    potential_score = 0
    if wildcard_count > 0:
        potential_score += 10
    if diversity_count >= 5:
        potential_score += 20
    elif diversity_count == 4:
        potential_score += 15
    elif diversity_count == 3:
        potential_score += 10
    elif diversity_count == 2:
        potential_score += 5
    potential_score = min(30, potential_score)

    total_score = max(0, min(100, structure_score + control_score + potential_score))
    label = _label_from_total(total_score)

    comment = "，".join(
        part for part in (
            _structure_comment(
                remaining_single_card_count,
                steel_plate_count=steel_plate_count,
                straight_count=straight_count,
                pair_straight_count=pair_straight_count,
                triple_with_pair_count=triple_with_pair_count,
            ),
            _control_comment(bomb_score, control_points_score),
            _potential_comment(wildcard_count, diversity_count),
        )
        if part
    )

    return {
        "total_score": int(total_score),
        "structure_score": int(structure_score),
        "control_score": int(control_score),
        "potential_score": int(potential_score),
        "label": label,
        "comment": comment,
    }