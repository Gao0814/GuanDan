"""Offline-only truth-metric tests for Step J-C1."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_allocations import PlayerAllocationBounds, enumerate_card_allocations
from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_constraints import CardConstraintState, PlayerCardConstraints
from evaluation.belief_metrics import evaluate_belief_state


def _inputs(
    *,
    token_counts: dict[str, int] | None = None,
    capacities: dict[int, int] | None = None,
    domains: dict[str, tuple[int, ...]] | None = None,
    confirmed: dict[int, tuple[str, ...]] | None = None,
    token_pool_exact: bool = True,
    constraints_exact: bool = True,
    constraints_consistent: bool = True,
    belief_phase: str = "endgame",
    constraints_phase: str = "endgame",
) -> tuple[CardBeliefState, CardConstraintState]:
    token_counts = {"3S": 1, "4H": 1} if token_counts is None else token_counts
    capacities = {2: 1, 3: 1} if capacities is None else capacities
    domains = (
        {token: tuple(capacities) for token in token_counts}
        if domains is None else domains
    )
    confirmed = {} if confirmed is None else confirmed
    rank_counts = {f"rank_{index}": count for index, count in enumerate(token_counts.values())}
    public_players = (
        PlayerPublicBelief(
            player_id=1,
            team="1&3",
            relation="self",
            remaining_count=0,
            finished=False,
            finish_rank=None,
            played_cards=(),
            pass_count=0,
        ),
        *(
            PlayerPublicBelief(
                player_id=player_id,
                team="2&4",
                relation="opponent",
                remaining_count=capacity,
                finished=False,
                finish_rank=None,
                played_cards=(),
                pass_count=0,
            )
            for player_id, capacity in capacities.items()
        ),
    )
    belief = CardBeliefState(
        phase=belief_phase,
        external_unknown_count=sum(token_counts.values()),
        unseen_cards_by_token=MappingProxyType(dict(token_counts)),
        unseen_cards_by_rank=MappingProxyType(rank_counts),
        players=public_players,
        diagnostics=(),
        token_pool_exact=token_pool_exact,
    )
    constraints = CardConstraintState(
        phase=constraints_phase,
        possible_owners_by_token=MappingProxyType(dict(domains)),
        possible_owners_by_rank=MappingProxyType({
            rank: tuple(capacities) for rank in rank_counts
        }),
        players=tuple(
            PlayerCardConstraints(
                player_id=player.player_id,
                relation=player.relation,
                remaining_capacity=player.remaining_count,
                possible_tokens=tuple(domains),
                possible_ranks=tuple(rank_counts),
                confirmed_cards=confirmed.get(player.player_id, ()),
            )
            for player in public_players
        ),
        diagnostics=(),
        is_consistent=constraints_consistent,
        token_constraints_exact=constraints_exact,
    )
    return belief, constraints


class BeliefMetricsTests(unittest.TestCase):
    def test_perfect_domain_and_duplicate_coverage(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 2},
            domains={"3S": (2,)},
        )

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S", "3S"]})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.domain_covered_count, 2)
        self.assertEqual(report.domain_missed_count, 0)
        self.assertEqual(report.domain_recall, 1.0)

    def test_domain_miss_counts_real_owner_card(self) -> None:
        belief, constraints = _inputs(domains={"3S": (3,), "4H": (2, 3)})

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})

        self.assertEqual(report.domain_covered_count, 1)
        self.assertEqual(report.domain_missed_count, 1)
        self.assertEqual(report.domain_recall, 0.5)

    def test_correct_and_excess_confirmed_copies(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1},
            capacities={2: 1},
            domains={"3S": (2,)},
            confirmed={2: ("3S", "3S")},
        )

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"]})

        self.assertEqual(report.confirmed_count, 2)
        self.assertEqual(report.confirmed_correct_count, 1)
        self.assertEqual(report.false_confirmed_count, 1)
        self.assertEqual(report.confirmed_precision, 0.5)
        self.assertEqual(report.confirmed_coverage, 1.0)

    def test_no_confirmed_cards_have_neutral_precision_and_zero_coverage(self) -> None:
        belief, constraints = _inputs()

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})

        self.assertEqual(report.confirmed_count, 0)
        self.assertEqual(report.confirmed_precision, 1.0)
        self.assertEqual(report.confirmed_coverage, 0.0)

    def test_complete_allocation_scores_bounds_and_domain_reduction(self) -> None:
        belief, constraints = _inputs(domains={"3S": (2, 3), "4H": (2,)})
        allocation = enumerate_card_allocations(belief, constraints)

        report = evaluate_belief_state(
            belief,
            constraints,
            allocation,
            {2: ["4H"], 3: ["3S"]},
        )

        self.assertEqual(report.prediction_source, "j_b2_allocation")
        self.assertEqual(report.bound_check_count, 4)
        self.assertEqual(report.bound_violation_count, 0)
        self.assertEqual(report.bounds_valid_rate, 1.0)
        self.assertEqual(report.j_b1_owner_edge_count, 3)
        self.assertEqual(report.final_owner_edge_count, 2)
        self.assertEqual(report.owner_edge_reduction_count, 1)

    def test_complete_allocation_detects_bound_violation(self) -> None:
        belief, constraints = _inputs()
        allocation = enumerate_card_allocations(belief, constraints)
        player_two = next(player for player in allocation.players if player.player_id == 2)
        altered_player_two = PlayerAllocationBounds(
            player_id=2,
            remaining_capacity=1,
            min_count_by_token=MappingProxyType({"3S": 1, "4H": 0}),
            max_count_by_token=player_two.max_count_by_token,
            confirmed_cards=(),
        )
        allocation = replace(
            allocation,
            players=tuple(
                altered_player_two if player.player_id == 2 else player
                for player in allocation.players
            ),
        )

        report = evaluate_belief_state(
            belief,
            constraints,
            allocation,
            {2: ["4H"], 3: ["3S"]},
        )

        self.assertGreaterEqual(report.bound_violation_count, 1)
        self.assertLess(report.bounds_valid_rate, 1.0)

    def test_truncated_allocation_falls_back_without_bounds(self) -> None:
        belief, constraints = _inputs()
        allocation = enumerate_card_allocations(belief, constraints, max_search_nodes=1)

        report = evaluate_belief_state(
            belief,
            constraints,
            allocation,
            {2: ["3S"], 3: ["4H"]},
        )

        self.assertTrue(report.valid_input)
        self.assertEqual(report.prediction_source, "j_b1_constraints")
        self.assertIn("allocation_not_complete", report.diagnostics)
        self.assertEqual(report.bound_check_count, 0)
        self.assertEqual(report.j_b1_owner_edge_count, report.final_owner_edge_count)

    def test_all_noncomplete_allocation_statuses_fall_back_to_j_b1(self) -> None:
        belief, constraints = _inputs()
        complete = enumerate_card_allocations(belief, constraints)
        no_solution_belief, no_solution_constraints = _inputs(
            domains={"3S": (2,), "4H": (2,)}
        )
        no_solution = enumerate_card_allocations(no_solution_belief, no_solution_constraints)
        cases = (
            (replace(complete, status="invalid_input", search_complete=False), belief, constraints),
            (replace(complete, status="skipped_too_many_cards", search_complete=False), belief, constraints),
            (no_solution, no_solution_belief, no_solution_constraints),
        )
        for allocation, case_belief, case_constraints in cases:
            with self.subTest(status=allocation.status):
                report = evaluate_belief_state(
                    case_belief,
                    case_constraints,
                    allocation,
                    {2: ["3S"], 3: ["4H"]},
                )
                self.assertTrue(report.valid_input)
                self.assertEqual(report.prediction_source, "j_b1_constraints")
                self.assertIn("allocation_not_complete", report.diagnostics)
                self.assertEqual(report.bound_check_count, 0)

    def test_none_allocation_uses_j_b1_only(self) -> None:
        belief, constraints = _inputs()

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.prediction_source, "j_b1_constraints")
        self.assertEqual(report.bound_check_count, 0)

    def test_missing_unexpected_and_bad_truth_counts_are_invalid(self) -> None:
        belief, constraints = _inputs()
        cases = (
            ({2: ["3S"]}, "missing_truth_player:3"),
            ({1: [], 2: ["3S"], 3: ["4H"]}, "unexpected_truth_player:1"),
            ({2: ["3S"], 3: ["4H"], 99: []}, "unexpected_truth_player:99"),
            ({2: ["3S", "4H"], 3: ["4H"]}, "truth_hand_count_mismatch:2"),
        )
        for truth, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                report = evaluate_belief_state(belief, constraints, None, truth)
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)
                self.assertEqual(report.truth_card_count, 0)
                self.assertEqual(report.domain_recall, 0.0)

    def test_truth_pool_mismatch_and_invalid_token_are_invalid(self) -> None:
        belief, constraints = _inputs()

        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["XX"]})
        self.assertFalse(report.valid_input)
        self.assertIn("truth_pool_mismatch", report.diagnostics)

        report = evaluate_belief_state(belief, constraints, None, {2: [""], 3: ["4H"]})
        self.assertFalse(report.valid_input)
        self.assertIn("invalid_truth_token:2", report.diagnostics)

    def test_inexact_inconsistent_and_phase_mismatch_inputs_are_invalid(self) -> None:
        belief, constraints = _inputs(token_pool_exact=False)
        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})
        self.assertIn("token_pool_inexact", report.diagnostics)
        self.assertFalse(report.valid_input)

        belief, constraints = _inputs(constraints_exact=False, constraints_consistent=False)
        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})
        self.assertIn("constraints_inexact", report.diagnostics)
        self.assertIn("constraints_inconsistent", report.diagnostics)

        belief, constraints = _inputs(constraints_phase="midgame")
        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})
        self.assertIn("phase_mismatch", report.diagnostics)

    def test_missing_domain_and_allocation_phase_mismatch_are_invalid(self) -> None:
        belief, constraints = _inputs(domains={"3S": (2, 3)})
        report = evaluate_belief_state(belief, constraints, None, {2: ["3S"], 3: ["4H"]})
        self.assertFalse(report.valid_input)
        self.assertIn("missing_constraint_domain:4H", report.diagnostics)

        belief, constraints = _inputs()
        allocation = replace(enumerate_card_allocations(belief, constraints), phase="midgame")
        report = evaluate_belief_state(belief, constraints, allocation, {2: ["3S"], 3: ["4H"]})
        self.assertFalse(report.valid_input)
        self.assertIn("allocation_phase_mismatch", report.diagnostics)

    def test_zero_truth_has_stable_zero_denominator_metrics(self) -> None:
        belief, constraints = _inputs(token_counts={}, capacities={}, domains={})

        report = evaluate_belief_state(belief, constraints, None, {})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.truth_card_count, 0)
        self.assertEqual(report.domain_recall, 1.0)
        self.assertEqual(report.confirmed_precision, 1.0)
        self.assertEqual(report.confirmed_coverage, 1.0)
        self.assertEqual(report.bounds_valid_rate, 1.0)
        self.assertEqual(report.owner_edge_reduction_rate, 0.0)

    def test_to_dict_is_serializable_and_never_contains_truth_hands(self) -> None:
        belief, constraints = _inputs()

        serialized = json.dumps(
            evaluate_belief_state(
                belief,
                constraints,
                None,
                {2: ["3S"], 3: ["4H"]},
            ).to_dict()
        )

        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("3S", serialized)
        self.assertNotIn("4H", serialized)

    def test_output_is_immutable_and_inputs_are_not_modified(self) -> None:
        belief, constraints = _inputs()
        allocation = enumerate_card_allocations(belief, constraints)
        before_belief = belief.to_dict()
        before_constraints = constraints.to_dict()
        before_allocation = allocation.to_dict()

        report = evaluate_belief_state(
            belief,
            constraints,
            allocation,
            {2: ["3S"], 3: ["4H"]},
        )

        with self.assertRaises(FrozenInstanceError):
            report.valid_input = False  # type: ignore[misc]
        self.assertEqual(belief.to_dict(), before_belief)
        self.assertEqual(constraints.to_dict(), before_constraints)
        self.assertEqual(allocation.to_dict(), before_allocation)

    def test_repeated_evaluation_is_deterministic(self) -> None:
        belief, constraints = _inputs()
        truth = {2: ["3S"], 3: ["4H"]}

        first = evaluate_belief_state(belief, constraints, None, truth)
        second = evaluate_belief_state(belief, constraints, None, truth)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
