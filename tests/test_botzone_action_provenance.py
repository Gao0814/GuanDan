from __future__ import annotations

import unittest
from pathlib import Path
import re

from integrations.botzone.cards import card_id_for
from integrations.botzone.models import GlobalState, PlayRequest
from integrations.botzone.play_adapter import AdapterError, NoTributeRuleBasedHandler
from integrations.botzone.session import HandlerContext


def _context() -> HandlerContext:
    return HandlerContext(
        match_key="unit",
        request_digest="digest",
        request=PlayRequest((), (), -1, GlobalState("2", 0, None, None, False)),
        local_player_id=0,
        own_hand=(card_id_for("3", "h"), card_id_for("4", "d")),
        history=(),
        latest_window=(),
        global_state=GlobalState("2", 0, None, None, False),
        finished=False,
    )


class _SpyAgent:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.observation: dict[str, object] | None = None
        self.legal_actions: list[dict[str, object]] | None = None

    def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> object:
        self.observation = observation
        self.legal_actions = legal_actions
        return self.answer


class BotzoneActionProvenanceTests(unittest.TestCase):
    def test_agent_receives_only_public_tokens_and_selected_provenance_is_rechecked(self) -> None:
        spy = _SpyAgent(1)
        handler = NoTributeRuleBasedHandler(lambda _: spy)
        result = handler(_context())
        self.assertIsNotNone(spy.observation)
        assert spy.observation is not None
        self.assertNotIn("match_key", spy.observation)
        self.assertNotIn("request_digest", spy.observation)
        self.assertNotIn("session", repr(spy.observation).lower())
        self.assertEqual(result.effect.action, tuple(__import__("json").loads(result.response)[0]))

    def test_non_integer_stale_and_exceptional_agent_answers_fail_closed(self) -> None:
        for answer in (True, "1", 1.0, 999):
            with self.subTest(answer=answer):
                with self.assertRaises(AdapterError):
                    NoTributeRuleBasedHandler(lambda _: _SpyAgent(answer))(_context())

        class Exploding:
            def select_action(self, observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
                raise RuntimeError("boom")

        with self.assertRaises(AdapterError):
            NoTributeRuleBasedHandler(lambda _: Exploding())(_context())

    def test_adapter_has_no_network_or_configuration_dependencies(self) -> None:
        source = (Path(__file__).parents[1] / "integrations" / "botzone" / "play_adapter.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?m)^\s*(?:from|import)\s+(?:urllib|requests|socket|dotenv|cli)\b", source))
        for marker in (".env", "api_key", "http://", "https://", "deepseek", "evaluation", "rag"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source.lower())


if __name__ == "__main__":
    unittest.main()
