"""Engine-backed regressions for public model-before action contrasts."""

from copy import deepcopy
from collections import Counter
from collections.abc import Callable
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from agents.action_structure import (
    CANDIDATE_RELATION_KINDS,
    representative_candidate_contrasts,
    select_candidate_structure_representatives,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
)
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import (
    DeepSeekClient,
    DeepSeekSuggestion,
    PROMPT_MAX_CANDIDATE_ACTIONS,
    _PROMPT_RELATION_SOURCE_IDS,
    _PROMPT_RELATION_KIND_ORDER,
)
from agents.game_phase import classify_game_phase
from agents.strategy_recommendation import build_strategy_recommendation
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame
from evaluation.h3_model_probe_fixtures import build_h3_model_probe_fixtures, build_h3_model_probe_opening_fixtures
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever
from agents.rag_advisor import RAGAdvisor
from agents.strategy_intent_prompt import RELATION_PROMPT_TEXT


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


def _midgame_engine_game_with_fixed_hand(hand_tokens: list[str]) -> GuanDanGame:
    """Construct a public midgame-shaped preset with a focused acting hand."""

    selected = list(_cards(hand_tokens))
    deck = build_double_deck()
    for card in selected:
        deck.remove(card)
    if len(selected) > 27:
        raise ValueError("fixed hand exceeds a complete-deal hand size")
    hands = {
        1: tuple(selected),
        2: tuple(deck[:20]),
        3: tuple(deck[20:40]),
        4: tuple(deck[40:60]),
    }
    return GuanDanGame(current_level_rank="2", preset_hands=hands)


def _take_cards(
    deck: list[Card], predicate: Callable[[Card], bool], count: int,
) -> list[Card]:
    selected: list[Card] = []
    for card in tuple(deck):
        if predicate(card):
            selected.append(card)
            deck.remove(card)
            if len(selected) == count:
                break
    if len(selected) != count:
        raise ValueError("synthetic deal does not contain requested cards")
    return selected


def _engine_follow_bomb_game(
    *,
    follow_rank: str,
    table_rank: str,
    follow_rank_count: int = 5,
    current_level_rank: str = "2",
    include_follow_wildcard: bool = False,
    excluded_filler_ranks: set[str] | None = None,
) -> GuanDanGame:
    """Build a complete deal, then reach a genuine follow through legal steps."""

    deck = list(build_double_deck())
    follower = _take_cards(deck, lambda card: card.rank == follow_rank, follow_rank_count)
    leader_bomb = _take_cards(deck, lambda card: card.rank == table_rank, 4)
    if include_follow_wildcard:
        follower.extend(
            _take_cards(
                deck,
                lambda card: card.rank == current_level_rank and card.suit == "H",
                1,
            )
        )
    wildcard_token = Card(rank=current_level_rank, suit="H")
    excluded_follower_filler_ranks = set(excluded_filler_ranks or ())
    follower.extend(
        _take_cards(
            deck,
            lambda card: (
                card.rank != follow_rank
                and card.rank not in excluded_follower_filler_ranks
                and card != wildcard_token
            ),
            27 - len(follower),
        )
    )

    leader = list(leader_bomb)
    # Leave many natural singleton leads so two ordinary rounds can be
    # completed without consuming the bomb used for the follow fixture.
    excluded_ranks = set(excluded_filler_ranks or ()) | {table_rank}
    seen_ranks: set[str] = set()
    for card in tuple(deck):
        if card.rank in excluded_ranks or card.rank in {"A", "K"} or card.rank in seen_ranks:
            continue
        leader.append(card)
        deck.remove(card)
        seen_ranks.add(card.rank)
        if len(leader) == 4 + 12:
            break
    for filler_rank in ("A", "K"):
        if filler_rank in excluded_ranks:
            continue
        needed = 27 - len(leader)
        if needed <= 0:
            break
        available = [card for card in deck if card.rank == filler_rank]
        take = min(needed, len(available))
        leader.extend(_take_cards(deck, lambda card, rank=filler_rank: card.rank == rank, take))
    if len(leader) < 27:
        leader.extend(_take_cards(deck, lambda card: card.rank not in excluded_ranks, 27 - len(leader)))
    if len(leader) != 27 or len(follower) != 27:
        raise ValueError("synthetic complete deal has incorrect hand sizes")

    hands = {
        1: tuple(follower),
        4: tuple(leader),
        2: tuple(deck[:27]),
        3: tuple(deck[27:54]),
    }
    game = GuanDanGame(
        current_level_rank=current_level_rank,
        preset_hands=hands,
        starting_player_id=4,
    )
    game.reset()

    def step_first_natural_single() -> None:
        action = next(
            item for item in game.legal_actions()
            if item["declared_pattern"] == "single" and item["wildcard_count"] == 0
        )
        game.step(int(action["action_id"]))

    def step_pass() -> None:
        action = next(item for item in game.legal_actions() if item["declared_pattern"] == "pass")
        game.step(int(action["action_id"]))

    for _ in range(2):
        step_first_natural_single()
        for _ in range(3):
            step_pass()
    table_action = next(
        action for action in game.legal_actions()
        if action["declared_pattern"] == "bomb"
        and len(action["carrier_cards"]) == 4
        and all(card[:-1] == table_rank for card in action["carrier_cards"])
        and action["wildcard_count"] == 0
    )
    game.step(int(table_action["action_id"]))
    observation = game.observe()
    if observation["my_info"]["player_id"] != 1 or observation["current_round"]["constraint"] == "free":
        raise AssertionError("synthetic legal replay did not reach the intended follow seat")
    return game


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


def _capture_production_request(
    observation: dict[str, object],
    actions: list[dict[str, object]],
    *,
    opening_formula_enabled: bool,
    advisor: RAGAdvisor,
) -> tuple["DeepSeekAIAgent", "_CapturingProductionClient", "_RequestCapturingTransport"]:
    recommendation = build_strategy_recommendation(observation, actions)
    chosen_id = recommendation.action_ids[0] if recommendation.action_ids else int(actions[0]["action_id"])
    transport = _RequestCapturingTransport(chosen_id)
    client = _CapturingProductionClient(
        "offline-test-key", "https://offline.invalid", "offline-test",
        max_retries=0, transport=transport,
    )
    safe_config = type(
        "OfflineConfig",
        (),
        {"card_tracking_enabled": False, "hand_evaluation_enabled": True,
         "opening_formula_enabled": opening_formula_enabled},
    )()
    with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
        "agents.deepseek_ai.evaluate_hand",
        return_value={"label": "中等", "total_score": 50, "control_score": 10},
    ):
        agent = DeepSeekAIAgent(
            1, client, rag_advisor=advisor, rag_top_k=3,
            hand_evaluation_enabled=True, opening_formula_enabled=opening_formula_enabled,
            strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
            strategy_recommendation_enabled=True,
        )
        selected_id = agent.select_action(observation, actions)
    if transport.calls != 1 or selected_id != chosen_id or agent.last_decision_source != "model":
        raise AssertionError("offline_request_path_not_preserved")
    return agent, client, transport


class _RecordingClient:
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self.prompt_actions: list[dict[str, object]] = []

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.prompt_actions = list(kwargs["prompt_actions"])
        return DeepSeekSuggestion(self.action_id, None)


class _RequestCapturingTransport:
    """No-network SSE transport that inspects the actual production request."""

    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self.calls = 0
        self.prompt = ""
        self.candidate_ids: tuple[int, ...] = ()

    def __call__(self, request: object, timeout: float) -> str:
        self.calls += 1
        raw = getattr(request, "data", None)
        if not isinstance(raw, bytes):
            raise OSError("request_body_missing")
        envelope = json.loads(raw.decode("utf-8"))
        messages = envelope.get("messages")
        if not isinstance(messages, list):
            raise OSError("request_messages_missing")
        users = [item for item in messages if isinstance(item, dict) and item.get("role") == "user"]
        if len(users) != 1 or not isinstance(users[0].get("content"), str):
            raise OSError("request_user_prompt_missing")
        self.prompt = users[0]["content"]
        start = self.prompt.find("【候选动作】")
        end = self.prompt.find("【规则库依据】")
        if start < 0 or end <= start:
            raise OSError("request_candidates_missing")
        rows = re.findall(r"#(\d+)\s+action_id=(\d+)\s+\|", self.prompt[start:end])
        if not rows or any(left != right for left, right in rows):
            raise OSError("request_candidates_invalid")
        self.candidate_ids = tuple(int(left) for left, _ in rows)
        if self.action_id not in self.candidate_ids:
            raise OSError("response_action_not_displayed")
        content = json.dumps({"action_id": self.action_id}, separators=(",", ":"))
        chunk = json.dumps({"choices": [{"delta": {"content": content}}]})
        return f"data: {chunk}\n\ndata: [DONE]\n"


class _CapturingProductionClient(DeepSeekClient):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.captured_kwargs: dict[str, object] = {}
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def suggest_action_id(self, **kwargs: object) -> DeepSeekSuggestion:
        self.captured_kwargs = dict(kwargs)
        return super().suggest_action_id(**kwargs)


class StrategyRelationshipContrastTests(unittest.TestCase):
    def test_natural_pair_rag_opportunity_is_broader_than_same_rank_pair_single_contrast(self) -> None:
        game = _game(["2S", "2C", "3S", "4H"])
        observation = game.reset()
        actions = game.legal_actions()
        contrasts = summarize_candidate_contrasts(observation, actions)
        applicability = RAGAdvisor._candidate_applicability(observation, actions)

        self.assertIsNotNone(contrasts)
        self.assertIsNotNone(applicability)
        assert contrasts is not None and applicability is not None
        self.assertNotIn("natural_pair_single", {item.kind for item in contrasts})
        self.assertTrue(applicability["natural_pair"])
        self.assertFalse(applicability["natural_pair_single"])

    def test_engine_bomb_contrast_protects_both_ids_and_explains_public_tradeoff(self) -> None:
        for rank in ("7", "9"):
            with self.subTest(rank=rank):
                game = _game([f"{rank}S", f"{rank}H", f"{rank}C", f"{rank}D", f"{rank}S", "3S", "4H"])
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
                self.assertIn("同点数自然炸弹残余用途对照", prompt)
                self.assertIn("留牌边际判据", prompt)
                self.assertIn("留牌事实", prompt)
                self.assertIn("可有条件倾向一并打出", prompt)
                self.assertIn("未识别不等于无未来用途", prompt)
                self.assertIn("不是动作指令", prompt)

    def test_free_lead_bomb_residual_uses_share_public_natural_structure_facts(self) -> None:
        cases = (
            (["7S", "7H", "7C", "7D", "7S", "7H", "3S", "4H"], "pair"),
            (["8S", "8H", "8C", "8D", "8S", "8H", "8C", "3S", "4H"], "triple"),
            (["9S", "9H", "9C", "9D", "9S", "9H", "9C", "9D"], "bomb"),
            (["6S", "6H", "6C", "6D", "6S", "3S", "4H", "5C", "7D"], "straight"),
        )
        for hand, expected_use in cases:
            with self.subTest(expected_use=expected_use):
                game = _game(hand)
                observation = game.reset()
                actions = game.legal_actions()
                contrasts = tuple(
                    item for item in summarize_candidate_contrasts(observation, actions) or ()
                    if item.kind == "bomb_residual"
                )
                self.assertTrue(contrasts)
                by_id = {int(action["action_id"]): action for action in actions}
                facts = {fact.action_id: fact for fact in summarize_candidate_structures(observation, actions) or ()}
                shorter = next(
                    contrast.action_ids[0]
                    for contrast in contrasts
                    if len(by_id[contrast.action_ids[0]]["carrier_cards"]) == 4
                )
                rank_uses = facts[shorter].residual_rank_uses
                self.assertIsNotNone(rank_uses)
                assert rank_uses is not None
                self.assertIn(expected_use, rank_uses[0].natural_pattern_kinds)

                recommendation = build_strategy_recommendation(observation, actions)
                final_actions = DeepSeekClient.prepare_prompt_actions(
                    actions, **_context(observation, actions, recommendation)
                )
                final_ids = {int(action["action_id"]) for action in final_actions}
                prompt = DeepSeekClient._build_structured_prompt(
                    my_info=observation["my_info"], current_round=observation["current_round"],
                    other_players=observation["other_players"], history=observation["history"],
                    legal_actions=final_actions, strategy_recommendation=recommendation,
                    residual_structure_source_actions=actions,
                )
                self.assertTrue(set(contrasts[0].action_ids).issubset(final_ids))
                self.assertIn("留牌事实", prompt)
                self.assertIn("所出点残留=", prompt)
                self.assertIn("可能重叠", prompt)

    def test_residual_control_resource_is_a_counted_cue_not_a_future_control_claim(self) -> None:
        game = _game(["5S", "5H", "5C", "5D", "5S", "AS", "3S", "4H"])
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "bomb_residual")
        facts = {fact.action_id: fact for fact in summarize_candidate_structures(observation, actions) or ()}
        shorter = facts[contrast.action_ids[0]]
        self.assertEqual(shorter.residual_natural_control_resource_count, 1)
        recommendation = build_strategy_recommendation(observation, actions)
        final_actions = DeepSeekClient.prepare_prompt_actions(
            actions, **_context(observation, actions, recommendation)
        )
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=observation["my_info"], current_round=observation["current_round"],
            other_players=observation["other_players"], history=observation["history"],
            legal_actions=final_actions, strategy_recommendation=recommendation,
            residual_structure_source_actions=actions,
        )
        self.assertIn("自然控制牌候选=1", prompt)
        self.assertIn("不保证未来牌权", prompt)

    def test_follow_bomb_residual_covers_natural_lengths_four_through_eight(self) -> None:
        expected_by_hand_count = {
            5: {(4, 5)},
            6: {(4, 5), (5, 6)},
            7: {(4, 5), (6, 7)},
            8: {(4, 5), (7, 8)},
        }
        for count, expected_pairs in expected_by_hand_count.items():
            with self.subTest(follow_rank_count=count):
                game = _engine_follow_bomb_game(
                    follow_rank="7", table_rank="3", follow_rank_count=count,
                    excluded_filler_ranks={"6", "8"},
                )
                observation = game.observe()
                actions = game.legal_actions()
                self.assertNotEqual(observation["current_round"]["constraint"], "free")
                self.assertEqual(classify_game_phase(observation).phase, "midgame")
                contrasts = tuple(
                    item for item in summarize_candidate_contrasts(observation, actions) or ()
                    if item.kind == "bomb_residual"
                )
                by_id = {int(action["action_id"]): action for action in actions}
                facts = {fact.action_id: fact for fact in summarize_candidate_structures(observation, actions) or ()}
                actual_pairs = set()
                for contrast in contrasts:
                    shorter, longer = (by_id[action_id] for action_id in contrast.action_ids)
                    lengths = (len(shorter["carrier_cards"]), len(longer["carrier_cards"]))
                    actual_pairs.add(lengths)
                    self.assertLess(lengths[0], lengths[1])
                    self.assertEqual((shorter["wildcard_count"], longer["wildcard_count"]), (0, 0))
                    self.assertTrue(all(card[:-1] == "7" for card in shorter["carrier_cards"] + longer["carrier_cards"]))
                    shorter_use = facts[contrast.action_ids[0]].residual_rank_uses
                    longer_use = facts[contrast.action_ids[1]].residual_rank_uses
                    self.assertIsNotNone(shorter_use)
                    self.assertIsNotNone(longer_use)
                    assert shorter_use is not None and longer_use is not None
                    self.assertGreater(shorter_use[0].remaining_count, longer_use[0].remaining_count)
                self.assertEqual(actual_pairs, expected_pairs)
                if count == 8:
                    rank_use = facts[next(item.action_ids[0] for item in contrasts if len(by_id[item.action_ids[0]]["carrier_cards"]) == 4)].residual_rank_uses
                    assert rank_use is not None
                    self.assertIn("bomb", rank_use[0].natural_pattern_kinds)

        missing_size = _engine_follow_bomb_game(
            follow_rank="7", table_rank="3", follow_rank_count=4,
        )
        self.assertFalse(any(
            item.kind == "bomb_residual"
            for item in summarize_candidate_contrasts(missing_size.observe(), missing_size.legal_actions()) or ()
        ))

        wildcard_follow = _engine_follow_bomb_game(
            follow_rank="8", table_rank="3", follow_rank_count=4,
            current_level_rank="7", include_follow_wildcard=True,
        )
        wildcard_actions = wildcard_follow.legal_actions()
        self.assertTrue(any(
            action["declared_pattern"] == "bomb" and len(action["carrier_cards"]) == 4
            and action["wildcard_count"] == 0 and all(card[:-1] == "8" for card in action["carrier_cards"])
            for action in wildcard_actions
        ))
        self.assertTrue(any(
            action["declared_pattern"] == "bomb" and len(action["carrier_cards"]) == 5
            and action["wildcard_count"] > 0 and set(action["declared_cards"]) == {"8"}
            for action in wildcard_actions
        ))
        self.assertFalse(any(item.kind == "bomb_residual" for item in summarize_candidate_contrasts(wildcard_follow.observe(), wildcard_actions) or ()))

        malformed_carrier = deepcopy(wildcard_actions)
        natural_action = next(
            action for action in malformed_carrier
            if action["declared_pattern"] == "bomb" and action["wildcard_count"] == 0
        )
        natural_action["declared_cards"][0] = "A"
        self.assertIsNone(summarize_candidate_contrasts(wildcard_follow.observe(), malformed_carrier))

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
        self.assertIn("留牌事实", prompt)
        self.assertIn("未识别不等于无未来用途", prompt)

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

    def test_production_prompt_character_budgets_for_openings_and_80_candidate_cap(self) -> None:
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        opening_cases = (
            ("low_cost_single", 53, 24, 10_000),
            ("neutral_soft_pair", 83, 56, 16_000),
        )
        for fixture, expected in zip(build_h3_model_probe_opening_fixtures(), opening_cases):
            name, raw_count, candidate_count, char_budget = expected
            with self.subTest(scene=name):
                self.assertEqual(fixture.name, name)
                self.assertEqual(len(fixture.legal_actions), raw_count)
                agent, client, transport = _capture_production_request(
                    fixture.observation,
                    fixture.legal_actions,
                    opening_formula_enabled=True,
                    advisor=advisor,
                )
                self.assertEqual(len(transport.candidate_ids), candidate_count)
                self.assertEqual(len(set(transport.candidate_ids)), candidate_count)
                self.assertLessEqual(len(transport.prompt), char_budget)
                self.assertNotIn("出后用途=", transport.prompt)
                if "开局跨牌型取舍" in transport.prompt:
                    self.assertIn("比较出后余组/孤张与拆组成本", transport.prompt)
                    self.assertNotIn("留牌边际判据", transport.prompt)
                else:
                    self.assertIn("留牌边际判据", transport.prompt)
                self.assertIn("留牌事实", transport.prompt)
                self.assertEqual(agent.last_decision_source, "model")
                self.assertEqual(
                    client.captured_kwargs.get("strategy_recommendation"),
                    agent.last_strategy_recommendation,
                )

        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        _, _, transport = _capture_production_request(
            observation,
            actions,
            opening_formula_enabled=False,
            advisor=advisor,
        )
        self.assertEqual(len(transport.candidate_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertLessEqual(len(transport.prompt), 30_000)
        self.assertNotIn("出后用途=", transport.prompt)

    def test_prompt_relation_budget_is_paired_source_aware_and_bounded(self) -> None:
        self.assertEqual(set(_PROMPT_RELATION_KIND_ORDER), set(CANDIDATE_RELATION_KINDS))
        self.assertEqual(set(_PROMPT_RELATION_SOURCE_IDS), set(CANDIDATE_RELATION_KINDS))
        game = GuanDanGame(seed=0, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        agent, client, transport = _capture_production_request(
            observation,
            actions,
            opening_formula_enabled=False,
            advisor=advisor,
        )
        final_ids = set(transport.candidate_ids)
        full_contrasts = summarize_candidate_contrasts(observation, actions)
        self.assertIsNotNone(full_contrasts)
        assert full_contrasts is not None
        self.assertEqual(len(full_contrasts), 64)
        self.assertTrue(any(item.kind == "bomb_wildcard_strength" for item in full_contrasts))
        rag_context = client.captured_kwargs.get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)
        selected = DeepSeekClient._prompt_candidate_contrasts(
            observation,
            actions,
            strategy_recommendation=agent.last_strategy_recommendation,
            rag_context=rag_context,
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertLessEqual(len(selected), 24)
        self.assertTrue(all(count <= 2 for count in Counter(item.kind for item in selected).values()))
        full_pair_set = {frozenset(item.action_ids) for item in full_contrasts}
        selected_pair_set = {frozenset(item.action_ids) for item in selected}
        self.assertTrue(selected_pair_set.issubset(full_pair_set))
        active_source_ids = {
            str(hit["source_id"])
            for hit in rag_context.get("experience_hits", [])
            if isinstance(hit, dict) and isinstance(hit.get("source_id"), str)
        }
        self.assertTrue(
            _PROMPT_RELATION_SOURCE_IDS.get(selected[0].kind, frozenset()) & active_source_ids
        )
        self.assertEqual(len(final_ids), len(set(transport.candidate_ids)))
        self.assertLessEqual(len(final_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertTrue(
            set(getattr(agent.last_strategy_recommendation, "action_ids", ())).issubset(final_ids)
        )

        prompt_lines = transport.prompt.splitlines()
        relation_start = prompt_lines.index("【公开关系对照】") + 1
        relation_end = next(
            (index for index in range(relation_start, len(prompt_lines))
             if prompt_lines[index].startswith("【")),
            len(prompt_lines),
        )
        relation_section = "\n".join(prompt_lines[relation_start:relation_end])
        displayed_pairs: set[frozenset[int]] = set()
        for line in relation_section.splitlines():
            ids = {int(value) for value in re.findall(r"action_id=(\d+)", line)}
            if ids:
                self.assertEqual(len(ids), 2)
                pair = frozenset(ids)
                self.assertTrue(pair.issubset(final_ids))
                self.assertIn(pair, full_pair_set)
                displayed_pairs.add(pair)
        self.assertTrue(displayed_pairs)
        self.assertTrue(displayed_pairs.issubset(selected_pair_set))
        self.assertEqual(agent.last_decision_source, "model")

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

    def test_follow_contrasts_require_matching_public_history_and_cover_nonresource_blocks(self) -> None:
        fixtures = build_h3_model_probe_fixtures()
        teammate = fixtures[4]
        danger = fixtures[5]
        teammate_contrasts = summarize_candidate_contrasts(teammate.observation, teammate.legal_actions)
        danger_contrasts = summarize_candidate_contrasts(danger.observation, danger.legal_actions)
        assert teammate_contrasts is not None and danger_contrasts is not None
        self.assertIn("teammate_control_resource", {item.kind for item in teammate_contrasts})
        self.assertIn("danger_block_choice", {item.kind for item in danger_contrasts})

        mismatched_history = deepcopy(teammate.observation)
        history_actions = mismatched_history["history"]["actions"]
        leader = next(item for item in history_actions if item["declared_pattern"] != "pass")
        leader["carrier_cards"] = ["AS"]
        after_mismatch = summarize_candidate_contrasts(mismatched_history, teammate.legal_actions)
        assert after_mismatch is not None
        self.assertNotIn("teammate_control_resource", {item.kind for item in after_mismatch})

        inconsistent_optional_field = deepcopy(teammate.observation)
        history_actions = inconsistent_optional_field["history"]["actions"]
        leader = next(item for item in history_actions if item["declared_pattern"] != "pass")
        leader["wildcard_count"] = 1
        after_optional_mismatch = summarize_candidate_contrasts(inconsistent_optional_field, teammate.legal_actions)
        assert after_optional_mismatch is not None
        self.assertNotIn("teammate_control_resource", {item.kind for item in after_optional_mismatch})

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
        bomb_contrasts = tuple(
            item for item in representative_candidate_contrasts(observation, actions) or ()
            if item.kind == "bomb_residual"
        )
        self.assertGreater(len(bomb_contrasts), 0)
        self.assertLessEqual(len(bomb_contrasts), 2)
        recommendation = build_strategy_recommendation(observation, actions)
        final_actions = DeepSeekClient.prepare_prompt_actions(actions, **_context(observation, actions, recommendation))
        final_ids = {int(action["action_id"]) for action in final_actions}

        self.assertLessEqual(len(final_actions), PROMPT_MAX_CANDIDATE_ACTIONS)
        for contrast in bomb_contrasts:
            self.assertTrue(set(contrast.action_ids).issubset(final_ids))
        self.assertLessEqual(len(recommendation.action_ids), 3)
        self.assertIsNotNone(DeepSeekClient._validated_strategy_recommendation(recommendation, actions))
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
        self.assertGreater(bomb_states, 0)
        self.assertEqual(visible_pairs, bomb_states)
        self.assertEqual(recommended_pairs, bomb_states)

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

    def test_real_client_request_unifies_router_rag_recommendation_and_public_contrast(self) -> None:
        fixtures = build_h3_model_probe_fixtures()
        cases = (
            (fixtures[0], "bomb_residual", "同点数自然炸弹残余用途对照", "同点不同长度炸弹的留牌边际用途、余组负担与炸弹资源/牌权成本", "炸弹与通配牌管理", "exp_bomb_wildcard_001"),
            (fixtures[1], "natural_single_cost", "自然单张成本对照", "不拆已成同点组的低成本自然单张", "自然单张成本与试探路线", "exp_soft_single_cost_probe_001"),
            (fixtures[2], "natural_pair_single", "同点数对子/单张对照", "自然对子清理与同点单张拆分", "传递牌型与清理低价值牌", None),
            (fixtures[3], "natural_group_single", "自然组牌/普通单张对照", "自然对子/三张与普通单张的清理和余组取舍", "可撤回的对子试探假设", "exp_soft_pair_probe_001"),
            (fixtures[4], "teammate_control_resource", "队友控桌对照", "队友控桌时让牌与消耗控制资源的取舍", "队友协同与让牌", None),
            (fixtures[5], "danger_block_choice", "危险对手对照", "危险对手控桌时pass与合法压制候选的取舍", "危险对手阻断", None),
            (fixtures[7], "wildcard_resource", "通配资源对照", "自然牌型与通配资源消耗", "炸弹与通配牌管理", "exp_bomb_wildcard_001"),
        )
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        safe_config = type(
            "OfflineConfig",
            (),
            {"card_tracking_enabled": False, "hand_evaluation_enabled": True, "opening_formula_enabled": True},
        )()

        for fixture, relation_kind, relation_marker, intent_marker, knowledge_marker, expected_source in cases:
            with self.subTest(scenario=fixture.name):
                contrasts = summarize_candidate_contrasts(fixture.observation, fixture.legal_actions)
                assert contrasts is not None
                contrast = next(item for item in contrasts if item.kind == relation_kind)
                transport = _RequestCapturingTransport(contrast.action_ids[0])
                client = _CapturingProductionClient(
                    "offline-test-key", "https://offline.invalid", "offline-test",
                    max_retries=0, transport=transport,
                )
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
                    "agents.deepseek_ai.evaluate_hand",
                    return_value={"label": "中等", "total_score": 50, "control_score": 10},
                ):
                    agent = DeepSeekAIAgent(
                        1, client, rag_advisor=advisor, rag_top_k=3,
                        hand_evaluation_enabled=True, opening_formula_enabled=True,
                        strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                        strategy_recommendation_enabled=True,
                    )
                    selected_id = agent.select_action(fixture.observation, fixture.legal_actions)

                self.assertEqual(transport.calls, 1)
                self.assertEqual(selected_id, contrast.action_ids[0])
                self.assertEqual(agent.last_decision_source, "model")
                self.assertIn(relation_marker, transport.prompt)
                intent = agent.last_strategy_intent
                self.assertIsNotNone(intent)
                assert intent is not None
                self.assertIn(relation_kind, intent.candidate_relation_kinds)
                self.assertEqual(agent.last_strategy_intent_prompt.status, "ready")
                self.assertTrue(agent.last_strategy_intent_prompt.text)
                self.assertIn(intent_marker, agent.last_strategy_intent_prompt.text)
                self.assertIn(agent.last_strategy_intent_prompt.text, transport.prompt)
                captured = client.captured_kwargs
                rag_context = captured.get("rag_context")
                self.assertIsInstance(rag_context, dict)
                assert isinstance(rag_context, dict)
                scene_tags = rag_context.get("scene_tags")
                self.assertIsInstance(scene_tags, dict)
                assert isinstance(scene_tags, dict)
                self.assertIn(relation_kind, str(scene_tags.get("candidate_relation_kinds", "")).split(","))
                self.assertEqual(scene_tags.get("strategy_intent"), intent.intent)
                experience_hits = rag_context.get("experience_hits")
                self.assertIsInstance(experience_hits, list)
                assert isinstance(experience_hits, list)
                hit_ids = {item.get("source_id") for item in experience_hits if isinstance(item, dict)}
                if expected_source is not None:
                    self.assertIn(expected_source, hit_ids)
                    self.assertIn("可撤回软假设：", transport.prompt)
                    self.assertIn(knowledge_marker, transport.prompt)
                else:
                    self.assertNotIn("可撤回软假设：", transport.prompt)
                if relation_kind == "natural_group_single":
                    applicability = RAGAdvisor._candidate_applicability(
                        fixture.observation, fixture.legal_actions
                    )
                    self.assertIsNotNone(applicability)
                    assert applicability is not None
                    self.assertTrue(applicability["natural_group_single"])
                self.assertNotIn("source_tier", transport.prompt)
                self.assertNotIn("王春国", transport.prompt)
                self.assertNotIn("https://", transport.prompt)
                self.assertLessEqual(len(transport.candidate_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
                self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
                self.assertTrue(set(transport.candidate_ids).issubset({int(a["action_id"]) for a in fixture.legal_actions}))
                recommendation = agent.last_strategy_recommendation
                validated = DeepSeekClient._validated_strategy_recommendation(
                    recommendation, fixture.legal_actions
                )
                self.assertIsNotNone(validated)
                assert validated is not None
                self.assertTrue(set(validated.action_ids).issubset(transport.candidate_ids))

    def test_free_and_follow_bomb_relations_reach_actual_request_and_both_choices_stay_model_owned(self) -> None:
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        safe_config = type(
            "OfflineConfig",
            (),
            {"card_tracking_enabled": False, "hand_evaluation_enabled": True, "opening_formula_enabled": False},
        )()
        scenarios: list[tuple[str, GuanDanGame]] = []
        lead_game = _game(["7S", "7H", "7C", "7D", "7S", "7H", "7C", "7D", "3S"])
        lead_game.reset()
        scenarios.append(("lead", lead_game))
        scenarios.extend(
            (
                f"follow-{count}",
                _engine_follow_bomb_game(
                    follow_rank="7", table_rank="3", follow_rank_count=count,
                    excluded_filler_ranks={"6", "8"},
                ),
            )
            for count in (5, 6, 7, 8)
        )

        for scenario_name, game in scenarios:
            observation = game.observe()
            actions = game.legal_actions()
            contrasts = tuple(
                item for item in summarize_candidate_contrasts(observation, actions) or ()
                if item.kind == "bomb_residual"
            )
            self.assertTrue(contrasts)
            recommendation = build_strategy_recommendation(observation, actions)
            if scenario_name.startswith("follow"):
                self.assertNotEqual(observation["current_round"]["constraint"], "free")
                self.assertEqual(classify_game_phase(observation).phase, "midgame")

            for contrast in contrasts:
                for action_id in contrast.action_ids:
                    with self.subTest(scenario=scenario_name, choice=action_id):
                        transport = _RequestCapturingTransport(action_id)
                        client = _CapturingProductionClient(
                            "offline-test-key", "https://offline.invalid", "offline-test",
                            max_retries=0, transport=transport,
                        )
                        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
                            "agents.deepseek_ai.evaluate_hand",
                            return_value={"label": "中等", "total_score": 50, "control_score": 10},
                        ):
                            agent = DeepSeekAIAgent(
                                1, client, rag_advisor=advisor, rag_top_k=3,
                                hand_evaluation_enabled=True, opening_formula_enabled=False,
                                strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                                strategy_recommendation_enabled=True,
                            )
                            selected_id = agent.select_action(observation, actions)

                        self.assertEqual(transport.calls, 1)
                        self.assertEqual(selected_id, action_id)
                        self.assertEqual(agent.last_decision_source, "model")
                        self.assertIn("同点数自然炸弹残余用途对照", transport.prompt)
                        self.assertIn("留牌事实", transport.prompt)
                        self.assertIn("价值不明时只比较当前可证成本", transport.prompt)
                        self.assertIn("不保证未来牌权", transport.prompt)
                        self.assertIn("可有条件倾向一并打出", transport.prompt)
                        self.assertIn("一次出完、公开紧急性", transport.prompt)
                        self.assertIsNotNone(agent.last_strategy_intent)
                        assert agent.last_strategy_intent is not None
                        self.assertIn("bomb_residual", agent.last_strategy_intent.candidate_relation_kinds)
                        self.assertEqual(agent.last_strategy_intent_prompt.status, "ready")
                        self.assertIn("同点不同长度炸弹的留牌边际用途", agent.last_strategy_intent_prompt.text)
                        captured = client.captured_kwargs
                        first_pass_ids = {
                            int(action["action_id"]) for action in captured["prompt_actions"]
                        }
                        self.assertTrue(set(contrast.action_ids).issubset(first_pass_ids))
                        self.assertTrue(set(contrast.action_ids).issubset(transport.candidate_ids))
                        self.assertLessEqual(len(transport.candidate_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
                        self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
                        self.assertTrue(set(transport.candidate_ids).issubset({int(item["action_id"]) for item in actions}))
                        validated = DeepSeekClient._validated_strategy_recommendation(
                            agent.last_strategy_recommendation, actions
                        )
                        self.assertIsNotNone(validated)
                        assert validated is not None
                        self.assertTrue(set(validated.action_ids).issubset(first_pass_ids))
                        self.assertTrue(set(validated.action_ids).issubset(transport.candidate_ids))
                        rag_context = captured.get("rag_context")
                        self.assertIsInstance(rag_context, dict)
                        assert isinstance(rag_context, dict)
                        hits = rag_context.get("experience_hits")
                        self.assertIsInstance(hits, list)
                        assert isinstance(hits, list)
                        self.assertIn(
                            "exp_bomb_wildcard_001",
                            {item.get("source_id") for item in hits if isinstance(item, dict)},
                        )
                        self.assertIn("可撤回软假设：", transport.prompt)
                        self.assertNotIn("source_tier", transport.prompt)
                        self.assertNotIn("https://", transport.prompt)

    def test_natural_bomb_strength_resource_relation_reaches_real_request(self) -> None:
        hand = [
            "5S", "5H", "5C", "5D", "5S",
            "7S", "7H", "7C", "7D", "7S", "7H",
            "3S", "4H",
        ]
        game = _game(hand)
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "bomb_strength_resource")
        applicability = RAGAdvisor._candidate_applicability(observation, actions)
        self.assertIsNotNone(applicability)
        assert applicability is not None
        self.assertTrue(applicability["bomb_strength_resource"])

        transport = _RequestCapturingTransport(contrast.action_ids[0])
        client = _CapturingProductionClient(
            "offline-test-key", "https://offline.invalid", "offline-test",
            max_retries=0, transport=transport,
        )
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        safe_config = type(
            "OfflineConfig",
            (),
            {"card_tracking_enabled": False, "hand_evaluation_enabled": True, "opening_formula_enabled": False},
        )()
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
            "agents.deepseek_ai.evaluate_hand",
            return_value={"label": "中等", "total_score": 50, "control_score": 10},
        ):
            agent = DeepSeekAIAgent(
                1, client, rag_advisor=advisor, rag_top_k=3,
                hand_evaluation_enabled=True, opening_formula_enabled=False,
                strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                strategy_recommendation_enabled=True,
            )
            selected_id = agent.select_action(observation, actions)

        self.assertEqual(transport.calls, 1)
        self.assertEqual(selected_id, contrast.action_ids[0])
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn("自然炸弹强度/资源对照", transport.prompt)
        self.assertIn("不规定先出小炸或大炸", transport.prompt)
        self.assertTrue(set(contrast.action_ids).issubset(transport.candidate_ids))
        self.assertLessEqual(len(transport.candidate_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
        self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
        self.assertTrue(set(transport.candidate_ids).issubset({int(item["action_id"]) for item in actions}))
        rag_context = client.captured_kwargs.get("rag_context")
        self.assertIsInstance(rag_context, dict)
        assert isinstance(rag_context, dict)
        hits = rag_context.get("experience_hits")
        self.assertIsInstance(hits, list)
        assert isinstance(hits, list)
        self.assertIn(
            "exp_bomb_wildcard_001",
            {item.get("source_id") for item in hits if isinstance(item, dict)},
        )
        self.assertIn("可撤回软假设：", transport.prompt)
        self.assertIn("自然炸弹", transport.prompt)
        recommendation = DeepSeekClient._validated_strategy_recommendation(
            agent.last_strategy_recommendation, actions
        )
        self.assertIsNotNone(recommendation)
        assert recommendation is not None
        self.assertTrue(set(recommendation.action_ids).issubset(transport.candidate_ids))

        second_transport = _RequestCapturingTransport(contrast.action_ids[1])
        second_client = _CapturingProductionClient(
            "offline-test-key", "https://offline.invalid", "offline-test",
            max_retries=0, transport=second_transport,
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
            "agents.deepseek_ai.evaluate_hand",
            return_value={"label": "中等", "total_score": 50, "control_score": 10},
        ):
            second_agent = DeepSeekAIAgent(
                1, second_client, rag_advisor=advisor, rag_top_k=3,
                hand_evaluation_enabled=True, opening_formula_enabled=False,
                strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                strategy_recommendation_enabled=True,
            )
            second_selected = second_agent.select_action(observation, actions)
        self.assertEqual(second_transport.calls, 1)
        self.assertEqual(second_selected, contrast.action_ids[1])
        self.assertEqual(second_agent.last_decision_source, "model")
        self.assertTrue(set(contrast.action_ids).issubset(second_transport.candidate_ids))

    def test_medium_opening_group_relation_activates_matching_b_principle_in_final_request(self) -> None:
        fixture = build_h3_model_probe_fixtures()[3]
        contrasts = summarize_candidate_contrasts(fixture.observation, fixture.legal_actions)
        assert contrasts is not None
        contrast = next(item for item in contrasts if item.kind == "natural_group_single")
        transport = _RequestCapturingTransport(contrast.action_ids[0])
        client = _CapturingProductionClient(
            "offline-test-key", "https://offline.invalid", "offline-test",
            max_retries=0, transport=transport,
        )
        safe_config = type(
            "OfflineConfig",
            (),
            {"card_tracking_enabled": False, "hand_evaluation_enabled": True, "opening_formula_enabled": True},
        )()
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
            "agents.deepseek_ai.evaluate_hand",
            return_value={"label": "中等", "total_score": 50, "control_score": 10},
        ):
            agent = DeepSeekAIAgent(
                1, client, rag_advisor=RAGAdvisor(
                    KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
                ),
                rag_top_k=3, hand_evaluation_enabled=True, opening_formula_enabled=True,
                strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                strategy_recommendation_enabled=True,
            )
            selected_id = agent.select_action(fixture.observation, fixture.legal_actions)

        self.assertEqual(transport.calls, 1)
        self.assertEqual(selected_id, contrast.action_ids[0])
        self.assertEqual(agent.last_decision_source, "model")
        self.assertIn("自然组牌/普通单张对照", transport.prompt)
        captured = client.captured_kwargs
        rag_context = captured.get("rag_context")
        assert isinstance(rag_context, dict)
        hits = rag_context.get("experience_hits")
        assert isinstance(hits, list)
        hit_ids = {item.get("source_id") for item in hits if isinstance(item, dict)}
        self.assertTrue(
            hit_ids & {"exp_lead_opening_medium_001", "exp_lead_opening_shape_001"}
        )
        self.assertTrue(
            any(marker in transport.prompt for marker in ("中性开局表达", "开局成型牌型与余组比较"))
        )

    def test_new_source_relationships_reach_real_request_with_both_canonical_sides(self) -> None:
        cases = (
            (
                "sequence",
                ["3S", "4S", "5S", "6S", "6H", "7S", "8S", "9C", "10D", "QC"],
                "sequence_structure_loss",
                "自然顺子/连组与同点组对照",
                None,
            ),
            (
                "straight_strength",
                ["3S", "4S", "5S", "6S", "6H", "7S", "8S", "9C", "10D", "QC"],
                "straight_strength",
                "自然顺子强弱对照",
                None,
            ),
            (
                "repartition",
                ["5S", "5H", "5C", "8S", "8H", "8C", "JS", "JH", "JC", "4S", "4H"],
                "triple_split_repartition",
                "三张拆分/三带二对照",
                "exp_soft_triple_repartition_001",
            ),
            (
                "straight_flush_bombs",
                ["5S", "6S", "6H", "6C", "6D", "7S", "8S", "8H", "8C", "8D", "9S"],
                "straight_flush_bomb_fragment",
                "同花顺/炸弹结构对照",
                "exp_soft_straight_flush_bomb_cost_001",
            ),
            (
                "steel_plates",
                ["3S", "3H", "3C", "4S", "4H", "4C", "8S", "8H", "8C", "9S", "9H", "9C"],
                "steel_plate_strength",
                "自然钢板强弱对照",
                "exp_soft_steel_plate_strength_001",
            ),
            (
                "triple_pair_gradient",
                ["7S", "7H", "7C", "5S", "5H", "8S", "8H", "10S", "10H", "QS", "QH"],
                "triple_pair_kicker_gradient",
                "三带二携带对子梯度",
                "exp_soft_triple_pair_gradient_001",
            ),
        )
        advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )
        safe_config = type(
            "OfflineConfig",
            (),
            {"card_tracking_enabled": False, "hand_evaluation_enabled": True, "opening_formula_enabled": True},
        )()

        for name, hand, relation_kind, marker, expected_source in cases:
            with self.subTest(relation=relation_kind):
                game = _midgame_engine_game_with_fixed_hand(hand)
                observation = game.reset()
                actions = game.legal_actions()
                contrasts = summarize_candidate_contrasts(observation, actions)
                assert contrasts is not None
                contrast = next(item for item in contrasts if item.kind == relation_kind)
                transport = _RequestCapturingTransport(contrast.action_ids[0])
                client = _CapturingProductionClient(
                    "offline-test-key", "https://offline.invalid", "offline-test",
                    max_retries=0, transport=transport,
                )
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=safe_config), patch(
                    "agents.deepseek_ai.evaluate_hand",
                    return_value={"label": "中等", "total_score": 50, "control_score": 10},
                ):
                    agent = DeepSeekAIAgent(
                        1, client, rag_advisor=advisor, rag_top_k=3,
                        hand_evaluation_enabled=True, opening_formula_enabled=True,
                        strategy_router_shadow_enabled=True, strategy_intent_prompt_enabled=True,
                        strategy_recommendation_enabled=True,
                    )
                    selected_id = agent.select_action(observation, actions)

                self.assertEqual(transport.calls, 1)
                self.assertEqual(selected_id, contrast.action_ids[0])
                self.assertEqual(agent.last_decision_source, "model")
                self.assertIn(marker, transport.prompt)
                self.assertTrue(set(contrast.action_ids).issubset(transport.candidate_ids))
                self.assertLessEqual(len(transport.candidate_ids), PROMPT_MAX_CANDIDATE_ACTIONS)
                self.assertEqual(len(transport.candidate_ids), len(set(transport.candidate_ids)))
                self.assertTrue(set(transport.candidate_ids).issubset({int(action["action_id"]) for action in actions}))
                captured = client.captured_kwargs
                self.assertEqual(len(captured["legal_actions"]), len(actions))
                recommendation = agent.last_strategy_recommendation
                validated = DeepSeekClient._validated_strategy_recommendation(recommendation, actions)
                self.assertIsNotNone(validated)
                assert validated is not None
                self.assertTrue(set(validated.action_ids).issubset(transport.candidate_ids))
                rag_context = captured.get("rag_context")
                self.assertIsInstance(rag_context, dict)
                assert isinstance(rag_context, dict)
                hits = rag_context.get("experience_hits")
                self.assertIsInstance(hits, list)
                assert isinstance(hits, list)
                hit_ids = {item.get("source_id") for item in hits if isinstance(item, dict)}
                if expected_source is not None:
                    self.assertIn(expected_source, hit_ids)
                    self.assertIn("可撤回软假设：", transport.prompt)
                self.assertNotIn("source_tier", transport.prompt)
                self.assertNotIn("王春国", transport.prompt)
                self.assertNotIn("https://", transport.prompt)

    def test_new_relation_applicability_is_false_without_a_legal_public_opportunity(self) -> None:
        game = _game(["3S", "5H", "8C", "JD", "AS"])
        observation = game.reset()
        actions = game.legal_actions()
        applicability = RAGAdvisor._candidate_applicability(observation, actions)
        assert applicability is not None
        for requirement in (
            "bomb_strength_resource",
            "sequence_structure_loss", "triple_split_repartition",
            "straight_flush_bomb_fragment", "steel_plate_strength",
            "triple_pair_kicker_gradient",
        ):
            with self.subTest(requirement=requirement):
                self.assertFalse(applicability[requirement])

    def test_straight_strength_orders_low_ace_window_below_six_high_window(self) -> None:
        game = _game(["AS", "2S", "3S", "4S", "5S", "2H", "3H", "4H", "5H", "6D", "QC"])
        observation = game.reset()
        actions = game.legal_actions()
        contrast = _contrast(observation, actions, "straight_strength")
        by_id = {int(action["action_id"]): action for action in actions}

        lower_ranks = {card[:-1] if card.endswith(("S", "H", "C", "D")) else card
                       for card in by_id[contrast.action_ids[0]]["declared_cards"]}
        higher_ranks = {card[:-1] if card.endswith(("S", "H", "C", "D")) else card
                        for card in by_id[contrast.action_ids[1]]["declared_cards"]}

        self.assertEqual(lower_ranks, {"A", "2", "3", "4", "5"})
        self.assertEqual(higher_ranks, {"2", "3", "4", "5", "6"})

    def test_every_candidate_relation_has_a_strict_intent_prompt_projection(self) -> None:
        from agents.action_structure import CANDIDATE_RELATION_KINDS

        self.assertEqual(set(RELATION_PROMPT_TEXT), set(CANDIDATE_RELATION_KINDS))

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
