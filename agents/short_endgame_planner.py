"""Conservative public-data grouping check for a very small free lead.

This is deliberately not a game-tree search.  It measures only whether the
currently supplied free-lead carrier groups can exactly partition the local
public hand in fewer groups.  Any incomplete or malformed public evidence
returns no recommendation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache


_NORMAL_RANKS = frozenset({"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"})
_SUITS = frozenset({"S", "H", "C", "D"})
_PATTERNS = frozenset({
    "single", "pair", "triple", "triple_with_pair", "straight", "pair_straight",
    "steel_plate", "bomb", "straight_flush", "joker_bomb",
})
_PATTERN_ORDER = {
    "single": 0, "pair": 1, "triple": 2, "straight": 3, "triple_with_pair": 4,
    "pair_straight": 5, "steel_plate": 6, "bomb": 7, "straight_flush": 8,
    "joker_bomb": 9,
}


@dataclass(frozen=True, slots=True)
class FreeLeadGroupingAnalysis:
    """Exact local-hand partition counts under a later free-lead assumption."""

    action_group_counts: tuple[tuple[int, int], ...]
    best_action_ids: tuple[int, ...]
    minimum_group_count: int
    maximum_group_count: int

    @property
    def has_route_difference(self) -> bool:
        return self.minimum_group_count < self.maximum_group_count

    def counts_by_action_id(self) -> dict[int, int]:
        return dict(self.action_group_counts)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _counter_key(cards: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((card, count) for card, count in cards.items() if count > 0))


def _is_submultiset(used: Counter[str], available: Counter[str]) -> bool:
    return bool(used) and all(count > 0 and count <= available.get(card, 0) for card, count in used.items())


def _subtract(available: Counter[str], used: Counter[str]) -> Counter[str]:
    remaining = available.copy()
    remaining.subtract(used)
    return Counter({card: count for card, count in remaining.items() if count > 0})


def _valid_card_token(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if value in {"SJ", "BJ"}:
        return True
    return len(value) >= 2 and value[-1] in _SUITS and value[:-1] in _NORMAL_RANKS


def _valid_declared_card(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value in _NORMAL_RANKS | {"SJ", "BJ"} or _valid_card_token(value)


def _validated_free_lead_actions(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[Counter[str], tuple[tuple[int, Counter[str]], ...]] | None:
    """Accept only a complete, canonical public free-lead payload."""

    if not _is_int(expected_player_id) or not isinstance(observation, Mapping):
        return None
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping):
        return None
    hand_count = my_info.get("hand_count")
    hand_cards = my_info.get("hand_cards")
    if (
        not _is_int(my_info.get("player_id"))
        or my_info.get("player_id") != expected_player_id
        or not _is_int(hand_count)
        or not 1 <= hand_count <= 8
        or not isinstance(hand_cards, list)
        or len(hand_cards) != hand_count
        or any(not _valid_card_token(card) for card in hand_cards)
        or any(count > 2 for count in Counter(hand_cards).values())
        or not _is_int(current_round.get("current_player_id"))
        or current_round.get("current_player_id") != expected_player_id
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
    ):
        return None
    if (
        not isinstance(legal_actions, Sequence)
        or isinstance(legal_actions, (str, bytes))
        or not legal_actions
        or len(legal_actions) > 2048
    ):
        return None

    hand = Counter(hand_cards)
    action_ids: set[int] = set()
    actions: list[tuple[int, Counter[str]]] = []
    single_tokens: set[str] = set()
    for action in legal_actions:
        if not isinstance(action, Mapping):
            return None
        action_id = action.get("action_id")
        pattern = action.get("declared_pattern")
        declared = action.get("declared_cards")
        carriers = action.get("carrier_cards")
        wildcard_count = action.get("wildcard_count")
        wildcard_info = action.get("wildcard_info")
        display_text = action.get("display_text")
        if (
            not _is_int(action_id)
            or action_id in action_ids
            or not isinstance(pattern, str)
            or pattern not in _PATTERNS
            or not isinstance(declared, list)
            or not declared
            or not isinstance(carriers, list)
            or not carriers
            or len(declared) != len(carriers)
            or any(not _valid_declared_card(card) for card in declared)
            or any(not _valid_card_token(card) for card in carriers)
            or not _is_int(wildcard_count)
            or not 0 <= wildcard_count <= 2
            or wildcard_count > len(carriers)
            or not isinstance(wildcard_info, list)
            or len(wildcard_info) != wildcard_count
            or any(not isinstance(item, Mapping) for item in wildcard_info)
            or not isinstance(display_text, str)
            or not display_text
        ):
            return None
        carrier_count = Counter(carriers)
        if not _is_submultiset(carrier_count, hand):
            return None
        action_ids.add(action_id)
        actions.append((action_id, carrier_count))
        if pattern == "single" and len(carriers) == 1:
            single_tokens.add(carriers[0])

    # A complete free-lead set must at least expose a canonical single for
    # every physical token in the public hand.  This catches a common class of
    # silently truncated candidate payloads without trying to recreate engine
    # legality inside the AI layer.
    if not set(hand).issubset(single_tokens):
        return None
    return hand, tuple(actions)


def _analysis_from_validated(
    validated: tuple[Counter[str], tuple[tuple[int, Counter[str]], ...]],
) -> FreeLeadGroupingAnalysis | None:
    hand, actions = validated
    # Canonical action IDs can differ while their physical carrier multiset is
    # identical.  Such variants do not create a new partition route.
    action_groups = tuple(
        Counter(dict(key))
        for key in dict.fromkeys(_counter_key(group) for _, group in actions)
    )

    @lru_cache(maxsize=None)
    def minimum_groups(key: tuple[tuple[str, int], ...]) -> int | None:
        if not key:
            return 0
        remaining = Counter(dict(key))
        best: int | None = None
        for group in action_groups:
            if not _is_submultiset(group, remaining):
                continue
            tail = minimum_groups(_counter_key(_subtract(remaining, group)))
            if tail is None:
                continue
            candidate = 1 + tail
            if best is None or candidate < best:
                best = candidate
        return best

    scores: dict[int, int] = {}
    for action_id, group in actions:
        tail = minimum_groups(_counter_key(_subtract(hand, group)))
        if tail is None:
            return None
        # Count groups remaining *after* the proposed first action.  The
        # comparison used to minimize total groups is unchanged by omitting
        # the same first action from every route, but this is the quantity
        # the model-facing label promises to describe.
        scores[action_id] = tail
    best_score = min(scores.values())
    worst_score = max(scores.values())
    best_ids = tuple(action_id for action_id, score in scores.items() if score == best_score)
    return FreeLeadGroupingAnalysis(
        action_group_counts=tuple(scores.items()),
        best_action_ids=best_ids,
        minimum_group_count=best_score,
        maximum_group_count=worst_score,
    )


def _minimum_group_free_lead_analysis(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> FreeLeadGroupingAnalysis | None:
    """Prove a strict first-action grouping difference from public payloads."""

    validated = _validated_free_lead_actions(observation, legal_actions, expected_player_id)
    return _analysis_from_validated(validated) if validated is not None else None


def analyze_free_lead_grouping(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> FreeLeadGroupingAnalysis | None:
    """Analyze a 1–8 card free lead using only a complete canonical payload.

    Counts are exact partitions of the currently visible physical hand by
    canonical carrier groups, conditional on later regaining a free lead.  They
    do not model opponents, future control, or whether that lead is regained.
    """

    return _minimum_group_free_lead_analysis(observation, legal_actions, expected_player_id)


def _stable_representative_key(action: Mapping[str, object]) -> tuple[object, ...]:
    carriers = action.get("carrier_cards")
    carrier_tuple = tuple(sorted(str(item) for item in carriers)) if isinstance(carriers, list) else ()
    action_id = action.get("action_id")
    return (
        _PATTERN_ORDER.get(str(action.get("declared_pattern")), 99),
        -len(carrier_tuple),
        carrier_tuple,
        action_id if _is_int(action_id) else -1,
    )


def free_lead_grouping_comparison_pairs(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[tuple[int, int], ...]:
    """Choose at most two stable best-vs-alternative pairs for 5–8 cards."""

    validated = _validated_free_lead_actions(observation, legal_actions, expected_player_id)
    if validated is None:
        return ()
    hand, _ = validated
    if not 5 <= sum(hand.values()) <= 8:
        return ()
    analysis = _analysis_from_validated(validated)
    if analysis is None or not analysis.has_route_difference:
        return ()
    scores = analysis.counts_by_action_id()
    actions_by_id = {
        action.get("action_id"): action
        for action in legal_actions
        if isinstance(action, Mapping) and _is_int(action.get("action_id"))
    }
    best_ids = [action_id for action_id, score in scores.items() if score == analysis.minimum_group_count]
    worst_ids = [action_id for action_id, score in scores.items() if score == analysis.maximum_group_count]
    best_id = min((actions_by_id[action_id] for action_id in best_ids), key=_stable_representative_key)["action_id"]
    worst_action = min(
        (actions_by_id[action_id] for action_id in worst_ids),
        key=lambda action: (
            str(action.get("declared_pattern")) == str(actions_by_id[best_id].get("declared_pattern")),
            _stable_representative_key(action),
        ),
    )
    worst_id = worst_action.get("action_id")
    if not _is_int(best_id) or not _is_int(worst_id) or best_id == worst_id:
        return ()
    pairs: list[tuple[int, int]] = [(best_id, worst_id)]

    middle_scores = sorted(score for score in set(scores.values()) if analysis.minimum_group_count < score < analysis.maximum_group_count)
    if middle_scores:
        middle_score = middle_scores[(len(middle_scores) - 1) // 2]
        middle_actions = [actions_by_id[action_id] for action_id, score in scores.items() if score == middle_score]
        middle_action = min(
            middle_actions,
            key=lambda action: (
                str(action.get("declared_pattern")) in {
                    str(actions_by_id[best_id].get("declared_pattern")),
                    str(actions_by_id[worst_id].get("declared_pattern")),
                },
                _stable_representative_key(action),
            ),
        )
        middle_id = middle_action.get("action_id")
        if _is_int(middle_id) and middle_id not in {best_id, worst_id}:
            pairs.append((best_id, middle_id))
    return tuple(pairs)


def minimum_group_free_lead_action_ids(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[int, ...] | None:
    """Return tied-best original IDs only for a proved short free-lead opportunity.

    The evidence must be a complete canonical public payload for a local hand
    of one to eight cards.  Every legal first action must leave a hand that can
    be partitioned by the same canonical carrier groups, and at least one
    first action must use strictly more groups than the minimum.
    """

    analysis = _minimum_group_free_lead_analysis(
        observation,
        legal_actions,
        expected_player_id,
    )
    if analysis is None:
        return None
    if not analysis.has_route_difference:
        return None
    return analysis.best_action_ids
