"""Red tests for minimal tribute/return match-flow closure (tests-first).

This file intentionally defines the minimal contract first.
Engine implementation is expected in a later step.
"""

import unittest

from engine.cards import Card
from engine.game import FourAIGameRunner, build_initial_state
import engine.game as game_module
from engine.logging_utils import DebugLogger
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint
from agents.rule_based_ai import RuleBasedAIAgent


def _mk_player(player_id: int, cards: tuple[Card, ...]) -> PlayerState:
    return PlayerState(player_id=player_id, hand_cards=cards)


def _mk_finished_state(winner_player_id: int, players: tuple[PlayerState, ...]) -> GameState:
    return GameState(
        players=players,
        current_player_id=winner_player_id,
        table_constraint=TableConstraint(),
        step_no=123,
        round_no=7,
        is_finished=True,
        winner_player_id=winner_player_id,
    )


class TestMinimalTributeReturnFlow(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def test_1_finished_game_can_enter_tribute_phase(self) -> None:
        resolve = self._require_callable("resolve_head_last_players")

        players = (
            _mk_player(0, ()),
            _mk_player(1, (Card(rank="A", suit="S"),)),
            _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
            _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
        )
        finished = _mk_finished_state(winner_player_id=0, players=players)

        head_id, last_id = resolve(finished)
        self.assertEqual(head_id, 0)
        self.assertEqual(last_id, 3)

    def test_2_can_identify_head_and_last(self) -> None:
        resolve = self._require_callable("resolve_head_last_players")

        players = (
            _mk_player(0, (Card(rank="A", suit="S"), Card(rank="K", suit="S"))),
            _mk_player(1, ()),
            _mk_player(2, (Card(rank="7", suit="S"),)),
            _mk_player(3, (Card(rank="3", suit="S"), Card(rank="4", suit="S"), Card(rank="5", suit="S"))),
        )
        finished = _mk_finished_state(winner_player_id=1, players=players)

        head_id, last_id = resolve(finished)
        self.assertEqual(head_id, 1)
        self.assertEqual(last_id, 3)

    def test_3_tribute_direction_last_loses_one_head_gains_one(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"),)),
            _mk_player(2, (Card(rank="8", suit="S"),)),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        updated_players, detail = apply_tr(players, head_player_id=0, last_player_id=3)

        self.assertEqual(detail["counts_after_tribute"][0], 4)
        self.assertEqual(detail["counts_after_tribute"][3], 2)
        self.assertEqual(len(updated_players[0].hand_cards), 3)
        self.assertEqual(len(updated_players[3].hand_cards), 3)

    def test_4_return_direction_head_loses_one_last_gains_one(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"),)),
            _mk_player(2, (Card(rank="8", suit="S"),)),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        _updated_players, detail = apply_tr(players, head_player_id=0, last_player_id=3)

        self.assertEqual(detail["counts_after_return"][0], 3)
        self.assertEqual(detail["counts_after_return"][3], 3)

    def test_5_tribute_card_rule_last_must_give_highest_single(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"),)),
            _mk_player(2, (Card(rank="8", suit="S"),)),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        _updated_players, detail = apply_tr(players, head_player_id=0, last_player_id=3)

        self.assertEqual(detail["tribute_card"].rank, "A")

    def test_6_return_card_rule_head_must_give_lowest_single(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"),)),
            _mk_player(2, (Card(rank="8", suit="S"),)),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        _updated_players, detail = apply_tr(players, head_player_id=0, last_player_id=3)

        self.assertEqual(detail["return_card"].rank, "4")

    def test_7_total_cards_are_conserved_after_tribute_return(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"),)),
            _mk_player(2, (Card(rank="8", suit="S"),)),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        before = sum(len(p.hand_cards) for p in players)
        updated_players, _detail = apply_tr(players, head_player_id=0, last_player_id=3)
        after = sum(len(p.hand_cards) for p in updated_players)

        self.assertEqual(before, after)

    def test_8_other_players_hands_not_polluted(self) -> None:
        apply_tr = self._require_callable("apply_minimal_tribute_return")

        players = (
            _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
            _mk_player(1, (Card(rank="9", suit="S"), Card(rank="9", suit="H"))),
            _mk_player(2, (Card(rank="8", suit="S"), Card(rank="8", suit="H"))),
            _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
        )

        updated_players, _detail = apply_tr(players, head_player_id=0, last_player_id=3)

        self.assertEqual(updated_players[1].hand_cards, players[1].hand_cards)
        self.assertEqual(updated_players[2].hand_cards, players[2].hand_cards)

    def test_9_after_tribute_return_can_start_next_game_initial_flow(self) -> None:
        start_next = self._require_callable("start_next_game_after_minimal_tribute")
        execute_transition = self._require_callable("execute_minimal_tribute_transition")

        players = (
            _mk_player(0, ()),
            _mk_player(1, (Card(rank="A", suit="S"),)),
            _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
            _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
        )
        finished = _mk_finished_state(winner_player_id=0, players=players)

        expected_players, _expected_detail = execute_transition(finished_state=finished)
        next_state, detail = start_next(finished, seed=42)

        self.assertFalse(next_state.is_finished)
        self.assertEqual(next_state.round_no, 1)
        self.assertEqual(next_state.current_player_id, 0)
        self.assertEqual(next_state.players, expected_players)
        self.assertIn("head_player_id", detail)
        self.assertIn("last_player_id", detail)
        self.assertIn("tribute_card", detail)
        self.assertIn("return_card", detail)

    def test_10_existing_single_game_mainline_is_still_valid(self) -> None:
        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=7))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)


class TestMinimalMatchHandoverFlow(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_handover(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def test_11_finished_game_can_build_minimal_match_handover_record(self) -> None:
        build_record = self._require_callable("build_minimal_match_handover_record")
        finished = self._build_finished_state_for_handover()

        record = build_record(finished_state=finished, game_index=1)

        self.assertEqual(record["game_index"], 1)
        self.assertEqual(record["winner_player_id"], 0)
        self.assertEqual(record["head_player_id"], 0)
        self.assertEqual(record["last_player_id"], 3)

    def test_12_handover_record_contains_required_fields(self) -> None:
        build_record = self._require_callable("build_minimal_match_handover_record")
        finished = self._build_finished_state_for_handover()

        record = build_record(finished_state=finished, game_index=2)

        required = {
            "winner_player_id",
            "head_player_id",
            "last_player_id",
            "game_index",
        }
        self.assertTrue(required.issubset(record.keys()))

    def test_13_handover_can_create_next_game_after_one_tribute_return(self) -> None:
        advance_once = self._require_callable("advance_minimal_match_once")
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_for_handover()

        expected_players, _expected_detail = execute_transition(finished_state=finished)
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=1,
            seed=123,
        )

        self.assertFalse(next_state.is_finished)
        self.assertEqual(next_state.round_no, 1)
        self.assertEqual(next_state.players, expected_players)
        self.assertEqual(handover["winner_player_id"], 0)
        self.assertEqual(handover["head_player_id"], 0)
        self.assertEqual(handover["last_player_id"], 3)

    def test_14_match_counter_is_incremented(self) -> None:
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_handover()

        handover, _next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=1,
            seed=321,
        )

        self.assertEqual(handover["games_played_before"], 1)
        self.assertEqual(handover["games_played_after"], 2)

    def test_15_two_game_minimal_handover_is_repeatable(self) -> None:
        advance_once = self._require_callable("advance_minimal_match_once")

        finished_game1 = self._build_finished_state_for_handover()
        handover1, _next_state1 = advance_once(
            finished_state=finished_game1,
            game_index=1,
            games_played=1,
            seed=11,
        )

        finished_game2 = _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="4", suit="S"), Card(rank="5", suit="S"))),
                _mk_player(1, (Card(rank="6", suit="S"),)),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="8", suit="S"), Card(rank="9", suit="S"))),
            ),
        )
        handover2, _next_state2 = advance_once(
            finished_state=finished_game2,
            game_index=2,
            games_played=handover1["games_played_after"],
            seed=12,
        )

        self.assertEqual(handover1["games_played_after"], 2)
        self.assertEqual(handover2["games_played_before"], 2)
        self.assertEqual(handover2["games_played_after"], 3)

    def test_16_unfinished_state_cannot_enter_match_handover(self) -> None:
        build_record = self._require_callable("build_minimal_match_handover_record")
        unfinished = build_initial_state(seed=19)

        with self.assertRaises(ValueError):
            _ = build_record(finished_state=unfinished, game_index=1)

    def test_17_single_game_mainline_stability_is_not_broken(self) -> None:
        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=27))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)


class TestMinimalMatchFinishBoundaryFlow(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_boundary(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=1,
            players=(
                _mk_player(0, (Card(rank="Q", suit="S"),)),
                _mk_player(1, ()),
                _mk_player(2, (Card(rank="8", suit="S"), Card(rank="7", suit="S"))),
                _mk_player(3, (Card(rank="A", suit="S"), Card(rank="K", suit="S"), Card(rank="9", suit="S"))),
            ),
        )

    def test_18_under_max_games_match_not_finished_and_can_continue(self) -> None:
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_for_boundary()

        expected_players, _expected_detail = execute_transition(finished_state=finished)
        handover, next_state, match_state = advance_with_boundary(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=2,
            seed=101,
        )

        self.assertEqual(handover["winner_player_id"], 1)
        self.assertIsNotNone(next_state)
        self.assertFalse(next_state.is_finished)
        assert next_state is not None
        self.assertEqual(next_state.players, expected_players)
        self.assertEqual(match_state["games_played"], 1)
        self.assertEqual(match_state["max_games"], 2)
        self.assertFalse(match_state["is_match_finished"])

    def test_19_reaching_max_games_marks_match_finished(self) -> None:
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        finished = self._build_finished_state_for_boundary()

        _handover, next_state, match_state = advance_with_boundary(
            finished_state=finished,
            game_index=2,
            games_played=1,
            max_games=2,
            seed=102,
        )

        self.assertIsNone(next_state)
        self.assertEqual(match_state["games_played"], 2)
        self.assertEqual(match_state["max_games"], 2)
        self.assertTrue(match_state["is_match_finished"])

    def test_20_finished_match_cannot_advance_further(self) -> None:
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        finished = self._build_finished_state_for_boundary()

        with self.assertRaises(ValueError):
            _ = advance_with_boundary(
                finished_state=finished,
                game_index=3,
                games_played=2,
                max_games=2,
                seed=103,
            )

    def test_21_match_counter_and_finished_flag_are_consistent(self) -> None:
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        finished = self._build_finished_state_for_boundary()

        _handover1, _next_state1, state1 = advance_with_boundary(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            seed=104,
        )
        self.assertEqual(state1["is_match_finished"], state1["games_played"] >= state1["max_games"])

        _handover2, _next_state2, state2 = advance_with_boundary(
            finished_state=finished,
            game_index=3,
            games_played=2,
            max_games=3,
            seed=105,
        )
        self.assertEqual(state2["is_match_finished"], state2["games_played"] >= state2["max_games"])

    def test_22_existing_minimal_match_handover_closure_is_not_broken(self) -> None:
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_boundary()

        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=1,
            seed=106,
        )

        self.assertEqual(handover["games_played_before"], 1)
        self.assertEqual(handover["games_played_after"], 2)
        self.assertFalse(next_state.is_finished)

    def test_23_single_game_mainline_stability_is_not_broken(self) -> None:
        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=37))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)


class TestCompleteFinishOrderClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_finish_order(self) -> GameState:
        # winner=0, remaining hand counts among non-winner are 1,2,3 for deterministic 1~4 place.
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(
                    3,
                    (
                        Card(rank="10", suit="S"),
                        Card(rank="9", suit="S"),
                        Card(rank="8", suit="S"),
                    ),
                ),
            ),
        )

    def _build_extreme_finished_state_for_finish_order(self) -> GameState:
        # Extreme tie-like remainder among non-winner, order must still be deterministic and complete.
        return _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="5", suit="S"), Card(rank="5", suit="H"))),
                _mk_player(1, (Card(rank="6", suit="S"), Card(rank="6", suit="H"))),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="7", suit="H"))),
            ),
        )

    def test_24_finished_game_can_build_complete_finish_order_len_4(self) -> None:
        build_finish = self._require_callable("build_complete_finish_order")
        finished = self._build_finished_state_for_finish_order()

        finish_order = build_finish(finished_state=finished)

        self.assertEqual(len(finish_order), 4)

    def test_25_finish_order_players_are_unique_no_duplicates(self) -> None:
        build_finish = self._require_callable("build_complete_finish_order")
        finished = self._build_finished_state_for_finish_order()

        finish_order = build_finish(finished_state=finished)

        self.assertEqual(len(set(finish_order)), 4)
        self.assertEqual(set(finish_order), {0, 1, 2, 3})

    def test_26_finish_order_can_map_to_minimal_team_finish_summary(self) -> None:
        build_summary = self._require_callable("build_minimal_team_finish_summary")
        finished = self._build_finished_state_for_finish_order()

        summary = build_summary(finished_state=finished)

        self.assertIn("finish_order", summary)
        self.assertIn("team_finish_summary", summary)
        self.assertEqual(len(summary["finish_order"]), 4)
        self.assertIn(0, summary["team_finish_summary"])
        self.assertIn(1, summary["team_finish_summary"])
        self.assertEqual(len(summary["team_finish_summary"][0]), 2)
        self.assertEqual(len(summary["team_finish_summary"][1]), 2)

    def test_27_extreme_state_still_builds_deterministic_complete_finish_order(self) -> None:
        build_finish = self._require_callable("build_complete_finish_order")
        extreme_finished = self._build_extreme_finished_state_for_finish_order()

        first = build_finish(finished_state=extreme_finished)
        second = build_finish(finished_state=extreme_finished)

        self.assertEqual(len(first), 4)
        self.assertEqual(first, second)
        self.assertEqual(first[0], 2)

    def test_28_finish_order_closure_does_not_break_minimal_match_handover(self) -> None:
        build_summary = self._require_callable("build_minimal_team_finish_summary")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_finish_order()

        summary = build_summary(finished_state=finished)
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=210,
        )

        self.assertEqual(len(summary["finish_order"]), 4)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_29_finish_order_closure_does_not_break_single_game_mainline(self) -> None:
        build_finish = self._require_callable("build_complete_finish_order")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=41))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        finish_order = build_finish(finished_state=final_state)
        self.assertEqual(len(finish_order), 4)


class TestMinimalTeamOutcomeClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_team_outcome(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_extreme_finished_state_for_team_outcome(self) -> GameState:
        # Non-winner players tie on remaining hand size; result must still be deterministic.
        return _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="5", suit="S"), Card(rank="5", suit="H"))),
                _mk_player(1, (Card(rank="6", suit="S"), Card(rank="6", suit="H"))),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="7", suit="H"))),
            ),
        )

    def test_30_finished_game_can_build_minimal_team_outcome(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        finished = self._build_finished_state_for_team_outcome()

        outcome = build_outcome(finished_state=finished)

        self.assertIsInstance(outcome, dict)

    def test_31_minimal_team_outcome_contains_required_fields(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        finished = self._build_finished_state_for_team_outcome()

        outcome = build_outcome(finished_state=finished)

        required = {
            "finish_order",
            "team_finish_summary",
            "winner_team_id",
            "loser_team_id",
            "outcome_basis",
        }
        self.assertTrue(required.issubset(outcome.keys()))

    def test_32_winner_team_matches_finish_order_first_player_team(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        finished = self._build_finished_state_for_team_outcome()

        outcome = build_outcome(finished_state=finished)

        finish_order = outcome["finish_order"]
        expected_winner_team = finish_order[0] % 2
        self.assertEqual(outcome["winner_team_id"], expected_winner_team)
        self.assertEqual(outcome["loser_team_id"], 1 - expected_winner_team)

    def test_33_minimal_team_outcome_is_deterministic_for_same_finished_state(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        finished = self._build_finished_state_for_team_outcome()

        first = build_outcome(finished_state=finished)
        second = build_outcome(finished_state=finished)

        self.assertEqual(first, second)

    def test_34_extreme_tie_state_still_builds_stable_team_outcome(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        finished = self._build_extreme_finished_state_for_team_outcome()

        outcome1 = build_outcome(finished_state=finished)
        outcome2 = build_outcome(finished_state=finished)

        self.assertEqual(outcome1, outcome2)
        self.assertEqual(outcome1["winner_team_id"], finished.winner_player_id % 2)

    def test_35_team_outcome_closure_does_not_break_minimal_match_handover(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_team_outcome()

        outcome = build_outcome(finished_state=finished)
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=307,
        )

        self.assertIn("winner_team_id", outcome)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_36_team_outcome_closure_does_not_break_single_game_mainline(self) -> None:
        build_outcome = self._require_callable("build_minimal_team_outcome")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=53))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        outcome = build_outcome(finished_state=final_state)
        self.assertIn("winner_team_id", outcome)


class TestMinimalTeamSettlementClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_12_vs_34(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(2, (Card(rank="A", suit="S"),)),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_finished_state_13_vs_24(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_finished_state_14_vs_23(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
                _mk_player(3, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
            ),
        )

    def test_58_finished_game_can_build_minimal_team_settlement(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_13_vs_24()

        settlement = build_settlement(finished_state=finished)

        self.assertIsInstance(settlement, dict)

    def test_59_minimal_team_settlement_contains_required_fields(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_13_vs_24()

        settlement = build_settlement(finished_state=finished)

        required = {
            "finish_order",
            "team_finish_summary",
            "winner_team_id",
            "loser_team_id",
            "settlement_pattern",
            "settlement_basis",
        }
        self.assertTrue(required.issubset(settlement.keys()))

    def test_60_same_team_rank_1_and_2_maps_to_12_vs_34(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_12_vs_34()

        settlement = build_settlement(finished_state=finished)

        self.assertEqual(settlement["team_finish_summary"][0], [1, 2])
        self.assertEqual(settlement["settlement_pattern"], "12_vs_34")

    def test_61_same_team_rank_1_and_3_maps_to_13_vs_24(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_13_vs_24()

        settlement = build_settlement(finished_state=finished)

        self.assertEqual(settlement["team_finish_summary"][0], [1, 3])
        self.assertEqual(settlement["settlement_pattern"], "13_vs_24")

    def test_62_same_team_rank_1_and_4_maps_to_14_vs_23(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_14_vs_23()

        settlement = build_settlement(finished_state=finished)

        self.assertEqual(settlement["team_finish_summary"][0], [1, 4])
        self.assertEqual(settlement["settlement_pattern"], "14_vs_23")

    def test_63_minimal_team_settlement_is_deterministic(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        finished = self._build_finished_state_13_vs_24()

        first = build_settlement(finished_state=finished)
        second = build_settlement(finished_state=finished)

        self.assertEqual(first, second)

    def test_64_team_settlement_closure_does_not_break_existing_match_helpers(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")
        build_outcome = self._require_callable("build_minimal_team_outcome")
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        build_level_card = self._require_callable("build_minimal_level_card_change_outcome")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_13_vs_24()

        settlement = build_settlement(finished_state=finished)
        outcome = build_outcome(finished_state=finished)
        level_change = build_level_change(
            finished_state=finished,
            team_levels={0: 6, 1: 6},
        )
        level_card = build_level_card(
            finished_state=finished,
            team_levels={0: 6, 1: 6},
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=365,
        )

        self.assertEqual(settlement["winner_team_id"], outcome["winner_team_id"])
        self.assertIn("winner_team_id", level_change)
        self.assertIn("winner_team_id", level_card)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_65_team_settlement_closure_does_not_break_single_game_mainline(self) -> None:
        build_settlement = self._require_callable("build_minimal_team_settlement")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=365))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        settlement = build_settlement(finished_state=final_state)
        self.assertIn("settlement_pattern", settlement)


class TestMinimalTributeTransitionClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_12_vs_34(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(2, (Card(rank="A", suit="S"),)),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_finished_state_13_vs_24(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_finished_state_14_vs_23(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
                _mk_player(3, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
            ),
        )

    def test_66_finished_game_can_build_minimal_tribute_transition(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_13_vs_24()

        transition = build_transition(finished_state=finished)

        self.assertIsInstance(transition, dict)

    def test_67_minimal_tribute_transition_contains_required_fields(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_13_vs_24()

        transition = build_transition(finished_state=finished)

        required = {
            "settlement_pattern",
            "tribute_mode",
            "head_player_ids",
            "tribute_player_ids",
            "transition_basis",
        }
        self.assertTrue(required.issubset(transition.keys()))

    def test_68_settlement_13_vs_24_maps_to_single_tribute(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_13_vs_24()

        transition = build_transition(finished_state=finished)

        self.assertEqual(transition["settlement_pattern"], "13_vs_24")
        self.assertEqual(transition["tribute_mode"], "single_tribute")
        self.assertEqual(transition["head_player_ids"], [0])
        self.assertEqual(transition["tribute_player_ids"], [3])

    def test_69_settlement_14_vs_23_maps_to_single_tribute(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_14_vs_23()

        transition = build_transition(finished_state=finished)

        self.assertEqual(transition["settlement_pattern"], "14_vs_23")
        self.assertEqual(transition["tribute_mode"], "single_tribute")
        self.assertEqual(transition["head_player_ids"], [0])
        self.assertEqual(transition["tribute_player_ids"], [2])

    def test_70_settlement_12_vs_34_maps_to_double_tribute_family(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_12_vs_34()

        transition = build_transition(finished_state=finished)

        self.assertEqual(transition["settlement_pattern"], "12_vs_34")
        self.assertEqual(transition["tribute_mode"], "double_tribute_family")
        self.assertEqual(transition["head_player_ids"], [0, 2])
        self.assertEqual(transition["tribute_player_ids"], [1, 3])

    def test_71_minimal_tribute_transition_is_deterministic(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        finished = self._build_finished_state_12_vs_34()

        first = build_transition(finished_state=finished)
        second = build_transition(finished_state=finished)

        self.assertEqual(first, second)

    def test_72_tribute_transition_closure_does_not_break_existing_match_helpers(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")
        build_settlement = self._require_callable("build_minimal_team_settlement")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_13_vs_24()

        transition = build_transition(finished_state=finished)
        settlement = build_settlement(finished_state=finished)
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=366,
        )

        self.assertEqual(transition["settlement_pattern"], settlement["settlement_pattern"])
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_73_tribute_transition_closure_does_not_break_single_game_mainline(self) -> None:
        build_transition = self._require_callable("build_minimal_tribute_transition")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=366))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        transition = build_transition(finished_state=final_state)
        self.assertIn("tribute_mode", transition)


class TestMinimalRealTributeExecutionClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_single_tribute(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
                _mk_player(1, (Card(rank="9", suit="S"),)),
                _mk_player(2, (Card(rank="8", suit="S"),)),
                _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
            ),
        )

    def _build_finished_state_double_tribute(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, (Card(rank="4", suit="S"), Card(rank="6", suit="S"))),
                _mk_player(1, (Card(rank="K", suit="S"), Card(rank="8", suit="S"))),
                _mk_player(2, (Card(rank="5", suit="S"),)),
                _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="S"), Card(rank="3", suit="S"))),
            ),
        )

    def test_74_finished_game_can_execute_minimal_tribute_transition(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_single_tribute()

        updated_players, detail = execute_transition(finished_state=finished)

        self.assertEqual(len(updated_players), 4)
        self.assertIsInstance(detail, dict)

    def test_75_single_tribute_execution_matches_existing_minimal_behavior(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        apply_single = self._require_callable("apply_minimal_tribute_return")
        finished = self._build_finished_state_single_tribute()

        updated_players, detail = execute_transition(finished_state=finished)
        expected_players, expected_detail = apply_single(
            finished.players,
            head_player_id=0,
            last_player_id=3,
        )

        self.assertEqual(updated_players, expected_players)
        self.assertEqual(detail["tribute_mode"], "single_tribute")
        self.assertEqual(detail["tribute_card"], expected_detail["tribute_card"])
        self.assertEqual(detail["return_card"], expected_detail["return_card"])
        self.assertEqual(detail["counts_after_return"], expected_detail["counts_after_return"])

    def test_76_double_tribute_execution_yields_two_pairs_two_tribute_cards_two_return_cards(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        updated_players, detail = execute_transition(finished_state=finished)

        self.assertEqual(detail["tribute_mode"], "double_tribute_family")
        self.assertEqual(detail["head_player_ids"], [0, 2])
        self.assertEqual(detail["tribute_player_ids"], [1, 3])
        self.assertEqual(detail["anti_tribute_requested"], False)
        self.assertEqual(detail["anti_tribute_status"], "not_requested")
        self.assertEqual(len(detail["exchange_pairs"]), 2)
        self.assertEqual([card.rank for card in detail["tribute_cards"]], ["A", "K"])
        self.assertEqual([card.rank for card in detail["return_cards"]], ["4", "5"])
        self.assertEqual(tuple(card.rank for card in updated_players[0].hand_cards), ("6", "A"))
        self.assertEqual(tuple(card.rank for card in updated_players[1].hand_cards), ("8", "5"))
        self.assertEqual(tuple(card.rank for card in updated_players[2].hand_cards), ("K",))
        self.assertEqual(tuple(card.rank for card in updated_players[3].hand_cards), ("9", "3", "4"))

    def test_77_double_tribute_execution_conserves_cards_and_does_not_pollute_non_participants(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        before_total = sum(len(player.hand_cards) for player in finished.players)
        updated_players, detail = execute_transition(finished_state=finished)
        after_total = sum(len(player.hand_cards) for player in updated_players)

        self.assertEqual(before_total, after_total)
        self.assertEqual(detail["counts_after_execution"], {0: 2, 1: 2, 2: 1, 3: 3})

    def test_78_real_tribute_execution_contains_required_fields(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        _updated_players, detail = execute_transition(finished_state=finished)

        required = {
            "settlement_pattern",
            "tribute_mode",
            "head_player_ids",
            "tribute_player_ids",
            "tribute_cards",
            "return_cards",
            "exchange_pairs",
            "counts_after_execution",
            "anti_tribute_requested",
            "anti_tribute_status",
            "execution_basis",
        }
        self.assertTrue(required.issubset(detail.keys()))

    def test_79_real_tribute_execution_is_deterministic(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        first_players, first_detail = execute_transition(finished_state=finished)
        second_players, second_detail = execute_transition(finished_state=finished)

        self.assertEqual(first_players, second_players)
        self.assertEqual(first_detail, second_detail)

    def test_80_start_next_game_bridge_reuses_real_tribute_execution_contract(self) -> None:
        start_next = self._require_callable("start_next_game_after_minimal_tribute")
        finished = self._build_finished_state_double_tribute()

        next_state, detail = start_next(finished_state=finished, seed=367)

        self.assertFalse(next_state.is_finished)
        self.assertEqual(detail["tribute_mode"], "double_tribute_family")
        self.assertEqual(len(detail["tribute_cards"]), 2)
        self.assertEqual(len(detail["return_cards"]), 2)

    def test_81_real_tribute_execution_closure_does_not_break_existing_match_and_game_flow(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        build_transition = self._require_callable("build_minimal_tribute_transition")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_single_tribute()

        updated_players, detail = execute_transition(finished_state=finished)
        transition = build_transition(finished_state=finished)
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=368,
        )

        self.assertEqual(detail["tribute_mode"], transition["tribute_mode"])
        self.assertEqual(sum(len(p.hand_cards) for p in updated_players), sum(len(p.hand_cards) for p in finished.players))
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)


class TestUnifiedMatchProgressionClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_single_tribute(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, (Card(rank="4", suit="S"), Card(rank="Q", suit="S"), Card(rank="6", suit="S"))),
                _mk_player(1, (Card(rank="9", suit="S"),)),
                _mk_player(2, (Card(rank="8", suit="S"),)),
                _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="H"), Card(rank="3", suit="D"))),
            ),
        )

    def _build_finished_state_double_tribute(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, (Card(rank="4", suit="S"), Card(rank="6", suit="S"))),
                _mk_player(1, (Card(rank="K", suit="S"), Card(rank="8", suit="S"))),
                _mk_player(2, (Card(rank="5", suit="S"),)),
                _mk_player(3, (Card(rank="A", suit="S"), Card(rank="9", suit="S"), Card(rank="3", suit="S"))),
            ),
        )

    def test_82_finished_game_can_build_minimal_match_progression(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        finished = self._build_finished_state_single_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=601,
        )

        self.assertIsInstance(progression, dict)

    def test_83_minimal_match_progression_contains_required_fields(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        finished = self._build_finished_state_single_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=602,
        )

        required = {
            "winner_player_id",
            "head_player_id",
            "last_player_id",
            "game_index",
            "games_played_before",
            "games_played_after",
            "max_games",
            "is_match_finished",
            "finish_order",
            "team_finish_summary",
            "winner_team_id",
            "loser_team_id",
            "settlement_pattern",
            "tribute_mode",
            "tribute_detail",
            "anti_tribute_requested",
            "anti_tribute_status",
            "team_levels_before",
            "team_levels_after",
            "team_level_cards_before",
            "team_level_cards_after",
            "next_state",
            "progression_basis",
        }
        self.assertTrue(required.issubset(progression.keys()))

    def test_84_single_tribute_progression_carries_real_tribute_result_into_next_state(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_single_tribute()

        expected_players, expected_detail = execute_transition(finished_state=finished)
        progression = build_progression(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=603,
        )

        next_state = progression["next_state"]
        self.assertIsNotNone(next_state)
        assert isinstance(next_state, GameState)
        self.assertEqual(next_state.players, expected_players)
        self.assertEqual(next_state.current_player_id, 0)
        self.assertEqual(next_state.round_no, 1)
        self.assertEqual(progression["tribute_detail"], expected_detail)

    def test_85_double_tribute_progression_carries_real_tribute_result_into_next_state(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        expected_players, expected_detail = execute_transition(finished_state=finished)
        progression = build_progression(
            finished_state=finished,
            game_index=2,
            games_played=1,
            max_games=4,
            team_levels={0: 8, 1: 8},
            seed=604,
        )

        next_state = progression["next_state"]
        self.assertIsNotNone(next_state)
        assert isinstance(next_state, GameState)
        self.assertEqual(progression["tribute_mode"], "double_tribute_family")
        self.assertEqual(next_state.players, expected_players)
        self.assertEqual(progression["tribute_detail"], expected_detail)

    def test_86_match_boundary_returns_complete_level_results_without_next_state(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        finished = self._build_finished_state_single_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=3,
            games_played=2,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=605,
        )

        self.assertTrue(progression["is_match_finished"])
        self.assertIsNone(progression["next_state"])
        self.assertIsNone(progression["tribute_detail"])
        self.assertEqual(progression["team_levels_before"], {0: 6, 1: 6})
        self.assertEqual(progression["team_levels_after"], {0: 7, 1: 5})
        self.assertEqual(progression["team_level_cards_before"], {0: "6", 1: "6"})
        self.assertEqual(progression["team_level_cards_after"], {0: "7", 1: "5"})

    def test_87_existing_wrappers_reuse_minimal_match_progression_contract(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        advance_once = self._require_callable("advance_minimal_match_once")
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        finished = self._build_finished_state_single_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=606,
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            team_levels={0: 6, 1: 6},
            seed=606,
        )
        boundary_handover, boundary_next_state, match_state = advance_with_boundary(
            finished_state=finished,
            game_index=1,
            games_played=0,
            max_games=3,
            team_levels={0: 6, 1: 6},
            seed=606,
        )

        self.assertEqual(handover["settlement_pattern"], progression["settlement_pattern"])
        self.assertEqual(handover["tribute_mode"], progression["tribute_mode"])
        self.assertEqual(handover["team_levels_after"], progression["team_levels_after"])
        self.assertEqual(next_state.players, progression["next_state"].players)
        self.assertEqual(boundary_handover["team_level_cards_after"], progression["team_level_cards_after"])
        self.assertEqual(boundary_next_state.players, progression["next_state"].players)
        self.assertEqual(match_state["games_played"], progression["games_played_after"])
        self.assertFalse(match_state["is_match_finished"])

    def test_88_handover_record_contains_settlement_and_transition_fields(self) -> None:
        build_record = self._require_callable("build_minimal_match_handover_record")
        finished = self._build_finished_state_double_tribute()

        record = build_record(finished_state=finished, game_index=2)

        required = {
            "finish_order",
            "team_finish_summary",
            "winner_team_id",
            "loser_team_id",
            "settlement_pattern",
            "tribute_mode",
            "head_player_ids",
            "tribute_player_ids",
        }
        self.assertTrue(required.issubset(record.keys()))

    def test_89_double_tribute_anti_tribute_requested_bypasses_real_exchange(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_double_tribute()

        updated_players, detail = execute_transition(
            finished_state=finished,
            anti_tribute_requested=True,
        )

        self.assertEqual(updated_players, finished.players)
        self.assertEqual(detail["tribute_mode"], "double_tribute_family")
        self.assertEqual(detail["anti_tribute_requested"], True)
        self.assertEqual(detail["anti_tribute_status"], "applied")
        self.assertEqual(detail["tribute_cards"], [])
        self.assertEqual(detail["return_cards"], [])
        self.assertEqual(detail["exchange_pairs"], [])
        self.assertEqual(detail["counts_after_execution"], {0: 2, 1: 2, 2: 1, 3: 3})

    def test_90_anti_tribute_next_state_keeps_original_players(self) -> None:
        start_next = self._require_callable("start_next_game_after_minimal_tribute")
        finished = self._build_finished_state_double_tribute()

        next_state, detail = start_next(
            finished_state=finished,
            seed=607,
            anti_tribute_requested=True,
        )

        self.assertEqual(next_state.players, finished.players)
        self.assertEqual(detail["anti_tribute_requested"], True)
        self.assertEqual(detail["anti_tribute_status"], "applied")

    def test_91_match_progression_and_wrappers_propagate_anti_tribute_fields(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        advance_once = self._require_callable("advance_minimal_match_once")
        advance_with_boundary = self._require_callable("advance_minimal_match_with_boundary")
        finished = self._build_finished_state_double_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=2,
            games_played=1,
            max_games=4,
            team_levels={0: 8, 1: 8},
            seed=608,
            anti_tribute_requested=True,
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=2,
            games_played=1,
            team_levels={0: 8, 1: 8},
            seed=608,
            anti_tribute_requested=True,
        )
        boundary_handover, boundary_next_state, match_state = advance_with_boundary(
            finished_state=finished,
            game_index=2,
            games_played=1,
            max_games=4,
            team_levels={0: 8, 1: 8},
            seed=608,
            anti_tribute_requested=True,
        )

        self.assertEqual(progression["anti_tribute_requested"], True)
        self.assertEqual(progression["anti_tribute_status"], "applied")
        self.assertEqual(handover["anti_tribute_status"], "applied")
        self.assertEqual(boundary_handover["anti_tribute_status"], "applied")
        self.assertEqual(next_state.players, finished.players)
        self.assertEqual(boundary_next_state.players, finished.players)
        self.assertFalse(match_state["is_match_finished"])

    def test_92_single_tribute_anti_tribute_requested_is_rejected(self) -> None:
        execute_transition = self._require_callable("execute_minimal_tribute_transition")
        finished = self._build_finished_state_single_tribute()

        with self.assertRaises(ValueError):
            _ = execute_transition(
                finished_state=finished,
                anti_tribute_requested=True,
            )

    def test_93_match_boundary_with_anti_tribute_still_returns_complete_level_results(self) -> None:
        build_progression = self._require_callable("build_minimal_match_progression")
        finished = self._build_finished_state_double_tribute()

        progression = build_progression(
            finished_state=finished,
            game_index=4,
            games_played=3,
            max_games=4,
            team_levels={0: 8, 1: 8},
            seed=609,
            anti_tribute_requested=True,
        )

        self.assertTrue(progression["is_match_finished"])
        self.assertIsNone(progression["next_state"])
        self.assertIsNone(progression["tribute_detail"])
        self.assertEqual(progression["anti_tribute_requested"], True)
        self.assertEqual(progression["anti_tribute_status"], "skipped_match_finished")
        self.assertEqual(progression["team_levels_before"], {0: 8, 1: 8})
        self.assertEqual(progression["team_levels_after"], {0: 9, 1: 7})

class TestMinimalPromotionDemotionClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_level_change(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_extreme_finished_state_for_level_change(self) -> GameState:
        # Non-winner players tie on remaining hand size; promotion/demotion outcome must remain deterministic.
        return _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="5", suit="S"), Card(rank="5", suit="H"))),
                _mk_player(1, (Card(rank="6", suit="S"), Card(rank="6", suit="H"))),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="7", suit="H"))),
            ),
        )

    def test_37_finished_game_can_build_minimal_promotion_demotion_outcome(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_level_change()

        result = build_level_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        self.assertIsInstance(result, dict)

    def test_38_minimal_promotion_demotion_outcome_contains_required_fields(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_level_change()

        result = build_level_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        required = {
            "winner_team_id",
            "loser_team_id",
            "team_levels_before",
            "team_levels_after",
            "level_change_basis",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_39_winner_team_level_up_and_loser_team_level_down(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_level_change()

        result = build_level_change(
            finished_state=finished,
            team_levels={0: 7, 1: 7},
        )

        winner_team_id = result["winner_team_id"]
        loser_team_id = result["loser_team_id"]
        before = result["team_levels_before"]
        after = result["team_levels_after"]

        self.assertEqual(after[winner_team_id], before[winner_team_id] + 1)
        self.assertEqual(after[loser_team_id], before[loser_team_id] - 1)

    def test_40_minimal_promotion_demotion_outcome_is_deterministic(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_level_change()

        first = build_level_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )
        second = build_level_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )

        self.assertEqual(first, second)

    def test_41_extreme_tie_state_still_builds_stable_level_change_outcome(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_extreme_finished_state_for_level_change()

        first = build_level_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )
        second = build_level_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )

        self.assertEqual(first, second)

    def test_42_level_change_closure_does_not_break_minimal_match_handover(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_level_change()

        result = build_level_change(
            finished_state=finished,
            team_levels={0: 6, 1: 6},
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=401,
        )

        self.assertIn("winner_team_id", result)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_43_level_change_closure_does_not_break_single_game_mainline(self) -> None:
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=61))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        result = build_level_change(
            finished_state=final_state,
            team_levels={0: 8, 1: 8},
        )
        self.assertIn("winner_team_id", result)


class TestMinimalLevelCardChangeClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_level_card(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_extreme_finished_state_for_level_card(self) -> GameState:
        # Non-winner players tie on remaining hand size; level-card outcome must remain deterministic.
        return _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="5", suit="S"), Card(rank="5", suit="H"))),
                _mk_player(1, (Card(rank="6", suit="S"), Card(rank="6", suit="H"))),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="7", suit="H"))),
            ),
        )

    def _expected_level_card(self, level: int) -> str:
        # Frozen minimal mapping for this stage: deterministic level label only.
        return f"L{level}"

    def test_44_finished_game_can_build_minimal_level_card_change_outcome(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        self.assertIsInstance(result, dict)

    def test_45_level_card_change_outcome_contains_required_fields(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        required = {
            "winner_team_id",
            "loser_team_id",
            "team_level_cards_before",
            "team_level_cards_after",
            "level_card_change_basis",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_46_level_card_change_is_consistent_with_promotion_demotion_levels(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_level_card()

        level_result = build_level_change(
            finished_state=finished,
            team_levels={0: 7, 1: 7},
        )
        card_result = build_change(
            finished_state=finished,
            team_levels={0: 7, 1: 7},
        )

        before_levels = level_result["team_levels_before"]
        after_levels = level_result["team_levels_after"]

        self.assertEqual(card_result["team_level_cards_before"][0], self._expected_level_card(before_levels[0]))
        self.assertEqual(card_result["team_level_cards_before"][1], self._expected_level_card(before_levels[1]))
        self.assertEqual(card_result["team_level_cards_after"][0], self._expected_level_card(after_levels[0]))
        self.assertEqual(card_result["team_level_cards_after"][1], self._expected_level_card(after_levels[1]))

    def test_47_level_card_change_outcome_is_deterministic(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_level_card()

        first = build_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )
        second = build_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )

        self.assertEqual(first, second)

    def test_48_extreme_tie_state_still_builds_stable_level_card_change(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_extreme_finished_state_for_level_card()

        first = build_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )
        second = build_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )

        self.assertEqual(first, second)

    def test_49_level_card_change_closure_does_not_break_minimal_match_handover(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 6, 1: 6},
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=509,
        )

        self.assertIn("winner_team_id", result)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_50_level_card_change_closure_does_not_break_single_game_mainline(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=71))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        result = build_change(
            finished_state=final_state,
            team_levels={0: 8, 1: 8},
        )
        self.assertIn("winner_team_id", result)


class TestRealLevelCardNominalMappingClosure(unittest.TestCase):
    def _require_callable(self, name: str):
        fn = getattr(game_module, name, None)
        self.assertTrue(callable(fn), f"expected callable in engine.game: {name}")
        return fn

    def _build_finished_state_for_real_level_card(self) -> GameState:
        return _mk_finished_state(
            winner_player_id=0,
            players=(
                _mk_player(0, ()),
                _mk_player(1, (Card(rank="A", suit="S"),)),
                _mk_player(2, (Card(rank="K", suit="S"), Card(rank="Q", suit="S"))),
                _mk_player(3, (Card(rank="10", suit="S"), Card(rank="9", suit="S"), Card(rank="8", suit="S"))),
            ),
        )

    def _build_extreme_finished_state_for_real_level_card(self) -> GameState:
        # Non-winner players tie on remaining hand size; nominal level-card mapping must remain stable.
        return _mk_finished_state(
            winner_player_id=2,
            players=(
                _mk_player(0, (Card(rank="5", suit="S"), Card(rank="5", suit="H"))),
                _mk_player(1, (Card(rank="6", suit="S"), Card(rank="6", suit="H"))),
                _mk_player(2, ()),
                _mk_player(3, (Card(rank="7", suit="S"), Card(rank="7", suit="H"))),
            ),
        )

    def _expected_nominal_level_card(self, level: int) -> str:
        # Frozen minimal mapping for this stage: level -> nominal card rank in a fixed 2..A cycle.
        order = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
        return order[(level - 2) % len(order)]

    def test_51_finished_game_can_build_real_nominal_level_card_change_outcome(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_real_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        self.assertIsInstance(result, dict)

    def test_52_real_nominal_level_card_change_contains_required_fields(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_real_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 5, 1: 5},
        )

        required = {
            "winner_team_id",
            "loser_team_id",
            "team_level_cards_before",
            "team_level_cards_after",
            "level_card_change_basis",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_53_real_nominal_level_cards_are_consistent_with_level_change(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        build_level_change = self._require_callable("build_minimal_promotion_demotion_outcome")
        finished = self._build_finished_state_for_real_level_card()

        level_result = build_level_change(
            finished_state=finished,
            team_levels={0: 7, 1: 7},
        )
        card_result = build_change(
            finished_state=finished,
            team_levels={0: 7, 1: 7},
        )

        before_levels = level_result["team_levels_before"]
        after_levels = level_result["team_levels_after"]

        self.assertEqual(
            card_result["team_level_cards_before"][0],
            self._expected_nominal_level_card(before_levels[0]),
        )
        self.assertEqual(
            card_result["team_level_cards_before"][1],
            self._expected_nominal_level_card(before_levels[1]),
        )
        self.assertEqual(
            card_result["team_level_cards_after"][0],
            self._expected_nominal_level_card(after_levels[0]),
        )
        self.assertEqual(
            card_result["team_level_cards_after"][1],
            self._expected_nominal_level_card(after_levels[1]),
        )
        self.assertEqual(
            card_result["level_card_change_basis"],
            "按当前最小项目口径，级别 N 按 2-10-J-Q-K-A 循环映射为级牌点数字符",
        )

    def test_54_real_nominal_level_card_change_outcome_is_deterministic(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_finished_state_for_real_level_card()

        first = build_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )
        second = build_change(
            finished_state=finished,
            team_levels={0: 3, 1: 9},
        )

        self.assertEqual(first, second)

    def test_55_extreme_tie_state_still_builds_stable_real_nominal_level_cards(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        finished = self._build_extreme_finished_state_for_real_level_card()

        first = build_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )
        second = build_change(
            finished_state=finished,
            team_levels={0: 4, 1: 4},
        )

        self.assertEqual(first, second)

    def test_56_real_nominal_level_card_closure_does_not_break_minimal_match_handover(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")
        advance_once = self._require_callable("advance_minimal_match_once")
        finished = self._build_finished_state_for_real_level_card()

        result = build_change(
            finished_state=finished,
            team_levels={0: 6, 1: 6},
        )
        handover, next_state = advance_once(
            finished_state=finished,
            game_index=1,
            games_played=0,
            seed=561,
        )

        self.assertIn("winner_team_id", result)
        self.assertEqual(handover["games_played_after"], 1)
        self.assertFalse(next_state.is_finished)

    def test_57_real_nominal_level_card_closure_does_not_break_single_game_mainline(self) -> None:
        build_change = self._require_callable("build_minimal_level_card_change_outcome")

        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=tuple(RuleBasedAIAgent(player_id=i, name=f"ai-{i}") for i in range(4)),
            debug_logger=DebugLogger(),
            max_steps=12000,
        )

        final_state = runner.run_one_game(build_initial_state(seed=571))
        self.assertTrue(final_state.is_finished)
        self.assertIsNotNone(final_state.winner_player_id)

        result = build_change(
            finished_state=final_state,
            team_levels={0: 8, 1: 8},
        )
        self.assertIn("winner_team_id", result)
