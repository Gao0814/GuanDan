"""Narrow, source-backed opening conventions over public canonical actions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from agents.game_phase import GamePhaseContext, OPENING, classify_game_phase


_NORMAL_RANKS = frozenset({"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"})
_SUITS = frozenset({"S", "H", "C", "D"})
_CONTROL_RANKS = frozenset({"A", "2", "SJ", "BJ"})
_PRESSURE_PATTERNS = frozenset({"bomb", "straight_flush", "joker_bomb"})
_PATTERNS = frozenset(
    {
        "single",
        "pair",
        "triple",
        "triple_with_pair",
        "straight",
        "pair_straight",
        "steel_plate",
        "bomb",
        "straight_flush",
        "joker_bomb",
    }
)
_RANK_ORDER = {
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
    "2": 15,
    "SJ": 16,
    "BJ": 17,
}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _rank_of(token: str) -> str:
    if token in {"SJ", "BJ"}:
        return token
    return token[:-1]


def _is_valid_token(token: object) -> bool:
    if not isinstance(token, str):
        return False
    if token in {"SJ", "BJ"}:
        return True
    return len(token) >= 2 and token[-1] in _SUITS and token[:-1] in _NORMAL_RANKS


def normalize_hand_strength(hand_eval: dict[str, object] | None) -> str:
    """Map the existing public hand evaluation to stable strategy roles."""

    if not isinstance(hand_eval, dict):
        return "medium"
    label = str(hand_eval.get("label", "")).strip().lower()
    if label in {"极强", "较强", "strong", "very_strong", "rather_strong"}:
        return "strong"
    if label in {"偏弱", "极弱", "weak", "very_weak", "rather_weak"}:
        return "weak"
    if label in {"中等", "medium", "average", "fair"}:
        return "medium"
    score = _coerce_int(hand_eval.get("total_score"), default=-1)
    if score >= 60:
        return "strong"
    if 0 <= score < 40:
        return "weak"
    return "medium"


class OpeningFormulaStrategy:
    """Apply only the strong-control natural-small-single opening convention."""

    def _is_applicable(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        *,
        phase_context: GamePhaseContext | None = None,
    ) -> bool:
        """Report only the shared phase/lead gate; selection remains stricter."""

        if not legal_actions or not isinstance(observation, Mapping):
            return False
        current_round = observation.get("current_round")
        if not isinstance(current_round, Mapping):
            return False
        try:
            computed = classify_game_phase(observation)
        except Exception:
            return False
        return (
            current_round.get("constraint") == "free"
            and current_round.get("table_action") is None
            and computed.phase == OPENING
            and (phase_context is None or phase_context == computed)
        )

    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None = None,
        phase_context: GamePhaseContext | None = None,
    ) -> object | None:
        validated = self._validated_context(observation, legal_actions, phase_context)
        if validated is None:
            return None
        hand, level_rank = validated
        strength = normalize_hand_strength(hand_eval)
        if strength != "strong":
            return None

        rank_counts = Counter(_rank_of(card) for card in hand.elements())
        structured_tokens = {
            str(card)
            for action in legal_actions
            if action["wildcard_count"] == 0
            and len(action["carrier_cards"]) > 1
            for card in action["carrier_cards"]
        }
        safe_singles: list[tuple[int, dict[str, object]]] = []
        for action in legal_actions:
            if action["declared_pattern"] != "single" or action["wildcard_count"] != 0:
                continue
            carriers = action["carrier_cards"]
            declared = action["declared_cards"]
            assert isinstance(carriers, list) and isinstance(declared, list)
            if len(carriers) != 1 or len(declared) != 1:
                continue
            carrier_rank = _rank_of(str(carriers[0]))
            declared_rank = str(declared[0])
            if _is_valid_token(declared_rank):
                declared_rank = _rank_of(declared_rank)
            if (
                declared_rank != carrier_rank
                or carrier_rank in _CONTROL_RANKS
                or carrier_rank == level_rank
                or rank_counts.get(carrier_rank) != 1
                or str(carriers[0]) in structured_tokens
            ):
                continue
            safe_singles.append((_RANK_ORDER[carrier_rank], action))

        distinct_ranks = {rank_value for rank_value, _ in safe_singles}
        if len(distinct_ranks) < 2:
            return None
        lowest = min(distinct_ranks)
        targets = [action for rank_value, action in safe_singles if rank_value == lowest]
        if len(targets) != 1 or not self._has_return_resource(hand, legal_actions, level_rank):
            return None
        return targets[0]["action_id"]

    @staticmethod
    def _has_return_resource(
        hand: Counter[str],
        legal_actions: list[dict[str, object]],
        level_rank: str,
    ) -> bool:
        if any(_rank_of(card) in _CONTROL_RANKS | {level_rank} for card in hand):
            return True
        return any(
            action["declared_pattern"] in _PRESSURE_PATTERNS
            and action["wildcard_count"] == 0
            for action in legal_actions
        )

    @staticmethod
    def _validated_context(
        observation: object,
        legal_actions: object,
        phase_context: GamePhaseContext | None,
    ) -> tuple[Counter[str], str] | None:
        if not isinstance(observation, Mapping):
            return None
        my_info = observation.get("my_info")
        current_round = observation.get("current_round")
        if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping):
            return None
        player_id = my_info.get("player_id")
        hand_count = my_info.get("hand_count")
        hand_cards = my_info.get("hand_cards")
        level_rank = current_round.get("current_level_rank")
        try:
            computed_phase = classify_game_phase(dict(observation))
        except Exception:
            return None
        hand_token_counts = Counter(hand_cards) if isinstance(hand_cards, list) else Counter()
        if (
            not _is_int(player_id)
            or not _is_int(hand_count)
            or hand_count <= 0
            or not isinstance(hand_cards, list)
            or len(hand_cards) != hand_count
            or any(not _is_valid_token(card) for card in hand_cards)
            or any(count > 2 for count in hand_token_counts.values())
            or type(level_rank) is not str
            or level_rank not in _NORMAL_RANKS
            or current_round.get("current_player_id") != player_id
            or current_round.get("constraint") != "free"
            or current_round.get("table_action") is not None
            or computed_phase.phase != OPENING
            or (phase_context is not None and phase_context != computed_phase)
            or not isinstance(legal_actions, Sequence)
            or isinstance(legal_actions, (str, bytes))
            or len(legal_actions) < 2
        ):
            return None

        hand = hand_token_counts
        action_ids: set[int] = set()
        for action in legal_actions:
            if not isinstance(action, Mapping):
                return None
            action_id = action.get("action_id")
            pattern = action.get("declared_pattern")
            declared = action.get("declared_cards")
            carriers = action.get("carrier_cards")
            wildcard_count = action.get("wildcard_count")
            wildcard_info = action.get("wildcard_info")
            if (
                not _is_int(action_id)
                or action_id in action_ids
                or pattern not in _PATTERNS
                or not isinstance(declared, list)
                or not declared
                or any(not isinstance(card, str) or not card for card in declared)
                or not isinstance(carriers, list)
                or not carriers
                or len(declared) != len(carriers)
                or any(not _is_valid_token(card) for card in carriers)
                or not _is_int(wildcard_count)
                or wildcard_count < 0
                or wildcard_count > len(carriers)
                or not isinstance(wildcard_info, list)
                or len(wildcard_info) != wildcard_count
                or any(not isinstance(item, Mapping) for item in wildcard_info)
                or not isinstance(action.get("display_text"), str)
                or not action.get("display_text")
            ):
                return None
            used = Counter(carriers)
            if any(count <= 0 or count > hand.get(card, 0) for card, count in used.items()):
                return None
            action_ids.add(action_id)
        return hand, level_rank
