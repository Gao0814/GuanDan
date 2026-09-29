from __future__ import annotations

import json
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient
from agents.short_endgame_planner import free_lead_grouping_comparison_pairs
from evaluation.short_endgame_scenarios import build_short_endgame_scenarios
from integrations.botzone.agent_runtime import build_agent_factory


class _CapturingSSETransport:
    """Capture the production Request in memory and return one legal fake ID."""

    def __init__(self) -> None:
        self.chosen_id: int | None = None
        self.choice_index = 0
        self.returned_id: int | None = None
        self.calls = 0
        self.candidate_ids: tuple[int, ...] = ()
        self.route_ids: tuple[int, ...] = ()
        self.prompt = ""

    def __call__(self, request: object, timeout: float) -> str:
        self.calls += 1
        body = getattr(request, "data", None)
        if not isinstance(body, bytes):
            raise OSError("request_body_missing")
        envelope = json.loads(body.decode("utf-8"))
        messages = envelope.get("messages")
        if not isinstance(messages, list):
            raise OSError("request_messages_missing")
        user_messages = [
            item for item in messages
            if isinstance(item, dict) and item.get("role") == "user"
        ]
        if len(user_messages) != 1 or not isinstance(user_messages[0].get("content"), str):
            raise OSError("request_user_prompt_missing")
        self.prompt = user_messages[0]["content"]
        start = self.prompt.find("【候选动作】")
        end = self.prompt.find("【规则库依据】")
        if start < 0 or end <= start:
            raise OSError("request_candidate_section_missing")
        rows = re.findall(r"#(\d+)\s+action_id=(\d+)\s+\|", self.prompt[start:end])
        if not rows or any(left != right for left, right in rows):
            raise OSError("request_candidate_rows_invalid")
        self.candidate_ids = tuple(int(left) for left, _ in rows)

        route_start = self.prompt.find("【残局出后分组路线】")
        route_end = self.prompt.find("【规则库依据】", route_start)
        if route_start < 0 or route_end <= route_start:
            raise OSError("request_route_section_missing")
        route_text = self.prompt[route_start:route_end]
        if "不保证取得牌权或必然走完" not in route_text:
            raise OSError("request_route_caveat_missing")
        route_rows = re.findall(
            r"action_id=(\d+).*?出后剩余手牌最少后续组数=(\d+)",
            route_text,
        )
        if len(route_rows) < 2:
            raise OSError("request_route_rows_missing")
        self.route_ids = tuple(int(action_id) for action_id, _ in route_rows)
        if len(self.route_ids) > 4 or not set(self.route_ids).issubset(self.candidate_ids):
            raise OSError("request_route_candidates_mismatch")
        if self.chosen_id is None:
            if self.choice_index >= len(self.route_ids):
                raise OSError("fake_route_choice_missing")
            selected_id = self.route_ids[self.choice_index]
        else:
            selected_id = self.chosen_id
        if selected_id not in self.candidate_ids:
            raise OSError("fake_choice_not_displayed")
        self.returned_id = selected_id

        content = json.dumps({"action_id": selected_id}, separators=(",", ":"))
        event = json.dumps({"choices": [{"delta": {"content": content}}]})
        return f"data: {event}\n\ndata: [DONE]\n"


class ShortEndgameModelInputTests(unittest.TestCase):
    def test_default_botzone_factory_request_protects_routes_and_preserves_both_model_choices(self) -> None:
        config = SimpleNamespace(
            deepseek_api_key="offline-only",
            deepseek_base_url="https://offline.invalid",
            deepseek_model="offline-only",
            deepseek_timeout=1.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=True,
            opening_formula_enabled=True,
            card_tracking_enabled=False,
        )
        transport = _CapturingSSETransport()

        def client_factory(**kwargs: object) -> DeepSeekClient:
            return DeepSeekClient(**kwargs, transport=transport)  # type: ignore[arg-type]

        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            factory = build_agent_factory(
                "deepseek",
                config_loader=lambda: config,
                client_factory=client_factory,
            )
            scenarios = build_short_endgame_scenarios()
            request_count = 0
            for scenario in scenarios:
                with self.subTest(scenario=scenario.name):
                    original_ids = {int(item["action_id"]) for item in scenario.legal_actions}
                    route_pairs = free_lead_grouping_comparison_pairs(
                        scenario.observation,
                        scenario.legal_actions,
                        1,
                    )
                    self.assertTrue(route_pairs)
                    agent = factory(1)
                    transport.chosen_id = None
                    transport.choice_index = 0
                    actual_id = agent.select_action(scenario.observation, scenario.legal_actions)
                    selected_id = transport.returned_id
                    request_count += 1

                    self.assertIsNotNone(selected_id)
                    self.assertEqual(actual_id, selected_id)
                    self.assertEqual(agent.last_decision_source, "model")
                    self.assertEqual(agent.client.last_outcome, "success")
                    self.assertIn(selected_id, original_ids)
                    self.assertLessEqual(len(transport.candidate_ids), 80)
                    self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
                    self.assertTrue(set(transport.candidate_ids).issubset(original_ids))
                    self.assertTrue(set(transport.route_ids).issubset(transport.candidate_ids))
                    experience_section = transport.prompt.split("【经验库依据】", 1)[1].split("【输出格式】", 1)[0]
                    if scenario.name in {"natural_bomb_residual", "wildcard_and_natural_groups"}:
                        self.assertTrue(
                            "残局规划" in experience_section
                            or "炸弹与通配牌管理" in experience_section
                        )
                        if "炸弹与通配牌管理" in experience_section:
                            self.assertIn("可撤回软假设", experience_section)
                    else:
                        self.assertIn("残局规划", experience_section)

                    first_selected_id = selected_id
                    transport.choice_index = 1
                    actual_id = agent.select_action(scenario.observation, scenario.legal_actions)
                    selected_id = transport.returned_id
                    request_count += 1

                    self.assertIsNotNone(selected_id)
                    self.assertEqual(actual_id, selected_id)
                    self.assertEqual(agent.last_decision_source, "model")
                    self.assertEqual(agent.client.last_outcome, "success")
                    self.assertIn(selected_id, original_ids)
                    self.assertLessEqual(len(transport.candidate_ids), 80)
                    self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
                    self.assertTrue(set(transport.candidate_ids).issubset(original_ids))
                    self.assertTrue(set(transport.route_ids).issubset(transport.candidate_ids))
                    self.assertNotEqual(selected_id, first_selected_id)

                    recommendation = agent.last_strategy_recommendation
                    self.assertIsNotNone(recommendation)
                    recommendation_ids = tuple(getattr(recommendation, "action_ids", ()))
                    self.assertTrue(set(recommendation_ids).issubset(transport.candidate_ids))
                    self.assertIn("endgame_planning", recommendation.strategy_domains)
                    self.assertIn("plan_endgame", recommendation.objective_codes)

                    context = agent.last_strategy_intent
                    self.assertIsNotNone(context)
                    if scenario.name == "urgent_teammate":
                        self.assertEqual(context.reason_codes, ("teammate_urgent",))
                        self.assertIn("分组少不自动优先", transport.prompt)
                    elif scenario.name == "urgent_opponent":
                        self.assertEqual(context.reason_codes, ("opponent_urgent",))
                        self.assertIn("分组少不自动优先", transport.prompt)

            self.assertEqual(transport.calls, request_count)
            self.assertEqual(request_count, 2 * len(scenarios))


if __name__ == "__main__":
    unittest.main()
