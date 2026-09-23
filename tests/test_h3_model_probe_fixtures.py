"""No-network regressions for the reproducible H3 model-probe qualification."""

from collections import Counter
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient, DeepSeekSuggestion
from engine.cards import build_double_deck, card_to_token
from evaluation.h3_model_probe_fixtures import (
    ProbeFixture,
    QualificationStage,
    SCENARIO_NAMES,
    _NoNetworkTransport,
    _RecordingDeepSeekClient,
    _advisor,
    _complete_opening_hands,
    _game,
    _run_projection,
    build_h3_model_probe_fixtures,
    qualify_h3_model_probe_fixture,
    qualify_h3_model_probe_fixtures,
)


class _EmptyRAGAdvisor:
    def get_rag_context(self, **_kwargs: object) -> dict[str, object]:
        return {"scene_tags": {}, "rule_hits": [], "experience_hits": [], "query": ""}


class _WrongSceneRAGAdvisor:
    def __init__(self) -> None:
        self._delegate = _advisor()

    def get_rag_context(self, **kwargs: object) -> dict[str, object]:
        context = self._delegate.get_rag_context(**kwargs)
        tags = dict(context.get("scene_tags", {}))
        tags["scene"] = "follow_response"
        return {**context, "scene_tags": tags}


class _IrrelevantHitsRAGAdvisor:
    def __init__(self) -> None:
        self._delegate = _advisor()

    def get_rag_context(self, **kwargs: object) -> dict[str, object]:
        context = self._delegate.get_rag_context(**kwargs)
        hits = []
        for hit in context.get("experience_hits", []):
            if isinstance(hit, dict):
                metadata = {**dict(hit.get("metadata", {})), "scene": "follow_response"}
                hits.append({**hit, "metadata": metadata})
        return {**context, "experience_hits": hits}


class _MissingMarkerClient(_RecordingDeepSeekClient):
    def _build_structured_prompt(self, **kwargs: object) -> str:
        self.final_prompt = super()._build_structured_prompt(**kwargs).replace("【模型前建议】", "【缺失建议】")
        return self.final_prompt


class _MissingContrastClient(_RecordingDeepSeekClient):
    def _build_structured_prompt(self, **kwargs: object) -> str:
        self.final_prompt = super()._build_structured_prompt(**kwargs).replace("【公开关系对照】", "【缺失对照】")
        return self.final_prompt


class _MissingSoftEvidenceClient(_RecordingDeepSeekClient):
    def _build_structured_prompt(self, **kwargs: object) -> str:
        prompt = super()._build_structured_prompt(**kwargs)
        self.final_prompt = prompt.replace("- 可撤回软假设：", "- 已移除软假设：")
        return self.final_prompt


class _MismatchedCandidateClient(_RecordingDeepSeekClient):
    def _build_structured_prompt(self, **kwargs: object) -> str:
        prompt = super()._build_structured_prompt(**kwargs)
        self.final_actions = self.final_actions[1:]
        return prompt


class _ReturnedOnlyMissingMarkerClient(_RecordingDeepSeekClient):
    def _build_structured_prompt(self, **kwargs: object) -> str:
        return super()._build_structured_prompt(**kwargs).replace("【模型前建议】", "【缺失建议】")


class _BadJsonTransport(_NoNetworkTransport):
    def __call__(self, request: object, timeout: float) -> str:
        request.data = b"{"  # type: ignore[attr-defined]
        return super().__call__(request, timeout)


class _MissingUserTransport(_NoNetworkTransport):
    def __call__(self, request: object, timeout: float) -> str:
        envelope = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        envelope["messages"] = [envelope["messages"][0]]
        request.data = json.dumps(envelope).encode("utf-8")  # type: ignore[attr-defined]
        return super().__call__(request, timeout)


class _DuplicateTransport(_NoNetworkTransport):
    def __call__(self, request: object, timeout: float) -> str:
        response = super().__call__(request, timeout)
        super().__call__(request, timeout)
        return response


class _CustomTransportClient(_RecordingDeepSeekClient):
    transport_type = _NoNetworkTransport

    def _new_transport(self) -> _NoNetworkTransport:
        return self.transport_type()


class _BadJsonClient(_CustomTransportClient):
    transport_type = _BadJsonTransport


class _MissingUserClient(_CustomTransportClient):
    transport_type = _MissingUserTransport


class _DuplicateTransportClient(_CustomTransportClient):
    transport_type = _DuplicateTransport


class _ZeroTransportClient(_RecordingDeepSeekClient):
    def suggest_action_id(self, **kwargs: object) -> object:
        self.calls += 1
        self.kwargs = dict(kwargs)
        actions = kwargs.get("prompt_actions")
        if not isinstance(actions, list) or not actions or not isinstance(actions[0], dict):
            return DeepSeekSuggestion(None, None)
        action_id = actions[0].get("action_id")
        return DeepSeekSuggestion(action_id if type(action_id) is int else None, None)


class _FailingClient(_RecordingDeepSeekClient):
    def suggest_action_id(self, **kwargs: object) -> object:
        raise RuntimeError("offline-client-failure")


class H3ModelProbeFixtureTests(unittest.TestCase):
    def test_frozen_engine_backed_fixtures_pass_every_public_projection_stage(self) -> None:
        fixtures = build_h3_model_probe_fixtures()
        self.assertEqual(tuple(fixture.name for fixture in fixtures), SCENARIO_NAMES)
        results = qualify_h3_model_probe_fixtures()

        self.assertEqual(tuple(result.name for result in results), SCENARIO_NAMES)
        self.assertTrue(all(result.stage is QualificationStage.READY for result in results))
        for result in results:
            with self.subTest(name=result.name):
                self.assertGreater(result.candidate_count, 0)
                self.assertGreater(result.final_candidate_count, 0)
                self.assertLessEqual(result.final_candidate_count, 80)
                self.assertTrue(result.recommendation_ready)
                self.assertTrue(result.prompt_markers_ready)
                self.assertTrue(result.source_is_model)
        for name in ("bomb_residual", "pair_cleanup"):
            self.assertTrue(next(result for result in results if result.name == name).contrast_ready)
        for name in ("low_cost_single", "neutral_soft_pair", "bomb_wildcard_soft"):
            self.assertTrue(next(result for result in results if result.name == name).soft_marker_ready)

    def test_malformed_fixture_fails_at_a_fixed_early_stage_without_projection(self) -> None:
        baseline = build_h3_model_probe_fixtures()[0]
        invalid_name = ProbeFixture("unknown", baseline.observation, baseline.legal_actions)
        empty_actions = ProbeFixture(baseline.name, baseline.observation, [])

        self.assertEqual(
            qualify_h3_model_probe_fixture(invalid_name).stage,
            QualificationStage.SCENARIO_CONSTRUCTION,
        )
        self.assertEqual(
            qualify_h3_model_probe_fixture(empty_actions).stage,
            QualificationStage.PUBLIC_CANONICAL,
        )

    def test_qualification_is_stable_and_does_not_load_dotenv_or_call_a_real_client(self) -> None:
        with patch("config.load_dotenv", side_effect=AssertionError("dotenv must remain untouched")):
            first = qualify_h3_model_probe_fixtures()
            second = qualify_h3_model_probe_fixtures()
        self.assertEqual(first, second)

    def test_actual_client_assembly_is_the_qualification_source_and_stays_offline(self) -> None:
        for fixture in build_h3_model_probe_fixtures():
            with self.subTest(name=fixture.name):
                agent, client, chosen = _run_projection(fixture, _advisor())
                self.assertTrue(agent.opening_formula_enabled)
                self.assertEqual(client.calls, 1)
                self.assertEqual(client.transport.calls, 1)
                self.assertTrue(client.transport.envelope_valid)
                self.assertEqual(client.final_prompt, client.transport.user_prompt)
                self.assertEqual(client.displayed_actions, client.final_actions)
                self.assertEqual(
                    {item["action_id"] for item in client.displayed_actions},
                    set(client.transport.prompt_action_ids),
                )
                self.assertIsNotNone(client.final_prompt)
                self.assertIn(chosen, {item["action_id"] for item in client.displayed_actions})
                self.assertEqual(agent.last_decision_source, "model")

    def test_opening_targets_are_complete_initial_double_deck_deals(self) -> None:
        fixtures = {fixture.name: fixture for fixture in build_h3_model_probe_fixtures()}
        full_deck = Counter(card_to_token(card) for card in build_double_deck())
        for name in ("low_cost_single", "neutral_soft_pair"):
            with self.subTest(name=name):
                fixture = fixtures[name]
                observation = fixture.observation
                my_info = observation["my_info"]
                current_round = observation["current_round"]
                history = observation["history"]
                assert isinstance(my_info, dict)
                assert isinstance(current_round, dict)
                assert isinstance(history, dict)
                first_hand = tuple(my_info["hand_cards"])
                deal = _complete_opening_hands(first_hand)

                self.assertEqual(tuple(len(hand) for hand in deal), (27, 27, 27, 27))
                self.assertEqual(sum(len(hand) for hand in deal), 108)
                self.assertTrue(
                    Counter(token for hand in deal for token in hand) == full_deck,
                    "opening_deal_must_match_complete_double_deck",
                )
                self.assertEqual(tuple(my_info["hand_cards"]), deal[0])
                self.assertEqual(current_round.get("step_no"), 0)
                self.assertEqual(current_round.get("round_no"), 1)
                self.assertEqual(current_round.get("current_player_id"), 1)
                self.assertEqual(current_round.get("constraint"), "free")
                self.assertIsNone(current_round.get("table_action"))
                self.assertEqual(history.get("actions"), [])
                self.assertEqual(history.get("finish_order"), [])
                other_players = observation["other_players"]
                self.assertIsInstance(other_players, list)
                self.assertEqual(
                    sorted(player.get("hand_count") for player in other_players if isinstance(player, dict)),
                    [27, 27, 27],
                )
                self.assertTrue(all(not player.get("finished") for player in other_players if isinstance(player, dict)))

                replay = _game(*deal)
                replay_observation = replay.reset()
                self.assertTrue(
                    replay_observation == fixture.observation
                    and replay.legal_actions() == fixture.legal_actions,
                    "opening_fixture_must_match_engine_public_payload",
                )

                result = qualify_h3_model_probe_fixture(fixture, advisor=_advisor())
                self.assertIs(result.stage, QualificationStage.READY)
                self.assertLessEqual(result.final_candidate_count, 80)
                self.assertTrue(result.recommendation_ready)
                self.assertTrue(result.soft_marker_ready)
                self.assertTrue(result.source_is_model)

    def test_other_six_fixtures_keep_their_qualified_projection(self) -> None:
        expected = {
            "bomb_residual": (10, 6, "endgame", "critical_endgame", True, True),
            "pair_cleanup": (7, 4, "endgame", "critical_endgame", True, False),
            "teammate_controls": (3, 3, "endgame", "critical_endgame", False, False),
            "danger_block": (3, 3, "endgame", "critical_endgame", False, False),
            "short_endgame": (5, 4, "endgame", "near_open_endgame", False, False),
            "bomb_wildcard_soft": (30, 25, "endgame", "critical_endgame", False, True),
        }
        fixtures = {fixture.name: fixture for fixture in build_h3_model_probe_fixtures()}
        results = {result.name: result for result in qualify_h3_model_probe_fixtures()}
        for name, (candidate_count, final_count, scene, phase, contrast, bomb_soft) in expected.items():
            with self.subTest(name=name):
                fixture = fixtures[name]
                result = results[name]
                _agent, client, _chosen = _run_projection(fixture, _advisor())
                context = client.kwargs["rag_context"] if client.kwargs is not None else None
                self.assertIsInstance(context, dict)
                assert isinstance(context, dict)
                tags = context.get("scene_tags")
                hits = context.get("experience_hits")
                self.assertIsInstance(tags, dict)
                self.assertIsInstance(hits, list)
                assert isinstance(tags, dict) and isinstance(hits, list)
                source_ids = {hit.get("source_id") for hit in hits if isinstance(hit, dict)}
                self.assertIs(result.stage, QualificationStage.READY)
                self.assertEqual((result.candidate_count, result.final_candidate_count), (candidate_count, final_count))
                self.assertLessEqual(result.final_candidate_count, 80)
                self.assertEqual((tags.get("scene"), tags.get("phase")), (scene, phase))
                self.assertEqual(result.contrast_ready, contrast)
                self.assertEqual("exp_bomb_wildcard_001" in source_ids, bomb_soft)

    def test_fixture_semantics_and_soft_evidence_use_the_actual_target_sources(self) -> None:
        expected_phase = {
            "low_cost_single": ("lead_opening", "opening"),
            "neutral_soft_pair": ("lead_opening", "opening"),
        }
        expected_soft_source = {
            "low_cost_single": "exp_soft_pair_probe_001",
            "neutral_soft_pair": "exp_soft_pair_probe_001",
            "bomb_wildcard_soft": "exp_bomb_wildcard_001",
        }
        for fixture in build_h3_model_probe_fixtures():
            with self.subTest(name=fixture.name):
                _agent, client, _chosen = _run_projection(fixture, _advisor())
                context = client.kwargs["rag_context"] if client.kwargs is not None else None
                self.assertIsInstance(context, dict)
                assert isinstance(context, dict)
                tags = context["scene_tags"]
                self.assertIsInstance(tags, dict)
                assert isinstance(tags, dict)
                if fixture.name in expected_phase:
                    self.assertEqual(
                        (tags.get("scene"), tags.get("phase")),
                        expected_phase[fixture.name],
                    )
                if fixture.name in expected_soft_source:
                    hits = context["experience_hits"]
                    self.assertIsInstance(hits, list)
                    expected = [hit for hit in hits if isinstance(hit, dict) and hit.get("source_id") == expected_soft_source[fixture.name]]
                    self.assertEqual(len(expected), 1)
                    rendered = DeepSeekClient._format_rag_hits(expected)
                    self.assertEqual(len(rendered), 1)
                    self.assertIn(rendered[0], client.transport.user_prompt or "")
                self.assertNotIn("candidate_requirements", json.dumps(context, ensure_ascii=False))

    def test_conditional_soft_evidence_requires_complete_public_opportunities(self) -> None:
        fixtures = {fixture.name: fixture for fixture in build_h3_model_probe_fixtures()}
        advisor = _advisor()
        for name in ("low_cost_single", "neutral_soft_pair", "pair_cleanup", "short_endgame"):
            with self.subTest(name=name):
                context = advisor.get_rag_context(
                    observation=fixtures[name].observation,
                    legal_actions=fixtures[name].legal_actions,
                    hand_eval={"label": "medium"},
                    top_k=3,
                )
                self.assertNotIn(
                    "exp_bomb_wildcard_001",
                    [hit.get("source_id") for hit in context["experience_hits"] if isinstance(hit, dict)],
                )

        neutral = fixtures["neutral_soft_pair"]
        context = advisor.get_rag_context(
            observation=neutral.observation,
            legal_actions=neutral.legal_actions,
            hand_eval={"label": "medium"},
            top_k=3,
        )
        self.assertIn(
            "exp_soft_pair_probe_001",
            [hit.get("source_id") for hit in context["experience_hits"] if isinstance(hit, dict)],
        )
        malformed_actions = deepcopy(neutral.legal_actions)
        malformed_actions[0]["carrier_cards"] = ["malformed"]
        malformed_context = advisor.get_rag_context(
            observation=neutral.observation,
            legal_actions=malformed_actions,
            hand_eval={"label": "medium"},
            top_k=3,
        )
        self.assertNotIn(
            "exp_soft_pair_probe_001",
            [hit.get("source_id") for hit in malformed_context["experience_hits"] if isinstance(hit, dict)],
        )

    def test_pair_soft_hypothesis_obeys_opening_midgame_and_endgame_boundaries(self) -> None:
        fixtures = {fixture.name: fixture for fixture in build_h3_model_probe_fixtures()}
        advisor = _advisor()
        opening = advisor.get_rag_context(
            observation=fixtures["neutral_soft_pair"].observation,
            legal_actions=fixtures["neutral_soft_pair"].legal_actions,
            hand_eval={"label": "medium"},
            top_k=10,
        )
        midgame = _game(
            ("6S", "6H", "3S", "4S", "5S", "7S", "8S", "9S", "10S", "JS", "QS", "KS"),
            ("3H", "4H", "5H", "6H", "7H", "8H", "9H", "10H", "JH", "QH", "KH", "AH"),
            ("3C", "4C", "5C", "6C", "7C", "8C", "9C", "10C", "JC", "QC", "KC", "AC"),
            ("3D", "4D", "5D", "6D", "7D", "8D", "9D", "10D", "JD", "QD", "KD", "AD"),
        )
        midgame_observation = midgame.reset()
        midgame_context = advisor.get_rag_context(
            observation=midgame_observation,
            legal_actions=midgame.legal_actions(),
            hand_eval={"label": "medium"},
            top_k=10,
        )
        endgame = advisor.get_rag_context(
            observation=fixtures["pair_cleanup"].observation,
            legal_actions=fixtures["pair_cleanup"].legal_actions,
            hand_eval={"label": "medium"},
            top_k=10,
        )

        contexts = {"opening": opening, "midgame": midgame_context, "endgame": endgame}
        for phase, context in contexts.items():
            with self.subTest(phase=phase):
                tags = context["scene_tags"]
                self.assertIsInstance(tags, dict)
                assert isinstance(tags, dict)
                if phase == "endgame":
                    self.assertIn(tags.get("phase"), {"endgame", "near_open_endgame", "critical_endgame"})
                else:
                    self.assertEqual(tags.get("phase"), phase)
                ids = [hit.get("source_id") for hit in context["experience_hits"] if isinstance(hit, dict)]
                if phase == "endgame":
                    self.assertNotIn("exp_soft_pair_probe_001", ids)
                else:
                    self.assertIn("exp_soft_pair_probe_001", ids)

    def test_empty_or_wrong_actual_rag_context_fails_all_qualifications(self) -> None:
        fixtures = build_h3_model_probe_fixtures()
        for advisor in (_EmptyRAGAdvisor(), _WrongSceneRAGAdvisor(), _IrrelevantHitsRAGAdvisor()):
            with self.subTest(advisor=type(advisor).__name__):
                results = tuple(qualify_h3_model_probe_fixture(fixture, advisor=advisor) for fixture in fixtures)
                self.assertEqual(len(results), len(SCENARIO_NAMES))
                self.assertTrue(all(result.stage is QualificationStage.RAG_CONTEXT for result in results))

    def test_missing_router_projection_cannot_be_qualified_as_ready(self) -> None:
        fixture = build_h3_model_probe_fixtures()[0]
        with patch("agents.strategy_router.route_strategy_intent", side_effect=RuntimeError("router-unavailable")):
            result = qualify_h3_model_probe_fixture(fixture, advisor=_advisor())
        self.assertIs(result.stage, QualificationStage.RAG_CONTEXT)
        self.assertFalse(result.ready)

    def test_actual_prompt_and_candidate_projection_fail_closed_when_tampered(self) -> None:
        fixtures = {fixture.name: fixture for fixture in build_h3_model_probe_fixtures()}
        cases = (
            ("low_cost_single", _MissingMarkerClient, QualificationStage.ROUTER_RAG_PROMPT),
            ("low_cost_single", _MissingSoftEvidenceClient, QualificationStage.ROUTER_RAG_PROMPT),
            ("bomb_residual", _MissingContrastClient, QualificationStage.ROUTER_RAG_PROMPT),
            ("neutral_soft_pair", _MissingSoftEvidenceClient, QualificationStage.ROUTER_RAG_PROMPT),
            ("bomb_wildcard_soft", _MissingSoftEvidenceClient, QualificationStage.ROUTER_RAG_PROMPT),
            ("bomb_residual", _MismatchedCandidateClient, QualificationStage.REQUEST_BINDING),
            ("low_cost_single", _FailingClient, QualificationStage.LOCAL_SHORTCUT),
        )
        for name, client_factory, expected_stage in cases:
            with self.subTest(name=name, client=client_factory.__name__):
                result = qualify_h3_model_probe_fixture(
                    fixtures[name],
                    advisor=_advisor(),
                    client_factory=client_factory,
                )
                self.assertIs(result.stage, expected_stage)
                self.assertFalse(result.ready)

    def test_actual_request_binding_fails_closed_for_mutated_or_invalid_envelopes(self) -> None:
        fixture = build_h3_model_probe_fixtures()[0]
        clients = (
            _ReturnedOnlyMissingMarkerClient,
            _BadJsonClient,
            _MissingUserClient,
            _DuplicateTransportClient,
            _ZeroTransportClient,
        )
        for client_factory in clients:
            with self.subTest(client=client_factory.__name__):
                result = qualify_h3_model_probe_fixture(
                    fixture,
                    advisor=_advisor(),
                    client_factory=client_factory,
                )
                self.assertIs(result.stage, QualificationStage.REQUEST_BINDING)
                self.assertFalse(result.ready)


if __name__ == "__main__":
    unittest.main()
