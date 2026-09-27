from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation import m2_expanded_same_state_eval as expanded
from evaluation import m2_same_state_model_eval as m2


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation" / "m2_same_state_model_eval.py"
PROFILE = {
    "hand_evaluation_enabled": True,
    "opening_formula_enabled": True,
    "card_tracking_enabled": True,
    "deepseek_timeout": 60.0,
}


def _specs() -> tuple[expanded.ExpandedM2StateSpec, ...]:
    return (
        expanded.ExpandedM2StateSpec(
            "opening_dense_1", 150000, 0, 150000, "digest:dense1", "opening", "opening_dense",
            "first_common_dense_opening", 224, 80, (("single", 7), ("pair", 2), ("triple", 1)),
            (("natural_pair_single", 4), ("wildcard_resource", 5)),
        ),
        expanded.ExpandedM2StateSpec(
            "opening_dense_2", 150001, 0, 150000, "digest:dense2", "opening", "opening_dense",
            "first_common_dense_opening", 220, 80, (("single", 8), ("pair", 2)),
            (("natural_pair_single", 3), ("wildcard_resource", 4)),
        ),
        expanded.ExpandedM2StateSpec(
            "opening_diverse_1", 151000, 0, 151000, "digest:diverse1", "opening", "opening_diverse",
            "first_common_diverse_opening", 75, 75, (("single", 2), ("pair", 3), ("triple", 1)), (),
        ),
        expanded.ExpandedM2StateSpec(
            "opening_diverse_2", 151001, 0, 151000, "digest:diverse2", "opening", "opening_diverse",
            "first_common_diverse_opening", 80, 80, (("single", 1), ("pair", 1), ("triple", 2)), (),
        ),
        expanded.ExpandedM2StateSpec(
            "midgame_pressure_resource", 160000, 11, 160000, "digest:midpressure", "midgame",
            "midgame_pressure_resource", "first_common_midgame_pressure_resource", 10, 6,
            (("single", 4),), (("wildcard_resource", 1),),
        ),
        expanded.ExpandedM2StateSpec(
            "midgame_team_danger", 160001, 15, 160000, "digest:midteam", "midgame",
            "midgame_team_danger", "first_distinct_common_midgame_team_danger", 12, 7,
            (("single", 3),), (("teammate_table_choice", 1),),
        ),
        expanded.ExpandedM2StateSpec(
            "endgame_1", 170000, 61, 170000, "digest:end1", "endgame", "endgame",
            "first_two_common_endgame_seeds", 7, 3, (("single", 2),), (),
        ),
        expanded.ExpandedM2StateSpec(
            "endgame_2", 170001, 58, 170000, "digest:end2", "critical_endgame", "endgame",
            "first_two_common_endgame_seeds", 6, 2, (("single", 2),), (),
        ),
    )


def _qualification_rows(specs: tuple[expanded.ExpandedM2StateSpec, ...]) -> tuple[m2.VersionQualification, ...]:
    rows: list[m2.VersionQualification] = []
    for spec in specs:
        for version in expanded.VERSION_ORDER:
            reference = 101 if version == "baseline" else 103
            rows.append(
                m2.VersionQualification(
                    state_name=spec.name,
                    version=version,
                    stage="ready",
                    state_digest=spec.state_digest,
                    state_phase=spec.phase,
                    canonical_count=spec.canonical_count,
                    final_count=2,
                    relation_counts=spec.relation_counts,
                    visible_relation_counts=spec.relation_counts,
                    recommendation_ids=(101,),
                    final_candidate_ids=(101, 102),
                    reference_action_id=reference,
                    response_action_id=102,
                    client_action_id=102,
                    source="model",
                    stream_entries=1,
                    transport_calls=1,
                    external_send_invocations=0,
                    envelope_bound=True,
                    candidate_closed=True,
                    recommendation_closed=True,
                    provider_outcome="success",
                    max_retries=0,
                    decision_budget_seconds=119.0,
                    configured_timeout_seconds=60.0,
                    request_controls_fingerprint="same-runtime-controls",
                )
            )
    return tuple(rows)


def _qualification_payload(
    *,
    outcome: str = "success",
    stage: str = "ready",
    sent: int = 1,
    spec: expanded.ExpandedM2StateSpec | None = None,
    version: str = "baseline",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "stage": stage,
        "state_digest": spec.state_digest if spec else "synthetic-state",
        "state_phase": spec.phase if spec else "opening",
        "canonical_count": spec.canonical_count if spec else 90,
        "final_count": 2,
        "candidate_patterns": {},
        "wildcard_candidate_count": 0,
        "relation_counts": dict(spec.relation_counts) if spec else {},
        "visible_relation_counts": dict(spec.relation_counts) if spec else {},
        "rendered_relation_line_count": 0,
        "rendered_contrast_count": 0,
        "rag_experience_hits": [],
        "recommendation_ids": [101],
        "final_candidate_ids": [101, 102],
        "reference_action_id": 103 if version == "current" else 101,
        "response_action_id": 102 if outcome == "success" else None,
        "client_action_id": 102 if outcome == "success" else None,
        "source": "model" if outcome == "success" else "rule_fallback",
        "stream_entries": 1 if sent else 0,
        "transport_calls": 1 if sent else 0,
        "default_transport_entries": 0,
        "external_send_invocations": sent,
        "envelope_bound": bool(sent),
        "candidate_closed": bool(sent),
        "recommendation_closed": bool(sent),
        "prompt_chars": 0,
        "prompt_utf8_bytes": 0,
        "request_utf8_bytes": 0,
        "provider_outcome": outcome,
        "max_retries": 0,
        "decision_budget_seconds": 119.0,
        "configured_timeout_seconds": 60.0,
        "request_controls_fingerprint": "same-runtime-controls",
    }
    return payload


class M2ExpandedSameStateTests(unittest.TestCase):
    def test_public_action_validation_requires_complete_canonical_payload_fields(self) -> None:
        from engine.game import GuanDanGame

        game = GuanDanGame(seed=19, current_level_rank="2")
        observation = game.reset()
        actions = game.legal_actions()
        self.assertEqual(observation["legal_actions"], actions)
        self.assertTrue(expanded._validate_public_actions(actions))

        missing_wildcard_info = [dict(action) for action in actions]
        missing_wildcard_info[0].pop("wildcard_info")
        self.assertFalse(expanded._validate_public_actions(missing_wildcard_info))
        missing_display = [dict(action) for action in actions]
        missing_display[0].pop("display_text")
        self.assertFalse(expanded._validate_public_actions(missing_display))
        malformed_wildcard_info = [dict(action) for action in actions]
        malformed_wildcard_info[0]["wildcard_info"] = [{"carrier_card": None, "declared_as": "X"}]
        self.assertFalse(expanded._validate_public_actions(malformed_wildcard_info))

        class DriftedObservationGame:
            def observe(self):
                altered = dict(observation)
                altered["legal_actions"] = actions[:-1]
                return altered

            def legal_actions(self):
                return actions

        self.assertIsNone(expanded._opening_state_summary(19, DriftedObservationGame()))

    def test_discovery_uses_first_common_public_states_in_each_frozen_range(self) -> None:
        def row(seed: int, step: int, selection: str) -> dict[str, object]:
            if selection == "opening_dense":
                count, patterns, relations, phase = 220, {"single": 4, "pair": 2}, {"natural_pair_single": 2, "wildcard_resource": 3}, "opening"
            elif selection == "opening_diverse":
                count, patterns, relations, phase = 78, {"single": 2, "pair": 1, "triple": 1}, {}, "opening"
            elif selection == "midgame_pressure_resource":
                count, patterns, relations, phase = 12, {"single": 4}, {"wildcard_resource": 1}, "midgame"
            elif selection == "midgame_team_danger":
                count, patterns, relations, phase = 13, {"single": 3}, {"teammate_table_choice": 1}, "midgame"
            else:
                count, patterns, relations, phase = 7, {"single": 2}, {}, "endgame"
            return {
                "seed": seed,
                "step": step,
                "state_digest": f"d:{selection}:{seed}:{step}",
                "phase": phase,
                "canonical_count": count,
                "nonpass_count": 3,
                "raw_pattern_counts": patterns,
                "relation_counts": relations,
                "relation_kinds": list(relations),
                "model_path": True,
            }

        def scan(_root: Path, _source: Path, selection: str, seeds: tuple[int, ...], _profile: object):
            candidates = []
            for seed in seeds:
                if selection.startswith("opening_"):
                    candidates.append(row(seed, 0, selection))
                elif selection == "midgame_pressure_resource":
                    candidates.append(row(seed, 7, selection))
                elif selection == "midgame_team_danger":
                    candidates.append(row(seed, 8, selection))
                else:
                    candidates.append(row(seed, 20, selection))
            return {"stage": "ready", "rows": candidates}

        with patch.object(expanded, "_validate_version_roots", return_value="ready"), patch.object(
            expanded, "_scan_subprocess", side_effect=scan,
        ):
            result = expanded.discover_expanded_state_specs(Path("baseline"), Path("current"), SOURCE, PROFILE)
        self.assertTrue(result.ready, result.stage)
        self.assertEqual(tuple((item.name, item.seed, item.step) for item in result.specs), (
            ("opening_dense_1", 150000, 0),
            ("opening_dense_2", 150001, 0),
            ("opening_diverse_1", 151000, 0),
            ("opening_diverse_2", 151001, 0),
            ("midgame_pressure_resource", 160000, 7),
            ("midgame_team_danger", 160000, 8),
            ("endgame_1", 170000, 20),
            ("endgame_2", 170001, 20),
        ))
        self.assertEqual(result.specs[0].canonical_count, 220)
        self.assertIn(("natural_pair_single", 2), result.specs[0].relation_counts)

    def test_discovery_stops_before_scanning_unpinned_version_roots(self) -> None:
        with patch.object(expanded, "_validate_version_roots", return_value="sealed_baseline_identity_mismatch"), patch.object(
            expanded, "_scan_subprocess",
        ) as scan:
            result = expanded.discover_expanded_state_specs(Path("baseline"), Path("current"), SOURCE, PROFILE)
        self.assertEqual(result.stage, "sealed_baseline_identity_mismatch")
        self.assertEqual(result.scanned_seed_counts, ())
        scan.assert_not_called()

    def test_common_state_join_rejects_changed_public_digest(self) -> None:
        baseline = [{"seed": 150000, "step": 0, "state_digest": "left", "phase": "opening", "canonical_count": 224, "nonpass_count": 8, "model_path": True}]
        current = [{"seed": 150000, "step": 0, "state_digest": "right", "phase": "opening", "canonical_count": 224, "nonpass_count": 8, "model_path": True}]
        self.assertEqual(expanded._common_rows(baseline, current), ())

    def test_selection_skips_non_model_or_non_matching_rows(self) -> None:
        dense = {
            "seed": 150000, "step": 0, "state_digest": "local", "phase": "opening",
            "canonical_count": 220, "nonpass_count": 8, "raw_pattern_counts": {"single": 4},
            "relation_counts": {"natural_pair_single": 1, "wildcard_resource": 1}, "model_path": False,
        }
        model_row = {**dense, "model_path": True}
        self.assertEqual(expanded._common_rows((model_row,), (dense,)), ())
        self.assertTrue(expanded._matches_selection(dense, "opening_dense"))
        diverse = {
            "seed": 151000, "step": 0, "state_digest": "missing-triple", "phase": "opening",
            "canonical_count": 78, "nonpass_count": 7, "raw_pattern_counts": {"single": 3, "pair": 1},
            "relation_counts": {}, "model_path": True,
        }
        self.assertFalse(expanded._matches_selection(diverse, "opening_diverse"))

    def test_offline_gate_requires_all_sixteen_version_rows_and_preserves_version_local_reference_visibility(self) -> None:
        specs = _specs()
        rows = _qualification_rows(specs)
        self.assertEqual(expanded.validate_expanded_offline_qualifications(specs, rows), "ready")
        baseline = next(row for row in rows if row.state_name == "opening_dense_1" and row.version == "baseline")
        current = next(row for row in rows if row.state_name == "opening_dense_1" and row.version == "current")
        self.assertTrue(baseline.to_dict()["reference_action_visible"])
        self.assertFalse(current.to_dict()["reference_action_visible"])
        self.assertEqual(expanded.validate_expanded_offline_qualifications(specs, rows[:-1]), "offline_qualification_count_invalid")

        changed = list(rows)
        changed[1] = replace(changed[1], state_digest="different-public-state")
        self.assertEqual(expanded.validate_expanded_offline_qualifications(specs, changed), "paired_public_state_mismatch")

    def test_offline_gate_requires_distinct_ascending_opening_seeds_and_resource_relation(self) -> None:
        specs = _specs()
        rows = _qualification_rows(specs)
        duplicate_dense = list(specs)
        duplicate_dense[1] = replace(
            duplicate_dense[1], seed=duplicate_dense[0].seed, step=1,
        )
        self.assertEqual(
            expanded.validate_expanded_offline_qualifications(duplicate_dense, rows),
            "dense_opening_seed_not_distinct",
        )

        out_of_order_diverse = list(specs)
        out_of_order_diverse[2] = replace(out_of_order_diverse[2], seed=151010)
        out_of_order_diverse[3] = replace(out_of_order_diverse[3], seed=151001)
        self.assertEqual(
            expanded.validate_expanded_offline_qualifications(out_of_order_diverse, rows),
            "diverse_opening_seed_order_invalid",
        )

        duplicate_position = list(specs)
        duplicate_position[5] = replace(
            duplicate_position[5],
            seed=duplicate_position[4].seed,
            step=duplicate_position[4].step,
            state_digest="different-digest-does-not-make-a-new-position",
        )
        self.assertEqual(
            expanded.validate_expanded_offline_qualifications(duplicate_position, rows),
            "duplicate_state",
        )

        mismatched_selection = list(specs)
        mismatched_selection[0] = replace(mismatched_selection[0], selection="opening_diverse")
        self.assertEqual(
            expanded.validate_expanded_offline_qualifications(mismatched_selection, rows),
            "sample_selection_invalid",
        )

        straight_only = list(specs)
        pressure = straight_only[4]
        straight_only[4] = replace(pressure, relation_counts=(("straight_strength", 1),))
        self.assertFalse(expanded._matches_selection(
            {"relation_counts": {"straight_strength": 1}, "raw_pattern_counts": {}},
            "midgame_pressure_resource",
        ))
        self.assertEqual(
            expanded.validate_expanded_offline_qualifications(straight_only, rows),
            "midgame_pressure_relation_missing",
        )

    def test_request_schedule_is_fixed_eight_states_two_repeats_and_thirty_two_slots(self) -> None:
        schedule = expanded.build_expanded_request_schedule(_specs())
        self.assertEqual(len(schedule), 32)
        self.assertEqual([slot.sequence for slot in schedule], list(range(1, 33)))
        self.assertEqual([(slot.version, slot.repeat) for slot in schedule[:4]], [
            ("baseline", 1), ("current", 1), ("current", 2), ("baseline", 2),
        ])
        self.assertEqual([(slot.version, slot.repeat) for slot in schedule[4:8]], [
            ("current", 1), ("baseline", 1), ("baseline", 2), ("current", 2),
        ])
        with self.assertRaises(ValueError):
            expanded.build_expanded_request_schedule(_specs()[:-1])
        self.assertEqual(expanded.MAX_RETRIES, 0)
        self.assertEqual(expanded.MAX_EXTERNAL_REQUESTS, 32)

    def test_no_authorization_or_incomplete_gate_never_calls_request_callback(self) -> None:
        calls: list[object] = []
        no_auth = expanded.run_authorized_expanded_requests(
            _specs(), _qualification_rows(_specs()), lambda *_args: calls.append(1),
        )
        self.assertEqual(no_auth.stage, "owner_authorization_required")
        self.assertEqual(no_auth.client_invocation_count, 0)
        self.assertEqual(calls, [])
        bad_gate = expanded.run_authorized_expanded_requests(
            _specs(), _qualification_rows(_specs())[:-1], lambda *_args: calls.append(1),
            owner_authorization_confirmed=True,
        )
        self.assertTrue(bad_gate.stage.startswith("offline_gate_"))
        self.assertEqual(calls, [])

    def test_synthetic_authorized_runner_hard_caps_at_fixed_thirty_two_slots_without_retry(self) -> None:
        specs = _specs()
        spec_digests = {spec.name: spec.state_digest for spec in specs}
        calls: list[tuple[str, str, int]] = []

        def fake_once(version: str, spec: expanded.ExpandedM2StateSpec, repeat: int):
            calls.append((spec.name, version, repeat))
            return _qualification_payload(spec=spec, version=version)

        def fake_rollout(_spec, selected, _ids, *, reference_action_id, expected_state_digest):
            self.assertEqual(selected, 102)
            self.assertEqual(expected_state_digest, spec_digests[_spec.name])
            return m2.M2RolloutComparison(
                selected_action_id=selected,
                reference_action_id=reference_action_id,
                selected_outcome="tie",
                selected_rank_sum=5,
                selected_steps=12,
                reference_outcome="tie",
                reference_rank_sum=5,
                reference_steps=12,
                comparison="tie",
                reference_visible=reference_action_id in _ids,
                selected_pattern="single",
                selected_carrier_count=1,
            )

        with patch.object(m2, "compare_with_frozen_rule_rollout", side_effect=fake_rollout):
            run = expanded.run_authorized_expanded_requests(
                specs, _qualification_rows(specs), fake_once, owner_authorization_confirmed=True,
            )
        self.assertEqual(run.stage, "complete")
        self.assertEqual(run.client_invocation_count, 32)
        self.assertEqual(run.external_request_count, 32)
        self.assertEqual(run.retry_count, 0)
        self.assertEqual(len(calls), 32)
        self.assertEqual(run.to_dict()["retry_count"], 0)
        self.assertTrue(all(attempt.rollout_status == "complete" for attempt in run.attempts))
        self.assertTrue(all(attempt.rollout.comparison == "tie" for attempt in run.attempts))

    def test_presend_failure_and_unknown_send_status_stop_without_a_second_attempt(self) -> None:
        specs = _specs()
        quals = _qualification_rows(specs)
        self.assertEqual(expanded.classify_send_status({"external_send_invocations": 0}), "not_sent")
        self.assertEqual(expanded.classify_send_status({"external_send_invocations": 1}), "sent")
        self.assertEqual(expanded.classify_send_status({}), "unknown")
        self.assertEqual(expanded.classify_send_status({"external_send_invocations": 2}), "send_count_invalid")

        pre_send_calls: list[int] = []

        def pre_send(*_args: object):
            pre_send_calls.append(1)
            return _qualification_payload(outcome="exception", stage="client_settings_invalid", sent=0)

        pre_send_run = expanded.run_authorized_expanded_requests(
            specs, quals, pre_send, owner_authorization_confirmed=True,
        )
        self.assertEqual(pre_send_run.stage, "pre_send_failure_stopped")
        self.assertEqual(pre_send_run.client_invocation_count, 1)
        self.assertEqual(pre_send_calls, [1])

        unknown_calls: list[int] = []

        def unknown(*_args: object):
            unknown_calls.append(1)
            return {"stage": "worker_failure"}

        unknown_run = expanded.run_authorized_expanded_requests(
            specs, quals, unknown, owner_authorization_confirmed=True,
        )
        self.assertEqual(unknown_run.stage, "send_status_unknown_stopped")
        self.assertEqual(unknown_run.client_invocation_count, 1)
        self.assertEqual(unknown_calls, [1])

    def test_known_provider_timeout_is_counted_once_without_retry(self) -> None:
        calls: list[int] = []

        def timeout(*_args: object):
            calls.append(1)
            version, spec, _repeat = _args
            return _qualification_payload(outcome="timeout", stage="model_provider_timeout", sent=1, spec=spec, version=version)

        run = expanded.run_authorized_expanded_requests(
            _specs(), _qualification_rows(_specs()), timeout, owner_authorization_confirmed=True,
        )
        self.assertEqual(run.stage, "complete")
        self.assertEqual(run.client_invocation_count, 32)
        self.assertEqual(run.external_request_count, 32)
        self.assertEqual(len(calls), 32)
        self.assertEqual(run.retry_count, 0)

    def test_known_invalid_suggestion_is_recorded_without_retry_or_false_model_success(self) -> None:
        calls: list[int] = []

        def invalid(*_args: object):
            calls.append(1)
            version, spec, _repeat = _args
            return _qualification_payload(outcome="invalid_suggestion", stage="model_suggestion_invalid", sent=1, spec=spec, version=version)

        run = expanded.run_authorized_expanded_requests(
            _specs(), _qualification_rows(_specs()), invalid, owner_authorization_confirmed=True,
        )
        self.assertEqual(run.stage, "complete")
        self.assertEqual(run.client_invocation_count, 32)
        self.assertEqual(run.external_request_count, 32)
        self.assertEqual(run.retry_count, 0)
        self.assertTrue(all(attempt.result.source == "rule_fallback" for attempt in run.attempts))
        self.assertEqual(len(calls), 32)

    def test_sent_result_state_drift_stops_after_counting_that_attempt(self) -> None:
        specs = _specs()
        rows = _qualification_rows(specs)
        calls: list[int] = []

        def drift(version: str, spec: expanded.ExpandedM2StateSpec, _repeat: int):
            calls.append(1)
            payload = _qualification_payload(spec=spec, version=version)
            payload["state_digest"] = "other-state"
            return payload

        run = expanded.run_authorized_expanded_requests(
            specs, rows, drift, owner_authorization_confirmed=True,
        )
        self.assertEqual(run.stage, "attempt_offline_binding_mismatch_stopped")
        self.assertEqual(run.client_invocation_count, 1)
        self.assertEqual(run.external_request_count, 1)
        self.assertEqual(calls, [1])

    def test_low_sensitivity_state_and_attempt_summaries_exclude_cards_prompts_and_credentials(self) -> None:
        spec_data = _specs()[0].to_dict()
        qualification_data = _qualification_rows(_specs())[0].to_dict()
        encoded = str((spec_data, qualification_data))
        for forbidden in ("hand_cards", "carrier_cards", "prompt\":", "reasoning", "api_key", "base_url", "Cookie"):
            self.assertNotIn(forbidden, encoded)
        self.assertIn("state_digest", spec_data)
        self.assertNotIn("final_candidate_ids", qualification_data)
        self.assertIn("response_action_id", qualification_data)


if __name__ == "__main__":
    unittest.main()
