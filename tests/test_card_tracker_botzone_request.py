from __future__ import annotations

import json
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame
from integrations.botzone.agent_runtime import build_agent_factory


def _card(token: str) -> Card:
    return Card(token) if token in {"SJ", "BJ"} else Card(token[:-1], token[-1])


def _game() -> GuanDanGame:
    deck = build_double_deck()
    target = [_card(token) for token in ("4S", "4H", "5S", "5H", "6S", "6H", "3S", "SJ")]
    for card in target:
        deck.remove(card)
    filler = []
    for card in tuple(deck):
        if card.rank in {"8", "10", "Q", "A", "2"} and not (card.rank == "2" and card.suit == "H"):
            filler.append(card)
            deck.remove(card)
            if len(filler) == 19:
                break
    own = target + filler
    remaining = deck
    return GuanDanGame(
        preset_hands={
            1: tuple(own), 2: tuple(remaining[:27]),
            3: tuple(remaining[27:54]), 4: tuple(remaining[54:81]),
        },
        current_level_rank="2",
    )


class CardTrackerBotzoneRequestTests(unittest.TestCase):
    def test_default_botzone_factory_sends_bounded_closed_m3_request_and_keeps_model_id(self) -> None:
        game = _game()
        observation = game.reset()
        legal_actions = game.legal_actions()
        captured_prompts: list[str] = []
        response_ids: list[int] = []
        transport_calls: list[int] = []

        def fake_transport(request, _timeout):
            transport_calls.append(1)
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][1]["content"]
            captured_prompts.append(prompt)
            candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
            answer_id = int(re.search(r"action_id=(\d+)", candidate_section).group(1))
            response_ids.append(answer_id)
            content = json.dumps({"action_id": answer_id, "reason": "synthetic"})
            event = json.dumps({"choices": [{"delta": {"content": content}}]})
            return f"data: {event}\n\ndata: [DONE]\n\n"

        config = SimpleNamespace(
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://example.invalid",
            deepseek_model="synthetic-model",
            deepseek_timeout=2.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
            card_tracking_enabled=True,
        )
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_transport),
            rag_factory=lambda: None,
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = factory(1)
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(transport_calls, [1])
        self.assertEqual(chosen, response_ids[0])
        self.assertIn(chosen, {action["action_id"] for action in legal_actions})
        self.assertEqual(agent.last_decision_source, "model")
        prompt = captured_prompts[0]
        self.assertIn("证据级=E1精确牌池/多人未分配", prompt)
        self.assertIn("M3候选对照", prompt)

        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        candidate_ids = {int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)}
        self.assertLessEqual(len(candidate_ids), 80)
        m3_pairs = re.findall(r"M3候选对照 action_id=(\d+).*?action_id=(\d+)", prompt)
        self.assertTrue(m3_pairs)
        for pair in m3_pairs:
            self.assertTrue(all(int(value) in candidate_ids for value in pair))
        recommendation = re.search(r"优先核验候选 action_id：([^\n]+)", prompt)
        if recommendation:
            self.assertTrue(all(int(value) in candidate_ids for value in re.findall(r"\d+", recommendation.group(1))))


if __name__ == "__main__":
    unittest.main()
