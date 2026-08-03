from dataclasses import replace
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.card_confidence_prompt import CardConfidencePromptPayload
from agents.strategy_intent_prompt import build_strategy_intent_prompt_payload
from agents.strategy_router import StrategyIntentContext


def _action(action_id: int, pattern: str = "single", cards: list[str] | None = None) -> dict[str, object]:
    carrier_cards = ["9S"] if cards is None else list(cards)
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"],
        "carrier_cards": [] if pattern == "pass" else carrier_cards,
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": pattern,
    }


def _observation(*, hand_count: int = 5) -> dict[str, object]:
    return {
        "my_info": {
            "player_id": 1,
            "team": "team_13",
            "hand_cards": ["3S"] * hand_count,
            "hand_count": hand_count,
            "remaining_single_card_count": 3,
        },
        "current_round": {
            "step_no": 9,
            "round_no": 2,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 5, "finished": False},
            {"player_id": 3, "team": "team_13", "hand_count": 5, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": 5, "finished": False},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _intent(status: str = "available") -> StrategyIntentContext:
    available = status == "available"
    return StrategyIntentContext(
        status=status,
        source="public_strategy_router_v1",
        phase="midgame",
        intent="control" if available else None,
        reason_codes=("stable_control",) if available else (),
        my_player_id=1 if available else None,
        my_team="team_13" if available else None,
        my_hand_count=5 if available else None,
        teammate_player_id=3 if available else None,
        teammate_hand_count=5 if available else None,
        minimum_opponent_hand_count=5 if available else None,
        urgent_opponent_ids=(),
        can_finish_now=False,
        is_free_lead=available,
        table_leader_player_id=None,
        table_leader_relation=None,
        table_leader_is_urgent=False,
        hand_strength="non_weak" if available else None,
        hand_total_score=50 if available else None,
        hand_control_score=10 if available else None,
        diagnostics=() if available else ("invalid_observation",),
    )


class _Client:
    def __init__(self, action_id: int | None = 1) -> None:
        self.action_id = action_id
        self.calls: list[dict[str, object]] = []

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.calls.append(kwargs)
        return DeepSeekSuggestion(action_id=self.action_id, reasoning=None)


class TestStrategyIntentPromptWiring(unittest.TestCase):
    def _agent(self, client: _Client, **kwargs: object) -> DeepSeekAIAgent:
        hand_evaluation_enabled = kwargs.pop("hand_evaluation_enabled", False)
        opening_formula_enabled = kwargs.pop("opening_formula_enabled", False)
        return DeepSeekAIAgent(
            player_id=1,
            client=client,
            hand_evaluation_enabled=hand_evaluation_enabled,
            opening_formula_enabled=opening_formula_enabled,
            **kwargs,
        )

    def test_switch_contract_and_audit_reset(self) -> None:
        agent = self._agent(_Client())
        self.assertFalse(agent.strategy_router_shadow_enabled)
        self.assertFalse(agent.strategy_intent_prompt_enabled)
        self.assertIsNone(agent.last_strategy_intent)
        self.assertIsNone(agent.last_strategy_intent_prompt)
        for keyword in ("strategy_router_shadow_enabled", "strategy_intent_prompt_enabled"):
            for value in (1, 0, "true", "", object()):
                with self.subTest(keyword=keyword, value=repr(value)):
                    with self.assertRaises(ValueError):
                        self._agent(_Client(), **{keyword: value})  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self._agent(_Client(), strategy_intent_prompt_enabled=True)

        agent.last_strategy_intent = _intent()
        agent.last_strategy_intent_prompt = build_strategy_intent_prompt_payload(_intent())
        with self.assertRaises(ValueError):
            agent.select_action(_observation(), [])
        self.assertIsNone(agent.last_strategy_intent)
        self.assertIsNone(agent.last_strategy_intent_prompt)

    def test_local_shortcuts_skip_router_and_formatter(self) -> None:
        agent = self._agent(
            _Client(),
            opening_formula_enabled=True,
            strategy_router_shadow_enabled=True,
            strategy_intent_prompt_enabled=True,
        )
        with mock.patch("agents.strategy_router.route_strategy_intent") as router, mock.patch(
            "agents.strategy_intent_prompt.build_strategy_intent_prompt_payload"
        ) as formatter, mock.patch(
            "agents.deepseek_ai.OpeningFormulaStrategy.select_action", return_value=2
        ):
            self.assertEqual(agent.select_action(_observation(), [_action(1, "pass")]), 1)
            self.assertEqual(agent.select_action(_observation(hand_count=2), [_action(2, "pair", ["9S", "9H"])]), 2)
            self.assertEqual(agent.select_action(_observation(), [_action(1), _action(2)]), 2)
        router.assert_not_called()
        formatter.assert_not_called()
        self.assertIsNone(agent.last_strategy_intent)
        self.assertIsNone(agent.last_strategy_intent_prompt)

    def test_off_shadow_omitted_and_ready_kwargs_contract(self) -> None:
        observation = _observation()
        actions = [_action(1), _action(2, "pair", ["8S", "8H"])]
        clients = [_Client() for _ in range(4)]
        off = self._agent(clients[0])
        shadow = self._agent(clients[1], strategy_router_shadow_enabled=True)
        omitted = self._agent(
            clients[2], strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True
        )
        ready = self._agent(
            clients[3], strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True
        )
        ready_payload = build_strategy_intent_prompt_payload(_intent())
        omitted_payload = build_strategy_intent_prompt_payload(_intent("unavailable"))
        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()) as router, mock.patch(
            "agents.strategy_intent_prompt.build_strategy_intent_prompt_payload", return_value=omitted_payload
        ) as formatter:
            self.assertEqual(off.select_action(observation, actions), 1)
            self.assertEqual(shadow.select_action(observation, actions), 1)
            self.assertEqual(omitted.select_action(observation, actions), 1)
        self.assertEqual(router.call_count, 2)
        formatter.assert_called_once()
        self.assertEqual(clients[0].calls, clients[1].calls)
        self.assertEqual(clients[1].calls, clients[2].calls)
        self.assertEqual(off.last_decision_source, shadow.last_decision_source)
        self.assertEqual(shadow.last_decision_source, omitted.last_decision_source)
        self.assertIs(omitted.last_strategy_intent_prompt, omitted_payload)
        self.assertNotIn("strategy_intent_prompt", clients[2].calls[0])

        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()), mock.patch(
            "agents.strategy_intent_prompt.build_strategy_intent_prompt_payload", return_value=ready_payload
        ) as ready_formatter:
            self.assertEqual(ready.select_action(observation, actions), 1)
        ready_formatter.assert_called_once()
        ready_kwargs = clients[3].calls[0]
        self.assertEqual(set(ready_kwargs) - set(clients[1].calls[0]), {"strategy_intent_prompt"})
        self.assertEqual(
            {key: value for key, value in ready_kwargs.items() if key != "strategy_intent_prompt"},
            clients[1].calls[0],
        )
        self.assertIs(ready.last_strategy_intent_prompt, ready_payload)
        self.assertIs(ready_kwargs["strategy_intent_prompt"], ready_payload)

    def test_unavailable_and_shadow_exceptions_do_not_change_model_path(self) -> None:
        observation, actions = _observation(), [_action(1), _action(2)]
        off_client, on_client = _Client(), _Client()
        off = self._agent(off_client)
        on = self._agent(on_client, strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True)
        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent("unavailable")):
            self.assertEqual(off.select_action(observation, actions), on.select_action(observation, actions))
        self.assertIsNotNone(on.last_strategy_intent)
        self.assertEqual(on.last_strategy_intent_prompt.status, "omitted")
        self.assertEqual(off_client.calls, on_client.calls)

        with mock.patch("agents.strategy_router.route_strategy_intent", side_effect=RuntimeError("router")), mock.patch(
            "agents.strategy_intent_prompt.build_strategy_intent_prompt_payload"
        ) as formatter:
            self.assertEqual(on.select_action(observation, actions), 1)
        formatter.assert_not_called()
        self.assertIsNone(on.last_strategy_intent)
        self.assertIsNone(on.last_strategy_intent_prompt)

        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()), mock.patch(
            "agents.strategy_intent_prompt.build_strategy_intent_prompt_payload", side_effect=RuntimeError("formatter")
        ):
            self.assertEqual(on.select_action(observation, actions), 1)
        self.assertIsNotNone(on.last_strategy_intent)
        self.assertIsNone(on.last_strategy_intent_prompt)

    def test_client_validates_exact_payload_and_insertion_order(self) -> None:
        observation = _observation()
        kwargs = {
            "my_info": observation["my_info"],
            "current_round": observation["current_round"],
            "other_players": observation["other_players"],
            "history": observation["history"],
            "legal_actions": [_action(1)],
            "rag_context": None,
        }
        payload = build_strategy_intent_prompt_payload(_intent())
        baseline = DeepSeekClient._build_structured_prompt(**kwargs)
        self.assertEqual(baseline, DeepSeekClient._build_structured_prompt(**kwargs, strategy_intent_prompt=None))
        prompt = DeepSeekClient._build_structured_prompt(**kwargs, strategy_intent_prompt=payload)
        self.assertEqual(prompt.count("【策略意图】"), 1)
        self.assertEqual(prompt.count(payload.text), 1)
        self.assertLess(prompt.index("【记牌信息】"), prompt.index("【策略意图】"))
        self.assertLess(prompt.index("【策略意图】"), prompt.index("【场景标签】"))

        malformed = (
            object(),
            replace(payload, status="omitted"),
            replace(payload, source="wrong"),
            replace(payload, router_source="wrong"),
            replace(payload, phase="opening"),
            replace(payload, intent="unknown"),
            replace(payload, diagnostics=("x",)),
            replace(payload, text="", char_count=0),
            replace(payload, char_count=True),
            replace(payload, char_count=len(payload.text) - 1),
            replace(payload, char_count=801),
            replace(payload, text=payload.text + "\nextra", char_count=len(payload.text) + 6),
            replace(payload, text=payload.text.replace("公开依据：手牌控制力稳定", "公开依据：任意文本")),
            replace(payload, text=payload.text.replace("公开依据：手牌控制力稳定", "公开依据：对手接近出完")),
            replace(payload, text=payload.text.replace("边界：", "边界X：")),
        )
        for invalid in malformed:
            with self.subTest(invalid=invalid):
                self.assertEqual(
                    DeepSeekClient._build_structured_prompt(**kwargs, strategy_intent_prompt=invalid),
                    baseline,
                )

    def test_confidence_and_strategy_sections_coexist_in_fixed_order(self) -> None:
        observation = _observation()
        confidence_text = "范围：critical_endgame_policy_diverse_v1\n说明：固定 confidence 测试文本"
        confidence = CardConfidencePromptPayload(
            status="ready",
            text=confidence_text,
            char_count=len(confidence_text),
            source="physical_assignment_marginal_v1",
            calibration_scope="critical_endgame_policy_diverse_v1",
            diagnostics=(),
        )
        strategy = build_strategy_intent_prompt_payload(_intent())
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=[_action(1)],
            card_confidence_prompt=confidence,
            strategy_intent_prompt=strategy,
        )
        self.assertEqual(prompt.count("【残局牌面信念】"), 1)
        self.assertEqual(prompt.count("【策略意图】"), 1)
        self.assertLess(prompt.index("【记牌信息】"), prompt.index("【残局牌面信念】"))
        self.assertLess(prompt.index("【残局牌面信念】"), prompt.index("【策略意图】"))
        self.assertLess(prompt.index("【策略意图】"), prompt.index("【场景标签】"))


if __name__ == "__main__":
    unittest.main()
