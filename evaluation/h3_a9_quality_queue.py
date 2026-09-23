"""Independent, deterministic H3-A9 state queue for the quality proxy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json

from agents.base import require_legal_action_id
from agents.game_phase import ENDGAME_PHASES, MIDGAME, OPENING, classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.action_quality_proxy import (
    MAX_ROLLOUT_STEPS,
    ReplayableQualitySample,
    SampleSetResult,
    SampleSetStage,
    _make_sample,
    _reference_action_id,
    build_replayable_quality_samples,
)
from evaluation.h3_model_probe_fixtures import _advisor as _h3_advisor


H3_A9_SEEDS = tuple(range(920, 960))
H3_A9_SAMPLE_COUNT = 6
_OPENING_LAYER = OPENING
_MIDGAME_LAYER = MIDGAME
_ENDGAME_LAYER = "endgame_family"
_LAYER_ORDER = (_OPENING_LAYER, _MIDGAME_LAYER, _ENDGAME_LAYER)


def _public_signature(observation: dict[str, object], actions: list[dict[str, object]]) -> str:
    return json.dumps(
        [observation, actions],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _valid_seeded_initial_observation(observation: object) -> bool:
    if not isinstance(observation, Mapping):
        return False
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    history = observation.get("history")
    others = observation.get("other_players")
    if (
        not isinstance(my_info, Mapping)
        or my_info.get("player_id") != 1
        or my_info.get("hand_count") != 27
        or not isinstance(my_info.get("hand_cards"), list)
        or len(my_info["hand_cards"]) != 27
        or not isinstance(current_round, Mapping)
        or current_round.get("current_player_id") != 1
        or current_round.get("step_no") != 0
        or current_round.get("current_level_rank") != "2"
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
        or not isinstance(history, Mapping)
        or history.get("actions") != []
        or history.get("finish_order") != []
        or not isinstance(others, list)
        or len(others) != 3
        or any(not isinstance(item, Mapping) or item.get("hand_count") != 27 for item in others)
    ):
        return False
    return sum([my_info["hand_count"], *(item["hand_count"] for item in others)]) == 108


def _layer_for_phase(phase: str) -> str | None:
    if phase == OPENING:
        return _OPENING_LAYER
    if phase == MIDGAME:
        return _MIDGAME_LAYER
    if phase in ENDGAME_PHASES:
        return _ENDGAME_LAYER
    return None


def _first_eligible_states_for_seed(
    seed: int,
    advisor: RAGAdvisor,
    forbidden_signatures: set[str],
) -> tuple[dict[str, ReplayableQualitySample] | None, str | None]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    try:
        initial_observation = game.reset()
    except Exception:
        return None, "seed_initial_deal_invalid"
    if not _valid_seeded_initial_observation(initial_observation):
        return None, "seed_initial_deal_invalid"

    agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
    found: dict[str, ReplayableQualitySample] = {}
    for _step in range(MAX_ROLLOUT_STEPS):
        try:
            observation = game.observe()
            legal_actions = game.legal_actions()
            my_info = observation.get("my_info")
            player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            phase = classify_game_phase(observation).phase
        except Exception:
            return None, "public_state_invalid"

        layer = _layer_for_phase(phase)
        if (
            layer is not None
            and layer not in found
            and player_id == 1
            and sum(action.get("declared_pattern") != "pass" for action in legal_actions) >= 2
        ):
            sample, failure = _make_sample(
                name=layer,
                phase=phase,
                game=game,
                observation=observation,
                legal_actions=legal_actions,
                source_seed=seed,
                advisor=advisor,
            )
            if failure is not None:
                return None, "model_path_invalid"
            if sample is not None:
                reference_id = _reference_action_id(observation, legal_actions)
                signature = _public_signature(observation, legal_actions)
                if reference_id is None:
                    return None, "reference_action_invalid"
                if reference_id in sample.final_candidate_ids and signature not in forbidden_signatures:
                    found[layer] = sample

        if len(found) == len(_LAYER_ORDER):
            return found, None
        if type(player_id) is not int or player_id not in agents:
            return None, "sample_player_invalid"
        try:
            action_id = require_legal_action_id(
                agents[player_id].select_action(observation, legal_actions), legal_actions
            )
            result = game.step(action_id)
        except Exception:
            return None, "sample_game_progress_failure"
        if result.get("game_over") is True:
            return found, None
    return None, "sample_game_step_limit"


def _selected_layers(
    samples_by_seed: dict[int, dict[str, ReplayableQualitySample]],
) -> dict[str, list[tuple[int, ReplayableQualitySample]]]:
    selected: dict[str, list[tuple[int, ReplayableQualitySample]]] = {}
    used_seeds: set[int] = set()
    for layer in _LAYER_ORDER:
        rows = [
            (seed, samples_by_seed[seed][layer])
            for seed in sorted(samples_by_seed)
            if seed not in used_seeds and layer in samples_by_seed[seed]
        ][:2]
        selected[layer] = rows
        used_seeds.update(seed for seed, _sample in rows)
    return selected


def _ordered_samples(
    selected: dict[str, list[tuple[int, ReplayableQualitySample]]],
) -> tuple[ReplayableQualitySample, ...]:
    names = {
        _OPENING_LAYER: ("opening_1", "opening_2"),
        _MIDGAME_LAYER: ("midgame_1", "midgame_2"),
        _ENDGAME_LAYER: ("endgame_1", "endgame_2"),
    }
    return tuple(
        replace(sample, name=names[layer][index], source_seed=seed)
        for layer in _LAYER_ORDER
        for index, (seed, sample) in enumerate(selected.get(layer, ()))
    )


def build_h3_a9_quality_samples(*, advisor: RAGAdvisor | None = None) -> SampleSetResult:
    """Freeze two opening, two midgame, then two endgame states from seeds 920–959.

    Each seed is replayed once with the frozen RuleBased agents.  A layer's
    first eligible state is captured in step order; layers are selected in
    opening/midgame/endgame order, with already-used seeds excluded.
    """
    try:
        rag_advisor = advisor or _h3_advisor()
        h3_a8_samples = build_replayable_quality_samples(advisor=rag_advisor)
    except Exception:
        return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, ())
    if not h3_a8_samples.ready:
        return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, ())

    forbidden_signatures = {
        _public_signature(sample.observation, sample.legal_actions)
        for sample in h3_a8_samples.samples
    }
    samples_by_seed: dict[int, dict[str, ReplayableQualitySample]] = {}
    for seed in H3_A9_SEEDS:
        try:
            found, failure = _first_eligible_states_for_seed(
                seed,
                rag_advisor,
                forbidden_signatures | {
                    _public_signature(sample.observation, sample.legal_actions)
                    for states in samples_by_seed.values()
                    for sample in states.values()
                },
            )
        except Exception:
            return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, _ordered_samples(_selected_layers(samples_by_seed)))
        if failure is not None or found is None:
            return SampleSetResult(SampleSetStage.MODEL_PATH_INVALID, _ordered_samples(_selected_layers(samples_by_seed)))
        samples_by_seed[seed] = found
        selected = _selected_layers(samples_by_seed)
        if all(len(selected[layer]) == 2 for layer in _LAYER_ORDER):
            break

    selected = _selected_layers(samples_by_seed)
    partial = _ordered_samples(selected)
    if len(selected[_OPENING_LAYER]) != 2:
        return SampleSetResult(SampleSetStage.OPENING_FIXTURE_INVALID, partial)
    if len(selected[_MIDGAME_LAYER]) != 2:
        return SampleSetResult(SampleSetStage.MIDGAME_SAMPLE_MISSING, partial)
    if len(selected[_ENDGAME_LAYER]) != 2:
        return SampleSetResult(SampleSetStage.ENDGAME_SAMPLE_MISSING, partial)
    if len(partial) != H3_A9_SAMPLE_COUNT:
        return SampleSetResult(SampleSetStage.DUPLICATE_STATE, partial)

    signatures = [_public_signature(sample.observation, sample.legal_actions) for sample in partial]
    seeds = [sample.source_seed for sample in partial]
    if len(set(signatures)) != H3_A9_SAMPLE_COUNT or len(set(seeds)) != H3_A9_SAMPLE_COUNT:
        return SampleSetResult(SampleSetStage.DUPLICATE_STATE, partial)
    if any(signature in forbidden_signatures for signature in signatures):
        return SampleSetResult(SampleSetStage.DUPLICATE_STATE, partial)
    return SampleSetResult(SampleSetStage.READY, partial)
