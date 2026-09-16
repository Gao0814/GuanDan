from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion, PROMPT_MAX_CANDIDATE_ACTIONS
from agents.game_phase import classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.action_structure import summarize_candidate_structures
from agents.strategy_recommendation import (
    MAX_RECOMMENDATION_OBJECTIVES,
    OBJECTIVE_CODES,
    StrategyRecommendation,
    build_strategy_recommendation,
)
from engine.cards import Card
from engine.game import GuanDanGame
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(rank=token, suit=None)
    return Card(rank=token[:-1], suit=token[-1])


def _engine_lead(cards: list[str]) -> tuple[dict[str, object], list[dict[str, object]]]:
    other_cards = ["3H", "4H", "5H", "6H", "8H", "9H"]
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands={
            1: tuple(_card(token) for token in cards),
            2: tuple(_card(token) for token in other_cards),
            3: tuple(_card(token) for token in other_cards),
            4: tuple(_card(token) for token in other_cards),
        },
    )
    observation = game.reset()
    return observation, game.legal_actions()


def _prepared(
    observation: dict[str, object],
    legal_actions: list[dict[str, object]],
) -> tuple[object, list[dict[str, object]], str]:
    recommendation = build_strategy_recommendation(observation, legal_actions)
    phase_context = classify_game_phase(observation)
    current_round = observation["current_round"]
    my_info = observation["my_info"]
    assert isinstance(current_round, dict)
    assert isinstance(my_info, dict)
    final_actions = DeepSeekClient.prepare_prompt_actions(
        legal_actions,
        constraint=str(current_round["constraint"]),
        step_no=int(current_round["step_no"]),
        hand_count=int(my_info["hand_count"]),
        phase_context=phase_context,
        strategy_recommendation=recommendation,
    )
    advisor = RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents()))
    rag_context = advisor.get_rag_context(
        observation=observation,
        legal_actions=legal_actions,
        hand_eval={"label": "medium"},
        phase_context=phase_context,
        strategy_recommendation=recommendation,
        top_k=10,
    )
    prompt = DeepSeekClient._build_structured_prompt(
        my_info=my_info,
        current_round=current_round,
        other_players=list(observation["other_players"]),
        history=dict(observation["history"]),
        legal_actions=final_actions,
        rag_context=rag_context,
        phase_context=phase_context,
        strategy_recommendation=recommendation,
        residual_structure_source_actions=legal_actions,
    )
    return recommendation, final_actions, prompt


def _objective_budget_state() -> tuple[dict[str, object], list[dict[str, object]]]:
    """Find a real later free-lead state with five independently public goals."""
    for seed in range(40):
        game = GuanDanGame(seed=seed, current_level_rank="2")
        game.reset()
        finished = False
        while not finished:
            observation = game.observe()
            legal_actions = game.legal_actions()
            facts = summarize_candidate_structures(observation, legal_actions)
            if facts is not None and facts and facts[0].is_free_lead:
                safe_natural_single = any(
                    fact.pattern == "single"
                    and not fact.uses_wildcard
                    and not fact.fragments_played_rank_group
                    and not fact.consumes_control_resource
                    and fact.natural_single_rank_value is not None
                    for fact in facts
                )
                if (
                    safe_natural_single
                    and any(fact.fragments_played_rank_group for fact in facts)
                    and any(fact.teammate_active and fact.teammate_hand_count is not None and fact.teammate_hand_count <= 2 for fact in facts)
                    and any(fact.minimum_opponent_hand_count is not None and fact.minimum_opponent_hand_count <= 2 for fact in facts)
                    and any(fact.finishes_hand for fact in facts) is False
                    and int(observation["my_info"]["hand_count"]) <= 4
                ):
                    return observation, legal_actions
            result = game.step(int(legal_actions[0]["action_id"]))
            finished = bool(result.get("game_over", False))
    raise AssertionError("expected deterministic objective-budget state")


class RecommendationCandidateClosureTests(unittest.TestCase):
    def test_engine_backed_objective_budget_preserves_public_urgency(self) -> None:
        observation, legal_actions = _objective_budget_state()
        recommendation, final_actions, prompt = _prepared(observation, legal_actions)

        self.assertEqual(recommendation.status, "ready")
        self.assertEqual(len(recommendation.objective_codes), MAX_RECOMMENDATION_OBJECTIVES)
        self.assertEqual(
            recommendation.objective_codes,
            ("block_opponent", "plan_endgame", "support_teammate", "protect_structure"),
        )
        self.assertNotIn("low_cost_probe", recommendation.objective_codes)
        self.assertIsNotNone(
            DeepSeekClient._validated_strategy_recommendation(recommendation, legal_actions)
        )
        self.assertTrue(
            set(recommendation.action_ids).issubset(
                {int(action["action_id"]) for action in final_actions}
            )
        )
        for marker in ("【模型前建议】", "策略域：", "目标：", "反例检查："):
            self.assertIn(marker, prompt)

    def test_external_five_objective_payload_is_rejected_without_truncation(self) -> None:
        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        legal_actions = game.legal_actions()
        production = build_strategy_recommendation(observation, legal_actions)
        external = replace(production, objective_codes=OBJECTIVE_CODES[:5])

        self.assertLessEqual(len(production.objective_codes), MAX_RECOMMENDATION_OBJECTIVES)
        self.assertIsNone(DeepSeekClient._validated_strategy_recommendation(external, legal_actions))

    def test_engine_backed_large_free_lead_keeps_recommendations_in_final_prompt(self) -> None:
        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        legal_actions = game.legal_actions()
        recommendation, final_actions, prompt = _prepared(observation, legal_actions)

        self.assertEqual(recommendation.status, "ready")
        final_ids = {int(action["action_id"]) for action in final_actions}
        raw_ids = {int(action["action_id"]) for action in legal_actions}
        self.assertGreater(len(legal_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue(set(recommendation.action_ids).issubset(final_ids))
        self.assertTrue(final_ids.issubset(raw_ids))
        signatures = [DeepSeekClient._action_signature(action) for action in final_actions]
        self.assertEqual(len(signatures), len(set(signatures)))
        for marker in ("【模型前建议】", "策略域：", "目标：", "反例检查："):
            self.assertIn(marker, prompt)

    def test_engine_backed_relation_fixtures_keep_guidance_and_soft_hypothesis(self) -> None:
        cases = {
            "low_cost_single_probe": ["3S", "4S", "7S", "7H"],
            "natural_pair_single_cleanup": ["3S", "4S", "7S", "7H", "9S"],
            "neutral_pair_triple_soft_hypothesis": ["3S", "3H", "3C", "5S", "5H", "7S"],
            "short_endgame_minimum_groups": ["6S", "7S", "JH", "JD"],
            "bomb_wildcard_resource": ["2H", "7S", "7H", "7C", "7D", "7S", "9S"],
        }
        expected_objectives = {
            "low_cost_single_probe": "low_cost_probe",
            "natural_pair_single_cleanup": "low_cost_probe",
            "short_endgame_minimum_groups": "plan_endgame",
            "bomb_wildcard_resource": "manage_bomb_wildcard",
        }
        for name, cards in cases.items():
            with self.subTest(name=name):
                observation, legal_actions = _engine_lead(cards)
                recommendation, final_actions, prompt = _prepared(observation, legal_actions)
                self.assertEqual(recommendation.status, "ready")
                self.assertTrue(
                    set(recommendation.action_ids).issubset(
                        {int(action["action_id"]) for action in final_actions}
                    )
                )
                self.assertIn("【模型前建议】", prompt)
                self.assertIn("可撤回软假设", prompt)
                if name == "natural_pair_single_cleanup":
                    self.assertTrue(
                        {"single", "pair"}.issubset(
                            {str(action["declared_pattern"]) for action in final_actions}
                        )
                    )
                if name in expected_objectives:
                    self.assertIn(expected_objectives[name], recommendation.objective_codes)

    def test_invalid_recommendations_do_not_expand_or_weaken_the_candidate_set(self) -> None:
        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        legal_actions = game.legal_actions()
        recommendation = build_strategy_recommendation(observation, legal_actions)
        current_round = observation["current_round"]
        my_info = observation["my_info"]
        assert isinstance(current_round, dict)
        assert isinstance(my_info, dict)
        kwargs = {
            "constraint": str(current_round["constraint"]),
            "step_no": int(current_round["step_no"]),
            "hand_count": int(my_info["hand_count"]),
            "phase_context": classify_game_phase(observation),
        }
        baseline = DeepSeekClient.prepare_prompt_actions(legal_actions, **kwargs)
        malformed = (
            replace(recommendation, action_ids=(recommendation.action_ids[0],) * 2),
            replace(recommendation, action_ids=(1, 2, 3, 4)),
            replace(recommendation, action_ids=(999999,)),
            replace(recommendation, objective_codes=("unknown",)),
            replace(recommendation, objective_codes=tuple(reversed(recommendation.objective_codes))),
            replace(recommendation, source="untrusted"),
            StrategyRecommendation(
                "ready", "public_strategy_recommendation_v2", list(recommendation.action_ids),
                recommendation.objective_codes, recommendation.countercheck_codes, recommendation.strategy_domains,
            ),
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                self.assertIsNone(DeepSeekClient._validated_strategy_recommendation(payload, legal_actions))
                self.assertEqual(
                    [action["action_id"] for action in baseline],
                    [action["action_id"] for action in DeepSeekClient.prepare_prompt_actions(
                        legal_actions,
                        strategy_recommendation=payload,
                        **kwargs,
                    )],
                )

    def test_multi_seed_full_game_properties_are_stable(self) -> None:
        state_count = 0
        for seed in range(40):
            with self.subTest(seed=seed):
                game = GuanDanGame(seed=seed, current_level_rank="2")
                game.reset()
                finished = False
                while not finished:
                    observation = game.observe()
                    legal_actions = game.legal_actions()
                    recommendation = build_strategy_recommendation(observation, legal_actions)
                    current_round = observation["current_round"]
                    my_info = observation["my_info"]
                    assert isinstance(current_round, dict)
                    assert isinstance(my_info, dict)
                    kwargs = {
                        "constraint": str(current_round["constraint"]),
                        "step_no": int(current_round["step_no"]),
                        "hand_count": int(my_info["hand_count"]),
                        "phase_context": classify_game_phase(observation),
                        "strategy_recommendation": recommendation,
                    }
                    first = DeepSeekClient.prepare_prompt_actions(legal_actions, **kwargs)
                    second = DeepSeekClient.prepare_prompt_actions(legal_actions, **kwargs)
                    raw_ids = {int(action["action_id"]) for action in legal_actions}
                    final_ids = {int(action["action_id"]) for action in first}
                    if recommendation.status == "ready":
                        self.assertIsNotNone(
                            DeepSeekClient._validated_strategy_recommendation(recommendation, legal_actions)
                        )
                        self.assertLessEqual(
                            len(recommendation.objective_codes),
                            MAX_RECOMMENDATION_OBJECTIVES,
                        )
                        self.assertTrue(set(recommendation.action_ids).issubset(final_ids))
                    self.assertLessEqual(len(first), PROMPT_MAX_CANDIDATE_ACTIONS)
                    self.assertTrue(final_ids.issubset(raw_ids))
                    signatures = [DeepSeekClient._action_signature(action) for action in first]
                    self.assertEqual(len(signatures), len(set(signatures)))
                    self.assertEqual(
                        [action["action_id"] for action in first],
                        [action["action_id"] for action in second],
                    )
                    result = game.step(int(legal_actions[0]["action_id"]))
                    finished = bool(result.get("game_over", False))
                    state_count += 1
        self.assertGreater(state_count, 0)

    def test_client_and_agent_share_final_candidates_and_preserve_model_id(self) -> None:
        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        legal_actions = game.legal_actions()
        recommendation = build_strategy_recommendation(observation, legal_actions)
        current_round = observation["current_round"]
        my_info = observation["my_info"]
        assert isinstance(current_round, dict)
        assert isinstance(my_info, dict)
        expected_actions = DeepSeekClient.prepare_prompt_actions(
            legal_actions,
            constraint=str(current_round["constraint"]),
            step_no=int(current_round["step_no"]),
            hand_count=int(my_info["hand_count"]),
            phase_context=classify_game_phase(observation),
            strategy_recommendation=recommendation,
        )
        returned_id = int(expected_actions[-1]["action_id"])
        captured: dict[str, object] = {}

        def transport(request, timeout: float) -> str:
            captured["body"] = json.loads(request.data.decode("utf-8")) if request.data else {}
            return f'data: {{"choices":[{{"delta":{{"content":"{{\\"action_id\\": {returned_id}}}"}}}}]}}\ndata: [DONE]\n'

        client = DeepSeekClient("test-key", "https://api.deepseek.com", "deepseek-chat", transport=transport)
        suggestion = client.suggest_action_id(
            observation=observation,
            legal_actions=legal_actions,
            strategy_recommendation=recommendation,
        )
        self.assertEqual(suggestion.action_id, returned_id)
        body = captured["body"]
        assert isinstance(body, dict)
        prompt = body["messages"][1]["content"]
        self.assertIn("【模型前建议】", prompt)

        class RecordingClient:
            def __init__(self) -> None:
                self.prompt_actions: list[dict[str, object]] = []

            def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
                self.prompt_actions = list(kwargs["prompt_actions"])
                return DeepSeekSuggestion(int(self.prompt_actions[-1]["action_id"]), None)

        recording = RecordingClient()
        config = SimpleNamespace(card_tracking_enabled=False)
        with mock.patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(
                1,
                recording,
                hand_evaluation_enabled=False,
                opening_formula_enabled=False,
            )
            chosen = agent.select_action(observation, legal_actions)
        self.assertEqual(chosen, returned_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertEqual(
            [action["action_id"] for action in recording.prompt_actions],
            [action["action_id"] for action in expected_actions],
        )


if __name__ == "__main__":
    unittest.main()
