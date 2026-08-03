from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from agents.game_phase import ENDGAME, MIDGAME, OPENING, GamePhaseContext
from agents.strategy_router import StrategyIntentContext
from evaluation.strategy_router_benchmark import (
    BLOCK_OPPONENT,
    CONTROL,
    RUN_OUT,
    SUPPORT_TEAMMATE,
    StrategyRouteBucket,
    run_strategy_router_benchmark,
)


def _action(action_id: int, pattern: str = "single", carrier_cards: list[str] | None = None) -> dict[str, object]:
    cards = [] if pattern == "pass" else list(carrier_cards or ["9S"])
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"],
        "carrier_cards": cards,
    }


def _observation(*, step_no: int, hand_count: int = 5) -> dict[str, object]:
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_count": hand_count, "hand_cards": ["9S"] * hand_count},
        "current_round": {"step_no": step_no, "round_no": 1, "current_player_id": 1, "current_level_rank": "2", "constraint": "free", "table_action": None},
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 5, "finished": False},
            {"player_id": 3, "team": "team_13", "hand_count": 5, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": 5, "finished": False},
        ],
        "history": {"actions": [], "finish_order": []},
    }


def _phase(name: str) -> GamePhaseContext:
    return GamePhaseContext(name, 5, (5, 5, 5), 15, 0, 0)


def _available(intent: str = CONTROL, *, relation: str | None = None, free: bool = True, strength: str = "non_weak") -> StrategyIntentContext:
    reason = {
        RUN_OUT: "weak_hand",
        BLOCK_OPPONENT: "opponent_urgent",
        SUPPORT_TEAMMATE: "teammate_urgent",
        CONTROL: "stable_control",
    }[intent]
    return StrategyIntentContext(
        status="available", source="public_strategy_router_v1", phase=MIDGAME,
        intent=intent, reason_codes=(reason,), my_player_id=1, my_team="team_13",
        my_hand_count=5, teammate_player_id=3, teammate_hand_count=5,
        minimum_opponent_hand_count=5, urgent_opponent_ids=(), can_finish_now=False,
        is_free_lead=free, table_leader_player_id=None if relation is None else 2,
        table_leader_relation=relation, table_leader_is_urgent=False,
        hand_strength=strength, hand_total_score=50, hand_control_score=10,
        diagnostics=(),
    )


def _unavailable(*diagnostics: str) -> StrategyIntentContext:
    return StrategyIntentContext(
        status="unavailable", source="public_strategy_router_v1", phase=MIDGAME,
        intent=None, reason_codes=(), my_player_id=None, my_team=None,
        my_hand_count=None, teammate_player_id=None, teammate_hand_count=None,
        minimum_opponent_hand_count=None, urgent_opponent_ids=(), can_finish_now=False,
        is_free_lead=False, table_leader_player_id=None, table_leader_relation=None,
        table_leader_is_urgent=False, hand_strength=None, hand_total_score=None,
        hand_control_score=None, diagnostics=diagnostics,
    )


class _FakeAgent:
    created: list[tuple[int, int]] = []

    def __init__(self, *, player_id: int, strategic_pass_rate: int) -> None:
        self.player_id = player_id
        self.strategic_pass_rate = strategic_pass_rate
        self.strategic_pass_opportunity_count = 0
        self.strategic_pass_count = 0
        type(self).created.append((player_id, strategic_pass_rate))

    def select_action(self, _observation: dict[str, object], legal_actions: list[dict[str, object]]) -> int:
        return int(legal_actions[0]["action_id"])


class _FakeGame:
    events: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    stepped_action_ids: list[int] = []

    def __init__(self, **_kwargs: object) -> None:
        self.index = 0
        self.events = [(deepcopy(observation), deepcopy(actions)) for observation, actions in type(self).events]

    def reset(self) -> dict[str, object]:
        return self.observe()

    def observe(self) -> dict[str, object]:
        return deepcopy(self.events[self.index][0])

    def legal_actions(self) -> list[dict[str, object]]:
        return deepcopy(self.events[self.index][1])

    def step(self, action_id: int) -> dict[str, object]:
        valid_ids = {action["action_id"] for action in self.events[self.index][1]}
        if action_id not in valid_ids:
            raise AssertionError("benchmark advanced an action outside legal_actions")
        type(self).stepped_action_ids.append(action_id)
        self.index += 1
        return {"game_over": self.index == len(self.events)}


class StrategyRouterBenchmarkTests(unittest.TestCase):
    def _assert_invalid_context(self, context: object) -> None:
        policy, _, _, _ = self._fake_run(
            [(_observation(step_no=1), [_action(1)])],
            [_phase(MIDGAME)],
            context,
        )
        bucket = policy.by_phase[MIDGAME]
        self.assertEqual((bucket.sample_count, bucket.available_count, bucket.unavailable_count, bucket.invalid_count), (1, 0, 0, 1))
        self.assertEqual(dict(bucket.diagnostic_counts), {"invalid_router_result": 1})
        self.assertEqual(sum(bucket.intent_counts.values()), 0)
        self.assertEqual(sum(bucket.reason_counts.values()), 0)
        self.assertEqual(sum(bucket.table_leader_relation_counts.values()), 0)
        self.assertEqual((bucket.free_lead_count, bucket.follow_count, bucket.weak_count, bucket.non_weak_count), (0, 0, 0, 0))
        self.assertEqual(_FakeGame.stepped_action_ids, [1])

    def _fake_run(
        self,
        events: list[tuple[dict[str, object], list[dict[str, object]]]],
        phases: list[GamePhaseContext],
        routed: object = None,
        *,
        max_steps: int = 20,
        cap: int = 128,
    ):
        _FakeGame.events = events
        _FakeGame.stepped_action_ids = []
        _FakeAgent.created = []
        router_return = _available() if routed is None else routed
        with mock.patch("evaluation.strategy_router_benchmark.GuanDanGame", _FakeGame), mock.patch(
            "evaluation.strategy_router_benchmark.StrategicPassAIAgent", _FakeAgent
        ), mock.patch(
            "evaluation.strategy_router_benchmark.classify_game_phase", side_effect=phases
        ) as classify, mock.patch(
            "evaluation.strategy_router_benchmark.evaluate_hand", return_value={"total_score": 50}
        ) as evaluate, mock.patch(
            "evaluation.strategy_router_benchmark.route_strategy_intent", return_value=router_return
        ) as router:
            report = run_strategy_router_benchmark((7,), strategic_pass_rates=(0,), max_steps=max_steps, max_samples_per_phase_per_game=cap)
        return report.policies[0], classify, evaluate, router

    def test_strict_input_validation(self) -> None:
        bad_calls = (
            {"seeds": ()}, {"seeds": (True,)}, {"seeds": (7, 7)},
            {"seeds": "7"}, {"seeds": (7,), "current_level_rank": "SJ"},
            {"seeds": (7,), "strategic_pass_rates": ()},
            {"seeds": (7,), "strategic_pass_rates": (0, 0)},
            {"seeds": (7,), "strategic_pass_rates": (True,)},
            {"seeds": (7,), "strategic_pass_rates": (101,)},
            {"seeds": (7,), "max_steps": 0}, {"seeds": (7,), "max_steps": True},
            {"seeds": (7,), "max_samples_per_phase_per_game": 0},
            {"seeds": (7,), "max_samples_per_phase_per_game": 1.0},
        )
        for kwargs in bad_calls:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    run_strategy_router_benchmark(**kwargs)  # type: ignore[arg-type]

    def test_ordered_immutable_json_safe_real_game_report_and_determinism(self) -> None:
        first = run_strategy_router_benchmark((7,), strategic_pass_rates=(100, 0, 25), max_steps=5000)
        second = run_strategy_router_benchmark((7,), strategic_pass_rates=(100, 0, 25), max_steps=5000)
        self.assertEqual(first, second)
        self.assertEqual(
            [(item.policy_name, item.strategic_pass_rate) for item in first.policies],
            [("strategic_pass_100", 100), ("forced_only", 0), ("strategic_pass_25", 25)],
        )
        payload = json.dumps(first.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertNotIn("seed", payload)
        self.assertNotIn("action_id", payload)
        self.assertNotIn("hand_cards", payload)
        self.assertNotIn("prompt", payload)
        with self.assertRaises(FrozenInstanceError):
            first.requested_policy_count = 0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            first.policies[0].by_phase[MIDGAME] = first.policies[0].overall  # type: ignore[index]
        with self.assertRaises(TypeError):
            first.policies[0].overall.intent_counts[CONTROL] = 1  # type: ignore[index]
        self.assertEqual(
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            hashlib.sha256(json.dumps(second.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
        )

    def test_skip_order_and_shared_phase_raw_actions_and_single_evaluation(self) -> None:
        events = [
            (_observation(step_no=0), [_action(1, "pass")]),
            (_observation(step_no=1, hand_count=1), [_action(2, "single", ["9S"])]),
            (_observation(step_no=2), [_action(3)]),
            (_observation(step_no=3), [_action(4)]),
        ]
        opening_phase, midgame_phase = _phase(OPENING), _phase(MIDGAME)
        policy, classify, evaluate, router = self._fake_run(events, [opening_phase, midgame_phase])
        self.assertEqual((policy.observed_turn_count, policy.only_pass_skipped_count, policy.finishing_skipped_count, policy.opening_skipped_count), (4, 1, 1, 1))
        self.assertEqual((policy.eligible_sample_count, policy.evaluated_sample_count), (1, 1))
        classify.assert_has_calls([mock.call(events[2][0]), mock.call(events[3][0])])
        evaluate.assert_called_once_with(events[3][0], events[3][1])
        self.assertIs(router.call_args.args[0], evaluate.call_args.args[0])
        self.assertIs(router.call_args.args[1], evaluate.call_args.args[1])
        self.assertIs(router.call_args.kwargs["phase_context"], midgame_phase)
        self.assertEqual(_FakeGame.stepped_action_ids, [1, 2, 3, 4])
        self.assertEqual(_FakeAgent.created, [(1, 0), (2, 0), (3, 0), (4, 0)])

    def test_available_aggregation_and_unavailable_diagnostic_deduplication(self) -> None:
        events = [(_observation(step_no=1), [_action(1)])]
        policy, _, _, _ = self._fake_run(events, [_phase(MIDGAME)], _available(BLOCK_OPPONENT, relation="opponent", free=False, strength="weak"))
        bucket = policy.by_phase[MIDGAME]
        self.assertEqual((bucket.sample_count, bucket.available_count, bucket.intent_counts[BLOCK_OPPONENT]), (1, 1, 1))
        self.assertEqual((bucket.reason_counts["opponent_urgent"], bucket.table_leader_relation_counts["opponent"], bucket.follow_count, bucket.weak_count), (1, 1, 1, 1))
        policy, _, _, _ = self._fake_run(events, [_phase(MIDGAME)], _unavailable("invalid_team:one", "invalid_team:two", "invalid_hand_count"))
        bucket = policy.by_phase[MIDGAME]
        self.assertEqual((bucket.sample_count, bucket.available_count, bucket.unavailable_count), (1, 0, 1))
        self.assertEqual(dict(bucket.diagnostic_counts), {"invalid_hand_count": 1, "invalid_team": 1})

    def test_available_contract_rejects_source_phase_reason_relation_and_bool_counterexamples(self) -> None:
        baseline = _available()
        teammate_controls = replace(
            _available(SUPPORT_TEAMMATE, relation="teammate", free=False),
            reason_codes=("teammate_controls_table",),
        )
        urgent_controls = replace(
            _available(BLOCK_OPPONENT, relation="opponent", free=False),
            reason_codes=("urgent_opponent_controls_table",),
            table_leader_is_urgent=True,
        )
        can_finish = replace(
            _available(RUN_OUT),
            reason_codes=("can_finish_now",),
            can_finish_now=True,
        )
        invalid_contexts: list[object] = [
            replace(baseline, source="wrong"),
            replace(baseline, phase=ENDGAME),
            replace(baseline, status="wrong"),
            replace(baseline, diagnostics=("invalid_team",)),
            replace(baseline, diagnostics=[]),  # type: ignore[arg-type]
            replace(baseline, urgent_opponent_ids=[]),  # type: ignore[arg-type]
            replace(baseline, intent="unknown"),
            replace(baseline, reason_codes=()),
            replace(baseline, reason_codes=("stable_control", "weak_hand")),
            replace(baseline, reason_codes=["stable_control"]),  # type: ignore[arg-type]
            replace(baseline, reason_codes=(1,)),
            replace(baseline, reason_codes=("unknown_reason",)),
            replace(baseline, intent=RUN_OUT, reason_codes=("stable_control",)),
            replace(baseline, intent=BLOCK_OPPONENT, reason_codes=("weak_hand",)),
            replace(baseline, intent=SUPPORT_TEAMMATE, reason_codes=("opponent_urgent",)),
            replace(baseline, intent=CONTROL, reason_codes=("teammate_urgent",)),
            replace(baseline, table_leader_relation="invalid"),
            replace(baseline, is_free_lead=1),
            replace(baseline, can_finish_now=1),
            replace(baseline, table_leader_is_urgent=1),
            replace(baseline, hand_strength="strong"),
            replace(baseline, can_finish_now=True),
            replace(can_finish, can_finish_now=False),
            replace(teammate_controls, table_leader_relation="opponent"),
            replace(urgent_controls, table_leader_relation="teammate"),
            replace(urgent_controls, table_leader_is_urgent=False),
            replace(baseline, table_leader_player_id=2),
            replace(teammate_controls, table_leader_player_id=True),
            replace(teammate_controls, table_leader_player_id=5),
            replace(teammate_controls, is_free_lead=True),
        ]
        for context in invalid_contexts:
            with self.subTest(context=context):
                self._assert_invalid_context(context)

    def test_every_allowed_available_reason_is_accepted(self) -> None:
        reasons = {
            RUN_OUT: ("can_finish_now", "weak_hand"),
            BLOCK_OPPONENT: (
                "urgent_opponent_controls_table", "opponent_more_urgent",
                "urgency_tie_block_opponent", "opponent_urgent",
            ),
            SUPPORT_TEAMMATE: ("teammate_controls_table", "teammate_more_urgent", "teammate_urgent"),
            CONTROL: ("stable_control",),
        }
        for intent, items in reasons.items():
            for reason in items:
                relation = "teammate" if reason == "teammate_controls_table" else "opponent" if reason == "urgent_opponent_controls_table" else None
                context = replace(
                    _available(intent, relation=relation, free=relation is None),
                    reason_codes=(reason,),
                    can_finish_now=reason == "can_finish_now",
                    table_leader_is_urgent=reason == "urgent_opponent_controls_table",
                )
                with self.subTest(intent=intent, reason=reason):
                    policy, _, _, _ = self._fake_run([(_observation(step_no=1), [_action(1)])], [_phase(MIDGAME)], context)
                    bucket = policy.by_phase[MIDGAME]
                    self.assertEqual((bucket.available_count, bucket.invalid_count, bucket.reason_counts[reason]), (1, 0, 1))

    def test_unavailable_contract_rejects_partial_or_malformed_contexts(self) -> None:
        baseline = _unavailable("invalid_team", "invalid_team:again")
        invalid_contexts: list[object] = [
            replace(baseline, source="wrong"),
            replace(baseline, phase=ENDGAME),
            replace(baseline, diagnostics=()),
            replace(baseline, diagnostics=["invalid_team"]),  # type: ignore[arg-type]
            replace(baseline, diagnostics=(1,)),
            replace(baseline, diagnostics=("",)),
            replace(baseline, diagnostics=(" invalid_team",)),
            replace(baseline, diagnostics=("invalid_team ",)),
            replace(baseline, intent=CONTROL),
            replace(baseline, reason_codes=("stable_control",)),
            replace(baseline, my_player_id=1),
            replace(baseline, my_team="team_13"),
            replace(baseline, my_hand_count=1),
            replace(baseline, teammate_player_id=3),
            replace(baseline, teammate_hand_count=1),
            replace(baseline, minimum_opponent_hand_count=1),
            replace(baseline, table_leader_player_id=2),
            replace(baseline, table_leader_relation="opponent"),
            replace(baseline, hand_strength="weak"),
            replace(baseline, hand_total_score=1),
            replace(baseline, hand_control_score=1),
            replace(baseline, urgent_opponent_ids=(2,)),
            replace(baseline, urgent_opponent_ids=[2]),  # type: ignore[arg-type]
            replace(baseline, can_finish_now=True),
            replace(baseline, can_finish_now=0),
            replace(baseline, is_free_lead=True),
            replace(baseline, is_free_lead=0),
            replace(baseline, table_leader_is_urgent=True),
            replace(baseline, table_leader_is_urgent=0),
        ]
        for context in invalid_contexts:
            with self.subTest(context=context):
                self._assert_invalid_context(context)

    def test_invalid_router_duplicate_limit_and_max_step_diagnostics(self) -> None:
        events = [(_observation(step_no=1), [_action(1)])]
        policy, _, _, _ = self._fake_run(events, [_phase(MIDGAME)], object())
        self.assertEqual((policy.overall.invalid_count, dict(policy.diagnostic_counts)), (1, {"invalid_router_result": 1}))

        duplicate_events = [(_observation(step_no=1), [_action(1)]), (_observation(step_no=1), [_action(2)])]
        policy, _, _, _ = self._fake_run(duplicate_events, [_phase(MIDGAME), _phase(MIDGAME)])
        self.assertEqual((policy.eligible_sample_count, policy.evaluated_sample_count, policy.duplicate_sample_count), (2, 1, 1))
        self.assertEqual(policy.diagnostic_counts["duplicate_sample"], 1)

        limit_events = [(_observation(step_no=1), [_action(1)]), (_observation(step_no=2), [_action(2)])]
        policy, _, _, _ = self._fake_run(limit_events, [_phase(ENDGAME), _phase(ENDGAME)], cap=1)
        self.assertEqual((policy.eligible_sample_count, policy.evaluated_sample_count, policy.sample_limit_skipped_count), (2, 1, 1))
        self.assertEqual(policy.diagnostic_counts["sample_limit_reached"], 1)

        _FakeGame.events = [
            (_observation(step_no=1), [_action(1)]),
            (_observation(step_no=2), [_action(2)]),
        ]
        _FakeGame.stepped_action_ids = []
        with mock.patch("evaluation.strategy_router_benchmark.GuanDanGame", _FakeGame), mock.patch(
            "evaluation.strategy_router_benchmark.StrategicPassAIAgent", _FakeAgent
        ):
            report = run_strategy_router_benchmark((7,), strategic_pass_rates=(0,), max_steps=1)
        self.assertEqual((report.policies[0].completed_game_count, report.policies[0].incomplete_game_count), (0, 1))
        self.assertEqual(report.policies[0].diagnostic_counts["max_steps_reached"], 1)

    def test_hand_evaluation_and_router_exceptions_are_invalid_without_leaking_text(self) -> None:
        events = [(_observation(step_no=1), [_action(1)])]
        _FakeGame.events = events
        _FakeGame.stepped_action_ids = []
        with mock.patch("evaluation.strategy_router_benchmark.GuanDanGame", _FakeGame), mock.patch(
            "evaluation.strategy_router_benchmark.StrategicPassAIAgent", _FakeAgent
        ), mock.patch(
            "evaluation.strategy_router_benchmark.classify_game_phase", return_value=_phase(MIDGAME)
        ), mock.patch(
            "evaluation.strategy_router_benchmark.evaluate_hand", side_effect=RuntimeError("private detail")
        ):
            hand_error = run_strategy_router_benchmark((7,), strategic_pass_rates=(0,))
        self.assertEqual(dict(hand_error.policies[0].overall.diagnostic_counts), {"hand_evaluation_error": 1})

        _FakeGame.events = events
        _FakeGame.stepped_action_ids = []
        with mock.patch("evaluation.strategy_router_benchmark.GuanDanGame", _FakeGame), mock.patch(
            "evaluation.strategy_router_benchmark.StrategicPassAIAgent", _FakeAgent
        ), mock.patch(
            "evaluation.strategy_router_benchmark.classify_game_phase", return_value=_phase(MIDGAME)
        ), mock.patch(
            "evaluation.strategy_router_benchmark.evaluate_hand", return_value={"total_score": 50}
        ), mock.patch(
            "evaluation.strategy_router_benchmark.route_strategy_intent", side_effect=RuntimeError("private detail")
        ):
            router_error = run_strategy_router_benchmark((7,), strategic_pass_rates=(0,))
        payload = json.dumps(router_error.to_dict(), allow_nan=False)
        self.assertEqual(dict(router_error.policies[0].overall.diagnostic_counts), {"router_error": 1})
        self.assertNotIn("private detail", payload)

    def test_phase_to_overall_conservation_and_policy_agent_boundaries(self) -> None:
        report = run_strategy_router_benchmark((7, 8), strategic_pass_rates=(0, 100), max_steps=5000)
        forced, strategic = report.policies
        self.assertEqual(forced.strategic_pass_count, 0)
        self.assertEqual(strategic.strategic_pass_count, strategic.strategic_pass_opportunity_count)
        for policy in report.policies:
            overall = policy.overall
            buckets = tuple(policy.by_phase.values())
            self.assertEqual(policy.evaluated_sample_count, overall.sample_count)
            self.assertEqual(sum(bucket.sample_count for bucket in buckets), overall.sample_count)
            self.assertEqual(sum(bucket.available_count for bucket in buckets), overall.available_count)
            self.assertEqual(sum(bucket.unavailable_count for bucket in buckets), overall.unavailable_count)
            self.assertEqual(sum(bucket.invalid_count for bucket in buckets), overall.invalid_count)
            self.assertEqual(overall.sample_count, overall.available_count + overall.unavailable_count + overall.invalid_count)
            self.assertEqual(sum(overall.intent_counts.values()), overall.available_count)
            self.assertEqual(sum(overall.reason_counts.values()), overall.available_count)
            self.assertEqual(sum(overall.table_leader_relation_counts.values()), overall.available_count)
            self.assertEqual(overall.free_lead_count + overall.follow_count, overall.available_count)
            self.assertEqual(overall.weak_count + overall.non_weak_count, overall.available_count)
            self.assertEqual(policy.observed_turn_count, policy.only_pass_skipped_count + policy.finishing_skipped_count + policy.opening_skipped_count + policy.eligible_sample_count)
            self.assertEqual(policy.eligible_sample_count, policy.duplicate_sample_count + policy.sample_limit_skipped_count + policy.evaluated_sample_count)

    def test_source_and_runtime_boundaries(self) -> None:
        source = Path("evaluation/strategy_router_benchmark.py").read_text(encoding="utf-8")
        for forbidden in ("DeepSeek", "api_key", "os.environ", "game._state", "ground_truth", "benchmark_truth", "urlopen"):
            self.assertNotIn(forbidden, source)
        for directory in ("agents", "cli", "rag"):
            for path in Path(directory).rglob("*.py"):
                self.assertNotIn("strategy_router_benchmark", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
