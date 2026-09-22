"""No-network regressions for the reproducible H3 model-probe qualification."""

import unittest
from unittest.mock import patch

from evaluation.h3_model_probe_fixtures import (
    ProbeFixture,
    QualificationStage,
    SCENARIO_NAMES,
    build_h3_model_probe_fixtures,
    qualify_h3_model_probe_fixture,
    qualify_h3_model_probe_fixtures,
)


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


if __name__ == "__main__":
    unittest.main()
