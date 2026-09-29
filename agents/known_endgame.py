"""Model-facing summaries for publicly confirmed, bounded endgame searches."""

from __future__ import annotations

from itertools import combinations

from engine.public_endgame import (
    PUBLIC_ENDGAME_MAX_CARDS,
    PUBLIC_ENDGAME_MAX_NODES,
    PUBLIC_ENDGAME_MAX_SECONDS,
    PublicEndgameAnalysis,
)


_OUTCOME_TEXT = {
    1: "本队可保胜",
    0: "双方最优回应下可和",
    -1: "本队无法避免负局",
}


def format_public_endgame_comparisons(
    analysis: PublicEndgameAnalysis,
    displayed_actions: list[dict[str, object]],
    *,
    preferred_action_ids: tuple[int, ...] = (),
    max_pairs: int = 2,
) -> str | None:
    """Format only distinct, solved values for actual displayed legal IDs."""
    if analysis.status != "solved" or type(max_pairs) is not int or max_pairs <= 0:
        return None
    values = dict(analysis.action_values)
    if any(type(value) is not int or value not in _OUTCOME_TEXT for value in values.values()):
        return None
    visible = [
        action for action in displayed_actions
        if type(action.get("action_id")) is int
        and int(action["action_id"]) in values
    ]
    preferred = set(preferred_action_ids)
    pairs = []
    for first, second in combinations(visible, 2):
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        first_value = values[first_id]
        second_value = values[second_id]
        if first_value == second_value:
            continue
        anchored = int(first_id in preferred) + int(second_id in preferred)
        pairs.append((
            (anchored, abs(first_value - second_value), max(first_value, second_value)),
            first,
            second,
        ))
    pairs.sort(key=lambda item: (
        item[0],
        -min(int(item[1]["action_id"]), int(item[2]["action_id"])),
        -max(int(item[1]["action_id"]), int(item[2]["action_id"])),
    ), reverse=True)

    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    used_ids: set[int] = set()
    for _, first, second in pairs:
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        if first_id in used_ids or second_id in used_ids:
            continue
        selected.append((first, second))
        used_ids.update((first_id, second_id))
        if len(selected) >= max_pairs:
            break
    if not selected:
        return None

    lines = [
        "【公开残局推演】活动玩家当前手牌由108张守恒与公开历史唯一确认；"
        "使用引擎合法动作、轮转、pass、牌权重置和终局真值作双方最优回应搜索；"
        f"总余牌不超过{PUBLIC_ENDGAME_MAX_CARDS}张，搜索上限"
        f"{PUBLIC_ENDGAME_MAX_NODES}节点/{PUBLIC_ENDGAME_MAX_SECONDS * 1000:.0f}毫秒；"
        "仅适用于本局当前状态且完整搜索未超限，不是胜率或概率。"
    ]
    for first, second in selected:
        first_id = int(first["action_id"])
        second_id = int(second["action_id"])
        first_value = values[first_id]
        second_value = values[second_id]
        first_label = str(first.get("display_text", first.get("declared_pattern", "")))[:72]
        second_label = str(second.get("display_text", second.get("declared_pattern", "")))[:72]
        lines.append(
            f"M5公开残局对照 action_id={first_id}({first_label})"
            f"={_OUTCOME_TEXT[first_value]} vs "
            f"action_id={second_id}({second_label})"
            f"={_OUTCOME_TEXT[second_value]}；"
            "该结果来自两队分别追求本队终局结果的对抗搜索。"
        )
    return "\n".join(lines)
