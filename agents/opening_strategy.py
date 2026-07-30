"""Formula-based early lead strategy for DeepSeek-free opening decisions.

This module only consumes public observation and legal_actions payloads.  It
never constructs actions and never decides legality.
"""

from __future__ import annotations


EARLY_MAX_HISTORY_ACTIONS = 8
EARLY_MIN_SELF_HAND_COUNT = 18
EARLY_MIN_OTHER_HAND_COUNT = 16
HIGH_RISK_PATTERNS = {"bomb", "straight_flush", "joker_bomb"}
RUN_PATTERNS = {"triple_with_pair", "pair_straight", "straight", "steel_plate"}
CONTROL_RANKS = {"A", "2", "SJ", "BJ"}
RANK_ORDER = {
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
PATTERN_BASE_SCORE = {
    "single": 10,
    "pair": 24,
    "triple": 20,
    "triple_with_pair": 32,
    "straight": 28,
    "pair_straight": 30,
    "steel_plate": 34,
    "bomb": -60,
    "straight_flush": -55,
    "joker_bomb": -80,
}


def normalize_hand_strength(hand_eval: dict[str, object] | None) -> str:
    """Map hand-evaluation payloads to stable strategy roles."""
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
    if score >= 0 and score < 40:
        return "weak"
    return "medium"


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _rank_of(token: object) -> str:
    value = str(token)
    if value in {"SJ", "BJ"}:
        return value
    if len(value) >= 2 and value[-1] in {"S", "H", "C", "D"}:
        return value[:-1]
    return value


def _action_id_sort_value(action: dict[str, object]) -> int:
    return _coerce_int(action.get("action_id"), default=10**9)


class OpeningFormulaStrategy:
    """Select an early free-lead action from original legal_actions."""

    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None = None,
    ) -> object | None:
        if not self._is_applicable(observation, legal_actions):
            return None

        candidates = [
            action
            for action in legal_actions
            if str(action.get("declared_pattern")) != "pass"
        ]
        if not candidates:
            return None

        non_risk = [
            action
            for action in candidates
            if str(action.get("declared_pattern")) not in HIGH_RISK_PATTERNS
        ]
        scorable = non_risk or candidates
        if not scorable:
            return None

        context = self._context(observation, legal_actions, hand_eval)
        scored = [
            (self._score_action(action, context, bool(non_risk)), self._tie_break(action), action)
            for action in scorable
        ]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2].get("action_id")

    def _is_applicable(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> bool:
        if not legal_actions:
            return False
        if all(str(action.get("declared_pattern")) == "pass" for action in legal_actions):
            return False

        current_round = dict(observation.get("current_round", {}))
        if current_round.get("table_action") is not None:
            return False
        constraint = str(current_round.get("constraint", "free"))
        if constraint != "free":
            return False

        history = dict(observation.get("history", {}))
        history_actions = list(history.get("actions", []))
        if len(history_actions) > EARLY_MAX_HISTORY_ACTIONS:
            return False

        my_info = dict(observation.get("my_info", {}))
        hand_count = _coerce_int(my_info.get("hand_count"), default=-1)
        if hand_count < EARLY_MIN_SELF_HAND_COUNT:
            return False

        other_players = list(observation.get("other_players", []))
        if len(other_players) != 3:
            return False
        other_counts = [
            _coerce_int(dict(player).get("hand_count"), default=-1)
            for player in other_players
            if not bool(dict(player).get("finished", False))
        ]
        if len(other_counts) != 3:
            return False
        if min(other_counts) < EARLY_MIN_OTHER_HAND_COUNT:
            return False

        return True

    def _context(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None,
    ) -> dict[str, object]:
        my_info = dict(observation.get("my_info", {}))
        current_round = dict(observation.get("current_round", {}))
        hand_cards = [str(card) for card in my_info.get("hand_cards", [])]
        ranks = [_rank_of(card) for card in hand_cards]
        current_level_rank = str(current_round.get("current_level_rank", ""))
        strength_role = normalize_hand_strength(hand_eval)
        control_score = _coerce_int(hand_eval.get("control_score"), default=0) if isinstance(hand_eval, dict) else 0
        remaining_singles = _coerce_int(my_info.get("remaining_single_card_count"), default=0)
        has_control = bool({"SJ", "BJ"} & set(ranks)) or control_score >= 18
        has_natural_triple_with_pair = any(
            str(action.get("declared_pattern")) == "triple_with_pair"
            and _coerce_int(action.get("wildcard_count"), default=0) == 0
            for action in legal_actions
        )
        return {
            "strength_role": strength_role,
            "control_score": control_score,
            "remaining_singles": remaining_singles,
            "has_control": has_control,
            "has_joker": bool({"SJ", "BJ"} & set(ranks)),
            "current_level_rank": current_level_rank,
            "has_natural_triple_with_pair": has_natural_triple_with_pair,
        }

    def _score_action(
        self,
        action: dict[str, object],
        context: dict[str, object],
        has_non_risk_option: bool,
    ) -> int:
        pattern = str(action.get("declared_pattern"))
        declared_ranks = [_rank_of(token) for token in action.get("declared_cards", [])]
        carrier_ranks = [_rank_of(token) for token in action.get("carrier_cards", [])]
        wildcard_count = _coerce_int(action.get("wildcard_count"), default=0)
        carrier_count = len(list(action.get("carrier_cards", [])))
        main_rank = declared_ranks[0] if declared_ranks else ""
        main_value = RANK_ORDER.get(main_rank, 0)
        strength_role = str(context.get("strength_role", "medium"))
        control_score = _coerce_int(context.get("control_score"), default=0)
        has_control = bool(context.get("has_control", False))
        current_level_rank = str(context.get("current_level_rank", ""))
        is_risk = pattern in HIGH_RISK_PATTERNS
        is_natural = wildcard_count == 0
        is_joker_single = pattern == "single" and main_rank in {"SJ", "BJ"}
        is_control_single = pattern == "single" and (
            main_rank in CONTROL_RANKS or main_rank == current_level_rank
        )

        score = PATTERN_BASE_SCORE.get(pattern, 0)
        score += carrier_count * 5
        score -= wildcard_count * 16
        if is_natural:
            score += 8
        if is_risk:
            score -= 70 if has_non_risk_option else 20

        if strength_role == "strong" or control_score >= 20:
            score += self._strong_hand_adjustment(pattern, main_value, is_joker_single, is_control_single)
        elif strength_role == "medium":
            score += self._medium_hand_adjustment(pattern, is_natural)
        elif strength_role == "weak":
            score += self._weak_hand_adjustment(pattern, main_value, is_natural)

        if pattern == "single" and has_control and not is_control_single:
            score += 18
        if pattern == "single" and is_joker_single:
            score -= 45
        if pattern == "single" and main_value <= RANK_ORDER["8"]:
            score -= 25
        if pattern == "single" and main_value >= RANK_ORDER["9"]:
            score += 12
        if pattern == "triple_with_pair" and is_natural and not bool(context.get("has_joker", False)):
            score += 18
        if pattern in RUN_PATTERNS and is_natural:
            score += 6
        if any(rank in {"SJ", "BJ"} for rank in carrier_ranks) and pattern != "single":
            score -= 30
        return score

    def _strong_hand_adjustment(
        self,
        pattern: str,
        main_value: int,
        is_joker_single: bool,
        is_control_single: bool,
    ) -> int:
        if pattern == "single":
            if is_joker_single:
                return -30
            if is_control_single:
                return -12
            return 24 + min(main_value, 12)
        if pattern == "pair":
            return 12
        if pattern in RUN_PATTERNS:
            return -6
        if pattern in HIGH_RISK_PATTERNS:
            return -80
        return 0

    def _medium_hand_adjustment(self, pattern: str, is_natural: bool) -> int:
        if pattern == "pair":
            return 40
        if pattern in RUN_PATTERNS:
            return 12 if is_natural else 4
        if pattern == "single":
            return -8
        return 0

    def _weak_hand_adjustment(self, pattern: str, main_value: int, is_natural: bool) -> int:
        if pattern in RUN_PATTERNS:
            return 28 if is_natural else 12
        if pattern == "pair":
            return 24
        if pattern == "triple":
            return 12
        if pattern == "single":
            return 14 if main_value >= RANK_ORDER["9"] else -35
        return 0

    def _tie_break(self, action: dict[str, object]) -> tuple[int, int, int, int, int]:
        wildcard_count = _coerce_int(action.get("wildcard_count"), default=0)
        pattern = str(action.get("declared_pattern"))
        is_risk = pattern in HIGH_RISK_PATTERNS
        carrier_count = len(list(action.get("carrier_cards", [])))
        return (
            -wildcard_count,
            0 if is_risk else 1,
            carrier_count,
            1 if wildcard_count == 0 else 0,
            -_action_id_sort_value(action),
        )
