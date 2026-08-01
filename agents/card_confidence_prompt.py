from __future__ import annotations

from dataclasses import dataclass
from math import gcd

from agents.card_confidence import CardConfidenceState


CARD_CONFIDENCE_PROMPT_MAX_CHARS = 2400

_PHASE = "critical_endgame"
_SOURCE = "physical_assignment_marginal_v1"
_SCOPE = "critical_endgame_policy_diverse_v1"
_RANK_ORDER = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2", "SJ", "BJ")
_RANK_INDEX = {rank: index for index, rank in enumerate(_RANK_ORDER)}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _is_non_negative_int(value: object) -> bool:
    return _is_int(value) and value >= 0


@dataclass(frozen=True, slots=True)
class CardConfidencePromptPayload:
    status: str
    text: str
    char_count: int
    source: str
    calibration_scope: str
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "text": self.text,
            "char_count": self.char_count,
            "source": self.source,
            "calibration_scope": self.calibration_scope,
            "diagnostics": list(self.diagnostics),
        }


def _omitted(diagnostics: list[str]) -> CardConfidencePromptPayload:
    return CardConfidencePromptPayload(
        status="omitted",
        text="",
        char_count=0,
        source="none",
        calibration_scope="none",
        diagnostics=tuple(diagnostics),
    )


def _exact_text(numerator: int, denominator: int) -> str:
    if numerator == 0:
        return "0"
    divisor = gcd(numerator, denominator)
    reduced_numerator = numerator // divisor
    reduced_denominator = denominator // divisor
    if reduced_denominator == 1:
        return str(reduced_numerator)
    return f"{reduced_numerator}/{reduced_denominator}"


def build_card_confidence_prompt_payload(
    confidence: CardConfidenceState,
    *,
    max_chars: int = CARD_CONFIDENCE_PROMPT_MAX_CHARS,
) -> CardConfidencePromptPayload:
    """Render verified integer marginals into a bounded, exact payload."""

    if not _is_int(max_chars) or not 1 <= max_chars <= CARD_CONFIDENCE_PROMPT_MAX_CHARS:
        raise ValueError("max_chars must be a non-bool integer from 1 through 2400")

    diagnostics: list[str] = []

    def diagnose(code: str) -> None:
        if code not in diagnostics:
            diagnostics.append(code)

    if not isinstance(confidence, CardConfidenceState):
        return _omitted(["invalid_confidence_state"])

    try:
        if confidence.status != "available":
            diagnose("confidence_unavailable")
        if confidence.phase != _PHASE:
            diagnose("invalid_phase")
        if confidence.source != _SOURCE:
            diagnose("invalid_source")
        if confidence.calibration_scope != _SCOPE:
            diagnose("invalid_calibration_scope")
        if not isinstance(confidence.diagnostics, tuple) or confidence.diagnostics:
            diagnose("confidence_diagnostics_present")

        external_count = confidence.external_unknown_count
        denominator = confidence.physical_assignment_count
        if not _is_int(external_count) or not 1 <= external_count <= 12:
            diagnose("invalid_external_unknown_count")
        if not _is_positive_int(denominator):
            diagnose("invalid_denominator")

        players = confidence.players
        if not isinstance(players, tuple) or not 1 <= len(players) <= 3:
            diagnose("invalid_player")
            return _omitted(diagnostics)

        seen_player_ids: set[int] = set()
        rank_layout: tuple[str, ...] | None = None
        capacity_total = 0
        rendered_players: list[tuple[int, int, tuple[tuple[str, int, int], ...]]] = []
        for player in players:
            player_id = getattr(player, "player_id", None)
            remaining_capacity = getattr(player, "remaining_capacity", None)
            ranks = getattr(player, "ranks", None)
            if not _is_int(player_id) or not 1 <= player_id <= 4:
                diagnose("invalid_player")
                continue
            if player_id in seen_player_ids:
                diagnose("duplicate_player")
                continue
            seen_player_ids.add(player_id)
            if not _is_int(remaining_capacity) or not 1 <= remaining_capacity <= 12:
                diagnose("invalid_capacity")
                continue
            capacity_total += remaining_capacity
            if not isinstance(ranks, tuple) or not ranks:
                diagnose("invalid_rank_order")
                continue

            rank_names: list[str] = []
            rank_values: list[tuple[str, int, int]] = []
            for marginal in ranks:
                rank = getattr(marginal, "rank", None)
                presence = getattr(marginal, "presence_numerator", None)
                copies = getattr(marginal, "expected_copy_numerator", None)
                marginal_denominator = getattr(marginal, "denominator", None)
                if not isinstance(rank, str) or rank not in _RANK_INDEX:
                    diagnose("invalid_rank_order")
                    continue
                rank_names.append(rank)
                if (
                    marginal_denominator != denominator
                    or not _is_non_negative_int(presence)
                    or (isinstance(denominator, int) and not isinstance(denominator, bool) and presence > denominator)
                    or not _is_non_negative_int(copies)
                    or (
                        isinstance(denominator, int)
                        and not isinstance(denominator, bool)
                        and copies > remaining_capacity * denominator
                    )
                ):
                    diagnose("invalid_rank_marginal")
                    continue
                rank_values.append((rank, presence, copies))

            rank_tuple = tuple(rank_names)
            if len(set(rank_tuple)) != len(rank_tuple):
                diagnose("duplicate_rank")
            if rank_tuple != tuple(sorted(rank_tuple, key=_RANK_INDEX.__getitem__)):
                diagnose("invalid_rank_order")
            if rank_layout is None:
                rank_layout = rank_tuple
            elif rank_tuple != rank_layout:
                diagnose("rank_set_mismatch")
            rendered_players.append((player_id, remaining_capacity, tuple(rank_values)))

        if capacity_total != external_count:
            diagnose("capacity_mismatch")
        if diagnostics:
            return _omitted(diagnostics)

        lines = [
            f"范围：{_SCOPE}",
            "说明：以下是公开硬约束下等权物理分配的组合边际，不是隐藏牌事实；P=至少持有一张，E=期望张数。",
        ]
        for player_id, capacity, ranks in rendered_players:
            rank_text = "；".join(
                f"{rank}[P={_exact_text(presence, denominator)},E={_exact_text(copies, denominator)}]"
                for rank, presence, copies in ranks
            )
            lines.append(f"玩家{player_id}（余{capacity}张）：{rank_text}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            return _omitted(["prompt_budget_exceeded"])
        return CardConfidencePromptPayload(
            status="ready",
            text=text,
            char_count=len(text),
            source=_SOURCE,
            calibration_scope=_SCOPE,
            diagnostics=(),
        )
    except Exception:
        return _omitted(["invalid_confidence_state"])
