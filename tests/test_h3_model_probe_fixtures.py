"""No-network regressions for the reproducible H3 model-probe qualification."""

import json
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekSuggestion
from evaluation.h3_model_probe_fixtures import (
    ProbeFixture,
    QualificationStage,
    SCENARIO_NAMES,
    _NoNetworkTransport,
    _RecordingDeepSeekClient,
    _advisor,
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
                metadata = {**dict(hit.get("metadata", {})), "scene": "lead_opening"}
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
        for name in ("neutral_soft_pair", "bomb_wildcard_soft"):
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
