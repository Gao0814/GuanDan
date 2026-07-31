"""Tests for offline-only J-D1b exact rank-marginal scoring."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_allocations import (
    CardAllocationResult,
    PlayerAllocationBounds,
    enumerate_card_allocations,
)
from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_constraints import CardConstraintState, PlayerCardConstraints
from evaluation.marginal_metrics import evaluate_rank_marginals


def _rank_counts(tokens: dict[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for token, count in tokens.items():
        rank = token if token in {"SJ", "BJ"} else token[:-1]
        result[rank] = result.get(rank, 0) + count
    return result


def _inputs(
    *,
    token_counts: dict[str, int] | None = None,
    capacities: dict[int, int] | None = None,
    domains: dict[str, tuple[int, ...]] | None = None,
) -> tuple[CardBeliefState, CardConstraintState]:
    token_counts = {"3S": 1, "3H": 1, "4C": 1} if token_counts is None else token_counts
    capacities = {2: 2, 3: 1} if capacities is None else capacities
    domains = (
        {token: tuple(capacities) for token in token_counts}
        if domains is None else domains
    )
    rank_counts = _rank_counts(token_counts)
    public_players = (
        PlayerPublicBelief(1, "1&3", "self", 0, False, None, (), 0),
        *(
            PlayerPublicBelief(player_id, "2&4", "opponent", capacity, False, None, (), 0)
            for player_id, capacity in capacities.items()
        ),
    )
    belief = CardBeliefState(
        phase="endgame",
        external_unknown_count=sum(token_counts.values()),
        unseen_cards_by_token=MappingProxyType(dict(token_counts)),
        unseen_cards_by_rank=MappingProxyType(rank_counts),
        players=public_players,
        diagnostics=(),
        token_pool_exact=True,
    )
    constraints = CardConstraintState(
        phase="endgame",
        possible_owners_by_token=MappingProxyType(dict(domains)),
        possible_owners_by_rank=MappingProxyType({rank: tuple(capacities) for rank in rank_counts}),
        players=tuple(
            PlayerCardConstraints(
                player.player_id,
                player.relation,
                player.remaining_count,
                tuple(domains),
                tuple(rank_counts),
                (),
            )
            for player in public_players
        ),
        diagnostics=(),
        is_consistent=True,
        token_constraints_exact=True,
    )
    return belief, constraints


def _complete_fixture() -> tuple[CardBeliefState, CardAllocationResult, dict[int, list[str]]]:
    belief, constraints = _inputs()
    allocation = enumerate_card_allocations(belief, constraints)
    assert allocation.status == "complete"
    return belief, allocation, {2: ["3S", "3H"], 3: ["4C"]}


def _player(allocation: CardAllocationResult, player_id: int) -> PlayerAllocationBounds:
    return next(item for item in allocation.players if item.player_id == player_id)


class MarginalMetricsTests(unittest.TestCase):
    def test_exact_multi_player_rank_errors_and_pairs(self) -> None:
        belief, allocation, truth = _complete_fixture()

        report = evaluate_rank_marginals(belief, allocation, truth)

        self.assertTrue(report.valid_input)
        self.assertEqual(report.prediction_source, "j_d1b_physical_marginals")
        self.assertEqual(report.physical_assignment_count, 3)
        self.assertEqual(report.rank_pair_count, 4)
        self.assertEqual(report.truth_positive_pair_count, 2)
        self.assertEqual((report.presence_brier_sum_numerator, report.presence_brier_sum_denominator), (4, 3))
        self.assertEqual((report.copy_squared_error_sum_numerator, report.copy_squared_error_sum_denominator), (16, 9))

    def test_calibration_bins_are_fixed_exact_and_include_negative_pairs(self) -> None:
        belief, allocation, truth = _complete_fixture()
        report = evaluate_rank_marginals(belief, allocation, truth)

        self.assertEqual(len(report.calibration_bins), 10)
        self.assertEqual(sum(item.prediction_count for item in report.calibration_bins), 4)
        self.assertEqual(sum(item.truth_positive_count for item in report.calibration_bins), 2)
        self.assertEqual(report.calibration_bins[3].prediction_sum_numerator, 1)
        self.assertEqual(report.calibration_bins[3].prediction_sum_denominator, 3)
        self.assertEqual(report.calibration_bins[6].prediction_count, 2)
        self.assertEqual(report.calibration_bins[6].prediction_sum_numerator, 4)
        self.assertEqual(report.calibration_bins[6].prediction_sum_denominator, 3)
        self.assertEqual(report.calibration_bins[9].prediction_sum_numerator, 1)
        self.assertEqual(report.calibration_bins[9].prediction_sum_denominator, 1)

    def test_bin_boundaries_zero_point_one_point_nine_and_one(self) -> None:
        tokens = {"3S": 1, "3H": 1, "3C": 1, "3D": 1}
        capacities = {2: 1, 3: 1, 4: 1, 5: 1}
        belief, _ = _inputs(token_counts=tokens, capacities=capacities)
        numerators = (0, 1, 9, 10)
        players = tuple(
            PlayerAllocationBounds(
                player_id=player_id,
                remaining_capacity=1,
                min_count_by_token=MappingProxyType({}),
                max_count_by_token=MappingProxyType({}),
                confirmed_cards=(),
                holding_assignment_count_by_rank=MappingProxyType({"3": holding}),
                copy_assignment_count_by_rank=MappingProxyType({"3": 10}),
            )
            for player_id, holding in zip(capacities, numerators)
        )
        allocation = CardAllocationResult(
            phase="endgame", status="complete", total_unseen_cards=4,
            feasible_assignment_count=1, search_nodes=1, search_complete=True,
            possible_owners_by_token=MappingProxyType({}), players=players,
            diagnostics=(), physical_assignment_count=10,
        )
        report = evaluate_rank_marginals(
            belief, allocation, {2: ["3S"], 3: ["3H"], 4: ["3C"], 5: ["3D"]},
        )

        self.assertTrue(report.valid_input)
        self.assertEqual([item.prediction_count for item in report.calibration_bins], [1, 1, 0, 0, 0, 0, 0, 0, 0, 2])
        self.assertEqual(
            (
                report.calibration_bins[9].prediction_sum_numerator,
                report.calibration_bins[9].prediction_sum_denominator,
            ),
            (19, 10),
        )

    def test_certainty_error_is_valid_scoring_result(self) -> None:
        belief, constraints = _inputs(
            token_counts={"3S": 1, "4C": 1},
            capacities={2: 1, 3: 1},
            domains={"3S": (2,), "4C": (3,)},
        )
        allocation = enumerate_card_allocations(belief, constraints)

        report = evaluate_rank_marginals(belief, allocation, {2: ["4C"], 3: ["3S"]})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.certainty_error_count, 4)

    def test_ten_and_joker_truth_tokens_map_to_ranks(self) -> None:
        belief, constraints = _inputs(
            token_counts={"10S": 1, "SJ": 1, "BJ": 1},
            capacities={2: 3},
            domains={"10S": (2,), "SJ": (2,), "BJ": (2,)},
        )
        allocation = enumerate_card_allocations(belief, constraints)

        report = evaluate_rank_marginals(belief, allocation, {2: ["10S", "SJ", "BJ"]})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.rank_pair_count, 3)
        self.assertEqual(report.truth_positive_pair_count, 3)
        self.assertEqual(report.presence_brier_sum_numerator, 0)
        self.assertEqual(report.copy_squared_error_sum_numerator, 0)

    def test_non_complete_or_invalid_allocation_fails_closed(self) -> None:
        belief, allocation, truth = _complete_fixture()
        for changed in (
            replace(allocation, status="truncated", search_complete=False, physical_assignment_count=0),
            replace(allocation, status="skipped_too_many_cards", search_complete=False, physical_assignment_count=0),
            replace(allocation, status="invalid_input", search_complete=False, physical_assignment_count=0),
            replace(allocation, status="no_feasible_allocation", search_complete=True, physical_assignment_count=0),
        ):
            with self.subTest(status=changed.status):
                report = evaluate_rank_marginals(belief, changed, truth)
                self.assertFalse(report.valid_input)
                self.assertIn("allocation_not_complete", report.diagnostics)
                self._assert_zero_report(report)

    def test_public_and_allocation_base_input_fail_closed(self) -> None:
        belief, allocation, truth = _complete_fixture()
        cases = (
            (replace(belief, token_pool_exact=False), allocation, "token_pool_inexact"),
            (belief, replace(allocation, phase="midgame"), "allocation_phase_mismatch"),
            (belief, replace(allocation, physical_assignment_count=0), "invalid_physical_assignment_count"),
            (belief, replace(allocation, physical_assignment_count=True), "invalid_physical_assignment_count"),
            (belief, replace(allocation, total_unseen_cards=99), "allocation_card_count_mismatch"),
        )
        for changed_belief, changed_allocation, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                report = evaluate_rank_marginals(changed_belief, changed_allocation, truth)
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)

    def test_allocation_players_capacities_keys_and_numerators_fail_closed(self) -> None:
        belief, allocation, truth = _complete_fixture()
        player_two = _player(allocation, 2)
        extra = replace(player_two, player_id=99)
        cases = (
            (replace(allocation, players=allocation.players[1:]), "missing_allocation_player"),
            (replace(allocation, players=allocation.players + (extra,)), "unexpected_allocation_player"),
            (replace(allocation, players=(replace(player_two, remaining_capacity=1), _player(allocation, 3))), "allocation_capacity_mismatch"),
            (replace(allocation, players=(replace(player_two, holding_assignment_count_by_rank=MappingProxyType({"3": 3})), _player(allocation, 3))), "rank_marginal_key_mismatch"),
            (replace(allocation, players=(replace(player_two, holding_assignment_count_by_rank=MappingProxyType({"3": -1, "4": 2})), _player(allocation, 3))), "invalid_rank_marginal"),
        )
        for changed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                report = evaluate_rank_marginals(belief, changed, truth)
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)

    def test_rank_copy_conservation_and_legacy_empty_rank_maps_fail_closed(self) -> None:
        belief, allocation, truth = _complete_fixture()
        player_two = _player(allocation, 2)
        broken = replace(
            player_two,
            copy_assignment_count_by_rank=MappingProxyType({"3": 3, "4": 2}),
        )
        report = evaluate_rank_marginals(
            belief,
            replace(allocation, players=(broken, _player(allocation, 3))),
            truth,
        )
        self.assertFalse(report.valid_input)
        self.assertIn("rank_copy_conservation_mismatch", report.diagnostics)

        legacy = PlayerAllocationBounds(2, 2, MappingProxyType({}), MappingProxyType({}), ())
        report = evaluate_rank_marginals(
            belief,
            replace(allocation, players=(legacy, _player(allocation, 3))),
            truth,
        )
        self.assertFalse(report.valid_input)
        self.assertIn("rank_marginal_key_mismatch", report.diagnostics)

    def test_truth_player_capacity_token_and_pool_fail_closed(self) -> None:
        belief, allocation, truth = _complete_fixture()
        cases = (
            ({2: ["3S", "3H"]}, "missing_truth_player"),
            ({2: ["3S", "3H"], 3: ["4C"], 99: []}, "unexpected_truth_player"),
            ({2: ["3S"], 3: ["4C"]}, "truth_hand_count_mismatch"),
            ({2: ["3S", "bad"], 3: ["4C"]}, "invalid_truth_token"),
            ({2: ["3S", "3S"], 3: ["4C"]}, "truth_pool_mismatch"),
        )
        for changed_truth, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                report = evaluate_rank_marginals(belief, allocation, changed_truth)
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)

    def test_invalid_report_is_zeroed_and_has_ten_empty_bins(self) -> None:
        belief, allocation, truth = _complete_fixture()
        report = evaluate_rank_marginals(replace(belief, token_pool_exact=False), allocation, truth)

        self._assert_zero_report(report)
        self.assertEqual(len(report.calibration_bins), 10)
        self.assertTrue(all(item.prediction_sum_denominator == 1 for item in report.calibration_bins))

    def test_output_is_immutable_json_safe_and_hides_truth_details(self) -> None:
        belief, allocation, truth = _complete_fixture()
        before_belief = belief.to_dict()
        before_allocation = allocation.to_dict()
        report = evaluate_rank_marginals(belief, allocation, truth)
        payload = report.to_dict()

        with self.assertRaises(FrozenInstanceError):
            report.phase = "midgame"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            report.calibration_bins[0].prediction_count = 1  # type: ignore[misc]
        serialized = json.dumps(payload, allow_nan=False)
        self.assertNotIn("ground_truth_hands", serialized)
        self.assertNotIn("3S", serialized)
        self.assertNotIn("4C", serialized)
        self.assertEqual(belief.to_dict(), before_belief)
        self.assertEqual(allocation.to_dict(), before_allocation)

    def test_fixed_input_is_deterministic(self) -> None:
        belief, allocation, truth = _complete_fixture()
        self.assertEqual(
            evaluate_rank_marginals(belief, allocation, truth),
            evaluate_rank_marginals(belief, allocation, truth),
        )

    def _assert_zero_report(self, report: object) -> None:
        assert hasattr(report, "valid_input")
        self.assertFalse(report.valid_input)  # type: ignore[attr-defined]
        self.assertEqual(report.physical_assignment_count, 0)  # type: ignore[attr-defined]
        self.assertEqual(report.rank_pair_count, 0)  # type: ignore[attr-defined]
        self.assertEqual(report.truth_positive_pair_count, 0)  # type: ignore[attr-defined]
        self.assertEqual(report.certainty_error_count, 0)  # type: ignore[attr-defined]
        self.assertEqual((report.presence_brier_sum_numerator, report.presence_brier_sum_denominator), (0, 1))  # type: ignore[attr-defined]
        self.assertEqual((report.copy_squared_error_sum_numerator, report.copy_squared_error_sum_denominator), (0, 1))  # type: ignore[attr-defined]
        self.assertTrue(all(item.prediction_count == 0 for item in report.calibration_bins))  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
