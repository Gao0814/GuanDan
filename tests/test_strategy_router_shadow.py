from copy import deepcopy
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from agents.game_phase import MIDGAME, GamePhaseContext
from agents.strategy_router import StrategyIntentContext


def _action(action_id: int, pattern: str = "single", carrier_cards: list[str] | None = None) -> dict[str, object]:
    cards = ["9S"] if carrier_cards is None else list(carrier_cards)
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"],
        "carrier_cards": [] if pattern == "pass" else cards,
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


def _phase() -> GamePhaseContext:
    return GamePhaseContext(MIDGAME, 5, (5, 5, 5), 15, 9, 0)


def _hand_evaluation() -> dict[str, object]:
    return {"total_score": 50, "control_score": 10, "label": "中等"}


def _intent(status: str = "available") -> StrategyIntentContext:
    return StrategyIntentContext(
        status=status,
        source="public_strategy_router_v1",
        phase=MIDGAME,
        intent="control" if status == "available" else None,
        reason_codes=("stable_control",) if status == "available" else (),
        my_player_id=1 if status == "available" else None,
        my_team="team_13" if status == "available" else None,
        my_hand_count=5 if status == "available" else None,
        teammate_player_id=3 if status == "available" else None,
        teammate_hand_count=5 if status == "available" else None,
        minimum_opponent_hand_count=5 if status == "available" else None,
        urgent_opponent_ids=(),
        can_finish_now=False,
        is_free_lead=True if status == "available" else False,
        table_leader_player_id=None,
        table_leader_relation=None,
        table_leader_is_urgent=False,
        hand_strength="non_weak" if status == "available" else None,
        hand_total_score=50 if status == "available" else None,
        hand_control_score=10 if status == "available" else None,
        diagnostics=() if status == "available" else ("invalid_observation",),
    )


class RecordingClient:
    def __init__(self, action_id: int | None = 1, *, capture_prompt: bool = False) -> None:
        self.action_id = action_id
        self.capture_prompt = capture_prompt
        self.calls: list[dict[str, object]] = []
        self.prompts: list[str] = []

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.calls.append(kwargs)
        if self.capture_prompt:
            self.prompts.append(DeepSeekClient._build_structured_prompt(**kwargs))
        return DeepSeekSuggestion(action_id=self.action_id, reasoning=None)


class TestStrategyRouterShadow(unittest.TestCase):
    def _agent(self, client: RecordingClient, **kwargs: object) -> DeepSeekAIAgent:
        return DeepSeekAIAgent(
            player_id=1,
            client=client,
            opening_formula_enabled=False,
            hand_evaluation_enabled=False,
            **kwargs,
        )

    def test_default_strict_bool_and_reset_contract(self) -> None:
        agent = self._agent(RecordingClient())
        self.assertFalse(agent.strategy_router_shadow_enabled)
        self.assertIsNone(agent.last_strategy_intent)
        for value in (1, 0, "true", ""):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    self._agent(RecordingClient(), strategy_router_shadow_enabled=value)
        agent.last_strategy_intent = _intent()
        with self.assertRaises(ValueError):
            agent.select_action(_observation(), [])
        self.assertIsNone(agent.last_strategy_intent)

    def test_local_shortcuts_skip_router_and_evaluation(self) -> None:
        agent = self._agent(RecordingClient(), strategy_router_shadow_enabled=True)
        with mock.patch("agents.strategy_router.route_strategy_intent") as router, mock.patch(
            "agents.deepseek_ai.evaluate_hand"
        ) as evaluate:
            self.assertEqual(agent.select_action(_observation(), [_action(1, "pass")]), 1)
            self.assertEqual(agent.select_action(_observation(hand_count=2), [_action(2, "pair", ["9S", "9H"])]), 2)
        router.assert_not_called()
        evaluate.assert_not_called()

    def test_opening_formula_shortcut_skips_router(self) -> None:
        agent = DeepSeekAIAgent(
            player_id=1,
            client=RecordingClient(),
            opening_formula_enabled=True,
            hand_evaluation_enabled=False,
            strategy_router_shadow_enabled=True,
        )
        with mock.patch("agents.deepseek_ai.OpeningFormulaStrategy.select_action", return_value=1), mock.patch(
            "agents.strategy_router.route_strategy_intent"
        ) as router:
            self.assertEqual(agent.select_action(_observation(), [_action(1), _action(2)]), 1)
        router.assert_not_called()
        self.assertIsNone(agent.last_strategy_intent)

    def test_shadow_on_uses_same_phase_original_actions_and_available_or_unavailable_audit(self) -> None:
        client = RecordingClient()
        agent = self._agent(client, strategy_router_shadow_enabled=True)
        observation = _observation()
        actions = [_action(1), _action(2, "pair", ["8S", "8H"])]
        phase = _phase()
        evaluation = _hand_evaluation()
        with mock.patch("agents.deepseek_ai.classify_game_phase", return_value=phase) as classify, mock.patch(
            "agents.deepseek_ai.evaluate_hand", return_value=evaluation
        ) as evaluate, mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()) as router:
            self.assertEqual(agent.select_action(observation, actions), 1)
        classify.assert_called_once_with(observation)
        evaluate.assert_called_once_with(observation, actions)
        router.assert_called_once_with(observation, actions, phase_context=phase, hand_evaluation=evaluation)
        self.assertIs(agent.last_strategy_intent, router.return_value)
        self.assertIsNone(client.calls[0]["hand_evaluation"])

        unavailable = _intent("unavailable")
        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=unavailable):
            self.assertEqual(agent.select_action(observation, actions), 1)
        self.assertIs(agent.last_strategy_intent, unavailable)

    def test_existing_hand_evaluation_is_reused_by_client_and_router_once(self) -> None:
        client = RecordingClient()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            opening_formula_enabled=False,
            hand_evaluation_enabled=True,
            strategy_router_shadow_enabled=True,
        )
        observation, actions, phase, evaluation = _observation(), [_action(1), _action(2)], _phase(), _hand_evaluation()
        with mock.patch("agents.deepseek_ai.classify_game_phase", return_value=phase), mock.patch(
            "agents.deepseek_ai.evaluate_hand", return_value=evaluation
        ) as evaluate, mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()) as router:
            self.assertEqual(agent.select_action(observation, actions), 1)
        evaluate.assert_called_once_with(observation, actions)
        self.assertIs(router.call_args.kwargs["hand_evaluation"], client.calls[0]["hand_evaluation"])

    def test_router_and_evaluation_exceptions_do_not_change_model_or_fallback(self) -> None:
        observation, actions = _observation(), [_action(1), _action(2)]
        client = RecordingClient(1)
        agent = self._agent(client, strategy_router_shadow_enabled=True)
        with mock.patch("agents.strategy_router.route_strategy_intent", side_effect=RuntimeError("shadow")):
            self.assertEqual(agent.select_action(observation, actions), 1)
        self.assertIsNone(agent.last_strategy_intent)
        self.assertEqual(agent.last_decision_source, "model")

        client = RecordingClient(None)
        agent = self._agent(client, strategy_router_shadow_enabled=True)
        with mock.patch("agents.deepseek_ai.evaluate_hand", side_effect=RuntimeError("shadow")), mock.patch(
            "agents.strategy_router.route_strategy_intent"
        ) as router:
            off_action = agent.select_action(observation, actions)
        router.assert_not_called()
        self.assertIsNone(agent.last_strategy_intent)
        self.assertIn(off_action, {1, 2})
        self.assertEqual(agent.last_decision_source, "model")

    def test_shadow_off_on_preserves_client_kwargs_actions_and_inputs(self) -> None:
        observation = _observation()
        actions = [_action(1), _action(2, "pair", ["8S", "8H"])]
        before = (deepcopy(observation), deepcopy(actions))
        off_client, on_client = RecordingClient(1, capture_prompt=True), RecordingClient(1, capture_prompt=True)
        off = self._agent(off_client)
        on = self._agent(on_client, strategy_router_shadow_enabled=True)
        with mock.patch("agents.strategy_router.route_strategy_intent", return_value=_intent()):
            self.assertEqual(off.select_action(observation, actions), on.select_action(observation, actions))
        self.assertEqual(off_client.calls, on_client.calls)
        self.assertEqual(off_client.prompts, on_client.prompts)
        self.assertEqual(off.last_decision_source, on.last_decision_source)
        self.assertIsNone(off.last_strategy_intent)
        self.assertIsNotNone(on.last_strategy_intent)
        self.assertEqual((observation, actions), before)


if __name__ == "__main__":
    unittest.main()
