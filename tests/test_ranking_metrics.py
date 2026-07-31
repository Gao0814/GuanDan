"""Tests for Step J-C2b2 tie-safe offline rank-ablation metrics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_ranker import (
    CardRankRankingState,
    PlayerRankCandidate,
    PlayerRankRanking,
    RankScoreEvidence,
)
from evaluation.ranking_metrics import evaluate_rank_ranking


def _candidate(
    rank: str,
    *,
    status: str = "possible",
    count: int = 0,
    score: int = 0,
    tier: int = 1,
    evidence: tuple[RankScoreEvidence, ...] | None = None,
) -> PlayerRankCandidate:
    if evidence is None:
        evidence = (
            (RankScoreEvidence("opponent_single_pass", 1, 0, "3", score),)
            if score < 0 else ()
        )
    return PlayerRankCandidate(rank, status, count, score, tier, evidence)


def _inputs(
    *,
    tokens: dict[str, int] | None = None,
    capacities: dict[int, int] | None = None,
    candidates: dict[int, tuple[PlayerRankCandidate, ...]] | None = None,
    phase: str = "endgame",
    ranking_phase: str | None = None,
    token_pool_exact: bool = True,
) -> tuple[CardBeliefState, CardRankRankingState]:
    tokens = {"3S": 1, "AH": 1} if tokens is None else tokens
    capacities = {2: sum(tokens.values())} if capacities is None else capacities
    candidates = {2: (_candidate("3"), _candidate("A"))} if candidates is None else candidates
    players = (
        PlayerPublicBelief(1, "team_13", "self", 0, False, None, (), 0),
        *(
            PlayerPublicBelief(player_id, "team_24", "opponent", count, False, None, (), 0)
            for player_id, count in capacities.items()
        ),
        PlayerPublicBelief(9, "team_24", "opponent", 0, True, 1, (), 0),
    )
    belief = CardBeliefState(
        phase=phase,
        external_unknown_count=sum(tokens.values()),
        unseen_cards_by_token=MappingProxyType(dict(tokens)),
        unseen_cards_by_rank=MappingProxyType({"3": sum(tokens.values())}),
        players=players,
        diagnostics=(),
        token_pool_exact=token_pool_exact,
    )
    ranking = CardRankRankingState(
        phase=phase if ranking_phase is None else ranking_phase,
        hard_source="j_b1_constraints",
        players=tuple(
            PlayerRankRanking(
                player_id=player_id,
                relation=next(player.relation for player in players if player.player_id == player_id),
                candidates=items,
            )
            for player_id, items in candidates.items()
        ),
        diagnostics=(),
    )
    return belief, ranking


class RankingMetricsTests(unittest.TestCase):
    def test_candidate_coverage_deduplicates_same_rank_copies(self) -> None:
        belief, ranking = _inputs(tokens={"3S": 2, "AH": 1}, capacities={2: 3})

        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "3S", "AH"]})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.soft.truth_rank_count, 2)
        self.assertEqual(report.soft.candidate_covered_count, 2)
        self.assertEqual(report.soft.candidate_recall, 1.0)
        self.assertEqual(report.candidate_recall_delta, 0.0)

    def test_missing_candidate_and_multi_player_truth_aggregate(self) -> None:
        belief, ranking = _inputs(
            tokens={"3S": 1, "AH": 1},
            capacities={2: 1, 3: 1},
            candidates={2: (_candidate("3"),), 3: (_candidate("3"),)},
        )

        report = evaluate_rank_ranking(belief, ranking, {2: ["3S"], 3: ["AH"]})

        self.assertEqual(report.soft.player_count, 2)
        self.assertEqual(report.soft.truth_rank_count, 2)
        self.assertEqual(report.soft.candidate_covered_count, 1)
        self.assertEqual(report.soft.candidate_missed_count, 1)

    def test_baseline_zeroes_possible_scores_and_preserves_confirmed_layer(self) -> None:
        belief, ranking = _inputs(
            candidates={2: (
                _candidate("3", status="confirmed", count=1, tier=1),
                _candidate("A", score=-1, tier=2),
            )},
        )

        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})

        self.assertEqual(report.baseline.top1_selected_count, 1)
        self.assertEqual(report.soft.top1_selected_count, 1)
        self.assertEqual(report.baseline.candidate_recall, report.soft.candidate_recall)

    def test_tie_safe_top1_and_top3_expand_full_tiers(self) -> None:
        candidates = {2: (
            _candidate("3", tier=1),
            _candidate("4", tier=1),
            _candidate("A", score=-1, tier=2),
            _candidate("2", score=-2, tier=3),
        )}
        belief, ranking = _inputs(
            tokens={"3S": 1, "4S": 1, "AH": 1, "2S": 1},
            capacities={2: 4},
            candidates=candidates,
        )

        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "4S", "AH", "2S"]})

        self.assertEqual(report.soft.top1_selected_count, 2)
        self.assertEqual(report.soft.top3_selected_count, 3)
        self.assertEqual(report.soft.top1_average_selection_size, 2.0)
        self.assertEqual(report.soft.top3_average_selection_size, 3.0)
        self.assertEqual(report.soft.top1_precision, 1.0)

    def test_same_tier_order_does_not_change_metrics(self) -> None:
        candidates = (_candidate("3", tier=1), _candidate("A", tier=1), _candidate("2", score=-1, tier=2))
        belief, ranking = _inputs(tokens={"3S": 1, "AH": 1, "2S": 1}, capacities={2: 3}, candidates={2: candidates})
        reversed_ranking = replace(ranking, players=(replace(ranking.players[0], candidates=tuple(reversed(candidates))),))
        truth = {2: ["3S", "AH", "2S"]}

        self.assertEqual(
            evaluate_rank_ranking(belief, ranking, truth),
            evaluate_rank_ranking(belief, reversed_ranking, truth),
        )

    def test_worst_case_mrr_and_missing_rank_contribution(self) -> None:
        belief, ranking = _inputs(
            tokens={"3S": 1, "AH": 1},
            capacities={2: 2},
            candidates={2: (_candidate("3", tier=1), _candidate("4", tier=1))},
        )

        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})

        self.assertEqual(report.soft.worst_case_mrr, 0.25)

    def test_soft_can_improve_or_worsen_relative_to_zero_score_baseline(self) -> None:
        candidates = {2: (_candidate("3", tier=1), _candidate("A", score=-1, tier=2))}
        belief, ranking = _inputs(tokens={"3S": 1}, capacities={2: 1}, candidates=candidates)
        improved = evaluate_rank_ranking(belief, ranking, {2: ["3S"]})
        belief, ranking = _inputs(tokens={"AH": 1}, capacities={2: 1}, candidates=candidates)
        worsened = evaluate_rank_ranking(belief, ranking, {2: ["AH"]})

        self.assertGreater(improved.top1_precision_delta, 0.0)
        self.assertLess(worsened.top1_recall_delta, 0.0)
        self.assertEqual(improved.candidate_recall_delta, 0.0)

    def test_zero_truth_denominators_are_stable(self) -> None:
        belief, ranking = _inputs(tokens={}, capacities={}, candidates={})

        report = evaluate_rank_ranking(belief, ranking, {})

        self.assertTrue(report.valid_input)
        self.assertEqual(report.soft.truth_rank_count, 0)
        self.assertEqual(report.soft.candidate_recall, 1.0)
        self.assertEqual(report.soft.top1_precision, 1.0)
        self.assertEqual(report.soft.worst_case_mrr, 1.0)

    def test_invalid_truth_inputs_fail_closed(self) -> None:
        belief, ranking = _inputs()
        cases = (
            ({}, "missing_truth_player"),
            ({1: [], 2: ["3S", "AH"]}, "unexpected_truth_player"),
            ({2: ["3S"]}, "truth_hand_count_mismatch"),
            ({2: ["3S", "XX"]}, "invalid_truth_token"),
        )
        for truth, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                report = evaluate_rank_ranking(belief, ranking, truth)
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)
                self.assertEqual(report.soft.truth_rank_count, 0)

    def test_pool_and_ranking_player_relation_validation_fail_closed(self) -> None:
        belief, ranking = _inputs(token_pool_exact=False)
        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})
        self.assertIn("token_pool_inexact", report.diagnostics)

        belief, ranking = _inputs(ranking_phase="midgame")
        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})
        self.assertIn("ranking_phase_mismatch", report.diagnostics)

        belief, ranking = _inputs(candidates={})
        report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})
        self.assertIn("missing_ranking_player", report.diagnostics)

        belief, ranking = _inputs()
        extra = PlayerRankRanking(99, "opponent", ())
        report = evaluate_rank_ranking(belief, replace(ranking, players=ranking.players + (extra,)), {2: ["3S", "AH"]})
        self.assertIn("unexpected_ranking_player", report.diagnostics)

        bad_relation = replace(ranking.players[0], relation="teammate")
        report = evaluate_rank_ranking(belief, replace(ranking, players=(bad_relation,)), {2: ["3S", "AH"]})
        self.assertIn("relation_mismatch", report.diagnostics)

    def test_candidate_status_count_score_and_evidence_validation_fail_closed(self) -> None:
        base_belief, base_ranking = _inputs()
        invalid_candidates = (
            _candidate("3"), _candidate("3"),
        )
        cases = (
            (invalid_candidates, "duplicate_candidate_rank"),
            ((_candidate("XX"),), "invalid_candidate_rank"),
            ((_candidate("3", status="bad"),), "invalid_hard_status"),
            ((_candidate("3", status="confirmed", count=0),), "invalid_confirmed_count"),
            ((_candidate("3", score=1),), "invalid_soft_score"),
            ((_candidate("3", score=-1, evidence=(RankScoreEvidence("x", 1, 0, "3", 0),)),), "invalid_evidence_delta"),
            ((_candidate("3", score=-2, evidence=(RankScoreEvidence("x", 1, 0, "3", -1),)),), "evidence_score_mismatch"),
        )
        for candidates, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                ranking = replace(base_ranking, players=(replace(base_ranking.players[0], candidates=candidates),))
                report = evaluate_rank_ranking(base_belief, ranking, {2: ["3S", "AH"]})
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)

    def test_tier_validation_fail_closed(self) -> None:
        belief, base = _inputs()
        cases = (
            ((_candidate("3", tier=2),), "non_contiguous_score_tier"),
            ((_candidate("3", tier=1), _candidate("A", score=-1, tier=1)), "inconsistent_tier_group"),
            ((_candidate("3", score=-1, tier=1), _candidate("A", tier=2)), "invalid_tier_order"),
        )
        for candidates, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                ranking = replace(base, players=(replace(base.players[0], candidates=candidates),))
                report = evaluate_rank_ranking(belief, ranking, {2: ["3S", "AH"]})
                self.assertFalse(report.valid_input)
                self.assertIn(diagnostic, report.diagnostics)

    def test_report_is_serializable_immutable_and_does_not_leak_truth(self) -> None:
        belief, ranking = _inputs()
        before_belief = belief.to_dict()
        before_ranking = ranking.to_dict()
        truth = {2: ["3S", "AH"]}
        report = evaluate_rank_ranking(belief, ranking, truth)
        serialized = json.dumps(report.to_dict())

        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("3S", serialized)
        self.assertNotIn("AH", serialized)
        with self.assertRaises(FrozenInstanceError):
            report.valid_input = False  # type: ignore[misc]
        self.assertEqual(belief.to_dict(), before_belief)
        self.assertEqual(ranking.to_dict(), before_ranking)
        self.assertEqual(
            report,
            evaluate_rank_ranking(belief, ranking, truth),
        )


if __name__ == "__main__":
    unittest.main()
