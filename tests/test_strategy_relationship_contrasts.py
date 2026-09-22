"""Engine-backed regressions for public model-before action contrasts."""

from copy import deepcopy
import unittest

from agents.action_structure import (
    select_candidate_structure_representatives,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
)
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion, PROMPT_MAX_CANDIDATE_ACTIONS
from agents.game_phase import classify_game_phase
from agents.strategy_recommendation import build_strategy_recommendation
from engine.cards import Card
from engine.game import GuanDanGame


def _cards(tokens: list[str]) -> tuple[Card, ...]:
    return tuple(Card(rank=token[:-1], suit=token[-1]) for token in tokens)


def _game(
    hand: list[str],
    *,
    teammate: list[str] | None = None,
    opponent_one: list[str] | None = None,
) -> GuanDanGame:
    return GuanDanGame(
        current_level_rank="2",
        preset_hands={
            1: _cards(hand),
            2: _cards(opponent_one or ["AS", "AH", "AC"]),
            3: _cards(teammate or ["KS", "KH"]),
            4: _cards(["QS", "QH", "QC"]),
        },
    )


def _context(observation: dict[str, object], actions: list[dict[str, object]], recommendation: object) -> dict[str, object]:
    current_round = observation["current_round"]
    my_info = observation["my_info"]
    assert isinstance(current_round, dict)
    assert isinstance(my_info, dict)
    return {
        "constraint": str(current_round["constraint"]),
        "step_no": int(current_round["step_no"]),
        "hand_count": int(my_info["hand_count"]),
        "phase_context": classify_game_phase(observation),
        "strategy_recommendation": recommendation,
    }


def _contrast(
    observation: dict[str, object], actions: list[dict[str, object]], kind: str
):
    contrasts = summarize_candidate_contrasts(observation, actions)
    assert contrasts is not None
    return next(item for item in contrasts if item.kind == kind)


class _RecordingClient:
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self.prompt_actions: list[dict[str, object]] = []

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.prompt_actions = list(kwargs["prompt_actions"])
        return DeepSeekSuggestion(self.action_id, None)


class StrategyRelationshipContrastTests(unittest.TestCase):
    def test_engine_bomb_contrast_protects_both_ids_and_explains_public_tradeoff(self) -> None:
        game = _game(["7S", "7H", "7C", "7D", "7S", "3S", "4H"])
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "bomb_residual")
        recommendation = build_strategy_recommendation(observation, actions)

        self.assertTrue(set(contrast.action_ids).issubset(recommendation.action_ids))
        final_actions = DeepSeekClient.prepare_prompt_actions(actions, **_context(observation, actions, recommendation))
        self.assertTrue(set(contrast.action_ids).issubset({action["action_id"] for action in final_actions}))
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"],
            other_players=observation["other_players"], history=observation["history"],
            legal_actions=final_actions, strategy_recommendation=recommendation,
            residual_structure_source_actions=actions,
        )
        self.assertIn("【公开关系对照】", prompt)
        self.assertIn("四/五炸对照", prompt)
        self.assertIn("少耗一张炸弹资源", prompt)
        self.assertIn("避免残余孤张", prompt)
        self.assertIn("不是动作指令", prompt)

    def test_engine_pair_single_contrast_beats_extra_singles_and_uses_public_teammate_count(self) -> None:
        game = _game(["6S", "6H", "3S", "4H", "9C", "AS"], teammate=["KS"])
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "natural_pair_single")
        recommendation = build_strategy_recommendation(observation, actions)

        self.assertEqual(recommendation.action_ids[:2], contrast.action_ids)
        self.assertLessEqual(len(recommendation.action_ids), 3)
        final_actions = DeepSeekClient.prepare_prompt_actions(actions, **_context(observation, actions, recommendation))
        self.assertTrue(set(contrast.action_ids).issubset({action["action_id"] for action in final_actions}))
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"],
            other_players=observation["other_players"], history=observation["history"],
            legal_actions=final_actions, strategy_recommendation=recommendation,
            residual_structure_source_actions=actions,
        )
        self.assertIn("同点数对子/单张对照", prompt)
        self.assertIn("队友公开剩余1张", prompt)
        self.assertIn("传递牌型与清理低价值牌", prompt)
        self.assertIn("不能推断队友暗牌", prompt)

    def test_initial_engine_range_keeps_safe_single_ahead_of_ordinary_pair_contrasts(self) -> None:
        pair_states = pair_front = safe_single_states = 0
        for seed in range(30):
            with self.subTest(seed=seed):
                game = GuanDanGame(seed=seed, current_level_rank="2")
                observation = game.reset()
                actions = game.legal_actions()
                facts = summarize_candidate_structures(observation, actions)
                assert facts is not None
                contrasts = summarize_candidate_contrasts(observation, actions)
                assert contrasts is not None
                contrast = next(item for item in contrasts if item.kind == "natural_pair_single")
                recommendation = build_strategy_recommendation(observation, actions)
                safe_ids = {
                    fact.action_id
                    for fact in facts
                    if (
                        fact.pattern == "single"
                        and fact.natural_single_rank_value is not None
                        and not fact.fragments_played_rank_group
                        and not fact.consumes_control_resource
                    )
                }
                pair_states += 1
                pair_front += int(set(recommendation.action_ids[:2]) == set(contrast.action_ids))
                safe_single_states += int(bool(safe_ids))
                if safe_ids and not any(item.kind == "bomb_residual" for item in contrasts):
                    self.assertIn(recommendation.action_ids[0], safe_ids)
                self.assertFalse(set(contrast.action_ids).issubset(recommendation.action_ids))
        self.assertEqual((pair_states, pair_front, safe_single_states), (30, 0, 29))

    def test_relationship_detection_is_stable_across_rank_and_public_hand_order(self) -> None:
        for rank in ("5", "9"):
            with self.subTest(rank=rank):
                hand = [f"{rank}S", f"{rank}H", "3S", "4H", "AC"]
                first_game = _game(hand, teammate=["KS", "KH", "KC"])
                second_game = _game(list(reversed(hand)), teammate=["KS", "KH", "KC"])
                first_observation = first_game.reset()
                second_observation = second_game.reset()
                first_contrast = _contrast(first_observation, first_game.legal_actions(), "natural_pair_single")
                second_contrast = _contrast(second_observation, second_game.legal_actions(), "natural_pair_single")
                self.assertEqual(first_contrast.action_ids, second_contrast.action_ids)
                self.assertEqual(first_contrast.teammate_hand_count, 3)

    def test_finisher_and_public_danger_keep_existing_objectives_without_forcing_a_side(self) -> None:
        game = _game(
            ["8S", "8H", "8C", "8D", "8S"],
            teammate=["KS", "KH"],
            opponent_one=["AS"],
        )
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "bomb_residual")
        recommendation = build_strategy_recommendation(observation, actions)

        self.assertIn("finish_now", recommendation.objective_codes)
        self.assertIn("block_opponent", recommendation.objective_codes)
        self.assertFalse(set(contrast.action_ids).issubset(recommendation.action_ids))
        self.assertLessEqual(len(recommendation.action_ids), 3)
        self.assertLessEqual(len(recommendation.objective_codes), 4)

    def test_overflow_keeps_engine_backed_bomb_contrast_within_existing_80_budget(self) -> None:
        hand = ["7S", "7H", "7C", "7D", "7S", "QS", "QH"]
        for rank in ("3", "4", "5", "6", "8", "9"):
            hand.extend((f"{rank}S", f"{rank}H", f"{rank}C"))
        hand.extend(("10S", "JS"))
        game = _game(hand[:27], teammate=["KS", "KH", "KC"])
        observation = game.reset()
        actions = game.legal_actions()
        self.assertGreater(len(actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        contrasts = summarize_candidate_contrasts(observation, actions)
        assert contrasts is not None
        self.assertTrue(any(item.kind == "natural_pair_single" for item in contrasts))
        contrast = _contrast(observation, actions, "bomb_residual")
        recommendation = build_strategy_recommendation(observation, actions)
        final_actions = DeepSeekClient.prepare_prompt_actions(actions, **_context(observation, actions, recommendation))
        final_ids = {int(action["action_id"]) for action in final_actions}

        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue(set(contrast.action_ids).issubset(recommendation.action_ids))
        self.assertTrue(set(contrast.action_ids).issubset(final_ids))
        self.assertTrue(final_ids.issubset({int(action["action_id"]) for action in actions}))
        signatures = [DeepSeekClient._action_signature(action) for action in final_actions]
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_initial_engine_range_promotes_bomb_contrasts_without_pair_budget_starvation(self) -> None:
        bomb_states = visible_pairs = recommended_pairs = 0
        for seed in range(100):
            game = GuanDanGame(seed=seed, current_level_rank="2")
            observation = game.reset()
            actions = game.legal_actions()
            contrasts = summarize_candidate_contrasts(observation, actions)
            assert contrasts is not None
            bomb = next((item for item in contrasts if item.kind == "bomb_residual"), None)
            if bomb is None:
                continue
            recommendation = build_strategy_recommendation(observation, actions)
            final_actions = DeepSeekClient.prepare_prompt_actions(
                actions, **_context(observation, actions, recommendation)
            )
            final_ids = {int(action["action_id"]) for action in final_actions}
            bomb_states += 1
            visible_pairs += int(set(bomb.action_ids).issubset(final_ids))
            recommended_pairs += int(set(bomb.action_ids).issubset(recommendation.action_ids))
        self.assertEqual((bomb_states, visible_pairs, recommended_pairs), (18, 18, 18))

    def test_both_model_choices_remain_original_model_ids(self) -> None:
        scenarios = (
            ("pair", ["6S", "6H", "3S", "4H", "9C", "AS"], "natural_pair_single"),
            ("bomb", ["7S", "7H", "7C", "7D", "7S", "3S", "4H"], "bomb_residual"),
        )
        for name, hand, kind in scenarios:
            game = _game(hand, teammate=["KS"])
            observation = game.reset()
            actions = game.legal_actions()
            contrast = _contrast(observation, actions, kind)
            for action_id in contrast.action_ids:
                with self.subTest(scenario=name, action_id=action_id):
                    client = _RecordingClient(action_id)
                    agent = DeepSeekAIAgent(
                        1, client, rag_advisor=None, hand_evaluation_enabled=False,
                        opening_formula_enabled=False,
                    )
                    self.assertEqual(agent.select_action(observation, actions), action_id)
                    self.assertEqual(agent.last_decision_source, "model")
                    self.assertTrue(set(contrast.action_ids).issubset({item["action_id"] for item in client.prompt_actions}))

    def test_malformed_payload_and_tight_representative_budget_fail_closed_without_half_contrast(self) -> None:
        game = _game(["5S", "5H", "3S", "4H"])
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "natural_pair_single")
        malformed = deepcopy(actions)
        malformed[0]["carrier_cards"] = ["AS"]
        self.assertIsNone(summarize_candidate_contrasts(observation, malformed))

        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        representatives = select_candidate_structure_representatives(
            facts,
            recommended_ids=tuple(fact.action_id for fact in facts[:3]),
            contrast_action_id_groups=(contrast.action_ids,),
            limit=3,
        )
        selected_ids = {item.action_id for item in representatives}
        self.assertFalse(set(contrast.action_ids) & selected_ids == set(contrast.action_ids))


if __name__ == "__main__":
    unittest.main()
