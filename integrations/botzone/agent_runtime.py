"""Explicit, match-safe agent composition for the Botzone connector."""

from __future__ import annotations

from collections.abc import Callable
import threading

from decision_deadline import DecisionDeadline, MODEL_RESPONSE_RESERVE_SECONDS

from .stage_trace import StageTraceSink, record_stage


class AgentRuntimeError(ValueError):
    """The explicitly selected agent mode cannot be composed safely."""


class _StrictDeepSeekClient:
    """Turn client faults or non-canonical suggestions into the agent fallback path."""

    def __init__(
        self,
        delegate: object,
        *,
        stage_trace: StageTraceSink | None = None,
        response_reserve_seconds: float = MODEL_RESPONSE_RESERVE_SECONDS,
    ) -> None:
        self._delegate = delegate
        self._stage_trace = stage_trace
        self._response_reserve_seconds = max(0.0, float(response_reserve_seconds))
        self.last_outcome: str | None = None
        self._decision_deadline: DecisionDeadline | None = None
        self._worker_lock = threading.Lock()
        self._worker_active = False

    @property
    def decision_deadline(self) -> DecisionDeadline | None:
        return self._decision_deadline

    def set_decision_deadline(self, deadline: DecisionDeadline | float | None) -> None:
        if deadline is None or isinstance(deadline, DecisionDeadline):
            self._decision_deadline = deadline
        else:
            self._decision_deadline = DecisionDeadline(deadline)

    def suggest_action_id(self, **kwargs: object) -> object:
        from agents.deepseek_client import DeepSeekSuggestion

        self.last_outcome = None
        record_stage(self._stage_trace, "model_enter", "started")
        deadline = self._decision_deadline
        if deadline is not None:
            return self._suggest_with_deadline(kwargs, deadline)
        try:
            suggestion = self._delegate.suggest_action_id(**kwargs)  # type: ignore[attr-defined]
        except TimeoutError:
            self.last_outcome = "timeout"
            record_stage(self._stage_trace, "model_complete", "timeout")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        except Exception:
            self.last_outcome = "exception"
            record_stage(self._stage_trace, "model_complete", "exception")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        action_id = getattr(suggestion, "action_id", None)
        legal_actions = kwargs.get("legal_actions")
        if type(action_id) is not int or not isinstance(legal_actions, list):
            self.last_outcome = "invalid_suggestion"
            record_stage(self._stage_trace, "model_complete", "invalid_suggestion")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        legal_ids = {
            action.get("action_id")
            for action in legal_actions
            if isinstance(action, dict) and type(action.get("action_id")) is int
        }
        if action_id not in legal_ids:
            self.last_outcome = "invalid_suggestion"
            record_stage(self._stage_trace, "model_complete", "invalid_suggestion")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        # The connector only needs the canonical public action ID.  Dropping
        # free-form model text keeps it out of the match-scoped agent cache.
        self.last_outcome = "success"
        record_stage(self._stage_trace, "model_complete", "success")
        return DeepSeekSuggestion(action_id=action_id, reasoning=None)

    def _suggest_with_deadline(
        self,
        kwargs: dict[str, object],
        deadline: DecisionDeadline,
    ) -> object:
        from agents.deepseek_client import DeepSeekSuggestion

        try:
            deadline.check(reserve_seconds=self._response_reserve_seconds)
        except TimeoutError:
            deadline.cancel()
            self.last_outcome = "timeout"
            record_stage(self._stage_trace, "model_complete", "timeout")
            return DeepSeekSuggestion(action_id=None, reasoning=None)

        with self._worker_lock:
            if self._worker_active:
                self.last_outcome = "timeout"
                record_stage(self._stage_trace, "model_complete", "timeout")
                return DeepSeekSuggestion(action_id=None, reasoning=None)
            self._worker_active = True

        completed = threading.Event()
        result: dict[str, object] = {}

        def invoke() -> None:
            try:
                call_kwargs = dict(kwargs)
                call_kwargs["decision_deadline"] = deadline
                result["suggestion"] = self._delegate.suggest_action_id(**call_kwargs)  # type: ignore[attr-defined]
            except BaseException as exc:
                result["error"] = exc
            finally:
                with self._worker_lock:
                    self._worker_active = False
                completed.set()

        worker = threading.Thread(target=invoke, name="botzone-deepseek-decision", daemon=True)
        try:
            worker.start()
        except Exception:
            with self._worker_lock:
                self._worker_active = False
            self.last_outcome = "exception"
            record_stage(self._stage_trace, "model_complete", "exception")
            return DeepSeekSuggestion(action_id=None, reasoning=None)

        worker.join(deadline.remaining(reserve_seconds=self._response_reserve_seconds))
        if not completed.is_set() or deadline.is_expired(reserve_seconds=self._response_reserve_seconds):
            deadline.cancel()
            self.last_outcome = "timeout"
            record_stage(self._stage_trace, "model_complete", "timeout")
            return DeepSeekSuggestion(action_id=None, reasoning=None)

        error = result.get("error")
        if error is not None:
            self.last_outcome = "timeout" if isinstance(error, TimeoutError) else "exception"
            record_stage(self._stage_trace, "model_complete", self.last_outcome)
            return DeepSeekSuggestion(action_id=None, reasoning=None)

        suggestion = result.get("suggestion")
        action_id = getattr(suggestion, "action_id", None)
        legal_actions = kwargs.get("legal_actions")
        if type(action_id) is not int or not isinstance(legal_actions, list):
            self.last_outcome = "invalid_suggestion"
            record_stage(self._stage_trace, "model_complete", "invalid_suggestion")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        legal_ids = {
            action.get("action_id")
            for action in legal_actions
            if isinstance(action, dict) and type(action.get("action_id")) is int
        }
        if action_id not in legal_ids:
            self.last_outcome = "invalid_suggestion"
            record_stage(self._stage_trace, "model_complete", "invalid_suggestion")
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        self.last_outcome = "success"
        record_stage(self._stage_trace, "model_complete", "success")
        return DeepSeekSuggestion(action_id=action_id, reasoning=None)


def build_agent_factory(
    mode: str,
    *,
    config_loader: Callable[[], object] | None = None,
    client_factory: Callable[..., object] | None = None,
    deepseek_agent_factory: Callable[..., object] | None = None,
    rag_factory: Callable[[], object | None] | None = None,
    stage_trace: StageTraceSink | None = None,
) -> Callable[[int], object]:
    """Return a factory that creates one agent per handler match/player cache key."""

    if mode == "rule":
        from agents.rule_based_ai import RuleBasedAIAgent

        return lambda player_id: RuleBasedAIAgent(player_id=player_id)
    if mode == "conditional_pressure_pass":
        from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent

        return lambda player_id: ConditionalPressurePassAIAgent(player_id=player_id)
    if mode != "deepseek":
        raise AgentRuntimeError("invalid_agent_mode")

    from agents.deepseek_ai import DeepSeekAIAgent
    from agents.deepseek_client import DeepSeekClient
    from agents.rag_advisor import RAGAdvisor
    from config import AppConfig
    from rag.kb_loader import KnowledgeBaseLoader
    from rag.retriever import KnowledgeRetriever

    config = (config_loader or AppConfig.from_env)()
    api_key = getattr(config, "deepseek_api_key", None)
    if not isinstance(api_key, str) or not api_key:
        raise AgentRuntimeError("deepseek_configuration_unavailable")
    client = (client_factory or DeepSeekClient)(
        api_key=api_key,
        base_url=getattr(config, "deepseek_base_url"),
        model=getattr(config, "deepseek_model"),
        timeout_seconds=getattr(config, "deepseek_timeout"),
        max_retries=getattr(config, "deepseek_max_retries"),
    )
    strict_client = _StrictDeepSeekClient(client, stage_trace=stage_trace)
    if rag_factory is None:
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[2]
        loader = KnowledgeBaseLoader(project_root / "rag")
        rag_advisor: object | None = RAGAdvisor(KnowledgeRetriever(loader.load_all_documents()))
    else:
        rag_advisor = rag_factory()
    agent_builder = deepseek_agent_factory or DeepSeekAIAgent

    def create(player_id: int) -> object:
        return agent_builder(
            player_id=player_id,
            client=strict_client,
            rag_advisor=rag_advisor,
            verbose=False,
            hand_evaluation_enabled=bool(getattr(config, "hand_evaluation_enabled", False)),
            opening_formula_enabled=bool(getattr(config, "opening_formula_enabled", True)),
            card_confidence_shadow_enabled=False,
            card_confidence_prompt_enabled=False,
            strategy_router_shadow_enabled=True,
            strategy_intent_prompt_enabled=True,
        )

    return create


def prepare_agent_factory(
    mode: str,
    *,
    agent_factory_builder: Callable[[str], Callable[[int], object]] = build_agent_factory,
    stage_trace: StageTraceSink | None = None,
) -> Callable[[int], object] | None:
    """Validate the selected local agent composition before transport exists."""

    if mode == "rule":
        return None
    if mode not in {"deepseek", "conditional_pressure_pass"}:
        raise AgentRuntimeError("invalid_agent_mode")
    try:
        if stage_trace is not None and agent_factory_builder is build_agent_factory:
            factory = agent_factory_builder(mode, stage_trace=stage_trace)
        else:
            factory = agent_factory_builder(mode)
        # DeepSeekAIAgent completes its local configuration in __post_init__.
        # A disposable instance proves that path without selecting an action.
        factory(1)
    except Exception as exc:
        category = "deepseek_configuration_unavailable" if mode == "deepseek" else "conditional_pressure_pass_composition_unavailable"
        raise AgentRuntimeError(category) from exc
    return factory
