"""Conservative public-data grouping check for a very small free lead.

This is deliberately not a game-tree search.  It measures only whether the
currently supplied free-lead carrier groups can exactly partition the local
public hand in fewer groups.  Any incomplete or malformed public evidence
returns no recommendation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from functools import lru_cache


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
        my_info.get("player_id") != expected_player_id
        or not _is_int(hand_count)
        or not 1 <= hand_count <= 4
        or not isinstance(hand_cards, list)
        or len(hand_cards) != hand_count
        or any(not isinstance(card, str) or not card for card in hand_cards)
        or current_round.get("current_player_id") != expected_player_id
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
    ):
        return None
    if not isinstance(legal_actions, Sequence) or isinstance(legal_actions, (str, bytes)) or not legal_actions:
        return None

    hand = Counter(hand_cards)
    action_ids: set[int] = set()
    actions: list[tuple[int, Counter[str]]] = []
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
            or pattern == "pass"
            or not isinstance(declared, list)
            or not declared
            or not isinstance(carriers, list)
            or not carriers
            or any(not isinstance(card, str) for card in declared + carriers)
            or not _is_int(wildcard_count)
            or wildcard_count < 0
            or not isinstance(wildcard_info, list)
            or not isinstance(display_text, str)
        ):
            return None
        carrier_count = Counter(carriers)
        if not _is_submultiset(carrier_count, hand):
            return None
        action_ids.add(action_id)
        actions.append((action_id, carrier_count))
    return hand, tuple(actions)


def _minimum_group_free_lead_analysis(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[dict[int, int], tuple[int, ...]] | None:
    """Prove a strict first-action grouping difference from public payloads."""

    validated = _validated_free_lead_actions(observation, legal_actions, expected_player_id)
    if validated is None:
        return None
    hand, actions = validated
    action_groups = tuple(group for _, group in actions)

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
        scores[action_id] = 1 + tail
    best_score = min(scores.values())
    best_ids = tuple(action_id for action_id, score in scores.items() if score == best_score)
    if len(best_ids) == len(scores):
        return None
    return scores, best_ids


def minimum_group_free_lead_action_ids(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
) -> tuple[int, ...] | None:
    """Return tied-best original IDs only for a proved short free-lead opportunity.

    The evidence must be a complete canonical public payload for a local hand
    of one to four cards.  Every legal first action must leave a hand that can
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
    _, best_ids = analysis
    return best_ids


def strictly_better_free_lead_action_ids(
    observation: object,
    legal_actions: object,
    expected_player_id: int,
    selected_action_id: int,
) -> tuple[int, ...] | None:
    """Return best original IDs only when ``selected_action_id`` uses more groups."""

    if not _is_int(selected_action_id):
        return None
    analysis = _minimum_group_free_lead_analysis(
        observation,
        legal_actions,
        expected_player_id,
    )
    if analysis is None:
        return None
    scores, best_ids = analysis
    selected_score = scores.get(selected_action_id)
    if selected_score is None or selected_action_id in best_ids:
        return None
    return best_ids
