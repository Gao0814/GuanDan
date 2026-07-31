"""Tests for Step J-C2b1 hard rank candidates and minimal pass ordering."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_allocations import CardAllocationResult, PlayerAllocationBounds
from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_constraints import CardConstraintState, PlayerCardConstraints
from agents.card_ranker import _rank_strength, build_card_rankings
from agents.card_signals import PublicBehaviorEvent, PublicSignalState


def _event(
    action_index: int,
    player_id: int,
    event_type: str,
    *,
    pattern: str = "pass",
    rank: str | None = None,
    response: int | None = None,
    round_no: int | None = 1,
) -> PublicBehaviorEvent:
    ranks = () if rank is None else (rank,)
    return PublicBehaviorEvent(
        action_index=action_index,
        step_no=action_index + 1,
        round_no=round_no,
        player_id=player_id,
        relation="opponent",
        event_type=event_type,
        declared_pattern=pattern,
        declared_cards=ranks,
        carrier_cards=(),
        declared_ranks=ranks,
        carrier_ranks=(),
        declaration_differs_from_carrier=False,
        response_to_action_index=response,
    )


def _inputs(
    *,
    token_counts: dict[str, int] | None = None,
    domains: dict[str, tuple[int, ...]] | None = None,
    confirmed: dict[int, tuple[str, ...]] | None = None,
    remaining: dict[int, int] | None = None,
    token_pool_exact: bool = True,
    constraints_exact: bool = True,
    constraints_consistent: bool = True,
    phase: str = "endgame",
    signal_phase: str | None = None,
    level: str | None = "5",
    events: tuple[PublicBehaviorEvent, ...] = (),
    signal_diagnostics: tuple[str, ...] = (),
) -> tuple[CardBeliefState, CardConstraintState, PublicSignalState]:
    token_counts = {"3S": 1, "AH": 1} if token_counts is None else token_counts
    remaining = {2: 2, 3: 1} if remaining is None else remaining
    domains = (
        {token: (2,) for token in token_counts}
        if domains is None else domains
    )
    confirmed = {} if confirmed is None else confirmed
    players = (
        PlayerPublicBelief(1, "team_13", "self", 0, False, None, (), 0),
        PlayerPublicBelief(2, "team_24", "opponent", remaining.get(2, 0), False, None, (), 0),
        PlayerPublicBelief(3, "team_13", "teammate", remaining.get(3, 0), False, None, (), 0),
        PlayerPublicBelief(4, "team_24", "opponent", remaining.get(4, 0), True, 1, (), 0),
    )
    belief = CardBeliefState(
        phase=phase,
        external_unknown_count=sum(token_counts.values()),
        unseen_cards_by_token=MappingProxyType(dict(token_counts)),
        unseen_cards_by_rank=MappingProxyType({"3": sum(token_counts.values())}),
        players=players,
        diagnostics=(),
        token_pool_exact=token_pool_exact,
    )
    constraints = CardConstraintState(
        phase=phase,
        possible_owners_by_token=MappingProxyType(dict(domains)),
        possible_owners_by_rank=MappingProxyType({"3": (2,)}),
        players=tuple(
            PlayerCardConstraints(
                player_id=player.player_id,
                relation=player.relation,
                remaining_capacity=player.remaining_count,
                possible_tokens=tuple(domains),
                possible_ranks=("3",),
                confirmed_cards=confirmed.get(player.player_id, ()),
            )
            for player in players
        ),
        diagnostics=(),
        is_consistent=constraints_consistent,
        token_constraints_exact=constraints_exact,
    )
    signals = PublicSignalState(
        phase=phase if signal_phase is None else signal_phase,
        current_level_rank=level,
        events=events,
        players=(),
        diagnostics=signal_diagnostics,
    )
    return belief, constraints, signals


def _ranking(state, player_id: int = 2):
    return next(player for player in state.players if player.player_id == player_id)


def _candidate(state, rank: str, player_id: int = 2):
    return next(item for item in _ranking(state, player_id).candidates if item.rank == rank)


class CardRankerTests(unittest.TestCase):
    def test_j_b1_domains_aggregate_unique_ranks_per_player(self) -> None:
        belief, constraints, signals = _inputs(
            token_counts={"3S": 1, "3H": 1, "AH": 1},
            domains={"3S": (2, 3), "3H": (2,), "AH": (2,)},
            remaining={2: 3, 3: 1},
        )

        state = build_card_rankings(belief, constraints, None, signals)

        self.assertEqual([item.rank for item in _ranking(state, 2).candidates], ["3", "A"])
        self.assertEqual([item.rank for item in _ranking(state, 3).candidates], ["3"])

    def test_complete_allocation_uses_narrowed_domain_and_confirmed_cards(self) -> None:
        belief, constraints, signals = _inputs(
            token_counts={"3S": 1, "AH": 1},
            domains={"3S": (2, 3), "AH": (2, 3)},
        )
        allocation = CardAllocationResult(
            phase="endgame",
            status="complete",
            total_unseen_cards=2,
            feasible_assignment_count=1,
            search_nodes=1,
            search_complete=True,
            possible_owners_by_token=MappingProxyType({"3S": (2,), "AH": (3,)}),
            players=(
                PlayerAllocationBounds(2, 1, MappingProxyType({}), MappingProxyType({}), ("3S",)),
                PlayerAllocationBounds(3, 1, MappingProxyType({}), MappingProxyType({}), ("AH",)),
            ),
            diagnostics=(),
        )

        state = build_card_rankings(belief, constraints, allocation, signals)

        self.assertEqual(state.hard_source, "j_b2_allocation")
        self.assertEqual(_candidate(state, "3", 2).hard_status, "confirmed")
        self.assertEqual([item.rank for item in _ranking(state, 3).candidates], ["A"])

    def test_incomplete_or_mismatched_allocation_falls_back_or_returns_empty(self) -> None:
        belief, constraints, signals = _inputs()
        incomplete = CardAllocationResult(
            phase="endgame", status="truncated", total_unseen_cards=2,
            feasible_assignment_count=0, search_nodes=1, search_complete=False,
            possible_owners_by_token=MappingProxyType({}), players=(), diagnostics=(),
        )
        state = build_card_rankings(belief, constraints, incomplete, signals)
        self.assertEqual(state.hard_source, "j_b1_constraints")
        self.assertIn("allocation_not_complete", state.diagnostics)
        self.assertTrue(state.players)

        mismatched = replace(incomplete, phase="midgame")
        state = build_card_rankings(belief, constraints, mismatched, signals)
        self.assertEqual(state.players, ())
        self.assertIn("allocation_phase_mismatch", state.diagnostics)

    def test_self_finished_and_zero_capacity_players_are_not_ranked(self) -> None:
        belief, constraints, signals = _inputs(
            token_counts={"3S": 1},
            domains={"3S": (2,)},
            remaining={2: 1, 3: 0, 4: 1},
        )

        state = build_card_rankings(belief, constraints, None, signals)

        self.assertEqual([player.player_id for player in state.players], [2])

    def test_confirmed_rank_is_first_and_ignores_pass_penalty(self) -> None:
        events = (
            _event(0, 3, "lead", pattern="single", rank="3"),
            _event(1, 2, "pass", response=0),
        )
        belief, constraints, signals = _inputs(
            token_counts={"AH": 1, "5S": 1},
            domains={"AH": (2,), "5S": (2,)},
            confirmed={2: ("AH",)},
            events=events,
        )

        state = build_card_rankings(belief, constraints, None, signals)
        candidates = _ranking(state, 2).candidates

        self.assertEqual(candidates[0].rank, "A")
        self.assertEqual(candidates[0].soft_score, 0)
        self.assertEqual(candidates[0].evidence, ())
        self.assertEqual(_candidate(state, "5").soft_score, -1)

    def test_opponent_single_pass_penalizes_only_strictly_higher_possible_ranks(self) -> None:
        events = (
            _event(0, 3, "lead", pattern="single", rank="5"),
            _event(1, 2, "pass", response=0),
        )
        belief, constraints, signals = _inputs(
            token_counts={"3S": 1, "5H": 1, "2S": 1},
            domains={"3S": (2,), "5H": (2,), "2S": (2,)},
            remaining={2: 3, 3: 1},
            events=events,
            level="7",
        )

        state = build_card_rankings(belief, constraints, None, signals)

        self.assertEqual(_candidate(state, "3").soft_score, 0)
        self.assertEqual(_candidate(state, "5").soft_score, 0)
        two = _candidate(state, "2")
        self.assertEqual(two.soft_score, -1)
        self.assertEqual(two.evidence[0].code, "opponent_single_pass")
        self.assertEqual(two.evidence[0].response_action_index, 0)

    def test_teammate_and_invalid_single_links_do_not_penalize(self) -> None:
        teammate_events = (
            _event(0, 1, "lead", pattern="single", rank="3"),
            _event(1, 3, "pass", response=0),
        )
        belief, constraints, signals = _inputs(
            token_counts={"AS": 1}, domains={"AS": (3,)}, remaining={2: 0, 3: 1}, events=teammate_events
        )
        state = build_card_rankings(belief, constraints, None, signals)
        self.assertEqual(_candidate(state, "A", 3).soft_score, 0)

        invalid_events = (
            _event(0, 3, "lead", pattern="pair", rank="3"),
            _event(1, 2, "pass", response=0),
            _event(2, 2, "pass", response=None),
        )
        belief, constraints, signals = _inputs(token_counts={"AS": 1}, domains={"AS": (2,)}, events=invalid_events)
        state = build_card_rankings(belief, constraints, None, signals)
        self.assertEqual(_candidate(state, "A").soft_score, 0)
        self.assertIn("invalid_leading_single", state.diagnostics)
        self.assertIn("invalid_response_link", state.diagnostics)

    def test_pass_after_follow_uses_the_follow_response(self) -> None:
        events = (
            _event(0, 3, "lead", pattern="single", rank="3"),
            _event(1, 1, "follow", pattern="single", rank="5", response=0),
            _event(2, 2, "pass", response=1),
        )
        belief, constraints, signals = _inputs(
            token_counts={"AS": 1},
            domains={"AS": (2,)},
            events=events,
            level="7",
        )

        state = build_card_rankings(belief, constraints, None, signals)

        evidence = _candidate(state, "A").evidence
        self.assertEqual(evidence[0].response_action_index, 1)
        self.assertEqual(evidence[0].leading_rank, "5")

    def test_rank_strength_boundaries_and_level_rank(self) -> None:
        for index, rank in enumerate(("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"), start=3):
            self.assertEqual(_rank_strength(rank, "5"), 16 if rank == "5" else index)
        self.assertEqual(_rank_strength("2", "5"), 15)
        self.assertEqual(_rank_strength("5", "5"), 16)
        self.assertEqual(_rank_strength("SJ", "5"), 17)
        self.assertEqual(_rank_strength("BJ", "5"), 18)

    def test_penalties_accumulate_to_cap_without_zero_delta_evidence(self) -> None:
        events = (
            _event(0, 3, "lead", pattern="single", rank="3"),
            _event(1, 2, "pass", response=0),
            _event(2, 3, "lead", pattern="single", rank="3", round_no=2),
            _event(3, 2, "pass", response=2, round_no=2),
            _event(4, 3, "lead", pattern="single", rank="3", round_no=3),
            _event(5, 2, "pass", response=4, round_no=3),
        )
        belief, constraints, signals = _inputs(token_counts={"AS": 1}, domains={"AS": (2,)}, events=events)

        state = build_card_rankings(belief, constraints, None, signals, max_pass_single_penalty=2)
        candidate = _candidate(state, "A")

        self.assertEqual(candidate.soft_score, -2)
        self.assertEqual(len(candidate.evidence), 2)
        self.assertEqual([item.delta for item in candidate.evidence], [-1, -1])

    def test_score_tiers_preserve_same_score_groups_and_stable_rank_order(self) -> None:
        belief, constraints, signals = _inputs(
            token_counts={"4S": 1, "3S": 1, "AS": 1},
            domains={"4S": (2,), "3S": (2,), "AS": (2,)},
            remaining={2: 3, 3: 1},
        )
        state = build_card_rankings(belief, constraints, None, signals)
        candidates = _ranking(state).candidates

        self.assertEqual([item.rank for item in candidates], ["3", "4", "A"])
        self.assertEqual({item.score_tier for item in candidates}, {1})

    def test_invalid_parameters_and_invalid_hard_inputs_return_no_scoring(self) -> None:
        belief, constraints, signals = _inputs()
        for keyword, value in (("pass_single_penalty", 0), ("max_pass_single_penalty", True)):
            with self.subTest(keyword=keyword):
                with self.assertRaises(ValueError):
                    build_card_rankings(belief, constraints, None, signals, **{keyword: value})

        cases = (
            (_inputs(token_pool_exact=False), "token_pool_inexact"),
            (_inputs(constraints_exact=False), "constraints_inexact"),
            (_inputs(constraints_consistent=False), "constraints_inconsistent"),
            (_inputs(domains={"3S": (2,)}), "missing_token_domain"),
            (_inputs(domains={"3S": (), "AH": (2,)}), "empty_token_domain"),
            (_inputs(domains={"3S": (99,), "AH": (2,)}), "unknown_domain_owner"),
            (_inputs(token_counts={"XX": 1}, domains={"XX": (2,)}), "unknown_candidate_token"),
        )
        for (case_belief, case_constraints, case_signals), diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                state = build_card_rankings(case_belief, case_constraints, None, case_signals)
                self.assertEqual(state.players, ())
                self.assertIn(diagnostic, state.diagnostics)

    def test_phase_invalid_level_unknown_team_and_signal_diagnostics_are_safe(self) -> None:
        belief, constraints, signals = _inputs(signal_phase="midgame")
        state = build_card_rankings(belief, constraints, None, signals)
        self.assertEqual(state.players, ())
        self.assertIn("phase_mismatch", state.diagnostics)

        events = (_event(0, 3, "lead", pattern="single", rank="3"), _event(1, 2, "pass", response=0))
        belief, constraints, signals = _inputs(token_counts={"AS": 1}, domains={"AS": (2,)}, events=events, level=None, signal_diagnostics=("orphan_pass",))
        state = build_card_rankings(belief, constraints, None, signals)
        self.assertTrue(state.players)
        self.assertEqual(_candidate(state, "A").soft_score, 0)
        self.assertIn("invalid_level_rank", state.diagnostics)
        self.assertIn("signal_diagnostics_present", state.diagnostics)

        altered_players = tuple(
            replace(player, team="") if player.player_id == 3 else player
            for player in belief.players
        )
        belief = replace(belief, players=altered_players)
        signals = replace(signals, current_level_rank="5", diagnostics=())
        state = build_card_rankings(belief, constraints, None, signals)
        self.assertIn("unknown_player_team", state.diagnostics)

    def test_output_is_serializable_immutable_and_does_not_modify_inputs(self) -> None:
        belief, constraints, signals = _inputs()
        before_belief = belief.to_dict()
        before_constraints = constraints.to_dict()
        before_signals = signals.to_dict()
        state = build_card_rankings(belief, constraints, None, signals)
        serialized = json.dumps(state.to_dict())

        for forbidden in ("probability", "confidence", "likelihood", "ground_truth"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(FrozenInstanceError):
            state.phase = "opening"  # type: ignore[misc]
        self.assertEqual(belief.to_dict(), before_belief)
        self.assertEqual(constraints.to_dict(), before_constraints)
        self.assertEqual(signals.to_dict(), before_signals)

    def test_fixed_input_is_deterministic(self) -> None:
        belief, constraints, signals = _inputs()

        self.assertEqual(
            build_card_rankings(belief, constraints, None, signals),
            build_card_rankings(belief, constraints, None, signals),
        )


if __name__ == "__main__":
    unittest.main()
