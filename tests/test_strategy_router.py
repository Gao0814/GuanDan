from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest

from agents.game_phase import CRITICAL_ENDGAME, ENDGAME, MIDGAME, NEAR_OPEN_ENDGAME, OPENING, GamePhaseContext, classify_game_phase
from agents.hand_evaluator import evaluate_hand
from agents.strategy_router import (
    BLOCK_OPPONENT,
    CONTROL,
    RUN_OUT,
    SUPPORT_TEAMMATE,
    StrategyIntentContext,
    route_strategy_intent,
)
from tests.test_deepseek_step_e import (
    _short_endgame_legal_actions,
    _short_endgame_observation,
    _teammate_joker_legal_actions,
    _teammate_joker_observation,
)


_TEAM = {1: "team_13", 2: "team_24", 3: "team_13", 4: "team_24"}


def _action(pattern: str = "single", carrier_cards: list[object] | None = None) -> dict[str, object]:
    cards = ["9S"] if carrier_cards is None else list(carrier_cards)
    return {
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"],
        "carrier_cards": [] if pattern == "pass" else cards,
    }


def _history_action(step_no: int, round_no: int, player_id: int, pattern: str = "pass") -> dict[str, object]:
    return {
        "step_no": step_no,
        "round_no": round_no,
        "player_id": player_id,
        **_action(pattern),
    }


def _observation(
    *,
    my_player_id: int = 1,
    hand_counts: dict[int, int] | None = None,
    finished_ids: set[int] | None = None,
    step_no: int = 9,
    round_no: int = 2,
    table_leader_id: int | None = None,
    include_current_round_pass: bool = False,
) -> dict[str, object]:
    counts = hand_counts or {1: 8, 2: 8, 3: 8, 4: 8}
    finished = finished_ids or set()
    table_action = _action("single") if table_leader_id is not None else None
    history = [
        _history_action(index, round_no - 1, ((index - 1) % 4) + 1)
        for index in range(1, step_no)
    ]
    if table_leader_id is not None:
        history.append(_history_action(step_no, round_no, table_leader_id, "single"))
    elif include_current_round_pass:
        history.append(_history_action(step_no, round_no, ((my_player_id % 4) + 1), "pass"))
    else:
        history.append(_history_action(step_no, round_no - 1, ((step_no - 1) % 4) + 1, "pass"))
    return {
        "my_info": {
            "player_id": my_player_id,
            "team": _TEAM[my_player_id],
            "hand_count": counts[my_player_id],
        },
        "other_players": [
            {
                "player_id": player_id,
                "team": _TEAM[player_id],
                "hand_count": counts[player_id],
                "finished": player_id in finished,
            }
            for player_id in (1, 2, 3, 4)
            if player_id != my_player_id
        ],
        "current_round": {
            "step_no": step_no,
            "round_no": round_no,
            "current_player_id": my_player_id,
            "constraint": "single:9" if table_action is not None else "free",
            "table_action": table_action,
        },
        "history": {"actions": history, "finish_order": sorted(finished)},
    }


def _phase(observation: dict[str, object], phase: str = MIDGAME) -> GamePhaseContext:
    other_players = observation["other_players"]
    assert isinstance(other_players, list)
    counts = tuple(player["hand_count"] for player in other_players)
    external = sum(player["hand_count"] for player in other_players if not player["finished"])
    history = observation["history"]
    assert isinstance(history, dict)
    return GamePhaseContext(
        phase,
        observation["my_info"]["hand_count"],
        counts,
        external,
        len(history["actions"]),
        sum(1 for player in other_players if player["finished"]),
    )


def _evaluation(total_score: int = 50, control_score: int = 10) -> dict[str, object]:
    label = "极强" if total_score >= 80 else "较强" if total_score >= 60 else "中等" if total_score >= 40 else "偏弱" if total_score >= 20 else "极弱"
    return {"total_score": total_score, "control_score": control_score, "label": label}


class TestStrategyRouter(unittest.TestCase):
    def _route(self, observation: dict[str, object], *, phase: str = MIDGAME, actions: list[dict[str, object]] | None = None, evaluation: dict[str, object] | None = None):
        return route_strategy_intent(
            observation,
            [_action()] if actions is None else actions,
            phase_context=_phase(observation, phase),
            hand_evaluation=_evaluation() if evaluation is None else evaluation,
        )

    def test_context_is_frozen_json_serializable_and_stable(self) -> None:
        context = self._route(_observation(table_leader_id=3))
        self.assertIsInstance(context, StrategyIntentContext)
        self.assertEqual(context.status, "available")
        self.assertEqual(context.intent, SUPPORT_TEAMMATE)
        self.assertEqual(json.loads(json.dumps(context.to_dict(), allow_nan=False)), context.to_dict())
        self.assertEqual(context.to_dict(), self._route(_observation(table_leader_id=3)).to_dict())
        with self.assertRaises(FrozenInstanceError):
            context.intent = CONTROL  # type: ignore[misc]

    def test_all_phases_including_opening_route(self) -> None:
        observation = _observation()
        opening = self._route(observation, phase=OPENING)
        self.assertEqual((opening.status, opening.intent, opening.diagnostics), ("available", CONTROL, ()))
        for phase in (MIDGAME, ENDGAME, NEAR_OPEN_ENDGAME, CRITICAL_ENDGAME):
            with self.subTest(phase=phase):
                self.assertEqual(self._route(observation, phase=phase).status, "available")

    def test_team_relationships_cover_all_seats(self) -> None:
        for player_id in (1, 2, 3, 4):
            teammate_id = 3 if player_id == 1 else 4 if player_id == 2 else 1 if player_id == 3 else 2
            context = self._route(_observation(my_player_id=player_id, table_leader_id=teammate_id))
            self.assertEqual((context.my_team, context.teammate_player_id, context.table_leader_relation), (_TEAM[player_id], teammate_id, "teammate"))

    def test_can_finish_now_has_highest_priority(self) -> None:
        observation = _observation(hand_counts={1: 2, 2: 1, 3: 1, 4: 2}, table_leader_id=3)
        context = self._route(observation, actions=[_action("single", ["9S", "9H"])] )
        self.assertEqual((context.intent, context.reason_codes, context.can_finish_now), (RUN_OUT, ("can_finish_now",), True))

    def test_table_leader_priorities_and_three_public_fixtures(self) -> None:
        round_two = _observation(hand_counts={1: 8, 2: 8, 3: 8, 4: 8}, step_no=16, round_no=2, table_leader_id=3)
        steel_plate = {
            "declared_pattern": "steel_plate",
            "declared_cards": ["Q", "Q", "Q", "K", "K", "K"],
            "carrier_cards": ["QS", "QH", "QC", "KS", "KH", "KC"],
        }
        round_two["current_round"]["table_action"] = deepcopy(steel_plate)
        round_two["history"]["actions"][-1].update(deepcopy(steel_plate))
        round_two_context = self._route(round_two)
        self.assertEqual((round_two_context.intent, round_two_context.reason_codes), (SUPPORT_TEAMMATE, ("teammate_controls_table",)))
        self.assertEqual(
            round_two_context.to_dict(),
            {
                "status": "available", "source": "public_strategy_router_v1", "phase": MIDGAME,
                "intent": SUPPORT_TEAMMATE, "reason_codes": ["teammate_controls_table"],
                "my_player_id": 1, "my_team": "team_13", "my_hand_count": 8,
                "teammate_player_id": 3, "teammate_hand_count": 8,
                "minimum_opponent_hand_count": 8, "urgent_opponent_ids": [],
                "can_finish_now": False, "is_free_lead": False,
                "table_leader_player_id": 3, "table_leader_relation": "teammate", "table_leader_is_urgent": False,
                "hand_strength": "non_weak", "hand_total_score": 50, "hand_control_score": 10, "diagnostics": [],
                "opponents_all_active": True, "teammate_big_joker_opportunity": False, "short_endgame_minimum_groups": False,
                "candidate_relation_kinds": [],
            },
        )

        round_sixteen = _observation(my_player_id=3, hand_counts={1: 1, 2: 8, 3: 7, 4: 2}, step_no=16, round_no=16, table_leader_id=4)
        single_eight = {"declared_pattern": "single", "declared_cards": ["8"], "carrier_cards": ["8S"]}
        round_sixteen["current_round"]["table_action"] = deepcopy(single_eight)
        round_sixteen["history"]["actions"][-1].update(deepcopy(single_eight))
        round_sixteen_context = self._route(round_sixteen)
        self.assertEqual((round_sixteen_context.intent, round_sixteen_context.reason_codes), (BLOCK_OPPONENT, ("urgent_opponent_controls_table",)))
        self.assertEqual(
            round_sixteen_context.to_dict(),
            {
                "status": "available", "source": "public_strategy_router_v1", "phase": MIDGAME,
                "intent": BLOCK_OPPONENT, "reason_codes": ["urgent_opponent_controls_table"],
                "my_player_id": 3, "my_team": "team_13", "my_hand_count": 7,
                "teammate_player_id": 1, "teammate_hand_count": 1,
                "minimum_opponent_hand_count": 2, "urgent_opponent_ids": [4],
                "can_finish_now": False, "is_free_lead": False,
                "table_leader_player_id": 4, "table_leader_relation": "opponent", "table_leader_is_urgent": True,
                "hand_strength": "non_weak", "hand_total_score": 50, "hand_control_score": 10, "diagnostics": [],
                "opponents_all_active": True, "teammate_big_joker_opportunity": False, "short_endgame_minimum_groups": False,
                "candidate_relation_kinds": [],
            },
        )

        round_twenty = _observation(my_player_id=2, hand_counts={1: 1, 2: 7, 3: 6, 4: 0}, finished_ids={4}, step_no=20, round_no=20)
        round_twenty_context = self._route(round_twenty, phase=ENDGAME)
        self.assertEqual((round_twenty_context.intent, round_twenty_context.reason_codes), (BLOCK_OPPONENT, ("opponent_urgent",)))
        self.assertEqual(
            round_twenty_context.to_dict(),
            {
                "status": "available", "source": "public_strategy_router_v1", "phase": ENDGAME,
                "intent": BLOCK_OPPONENT, "reason_codes": ["opponent_urgent"],
                "my_player_id": 2, "my_team": "team_24", "my_hand_count": 7,
                "teammate_player_id": 4, "teammate_hand_count": 0,
                "minimum_opponent_hand_count": 1, "urgent_opponent_ids": [1],
                "can_finish_now": False, "is_free_lead": True,
                "table_leader_player_id": None, "table_leader_relation": None, "table_leader_is_urgent": False,
                "hand_strength": "non_weak", "hand_total_score": 50, "hand_control_score": 10, "diagnostics": [],
                "opponents_all_active": True, "teammate_big_joker_opportunity": False, "short_endgame_minimum_groups": False,
                "candidate_relation_kinds": [],
            },
        )

    def test_short_endgame_minimum_groups_is_a_specific_public_free_lead_reason(self) -> None:
        observation = _short_endgame_observation()
        actions = _short_endgame_legal_actions()
        context = route_strategy_intent(
            observation,
            actions,
            phase_context=classify_game_phase(observation),
            hand_evaluation=evaluate_hand(observation, actions),
        )
        self.assertEqual(
            (context.status, context.intent, context.reason_codes, context.short_endgame_minimum_groups),
            ("available", RUN_OUT, ("short_endgame_minimum_groups",), True),
        )

        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        tied = _short_endgame_observation()
        tied["my_info"] = dict(tied["my_info"], hand_cards=["6S", "7S"], hand_count=2)
        cases.append((tied, _short_endgame_legal_actions()[:2]))
        oversized = _short_endgame_observation()
        oversized["my_info"] = dict(
            oversized["my_info"],
            hand_cards=["3S", "4S", "5S", "6S", "7S"],
            hand_count=5,
        )
        cases.append((oversized, _short_endgame_legal_actions()))
        following = _short_endgame_observation()
        following["current_round"] = dict(
            following["current_round"],
            constraint="single:5",
            table_action={"declared_pattern": "single", "declared_cards": ["5"], "carrier_cards": ["5S"]},
        )
        cases.append((following, _short_endgame_legal_actions()))
        pass_action = [{"action_id": 9, "declared_pattern": "pass", "declared_cards": [], "carrier_cards": [], "wildcard_count": 0, "wildcard_info": [], "display_text": "pass"}]
        cases.append((_short_endgame_observation(), pass_action + _short_endgame_legal_actions()))
        duplicate_id = _short_endgame_legal_actions()
        duplicate_id[1]["action_id"] = 1
        cases.append((_short_endgame_observation(), duplicate_id))
        bad_carrier = _short_endgame_legal_actions()
        bad_carrier[0]["carrier_cards"] = ["AS"]
        cases.append((_short_endgame_observation(), bad_carrier))
        cases.append((_short_endgame_observation(), _short_endgame_legal_actions()[:-1]))
        for snapshot, candidates in cases:
            with self.subTest(snapshot=snapshot):
                context = route_strategy_intent(
                    snapshot,
                    candidates,
                    phase_context=classify_game_phase(snapshot),
                    hand_evaluation=evaluate_hand(snapshot, candidates),
                )
                self.assertFalse(context.short_endgame_minimum_groups)
                self.assertNotEqual(context.reason_codes, ("short_endgame_minimum_groups",))

    def test_can_finish_now_remains_ahead_of_short_endgame_minimum_groups(self) -> None:
        observation = _short_endgame_observation()
        observation["my_info"] = dict(
            observation["my_info"],
            hand_cards=["6S", "6H", "6C"],
            hand_count=3,
        )
        actions = [
            {"action_id": 1, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
            {"action_id": 2, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6H"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
            {"action_id": 3, "declared_pattern": "single", "declared_cards": ["6"], "carrier_cards": ["6C"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:6"},
            {"action_id": 4, "declared_pattern": "pair", "declared_cards": ["6", "6"], "carrier_cards": ["6S", "6H"], "wildcard_count": 0, "wildcard_info": [], "display_text": "pair:6,6"},
            {"action_id": 5, "declared_pattern": "pair", "declared_cards": ["6", "6"], "carrier_cards": ["6S", "6C"], "wildcard_count": 0, "wildcard_info": [], "display_text": "pair:6,6"},
            {"action_id": 6, "declared_pattern": "pair", "declared_cards": ["6", "6"], "carrier_cards": ["6H", "6C"], "wildcard_count": 0, "wildcard_info": [], "display_text": "pair:6,6"},
            {"action_id": 7, "declared_pattern": "triple", "declared_cards": ["6", "6", "6"], "carrier_cards": ["6S", "6H", "6C"], "wildcard_count": 0, "wildcard_info": [], "display_text": "triple:6,6,6"},
        ]
        context = route_strategy_intent(
            observation,
            actions,
            phase_context=classify_game_phase(observation),
            hand_evaluation=evaluate_hand(observation, actions),
        )
        self.assertTrue(context.short_endgame_minimum_groups)
        self.assertEqual((context.intent, context.reason_codes), (RUN_OUT, ("can_finish_now",)))

    def test_big_joker_teammate_control_is_a_specific_public_reason(self) -> None:
        observation = _teammate_joker_observation()
        context = route_strategy_intent(
            observation,
            _teammate_joker_legal_actions(),
            phase_context=GamePhaseContext(ENDGAME, 2, (5, 8, 5), 18, 12, 0),
            hand_evaluation=_evaluation(),
        )
        self.assertEqual(
            (context.status, context.intent, context.reason_codes),
            ("available", SUPPORT_TEAMMATE, ("teammate_big_joker_preservation",)),
        )
        self.assertTrue(context.teammate_big_joker_opportunity)
        self.assertTrue(context.opponents_all_active)

        ordinary = self._route(_observation(table_leader_id=3))
        self.assertEqual(ordinary.reason_codes, ("teammate_controls_table",))
        self.assertFalse(ordinary.teammate_big_joker_opportunity)

        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        free = _teammate_joker_observation()
        free["current_round"] = {"step_no": 12, "round_no": 4, "current_player_id": 4, "constraint": "free", "table_action": None}
        free["history"] = {"actions": []}
        cases.append((free, _teammate_joker_legal_actions()))
        opponent = _teammate_joker_observation()
        opponent["history"]["actions"][0]["player_id"] = 1  # type: ignore[index]
        cases.append((opponent, _teammate_joker_legal_actions()))
        mismatch = _teammate_joker_observation()
        mismatch["history"]["actions"][0]["carrier_cards"] = ["BJ"]  # type: ignore[index]
        cases.append((mismatch, _teammate_joker_legal_actions()))
        no_pass = [action for action in _teammate_joker_legal_actions() if action["declared_pattern"] != "pass"]
        cases.append((_teammate_joker_observation(), no_pass))
        no_big = [action for action in _teammate_joker_legal_actions() if action["declared_pattern"] == "pass"]
        cases.append((_teammate_joker_observation(), no_big))
        cases.append((_teammate_joker_observation(own_count=1), _teammate_joker_legal_actions()))
        cases.append((_teammate_joker_observation(opponent_count=2), _teammate_joker_legal_actions()))
        cases.append((_teammate_joker_observation(opponent_finished=True), _teammate_joker_legal_actions()))
        malformed_player = _teammate_joker_observation()
        malformed_player["other_players"][0]["team"] = "wrong"  # type: ignore[index]
        cases.append((malformed_player, _teammate_joker_legal_actions()))
        malformed_action = _teammate_joker_legal_actions()
        malformed_action[1]["wildcard_info"] = "invalid"
        cases.append((_teammate_joker_observation(), malformed_action))
        for snapshot, actions in cases:
            with self.subTest(snapshot=snapshot):
                others = snapshot["other_players"]
                assert isinstance(others, list)
                context = route_strategy_intent(
                    snapshot,
                    actions,
                    phase_context=GamePhaseContext(
                        ENDGAME,
                        snapshot["my_info"]["hand_count"],  # type: ignore[index]
                        tuple(item["hand_count"] for item in others),
                        sum(item["hand_count"] for item in others if not item["finished"]),
                        12,
                        sum(1 for item in others if item["finished"]),
                    ),
                    hand_evaluation=_evaluation(),
                )
                self.assertFalse(context.teammate_big_joker_opportunity)
                self.assertNotEqual(context.reason_codes, ("teammate_big_joker_preservation",))

    def test_urgency_ties_and_fallback_intents(self) -> None:
        cases = (
            ({1: 6, 2: 2, 3: 1, 4: 8}, SUPPORT_TEAMMATE, "teammate_more_urgent"),
            ({1: 6, 2: 1, 3: 2, 4: 8}, BLOCK_OPPONENT, "opponent_more_urgent"),
            ({1: 6, 2: 2, 3: 2, 4: 8}, BLOCK_OPPONENT, "urgency_tie_block_opponent"),
        )
        for counts, intent, reason in cases:
            with self.subTest(counts=counts):
                context = self._route(_observation(hand_counts=counts))
                self.assertEqual((context.intent, context.reason_codes), (intent, (reason,)))
        self.assertEqual(self._route(_observation(hand_counts={1: 7, 2: 8, 3: 2, 4: 8})).intent, SUPPORT_TEAMMATE)
        self.assertEqual(self._route(_observation(hand_counts={1: 7, 2: 2, 3: 8, 4: 8})).intent, BLOCK_OPPONENT)
        self.assertEqual(self._route(_observation(), evaluation=_evaluation(30)).intent, RUN_OUT)
        self.assertEqual(self._route(_observation(), evaluation=_evaluation(50)).intent, CONTROL)

    def test_free_lead_pass_history_and_table_action_mismatch(self) -> None:
        free = self._route(_observation(include_current_round_pass=True))
        self.assertTrue(free.is_free_lead)
        self.assertIsNone(free.table_leader_player_id)

        mismatch = _observation(table_leader_id=3)
        mismatch["current_round"]["table_action"] = _action("pair", ["9S", "9H"])
        context = self._route(mismatch)
        self.assertEqual((context.status, context.diagnostics), ("unavailable", ("table_leader_mismatch",)))

    def test_invalid_inputs_fail_closed_with_stable_diagnostics(self) -> None:
        observation = _observation()
        invalid_actions = route_strategy_intent(observation, [], phase_context=_phase(observation), hand_evaluation=_evaluation())
        self.assertEqual(invalid_actions.diagnostics, ("invalid_legal_actions",))

        bad_count = deepcopy(observation)
        bad_count_phase = _phase(bad_count)
        bad_count["other_players"][0]["hand_count"] = True
        self.assertEqual(
            route_strategy_intent(bad_count, [_action()], phase_context=bad_count_phase, hand_evaluation=_evaluation()).diagnostics,
            ("invalid_hand_count",),
        )

        duplicate = deepcopy(observation)
        duplicate["other_players"][1]["player_id"] = duplicate["other_players"][0]["player_id"]
        self.assertEqual(
            self._route(duplicate).diagnostics,
            ("invalid_team", "player_set_mismatch", "duplicate_player"),
        )

        malformed_history = deepcopy(observation)
        malformed_history["history"]["actions"][0]["step_no"] = 0
        self.assertEqual(self._route(malformed_history).diagnostics, ("malformed_current_round_history",))

        bad_eval = self._route(observation, evaluation={"total_score": 50, "control_score": 10, "label": "极强"})
        self.assertEqual(bad_eval.diagnostics, ("hand_label_mismatch",))

    def test_player_set_and_hand_count_validation_rejects_malformed_values(self) -> None:
        for value in ("8", 8.0, -1, True):
            with self.subTest(hand_count=repr(value)):
                observation = _observation()
                phase = _phase(observation)
                observation["other_players"][0]["hand_count"] = value
                context = route_strategy_intent(observation, [_action()], phase_context=phase, hand_evaluation=_evaluation())
                self.assertEqual(context.diagnostics, ("invalid_hand_count",))

        missing = _observation()
        missing_phase = _phase(missing)
        missing["other_players"].pop()
        self.assertEqual(
            route_strategy_intent(missing, [_action()], phase_context=missing_phase, hand_evaluation=_evaluation()).diagnostics,
            ("player_set_mismatch",),
        )

        invalid_id = _observation()
        invalid_id["other_players"][0]["player_id"] = "two"
        self.assertEqual(self._route(invalid_id).diagnostics, ("invalid_player_id", "player_set_mismatch"))

        invalid_team = _observation()
        invalid_team["other_players"][0]["team"] = "team_13"
        self.assertEqual(self._route(invalid_team).diagnostics, ("invalid_team",))

    def test_hand_evaluation_and_action_shapes_are_strict(self) -> None:
        observation = _observation()
        for evaluation in (
            {"total_score": True, "control_score": 10, "label": "中等"},
            {"total_score": 50, "control_score": 31, "label": "中等"},
            {"total_score": 50, "control_score": 10, "label": "strong"},
        ):
            with self.subTest(evaluation=evaluation):
                self.assertEqual(self._route(observation, evaluation=evaluation).diagnostics, ("invalid_hand_evaluation",))
        malformed_actions = [{"declared_pattern": "single", "declared_cards": ["9"], "carrier_cards": ("9S",)}]
        self.assertEqual(self._route(observation, actions=malformed_actions).diagnostics, ("malformed_action",))

    def test_history_passes_still_locate_last_non_pass_table_leader(self) -> None:
        observation = _observation(table_leader_id=3)
        observation["history"]["actions"].append(_history_action(10, 2, 4, "pass"))
        observation["current_round"]["step_no"] = 10
        phase = _phase(observation)
        context = route_strategy_intent(observation, [_action()], phase_context=phase, hand_evaluation=_evaluation())
        self.assertEqual((context.status, context.table_leader_player_id, context.table_leader_relation), ("available", 3, "teammate"))

    def test_unavailable_context_has_no_partial_public_conclusion(self) -> None:
        observation = _observation()
        observation["my_info"]["team"] = "team_24"
        context = self._route(observation)
        self.assertEqual(context.status, "unavailable")
        self.assertIsNone(context.intent)
        self.assertIsNone(context.my_player_id)
        self.assertFalse(context.can_finish_now)
        self.assertEqual(context.diagnostics, ("invalid_team",))

    def test_phase_context_deep_fields_reject_bool_and_other_invalid_values(self) -> None:
        observation = _observation(hand_counts={1: 1, 2: 8, 3: 8, 4: 8})
        base = _phase(observation)
        invalid_contexts: list[GamePhaseContext] = [
            replace(base, phase=True),
            replace(base, phase="unknown"),
            replace(base, other_hand_counts=[8, 8, 8]),  # type: ignore[arg-type]
            replace(base, other_hand_counts=(8, 8)),
            replace(base, other_hand_counts=(8, True, 8)),
            replace(base, other_hand_counts=(8, False, 8)),
            replace(base, other_hand_counts=(8, "8", 8)),
            replace(base, other_hand_counts=(8, 8.0, 8)),
            replace(base, other_hand_counts=(8, -1, 8)),
        ]
        for field_name in (
            "my_hand_count",
            "external_unknown_count",
            "history_action_count",
            "finished_player_count",
        ):
            for invalid_value in (True, False, "1", 1.0, -1):
                invalid_contexts.append(replace(base, **{field_name: invalid_value}))  # type: ignore[arg-type]
        invalid_contexts.append(replace(base, finished_player_count=4))
        for phase_context in invalid_contexts:
            with self.subTest(phase_context=phase_context):
                context = route_strategy_intent(
                    observation,
                    [_action()],
                    phase_context=phase_context,
                    hand_evaluation=_evaluation(),
                )
                self.assertEqual(context.status, "unavailable")
                self.assertIsNone(context.phase)
                self.assertIsNone(context.intent)
                self.assertIn("invalid_phase_context", context.diagnostics)
        true_equals_one = route_strategy_intent(
            observation,
            [_action()],
            phase_context=replace(base, my_hand_count=True),
            hand_evaluation=_evaluation(),
        )
        self.assertEqual(
            (true_equals_one.status, true_equals_one.phase, true_equals_one.intent, true_equals_one.diagnostics),
            ("unavailable", None, None, ("invalid_phase_context",)),
        )

    def test_independent_diagnostics_aggregate_in_fixed_order(self) -> None:
        observation = _observation()
        phase = _phase(observation)
        observation["my_info"]["team"] = "team_24"
        observation["my_info"]["hand_count"] = True
        self.assertEqual(
            route_strategy_intent(observation, [_action()], phase_context=phase, hand_evaluation=_evaluation()).diagnostics,
            ("invalid_team", "invalid_hand_count"),
        )

        observation = _observation()
        phase = _phase(observation)
        observation["other_players"][0]["team"] = "team_13"
        observation["other_players"][1]["finished"] = 1
        result = route_strategy_intent(
            observation,
            [_action()],
            phase_context=phase,
            hand_evaluation={"total_score": 50, "control_score": 10, "label": "极强"},
        )
        self.assertEqual(
            result.diagnostics,
            ("invalid_team", "invalid_finished_flag", "hand_label_mismatch"),
        )

        observation = _observation()
        observation["my_info"]["team"] = "team_24"
        result = route_strategy_intent(
            observation,
            [_action()],
            phase_context=replace(_phase(_observation()), my_hand_count=True),
            hand_evaluation=_evaluation(),
        )
        self.assertEqual(result.diagnostics, ("invalid_phase_context", "invalid_team"))

    def test_duplicate_diagnostics_and_unreadable_containers_fail_closed(self) -> None:
        observation = _observation()
        phase = _phase(observation)
        observation["other_players"][0]["team"] = "team_13"
        observation["other_players"][1]["team"] = "team_13"
        context = route_strategy_intent(observation, [_action()], phase_context=phase, hand_evaluation=_evaluation())
        self.assertEqual(context.diagnostics, ("invalid_team",))

        malformed = {"my_info": [], "other_players": [], "current_round": [], "history": []}
        context = route_strategy_intent(malformed, [_action()], phase_context=_phase(_observation()), hand_evaluation=_evaluation())
        self.assertEqual(context.diagnostics, ("invalid_observation",))
        self.assertIsNone(context.my_player_id)
        self.assertFalse(context.is_free_lead)

    def test_phase_counts_finished_and_round_context_are_validated(self) -> None:
        observation = _observation()
        wrong_phase = GamePhaseContext(MIDGAME, 99, (8, 8, 8), 24, 9, 0)
        result = route_strategy_intent(observation, [_action()], phase_context=wrong_phase, hand_evaluation=_evaluation())
        self.assertEqual(result.diagnostics, ("external_count_mismatch",))

        finished = _observation(hand_counts={1: 8, 2: 0, 3: 8, 4: 8}, finished_ids={2})
        finished["other_players"][0]["finished"] = 1
        self.assertEqual(self._route(finished).diagnostics, ("invalid_finished_flag",))

        malformed_round = _observation()
        malformed_round["current_round"]["constraint"] = 1
        self.assertEqual(self._route(malformed_round).diagnostics, ("invalid_round_context",))

    def test_pass_is_not_an_immediate_finish_and_inputs_are_unchanged(self) -> None:
        observation = _observation(hand_counts={1: 1, 2: 8, 3: 8, 4: 8})
        actions = [_action("pass")]
        phase = _phase(observation)
        evaluation = _evaluation()
        before = (deepcopy(observation), deepcopy(actions), phase, deepcopy(evaluation))
        context = route_strategy_intent(observation, actions, phase_context=phase, hand_evaluation=evaluation)
        self.assertFalse(context.can_finish_now)
        self.assertEqual((observation, actions, phase, evaluation), before)

    def test_source_and_runtime_boundaries_are_not_imported(self) -> None:
        source = Path("agents/strategy_router.py").read_text(encoding="utf-8")
        for forbidden in ("classify_game_phase", "from evaluation", "import evaluation", "from rag", "import rag", "deepseek", "confidence", "belief", "signals", "game._state", "ground_truth", "os.environ"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
