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
    DeepSeekClientSettings,
    ProviderInput,
    SampleSetStage,
    build_replayable_quality_samples,
    evaluate_quality_sample,
    evaluate_quality_samples,
)
from evaluation.h3_model_probe_fixtures import (
    _RequestRecordingTransport,
    _RecordingDeepSeekClient,
    _complete_opening_hands,
)
from evaluation.strategy_intent_action_quality import RuleRolloutOutcome
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _advisor() -> RAGAdvisor:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "rag"
    return RAGAdvisor(KnowledgeRetriever(KnowledgeBaseLoader(root).load_all_documents()))


class _FakeSSETransport:
    """Offline transport that answers once from IDs found in the real request."""

    def __init__(self, choose: object, *, failure: bool = False, mutate_request: bool = False) -> None:
        self.choose = choose
        self.failure = failure
        self.mutate_request = mutate_request
        self.calls = 0
        self.request_candidate_ids: list[tuple[int, ...]] = []
        self.response_action_ids: list[object] = []
        self.request_envelopes_valid: list[bool] = []

    def __call__(self, request: object, _timeout: float) -> str:
        self.calls += 1
        raw = getattr(request, "data", None)
        try:
            envelope = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            envelope = None
        messages = envelope.get("messages") if isinstance(envelope, dict) else None
        users = [item for item in messages if isinstance(item, dict) and item.get("role") == "user"] if isinstance(messages, list) else []
        prompt = users[0].get("content") if len(users) == 1 else None
        action_ids = _RequestRecordingTransport._candidate_ids(prompt) if isinstance(prompt, str) else None
        self.request_envelopes_valid.append(
            isinstance(envelope, dict)
            and envelope.get("stream") is True
            and len(users) == 1
            and isinstance(prompt, str)
            and action_ids is not None
        )
        if action_ids is None:
            raise OSError("fake_request_invalid")
        self.request_candidate_ids.append(action_ids)
        if self.failure:
            raise TimeoutError("offline provider failure")
        selector = self.choose
        if not callable(selector):
            raise TypeError("fake_selector_invalid")
        action_id = selector(action_ids)
        self.response_action_ids.append(action_id)
        response_content = json.dumps({"action_id": action_id}, separators=(",", ":"))
        chunk = json.dumps({"choices": [{"delta": {"content": response_content}}]})
        if self.mutate_request:
            request.data = raw + b" "  # type: ignore[attr-defined,operator]
        return f"data: {chunk}\n\ndata: [DONE]\n"


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
        self.assertIn(reference_id, sample.final_candidate_ids)
        transport = _FakeSSETransport(lambda candidate_ids: reference_id)

        calls: list[tuple[int, int]] = []
        original_rollout = proxy._rollout

        def rollout(game: object, action_id: object, observer: object, max_steps: int) -> RuleRolloutOutcome:
            self.assertEqual(max_steps, 5000)
            self.assertEqual(game.observe(), sample.observation)  # type: ignore[attr-defined]
            self.assertEqual(game.legal_actions(), sample.legal_actions)  # type: ignore[attr-defined]
            calls.append((id(game), int(action_id)))
            return original_rollout(game, action_id, observer, max_steps)  # type: ignore[arg-type]

        with patch.object(proxy, "_rollout", side_effect=rollout):
            result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        self.assertEqual(len(calls), 1)
        self.assertEqual(transport.calls, 1)
        self.assertTrue(transport.request_envelopes_valid[0])
        self.assertEqual(calls[0][1], transport.response_action_ids[0])
        self.assertTrue(result.same_action_reused)
        self.assertEqual(result.comparison, Comparison.TIE)
        self.assertTrue(result.reference_action_in_model_candidates)
        self.assertTrue(result.selected.completed and result.reference.completed)

    def test_different_actions_use_independent_clones_and_frozen_comparison_order(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)
        original_public = (sample.game_snapshot.observe(), sample.game_snapshot.legal_actions())
        transport = _FakeSSETransport(
            lambda candidate_ids: next(candidate_id for candidate_id in candidate_ids if candidate_id != reference_id)
        )

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
            result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        self.assertEqual(transport.calls, 1)
        self.assertTrue(transport.response_action_ids)
        self.assertNotEqual(transport.response_action_ids[0], reference_id)
        self.assertEqual(len(branch_ids), 2)
        self.assertNotEqual(branch_ids[0], branch_ids[1])
        self.assertEqual(result.comparison, Comparison.SELECTED_BETTER)
        self.assertEqual(result.selected.team_outcome, "win")
        self.assertEqual(result.reference.team_outcome, "loss")
        self.assertEqual((sample.game_snapshot.observe(), sample.game_snapshot.legal_actions()), original_public)

    def test_provider_action_outside_final_candidates_fails_closed_without_rollout(self) -> None:
        sample = self.samples[0]
        raw_ids = {action["action_id"] for action in sample.legal_actions}
        unshown_id = next(action_id for action_id in raw_ids if action_id not in sample.final_candidate_ids)
        transport = _FakeSSETransport(lambda _candidate_ids: unshown_id)

        with patch.object(proxy, "_rollout") as rollout:
            result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(transport.calls, 1)
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
        transport = _FakeSSETransport(lambda candidate_ids: candidate_ids[0])
        original = _RecordingDeepSeekClient._build_structured_prompt

        def drifted_prompt(self: object, **kwargs: object) -> str:
            return original(self, **kwargs) + " "  # type: ignore[arg-type]

        with patch.object(_RecordingDeepSeekClient, "_build_structured_prompt", drifted_prompt):
            result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        self.assertEqual(transport.calls, 0)
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

    def test_all_six_samples_use_injected_transport_and_complete_real_rollouts(self) -> None:
        transport = _FakeSSETransport(lambda candidate_ids: candidate_ids[0])
        settings = DeepSeekClientSettings(
            api_key="offline-test-key",
            base_url="https://offline.invalid",
            model="offline-test-model",
            timeout_seconds=1.0,
            max_retries=0,
        )
        report = evaluate_quality_samples(
            self.sample_set,
            transport=transport,
            client_settings=settings,
            advisor=self.advisor,
        )
        self.assertEqual(len(report.results), 6)
        self.assertEqual(report.completed_sample_count, 6)
        self.assertEqual(report.sample_set_stage, SampleSetStage.READY)
        self.assertTrue(all(result.comparison in set(Comparison) - {Comparison.UNEVALUABLE} for result in report.results))
        self.assertTrue(all(result.reference_action_in_model_candidates for result in report.results))
        self.assertTrue(all(2 <= result.final_candidate_count <= 80 for result in report.results))
        self.assertEqual(transport.calls, 6)
        self.assertEqual(len(transport.request_candidate_ids), 6)
        self.assertTrue(all(transport.request_envelopes_valid))
        self.assertTrue(
            all(set(actual) == set(sample.final_candidate_ids)
                for actual, sample in zip(transport.request_candidate_ids, self.samples))
        )
        serialized = report.to_json()
        for forbidden in (
            "action_id", "hand_cards", "game_snapshot", "prompt", "source_seed",
            "offline-test-key", "offline.invalid", "offline-test-model",
        ):
            self.assertNotIn(forbidden, serialized)
        repeated_transport = _FakeSSETransport(lambda candidate_ids: candidate_ids[0])
        repeated = evaluate_quality_samples(
            self.sample_set,
            transport=repeated_transport,
            client_settings=settings,
            advisor=self.advisor,
        )
        self.assertEqual(repeated.to_json().encode("utf-8"), serialized.encode("utf-8"))
        self.assertEqual(repeated_transport.calls, 6)

    def test_transport_failure_unshown_id_body_mutation_and_zero_call_fail_closed(self) -> None:
        sample = self.samples[0]
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)
        failure_transport = _FakeSSETransport(lambda ids: ids[0], failure=True)
        with patch.object(proxy, "_rollout") as rollout:
            failed = evaluate_quality_sample(sample, transport=failure_transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(failure_transport.calls, 1)
        self.assertEqual(failed.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(failed.failure_code, "injected_transport_failure")

        mutating_transport = _FakeSSETransport(lambda ids: ids[0], mutate_request=True)
        with patch.object(proxy, "_rollout") as rollout:
            mutated = evaluate_quality_sample(sample, transport=mutating_transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(mutating_transport.calls, 1)
        self.assertEqual(mutated.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(mutated.failure_code, "request_body_mutated")

        shortcut_transport = _FakeSSETransport(lambda ids: ids[0])
        with patch("agents.opening_strategy.OpeningFormulaStrategy.select_action", return_value=reference_id):
            with patch.object(proxy, "_rollout") as rollout:
                shortcut = evaluate_quality_sample(sample, transport=shortcut_transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(shortcut_transport.calls, 0)
        self.assertEqual(shortcut.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(shortcut.failure_code, "model_path_not_reached")

    def test_prompt_candidate_drift_fails_before_injected_transport_or_rollout(self) -> None:
        sample = self.samples[0]
        transport = _FakeSSETransport(lambda ids: ids[0])
        original = _RecordingDeepSeekClient._build_structured_prompt

        def drift_candidate(self: object, **kwargs: object) -> str:
            prompt = original(self, **kwargs)  # type: ignore[arg-type]
            action_ids = _RequestRecordingTransport._candidate_ids(prompt)
            if not action_ids:
                raise AssertionError("fixture_prompt_candidates_missing")
            old_id = action_ids[0]
            new_id = max(action_ids) + 10000
            old_line = f"#{old_id} action_id={old_id} |"
            new_line = f"#{new_id} action_id={new_id} |"
            self.final_prompt = prompt.replace(old_line, new_line, 1)  # type: ignore[attr-defined]
            return self.final_prompt  # type: ignore[attr-defined]

        with patch.object(_RecordingDeepSeekClient, "_build_structured_prompt", drift_candidate):
            with patch.object(proxy, "_rollout") as rollout:
                result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(transport.calls, 0)
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(result.failure_code, "request_binding_invalid")

    def test_duplicate_suggest_call_fails_closed_before_rollout(self) -> None:
        sample = self.samples[0]
        transport = _FakeSSETransport(lambda ids: ids[0])
        original = _RecordingDeepSeekClient.suggest_action_id

        def doubled(self: object, **kwargs: object) -> object:
            result = original(self, **kwargs)  # type: ignore[arg-type]
            original(self, **kwargs)  # type: ignore[arg-type]
            return result

        with patch.object(_RecordingDeepSeekClient, "suggest_action_id", doubled):
            with patch.object(proxy, "_rollout") as rollout:
                result = evaluate_quality_sample(sample, transport=transport, advisor=self.advisor)
        rollout.assert_not_called()
        self.assertEqual(transport.calls, 2)
        self.assertEqual(result.comparison, Comparison.UNEVALUABLE)
        self.assertEqual(result.failure_code, "transport_call_count_invalid")

    def test_transport_binding_keeps_raw_response_client_result_and_source_in_memory(self) -> None:
        sample = self.samples[0]
        transport = _FakeSSETransport(lambda ids: ids[0])
        selection = proxy._invoke_model_path(
            sample.game_snapshot,
            sample.observation,
            sample.legal_actions,
            None,
            self.advisor,
            transport=transport,
        )
        self.assertIsNone(selection.failure_code)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(selection.transport_call_count, 1)
        self.assertEqual(selection.raw_response_action_id, transport.response_action_ids[0])
        self.assertEqual(selection.client_returned_action_id, transport.response_action_ids[0])
        self.assertEqual(selection.action_id, transport.response_action_ids[0])
        self.assertEqual(selection.decision_source, "model")
        self.assertIn(selection.action_id, selection.final_action_ids)

    def test_transport_api_refuses_retry_budget_and_hides_client_configuration(self) -> None:
        settings = DeepSeekClientSettings("offline-key", "https://offline.invalid", "offline-model")
        self.assertNotIn("offline-key", repr(settings))
        self.assertNotIn("offline.invalid", repr(settings))
        with self.assertRaisesRegex(ValueError, "client_settings_invalid"):
            DeepSeekClientSettings("offline-key", "https://offline.invalid", "offline-model", max_retries=1)


if __name__ == "__main__":
    unittest.main()
