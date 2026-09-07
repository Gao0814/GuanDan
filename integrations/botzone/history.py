"""Opt-in, human-readable connector-observed history artifact.

This module deliberately consumes only durable session snapshots and finished
rows.  It never participates in protocol validation, response delivery, or
audit aggregation: a failed diagnostic write must not change a game action.
"""

from __future__ import annotations

import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .cards import TOTAL_CARDS, card_from_id
from .models import HistoryEntry
from .poll import FinishedRow
from .play_adapter import AdapterError, _history_entry_to_action
from .result_observability import classify_finished_score

if TYPE_CHECKING:
    from .session import SessionRecord


_SUIT_NAMES = {"h": "红桃", "d": "方块", "s": "黑桃", "c": "梅花"}
_SUIT_TOKENS = {"h": "H", "d": "D", "s": "S", "c": "C"}
_PATTERN_LABELS = {
    "single": "单张",
    "pair": "对子",
    "triple": "三张",
    "triple_with_pair": "三带二",
    "straight": "顺子",
    "pair_straight": "连对",
    "steel_plate": "钢板",
    "bomb": "炸弹",
    "straight_flush": "同花顺",
    "joker_bomb": "天王炸",
}


class HistoryWriteError(ValueError):
    """The optional artifact cannot be safely replaced."""


def _player(player_id: int) -> str:
    return f"玩家{player_id + 1}"


def _physical_card(card_id: int) -> str:
    card = card_from_id(card_id)
    if card.rank == "SJ":
        return "SJ（小王）"
    if card.rank == "BJ":
        return "BJ（大王）"
    assert card.suit is not None
    return f"{_SUIT_TOKENS[card.suit]}{card.rank}（{_SUIT_NAMES[card.suit]}{card.rank}）"


def _declared_card(card_id: int) -> str:
    card = card_from_id(card_id)
    if card.rank == "SJ":
        return "小王"
    if card.rank == "BJ":
        return "大王"
    return card.rank


def _pattern_label(entry: HistoryEntry, level: str) -> str:
    if entry.response.is_pass:
        return "pass"
    try:
        action = _history_entry_to_action(entry, level)
    except AdapterError as exc:
        raise HistoryWriteError("unsupported_history_pattern") from exc
    if action.declared_pattern is None:
        raise HistoryWriteError("unsupported_history_pattern")
    label = _PATTERN_LABELS.get(action.declared_pattern.value)
    if label is None:
        raise HistoryWriteError("unsupported_history_pattern")
    return label


def _is_free_before(events: tuple[HistoryEntry, ...], player_id: int) -> bool:
    for entry in reversed(events[-4:]):
        if entry.player_id == player_id:
            break
        if not entry.response.is_pass:
            return False
    return True


def _rounds(history: tuple[HistoryEntry, ...]) -> tuple[tuple[int, tuple[HistoryEntry, ...]], ...]:
    grouped: list[tuple[int, list[HistoryEntry]]] = []
    prior: list[HistoryEntry] = []
    round_no = 0
    for entry in history:
        if _is_free_before(tuple(prior), entry.player_id):
            round_no += 1
            grouped.append((round_no, []))
        if not grouped:
            raise HistoryWriteError("invalid_round_history")
        grouped[-1][1].append(entry)
        prior.append(entry)
    return tuple((number, tuple(entries)) for number, entries in grouped)


def _played_counts(history: tuple[HistoryEntry, ...]) -> Counter[int]:
    counts: Counter[int] = Counter()
    seen: set[int] = set()
    for entry in history:
        for card_id in entry.response.action:
            if card_id in seen:
                raise HistoryWriteError("duplicate_public_entity")
            seen.add(card_id)
            counts[entry.player_id] += 1
    return counts


def _initial_hand(record: "SessionRecord", history: tuple[HistoryEntry, ...]) -> tuple[int, ...]:
    observed_local = tuple(
        card_id
        for entry in history
        if entry.player_id == record.local_player_id
        for card_id in entry.response.action
    )
    hand = tuple(sorted(set(record.own_hand) | set(observed_local)))
    if len(hand) != 27 or len(set(record.own_hand)) != len(record.own_hand):
        raise HistoryWriteError("initial_hand_unavailable")
    return hand


def _hand_after(initial: tuple[int, ...], history: tuple[HistoryEntry, ...], local_player_id: int) -> tuple[int, ...]:
    used = {
        card_id
        for entry in history
        if entry.player_id == local_player_id
        for card_id in entry.response.action
    }
    if not used.issubset(initial):
        raise HistoryWriteError("local_hand_conservation_failed")
    return tuple(card_id for card_id in initial if card_id not in used)


def _hands_block(
    initial: tuple[int, ...],
    history: tuple[HistoryEntry, ...],
    local_player_id: int,
    inferred_initials: dict[int, tuple[int, ...]] | None = None,
) -> list[str]:
    counts = _played_counts(history)
    local_hand = _hand_after(initial, history, local_player_id)
    lines: list[str] = []
    for player_id in range(4):
        if player_id == local_player_id:
            lines.append(f"{_player(player_id)}手牌：{' '.join(_physical_card(card_id) for card_id in local_hand)}")
        elif inferred_initials is not None:
            inferred = _hand_after(inferred_initials[player_id], history, player_id)
            lines.append(f"{_player(player_id)}手牌：推导手牌 {' '.join(_physical_card(card_id) for card_id in inferred)}")
        else:
            remaining = 27 - counts[player_id]
            if not 0 <= remaining <= 27:
                raise HistoryWriteError("public_capacity_invalid")
            lines.append(f"{_player(player_id)}手牌：未知（剩余{remaining}张）")
    return lines


def _terminal_inference(history: tuple[HistoryEntry, ...]) -> tuple[bool, tuple[int | None, ...]]:
    """Return ranks only when the observed actions prove all hidden sets."""

    try:
        counts = _played_counts(history)
    except HistoryWriteError:
        return False, (None, None, None, None)
    finished = [player_id for player_id in range(4) if counts[player_id] == 27]
    remaining = [player_id for player_id in range(4) if counts[player_id] < 27]
    if len(finished) != 3 or len(remaining) != 1 or sum(counts.values()) > TOTAL_CARDS:
        return False, (None, None, None, None)
    reached: list[int] = []
    running: Counter[int] = Counter()
    for entry in history:
        running[entry.player_id] += len(entry.response.action)
        if running[entry.player_id] == 27:
            reached.append(entry.player_id)
    if len(reached) != 3 or len(set(reached)) != 3 or set(reached) != set(finished):
        return False, (None, None, None, None)
    return True, tuple(reached + remaining)


def _inferred_initial_hands(history: tuple[HistoryEntry, ...]) -> dict[int, tuple[int, ...]] | None:
    complete, ranks = _terminal_inference(history)
    if not complete:
        return None
    by_player: dict[int, set[int]] = {player_id: set() for player_id in range(4)}
    all_played: set[int] = set()
    for entry in history:
        by_player[entry.player_id].update(entry.response.action)
        all_played.update(entry.response.action)
    last = ranks[-1]
    assert last is not None
    by_player[last].update(set(range(TOTAL_CARDS)) - all_played)
    if any(len(cards) != 27 for cards in by_player.values()):
        return None
    return {player_id: tuple(sorted(cards)) for player_id, cards in by_player.items()}


def _combined_history(record: "SessionRecord") -> tuple[HistoryEntry, ...]:
    """Merge public history with acknowledged local evidence without guessing order."""

    public = record.history
    extra: list[HistoryEntry] = []
    for confirmed in record.confirmed_history:
        if confirmed.public_history_length > len(public):
            raise HistoryWriteError("confirmed_history_alignment_failed")
        tail = public[confirmed.public_history_length:]
        exact = [entry for entry in tail if entry == confirmed.entry]
        same_carrier = [
            entry
            for entry in tail
            if entry.player_id == confirmed.entry.player_id and entry.response.action == confirmed.entry.response.action
        ]
        if exact:
            continue
        if same_carrier or len(public) != confirmed.public_history_length:
            raise HistoryWriteError("confirmed_history_conflict")
        extra.append(confirmed.entry)
    return public + tuple(extra)


@dataclass(slots=True)
class ConnectorObservedHistory:
    """Best-effort atomic writer for one explicitly selected diagnostic file."""

    path: Path | str
    failed: bool = False
    _bound_match: str | None = None

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @property
    def status(self) -> str:
        return "failed" if self.failed else "ok"

    def update(self, record: "SessionRecord") -> None:
        if self.failed:
            return
        try:
            self._bind(record.match_id)
            self._write(self._render(record, None))
        except (HistoryWriteError, OSError):
            self.failed = True

    def finish(self, record: "SessionRecord", row: FinishedRow) -> None:
        if self.failed:
            return
        try:
            self._bind(record.match_id)
            self._write(self._render(record, row))
        except (HistoryWriteError, OSError):
            self.failed = True

    def _bind(self, match_id: str) -> None:
        if self._bound_match is None:
            self._bound_match = match_id
        elif self._bound_match != match_id:
            raise HistoryWriteError("history_match_conflict")

    def _write(self, text: str) -> None:
        target = Path(self.path)
        parent = target.parent
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def _render(self, record: "SessionRecord", row: FinishedRow | None) -> str:
        history = _combined_history(record)
        initial = _initial_hand(record, history)
        _played_counts(history)
        complete, ranks = _terminal_inference(history) if row is not None else (False, (None, None, None, None))
        inferred_initials = _inferred_initial_hands(history) if complete else None
        lines = ["==== Connector Observed History ===="]
        lines.extend(_hands_block(initial, (), record.local_player_id, inferred_initials))
        lines.extend(
            (
                "",
                f"本家座位：{_player(record.local_player_id)}",
                f"当前级牌：{record.global_state.level}",
                "轮次说明：第N轮仅表示 connector 按已观察公开动作划分的第N个牌权段，不保证等于裁判完整终局轮次。",
                "",
            )
        )
        rounds = _rounds(history)
        consumed = 0
        for index, (round_no, entries) in enumerate(rounds):
            lines.append(f"==== 第{round_no}轮 ====")
            for step_no, entry in enumerate(entries, start=1):
                if entry.response.is_pass:
                    lines.append(f"第{round_no}轮 第{step_no}步 {_player(entry.player_id)}：pass")
                else:
                    declared = ",".join(_declared_card(card_id) for card_id in entry.response.claim)
                    carriers = ", ".join(_physical_card(card_id) for card_id in entry.response.action)
                    lines.append(f"第{round_no}轮 第{step_no}步 {_player(entry.player_id)}：{_pattern_label(entry, record.global_state.level)} {declared}")
                    lines.append(f"  声明牌：{declared}")
                    lines.append(f"  载体牌：{carriers}")
            consumed += len(entries)
            if index < len(rounds) - 1:
                lines.extend(("", f"==== 第{round_no}轮结束后的手牌 ===="))
                lines.extend(_hands_block(initial, history[:consumed], record.local_player_id, inferred_initials))
            elif row is not None:
                hand_heading = "==== 对局结束时的手牌 ====" if complete else "==== 最后一次观测后的手牌（该牌权段可能尚未结束） ===="
                lines.extend(("", hand_heading))
                lines.extend(_hands_block(initial, history[:consumed], record.local_player_id, inferred_initials))
            lines.append("")
        if row is not None:
            result, _ = classify_finished_score(row.local_player_id, row.scores)
            result_text = {"local_team_win": "胜", "local_team_loss": "负"}.get(result, "未知")
            lines.append("==== 对局结束 ====")
            lines.append(f"本队结果：{result_text}")
            labels = ("头游", "二游", "三游", "四游")
            for label, player_id in zip(labels, ranks):
                lines.append(f"{label}：{_player(player_id) if player_id is not None else '未知'}")
            if not complete:
                local_played = _played_counts(history)[record.local_player_id]
                if local_played == 27:
                    lines.append("说明：平台已通知对局结束；本家出完后至终局的公开动作可能未被 connector 观察到。")
                else:
                    lines.append("说明：平台已通知对局结束；最后一次观测后至终局的公开动作可能未被 connector 观察到。")
            lines.append(
                "history_completeness: terminal_history_complete" if complete
                else "history_completeness: terminal_tail_may_be_unobserved"
            )
        return "\n".join(lines).rstrip() + "\n"
