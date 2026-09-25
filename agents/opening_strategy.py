"""Narrow, source-backed opening conventions over public canonical actions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from agents.action_structure import (
    CandidateStructure,
    representative_candidate_contrasts,
    summarize_candidate_structures,
)
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

# The direct rule is intentionally narrower than the model-before knowledge.
# All other public openings are routed to the existing RAG + DeepSeek path.
OPENING_FORMULA_CONDITION_TABLE = (
    (
        "direct_small_single",
        "exp_lead_opening_strong_001",
        "强牌开局自由首出；唯一最低自然单张、未处于实际展示的关系对照，且动作后还留有独立控制/压制回手资源时可本地直出；比较小单成本与资源路线",
    ),
    (
        "direct_natural_shape",
        "exp_lead_opening_shape_001, exp_lead_opening_weak_001",
        "任意开局牌力；自然对子/三张/顺子在完整canonical集合中是唯一Pareto未支配路线，剩余分组、孤张、拆组、通配、控制和压制成本均不差，并保留独立回手路线时可直出",
    ),
    (
        "model_single_tradeoff",
        "exp_lead_opening_strong_001, exp_soft_single_cost_probe_001",
        "低成本自然单张与较高单张/控制路线存在可见取舍时，将两侧原始候选及余组反例交给DeepSeek；软假设仅作可撤回输入",
    ),
    (
        "model_group_and_sequence_tradeoff",
        "exp_lead_opening_medium_001, exp_lead_opening_shape_001, exp_lead_opening_weak_001, exp_soft_pair_probe_001",
        "自然对子/三张/顺子与小单、同点拆分、连续结构或回手路线并存时，展示实际canonical关系和动作后结构；不设单张或成组牌型的固定顺序，软假设仅补充可撤回观察",
    ),
    (
        "model_resource_or_public_urgency",
        "exp_general_boundary_001, exp_soft_straight_flush_bomb_cost_001, exp_bomb_wildcard_001",
        "炸弹/通配/控制资源、公开队友协同或危险对手产生实质竞争时交给模型比较；炸弹软假设只在语料的对应条件/phase激活；紧急性、资源损失和可证回手作为反例，不推断暗牌",
    ),
    (
        "not_applicable",
        "any",
        "跟牌、非开局、公开输入或canonical候选畸形、公开紧急性或未能证明来源条件/独立回手时不作本地开局直选；立即出完仍由既有高优先级捷径处理",
    ),
)


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
    """Apply narrow source-backed openings only when public evidence is decisive.

    B-tier small-single guidance remains specific to strong hands.  For a
    natural pair, triple, or straight, a local choice is permitted only when
    it is the sole Pareto-undominated, structure-safe route across the full
    canonical action set and leaves an independent public return resource.
    Incomparable shapes and all material candidate relations remain model
    choices.
    """

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
        rank_counts = Counter(_rank_of(card) for card in hand.elements())
        facts = summarize_candidate_structures(observation, legal_actions)
        contrasts = representative_candidate_contrasts(observation, legal_actions)
        if facts is None or contrasts is None:
            return None
        if any(
            fact.finishes_hand
            for fact in facts
        ) or self._has_public_urgency(observation):
            return None
        actions_by_id = {int(action["action_id"]): action for action in legal_actions}
        facts_by_id = {fact.action_id: fact for fact in facts}

        # B-tier strong-hand small-single convention: do not promote a low
        # singleton if it is part of an observed relationship or has no
        # independently playable return route after the proposed lead.
        if strength == "strong":
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
                ):
                    continue
                safe_singles.append((_RANK_ORDER[carrier_rank], action))

            lowest = min((rank_value for rank_value, _ in safe_singles), default=None)
            targets = [action for rank_value, action in safe_singles if rank_value == lowest]
            if len(targets) == 1:
                target_id = targets[0]["action_id"]
                if (
                    not any(target_id in contrast.action_ids for contrast in contrasts)
                    and self._has_return_resource_after(
                        observation, targets[0], legal_actions, facts_by_id,
                    )
                ):
                    return target_id

        # B-tier structure guidance is not a fixed pair/triple/straight order.
        # A direct lead is allowed only when exactly one canonical action is
        # undominated on both visible residual grouping measures and on the
        # independently visible structure/resource costs.  Any incomparable
        # route, including a materially relevant contrast, goes to the model.
        frontier = [
            fact for fact in facts
            if not any(
                other.action_id != fact.action_id
                and self._profile_dominates(other, fact)
                for other in facts
            )
        ]
        if len(frontier) != 1:
            return None
        target_fact = frontier[0]
        if (
            target_fact.pattern not in {"pair", "triple", "straight"}
            or target_fact.uses_wildcard
            or target_fact.fragments_played_rank_group
            or target_fact.consumes_control_resource
            or target_fact.pattern in _PRESSURE_PATTERNS
        ):
            return None
        if target_fact.pattern == "straight" and any(
            contrast.kind == "natural_sequence_single"
            and target_fact.action_id in contrast.action_ids
            for contrast in contrasts
        ):
            # A straight versus one of its playable natural singletons is the
            # exact low-cost-probe tradeoff the source asks us to expose. Keep
            # it in the model path instead of resolving it by a local formula.
            return None
        target_action = actions_by_id.get(target_fact.action_id)
        if target_action is None or not self._has_return_resource_after(
            observation, target_action, legal_actions, facts_by_id,
        ):
            return None
        return target_fact.action_id

    @staticmethod
    def _profile_dominates(left: CandidateStructure, right: CandidateStructure) -> bool:
        """Compare source-backed costs without inventing scalar weights."""

        left_profile = (
            left.estimated_remaining_rank_groups,
            left.residual_singleton_rank_count,
            int(left.fragments_played_rank_group),
            int(left.uses_wildcard),
            int(left.consumes_control_resource),
            int(left.pattern in _PRESSURE_PATTERNS),
        )
        right_profile = (
            right.estimated_remaining_rank_groups,
            right.residual_singleton_rank_count,
            int(right.fragments_played_rank_group),
            int(right.uses_wildcard),
            int(right.consumes_control_resource),
            int(right.pattern in _PRESSURE_PATTERNS),
        )
        return all(a <= b for a, b in zip(left_profile, right_profile)) and any(
            a < b for a, b in zip(left_profile, right_profile)
        )

    @staticmethod
    def _has_return_resource_after(
        observation: Mapping[str, object],
        selected_action: Mapping[str, object],
        legal_actions: list[dict[str, object]],
        facts_by_id: Mapping[int, CandidateStructure],
    ) -> bool:
        my_info = observation.get("my_info")
        hand_cards = my_info.get("hand_cards") if isinstance(my_info, Mapping) else None
        selected_carriers = selected_action.get("carrier_cards")
        if (
            not isinstance(hand_cards, list)
            or any(not isinstance(card, str) for card in hand_cards)
            or not isinstance(selected_carriers, list)
        ):
            return False
        remaining = Counter(hand_cards)
        remaining.subtract(selected_carriers)
        if any(count < 0 for count in remaining.values()):
            return False
        remaining = Counter({card: count for card, count in remaining.items() if count > 0})
        current_round = observation.get("current_round")
        level_rank = current_round.get("current_level_rank") if isinstance(current_round, Mapping) else None
        if not isinstance(level_rank, str):
            return False
        for action in legal_actions:
            action_id = action.get("action_id")
            if type(action_id) is not int or action_id == selected_action.get("action_id"):
                continue
            fact = facts_by_id.get(action_id)
            carriers = action.get("carrier_cards")
            if (
                fact is None
                or action.get("wildcard_count") != 0
                or not isinstance(carriers, list)
                or not carriers
            ):
                continue
            used = Counter(carriers)
            if any(count > remaining.get(card, 0) for card, count in used.items()):
                continue
            if (
                fact.pattern == "single"
                and len(carriers) == 1
                and fact.consumes_control_resource
                and not fact.fragments_played_rank_group
            ):
                return True
            if (
                fact.pattern in _PRESSURE_PATTERNS
                and not fact.fragments_played_rank_group
                and fact.leaves_bomb_rank_singleton is not True
            ):
                return True
        return False

    @staticmethod
    def _has_return_resource(
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> bool:
        facts = summarize_candidate_structures(observation, legal_actions)
        if facts is None:
            return False
        return any(
            not fact.finishes_hand
            and not fact.fragments_played_rank_group
            and not fact.uses_wildcard
            and (
                fact.pattern == "single" and fact.consumes_control_resource
                or fact.pattern in _PRESSURE_PATTERNS and fact.leaves_bomb_rank_singleton is not True
            )
            for fact in facts
        )

    @staticmethod
    def _has_public_urgency(observation: dict[str, object]) -> bool:
        my_info = observation.get("my_info")
        players = observation.get("other_players")
        if not isinstance(my_info, Mapping) or not isinstance(players, list):
            return True
        for player in players:
            if not isinstance(player, Mapping):
                return True
            count = player.get("hand_count")
            if type(count) is not int or type(player.get("finished")) is not bool:
                return True
            if not player["finished"] and 0 < count <= 2:
                return True
        return False

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
