"""Offline contracts for the fixed same-state action-quality proxy."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from agents.base import require_legal_action_id
from agents.deepseek_client import DeepSeekClient
from agents.game_phase import classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.cards import build_double_deck, card_to_token
from evaluation import action_quality_proxy as proxy
from evaluation.action_quality_proxy import (
    ActionIdProvider,
    Comparison,
    ProviderInput,
    SampleSetStage,
    build_replayable_quality_samples,
    evaluate_quality_sample,
    evaluate_quality_samples,
)
from evaluation.h3_model_probe_fixtures import _RecordingDeepSeekClient, _complete_opening_hands
from evaluation.strategy_intent_action_quality import RuleRolloutOutcome
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _advisor() -> RAGAdvisor:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "rag"
    return RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(root).load_all_documents()))


class ActionQualityProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.advisor = _advisor()
        cls.sample_set = build_replayable_quality_samples(advisor=cls.advisor)
        if not cls.sample_set.ready:
            raise AssertionError("fixed_offline_sample_qualification_failed")
        cls.samples = cls.sample_set.samples

    def test_fixed_six_samples_are_physical_replayable_and_phase_stable(self) -> None:
        self.assertEqual(
            tuple(sample.name for sample in self.samples),
            (
                "opening_low_cost_single",
                "opening_neutral_soft_pair",
                "midgame_1",
                "midgame_2",
                "endgame_1",
                "endgame_2",
            ),
        )
        self.assertEqual(tuple(sample.phase for sample in self.samples[:2]), ("opening", "opening"))
        self.assertEqual(tuple(sample.phase for sample in self.samples[2:4]), ("midgame", "midgame"))
        self.assertTrue(all(sample.phase in {"endgame", "near_open_endgame", "critical_endgame"} for sample in self.samples[4:]))
        self.assertEqual(
            tuple(sample.observation["current_round"]["step_no"] for sample in self.samples),  # type: ignore[index]
            (0, 0, 16, 24, 40, 48),
        )
        self.assertTrue(
            all(sample.observation["current_round"]["current_level_rank"] == "2" for sample in self.samples)  # type: ignore[index]
        )
        self.assertEqual(len({sample.source_seed for sample in self.samples[2:]}), 4)
        self.assertEqual(tuple(sample.source_seed for sample in self.samples[2:]), (900, 901, 902, 903))
        self.assertTrue(all(sample.source_seed is not None and 900 <= sample.source_seed <= 919 for sample in self.samples[2:]))
        self.assertEqual(
            tuple((sample.canonical_candidate_count, sample.final_candidate_count) for sample in self.samples),
            ((53, 21), (83, 50), (6, 6), (6, 6), (9, 9), (8, 4)),
        )
        for sample in self.samples:
            observation = sample.game_snapshot.observe()
            legal_actions = sample.game_snapshot.legal_actions()
            self.assertEqual(observation, sample.observation)
            self.assertEqual(legal_actions, sample.legal_actions)
            self.assertEqual(classify_game_phase(observation).phase, sample.phase)
            self.assertEqual(observation["my_info"]["player_id"], 1)  # type: ignore[index]
            self.assertGreaterEqual(sample.canonical_candidate_count, 2)
            self.assertGreaterEqual(sample.final_candidate_count, 2)
            self.assertLessEqual(sample.final_candidate_count, 80)
            self.assertGreaterEqual(
                sum(action.get("declared_pattern") != "pass" for action in legal_actions),
                2,
            )

    def test_opening_snapshots_are_complete_double_deck_initial_deals(self) -> None:
        full_deck = Counter(card_to_token(card) for card in build_double_deck())
        for sample in self.samples[:2]:
            observation = sample.observation
            my_info = observation["my_info"]
            current_round = observation["current_round"]
            history = observation["history"]
            other_players = observation["other_players"]
            self.assertEqual(my_info["hand_count"], 27)  # type: ignore[index]
            self.assertEqual(current_round["step_no"], 0)  # type: ignore[index]
            self.assertEqual(history["actions"], [])  # type: ignore[index]
            self.assertEqual(history["finish_order"], [])  # type: ignore[index]
            self.assertEqual(sum([my_info["hand_count"], *(item["hand_count"] for item in other_players)]), 108)  # type: ignore[index]
            deal = _complete_opening_hands(tuple(my_info["hand_cards"]))  # type: ignore[index]
            self.assertEqual(Counter(token for hand in deal for token in hand), full_deck)

    def test_sample_set_summary_is_byte_stable_and_contains_no_private_payload(self) -> None:
        repeated = build_replayable_quality_samples(advisor=self.advisor)
        first_json = json.dumps(self.sample_set.to_dict(), sort_keys=True, separators=(",", ":"))
        repeated_json = json.dumps(repeated.to_dict(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_json.encode("utf-8"), repeated_json.encode("utf-8"))
        self.assertEqual(
            tuple(sample.source_seed for sample in self.sample_set.samples),
            tuple(sample.source_seed for sample in repeated.samples),
        )
        self.assertEqual(
            tuple(sample.final_candidate_ids for sample in self.sample_set.samples),
            tuple(sample.final_candidate_ids for sample in repeated.samples),
        )
        self.assertEqual(self.sample_set.stage, SampleSetStage.READY)
        for forbidden in ("action_id", "hand_cards", "game_snapshot", "prompt", "source_seed"):
            self.assertNotIn(forbidden, first_json)

    def test_same_action_reuses_one_frozen_rollout_and_reports_visibility(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)
        visible: list[bool] = []

        def provider(request: ProviderInput) -> object:
            candidate_ids = {action["action_id"] for action in request.final_candidates}
            visible.append(reference_id in candidate_ids)
            self.assertNotIn("game_snapshot", request.__dataclass_fields__)
            self.assertNotIn("hand_cards", request.observation["other_players"][0])  # type: ignore[index]
            return reference_id

        calls: list[tuple[int, int]] = []

        def rollout(game: object, action_id: object, observer: object, max_steps: int) -> RuleRolloutOutcome:
            self.assertEqual(max_steps, 5000)
            calls.append((id(game), int(action_id)))
            return RuleRolloutOutcome("draw", 1, 5, 77, True, ())

        with patch.object(proxy, "_rollout", side_effect=rollout):
            result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        self.assertEqual(len(calls), 1)
        self.assertTrue(result.same_action_reused)
        self.assertEqual(result.comparison, Comparison.TIE)
        self.assertEqual(result.reference_action_in_model_candidates, visible[0])
        self.assertTrue(result.selected.completed and result.reference.completed)

    def test_different_actions_use_independent_clones_and_frozen_comparison_order(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)
        original_public = (sample.game_snapshot.observe(), sample.game_snapshot.legal_actions())
        seen_candidate_ids: list[int] = []

        def provider(request: ProviderInput) -> object:
            for action in request.final_candidates:
                candidate_id = action.get("action_id")
                if type(candidate_id) is int and candidate_id != reference_id:
                    seen_candidate_ids.append(candidate_id)
                    return candidate_id
            return reference_id

        branch_ids: list[int] = []
        outcomes = iter(
            (
                RuleRolloutOutcome("win", 2, 4, 81, True, ()),
                RuleRolloutOutcome("loss", 0, 7, 91, True, ()),
            )
        )

        def rollout(game: GuanDanGame, action_id: object, observer: object, max_steps: int) -> RuleRolloutOutcome:
            branch_ids.append(id(game))
            self.assertEqual(max_steps, 5000)
            if len(branch_ids) == 2:
                self.assertEqual((game.observe(), game.legal_actions()), original_public)
            legal_id = require_legal_action_id(action_id, game.legal_actions())  # type: ignore[arg-type]
            game.step(legal_id)
            return next(outcomes)

        with patch.object(proxy, "_rollout", side_effect=rollout):
            result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        self.assertTrue(seen_candidate_ids)
        self.assertEqual(len(branch_ids), 2)
        self.assertNotEqual(branch_ids[0], branch_ids[1])
        self.assertEqual(result.comparison, Comparison.SELECTED_BETTER)
        self.assertEqual(result.selected.team_outcome, "win")
        self.assertEqual(result.reference.team_outcome, "loss")
        self.assertEqual((sample.game_snapshot.observe(), sample.game_snapshot.legal_actions()), original_public)

    def test_provider_action_outside_final_candidates_fails_closed_without_rollout(self) -> None:
        sample = self.samples[0]
        provider_calls = 0

        def provider(request: ProviderInput) -> object:
            nonlocal provider_calls
            provider_calls += 1
            displayed = {action["action_id"] for action in request.final_candidates}
            return next(
                action["action_id"]
                for action in request.legal_actions
                if action["action_id"] not in displayed
            )

        with patch.object(proxy, "_rollout") as rollout:
            result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(provider_calls, 1)
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(result.failure_code, "provider_action_not_in_final_candidates")
        self.assertGreaterEqual(result.final_candidate_count, 2)
        self.assertFalse(result.selected.completed)

    def test_quality_comparison_uses_team_outcome_then_rank_sum_not_steps(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)

        def provider(request: ProviderInput) -> object:
            return next(
                action["action_id"]
                for action in request.final_candidates
                if action["action_id"] != reference_id
            )

        cases = (
            (
                RuleRolloutOutcome("draw", 1, 2, 999, True, ()),
                RuleRolloutOutcome("win", 2, 8, 2, True, ()),
                Comparison.REFERENCE_BETTER,
            ),
            (
                RuleRolloutOutcome("draw", 1, 3, 999, True, ()),
                RuleRolloutOutcome("draw", 1, 4, 2, True, ()),
                Comparison.SELECTED_BETTER,
            ),
            (
                RuleRolloutOutcome("draw", 1, 3, 1, True, ()),
                RuleRolloutOutcome("draw", 1, 3, 900, True, ()),
                Comparison.TIE,
            ),
        )
        for selected, reference, expected in cases:
            with self.subTest(expected=expected.value):
                with patch.object(proxy, "_rollout", side_effect=(selected, reference)) as rollout:
                    result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
                self.assertEqual(rollout.call_count, 2)
                self.assertEqual(result.comparison, expected)

    def test_failed_or_over_limit_rollout_is_unevaluable(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)

        def provider(request: ProviderInput) -> object:
            return next(
                action["action_id"]
                for action in request.final_candidates
                if action["action_id"] != reference_id
            )

        with patch.object(
            proxy,
            "_rollout",
            return_value=RuleRolloutOutcome("", 0, 0, 5000, False, ("rollout_step_limit_reached",)),
        ) as rollout:
            result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        self.assertEqual(rollout.call_count, 2)
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(result.failure_code, "rollout_incomplete")
        self.assertFalse(result.selected.completed or result.reference.completed)
        with patch.object(
            proxy,
            "_rollout",
            return_value=RuleRolloutOutcome("win", 2, 3, 5001, True, ()),
        ):
            over_limit = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        self.assertEqual(over_limit.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(over_limit.failure_code, "rollout_step_count_invalid")

    def test_request_body_prompt_drift_fails_closed_before_provider(self) -> None:
        sample = self.samples[0]
        provider_calls = 0
        original = _RecordingDeepSeekClient._build_structured_prompt

        def drifted_prompt(self: object, **kwargs: object) -> str:
            return original(self, **kwargs) + " "  # type: ignore[arg-type]

        def provider(_request: ProviderInput) -> object:
            nonlocal provider_calls
            provider_calls += 1
            return 1

        with patch.object(_RecordingDeepSeekClient, "_build_structured_prompt", drifted_prompt):
            result = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        self.assertEqual(provider_calls, 0)
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(result.failure_code, "request_binding_invalid")

    def test_snapshot_mismatch_fails_before_any_provider_call(self) -> None:
        sample = self.samples[0]
        altered_observation = dict(sample.observation)
        altered_observation["untrusted_marker"] = True
        malformed = proxy.ReplayableQualitySample(
            name=sample.name,
            phase=sample.phase,
            canonical_candidate_count=sample.canonical_candidate_count,
            final_candidate_count=sample.final_candidate_count,
            observation=altered_observation,
            legal_actions=sample.legal_actions,
            game_snapshot=sample.game_snapshot,
            source_seed=sample.source_seed,
        )
        provider_calls = 0

        def provider(_request: ProviderInput) -> object:
            nonlocal provider_calls
            provider_calls += 1
            return 1

        result = evaluate_quality_sample(malformed, provider, advisor=self.advisor)
        self.assertEqual(provider_calls, 0)
        self.assertEqual(result.failure_code, "snapshot_public_mismatch")
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)

    def test_candidate_order_drift_fails_closed_without_replacing_sample(self) -> None:
        sample = self.samples[0]
        altered = replace(sample, final_candidate_ids=tuple(reversed(sample.final_candidate_ids)))
        provider_calls = 0

        def provider(request: ProviderInput) -> object:
            nonlocal provider_calls
            provider_calls += 1
            return request.final_candidates[0].get("action_id")

        with patch.object(proxy, "_rollout") as rollout:
            result = evaluate_quality_sample(altered, provider, advisor=self.advisor)
        self.assertEqual(provider_calls, 1)
        rollout.assert_not_called()
        self.assertEqual(result.failure_code, "final_candidate_set_changed")
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)

    def test_real_rollout_reruns_produce_byte_identical_safe_output(self) -> None:
        sample = self.samples[0]

        def provider(request: ProviderInput) -> object:
            return RuleBasedAIAgent(player_id=1).select_action(request.observation, request.legal_actions)

        first = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        second = evaluate_quality_sample(sample, provider, advisor=self.advisor)
        first_bytes = json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        second_bytes = json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(first.comparison, Comparison.TIE)
        self.assertTrue(first.selected.completed)
        for forbidden in ("action_id", "hand_cards", "game_snapshot", "prompt", "api_key", "offline.invalid"):
            self.assertNotIn(forbidden, first_bytes.decode("utf-8"))

    def test_all_six_samples_run_through_the_production_offline_client_path(self) -> None:
        report_outcome = RuleRolloutOutcome("draw", 1, 5, 123, True, ())

        def provider(request: ProviderInput) -> object:
            return request.final_candidates[0].get("action_id")

        with patch.object(proxy, "_rollout", return_value=report_outcome):
            report = evaluate_quality_samples(self.sample_set, provider, advisor=self.advisor)
        self.assertEqual(len(report.results), 6)
        self.assertEqual(report.completed_sample_count, 6)
        self.assertEqual(report.sample_set_stage, SampleSetStage.READY)
        self.assertTrue(all(result.comparison in set(Comparison) - {Comparison.UNEVALUABLE} for result in report.results))
        self.assertTrue(all(2 <= result.final_candidate_count <= 80 for result in report.results))
        serialized = report.to_json()
        for forbidden in ("action_id", "hand_cards", "game_snapshot", "prompt", "source_seed", "offline.invalid"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
