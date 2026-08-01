"""Tests for the fail-closed runtime exact-marginal confidence contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from agents.card_allocations import enumerate_card_allocations
from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_confidence import build_card_confidence
from agents.card_constraints import CardConstraintState, PlayerCardConstraints


def _inputs(
    *,
    token_counts: dict[str, int] | None = None,
    capacities: dict[int, int] | None = None,
    phase: str = "critical_endgame",
) -> tuple[CardBeliefState, CardConstraintState]:
    token_counts = {"3S": 1, "3H": 1, "4C": 1} if token_counts is None else token_counts
    capacities = {2: 2, 3: 1} if capacities is None else capacities
    rank_counts: dict[str, int] = {}
    for token, count in token_counts.items():
        rank = token if token in {"SJ", "BJ"} else token[:-1]
        rank_counts[rank] = rank_counts.get(rank, 0) + count
    players = (
        PlayerPublicBelief(1, "1&3", "self", 0, False, None, (), 0),
        *(PlayerPublicBelief(player_id, "2&4", "opponent", capacity, False, None, (), 0) for player_id, capacity in capacities.items()),
    )
    constraints_players = tuple(
        PlayerCardConstraints(
            player.player_id, player.relation, player.remaining_count,
            tuple(token_counts), tuple(rank_counts), (),
        )
        for player in players
    )
    belief = CardBeliefState(
        phase, sum(token_counts.values()), MappingProxyType(dict(token_counts)),
        MappingProxyType(rank_counts), players, (), True,
    )
    constraints = CardConstraintState(
        phase, MappingProxyType({token: tuple(capacities) for token in token_counts}),
        MappingProxyType({rank: tuple(capacities) for rank in rank_counts}),
        constraints_players, (), True, True,
    )
    return belief, constraints


def _complete() -> tuple[CardBeliefState, CardConstraintState, object]:
    belief, constraints = _inputs()
    return belief, constraints, enumerate_card_allocations(belief, constraints)


class CardConfidenceTests(unittest.TestCase):
    def test_complete_exact_marginals_and_union_presence_are_preserved(self) -> None:
        belief, constraints, allocation = _complete()
        state = build_card_confidence(belief, constraints, allocation)

        self.assertEqual(state.status, "available")
        self.assertEqual(state.physical_assignment_count, 3)
        self.assertEqual(tuple(player.player_id for player in state.players), (2, 3))
        player_two = state.players[0]
        self.assertEqual([(rank.rank, rank.presence_numerator, rank.expected_copy_numerator) for rank in player_two.ranks], [("3", 3, 4), ("4", 2, 2)])
        self.assertEqual(player_two.ranks[0].denominator, 3)

    def test_certain_impossible_and_cross_player_copy_conservation(self) -> None:
        belief, constraints = _inputs(token_counts={"3S": 2}, capacities={2: 1, 3: 1})
        allocation = enumerate_card_allocations(belief, constraints)
        state = build_card_confidence(belief, constraints, allocation)

        self.assertTrue(all(rank.is_certain for player in state.players for rank in player.ranks))
        self.assertFalse(any(rank.is_impossible for player in state.players for rank in player.ranks))
        self.assertEqual(sum(player.ranks[0].expected_copy_numerator for player in state.players), 2 * state.physical_assignment_count)

        belief, constraints = _inputs(token_counts={"3S": 1, "4H": 1}, capacities={2: 1, 3: 1})
        constrained = replace(
            constraints,
            possible_owners_by_token=MappingProxyType({"3S": (3,), "4H": (2,)}),
        )
        allocation = enumerate_card_allocations(belief, constrained)
        state = build_card_confidence(belief, constrained, allocation)
        by_rank = {rank.rank: rank for rank in state.players[0].ranks}
        self.assertTrue(by_rank["4"].is_certain)
        self.assertTrue(by_rank["3"].is_impossible)

    def test_rank_order_frozen_output_and_json_are_stable(self) -> None:
        belief, constraints = _inputs(token_counts={"BJ": 1, "10S": 1, "3H": 1}, capacities={2: 2, 3: 1})
        allocation = enumerate_card_allocations(belief, constraints)
        state = build_card_confidence(belief, constraints, allocation)

        self.assertEqual(tuple(rank.rank for rank in state.players[0].ranks), ("3", "10", "BJ"))
        with self.assertRaises(FrozenInstanceError):
            state.status = "unavailable"  # type: ignore[misc]
        self.assertIsInstance(json.dumps(state.to_dict(), allow_nan=False), str)
        self.assertEqual(state.to_dict(), build_card_confidence(belief, constraints, allocation).to_dict())

    def test_noncritical_and_public_or_constraint_failures_are_unavailable(self) -> None:
        belief, constraints, allocation = _complete()
        for phase in ("near_open_endgame", "endgame", "opening", "midgame"):
            with self.subTest(phase=phase):
                state = build_card_confidence(
                    replace(belief, phase=phase), replace(constraints, phase=phase), replace(allocation, phase=phase),
                )
                self.assertEqual(state.status, "unavailable")
                self.assertIn("unsupported_phase", state.diagnostics)
        cases = (
            (replace(belief, token_pool_exact=False), constraints, allocation, "token_pool_inexact"),
            (replace(belief, diagnostics=("bad",)), constraints, allocation, "belief_diagnostics_present"),
            (belief, replace(constraints, token_constraints_exact=False), allocation, "constraints_inexact"),
            (belief, replace(constraints, is_consistent=False), allocation, "constraints_inconsistent"),
        )
        for item_belief, item_constraints, item_allocation, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(diagnostic, build_card_confidence(item_belief, item_constraints, item_allocation).diagnostics)

    def test_incomplete_phase_count_player_and_capacity_failures_are_closed(self) -> None:
        belief, constraints, allocation = _complete()
        cases = (
            (belief, constraints, replace(allocation, status="truncated", search_complete=False), "allocation_not_complete"),
            (belief, constraints, replace(allocation, diagnostics=("bad",)), "allocation_diagnostics_present"),
            (replace(belief, external_unknown_count=13), constraints, allocation, "invalid_external_unknown_count"),
            (belief, replace(constraints, phase="endgame"), allocation, "phase_mismatch"),
            (belief, constraints, replace(allocation, total_unseen_cards=2), "external_count_mismatch"),
            (belief, constraints, replace(allocation, players=allocation.players[:-1]), "player_set_mismatch"),
            (belief, constraints, replace(allocation, players=(replace(allocation.players[0], player_id=[]), *allocation.players[1:])), "player_set_mismatch"),
            (belief, constraints, replace(allocation, players=(replace(allocation.players[0], remaining_capacity=1), *allocation.players[1:])), "capacity_mismatch"),
        )
        for item_belief, item_constraints, item_allocation, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                state = build_card_confidence(item_belief, item_constraints, item_allocation)
                self.assertEqual(state.status, "unavailable")
                self.assertEqual(state.players, ())
                self.assertEqual(state.physical_assignment_count, 0)
                self.assertIn(diagnostic, state.diagnostics)

    def test_invalid_denominator_rank_keys_numerators_and_conservation_fail_closed(self) -> None:
        belief, constraints, allocation = _complete()
        player = allocation.players[0]
        cases = (
            (replace(allocation, physical_assignment_count=True), "invalid_physical_assignment_count"),
            (replace(allocation, physical_assignment_count=0), "invalid_physical_assignment_count"),
            (replace(allocation, players=(replace(player, holding_assignment_count_by_rank=MappingProxyType({"3": 3}),), *allocation.players[1:])), "rank_key_mismatch"),
            (replace(allocation, players=(replace(player, holding_assignment_count_by_rank=MappingProxyType({"3": True, "4": 2}),), *allocation.players[1:])), "invalid_presence_numerator"),
            (replace(allocation, players=(replace(player, copy_assignment_count_by_rank=MappingProxyType({"3": 99, "4": 2}),), *allocation.players[1:])), "invalid_copy_numerator"),
            (replace(allocation, players=(replace(player, copy_assignment_count_by_rank=MappingProxyType({"3": 3, "4": 2}),), *allocation.players[1:])), "copy_conservation_mismatch"),
        )
        for item_allocation, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                state = build_card_confidence(belief, constraints, item_allocation)
                self.assertEqual(state.status, "unavailable")
                self.assertEqual(state.physical_assignment_count, 0)
                self.assertEqual(state.players, ())
                self.assertIn(diagnostic, state.diagnostics)

    def test_truthy_non_boolean_flags_fail_closed_with_existing_diagnostics(self) -> None:
        belief, constraints, allocation = _complete()
        cases = (
            ("token_pool_exact", "belief", "token_pool_inexact"),
            ("token_constraints_exact", "constraints", "constraints_inexact"),
            ("is_consistent", "constraints", "constraints_inconsistent"),
            ("search_complete", "allocation", "allocation_not_complete"),
        )
        for value in (1, "yes"):
            for field, target, diagnostic in cases:
                with self.subTest(field=field, value=value):
                    inputs = {"card_belief": belief, "constraints": constraints, "allocation": allocation}
                    target = "card_belief" if target == "belief" else target
                    inputs[target] = replace(inputs[target], **{field: value})
                    state = build_card_confidence(**inputs)
                    self.assertEqual(state.status, "unavailable")
                    self.assertEqual(state.physical_assignment_count, 0)
                    self.assertEqual(state.players, ())
                    self.assertIn(diagnostic, state.diagnostics)

    def test_constraint_and_allocation_candidate_sets_are_strict(self) -> None:
        belief, constraints, allocation = _complete()
        external_constraint = PlayerCardConstraints(99, "opponent", 1, (), (), ())
        external_allocation = replace(allocation.players[0], player_id=99)
        cases = (
            (replace(constraints, players=(*constraints.players, external_constraint)), allocation),
            (constraints, replace(allocation, players=(*allocation.players, external_allocation))),
            (replace(constraints, players=(*constraints.players, constraints.players[1])), allocation),
            (constraints, replace(allocation, players=(*allocation.players, allocation.players[0]))),
            (replace(constraints, players=(constraints.players[0], replace(constraints.players[1], player_id=99), constraints.players[2])), allocation),
            (replace(constraints, players=(constraints.players[0], replace(constraints.players[1], player_id=[]), constraints.players[2])), allocation),
        )
        for item_constraints, item_allocation in cases:
            with self.subTest(case=item_constraints.players):
                state = build_card_confidence(belief, item_constraints, item_allocation)
                self.assertEqual(state.status, "unavailable")
                self.assertEqual(state.players, ())
                self.assertIn("player_set_mismatch", state.diagnostics)

    def test_malformed_copy_values_fail_before_conservation(self) -> None:
        belief, constraints, allocation = _complete()
        player = allocation.players[0]
        for value in ("bad", None, 1.5, True, -1, 99):
            with self.subTest(value=value):
                copies = dict(player.copy_assignment_count_by_rank)
                copies["3"] = value
                malformed = replace(
                    allocation,
                    players=(
                        replace(player, copy_assignment_count_by_rank=MappingProxyType(copies)),
                        *allocation.players[1:],
                    ),
                )
                state = build_card_confidence(belief, constraints, malformed)
                self.assertEqual(state.status, "unavailable")
                self.assertEqual(state.physical_assignment_count, 0)
                self.assertEqual(state.players, ())
                self.assertIn("invalid_copy_numerator", state.diagnostics)

    def test_available_snapshot_is_unchanged(self) -> None:
        belief, constraints, allocation = _complete()
        self.assertEqual(build_card_confidence(belief, constraints, allocation).to_dict(), {
            "phase": "critical_endgame",
            "status": "available",
            "source": "physical_assignment_marginal_v1",
            "calibration_scope": "critical_endgame_policy_diverse_v1",
            "external_unknown_count": 3,
            "physical_assignment_count": 3,
            "players": [
                {"player_id": 2, "remaining_capacity": 2, "ranks": [
                    {"rank": "3", "presence_numerator": 3, "expected_copy_numerator": 4, "denominator": 3, "is_certain": True, "is_impossible": False},
                    {"rank": "4", "presence_numerator": 2, "expected_copy_numerator": 2, "denominator": 3, "is_certain": False, "is_impossible": False},
                ]},
                {"player_id": 3, "remaining_capacity": 1, "ranks": [
                    {"rank": "3", "presence_numerator": 2, "expected_copy_numerator": 2, "denominator": 3, "is_certain": False, "is_impossible": False},
                    {"rank": "4", "presence_numerator": 1, "expected_copy_numerator": 1, "denominator": 3, "is_certain": False, "is_impossible": False},
                ]},
            ],
            "diagnostics": [],
        })

    def test_source_boundary_and_non_confidence_consumers_do_not_reference_module(self) -> None:
        source = Path("agents/card_confidence.py").read_text(encoding="utf-8")
        for forbidden in ("evaluation", "ground_truth", "game._state", "observation", "history", "deepseek", "rag"):
            self.assertNotIn(forbidden, source)
        for path in (
            "agents/rag_advisor.py",
            "cli/run_4ai_debug.py", "engine/game.py",
        ):
            self.assertNotIn("card_confidence", Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
