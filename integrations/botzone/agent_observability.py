"""Low-cardinality, non-sensitive runtime aggregates for connector agents."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


DECISION_SOURCES = frozenset(
    {
        "rule_primary",
        "local_shortcut",
        "model",
        "danger_opponent_block",
        "short_endgame_plan",
        "teammate_control_block",
        "deepseek_rule_fallback",
        "adapter_rule_fallback",
        "conditional_pressure_pass",
        "conditional_rule_based",
    }
)
MODEL_OUTCOMES = frozenset({"success", "timeout", "exception", "invalid_suggestion"})
AGENT_MODES = frozenset({"rule", "deepseek", "conditional_pressure_pass"})


class AgentObservabilityError(ValueError):
    """Aggregates are incomplete or fail their fixed accounting contract."""


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise AgentObservabilityError("invalid_count")
    return value


def _normalized_counts(values: Counter[str], allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    normalized: list[tuple[str, int]] = []
    for name, count in values.items():
        if name not in allowed:
            raise AgentObservabilityError("invalid_category")
        count = _count(count)
        if count:
            normalized.append((name, count))
    return tuple(sorted(normalized))


def _validate_count_tuple(values: object, allowed: frozenset[str]) -> tuple[tuple[str, int], ...]:
    if not isinstance(values, tuple):
        raise AgentObservabilityError("invalid_counts")
    seen: set[str] = set()
    normalized: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise AgentObservabilityError("invalid_counts")
        name, count = item
        if not isinstance(name, str) or name not in allowed or name in seen or _count(count) == 0:
            raise AgentObservabilityError("invalid_counts")
        seen.add(name)
        normalized.append((name, count))
    result = tuple(sorted(normalized))
    if result != values:
        raise AgentObservabilityError("noncanonical_counts")
    return result


@dataclass(frozen=True, slots=True)
class AgentObservabilitySnapshot:
    """Immutable JSON-friendly totals only; no per-decision information survives."""

    agent_mode: str
    agent_decision_count: int
    decision_source_counts: tuple[tuple[str, int], ...]
    model_attempt_count: int
    model_outcome_counts: tuple[tuple[str, int], ...]
    rule_fallback_count: int

    def __post_init__(self) -> None:
        if self.agent_mode not in AGENT_MODES:
            raise AgentObservabilityError("invalid_agent_mode")
        decisions = _validate_count_tuple(self.decision_source_counts, DECISION_SOURCES)
        outcomes = _validate_count_tuple(self.model_outcome_counts, MODEL_OUTCOMES)
        if _count(self.agent_decision_count) != sum(count for _, count in decisions):
            raise AgentObservabilityError("decision_conservation_failed")
        if _count(self.model_attempt_count) != sum(count for _, count in outcomes):
            raise AgentObservabilityError("model_conservation_failed")
        fallback_count = _count(self.rule_fallback_count)
        sources = dict(decisions)
        if fallback_count != sources.get("deepseek_rule_fallback", 0) + sources.get("adapter_rule_fallback", 0):
            raise AgentObservabilityError("fallback_conservation_failed")
        if self.agent_mode == "rule":
            if self.model_attempt_count or outcomes or any(name != "rule_primary" for name, _ in decisions):
                raise AgentObservabilityError("rule_mode_model_activity")
        elif self.agent_mode == "deepseek":
            if self.model_attempt_count != (
                sources.get("model", 0)
                + sources.get("danger_opponent_block", 0)
                + sources.get("short_endgame_plan", 0)
                + sources.get("teammate_control_block", 0)
                + sources.get("deepseek_rule_fallback", 0)
            ):
                raise AgentObservabilityError("deepseek_model_conservation_failed")
        elif (
            self.model_attempt_count
            or outcomes
            or fallback_count
            or any(name not in {"conditional_pressure_pass", "conditional_rule_based"} for name, _ in decisions)
        ):
            raise AgentObservabilityError("conditional_pressure_pass_mode_activity")

    def to_json(self) -> dict[str, object]:
        return {
            "agent_mode": self.agent_mode,
            "agent_decision_count": self.agent_decision_count,
            "decision_source_counts": [[name, count] for name, count in self.decision_source_counts],
            "model_attempt_count": self.model_attempt_count,
            "model_outcome_counts": [[name, count] for name, count in self.model_outcome_counts],
            "rule_fallback_count": self.rule_fallback_count,
        }


class AgentObservabilityRecorder:
    """Mutable recorder whose only public output is an immutable snapshot."""

    __slots__ = ("_decision_sources", "_model_outcomes")

    def __init__(self) -> None:
        self._decision_sources: Counter[str] = Counter()
        self._model_outcomes: Counter[str] = Counter()

    def record_decision_source(self, source: object) -> None:
        if not isinstance(source, str) or source not in DECISION_SOURCES:
            raise AgentObservabilityError("invalid_decision_source")
        self._decision_sources[source] += 1

    def record_model_outcome(self, outcome: object) -> None:
        if not isinstance(outcome, str) or outcome not in MODEL_OUTCOMES:
            raise AgentObservabilityError("invalid_model_outcome")
        self._model_outcomes[outcome] += 1

    def snapshot(self, agent_mode: object) -> AgentObservabilitySnapshot:
        if not isinstance(agent_mode, str):
            raise AgentObservabilityError("invalid_agent_mode")
        decisions = _normalized_counts(self._decision_sources, DECISION_SOURCES)
        outcomes = _normalized_counts(self._model_outcomes, MODEL_OUTCOMES)
        sources = dict(decisions)
        return AgentObservabilitySnapshot(
            agent_mode=agent_mode,
            agent_decision_count=sum(count for _, count in decisions),
            decision_source_counts=decisions,
            model_attempt_count=sum(count for _, count in outcomes),
            model_outcome_counts=outcomes,
            rule_fallback_count=sources.get("deepseek_rule_fallback", 0) + sources.get("adapter_rule_fallback", 0),
        )
