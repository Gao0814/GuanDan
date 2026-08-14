"""Explicit, match-safe agent composition for the Botzone connector."""

from __future__ import annotations

from collections.abc import Callable


class AgentRuntimeError(ValueError):
    """The explicitly selected agent mode cannot be composed safely."""


class _StrictDeepSeekClient:
    """Turn client faults or non-canonical suggestions into the agent fallback path."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def suggest_action_id(self, **kwargs: object) -> object:
        from agents.deepseek_client import DeepSeekSuggestion

        try:
            suggestion = self._delegate.suggest_action_id(**kwargs)  # type: ignore[attr-defined]
        except Exception:
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        action_id = getattr(suggestion, "action_id", None)
        legal_actions = kwargs.get("legal_actions")
        if type(action_id) is not int or not isinstance(legal_actions, list):
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        legal_ids = {
            action.get("action_id")
            for action in legal_actions
            if isinstance(action, dict) and type(action.get("action_id")) is int
        }
        if action_id not in legal_ids:
            return DeepSeekSuggestion(action_id=None, reasoning=None)
        # The connector only needs the canonical public action ID.  Dropping
        # free-form model text keeps it out of the match-scoped agent cache.
        return DeepSeekSuggestion(action_id=action_id, reasoning=None)


def build_agent_factory(
    mode: str,
    *,
    config_loader: Callable[[], object] | None = None,
    client_factory: Callable[..., object] | None = None,
    deepseek_agent_factory: Callable[..., object] | None = None,
    rag_factory: Callable[[], object | None] | None = None,
) -> Callable[[int], object]:
    """Return a factory that creates one agent per handler match/player cache key."""

    if mode == "rule":
        from agents.rule_based_ai import RuleBasedAIAgent

        return lambda player_id: RuleBasedAIAgent(player_id=player_id)
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
    strict_client = _StrictDeepSeekClient(client)
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
            strategy_router_shadow_enabled=False,
            strategy_intent_prompt_enabled=False,
        )

    return create


def prepare_agent_factory(
    mode: str,
    *,
    agent_factory_builder: Callable[[str], Callable[[int], object]] = build_agent_factory,
) -> Callable[[int], object] | None:
    """Validate the selected local agent composition before transport exists."""

    if mode == "rule":
        return None
    if mode != "deepseek":
        raise AgentRuntimeError("invalid_agent_mode")
    try:
        factory = agent_factory_builder(mode)
        # DeepSeekAIAgent completes its local configuration in __post_init__.
        # A disposable instance proves that path without selecting an action.
        factory(1)
    except Exception as exc:
        raise AgentRuntimeError("deepseek_configuration_unavailable") from exc
    return factory
