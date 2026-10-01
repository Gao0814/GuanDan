"""Legal-state and request-boundary tests for M4 trade-off inputs."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.action_structure import (
    CandidateContrast,
    candidate_response_net_effect,
    summarize_candidate_contrasts,
    summarize_candidate_structures,
)
from agents.deepseek_client import DeepSeekClient
from engine.cards import Card, build_double_deck, card_to_token
from engine.game import GuanDanGame
from integrations.botzone.agent_runtime import build_agent_factory
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever
from agents.rag_advisor import RAGAdvisor


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(token)
    return Card(token[:-1], token[-1])


def _take(deck: list[Card], tokens: list[str]) -> list[Card]:
    result: list[Card] = []
    for token in tokens:
        card = _card(token)
        deck.remove(card)
        result.append(card)
    return result


def _deal(
    *,
    own_tokens: list[str],
    own_excluded_ranks: set[str],
    player_two_tokens: list[str] | None = None,
    player_two_excluded_ranks: set[str] | None = None,
    player_three_tokens: list[str] | None = None,
    player_three_excluded_ranks: set[str] | None = None,
) -> dict[int, tuple[Card, ...]]:
    """Build a complete 108-card deal with focused but unaltered legal hands."""
    deck = list(build_double_deck())
    hands = {1: _take(deck, own_tokens), 2: [], 3: [], 4: []}
    if player_two_tokens:
        hands[2] = _take(deck, player_two_tokens)
    if player_three_tokens:
        hands[3] = _take(deck, player_three_tokens)

    def fill(player_id: int, excluded_ranks: set[str] | None = None) -> None:
        excluded = excluded_ranks or set()
        while len(hands[player_id]) < 27:
            card = next((item for item in deck if item.rank not in excluded), None)
            if card is None:
                raise AssertionError("could not complete focused hand")
            deck.remove(card)
            hands[player_id].append(card)

    fill(1, own_excluded_ranks)
    fill(2, player_two_excluded_ranks)
    fill(3, player_three_excluded_ranks)
    hands[4] = list(deck)
    assert all(len(hand) == 27 for hand in hands.values())
    dealt = Counter(card_to_token(card) for hand in hands.values() for card in hand)
    full_deck = Counter(card_to_token(card) for card in build_double_deck())
    assert dealt == full_deck
    return {player_id: tuple(cards) for player_id, cards in hands.items()}


def _action(game: GuanDanGame, predicate) -> dict[str, object]:
    return next(item for item in game.legal_actions() if predicate(item))


def _step_pass(game: GuanDanGame) -> None:
    game.step(int(_action(game, lambda item: item["declared_pattern"] == "pass")["action_id"]))


def _warm_free_leader(
    game: GuanDanGame,
    *,
    leader_id: int,
    target_rank: str,
    rounds: int,
    protected_tokens: set[str] | None = None,
) -> None:
    protected = protected_tokens or set()
    for _ in range(rounds):
        observation = game.observe()
        assert observation["my_info"]["player_id"] == leader_id
        lead = _action(
            game,
            lambda item: item["declared_pattern"] == "single"
            and item["wildcard_count"] == 0
            and item["carrier_cards"][0] not in protected
            and item["carrier_cards"][0][:-1] != target_rank,
        )
        game.step(int(lead["action_id"]))
        for _ in range(3):
            _step_pass(game)


def _free_bomb_split_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["3S", "3S", "3H", "3C", "3D", "QS", "QH"],
            own_excluded_ranks={"2", "3", "Q", "K", "A"},
        ),
    )
    game.reset()
    _warm_free_leader(game, leader_id=1, target_rank="3", rounds=3)
    return game


def _wildcard_bomb_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["7S", "7H", "7C", "7D", "2H"],
            own_excluded_ranks={"2", "7"},
        ),
    )
    game.reset()
    _warm_free_leader(
        game, leader_id=1, target_rank="7", rounds=3, protected_tokens={"2H"},
    )
    return game


def _follow_game(*, teammate_leads: bool, urgent_opponent: bool = False) -> GuanDanGame:
    own_tokens = ["10S", "2H"] if teammate_leads else ["8S", "2H"]
    own_excluded = {"2", "8", "10"} if teammate_leads else {"2", "5", "8"}
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks=own_excluded,
        player_two_tokens=["5S"],
        player_two_excluded_ranks={"5"},
        player_three_tokens=["4S"] if teammate_leads else [],
        player_three_excluded_ranks={"4"} if teammate_leads else None,
    )
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=hands,
        starting_player_id=3 if teammate_leads else 2,
    )
    game.reset()
    leader_id = 3 if teammate_leads else 2
    if urgent_opponent:
        # Reach a public two-card opposing leader through 24 real single-card
        # plays and complete pass cycles.  The 5S lead remains in hand.
        for _ in range(24):
            lead = _action(
                game,
                lambda item: item["declared_pattern"] == "single"
                and item["carrier_cards"] != ["5S"],
            )
            game.step(int(lead["action_id"]))
            for _ in range(3):
                _step_pass(game)
        assert game.observe()["my_info"]["hand_count"] == 3
    else:
        _warm_free_leader(game, leader_id=leader_id, target_rank="4" if teammate_leads else "5", rounds=2)

    lead_token = "4S" if teammate_leads else "5S"
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "single" and item["carrier_cards"] == [lead_token],
    )
    game.step(int(lead["action_id"]))
    passes_to_me = 1 if teammate_leads else 2
    for _ in range(passes_to_me):
        _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["current_round"]["table_action"]["carrier_cards"] == [lead_token]
    if urgent_opponent:
        leader = next(item for item in observation["other_players"] if item["player_id"] == 2)
        assert leader["hand_count"] == 2
    return game


def _urgent_bomb_follow_game() -> GuanDanGame:
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands=_deal(
            own_tokens=["7S", "7H", "7C", "7D", "2H"],
            own_excluded_ranks={"2", "7"},
            player_two_tokens=["6S", "6H", "6C", "6D"],
            player_two_excluded_ranks={"6"},
        ),
        starting_player_id=2,
    )
    game.reset()
    # Retain the four natural sixes while the opponent legally spends 21
    # single cards and reaches a two-card public remainder after the bomb.
    for _ in range(21):
        lead = _action(
            game,
            lambda item: item["declared_pattern"] == "single"
            and item["carrier_cards"][0][:-1] != "6",
        )
        game.step(int(lead["action_id"]))
        for _ in range(3):
            _step_pass(game)
    bomb = _action(
        game,
        lambda item: item["declared_pattern"] == "bomb"
        and item["wildcard_count"] == 0
        and len(item["carrier_cards"]) == 4
        and all(card[:-1] == "6" for card in item["carrier_cards"]),
    )
    game.step(int(bomb["action_id"]))
    _step_pass(game)
    _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["other_players"][0]["player_id"] == 2
    assert observation["other_players"][0]["hand_count"] == 2
    return game


def _fresh_follow_game(
    own_tokens: list[str],
    *,
    teammate_leads: bool = False,
    leader_token: str = "5S",
    own_extra_excluded_ranks: set[str] | None = None,
) -> GuanDanGame:
    """Build a complete 108-card deal, then reach a real single-card follow."""
    leader_id = 3 if teammate_leads else 2
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks=(
            {token[:-1] for token in own_tokens if token not in {"SJ", "BJ"}}
            | (own_extra_excluded_ranks or set())
        ),
        player_two_tokens=[leader_token] if leader_id == 2 else None,
        player_two_excluded_ranks={leader_token[:-1]} if leader_id == 2 else None,
        player_three_tokens=[leader_token] if leader_id == 3 else None,
        player_three_excluded_ranks={leader_token[:-1]} if leader_id == 3 else None,
    )
    game = GuanDanGame(
        current_level_rank="2", preset_hands=hands, starting_player_id=leader_id,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "single"
        and item["carrier_cards"] == [leader_token],
    )
    game.step(int(lead["action_id"]))
    for _ in range(2 if leader_id == 2 else 1):
        _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["current_round"]["table_action"]["carrier_cards"] == [leader_token]
    return game


def _sequence_follow_game_with_natural_bomb_split() -> GuanDanGame:
    """Create a full deal where a legal straight response breaks a natural bomb."""
    own_tokens = ["9S", "9H", "9C", "9D", "5S", "6H", "7C", "8D", "2H"]
    leader_tokens = ["4S", "5H", "6C", "7D", "8H"]
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks={token[:-1] for token in own_tokens},
        player_two_tokens=leader_tokens,
        player_two_excluded_ranks={token[:-1] for token in leader_tokens},
    )
    game = GuanDanGame(
        current_level_rank="2", preset_hands=hands, starting_player_id=2,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "straight"
        and Counter(item["carrier_cards"]) == Counter(leader_tokens)
        and item["wildcard_count"] == 0,
    )
    game.step(int(lead["action_id"]))
    _step_pass(game)
    _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["current_round"]["table_action"]["declared_pattern"] == "straight"
    return game


def _sequence_follow_game_with_bomb_and_pair_split() -> GuanDanGame:
    """Create a legal follow where one straight takes a bomb card and a pair card."""
    own_tokens = [
        "9S", "9H", "9C", "9D", "QS", "QH", "QC", "10S", "JH", "KC",
        "3S", "3H", "3C", "4S", "4H", "4C", "7S", "7H", "7C",
        "10H", "JS", "KD", "2S", "2C", "5S", "5H", "5C",
    ]
    leader_tokens = ["4S", "5H", "6C", "7D", "8H"]
    deck = list(build_double_deck())
    hands: dict[int, list[Card]] = {
        1: _take(deck, own_tokens),
        2: _take(deck, leader_tokens),
        3: [],
        4: [],
    }
    for player_id in (2, 3):
        while len(hands[player_id]) < 27:
            hands[player_id].append(deck.pop(0))
    hands[4] = list(deck)
    assert {player_id: len(hand) for player_id, hand in hands.items()} == {1: 27, 2: 27, 3: 27, 4: 27}
    game = GuanDanGame(
        current_level_rank="2",
        preset_hands={player_id: tuple(hand) for player_id, hand in hands.items()},
        starting_player_id=2,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "straight"
        and {token[:-1] for token in item["carrier_cards"]} == {token[:-1] for token in leader_tokens}
        and item["wildcard_count"] == 0,
    )
    game.step(int(lead["action_id"]))
    _step_pass(game)
    _step_pass(game)
    observation = game.observe()
    assert observation["my_info"]["player_id"] == 1
    assert observation["current_round"]["table_action"]["declared_pattern"] == "straight"
    return game


def _straight_follow_game_from_own_tokens(
    own_tokens: list[str],
    *,
    leader_tokens: list[str] | None = None,
) -> GuanDanGame:
    """Build a complete legal deal and reach player one's straight response."""
    leader_tokens = leader_tokens or ["4S", "5H", "6C", "7D", "8H"]
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks={token[:-1] for token in own_tokens if token not in {"SJ", "BJ"}},
        player_two_tokens=leader_tokens,
        player_two_excluded_ranks={token[:-1] for token in leader_tokens},
    )
    game = GuanDanGame(
        current_level_rank="2", preset_hands=hands, starting_player_id=2,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "straight"
        and Counter(item["carrier_cards"]) == Counter(leader_tokens)
        and item["wildcard_count"] == 0,
    )
    game.step(int(lead["action_id"]))
    _step_pass(game)
    _step_pass(game)
    assert game.observe()["my_info"]["player_id"] == 1
    return game


def _single_follow_with_unrelated_straight_and_bomb() -> GuanDanGame:
    own_tokens = [
        "9S", "9H", "9C", "9D", "3S", "4S", "5S", "6S", "7S",
        "2S", "2C", "2D", "8S", "8H", "8C", "10S", "10H", "10C",
        "JS", "JH", "JC", "QS", "QH", "QC", "KS", "KH", "KC",
    ]
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks={token[:-1] for token in own_tokens},
        player_two_tokens=["8S"],
        player_two_excluded_ranks={"8"},
    )
    game = GuanDanGame(
        current_level_rank="2", preset_hands=hands, starting_player_id=2,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "single" and item["carrier_cards"] == ["8S"],
    )
    game.step(int(lead["action_id"]))
    _step_pass(game)
    _step_pass(game)
    assert game.observe()["my_info"]["player_id"] == 1
    return game


def _wildcard_bomb_follow_game() -> GuanDanGame:
    own_tokens = ["7S", "7H", "7C", "7D", "2H"]
    leader_tokens = ["6S", "6H", "6C", "6D"]
    hands = _deal(
        own_tokens=own_tokens,
        own_excluded_ranks={"2", "6", "7"},
        player_two_tokens=leader_tokens,
        player_two_excluded_ranks={"2", "6", "7"},
    )
    game = GuanDanGame(
        current_level_rank="2", preset_hands=hands, starting_player_id=2,
    )
    game.reset()
    lead = _action(
        game,
        lambda item: item["declared_pattern"] == "bomb"
        and item["carrier_cards"] == leader_tokens
        and item["wildcard_count"] == 0,
    )
    game.step(int(lead["action_id"]))
    _step_pass(game)
    _step_pass(game)
    assert game.observe()["my_info"]["player_id"] == 1
    return game


class M4TradeoffInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rag_advisor = RAGAdvisor(
            KnowledgeRetriever(KnowledgeBaseLoader(Path("rag")).load_all_documents())
        )

    def _factory_request(self, game: GuanDanGame, requested_action_id: int) -> tuple[str, list[int], int]:
        observation = game.observe()
        legal_actions = game.legal_actions()
        captured: list[str] = []
        chosen_ids: list[int] = []

        def fake_transport(request, _timeout):
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][1]["content"]
            captured.append(prompt)
            candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
            candidate_ids = [int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)]
            if requested_action_id not in candidate_ids:
                raise AssertionError("fake response ID was not in the model-visible candidates")
            chosen_ids.append(requested_action_id)
            content = json.dumps({"action_id": requested_action_id, "reason": "synthetic test"})
            event = json.dumps({"choices": [{"delta": {"content": content}}]})
            return f"data: {event}\n\ndata: [DONE]\n\n"

        config = SimpleNamespace(
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://example.invalid",
            deepseek_model="synthetic-model",
            deepseek_timeout=2.0,
            deepseek_max_retries=0,
            hand_evaluation_enabled=False,
            card_tracking_enabled=True,
            opening_formula_enabled=True,
        )
        factory = build_agent_factory(
            "deepseek",
            config_loader=lambda: config,
            client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_transport),
            rag_factory=lambda: self.rag_advisor,
        )
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = factory(1)
            chosen = agent.select_action(observation, legal_actions)

        self.assertEqual(chosen_ids, [requested_action_id])
        self.assertEqual(chosen, requested_action_id)
        self.assertEqual(agent.last_decision_source, "model")
        prompt = captured[0]
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        candidate_ids = {int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)}
        self.assertLessEqual(len(candidate_ids), 80)
        self.assertTrue(candidate_ids.issubset({int(action["action_id"]) for action in legal_actions}))
        for first, second in re.findall(r"公开关系对照 action_id=(\d+).*?action_id=(\d+)", prompt):
            self.assertIn(int(first), candidate_ids)
            self.assertIn(int(second), candidate_ids)
        recommendation = re.search(r"优先核验候选 action_id：([^\n]+)", prompt)
        if recommendation:
            self.assertTrue(all(int(value) in candidate_ids for value in re.findall(r"\d+", recommendation.group(1))))
        return prompt, sorted(candidate_ids), len(legal_actions)

    @staticmethod
    def _contrast(game: GuanDanGame, kind: str):
        observation = game.observe()
        contrasts = summarize_candidate_contrasts(observation, game.legal_actions())
        assert contrasts is not None
        return next(item for item in contrasts if item.kind == kind)

    @staticmethod
    def _response_text(game: GuanDanGame, response_action: dict[str, object]) -> tuple[str, object]:
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        pass_action = next(item for item in actions if item["declared_pattern"] == "pass")
        by_id = {item.action_id: item for item in facts}
        contrast = CandidateContrast(
            kind="follow_response_net_tradeoff",
            action_ids=(int(pass_action["action_id"]), int(response_action["action_id"])),
            teammate_hand_count=None,
        )
        text = DeepSeekClient._response_net_tradeoff_text(contrast, by_id)
        effect = candidate_response_net_effect(
            by_id[int(pass_action["action_id"])], by_id[int(response_action["action_id"])],
        )
        assert effect is not None
        return text, effect

    def test_natural_five_bomb_is_compared_to_three_plus_two_and_request_keeps_both_ids(self) -> None:
        game = _free_bomb_split_game()
        observation = game.observe()
        actions = game.legal_actions()
        contrast = self._contrast(game, "triple_bomb_split")
        action_by_id = {int(action["action_id"]): action for action in actions}
        triple, bomb = (action_by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(triple["declared_pattern"], "triple_with_pair")
        self.assertEqual(Counter(card[:-1] for card in triple["carrier_cards"]), Counter({"3": 3, "Q": 2}))
        self.assertEqual(bomb["declared_pattern"], "bomb")
        self.assertEqual(len(bomb["carrier_cards"]), 5)
        self.assertEqual(set(card[:-1] for card in bomb["carrier_cards"]), {"3"})
        prompt, visible, raw_count = self._factory_request(game, contrast.action_ids[0])
        self.assertGreater(raw_count, len(visible))
        self.assertIn(contrast.action_ids[0], visible)
        self.assertIn(contrast.action_ids[1], visible)
        self.assertIn("三带二拆自然炸/对子成本", prompt)
        self.assertIn("Q对子", prompt)
        self.assertIn("炸弹牌型获得高于普通三带二的即时压制层级", prompt)
        self.assertIn("三带二携带对子成本", prompt)
        rag_context = self.rag_advisor.get_rag_context(
            observation=observation,
            legal_actions=actions,
            top_k=1,
        )
        self.assertIn("exp_bomb_wildcard_001", {
            str(item["source_id"]) for item in rag_context["experience_hits"]
        })

    def test_natural_four_seven_and_wildcard_extended_five_bomb_are_compared(self) -> None:
        game = _wildcard_bomb_game()
        actions = game.legal_actions()
        contrast = self._contrast(game, "bomb_wildcard_strength")
        action_by_id = {int(action["action_id"]): action for action in actions}
        natural, extended = (action_by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(natural["declared_pattern"], "bomb")
        self.assertEqual(len(natural["carrier_cards"]), 4)
        self.assertEqual(extended["declared_pattern"], "bomb")
        self.assertEqual(len(extended["carrier_cards"]), 5)
        self.assertEqual(extended["wildcard_count"], 1)
        self.assertEqual(extended["wildcard_info"][0]["carrier_card"], "2H")
        prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
        self.assertTrue(set(contrast.action_ids).issubset(visible))
        self.assertIn("自然炸/通配加长炸对照", prompt)
        self.assertIn("多用一张逢人配", prompt)
        self.assertIn("急需更强压制", prompt)
        self.assertIn("本次出完可以支持花配", prompt)

    def test_teammate_single_compares_pass_ordinary_response_and_order(self) -> None:
        game = _follow_game(teammate_leads=True)
        actions = game.legal_actions()
        contrasts = summarize_candidate_contrasts(game.observe(), actions)
        assert contrasts is not None
        table_choice = next(item for item in contrasts if item.kind == "teammate_table_choice")
        resource_choice = next(item for item in contrasts if item.kind == "teammate_control_resource")
        by_id = {int(action["action_id"]): action for action in actions}
        self.assertEqual(by_id[table_choice.action_ids[0]]["declared_pattern"], "pass")
        self.assertEqual(by_id[table_choice.action_ids[1]]["declared_pattern"], "single")
        self.assertEqual(by_id[table_choice.action_ids[1]]["carrier_cards"], ["10S"])
        self.assertEqual(by_id[resource_choice.action_ids[0]]["declared_pattern"], "pass")
        prompt, visible, _raw_count = self._factory_request(game, table_choice.action_ids[1])
        self.assertTrue(set(table_choice.action_ids).issubset(visible))
        self.assertTrue(set(resource_choice.action_ids).issubset(visible))
        self.assertIn("队友控桌对照", prompt)
        self.assertIn("保留其当前领出机会", prompt)
        self.assertIn("若后续无人改写桌面", prompt)
        self.assertIn("保留当前全部", prompt)
        self.assertIn("但放弃本家这次应手", prompt)
        self.assertIn("下一名仍在局玩家为玩家2（对手", prompt)
        self.assertIn("队友协同与让牌", prompt)
        document = next(doc for doc in self.rag_advisor._retriever.documents
                        if doc.doc_id == "exp_midgame_teammate_001")
        self.assertEqual(RAGAdvisor._clip(document.content), document.content)
        _title, body = DeepSeekClient._rag_title_and_body({"snippet": document.content})
        self.assertEqual(body, document.content.split("\n\n", 1)[1])
        self.assertIn(body, prompt)
        self.assertIn("紧急阻断、可核对控制/重组收益可推翻", prompt)
        for governance in ("王春国", "news.bjd.com.cn", "source_tier"):
            self.assertNotIn(governance, prompt)
        _pass_prompt, pass_visible, _raw_count = self._factory_request(game, table_choice.action_ids[0])
        self.assertTrue(set(table_choice.action_ids).issubset(pass_visible))

    def test_ordinary_bomb_cost_and_teammate_tendency_generalize(self) -> None:
        for rank, count in (("7", 4), ("J", 4), ("7", 5)):
            tokens = [rank + suit for suit in "SHCD"]
            if count == 5:
                tokens.append(rank + "S")
            game = _fresh_follow_game(tokens, teammate_leads=True,
                                      own_extra_excluded_ranks={"2"})
            actions = game.legal_actions()
            single = _action(game, lambda a: a["declared_pattern"] == "single"
                             and a["carrier_cards"] == [rank + "S"])
            for rotation in (0, 1):
                obs = deepcopy(game.observe())
                if rotation:
                    rotate = lambda p: p % 4 + 1
                    for row in [obs["my_info"], *obs["other_players"]]:
                        row["player_id"] = rotate(row["player_id"])
                        row["team"] = "team_13" if row["player_id"] % 2 else "team_24"
                    obs["current_round"]["current_player_id"] = obs["my_info"]["player_id"]
                    for row in obs["history"]["actions"]:
                        row["player_id"] = rotate(row["player_id"])
                facts = summarize_candidate_structures(obs, actions)
                contrasts = summarize_candidate_contrasts(obs, actions)
                self.assertIsNotNone(facts)
                self.assertIsNotNone(contrasts)
                contrast = next(c for c in contrasts if c.kind == "follow_response_net_tradeoff"
                                and c.action_ids[1] == single["action_id"])
                text = DeepSeekClient._response_net_tradeoff_text(
                    contrast, {f.action_id: f for f in facts})
                self.assertIn(f"{rank}点自然牌{count}→{count - 1}张", text)
                self.assertIn("不能因未出炸弹就称保炸或低成本", text)
                self.assertIn("pass后本家是否再次行动、能否压回均不保证", text)
                if count == 4:
                    self.assertIn("1组完整自然炸弹丧失", text)
                    self.assertIn("倾向pass保留队友机会与完整资源", text)
                else:
                    self.assertIn("最大长度减弱但仍保有炸弹", text)
                    self.assertNotIn("完整自然炸弹丧失", text)
                    self.assertNotIn("倾向pass保留队友机会与完整资源", text)

    def test_ambiguous_history_or_unknown_team_omits_follow_relationship(self) -> None:
        game = _follow_game(teammate_leads=True)
        observation = game.observe()
        table_action = observation["current_round"]["table_action"]
        history = observation["history"]
        matching = next(
            item for item in history["actions"]
            if item["round_no"] == observation["current_round"]["round_no"]
            and item["declared_pattern"] == table_action["declared_pattern"]
            and item["declared_cards"] == table_action["declared_cards"]
            and item["carrier_cards"] == table_action["carrier_cards"]
        )

        duplicated_observation = dict(observation)
        duplicated_history = dict(history)
        duplicated_history["actions"] = [*history["actions"], dict(matching)]
        duplicated_observation["history"] = duplicated_history
        ambiguous_contrasts = summarize_candidate_contrasts(
            duplicated_observation, game.legal_actions()
        )
        assert ambiguous_contrasts is not None
        self.assertFalse(
            any(item.kind in {"teammate_table_choice", "teammate_control_resource"}
                for item in ambiguous_contrasts)
        )

        unknown_team_observation = dict(observation)
        unknown_team_observation["my_info"] = {**observation["my_info"], "team": None}
        unknown_team_contrasts = summarize_candidate_contrasts(
            unknown_team_observation, game.legal_actions()
        )
        self.assertIsNone(unknown_team_contrasts)

    def test_opponent_single_compares_eight_and_level_control_two_with_urgent_exception(self) -> None:
        for urgent in (False, True):
            with self.subTest(urgent=urgent):
                game = _follow_game(teammate_leads=False, urgent_opponent=urgent)
                contrast = self._contrast(game, "opponent_single_control_cost")
                self.assertEqual(contrast.rank_labels, ("8", "2"))
                prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[0])
                self.assertTrue(set(contrast.action_ids).issubset(visible))
                self.assertIn("自然普通单张8", prompt)
                self.assertIn("控制资源自然单张2", prompt)
                if urgent:
                    self.assertEqual(contrast.table_leader_hand_count, 2)
                    self.assertIn("对手领出后公开余2张", prompt)
                    self.assertIn("可值得花控制牌阻断", prompt)
                    self.assertIn("危险对手对照", prompt)
                    self.assertIn("公开紧迫对手", prompt)
                    self.assertIn("pass后由后续玩家继续应对", prompt)
                    self.assertIn("对手可能保持本轮领出优势", prompt)
                    _high_prompt, _high_visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
                else:
                    self.assertGreater(contrast.table_leader_hand_count or 0, 2)
                    self.assertIn("控制牌与牌权争夺", prompt)
                    self.assertIn("应手/让牌对照", prompt)

    def test_general_response_pass_relations_cover_each_real_action_and_request_ids(self) -> None:
        game = _follow_game(teammate_leads=False)
        observation = game.observe()
        actions = game.legal_actions()
        pass_id = int(_action(game, lambda item: item["declared_pattern"] == "pass")["action_id"])
        contrasts = summarize_candidate_contrasts(observation, actions)
        assert contrasts is not None
        net_contrasts = tuple(
            item for item in contrasts if item.kind == "follow_response_net_tradeoff"
        )
        expected = {
            (pass_id, int(action["action_id"]))
            for action in actions if action["declared_pattern"] != "pass"
        }
        self.assertEqual({item.action_ids for item in net_contrasts}, expected)
        self.assertTrue(all(item.table_leader_relation == "opponent" for item in net_contrasts))

        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        facts_by_id = {item.action_id: item for item in facts}
        selected = DeepSeekClient._prompt_candidate_contrasts(observation, actions)
        selected_net = tuple(
            item for item in selected or ()
            if item.kind == "follow_response_net_tradeoff"
        )
        self.assertGreaterEqual(len(selected_net), 1)
        self.assertLessEqual(len(selected_net), 2)
        selected_information = [
            candidate_response_net_effect(
                facts_by_id[item.action_ids[0]], facts_by_id[item.action_ids[1]],
            ).comparison_information
            for item in selected_net
        ]
        self.assertEqual(selected_information, sorted(selected_information, reverse=True))

        prompt, visible, _raw_count = self._factory_request(game, pass_id)
        self.assertIn("应手/让牌对照", prompt)
        self.assertIn("替换当前桌面", prompt)
        self.assertIn("需出合法更强牌并消耗实体牌，是否持有未知", prompt)
        self.assertIn("任何一侧都不保证最终控桌", prompt)
        self.assertLessEqual(len([line for line in prompt.splitlines() if "action_id=" in line and "为pass" in line]), 2)
        self.assertEqual(prompt.count("行动顺序/当前压制："), 1)
        request_pairs = re.findall(
            r"action_id=(\d+) 为pass，[^\n]*?action_id=(\d+) 是当前合法", prompt,
        )
        self.assertTrue(request_pairs)
        for first_id, second_id in request_pairs:
            self.assertIn(int(first_id), visible)
            self.assertIn(int(second_id), visible)
        request_effects = [
            candidate_response_net_effect(facts_by_id[pass_id], facts_by_id[int(second_id)])
            for _first_id, second_id in request_pairs
        ]
        self.assertTrue(any(effect is not None and effect.fragments_rank_group for effect in request_effects))
        self.assertTrue(any(effect is not None and effect.uses_wildcard for effect in request_effects))

    def test_public_net_effect_distinguishes_group_split_control_cost_and_pass(self) -> None:
        game = _fresh_follow_game(
            ["7S", "7H", "7C", "7D", "8S", "2H"],
        )
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        pass_fact = next(item for item in facts if item.pattern == "pass")
        fact_by_id = {item.action_id: item for item in facts}
        split_action = next(
            item for item in actions
            if item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["7S"]
            and item["wildcard_count"] == 0
        )
        split_effect = candidate_response_net_effect(
            pass_fact, fact_by_id[int(split_action["action_id"])],
        )
        assert split_effect is not None
        self.assertTrue(split_effect.fragments_rank_group)
        self.assertFalse(split_effect.spends_control_resource)
        self.assertEqual(split_effect.cards_played, 1)

        wildcard_action = next(
            item for item in actions
            if item["declared_pattern"] == "single"
            and item["carrier_cards"] == ["2H"]
            and item["wildcard_count"] == 1
        )
        wildcard_effect = candidate_response_net_effect(
            pass_fact, fact_by_id[int(wildcard_action["action_id"])],
        )
        assert wildcard_effect is not None
        self.assertTrue(wildcard_effect.uses_wildcard)
        self.assertTrue(wildcard_effect.spends_control_resource)
        self.assertGreater(wildcard_effect.comparison_information, 0)

        prompt, visible, _raw_count = self._factory_request(
            game, int(_action(game, lambda item: item["declared_pattern"] == "pass")["action_id"]),
        )
        self.assertTrue(set((int(split_action["action_id"]), int(wildcard_action["action_id"]))).issubset(
            {int(item["action_id"]) for item in actions}
        ))
        self.assertIn("应手/让牌对照", prompt)
        self.assertIn("2点逢人配资源1→0", prompt)
        self.assertRegex(prompt, r"\d+点自然牌\d+→\d+张")
        self.assertIn("自然组合线索可重叠，不等于互斥可走手数", prompt)
        request_pairs = re.findall(
            r"action_id=(\d+) 为pass，[^\n]*?action_id=(\d+) 是当前合法", prompt,
        )
        self.assertTrue(request_pairs)
        for first_id, second_id in request_pairs:
            self.assertIn(int(first_id), visible)
            self.assertIn(int(second_id), visible)

    def test_second_net_relation_balances_group_response_and_pressure_resources(self) -> None:
        game = _sequence_follow_game_with_natural_bomb_split()
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        facts_by_id = {item.action_id: item for item in facts}
        contrasts = summarize_candidate_contrasts(observation, actions)
        assert contrasts is not None
        net_contrasts = tuple(
            item for item in contrasts if item.kind == "follow_response_net_tradeoff"
        )
        self.assertTrue(any(
            facts_by_id[item.action_ids[1]].pattern == "straight"
            and not facts_by_id[item.action_ids[1]].uses_wildcard
            and not facts_by_id[item.action_ids[1]].consumes_control_resource
            and candidate_response_net_effect(
                facts_by_id[item.action_ids[0]], facts_by_id[item.action_ids[1]],
            ).fragments_rank_group
            for item in net_contrasts
        ))

        selected = DeepSeekClient._prompt_candidate_contrasts(observation, actions)
        selected_net = tuple(
            item for item in selected or ()
            if item.kind == "follow_response_net_tradeoff"
        )
        self.assertEqual(len(selected_net), 2)

        def lane(action_id: int) -> str:
            fact = facts_by_id[action_id]
            effect = candidate_response_net_effect(
                facts_by_id[selected_net[0].action_ids[0]], fact,
            )
            assert effect is not None
            return (
                "resource"
                if fact.pattern in {"bomb", "straight_flush", "joker_bomb"}
                or effect.uses_wildcard or effect.spends_control_resource
                else "ordinary"
            )

        lanes = {lane(item.action_ids[1]) for item in selected_net}
        self.assertEqual(lanes, {"ordinary", "resource"})
        self.assertTrue(any(facts_by_id[item.action_ids[1]].pattern == "straight" for item in selected_net))

        pass_id = next(item.action_ids[0] for item in selected_net)
        prompt, visible, _raw_count = self._factory_request(game, pass_id)
        self.assertLessEqual(len(visible), 80)
        request_pairs = re.findall(
            r"action_id=(\d+) 为pass，[^\n]*?action_id=(\d+) 是当前合法", prompt,
        )
        self.assertEqual(len(request_pairs), 2)
        self.assertEqual(
            {
                "resource"
                if facts_by_id[int(action_id)].pattern in {"bomb", "straight_flush", "joker_bomb"}
                or facts_by_id[int(action_id)].uses_wildcard
                or facts_by_id[int(action_id)].consumes_control_resource
                else "ordinary"
                for _pass, action_id in request_pairs
            },
            {"ordinary", "resource"},
        )
        self.assertTrue(any(
            facts_by_id[int(action_id)].pattern == "straight"
            and not facts_by_id[int(action_id)].uses_wildcard
            and not facts_by_id[int(action_id)].consumes_control_resource
            for _pass, action_id in request_pairs
        ))
        self.assertTrue(any(
            facts_by_id[int(action_id)].pattern in {"bomb", "straight_flush", "joker_bomb"}
            or facts_by_id[int(action_id)].uses_wildcard
            for _pass, action_id in request_pairs
        ))
        self.assertIn("逐点净变化=", prompt)

    def test_control_pair_cost_is_exact_and_singleton_response_has_no_false_group_split(self) -> None:
        game = _fresh_follow_game(
            ["8S", "AS", "AH"], leader_token="5S", own_extra_excluded_ranks={"2"},
        )
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        facts_by_id = {item.action_id: item for item in facts}
        pass_fact = next(item for item in facts if item.pattern == "pass")
        ace = next(
            action for action in actions
            if action["declared_pattern"] == "single"
            and action["wildcard_count"] == 0
            and any(token.startswith("A") for token in action["carrier_cards"])
        )
        eight = next(
            action for action in actions
            if action["declared_pattern"] == "single"
            and action["wildcard_count"] == 0
            and action["carrier_cards"] == ["8S"]
        )
        ace_effect = candidate_response_net_effect(pass_fact, facts_by_id[int(ace["action_id"])])
        eight_effect = candidate_response_net_effect(pass_fact, facts_by_id[int(eight["action_id"])])
        assert ace_effect is not None and eight_effect is not None
        ace_change = next(item for item in ace_effect.rank_resource_changes or () if item.rank == "A")
        self.assertEqual((ace_change.natural_count_before, ace_change.natural_count_after), (2, 1))
        self.assertIn("pair", ace_change.lost_group_kinds)
        self.assertTrue(ace_change.loses_control_resource)
        self.assertEqual(DeepSeekClient._rank_resource_delta_text(eight_effect), "")
        self.assertFalse(eight_effect.has_exact_group_loss)

        pass_id = next(int(action["action_id"]) for action in actions if action["declared_pattern"] == "pass")
        prompt, visible, _raw_count = self._factory_request(game, pass_id)
        control_line = next(
            line for line in prompt.splitlines() if "对手单张低/高跟牌成本：" in line
        )
        self.assertIn("action_id=", control_line)
        self.assertIn("A点自然控制牌2→1张", control_line)
        self.assertIn("相对pass逐点净变化=", control_line)
        self.assertLessEqual(len(visible), 80)

    def test_wildcard_use_has_physical_resource_delta_and_keeps_m8_routes_distinct(self) -> None:
        game = _wildcard_bomb_follow_game()
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        facts_by_id = {item.action_id: item for item in facts}
        pass_fact = next(item for item in facts if item.pattern == "pass")
        wildcard_bomb = next(
            action for action in actions
            if action["declared_pattern"] == "bomb"
            and action["wildcard_count"] == 1
            and "2H" in action["carrier_cards"]
        )
        effect = candidate_response_net_effect(pass_fact, facts_by_id[int(wildcard_bomb["action_id"])])
        assert effect is not None
        wild_delta = next(item for item in effect.rank_resource_changes or () if item.rank == "2")
        self.assertEqual((wild_delta.wildcard_count_before, wild_delta.wildcard_count_after), (1, 0))
        self.assertTrue(wild_delta.spends_wildcard)
        self.assertIn("2点逢人配资源1→0", DeepSeekClient._rank_resource_delta_text(effect))
        tradeoff, _wild_effect = self._response_text(game, wildcard_bomb)
        self.assertIn("2点逢人配资源1→0", tradeoff)
        self.assertNotIn("使用逢人配", tradeoff)

        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        self.assertIn(int(wildcard_bomb["action_id"]), {int(action["action_id"]) for action in projected})
        sf_game = _sequence_follow_game_with_natural_bomb_split()
        sf_projected = DeepSeekClient._project_prompt_actions(sf_game.observe(), sf_game.legal_actions())
        sf_actions = sf_game.legal_actions()
        self.assertTrue(any(action["declared_pattern"] == "straight_flush" for action in sf_actions))
        self.assertTrue(any(action["declared_pattern"] == "straight_flush" for action in sf_projected))

    def test_urgent_opponent_bomb_response_can_spend_wildcard_for_a_longer_bomb(self) -> None:
        game = _urgent_bomb_follow_game()
        actions = game.legal_actions()
        contrast = self._contrast(game, "bomb_wildcard_strength")
        by_id = {int(action["action_id"]): action for action in actions}
        natural, extended = (by_id[action_id] for action_id in contrast.action_ids)
        self.assertEqual(len(natural["carrier_cards"]), 4)
        self.assertEqual(len(extended["carrier_cards"]), 5)
        self.assertEqual(extended["wildcard_count"], 1)
        prompt, visible, _raw_count = self._factory_request(game, contrast.action_ids[1])
        self.assertTrue(set(contrast.action_ids).issubset(visible))
        self.assertIn("自然炸/通配加长炸对照", prompt)
        self.assertIn("公开危险对手", prompt)
        self.assertIn("多用一张逢人配", prompt)

    def test_follow_request_shows_exact_bomb_and_pair_cost_against_pass(self) -> None:
        game = _sequence_follow_game_with_bomb_and_pair_split()
        observation = game.observe()
        actions = game.legal_actions()
        facts = summarize_candidate_structures(observation, actions)
        assert facts is not None
        facts_by_id = {item.action_id: item for item in facts}
        pass_action = next(action for action in actions if action["declared_pattern"] == "pass")
        straight = next(
            action for action in actions
            if action["declared_pattern"] == "straight"
            and {token[:-1] for token in action["carrier_cards"]} == {"9", "10", "J", "Q", "K"}
        )
        bomb = next(
            action for action in actions
            if action["declared_pattern"] == "bomb"
            and action["wildcard_count"] == 0
            and all(token[:-1] == "9" for token in action["carrier_cards"])
        )
        straight_effect = candidate_response_net_effect(
            facts_by_id[int(pass_action["action_id"])], facts_by_id[int(straight["action_id"])],
        )
        bomb_effect = candidate_response_net_effect(
            facts_by_id[int(pass_action["action_id"])], facts_by_id[int(bomb["action_id"])],
        )
        assert straight_effect is not None and bomb_effect is not None
        straight_changes = {item.rank: item for item in straight_effect.rank_resource_changes or ()}
        bomb_changes = {item.rank: item for item in bomb_effect.rank_resource_changes or ()}
        self.assertEqual((straight_changes["9"].natural_count_before, straight_changes["9"].natural_count_after), (4, 3))
        self.assertIn("bomb", straight_changes["9"].lost_group_kinds)
        self.assertEqual((straight_changes["Q"].natural_count_before, straight_changes["Q"].natural_count_after), (3, 2))
        self.assertIn("triple", straight_changes["Q"].lost_group_kinds)
        self.assertEqual((bomb_changes["9"].natural_count_before, bomb_changes["9"].natural_count_after), (4, 0))

        selected = DeepSeekClient._prompt_candidate_contrasts(observation, actions)
        selected_net = tuple(
            item for item in selected or () if item.kind == "follow_response_net_tradeoff"
        )
        self.assertEqual(len(selected_net), 2)
        selected_patterns = {
            facts_by_id[item.action_ids[1]].pattern for item in selected_net
        }
        self.assertEqual(selected_patterns, {"straight", "bomb"})

        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        request_straight = next(
            action for action in projected
            if action["declared_pattern"] == "straight"
            and {str(card)[:-1] for card in action["carrier_cards"]} == {"9", "10", "J", "Q", "K"}
        )
        prompt, visible, _raw_count = self._factory_request(
            game, int(request_straight["action_id"]),
        )
        request_pairs = [
            (int(first), int(second))
            for first, second in re.findall(
                r"action_id=(\d+) 为pass，[^\n]*?action_id=(\d+) 是当前合法", prompt,
            )
        ]
        response_patterns = {
            next(action["declared_pattern"] for action in actions if int(action["action_id"]) == response_id)
            for _pass_id, response_id in request_pairs
        }
        self.assertEqual(response_patterns, {"straight", "bomb"})
        self.assertIn("9点自然牌4→3张", prompt)
        self.assertIn("9点自然牌4→0张", prompt)
        self.assertIn("Q点自然牌3→2张", prompt)
        self.assertIn("自然组合线索可重叠，不等于互斥可走手数", prompt)
        self.assertLessEqual(len(visible), 80)

    def test_exact_group_cost_does_not_hide_unrepresented_straight_loss_in_request(self) -> None:
        own_tokens = [
            "9S", "9H", "9C", "9D", "10S", "JH", "QC", "KD",
            "2S", "2C", "2D", "3S", "3H", "3C", "4S", "4H", "4C",
            "6S", "6H", "6C", "7S", "8S", "8H", "8C", "KS", "KH", "KC",
        ]
        game = _straight_follow_game_from_own_tokens(
            own_tokens,
            leader_tokens=["8D", "9D", "10H", "JS", "QD"],
        )
        actions = game.legal_actions()
        straight = next(
            action for action in actions
            if action["declared_pattern"] == "straight"
            and {str(card)[:-1] for card in action["carrier_cards"]} == {"9", "10", "J", "Q", "K"}
            and action["wildcard_count"] == 0
        )
        tradeoff, effect = self._response_text(game, straight)
        self.assertIn("bomb", effect.lost_natural_uses)
        self.assertIn("straight", effect.lost_natural_uses)
        self.assertIn("9点自然牌4→3张（失去自然炸弹线索", tradeoff)
        self.assertIn("出后不再保有部分当前可识别的顺子点数结构线索", tradeoff)
        self.assertNotIn("不再保有部分当前可识别的炸弹线索", tradeoff)

        prompt, visible, _raw_count = self._factory_request(
            game, int(straight["action_id"]),
        )
        self.assertIn("9点自然牌4→3张（失去自然炸弹线索", prompt)
        self.assertIn("出后不再保有部分当前可识别的顺子点数结构线索", prompt)
        self.assertIn(int(straight["action_id"]), visible)
        response_line = next(
            line for line in prompt.splitlines()
            if re.search(
                rf"action_id=\d+ 为pass，.*?action_id={int(straight['action_id'])} 是当前合法",
                line,
            )
        )
        self.assertIn("自然牌4→3张（失去自然炸弹线索", response_line)
        self.assertIn("K点自然牌4→3张（失去自然炸弹线索", response_line)
        self.assertIn("出后不再保有部分当前可识别的顺子点数结构线索", response_line)
        self.assertNotIn("出后不再保有部分当前可识别的自然炸弹线索", response_line)
        self.assertLessEqual(len(visible), 80)

    def test_exact_group_only_is_deduplicated_but_straight_only_loss_remains(self) -> None:
        exact_game = _single_follow_with_unrelated_straight_and_bomb()
        exact_actions = exact_game.legal_actions()
        nine = next(
            action for action in exact_actions
            if action["declared_pattern"] == "single"
            and action["wildcard_count"] == 0
            and str(action["carrier_cards"][0]).startswith("9")
        )
        exact_text, exact_effect = self._response_text(exact_game, nine)
        self.assertEqual(exact_effect.lost_natural_uses, ("bomb",))
        self.assertIn("9点自然牌4→3张（失去自然炸弹线索", exact_text)
        self.assertNotIn("出后不再保有部分当前可识别的炸弹线索", exact_text)

        straight_only_tokens = [
            "9S", "10S", "JH", "QC", "KD",
            "2S", "2C", "2D", "2H", "3S", "3H", "3C", "3D",
            "4S", "4H", "4C", "4D", "4C", "4D",
            "6S", "6H", "6C", "6D", "8S", "8H", "8C", "8D",
        ]
        straight_game = _straight_follow_game_from_own_tokens(straight_only_tokens)
        straight_actions = straight_game.legal_actions()
        response = next(
            action for action in straight_actions
            if action["declared_pattern"] == "straight"
            and {str(card)[:-1] for card in action["carrier_cards"]} == {"9", "10", "J", "Q", "K"}
            and action["wildcard_count"] == 0
        )
        straight_text, straight_effect = self._response_text(straight_game, response)
        self.assertEqual(straight_effect.lost_natural_uses, ("straight",))
        self.assertEqual(DeepSeekClient._rank_resource_delta_text(straight_effect), "")
        self.assertIn("出后不再保有部分当前可识别的顺子点数结构线索", straight_text)

    def test_four_rank_detail_cap_keeps_unrendered_split_summary(self) -> None:
        own_tokens = [
            *(f"{rank}{suit}" for rank in ("5", "6", "7", "8", "9") for suit in "SHCD"),
            "3S", "4S", "10S", "JS", "QS", "KS", "AS",
        ]
        game = _straight_follow_game_from_own_tokens(own_tokens)
        response = next(
            action for action in game.legal_actions()
            if action["declared_pattern"] == "straight"
            and {str(card)[:-1] for card in action["carrier_cards"]} == {"5", "6", "7", "8", "9"}
            and action["wildcard_count"] == 0
        )
        text, effect = self._response_text(game, response)
        self.assertEqual(len(effect.rank_resource_changes or ()), 5)
        self.assertEqual(effect.lost_natural_uses, ("bomb",))
        exact_text = DeepSeekClient._rank_resource_delta_text(effect)
        self.assertIn("另有1处", exact_text)
        self.assertIn("出后不再保有部分当前可识别的自然炸弹线索", text)
        self.assertIn("拆动已识别同点组", text)


if __name__ == "__main__":
    unittest.main()
