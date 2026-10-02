from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch

from agents.card_tracker import exact_public_hand_assignment
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from engine.actions import Action, ActionType
from engine.cards import Card, build_double_deck, card_to_token, sort_cards
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from engine.rules import BaseRuleEngine
from engine.patterns import PatternType
from engine.public_endgame import (
    PublicEndgameAnalysis,
    analyze_public_endgame,
)
from engine.state import GameState, HistoryEntry, PlayerState, TableConstraint
from integrations.botzone.agent_runtime import build_agent_factory


def _rollout_to_step(
    seed: int,
    target_step: int,
) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]]]:
    game, observation, actions = _rollout_to_step_or_terminal(seed, target_step)
    if observation is None or actions is None:
        raise AssertionError("seeded game ended before requested observation")
    return game, observation, actions


def _rollout_to_step_or_terminal(
    seed: int,
    target_step: int,
) -> tuple[
    GuanDanGame,
    dict[str, object] | None,
    list[dict[str, object]] | None,
]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    game.reset()
    while game.observe()["current_round"]["step_no"] < target_step:
        if game._state.is_finished:  # noqa: SLF001 - deterministic engine fixture
            return game, None, None
        observation = game.observe()
        actions = game.legal_actions()
        player_id = int(observation["my_info"]["player_id"])
        game.step(RuleBasedAIAgent(player_id).select_action(observation, actions))
    if game._state.is_finished:  # noqa: SLF001 - deterministic engine fixture
        return game, None, None
    return game, game.observe(), game.legal_actions()


def _clone_game(game: GuanDanGame) -> GuanDanGame:
    clone = GuanDanGame(current_level_rank=game._current_level_rank)  # noqa: SLF001
    clone._state = game._require_state()  # noqa: SLF001 - engine oracle only
    clone._invalidate_legal_actions_cache()  # noqa: SLF001
    return clone


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(token)
    return Card(token[:-1], token[-1])


def _public_endgame_fixture(
    *,
    current_hands: dict[int, tuple[str, ...]],
    finish_order: tuple[int, int],
    current_player_id: int,
    leading_token: str | None = None,
    leader_player_id: int | None = None,
) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]]]:
    deck = build_double_deck()
    hands = {
        player_id: list(sort_cards(tuple(_card(token) for token in current_hands.get(player_id, ()))))
        for player_id in range(1, 5)
    }
    for cards in hands.values():
        for card in cards:
            deck.remove(card)

    lead_card = _card(leading_token) if leading_token is not None else None
    played: dict[int, list[Card]] = {player_id: [] for player_id in range(1, 5)}
    if lead_card is not None:
        if leader_player_id not in played:
            raise AssertionError("a public lead needs its actual player")
        deck.remove(lead_card)
        played[int(leader_player_id)].append(lead_card)

    for player_id in range(1, 5):
        needed = 27 - len(hands[player_id]) - len(played[player_id])
        if needed < 0:
            raise AssertionError("fixture exceeds a player's initial hand")
        played[player_id].extend(deck[:needed])
        del deck[:needed]
    if deck:
        raise AssertionError("fixture must conserve the full double deck")

    events: list[HistoryEntry] = []
    for owner in range(1, 5):
        cards = played[owner]
        if lead_card is not None and owner == leader_player_id:
            cards = list(cards)
            cards.remove(lead_card)
        by_rank: dict[str, list[Card]] = defaultdict(list)
        for card in cards:
            by_rank[card.rank].append(card)
        for rank in sorted(by_rank):
            carrier_group = tuple(by_rank[rank])
            if len(carrier_group) == 1:
                pattern = PatternType.SINGLE
            elif len(carrier_group) == 2:
                pattern = PatternType.PAIR
            elif len(carrier_group) == 3:
                pattern = PatternType.TRIPLE
            elif 4 <= len(carrier_group) <= 10:
                pattern = PatternType.BOMB
            else:
                raise AssertionError("rank group exceeds a canonical pattern length")
            action = Action(
                player_id=owner,
                action_type=ActionType.PLAY,
                declared_pattern=pattern,
                declared_cards=tuple(Card(rank) for _card in carrier_group),
                carrier_cards=carrier_group,
                display_text=f"{pattern.value}:{rank}",
            )
            events.append(HistoryEntry(len(events) + 1, 1, owner, action))
    if lead_card is not None:
        action = Action(
            player_id=int(leader_player_id),
            action_type=ActionType.PLAY,
            declared_pattern=PatternType.SINGLE,
            declared_cards=(Card(lead_card.rank),),
            carrier_cards=(lead_card,),
            display_text=f"single:{lead_card.rank}",
        )
        events.append(HistoryEntry(len(events) + 1, 1, int(leader_player_id), action))

    finish_rank = {player_id: index + 1 for index, player_id in enumerate(finish_order)}
    players = tuple(
        PlayerState(player_id, tuple(hands[player_id]), finish_rank.get(player_id))
        for player_id in range(1, 5)
    )
    active_ids = {player_id for player_id, cards in hands.items() if cards}
    table = TableConstraint()
    if lead_card is not None:
        pending = []
        current = int(leader_player_id)
        for _ in range(4):
            current = current % 4 + 1
            if current in active_ids and current != leader_player_id:
                pending.append(current)
        if not pending or pending[0] != current_player_id:
            raise AssertionError("fixture current seat is not the first responder")
        lead_action = events[-1].action
        table = TableConstraint(lead_action, int(leader_player_id), tuple(pending))

    game = GuanDanGame(current_level_rank="2")
    game._state = GameState(
        players=players,
        current_player_id=current_player_id,
        current_level_rank="2",
        table_constraint=table,
        step_no=len(events),
        round_no=1,
        finish_order=finish_order,
        history=tuple(events),
    )
    game._invalidate_legal_actions_cache()
    observation = game.observe()
    actions = game.legal_actions()
    return game, observation, actions


def _reference_profile(game: GuanDanGame, root_team: str) -> tuple[int, tuple[int, ...]]:
    """Exhaustively enumerate engine continuations without using M9 search code."""
    state = game._require_state()  # noqa: SLF001 - test-only continuation oracle
    if state.is_finished:
        winner = state.winner
        value = 0 if winner == "draw" else 1 if winner == root_team else -1
        return value, (value,)

    current_team = "team_13" if state.current_player_id in {1, 3} else "team_24"
    maximizing = current_team == root_team
    child_profiles = []
    for action in game.legal_actions():
        child = _clone_game(game)
        child.step(int(action["action_id"]))
        child_profiles.append(_reference_profile(child, root_team))
    guarantees = [profile[0] for profile in child_profiles]
    reachable = tuple(sorted({value for _, values in child_profiles for value in values}))
    return (max(guarantees) if maximizing else min(guarantees)), reachable


def _reference_root_profiles(
    game: GuanDanGame,
) -> tuple[
    tuple[tuple[int, int], ...],
    tuple[tuple[int, tuple[int, ...]], ...],
]:
    player_id = game._require_state().current_player_id  # noqa: SLF001
    root_team = "team_13" if player_id in {1, 3} else "team_24"
    guarantees = []
    reachable = []
    for action in game.legal_actions():
        child = _clone_game(game)
        child.step(int(action["action_id"]))
        value, outcomes = _reference_profile(child, root_team)
        action_id = int(action["action_id"])
        guarantees.append((action_id, value))
        reachable.append((action_id, outcomes))
    return tuple(guarantees), tuple(reachable)


def _fake_response_transport(captured: list[dict[str, object]]):
    def transport(request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        captured.append(payload)
        prompt = payload["messages"][1]["content"]
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        ids = [int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)]
        assert ids
        answer = ids[-1]
        event = json.dumps({"choices": [{"delta": {"content": json.dumps({"action_id": answer})}}]})
        return f"data: {event}\n\ndata: [DONE]\n\n"
    return transport


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        deepseek_api_key="synthetic-key",
        deepseek_base_url="https://example.invalid",
        deepseek_model="synthetic-model",
        deepseek_timeout=2.0,
        deepseek_max_retries=0,
        hand_evaluation_enabled=False,
        opening_formula_enabled=False,
        card_tracking_enabled=False,
    )


def _factory_agent(captured: list[dict[str, object]]):
    config = _config()
    factory = build_agent_factory(
        "deepseek",
        config_loader=lambda: config,
        client_factory=lambda **kwargs: DeepSeekClient(
            **kwargs,
            transport=_fake_response_transport(captured),
        ),
        rag_factory=lambda: None,
    )
    return config, factory


class M9PublicEndgameOpportunityTests(unittest.TestCase):
    def test_search_legal_cache_keys_exact_inputs_and_is_call_local(self) -> None:
        from engine.public_endgame import _SearchContext, _search_action_ids

        game, _, _ = _public_endgame_fixture(
            current_hands={3: ("2H", "9C", "10D"), 4: ("JS", "QC")},
            finish_order=(1, 2), current_player_id=3,
            leading_token="8S", leader_player_id=4,
        )
        context = _SearchContext(deadline=float("inf"), max_nodes=5)
        first_ids = _search_action_ids(game, context)
        same = _clone_game(game)
        same._state = replace(same._state, step_no=same._state.step_no + 7,
                              round_no=same._state.round_no + 2)
        with patch.object(BaseRuleEngine, "generate_legal_actions",
                          side_effect=AssertionError("identical rule inputs")):
            self.assertEqual(_search_action_ids(same, context), first_ids)
        self.assertEqual(same.legal_actions(), game.legal_actions())
        reference = _clone_game(same)
        self.assertEqual(same.step(first_ids[0]), reference.step(first_ids[0]))
        self.assertEqual(same.observe(), reference.observe())

        state = game._require_state()
        lead = state.table_constraint.leading_action
        variants = (
            replace(state, current_level_rank="3"),
            replace(state, current_player_id=4),
            replace(state, players=tuple(
                replace(p, hand_cards=p.hand_cards[:-1]) if p.player_id == 3 else p
                for p in state.players)),
            replace(state, table_constraint=replace(state.table_constraint,
                leading_action=replace(lead, carrier_cards=(Card("8", "C"),)))),
            replace(state, table_constraint=replace(state.table_constraint,
                leading_action=replace(lead, declared_cards=(Card("9"),),
                                       carrier_cards=(Card("9", "C"),)))),
            replace(state, table_constraint=TableConstraint()),
        )
        original_generate = BaseRuleEngine.generate_legal_actions
        for variant in variants:
            candidate = _clone_game(game)
            candidate._state = variant
            with patch.object(BaseRuleEngine, "generate_legal_actions",
                              autospec=True, side_effect=original_generate) as generate:
                _search_action_ids(candidate, context)
                generate.assert_called_once()
            oracle = _clone_game(candidate)
            self.assertEqual(candidate.legal_actions(), oracle.legal_actions())
        fresh = _SearchContext(deadline=float("inf"), max_nodes=5)
        self.assertEqual(fresh.legal_cache, {})
        with patch.object(BaseRuleEngine, "generate_legal_actions", autospec=True,
                          side_effect=original_generate) as generate:
            self.assertEqual(_search_action_ids(_clone_game(game), fresh), first_ids)
            generate.assert_called_once()
        self.assertLessEqual(len(context.legal_cache), context.max_nodes + 1)

    def test_search_branch_reuses_only_current_cache_and_matches_engine_step(self) -> None:
        from engine.public_endgame import _copy_game

        game, _, actions = _public_endgame_fixture(
            current_hands={3: ("2H", "9C", "10D"), 4: ("JS",)},
            finish_order=(1, 2), current_player_id=3,
            leading_token="8S", leader_player_id=4,
        )
        original = game.observe()
        cached_map = game._legal_action_map
        for action in actions:
            child = _copy_game(game)
            reference = _clone_game(game)
            with patch.object(BaseRuleEngine, "generate_legal_actions",
                              side_effect=AssertionError("same-state regeneration")):
                result = child.step(action["action_id"])
            self.assertEqual(result, reference.step(action["action_id"]))
            self.assertEqual(child.observe(), reference.observe())
            self.assertIs(game._legal_action_map, cached_map)
            self.assertEqual(game.observe(), original)

    def test_complete_equal_profiles_reach_factory_without_selecting_for_model(self) -> None:
        from agents.known_endgame import format_public_endgame_comparisons

        game, observation, actions = _public_endgame_fixture(
            current_hands={4: ("3S", "3C", "4D", "5S"), 3: ("6C", "7S")},
            finish_order=(1, 2), current_player_id=4,
        )
        expected, reachable = _reference_root_profiles(game)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            solved = analyze_public_endgame(observation, actions, exact_public_hand_assignment(observation))
        self.assertEqual(solved.status, "solved")
        self.assertEqual((solved.action_values, solved.action_reachable_values), (expected, reachable))
        summary = format_public_endgame_comparisons(solved, actions, legal_actions=actions)
        self.assertIn("全部原始合法首手", summary)
        self.assertIn("均保底负局、可达{负局,规则平}，无可达本队胜局", summary)
        self.assertNotIn("action_id=", summary)
        self.assertIsNone(format_public_endgame_comparisons(solved, actions))
        incomplete = replace(solved, action_values=solved.action_values[:-1])
        duplicate = replace(solved, action_values=solved.action_values[:-1] + (solved.action_values[0],))
        differing = replace(solved, action_reachable_values=(
            (actions[0]["action_id"], (-1,)), *solved.action_reachable_values[1:]))
        self.assertIsNone(format_public_endgame_comparisons(incomplete, actions, legal_actions=actions))
        self.assertIsNone(format_public_endgame_comparisons(duplicate, actions, legal_actions=actions))
        different_text = format_public_endgame_comparisons(differing, actions, legal_actions=actions)
        self.assertIn("M5公开残局对照", different_text)
        self.assertNotIn("全部原始合法首手", different_text)
        for analysis, same in ((solved, True), (differing, False),
                               (PublicEndgameAnalysis(status="budget_exceeded"), False)):
            captured = []
            config, factory = _factory_agent(captured)
            with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config), \
                    patch("engine.public_endgame.analyze_public_endgame", return_value=analysis):
                agent = factory(4)
                chosen = agent.select_action(observation, actions)
            prompt = captured[0]["messages"][1]["content"]
            self.assertEqual(agent.last_decision_source, "model")
            if same:
                self.assertIn(summary, prompt)
                self.assertIn("牌权、资源与其他策略价值仍需判断", prompt)
            elif analysis.status == "solved":
                self.assertIn("M5公开残局对照", prompt)
            else:
                self.assertNotIn("全部原始合法首手", prompt)
                self.assertNotIn("M5公开残局对照", prompt)
            section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
            visible = [int(i) for i in re.findall(r"#(\d+)\s+action_id=", section)]
            self.assertEqual(chosen, visible[-1])
            self.assertLessEqual(len(visible), 80)
            if same:
                self.assertLess(len(visible), len(actions))
            self.assertIn(chosen, [a["action_id"] for a in actions])

    def test_corrected_canonical_double_wild_response_is_in_full_m9_position(self) -> None:
        game, observation, actions = _public_endgame_fixture(
            current_hands={
                1: ("7S", "7S", "7C", "7D", "3S"),
                2: ("9S", "9C", "9D", "9H", "2H", "2H"),
            },
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        four_bomb = next(
            action for action in actions
            if action["declared_pattern"] == "bomb"
            and len(action["carrier_cards"]) == 4
            and set(action["declared_cards"]) == {"7"}
        )
        response_game = _clone_game(game)
        response_game.step(int(four_bomb["action_id"]))
        six_bomb = next(
            action for action in response_game.legal_actions()
            if action["declared_pattern"] == "bomb"
            and len(action["carrier_cards"]) == 6
            and action["wildcard_count"] == 2
            and set(action["declared_cards"]) == {"9"}
        )
        self.assertEqual(six_bomb["wildcard_count"], 2)
        self.assertEqual(six_bomb["carrier_cards"].count("2H"), 2)

        analysis = analyze_public_endgame(
            observation,
            actions,
            assignment,
            max_nodes=1,
        )
        self.assertEqual(analysis.status, "budget_exceeded")
        self.assertEqual(analysis.action_values, ())
        self.assertEqual(analysis.action_reachable_values, ())

    def test_m9_matches_engine_for_proven_route_and_project_draw(self) -> None:
        win_game, win_observation, win_actions = _public_endgame_fixture(
            current_hands={
                1: ("3S", "3C", "4S", "4C"),
                2: ("5H",),
            },
            finish_order=(3, 4),
            current_player_id=1,
        )
        win_assignment = exact_public_hand_assignment(win_observation)
        self.assertIsNotNone(win_assignment)
        win_expected, _ = _reference_root_profiles(win_game)
        # Keep the positive proof fixture deterministic without increasing the
        # production 35 ms fail-closed search budget.
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            win_analysis = analyze_public_endgame(win_observation, win_actions, win_assignment)
        self.assertEqual(win_analysis.status, "proven_win")
        first_win = next(action_id for action_id, value in win_expected if value == 1)
        self.assertEqual(win_analysis.proven_action_id, first_win)

        draw_game, draw_observation, draw_actions = _public_endgame_fixture(
            current_hands={3: ("3S", "4S"), 4: ("5S",)},
            finish_order=(1, 2),
            current_player_id=3,
            leading_token="2S",
            leader_player_id=4,
        )
        draw_assignment = exact_public_hand_assignment(draw_observation)
        self.assertIsNotNone(draw_assignment)
        draw_expected, draw_reachable = _reference_root_profiles(draw_game)
        self.assertEqual(draw_expected, ((int(draw_actions[0]["action_id"]), 0),))
        self.assertEqual(draw_reachable, ((int(draw_actions[0]["action_id"]), (0,)),))
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            draw_analysis = analyze_public_endgame(draw_observation, draw_actions, draw_assignment)
        self.assertEqual(draw_analysis.status, "solved")
        self.assertEqual(draw_analysis.action_values, draw_expected)
        self.assertEqual(draw_analysis.action_reachable_values, draw_reachable)
        self.assertIsNone(draw_analysis.proven_action_id)

    def test_first_complete_proof_returns_before_later_root_actions(self) -> None:
        from engine import public_endgame

        game, observation, actions = _public_endgame_fixture(
            current_hands={
                1: ("3S", "3C", "4S", "4C"),
                2: ("5H",),
            },
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        expected_values, _ = _reference_root_profiles(game)
        first_proof = next(action_id for action_id, value in expected_values if value == 1)
        proof_index = next(index for index, action in enumerate(actions) if int(action["action_id"]) == first_proof)

        original_build = public_endgame._build_public_game
        original_copy = public_endgame._copy_game
        built_games = []
        root_copies = 0

        def capture_build(*args, **kwargs):
            rebuilt = original_build(*args, **kwargs)
            built_games.append(rebuilt)
            return rebuilt

        def count_root_copy(candidate):
            nonlocal root_copies
            if built_games and candidate._require_state() is built_games[0]._require_state():
                root_copies += 1
                if root_copies > proof_index + 1:
                    raise AssertionError("a later root action was searched after a complete win proof")
            return original_copy(candidate)

        with (
            patch("engine.public_endgame._build_public_game", side_effect=capture_build),
            patch("engine.public_endgame._copy_game", side_effect=count_root_copy),
        ):
            with patch("engine.public_endgame.monotonic", return_value=0.0):
                analysis = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(analysis.status, "proven_win")
        self.assertEqual(analysis.proven_action_id, first_proof)
        self.assertEqual(root_copies, proof_index + 1)

    def test_search_profiles_match_exhaustive_engine_continuations(self) -> None:
        # Keep the historical seed/step anchors. Correct lower-end patterns
        # and double-down can make some anchors unreachable or no longer
        # uniquely attributable from the public trace. Those cases must fail
        # closed instead of reusing a stale perfect-information endgame.
        for seed, step in (
            (10, 86), (10, 87), (9, 78), (26, 85), (288, 83), (12, 87),
            (13, 99), (6, 93),
        ):
            with self.subTest(seed=seed, step=step):
                game, observation, actions = _rollout_to_step_or_terminal(seed, step)
                if observation is None or actions is None:
                    state = game._require_state()  # noqa: SLF001 - engine fixture assertion
                    self.assertTrue(state.is_finished)
                    if len(state.finish_order) == 2:
                        self.assertEqual((state.finish_order[1] - state.finish_order[0]) % 2, 0)
                    else:
                        self.assertEqual(len(state.finish_order), 4)
                    self.assertEqual(
                        [player.player_id for player in sorted(
                            (item for item in state.players if item.finish_rank is not None),
                            key=lambda item: item.finish_rank or 99,
                        )],
                        list(state.finish_order),
                    )
                    self.assertEqual(game.legal_actions(), [])
                    continue
                assignment = exact_public_hand_assignment(observation)
                analysis = analyze_public_endgame(observation, actions, assignment)
                if assignment is None:
                    self.assertEqual(analysis.status, "ineligible")
                    self.assertEqual(analysis.action_values, ())
                    self.assertEqual(analysis.action_reachable_values, ())
                    continue
                if analysis.status == "budget_exceeded":
                    self.assertIsNone(analysis.proven_action_id)
                    self.assertEqual(analysis.action_values, ())
                    self.assertEqual(analysis.action_reachable_values, ())
                    continue
                expected_values, expected_reachable = _reference_root_profiles(game)
                first_guaranteed = next(
                    (action_id for action_id, value in expected_values if value == 1),
                    None,
                )
                if analysis.status == "proven_win":
                    self.assertIsNotNone(first_guaranteed)
                    self.assertEqual(analysis.proven_action_id, first_guaranteed)
                    self.assertEqual(analysis.action_values, ())
                    self.assertEqual(analysis.action_reachable_values, ())
                    self.assertEqual(analysis.best_action_ids, ())
                    self.assertIsNone(analysis.unique_best_action_id)
                else:
                    self.assertEqual(analysis.status, "solved")
                    self.assertIsNone(analysis.proven_action_id)
                    self.assertIsNone(first_guaranteed)
                    self.assertEqual(analysis.action_values, expected_values)
                    self.assertEqual(analysis.action_reachable_values, expected_reachable)

    def test_any_completed_guarantee_shortcuts_even_if_other_routes_also_win(self) -> None:
        from agents.known_endgame import (
            describe_proven_endgame_choice,
            select_proven_endgame_action,
        )
        game, observation, actions = _public_endgame_fixture(
            current_hands={1: ("3S", "3C", "4S", "4C"), 2: ("5H",)},
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            analysis = analyze_public_endgame(observation, actions, assignment)
        expected_values, _ = _reference_root_profiles(game)
        proven_ids = [action_id for action_id, value in expected_values if value == 1]
        self.assertGreater(len(proven_ids), 1)
        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        signatures = {
            int(action["action_id"]): DeepSeekClient._action_signature(action)
            for action in projected
        }
        self.assertEqual(analysis.status, "proven_win")
        self.assertEqual(analysis.proven_action_id, proven_ids[0])
        selected = select_proven_endgame_action(analysis, actions, signatures)
        self.assertEqual(selected, proven_ids[0])
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertIn("可保底本队胜", describe_proven_endgame_choice(analysis, selected))

        # Distinct non-guaranteed routes with possible winning continuations
        # remain a model choice; public search does not turn possibility into
        # a local guarantee.
        reply_game, reply_observation, reply_actions = _public_endgame_fixture(
            current_hands={3: ("6S", "7S"), 4: ("8S",)},
            finish_order=(1, 2),
            current_player_id=3,
            leading_token="5S",
            leader_player_id=4,
        )
        reply_assignment = exact_public_hand_assignment(reply_observation)
        self.assertIsNotNone(reply_assignment)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            reply_analysis = analyze_public_endgame(reply_observation, reply_actions, reply_assignment)
        reply_expected, reply_reachable = _reference_root_profiles(reply_game)
        self.assertEqual(reply_analysis.status, "solved")
        self.assertEqual(reply_analysis.action_values, reply_expected)
        self.assertEqual(reply_analysis.action_reachable_values, reply_reachable)
        reply_projected = DeepSeekClient._project_prompt_actions(reply_observation, reply_actions)
        reply_signatures = {
            int(action["action_id"]): DeepSeekClient._action_signature(action)
            for action in reply_projected
        }
        reachable = dict(reply_analysis.action_reachable_values)
        winning_routes = {
            (reply_signatures[action_id], reachable[action_id])
            for action_id in reachable if 1 in reachable[action_id]
        }
        self.assertGreater(len(winning_routes), 1)
        self.assertIsNone(select_proven_endgame_action(reply_analysis, reply_actions, reply_signatures))

        # The agent-level path returns a raw canonical ID and skips the model
        # as soon as the first complete guarantee is found.
        class _NoCallClient:
            def suggest_action_id(self, **_kwargs):
                raise AssertionError("complete guaranteed route should be selected locally")

        config = _config()
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(
                player_id=int(observation["my_info"]["player_id"]),
                client=_NoCallClient(),  # type: ignore[arg-type]
                hand_evaluation_enabled=False,
                opening_formula_enabled=False,
            )
            with patch("engine.public_endgame.monotonic", return_value=0.0):
                selected = agent.select_action(observation, actions)
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertEqual(agent.last_decision_source, "local")
        self.assertIn("可保底本队胜", agent.last_public_endgame_decision_summary)

    def test_guaranteed_root_stops_before_searching_later_root_at_exact_budget(self) -> None:
        from engine import public_endgame

        _, observation, actions = _public_endgame_fixture(
            current_hands={1: ("3S", "3C", "4S", "4C"), 2: ("5H",)},
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            baseline = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(baseline.status, "proven_win")
        self.assertIn(baseline.proven_action_id, {int(action["action_id"]) for action in actions})
        self.assertGreater(baseline.nodes, 0)
        proof_index = next(
            index for index, action in enumerate(actions)
            if int(action["action_id"]) == baseline.proven_action_id
        )

        original_build = public_endgame._build_public_game
        original_copy = public_endgame._copy_game
        built_games = []
        root_copies = 0

        def capture_build(*args, **kwargs):
            game = original_build(*args, **kwargs)
            built_games.append(game)
            return game

        def reject_later_root_copy(game):
            nonlocal root_copies
            if built_games and game._require_state() is built_games[0]._require_state():
                root_copies += 1
                if root_copies > proof_index + 1:
                    raise AssertionError("a later root action was searched after a complete win proof")
            return original_copy(game)

        with (
            patch("engine.public_endgame._build_public_game", side_effect=capture_build),
            patch("engine.public_endgame._copy_game", side_effect=reject_later_root_copy),
            patch("engine.public_endgame.monotonic", return_value=0.0),
        ):
            result = analyze_public_endgame(
                observation,
                actions,
                assignment,
                max_nodes=baseline.nodes,
            )

        self.assertEqual(result.status, "proven_win")
        self.assertEqual(result.proven_action_id, baseline.proven_action_id)
        self.assertEqual(root_copies, proof_index + 1)

    def test_default_factory_skips_model_for_multiple_proven_routes(self) -> None:
        game, observation, actions = _public_endgame_fixture(
            current_hands={1: ("3S", "3C", "4S", "4C"), 2: ("5H",)},
            finish_order=(3, 4),
            current_player_id=1,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        expected_values, _ = _reference_root_profiles(game)
        proven_ids = [action_id for action_id, value in expected_values if value == 1]
        self.assertGreater(len(proven_ids), 1)

        captured: list[dict[str, object]] = []
        config, factory = _factory_agent(captured)
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch("engine.public_endgame.monotonic", return_value=0.0),
        ):
            agent = factory(int(observation["my_info"]["player_id"]))
            selected = agent.select_action(observation, actions)

        self.assertEqual(selected, proven_ids[0])
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(agent.last_public_endgame_analysis.status, "proven_win")
        self.assertIn("可保底本队胜", agent.last_public_endgame_decision_summary)
        self.assertEqual(captured, [])

    def test_equivalent_raw_ids_choose_one_stable_original_representative(self) -> None:
        from agents.known_endgame import select_proven_endgame_action

        _, observation, actions = _public_endgame_fixture(
            current_hands={1: ("6S", "6C"), 2: ("5H",)},
            finish_order=(3, 4),
            current_player_id=1,
            leading_token="4H",
            leader_player_id=2,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            analysis = analyze_public_endgame(observation, actions, assignment)
        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        signatures = {
            int(action["action_id"]): DeepSeekClient._action_signature(action)
            for action in projected
        }
        raw_single_ids = [
            int(action["action_id"])
            for action in actions
            if action["declared_pattern"] == "single"
        ]
        self.assertEqual(len(raw_single_ids), 2)
        self.assertEqual(signatures[raw_single_ids[0]], signatures[raw_single_ids[1]])
        self.assertEqual(
            select_proven_endgame_action(analysis, actions, signatures),
            raw_single_ids[0],
        )

    def test_default_factory_formats_unresolved_endgame_and_keeps_model_id(self) -> None:
        _, observation, actions = _public_endgame_fixture(
            current_hands={3: ("6S", "7S"), 4: ("8S",)},
            finish_order=(1, 2),
            current_player_id=3,
            leading_token="5S",
            leader_player_id=4,
        )
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        with patch("engine.public_endgame.monotonic", return_value=0.0):
            solved = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(solved.status, "solved")
        from agents.known_endgame import select_proven_endgame_action

        self.assertIsNone(
            select_proven_endgame_action(
                solved,
                actions,
                {
                    int(action["action_id"]): DeepSeekClient._action_signature(action)
                    for action in DeepSeekClient._project_prompt_actions(observation, actions)
                },
            )
        )

        captured: list[dict[str, object]] = []
        config, factory = _factory_agent(captured)
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch("engine.public_endgame.analyze_public_endgame", return_value=solved),
        ):
            agent = factory(int(observation["my_info"]["player_id"]))
            selected = agent.select_action(observation, actions)

        self.assertEqual(len(captured), 1)
        self.assertEqual(agent.last_decision_source, "model")
        prompt = captured[0]["messages"][1]["content"]
        self.assertIn("【公开确证手牌】", prompt)
        self.assertIn("【公开残局推演】", prompt)
        self.assertIn("可达{", prompt)
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        visible_ids = {int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)}
        compared_ids = {
            int(value)
            for pair in re.findall(r"M5公开残局对照 action_id=(\d+).*?action_id=(\d+)", prompt)
            for value in pair
        }
        self.assertTrue(compared_ids)
        self.assertTrue(compared_ids.issubset(visible_ids))
        self.assertLessEqual(len(visible_ids), 80)
        self.assertIn(selected, visible_ids)
        self.assertIn(selected, {int(action["action_id"]) for action in actions})

    def test_budget_exceeded_and_oversized_exact_hands_still_reach_model_request(self) -> None:
        from engine.public_endgame import analyze_public_endgame as actual_analyze

        cases = (
            (
                "node_budget",
                _public_endgame_fixture(
                    current_hands={1: ("3S", "3C", "4S", "4C"), 2: ("5H",)},
                    finish_order=(3, 4),
                    current_player_id=1,
                )[1:],
            ),
            ("search_scope", _rollout_to_step(110, 69)[1:]),
        )
        for reason, (observation, actions) in cases:
            with self.subTest(reason=reason):
                assignment = exact_public_hand_assignment(observation)
                self.assertIsNotNone(assignment)
                captured: list[dict[str, object]] = []
                config, factory = _factory_agent(captured)
                if reason == "node_budget":
                    def limited(*args, **kwargs):
                        return actual_analyze(*args, **kwargs, max_nodes=1)
                    analyzer_patch = patch("engine.public_endgame.analyze_public_endgame", side_effect=limited)
                else:
                    analyzer_patch = patch("engine.public_endgame.analyze_public_endgame")

                with (
                    patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
                    analyzer_patch as analyzer,
                ):
                    agent = factory(int(observation["my_info"]["player_id"]))
                    selected = agent.select_action(observation, actions)

                self.assertEqual(len(captured), 1)
                self.assertEqual(agent.last_decision_source, "model")
                self.assertIn(selected, {int(action["action_id"]) for action in actions})
                self.assertIn("【公开确证手牌】", captured[0]["messages"][1]["content"])
                if reason == "node_budget":
                    self.assertEqual(agent.last_public_endgame_analysis.status, "budget_exceeded")
                    analyzer.assert_called_once()
                else:
                    self.assertIsNone(agent.last_public_endgame_analysis)
                    analyzer.assert_not_called()

    def test_uncertain_or_incomplete_public_assignment_is_not_disclosed(self) -> None:
        from copy import deepcopy

        _, observation, actions = _rollout_to_step(26, 85)
        truncated = deepcopy(observation)
        truncated["history"]["actions"].pop()
        self.assertIsNone(exact_public_hand_assignment(truncated))

        _, early_observation, early_actions = _rollout_to_step(1, 0)
        self.assertIsNone(exact_public_hand_assignment(early_observation))

        inconsistent_count = deepcopy(observation)
        next(row for row in inconsistent_count["other_players"] if not row["finished"])["hand_count"] += 1
        self.assertIsNone(exact_public_hand_assignment(inconsistent_count))

        scenarios = (
            (truncated, actions),
            (early_observation, early_actions),
            (inconsistent_count, actions),
        )
        for candidate_observation, candidate_actions in scenarios:
            with self.subTest(step=candidate_observation["current_round"]["step_no"]):
                captured: list[dict[str, object]] = []
                config, factory = _factory_agent(captured)
                with (
                    patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
                    patch("engine.public_endgame.analyze_public_endgame") as analyzer,
                ):
                    agent = factory(int(candidate_observation["my_info"]["player_id"]))
                    agent.select_action(candidate_observation, candidate_actions)
                self.assertEqual(len(captured), 1)
                prompt = captured[0]["messages"][1]["content"]
                self.assertNotIn("【公开确证手牌】", prompt)
                analyzer.assert_not_called()

        # This historical anchor is no longer a model-choice state: after the
        # rule correction its canonical action set contains only forced pass.
        # The local protocol shortcut must stay local and not fabricate a M9
        # disclosure or call the model.
        _, forced_observation, forced_actions = _rollout_to_step(9, 78)
        self.assertEqual([action["declared_pattern"] for action in forced_actions], ["pass"])
        captured: list[dict[str, object]] = []
        config, factory = _factory_agent(captured)
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch("engine.public_endgame.analyze_public_endgame") as analyzer,
        ):
            agent = factory(int(forced_observation["my_info"]["player_id"]))
            selected = agent.select_action(forced_observation, forced_actions)
        self.assertEqual(selected, int(forced_actions[0]["action_id"]))
        self.assertEqual(agent.last_decision_source, "local")
        self.assertEqual(captured, [])
        analyzer.assert_not_called()

    def test_explicit_time_budget_returns_no_partial_proof(self) -> None:
        _, observation, actions = _rollout_to_step(26, 85)
        assignment = exact_public_hand_assignment(observation)
        with patch("engine.public_endgame.monotonic", side_effect=(10.0, 11.0, 11.0)):
            result = analyze_public_endgame(
                observation,
                actions,
                assignment,
            )
        self.assertEqual(result.status, "budget_exceeded")
        self.assertEqual(result.action_values, ())
        self.assertEqual(result.action_reachable_values, ())


if __name__ == "__main__":
    unittest.main()
