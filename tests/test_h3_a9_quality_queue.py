"""Deterministic offline qualification for the independent H3-A9 queue."""

from __future__ import annotations

from collections import Counter
import json
import random
import unittest

from agents.base import require_legal_action_id
from agents.game_phase import classify_game_phase
from agents.rag_advisor import RAGAdvisor
from agents.rule_based_ai import RuleBasedAIAgent
from engine.cards import build_double_deck, card_to_token
from engine.game import GuanDanGame
from evaluation.action_quality_proxy import (
    Comparison,
    DeepSeekClientSettings,
    SampleSetStage,
    build_replayable_quality_samples,
    evaluate_quality_samples,
)
from evaluation.h3_a9_quality_queue import H3_A9_SEEDS, build_h3_a9_quality_samples
from evaluation.h3_model_probe_fixtures import _RequestRecordingTransport, _advisor


class _BoundFakeTransport:
    """Return a visible non-reference ID from each real client request."""

    def __init__(self, reference_ids: tuple[int, ...]) -> None:
        self.reference_ids = iter(reference_ids)
        self.calls = 0
        self.candidate_ids: list[tuple[int, ...]] = []
        self.returned_ids: list[int] = []
        self.envelopes_valid: list[bool] = []

    def __call__(self, request: object, _timeout: float) -> str:
        self.calls += 1
        raw = getattr(request, "data", None)
        try:
            envelope = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            envelope = None
        messages = envelope.get("messages") if isinstance(envelope, dict) else None
        users = (
            [message for message in messages if isinstance(message, dict) and message.get("role") == "user"]
            if isinstance(messages, list)
            else []
        )
        prompt = users[0].get("content") if len(users) == 1 else None
        candidate_ids = _RequestRecordingTransport._candidate_ids(prompt) if isinstance(prompt, str) else None
        valid = (
            isinstance(envelope, dict)
            and envelope.get("stream") is True
            and len(users) == 1
            and isinstance(prompt, str)
            and candidate_ids is not None
        )
        self.envelopes_valid.append(bool(valid))
        if not valid or candidate_ids is None:
            raise OSError("offline_request_invalid")
        reference_id = next(self.reference_ids)
        selected_id = next(action_id for action_id in candidate_ids if action_id != reference_id)
        self.candidate_ids.append(candidate_ids)
        self.returned_ids.append(selected_id)
        content = json.dumps({"action_id": selected_id}, separators=(",", ":"))
        chunk = json.dumps({"choices": [{"delta": {"content": content}}]})
        return f"data: {chunk}\n\ndata: [DONE]\n"


def _state_signature(observation: dict[str, object], legal_actions: list[dict[str, object]]) -> str:
    return json.dumps([observation, legal_actions], sort_keys=True, separators=(",", ":"))


def _reference_id(sample: object) -> int:
    reference = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)  # type: ignore[attr-defined]
    return require_legal_action_id(reference, sample.legal_actions)  # type: ignore[attr-defined,arg-type]


class H3A9QualityQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.advisor: RAGAdvisor = _advisor()
        cls.sample_set = build_h3_a9_quality_samples(advisor=cls.advisor)
        if not cls.sample_set.ready:
            raise AssertionError("h3_a9_offline_queue_not_ready")
        cls.samples = cls.sample_set.samples

    def test_queue_uses_frozen_layer_seed_and_step_order(self) -> None:
        self.assertEqual(
            tuple(sample.name for sample in self.samples),
            ("opening_1", "opening_2", "midgame_1", "midgame_2", "endgame_1", "endgame_2"),
        )
        self.assertEqual(tuple(sample.source_seed for sample in self.samples), (920, 921, 922, 923, 924, 925))
        self.assertTrue(all(sample.source_seed in H3_A9_SEEDS for sample in self.samples))
        self.assertEqual(len({sample.source_seed for sample in self.samples}), 6)
        self.assertEqual(tuple(sample.observation["current_round"]["step_no"] for sample in self.samples), (0, 4, 8, 8, 64, 64))  # type: ignore[index]
        self.assertEqual(tuple(sample.phase for sample in self.samples[:2]), ("opening", "opening"))
        self.assertEqual(tuple(sample.phase for sample in self.samples[2:4]), ("midgame", "midgame"))
        self.assertEqual(tuple(sample.phase for sample in self.samples[4:]), ("critical_endgame", "near_open_endgame"))
        self.assertEqual(
            tuple((sample.canonical_candidate_count, sample.final_candidate_count) for sample in self.samples),
            ((77, 53), (3, 3), (25, 13), (11, 11), (8, 8), (9, 9)),
        )

    def test_every_sample_replays_from_a_complete_seeded_opening(self) -> None:
        deck_counts = Counter(card_to_token(card) for card in build_double_deck())
        for sample in self.samples:
            seed = sample.source_seed
            self.assertIsNotNone(seed)
            shuffled_deck = build_double_deck()
            random.Random(seed).shuffle(shuffled_deck)  # type: ignore[arg-type]
            seeded_hands = tuple(
                tuple(shuffled_deck[index * 27 : (index + 1) * 27])
                for index in range(4)
            )
            self.assertEqual(tuple(len(hand) for hand in seeded_hands), (27, 27, 27, 27))
            self.assertEqual(
                Counter(card_to_token(card) for hand in seeded_hands for card in hand),
                deck_counts,
            )
            start = GuanDanGame(seed=seed, current_level_rank="2")  # type: ignore[arg-type]
            initial = start.reset()
            self.assertEqual(initial["my_info"]["player_id"], 1)  # type: ignore[index]
            self.assertEqual(initial["my_info"]["hand_count"], 27)  # type: ignore[index]
            self.assertEqual(len(initial["my_info"]["hand_cards"]), 27)  # type: ignore[index]
            initial_hand_counts = Counter(initial["my_info"]["hand_cards"])  # type: ignore[index]
            self.assertTrue(
                all(count <= deck_counts[token] for token, count in initial_hand_counts.items())
            )
            self.assertEqual(
                initial_hand_counts,
                Counter(card_to_token(card) for card in seeded_hands[0]),
            )
            self.assertEqual(
                tuple(item["hand_count"] for item in initial["other_players"]),  # type: ignore[index]
                (27, 27, 27),
            )
            self.assertEqual(sum([initial["my_info"]["hand_count"], *(item["hand_count"] for item in initial["other_players"])]), 108)  # type: ignore[index]
            self.assertEqual(initial["current_round"]["step_no"], 0)  # type: ignore[index]
            self.assertEqual(initial["current_round"]["current_level_rank"], "2")  # type: ignore[index]
            self.assertEqual(initial["history"]["actions"], [])  # type: ignore[index]

            agents = {player: RuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
            target_step = sample.observation["current_round"]["step_no"]  # type: ignore[index]
            for _ in range(target_step):
                observation = start.observe()
                actions = start.legal_actions()
                player = observation["my_info"]["player_id"]  # type: ignore[index]
                action_id = require_legal_action_id(agents[player].select_action(observation, actions), actions)
                self.assertFalse(start.step(action_id)["game_over"])
            self.assertEqual(start.observe(), sample.observation)
            self.assertEqual(start.legal_actions(), sample.legal_actions)
            self.assertEqual(classify_game_phase(start.observe()).phase, sample.phase)
            self.assertEqual(start.observe()["my_info"]["player_id"], 1)  # type: ignore[index]
            self.assertGreaterEqual(
                sum(action.get("declared_pattern") != "pass" for action in start.legal_actions()),
                2,
            )

    def test_states_and_complete_action_signatures_do_not_overlap_h3_a8(self) -> None:
        prior = build_replayable_quality_samples(advisor=self.advisor)
        self.assertTrue(prior.ready)
        prior_signatures = {
            _state_signature(sample.observation, sample.legal_actions)
            for sample in prior.samples
        }
        current_signatures = [
            _state_signature(sample.observation, sample.legal_actions)
            for sample in self.samples
        ]
        self.assertEqual(len(set(current_signatures)), 6)
        self.assertTrue(set(current_signatures).isdisjoint(prior_signatures))
        prior_seeds = {sample.source_seed for sample in prior.samples if sample.source_seed is not None}
        self.assertTrue({sample.source_seed for sample in self.samples}.isdisjoint(prior_seeds))

    def test_six_real_client_fake_transport_calls_bind_candidates_and_complete_rollouts(self) -> None:
        references = tuple(_reference_id(sample) for sample in self.samples)
        for sample, reference_id in zip(self.samples, references):
            self.assertIn(reference_id, sample.final_candidate_ids)
            self.assertLessEqual(sample.final_candidate_count, 80)
            self.assertEqual(sample.final_candidate_count, len(set(sample.final_candidate_ids)))
            canonical_ids = {action["action_id"] for action in sample.legal_actions}
            self.assertTrue(set(sample.final_candidate_ids).issubset(canonical_ids))

        transport = _BoundFakeTransport(references)
        settings = DeepSeekClientSettings(
            "offline-a9-key",
            "https://offline.invalid",
            "offline-a9-model",
            timeout_seconds=1.0,
            max_retries=0,
        )
        report = evaluate_quality_samples(
            self.sample_set,
            transport=transport,
            client_settings=settings,
            advisor=self.advisor,
        )
        self.assertEqual(transport.calls, 6)
        self.assertEqual(tuple(len(ids) for ids in transport.candidate_ids), tuple(s.final_candidate_count for s in self.samples))
        self.assertTrue(all(transport.envelopes_valid))
        self.assertTrue(
            all(set(ids) == set(sample.final_candidate_ids) for ids, sample in zip(transport.candidate_ids, self.samples))
        )
        self.assertTrue(all(action_id in ids for action_id, ids in zip(transport.returned_ids, transport.candidate_ids)))
        self.assertEqual(report.completed_sample_count, 6)
        self.assertTrue(all(result.failure_code is None for result in report.results))
        self.assertTrue(all(result.reference_action_in_model_candidates for result in report.results))
        self.assertTrue(all(result.selected.completed and result.reference.completed for result in report.results))
        self.assertTrue(all(not result.same_action_reused for result in report.results))
        self.assertNotIn(Comparison.UNEVALUABLE, {result.comparison for result in report.results})
        safe_json = report.to_json()
        for forbidden in ("action_id", "hand_cards", "game_snapshot", "prompt", "source_seed", "offline-a9-key", "offline.invalid"):
            self.assertNotIn(forbidden, safe_json)

    def test_queue_and_fake_proxy_report_are_repeatable(self) -> None:
        repeated = build_h3_a9_quality_samples(advisor=self.advisor)
        self.assertTrue(repeated.ready)
        self.assertEqual(
            json.dumps(self.sample_set.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8"),
            json.dumps(repeated.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )
        self.assertEqual(
            tuple((sample.source_seed, sample.final_candidate_ids) for sample in self.samples),
            tuple((sample.source_seed, sample.final_candidate_ids) for sample in repeated.samples),
        )
        self.assertNotIn("source_seed", json.dumps(self.sample_set.to_dict(), sort_keys=True))
        references = tuple(_reference_id(sample) for sample in repeated.samples)
        first_transport = _BoundFakeTransport(references)
        second_transport = _BoundFakeTransport(references)
        settings = DeepSeekClientSettings(
            "offline-a9-key",
            "https://offline.invalid",
            "offline-a9-model",
            timeout_seconds=1.0,
            max_retries=0,
        )
        first_report = evaluate_quality_samples(
            self.sample_set,
            transport=first_transport,
            client_settings=settings,
            advisor=self.advisor,
        )
        second_report = evaluate_quality_samples(
            repeated,
            transport=second_transport,
            client_settings=settings,
            advisor=self.advisor,
        )
        self.assertEqual(first_transport.calls, 6)
        self.assertEqual(second_transport.calls, 6)
        self.assertEqual(first_report.to_json().encode("utf-8"), second_report.to_json().encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
