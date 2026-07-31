"""Tests for Step J-B2 controlled exact allocation enumeration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_allocations import PlayerAllocationBounds, enumerate_card_allocations
from agents.card_belief import (
    CardBeliefState,
    JOKER_RANKS,
    NORMAL_RANKS,
    SUITS,
    PlayerPublicBelief,
)
from agents.card_constraints import CardConstraintState, PlayerCardConstraints


def _rank_counts(token_counts: dict[str, int]) -> dict[str, int]:
    """Build the exact public rank pool for valid physical token fixtures."""

    result: dict[str, int] = {}
    for token, count in token_counts.items():
        if token in JOKER_RANKS:
            rank = token
        elif len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
            rank = token[:-1]
        else:
            continue
        result[rank] = result.get(rank, 0) + count
    return result


def _inputs(
    *,
    token_counts: dict[str, int] | None = None,
    capacities: dict[int, int] | None = None,
    domains: dict[str, tuple[int, ...]] | None = None,
    token_pool_exact: bool = True,
    constraints_exact: bool = True,
    constraints_consistent: bool = True,
    belief_phase: str = "endgame",
    constraints_phase: str = "endgame",
    external_unknown_count: int | None = None,
    rank_counts: dict[str, int] | None = None,
) -> tuple[CardBeliefState, CardConstraintState]:
    token_counts = {"3S": 1, "4H": 1} if token_counts is None else token_counts
    capacities = {2: 1, 3: 1} if capacities is None else capacities
    domains = (
        {token: tuple(capacities) for token in token_counts}
        if domains is None else domains
    )
    rank_counts = _rank_counts(token_counts) if rank_counts is None else rank_counts
    total = sum(token_counts.values())
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
    constraint_players = tuple(
        PlayerCardConstraints(
            player_id=player.player_id,
            relation=player.relation,
            remaining_capacity=player.remaining_count,
            possible_tokens=tuple(domains),
            possible_ranks=tuple(rank_counts),
            confirmed_cards=(),
        )
        for player in public_players
    )
    belief = CardBeliefState(
        phase=belief_phase,
        external_unknown_count=(
            total if external_unknown_count is None else external_unknown_count
        ),
        unseen_cards_by_token=MappingProxyType(dict(token_counts)),
        unseen_cards_by_rank=MappingProxyType(dict(rank_counts)),
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
        players=constraint_players,
        diagnostics=(),
        is_consistent=constraints_consistent,
        token_constraints_exact=constraints_exact,
    )
    return belief, constraints


def _bounds(result, player_id: int):
    return next(player for player in result.players if player.player_id == player_id)


class CardAllocationTests(unittest.TestCase):
    def test_single_player_has_unique_complete_allocation(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2, "BJ": 1},
            capacities={2: 3},
            domains={"3S": (2,), "BJ": (2,)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "complete")
        self.assertTrue(result.search_complete)
        self.assertEqual(result.feasible_assignment_count, 1)
        self.assertEqual(result.physical_assignment_count, 1)
        self.assertEqual(_bounds(result, 2).confirmed_cards, ("3S", "3S", "BJ"))

    def test_two_player_multiple_solutions_do_not_confirm(self) -> None:
        belief, constraints = _inputs()

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.feasible_assignment_count, 2)
        self.assertEqual(result.physical_assignment_count, 2)
        self.assertEqual(_bounds(result, 2).confirmed_cards, ())
        self.assertEqual(_bounds(result, 3).confirmed_cards, ())

    def test_differentiated_domains_and_capacity_propagate_unique_solution(self) -> None:
        belief, constraints = _inputs(domains={"3S": (2, 3), "4H": (2,)})

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.feasible_assignment_count, 1)
        self.assertEqual(result.physical_assignment_count, 1)
        self.assertEqual(_bounds(result, 2).confirmed_cards, ("4H",))
        self.assertEqual(_bounds(result, 3).confirmed_cards, ("3S",))

    def test_asymmetric_counts_aggregate_exact_physical_weight_and_marginals(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2, "4H": 1},
            capacities={2: 2, 3: 1},
            domains={"3S": (2, 3), "4H": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)
        player_two = _bounds(result, 2)
        player_three = _bounds(result, 3)

        self.assertEqual(result.feasible_assignment_count, 2)
        self.assertEqual(result.physical_assignment_count, 3)
        self.assertEqual(player_two.holding_assignment_count_by_token, {"3S": 3, "4H": 2})
        self.assertEqual(player_two.copy_assignment_count_by_token, {"3S": 4, "4H": 2})
        self.assertEqual(player_three.holding_assignment_count_by_token, {"3S": 2, "4H": 1})
        self.assertEqual(player_three.copy_assignment_count_by_token, {"3S": 2, "4H": 1})
        self.assertEqual(player_two.holding_assignment_count_by_rank, {"3": 3, "4": 2})
        self.assertEqual(player_two.copy_assignment_count_by_rank, {"3": 4, "4": 2})
        self.assertEqual(player_three.holding_assignment_count_by_rank, {"3": 2, "4": 1})
        self.assertEqual(player_three.copy_assignment_count_by_rank, {"3": 2, "4": 1})

    def test_token_to_rank_mapping_handles_ten_and_jokers(self) -> None:
        belief, constraints = _inputs(
            token_counts={"10S": 1, "SJ": 1, "BJ": 1},
            capacities={2: 3},
            domains={"10S": (2,), "SJ": (2,), "BJ": (2,)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "complete")
        self.assertEqual(
            _bounds(result, 2).copy_assignment_count_by_rank,
            {"10": 1, "SJ": 1, "BJ": 1},
        )

    def test_invalid_token_rank_fails_closed_before_search(self) -> None:
        belief, constraints = _inputs(
            token_counts={"invalid": 1},
            capacities={2: 1},
            domains={"invalid": (2,)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "invalid_input")
        self.assertEqual(result.search_nodes, 0)
        self.assertIn("invalid_token_rank:invalid", result.diagnostics)
        self.assertEqual(result.physical_assignment_count, 0)
        self.assertEqual(result.players, ())

    def test_rank_pool_mismatch_fails_closed_before_search(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1, "3H": 1},
            capacities={2: 2},
            domains={"3S": (2,), "3H": (2,)},
            rank_counts={"3": 1, "4": 1},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "invalid_input")
        self.assertEqual(result.search_nodes, 0)
        self.assertIn("rank_pool_mismatch:3", result.diagnostics)
        self.assertIn("rank_pool_mismatch:4", result.diagnostics)

    def test_single_token_rank_marginals_match_token_marginals(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 1, 3: 1},
            domains={"3S": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)

        for player in result.players:
            self.assertEqual(
                player.holding_assignment_count_by_rank["3"],
                player.holding_assignment_count_by_token["3S"],
            )
            self.assertEqual(
                player.copy_assignment_count_by_rank["3"],
                player.copy_assignment_count_by_token["3S"],
            )

    def test_same_rank_tokens_use_union_for_holding_marginal(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1, "3H": 1, "4C": 1},
            capacities={2: 2, 3: 1},
            domains={"3S": (2, 3), "3H": (2, 3), "4C": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)
        player_two = _bounds(result, 2)

        self.assertEqual(result.feasible_assignment_count, 3)
        self.assertEqual(result.physical_assignment_count, 3)
        self.assertEqual(player_two.holding_assignment_count_by_rank["3"], 3)
        self.assertEqual(player_two.copy_assignment_count_by_rank["3"], 4)
        self.assertEqual(
            player_two.holding_assignment_count_by_token["3S"]
            + player_two.holding_assignment_count_by_token["3H"],
            4,
        )
        self.assertLess(
            player_two.holding_assignment_count_by_rank["3"],
            player_two.holding_assignment_count_by_token["3S"]
            + player_two.holding_assignment_count_by_token["3H"],
        )

    def test_rank_copy_marginals_obey_cross_player_conservation(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1, "3H": 1, "4C": 1},
            capacities={2: 2, 3: 1},
        )
        result = enumerate_card_allocations(belief, constraints)

        for rank, count in belief.unseen_cards_by_rank.items():
            self.assertEqual(
                sum(player.copy_assignment_count_by_rank[rank] for player in result.players),
                count * result.physical_assignment_count,
            )

    def test_multi_token_matrix_weights_multiply(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2, "4H": 2},
            capacities={2: 2, 3: 2},
            domains={"3S": (2, 3), "4H": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.feasible_assignment_count, 3)
        self.assertEqual(result.physical_assignment_count, 6)

    def test_identical_token_copies_are_counted_as_one_split(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 1, 3: 1},
            domains={"3S": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.feasible_assignment_count, 1)
        self.assertEqual(result.physical_assignment_count, 2)

    def test_split_identical_copies_confirm_one_for_each_player(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 1, 3: 1},
            domains={"3S": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(_bounds(result, 2).confirmed_cards, ("3S",))
        self.assertEqual(_bounds(result, 3).confirmed_cards, ("3S",))

    def test_complete_search_reports_min_and_max_counts(self) -> None:
        belief, constraints = _inputs()

        result = enumerate_card_allocations(belief, constraints)

        player_two = _bounds(result, 2)
        self.assertEqual(player_two.min_count_by_token["3S"], 0)
        self.assertEqual(player_two.max_count_by_token["3S"], 1)
        self.assertEqual(player_two.min_count_by_token["4H"], 0)
        self.assertEqual(player_two.max_count_by_token["4H"], 1)

    def test_complete_search_removes_owners_absent_from_all_solutions(self) -> None:
        belief, constraints = _inputs(domains={"3S": (2, 3), "4H": (2,)})

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.possible_owners_by_token["3S"], (3,))
        self.assertEqual(result.possible_owners_by_token["4H"], (2,))

    def test_physical_marginals_obey_conservation_and_bounds(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2, "4H": 1},
            capacities={2: 2, 3: 1},
        )
        result = enumerate_card_allocations(belief, constraints)

        for token, count in belief.unseen_cards_by_token.items():
            if not count:
                continue
            copies = sum(
                player.copy_assignment_count_by_token[token]
                for player in result.players
            )
            self.assertEqual(copies, count * result.physical_assignment_count)
        for player in result.players:
            for token, minimum in player.min_count_by_token.items():
                holding = player.holding_assignment_count_by_token[token]
                copies = player.copy_assignment_count_by_token[token]
                maximum = player.max_count_by_token[token]
                self.assertLessEqual(holding, result.physical_assignment_count)
                self.assertLessEqual(
                    copies,
                    belief.unseen_cards_by_token[token] * result.physical_assignment_count,
                )
                if minimum > 0:
                    self.assertEqual(holding, result.physical_assignment_count)
                if maximum == 0:
                    self.assertEqual(holding, 0)
                    self.assertEqual(copies, 0)

    def test_zero_count_tokens_do_not_appear_in_marginals(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1, "4H": 0},
            capacities={2: 1},
            domains={"3S": (2,), "4H": (2,)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.physical_assignment_count, 1)
        self.assertEqual(_bounds(result, 2).copy_assignment_count_by_token, {"3S": 1})

    def test_no_feasible_allocation_is_diagnosed_without_confirmation(self) -> None:
        belief, constraints = _inputs(domains={"3S": (2,), "4H": (2,)})

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "no_feasible_allocation")
        self.assertIn("no_feasible_allocation", result.diagnostics)
        self.assertTrue(all(not player.confirmed_cards for player in result.players))
        self.assertEqual(result.physical_assignment_count, 0)
        self.assertTrue(all(not player.holding_assignment_count_by_token for player in result.players))
        self.assertTrue(all(not player.copy_assignment_count_by_token for player in result.players))
        self.assertTrue(all(not player.copy_assignment_count_by_rank for player in result.players))

    def test_inexact_belief_or_constraints_do_not_start_search(self) -> None:
        belief, constraints = _inputs(token_pool_exact=False)
        result = enumerate_card_allocations(belief, constraints)
        self.assertEqual(result.status, "invalid_input")
        self.assertIn("token_pool_inexact", result.diagnostics)
        self.assertEqual(result.search_nodes, 0)
        self.assertEqual(result.physical_assignment_count, 0)

        belief, constraints = _inputs(constraints_exact=False, constraints_consistent=False)
        result = enumerate_card_allocations(belief, constraints)
        self.assertEqual(result.status, "invalid_input")
        self.assertIn("constraints_inexact", result.diagnostics)
        self.assertIn("constraints_inconsistent", result.diagnostics)

    def test_phase_and_total_count_mismatches_do_not_start_search(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 1},
            domains={"3S": (2,)},
            belief_phase="endgame",
            constraints_phase="midgame",
            external_unknown_count=1,
            rank_counts={"3": 1},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "invalid_input")
        self.assertIn("phase_mismatch", result.diagnostics)
        self.assertIn("external_count_mismatch", result.diagnostics)
        self.assertIn("capacity_mismatch", result.diagnostics)

    def test_missing_empty_and_unknown_token_domains_do_not_start_search(self) -> None:
        cases = (
            ({"4H": (2,)}, "missing_token_domain:3S"),
            ({"3S": (), "4H": (2,)}, "empty_token_domain:3S"),
            ({"3S": (99,), "4H": (2,)}, "unknown_domain_owner:3S:99"),
        )
        for domains, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                belief, constraints = _inputs(domains=domains)
                result = enumerate_card_allocations(belief, constraints)
                self.assertEqual(result.status, "invalid_input")
                self.assertIn(diagnostic, result.diagnostics)
                self.assertEqual(result.search_nodes, 0)

    def test_more_than_twelve_cards_is_skipped(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 13},
            capacities={2: 13},
            domains={"3S": (2,)},
        )

        result = enumerate_card_allocations(belief, constraints)

        self.assertEqual(result.status, "skipped_too_many_cards")
        self.assertIn("too_many_external_cards", result.diagnostics)
        self.assertEqual(result.search_nodes, 0)
        self.assertEqual(result.physical_assignment_count, 0)

    def test_node_limit_truncation_preserves_domains_and_confirms_nothing(self) -> None:
        belief, constraints = _inputs()

        result = enumerate_card_allocations(belief, constraints, max_search_nodes=1)

        self.assertEqual(result.status, "truncated")
        self.assertFalse(result.search_complete)
        self.assertIn("search_node_limit_reached", result.diagnostics)
        self.assertEqual(result.possible_owners_by_token, constraints.possible_owners_by_token)
        self.assertTrue(all(not player.confirmed_cards for player in result.players))
        self.assertEqual(result.physical_assignment_count, 0)
        self.assertTrue(all(not player.copy_assignment_count_by_token for player in result.players))
        self.assertTrue(all(not player.holding_assignment_count_by_rank for player in result.players))

    def test_solution_limit_truncation_preserves_domains_and_confirms_nothing(self) -> None:
        belief, constraints = _inputs()

        result = enumerate_card_allocations(belief, constraints, max_solutions=1)

        self.assertEqual(result.status, "truncated")
        self.assertEqual(result.feasible_assignment_count, 1)
        self.assertIn("solution_limit_reached", result.diagnostics)
        self.assertEqual(result.possible_owners_by_token, constraints.possible_owners_by_token)
        self.assertTrue(all(not player.confirmed_cards for player in result.players))
        self.assertEqual(result.physical_assignment_count, 0)
        self.assertTrue(all(not player.holding_assignment_count_by_token for player in result.players))
        self.assertTrue(all(not player.copy_assignment_count_by_rank for player in result.players))

    def test_solution_limit_remains_a_count_matrix_limit_not_physical_weight_limit(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 2},
            capacities={2: 1, 3: 1},
            domains={"3S": (2, 3)},
        )

        result = enumerate_card_allocations(belief, constraints, max_solutions=1)

        self.assertEqual(result.feasible_assignment_count, 1)
        self.assertEqual(result.status, "truncated")
        self.assertEqual(result.physical_assignment_count, 0)

    def test_fixed_input_is_deterministic(self) -> None:
        belief, constraints = _inputs()

        first = enumerate_card_allocations(belief, constraints).to_dict()
        second = enumerate_card_allocations(belief, constraints).to_dict()

        self.assertEqual(first, second)

    def test_to_dict_output_is_json_serializable(self) -> None:
        belief, constraints = _inputs()

        self.assertIsInstance(json.dumps(enumerate_card_allocations(belief, constraints).to_dict()), str)

    def test_output_is_immutable_and_inputs_are_not_modified(self) -> None:
        belief, constraints = _inputs()
        before_belief = belief.to_dict()
        before_constraints = constraints.to_dict()
        result = enumerate_card_allocations(belief, constraints)

        with self.assertRaises(FrozenInstanceError):
            result.status = "invalid_input"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            result.possible_owners_by_token["3S"] = ()  # type: ignore[index]
        with self.assertRaises(TypeError):
            _bounds(result, 2).copy_assignment_count_by_token["3S"] = 0  # type: ignore[index]
        with self.assertRaises(TypeError):
            _bounds(result, 2).copy_assignment_count_by_rank["3"] = 0  # type: ignore[index]
        self.assertEqual(belief.to_dict(), before_belief)
        self.assertEqual(constraints.to_dict(), before_constraints)

    def test_new_statistics_are_integer_json_safe_and_do_not_expose_probabilities(self) -> None:
        belief, constraints = _inputs(token_counts={"3S": 2}, capacities={2: 1, 3: 1})
        payload = enumerate_card_allocations(belief, constraints).to_dict()
        serialized = json.dumps(payload)

        self.assertIsInstance(payload["physical_assignment_count"], int)
        self.assertNotIn("probability", serialized)
        self.assertNotIn("confidence", serialized)
        self.assertNotIn("ground_truth", serialized)

    def test_legacy_player_bounds_construction_keeps_new_rank_defaults(self) -> None:
        bounds = PlayerAllocationBounds(
            player_id=2,
            remaining_capacity=1,
            min_count_by_token=MappingProxyType({"3S": 1}),
            max_count_by_token=MappingProxyType({"3S": 1}),
            confirmed_cards=("3S",),
        )

        self.assertEqual(bounds.holding_assignment_count_by_rank, {})
        self.assertEqual(bounds.copy_assignment_count_by_rank, {})

    def test_invalid_limits_raise_value_error(self) -> None:
        belief, constraints = _inputs()

        for keyword, value in (("max_external_cards", 0), ("max_search_nodes", True), ("max_solutions", -1)):
            with self.subTest(keyword=keyword):
                with self.assertRaises(ValueError):
                    enumerate_card_allocations(belief, constraints, **{keyword: value})


if __name__ == "__main__":
    unittest.main()
