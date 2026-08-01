"""Tests for public-only runtime confidence assembly."""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from agents.card_confidence import CardConfidenceState
from agents.card_confidence_pipeline import build_runtime_card_confidence
from agents.game_phase import CRITICAL_ENDGAME, GamePhaseContext


def _context(phase: str = CRITICAL_ENDGAME) -> GamePhaseContext:
    return GamePhaseContext(phase, 10, (4, 4, 4), 12, 9, 0)


def _available() -> CardConfidenceState:
    return CardConfidenceState(
        phase=CRITICAL_ENDGAME,
        status="available",
        source="physical_assignment_marginal_v1",
        calibration_scope="critical_endgame_policy_diverse_v1",
        external_unknown_count=1,
        physical_assignment_count=1,
        players=(),
        diagnostics=(),
    )


class CardConfidencePipelineTests(unittest.TestCase):
    def test_critical_path_calls_each_public_layer_once_in_order(self) -> None:
        observation = {"public": "value"}
        belief = object()
        constraints = object()
        allocation = object()
        events: list[str] = []

        def build_belief(received_observation, received_context):
            events.append("belief")
            self.assertIs(received_observation, observation)
            self.assertIs(received_context, _context_value)
            return belief

        def build_constraints(received_belief):
            events.append("constraints")
            self.assertIs(received_belief, belief)
            return constraints

        def allocate(received_belief, received_constraints, **limits):
            events.append("allocation")
            self.assertIs(received_belief, belief)
            self.assertIs(received_constraints, constraints)
            self.assertEqual(limits, {"max_external_cards": 12, "max_search_nodes": 9, "max_solutions": 8})
            return allocation

        def build_confidence(received_belief, received_constraints, received_allocation):
            events.append("confidence")
            self.assertIs(received_allocation, allocation)
            return _available()

        _context_value = _context()
        with (
            patch("agents.card_confidence_pipeline.build_card_belief", side_effect=build_belief),
            patch("agents.card_confidence_pipeline.build_card_constraints", side_effect=build_constraints),
            patch("agents.card_confidence_pipeline.enumerate_card_allocations", side_effect=allocate),
            patch("agents.card_confidence_pipeline.build_card_confidence", side_effect=build_confidence),
        ):
            result = build_runtime_card_confidence(observation, _context_value, max_search_nodes=9, max_solutions=8)

        self.assertEqual(result, _available())
        self.assertEqual(events, ["belief", "constraints", "allocation", "confidence"])

    def test_noncritical_and_invalid_context_do_not_start_pipeline(self) -> None:
        for phase in ("opening", "midgame", "endgame", "near_open_endgame"):
            with self.subTest(phase=phase), patch(
                "agents.card_confidence_pipeline.build_card_belief",
                side_effect=AssertionError("must not run"),
            ):
                result = build_runtime_card_confidence({}, _context(phase))
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(result.diagnostics, ("unsupported_phase",))
        result = build_runtime_card_confidence({}, object())  # type: ignore[arg-type]
        self.assertEqual(result.diagnostics, ("invalid_phase_context",))

    def test_layer_exceptions_are_normalized_and_builder_unavailable_is_preserved(self) -> None:
        for target in (
            "build_card_belief", "build_card_constraints", "enumerate_card_allocations", "build_card_confidence",
        ):
            with self.subTest(target=target), patch(
                f"agents.card_confidence_pipeline.{target}",
                side_effect=RuntimeError("private detail"),
            ):
                result = build_runtime_card_confidence({}, _context())
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(result.diagnostics, ("pipeline_error",))
        unavailable = CardConfidenceState(CRITICAL_ENDGAME, "unavailable", "none", "none", 0, 0, (), ("allocation_not_complete",))
        with (
            patch("agents.card_confidence_pipeline.build_card_belief", return_value=object()),
            patch("agents.card_confidence_pipeline.build_card_constraints", return_value=object()),
            patch("agents.card_confidence_pipeline.enumerate_card_allocations", return_value=object()),
            patch("agents.card_confidence_pipeline.build_card_confidence", return_value=unavailable),
        ):
            self.assertIs(build_runtime_card_confidence({}, _context()), unavailable)

    def test_limits_are_strict_and_output_is_json_safe(self) -> None:
        for keyword in ("max_external_cards", "max_search_nodes", "max_solutions"):
            for value in (0, -1, 1.5, True):
                with self.subTest(keyword=keyword, value=value):
                    with self.assertRaises(ValueError):
                        build_runtime_card_confidence({}, _context(), **{keyword: value})
        with self.assertRaises(ValueError):
            build_runtime_card_confidence({}, _context(), max_external_cards=13)
        result = build_runtime_card_confidence({}, _context("opening"))
        self.assertIsInstance(json.dumps(result.to_dict(), allow_nan=False), str)
        self.assertNotIn("public", json.dumps(result.to_dict()))


if __name__ == "__main__":
    unittest.main()
