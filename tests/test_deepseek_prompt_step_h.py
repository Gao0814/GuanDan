import json
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import (
    PROMPT_MAX_CANDIDATE_ACTIONS,
    PROMPT_MAX_RAG_BODY_CHARS,
    DeepSeekClient,
    DeepSeekSuggestion,
)


def _action(
    action_id: object,
    pattern: str,
    declared_cards: list[str],
    carrier_cards: list[str] | None = None,
    *,
    wildcard_count: int = 0,
    wildcard_info: list[dict[str, object]] | None = None,
    display_text: str | None = None,
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": declared_cards,
        "carrier_cards": carrier_cards if carrier_cards is not None else list(declared_cards),
        "wildcard_count": wildcard_count,
        "wildcard_info": wildcard_info or [],
        "display_text": display_text or (f"{pattern}:{','.join(declared_cards)}" if declared_cards else "pass"),
    }


def _observation(*, hand_count: int = 20, constraint: str = "free", step_no: int = 5) -> dict[str, object]:
    table_action = None
    if constraint != "free":
        table_action = _action(99, "single", ["8"], ["8S"], display_text="single:8")
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": ["3S"] * hand_count,
            "hand_count": hand_count,
            "remaining_single_card_count": 4,
        },
        "current_round": {
            "step_no": step_no,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": constraint,
            "table_action": table_action,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _rag_context() -> dict[str, object]:
    return {
        "scene_tags": {
            "scene": "follow_response",
            "phase": "midgame",
            "hand_strength": "medium",
            "action_context": "follow",
        },
        "rule_hits": [
            {
                "source_id": "rule:1",
                "layer": "rule",
                "snippet": "跟牌只能同型压制，或用炸弹 / 同花顺 / 天王炸跨型压制。",
                "metadata": {"status": "accepted"},
            }
        ],
        "experience_hits": [
            {
                "source_id": "exp:1",
                "layer": "experience",
                "snippet": "跟牌时要看压制收益和资源交换，不应机械交炸弹。",
                "metadata": {"status": "accepted"},
            }
        ],
        "query": "scene:follow_response phase:midgame hand_strength:medium",
    }


class CountingClient:
    def __init__(self, action_id: int | None = 1) -> None:
        self.calls = 0
        self.action_id = action_id

    def suggest_action_id(self, **_kwargs):
        self.calls += 1
        return DeepSeekSuggestion(action_id=self.action_id, reasoning="test")


class CountingRAGAdvisor:
    def __init__(self) -> None:
        self.calls = 0

    def get_rag_context(self, **_kwargs):
        self.calls += 1
        return _rag_context()


class TestDeepSeekPromptStepH(unittest.TestCase):
    def test_prompt_contains_fixed_sections(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=_rag_context(),
            hand_evaluation={"total_score": 55, "structure_score": 20, "control_score": 15, "potential_score": 20, "label": "中等", "comment": "结构一般"},
            card_tracking_summary="记牌摘要：9剩余较多",
        )

        sections = (
            "【任务与硬约束】",
            "【当前局面】",
            "【手牌评估】",
            "【记牌信息】",
            "【场景标签】",
            "【候选动作】",
            "【规则库依据】",
            "【经验库依据】",
            "【输出格式】",
        )
        for section in sections:
            self.assertIn(section, prompt)
        prompt_lines = prompt.splitlines()
        self.assertEqual([prompt_lines.index(section) for section in sections], sorted(prompt_lines.index(section) for section in sections))
        self.assertNotIn("【任务】", prompt)
        self.assertNotIn("【硬性规则】", prompt)

    def test_prompt_uses_scene_tags_rule_hits_and_experience_hits(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=_rag_context(),
        )

        self.assertIn("scene: follow_response", prompt)
        self.assertIn("rule:1", prompt)
        self.assertIn("跟牌只能同型压制", prompt)
        self.assertIn("exp:1", prompt)
        self.assertIn("跟牌时要看压制收益", prompt)
        self.assertLess(prompt.index("【规则库依据】"), prompt.index("【经验库依据】"))

    def test_prompt_candidate_actions_include_required_action_fields(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[
                _action(1, "single", ["9"], ["9S"], wildcard_count=0, display_text="single:9"),
                _action(2, "pair", ["7", "7"], ["7S", "7H"], wildcard_count=0, display_text="pair:7"),
            ],
            rag_context=_rag_context(),
        )

        self.assertIn("#1", prompt)
        self.assertIn("action_id=1", prompt)
        self.assertIn("declared_pattern=single", prompt)
        self.assertIn('carrier_cards=["9S"]', prompt)
        self.assertIn("wildcard_count=0", prompt)
        self.assertIn("display=single:9", prompt)

    def test_prompt_forbids_constructing_illegal_actions(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=_rag_context(),
        )

        self.assertIn("不得构造新动作", prompt)
        self.assertIn("不能替代 legal_actions", prompt)
        self.assertIn("不要输出候选列表以外的 action_id", prompt)

    def test_prompt_does_not_expose_engine_internal_state_names(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=_rag_context(),
        )

        self.assertNotIn("GameState", prompt)
        self.assertNotIn("PlayerState", prompt)
        self.assertNotIn("Action(", prompt)

    def test_prompt_builds_with_empty_rag_context(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context={"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""},
        )

        self.assertIn("【场景标签】", prompt)
        self.assertIn("（无）", prompt)
        self.assertIn("【规则库依据】", prompt)

    def test_prompt_omits_full_hand_history_and_duplicate_tracker_heading(self) -> None:
        observation = _observation()
        observation["history"] = {
            "actions": [{"step_no": 1, "player_id": 2, "declared_pattern": "single", "declared_cards": ["K"]}],
            "finish_order": [],
        }
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            card_tracking_summary="【记牌信息】\n外部剩余：60张",
        )

        self.assertNotIn("手牌明细", prompt)
        self.assertNotIn("最近历史", prompt)
        self.assertNotIn("玩家2 single K", prompt)
        self.assertEqual(prompt.count("【记牌信息】"), 1)

    def test_prompt_ignores_legacy_rag_keys(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context={
                "scene_tags": {},
                "rule": [{"source_id": "legacy-rule", "snippet": "旧规则文本"}],
                "experience": [{"source_id": "legacy-exp", "snippet": "旧经验文本"}],
            },
        )

        self.assertNotIn("legacy-rule", prompt)
        self.assertNotIn("legacy-exp", prompt)
        self.assertNotIn("旧规则文本", prompt)
        self.assertNotIn("旧经验文本", prompt)

    def test_rag_hits_are_independent_and_bounded(self) -> None:
        long_body = "规则正文" * 100
        rag_context = {
            "scene_tags": {"scene": "follow_response"},
            "rule_hits": [
                {
                    "source_id": f"rule:{index}",
                    "snippet": f"# 规则块{index}\n{long_body}",
                    "metadata": {"topic": "pass"},
                }
                for index in range(1, 5)
            ],
            "experience_hits": [
                {
                    "source_id": f"exp:{index}",
                    "snippet": f"# 经验块{index}\n经验正文{index}",
                    "metadata": {"topic": "follow_response"},
                }
                for index in range(1, 5)
            ],
        }
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=rag_context,
        )

        self.assertIn("规则块1", prompt)
        self.assertIn("规则块2", prompt)
        self.assertIn("规则块3", prompt)
        self.assertNotIn("规则块4", prompt)
        self.assertIn("经验块1", prompt)
        self.assertNotIn("经验块4", prompt)
        rule_line = next(line for line in prompt.splitlines() if "规则块1" in line)
        self.assertLessEqual(len(rule_line.split("：", 1)[-1]), PROMPT_MAX_RAG_BODY_CHARS + 1)

    def test_wildcard_candidate_preserves_carrier_and_wildcard_info(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[
                _action(
                    8,
                    "pair",
                    ["9", "9"],
                    ["9S", "2H"],
                    wildcard_count=1,
                    wildcard_info=[{"carrier_card": "2H", "declared_as": "9"}],
                )
            ],
        )

        self.assertIn('carrier_cards=["9S","2H"]', prompt)
        self.assertIn("wildcard_count=1", prompt)
        self.assertIn('wildcard_info=[{"carrier_card":"2H","declared_as":"9"}]', prompt)

    def test_prompt_preserves_original_action_id_representation(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action("action-A", "single", ["9"], ["9S"])],
        )

        self.assertIn('action_id="action-A"', prompt)

    def test_prompt_candidate_limit_is_stable_and_keeps_critical_actions(self) -> None:
        actions = [
            _action(index, "single", [str(index)], [f"{index}S"])
            for index in range(PROMPT_MAX_CANDIDATE_ACTIONS + 20)
        ]
        actions.extend(
            [
                _action(1001, "bomb", ["7"] * 4, ["7S", "7H", "7C", "7D"]),
                _action(1002, "pass", [], []),
            ]
        )
        observation = _observation(constraint="single:8")
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"],
            current_round=observation["current_round"],
            other_players=observation["other_players"],
            history=observation["history"],
            legal_actions=actions,
        )

        self.assertIn("action_id=1001", prompt)
        self.assertIn("action_id=1002", prompt)
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        self.assertEqual(candidate_section.count("action_id="), PROMPT_MAX_CANDIDATE_ACTIONS)

    def test_empty_optional_context_still_builds_prompt(self) -> None:
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=_observation()["my_info"],
            current_round=_observation()["current_round"],
            other_players=_observation()["other_players"],
            history=_observation()["history"],
            legal_actions=[_action(1, "single", ["9"], ["9S"])],
            rag_context=None,
            hand_evaluation=None,
            card_tracking_summary=None,
        )

        self.assertIn("【手牌评估】\n（无）", prompt)
        self.assertIn("【记牌信息】\n（无）", prompt)
        self.assertIn("【规则库依据】", prompt)

    def test_existing_json_response_parser_remains_compatible(self) -> None:
        parsed = DeepSeekClient._extract_json('{"action_id": 7, "reason": "简短理由"}')
        self.assertEqual(DeepSeekClient._extract_action_id(parsed), 7)

    def test_client_prompt_uses_pruned_candidate_actions(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else {}
            return "data: {\"choices\":[{\"delta\":{\"content\":\"{\\\"action_id\\\": 3}\"}}]}\ndata: [DONE]\n"

        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["4"], ["4S"]),
            _action(3, "single", ["5"], ["5S"]),
            _action(4, "single", ["6"], ["6S"]),
            _action(5, "single", ["7"], ["7S"]),
        ]
        client = DeepSeekClient("test-key", "https://api.deepseek.com", "deepseek-chat", transport=transport)

        suggestion = client.suggest_action_id(
            observation=_observation(),
            legal_actions=legal_actions,
            rag_context=_rag_context(),
        )

        body = captured["body"]
        assert isinstance(body, dict)
        prompt = body["messages"][1]["content"]
        self.assertIn("#1", prompt)
        self.assertIn("#5", prompt)
        self.assertNotIn("#3 ", prompt)
        self.assertEqual(suggestion.action_id, 3)

    def test_client_uses_supplied_prompt_actions_without_repruning(self) -> None:
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else {}
            return "data: {\"choices\":[{\"delta\":{\"content\":\"{\\\"action_id\\\": 1}\"}}]}\ndata: [DONE]\n"

        legal_actions = [
            _action(1, "single", ["3"], ["3S"]),
            _action(2, "single", ["4"], ["4S"]),
        ]
        client = DeepSeekClient("test-key", "https://api.deepseek.com", "deepseek-chat", transport=transport)

        with mock.patch.object(
            DeepSeekClient,
            "_prune_legal_actions",
            side_effect=AssertionError("supplied prompt actions should not be pruned again"),
        ):
            suggestion = client.suggest_action_id(
                observation=_observation(),
                legal_actions=legal_actions,
                prompt_actions=[legal_actions[0]],
            )

        body = captured["body"]
        assert isinstance(body, dict)
        prompt = body["messages"][1]["content"]
        self.assertIn("action_id=1", prompt)
        self.assertNotIn("action_id=2", prompt)
        self.assertEqual(suggestion.action_id, 1)

    def test_local_shortcuts_do_not_build_deepseek_prompt(self) -> None:
        client = CountingClient()
        rag = CountingRAGAdvisor()

        with mock.patch.object(DeepSeekClient, "_build_structured_prompt", side_effect=AssertionError("prompt should not be built")):
            only_pass_agent = DeepSeekAIAgent(1, client, rag_advisor=rag, hand_evaluation_enabled=False, opening_formula_enabled=True)
            self.assertEqual(only_pass_agent.select_action(_observation(constraint="single:8"), [_action(7, "pass", [], [])]), 7)

            finish_agent = DeepSeekAIAgent(1, client, rag_advisor=rag, hand_evaluation_enabled=False, opening_formula_enabled=True)
            self.assertEqual(
                finish_agent.select_action(
                    _observation(hand_count=2),
                    [_action(1, "single", ["9"], ["9S"]), _action(2, "pair", ["9", "9"], ["9S", "9H"])],
                ),
                2,
            )

            opening_agent = DeepSeekAIAgent(1, client, rag_advisor=rag, hand_evaluation_enabled=False, opening_formula_enabled=True)
            self.assertEqual(
                opening_agent.select_action(
                    _observation(hand_count=20, step_no=0),
                    [_action(1, "single", ["9"], ["9S"]), _action(2, "pair", ["7", "7"], ["7S", "7H"])],
                ),
                2,
            )

        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.calls, 0)

    def test_pass_and_finish_shortcuts_precede_auxiliary_processing(self) -> None:
        client = CountingClient()
        rag = CountingRAGAdvisor()

        with (
            mock.patch("agents.deepseek_ai.evaluate_hand", side_effect=AssertionError("evaluation should not run")),
            mock.patch.object(DeepSeekClient, "_prune_legal_actions", side_effect=AssertionError("pruning should not run")),
            mock.patch("agents.card_tracker.CardTracker", side_effect=AssertionError("tracking should not run")),
        ):
            pass_agent = DeepSeekAIAgent(
                1,
                client,
                rag_advisor=rag,
                hand_evaluation_enabled=True,
                opening_formula_enabled=True,
            )
            self.assertEqual(
                pass_agent.select_action(
                    _observation(constraint="single:8"),
                    [_action(7, "pass", [], [])],
                ),
                7,
            )

            finish_agent = DeepSeekAIAgent(
                1,
                client,
                rag_advisor=rag,
                hand_evaluation_enabled=True,
                opening_formula_enabled=True,
            )
            self.assertEqual(
                finish_agent.select_action(
                    _observation(hand_count=2),
                    [_action(1, "single", ["9"], ["9S"]), _action(2, "pair", ["9", "9"], ["9S", "9H"])],
                ),
                2,
            )

        self.assertEqual(client.calls, 0)
        self.assertEqual(rag.calls, 0)

    def test_model_path_orders_pruning_evaluation_rag_and_client(self) -> None:
        events: list[str] = []
        observation = _observation(hand_count=20, step_no=5)
        legal_actions = [
            _action(1, "single", ["9"], ["9S"]),
            _action(2, "single", ["10"], ["10S"]),
        ]

        class OrderedClient:
            def suggest_action_id(self, **_kwargs):
                events.append("client")
                return DeepSeekSuggestion(action_id=1, reasoning="test")

        class OrderedRAG:
            def get_rag_context(self, **_kwargs):
                events.append("rag")
                return {"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""}

        config = mock.Mock(card_tracking_enabled=False)

        def prune(actions, _constraint, *, step_no, hand_count, phase_context):
            events.append("prune")
            return list(actions)

        def evaluate(_observation, _actions):
            events.append("evaluate")
            return {"total_score": 50, "label": "中等"}

        with (
            mock.patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            mock.patch.object(DeepSeekClient, "_prune_legal_actions", side_effect=prune),
            mock.patch("agents.deepseek_ai.evaluate_hand", side_effect=evaluate),
        ):
            agent = DeepSeekAIAgent(
                1,
                OrderedClient(),
                rag_advisor=OrderedRAG(),
                hand_evaluation_enabled=True,
                opening_formula_enabled=False,
            )
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen, 1)
        self.assertEqual(events, ["prune", "evaluate", "rag", "client"])

    def test_invalid_model_action_id_still_falls_back(self) -> None:
        client = CountingClient(action_id=999)
        rag = CountingRAGAdvisor()
        agent = DeepSeekAIAgent(
            player_id=1,
            client=client,
            rag_advisor=rag,
            hand_evaluation_enabled=False,
            opening_formula_enabled=False,
        )

        chosen = agent.select_action(
            _observation(step_no=5),
            [_action(1, "single", ["9"], ["9S"]), _action(2, "single", ["10"], ["10S"])],
        )

        self.assertIn(chosen, {1, 2})
        self.assertNotEqual(chosen, 999)
        self.assertEqual(client.calls, 1)
        self.assertEqual(rag.calls, 1)


if __name__ == "__main__":
    unittest.main()
