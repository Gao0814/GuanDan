"""Aggregate-only paired prompt coverage collection for confidence payloads."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from agents.base import require_legal_action_id
from agents.card_belief import NORMAL_RANKS
from agents.card_confidence_pipeline import build_runtime_card_confidence
from agents.card_confidence_prompt import build_card_confidence_prompt_payload
from agents.deepseek_client import DeepSeekClient
from agents.game_phase import CRITICAL_ENDGAME, classify_game_phase
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_EXTERNAL_BUCKETS = (
    ("external_0_4", 0, 4),
    ("external_5_8", 5, 8),
    ("external_9_12", 9, 12),
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _diagnostic_category(value: object) -> str:
    return str(value).split(":", 1)[0]


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _validate_inputs(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int],
    current_level_rank: str,
    max_steps: int,
    max_samples_per_game: int,
    max_external_cards: int,
    max_search_nodes: int,
    max_solutions: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if isinstance(seeds, (str, bytes)) or not isinstance(seeds, Sequence) or not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    normalized_seeds = tuple(seeds)
    if any(not _is_int(seed) for seed in normalized_seeds):
        raise ValueError("each seed must be an integer")
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must not contain duplicates")
    if (
        isinstance(strategic_pass_rates, (str, bytes))
        or not isinstance(strategic_pass_rates, Sequence)
        or not strategic_pass_rates
    ):
        raise ValueError("strategic_pass_rates must be a non-empty sequence")
    rates = tuple(strategic_pass_rates)
    if any(not _is_int(rate) or not 0 <= rate <= 100 for rate in rates):
        raise ValueError("each strategic_pass_rate must be an integer from 0 to 100")
    if len(set(rates)) != len(rates):
        raise ValueError("strategic_pass_rates must not contain duplicates")
    if not isinstance(current_level_rank, str) or current_level_rank not in NORMAL_RANKS:
        raise ValueError("current_level_rank must be a supported normal rank")
    for name, value in (
        ("max_steps", max_steps),
        ("max_samples_per_game", max_samples_per_game),
        ("max_external_cards", max_external_cards),
        ("max_search_nodes", max_search_nodes),
        ("max_solutions", max_solutions),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")
    if max_external_cards > 12:
        raise ValueError("max_external_cards must not exceed 12")
    return normalized_seeds, rates


def _external_bucket(value: object) -> str | None:
    if not _is_int(value):
        return None
    for name, lower, upper in _EXTERNAL_BUCKETS:
        if lower <= value <= upper:
            return name
    return None


@dataclass(frozen=True, slots=True)
class ConfidencePromptCoverageBucket:
    sample_count: int
    confidence_available_count: int
    confidence_unavailable_count: int
    payload_ready_count: int
    payload_omitted_count: int
    budget_omitted_count: int
    ready_exact_insertion_count: int
    omitted_prompt_equal_count: int
    pair_mismatch_count: int
    payload_char_sum: int
    payload_char_min: int
    payload_char_max: int
    prompt_delta_char_sum: int
    prompt_delta_char_min: int
    prompt_delta_char_max: int
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "confidence_available_count": self.confidence_available_count,
            "confidence_unavailable_count": self.confidence_unavailable_count,
            "payload_ready_count": self.payload_ready_count,
            "payload_omitted_count": self.payload_omitted_count,
            "budget_omitted_count": self.budget_omitted_count,
            "ready_exact_insertion_count": self.ready_exact_insertion_count,
            "omitted_prompt_equal_count": self.omitted_prompt_equal_count,
            "pair_mismatch_count": self.pair_mismatch_count,
            "payload_char_sum": self.payload_char_sum,
            "payload_char_min": self.payload_char_min,
            "payload_char_max": self.payload_char_max,
            "prompt_delta_char_sum": self.prompt_delta_char_sum,
            "prompt_delta_char_min": self.prompt_delta_char_min,
            "prompt_delta_char_max": self.prompt_delta_char_max,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class PolicyConfidencePromptReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    eligible_sample_count: int
    evaluated_sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    sample_limit_skipped_count: int
    overall: ConfidencePromptCoverageBucket
    by_external_count: Mapping[str, ConfidencePromptCoverageBucket]
    prompt_pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_name": self.policy_name,
            "strategic_pass_rate": self.strategic_pass_rate,
            "strategic_pass_opportunity_count": self.strategic_pass_opportunity_count,
            "strategic_pass_count": self.strategic_pass_count,
            "requested_game_count": self.requested_game_count,
            "completed_game_count": self.completed_game_count,
            "incomplete_game_count": self.incomplete_game_count,
            "eligible_sample_count": self.eligible_sample_count,
            "evaluated_sample_count": self.evaluated_sample_count,
            "valid_sample_count": self.valid_sample_count,
            "invalid_sample_count": self.invalid_sample_count,
            "sample_limit_skipped_count": self.sample_limit_skipped_count,
            "overall": self.overall.to_dict(),
            "by_external_count": {
                name: bucket.to_dict() for name, bucket in self.by_external_count.items()
            },
            "prompt_pair_sha256": self.prompt_pair_sha256,
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class ConfidencePromptBenchmarkReport:
    requested_policy_count: int
    by_policy: Mapping[str, PolicyConfidencePromptReport]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "by_policy": {name: report.to_dict() for name, report in self.by_policy.items()},
        }


class _BucketAccumulator:
    def __init__(self) -> None:
        self.sample_count = 0
        self.confidence_available_count = 0
        self.confidence_unavailable_count = 0
        self.payload_ready_count = 0
        self.payload_omitted_count = 0
        self.budget_omitted_count = 0
        self.ready_exact_insertion_count = 0
        self.omitted_prompt_equal_count = 0
        self.pair_mismatch_count = 0
        self.payload_chars: list[int] = []
        self.prompt_deltas: list[int] = []
        self.diagnostic_counts: Counter[str] = Counter()

    def record_failure(self, diagnostic: str) -> None:
        self.sample_count += 1
        self.confidence_unavailable_count += 1
        self.payload_omitted_count += 1
        self.diagnostic_counts[_diagnostic_category(diagnostic)] += 1

    def record(
        self,
        *,
        confidence: object,
        payload: object,
        off_prompt: str,
        on_prompt: str,
    ) -> bool:
        self.sample_count += 1
        sample_diagnostics: set[str] = set()
        confidence_status = getattr(confidence, "status", None)
        if confidence_status == "available":
            self.confidence_available_count += 1
        else:
            self.confidence_unavailable_count += 1
        sample_diagnostics.update(
            _diagnostic_category(item)
            for item in getattr(confidence, "diagnostics", ())
        )

        payload_status = getattr(payload, "status", None)
        if payload_status == "ready":
            self.payload_ready_count += 1
            char_count = getattr(payload, "char_count", 0)
            if _is_positive_int(char_count):
                self.payload_chars.append(char_count)
            else:
                sample_diagnostics.add("invalid_payload_char_count")
            text = getattr(payload, "text", "")
            expected = _expected_on_prompt(off_prompt, text)
            exact = (
                on_prompt == expected
                and on_prompt.count("【残局牌面信念】") == 1
                and isinstance(text, str)
                and on_prompt.count(text) == 1
            )
            delta = len(on_prompt) - len(off_prompt)
            if exact and delta > 0:
                self.ready_exact_insertion_count += 1
                self.prompt_deltas.append(delta)
                valid = True
            else:
                self.pair_mismatch_count += 1
                sample_diagnostics.add("prompt_pair_mismatch")
                valid = False
        else:
            self.payload_omitted_count += 1
            sample_diagnostics.update(
                _diagnostic_category(item)
                for item in getattr(payload, "diagnostics", ())
            )
            if "prompt_budget_exceeded" in sample_diagnostics:
                self.budget_omitted_count += 1
            if on_prompt == off_prompt:
                self.omitted_prompt_equal_count += 1
                valid = True
            else:
                self.pair_mismatch_count += 1
                sample_diagnostics.add("prompt_pair_mismatch")
                valid = False
        self.diagnostic_counts.update(sample_diagnostics)
        return valid

    def freeze(self) -> ConfidencePromptCoverageBucket:
        return ConfidencePromptCoverageBucket(
            sample_count=self.sample_count,
            confidence_available_count=self.confidence_available_count,
            confidence_unavailable_count=self.confidence_unavailable_count,
            payload_ready_count=self.payload_ready_count,
            payload_omitted_count=self.payload_omitted_count,
            budget_omitted_count=self.budget_omitted_count,
            ready_exact_insertion_count=self.ready_exact_insertion_count,
            omitted_prompt_equal_count=self.omitted_prompt_equal_count,
            pair_mismatch_count=self.pair_mismatch_count,
            payload_char_sum=sum(self.payload_chars),
            payload_char_min=min(self.payload_chars, default=0),
            payload_char_max=max(self.payload_chars, default=0),
            prompt_delta_char_sum=sum(self.prompt_deltas),
            prompt_delta_char_min=min(self.prompt_deltas, default=0),
            prompt_delta_char_max=max(self.prompt_deltas, default=0),
            diagnostic_counts=_freeze_counts(self.diagnostic_counts),
        )


def _expected_on_prompt(off_prompt: str, text: object) -> str:
    if not isinstance(text, str):
        return off_prompt
    marker = "【场景标签】"
    insertion = f"【残局牌面信念】\n{text}\n\n"
    if off_prompt.count(marker) != 1:
        return off_prompt
    return off_prompt.replace(marker, insertion + marker, 1)


def _overall_bucket(buckets: Mapping[str, _BucketAccumulator]) -> ConfidencePromptCoverageBucket:
    combined = _BucketAccumulator()
    for accumulator in buckets.values():
        combined.sample_count += accumulator.sample_count
        combined.confidence_available_count += accumulator.confidence_available_count
        combined.confidence_unavailable_count += accumulator.confidence_unavailable_count
        combined.payload_ready_count += accumulator.payload_ready_count
        combined.payload_omitted_count += accumulator.payload_omitted_count
        combined.budget_omitted_count += accumulator.budget_omitted_count
        combined.ready_exact_insertion_count += accumulator.ready_exact_insertion_count
        combined.omitted_prompt_equal_count += accumulator.omitted_prompt_equal_count
        combined.pair_mismatch_count += accumulator.pair_mismatch_count
        combined.payload_chars.extend(accumulator.payload_chars)
        combined.prompt_deltas.extend(accumulator.prompt_deltas)
        combined.diagnostic_counts.update(accumulator.diagnostic_counts)
    return combined.freeze()


def _prompt_pair(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
    phase_context: object,
    payload: object,
) -> tuple[str, str]:
    my_info = dict(observation.get("my_info", {}))
    current_round = dict(observation.get("current_round", {}))
    other_players = [dict(item) for item in observation.get("other_players", []) if isinstance(item, dict)]
    history = dict(observation.get("history", {}))
    constraint = str(current_round.get("constraint", "free"))
    step_no = current_round.get("step_no", 0)
    hand_count = my_info.get("hand_count")
    pruned_actions = DeepSeekClient._prune_legal_actions(
        legal_actions,
        constraint,
        step_no=step_no if _is_int(step_no) else 0,
        hand_count=hand_count if _is_int(hand_count) else None,
        phase_context=phase_context,
    )
    common = {
        "my_info": my_info,
        "current_round": current_round,
        "other_players": other_players,
        "history": history,
        "legal_actions": pruned_actions,
        "rag_context": None,
        "hand_evaluation": None,
        "card_tracking_summary": None,
        "phase_context": phase_context,
    }
    off_prompt = DeepSeekClient._build_structured_prompt(**common)
    on_prompt = DeepSeekClient._build_structured_prompt(
        **common,
        card_confidence_prompt=payload,
    )
    return off_prompt, on_prompt


def _hash_pair(hasher: object, bucket_name: str, off_prompt: str, on_prompt: str) -> None:
    item = json.dumps(
        [bucket_name, off_prompt, on_prompt],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    hasher.update(item.encode("utf-8"))


def _run_policy(
    seeds: tuple[int, ...],
    *,
    rate: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_game: int,
    max_external_cards: int,
    max_search_nodes: int,
    max_solutions: int,
) -> PolicyConfidencePromptReport:
    accumulators = {name: _BucketAccumulator() for name, _, _ in _EXTERNAL_BUCKETS}
    runtime_diagnostics: Counter[str] = Counter()
    hasher = hashlib.sha256()
    seen_sample_ids: set[tuple[int, object, object]] = set()
    created_agents: list[StrategicPassAIAgent] = []
    eligible_sample_count = 0
    valid_sample_count = 0
    invalid_sample_count = 0
    sample_limit_skipped_count = 0
    completed_game_count = 0
    incomplete_game_count = 0

    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents: dict[int, StrategicPassAIAgent] = {}
        for player_id in (1, 2, 3, 4):
            agent = StrategicPassAIAgent(player_id=player_id, strategic_pass_rate=rate)
            agents[player_id] = agent
            created_agents.append(agent)
        game_sample_count = 0
        sample_limit_reported = False
        game_over = False

        for _ in range(max_steps):
            observation = game.observe()
            phase_context = classify_game_phase(observation)
            my_info = observation.get("my_info")
            current_round = observation.get("current_round")
            observer_player_id = my_info.get("player_id") if isinstance(my_info, dict) else None
            step_no = current_round.get("step_no") if isinstance(current_round, dict) else None

            if phase_context.phase == CRITICAL_ENDGAME:
                eligible_sample_count += 1
                sample_id = (seed, step_no, observer_player_id)
                if sample_id in seen_sample_ids:
                    runtime_diagnostics["duplicate_sample"] += 1
                else:
                    seen_sample_ids.add(sample_id)
                    bucket_name = _external_bucket(phase_context.external_unknown_count)
                    if bucket_name is None:
                        runtime_diagnostics["unexpected_external_count"] += 1
                    elif game_sample_count >= max_samples_per_game:
                        sample_limit_skipped_count += 1
                        if not sample_limit_reported:
                            runtime_diagnostics["sample_limit_reached"] += 1
                            sample_limit_reported = True
                    else:
                        game_sample_count += 1
                        try:
                            confidence = build_runtime_card_confidence(
                                observation,
                                phase_context,
                                max_external_cards=max_external_cards,
                                max_search_nodes=max_search_nodes,
                                max_solutions=max_solutions,
                            )
                            payload = build_card_confidence_prompt_payload(confidence)
                            off_prompt, on_prompt = _prompt_pair(
                                observation,
                                game.legal_actions(),
                                phase_context,
                                payload,
                            )
                            _hash_pair(hasher, bucket_name, off_prompt, on_prompt)
                            if accumulators[bucket_name].record(
                                confidence=confidence,
                                payload=payload,
                                off_prompt=off_prompt,
                                on_prompt=on_prompt,
                            ):
                                valid_sample_count += 1
                            else:
                                invalid_sample_count += 1
                        except Exception:
                            runtime_diagnostics["collection_error"] += 1
                            accumulators[bucket_name].record_failure("collection_error")
                            invalid_sample_count += 1

            legal_actions = game.legal_actions()
            if not _is_int(observer_player_id) or observer_player_id not in agents:
                raise RuntimeError("public observer player id is invalid")
            action_id = agents[observer_player_id].select_action(observation, legal_actions)
            step_result = game.step(require_legal_action_id(action_id, legal_actions))
            if bool(step_result["game_over"]):
                game_over = True
                break

        if game_over:
            completed_game_count += 1
        else:
            incomplete_game_count += 1
            runtime_diagnostics["max_steps_reached"] += 1

    by_external_count = {name: accumulator.freeze() for name, accumulator in accumulators.items()}
    overall = _overall_bucket(accumulators)
    evaluated_sample_count = valid_sample_count + invalid_sample_count
    combined_diagnostics = Counter(runtime_diagnostics)
    combined_diagnostics.update(overall.diagnostic_counts)
    opportunity_count = sum(agent.strategic_pass_opportunity_count for agent in created_agents)
    pass_count = sum(agent.strategic_pass_count for agent in created_agents)
    if not 0 <= pass_count <= opportunity_count:
        raise RuntimeError("strategic pass counters violate their invariant")
    return PolicyConfidencePromptReport(
        policy_name=_policy_name(rate),
        strategic_pass_rate=rate,
        strategic_pass_opportunity_count=opportunity_count,
        strategic_pass_count=pass_count,
        requested_game_count=len(seeds),
        completed_game_count=completed_game_count,
        incomplete_game_count=incomplete_game_count,
        eligible_sample_count=eligible_sample_count,
        evaluated_sample_count=evaluated_sample_count,
        valid_sample_count=valid_sample_count,
        invalid_sample_count=invalid_sample_count,
        sample_limit_skipped_count=sample_limit_skipped_count,
        overall=overall,
        by_external_count=MappingProxyType(dict(by_external_count)),
        prompt_pair_sha256=hasher.hexdigest(),
        diagnostic_counts=_freeze_counts(combined_diagnostics),
    )


def run_confidence_prompt_benchmark(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> ConfidencePromptBenchmarkReport:
    """Collect deterministic aggregate-only prompt coverage by policy variant."""

    normalized_seeds, rates = _validate_inputs(
        seeds,
        strategic_pass_rates=strategic_pass_rates,
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_game=max_samples_per_game,
        max_external_cards=max_external_cards,
        max_search_nodes=max_search_nodes,
        max_solutions=max_solutions,
    )
    by_policy = {
        _policy_name(rate): _run_policy(
            normalized_seeds,
            rate=rate,
            current_level_rank=current_level_rank,
            max_steps=max_steps,
            max_samples_per_game=max_samples_per_game,
            max_external_cards=max_external_cards,
            max_search_nodes=max_search_nodes,
            max_solutions=max_solutions,
        )
        for rate in rates
    }
    return ConfidencePromptBenchmarkReport(
        requested_policy_count=len(rates),
        by_policy=MappingProxyType(dict(by_policy)),
    )
