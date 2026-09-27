"""Offline qualification and authorization-gated schedule for expanded M2.

This module does not read credentials or send network requests during import,
state discovery, or offline qualification.  Its real-request runner requires a
per-call explicit owner-authorization flag and a complete sixteen-cell offline
qualification.  The 32 slots are one fixed assessment, never split into
smaller batches.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


BASELINE_VERSION = "baseline"
CURRENT_VERSION = "current"
VERSION_ORDER = (BASELINE_VERSION, CURRENT_VERSION)
BASELINE_REF = "9/26_v0"
SEALED_BASELINE_COMMIT = "c5a8bb9848ee75518987a4c377885fcd7fa58562"
CURRENT_PRODUCTION_COMMIT = "89106691243cb38cd1cb08b7f870f9d2185dccc3"
MAX_EXTERNAL_REQUESTS = 32
MAX_RETRIES = 0
REPETITIONS_PER_VERSION = 2
MAX_SCAN_STEPS = 5000
OPENING_DENSE_RANGE = (150000, 150799)
OPENING_DIVERSE_RANGE = (151000, 151799)
MIDGAME_RANGE = (160000, 160799)
ENDGAME_RANGE = (170000, 170799)
_OPENING_BATCH_SIZE = 64
_CONTINUATION_BATCH_SIZE = 8
_PHASES = frozenset({"opening", "midgame", "endgame", "near_open_endgame", "critical_endgame"})
_ENDGAME_PHASES = frozenset({"endgame", "near_open_endgame", "critical_endgame"})
_PRESSURE_RESOURCE_RELATIONS = frozenset(
    {
        "bomb_residual",
        "bomb_strength_resource",
        "danger_block_choice",
        "danger_block_resource",
        "single_control_resource",
        "straight_flush_bomb_fragment",
        "teammate_control_resource",
        "wildcard_resource",
    }
)
_TEAM_DANGER_PREFIXES = ("teammate_", "danger_block_")
_EXPECTED_NAMES = (
    "opening_dense_1",
    "opening_dense_2",
    "opening_diverse_1",
    "opening_diverse_2",
    "midgame_pressure_resource",
    "midgame_team_danger",
    "endgame_1",
    "endgame_2",
)
_EXPECTED_SELECTIONS = (
    "opening_dense",
    "opening_dense",
    "opening_diverse",
    "opening_diverse",
    "midgame_pressure_resource",
    "midgame_team_danger",
    "endgame",
    "endgame",
)
_SELECTIONS = frozenset(
    {
        "opening_dense",
        "opening_diverse",
        "midgame_pressure_resource",
        "midgame_team_danger",
        "endgame",
    }
)


@dataclass(frozen=True, slots=True)
class ExpandedM2StateSpec:
    name: str
    seed: int
    step: int
    requested_seed: int
    state_digest: str
    phase: str
    selection: str
    selection_reason: str
    canonical_count: int
    nonpass_count: int
    raw_pattern_counts: tuple[tuple[str, int], ...]
    relation_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "seed": self.seed,
            "step": self.step,
            "requested_seed": self.requested_seed,
            "state_digest": self.state_digest,
            "phase": self.phase,
            "selection": self.selection,
            "selection_reason": self.selection_reason,
            "canonical_count": self.canonical_count,
            "nonpass_count": self.nonpass_count,
            "raw_pattern_counts": dict(self.raw_pattern_counts),
            "relation_counts": dict(self.relation_counts),
        }

    def as_m2_spec(self) -> object:
        from evaluation.m2_same_state_model_eval import M2StateSpec

        return M2StateSpec(
            self.name,
            self.seed,
            self.step,
            self.requested_seed,
            self.selection_reason,
        )


@dataclass(frozen=True, slots=True)
class ExpandedDiscoveryResult:
    stage: str
    specs: tuple[ExpandedM2StateSpec, ...] = ()
    scanned_seed_counts: tuple[tuple[str, int], ...] = ()

    @property
    def ready(self) -> bool:
        return self.stage == "ready" and len(self.specs) == len(_EXPECTED_NAMES)

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "state_count": len(self.specs),
            "specs": [item.to_dict() for item in self.specs],
            "scanned_seed_counts": dict(self.scanned_seed_counts),
        }


@dataclass(frozen=True, slots=True)
class ExpandedQualificationResult:
    stage: str
    rows: tuple[object, ...]

    @property
    def ready(self) -> bool:
        return self.stage == "ready" and len(self.rows) == 16

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "row_count": len(self.rows),
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass(frozen=True, slots=True)
class ExpandedRequestSlot:
    sequence: int
    state_name: str
    version: str
    repeat: int

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "state_name": self.state_name,
            "version": self.version,
            "repeat": self.repeat,
        }


@dataclass(frozen=True, slots=True)
class ExpandedRequestAttempt:
    slot: ExpandedRequestSlot
    result: object
    send_status: str
    rollout: object | None = None
    rollout_status: str = "not_run"

    def to_dict(self) -> dict[str, object]:
        return {
            **self.slot.to_dict(),
            "send_status": self.send_status,
            "result": self.result.to_dict(),
            "rollout_status": self.rollout_status,
            "rollout": self.rollout.to_dict() if self.rollout is not None else None,
        }


@dataclass(frozen=True, slots=True)
class ExpandedRequestRun:
    stage: str
    attempts: tuple[ExpandedRequestAttempt, ...] = ()

    @property
    def client_invocation_count(self) -> int:
        return len(self.attempts)

    @property
    def external_request_count(self) -> int:
        return sum(
            int(getattr(attempt.result, "external_send_invocations", 0) or 0)
            for attempt in self.attempts
        )

    @property
    def retry_count(self) -> int:
        return 0

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "client_invocation_count": self.client_invocation_count,
            "external_request_count": self.external_request_count,
            "retry_count": self.retry_count,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


def _canonical_digest(observation: object, actions: object) -> str | None:
    try:
        encoded = json.dumps(
            [observation, actions],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _safe_scan_profile(profile: Mapping[str, object]) -> dict[str, object] | None:
    bool_fields = ("hand_evaluation_enabled", "opening_formula_enabled", "card_tracking_enabled")
    timeout = profile.get("deepseek_timeout")
    if (
        any(type(profile.get(key)) is not bool for key in bool_fields)
        or type(timeout) not in (int, float)
        or not math.isfinite(float(timeout))
        or float(timeout) <= 0
    ):
        return None
    # This scan profile contains no credentials or endpoints.
    return {key: profile[key] for key in (*bool_fields, "deepseek_timeout")}


def _validate_public_actions(actions: object) -> bool:
    if not isinstance(actions, list) or not actions:
        return False
    ids: list[int] = []
    for action in actions:
        if not isinstance(action, Mapping):
            return False
        action_id = action.get("action_id")
        if type(action_id) is not int or not isinstance(action.get("declared_pattern"), str):
            return False
        if not isinstance(action.get("declared_cards"), list) or not isinstance(action.get("carrier_cards"), list):
            return False
        if (
            any(not isinstance(card, str) for card in action["declared_cards"])
            or any(not isinstance(card, str) for card in action["carrier_cards"])
            or not isinstance(action.get("wildcard_info"), list)
            or not isinstance(action.get("display_text"), str)
            or any(
                not isinstance(info, Mapping)
                or not isinstance(info.get("carrier_card"), str)
                or not isinstance(info.get("declared_as"), str)
                for info in action["wildcard_info"]
            )
        ):
            return False
        if type(action.get("wildcard_count")) is not int or action["wildcard_count"] < 0:
            return False
        ids.append(action_id)
    return len(ids) == len(set(ids))


def _opening_formula_result(observation: dict[str, object], actions: list[dict[str, object]]) -> tuple[str, int | None]:
    try:
        from agents.game_phase import classify_game_phase
        from agents.hand_evaluator import evaluate_hand
        from agents.opening_strategy import OpeningFormulaStrategy

        result = OpeningFormulaStrategy().select_action(
            observation,
            actions,
            evaluate_hand(observation, actions),
            classify_game_phase(observation),
        )
    except Exception:
        return "invalid", None
    if result is not None and type(result) is not int:
        return "invalid", None
    return ("local" if result is not None else "model", result)


def _opening_state_summary(seed: int, game: object) -> dict[str, object] | None:
    try:
        from agents.action_structure import summarize_candidate_contrasts
        from agents.game_phase import classify_game_phase

        observation = game.observe()  # type: ignore[attr-defined]
        actions = game.legal_actions()  # type: ignore[attr-defined]
    except Exception:
        return None
    if (
        not isinstance(observation, dict)
        or not _validate_public_actions(actions)
        or observation.get("legal_actions") != actions
    ):
        return None
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    history = observation.get("history")
    other_players = observation.get("other_players")
    if (
        not isinstance(my_info, Mapping)
        or my_info.get("player_id") != 1
        or my_info.get("hand_count") != 27
        or not isinstance(my_info.get("hand_cards"), list)
        or len(my_info["hand_cards"]) != 27
        or not isinstance(current_round, Mapping)
        or current_round.get("current_player_id") != 1
        or current_round.get("current_level_rank") != "2"
        or current_round.get("step_no") != 0
        or current_round.get("constraint") != "free"
        or current_round.get("table_action") is not None
        or not isinstance(history, Mapping)
        or history.get("actions") != []
        or not isinstance(other_players, list)
        or len(other_players) != 3
        or any(not isinstance(item, Mapping) or item.get("hand_count") != 27 for item in other_players)
        or classify_game_phase(observation).phase != "opening"
    ):
        return None
    if sum([my_info["hand_count"], *(item["hand_count"] for item in other_players)]) != 108:
        return None
    formula_status, _formula_id = _opening_formula_result(observation, actions)
    if formula_status == "invalid":
        return None
    contrasts = summarize_candidate_contrasts(observation, actions)
    if contrasts is None:
        return None
    digest = _canonical_digest(observation, actions)
    if digest is None:
        return None
    patterns = Counter(str(action.get("declared_pattern")) for action in actions)
    relations = Counter(str(item.kind) for item in contrasts)
    nonpass_count = sum(action.get("declared_pattern") != "pass" for action in actions)
    return {
        "seed": seed,
        "step": 0,
        "state_digest": digest,
        "phase": "opening",
        "canonical_count": len(actions),
        "nonpass_count": nonpass_count,
        "raw_pattern_counts": dict(sorted(patterns.items())),
        "relation_counts": dict(sorted(relations.items())),
        "relation_kinds": sorted(relations),
        "model_path": formula_status == "model",
    }


def _transition_state_summaries(seed: int, selection: str) -> tuple[str, list[dict[str, object]]]:
    try:
        from agents.base import require_legal_action_id
        from agents.action_structure import summarize_candidate_contrasts
        from agents.game_phase import ENDGAME_PHASES, MIDGAME, classify_game_phase
        from agents.rule_based_ai import RuleBasedAIAgent
        from engine.game import GuanDanGame

        game = GuanDanGame(seed=seed, current_level_rank="2")
        initial = game.reset()
        if not isinstance(initial, dict) or not _validate_initial_distribution(initial):
            return "initial_public_state_invalid", []
        rule_agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        rows: list[dict[str, object]] = []
        for step in range(MAX_SCAN_STEPS):
            observation = game.observe()
            actions = game.legal_actions()
            if (
                not isinstance(observation, dict)
                or not _validate_public_actions(actions)
                or observation.get("legal_actions") != actions
            ):
                return "public_state_invalid", []
            my_info = observation.get("my_info")
            player_id = my_info.get("player_id") if isinstance(my_info, Mapping) else None
            if type(player_id) is not int or player_id not in rule_agents:
                return "current_player_invalid", []
            phase = classify_game_phase(observation).phase
            nonpass_count = sum(action.get("declared_pattern") != "pass" for action in actions)
            phase_match = (
                phase == MIDGAME if selection.startswith("midgame_")
                else phase in ENDGAME_PHASES if selection == "endgame"
                else False
            )
            if player_id == 1 and phase_match and nonpass_count >= 2:
                formula_status, _formula_id = _opening_formula_result(observation, actions)
                if formula_status == "invalid":
                    return "opening_formula_invalid", []
                if formula_status == "model":
                    contrasts = summarize_candidate_contrasts(observation, actions)
                    if contrasts is None:
                        return "canonical_relationships_invalid", []
                    relation_counts = Counter(str(item.kind) for item in contrasts)
                    kinds = set(relation_counts)
                    if selection == "midgame_pressure_resource":
                        qualifies = bool(kinds & _PRESSURE_RESOURCE_RELATIONS)
                    elif selection == "midgame_team_danger":
                        qualifies = any(kind.startswith(_TEAM_DANGER_PREFIXES) for kind in kinds)
                    else:
                        qualifies = selection == "endgame"
                    if qualifies:
                        patterns = Counter(str(action.get("declared_pattern")) for action in actions)
                        digest = _canonical_digest(observation, actions)
                        if digest is None:
                            return "public_state_serialization_invalid", []
                        rows.append(
                            {
                                "seed": seed,
                                "step": step,
                                "state_digest": digest,
                                "phase": phase,
                                "canonical_count": len(actions),
                                "nonpass_count": nonpass_count,
                                "raw_pattern_counts": dict(sorted(patterns.items())),
                                "relation_counts": dict(sorted(relation_counts.items())),
                                "relation_kinds": sorted(kinds),
                                "model_path": True,
                            }
                        )
            try:
                action_id = require_legal_action_id(rule_agents[player_id].select_action(observation, actions), actions)
                result = game.step(action_id)
            except Exception:
                return "rule_rollout_failed", []
            if result.get("game_over") is True:
                return "ready", rows
        return "state_step_limit", []
    except Exception:
        return "scan_failure", []


def _validate_initial_distribution(observation: Mapping[str, object]) -> bool:
    info = observation.get("my_info")
    others = observation.get("other_players")
    current = observation.get("current_round")
    history = observation.get("history")
    return bool(
        isinstance(info, Mapping)
        and info.get("player_id") == 1
        and info.get("hand_count") == 27
        and isinstance(info.get("hand_cards"), list)
        and len(info["hand_cards"]) == 27
        and isinstance(others, list)
        and len(others) == 3
        and all(isinstance(row, Mapping) and row.get("hand_count") == 27 for row in others)
        and isinstance(current, Mapping)
        and current.get("current_level_rank") == "2"
        and current.get("step_no") == 0
        and current.get("current_player_id") == 1
        and current.get("constraint") == "free"
        and current.get("table_action") is None
        and isinstance(history, Mapping)
        and history.get("actions") == []
        and history.get("finish_order") == []
        and sum([info["hand_count"], *(row["hand_count"] for row in others)]) == 108
    )


def _version_scan_worker(payload: Mapping[str, object]) -> dict[str, object]:
    """Process-isolated scanner; only public hashes and count summaries leave it."""
    try:
        selection = payload.get("selection")
        seeds = payload.get("seeds")
        profile_raw = payload.get("profile")
        if (
            selection not in _SELECTIONS
            or not isinstance(seeds, list)
            or not seeds
            or len(seeds) > 64
            or any(type(seed) is not int or seed < 0 for seed in seeds)
            or seeds != sorted(set(seeds))
            or not isinstance(profile_raw, Mapping)
        ):
            return {"stage": "scan_input_invalid", "rows": []}
        profile = _safe_scan_profile(profile_raw)
        if profile is None or profile["opening_formula_enabled"] is not True:
            return {"stage": "runtime_profile_invalid", "rows": []}
        if selection.startswith("opening_"):
            try:
                from engine.game import GuanDanGame
            except Exception:
                return {"stage": "engine_unavailable", "rows": []}
            rows: list[dict[str, object]] = []
            for seed in seeds:
                try:
                    game = GuanDanGame(seed=seed, current_level_rank="2")
                    game.reset()
                except Exception:
                    return {"stage": "seed_initial_deal_invalid", "rows": []}
                row = _opening_state_summary(seed, game)
                if row is None:
                    return {"stage": "opening_public_state_invalid", "rows": []}
                relations = row.get("relation_counts")
                patterns = row.get("raw_pattern_counts")
                if not isinstance(relations, Mapping) or not isinstance(patterns, Mapping):
                    return {"stage": "scan_summary_invalid", "rows": []}
                if selection == "opening_dense":
                    qualifies = (
                        row["canonical_count"] > 80
                        and row["model_path"] is True
                        and int(relations.get("natural_pair_single", 0)) > 0
                        and int(relations.get("wildcard_resource", 0)) > 0
                    )
                else:
                    qualifies = (
                        row["canonical_count"] <= 80
                        and row["model_path"] is True
                        and all(int(patterns.get(kind, 0)) > 0 for kind in ("single", "pair", "triple"))
                    )
                if qualifies:
                    rows.append(row)
            return {"stage": "ready", "rows": rows}

        rows = []
        for seed in seeds:
            stage, seed_rows = _transition_state_summaries(seed, str(selection))
            if stage != "ready":
                return {"stage": stage, "rows": []}
            rows.extend(seed_rows)
        rows.sort(key=lambda row: (int(row["seed"]), int(row["step"]), str(row["state_digest"])))
        return {"stage": "ready", "rows": rows}
    except Exception:
        return {"stage": "scan_failure", "rows": []}


def _scan_subprocess(
    repo_root: Path,
    source_path: Path,
    selection: str,
    seeds: tuple[int, ...],
    profile: Mapping[str, object],
) -> dict[str, object]:
    root = repo_root.resolve()
    source = source_path.resolve()
    if not root.is_dir() or not source.is_file():
        return {"stage": "scan_path_invalid", "rows": []}
    bootstrap = (
        "import importlib.util,json,sys;"
        f"p={str(source)!r};"
        "s=importlib.util.spec_from_file_location('_m2_expanded_scan',p);"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
        "x=json.load(sys.stdin);"
        "print(json.dumps(m._version_scan_worker(x),ensure_ascii=False,separators=(',',':'),sort_keys=True))"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", bootstrap],
            cwd=root,
            input=json.dumps(
                {"selection": selection, "seeds": list(seeds), "profile": dict(profile)},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=300,
            check=False,
            env={**os.environ, "PYTHON_DOTENV_DISABLED": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if completed.returncode != 0:
            return {"stage": "scan_process_failed", "rows": []}
        decoded = json.loads(completed.stdout)
        return decoded if isinstance(decoded, dict) else {"stage": "scan_output_invalid", "rows": []}
    except subprocess.TimeoutExpired:
        return {"stage": "scan_process_timeout", "rows": []}
    except Exception:
        return {"stage": "scan_process_failure", "rows": []}


def _git_output(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root.resolve()), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except Exception:
        return None


def _validate_version_roots(baseline_root: Path, current_root: Path) -> str:
    """Require the sealed tag worktree and a current tree containing M1 start."""
    baseline_head = _git_output(baseline_root, "rev-parse", "HEAD")
    current_head = _git_output(current_root, "rev-parse", "HEAD")
    tag_commit = _git_output(current_root, "rev-parse", f"{BASELINE_REF}^{{commit}}")
    if (
        baseline_head is None
        or baseline_head.returncode != 0
        or current_head is None
        or current_head.returncode != 0
        or tag_commit is None
        or tag_commit.returncode != 0
    ):
        return "version_git_identity_unavailable"
    if (
        baseline_head.stdout.strip() != SEALED_BASELINE_COMMIT
        or tag_commit.stdout.strip() != SEALED_BASELINE_COMMIT
    ):
        return "sealed_baseline_identity_mismatch"
    ancestor = _git_output(
        current_root,
        "merge-base",
        "--is-ancestor",
        CURRENT_PRODUCTION_COMMIT,
        "HEAD",
    )
    if ancestor is None or ancestor.returncode != 0:
        return "current_production_commit_missing"
    return "ready"


def _common_rows(
    baseline_rows: Sequence[Mapping[str, object]],
    current_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    def index(rows: Sequence[Mapping[str, object]]) -> dict[tuple[int, int, str], Mapping[str, object]]:
        result: dict[tuple[int, int, str], Mapping[str, object]] = {}
        for row in rows:
            seed, step, digest = row.get("seed"), row.get("step"), row.get("state_digest")
            if type(seed) is int and type(step) is int and isinstance(digest, str) and digest:
                result[(seed, step, digest)] = row
        return result

    left = index(baseline_rows)
    right = index(current_rows)
    result: list[dict[str, object]] = []
    for key in sorted(left.keys() & right.keys()):
        first, second = left[key], right[key]
        if (
            first.get("model_path") is not True
            or second.get("model_path") is not True
            or first.get("phase") != second.get("phase")
            or first.get("canonical_count") != second.get("canonical_count")
            or first.get("nonpass_count") != second.get("nonpass_count")
        ):
            continue
        result.append(dict(first))
    return tuple(result)


def _matches_selection(row: Mapping[str, object], selection: str) -> bool:
    relations = row.get("relation_counts")
    patterns = row.get("raw_pattern_counts")
    if not isinstance(relations, Mapping) or not isinstance(patterns, Mapping):
        return False
    kinds = {str(key) for key, value in relations.items() if type(value) is int and value > 0}
    if selection == "opening_dense":
        return (
            int(row.get("canonical_count", 0)) > 80
            and int(relations.get("natural_pair_single", 0)) > 0
            and int(relations.get("wildcard_resource", 0)) > 0
        )
    if selection == "opening_diverse":
        return (
            int(row.get("canonical_count", 0)) <= 80
            and all(int(patterns.get(kind, 0)) > 0 for kind in ("single", "pair", "triple"))
        )
    if selection == "midgame_pressure_resource":
        return bool(kinds & _PRESSURE_RESOURCE_RELATIONS)
    if selection == "midgame_team_danger":
        return any(kind.startswith(_TEAM_DANGER_PREFIXES) for kind in kinds)
    if selection == "endgame":
        return row.get("phase") in _ENDGAME_PHASES and int(row.get("nonpass_count", 0)) >= 2
    return False


def _spec_from_row(
    name: str,
    selection: str,
    requested_seed: int,
    reason: str,
    row: Mapping[str, object],
) -> ExpandedM2StateSpec:
    def count_pairs(key: str) -> tuple[tuple[str, int], ...]:
        raw = row.get(key)
        if not isinstance(raw, Mapping):
            return ()
        return tuple(sorted((str(name), int(count)) for name, count in raw.items() if type(count) is int and count >= 0))

    seed, step, digest = row.get("seed"), row.get("step"), row.get("state_digest")
    phase = row.get("phase")
    if (
        type(seed) is not int
        or type(step) is not int
        or not isinstance(digest, str)
        or not digest
        or phase not in _PHASES
        or type(row.get("canonical_count")) is not int
        or type(row.get("nonpass_count")) is not int
    ):
        raise ValueError("expanded_scan_row_invalid")
    return ExpandedM2StateSpec(
        name,
        seed,
        step,
        requested_seed,
        digest,
        str(phase),
        selection,
        reason,
        int(row["canonical_count"]),
        int(row["nonpass_count"]),
        count_pairs("raw_pattern_counts"),
        count_pairs("relation_counts"),
    )


def discover_expanded_state_specs(
    baseline_root: Path,
    current_root: Path,
    source_path: Path,
    profile: Mapping[str, object],
) -> ExpandedDiscoveryResult:
    """Find the earliest common states in the four frozen seed windows."""
    safe_profile = _safe_scan_profile(profile)
    if safe_profile is None:
        return ExpandedDiscoveryResult("runtime_profile_invalid")
    roots_stage = _validate_version_roots(baseline_root, current_root)
    if roots_stage != "ready":
        return ExpandedDiscoveryResult(roots_stage)
    roots = {BASELINE_VERSION: baseline_root, CURRENT_VERSION: current_root}
    scanned: Counter[str] = Counter()
    specs: list[ExpandedM2StateSpec] = []
    used_states: set[tuple[int, int, str]] = set()

    def select_from_range(
        selection: str,
        bounds: tuple[int, int],
        count: int,
        *,
        distinct_seed: bool = True,
        reason: str,
    ) -> tuple[dict[str, object], ...] | None:
        selected: list[dict[str, object]] = []
        selected_keys: set[tuple[int, int, str]] = set()
        selected_seeds: set[int] = set()
        start, end = bounds
        cursor = start
        batch_size = _OPENING_BATCH_SIZE if selection.startswith("opening_") else _CONTINUATION_BATCH_SIZE
        while cursor <= end and len(selected) < count:
            batch = tuple(range(cursor, min(cursor + batch_size, end + 1)))
            version_rows: dict[str, tuple[Mapping[str, object], ...]] = {}
            for version in VERSION_ORDER:
                raw = _scan_subprocess(roots[version], source_path, selection, batch, safe_profile)
                if raw.get("stage") != "ready" or not isinstance(raw.get("rows"), list):
                    return None
                version_rows[version] = tuple(item for item in raw["rows"] if isinstance(item, Mapping))
            scanned[selection] += len(batch)
            common = _common_rows(version_rows[BASELINE_VERSION], version_rows[CURRENT_VERSION])
            for row in sorted(common, key=lambda item: (int(item["seed"]), int(item["step"]))):
                state_key = (int(row["seed"]), int(row["step"]), str(row["state_digest"]))
                if (
                    not _matches_selection(row, selection)
                    or state_key in used_states
                    or state_key in selected_keys
                    or (distinct_seed and int(row["seed"]) in selected_seeds)
                ):
                    continue
                selected.append(dict(row))
                selected_keys.add(state_key)
                selected_seeds.add(int(row["seed"]))
                if len(selected) == count:
                    break
            cursor += len(batch)
        return tuple(selected) if len(selected) == count else None

    groups = (
        ("opening_dense", OPENING_DENSE_RANGE, 2, True, "first_common_dense_opening"),
        ("opening_diverse", OPENING_DIVERSE_RANGE, 2, True, "first_common_diverse_opening"),
    )
    names_by_selection = {
        "opening_dense": ("opening_dense_1", "opening_dense_2"),
        "opening_diverse": ("opening_diverse_1", "opening_diverse_2"),
    }
    for selection, bounds, count, distinct, reason in groups:
        matches = select_from_range(selection, bounds, count, distinct_seed=distinct, reason=reason)
        if matches is None:
            return ExpandedDiscoveryResult(f"{selection}_common_state_missing", tuple(specs), tuple(sorted(scanned.items())))
        for name, row in zip(names_by_selection[selection], matches):
            try:
                item = _spec_from_row(name, selection, bounds[0], reason, row)
            except ValueError:
                return ExpandedDiscoveryResult("scan_row_invalid", tuple(specs), tuple(sorted(scanned.items())))
            specs.append(item)
            used_states.add((item.seed, item.step, item.state_digest))

    for selection, name, reason in (
        ("midgame_pressure_resource", "midgame_pressure_resource", "first_common_midgame_pressure_resource"),
        ("midgame_team_danger", "midgame_team_danger", "first_distinct_common_midgame_team_danger"),
    ):
        match = select_from_range(selection, MIDGAME_RANGE, 1, distinct_seed=False, reason=reason)
        if match is None:
            return ExpandedDiscoveryResult(f"{selection}_common_state_missing", tuple(specs), tuple(sorted(scanned.items())))
        try:
            item = _spec_from_row(name, selection, MIDGAME_RANGE[0], reason, match[0])
        except ValueError:
            return ExpandedDiscoveryResult("scan_row_invalid", tuple(specs), tuple(sorted(scanned.items())))
        specs.append(item)
        used_states.add((item.seed, item.step, item.state_digest))

    endgame = select_from_range("endgame", ENDGAME_RANGE, 2, distinct_seed=True, reason="first_two_common_endgame_seeds")
    if endgame is None:
        return ExpandedDiscoveryResult("endgame_common_states_missing", tuple(specs), tuple(sorted(scanned.items())))
    for name, row in zip(("endgame_1", "endgame_2"), endgame):
        try:
            item = _spec_from_row(name, "endgame", ENDGAME_RANGE[0], "first_two_common_endgame_seeds", row)
        except ValueError:
            return ExpandedDiscoveryResult("scan_row_invalid", tuple(specs), tuple(sorted(scanned.items())))
        specs.append(item)
        used_states.add((item.seed, item.step, item.state_digest))

    if tuple(item.name for item in specs) != _EXPECTED_NAMES:
        return ExpandedDiscoveryResult("queue_order_invalid", tuple(specs), tuple(sorted(scanned.items())))
    if len({(item.seed, item.step) for item in specs}) != len(specs):
        return ExpandedDiscoveryResult("duplicate_state", tuple(specs), tuple(sorted(scanned.items())))
    if specs[-2].seed == specs[-1].seed:
        return ExpandedDiscoveryResult("endgame_seed_not_distinct", tuple(specs), tuple(sorted(scanned.items())))
    return ExpandedDiscoveryResult("ready", tuple(specs), tuple(sorted(scanned.items())))


def _m2_module() -> Any:
    from evaluation import m2_same_state_model_eval

    return m2_same_state_model_eval


def validate_expanded_offline_qualifications(
    specs: Sequence[ExpandedM2StateSpec],
    qualifications: Sequence[object],
) -> str:
    """Require eight frozen states × two actual-client fake-request rows."""
    if tuple(item.name for item in specs) != _EXPECTED_NAMES or len(specs) != 8 or len(qualifications) != 16:
        return "offline_qualification_count_invalid"
    if len({(item.seed, item.step) for item in specs}) != 8:
        return "duplicate_state"
    if tuple(item.selection for item in specs) != _EXPECTED_SELECTIONS:
        return "sample_selection_invalid"
    if specs[0].seed not in range(*_inclusive_tuple(OPENING_DENSE_RANGE)) or specs[1].seed not in range(*_inclusive_tuple(OPENING_DENSE_RANGE)):
        return "dense_opening_range_invalid"
    if specs[0].seed == specs[1].seed:
        return "dense_opening_seed_not_distinct"
    if specs[0].seed > specs[1].seed:
        return "dense_opening_seed_order_invalid"
    if specs[2].seed not in range(*_inclusive_tuple(OPENING_DIVERSE_RANGE)) or specs[3].seed not in range(*_inclusive_tuple(OPENING_DIVERSE_RANGE)):
        return "diverse_opening_range_invalid"
    if specs[2].seed == specs[3].seed:
        return "diverse_opening_seed_not_distinct"
    if specs[2].seed > specs[3].seed:
        return "diverse_opening_seed_order_invalid"
    if any(spec.step != 0 for spec in specs[:4]) or specs[4].seed not in range(*_inclusive_tuple(MIDGAME_RANGE)) or specs[5].seed not in range(*_inclusive_tuple(MIDGAME_RANGE)):
        return "opening_midgame_spec_invalid"
    if specs[4].phase != "midgame" or specs[5].phase != "midgame":
        return "midgame_phase_invalid"
    if specs[6].phase not in _ENDGAME_PHASES or specs[7].phase not in _ENDGAME_PHASES:
        return "endgame_phase_invalid"
    if specs[6].seed not in range(*_inclusive_tuple(ENDGAME_RANGE)) or specs[7].seed not in range(*_inclusive_tuple(ENDGAME_RANGE)):
        return "endgame_range_invalid"
    if specs[6].seed == specs[7].seed:
        return "endgame_seed_not_distinct"
    for item in specs:
        if (
            item.step < 0
            or item.requested_seed != (
                OPENING_DENSE_RANGE[0] if item.selection == "opening_dense"
                else OPENING_DIVERSE_RANGE[0] if item.selection == "opening_diverse"
                else MIDGAME_RANGE[0] if item.selection.startswith("midgame_")
                else ENDGAME_RANGE[0]
            )
            or item.canonical_count < 2
            or item.nonpass_count < 2
            or not item.state_digest
        ):
            return "sample_spec_invalid"
        if item.selection not in _SELECTIONS:
            return "sample_selection_invalid"
        raw_patterns = dict(item.raw_pattern_counts)
        raw_relations = dict(item.relation_counts)
        if item.selection == "opening_dense" and (
            item.canonical_count <= 80
            or raw_relations.get("natural_pair_single", 0) <= 0
            or raw_relations.get("wildcard_resource", 0) <= 0
        ):
            return "dense_opening_selection_invalid"
        if item.selection == "opening_diverse" and (
            item.canonical_count > 80
            or any(raw_patterns.get(kind, 0) <= 0 for kind in ("single", "pair", "triple"))
        ):
            return "diverse_opening_selection_invalid"
        if item.selection == "midgame_pressure_resource" and not (
            set(raw_relations) & _PRESSURE_RESOURCE_RELATIONS
        ):
            return "midgame_pressure_relation_missing"
        if item.selection == "midgame_team_danger" and not any(
            kind.startswith(_TEAM_DANGER_PREFIXES) for kind in raw_relations
        ):
            return "midgame_team_danger_relation_missing"
        if item.selection == "endgame" and (
            item.phase not in _ENDGAME_PHASES or item.nonpass_count < 2
        ):
            return "endgame_selection_invalid"

    index: dict[tuple[str, str], object] = {}
    for row in qualifications:
        key = (getattr(row, "state_name", None), getattr(row, "version", None))
        if key in index:
            return "offline_qualification_duplicate"
        index[key] = row
    if len(index) != 16:
        return "offline_qualification_duplicate"

    timeout_fingerprint: tuple[object, object, object] | None = None
    for spec in specs:
        version_rows = [index.get((spec.name, version)) for version in VERSION_ORDER]
        if any(row is None for row in version_rows):
            return "offline_qualification_missing"
        for row in version_rows:
            assert row is not None
            if (
                getattr(row, "state_digest", None) != spec.state_digest
                or getattr(row, "canonical_count", None) != spec.canonical_count
            ):
                return "paired_public_state_mismatch"
            if (
                getattr(row, "stage", None) != "ready"
                or getattr(row, "state_phase", None) != spec.phase
                or getattr(row, "max_retries", None) != MAX_RETRIES
                or getattr(row, "transport_calls", None) != 1
                or getattr(row, "external_send_invocations", None) != 0
                or getattr(row, "stream_entries", None) != 1
                or getattr(row, "default_transport_entries", None) != 0
                or not getattr(row, "envelope_bound", False)
                or not getattr(row, "candidate_closed", False)
                or not getattr(row, "recommendation_closed", False)
                or getattr(row, "source", None) != "model"
                or getattr(row, "provider_outcome", None) != "success"
                or not (1 <= getattr(row, "final_count", 0) <= 80)
                or len(getattr(row, "final_candidate_ids", ())) != getattr(row, "final_count", 0)
                or getattr(row, "response_action_id", None) != getattr(row, "client_action_id", None)
                or getattr(row, "response_action_id", None) not in getattr(row, "final_candidate_ids", ())
                or getattr(row, "configured_timeout_seconds", None) is None
                or getattr(row, "configured_timeout_seconds", 0) <= 0
                or getattr(row, "decision_budget_seconds", None) != 119.0
            ):
                return "offline_candidate_or_model_contract_invalid"
            own_reference = getattr(row, "reference_action_id", None)
            if type(own_reference) is not int:
                return "version_reference_action_invalid"
            # Visibility is intentionally derived from this same version row.
            visible = own_reference in getattr(row, "final_candidate_ids", ())
            if visible != (getattr(row, "reference_action_id", None) in getattr(row, "final_candidate_ids", ())):
                return "version_reference_visibility_invalid"
            fingerprint = (
                getattr(row, "request_controls_fingerprint", None),
                getattr(row, "configured_timeout_seconds", None),
                getattr(row, "decision_budget_seconds", None),
            )
            if not fingerprint[0]:
                return "offline_request_controls_invalid"
            if timeout_fingerprint is None:
                timeout_fingerprint = fingerprint
            elif fingerprint != timeout_fingerprint:
                return "paired_request_controls_mismatch"
            relation_counts = dict(getattr(row, "relation_counts", ()))
            if spec.selection == "opening_dense" and not all(
                int(relation_counts.get(kind, 0)) > 0 for kind in ("natural_pair_single", "wildcard_resource")
            ):
                return "dense_opening_relation_missing"
        baseline = version_rows[0]
        current = version_rows[1]
        assert baseline is not None and current is not None
        if (
            getattr(baseline, "state_digest", None) != getattr(current, "state_digest", None)
            or getattr(baseline, "canonical_count", None) != getattr(current, "canonical_count", None)
        ):
            return "paired_public_state_mismatch"
    return "ready"


def _inclusive_tuple(bounds: tuple[int, int]) -> tuple[int, int]:
    return bounds[0], bounds[1] + 1


def qualify_expanded_states(
    specs: Sequence[ExpandedM2StateSpec],
    roots: Mapping[str, Path],
    source_path: Path,
    profile: Mapping[str, object],
) -> ExpandedQualificationResult:
    if set(roots) != set(VERSION_ORDER):
        return ExpandedQualificationResult("version_roots_invalid", ())
    m2 = _m2_module()
    rows: list[object] = []
    for spec in specs:
        m2_spec = spec.as_m2_spec()
        for version in VERSION_ORDER:
            raw = m2.probe_version_state(roots[version], source_path, m2_spec, profile, real=False)
            rows.append(m2.qualification_from_worker(spec.name, version, raw))
    result_rows = tuple(rows)
    return ExpandedQualificationResult(
        validate_expanded_offline_qualifications(specs, result_rows),
        result_rows,
    )


def build_expanded_request_schedule(specs: Sequence[ExpandedM2StateSpec]) -> tuple[ExpandedRequestSlot, ...]:
    if tuple(item.name for item in specs) != _EXPECTED_NAMES or len(specs) != 8:
        raise ValueError("expanded_schedule_state_specs_invalid")
    slots: list[ExpandedRequestSlot] = []
    for state_index, spec in enumerate(specs, start=1):
        order = (BASELINE_VERSION, CURRENT_VERSION, CURRENT_VERSION, BASELINE_VERSION)
        if state_index % 2 == 0:
            order = (CURRENT_VERSION, BASELINE_VERSION, BASELINE_VERSION, CURRENT_VERSION)
        repeat_counts = Counter()
        for version in order:
            repeat_counts[version] += 1
            slots.append(ExpandedRequestSlot(len(slots) + 1, spec.name, version, repeat_counts[version]))
    schedule = tuple(slots)
    if len(schedule) != MAX_EXTERNAL_REQUESTS or any(slot.sequence != index for index, slot in enumerate(schedule, 1)):
        raise ValueError("expanded_schedule_budget_invalid")
    return schedule


def classify_send_status(result: Mapping[str, object]) -> str:
    count = result.get("external_send_invocations")
    if type(count) is not int:
        return "unknown"
    if count == 0:
        return "not_sent"
    if count == 1:
        return "sent"
    return "send_count_invalid"


def _sent_result_stage(row: object, send_status: str) -> str | None:
    if send_status == "not_sent":
        return "pre_send_failure"
    if send_status != "sent":
        return "send_status_unknown"
    if getattr(row, "max_retries", None) != MAX_RETRIES:
        return "retry_cap_invalid"
    outcome = getattr(row, "provider_outcome", None)
    if outcome in {"timeout", "exception", "invalid_suggestion"}:
        if getattr(row, "transport_calls", None) != 1 or not getattr(row, "envelope_bound", False):
            return "provider_failure_binding_invalid"
        return None
    if outcome != "success":
        return "provider_outcome_invalid"
    candidate_ids = getattr(row, "final_candidate_ids", ())
    response_id = getattr(row, "response_action_id", None)
    if (
        getattr(row, "stage", None) != "ready"
        or getattr(row, "transport_calls", None) != 1
        or not getattr(row, "envelope_bound", False)
        or not getattr(row, "candidate_closed", False)
        or not getattr(row, "recommendation_closed", False)
        or getattr(row, "source", None) != "model"
        or getattr(row, "client_action_id", None) != response_id
        or type(response_id) is not int
        or response_id not in candidate_ids
        or not (1 <= getattr(row, "final_count", 0) <= 80)
    ):
        return "model_result_contract_invalid"
    return None


def _attempt_binding_stage(spec: ExpandedM2StateSpec, offline: object, actual: object) -> str | None:
    """Bind a sent result to that version's own offline request qualification."""
    exact_fields = (
        "state_digest",
        "state_phase",
        "canonical_count",
        "final_count",
        "candidate_patterns",
        "wildcard_candidate_count",
        "relation_counts",
        "visible_relation_counts",
        "rendered_relation_line_count",
        "rendered_contrast_count",
        "rag_experience_hits",
        "recommendation_ids",
        "final_candidate_ids",
        "reference_action_id",
        "prompt_chars",
        "prompt_utf8_bytes",
        "request_utf8_bytes",
        "request_controls_fingerprint",
        "configured_timeout_seconds",
        "decision_budget_seconds",
    )
    for field in exact_fields:
        if getattr(actual, field, None) != getattr(offline, field, None):
            return "attempt_offline_binding_mismatch"
    if (
        getattr(actual, "state_digest", None) != spec.state_digest
        or getattr(actual, "state_phase", None) != spec.phase
        or getattr(actual, "canonical_count", None) != spec.canonical_count
        or getattr(actual, "decision_budget_seconds", None) != 119.0
        or getattr(actual, "max_retries", None) != MAX_RETRIES
        or getattr(actual, "transport_calls", None) != 1
        or not getattr(actual, "envelope_bound", False)
    ):
        return "attempt_state_or_request_binding_invalid"
    return None


def run_authorized_expanded_requests(
    specs: Sequence[ExpandedM2StateSpec],
    qualifications: Sequence[object],
    request_once: Callable[[str, ExpandedM2StateSpec, int], Mapping[str, object]],
    *,
    owner_authorization_confirmed: bool = False,
) -> ExpandedRequestRun:
    """Run the single 32-slot schedule only after explicit task authorization.

    This function is not called by state discovery or tests that only qualify
    the queue.  A future caller must confirm authorization for this exact
    32-request task; failures never retry and an unknown send state stops work.
    """
    if owner_authorization_confirmed is not True:
        return ExpandedRequestRun("owner_authorization_required")
    gate = validate_expanded_offline_qualifications(specs, qualifications)
    if gate != "ready":
        return ExpandedRequestRun(f"offline_gate_{gate}")
    m2 = _m2_module()
    schedule = build_expanded_request_schedule(specs)
    spec_index = {item.name: item for item in specs}
    qualification_index = {
        (getattr(row, "state_name", None), getattr(row, "version", None)): row
        for row in qualifications
    }
    attempts: list[ExpandedRequestAttempt] = []
    for slot in schedule:
        if len(attempts) >= MAX_EXTERNAL_REQUESTS:
            return ExpandedRequestRun("request_budget_exhausted", tuple(attempts))
        spec = spec_index[slot.state_name]
        try:
            raw = request_once(slot.version, spec, slot.repeat)
            if not isinstance(raw, Mapping):
                raw = {"stage": "worker_output_invalid"}
        except Exception:
            raw = {"stage": "worker_failure"}
        row = m2.qualification_from_worker(spec.name, slot.version, raw)
        send_status = classify_send_status(raw)
        attempt_index = len(attempts)
        attempts.append(ExpandedRequestAttempt(slot, row, send_status))
        if send_status in {"unknown", "send_count_invalid"}:
            return ExpandedRequestRun("send_status_unknown_stopped", tuple(attempts))
        if send_status == "not_sent":
            return ExpandedRequestRun("pre_send_failure_stopped", tuple(attempts))
        offline_row = qualification_index.get((spec.name, slot.version))
        if offline_row is None:
            return ExpandedRequestRun("offline_qualification_missing_stopped", tuple(attempts))
        binding_error = _attempt_binding_stage(spec, offline_row, row)
        if binding_error is not None:
            return ExpandedRequestRun(f"{binding_error}_stopped", tuple(attempts))
        provider_failure = row.provider_outcome in {"timeout", "exception", "invalid_suggestion"}
        if row.stage in m2._INTEGRITY_FAILURE_STAGES and not provider_failure:
            return ExpandedRequestRun("integrity_failure_stopped", tuple(attempts))
        sent_error = _sent_result_stage(row, send_status)
        if sent_error is not None:
            return ExpandedRequestRun(f"{sent_error}_stopped", tuple(attempts))
        if row.max_retries != MAX_RETRIES:
            return ExpandedRequestRun("retry_cap_invalid_stopped", tuple(attempts))
        if row.provider_outcome == "success":
            rollout = m2.compare_with_frozen_rule_rollout(
                spec.as_m2_spec(),
                row.response_action_id,
                tuple(row.final_candidate_ids),
                reference_action_id=row.reference_action_id,
                expected_state_digest=spec.state_digest,
            )
            if rollout is None:
                attempts[attempt_index] = replace(attempts[attempt_index], rollout_status="unevaluable")
            else:
                comparison = getattr(rollout, "comparison", None)
                if comparison not in {"selected_better", "reference_better", "tie", "unevaluable"}:
                    return ExpandedRequestRun("rollout_result_invalid_stopped", tuple(attempts))
                attempts[attempt_index] = replace(
                    attempts[attempt_index],
                    rollout=rollout,
                    rollout_status="unevaluable" if comparison == "unevaluable" else "complete",
                )
    return ExpandedRequestRun("complete", tuple(attempts))


def _version_scan_entrypoint() -> int:
    try:
        payload = json.load(sys.stdin)
        result = _version_scan_worker(payload) if isinstance(payload, Mapping) else {"stage": "scan_input_invalid", "rows": []}
    except Exception:
        result = {"stage": "scan_failure", "rows": []}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_version_scan_entrypoint())
