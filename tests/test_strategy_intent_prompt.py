from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from agents.game_phase import GamePhaseContext, MIDGAME
from agents.strategy_intent_prompt import (
    StrategyIntentPromptPayload,
    build_strategy_intent_prompt_payload,
)
from agents.strategy_router import StrategyIntentContext, route_strategy_intent


_SOURCE = "public_strategy_router_v1"
_TEAM = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}


class _DerivedStrategyIntentContext(StrategyIntentContext):
    pass


def _context(
    reason: str = "stable_control",
    *,
    phase: str = "critical_endgame",
) -> StrategyIntentContext:
    intent_by_reason = {
        "can_finish_now": "run_out",
        "weak_hand": "run_out",
        "stable_control": "control",
        "teammate_controls_table": "support_teammate",
        "urgent_opponent_controls_table": "block_opponent",
        "teammate_more_urgent": "support_teammate",
        "opponent_more_urgent": "block_opponent",
        "urgency_tie_block_opponent": "block_opponent",
        "opponent_urgent": "block_opponent",
        "teammate_urgent": "support_teammate",
    }
    values: dict[str, object] = {
        "status": "available",
        "source": _SOURCE,
        "phase": phase,
        "intent": intent_by_reason[reason],
        "reason_codes": (reason,),
        "my_player_id": 1,
        "my_team": "team_13",
        "my_hand_count": 7,
        "teammate_player_id": 3,
        "teammate_hand_count": 5,
        "minimum_opponent_hand_count": 5,
        "urgent_opponent_ids": (),
        "can_finish_now": reason == "can_finish_now",
        "is_free_lead": True,
        "table_leader_player_id": None,
        "table_leader_relation": None,
        "table_leader_is_urgent": False,
        "hand_strength": "weak" if reason == "weak_hand" else "non_weak",
        "hand_total_score": 30 if reason == "weak_hand" else 50,
        "hand_control_score": 10,
        "diagnostics": (),
    }
    if reason == "teammate_controls_table":
        values.update(is_free_lead=False, table_leader_player_id=3, table_leader_relation="teammate")
    elif reason == "urgent_opponent_controls_table":
        values.update(
            is_free_lead=False,
            table_leader_player_id=2,
            table_leader_relation="opponent",
            table_leader_is_urgent=True,
            minimum_opponent_hand_count=2,
            urgent_opponent_ids=(2,),
        )
    elif reason == "teammate_more_urgent":
        values.update(teammate_hand_count=1, minimum_opponent_hand_count=2, urgent_opponent_ids=(2,))
    elif reason == "opponent_more_urgent":
        values.update(teammate_hand_count=2, minimum_opponent_hand_count=1, urgent_opponent_ids=(2,))
    elif reason == "urgency_tie_block_opponent":
        values.update(teammate_hand_count=2, minimum_opponent_hand_count=2, urgent_opponent_ids=(2,))
    elif reason == "opponent_urgent":
        values.update(minimum_opponent_hand_count=2, urgent_opponent_ids=(2,))
    elif reason == "teammate_urgent":
        values.update(teammate_hand_count=2, minimum_opponent_hand_count=5)
    return StrategyIntentContext(**values)  # type: ignore[arg-type]


def _router_fixture(
    *,
    my_player_id: int,
    hand_counts: dict[int, int],
    finished_ids: set[int],
    table_leader_id: int | None,
    step_no: int,
    round_no: int,
    table_action: dict[str, object] | None = None,
) -> StrategyIntentContext:
    action = table_action or {
        "declared_pattern": "single",
        "declared_cards": ["8"],
        "carrier_cards": ["8S"],
    }
    history_actions: list[dict[str, object]] = [
        {
            "step_no": index,
            "round_no": max(1, round_no - 1),
            "player_id": ((index - 1) % 4) + 1,
            "declared_pattern": "pass",
            "declared_cards": [],
            "carrier_cards": [],
        }
        for index in range(1, step_no)
    ]
    if table_leader_id is not None:
        history_actions.append({
            "step_no": step_no,
            "round_no": round_no,
            "player_id": table_leader_id,
            **deepcopy(action),
        })
    else:
        history_actions.append({
            "step_no": step_no,
            "round_no": max(1, round_no - 1),
            "player_id": ((step_no - 1) % 4) + 1,
            "declared_pattern": "pass",
            "declared_cards": [],
            "carrier_cards": [],
        })
    snapshot = {
        "my_info": {"player_id": my_player_id, "team": _TEAM[my_player_id], "hand_count": hand_counts[my_player_id]},
        "other_players": [
            {"player_id": player_id, "team": _TEAM[player_id], "hand_count": hand_counts[player_id], "finished": player_id in finished_ids}
            for player_id in (1, 2, 3, 4)
            if player_id != my_player_id
        ],
        "current_round": {
            "step_no": step_no,
            "round_no": round_no,
            "current_player_id": my_player_id,
            "constraint": "free" if table_leader_id is None else "single:8",
            "table_action": None if table_leader_id is None else deepcopy(action),
        },
        "history": {"actions": history_actions, "finish_order": sorted(finished_ids)},
    }
    others = snapshot["other_players"]
    assert isinstance(others, list)
    phase = GamePhaseContext(
        MIDGAME,
        hand_counts[my_player_id],
        tuple(item["hand_count"] for item in others),
        sum(item["hand_count"] for item in others if not item["finished"]),
        len(history_actions),
        len(finished_ids),
    )
    return route_strategy_intent(
        snapshot,
        [{"declared_pattern": "single", "declared_cards": ["9"], "carrier_cards": ["9S"]}],
        phase_context=phase,
        hand_evaluation={"total_score": 50, "control_score": 10, "label": "中等"},
    )


class TestStrategyIntentPrompt(unittest.TestCase):
    def test_all_locked_intent_reason_pairs_have_exact_ready_text(self) -> None:
        expected = {
            "can_finish_now": ("run_out", "加速走牌", "本次可直接出完"),
            "weak_hand": ("run_out", "加速走牌", "手牌偏弱，优先减少手数"),
            "stable_control": ("control", "控制牌权", "手牌控制力稳定"),
            "teammate_controls_table": ("support_teammate", "支援队友", "队友当前控桌"),
            "urgent_opponent_controls_table": ("block_opponent", "阻断对手", "紧急对手当前控桌"),
            "teammate_more_urgent": ("support_teammate", "支援队友", "队友跑牌更紧迫"),
            "opponent_more_urgent": ("block_opponent", "阻断对手", "对手威胁更紧迫"),
            "urgency_tie_block_opponent": ("block_opponent", "阻断对手", "双方同样紧迫，优先阻断对手"),
            "opponent_urgent": ("block_opponent", "阻断对手", "对手接近出完"),
            "teammate_urgent": ("support_teammate", "支援队友", "队友接近出完"),
        }
        for reason, (intent, intent_text, reason_text) in expected.items():
            with self.subTest(reason=reason):
                payload = build_strategy_intent_prompt_payload(_context(reason))
                self.assertEqual((payload.status, payload.intent, payload.diagnostics), ("ready", intent, ()))
                self.assertEqual(
                    payload.text,
                    "\n".join((
                        "范围：critical_endgame",
                        f"策略意图：{intent_text}",
                        f"公开依据：{reason_text}",
                        "边界：这是公开局面下的策略偏好，不是隐藏牌事实或合法性结论；只能从候选动作中选择。",
                    )),
                )
                self.assertEqual(payload.char_count, len(payload.text))

    def test_three_public_route_snapshots(self) -> None:
        steel_plate = {
            "declared_pattern": "steel_plate",
            "declared_cards": ["Q", "Q", "Q", "K", "K", "K"],
            "carrier_cards": ["QS", "QH", "QC", "KS", "KH", "KC"],
        }
        cases = (
            (
                _router_fixture(my_player_id=1, hand_counts={1: 8, 2: 8, 3: 8, 4: 8}, finished_ids=set(), table_leader_id=3, step_no=16, round_no=2, table_action=steel_plate),
                "support_teammate", "队友当前控桌",
            ),
            (
                _router_fixture(my_player_id=3, hand_counts={1: 1, 2: 8, 3: 7, 4: 2}, finished_ids=set(), table_leader_id=4, step_no=16, round_no=16),
                "block_opponent", "紧急对手当前控桌",
            ),
            (
                _router_fixture(my_player_id=2, hand_counts={1: 1, 2: 7, 3: 8, 4: 0}, finished_ids={4}, table_leader_id=None, step_no=20, round_no=20),
                "block_opponent", "对手接近出完",
            ),
        )
        for context, intent, reason_text in cases:
            with self.subTest(intent=intent, phase=context.phase):
                payload = build_strategy_intent_prompt_payload(context)
                self.assertEqual(
                    payload.to_dict(),
                    {
                        "status": "ready",
                        "source": "strategy_intent_prompt_v1",
                        "router_source": _SOURCE,
                        "phase": context.phase,
                        "intent": intent,
                        "text": "\n".join((
                            f"范围：{context.phase}",
                            "策略意图：支援队友" if intent == "support_teammate" else "策略意图：阻断对手",
                            f"公开依据：{reason_text}",
                            "边界：这是公开局面下的策略偏好，不是隐藏牌事实或合法性结论；只能从候选动作中选择。",
                        )),
                        "char_count": payload.char_count,
                        "diagnostics": [],
                    },
                )

    def test_omits_bad_status_type_source_phase_and_diagnostics_without_leaking_values(self) -> None:
        base = _context()
        derived = _DerivedStrategyIntentContext(
            **{name: getattr(base, name) for name in base.__dataclass_fields__}
        )
        cases = (
            (object(), "invalid_context_type"),
            (derived, "invalid_context_type"),
            (replace(base, status="unavailable", diagnostics=("untrusted: detail",)), "context_unavailable"),
            (replace(base, source="untrusted-source"), "invalid_router_source"),
            (replace(base, phase="opening"), "invalid_phase"),
            (replace(base, diagnostics=("unknown: injected",)), "invalid_context_fields"),
            (replace(base, diagnostics=["not-a-tuple"]), "invalid_context_fields"),  # type: ignore[arg-type]
        )
        for context, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                payload = build_strategy_intent_prompt_payload(context)  # type: ignore[arg-type]
                self.assertEqual(payload.status, "omitted")
                self.assertIn(diagnostic, payload.diagnostics)
                self.assertEqual((payload.router_source, payload.phase, payload.intent, payload.text, payload.char_count), (None, None, None, "", 0))
                self.assertNotIn("untrusted", " ".join(payload.diagnostics))

    def test_omits_invalid_intent_reason_and_context_semantics(self) -> None:
        base = _context()
        cases = (
            replace(base, intent="unknown"),
            replace(base, intent=["control"]),  # type: ignore[arg-type]
            replace(base, reason_codes=("unknown_reason",)),
            replace(base, reason_codes=(["stable_control"],)),  # type: ignore[arg-type]
            replace(base, reason_codes=()),
            replace(base, reason_codes=("stable_control", "weak_hand")),
            replace(base, reason_codes=["stable_control"]),  # type: ignore[arg-type]
            replace(base, intent="control", reason_codes=("weak_hand",)),
            replace(base, can_finish_now=True),
            replace(_context("teammate_controls_table"), table_leader_relation="opponent"),
            replace(_context("urgent_opponent_controls_table"), table_leader_is_urgent=False),
        )
        for context in cases:
            with self.subTest(context=context):
                payload = build_strategy_intent_prompt_payload(context)
                self.assertEqual(payload.status, "omitted")
                self.assertTrue(set(payload.diagnostics) & {"invalid_intent_reason", "invalid_context_fields"})

    def test_omits_strict_bool_player_capacity_leader_and_strength_violations(self) -> None:
        base = _context()
        cases = (
            replace(base, my_player_id=True),
            replace(base, my_hand_count=True),
            replace(base, teammate_hand_count="5"),
            replace(base, minimum_opponent_hand_count=1.0),
            replace(base, hand_total_score=True),
            replace(base, hand_control_score=31),
            replace(base, my_team="team_24"),
            replace(base, teammate_player_id=2),
            replace(base, urgent_opponent_ids=(3,)),
            replace(base, urgent_opponent_ids=([],)),  # type: ignore[arg-type]
            replace(base, hand_strength="strong"),
            replace(base, hand_strength=["weak"]),  # type: ignore[arg-type]
            replace(base, is_free_lead=1),  # type: ignore[arg-type]
            replace(base, table_leader_is_urgent=1),  # type: ignore[arg-type]
            replace(base, table_leader_relation="opponent", table_leader_player_id=None),
            replace(base, table_leader_relation=[]),  # type: ignore[arg-type]
            replace(base, is_free_lead=True, table_leader_relation="opponent", table_leader_player_id=2),
        )
        for context in cases:
            with self.subTest(context=context):
                payload = build_strategy_intent_prompt_payload(context)
                self.assertEqual((payload.status, payload.diagnostics), ("omitted", ("invalid_context_fields",)))

    def test_opening_unavailable_and_budget_are_fail_closed(self) -> None:
        context = _context()
        ready = build_strategy_intent_prompt_payload(context)
        self.assertEqual(build_strategy_intent_prompt_payload(context, max_chars=len(ready.text)).status, "ready")
        self.assertEqual(
            build_strategy_intent_prompt_payload(context, max_chars=len(ready.text) - 1).diagnostics,
            ("prompt_budget_exceeded",),
        )
        for bad_max in (0, -1, 1.5, True, "800"):
            with self.subTest(max_chars=bad_max):
                with self.assertRaises(ValueError):
                    build_strategy_intent_prompt_payload(context, max_chars=bad_max)  # type: ignore[arg-type]
        self.assertEqual(
            build_strategy_intent_prompt_payload(replace(context, phase="opening")).diagnostics,
            ("invalid_phase",),
        )

    def test_preregistered_cross_field_counterexamples_fail_closed(self) -> None:
        cases = (
            (replace(_context(), minimum_opponent_hand_count=1, urgent_opponent_ids=(2,)), "invalid_intent_reason"),
            (replace(_context("weak_hand"), teammate_hand_count=1), "invalid_intent_reason"),
            (replace(_context("opponent_urgent"), teammate_hand_count=1), "invalid_intent_reason"),
            (replace(_context("opponent_urgent"), minimum_opponent_hand_count=None), "invalid_context_fields"),
            (replace(_context("urgent_opponent_controls_table"), minimum_opponent_hand_count=5, urgent_opponent_ids=()), "invalid_context_fields"),
            (replace(_context("weak_hand"), hand_total_score=50), "invalid_context_fields"),
            (replace(_context("stable_control"), hand_total_score=30), "invalid_context_fields"),
            (replace(_context(), hand_control_score=51), "invalid_context_fields"),
            (replace(_context("teammate_more_urgent"), is_free_lead=False, table_leader_player_id=3, table_leader_relation="teammate", table_leader_is_urgent=True), "invalid_intent_reason"),
        )
        for context, diagnostic in cases:
            with self.subTest(context=context):
                payload = build_strategy_intent_prompt_payload(context)
                self.assertEqual(payload.status, "omitted")
                self.assertIn(diagnostic, payload.diagnostics)
                self.assertEqual((payload.text, payload.char_count, payload.router_source, payload.phase, payload.intent), ("", 0, None, None, None))

    def test_expected_reason_priority_masks_lower_conditions(self) -> None:
        high_priority_cases = (
            (
                replace(
                    _context("teammate_controls_table"),
                    intent="run_out",
                    reason_codes=("can_finish_now",),
                    can_finish_now=True,
                ),
                "can_finish_now",
            ),
            (
                replace(
                    _context("teammate_controls_table"),
                    teammate_hand_count=1,
                    minimum_opponent_hand_count=1,
                    urgent_opponent_ids=(2,),
                    table_leader_is_urgent=True,
                ),
                "teammate_controls_table",
            ),
            (
                replace(_context("urgent_opponent_controls_table"), teammate_hand_count=1, minimum_opponent_hand_count=1),
                "urgent_opponent_controls_table",
            ),
        )
        for context, expected_reason in high_priority_cases:
            with self.subTest(expected_reason=expected_reason):
                payload = build_strategy_intent_prompt_payload(context)
                self.assertEqual((payload.status, context.reason_codes), ("ready", (expected_reason,)))

        for reason in ("teammate_more_urgent", "opponent_more_urgent", "urgency_tie_block_opponent", "opponent_urgent", "teammate_urgent", "weak_hand", "stable_control"):
            with self.subTest(reason=reason):
                self.assertEqual(build_strategy_intent_prompt_payload(_context(reason)).status, "ready")

    def test_score_and_urgency_boundaries(self) -> None:
        for total_score, strength, expected in ((39, "weak", "ready"), (40, "non_weak", "ready"), (39, "non_weak", "omitted"), (40, "weak", "omitted")):
            with self.subTest(total_score=total_score, strength=strength):
                payload = build_strategy_intent_prompt_payload(
                    replace(_context("weak_hand" if strength == "weak" else "stable_control"), hand_total_score=total_score, hand_strength=strength)
                )
                self.assertEqual(payload.status, expected)
        for value in (-1, 101, True, "50", 50.0):
            with self.subTest(score=value):
                self.assertEqual(build_strategy_intent_prompt_payload(replace(_context(), hand_total_score=value)).diagnostics, ("invalid_context_fields",))  # type: ignore[arg-type]
        for value in (-1, 31, True, "10", 10.0):
            with self.subTest(control_score=value):
                self.assertEqual(build_strategy_intent_prompt_payload(replace(_context(), hand_control_score=value)).status, "omitted")  # type: ignore[arg-type]
        self.assertEqual(
            build_strategy_intent_prompt_payload(
                replace(_context("weak_hand"), hand_total_score=10, hand_control_score=20)
            ).diagnostics,
            ("invalid_context_fields",),
        )

        valid_minimums = ((None, (), "stable_control"), (1, (2,), "opponent_urgent"), (2, (2,), "opponent_urgent"), (3, (), "stable_control"))
        for minimum, urgent_ids, reason in valid_minimums:
            with self.subTest(minimum=minimum):
                payload = build_strategy_intent_prompt_payload(replace(_context(reason), minimum_opponent_hand_count=minimum, urgent_opponent_ids=urgent_ids))
                self.assertEqual(payload.status, "ready")
        invalid_minimums = ((None, (2,)), (1, ()), (2, ()), (3, (2,)))
        for minimum, urgent_ids in invalid_minimums:
            with self.subTest(invalid_minimum=minimum):
                self.assertEqual(
                    build_strategy_intent_prompt_payload(replace(_context(), minimum_opponent_hand_count=minimum, urgent_opponent_ids=urgent_ids)).diagnostics,
                    ("invalid_context_fields",),
                )

    def test_teammate_and_opponent_leader_urgency_boundaries(self) -> None:
        for count, reason in ((0, "stable_control"), (1, "teammate_urgent"), (2, "teammate_urgent"), (3, "stable_control")):
            with self.subTest(teammate_count=count):
                payload = build_strategy_intent_prompt_payload(replace(_context(reason), teammate_hand_count=count))
                self.assertEqual(payload.status, "ready")

        different_urgent_leader = replace(
            _context("urgent_opponent_controls_table"),
            table_leader_player_id=4,
            minimum_opponent_hand_count=1,
            urgent_opponent_ids=(2,),
        )
        self.assertEqual(build_strategy_intent_prompt_payload(different_urgent_leader).status, "ready")
        invalid_cases = (
            (replace(different_urgent_leader, table_leader_is_urgent=False), "invalid_intent_reason"),
            (replace(different_urgent_leader, minimum_opponent_hand_count=3, urgent_opponent_ids=()), "invalid_context_fields"),
            (replace(_context("teammate_controls_table"), teammate_hand_count=1, table_leader_is_urgent=False), "invalid_context_fields"),
        )
        for context, diagnostic in invalid_cases:
            with self.subTest(context=context):
                self.assertEqual(build_strategy_intent_prompt_payload(context).diagnostics, (diagnostic,))

    def test_payload_is_frozen_json_safe_deterministic_and_does_not_mutate_context(self) -> None:
        context = _context("opponent_urgent")
        before = context.to_dict()
        first = build_strategy_intent_prompt_payload(context)
        second = build_strategy_intent_prompt_payload(context)
        self.assertIsInstance(first, StrategyIntentPromptPayload)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(json.loads(json.dumps(first.to_dict(), ensure_ascii=False, allow_nan=False)), first.to_dict())
        self.assertEqual(context.to_dict(), before)
        with self.assertRaises(FrozenInstanceError):
            first.text = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
