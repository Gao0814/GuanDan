"""Deterministic, no-network qualifications for the H3 model probe.

The fixtures are built through :class:`GuanDanGame` and exposed only as the
same public observation/canonical-action payloads that an agent receives.
They deliberately do not know about API configuration or perform requests.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
import json
from pathlib import Path
import re
from typing import Callable
from unittest.mock import patch

from agents.action_structure import CandidateContrast, CandidateStructure, summarize_candidate_contrasts, summarize_candidate_structures
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion, DeepSeekTransport
from agents.rag_advisor import RAGAdvisor
from agents.short_endgame_planner import minimum_group_free_lead_action_ids
from config import AppConfig
from engine.cards import Card, build_double_deck, card_to_token
from engine.game import GuanDanGame
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


class QualificationStage(StrEnum):
    READY = "ready"
    SCENARIO_CONSTRUCTION = "scenario_construction"
    PUBLIC_CANONICAL = "public_canonical"
    CATEGORY_PARTITION = "category_partition"
    RECOMMENDATION = "recommendation"
    REQUEST_BINDING = "request_binding"
    FINAL_CANDIDATES = "final_candidates"
    RAG_CONTEXT = "rag_context"
    ROUTER_RAG_PROMPT = "router_rag_prompt"
    LOCAL_SHORTCUT = "local_shortcut"
    MODEL_PASSTHROUGH = "model_passthrough"


SCENARIO_NAMES = (
    "bomb_residual",
    "low_cost_single",
    "pair_cleanup",
    "neutral_soft_pair",
    "teammate_controls",
    "danger_block",
    "short_endgame",
    "bomb_wildcard_soft",
)


@dataclass(frozen=True, slots=True)
class ProbeFixture:
    name: str
    observation: dict[str, object]
    legal_actions: list[dict[str, object]]
    # Kept only so evaluation code can clone the exact engine state for local
    # rollouts.  Agents receive observation/legal_actions, never this snapshot.
    game_snapshot: GuanDanGame | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class QualificationResult:
    name: str
    stage: QualificationStage
    candidate_count: int
    final_candidate_count: int
    category_counts: tuple[tuple[str, int], ...]
    recommendation_ready: bool
    contrast_ready: bool
    soft_marker_ready: bool
    prompt_markers_ready: bool
    source_is_model: bool

    @property
    def ready(self) -> bool:
        return self.stage is QualificationStage.READY


_SAFE_CONFIG = AppConfig(
    deepseek_api_key=None,
    deepseek_base_url="",
    deepseek_model="",
    deepseek_enabled=False,
    hand_evaluation_enabled=True,
    card_tracking_enabled=False,
    opening_formula_enabled=True,
    deepseek_timeout=1.0,
    deepseek_max_retries=0,
    debug=False,
)


def _cards(tokens: tuple[str, ...]) -> tuple[Card, ...]:
    return tuple(
        Card(rank=token, suit=None) if token in {"SJ", "BJ"} else Card(rank=token[:-1], suit=token[-1])
        for token in tokens
    )


def _game(
    one: tuple[str, ...],
    two: tuple[str, ...],
    three: tuple[str, ...],
    four: tuple[str, ...],
    *,
    starting_player_id: int = 1,
) -> GuanDanGame:
    return GuanDanGame(
        current_level_rank="2",
        preset_hands={1: _cards(one), 2: _cards(two), 3: _cards(three), 4: _cards(four)},
        starting_player_id=starting_player_id,
    )


def _complete_opening_hands(
    first_hand: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Complete a deterministic first hand into a physical double-deck deal."""
    deck = [card_to_token(card) for card in build_double_deck()]
    deck_counts = Counter(deck)
    first_counts = Counter(first_hand)
    if len(first_hand) != 27 or any(count > deck_counts.get(token, 0) for token, count in first_counts.items()):
        raise RuntimeError("fixture_opening_hand_invalid")

    remainder = list(deck)
    for token in first_hand:
        remainder.remove(token)
    if len(remainder) != 81:
        raise RuntimeError("fixture_opening_remainder_invalid")
    return (
        tuple(first_hand),
        tuple(remainder[:27]),
        tuple(remainder[27:54]),
        tuple(remainder[54:81]),
    )


def _action_id(game: GuanDanGame, predicate: Callable[[dict[str, object]], bool]) -> int:
    for action in game.legal_actions():
        if predicate(action):
            return int(action["action_id"])
    raise RuntimeError("fixture_canonical_action_missing")


def _pass(game: GuanDanGame) -> int:
    return _action_id(game, lambda action: action["declared_pattern"] == "pass")


def _single(game: GuanDanGame, rank: str) -> int:
    return _action_id(
        game,
        lambda action: action["declared_pattern"] == "single" and action["declared_cards"] == [rank],
    )


def _snapshot(name: str, game: GuanDanGame) -> ProbeFixture:
    return ProbeFixture(name, game.observe(), game.legal_actions(), game_snapshot=game)


def _bomb_residual() -> ProbeFixture:
    game = _game(
        ("7S", "7H", "7C", "7D", "7S", "3S", "4H"),
        ("AS", "AH", "AC"), ("KS", "KH", "KC"), ("QS", "QH", "QC"),
    )
    game.reset()
    return _snapshot("bomb_residual", game)


def _low_cost_single() -> ProbeFixture:
    hands = _complete_opening_hands(
        (
            "3S", "9C", "AH",
            "4S", "4H", "5C", "5D", "6S", "6H", "7C", "7D", "8S", "8H",
            "10S", "10C", "JH", "JD", "QS", "QC", "KH", "KD", "2S", "2C",
            "SJ", "SJ", "BJ", "BJ",
        ),
    )
    game = _game(
        *hands,
    )
    game.reset()
    return _snapshot("low_cost_single", game)


def _pair_cleanup() -> ProbeFixture:
    game = _game(
        ("6S", "6H", "3S", "4H", "9C", "AS"),
        ("QS", "QH", "QC"), ("KS",), ("JS", "JH", "JC"),
    )
    game.reset()
    return _snapshot("pair_cleanup", game)


def _neutral_soft_pair() -> ProbeFixture:
    hands = _complete_opening_hands(
        (
            "3S", "6S", "6H", "6C", "8S", "8H", "AH",
            "4S", "4H", "5S", "5H", "7S", "7H", "9S", "9H", "10S", "10H",
            "JS", "JH", "QS", "QH", "KS", "KH", "2S", "2C", "SJ", "SJ",
        ),
    )
    game = _game(
        *hands,
    )
    game.reset()
    return _snapshot("neutral_soft_pair", game)


def _teammate_controls() -> ProbeFixture:
    game = _game(
        ("AS", "BJ", "6S", "7S"), ("9H", "10H", "JH"),
        ("8S", "3S", "4H", "5C"), ("3H", "4D", "5D"), starting_player_id=3,
    )
    game.reset()
    game.step(_single(game, "8"))
    game.step(_pass(game))
    return _snapshot("teammate_controls", game)


def _danger_block() -> ProbeFixture:
    game = _game(
        ("9S", "JH", "3S"), ("8S", "3S", "4H"),
        ("3H", "4D", "5D"), ("3C", "4C", "5C"), starting_player_id=2,
    )
    game.reset()
    game.step(_single(game, "8"))
    game.step(_pass(game))
    game.step(_pass(game))
    return _snapshot("danger_block", game)


def _short_endgame() -> ProbeFixture:
    game = _game(
        ("6S", "7S", "JH", "JD"),
        ("AS", "AH", "AC", "AD", "KS"),
        ("QS", "QH", "QC", "QD", "JS", "JH"),
        ("10S", "10H", "10C", "10D", "9S"),
    )
    game.reset()
    return _snapshot("short_endgame", game)


def _bomb_wildcard_soft() -> ProbeFixture:
    game = _game(
        ("2H", "7S", "7H", "7C", "7D", "3S", "4H"),
        ("AS", "AH", "AC"), ("KS", "KH", "KC"), ("QS", "QH", "QC"),
    )
    game.reset()
    return _snapshot("bomb_wildcard_soft", game)


def build_h3_model_probe_fixtures() -> tuple[ProbeFixture, ...]:
    """Build the frozen H3 categories from real engine public payloads."""
    return (
        _bomb_residual(), _low_cost_single(), _pair_cleanup(), _neutral_soft_pair(),
        _teammate_controls(), _danger_block(), _short_endgame(), _bomb_wildcard_soft(),
    )


def build_h3_model_probe_opening_fixtures() -> tuple[ProbeFixture, ProbeFixture]:
    """Return only the two complete physical opening deals used by H3-A5b."""
    return _low_cost_single(), _neutral_soft_pair()


class _RequestRecordingTransport:
    """Record the client request and optionally delegate to an injected transport."""

    def __init__(self, delegate: DeepSeekTransport | None = None) -> None:
        self.calls = 0
        self.delegate_calls = 0
        self.delegate = delegate
        self.client: _RecordingDeepSeekClient | None = None
        self.envelope_valid = False
        self.user_prompt: str | None = None
        self.prompt_action_ids: tuple[int, ...] = ()
        self.failure_code: str | None = None
        self._request_data: bytes | None = None

    @staticmethod
    def _candidate_ids(prompt: str) -> tuple[int, ...] | None:
        start = prompt.find("【候选动作】")
        end = prompt.find("【规则库依据】")
        if start < 0 or end <= start:
            return None
        pairs = re.findall(r"#(\d+)\s+action_id=(\d+)\s+\|", prompt[start:end])
        if not pairs or any(first != second for first, second in pairs):
            return None
        action_ids = tuple(int(first) for first, _ in pairs)
        return action_ids if len(action_ids) == len(set(action_ids)) else None

    def _capture_request(self, request: object) -> None:
        self.envelope_valid = False
        self.user_prompt = None
        self.prompt_action_ids = ()
        raw = getattr(request, "data", None)
        if not isinstance(raw, bytes):
            return
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if (
            not isinstance(envelope, dict)
            or not isinstance(envelope.get("model"), str)
            or not envelope["model"]
            or envelope.get("temperature") != 0
            or envelope.get("stream") is not True
        ):
            return
        messages = envelope.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            return
        system_messages = [item for item in messages if isinstance(item, dict) and item.get("role") == "system"]
        user_messages = [item for item in messages if isinstance(item, dict) and item.get("role") == "user"]
        if (
            len(system_messages) != 1
            or len(user_messages) != 1
            or not isinstance(system_messages[0].get("content"), str)
        ):
            return
        prompt = user_messages[0].get("content")
        if not isinstance(prompt, str):
            return
        action_ids = self._candidate_ids(prompt)
        if action_ids is None:
            return
        self.envelope_valid = True
        self.user_prompt = prompt
        self.prompt_action_ids = action_ids
        self._request_data = raw

    def __call__(self, request: object, timeout: float) -> str:
        self.calls += 1
        self._capture_request(request)
        client = self.client
        if client is None or not client.displayed_actions:
            self.failure_code = "client_request_not_assembled"
            raise OSError("probe_client_not_assembled")
        displayed_ids = tuple(item.get("action_id") for item in client.displayed_actions)
        if (
            not self.envelope_valid
            or self.user_prompt != client.final_prompt
            or len(displayed_ids) != len(self.prompt_action_ids)
            or any(type(action_id) is not int for action_id in displayed_ids)
            or set(displayed_ids) != set(self.prompt_action_ids)
        ):
            self.failure_code = "request_binding_invalid"
            raise OSError("probe_request_binding_invalid")
        if client.selection_provider is not None:
            kwargs = client.kwargs
            observation = kwargs.get("observation") if isinstance(kwargs, dict) else None
            legal_actions = kwargs.get("legal_actions") if isinstance(kwargs, dict) else None
            if not isinstance(observation, dict) or not isinstance(legal_actions, list):
                self.failure_code = "provider_input_invalid"
                raise OSError("probe_provider_input_invalid")
            try:
                client.provider_call_count += 1
                action_id = client.selection_provider(
                    deepcopy(observation),
                    deepcopy(legal_actions),
                    deepcopy(client.displayed_actions),
                )
                client.provider_action_id = action_id
            except Exception:
                self.failure_code = "provider_exception"
                raise OSError("probe_provider_failure") from None
        elif self.delegate is not None:
            try:
                self.delegate_calls += 1
                response = self.delegate(request, timeout)
            except Exception:
                self.failure_code = "injected_transport_failure"
                raise OSError("probe_injected_transport_failure") from None
            if getattr(request, "data", None) != self._request_data:
                self.failure_code = "request_body_mutated"
                raise OSError("probe_request_body_mutated")
            return response
        else:
            action_id = client.displayed_actions[0].get("action_id")
        if type(action_id) is not int:
            self.failure_code = self.failure_code or "provider_action_invalid"
            raise OSError("probe_displayed_action_invalid")
        content = json.dumps({"action_id": action_id}, separators=(",", ":"))
        chunk = json.dumps({"choices": [{"delta": {"content": content}}]})
        return f"data: {chunk}\n\ndata: [DONE]\n"


class _RecordingDeepSeekClient(DeepSeekClient):
    """Exercise the production client while retaining only in-memory projections."""

    def __init__(
        self,
        selection_provider: Callable[
            [dict[str, object], list[dict[str, object]], list[dict[str, object]]], object
        ] | None = None,
        *,
        transport: DeepSeekTransport | None = None,
        api_key: str = "offline-probe",
        base_url: str = "https://offline.invalid",
        model: str = "offline-probe",
        timeout_seconds: float = 1.0,
        max_retries: int = 0,
    ) -> None:
        if selection_provider is not None and transport is not None:
            raise ValueError("probe_transport_source_ambiguous")
        self.transport = self._new_transport()
        self.transport.delegate = transport
        self.selection_provider = selection_provider
        self.calls = 0
        self.provider_call_count = 0
        self.provider_action_id: object = None
        self.response_action_id: int | None = None
        self.client_result_action_id: int | None = None
        self.kwargs: dict[str, object] | None = None
        self.displayed_actions: list[dict[str, object]] = []
        self.final_actions: list[dict[str, object]] = []
        self.final_prompt: str | None = None
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            transport=self.transport,
        )
        self.transport.client = self

    def _new_transport(self) -> _RequestRecordingTransport:
        return _RequestRecordingTransport()

    def suggest_action_id(self, **kwargs: object) -> object:
        self.calls += 1
        self.kwargs = dict(kwargs)
        suggestion = super().suggest_action_id(**kwargs)
        self.client_result_action_id = (
            suggestion.action_id if isinstance(suggestion, DeepSeekSuggestion) else None
        )
        return suggestion

    @staticmethod
    def _strict_response_action_id(content: str) -> int | None:
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            return None
        if type(payload) is int:
            return payload
        if not isinstance(payload, dict):
            return None
        for key in ("action_id", "suggested_action_id"):
            if key in payload:
                value = payload.get(key)
                return value if type(value) is int else None
        suggested = payload.get("suggested_action")
        if isinstance(suggested, dict):
            value = suggested.get("action_id")
            return value if type(value) is int else None
        return None

    def _stream_sse(self, req: object, timeout: float) -> tuple[str, str]:
        content, reasoning = super()._stream_sse(req, timeout)  # type: ignore[arg-type]
        self.response_action_id = self._strict_response_action_id(content)
        return content, reasoning

    def _build_structured_prompt(self, **kwargs: object) -> str:
        actions = kwargs.get("legal_actions")
        if not isinstance(actions, list) or not all(isinstance(action, dict) for action in actions):
            raise RuntimeError("probe_final_actions_invalid")
        self.displayed_actions = [dict(action) for action in actions]
        self.final_actions = [dict(action) for action in actions]
        prompt = DeepSeekClient._build_structured_prompt(**kwargs)
        self.final_prompt = prompt
        return prompt


def _advisor() -> RAGAdvisor:
    root = Path(__file__).resolve().parents[1] / "rag"
    return RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(root).load_all_documents()))


def _run_projection(
    fixture: ProbeFixture,
    advisor: RAGAdvisor,
    *,
    client_factory: Callable[[], _RecordingDeepSeekClient] = _RecordingDeepSeekClient,
) -> tuple[DeepSeekAIAgent, _RecordingDeepSeekClient, int | None]:
    client = client_factory()
    player_id = fixture.observation.get("my_info", {}).get("player_id") if isinstance(fixture.observation.get("my_info"), dict) else None
    if type(player_id) is not int:
        raise RuntimeError("fixture_player_id_invalid")
    # DeepSeekAIAgent normally reads config only to choose optional local
    # helpers.  The probe fixes those helpers explicitly and patches the read
    # so test/import execution never loads dotenv or requests a model.
    with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_SAFE_CONFIG):
        agent = DeepSeekAIAgent(
            player_id, client, rag_advisor=advisor, rag_top_k=3,
            hand_evaluation_enabled=True, opening_formula_enabled=True,
            strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
            strategy_recommendation_enabled=True,
        )
        chosen = agent.select_action(fixture.observation, fixture.legal_actions)
    return agent, client, chosen


def _classify(
    name: str,
    action_id: int,
    final_ids: set[int],
    facts: dict[int, CandidateStructure],
    contrasts: tuple[CandidateContrast, ...],
    minimum_ids: tuple[int, ...],
) -> str | None:
    fact = facts.get(action_id)
    if fact is None or action_id not in final_ids:
        return None
    if name == "bomb_residual":
        contrast = next((item for item in contrasts if item.kind == "bomb_residual"), None)
        if contrast is None:
            return None
        if action_id == contrast.action_ids[1]:
            return "five_bomb"
        if action_id == contrast.action_ids[0]:
            return "four_bomb_leaves_singleton"
        return "alternative"
    if name == "low_cost_single":
        safe = sorted(
            (item for item in facts.values() if item.action_id in final_ids and item.pattern == "single"
             and item.natural_single_rank_value is not None and not item.fragments_played_rank_group
             and not item.consumes_control_resource),
            key=lambda item: (item.natural_single_rank_value, item.action_id),
        )
        if fact.consumes_control_resource:
            return "control_resource"
        if safe and action_id == safe[0].action_id:
            return "low_cost_single"
        if len(safe) > 1 and action_id == safe[-1].action_id:
            return "high_single"
        return "other"
    if name == "pair_cleanup":
        contrast = next((item for item in contrasts if item.kind == "natural_pair_single"), None)
        if contrast is None:
            return None
        if action_id == contrast.action_ids[0]:
            return "pair_cleanup"
        if action_id == contrast.action_ids[1]:
            return "single_split"
        return "other"
    if name == "neutral_soft_pair":
        if fact.pattern in {"pair", "triple"} and not fact.uses_wildcard:
            return "neutral_group"
        return "single" if fact.pattern == "single" else "other"
    if name == "teammate_controls":
        if fact.pattern == "pass":
            return "pass_preserve"
        return "spend_control" if fact.consumes_control_resource else "other"
    if name == "danger_block":
        return "pass" if fact.pattern == "pass" else "block"
    if name == "short_endgame":
        return "minimum_group" if action_id in minimum_ids else "strictly_worse"
    if name == "bomb_wildcard_soft":
        return "spend_resource" if fact.uses_wildcard or fact.bomb_length is not None else "preserve_resource"
    return None


def _result(
    fixture: ProbeFixture,
    stage: QualificationStage,
    *,
    candidate_count: int = 0,
    final_candidate_count: int = 0,
    category_counts: Counter[str] | None = None,
    recommendation_ready: bool = False,
    contrast_ready: bool = False,
    soft_marker_ready: bool = False,
    prompt_markers_ready: bool = False,
    source_is_model: bool = False,
) -> QualificationResult:
    return QualificationResult(
        fixture.name, stage, candidate_count, final_candidate_count,
        tuple(sorted((category_counts or Counter()).items())), recommendation_ready,
        contrast_ready, soft_marker_ready, prompt_markers_ready, source_is_model,
    )


def _rag_context_ready(
    fixture: ProbeFixture,
    captured: dict[str, object],
    intent: object,
) -> bool:
    """Require the actual, scene-appropriate RAG projection used by the client."""
    rag_context = captured.get("rag_context")
    phase_context = captured.get("phase_context")
    hand_evaluation = captured.get("hand_evaluation")
    if (
        not isinstance(rag_context, dict)
        or phase_context is None
        or not isinstance(hand_evaluation, dict)
        or getattr(intent, "status", None) != "available"
    ):
        return False
    tags = rag_context.get("scene_tags")
    rule_hits = rag_context.get("rule_hits")
    experience_hits = rag_context.get("experience_hits")
    if not isinstance(tags, dict) or not isinstance(rule_hits, list) or not isinstance(experience_hits, list):
        return False
    expected_tags = RAGAdvisor._scene_tags(
        fixture.observation,
        fixture.legal_actions,
        hand_evaluation,
        phase_context,
    )
    required_tag_keys = ("scene", "phase", "hand_strength", "action_context")
    if any(tags.get(key) != expected_tags.get(key) for key in required_tag_keys):
        return False
    if tags.get("strategy_intent") != getattr(intent, "intent", None):
        return False
    expected_phase = {
        "low_cost_single": ("lead_opening", "opening"),
        "neutral_soft_pair": ("lead_opening", "opening"),
    }.get(fixture.name)
    if expected_phase is not None and (
        tags.get("scene"), tags.get("phase")
    ) != expected_phase:
        return False

    def accepted_hits(items: list[object]) -> bool:
        return bool(items) and all(
            isinstance(item, dict)
            and isinstance(item.get("source_id"), str)
            and item.get("source_id")
            and isinstance(item.get("metadata"), dict)
            and item["metadata"].get("status") == "accepted"
            for item in items
        )

    if not accepted_hits(rule_hits) or not accepted_hits(experience_hits):
        return False

    def supports_scene(item: object) -> bool:
        if not isinstance(item, dict) or not isinstance(item.get("metadata"), dict):
            return False
        metadata = item["metadata"]

        def contains(key: str, expected: object) -> bool:
            raw = metadata.get(key)
            if not isinstance(raw, str) or not raw:
                return False
            values = {value.strip() for value in raw.split(",")}
            if "any" in values or expected in values:
                return True
            return key == "phase" and expected in {"near_open_endgame", "critical_endgame"} and "endgame" in values

        return all(contains(key, tags.get(key)) for key in ("scene", "phase", "action_context"))

    return any(supports_scene(item) for item in experience_hits)


def _soft_evidence_ready(
    captured: dict[str, object],
    prompt: str | None,
    expected_source_id: str,
) -> bool:
    """Tie the rendered soft marker to an accepted RAG hit, not free text."""
    rag_context = captured.get("rag_context")
    if not isinstance(rag_context, dict) or not isinstance(prompt, str):
        return False
    hits = rag_context.get("experience_hits")
    if not isinstance(hits, list):
        return False
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get("metadata"), dict):
            continue
        if (
            hit.get("source_id") != expected_source_id
            or hit["metadata"].get("status") != "accepted"
            or hit["metadata"].get("guidance_mode") != "soft_hypothesis"
        ):
            continue
        rendered = DeepSeekClient._format_rag_hits([hit])
        if len(rendered) == 1 and rendered[0].startswith("- 可撤回软假设：") and rendered[0] in prompt:
            return True
    return False


def _same_action_ids(left: list[dict[str, object]], right: list[dict[str, object]]) -> bool:
    return [item.get("action_id") for item in left] == [item.get("action_id") for item in right]


def _request_binding_ready(client: _RecordingDeepSeekClient) -> bool:
    """Bind recorded projections to the user prompt actually sent to transport."""
    displayed_ids = tuple(item.get("action_id") for item in client.displayed_actions)
    return bool(
        client.transport.calls == 1
        and client.transport.envelope_valid
        and client.final_prompt is not None
        and client.transport.user_prompt == client.final_prompt
        and len(displayed_ids) == len(client.transport.prompt_action_ids)
        and len(set(displayed_ids)) == len(displayed_ids)
        and set(displayed_ids) == set(client.transport.prompt_action_ids)
        and _same_action_ids(client.displayed_actions, client.final_actions)
    )


def qualify_h3_model_probe_fixture(
    fixture: ProbeFixture,
    *,
    advisor: RAGAdvisor | None = None,
    client_factory: Callable[[], _RecordingDeepSeekClient] = _RecordingDeepSeekClient,
) -> QualificationResult:
    """Run the frozen, no-network production projection stage by stage."""
    if fixture.name not in SCENARIO_NAMES or not isinstance(fixture.observation, dict) or not isinstance(fixture.legal_actions, list):
        return _result(fixture, QualificationStage.SCENARIO_CONSTRUCTION)
    candidate_count = len(fixture.legal_actions)
    facts_tuple = summarize_candidate_structures(fixture.observation, fixture.legal_actions)
    contrasts = summarize_candidate_contrasts(fixture.observation, fixture.legal_actions)
    if facts_tuple is None or contrasts is None or candidate_count == 0:
        return _result(fixture, QualificationStage.PUBLIC_CANONICAL, candidate_count=candidate_count)
    facts = {item.action_id: item for item in facts_tuple}
    try:
        agent, client, chosen = _run_projection(
            fixture,
            advisor or _advisor(),
            client_factory=client_factory,
        )
    except Exception:
        return _result(fixture, QualificationStage.ROUTER_RAG_PROMPT, candidate_count=candidate_count)
    if client.calls != 1 or client.kwargs is None or agent.last_decision_source != "model":
        return _result(fixture, QualificationStage.LOCAL_SHORTCUT, candidate_count=candidate_count)
    recommendation = agent.last_strategy_recommendation
    validated = DeepSeekClient._validated_strategy_recommendation(recommendation, fixture.legal_actions)
    if validated is None or len(validated.action_ids) > 3 or len(validated.objective_codes) > 4:
        return _result(fixture, QualificationStage.RECOMMENDATION, candidate_count=candidate_count)
    if not _request_binding_ready(client):
        return _result(
            fixture,
            QualificationStage.REQUEST_BINDING,
            candidate_count=candidate_count,
            recommendation_ready=True,
        )
    final_actions = client.final_actions
    if not final_actions or not _same_action_ids(final_actions, client.displayed_actions):
        return _result(
            fixture,
            QualificationStage.FINAL_CANDIDATES,
            candidate_count=candidate_count,
            recommendation_ready=True,
        )
    final_ids = {int(item["action_id"]) for item in final_actions}
    source_ids = {int(item["action_id"]) for item in fixture.legal_actions}
    signatures = [DeepSeekClient._action_signature(item) for item in final_actions]
    if (
        len(final_actions) > 80 or not final_ids.issubset(source_ids)
        or len(signatures) != len(set(signatures)) or not set(validated.action_ids).issubset(final_ids)
    ):
        return _result(fixture, QualificationStage.FINAL_CANDIDATES, candidate_count=candidate_count, final_candidate_count=len(final_actions), recommendation_ready=True)
    player_id = fixture.observation["my_info"].get("player_id") if isinstance(fixture.observation.get("my_info"), dict) else None
    minimum_ids = minimum_group_free_lead_action_ids(fixture.observation, fixture.legal_actions, player_id) if type(player_id) is int else None
    categories = [_classify(fixture.name, int(item["action_id"]), final_ids, facts, contrasts, minimum_ids or ()) for item in final_actions]
    if any(category is None for category in categories):
        return _result(fixture, QualificationStage.CATEGORY_PARTITION, candidate_count=candidate_count, final_candidate_count=len(final_actions), recommendation_ready=True)
    category_counts = Counter(category for category in categories if category is not None)
    if sum(category_counts.values()) != len(final_actions) or not _required_categories_ready(fixture.name, category_counts):
        return _result(fixture, QualificationStage.CATEGORY_PARTITION, candidate_count=candidate_count, final_candidate_count=len(final_actions), category_counts=category_counts, recommendation_ready=True)
    prompt = client.final_prompt
    intent = agent.last_strategy_intent
    intent_prompt = agent.last_strategy_intent_prompt
    prompt_markers = bool(prompt and all(marker in prompt for marker in ("【模型前建议】", "策略域：", "目标：", "反例检查：")))
    contrast_ready = _contrast_ready(fixture.name, contrasts, final_ids, validated.action_ids, prompt)
    expected_soft_source = {
        "low_cost_single": "exp_soft_pair_probe_001",
        "neutral_soft_pair": "exp_soft_pair_probe_001",
        "bomb_wildcard_soft": "exp_bomb_wildcard_001",
    }.get(fixture.name)
    soft_ready = bool(
        expected_soft_source
        and _soft_evidence_ready(client.kwargs, prompt, expected_soft_source)
    )
    if not _rag_context_ready(fixture, client.kwargs, intent):
        return _result(
            fixture,
            QualificationStage.RAG_CONTEXT,
            candidate_count=candidate_count,
            final_candidate_count=len(final_actions),
            category_counts=category_counts,
            recommendation_ready=True,
            contrast_ready=contrast_ready,
            soft_marker_ready=soft_ready,
            prompt_markers_ready=prompt_markers,
        )
    if (
        prompt is None or intent is None or getattr(intent, "status", None) != "available"
        or intent_prompt is None or getattr(intent_prompt, "status", None) != "ready"
        or not prompt_markers or (fixture.name in {"bomb_residual", "pair_cleanup"} and not contrast_ready)
        or (fixture.name in {"low_cost_single", "neutral_soft_pair", "bomb_wildcard_soft"} and not soft_ready)
    ):
        return _result(fixture, QualificationStage.ROUTER_RAG_PROMPT, candidate_count=candidate_count, final_candidate_count=len(final_actions), category_counts=category_counts, recommendation_ready=True, contrast_ready=contrast_ready, soft_marker_ready=soft_ready, prompt_markers_ready=prompt_markers)
    if chosen not in final_ids:
        return _result(fixture, QualificationStage.MODEL_PASSTHROUGH, candidate_count=candidate_count, final_candidate_count=len(final_actions), category_counts=category_counts, recommendation_ready=True, contrast_ready=contrast_ready, soft_marker_ready=soft_ready, prompt_markers_ready=prompt_markers, source_is_model=True)
    return _result(fixture, QualificationStage.READY, candidate_count=candidate_count, final_candidate_count=len(final_actions), category_counts=category_counts, recommendation_ready=True, contrast_ready=contrast_ready, soft_marker_ready=soft_ready, prompt_markers_ready=prompt_markers, source_is_model=True)


def _required_categories_ready(name: str, counts: Counter[str]) -> bool:
    required = {
        "bomb_residual": {"five_bomb", "four_bomb_leaves_singleton"},
        "low_cost_single": {"low_cost_single", "high_single", "control_resource"},
        "pair_cleanup": {"pair_cleanup", "single_split"},
        "neutral_soft_pair": {"neutral_group", "single"},
        "teammate_controls": {"pass_preserve", "spend_control"},
        "danger_block": {"block", "pass"},
        "short_endgame": {"minimum_group", "strictly_worse"},
        "bomb_wildcard_soft": {"preserve_resource", "spend_resource"},
    }
    return required[name].issubset(counts)


def _contrast_ready(name: str, contrasts: tuple[CandidateContrast, ...], final_ids: set[int], recommendation_ids: tuple[int, ...], prompt: str | None) -> bool:
    kind = {"bomb_residual": "bomb_residual", "pair_cleanup": "natural_pair_single"}.get(name)
    if kind is None:
        return False
    contrast = next((item for item in contrasts if item.kind == kind), None)
    return bool(
        contrast is not None and set(contrast.action_ids).issubset(final_ids)
        and set(contrast.action_ids).issubset(recommendation_ids)
        and prompt is not None and "【公开关系对照】" in prompt
    )


def qualify_h3_model_probe_fixtures() -> tuple[QualificationResult, ...]:
    """Qualify all eight fixtures in frozen order without API/config side effects."""
    advisor = _advisor()
    return tuple(qualify_h3_model_probe_fixture(fixture, advisor=advisor) for fixture in build_h3_model_probe_fixtures())
