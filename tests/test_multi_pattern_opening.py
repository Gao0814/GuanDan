"""Engine-backed coverage for source-conditioned multi-pattern opening leads."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from agents.action_structure import (
    representative_candidate_contrasts,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
)
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from agents.hand_evaluator import evaluate_hand
from agents.opening_strategy import OpeningFormulaStrategy, normalize_hand_strength
from agents.rag_advisor import RAGAdvisor
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame
from evaluation.h3_model_probe_fixtures import build_h3_model_probe_fixtures
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _complete_game_with_hand(spec: tuple[tuple[str, int], ...]) -> GuanDanGame:
    """Make a full 108-card deal while prescribing only player one's hand."""

    deck = build_double_deck()
    hand: list[Card] = []
    for rank, count in spec:
        selected = [card for card in tuple(deck) if card.rank == rank][:count]
        if len(selected) != count:
            raise AssertionError("fixture_card_count_unavailable")
        for card in selected:
            deck.remove(card)
        hand.extend(selected)
    if len(hand) != 27 or len(deck) != 81:
        raise AssertionError("fixture_deal_not_conserved")
    return GuanDanGame(
        current_level_rank="2",
        preset_hands={
            1: tuple(hand),
            2: tuple(deck[:27]),
            3: tuple(deck[27:54]),
            4: tuple(deck[54:81]),
        },
    )


def _shape_games() -> tuple[tuple[str, GuanDanGame], ...]:
    return (
        (
            "pair",
            _complete_game_with_hand(
                (("3", 2), ("4", 5), *((rank, 4) for rank in ("5", "6", "7", "8", "9")))
            ),
        ),
        (
            "triple",
            _complete_game_with_hand(
                (("3", 3), *((rank, 4) for rank in ("4", "5", "6", "7", "8", "9")))
            ),
        ),
        (
            "straight",
            _complete_game_with_hand(
                (
                    *((rank, 1) for rank in ("3", "4", "5", "6", "7")),
                    *((rank, 4) for rank in ("8", "9", "10", "J", "Q")),
                    ("A", 2),
                )
            ),
        ),
    )


class _OfflineConfig:
    card_tracking_enabled = False
    hand_evaluation_enabled = True
    opening_formula_enabled = True


class _CapturingTransport:
    """Capture the actual production Request and answer with a displayed ID."""

    def __init__(self) -> None:
        self.calls = 0
        self.prompt = ""
        self.candidate_ids: tuple[int, ...] = ()
        self.action_id: int | None = None

    def __call__(self, request: object, _timeout: float) -> str:
        self.calls += 1
        raw = getattr(request, "data", None)
        if not isinstance(raw, bytes):
            raise OSError("offline_request_body_missing")
        envelope = json.loads(raw.decode("utf-8"))
        messages = envelope.get("messages")
        if not isinstance(messages, list):
            raise OSError("offline_messages_missing")
        users = [item for item in messages if isinstance(item, dict) and item.get("role") == "user"]
        if len(users) != 1 or not isinstance(users[0].get("content"), str):
            raise OSError("offline_user_prompt_missing")
        self.prompt = users[0]["content"]
        start = self.prompt.find("【候选动作】")
        end = self.prompt.find("【规则库依据】")
        if start < 0 or end <= start:
            raise OSError("offline_candidates_missing")
        rows = re.findall(r"#(\d+)\s+action_id=(\d+)\s+\|", self.prompt[start:end])
        if not rows or any(left != right for left, right in rows):
            raise OSError("offline_candidates_invalid")
        self.candidate_ids = tuple(int(left) for left, _ in rows)
        self.action_id = self.candidate_ids[0]
        response = json.dumps({"action_id": self.action_id}, separators=(",", ":"))
        chunk = json.dumps({"choices": [{"delta": {"content": response}}]})
        return f"data: {chunk}\n\ndata: [DONE]\n"


class _CapturingClient(DeepSeekClient):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.suggestion_kwargs: dict[str, object] = {}
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def suggest_action_id(self, **kwargs: object):
        self.suggestion_kwargs = dict(kwargs)
        return super().suggest_action_id(**kwargs)


class MultiPatternOpeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = OpeningFormulaStrategy()

    def test_full_deal_group_routes_with_material_contrasts_stay_with_the_model(self) -> None:
        for expected_pattern, game in _shape_games():
            with self.subTest(pattern=expected_pattern):
                observation = game.reset()
                actions = game.legal_actions()
                my_info = observation["my_info"]
                other_players = observation["other_players"]
                current_round = observation["current_round"]
                self.assertEqual(my_info["hand_count"], 27)
                self.assertEqual([item["hand_count"] for item in other_players], [27, 27, 27])
                self.assertEqual(current_round["step_no"], 0)
                self.assertEqual(current_round["constraint"], "free")
                hand_eval = evaluate_hand(observation, actions)
                chosen = self.strategy.select_action(observation, actions, hand_eval)
                self.assertIsNone(chosen)
                contrasts = summarize_candidate_contrasts(observation, actions)
                self.assertIsNotNone(contrasts)
                assert contrasts is not None
                target_actions = [item for item in actions if item["declared_pattern"] == expected_pattern]
                self.assertTrue(target_actions)
                self.assertTrue(
                    any(
                        action["action_id"] in contrast.action_ids
                        for action in target_actions
                        for contrast in contrasts
                    )
                )
                if expected_pattern == "straight":
                    self.assertTrue(any(item.kind == "natural_sequence_single" for item in contrasts))
                self.assertIsNotNone(summarize_candidate_structures(observation, actions))

    def test_full_opening_can_select_a_unique_low_single_with_independent_bomb_return(self) -> None:
        specifications = (
            (("3", 4), ("6", 4), ("8", 4), ("10", 4), ("5", 5), ("J", 5), ("4", 1)),
            (("3", 4), ("5", 4), ("9", 4), ("J", 4), ("4", 5), ("10", 5), ("7", 1)),
        )
        for specification in specifications:
            with self.subTest(shape_count=len(specification)):
                game = _complete_game_with_hand(specification)
                observation = game.reset()
                actions = game.legal_actions()
                selected = self.strategy.select_action(
                    observation,
                    actions,
                    evaluate_hand(observation, actions),
                )
                selected_action = next(item for item in actions if item["action_id"] == selected)
                self.assertEqual(selected_action["declared_pattern"], "single")
                self.assertIn(selected, {item["action_id"] for item in actions})
                self.assertTrue(self.strategy._has_return_resource(observation, actions))
                contrasts = representative_candidate_contrasts(observation, actions)
                self.assertIsNotNone(contrasts)
                assert contrasts is not None
                self.assertFalse(any(selected in item.action_ids for item in contrasts))

    def test_structured_lower_single_is_filtered_before_probe_ranking(self) -> None:
        from agents.opening_strategy import _CONTROL_RANKS, _RANK_ORDER, _rank_of

        # This deal has a structured lower singleton but another clean probe
        # above it; the selected small single remains outside all structures.
        game = GuanDanGame(seed=43, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        hand_counts = Counter(_rank_of(card) for card in observation["my_info"]["hand_cards"])
        structured_tokens = {
            card
            for action in actions
            if action["wildcard_count"] == 0 and len(action["carrier_cards"]) > 1
            for card in action["carrier_cards"]
        }
        natural_singletons = []
        for action in actions:
            carriers = action["carrier_cards"]
            declared = action["declared_cards"]
            if (
                action["declared_pattern"] != "single"
                or action["wildcard_count"] != 0
                or len(carriers) != 1
                or len(declared) != 1
            ):
                continue
            rank = _rank_of(carriers[0])
            if (
                declared[0] not in {rank, carriers[0]}
                or hand_counts[rank] != 1
                or rank in _CONTROL_RANKS
            ):
                continue
            natural_singletons.append(action)
        lowest_overall = min(
            natural_singletons,
            key=lambda action: _RANK_ORDER[_rank_of(action["carrier_cards"][0])],
        )
        selected = self.strategy.select_action(
            observation,
            actions,
            evaluate_hand(observation, actions),
        )
        self.assertIsNotNone(selected)
        selected_action = next(action for action in actions if action["action_id"] == selected)
        self.assertEqual(selected_action["declared_pattern"], "single")
        lowest_token = lowest_overall["carrier_cards"][0]
        selected_token = selected_action["carrier_cards"][0]
        self.assertIn(lowest_token, structured_tokens)
        self.assertNotIn(selected_token, structured_tokens)
        self.assertGreater(
            _RANK_ORDER[_rank_of(selected_token)],
            _RANK_ORDER[_rank_of(lowest_token)],
        )
        contrasts = representative_candidate_contrasts(observation, actions)
        self.assertIsNotNone(contrasts)
        assert contrasts is not None
        self.assertFalse(any(selected in item.action_ids for item in contrasts))

    def test_complete_group_relationship_keeps_choice_with_model(self) -> None:
        # The earlier display-filtered check treated this as one group route.
        # The full canonical relation set shows real alternatives, so the
        # source-backed formula must defer regardless of a scalar label.
        game = GuanDanGame(seed=89, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        self.assertEqual(observation["my_info"]["hand_count"], 27)
        self.assertEqual([player["hand_count"] for player in observation["other_players"]], [27, 27, 27])
        self.assertEqual(observation["current_round"]["step_no"], 0)
        analyses = []
        for label in ("strong", "medium", "weak"):
            with self.subTest(label=label):
                analysis = self.strategy.analyze_action(
                    observation,
                    actions,
                    {"label": label, "total_score": 50, "control_score": 8},
                )
                self.assertIsNone(analysis.action_id)
                analyses.append(analysis)
        self.assertEqual(analyses[0], analyses[1])
        self.assertEqual(analyses[1], analyses[2])
        transport = _CapturingTransport()
        client = _CapturingClient(
            "offline-test-key",
            "https://offline.invalid",
            "offline-test-model",
            max_retries=0,
            transport=transport,
        )
        rag_root = Path(__file__).resolve().parents[1] / "rag"
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(rag_root).load_all_documents())
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_OfflineConfig()):
            agent = DeepSeekAIAgent(
                1,
                client,
                rag_advisor=advisor,
                hand_evaluation_enabled=True,
                opening_formula_enabled=True,
            )
            chosen = agent.select_action(observation, actions)
        self.assertIn(chosen, {item["action_id"] for item in actions})
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn(chosen, transport.candidate_ids)
        self.assertEqual(chosen, transport.action_id)
        self.assertEqual(transport.calls, 1)
        self.assertIn("【公开关系对照】", transport.prompt)
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        from agents.opening_strategy import _rank_of

        routes = self.strategy._eligible_natural_group_routes(
            observation,
            actions,
            facts,
            {fact.action_id: fact for fact in facts},
            {int(item["action_id"]): item for item in actions},
            Counter(_rank_of(card) for card in observation["my_info"]["hand_cards"]),
            str(observation["current_round"]["current_level_rank"]),
        )
        self.assertIsNotNone(routes)
        self.assertTrue(
            all(route.action_id in transport.candidate_ids for route in routes or ())
        )

    def test_fourteen_omitted_full_relations_reach_actual_bounded_model_request(self) -> None:
        missed = (
            (33, "wildcard_resource"),
            (77, "wildcard_resource"),
            (113, "wildcard_resource"),
            (125, "natural_pair_single"),
            (5030, "wildcard_resource"),
            (5060, "wildcard_resource"),
            (5066, "wildcard_resource"),
            (5070, "wildcard_resource"),
            (5077, "wildcard_resource"),
            (5141, "natural_pair_single"),
            (5173, "wildcard_resource"),
            (5181, "wildcard_resource"),
            (5186, "wildcard_resource"),
            (5187, "wildcard_resource"),
        )
        relation_markers = {
            "wildcard_resource": "通配资源对照",
            "natural_pair_single": "同点数对子/单张对照",
        }
        for seed, expected_kind in missed:
            with self.subTest(seed=seed, relation=expected_kind):
                game = GuanDanGame(seed=seed, current_level_rank="2")
                observation = game.reset()
                actions = game.legal_actions()
                analysis = self.strategy.analyze_action(
                    observation, actions, evaluate_hand(observation, actions),
                )
                self.assertIsNone(analysis.action_id)
                representatives = representative_candidate_contrasts(observation, actions)
                full = summarize_candidate_contrasts(observation, actions)
                self.assertIsNotNone(representatives)
                self.assertIsNotNone(full)
                assert representatives is not None and full is not None
                representative_pairs = {
                    (item.kind, item.action_ids) for item in representatives
                }
                omitted = tuple(
                    item for item in analysis.model_contrasts
                    if item.kind == expected_kind
                    and (item.kind, item.action_ids) not in representative_pairs
                )
                self.assertTrue(omitted)
                self.assertTrue(all(item in full for item in omitted))

                transport = _CapturingTransport()
                client = _CapturingClient(
                    "offline-test-key",
                    "https://offline.invalid",
                    "offline-test-model",
                    max_retries=0,
                    transport=transport,
                )
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_OfflineConfig()):
                    agent = DeepSeekAIAgent(
                        1,
                        client,
                        hand_evaluation_enabled=True,
                        opening_formula_enabled=True,
                    )
                    selected = agent.select_action(observation, actions)

                candidate_set = set(transport.candidate_ids)
                raw_ids = {item["action_id"] for item in actions}
                self.assertEqual(transport.calls, 1)
                self.assertEqual(agent.last_decision_source, "model")
                self.assertEqual(selected, transport.action_id)
                self.assertIn(selected, candidate_set)
                self.assertLessEqual(len(candidate_set), 80)
                self.assertEqual(len(candidate_set), len(transport.candidate_ids))
                self.assertTrue(candidate_set.issubset(raw_ids))
                for contrast in omitted:
                    self.assertTrue(set(contrast.action_ids).issubset(candidate_set))
                    relation_lines = [
                        line for line in transport.prompt.splitlines()
                        if relation_markers[expected_kind] in line
                    ]
                    self.assertTrue(
                        any(
                            all(f"action_id={action_id}" in line for action_id in contrast.action_ids)
                            for line in relation_lines
                        )
                    )

    def test_material_opening_tradeoff_reaches_real_client_request_and_preserves_model_id(self) -> None:
        game = GuanDanGame(seed=29, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        hand_eval = evaluate_hand(observation, actions)
        self.assertEqual(normalize_hand_strength(hand_eval), "strong")
        self.assertIsNone(self.strategy.select_action(observation, actions, hand_eval))
        contrasts = summarize_candidate_contrasts(observation, actions)
        self.assertIsNotNone(contrasts)
        assert contrasts is not None
        expected_relations = {item.kind for item in contrasts}
        self.assertIn("natural_sequence_single", expected_relations)

        rag_root = Path(__file__).resolve().parents[1] / "rag"
        advisor = RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(rag_root).load_all_documents()))
        transport = _CapturingTransport()
        client = _CapturingClient(
            "offline-test-key",
            "https://offline.invalid",
            "offline-test-model",
            max_retries=0,
            transport=transport,
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_OfflineConfig()):
            agent = DeepSeekAIAgent(
                1,
                client,
                rag_advisor=advisor,
                rag_top_k=3,
                hand_evaluation_enabled=True,
                opening_formula_enabled=True,
                strategy_router_shadow_enabled=True,
                strategy_intent_prompt_enabled=True,
                strategy_recommendation_enabled=True,
            )
            chosen = agent.select_action(observation, actions)

        self.assertEqual(transport.calls, 1)
        self.assertEqual(chosen, transport.action_id)
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn(chosen, transport.candidate_ids)
        self.assertLessEqual(len(transport.candidate_ids), 80)
        self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
        self.assertTrue(set(transport.candidate_ids).issubset({item["action_id"] for item in actions}))
        sequence_contrast = next(item for item in contrasts if item.kind == "natural_sequence_single")
        self.assertTrue(set(sequence_contrast.action_ids).issubset(transport.candidate_ids))
        self.assertEqual(getattr(agent.last_strategy_recommendation, "status", None), "ready")
        rag_context = client.suggestion_kwargs.get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)
        hit_ids = {item.get("source_id") for item in rag_context["experience_hits"]}
        self.assertTrue(
            hit_ids
            & {
                "exp_lead_opening_medium_001",
                "exp_lead_opening_shape_001",
                "exp_lead_opening_weak_001",
            }
        )
        self.assertTrue(
            hit_ids & {"exp_soft_pair_probe_001", "exp_soft_single_cost_probe_001"}
        )
        self.assertIn("自然顺子/其中单张对照", transport.prompt)
        self.assertTrue(
            any(
                marker in transport.prompt
                for marker in ("同点数对子/单张对照", "自然组牌/普通单张对照", "自然顺子/连组与同点组对照")
            )
        )
        self.assertTrue(any(marker in transport.prompt for marker in ("反例", "可以推翻", "可推翻")))

    def test_opening_shape_source_does_not_activate_in_public_endgame(self) -> None:
        fixture = build_h3_model_probe_fixtures()[6]
        applicability = RAGAdvisor._candidate_applicability(
            fixture.observation, fixture.legal_actions
        )
        self.assertIsNotNone(applicability)
        assert applicability is not None
        self.assertFalse(applicability["opening_natural_shape"])
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        context = advisor.get_rag_context(
            observation=fixture.observation,
            legal_actions=fixture.legal_actions,
            top_k=3,
        )
        self.assertNotIn(
            "exp_lead_opening_shape_001",
            {item.get("source_id") for item in context["experience_hits"]},
        )

    def test_held_out_initial_deal_interval_revalidates_non_single_coverage(self) -> None:
        from agents.opening_strategy import _rank_of

        formula_patterns: Counter[str] = Counter()
        no_direct = 0
        state_count = 200
        for seed in range(5000, 5200):
            game = GuanDanGame(seed=seed, current_level_rank="2")
            observation = game.reset()
            actions = game.legal_actions()
            self.assertEqual(observation["my_info"]["hand_count"], 27)
            self.assertEqual([player["hand_count"] for player in observation["other_players"]], [27, 27, 27])
            self.assertEqual(observation["current_round"]["step_no"], 0)
            chosen = self.strategy.select_action(observation, actions, evaluate_hand(observation, actions))
            if chosen is None:
                no_direct += 1
                continue
            action = next(item for item in actions if item["action_id"] == chosen)
            pattern = str(action["declared_pattern"])
            formula_patterns[pattern] += 1
            self.assertIn(chosen, {item["action_id"] for item in actions})
            facts = summarize_candidate_structures(observation, actions)
            contrasts = summarize_candidate_contrasts(observation, actions)
            assert facts is not None and contrasts is not None
            if pattern == "single":
                self.assertTrue(
                    self.strategy._small_single_relationships_are_source_supported(
                        int(chosen), contrasts, {fact.action_id: fact for fact in facts},
                    )
                )
            else:
                self.assertIn(pattern, {"pair", "triple"})
                self.assertFalse(any(chosen in item.action_ids for item in contrasts))
                current_round = observation["current_round"]
                routes = self.strategy._eligible_natural_group_routes(
                    observation,
                    actions,
                    facts,
                    {fact.action_id: fact for fact in facts},
                    {int(item["action_id"]): item for item in actions},
                    Counter(_rank_of(card) for card in observation["my_info"]["hand_cards"]),
                    str(current_round["current_level_rank"]),
                )
                self.assertIsNotNone(routes)
                self.assertEqual(len(routes or ()), 1)

        self.assertEqual(formula_patterns["single"], 6)
        self.assertEqual(formula_patterns["pair"] + formula_patterns["triple"], 0)
        self.assertEqual(sum(formula_patterns.values()) + no_direct, state_count)

    def test_untuned_independent_initial_deal_interval_keeps_relationship_fail_closed(self) -> None:
        from agents.opening_strategy import _rank_of

        formula_patterns: Counter[str] = Counter()
        no_direct = 0
        for seed in range(20000, 20200):
            game = GuanDanGame(seed=seed, current_level_rank="2")
            observation = game.reset()
            actions = game.legal_actions()
            chosen = self.strategy.select_action(
                observation, actions, evaluate_hand(observation, actions),
            )
            if chosen is None:
                no_direct += 1
                continue
            action = next(item for item in actions if item["action_id"] == chosen)
            pattern = str(action["declared_pattern"])
            formula_patterns[pattern] += 1
            self.assertIn(chosen, {item["action_id"] for item in actions})
            facts = summarize_candidate_structures(observation, actions)
            contrasts = summarize_candidate_contrasts(observation, actions)
            assert facts is not None and contrasts is not None
            if pattern == "single":
                self.assertTrue(
                    self.strategy._small_single_relationships_are_source_supported(
                        int(chosen), contrasts, {fact.action_id: fact for fact in facts},
                    )
                )
            else:
                self.assertIn(pattern, {"pair", "triple"})
                self.assertFalse(any(chosen in item.action_ids for item in contrasts))
                current_round = observation["current_round"]
                routes = self.strategy._eligible_natural_group_routes(
                    observation,
                    actions,
                    facts,
                    {fact.action_id: fact for fact in facts},
                    {int(item["action_id"]): item for item in actions},
                    Counter(_rank_of(card) for card in observation["my_info"]["hand_cards"]),
                    str(current_round["current_level_rank"]),
                )
                self.assertIsNotNone(routes)
                self.assertEqual(len(routes or ()), 1)

        self.assertEqual(sum(formula_patterns.values()) + no_direct, 200)


if __name__ == "__main__":
    unittest.main()
