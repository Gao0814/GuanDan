"""Low-cardinality finished-score aggregates for completed local-AI matches."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


RESULT_CATEGORIES = frozenset(
    {"local_team_win", "local_team_loss", "platform_error", "invalid_score_shape"}
)
LOCAL_TEAM_SCORE_BUCKETS = frozenset({"score_0", "score_1", "score_2", "score_3"})


class ResultObservabilityError(ValueError):
    """Finished-score aggregates fail the fixed, non-sensitive contract."""


def _strict_count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ResultObservabilityError("invalid_count")
    return value


def _validated_pairs(values: object, allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    if not isinstance(values, tuple):
        raise ResultObservabilityError("invalid_counts")
    previous = ""
    seen: set[str] = set()
    normalized: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ResultObservabilityError("invalid_counts")
        name, count = item
        if (
            not isinstance(name, str)
            or name not in allowed
            or name in seen
            or _strict_count(count) == 0
            or name <= previous
        ):
            raise ResultObservabilityError("invalid_counts")
        seen.add(name)
        previous = name
        normalized.append((name, count))
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class ResultObservabilitySnapshot:
    """Immutable aggregate only; it retains no row, player, or score tuple."""

    result_category_counts: tuple[tuple[str, int], ...]
    normal_result_count: int
    local_team_score_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        categories = _validated_pairs(self.result_category_counts, RESULT_CATEGORIES)
        buckets = _validated_pairs(self.local_team_score_counts, LOCAL_TEAM_SCORE_BUCKETS)
        category_map = dict(categories)
        if _strict_count(self.normal_result_count) != (
            category_map.get("local_team_win", 0) + category_map.get("local_team_loss", 0)
        ):
            raise ResultObservabilityError("normal_result_conservation_failed")
        if self.normal_result_count != sum(count for _, count in buckets):
            raise ResultObservabilityError("score_bucket_conservation_failed")

    def to_json(self) -> dict[str, object]:
        return {
            "result_category_counts": [[name, count] for name, count in self.result_category_counts],
            "normal_result_count": self.normal_result_count,
            "local_team_score_counts": [[name, count] for name, count in self.local_team_score_counts],
        }


def classify_finished_score(local_player_id: object, scores: object) -> tuple[str, str | None]:
    """Classify only fixed outcome buckets without exposing the score sequence."""

    if type(local_player_id) is not int or not 0 <= local_player_id <= 3:
        return "invalid_score_shape", None
    if not isinstance(scores, tuple) or len(scores) != 4 or any(type(score) is not int for score in scores):
        return "invalid_score_shape", None

    negative = [seat for seat, score in enumerate(scores) if score == -2]
    if len(negative) == 1:
        offender = negative[0]
        teammate = (offender + 2) % 4
        opponents = tuple(seat for seat in range(4) if seat not in {offender, teammate})
        if scores[teammate] == 0 and all(scores[seat] == 1 for seat in opponents):
            return "platform_error", None

    local_team = (local_player_id, (local_player_id + 2) % 4)
    other_team = tuple(seat for seat in range(4) if seat not in local_team)
    local_scores = (scores[local_team[0]], scores[local_team[1]])
    other_scores = (scores[other_team[0]], scores[other_team[1]])
    if local_scores[0] != local_scores[1] or other_scores[0] != other_scores[1]:
        return "invalid_score_shape", None
    local_score, other_score = local_scores[0], other_scores[0]
    if local_score == 0 and other_score in {1, 2, 3}:
        return "local_team_loss", "score_0"
    if other_score == 0 and local_score in {1, 2, 3}:
        return "local_team_win", "score_{}".format(local_score)
    return "invalid_score_shape", None


class ResultObservabilityRecorder:
    """Controlled mutable counter with an immutable aggregate boundary."""

    __slots__ = ("_categories", "_score_buckets")

    def __init__(self) -> None:
        self._categories: Counter[str] = Counter()
        self._score_buckets: Counter[str] = Counter()

    def record_qualified_finished(self, local_player_id: object, scores: object) -> None:
        category, bucket = classify_finished_score(local_player_id, scores)
        if category not in RESULT_CATEGORIES:
            raise ResultObservabilityError("invalid_category")
        self._categories[category] += 1
        if bucket is not None:
            if bucket not in LOCAL_TEAM_SCORE_BUCKETS:
                raise ResultObservabilityError("invalid_bucket")
            self._score_buckets[bucket] += 1

    def snapshot(self) -> ResultObservabilitySnapshot:
        categories = tuple(sorted((name, _strict_count(count)) for name, count in self._categories.items() if count))
        buckets = tuple(sorted((name, _strict_count(count)) for name, count in self._score_buckets.items() if count))
        category_map = dict(categories)
        return ResultObservabilitySnapshot(
            result_category_counts=categories,
            normal_result_count=category_map.get("local_team_win", 0) + category_map.get("local_team_loss", 0),
            local_team_score_counts=buckets,
        )
