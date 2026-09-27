"""Same-public-state comparison of the frozen baseline and current M1 path.

This is an evaluation-only harness.  Its worker can be loaded from a separate
Git worktree while importing that worktree's ``agents`` and ``engine`` modules;
only compact, low-sensitivity summaries cross the subprocess boundary.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


BASELINE_REF = "9/26_v0"
MAX_EXTERNAL_REQUESTS = 8
MAX_RETRIES = 0
DECISION_BUDGET_SECONDS = 119.0
INITIAL_SCAN_LIMIT = 10_000
WILDCARD_RELATION_SEEDS = tuple(range(5000, 5200))
H3_A9_MIDGAME_1 = (922, 8)
_CANDIDATE_LINE_RE = re.compile(r"#(\d+)\s+action_id=(\d+)\s+\|")


@dataclass(frozen=True, slots=True)
class M2StateSpec:
    name: str
    seed: int
    step: int
    requested_seed: int
    replacement_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "seed": self.seed,
            "step": self.step,
            "requested_seed": self.requested_seed,
            "replacement_reason": self.replacement_reason,
        }


@dataclass(frozen=True, slots=True)
class VersionQualification:
    state_name: str
    version: str
    stage: str
    state_digest: str | None = None
    state_phase: str | None = None
    canonical_count: int = 0
    final_count: int = 0
    candidate_patterns: tuple[tuple[str, int], ...] = ()
    wildcard_candidate_count: int = 0
    relation_counts: tuple[tuple[str, int], ...] = ()
    visible_relation_counts: tuple[tuple[str, int], ...] = ()
    rendered_relation_line_count: int = 0
    rendered_contrast_count: int = 0
    rag_experience_hits: tuple[tuple[str, str], ...] = ()
    recommendation_ids: tuple[int, ...] = field(default=(), repr=False)
    final_candidate_ids: tuple[int, ...] = field(default=(), repr=False)
    reference_action_id: int | None = field(default=None, repr=False)
    response_action_id: int | None = field(default=None, repr=False)
    client_action_id: int | None = field(default=None, repr=False)
    source: str | None = None
    stream_entries: int = 0
    default_transport_entries: int = 0
    stream_error_category: str | None = None
    default_transport_error_category: str | None = None
    default_transport_completed: bool = False
    transport_calls: int = 0
    external_send_invocations: int = 0
    envelope_bound: bool = False
    recommendation_closed: bool = False
    candidate_closed: bool = False
    prompt_chars: int = 0
    prompt_utf8_bytes: int = 0
    request_utf8_bytes: int = 0
    assembly_ms: float | None = None
    decision_elapsed_ms: float | None = None
    response_headers_ms: float | None = None
    first_sse_line_ms: float | None = None
    terminal_event_ms: float | None = None
    provider_outcome: str = "not_called"
    max_retries: int | None = None
    decision_budget_seconds: float | None = None
    configured_timeout_seconds: float | None = None
    request_controls_fingerprint: str | None = field(default=None, repr=False)

    @property
    def ready(self) -> bool:
        return self.stage == "ready"

    def to_dict(self) -> dict[str, object]:
        """Safe summary; raw candidate IDs, cards, prompt and credentials stay private."""
        return {
            "state_name": self.state_name,
            "version": self.version,
            "stage": self.stage,
            "state_digest": self.state_digest,
            "state_phase": self.state_phase,
            "canonical_count": self.canonical_count,
            "final_count": self.final_count,
            "candidate_patterns": dict(self.candidate_patterns),
            "wildcard_candidate_count": self.wildcard_candidate_count,
            "relation_counts": dict(self.relation_counts),
            "visible_relation_counts": dict(self.visible_relation_counts),
            "rendered_relation_line_count": self.rendered_relation_line_count,
            "rendered_contrast_count": self.rendered_contrast_count,
            "rag_experience_hits": [
                {"entry_id": source_id, "tier": tier}
                for source_id, tier in self.rag_experience_hits
            ],
            "recommendation_count": len(self.recommendation_ids),
            "reference_action_visible": (
                self.reference_action_id in self.final_candidate_ids
                if self.reference_action_id is not None
                else False
            ),
            "source": self.source,
            "stream_entries": self.stream_entries,
            "default_transport_entries": self.default_transport_entries,
            "stream_error_category": self.stream_error_category,
            "default_transport_error_category": self.default_transport_error_category,
            "default_transport_completed": self.default_transport_completed,
            "transport_calls": self.transport_calls,
            "external_send_invocations": self.external_send_invocations,
            "envelope_bound": self.envelope_bound,
            "recommendation_closed": self.recommendation_closed,
            "candidate_closed": self.candidate_closed,
            "prompt_chars": self.prompt_chars,
            "prompt_utf8_bytes": self.prompt_utf8_bytes,
            "request_utf8_bytes": self.request_utf8_bytes,
            "assembly_ms": self.assembly_ms,
            "decision_elapsed_ms": self.decision_elapsed_ms,
            "response_headers_ms": self.response_headers_ms,
            "first_sse_line_ms": self.first_sse_line_ms,
            "terminal_event_ms": self.terminal_event_ms,
            "provider_outcome": self.provider_outcome,
            "response_action_id": self.response_action_id,
            "client_action_id": self.client_action_id,
            "max_retries": self.max_retries,
            "decision_budget_seconds": self.decision_budget_seconds,
            "configured_timeout_seconds": self.configured_timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class M2RolloutComparison:
    selected_action_id: int | None
    reference_action_id: int
    selected_outcome: str | None
    selected_rank_sum: int | None
    selected_steps: int
    reference_outcome: str | None
    reference_rank_sum: int | None
    reference_steps: int
    comparison: str
    reference_visible: bool
    selected_pattern: str | None = None
    selected_carrier_count: int | None = None
    selected_uses_wildcard: bool | None = None
    selected_fragments_structure: bool | None = None
    selected_consumes_control: bool | None = None
    selected_residual_singletons: int | None = None
    selected_estimated_remaining_groups: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_action_id": self.selected_action_id,
            "reference_action_id": self.reference_action_id,
            "selected_outcome": self.selected_outcome,
            "selected_team_rank_sum": self.selected_rank_sum,
            "selected_continuation_steps": self.selected_steps,
            "reference_outcome": self.reference_outcome,
            "reference_team_rank_sum": self.reference_rank_sum,
            "reference_continuation_steps": self.reference_steps,
            "comparison": self.comparison,
            "reference_visible": self.reference_visible,
            "selected_pattern": self.selected_pattern,
            "selected_carrier_count": self.selected_carrier_count,
            "selected_uses_wildcard": self.selected_uses_wildcard,
            "selected_fragments_structure": self.selected_fragments_structure,
            "selected_consumes_control": self.selected_consumes_control,
            "selected_residual_singletons": self.selected_residual_singletons,
            "selected_estimated_remaining_groups": self.selected_estimated_remaining_groups,
        }


@dataclass(frozen=True, slots=True)
class M2PairedResult:
    state_name: str
    seed: int
    step: int
    state_digest: str
    baseline: VersionQualification
    current: VersionQualification
    same_action: bool | None
    baseline_rollout: M2RolloutComparison | None
    current_rollout: M2RolloutComparison | None

    def to_dict(self) -> dict[str, object]:
        return {
            "state_name": self.state_name,
            "seed": self.seed,
            "step": self.step,
            "state_digest": self.state_digest,
            "baseline": self.baseline.to_dict(),
            "current": self.current.to_dict(),
            "same_action": self.same_action,
            "baseline_rollout": self.baseline_rollout.to_dict() if self.baseline_rollout else None,
            "current_rollout": self.current_rollout.to_dict() if self.current_rollout else None,
        }


def _safe_profile_fields(profile: Mapping[str, object]) -> dict[str, object]:
    allowed = (
        "hand_evaluation_enabled",
        "opening_formula_enabled",
        "card_tracking_enabled",
        "deepseek_timeout",
    )
    result = {key: profile.get(key) for key in allowed}
    if (
        type(result["hand_evaluation_enabled"]) is not bool
        or type(result["opening_formula_enabled"]) is not bool
        or type(result["card_tracking_enabled"]) is not bool
        or type(result["deepseek_timeout"]) not in (int, float)
        or float(result["deepseek_timeout"]) <= 0
    ):
        raise ValueError("runtime_profile_invalid")
    return result


def _canonical_json_digest(observation: object, legal_actions: object) -> str | None:
    try:
        payload = json.dumps(
            [observation, legal_actions],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


def _install_default_transport_entry_counter(
    deepseek_client_module: object,
    capture: dict[str, object],
) -> Any:
    """Wrap, but do not replace, the production default transport behavior."""
    original = getattr(deepseek_client_module, "_default_transport")

    def measured_default_transport(
        request: object,
        timeout_value: float,
        *,
        decision_deadline: object = None,
    ) -> object:
        capture["default_transport_entries"] = int(capture["default_transport_entries"]) + 1

        def measured_lines() -> Any:
            try:
                for line in original(
                    request,
                    timeout_value,
                    decision_deadline=decision_deadline,
                ):
                    if isinstance(line, bytes) and line.strip() == b"data: [DONE]":
                        capture["default_transport_completed"] = True
                    yield line
                capture["default_transport_completed"] = True
            except GeneratorExit:
                raise
            except BaseException as exc:
                capture["default_transport_error_category"] = _fixed_exception_category(exc)
                raise

        return measured_lines()

    setattr(deepseek_client_module, "_default_transport", measured_default_transport)
    return original


def _fixed_exception_category(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, OSError):
        return "os_error"
    if isinstance(exc, TypeError):
        return "type_error"
    if isinstance(exc, ValueError):
        return "value_error"
    if isinstance(exc, RuntimeError):
        return "runtime_error"
    return "other"


def _make_measured_urlopen(
    *,
    original_urlopen: Any,
    parse_request: Any,
    capture: dict[str, object],
    timing: dict[str, object],
    response_wrapper: Any,
) -> Any:
    """Instrument urllib's keyword ``timeout`` call without changing its request."""
    def measured_urlopen(request: object, timeout: float) -> object:
        timing["urlopen_start_ns"] = time.perf_counter_ns()
        capture["transport_calls"] = int(capture["transport_calls"]) + 1
        envelope, _prompt, ids, request_bytes = parse_request(request)
        capture["request_utf8_bytes"] = request_bytes
        capture["request_candidate_ids"] = ids or ()
        capture["request_envelope_valid"] = envelope is not None
        capture["request_candidate_count"] = len(ids) if ids is not None else 0
        prompt_candidate_ids = capture["prompt_candidate_ids"]
        expected = prompt_candidate_ids if isinstance(prompt_candidate_ids, tuple) else ()
        capture["prompt_candidate_count"] = len(expected)
        capture["request_controls_fingerprint"] = _request_controls_fingerprint(envelope)
        capture["body_bound"] = bool(
            envelope is not None
            and ids is not None
            and capture["request_controls_fingerprint"] is not None
            and len(ids) == len(expected)
            and set(ids) == set(expected)
        )
        if not capture["body_bound"]:
            raise OSError("m2_request_body_binding_invalid")
        capture["external_send_invocations"] = int(capture["external_send_invocations"]) + 1
        # urllib.request.urlopen is called with this keyword by the production
        # default transport; keep the same call shape in the measurement shim.
        response = original_urlopen(request, timeout=timeout)
        timing["response_headers_ms"] = round(
            (time.perf_counter_ns() - int(timing["urlopen_start_ns"])) / 1_000_000,
            3,
        )
        return response_wrapper(response)

    return measured_urlopen


def _request_controls_fingerprint(envelope: object) -> str | None:
    """Hash only non-secret model generation controls, never the request body."""
    if not isinstance(envelope, Mapping):
        return None
    controls = {key: envelope.get(key) for key in ("model", "temperature", "stream")}
    if (
        not isinstance(controls["model"], str)
        or not controls["model"]
        or type(controls["temperature"]) not in (int, float)
        or controls["temperature"] != 0
        or controls["stream"] is not True
    ):
        return None
    encoded = json.dumps(controls, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _make_game(seed: int, step: int) -> tuple[object | None, dict[str, object] | None, list[dict[str, object]] | None]:
    """Rebuild a state through public game operations and deterministic rule play."""
    try:
        from agents.base import require_legal_action_id
        from agents.rule_based_ai import RuleBasedAIAgent
        from engine.game import GuanDanGame

        if type(seed) is not int or seed < 0 or type(step) is not int or not 0 <= step <= 5000:
            return None, None, None
        game = GuanDanGame(seed=seed, current_level_rank="2")
        game.reset()
        agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        for _ in range(step):
            observation = game.observe()
            legal_actions = game.legal_actions()
            player_info = observation.get("my_info")
            player = player_info.get("player_id") if isinstance(player_info, Mapping) else None
            if type(player) is not int or player not in agents:
                return None, None, None
            action_id = require_legal_action_id(agents[player].select_action(observation, legal_actions), legal_actions)
            if game.step(action_id).get("game_over") is True:
                return None, None, None
        observation = game.observe()
        legal_actions = game.legal_actions()
        if observation.get("my_info", {}).get("player_id") != 1:
            return None, None, None
        return game, observation, legal_actions
    except Exception:
        return None, None, None


def _formula_action_id(observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int | None:
    try:
        from agents.game_phase import classify_game_phase
        from agents.hand_evaluator import evaluate_hand
        from agents.opening_strategy import OpeningFormulaStrategy

        return OpeningFormulaStrategy().select_action(
            observation,
            legal_actions,
            evaluate_hand(observation, legal_actions),
            classify_game_phase(observation),
        )
    except Exception:
        return -1  # Invalid formula input is distinct from an ordinary model path.


def _initial_scan(seeds: list[int], profile: Mapping[str, object], *, require_pair_wildcard: bool) -> dict[str, object]:
    try:
        from agents.action_structure import summarize_candidate_contrasts

        _safe_profile_fields(profile)
        rows: list[dict[str, object]] = []
        for seed in seeds:
            _game, observation, actions = _make_game(seed, 0)
            if observation is None or actions is None:
                return {"stage": "state_rebuild_failed", "eligible_seeds": []}
            if not isinstance(observation.get("current_round"), Mapping):
                return {"stage": "public_state_invalid", "eligible_seeds": []}
            if observation["current_round"].get("constraint") != "free":  # type: ignore[index]
                continue
            formula_id = (
                _formula_action_id(observation, actions)
                if profile.get("opening_formula_enabled") is True
                else None
            )
            if formula_id == -1:
                return {"stage": "opening_formula_invalid", "eligible_seeds": []}
            contrasts = summarize_candidate_contrasts(observation, actions)
            if contrasts is None:
                return {"stage": "canonical_relationships_invalid", "eligible_seeds": []}
            kinds = {item.kind for item in contrasts}
            pair_ok = "natural_pair_single" in kinds
            wildcard_ok = "wildcard_resource" in kinds
            model_path = formula_id is None
            rows.append(
                {
                    "seed": seed,
                    "state_digest": _canonical_json_digest(observation, actions),
                    "model_path": model_path,
                    "local_formula": formula_id is not None,
                    "pair_single": pair_ok,
                    "wildcard_resource": wildcard_ok,
                    "qualifies": model_path and (not require_pair_wildcard or (pair_ok and wildcard_ok)),
                }
            )
        return {"stage": "ready", "eligible_seeds": rows}
    except Exception:
        return {"stage": "scan_failed", "eligible_seeds": []}


def _parse_prompt_candidate_ids(prompt: object) -> tuple[int, ...] | None:
    if not isinstance(prompt, str):
        return None
    start = prompt.find("【候选动作】")
    end = prompt.find("【规则库依据】", start)
    if start < 0 or end <= start:
        return None
    matches = tuple(_CANDIDATE_LINE_RE.findall(prompt[start:end]))
    if not matches or any(label != action_id for label, action_id in matches):
        return None
    result = tuple(int(action_id) for _label, action_id in matches)
    return result if len(result) == len(set(result)) else None


def _prompt_relation_lines(prompt: str) -> tuple[int, str]:
    start = prompt.find("【公开关系对照】")
    if start < 0:
        return 0, ""
    start = prompt.find("\n", start)
    if start < 0:
        return 0, ""
    tail = prompt[start + 1 :]
    end = tail.find("\n【")
    section = tail if end < 0 else tail[:end]
    relation_lines = [line for line in section.splitlines() if "action_id=" in line]
    return len(relation_lines), "\n".join(relation_lines)


def _rag_hit_summary(rag_context: object, repo_root: Path) -> tuple[tuple[str, str], ...] | None:
    if not isinstance(rag_context, Mapping):
        return None
    hits = rag_context.get("experience_hits")
    if not isinstance(hits, (list, tuple)):
        return None
    registry_path = repo_root / "rag" / "experience_provenance.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        records = registry.get("records") if isinstance(registry, Mapping) else None
        if not isinstance(records, list):
            return None
        tiers = {
            item.get("entry_id"): item.get("source_tier")
            for item in records
            if isinstance(item, Mapping)
            and isinstance(item.get("entry_id"), str)
            and isinstance(item.get("source_tier"), str)
            and item.get("evidence_status") == "active"
        }
        rows: list[tuple[str, str]] = []
        for hit in hits:
            source_id = (
                hit.get("source_id") if isinstance(hit, Mapping)
                else getattr(hit, "source_id", None)
            )
            if not isinstance(source_id, str) or source_id not in tiers:
                return None
            rows.append((source_id, str(tiers[source_id])))
        return tuple(rows)
    except Exception:
        return None


def _worker(payload: Mapping[str, object]) -> dict[str, object]:
    """Version-local worker.  It emits no card text, prompt, credentials or exception text."""
    try:
        operation = payload.get("operation")
        profile_raw = payload.get("profile")
        if not isinstance(profile_raw, Mapping):
            return {"stage": "runtime_profile_invalid"}
        profile = _safe_profile_fields(profile_raw)
        if operation == "scan":
            seeds = payload.get("seeds")
            if not isinstance(seeds, list) or any(type(seed) is not int for seed in seeds):
                return {"stage": "scan_input_invalid"}
            return _initial_scan(seeds, profile, require_pair_wildcard=payload.get("require_pair_wildcard") is True)
        if operation != "probe":
            return {"stage": "operation_invalid"}
        seed = payload.get("seed")
        step = payload.get("step")
        state_name = payload.get("state_name")
        mode = payload.get("mode")
        if type(seed) is not int or type(step) is not int or not isinstance(state_name, str):
            return {"stage": "sample_spec_invalid"}
        if mode not in {"fake", "real"}:
            return {"stage": "mode_invalid"}
        game, observation, legal_actions = _make_game(seed, step)
        if game is None or observation is None or legal_actions is None:
            return {"stage": "state_rebuild_failed"}
        digest = _canonical_json_digest(observation, legal_actions)
        if digest is None:
            return {"stage": "public_state_invalid"}

        from agents.action_structure import summarize_candidate_contrasts, summarize_candidate_structures
        from agents.base import require_legal_action_id
        from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
        from agents.game_phase import classify_game_phase
        from agents.rule_based_ai import RuleBasedAIAgent
        from integrations.botzone.agent_runtime import build_agent_factory
        from unittest.mock import patch

        contrasts = summarize_candidate_contrasts(observation, legal_actions)
        facts = summarize_candidate_structures(observation, legal_actions)
        if contrasts is None or facts is None or len(facts) != len(legal_actions):
            return {"stage": "canonical_relationships_invalid", "state_digest": digest}
        relation_counts = Counter(item.kind for item in contrasts)
        full_ids = {action.get("action_id") for action in legal_actions}
        if any(type(action_id) is not int for action_id in full_ids) or len(full_ids) != len(legal_actions):
            return {"stage": "canonical_ids_invalid", "state_digest": digest}
        reference_id = require_legal_action_id(
            RuleBasedAIAgent(player_id=1).select_action(observation, legal_actions), legal_actions
        )

        settings_raw = payload.get("client_settings")
        if mode == "real":
            if not isinstance(settings_raw, Mapping):
                return {"stage": "client_settings_invalid", "state_digest": digest}
            api_key = settings_raw.get("api_key")
            base_url = settings_raw.get("base_url")
            model = settings_raw.get("model")
            timeout = settings_raw.get("timeout_seconds")
            retries = settings_raw.get("max_retries")
            if (
                not isinstance(api_key, str) or not api_key
                or not isinstance(base_url, str) or not base_url
                or not isinstance(model, str) or not model
                or type(timeout) not in (int, float) or float(timeout) <= 0
                or type(retries) is not int or retries != 0
            ):
                return {"stage": "client_settings_invalid", "state_digest": digest}
            offline = False
        else:
            api_key = "offline-m2-placeholder"
            base_url = "https://offline.invalid"
            model = "offline-m2"
            timeout = float(profile["deepseek_timeout"])
            retries = 0
            offline = True
        app_config = type("M2AppConfig", (), {})()
        app_config.deepseek_api_key = api_key
        app_config.deepseek_base_url = base_url
        app_config.deepseek_model = model
        app_config.deepseek_enabled = True
        app_config.hand_evaluation_enabled = profile["hand_evaluation_enabled"]
        app_config.card_tracking_enabled = profile["card_tracking_enabled"]
        app_config.opening_formula_enabled = profile["opening_formula_enabled"]
        app_config.deepseek_timeout = float(timeout)
        app_config.deepseek_max_retries = 0
        app_config.debug = False

        capture: dict[str, object] = {
            "selected_id": payload.get("selected_action_id"),
            "stream_entries": 0,
            "default_transport_entries": 0,
            "stream_error_category": None,
            "default_transport_error_category": None,
            "default_transport_completed": False,
            "transport_calls": 0,
            "external_send_invocations": 0,
            "body_bound": False,
            "prompt_candidate_ids": (),
            "request_candidate_ids": (),
            "request_envelope_valid": False,
            "request_controls_fingerprint": None,
            "request_candidate_count": 0,
            "prompt_candidate_count": 0,
            "prompt_chars": 0,
            "prompt_utf8_bytes": 0,
            "request_utf8_bytes": 0,
            "agent_start_ns": 0,
            "assembly_ms": None,
            "request_open_ns": None,
            "response_headers_ms": None,
            "first_sse_line_ms": None,
            "terminal_event_ms": None,
            "relation_line_count": 0,
            "relation_lines": "",
            "rag_hits": None,
            "recommendation_ids": (),
            "candidate_actions": (),
            "response_action_id": None,
            "client_action_id": None,
            "provider_outcome": "not_called",
            "sse_line_bytes": 0,
        }

        def parse_request(request: object) -> tuple[dict[str, object] | None, str | None, tuple[int, ...] | None, int]:
            raw = getattr(request, "data", None)
            if not isinstance(raw, bytes):
                return None, None, None, 0
            try:
                envelope = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None, None, None, len(raw)
            messages = envelope.get("messages") if isinstance(envelope, dict) else None
            users = [item for item in messages if isinstance(item, dict) and item.get("role") == "user"] if isinstance(messages, list) else []
            prompt = users[0].get("content") if len(users) == 1 else None
            ids = _parse_prompt_candidate_ids(prompt)
            if (
                not isinstance(envelope, dict)
                or envelope.get("stream") is not True
                or envelope.get("temperature") != 0
                or envelope.get("model") != model
                or len(users) != 1
                or not isinstance(prompt, str)
                or ids is None
            ):
                return None, prompt if isinstance(prompt, str) else None, None, len(raw)
            return envelope, prompt, ids, len(raw)

        def fake_transport(request: object, _timeout: float) -> str:
            capture["transport_calls"] = int(capture["transport_calls"]) + 1
            envelope, prompt, ids, request_bytes = parse_request(request)
            capture["request_utf8_bytes"] = request_bytes
            capture["request_candidate_ids"] = ids or ()
            expected = capture["prompt_candidate_ids"]
            capture["request_envelope_valid"] = envelope is not None
            capture["request_candidate_count"] = len(ids) if ids is not None else 0
            capture["prompt_candidate_count"] = len(expected) if isinstance(expected, tuple) else 0
            capture["request_controls_fingerprint"] = _request_controls_fingerprint(envelope)
            capture["body_bound"] = bool(
                envelope is not None
                and ids is not None
                and capture["request_controls_fingerprint"] is not None
                and isinstance(expected, tuple)
                and len(ids) == len(expected)
                and set(ids) == set(expected)
            )
            if not capture["body_bound"] or not ids:
                raise OSError("m2_fake_request_invalid")
            forced_outcome = payload.get("fake_outcome")
            if forced_outcome == "timeout":
                capture["provider_outcome"] = "timeout"
                raise TimeoutError("m2_fake_timeout")
            if forced_outcome == "exception":
                capture["provider_outcome"] = "exception"
                raise OSError("m2_fake_exception")
            selected = capture["selected_id"]
            if selected is None:
                selected = ids[0]
            if type(selected) is not int:
                capture["provider_outcome"] = "invalid_suggestion"
                raise OSError("m2_fake_action_type_invalid")
            capture["provider_outcome"] = "success"
            capture["response_action_id"] = selected
            content = json.dumps({"action_id": selected}, separators=(",", ":"))
            chunk = json.dumps({"choices": [{"delta": {"content": content}}]}, separators=(",", ":"))
            return f"data: {chunk}\n\ndata: [DONE]\n"

        class M2CaptureClient(DeepSeekClient):
            def __init__(self, **kwargs: object) -> None:
                transport = fake_transport if offline else None
                super().__init__(**kwargs, transport=transport)  # type: ignore[arg-type]
                if self._max_retries != 0:
                    raise ValueError("m2_retry_configuration_invalid")
                original_builder = self._build_structured_prompt

                def capture_builder(**kwargs: object) -> str:
                    prompt_value = original_builder(**kwargs)  # type: ignore[arg-type]
                    capture["prompt_chars"] = len(prompt_value)
                    capture["prompt_utf8_bytes"] = len(prompt_value.encode("utf-8"))
                    capture["relation_line_count"], capture["relation_lines"] = _prompt_relation_lines(prompt_value)
                    prompt_actions = kwargs.get("legal_actions")
                    capture["candidate_actions"] = tuple(prompt_actions) if isinstance(prompt_actions, list) else ()
                    capture["prompt_candidate_ids"] = tuple(
                        action.get("action_id") for action in capture["candidate_actions"]
                        if isinstance(action, Mapping) and type(action.get("action_id")) is int
                    )
                    rag_context = kwargs.get("rag_context")
                    capture["rag_hits"] = _rag_hit_summary(rag_context, Path.cwd())
                    recommendation = kwargs.get("strategy_recommendation")
                    raw_ids = getattr(recommendation, "action_ids", ())
                    capture["recommendation_ids"] = tuple(raw_ids) if isinstance(raw_ids, tuple) else ()
                    return prompt_value

                self._build_structured_prompt = capture_builder  # type: ignore[method-assign]

            def _stream_sse(self, req: object, timeout_value: float, **kwargs: object) -> tuple[str, str]:
                capture["stream_entries"] = int(capture["stream_entries"]) + 1
                capture["transport_start_ns"] = time.perf_counter_ns()
                if capture["agent_start_ns"]:
                    capture["assembly_ms"] = round(
                        (int(capture["transport_start_ns"]) - int(capture["agent_start_ns"])) / 1_000_000,
                        3,
                    )
                try:
                    content, reasoning = super()._stream_sse(req, timeout_value, **kwargs)  # type: ignore[arg-type]
                except BaseException as exc:
                    capture["stream_error_category"] = _fixed_exception_category(exc)
                    raise
                try:
                    payload = self._extract_json(content)
                    capture["response_action_id"] = self._extract_action_id(payload)
                    capture["provider_outcome"] = "success" if type(capture["response_action_id"]) is int else "invalid_suggestion"
                except Exception:
                    capture["provider_outcome"] = "invalid_suggestion"
                return content, reasoning

            def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
                rag_context = kwargs.get("rag_context")
                if capture["rag_hits"] is None:
                    capture["rag_hits"] = _rag_hit_summary(rag_context, Path.cwd())
                suggestion = super().suggest_action_id(**kwargs)
                capture["client_action_id"] = (
                    suggestion.action_id if isinstance(suggestion, DeepSeekSuggestion) else None
                )
                return suggestion  # type: ignore[return-value]

        client_holder: dict[str, object] = {}

        # Keep the real default transport path intact while marking its entry.
        # This makes a failure before urlopen distinguishable from an HTTP
        # attempt, without recording request data or exception text.
        original_default_transport = None
        if not offline:
            import agents.deepseek_client as deepseek_client_module
            original_default_transport = _install_default_transport_entry_counter(
                deepseek_client_module,
                capture,
            )

        def client_factory(**kwargs: object) -> M2CaptureClient:
            client = M2CaptureClient(**kwargs)
            client_holder["client"] = client
            return client

        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=app_config):
            factory = build_agent_factory(
                "deepseek",
                config_loader=lambda: app_config,
                client_factory=client_factory,
            )
            agent = factory(1)
            strict_client = getattr(agent, "client", None)
            deadline_setter = getattr(strict_client, "set_decision_deadline", None)
            if not callable(deadline_setter):
                return {"stage": "deadline_interface_invalid", "state_digest": digest}
            decision_started = time.monotonic()
            capture["agent_start_ns"] = time.perf_counter_ns()
            deadline_setter(time.monotonic() + DECISION_BUDGET_SECONDS)

            timing = {
                "urlopen_start_ns": None,
                "response_headers_ms": None,
                "first_sse_line_ms": None,
                "terminal_event_ms": None,
            }
            original_urlopen = None
            response_context = None
            if not offline:
                from agents.deepseek_client import urllib_request
                original_urlopen = urllib_request.urlopen

                class MeasuredResponse:
                    def __init__(self, response: object) -> None:
                        self._response = response

                    def __enter__(self) -> object:
                        entered = self._response.__enter__()  # type: ignore[attr-defined]
                        return self if entered is self._response else entered

                    def __exit__(self, *exc_info: object) -> object:
                        return self._response.__exit__(*exc_info)  # type: ignore[attr-defined]

                    def __getattr__(self, name: str) -> object:
                        return getattr(self._response, name)

                    def readline(self, *args: object, **kwargs: object) -> bytes:
                        line = self._response.readline(*args, **kwargs)  # type: ignore[attr-defined]
                        now = time.perf_counter_ns()
                        if timing["urlopen_start_ns"] is not None and timing["first_sse_line_ms"] is None and line:
                            timing["first_sse_line_ms"] = round((now - int(timing["urlopen_start_ns"])) / 1_000_000, 3)
                        if line.strip() == b"data: [DONE]" and timing["urlopen_start_ns"] is not None:
                            timing["terminal_event_ms"] = round((now - int(timing["urlopen_start_ns"])) / 1_000_000, 3)
                        return line

                urllib_request.urlopen = _make_measured_urlopen(
                    original_urlopen=original_urlopen,
                    parse_request=parse_request,
                    capture=capture,
                    timing=timing,
                    response_wrapper=MeasuredResponse,
                )  # type: ignore[assignment]
            try:
                chosen = agent.select_action(observation, legal_actions)
            finally:
                if original_urlopen is not None:
                    from agents.deepseek_client import urllib_request
                    urllib_request.urlopen = original_urlopen  # type: ignore[assignment]
                if original_default_transport is not None:
                    import agents.deepseek_client as deepseek_client_module
                    deepseek_client_module._default_transport = original_default_transport  # type: ignore[assignment]
            decision_elapsed_ms = round((time.monotonic() - decision_started) * 1000, 3)

        client = client_holder.get("client")
        if not isinstance(client, M2CaptureClient):
            return {"stage": "client_composition_invalid", "state_digest": digest}
        final_actions = capture["candidate_actions"]
        candidate_ids = capture["prompt_candidate_ids"]
        if not isinstance(final_actions, tuple) or not isinstance(candidate_ids, tuple):
            return {"stage": "candidate_capture_invalid", "state_digest": digest}
        candidate_ids = tuple(candidate_ids)
        action_signatures = tuple(DeepSeekClient._action_signature(item) for item in final_actions)
        final_set = set(candidate_ids)
        candidate_closed = (
            bool(candidate_ids)
            and len(candidate_ids) <= 80
            and len(candidate_ids) == len(final_set)
            and len(action_signatures) == len(set(action_signatures))
            and final_set.issubset(full_ids)
            and len(tuple(capture["request_candidate_ids"])) == len(candidate_ids)
            and set(capture["request_candidate_ids"]) == set(candidate_ids)
        )
        recommendation_ids = capture["recommendation_ids"]
        if not isinstance(recommendation_ids, tuple):
            recommendation_ids = ()
        recommendation_closed = all(
            type(action_id) is int and action_id in final_set
            for action_id in recommendation_ids
        )
        rag_hits = capture["rag_hits"]
        if rag_hits is None:
            return {"stage": "rag_provenance_unavailable", "state_digest": digest}
        action_by_id = {action["action_id"]: action for action in legal_actions}
        pattern_counts = Counter(str(action_by_id[action_id].get("declared_pattern")) for action_id in candidate_ids)
        wildcard_candidate_count = sum(
            1 for action_id in candidate_ids
            if int(action_by_id[action_id].get("wildcard_count", 0) or 0) > 0
        )
        visible_counts: Counter[str] = Counter()
        for contrast in contrasts:
            if all(action_id in final_set for action_id in contrast.action_ids):
                visible_counts[contrast.kind] += 1
        relation_line_count = int(capture["relation_line_count"])
        relation_lines = str(capture["relation_lines"])
        rendered_contrasts = 0
        for contrast in contrasts:
            left, right = (f"action_id={action_id}" for action_id in contrast.action_ids)
            if left in relation_lines and right in relation_lines:
                rendered_contrasts += 1
        raw_response_id = capture["response_action_id"]
        client_action_id = capture["client_action_id"]
        transport_calls = int(capture["transport_calls"])
        stream_entries = int(capture["stream_entries"])
        default_transport_entries = int(capture["default_transport_entries"])
        envelope_bound = bool(capture["body_bound"])
        provider_outcome = str(capture["provider_outcome"])
        client_outcome = getattr(strict_client, "last_outcome", None)
        if client_outcome in {"success", "timeout", "exception", "invalid_suggestion"}:
            provider_outcome = str(client_outcome)
        if not offline:
            capture["response_headers_ms"] = timing["response_headers_ms"]
            capture["first_sse_line_ms"] = timing["first_sse_line_ms"]
            capture["terminal_event_ms"] = timing["terminal_event_ms"]
            capture["decision_elapsed_ms"] = decision_elapsed_ms
        source = getattr(agent, "last_decision_source", None)
        selected_id = (
            chosen
            if type(chosen) is int and source == "model" and provider_outcome == "success"
            else None
        )
        stage = "ready"
        if not offline and stream_entries != 1:
            stage = "stream_entry_count_invalid"
        elif not offline and default_transport_entries != 1:
            stage = "default_transport_entry_count_invalid"
        elif transport_calls != 1:
            stage = "transport_call_count_invalid"
        elif not envelope_bound:
            stage = "request_body_binding_invalid"
        elif provider_outcome == "timeout":
            stage = "model_provider_timeout"
        elif provider_outcome == "exception":
            stage = "model_provider_exception"
        elif provider_outcome == "invalid_suggestion":
            stage = "model_suggestion_invalid"
        elif not candidate_closed:
            stage = "candidate_closure_invalid"
        elif not recommendation_closed:
            stage = "recommendation_closure_invalid"
        elif source != "model" or provider_outcome != "success":
            stage = "model_result_not_preserved"
        elif type(raw_response_id) is not int or raw_response_id not in final_set:
            stage = "response_not_final_candidate"
        elif type(client_action_id) is not int or client_action_id != raw_response_id:
            stage = "client_id_drift"
        elif selected_id != raw_response_id:
            stage = "agent_id_drift"

        result = {
            "stage": stage,
            "state_digest": digest,
            "state_phase": classify_game_phase(observation).phase,
            "canonical_count": len(legal_actions),
            "final_count": len(candidate_ids),
            "candidate_patterns": dict(sorted(pattern_counts.items())),
            "wildcard_candidate_count": wildcard_candidate_count,
            "relation_counts": dict(sorted(relation_counts.items())),
            "visible_relation_counts": dict(sorted(visible_counts.items())),
            "rendered_relation_line_count": relation_line_count,
            "rendered_contrast_count": rendered_contrasts,
            "rag_experience_hits": [list(row) for row in rag_hits],
            "recommendation_ids": list(recommendation_ids),
            "final_candidate_ids": list(candidate_ids),
            "reference_action_id": reference_id,
            "response_action_id": raw_response_id,
            "client_action_id": client_action_id,
            "selected_action_id": selected_id,
            "source": source if isinstance(source, str) else None,
            "stream_entries": int(capture["stream_entries"]),
            "default_transport_entries": int(capture["default_transport_entries"]),
            "stream_error_category": capture["stream_error_category"],
            "default_transport_error_category": capture["default_transport_error_category"],
            "default_transport_completed": capture["default_transport_completed"],
            "transport_calls": transport_calls,
            "external_send_invocations": int(capture["external_send_invocations"]),
            "envelope_bound": envelope_bound,
            "request_envelope_valid": capture["request_envelope_valid"],
            "request_candidate_count": capture["request_candidate_count"],
            "prompt_candidate_count": capture["prompt_candidate_count"],
            "recommendation_closed": recommendation_closed,
            "candidate_closed": candidate_closed,
            "prompt_chars": int(capture["prompt_chars"]),
            "prompt_utf8_bytes": int(capture["prompt_utf8_bytes"]),
            "request_utf8_bytes": int(capture["request_utf8_bytes"]),
            "assembly_ms": capture["assembly_ms"],
            "prompt_build_ms": capture.get("prompt_build_ms"),
            "response_headers_ms": capture["response_headers_ms"],
            "first_sse_line_ms": capture["first_sse_line_ms"],
            "terminal_event_ms": capture["terminal_event_ms"],
            "decision_elapsed_ms": capture.get("decision_elapsed_ms"),
            "provider_outcome": provider_outcome,
            "max_retries": getattr(client, "_max_retries", None),
            "decision_budget_seconds": DECISION_BUDGET_SECONDS,
            "configured_timeout_seconds": getattr(client, "_timeout_seconds", None),
            "request_controls_fingerprint": capture["request_controls_fingerprint"],
        }
        return result
    except Exception:
        return {"stage": "worker_failure"}


def _worker_entry(source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Run a worker against a repo's own imports without changing its worktree."""
    bootstrap = (
        "import importlib.util,json,sys;"
        f"p={str(source_path)!r};"
        "s=importlib.util.spec_from_file_location('_m2_eval_worker',p);"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
        "x=json.load(sys.stdin);"
        "print(json.dumps(m._worker(x),ensure_ascii=False,separators=(',',':'),sort_keys=True))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", bootstrap],
            cwd=Path.cwd(),
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=DECISION_BUDGET_SECONDS + 45,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1"},
        )
        if result.returncode != 0:
            return {"stage": "worker_process_failed"}
        parsed = json.loads(result.stdout)
        return parsed if isinstance(parsed, dict) else {"stage": "worker_output_invalid"}
    except subprocess.TimeoutExpired:
        return {"stage": "worker_process_timeout"}
    except Exception:
        return {"stage": "worker_process_failure"}


def run_in_repo(repo_root: Path, source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Execute a version-local request pipeline and return only its safe summary."""
    repo = repo_root.resolve()
    if not repo.is_dir() or not (repo / "agents").is_dir():
        return {"stage": "repo_root_invalid"}
    # _worker_entry uses the active cwd; do not change it in-process. A shell
    # caller should use the subprocess form below when testing another worktree.
    if repo != Path.cwd().resolve():
        bootstrap = (
            "import importlib.util,json,sys;"
            f"p={str(source_path.resolve())!r};"
            "s=importlib.util.spec_from_file_location('_m2_eval_worker',p);"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
            "x=json.load(sys.stdin);"
            "print(json.dumps(m._worker(x),ensure_ascii=False,separators=(',',':'),sort_keys=True))"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", bootstrap],
                cwd=repo,
                input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=DECISION_BUDGET_SECONDS + 45,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1"},
            )
            if result.returncode != 0:
                return {"stage": "worker_process_failed"}
            parsed = json.loads(result.stdout)
            return parsed if isinstance(parsed, dict) else {"stage": "worker_output_invalid"}
        except subprocess.TimeoutExpired:
            return {"stage": "worker_process_timeout"}
        except Exception:
            return {"stage": "worker_process_failure"}
    return _worker_entry(source_path.resolve(), payload)


def scan_version_initial_states(
    repo_root: Path,
    source_path: Path,
    seeds: tuple[int, ...],
    profile: Mapping[str, object],
    *,
    require_pair_wildcard: bool = False,
) -> tuple[dict[str, object], ...] | None:
    result = run_in_repo(
        repo_root,
        source_path,
        {
            "operation": "scan",
            "seeds": list(seeds),
            "profile": _safe_profile_fields(profile),
            "require_pair_wildcard": require_pair_wildcard,
        },
    )
    rows = result.get("eligible_seeds")
    if result.get("stage") != "ready" or not isinstance(rows, list):
        return None
    return tuple(row for row in rows if isinstance(row, dict))


def profile_from_app_config(config: object, *, offline: bool) -> dict[str, object]:
    """Extract non-secret path settings; credentials are added only for real calls."""
    values = {
        "hand_evaluation_enabled": getattr(config, "hand_evaluation_enabled", None),
        "opening_formula_enabled": getattr(config, "opening_formula_enabled", None),
        "card_tracking_enabled": getattr(config, "card_tracking_enabled", None),
        "deepseek_timeout": getattr(config, "deepseek_timeout", None),
    }
    profile = _safe_profile_fields(values)
    if offline:
        return profile
    api_key = getattr(config, "deepseek_api_key", None)
    base_url = getattr(config, "deepseek_base_url", None)
    model = getattr(config, "deepseek_model", None)
    if not all(isinstance(value, str) and value for value in (api_key, base_url, model)):
        raise ValueError("external_model_configuration_unavailable")
    return {
        **profile,
        "client_settings": {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "timeout_seconds": float(getattr(config, "deepseek_timeout")),
            "max_retries": MAX_RETRIES,
        },
    }


def build_state_specs(
    baseline_rows: Mapping[str, tuple[dict[str, object], ...]],
    *,
    midgame_state: tuple[int, int] = H3_A9_MIDGAME_1,
) -> tuple[M2StateSpec, ...] | None:
    """Choose earliest common model-path starts in the registered search order."""
    if set(baseline_rows) != {"baseline", "current"}:
        return None
    indexes = {
        version: {int(row["seed"]): row for row in rows if type(row.get("seed")) is int}
        for version, rows in baseline_rows.items()
    }
    chosen: list[M2StateSpec] = []
    starts = (("opening_seed_0", 0), ("opening_seed_29", 29))
    for name, requested in starts:
        match = next(
            (
                seed for seed in range(requested, requested + INITIAL_SCAN_LIMIT)
                if seed in indexes["baseline"] and seed in indexes["current"]
                and all(indexes[version][seed].get("model_path") is True for version in ("baseline", "current"))
                and not any(item.seed == seed for item in chosen)
            ),
            None,
        )
        if match is None:
            return None
        cause = []
        for version in ("baseline", "current"):
            row = indexes[version].get(requested)
            if row is not None and row.get("model_path") is not True:
                cause.append(f"{version}_opening_formula")
        chosen.append(
            M2StateSpec(
                name,
                match,
                0,
                requested,
                "requested_seed_model_path_both_versions"
                if match == requested
                else "advanced_due_" + ("_and_".join(cause) if cause else "local_path_not_model_in_one_or_both_versions"),
            )
        )
    pair_rows = {
        version: {int(row["seed"]): row for row in rows if type(row.get("seed")) is int}
        for version, rows in baseline_rows.items()
    }
    target_seed = next(
        (
            seed for seed in WILDCARD_RELATION_SEEDS
            if seed in pair_rows["baseline"] and seed in pair_rows["current"]
            and pair_rows["baseline"][seed].get("model_path") is True
            and pair_rows["current"][seed].get("model_path") is True
            and pair_rows["baseline"][seed].get("pair_single") is True
            and pair_rows["current"][seed].get("pair_single") is True
            and pair_rows["baseline"][seed].get("wildcard_resource") is True
            and pair_rows["current"][seed].get("wildcard_resource") is True
        ),
        None,
    )
    if target_seed is None or any(item.seed == target_seed for item in chosen):
        return None
    chosen.append(M2StateSpec("pair_single_wildcard", target_seed, 0, 5000, "first_common_relation_model_state"))
    midgame_seed, midgame_step = midgame_state
    if midgame_seed in {item.seed for item in chosen}:
        return None
    chosen.append(M2StateSpec("h3_a9_midgame_1", midgame_seed, midgame_step, midgame_seed, "frozen_h3_a9_production_state"))
    return tuple(chosen)


def discover_m2_state_specs(
    baseline_root: Path,
    current_root: Path,
    source_path: Path,
    profile: Mapping[str, object],
    *,
    midgame_state: tuple[int, int] = H3_A9_MIDGAME_1,
) -> tuple[tuple[M2StateSpec, ...] | None, str]:
    """Resolve the registered four states using both versions' public pipeline gates."""
    public_profile = _safe_profile_fields(profile)
    rows: dict[str, dict[int, dict[str, object]]] = {"baseline": {}, "current": {}}
    roots = {"baseline": baseline_root, "current": current_root}
    used: set[int] = set()
    selected: list[M2StateSpec] = []

    def add_scan(seed_values: tuple[int, ...], *, needs_pair: bool = False) -> bool:
        for version in ("baseline", "current"):
            result = scan_version_initial_states(
                roots[version], source_path, seed_values, public_profile,
                require_pair_wildcard=needs_pair,
            )
            if result is None:
                return False
            for row in result:
                seed_value = row.get("seed")
                if type(seed_value) is int:
                    rows[version][seed_value] = row
        return True

    for name, requested in (("opening_seed_0", 0), ("opening_seed_29", 29)):
        cursor = requested
        match: int | None = None
        while cursor < requested + INITIAL_SCAN_LIMIT and match is None:
            batch_end = min(cursor + 64, requested + INITIAL_SCAN_LIMIT)
            if not add_scan(tuple(range(cursor, batch_end))):
                return None, "initial_state_scan_failed"
            common = sorted(
                seed for seed in rows["baseline"].keys() & rows["current"].keys()
                if seed >= requested
                and seed not in used
                and rows["baseline"][seed].get("model_path") is True
                and rows["current"][seed].get("model_path") is True
            )
            if common:
                match = common[0]
            cursor = batch_end
        if match is None:
            return None, "common_opening_model_state_missing"
        cause: list[str] = []
        if match != requested:
            for version in ("baseline", "current"):
                original = rows[version].get(requested)
                if original is not None and original.get("model_path") is not True:
                    cause.append(f"{version}_opening_formula")
            reason = "advanced_due_" + ("_and_".join(cause) if cause else "model_path_not_reached_in_one_or_both_versions")
        else:
            reason = "requested_seed_model_path_both_versions"
        selected.append(M2StateSpec(name, match, 0, requested, reason))
        used.add(match)

    if not add_scan(WILDCARD_RELATION_SEEDS, needs_pair=True):
        return None, "wildcard_pair_relation_scan_failed"
    common_relation_seeds = sorted(
        seed for seed in rows["baseline"].keys() & rows["current"].keys()
        if seed in WILDCARD_RELATION_SEEDS
        and seed not in used
        and all(rows[version][seed].get(key) is True for version in ("baseline", "current") for key in (
            "model_path", "pair_single", "wildcard_resource",
        ))
    )
    if not common_relation_seeds:
        return None, "common_pair_wildcard_state_missing"
    pair_seed = common_relation_seeds[0]
    selected.append(M2StateSpec("pair_single_wildcard", pair_seed, 0, 5000, "first_common_pair_wildcard_model_state"))
    midgame_seed, midgame_step = midgame_state
    if midgame_seed in used or any(item.seed == midgame_seed for item in selected):
        return None, "frozen_midgame_state_duplicate"
    selected.append(M2StateSpec("h3_a9_midgame_1", midgame_seed, midgame_step, midgame_seed, "frozen_h3_a9_production_state"))
    return tuple(selected), "ready"


def _worker_profile(profile: Mapping[str, object], *, real: bool) -> dict[str, object]:
    result = _safe_profile_fields(profile)
    if real:
        settings = profile.get("client_settings")
        if not isinstance(settings, Mapping):
            raise ValueError("client_settings_missing")
        result["client_settings"] = dict(settings)
    return result


def probe_version_state(
    repo_root: Path,
    source_path: Path,
    spec: M2StateSpec,
    profile: Mapping[str, object],
    *,
    real: bool = False,
    selected_action_id: int | None = None,
    fake_outcome: str | None = None,
) -> dict[str, object]:
    worker_profile = _worker_profile(profile, real=real)
    payload: dict[str, object] = {
        "operation": "probe",
        "state_name": spec.name,
        "seed": spec.seed,
        "step": spec.step,
        "mode": "real" if real else "fake",
        "profile": _safe_profile_fields(profile),
        "selected_action_id": selected_action_id,
        "fake_outcome": fake_outcome,
    }
    if real:
        payload["client_settings"] = worker_profile.get("client_settings")
    return run_in_repo(repo_root, source_path, payload)


def _replay_current_state(seed: int, step: int) -> tuple[object, dict[str, object], list[dict[str, object]]]:
    game, observation, legal = _make_game(seed, step)
    if game is None or observation is None or legal is None:
        raise ValueError("state_replay_failed")
    return game, observation, legal


def compare_with_frozen_rule_rollout(
    spec: M2StateSpec,
    selected_action_id: int | None,
    final_candidate_ids: tuple[int, ...],
    *,
    reference_action_id: int | None = None,
    expected_state_digest: str | None = None,
) -> M2RolloutComparison | None:
    """Compare the returned model action to one frozen RuleBased continuation.

    The labels are a local RuleBased continuation proxy only, not a win-rate
    estimate.  Both branches use independent clones and current public engine
    operations.  No result is inferred for failed model responses.
    """
    if type(selected_action_id) is not int:
        return None
    try:
        from copy import deepcopy
        from agents.base import require_legal_action_id
        from agents.rule_based_ai import RuleBasedAIAgent
        from evaluation.strategy_intent_action_quality import _compare_quality, _rollout

        game, observation, legal = _replay_current_state(spec.seed, spec.step)
        rebuilt_digest = _canonical_json_digest(observation, legal)
        if rebuilt_digest is None or (
            expected_state_digest is not None and rebuilt_digest != expected_state_digest
        ):
            return None
        final_ids = tuple(final_candidate_ids)
        canonical_ids = {item.get("action_id") for item in legal}
        if (
            not final_ids
            or len(final_ids) != len(set(final_ids))
            or selected_action_id not in final_ids
            or not set(final_ids).issubset(canonical_ids)
        ):
            return None
        canonical_reference = require_legal_action_id(
            RuleBasedAIAgent(player_id=1).select_action(observation, legal), legal
        )
        reference = canonical_reference if reference_action_id is None else reference_action_id
        if reference != canonical_reference:
            return None
        require_legal_action_id(reference, legal)
        selected_clone = deepcopy(game)
        if selected_clone is game or selected_clone.observe() != observation or selected_clone.legal_actions() != legal:
            return None
        if selected_action_id == reference:
            selected_outcome = _rollout(selected_clone, selected_action_id, 1, 5000)
            reference_outcome = selected_outcome
        else:
            reference_clone = deepcopy(game)
            if reference_clone is game or reference_clone.observe() != observation or reference_clone.legal_actions() != legal:
                return None
            selected_outcome = _rollout(selected_clone, selected_action_id, 1, 5000)
            reference_outcome = _rollout(reference_clone, reference, 1, 5000)
        if not selected_outcome.complete or not reference_outcome.complete:
            label = "unevaluable"
        elif selected_action_id == reference:
            label = "tie"
        else:
            label = {
                "on_better": "selected_better",
                "off_better": "reference_better",
                "tie": "tie",
            }[_compare_quality(reference_outcome, selected_outcome)]
        from agents.action_structure import summarize_candidate_structures
        selected_fact = next(
            (
                fact for fact in summarize_candidate_structures(observation, legal) or ()
                if fact.action_id == selected_action_id
            ),
            None,
        )
        if selected_fact is None:
            return None
        return M2RolloutComparison(
            selected_action_id,
            reference,
            selected_outcome.team_outcome if selected_outcome.complete else None,
            selected_outcome.team_placement_sum if selected_outcome.complete else None,
            selected_outcome.rollout_step_count,
            reference_outcome.team_outcome if reference_outcome.complete else None,
            reference_outcome.team_placement_sum if reference_outcome.complete else None,
            reference_outcome.rollout_step_count,
            label,
            reference in final_candidate_ids,
            selected_fact.pattern,
            selected_fact.carrier_count,
            selected_fact.uses_wildcard,
            selected_fact.fragments_played_rank_group,
            selected_fact.consumes_control_resource,
            selected_fact.residual_singleton_rank_count,
            selected_fact.estimated_remaining_rank_groups,
        )
    except Exception:
        return None


def qualification_from_worker(state_name: str, version: str, result: Mapping[str, object]) -> VersionQualification:
    """Convert a version-local summary to a typed in-memory report row."""
    def pairs(name: str) -> tuple[tuple[str, int], ...]:
        raw = result.get(name)
        if not isinstance(raw, Mapping):
            return ()
        return tuple(sorted((str(key), int(value)) for key, value in raw.items() if type(value) is int))

    raw_hits = result.get("rag_experience_hits")
    hits: tuple[tuple[str, str], ...] = ()
    if isinstance(raw_hits, list):
        hits = tuple((str(row[0]), str(row[1])) for row in raw_hits if isinstance(row, list) and len(row) == 2)
    ints = lambda name: tuple(int(item) for item in result.get(name, []) if type(item) is int) if isinstance(result.get(name), list) else ()
    optional_int = lambda name: result.get(name) if type(result.get(name)) is int else None
    optional_float = lambda name: float(result[name]) if type(result.get(name)) in (int, float) else None
    return VersionQualification(
        state_name=state_name,
        version=version,
        stage=str(result.get("stage", "worker_result_invalid")),
        state_digest=result.get("state_digest") if isinstance(result.get("state_digest"), str) else None,
        state_phase=result.get("state_phase") if isinstance(result.get("state_phase"), str) else None,
        canonical_count=int(result.get("canonical_count", 0)) if type(result.get("canonical_count")) is int else 0,
        final_count=int(result.get("final_count", 0)) if type(result.get("final_count")) is int else 0,
        candidate_patterns=pairs("candidate_patterns"),
        wildcard_candidate_count=int(result.get("wildcard_candidate_count", 0)) if type(result.get("wildcard_candidate_count")) is int else 0,
        relation_counts=pairs("relation_counts"),
        visible_relation_counts=pairs("visible_relation_counts"),
        rendered_relation_line_count=int(result.get("rendered_relation_line_count", 0)) if type(result.get("rendered_relation_line_count")) is int else 0,
        rendered_contrast_count=int(result.get("rendered_contrast_count", 0)) if type(result.get("rendered_contrast_count")) is int else 0,
        rag_experience_hits=hits,
        recommendation_ids=ints("recommendation_ids"),
        final_candidate_ids=ints("final_candidate_ids"),
        reference_action_id=optional_int("reference_action_id"),
        response_action_id=optional_int("response_action_id"),
        client_action_id=optional_int("client_action_id"),
        source=result.get("source") if isinstance(result.get("source"), str) else None,
        stream_entries=int(result.get("stream_entries", 0)) if type(result.get("stream_entries")) is int else 0,
        default_transport_entries=(
            int(result.get("default_transport_entries", 0))
            if type(result.get("default_transport_entries")) is int
            else 0
        ),
        stream_error_category=(
            result.get("stream_error_category") if isinstance(result.get("stream_error_category"), str) else None
        ),
        default_transport_error_category=(
            result.get("default_transport_error_category")
            if isinstance(result.get("default_transport_error_category"), str)
            else None
        ),
        default_transport_completed=result.get("default_transport_completed") is True,
        transport_calls=int(result.get("transport_calls", 0)) if type(result.get("transport_calls")) is int else 0,
        external_send_invocations=(
            int(result.get("external_send_invocations", 0))
            if type(result.get("external_send_invocations")) is int
            else 0
        ),
        envelope_bound=result.get("envelope_bound") is True,
        recommendation_closed=result.get("recommendation_closed") is True,
        candidate_closed=result.get("candidate_closed") is True,
        prompt_chars=int(result.get("prompt_chars", 0)) if type(result.get("prompt_chars")) is int else 0,
        prompt_utf8_bytes=int(result.get("prompt_utf8_bytes", 0)) if type(result.get("prompt_utf8_bytes")) is int else 0,
        request_utf8_bytes=int(result.get("request_utf8_bytes", 0)) if type(result.get("request_utf8_bytes")) is int else 0,
        assembly_ms=optional_float("assembly_ms"),
        decision_elapsed_ms=optional_float("decision_elapsed_ms"),
        response_headers_ms=optional_float("response_headers_ms"),
        first_sse_line_ms=optional_float("first_sse_line_ms"),
        terminal_event_ms=optional_float("terminal_event_ms"),
        provider_outcome=str(result.get("provider_outcome", "not_called")),
        max_retries=result.get("max_retries") if type(result.get("max_retries")) is int else None,
        decision_budget_seconds=(
            float(result["decision_budget_seconds"])
            if type(result.get("decision_budget_seconds")) in (int, float)
            else None
        ),
        configured_timeout_seconds=(
            float(result["configured_timeout_seconds"])
            if type(result.get("configured_timeout_seconds")) in (int, float)
            else None
        ),
        request_controls_fingerprint=(
            result.get("request_controls_fingerprint")
            if isinstance(result.get("request_controls_fingerprint"), str)
            else None
        ),
    )


@dataclass(frozen=True, slots=True)
class M2RequestAttempt:
    sequence: int
    state_name: str
    version: str
    result: VersionQualification

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "state_name": self.state_name,
            "version": self.version,
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class M2RequestRun:
    stage: str
    attempts: tuple[M2RequestAttempt, ...]

    @property
    def external_request_count(self) -> int:
        """Number of actual calls handed to urllib after request binding passed."""
        return sum(attempt.result.external_send_invocations for attempt in self.attempts)

    @property
    def client_invocation_count(self) -> int:
        """Budget-consuming model client invocations, including pre-send failures."""
        return len(self.attempts)

    @property
    def observed_transport_invocations(self) -> int:
        return sum(attempt.result.transport_calls for attempt in self.attempts)

    @property
    def uncertain_transport_attempts(self) -> int:
        return sum(
            attempt.result.stage in {"worker_process_timeout", "worker_process_failed", "worker_process_failure", "worker_failure"}
            for attempt in self.attempts
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "external_request_count": self.external_request_count,
            "client_invocation_count": self.client_invocation_count,
            "observed_transport_invocations": self.observed_transport_invocations,
            "uncertain_transport_attempts": self.uncertain_transport_attempts,
            "retry_count": 0,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


def validate_offline_qualifications(
    specs: tuple[M2StateSpec, ...],
    qualifications: tuple[VersionQualification, ...],
) -> str:
    """Fail closed unless all four paired, actual-client offline gates agree."""
    expected_names = ("opening_seed_0", "opening_seed_29", "pair_single_wildcard", "h3_a9_midgame_1")
    if tuple(spec.name for spec in specs) != expected_names or len(qualifications) != 8:
        return "offline_qualification_count_invalid"
    if (
        specs[0].requested_seed != 0
        or specs[0].step != 0
        or specs[0].seed < 0
        or specs[1].requested_seed != 29
        or specs[1].step != 0
        or specs[1].seed < 29
        or specs[2].requested_seed != 5000
        or specs[2].step != 0
        or specs[2].seed not in WILDCARD_RELATION_SEEDS
        or (specs[3].seed, specs[3].step) != H3_A9_MIDGAME_1
    ):
        return "frozen_state_spec_invalid"
    index = {(row.state_name, row.version): row for row in qualifications}
    if len(index) != len(qualifications):
        return "offline_qualification_duplicate"
    for spec in specs:
        pair = [index.get((spec.name, version)) for version in ("baseline", "current")]
        if any(row is None for row in pair):
            return "offline_qualification_missing"
        baseline, current = pair
        assert baseline is not None and current is not None
        for row in (baseline, current):
            if not row.ready:
                return "offline_production_request_not_ready"
            if (
                row.max_retries != MAX_RETRIES
                or row.transport_calls != 1
                or row.external_send_invocations != 0
                or not row.envelope_bound
                or not row.candidate_closed
                or not row.recommendation_closed
                or row.source != "model"
                or row.provider_outcome != "success"
                or row.final_count < 1
                or row.final_count > 80
                or len(row.final_candidate_ids) != row.final_count
                or row.response_action_id != row.client_action_id
                or row.response_action_id not in row.final_candidate_ids
            ):
                return "offline_candidate_or_model_contract_invalid"
            if (
                row.configured_timeout_seconds is None
                or row.configured_timeout_seconds <= 0
                or row.decision_budget_seconds != DECISION_BUDGET_SECONDS
                or row.request_controls_fingerprint is None
            ):
                return "offline_request_settings_invalid"
            expected_phase = "midgame" if spec.name == "h3_a9_midgame_1" else "opening"
            if row.state_phase != expected_phase:
                return "public_phase_mismatch"
        if (
            baseline.state_digest is None
            or baseline.state_digest != current.state_digest
            or baseline.canonical_count != current.canonical_count
            or baseline.reference_action_id is None
            or baseline.reference_action_id != current.reference_action_id
            or baseline.request_controls_fingerprint != current.request_controls_fingerprint
            or baseline.configured_timeout_seconds != current.configured_timeout_seconds
            or baseline.decision_budget_seconds != current.decision_budget_seconds
        ):
            return "paired_public_state_or_reference_mismatch"
    return "ready"


def qualify_fixed_states(
    specs: tuple[M2StateSpec, ...],
    roots: Mapping[str, Path],
    source_path: Path,
    profile: Mapping[str, object],
) -> tuple[str, tuple[VersionQualification, ...]]:
    """Run all eight no-network production-factory probes before any live call."""
    if set(roots) != {"baseline", "current"}:
        return "version_roots_invalid", ()
    rows: list[VersionQualification] = []
    for spec in specs:
        for version in ("baseline", "current"):
            raw = probe_version_state(roots[version], source_path, spec, profile)
            rows.append(qualification_from_worker(spec.name, version, raw))
    qualifications = tuple(rows)
    return validate_offline_qualifications(specs, qualifications), qualifications


_INTEGRITY_FAILURE_STAGES = frozenset(
    {
        "client_settings_invalid",
        "runtime_profile_invalid",
        "sample_spec_invalid",
        "mode_invalid",
        "state_rebuild_failed",
        "public_state_invalid",
        "canonical_relationships_invalid",
        "canonical_ids_invalid",
        "deadline_interface_invalid",
        "candidate_capture_invalid",
        "rag_provenance_unavailable",
        "worker_process_timeout",
        "worker_process_failed",
        "worker_process_failure",
        "worker_output_invalid",
        "worker_failure",
        "transport_call_count_invalid",
        "request_body_binding_invalid",
        "candidate_closure_invalid",
        "recommendation_closure_invalid",
        "model_result_not_preserved",
        "response_not_final_candidate",
        "client_id_drift",
        "agent_id_drift",
        "client_composition_invalid",
        "stream_entry_count_invalid",
        "default_transport_entry_count_invalid",
    }
)


def run_bounded_real_requests(
    specs: tuple[M2StateSpec, ...],
    qualifications: tuple[VersionQualification, ...],
    request_once: Any,
) -> M2RequestRun:
    """Run the fixed interleaved pair order, one production invocation per cell."""
    gate = validate_offline_qualifications(specs, qualifications)
    if gate != "ready":
        return M2RequestRun(f"offline_gate_{gate}", ())
    attempts: list[M2RequestAttempt] = []
    for spec in specs:
        for version in ("baseline", "current"):
            if len(attempts) >= MAX_EXTERNAL_REQUESTS:
                return M2RequestRun("request_budget_exhausted", tuple(attempts))
            try:
                raw = request_once(version, spec)
                if not isinstance(raw, Mapping):
                    raw = {"stage": "worker_output_invalid"}
            except Exception:
                raw = {"stage": "worker_failure"}
            qualification = qualification_from_worker(spec.name, version, raw)
            attempts.append(M2RequestAttempt(len(attempts) + 1, spec.name, version, qualification))
            if qualification.stage in _INTEGRITY_FAILURE_STAGES:
                return M2RequestRun("integrity_failure_stopped", tuple(attempts))
    return M2RequestRun("complete", tuple(attempts))


def _entrypoint() -> int:
    """Private subprocess entry; standard output is one sanitized JSON object."""
    try:
        payload = json.load(sys.stdin)
        result = _worker(payload) if isinstance(payload, Mapping) else {"stage": "worker_input_invalid"}
    except Exception:
        result = {"stage": "worker_failure"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
