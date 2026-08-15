"""Offline-only, aggregate-only comparison of Botzone rule and DeepSeek audits."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType


POLICIES = frozenset({"rule", "deepseek"})
PROFILE_VERSION = "botzone_no_tribute_level_2/v1"
PREVIOUS_RANK_PROFILE = "same_previous_rank_profile"

DECISION_SOURCES = frozenset(
    {"rule_primary", "local_shortcut", "model", "deepseek_rule_fallback", "adapter_rule_fallback"}
)
MODEL_OUTCOMES = frozenset({"success", "timeout", "exception", "invalid_suggestion"})
RESULT_CATEGORIES = frozenset(
    {"local_team_win", "local_team_loss", "platform_error", "invalid_score_shape"}
)
SCORE_BUCKETS = frozenset({"score_0", "score_1", "score_2", "score_3"})
FINISHED_CATEGORIES = frozenset({"aborted", "non_four_player", "four_player_unqualified", "qualified"})
TRANSPORT_FAILURE_CATEGORIES = frozenset(
    {"dns_or_connect_failed", "http_error", "invalid_response", "redirect", "tls_failed", "unclassified"}
)
DIAGNOSTICS = frozenset(
    {
        "atomic_write_failed",
        "corrupt_session",
        "envelope_shape_invalid",
        "header_injection",
        "handler_failure",
        "handler_lifecycle_failure",
        "history_alignment_failed",
        "historical_response_invalid",
        "inner_request_invalid",
        "invalid_play_effect",
        "malformed_request",
        "malformed_handler_result",
        "missing_provenance",
        "poll_malformed",
        "play_without_state",
        "replay_history_invalid",
        "request_json_invalid",
        "session_error",
        "transport_failure",
        "transport_timeout",
        "unsupported_stage",
    }
)
DETAILS = frozenset(
    {
        "envelope_top_level_invalid",
        "envelope_required_fields_missing",
        "envelope_unknown_field",
        "envelope_optional_value_invalid",
        "envelope_requests_not_list",
        "envelope_responses_not_list",
        "envelope_requests_empty",
        "envelope_length_mismatch",
    }
)
PROFILES = frozenset(
    {
        "required_requests_missing",
        "required_responses_missing",
        "required_both_missing_empty_object",
        "required_both_missing_inner_stage_candidate",
        "required_both_missing_optional_only",
        "required_both_missing_other_object",
    }
)
BENCHMARK_DIAGNOSTICS = frozenset(
    {
        "audit_invalid",
        "condition_mismatch",
        "duplicate_side",
        "invalid_submission",
        "missing_side",
        "strategy_mismatch",
        "unknown_condition",
    }
)

AUDIT_FIELDS = frozenset(
    {
        "schema",
        "version",
        "exit_code",
        "stop_reason",
        "cycles",
        "successful_cycles",
        "transport_failures",
        "transport_timeouts",
        "transport_failure_categories",
        "headers_sent",
        "requests_seen",
        "responses_prepared",
        "finished_seen",
        "finished_qualified",
        "finished_categories",
        "diagnostics",
        "diagnostic_details",
        "diagnostic_profiles",
        "agent_mode",
        "agent_decision_count",
        "decision_source_counts",
        "model_attempt_count",
        "model_outcome_counts",
        "rule_fallback_count",
        "result_category_counts",
        "normal_result_count",
        "local_team_score_counts",
    }
)


class PolicyBenchmarkError(ValueError):
    """The fixed offline benchmark contract is not satisfied."""


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise PolicyBenchmarkError("invalid_count")
    return value


def _positive_count(value: object) -> int:
    value = _count(value)
    if value == 0:
        raise PolicyBenchmarkError("invalid_count")
    return value


def _pairs(values: object, allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    if not isinstance(values, list):
        raise PolicyBenchmarkError("invalid_pairs")
    previous = ""
    result: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, list) or len(item) != 2:
            raise PolicyBenchmarkError("invalid_pairs")
        name, count = item
        if not isinstance(name, str) or name not in allowed or name <= previous:
            raise PolicyBenchmarkError("invalid_pairs")
        result.append((name, _positive_count(count)))
        previous = name
    return tuple(result)


def _snapshot_pairs(values: object, allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    if not isinstance(values, tuple):
        raise PolicyBenchmarkError("invalid_snapshot")
    previous = ""
    result: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise PolicyBenchmarkError("invalid_snapshot")
        name, count = item
        if not isinstance(name, str) or name not in allowed or name <= previous:
            raise PolicyBenchmarkError("invalid_snapshot")
        result.append((name, _positive_count(count)))
        previous = name
    return tuple(result)


def _fraction(value: int, denominator: int) -> Fraction:
    if type(value) is not int:
        raise PolicyBenchmarkError("invalid_count")
    _count(denominator)
    return Fraction(value, denominator) if denominator else Fraction(0, 1)


def _fraction_dict(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _score_value(score_bucket: str) -> int:
    return int(score_bucket[-1])


@dataclass(frozen=True, slots=True)
class BenchmarkConditions:
    """Non-sensitive conditions shared by every paired evaluation game."""

    profile_version: str
    seed_contract_confirmed: bool
    opponent_profile_confirmed: bool
    no_tribute: bool = True
    current_level_rank: int = 2
    previous_rank_profile: str = PREVIOUS_RANK_PROFILE

    def __post_init__(self) -> None:
        if (
            self.profile_version != PROFILE_VERSION
            or type(self.seed_contract_confirmed) is not bool
            or type(self.opponent_profile_confirmed) is not bool
            or self.no_tribute is not True
            or type(self.current_level_rank) is not int
            or self.current_level_rank != 2
            or self.previous_rank_profile != PREVIOUS_RANK_PROFILE
        ):
            raise PolicyBenchmarkError("invalid_conditions")

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_version": self.profile_version,
            "seed_contract_confirmed": self.seed_contract_confirmed,
            "opponent_profile_confirmed": self.opponent_profile_confirmed,
            "no_tribute": self.no_tribute,
            "current_level_rank": self.current_level_rank,
            "previous_rank_profile": self.previous_rank_profile,
        }


@dataclass(frozen=True, slots=True, repr=False)
class ScheduledPair:
    """An in-memory-only pair; its seed deliberately has no serializing API."""

    seed: int
    local_seat: int
    first_strategy: str
    second_strategy: str

    def __post_init__(self) -> None:
        if (
            type(self.seed) is not int
            or type(self.local_seat) is not int
            or self.local_seat not in range(4)
            or self.first_strategy not in POLICIES
            or self.second_strategy not in POLICIES
            or self.first_strategy == self.second_strategy
        ):
            raise PolicyBenchmarkError("invalid_schedule")

    def __repr__(self) -> str:
        return "ScheduledPair(redacted)"


@dataclass(frozen=True, slots=True, repr=False)
class PolicyAuditSubmission:
    """In-memory audit input; identifiers and payload never enter reports."""

    seed: object
    local_seat: object
    strategy: object
    profile_version: object
    audit: object

    def __post_init__(self) -> None:
        if isinstance(self.audit, Mapping):
            object.__setattr__(self, "audit", MappingProxyType(dict(self.audit)))

    def __repr__(self) -> str:
        return "PolicyAuditSubmission(redacted)"


def build_paired_schedule(seeds: Iterable[object], conditions: BenchmarkConditions) -> tuple[ScheduledPair, ...]:
    """Build deterministic AB/BA pairs without random or time-derived ordering."""

    if (
        not isinstance(conditions, BenchmarkConditions)
        or not conditions.seed_contract_confirmed
        or not conditions.opponent_profile_confirmed
    ):
        raise PolicyBenchmarkError("seed_contract_unconfirmed")
    try:
        values = tuple(seeds)
    except TypeError:
        raise PolicyBenchmarkError("invalid_seeds") from None
    if any(type(seed) is not int for seed in values) or len(set(values)) != len(values):
        raise PolicyBenchmarkError("invalid_seeds")
    result: list[ScheduledPair] = []
    for index, seed in enumerate(sorted(values)):
        for seat in range(4):
            first = "rule" if (index + seat) % 2 == 0 else "deepseek"
            result.append(ScheduledPair(seed, seat, first, "deepseek" if first == "rule" else "rule"))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class _ValidatedAudit:
    outcome: str
    score_bucket: str
    score: int
    agent_decision_count: int
    decision_sources: tuple[tuple[str, int], ...]
    model_attempt_count: int
    model_outcomes: tuple[tuple[str, int], ...]
    rule_fallback_count: int


def _validate_audit(value: object, expected_strategy: str) -> _ValidatedAudit:
    if not isinstance(value, Mapping) or set(value) != AUDIT_FIELDS:
        raise PolicyBenchmarkError("invalid_audit")
    if (
        value["schema"] != "botzone_local_smoke_audit"
        or type(value["version"]) is not int
        or value["version"] != 7
        or type(value["exit_code"]) is not int
    ):
        raise PolicyBenchmarkError("invalid_audit")
    if value["agent_mode"] != expected_strategy or expected_strategy not in POLICIES:
        raise PolicyBenchmarkError("strategy_mismatch")
    if value["exit_code"] != 0 or value["stop_reason"] != "finished_target":
        raise PolicyBenchmarkError("invalid_audit")

    scalar_names = (
        "cycles", "successful_cycles", "transport_failures", "transport_timeouts", "headers_sent",
        "requests_seen", "responses_prepared", "finished_seen", "finished_qualified", "agent_decision_count",
        "model_attempt_count", "rule_fallback_count", "normal_result_count",
    )
    scalars = {name: _count(value[name]) for name in scalar_names}
    if (
        scalars["requests_seen"] == 0
        or scalars["requests_seen"] != scalars["responses_prepared"]
        or scalars["requests_seen"] != scalars["headers_sent"]
        or scalars["finished_qualified"] != 1
        or scalars["transport_failures"] != 0
        or scalars["transport_timeouts"] != 0
        or scalars["normal_result_count"] != 1
        or scalars["agent_decision_count"] > scalars["responses_prepared"]
    ):
        raise PolicyBenchmarkError("invalid_audit")

    failures = _pairs(value["transport_failure_categories"], TRANSPORT_FAILURE_CATEGORIES)
    finished = _pairs(value["finished_categories"], FINISHED_CATEGORIES)
    diagnostics = _pairs(value["diagnostics"], DIAGNOSTICS)
    details = _pairs(value["diagnostic_details"], DETAILS)
    profiles = _pairs(value["diagnostic_profiles"], PROFILES)
    if failures or diagnostics or details or profiles or sum(count for _, count in finished) != scalars["finished_seen"]:
        raise PolicyBenchmarkError("invalid_audit")
    if dict(finished).get("qualified", 0) != 1:
        raise PolicyBenchmarkError("invalid_audit")

    sources = _pairs(value["decision_source_counts"], DECISION_SOURCES)
    outcomes = _pairs(value["model_outcome_counts"], MODEL_OUTCOMES)
    source_map = dict(sources)
    if (
        sum(count for _, count in sources) != scalars["agent_decision_count"]
        or sum(count for _, count in outcomes) != scalars["model_attempt_count"]
        or scalars["rule_fallback_count"]
        != source_map.get("deepseek_rule_fallback", 0) + source_map.get("adapter_rule_fallback", 0)
    ):
        raise PolicyBenchmarkError("invalid_audit")
    if expected_strategy == "rule":
        if scalars["model_attempt_count"] or outcomes or scalars["rule_fallback_count"] or any(name != "rule_primary" for name, _ in sources):
            raise PolicyBenchmarkError("invalid_audit")
    elif scalars["model_attempt_count"] != source_map.get("model", 0) + source_map.get("deepseek_rule_fallback", 0):
        raise PolicyBenchmarkError("invalid_audit")

    categories = _pairs(value["result_category_counts"], RESULT_CATEGORIES)
    buckets = _pairs(value["local_team_score_counts"], SCORE_BUCKETS)
    category_map = dict(categories)
    if (
        sum(count for _, count in categories) != 1
        or category_map.get("platform_error", 0)
        or category_map.get("invalid_score_shape", 0)
        or sum(count for _, count in buckets) != 1
    ):
        raise PolicyBenchmarkError("invalid_audit")
    if category_map.get("local_team_win", 0) == 1:
        outcome = "win"
        allowed_buckets = {"score_1", "score_2", "score_3"}
    elif category_map.get("local_team_loss", 0) == 1:
        outcome = "loss"
        allowed_buckets = {"score_0"}
    else:
        raise PolicyBenchmarkError("invalid_audit")
    score_bucket = buckets[0][0] if len(buckets) == 1 else ""
    if score_bucket not in allowed_buckets:
        raise PolicyBenchmarkError("invalid_audit")
    return _ValidatedAudit(
        outcome,
        score_bucket,
        _score_value(score_bucket),
        scalars["agent_decision_count"],
        sources,
        scalars["model_attempt_count"],
        outcomes,
        scalars["rule_fallback_count"],
    )


@dataclass(frozen=True, slots=True)
class SeatBenchmarkSummary:
    local_seat: int
    requested_pair_count: int
    valid_pair_count: int
    invalid_pair_count: int
    incomplete_pair_count: int
    rule_win_count: int
    rule_loss_count: int
    deepseek_win_count: int
    deepseek_loss_count: int
    rule_score_counts: tuple[tuple[str, int], ...]
    deepseek_score_counts: tuple[tuple[str, int], ...]
    rule_score_sum: int
    deepseek_score_sum: int
    paired_score_delta_sum: int
    deepseek_score_better: int
    rule_score_better: int
    equal_score: int
    ab_pair_count: int
    ba_pair_count: int

    def __post_init__(self) -> None:
        if type(self.local_seat) is not int or self.local_seat not in range(4):
            raise PolicyBenchmarkError("invalid_seat_summary")
        _validate_aggregate(self)

    def to_dict(self) -> dict[str, object]:
        valid = self.valid_pair_count
        return {
            "local_seat": self.local_seat,
            "requested_pair_count": self.requested_pair_count,
            "valid_pair_count": valid,
            "invalid_pair_count": self.invalid_pair_count,
            "incomplete_pair_count": self.incomplete_pair_count,
            "rule_win_count": self.rule_win_count,
            "rule_loss_count": self.rule_loss_count,
            "deepseek_win_count": self.deepseek_win_count,
            "deepseek_loss_count": self.deepseek_loss_count,
            "rule_score_counts": [[name, count] for name, count in self.rule_score_counts],
            "deepseek_score_counts": [[name, count] for name, count in self.deepseek_score_counts],
            "rule_score_sum": self.rule_score_sum,
            "deepseek_score_sum": self.deepseek_score_sum,
            "rule_score_mean": _fraction_dict(_fraction(self.rule_score_sum, valid)),
            "deepseek_score_mean": _fraction_dict(_fraction(self.deepseek_score_sum, valid)),
            "paired_score_delta_sum": self.paired_score_delta_sum,
            "paired_score_delta_mean": _fraction_dict(_fraction(self.paired_score_delta_sum, valid)),
            "deepseek_score_better": self.deepseek_score_better,
            "rule_score_better": self.rule_score_better,
            "equal_score": self.equal_score,
            "ab_pair_count": self.ab_pair_count,
            "ba_pair_count": self.ba_pair_count,
        }


def _validate_aggregate(value: SeatBenchmarkSummary) -> None:
    scalar_names = (
        "requested_pair_count", "valid_pair_count", "invalid_pair_count", "incomplete_pair_count",
        "rule_win_count", "rule_loss_count", "deepseek_win_count", "deepseek_loss_count", "rule_score_sum",
        "deepseek_score_sum", "deepseek_score_better", "rule_score_better", "equal_score", "ab_pair_count", "ba_pair_count",
    )
    if any(_count(getattr(value, name)) < 0 for name in scalar_names) or type(value.paired_score_delta_sum) is not int:
        raise PolicyBenchmarkError("invalid_aggregate")
    rule_scores = _snapshot_pairs(value.rule_score_counts, SCORE_BUCKETS)
    deepseek_scores = _snapshot_pairs(value.deepseek_score_counts, SCORE_BUCKETS)
    valid = value.valid_pair_count
    if (
        value.requested_pair_count != valid + value.invalid_pair_count + value.incomplete_pair_count
        or valid != value.rule_win_count + value.rule_loss_count
        or valid != value.deepseek_win_count + value.deepseek_loss_count
        or valid != value.deepseek_score_better + value.rule_score_better + value.equal_score
        or valid != value.ab_pair_count + value.ba_pair_count
        or valid != sum(count for _, count in rule_scores)
        or valid != sum(count for _, count in deepseek_scores)
        or value.rule_score_sum != sum(_score_value(name) * count for name, count in rule_scores)
        or value.deepseek_score_sum != sum(_score_value(name) * count for name, count in deepseek_scores)
        or value.paired_score_delta_sum != value.deepseek_score_sum - value.rule_score_sum
    ):
        raise PolicyBenchmarkError("aggregate_conservation_failed")


@dataclass(frozen=True, slots=True)
class PolicyBenchmarkReport:
    profile_version: str
    requested_pair_count: int
    valid_pair_count: int
    invalid_pair_count: int
    incomplete_pair_count: int
    duplicate_pair_count: int
    rule_valid_game_count: int
    deepseek_valid_game_count: int
    deepseek_score_better: int
    rule_score_better: int
    equal_score: int
    rule_win_count: int
    rule_loss_count: int
    deepseek_win_count: int
    deepseek_loss_count: int
    rule_score_counts: tuple[tuple[str, int], ...]
    deepseek_score_counts: tuple[tuple[str, int], ...]
    rule_score_sum: int
    deepseek_score_sum: int
    paired_score_delta_sum: int
    ab_pair_count: int
    ba_pair_count: int
    deepseek_model_exposed_game_count: int
    deepseek_model_attempt_count: int
    deepseek_model_outcome_counts: tuple[tuple[str, int], ...]
    deepseek_decision_source_counts: tuple[tuple[str, int], ...]
    deepseek_rule_fallback_count: int
    seat_summaries: tuple[SeatBenchmarkSummary, ...]
    diagnostics: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if self.profile_version != PROFILE_VERSION:
            raise PolicyBenchmarkError("invalid_report")
        if any(
            type(getattr(self, name)) is not int
            for name in (
                "requested_pair_count", "valid_pair_count", "invalid_pair_count", "incomplete_pair_count",
                "duplicate_pair_count", "rule_valid_game_count", "deepseek_valid_game_count", "deepseek_score_better",
                "rule_score_better", "equal_score", "rule_win_count", "rule_loss_count", "deepseek_win_count",
                "deepseek_loss_count", "rule_score_sum", "deepseek_score_sum", "paired_score_delta_sum", "ab_pair_count",
                "ba_pair_count", "deepseek_model_exposed_game_count", "deepseek_model_attempt_count",
                "deepseek_rule_fallback_count",
            )
        ):
            raise PolicyBenchmarkError("invalid_report")
        aggregate = SeatBenchmarkSummary(
            0,
            self.requested_pair_count,
            self.valid_pair_count,
            self.invalid_pair_count,
            self.incomplete_pair_count,
            self.rule_win_count,
            self.rule_loss_count,
            self.deepseek_win_count,
            self.deepseek_loss_count,
            self.rule_score_counts,
            self.deepseek_score_counts,
            self.rule_score_sum,
            self.deepseek_score_sum,
            self.paired_score_delta_sum,
            self.deepseek_score_better,
            self.rule_score_better,
            self.equal_score,
            self.ab_pair_count,
            self.ba_pair_count,
        )
        if self.rule_valid_game_count != self.valid_pair_count or self.deepseek_valid_game_count != self.valid_pair_count:
            raise PolicyBenchmarkError("invalid_report")
        if _count(self.duplicate_pair_count) > self.invalid_pair_count:
            raise PolicyBenchmarkError("invalid_report")
        outcomes = _snapshot_pairs(self.deepseek_model_outcome_counts, MODEL_OUTCOMES)
        sources = _snapshot_pairs(self.deepseek_decision_source_counts, DECISION_SOURCES)
        if (
            _count(self.deepseek_model_exposed_game_count) > self.deepseek_valid_game_count
            or _count(self.deepseek_model_attempt_count) != sum(count for _, count in outcomes)
            or _count(self.deepseek_rule_fallback_count)
            != dict(sources).get("deepseek_rule_fallback", 0) + dict(sources).get("adapter_rule_fallback", 0)
            or self.deepseek_model_attempt_count
            != dict(sources).get("model", 0) + dict(sources).get("deepseek_rule_fallback", 0)
        ):
            raise PolicyBenchmarkError("invalid_report")
        diagnostics = _snapshot_pairs(self.diagnostics, BENCHMARK_DIAGNOSTICS)
        if not isinstance(self.seat_summaries, tuple) or tuple(item.local_seat for item in self.seat_summaries) != (0, 1, 2, 3):
            raise PolicyBenchmarkError("invalid_report")
        for field_name in (
            "requested_pair_count", "valid_pair_count", "invalid_pair_count", "incomplete_pair_count", "rule_win_count",
            "rule_loss_count", "deepseek_win_count", "deepseek_loss_count", "rule_score_sum", "deepseek_score_sum",
            "paired_score_delta_sum", "deepseek_score_better", "rule_score_better", "equal_score", "ab_pair_count", "ba_pair_count",
        ):
            expected = getattr(aggregate, field_name)
            actual = sum(getattr(item, field_name) for item in self.seat_summaries)
            if actual != expected:
                raise PolicyBenchmarkError("seat_conservation_failed")
        if diagnostics != self.diagnostics:
            raise PolicyBenchmarkError("invalid_report")

    def to_dict(self) -> dict[str, object]:
        valid = self.valid_pair_count
        return {
            "profile_version": self.profile_version,
            "requested_pair_count": self.requested_pair_count,
            "valid_pair_count": valid,
            "invalid_pair_count": self.invalid_pair_count,
            "incomplete_pair_count": self.incomplete_pair_count,
            "duplicate_pair_count": self.duplicate_pair_count,
            "rule_valid_game_count": self.rule_valid_game_count,
            "deepseek_valid_game_count": self.deepseek_valid_game_count,
            "deepseek_score_better": self.deepseek_score_better,
            "rule_score_better": self.rule_score_better,
            "equal_score": self.equal_score,
            "rule_win_count": self.rule_win_count,
            "rule_loss_count": self.rule_loss_count,
            "deepseek_win_count": self.deepseek_win_count,
            "deepseek_loss_count": self.deepseek_loss_count,
            "rule_score_counts": [[name, count] for name, count in self.rule_score_counts],
            "deepseek_score_counts": [[name, count] for name, count in self.deepseek_score_counts],
            "rule_score_sum": self.rule_score_sum,
            "deepseek_score_sum": self.deepseek_score_sum,
            "rule_score_mean": _fraction_dict(_fraction(self.rule_score_sum, valid)),
            "deepseek_score_mean": _fraction_dict(_fraction(self.deepseek_score_sum, valid)),
            "paired_score_delta_sum": self.paired_score_delta_sum,
            "paired_score_delta_mean": _fraction_dict(_fraction(self.paired_score_delta_sum, valid)),
            "rule_win_rate": _fraction_dict(_fraction(self.rule_win_count, valid)),
            "deepseek_win_rate": _fraction_dict(_fraction(self.deepseek_win_count, valid)),
            "ab_pair_count": self.ab_pair_count,
            "ba_pair_count": self.ba_pair_count,
            "deepseek_model_exposed_game_count": self.deepseek_model_exposed_game_count,
            "deepseek_model_attempt_count": self.deepseek_model_attempt_count,
            "deepseek_model_outcome_counts": [[name, count] for name, count in self.deepseek_model_outcome_counts],
            "deepseek_decision_source_counts": [[name, count] for name, count in self.deepseek_decision_source_counts],
            "deepseek_rule_fallback_count": self.deepseek_rule_fallback_count,
            "seat_summaries": [item.to_dict() for item in self.seat_summaries],
            "diagnostics": [[name, count] for name, count in self.diagnostics],
        }


@dataclass(slots=True)
class _MutableAggregate:
    requested: int = 0
    valid: int = 0
    invalid: int = 0
    incomplete: int = 0
    rule_wins: int = 0
    rule_losses: int = 0
    deepseek_wins: int = 0
    deepseek_losses: int = 0
    rule_scores: Counter[str] = field(default_factory=Counter)
    deepseek_scores: Counter[str] = field(default_factory=Counter)
    rule_score_sum: int = 0
    deepseek_score_sum: int = 0
    deepseek_better: int = 0
    rule_better: int = 0
    equal: int = 0
    ab: int = 0
    ba: int = 0

    def add_valid(self, pair: ScheduledPair, rule: _ValidatedAudit, deepseek: _ValidatedAudit) -> None:
        self.valid += 1
        self.rule_scores[rule.score_bucket] += 1
        self.deepseek_scores[deepseek.score_bucket] += 1
        self.rule_score_sum += rule.score
        self.deepseek_score_sum += deepseek.score
        if rule.outcome == "win":
            self.rule_wins += 1
        else:
            self.rule_losses += 1
        if deepseek.outcome == "win":
            self.deepseek_wins += 1
        else:
            self.deepseek_losses += 1
        delta = deepseek.score - rule.score
        if delta > 0:
            self.deepseek_better += 1
        elif delta < 0:
            self.rule_better += 1
        else:
            self.equal += 1
        if pair.first_strategy == "rule":
            self.ab += 1
        else:
            self.ba += 1

    def snapshot(self, seat: int) -> SeatBenchmarkSummary:
        return SeatBenchmarkSummary(
            seat,
            self.requested,
            self.valid,
            self.invalid,
            self.incomplete,
            self.rule_wins,
            self.rule_losses,
            self.deepseek_wins,
            self.deepseek_losses,
            tuple(sorted(self.rule_scores.items())),
            tuple(sorted(self.deepseek_scores.items())),
            self.rule_score_sum,
            self.deepseek_score_sum,
            self.deepseek_score_sum - self.rule_score_sum,
            self.deepseek_better,
            self.rule_better,
            self.equal,
            self.ab,
            self.ba,
        )


def _normalized_counts(values: Counter[str], allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((name, _count(count)) for name, count in values.items() if count and name in allowed))


def aggregate_policy_audits(
    schedule: Iterable[ScheduledPair],
    submissions: Iterable[object],
    conditions: BenchmarkConditions,
) -> PolicyBenchmarkReport:
    """Fail closed by excluding every incomplete, duplicate, or invalid pair."""

    if (
        not isinstance(conditions, BenchmarkConditions)
        or not conditions.seed_contract_confirmed
        or not conditions.opponent_profile_confirmed
    ):
        raise PolicyBenchmarkError("seed_contract_unconfirmed")
    pairs = tuple(schedule)
    expected: dict[tuple[int, int], ScheduledPair] = {}
    seeds: set[int] = set()
    for pair in pairs:
        if not isinstance(pair, ScheduledPair) or (pair.seed, pair.local_seat) in expected:
            raise PolicyBenchmarkError("invalid_schedule")
        expected[(pair.seed, pair.local_seat)] = pair
        seeds.add(pair.seed)
    for index, seed in enumerate(sorted(seeds)):
        for seat in range(4):
            pair = expected.get((seed, seat))
            expected_first = "rule" if (index + seat) % 2 == 0 else "deepseek"
            if pair is None or pair.first_strategy != expected_first:
                raise PolicyBenchmarkError("invalid_schedule")

    by_pair: dict[tuple[int, int], list[PolicyAuditSubmission]] = defaultdict(list)
    diagnostics: Counter[str] = Counter()
    for submission in submissions:
        if not isinstance(submission, PolicyAuditSubmission):
            diagnostics["invalid_submission"] += 1
            continue
        if type(submission.seed) is not int or type(submission.local_seat) is not int:
            diagnostics["unknown_condition"] += 1
            continue
        key = (submission.seed, submission.local_seat)
        if key not in expected:
            diagnostics["unknown_condition"] += 1
            continue
        by_pair[key].append(submission)

    overall = _MutableAggregate()
    seats = [_MutableAggregate() for _ in range(4)]
    model_exposed = model_attempts = deepseek_fallbacks = 0
    model_outcomes: Counter[str] = Counter()
    decision_sources: Counter[str] = Counter()
    duplicate_pairs = 0

    for key, pair in expected.items():
        overall.requested += 1
        seats[pair.local_seat].requested += 1
        candidates = by_pair.get(key, [])
        expected_sides: dict[str, list[PolicyAuditSubmission]] = {"rule": [], "deepseek": []}
        invalid_pair = False
        for candidate in candidates:
            if candidate.strategy not in POLICIES:
                diagnostics["strategy_mismatch"] += 1
                invalid_pair = True
            elif candidate.profile_version != conditions.profile_version:
                diagnostics["condition_mismatch"] += 1
                invalid_pair = True
            else:
                expected_sides[candidate.strategy].append(candidate)
        duplicate = any(len(items) > 1 for items in expected_sides.values())
        if duplicate:
            diagnostics["duplicate_side"] += 1
            duplicate_pairs += 1
            invalid_pair = True
        if invalid_pair:
            overall.invalid += 1
            seats[pair.local_seat].invalid += 1
            continue
        if any(len(expected_sides[strategy]) == 0 for strategy in POLICIES):
            diagnostics["missing_side"] += 1
            overall.incomplete += 1
            seats[pair.local_seat].incomplete += 1
            continue
        try:
            rule = _validate_audit(expected_sides["rule"][0].audit, "rule")
            deepseek = _validate_audit(expected_sides["deepseek"][0].audit, "deepseek")
        except PolicyBenchmarkError as error:
            diagnostics["strategy_mismatch" if str(error) == "strategy_mismatch" else "audit_invalid"] += 1
            overall.invalid += 1
            seats[pair.local_seat].invalid += 1
            continue
        except Exception:
            diagnostics["audit_invalid"] += 1
            overall.invalid += 1
            seats[pair.local_seat].invalid += 1
            continue

        overall.add_valid(pair, rule, deepseek)
        seats[pair.local_seat].add_valid(pair, rule, deepseek)
        model_attempts += deepseek.model_attempt_count
        model_outcomes.update(dict(deepseek.model_outcomes))
        decision_sources.update(dict(deepseek.decision_sources))
        deepseek_fallbacks += deepseek.rule_fallback_count
        if deepseek.model_attempt_count:
            model_exposed += 1

    seat_snapshots = tuple(item.snapshot(index) for index, item in enumerate(seats))
    diagnostics_tuple = _normalized_counts(diagnostics, BENCHMARK_DIAGNOSTICS)
    return PolicyBenchmarkReport(
        PROFILE_VERSION,
        overall.requested,
        overall.valid,
        overall.invalid,
        overall.incomplete,
        duplicate_pairs,
        overall.valid,
        overall.valid,
        overall.deepseek_better,
        overall.rule_better,
        overall.equal,
        overall.rule_wins,
        overall.rule_losses,
        overall.deepseek_wins,
        overall.deepseek_losses,
        tuple(sorted(overall.rule_scores.items())),
        tuple(sorted(overall.deepseek_scores.items())),
        overall.rule_score_sum,
        overall.deepseek_score_sum,
        overall.deepseek_score_sum - overall.rule_score_sum,
        overall.ab,
        overall.ba,
        model_exposed,
        model_attempts,
        _normalized_counts(model_outcomes, MODEL_OUTCOMES),
        _normalized_counts(decision_sources, DECISION_SOURCES),
        deepseek_fallbacks,
        seat_snapshots,
        diagnostics_tuple,
    )
