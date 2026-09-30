from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evaluation import m2_same_state_model_eval as m2
from evaluation.action_quality_proxy import FROZEN_H3_A9_OPENING_2_PROJECTION
from evaluation.h3_a9_quality_queue import build_h3_a9_quality_samples
from agents.rule_based_ai import RuleBasedAIAgent


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation" / "m2_same_state_model_eval.py"
PROFILE = {
    "hand_evaluation_enabled": True,
    "opening_formula_enabled": True,
    "card_tracking_enabled": True,
    "deepseek_timeout": 60.0,
}
FIXED_SPECS = (
    m2.M2StateSpec("opening_seed_0", 0, 0, 0, "requested_seed_model_path_both_versions"),
    m2.M2StateSpec("opening_seed_29", 29, 0, 29, "requested_seed_model_path_both_versions"),
    m2.M2StateSpec("pair_single_wildcard", 5000, 0, 5000, "first_common_pair_wildcard_model_state"),
    m2.M2StateSpec("h3_a9_midgame_1", 922, 8, 922, "frozen_h3_a9_production_state"),
)


def _ready_rows() -> tuple[m2.VersionQualification, ...]:
    rows: list[m2.VersionQualification] = []
    for spec in FIXED_SPECS:
        phase = "midgame" if spec.name == "h3_a9_midgame_1" else "opening"
        for version in ("baseline", "current"):
            rows.append(
                m2.VersionQualification(
                    state_name=spec.name,
                    version=version,
                    stage="ready",
                    state_digest=f"digest:{spec.name}",
                    state_phase=phase,
                    canonical_count=8,
                    final_count=2,
                    recommendation_ids=(101,),
                    final_candidate_ids=(101, 102),
                    reference_action_id=101,
                    response_action_id=102,
                    client_action_id=102,
                    source="model",
                    transport_calls=1,
                    envelope_bound=True,
                    recommendation_closed=True,
                    candidate_closed=True,
                    provider_outcome="success",
                    max_retries=0,
                    decision_budget_seconds=m2.DECISION_BUDGET_SECONDS,
                    configured_timeout_seconds=60.0,
                    request_controls_fingerprint="same-controls",
                )
            )
    return tuple(rows)


class M2SameStateEvaluationTests(unittest.TestCase):
    def test_discovery_uses_first_common_pair_wildcard_seed_in_reserved_interval(self) -> None:
        def scan(_root: Path, _source: Path, seeds: tuple[int, ...], _profile: object, *, require_pair_wildcard: bool = False):
            return tuple(
                {
                    "seed": seed,
                    "model_path": True,
                    "pair_single": require_pair_wildcard,
                    "wildcard_resource": require_pair_wildcard,
                }
                for seed in seeds
            )

        with patch.object(m2, "scan_version_initial_states", side_effect=scan):
            specs, stage = m2.discover_m2_state_specs(Path("baseline"), Path("current"), SOURCE, PROFILE)
        self.assertEqual(stage, "ready")
        self.assertIsNotNone(specs)
        assert specs is not None
        self.assertEqual(tuple((item.name, item.seed, item.step) for item in specs), (
            ("opening_seed_0", 0, 0),
            ("opening_seed_29", 29, 0),
            ("pair_single_wildcard", 5000, 0),
            ("h3_a9_midgame_1", 922, 8),
        ))
        self.assertNotIn((921, 0), {(item.seed, item.step) for item in specs})

    def test_h3_a9_opening_2_stays_separate_counterfactual_coverage_row(self) -> None:
        sample_set = build_h3_a9_quality_samples()
        self.assertTrue(sample_set.ready)
        sample = next(item for item in sample_set.samples if item.name == "opening_2")
        reference_id = RuleBasedAIAgent(player_id=1).select_action(sample.observation, sample.legal_actions)
        self.assertEqual(sample.source_seed, 921)
        self.assertEqual(sample.observation["current_round"]["step_no"], 0)  # type: ignore[index]
        self.assertEqual((sample.canonical_candidate_count, sample.final_candidate_count), (573, 52))
        self.assertFalse(sample.opening_formula_enabled)
        self.assertEqual(sample.candidate_projection, FROZEN_H3_A9_OPENING_2_PROJECTION)
        self.assertIn(reference_id, sample.final_candidate_ids)
        self.assertNotIn((sample.source_seed, 0), {(item.seed, item.step) for item in FIXED_SPECS})

    def test_current_production_factory_fake_request_is_bound_and_preserves_raw_id(self) -> None:
        spec = FIXED_SPECS[1]
        first = m2.probe_version_state(ROOT, SOURCE, spec, PROFILE)
        qualification = m2.qualification_from_worker(spec.name, "current", first)
        self.assertEqual(qualification.stage, "ready")
        self.assertEqual(qualification.state_phase, "opening")
        self.assertEqual(qualification.canonical_count, 491)
        self.assertEqual(qualification.final_count, 52)
        self.assertLessEqual(qualification.final_count, 80)
        self.assertEqual(qualification.transport_calls, 1)
        self.assertEqual(qualification.stream_entries, 1)
        self.assertEqual(qualification.default_transport_entries, 0)
        self.assertIsNone(qualification.stream_error_category)
        self.assertFalse(qualification.default_transport_completed)
        self.assertTrue(qualification.envelope_bound)
        self.assertTrue(qualification.candidate_closed)
        self.assertTrue(qualification.recommendation_closed)
        self.assertEqual(qualification.source, "model")
        self.assertEqual(qualification.provider_outcome, "success")
        self.assertEqual(qualification.max_retries, 0)
        self.assertEqual(qualification.response_action_id, qualification.client_action_id)
        self.assertIn(qualification.response_action_id, qualification.final_candidate_ids)
        self.assertGreater(qualification.rendered_contrast_count, 0)
        self.assertEqual(dict(qualification.rag_experience_hits), {
            "exp_lead_opening_shape_001": "B",
            "exp_soft_pair_probe_001": "C",
        })
        self.assertTrue({"single", "pair", "straight", "triple", "triple_with_pair"}.issubset(
            set(dict(qualification.candidate_patterns))
        ))

        final_ids = tuple(first["final_candidate_ids"])
        chosen = final_ids[-1]
        second = m2.probe_version_state(ROOT, SOURCE, spec, PROFILE, selected_action_id=chosen)
        self.assertEqual(second.get("stage"), "ready")
        self.assertEqual(second.get("response_action_id"), chosen)
        self.assertEqual(second.get("client_action_id"), chosen)
        self.assertEqual(second.get("selected_action_id"), chosen)
        self.assertEqual(second.get("source"), "model")
        self.assertEqual(second.get("transport_calls"), 1)

    def test_all_four_current_states_pass_the_production_factory_offline_gate(self) -> None:
        gate, rows = m2.qualify_fixed_states(
            FIXED_SPECS,
            {"baseline": ROOT, "current": ROOT},
            SOURCE,
            PROFILE,
        )
        self.assertEqual(gate, "ready")
        self.assertEqual(len(rows), 8)
        for spec in FIXED_SPECS:
            pair = [row for row in rows if row.state_name == spec.name]
            self.assertEqual(len(pair), 2)
            self.assertEqual(pair[0].state_digest, pair[1].state_digest)
            self.assertEqual(pair[0].reference_action_id, pair[1].reference_action_id)
            self.assertTrue(all(row.ready for row in pair))
            self.assertTrue(all(row.envelope_bound and row.candidate_closed and row.recommendation_closed for row in pair))
            self.assertTrue(all(row.max_retries == 0 and row.transport_calls == 1 for row in pair))

    def test_timeout_and_unshown_model_id_fail_closed_without_retry(self) -> None:
        spec = FIXED_SPECS[1]
        timed_out = m2.probe_version_state(ROOT, SOURCE, spec, PROFILE, fake_outcome="timeout")
        self.assertEqual(timed_out.get("stage"), "model_provider_timeout")
        self.assertEqual(timed_out.get("provider_outcome"), "timeout")
        self.assertEqual(timed_out.get("transport_calls"), 1)
        self.assertEqual(timed_out.get("max_retries"), 0)
        self.assertIsNone(timed_out.get("selected_action_id"))

        invalid = m2.probe_version_state(ROOT, SOURCE, spec, PROFILE, selected_action_id=2**31)
        self.assertEqual(invalid.get("stage"), "model_suggestion_invalid")
        self.assertEqual(invalid.get("provider_outcome"), "invalid_suggestion")
        self.assertEqual(invalid.get("transport_calls"), 1)
        self.assertEqual(invalid.get("max_retries"), 0)
        self.assertIsNone(invalid.get("selected_action_id"))

    def test_real_worker_receives_client_settings_without_starting_transport(self) -> None:
        config = SimpleNamespace(
            hand_evaluation_enabled=True,
            opening_formula_enabled=True,
            card_tracking_enabled=True,
            deepseek_timeout=60.0,
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://synthetic.invalid",
            deepseek_model="synthetic-model",
        )
        profile = m2.profile_from_app_config(config, offline=False)
        captured: dict[str, object] = {}

        def capture_payload(_root: Path, _source: Path, payload: dict[str, object]) -> dict[str, object]:
            captured.update(payload)
            return {"stage": "synthetic_pretransport_stop"}

        with patch.object(m2, "run_in_repo", side_effect=capture_payload):
            result = m2.probe_version_state(ROOT, SOURCE, FIXED_SPECS[0], profile, real=True)
        self.assertEqual(result["stage"], "synthetic_pretransport_stop")
        self.assertNotIn("client_settings", captured["profile"])
        settings = captured.get("client_settings")
        self.assertIsInstance(settings, dict)
        assert isinstance(settings, dict)
        self.assertEqual(settings["max_retries"], 0)
        self.assertEqual(settings["api_key"], "synthetic-key")

    def test_offline_gate_requires_same_state_and_reference_in_both_versions(self) -> None:
        rows = _ready_rows()
        self.assertEqual(m2.validate_offline_qualifications(FIXED_SPECS, rows), "ready")
        changed = list(rows)
        changed[1] = replace(changed[1], state_digest="different")
        self.assertEqual(
            m2.validate_offline_qualifications(FIXED_SPECS, tuple(changed)),
            "paired_public_state_or_reference_mismatch",
        )
        changed = list(rows)
        changed[1] = replace(changed[1], request_controls_fingerprint="different")
        self.assertEqual(
            m2.validate_offline_qualifications(FIXED_SPECS, tuple(changed)),
            "paired_public_state_or_reference_mismatch",
        )

    def test_bounded_requests_are_interleaved_once_each_and_stop_on_integrity_failure(self) -> None:
        calls: list[tuple[str, str]] = []

        def timeout_once(version: str, spec: m2.M2StateSpec) -> dict[str, object]:
            calls.append((spec.name, version))
            return {"stage": "model_provider_timeout", "provider_outcome": "timeout", "max_retries": 0}

        run = m2.run_bounded_real_requests(FIXED_SPECS, _ready_rows(), timeout_once)
        self.assertEqual(run.stage, "complete")
        self.assertEqual(run.client_invocation_count, 8)
        self.assertEqual(run.external_request_count, 0)
        self.assertEqual(run.observed_transport_invocations, 0)
        self.assertEqual([attempt.sequence for attempt in run.attempts], list(range(1, 9)))
        self.assertEqual(run.to_dict()["retry_count"], 0)
        self.assertEqual(calls, [
            (spec.name, version)
            for spec in FIXED_SPECS
            for version in ("baseline", "current")
        ])

        no_calls: list[object] = []
        incomplete = m2.run_bounded_real_requests(FIXED_SPECS, _ready_rows()[:-1], lambda *_: no_calls.append(1))
        self.assertEqual(incomplete.external_request_count, 0)
        self.assertEqual(incomplete.client_invocation_count, 0)
        self.assertEqual(no_calls, [])

        stopped_calls: list[tuple[str, str]] = []

        def broken_binding(version: str, spec: m2.M2StateSpec) -> dict[str, object]:
            stopped_calls.append((spec.name, version))
            return {"stage": "request_body_binding_invalid", "max_retries": 0}

        stopped = m2.run_bounded_real_requests(FIXED_SPECS, _ready_rows(), broken_binding)
        self.assertEqual(stopped.stage, "integrity_failure_stopped")
        self.assertEqual(stopped.client_invocation_count, 1)
        self.assertEqual(stopped.external_request_count, 0)
        self.assertEqual(len(stopped_calls), 1)

        setup_calls: list[tuple[str, str]] = []

        def settings_failure(version: str, spec: m2.M2StateSpec) -> dict[str, object]:
            setup_calls.append((spec.name, version))
            return {"stage": "client_settings_invalid", "provider_outcome": "not_called"}

        setup_stopped = m2.run_bounded_real_requests(FIXED_SPECS, _ready_rows(), settings_failure)
        self.assertEqual(setup_stopped.stage, "integrity_failure_stopped")
        self.assertEqual(setup_stopped.client_invocation_count, 1)
        self.assertEqual(setup_stopped.external_request_count, 0)
        self.assertEqual(len(setup_calls), 1)

    def test_runtime_retry_cap_and_low_sensitivity_serialization(self) -> None:
        config = SimpleNamespace(
            hand_evaluation_enabled=True,
            opening_formula_enabled=True,
            card_tracking_enabled=True,
            deepseek_timeout=60.0,
            deepseek_api_key="synthetic-key",
            deepseek_base_url="https://synthetic.invalid",
            deepseek_model="synthetic-model",
        )
        real_profile = m2.profile_from_app_config(config, offline=False)
        settings = real_profile["client_settings"]
        self.assertEqual(settings["max_retries"], 0)  # type: ignore[index]
        safe = m2.qualification_from_worker(
            "opening_seed_29",
            "current",
            m2.probe_version_state(ROOT, SOURCE, FIXED_SPECS[1], PROFILE),
        ).to_dict()
        encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "prompt\":",
            "observation\":",
            "hand_cards",
            "reasoning",
            "api_key",
            "base_url",
            "synthetic-key",
            "synthetic.invalid",
            "offline-m2-placeholder",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertIn("response_action_id", safe)
        self.assertIn("client_action_id", safe)
        self.assertNotIn("final_candidate_ids", safe)

    def test_default_transport_counter_preserves_default_branch_without_network(self) -> None:
        import agents.deepseek_client as client_module

        capture: dict[str, object] = {
            "default_transport_entries": 0,
            "default_transport_completed": False,
            "default_transport_error_category": None,
        }
        original_transport = m2._install_default_transport_entry_counter(client_module, capture)

        event = json.dumps(
            {"choices": [{"delta": {"content": '{"action_id":42}'}}]},
            separators=(",", ":"),
        ).encode("utf-8")

        class SyntheticResponse:
            def __init__(self) -> None:
                self._lines = [b"data: " + event + b"\n", b"\n", b"data: [DONE]\n"]

            def __enter__(self) -> "SyntheticResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def readline(self) -> bytes:
                return self._lines.pop(0) if self._lines else b""

        calls: list[int] = []
        request = client_module.urllib_request.Request(
            "https://synthetic.invalid/chat/completions",
            data=b"{}",
            method="POST",
        )
        client = client_module.DeepSeekClient(
            api_key="synthetic-key",
            base_url="https://synthetic.invalid",
            model="synthetic-model",
            timeout_seconds=1.0,
            max_retries=0,
        )
        self.assertIs(client._transport, client_module._default_transport)
        try:
            with patch.object(
                client_module.urllib_request,
                "urlopen",
                side_effect=lambda _request, **_kwargs: (calls.append(1) or SyntheticResponse()),
            ):
                content, reasoning = client._stream_sse(request, 1.0)
        finally:
            client_module._default_transport = original_transport

        self.assertEqual(capture["default_transport_entries"], 1)
        self.assertTrue(capture["default_transport_completed"])
        self.assertIsNone(capture.get("default_transport_error_category"))
        self.assertEqual(calls, [1])
        self.assertEqual(content, '{"action_id":42}')
        self.assertEqual(reasoning, "")

    def test_measured_urlopen_accepts_production_timeout_keyword_and_binds_body(self) -> None:
        capture: dict[str, object] = {
            "transport_calls": 0,
            "external_send_invocations": 0,
            "prompt_candidate_ids": (11, 12),
            "prompt_candidate_count": 0,
            "request_candidate_ids": (),
            "request_candidate_count": 0,
            "request_utf8_bytes": 0,
            "request_envelope_valid": False,
            "request_controls_fingerprint": None,
            "body_bound": False,
        }
        timing: dict[str, object] = {"urlopen_start_ns": None, "response_headers_ms": None}
        request = SimpleNamespace(data=b"synthetic-request")
        envelope = {"model": "synthetic", "temperature": 0, "stream": True}
        forwarded: list[tuple[object, float]] = []

        def parse(_request: object):
            return envelope, "synthetic prompt", (11, 12), len(request.data)

        def original_urlopen(actual_request: object, *, timeout: float) -> object:
            forwarded.append((actual_request, timeout))
            return "synthetic-response"

        measured = m2._make_measured_urlopen(
            original_urlopen=original_urlopen,
            parse_request=parse,
            capture=capture,
            timing=timing,
            response_wrapper=lambda response: ("wrapped", response),
        )
        response = measured(request, timeout=12.5)

        self.assertEqual(response, ("wrapped", "synthetic-response"))
        self.assertEqual(forwarded, [(request, 12.5)])
        self.assertEqual(capture["transport_calls"], 1)
        self.assertEqual(capture["external_send_invocations"], 1)
        self.assertEqual(capture["request_candidate_ids"], (11, 12))
        self.assertTrue(capture["body_bound"])


if __name__ == "__main__":
    unittest.main()
