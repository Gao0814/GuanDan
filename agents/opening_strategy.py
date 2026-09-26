"""Narrow, source-backed opening conventions over public canonical actions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agents.action_structure import (
    CandidateContrast,
    CandidateStructure,
    representative_candidate_contrasts,
    summarize_candidate_contrasts,
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
MAX_OPENING_FORMULA_CONTRASTS = 12


@dataclass(frozen=True, slots=True)
class OpeningFormulaAnalysis:
    """A local result plus full public contrasts relevant to model deferral."""

    action_id: int | None = None
    model_contrasts: tuple[CandidateContrast, ...] = ()

# The direct rule is intentionally narrower than the model-before knowledge.
# All other public openings are routed to the existing RAG + DeepSeek path.
OPENING_FORMULA_CONDITION_TABLE = (
    (
        "direct_small_single",
        "exp_lead_opening_strong_001",
        "强牌开局自由首出；先排除参与已识别自然组合的单张，再比较仍可独立出手且保留回手资源的候选；完整公开关系若仅是B级原则明确支持的低成本自然单张或保留控制资源取舍，且目标位于受支持一侧时可直出；通配、拆组或其他实质取舍交模型",
    ),
    (
        "direct_natural_shape",
        "exp_lead_opening_shape_001, exp_lead_opening_weak_001",
        "任意开局牌力；不存在适用安全自然单张路线；完整公开自然单张/对子/三张/顺子路线的余组与孤张事实只有一个Pareto非支配路线，且它是完整清理的对子/三张或清除五个独立单张点数组的自然顺子；无拆组/资源损失并保留独立回手时，仅允许严格结构占优的B级组牌/同点自然单张对照或顺子/所含自然单张对照，炸弹、通配、协同、控制或其他未解决关系仍交模型",
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

    B-tier small-single guidance remains specific to strong hands. Its
    applicability is checked before ranking: a singleton that participates
    in a natural multi-card action is not a clean probe candidate. A natural
    group or straight can be selected only when public residual-structure
    facts give it the unique Pareto-minimal route among clean natural routes,
    it preserves an independent return, and the complete relation set has no
    unresolved trade-off. Prompt representatives never affect this decision.
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
        return self.analyze_action(
            observation,
            legal_actions,
            hand_eval,
            phase_context,
        ).action_id

    def analyze_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None = None,
        phase_context: GamePhaseContext | None = None,
    ) -> OpeningFormulaAnalysis:
        """Evaluate local eligibility and expose blocking relations to the model."""

        validated = self._validated_context(observation, legal_actions, phase_context)
        if validated is None:
            return OpeningFormulaAnalysis()
        hand, level_rank = validated
        strength = normalize_hand_strength(hand_eval)
        rank_counts = Counter(_rank_of(card) for card in hand.elements())
        facts = summarize_candidate_structures(observation, legal_actions)
        contrasts = summarize_candidate_contrasts(observation, legal_actions)
        if facts is None or contrasts is None:
            return OpeningFormulaAnalysis()
        if any(
            fact.finishes_hand
            for fact in facts
        ) or self._has_public_urgency(observation):
            return OpeningFormulaAnalysis()
        actions_by_id = {int(action["action_id"]): action for action in legal_actions}
        facts_by_id = {fact.action_id: fact for fact in facts}
        structured_tokens = {
            str(card)
            for fact in facts
            if fact.carrier_count > 1 and not fact.uses_wildcard
            for card in actions_by_id[fact.action_id]["carrier_cards"]
        }

        # B-tier strong-hand small-single convention: do not promote a low
        # singleton if it is part of an observed relationship or has no
        # independently playable return route after the proposed lead.
        applicable_singles: list[tuple[int, dict[str, object]]] = []
        for action in legal_actions:
            if action["declared_pattern"] != "single" or action["wildcard_count"] != 0:
                continue
            carriers = action["carrier_cards"]
            declared = action["declared_cards"]
            assert isinstance(carriers, list) and isinstance(declared, list)
            if len(carriers) != 1 or len(declared) != 1 or str(carriers[0]) in structured_tokens:
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
                or not self._has_return_resource_after(
                    observation, action, legal_actions, facts_by_id,
                )
            ):
                continue
            applicable_singles.append((_RANK_ORDER[carrier_rank], action))

        if strength == "strong" and applicable_singles:
            lowest = min(rank_value for rank_value, _ in applicable_singles)
            targets = [action for rank_value, action in applicable_singles if rank_value == lowest]
            if len(targets) == 1:
                target_id = targets[0]["action_id"]
                if self._small_single_relationships_are_source_supported(
                    target_id, contrasts, facts_by_id,
                ):
                    return OpeningFormulaAnalysis(action_id=int(target_id))
                # A conflict attached to the actual lowest applicable probe is
                # still a model choice; do not quietly choose a higher one.
                representatives = representative_candidate_contrasts(observation, legal_actions)
                return self._analysis_for_related_actions(
                    (int(target_id),), contrasts, representatives,
                )

        # Compare all source-backed, natural singleton/group/straight routes
        # on the same public residual facts. The two dimensions are kept
        # separate: fewer estimated rank groups and fewer residual singletons
        # must jointly dominate; there is no invented scalar weighting.
        if applicable_singles:
            # No group action is being proposed by the local formula here:
            # either the hand role does not authorize a small-single choice,
            # or multiple singleton routes already leave the decision open.
            # Ordinary display representatives remain responsible for those
            # model choices; only a specific rejected local target adds its
            # complete blocking relationships below/above.
            return OpeningFormulaAnalysis()
        group_routes = self._eligible_natural_group_routes(
            observation,
            legal_actions,
            facts,
            facts_by_id,
            actions_by_id,
            rank_counts,
            level_rank,
        )
        if group_routes is None:
            return OpeningFormulaAnalysis()

        straight_routes = self._eligible_natural_straight_routes(
            observation,
            legal_actions,
            facts,
            facts_by_id,
            actions_by_id,
            rank_counts,
            level_rank,
        )
        source_routes = self._eligible_natural_single_routes(
            observation,
            legal_actions,
            facts,
            facts_by_id,
            actions_by_id,
            rank_counts,
            level_rank,
        ) + group_routes + straight_routes
        unique_frontier = self._unique_residual_frontier(source_routes)
        if unique_frontier is None:
            # Keep a bounded, complete blocker available to the model when a
            # natural group route looked unique only after display pruning.
            # This affects model input only; it never changes local eligibility.
            representatives = representative_candidate_contrasts(observation, legal_actions)
            representative_ids = {
                action_id
                for contrast in (representatives or ())
                for action_id in contrast.action_ids
            }
            display_unlinked_routes = tuple(
                fact.action_id
                for fact in group_routes
                if fact.action_id not in representative_ids
            )
            if len(display_unlinked_routes) == 1:
                return self._analysis_for_related_actions(
                    display_unlinked_routes, contrasts, representatives,
                )
            return OpeningFormulaAnalysis()

        selected_fact = unique_frontier
        if selected_fact.pattern == "straight":
            if not self._straight_relations_are_source_supported(
                selected_fact.action_id,
                contrasts,
                actions_by_id,
            ):
                representatives = representative_candidate_contrasts(observation, legal_actions)
                return self._analysis_for_related_actions(
                    (selected_fact.action_id,), contrasts, representatives,
                )
            return OpeningFormulaAnalysis(action_id=selected_fact.action_id)

        if selected_fact.pattern not in {"pair", "triple"}:
            return OpeningFormulaAnalysis()
        if selected_fact not in group_routes:
            return OpeningFormulaAnalysis()

        # The frontier uses the complete clean-route set, never display
        # representatives. Only a strictly public, B-supported group cleanup
        # relation may be resolved locally; every other full relation returns
        # to the model.
        selected_group_id = selected_fact.action_id
        if not self._group_relations_are_source_supported(
            selected_group_id,
            contrasts,
            facts_by_id,
            actions_by_id,
        ):
            representatives = representative_candidate_contrasts(observation, legal_actions)
            return self._analysis_for_related_actions(
                (selected_group_id,), contrasts, representatives,
            )
        return OpeningFormulaAnalysis(action_id=selected_group_id)

    @classmethod
    def _eligible_natural_single_routes(
        cls,
        observation: Mapping[str, object],
        legal_actions: list[dict[str, object]],
        facts: tuple[CandidateStructure, ...],
        facts_by_id: Mapping[int, CandidateStructure],
        actions_by_id: Mapping[int, Mapping[str, object]],
        rank_counts: Mapping[str, int],
        level_rank: str,
    ) -> tuple[CandidateStructure, ...]:
        routes: list[CandidateStructure] = []
        for fact in facts:
            if (
                fact.pattern != "single"
                or fact.finishes_hand
                or fact.uses_wildcard
                or fact.fragments_played_rank_group
                or fact.consumes_control_resource
                or fact.natural_single_rank_value is None
            ):
                continue
            action = actions_by_id.get(fact.action_id)
            carriers = action.get("carrier_cards") if isinstance(action, Mapping) else None
            declared = action.get("declared_cards") if isinstance(action, Mapping) else None
            if (
                not isinstance(carriers, list)
                or len(carriers) != 1
                or not isinstance(declared, list)
                or len(declared) != 1
            ):
                continue
            rank = _rank_of(str(carriers[0]))
            declared_rank = _rank_of(str(declared[0]))
            if (
                declared_rank != rank
                or rank_counts.get(rank) != 1
                or rank in _CONTROL_RANKS
                or rank == level_rank
                or not cls._has_return_resource_after(
                    observation, action, legal_actions, facts_by_id,
                )
            ):
                continue
            routes.append(fact)
        return tuple(routes)

    @staticmethod
    def _unique_residual_frontier(
        routes: tuple[CandidateStructure, ...],
    ) -> CandidateStructure | None:
        """Return a unique Pareto-minimal natural route, without scalar weights."""
        if not routes:
            return None
        frontier = tuple(
            route
            for route in routes
            if not any(
                other.action_id != route.action_id
                and other.estimated_remaining_rank_groups
                <= route.estimated_remaining_rank_groups
                and other.residual_singleton_rank_count
                <= route.residual_singleton_rank_count
                and (
                    other.estimated_remaining_rank_groups
                    < route.estimated_remaining_rank_groups
                    or other.residual_singleton_rank_count
                    < route.residual_singleton_rank_count
                )
                for other in routes
            )
        )
        return frontier[0] if len(frontier) == 1 else None

    @staticmethod
    def _eligible_natural_straight_routes(
        observation: Mapping[str, object],
        legal_actions: list[dict[str, object]],
        facts: tuple[CandidateStructure, ...],
        facts_by_id: Mapping[int, CandidateStructure],
        actions_by_id: Mapping[int, Mapping[str, object]],
        rank_counts: Mapping[str, int],
        level_rank: str,
    ) -> tuple[CandidateStructure, ...]:
        routes: list[CandidateStructure] = []
        for fact in facts:
            if (
                fact.pattern != "straight"
                or fact.finishes_hand
                or fact.uses_wildcard
                or fact.fragments_played_rank_group
                or fact.consumes_control_resource
                or not fact.clears_played_rank_groups
            ):
                continue
            action = actions_by_id.get(fact.action_id)
            carriers = action.get("carrier_cards") if isinstance(action, Mapping) else None
            if not isinstance(carriers, list) or len(carriers) != 5:
                continue
            ranks = tuple(_rank_of(str(card)) for card in carriers)
            if (
                len(set(ranks)) != len(ranks)
                or any(
                    rank_counts.get(rank) != 1
                    or rank in _CONTROL_RANKS
                    or rank == level_rank
                    for rank in ranks
                )
                or not OpeningFormulaStrategy._has_return_resource_after(
                    observation, action, legal_actions, facts_by_id,
                )
            ):
                continue
            routes.append(fact)
        return tuple(routes)

    @staticmethod
    def _straight_relations_are_source_supported(
        action_id: int,
        contrasts: tuple[CandidateContrast, ...],
        actions_by_id: Mapping[int, Mapping[str, object]],
    ) -> bool:
        """Allow only the B-supported cleanup comparison with its singleton cards."""
        related = [contrast for contrast in contrasts if action_id in contrast.action_ids]
        for contrast in related:
            if (
                contrast.kind != "natural_sequence_single"
                or contrast.action_ids[0] != action_id
            ):
                return False
            other_id = contrast.action_ids[1] if contrast.action_ids[0] == action_id else contrast.action_ids[0]
            other = actions_by_id.get(other_id)
            carriers = other.get("carrier_cards") if isinstance(other, Mapping) else None
            if (
                not isinstance(other, Mapping)
                or other.get("declared_pattern") != "single"
                or other.get("wildcard_count") != 0
                or not isinstance(carriers, list)
                or len(carriers) != 1
            ):
                return False
        return True

    @staticmethod
    def _group_relations_are_source_supported(
        action_id: int,
        contrasts: tuple[CandidateContrast, ...],
        facts_by_id: Mapping[int, CandidateStructure],
        actions_by_id: Mapping[int, Mapping[str, object]],
    ) -> bool:
        """Resolve only a strictly structure-dominant natural-group cleanup.

        The B-tier structure principle permits a local choice only when the
        public residual comparison is uniquely clear. A relation is not by
        itself a veto, but any resource, sequence-fragment, wildcard, urgency,
        or reversed/unknown relation remains a model decision.
        """
        related = [contrast for contrast in contrasts if action_id in contrast.action_ids]
        group = facts_by_id.get(action_id)
        group_action = actions_by_id.get(action_id)
        if (
            group is None
            or group_action is None
            or group.pattern not in {"pair", "triple"}
            or not group.clears_played_rank_groups
            or group.fragments_played_rank_group
            or group.uses_wildcard
            or group.consumes_control_resource
        ):
            return False
        carriers = group_action.get("carrier_cards")
        if (
            group_action.get("declared_pattern") != group.pattern
            or group_action.get("wildcard_count") != 0
            or not isinstance(carriers, list)
            or len(carriers) != group.carrier_count
            or len({_rank_of(str(card)) for card in carriers}) != 1
        ):
            return False

        for contrast in related:
            if (
                contrast.kind not in {"natural_pair_single", "natural_group_single"}
                or contrast.action_ids[0] != action_id
            ):
                return False
            other_id = contrast.action_ids[1]
            other = facts_by_id.get(other_id)
            other_action = actions_by_id.get(other_id)
            other_carriers = other_action.get("carrier_cards") if other_action is not None else None
            other_declared = other_action.get("declared_cards") if other_action is not None else None
            if (
                other is None
                or other_action is None
                or other.pattern != "single"
                or other.finishes_hand
                or other.uses_wildcard
                or other.consumes_control_resource
                or other_action.get("declared_pattern") != "single"
                or other_action.get("wildcard_count") != 0
                or not isinstance(other_carriers, list)
                or len(other_carriers) != 1
                or not isinstance(other_declared, list)
                or len(other_declared) != 1
            ):
                return False
            # A route's estimated groups are an ordering cue, not a promised
            # exact turn count. Require strict improvement on at least one
            # structural dimension and no regression on the other.
            if not (
                group.estimated_remaining_rank_groups <= other.estimated_remaining_rank_groups
                and group.residual_singleton_rank_count <= other.residual_singleton_rank_count
                and (
                    group.estimated_remaining_rank_groups < other.estimated_remaining_rank_groups
                    or group.residual_singleton_rank_count < other.residual_singleton_rank_count
                )
            ):
                return False
        return True

    @staticmethod
    def _analysis_for_related_actions(
        action_ids: tuple[int, ...],
        contrasts: tuple[CandidateContrast, ...],
        representatives: tuple[CandidateContrast, ...] | None,
    ) -> OpeningFormulaAnalysis:
        if representatives is None:
            return OpeningFormulaAnalysis()
        represented_ids = {
            candidate_id
            for contrast in representatives
            for candidate_id in contrast.action_ids
        }
        target_ids = set(action_ids).difference(represented_ids)
        if not target_ids:
            return OpeningFormulaAnalysis()
        representative_pairs = {
            (item.kind, item.action_ids) for item in representatives
        }
        related: list[CandidateContrast] = []
        for contrast in contrasts:
            if (
                not target_ids.intersection(contrast.action_ids)
                or (contrast.kind, contrast.action_ids) in representative_pairs
            ):
                continue
            related.append(contrast)
            if len(related) >= MAX_OPENING_FORMULA_CONTRASTS:
                break
        return OpeningFormulaAnalysis(model_contrasts=tuple(related))

    @classmethod
    def _eligible_natural_group_routes(
        cls,
        observation: Mapping[str, object],
        legal_actions: list[dict[str, object]],
        facts: tuple[CandidateStructure, ...],
        facts_by_id: Mapping[int, CandidateStructure],
        actions_by_id: Mapping[int, Mapping[str, object]],
        rank_counts: Mapping[str, int],
        level_rank: str,
    ) -> tuple[CandidateStructure, ...] | None:
        """Return all source-shaped natural group routes before relation gating."""

        group_routes: list[CandidateStructure] = []
        for fact in facts:
            if (
                fact.pattern not in {"pair", "triple"}
                or fact.finishes_hand
                or fact.uses_wildcard
                or fact.fragments_played_rank_group
                or fact.consumes_control_resource
                or not fact.clears_played_rank_groups
            ):
                continue
            action = actions_by_id.get(fact.action_id)
            carriers = action.get("carrier_cards") if isinstance(action, Mapping) else None
            if not isinstance(carriers, list) or not carriers:
                return None
            carrier_ranks = {_rank_of(card) for card in carriers}
            if len(carrier_ranks) != 1:
                continue
            rank = next(iter(carrier_ranks))
            if (
                rank in _CONTROL_RANKS
                or rank == level_rank
                or rank_counts.get(rank) != len(carriers)
                or not cls._has_return_resource_after(
                    observation, action, legal_actions, facts_by_id,
                )
            ):
                continue
            group_routes.append(fact)
        return tuple(group_routes)

    @staticmethod
    def _small_single_relationships_are_source_supported(
        action_id: int,
        contrasts: tuple[CandidateContrast, ...],
        facts_by_id: Mapping[int, CandidateStructure],
    ) -> bool:
        """Allow only small-single comparisons whose direction has B-tier support."""

        related = [contrast for contrast in contrasts if action_id in contrast.action_ids]
        for contrast in related:
            # The B-tier opening principle supports a lowest safe natural
            # single over a middle-cost natural probe when control resources
            # remain available.  This relation is explicitly ordered by the
            # contrast builder, so accept only its cheaper side.
            if contrast.kind == "natural_single_cost" and contrast.action_ids[0] == action_id:
                continue
            # The same B-tier source supports preserving an independently
            # playable control card instead of spending it on an ordinary
            # singleton.  Verify the compared route really consumes one.
            if contrast.kind == "single_control_resource" and contrast.action_ids[0] == action_id:
                alternative = facts_by_id.get(contrast.action_ids[1])
                if alternative is not None and alternative.consumes_control_resource:
                    continue
            # In particular, wildcard/resource, group, sequence, and any
            # unrecognized relationship remains a genuine trade-off for the
            # model; C-tier soft hypotheses never authorize a direct choice.
            return False
        return True

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
