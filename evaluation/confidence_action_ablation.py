"""Aggregate-only paired action ablation for confidence prompt payloads.

The harness deliberately has no provider implementation.  Callers inject a
suggestion callable, allowing deterministic local tests without configuration,
transport, or model access.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
from types import MappingProxyType
from typing import Protocol

from agents.base import require_legal_action_id
from agents.card_belief import NORMAL_RANKS
from agents.card_confidence_prompt import CardConfidencePromptPayload, build_card_confidence_prompt_payload
from agents.card_confidence_pipeline import build_runtime_card_confidence
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.game_phase import CRITICAL_ENDGAME, GamePhaseContext, classify_game_phase
from engine.game import GuanDanGame
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


_EXTERNAL_BUCKETS = (
    ("external_0_4", 0, 4),
    ("external_5_8", 5, 8),
    ("external_9_12", 9, 12),
)
_PRESSURE_PATTERNS = frozenset({"bomb", "straight_flush", "joker_bomb"})


class SuggestionProvider(Protocol):
    def __call__(self, **kwargs: object) -> DeepSeekSuggestion:
        ...


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value > 0


def _freeze_counts(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted(values.items())))


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _external_bucket(value: object) -> str | None:
    if not _is_int(value):
        return None
    for name, lower, upper in _EXTERNAL_BUCKETS:
        if lower <= value <= upper:
            return name
    return None


def _category(value: object) -> str:
    return str(value).split(":", 1)[0]


def _validate_inputs(
    seeds: Sequence[int],
    *,
    suggestion_provider: SuggestionProvider,
    strategic_pass_rates: Sequence[int],
    samples_per_bucket: int,
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
        raise ValueError("each seed must be a non-bool integer")
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
        raise ValueError("each strategic_pass_rate must be an integer from 0 through 100")
    if len(set(rates)) != len(rates):
        raise ValueError("strategic_pass_rates must not contain duplicates")
    if not callable(suggestion_provider):
        raise ValueError("suggestion_provider must be callable")
    if not isinstance(current_level_rank, str) or current_level_rank not in NORMAL_RANKS:
        raise ValueError("current_level_rank must be a supported normal rank")
    for name, value in (
        ("samples_per_bucket", samples_per_bucket),
        ("max_steps", max_steps),
        ("max_samples_per_game", max_samples_per_game),
        ("max_external_cards", max_external_cards),
        ("max_search_nodes", max_search_nodes),
        ("max_solutions", max_solutions),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive non-bool integer")
    if max_external_cards > 12:
        raise ValueError("max_external_cards must not exceed 12")
    return normalized_seeds, rates


@dataclass(frozen=True, slots=True)
class ActionAblationBucket:
    only_pass_skip_count: int
    finish_action_skip_count: int
    confidence_unavailable_count: int
    payload_omitted_count: int
    prompt_mismatch_count: int
    qualified_candidate_count: int
    quota_not_selected_count: int
    selected_sample_count: int
    off_first_pair_count: int
    on_first_pair_count: int
    off_attempted_call_count: int
    on_attempted_call_count: int
    off_valid_response_count: int
    on_valid_response_count: int
    off_no_action_count: int
    on_no_action_count: int
    off_exception_count: int
    on_exception_count: int
    off_malformed_result_count: int
    on_malformed_result_count: int
    off_invalid_action_type_count: int
    on_invalid_action_type_count: int
    off_outside_legal_count: int
    on_outside_legal_count: int
    off_outside_prompt_count: int
    on_outside_prompt_count: int
    both_valid_pair_count: int
    only_off_valid_count: int
    only_on_valid_count: int
    neither_valid_count: int
    same_action_count: int
    changed_action_count: int
    off_pass_selection_count: int
    on_pass_selection_count: int
    off_pressure_selection_count: int
    on_pressure_selection_count: int
    prompt_pair_sha256: str
    diagnostic_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        fields = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"diagnostic_counts"}
        }
        fields["diagnostic_counts"] = dict(self.diagnostic_counts)
        return fields


@dataclass(frozen=True, slots=True)
class PolicyActionAblationReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    requested_game_count: int
    completed_game_count: int
    incomplete_game_count: int
    eligible_critical_count: int
    duplicate_sample_count: int
    sample_limit_skipped_count: int
    unexpected_external_count: int
    overall: ActionAblationBucket
    by_external_count: Mapping[str, ActionAblationBucket]
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
            "eligible_critical_count": self.eligible_critical_count,
            "duplicate_sample_count": self.duplicate_sample_count,
            "sample_limit_skipped_count": self.sample_limit_skipped_count,
            "unexpected_external_count": self.unexpected_external_count,
            "overall": self.overall.to_dict(),
            "by_external_count": {
                name: bucket.to_dict() for name, bucket in self.by_external_count.items()
            },
            "diagnostic_counts": dict(self.diagnostic_counts),
        }


@dataclass(frozen=True, slots=True)
class ConfidenceActionAblationReport:
    requested_policy_count: int
    by_policy: Mapping[str, PolicyActionAblationReport]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "by_policy": {name: report.to_dict() for name, report in self.by_policy.items()},
        }


class _Accumulator:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.diagnostics: Counter[str] = Counter()
        self.hasher = hashlib.sha256()

    def add_diagnostic(self, diagnostic: str) -> None:
        self.diagnostics[_category(diagnostic)] += 1

    def digest_pair(self, bucket_name: str, off_prompt: str, on_prompt: str) -> None:
        item = json.dumps(
            [bucket_name, off_prompt, on_prompt],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.hasher.update(item.encode("utf-8"))

    def freeze(self) -> ActionAblationBucket:
        return ActionAblationBucket(
            **{name: self.counts[name] for name in ActionAblationBucket.__dataclass_fields__
               if name not in {"prompt_pair_sha256", "diagnostic_counts"}},
            prompt_pair_sha256=self.hasher.hexdigest(),
            diagnostic_counts=_freeze_counts(self.diagnostics),
        )


@dataclass(slots=True)
class _Candidate:
    priority_digest: str
    step_no: int
    observer_player_id: int
    bucket_name: str
    observation: dict[str, object]
    legal_actions: list[dict[str, object]]
    prompt_actions: list[dict[str, object]]
    phase_context: GamePhaseContext
    payload: CardConfidencePromptPayload
    off_prompt: str
    on_prompt: str


def _is_only_pass(legal_actions: Sequence[Mapping[str, object]]) -> bool:
    return bool(legal_actions) and all(action.get("declared_pattern") == "pass" for action in legal_actions)


def _has_finish_action(legal_actions: Sequence[Mapping[str, object]], hand_count: object) -> bool:
    if not _is_positive_int(hand_count):
        return False
    return any(
        action.get("declared_pattern") != "pass"
        and isinstance(action.get("carrier_cards"), list)
        and len(action["carrier_cards"]) == hand_count
        for action in legal_actions
    )


def _priority(policy_name: str, bucket_name: str, seed: int, step_no: int, player_id: int) -> str:
    value = "|".join((policy_name, bucket_name, str(seed), str(step_no), str(player_id)))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _prompt_actions(
    observation: Mapping[str, object],
    legal_actions: list[dict[str, object]],
    phase_context: GamePhaseContext,
) -> list[dict[str, object]]:
    current_round = observation.get("current_round")
    my_info = observation.get("my_info")
    if not isinstance(current_round, Mapping) or not isinstance(my_info, Mapping):
        return []
    constraint = current_round.get("constraint")
    step_no = current_round.get("step_no")
    hand_count = my_info.get("hand_count")
    if not isinstance(constraint, str):
        return []
    return DeepSeekClient._prune_legal_actions(
        legal_actions,
        constraint,
        step_no=step_no if _is_int(step_no) else 0,
        hand_count=hand_count if _is_int(hand_count) else None,
        phase_context=phase_context,
    )


def _structured_prompt(
    observation: Mapping[str, object],
    prompt_actions: list[dict[str, object]],
    phase_context: GamePhaseContext,
    payload: CardConfidencePromptPayload | None,
) -> str:
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    other_players = observation.get("other_players")
    history = observation.get("history")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping):
        raise ValueError("malformed public observation")
    return DeepSeekClient._build_structured_prompt(
        my_info=dict(my_info),
        current_round=dict(current_round),
        other_players=[dict(item) for item in other_players if isinstance(item, Mapping)]
        if isinstance(other_players, Sequence) and not isinstance(other_players, (str, bytes)) else [],
        history=dict(history) if isinstance(history, Mapping) else {},
        legal_actions=prompt_actions,
        rag_context=None,
        hand_evaluation=None,
        card_tracking_summary=None,
        phase_context=phase_context,
        card_confidence_prompt=payload,
    )


def _expected_on_prompt(off_prompt: str, payload: CardConfidencePromptPayload) -> str:
    marker = "【场景标签】"
    insertion = f"【残局牌面信念】\n{payload.text}\n\n"
    return off_prompt.replace(marker, insertion + marker, 1) if off_prompt.count(marker) == 1 else off_prompt


def _prompt_pair_is_exact(off_prompt: str, on_prompt: str, payload: CardConfidencePromptPayload) -> bool:
    return (
        on_prompt == _expected_on_prompt(off_prompt, payload)
        and on_prompt.count("【残局牌面信念】") == 1
        and on_prompt.count(payload.text) == 1
    )


def _classify_result(
    result: object,
    legal_by_id: Mapping[int, Mapping[str, object]],
    prompt_ids: frozenset[int],
) -> tuple[str, int | None]:
    if not isinstance(result, DeepSeekSuggestion):
        return "malformed_result", None
    action_id = result.action_id
    if action_id is None:
        return "no_action", None
    if not _is_int(action_id):
        return "invalid_action_type", None
    if action_id not in legal_by_id:
        return "outside_legal", None
    if action_id not in prompt_ids:
        return "outside_prompt", None
    return "valid", action_id


def _call_provider(
    provider: SuggestionProvider,
    kwargs: Mapping[str, object],
    *,
    legal_by_id: Mapping[int, Mapping[str, object]],
    prompt_ids: frozenset[int],
) -> tuple[str, int | None]:
    try:
        return _classify_result(provider(**kwargs), legal_by_id, prompt_ids)
    except Exception:
        return "exception", None


def _record_condition(
    accumulator: _Accumulator,
    condition: str,
    outcome: str,
    action_id: int | None,
    legal_by_id: Mapping[int, Mapping[str, object]],
) -> bool:
    accumulator.counts[f"{condition}_attempted_call_count"] += 1
    if outcome != "valid" or action_id is None:
        accumulator.counts[f"{condition}_{outcome}_count"] += 1
        return False
    accumulator.counts[f"{condition}_valid_response_count"] += 1
    action = legal_by_id[action_id]
    pattern = action.get("declared_pattern")
    if pattern == "pass":
        accumulator.counts[f"{condition}_pass_selection_count"] += 1
    if pattern in _PRESSURE_PATTERNS:
        accumulator.counts[f"{condition}_pressure_selection_count"] += 1
    return True


def _merge_accumulators(accumulators: Mapping[str, _Accumulator]) -> ActionAblationBucket:
    combined = _Accumulator()
    for name in (bucket[0] for bucket in _EXTERNAL_BUCKETS):
        source = accumulators[name]
        combined.counts.update(source.counts)
        combined.diagnostics.update(source.diagnostics)
        combined.hasher.update(source.hasher.digest())
    return combined.freeze()


def _collect_policy(
    seeds: tuple[int, ...],
    *,
    rate: int,
    suggestion_provider: SuggestionProvider,
    samples_per_bucket: int,
    current_level_rank: str,
    max_steps: int,
    max_samples_per_game: int,
    max_external_cards: int,
    max_search_nodes: int,
    max_solutions: int,
) -> PolicyActionAblationReport:
    policy_name = _policy_name(rate)
    accumulators = {name: _Accumulator() for name, _, _ in _EXTERNAL_BUCKETS}
    selected: dict[str, list[_Candidate]] = {name: [] for name, _, _ in _EXTERNAL_BUCKETS}
    overall_pair_hasher = hashlib.sha256()
    qualified_counts: Counter[str] = Counter()
    runtime_diagnostics: Counter[str] = Counter()
    created_agents: list[StrategicPassAIAgent] = []
    seen_sample_ids: set[tuple[int, int, int]] = set()
    eligible_critical_count = duplicate_sample_count = sample_limit_skipped_count = 0
    unexpected_external_count = completed_game_count = incomplete_game_count = 0

    for seed in seeds:
        game = GuanDanGame(seed=seed, current_level_rank=current_level_rank)
        game.reset()
        agents = {
            player_id: StrategicPassAIAgent(player_id=player_id, strategic_pass_rate=rate)
            for player_id in (1, 2, 3, 4)
        }
        created_agents.extend(agents.values())
        game_critical_count = 0
        limit_reported = False
        game_over = False

        for _ in range(max_steps):
            observation = game.observe()
            phase_context = classify_game_phase(observation)
            my_info = observation.get("my_info")
            current_round = observation.get("current_round")
            player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            step_no = current_round.get("step_no") if isinstance(current_round, Mapping) else None
            legal_actions = game.legal_actions()

            if phase_context.phase == CRITICAL_ENDGAME:
                eligible_critical_count += 1
                if not _is_int(player_id) or not _is_int(step_no):
                    runtime_diagnostics["invalid_sample_identity"] += 1
                else:
                    sample_id = (seed, step_no, player_id)
                    if sample_id in seen_sample_ids:
                        duplicate_sample_count += 1
                        runtime_diagnostics["duplicate_sample"] += 1
                    else:
                        seen_sample_ids.add(sample_id)
                        bucket_name = _external_bucket(phase_context.external_unknown_count)
                        if bucket_name is None:
                            unexpected_external_count += 1
                            runtime_diagnostics["unexpected_external_count"] += 1
                        elif game_critical_count >= max_samples_per_game:
                            sample_limit_skipped_count += 1
                            if not limit_reported:
                                runtime_diagnostics["sample_limit_reached"] += 1
                                limit_reported = True
                        else:
                            game_critical_count += 1
                            accumulator = accumulators[bucket_name]
                            legal_mappings = [item for item in legal_actions if isinstance(item, Mapping)]
                            if not legal_mappings or _is_only_pass(legal_mappings):
                                accumulator.counts["only_pass_skip_count"] += 1
                            elif _has_finish_action(legal_mappings, my_info.get("hand_count") if isinstance(my_info, Mapping) else None):
                                accumulator.counts["finish_action_skip_count"] += 1
                            else:
                                try:
                                    confidence = build_runtime_card_confidence(
                                        observation,
                                        phase_context,
                                        max_external_cards=max_external_cards,
                                        max_search_nodes=max_search_nodes,
                                        max_solutions=max_solutions,
                                    )
                                    if confidence.status != "available":
                                        accumulator.counts["confidence_unavailable_count"] += 1
                                        for diagnostic in confidence.diagnostics:
                                            accumulator.add_diagnostic(str(diagnostic))
                                    else:
                                        payload = build_card_confidence_prompt_payload(confidence)
                                        if payload.status != "ready":
                                            accumulator.counts["payload_omitted_count"] += 1
                                            for diagnostic in payload.diagnostics:
                                                accumulator.add_diagnostic(diagnostic)
                                        else:
                                            prompt_actions = _prompt_actions(observation, legal_actions, phase_context)
                                            off_prompt = _structured_prompt(observation, prompt_actions, phase_context, None)
                                            on_prompt = _structured_prompt(observation, prompt_actions, phase_context, payload)
                                            if not prompt_actions or not _prompt_pair_is_exact(off_prompt, on_prompt, payload):
                                                accumulator.counts["prompt_mismatch_count"] += 1
                                                accumulator.add_diagnostic("prompt_pair_mismatch")
                                            else:
                                                qualified_counts[bucket_name] += 1
                                                accumulator.counts["qualified_candidate_count"] += 1
                                                candidate = _Candidate(
                                                    _priority(policy_name, bucket_name, seed, step_no, player_id),
                                                    step_no, player_id, bucket_name, observation, legal_actions,
                                                    prompt_actions, phase_context, payload, off_prompt, on_prompt,
                                                )
                                                current = selected[bucket_name]
                                                current.append(candidate)
                                                current.sort(key=lambda item: (item.priority_digest, item.step_no, item.observer_player_id))
                                                if len(current) > samples_per_bucket:
                                                    current.pop()
                                except Exception:
                                    accumulator.counts["prompt_mismatch_count"] += 1
                                    accumulator.add_diagnostic("collection_error")

            if not _is_int(player_id) or player_id not in agents:
                raise RuntimeError("public observer player id is invalid")
            action_id = agents[player_id].select_action(observation, legal_actions)
            result = game.step(require_legal_action_id(action_id, legal_actions))
            if result.get("game_over") is True:
                game_over = True
                break
        if game_over:
            completed_game_count += 1
        else:
            incomplete_game_count += 1
            runtime_diagnostics["max_steps_reached"] += 1

    for bucket_name, _, _ in _EXTERNAL_BUCKETS:
        accumulator = accumulators[bucket_name]
        candidates = selected[bucket_name]
        accumulator.counts["quota_not_selected_count"] = qualified_counts[bucket_name] - len(candidates)
        if len(candidates) < samples_per_bucket:
            accumulator.add_diagnostic("sample_quota_not_reached")
        for index, candidate in enumerate(candidates):
            accumulator.counts["selected_sample_count"] += 1
            off_first = index % 2 == 0
            accumulator.counts["off_first_pair_count" if off_first else "on_first_pair_count"] += 1
            legal_by_id = {
                action["action_id"]: action
                for action in candidate.legal_actions
                if _is_int(action.get("action_id"))
            }
            prompt_ids = frozenset(
                action["action_id"] for action in candidate.prompt_actions if _is_int(action.get("action_id"))
            )
            common: dict[str, object] = {
                "observation": candidate.observation,
                "legal_actions": candidate.legal_actions,
                "prompt_actions": candidate.prompt_actions,
                "rag_context": None,
                "hand_evaluation": None,
                "card_tracking_summary": None,
                "phase_context": candidate.phase_context,
                "verbose": False,
                "debug_prefix": "[confidence-action-ablation]",
            }
            on_kwargs = dict(common)
            on_kwargs["card_confidence_prompt"] = candidate.payload
            if set(on_kwargs) - set(common) != {"card_confidence_prompt"} or any(
                on_kwargs[key] != value for key, value in common.items()
            ):
                raise RuntimeError("paired provider kwargs diverged")
            calls = (("off", common), ("on", on_kwargs)) if off_first else (("on", on_kwargs), ("off", common))
            results: dict[str, tuple[str, int | None]] = {}
            for condition, kwargs in calls:
                results[condition] = _call_provider(
                    suggestion_provider,
                    kwargs,
                    legal_by_id=legal_by_id,
                    prompt_ids=prompt_ids,
                )
            off_valid = _record_condition(accumulator, "off", *results["off"], legal_by_id)
            on_valid = _record_condition(accumulator, "on", *results["on"], legal_by_id)
            if off_valid and on_valid:
                accumulator.counts["both_valid_pair_count"] += 1
                if results["off"][1] == results["on"][1]:
                    accumulator.counts["same_action_count"] += 1
                else:
                    accumulator.counts["changed_action_count"] += 1
            elif off_valid:
                accumulator.counts["only_off_valid_count"] += 1
            elif on_valid:
                accumulator.counts["only_on_valid_count"] += 1
            else:
                accumulator.counts["neither_valid_count"] += 1
            accumulator.digest_pair(bucket_name, candidate.off_prompt, candidate.on_prompt)
            item = json.dumps(
                [bucket_name, candidate.off_prompt, candidate.on_prompt],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            overall_pair_hasher.update(item.encode("utf-8"))

    buckets = {name: accumulators[name].freeze() for name, _, _ in _EXTERNAL_BUCKETS}
    overall = replace(
        _merge_accumulators(accumulators),
        prompt_pair_sha256=overall_pair_hasher.hexdigest(),
    )
    diagnostics = Counter(runtime_diagnostics)
    for bucket in buckets.values():
        diagnostics.update(bucket.diagnostic_counts)
    opportunity_count = sum(agent.strategic_pass_opportunity_count for agent in created_agents)
    pass_count = sum(agent.strategic_pass_count for agent in created_agents)
    if not 0 <= pass_count <= opportunity_count:
        raise RuntimeError("strategic pass counters violate their invariant")
    return PolicyActionAblationReport(
        policy_name=policy_name,
        strategic_pass_rate=rate,
        strategic_pass_opportunity_count=opportunity_count,
        strategic_pass_count=pass_count,
        requested_game_count=len(seeds),
        completed_game_count=completed_game_count,
        incomplete_game_count=incomplete_game_count,
        eligible_critical_count=eligible_critical_count,
        duplicate_sample_count=duplicate_sample_count,
        sample_limit_skipped_count=sample_limit_skipped_count,
        unexpected_external_count=unexpected_external_count,
        overall=overall,
        by_external_count=MappingProxyType(dict(buckets)),
        diagnostic_counts=_freeze_counts(diagnostics),
    )


def run_confidence_action_ablation(
    seeds: Sequence[int],
    *,
    suggestion_provider: SuggestionProvider,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    samples_per_bucket: int = 4,
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> ConfidenceActionAblationReport:
    """Run fixed public samples through an injected off/on suggestion provider."""

    normalized_seeds, rates = _validate_inputs(
        seeds,
        suggestion_provider=suggestion_provider,
        strategic_pass_rates=strategic_pass_rates,
        samples_per_bucket=samples_per_bucket,
        current_level_rank=current_level_rank,
        max_steps=max_steps,
        max_samples_per_game=max_samples_per_game,
        max_external_cards=max_external_cards,
        max_search_nodes=max_search_nodes,
        max_solutions=max_solutions,
    )
    reports = {
        _policy_name(rate): _collect_policy(
            normalized_seeds,
            rate=rate,
            suggestion_provider=suggestion_provider,
            samples_per_bucket=samples_per_bucket,
            current_level_rank=current_level_rank,
            max_steps=max_steps,
            max_samples_per_game=max_samples_per_game,
            max_external_cards=max_external_cards,
            max_search_nodes=max_search_nodes,
            max_solutions=max_solutions,
        )
        for rate in rates
    }
    return ConfidenceActionAblationReport(
        requested_policy_count=len(rates),
        by_policy=MappingProxyType(dict(reports)),
    )
