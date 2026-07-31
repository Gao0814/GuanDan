"""Tests for isolated strategic-pass marginal corpus variants."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.marginal_benchmark import aggregate_marginal_reports
from evaluation.marginal_corpus import MarginalCorpusReport, run_marginal_corpus
from evaluation.marginal_policy_corpus import run_marginal_policy_corpus


def _empty_corpus() -> MarginalCorpusReport:
    overall = aggregate_marginal_reports((), phase="overall")
    external = {
        name: aggregate_marginal_reports((), phase="critical_endgame")
        for name in ("external_0_4", "external_5_8", "external_9_12")
    }
    from types import MappingProxyType

    return MarginalCorpusReport(
        requested_game_count=0,
        completed_game_count=0,
        incomplete_game_count=0,
        eligible_sample_count=0,
        evaluated_sample_count=0,
        valid_sample_count=0,
        invalid_sample_count=0,
        sample_limit_skipped_count=0,
        overall=overall,
        by_external_count=MappingProxyType(external),
        diagnostic_counts=MappingProxyType({}),
    )


class MarginalPolicyCorpusTests(unittest.TestCase):
    def test_default_and_custom_policy_names_preserve_rate_order(self) -> None:
        with patch(
            "evaluation.marginal_policy_corpus.run_marginal_corpus",
            return_value=_empty_corpus(),
        ):
            default = run_marginal_policy_corpus([1])
            custom = run_marginal_policy_corpus([1], strategic_pass_rates=(100, 0, 50))

        self.assertEqual(
            tuple(default.by_policy),
            ("forced_only", "strategic_pass_25", "strategic_pass_50", "strategic_pass_100"),
        )
        self.assertEqual(
            tuple(custom.by_policy),
            ("strategic_pass_100", "forced_only", "strategic_pass_50"),
        )

    def test_invalid_rates_fail_before_starting_any_corpus(self) -> None:
        invalid_rates = ((), "0", [0, 0], [True], [-1], [101], ["25"])
        with patch("evaluation.marginal_policy_corpus.run_marginal_corpus") as corpus:
            for rates in invalid_rates:
                with self.subTest(rates=rates):
                    with self.assertRaises(ValueError):
                        run_marginal_policy_corpus([1], strategic_pass_rates=rates)  # type: ignore[arg-type]
        self.assertEqual(corpus.call_count, 0)

    def test_each_policy_has_fresh_factory_agents_and_forwarded_parameters(self) -> None:
        calls: list[tuple[int, int, int]] = []

        def fake_corpus(seeds: object, **kwargs: object) -> MarginalCorpusReport:
            factory = kwargs["agent_factory"]
            self.assertEqual(seeds, (7, 8))
            self.assertEqual(
                {name: kwargs[name] for name in (
                    "current_level_rank", "max_steps", "max_samples_per_game",
                    "max_external_cards", "max_search_nodes", "max_solutions",
                )},
                {
                    "current_level_rank": "5", "max_steps": 99,
                    "max_samples_per_game": 7, "max_external_cards": 12,
                    "max_search_nodes": 111, "max_solutions": 222,
                },
            )
            for seed in (7, 8):
                for player_id in (1, 2, 3, 4):
                    agent = factory(seed, player_id)  # type: ignore[operator]
                    calls.append((agent.strategic_pass_rate, seed, player_id))
            return _empty_corpus()

        with patch(
            "evaluation.marginal_policy_corpus.run_marginal_corpus",
            side_effect=fake_corpus,
        ) as corpus:
            report = run_marginal_policy_corpus(
                (7, 8), strategic_pass_rates=(0, 100), current_level_rank="5",
                max_steps=99, max_samples_per_game=7, max_external_cards=12,
                max_search_nodes=111, max_solutions=222,
            )

        self.assertEqual(corpus.call_count, 2)
        self.assertEqual(calls, [
            *( (0, seed, player) for seed in (7, 8) for player in (1, 2, 3, 4) ),
            *( (100, seed, player) for seed in (7, 8) for player in (1, 2, 3, 4) ),
        ])
        self.assertIsNot(report.by_policy["forced_only"].corpus, report.by_policy["strategic_pass_100"].corpus)

    def test_rate_zero_corpus_matches_default_collector(self) -> None:
        direct = run_marginal_corpus([60], max_steps=500, max_samples_per_game=2)
        wrapped = run_marginal_policy_corpus(
            [60], strategic_pass_rates=(0,), max_steps=500, max_samples_per_game=2,
        )

        variant = wrapped.by_policy["forced_only"]
        self.assertEqual(variant.corpus, direct)
        self.assertEqual(variant.strategic_pass_count, 0)
        self.assertLessEqual(
            variant.strategic_pass_count,
            variant.strategic_pass_opportunity_count,
        )

    def test_rate_boundaries_and_determinism_with_small_public_games(self) -> None:
        first = run_marginal_policy_corpus(
            [60], strategic_pass_rates=(0, 100), max_steps=500, max_samples_per_game=2,
        )
        second = run_marginal_policy_corpus(
            [60], strategic_pass_rates=(0, 100), max_steps=500, max_samples_per_game=2,
        )

        self.assertEqual(first, second)
        forced = first.by_policy["forced_only"]
        maximum = first.by_policy["strategic_pass_100"]
        self.assertEqual(forced.strategic_pass_count, 0)
        self.assertEqual(
            maximum.strategic_pass_count,
            maximum.strategic_pass_opportunity_count,
        )
        for variant in first.by_policy.values():
            self.assertLessEqual(
                variant.strategic_pass_count,
                variant.strategic_pass_opportunity_count,
            )

    def test_corpus_failure_propagates_without_partial_top_level_report(self) -> None:
        with patch(
            "evaluation.marginal_policy_corpus.run_marginal_corpus",
            side_effect=RuntimeError("collector failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "collector failure"):
                run_marginal_policy_corpus([1], strategic_pass_rates=(0, 25))

    def test_report_is_immutable_json_safe_and_does_not_expose_sensitive_detail(self) -> None:
        report = run_marginal_policy_corpus(
            [60], strategic_pass_rates=(0,), max_steps=500, max_samples_per_game=1,
        )
        with self.assertRaises(FrozenInstanceError):
            report.requested_policy_count = 0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            report.by_policy["other"] = report.by_policy["forced_only"]  # type: ignore[index]
        payload = report.to_dict()
        encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
        self.assertEqual(
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            hashlib.sha256(json.dumps(report.to_dict(), allow_nan=False, sort_keys=True).encode("utf-8")).hexdigest(),
        )
        for forbidden in ("seed", "observation", "ground_truth", "player_id", "hand_cards", "3S"):
            self.assertNotIn(forbidden, encoded)

    def test_runtime_modules_do_not_import_the_new_evaluation_wrapper(self) -> None:
        for folder in ("agents", "cli", "rag"):
            for path in Path(folder).rglob("*.py"):
                self.assertNotIn("marginal_policy_corpus", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
