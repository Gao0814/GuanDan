"""Minimal DeepSeek client for legal-action suggestion support."""

import json
from typing import Protocol
from urllib import request as urllib_request

from agents.base import AgentContext
from engine.actions import Action
from engine.state import GameState


class DeepSeekTransport(Protocol):
    """Transport protocol for dependency-injected HTTP calls in tests."""

    def __call__(self, request: urllib_request.Request, timeout: float) -> str:
        ...


def _default_transport(req: urllib_request.Request, timeout: float) -> str:
    with urllib_request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


class DeepSeekClient:
    """Minimal one-shot client for DeepSeek chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 5.0,
        transport: DeepSeekTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("deepseek api key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport: DeepSeekTransport = transport or _default_transport

    @staticmethod
    def _action_to_dict(action: Action) -> dict[str, object]:
        return {
            "action_type": action.action_type.value,
            "declared_pattern": action.declared_pattern.value if action.declared_pattern else None,
            "cards": [f"{card.rank}{card.suit or ''}" for card in action.cards],
        }

    @staticmethod
    def _extract_suggested_action(content: str) -> dict[str, object] | None:
        if not content:
            return None

        parsed: object
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None

        if isinstance(parsed, dict) and isinstance(parsed.get("suggested_action"), dict):
            return parsed["suggested_action"]
        if isinstance(parsed, dict):
            if {"action_type", "declared_pattern", "cards"}.issubset(parsed.keys()):
                return parsed
        return None

    @staticmethod
    def _build_action_focus(legal_actions: tuple[Action, ...]) -> dict[str, object]:
        preferred_patterns: list[str] = []
        for pattern_name in ("straight", "pair_straight", "triple_with_pair"):
            if any(
                action.declared_pattern is not None and action.declared_pattern.value == pattern_name
                for action in legal_actions
            ):
                preferred_patterns.append(pattern_name)

        has_bomb = any(
            action.declared_pattern is not None and action.declared_pattern.value == "bomb"
            for action in legal_actions
        )
        has_non_bomb_play = any(
            action.action_type.value == "play"
            and (action.declared_pattern is None or action.declared_pattern.value != "bomb")
            for action in legal_actions
        )

        return {
            "preferred_patterns": preferred_patterns[:3],
            "avoid_low_value_single_when_compound_exists": bool(preferred_patterns),
            "avoid_unnecessary_bomb": bool(has_bomb and has_non_bomb_play),
        }

    def suggest_action(
        self,
        state: GameState,
        legal_actions: tuple[Action, ...],
        context: AgentContext,
        rag_context: dict[str, list[dict[str, str]]] | None = None,
    ) -> object:
        user_payload: dict[str, object] = {
            "step_no": context.step_no,
            "current_player_id": state.current_player_id,
            "legal_actions": [self._action_to_dict(action) for action in legal_actions],
            "action_focus": self._build_action_focus(legal_actions),
        }
        if rag_context is not None:
            user_payload["rag_context"] = rag_context

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是掼蛋动作建议器。"
                        "只能在给定 legal_actions 中选择一个动作。"
                        "优先不破坏高价值组合，选择少破组、少浪费、组合完整的动作。"
                        "存在 triple_with_pair / pair_straight / straight 时可优先复合牌型，"
                        "但不要为了出顺子而拆更高价值组合。"
                        "不要为了平滑出牌牺牲明显更优的保组动作。"
                        "避免无意义单张。"
                        "有合理非炸弹动作时不要先炸。"
                        "只返回 JSON，格式: {\"suggested_action\": {...}}。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            "temperature": 0,
        }

        req = urllib_request.Request(
            url=f"{self._base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        last_timeout: TimeoutError | None = None
        raw: str | None = None
        for _ in range(2):
            try:
                raw = self._transport(req, self._timeout_seconds)
                break
            except TimeoutError as exc:
                last_timeout = exc
        if raw is None:
            if last_timeout is not None:
                raise last_timeout
            raise RuntimeError("deepseek transport returned no response")

        body = json.loads(raw)
        choices = body.get("choices", []) if isinstance(body, dict) else []
        if not choices or not isinstance(choices[0], dict):
            return None

        message = choices[0].get("message")
        if not isinstance(message, dict):
            return None

        content = message.get("content")
        if not isinstance(content, str):
            return None

        return self._extract_suggested_action(content)
