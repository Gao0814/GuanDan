"""Contract tests for the aggregate-only full-game conditional-pass trial."""

from __future__ import annotations

from dataclasses import replace
import json
from types import MappingProxyType
import unittest
from unittest.mock import patch

from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent
from evaluation.conditional_pressure_pass_runtime_trial import (
    ConditionalPressurePassRuntimeTrialReport,
    _pair_schedule,
    _play_trial_game,
    _valid_report,
    run_conditional_pressure_pass_runtime_trial,
    runtime_trial_decision,
)


def _report(**changes: object) -> ConditionalPressurePassRuntimeTrialReport:
    values: dict[str, object] = {
        "requested_seed_pair_count": 20,
        "completed_seed_pair_count": 20,
        "incomplete_seed_pair_count": 0,
        "requested_game_count": 40,
        "completed_game_count": 40,
        "incomplete_game_count": 0,
        "scheduled_candidate_team_13_game_count": 20,
        "scheduled_candidate_team_24_game_count": 20,
        "current_level_rank": "2",
        "max_steps": 5000,
        "candidate_opportunity_count": 20,
        "candidate_conditional_pass_count": 20,
        "active_conditional_pass_seed_pair_count": 20,
        "candidate_win_count": 20,
        "candidate_draw_count": 20,
        "candidate_loss_count": 0,
        "baseline_win_count": 0,
        "baseline_draw_count": 20,
        "baseline_loss_count": 20,
        "candidate_team_outcome_score_total": 60,
        "baseline_team_outcome_score_total": 20,
        "candidate_placement_sum_total": 160,
        "baseline_placement_sum_total": 240,
        "candidate_better_count": 20,
        "baseline_better_count": 0,
        "tie_count": 0,
        "trial_sha256": "0" * 64,
        "diagnostic_counts": MappingProxyType({}),
    }
    values.update(changes)
    return ConditionalPressurePassRuntimeTrialReport(**values)  # type: ignore[arg-type]


class ConditionalPressurePassRuntimeTrialTests(unittest.TestCase):
    def test_symmetric_schedule_and_decision_boundaries(self) -> None:
        self.assertEqual(
            _pair_schedule((9, 10)),
            ((9, "team_13"), (9, "team_24"), (10, "team_13"), (10, "team_24")),
        )
        retain = _report()
        self.assertEqual(runtime_trial_decision(retain), "retain_conditional_pressure_pass_for_botzone_opt_in_smoke")
        baseline_better = _report(
            candidate_win_count=0, candidate_draw_count=20, candidate_loss_count=20,
            baseline_win_count=20, baseline_draw_count=20, baseline_loss_count=0,
            candidate_team_outcome_score_total=20, baseline_team_outcome_score_total=60,
            candidate_placement_sum_total=240, baseline_placement_sum_total=160,
            candidate_better_count=0, baseline_better_count=20,
        )
        self.assertEqual(runtime_trial_decision(baseline_better), "reject_conditional_pressure_pass_runtime_candidate")
        tie = _report(
            candidate_win_count=20, candidate_draw_count=0, candidate_loss_count=20,
            baseline_win_count=20, baseline_draw_count=0, baseline_loss_count=20,
            candidate_team_outcome_score_total=40, baseline_team_outcome_score_total=40,
            candidate_placement_sum_total=200, baseline_placement_sum_total=200,
            candidate_better_count=0, tie_count=20,
        )
        self.assertEqual(runtime_trial_decision(tie), "reject_conditional_pressure_pass_runtime_candidate")
        self.assertEqual(
            runtime_trial_decision(replace(retain, active_conditional_pass_seed_pair_count=19)),
            "conditional_pressure_pass_runtime_trial_evidence_insufficient",
        )
        self.assertEqual(
            runtime_trial_decision(replace(retain, diagnostic_counts=MappingProxyType({"agent_action_invalid": 1}))),
            "conditional_pressure_pass_runtime_trial_invalid",
        )
        self.assertEqual(
            runtime_trial_decision(replace(retain, requested_game_count=3)),
            "conditional_pressure_pass_runtime_trial_invalid",
        )
        for invalid in (
            replace(retain, scheduled_candidate_team_13_game_count=19),
            replace(retain, candidate_conditional_pass_count=19),
            replace(retain, candidate_placement_sum_total=161),
            replace(retain, trial_sha256="A" * 64),
            replace(retain, candidate_win_count=-1),
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(runtime_trial_decision(invalid), "conditional_pressure_pass_runtime_trial_invalid")

    def test_pair_game_cross_conservation_rejects_complete_games_for_incomplete_pair(self) -> None:
        malformed = _report(
            requested_seed_pair_count=21,
            completed_seed_pair_count=20,
            incomplete_seed_pair_count=1,
            requested_game_count=42,
            completed_game_count=42,
            incomplete_game_count=0,
            scheduled_candidate_team_13_game_count=21,
            scheduled_candidate_team_24_game_count=21,
            trial_sha256="not-a-digest",
        )
        self.assertEqual(runtime_trial_decision(malformed), "conditional_pressure_pass_runtime_trial_invalid")

    def test_validator_rejects_non_complementary_results_and_out_of_range_placements(self) -> None:
        retain = _report()
        cases = (
            _report(
                baseline_win_count=1, baseline_draw_count=18, baseline_loss_count=21,
                baseline_team_outcome_score_total=20,
            ),
            _report(baseline_win_count=1, baseline_loss_count=19, baseline_team_outcome_score_total=22),
            _report(baseline_draw_count=19, baseline_loss_count=21, baseline_team_outcome_score_total=19),
            _report(candidate_placement_sum_total=119, baseline_placement_sum_total=281),
            _report(candidate_placement_sum_total=281, baseline_placement_sum_total=119),
        )
        self.assertTrue(_valid_report(retain))
        for malformed in cases:
            with self.subTest(malformed=malformed):
                self.assertEqual(runtime_trial_decision(malformed), "conditional_pressure_pass_runtime_trial_invalid")

    def test_validator_accepts_only_fixed_rank_and_diagnostic_categories(self) -> None:
        retain = _report()
        for rank in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"):
            with self.subTest(rank=rank):
                self.assertTrue(_valid_report(replace(retain, current_level_rank=rank)))
        self.assertFalse(_valid_report(replace(retain, current_level_rank="invalid")))
        allowed = (
            "invalid_public_player", "agent_action_invalid", "game_step_invalid",
            "invalid_terminal_winner", "invalid_finish_order", "game_step_limit_reached",
        )
        for name in allowed:
            with self.subTest(diagnostic=name):
                report = replace(retain, diagnostic_counts=MappingProxyType({name: 1}))
                self.assertTrue(_valid_report(report))
                self.assertEqual(runtime_trial_decision(report), "conditional_pressure_pass_runtime_trial_invalid")
        for diagnostics in (
            MappingProxyType({"unknown": 1}), MappingProxyType({"": 1}),
            MappingProxyType({"agent_action_invalid": 0}), MappingProxyType({"agent_action_invalid": -1}),
            MappingProxyType({"agent_action_invalid": True}),
        ):
            with self.subTest(diagnostics=diagnostics):
                self.assertFalse(_valid_report(replace(retain, diagnostic_counts=diagnostics)))

    def test_validator_rejects_empty_capacity_and_inconsistent_active_pass_counts(self) -> None:
        retain = _report()
        empty = replace(
            retain,
            requested_seed_pair_count=0, completed_seed_pair_count=0, requested_game_count=0,
            completed_game_count=0, scheduled_candidate_team_13_game_count=0, scheduled_candidate_team_24_game_count=0,
            candidate_opportunity_count=0, candidate_conditional_pass_count=0, active_conditional_pass_seed_pair_count=0,
            candidate_win_count=0, candidate_draw_count=0, baseline_draw_count=0, baseline_loss_count=0,
            candidate_team_outcome_score_total=0, baseline_team_outcome_score_total=0,
            candidate_placement_sum_total=0, baseline_placement_sum_total=0,
            candidate_better_count=0,
        )
        self.assertEqual(runtime_trial_decision(empty), "conditional_pressure_pass_runtime_trial_invalid")
        cases = (
            replace(retain, candidate_opportunity_count=0, candidate_conditional_pass_count=0, active_conditional_pass_seed_pair_count=20),
            replace(retain, active_conditional_pass_seed_pair_count=0),
            replace(retain, candidate_opportunity_count=19, candidate_conditional_pass_count=19),
        )
        for malformed in cases:
            with self.subTest(malformed=malformed):
                self.assertEqual(runtime_trial_decision(malformed), "conditional_pressure_pass_runtime_trial_invalid")

    def test_agents_are_per_game_and_persist_for_the_full_game(self) -> None:
        created: list[ConditionalPressurePassAIAgent] = []

        class TrackingCandidate(ConditionalPressurePassAIAgent):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)  # type: ignore[arg-type]
                created.append(self)

        with patch("evaluation.conditional_pressure_pass_runtime_trial.ConditionalPressurePassAIAgent", TrackingCandidate):
            first = _play_trial_game(46200, "team_13", "2", 5000)
            first_agents = tuple(created)
            second = _play_trial_game(46200, "team_24", "2", 5000)
        self.assertTrue(first.complete)
        self.assertTrue(second.complete)
        self.assertEqual(len(first_agents), 2)
        self.assertEqual(len(created), 4)
        self.assertTrue(all(agent.opportunity_count >= agent.conditional_pass_count for agent in created))
        self.assertEqual(sum(agent.conditional_pass_count for agent in first_agents), first.conditional_pass_count)

    def test_real_small_trial_is_deterministic_and_aggregate_only(self) -> None:
        first = run_conditional_pressure_pass_runtime_trial((46200,), current_level_rank="2", max_steps=5000)
        second = run_conditional_pressure_pass_runtime_trial((46200,), current_level_rank="2", max_steps=5000)
        self.assertEqual(first, second)
        self.assertEqual(first.canonical_json_bytes(), second.canonical_json_bytes())
        self.assertEqual(first.requested_game_count, 2)
        self.assertEqual(first.completed_game_count, 2)
        self.assertEqual(first.incomplete_game_count, 0)
        self.assertGreater(first.candidate_conditional_pass_count, 0)
        self.assertEqual(first.candidate_conditional_pass_count, first.candidate_opportunity_count)
        self.assertEqual(first.active_conditional_pass_seed_pair_count, 1)
        serialized = json.dumps(first.to_dict(), sort_keys=True)
        for forbidden in ("46200", "hand_cards", "observation", "action_id", "player_id", "snapshot"):
            self.assertNotIn(forbidden, serialized)

    def test_input_validation_rejects_ambiguous_runs(self) -> None:
        for seeds, kwargs in (
            ((), {}), ((1, 1), {}), ((True,), {}), (("1",), {}), ((1,), {"max_steps": 0}),
        ):
            with self.subTest(seeds=seeds, kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_conditional_pressure_pass_runtime_trial(seeds, **kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
