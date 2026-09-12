"""Boundary and determinism tests for the evaluation-only pass candidate."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent as RuntimeConditionalPressurePassAIAgent
from agents.conditional_pressure_pass_policy import (
    conditional_pressure_pass_id,
    dangerous_opponent_pass_id,
    teammate_big_joker_opportunity,
    teammate_big_joker_pass_id,
    teammate_pressure_pass_id,
)
from agents.rule_based_ai import FrozenRuleBasedAIAgent, RuleBasedAIAgent
from engine.game import GuanDanGame
from evaluation.conditional_pressure_pass import (
    ConditionalPressurePassAIAgent,
    benchmark_decision,
    run_conditional_pressure_pass_benchmark,
)


def _action(action_id: int, pattern: str, count: int = 0) -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": [] if pattern == "pass" else ["9"] * count,
        "carrier_cards": [] if pattern == "pass" else ["9S"] * count,
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": pattern,
    }


def _history_row(action: dict[str, object], *, step_no: int = 7, round_no: int = 2, player_id: int = 1) -> dict[str, object]:
    return {
        "step_no": step_no,
        "round_no": round_no,
        "player_id": player_id,
        "declared_pattern": action["declared_pattern"],
        "declared_cards": action["declared_cards"],
        "carrier_cards": action["carrier_cards"],
    }


def _observation(*, leader: int = 1, my_hand_count: int = 10, opponent_count: int = 8, finished: bool = False) -> dict[str, object]:
    table = _action(99, "triple", 3)
    table["action_id"] = None
    return {
        "my_info": {"player_id": 2, "team": "team_24", "hand_count": my_hand_count},
        "other_players": [
            {"player_id": 1, "team": "team_13", "hand_count": 0 if finished else opponent_count, "finished": finished},
            {"player_id": 3, "team": "team_13", "hand_count": opponent_count, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": opponent_count, "finished": False},
        ],
        "current_round": {"step_no": 7, "round_no": 2, "current_player_id": 2, "constraint": "triple", "table_action": table},
        "history": {"actions": [_history_row(table, player_id=leader)]},
    }


def _review_teammate_observation(
    *,
    my_hand_count: int = 10,
    opponent_count: int = 8,
    opponent_finished: bool = False,
) -> dict[str, object]:
    """Minimal public equivalent of the reviewed teammate steel-plate lead."""

    table = _action(99, "steel_plate", 6)
    table["action_id"] = None
    return {
        "my_info": {"player_id": 1, "team": "team_13", "hand_count": my_hand_count},
        "other_players": [
            {"player_id": 2, "team": "team_24", "hand_count": 0 if opponent_finished else opponent_count, "finished": opponent_finished},
            {"player_id": 3, "team": "team_13", "hand_count": 8, "finished": False},
            {"player_id": 4, "team": "team_24", "hand_count": opponent_count, "finished": False},
        ],
        "current_round": {"step_no": 7, "round_no": 2, "current_player_id": 1, "constraint": "steel_plate", "table_action": table},
        "history": {"actions": [_history_row(table, player_id=3)]},
    }


def _legal(*patterns: tuple[str, int]) -> list[dict[str, object]]:
    return [_action(1, "pass")] + [_action(index + 2, pattern, count) for index, (pattern, count) in enumerate(patterns)]


def _joker_teammate_observation(*, opponent_count: int = 5, opponent_finished: bool = False, my_hand_count: int = 2) -> dict[str, object]:
    table = {
        "action_id": None, "declared_pattern": "single", "declared_cards": ["SJ"], "carrier_cards": ["SJ"],
        "wildcard_count": 0, "wildcard_info": [], "display_text": "single:SJ",
    }
    return {
        "my_info": {"player_id": 4, "team": "team_24", "hand_count": my_hand_count},
        "other_players": [
            {"player_id": 1, "team": "team_13", "hand_count": 0 if opponent_finished else opponent_count, "finished": opponent_finished},
            {"player_id": 2, "team": "team_24", "hand_count": 8, "finished": False},
            {"player_id": 3, "team": "team_13", "hand_count": opponent_count, "finished": False},
        ],
        "current_round": {"step_no": 12, "round_no": 4, "current_player_id": 4, "constraint": "single:SJ", "table_action": table},
        "history": {"actions": [{"step_no": 12, "round_no": 4, "player_id": 2, "declared_pattern": "single", "declared_cards": ["SJ"], "carrier_cards": ["SJ"]}]},
    }


def _joker_teammate_actions(*, include_pass: bool = True) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if include_pass:
        actions.append({"action_id": 1, "declared_pattern": "pass", "declared_cards": [], "carrier_cards": [], "wildcard_count": 0, "wildcard_info": [], "display_text": "pass"})
    actions.extend([
        {"action_id": 2, "declared_pattern": "single", "declared_cards": ["BJ"], "carrier_cards": ["BJ"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:BJ"},
    ])
    return actions


class ConditionalPressurePassAgentTests(unittest.TestCase):
    def _select(self, observation: dict[str, object], actions: list[dict[str, object]]) -> int:
        return ConditionalPressurePassAIAgent(player_id=2).select_action(observation, actions)

    def test_enemy_leader_special_only_chooses_original_pass(self) -> None:
        for patterns in (
            (("bomb", 4),),
            (("straight_flush", 5),),
            (("joker_bomb", 4),),
            (("bomb", 4), ("straight_flush", 5)),
        ):
            with self.subTest(patterns=patterns):
                self.assertEqual(self._select(_observation(), _legal(*patterns)), 1)

    def test_default_rule_based_agent_uses_shared_pressure_pass_and_frozen_baseline_does_not(self) -> None:
        actions = _legal(("bomb", 4))
        self.assertEqual(FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), actions), 2)
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), actions), 1)
        self.assertEqual(self._select(_observation(), actions), 1)

    def test_teammate_steel_plate_lead_preserves_special_actions_with_original_pass(self) -> None:
        observation = _review_teammate_observation()
        for patterns in (
            (("bomb", 4),),
            (("straight_flush", 5),),
            (("joker_bomb", 4),),
            (("bomb", 4), ("straight_flush", 5)),
        ):
            with self.subTest(patterns=patterns):
                actions = _legal(*patterns)
                expected = FrozenRuleBasedAIAgent(player_id=1).select_action(observation, actions)
                self.assertEqual(RuleBasedAIAgent(player_id=1).select_action(observation, actions), 1)
                self.assertEqual(ConditionalPressurePassAIAgent(player_id=1).select_action(observation, actions), expected)

    def test_teammate_pressure_pass_keeps_finish_and_endgame_exceptions(self) -> None:
        cases = (
            (_review_teammate_observation(my_hand_count=4), _legal(("bomb", 4))),
            (_review_teammate_observation(opponent_count=2), _legal(("bomb", 4))),
            (_review_teammate_observation(opponent_finished=True), _legal(("bomb", 4))),
            (_review_teammate_observation(), _legal(("bomb", 4), ("steel_plate", 6))),
        )
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=1).select_action(observation, actions)
                self.assertEqual(RuleBasedAIAgent(player_id=1).select_action(observation, actions), expected)

    def test_teammate_pressure_pass_fails_closed_for_incomplete_or_non_team_context(self) -> None:
        mismatch = _review_teammate_observation()
        mismatch["history"]["actions"][0]["declared_cards"] = ["Q"] * 6  # type: ignore[index]
        free = _review_teammate_observation()
        free["current_round"] = {"step_no": 7, "round_no": 2, "current_player_id": 1, "constraint": "free", "table_action": None}
        free["history"] = {"actions": []}
        no_pass = [_action(2, "bomb", 4)]
        cases = (
            (mismatch, _legal(("bomb", 4))),
            (free, _legal(("bomb", 4))),
            (_review_teammate_observation(), no_pass),
            (_review_teammate_observation(), [_action(1, "pass")]),
        )
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=1).select_action(observation, actions)
                self.assertEqual(RuleBasedAIAgent(player_id=1).select_action(observation, actions), expected)

    def test_dangerous_opponent_guard_requires_a_proved_near_finish_enemy_lead(self) -> None:
        actions = _legal(("triple", 3))
        self.assertEqual(dangerous_opponent_pass_id(_observation(opponent_count=2), actions, 2), 1)
        self.assertEqual(dangerous_opponent_pass_id(_observation(opponent_count=1), actions, 2), 1)
        mismatch = _observation(opponent_count=2)
        mismatch["history"]["actions"][0]["declared_cards"] = ["8", "8", "8"]  # type: ignore[index]
        free = _observation(opponent_count=2)
        free["current_round"] = {"step_no": 7, "round_no": 2, "current_player_id": 2, "constraint": "free", "table_action": None}
        free["history"] = {"actions": []}
        for observation, legal_actions in (
            (_observation(opponent_count=3), actions),
            (_observation(opponent_count=2, finished=True), actions),
            (_observation(leader=4, opponent_count=2), actions),
            (mismatch, actions),
            (free, actions),
            (_observation(opponent_count=2), [_action(1, "pass")]),
            (_observation(opponent_count=2), [_action(2, "triple", 3)]),
        ):
            with self.subTest(observation=observation):
                self.assertIsNone(dangerous_opponent_pass_id(observation, legal_actions, 2))

    def test_teammate_big_joker_guard_is_narrow_and_fail_closed(self) -> None:
        actions = _joker_teammate_actions()
        self.assertEqual(teammate_big_joker_opportunity(_joker_teammate_observation(), actions, 4), (1, (2,)))
        self.assertEqual(teammate_big_joker_pass_id(_joker_teammate_observation(), actions, 4, 2), 1)
        duplicate_big_joker = dict(actions[1], action_id=3)
        multiple_big_jokers = actions + [duplicate_big_joker]
        self.assertEqual(
            teammate_big_joker_opportunity(_joker_teammate_observation(), multiple_big_jokers, 4),
            (1, (2, 3)),
        )
        self.assertEqual(teammate_big_joker_pass_id(_joker_teammate_observation(), multiple_big_jokers, 4, 3), 1)
        cases: list[tuple[dict[str, object], list[dict[str, object]], int]] = []
        cases.append((_joker_teammate_observation(), actions, 1))
        cases.append((_joker_teammate_observation(my_hand_count=1), actions, 2))
        cases.append((_joker_teammate_observation(opponent_count=2), actions, 2))
        cases.append((_joker_teammate_observation(opponent_finished=True), actions, 2))
        cases.append((_joker_teammate_observation(), _joker_teammate_actions(include_pass=False), 2))

        free = _joker_teammate_observation()
        free["current_round"] = {"step_no": 12, "round_no": 4, "current_player_id": 4, "constraint": "free", "table_action": None}
        free["history"] = {"actions": []}
        cases.append((free, actions, 2))

        enemy_lead = _joker_teammate_observation()
        enemy_lead["history"]["actions"][0]["player_id"] = 1  # type: ignore[index]
        cases.append((enemy_lead, actions, 2))

        mismatch = _joker_teammate_observation()
        mismatch["history"]["actions"][0]["carrier_cards"] = ["BJ"]  # type: ignore[index]
        cases.append((mismatch, actions, 2))

        bad_team = _joker_teammate_observation()
        bad_team["other_players"][1]["team"] = "wrong"  # type: ignore[index]
        cases.append((bad_team, actions, 2))

        for observation, legal_actions, selected in cases:
            with self.subTest(selected=selected, constraint=observation["current_round"]["constraint"]):
                self.assertIsNone(teammate_big_joker_pass_id(observation, legal_actions, 4, selected))

        self.assertEqual(teammate_big_joker_opportunity(_joker_teammate_observation(), actions, 4), (1, (2,)))

    def test_shared_follow_context_rejects_malformed_constraint_and_table_identity_for_all_helpers(self) -> None:
        def assert_all_fail(mutator) -> None:
            enemy_actions = _legal(("bomb", 4))
            enemy = _observation()
            mutator(enemy)
            self.assertIsNone(conditional_pressure_pass_id(enemy, enemy_actions, 2))

            danger = _observation(opponent_count=2)
            mutator(danger)
            self.assertIsNone(dangerous_opponent_pass_id(danger, enemy_actions, 2))

            teammate = _review_teammate_observation()
            mutator(teammate)
            self.assertIsNone(teammate_pressure_pass_id(teammate, _legal(("bomb", 4)), 1))

            joker = _joker_teammate_observation()
            mutator(joker)
            self.assertIsNone(teammate_big_joker_pass_id(joker, _joker_teammate_actions(), 4, 2))

        constraint_cases = {
            "missing": lambda observation: observation["current_round"].pop("constraint"),
            "none": lambda observation: observation["current_round"].__setitem__("constraint", None),
            "empty": lambda observation: observation["current_round"].__setitem__("constraint", ""),
            "bool": lambda observation: observation["current_round"].__setitem__("constraint", True),
            "list": lambda observation: observation["current_round"].__setitem__("constraint", []),
            "display_mismatch": lambda observation: observation["current_round"].__setitem__("constraint", "different"),
        }
        for name, mutator in constraint_cases.items():
            with self.subTest(category="constraint", value=name):
                assert_all_fail(mutator)

        def mutate_table_identity(value: object, *, remove: bool = False):
            def apply(observation: dict[str, object]) -> None:
                table = observation["current_round"]["table_action"]
                assert isinstance(table, dict)
                if remove:
                    table.pop("action_id")
                else:
                    table["action_id"] = value
            return apply

        valid_sentinel_cases = (
            (_observation(), _legal(("bomb", 4)), 2, conditional_pressure_pass_id),
            (_observation(opponent_count=2), _legal(("bomb", 4)), 2, dangerous_opponent_pass_id),
            (_review_teammate_observation(), _legal(("bomb", 4)), 1, teammate_pressure_pass_id),
            (_joker_teammate_observation(), _joker_teammate_actions(), 4, lambda observation, actions, player: teammate_big_joker_pass_id(observation, actions, player, 2)),
        )
        for observation, actions, player_id, helper in valid_sentinel_cases:
            with self.subTest(category="table_action_id", value="none"):
                self.assertEqual(helper(observation, actions, player_id), 1)

        identity_cases = {
            "missing": mutate_table_identity(None, remove=True),
            "bool": mutate_table_identity(True),
            "string": mutate_table_identity("90"),
            "integer": mutate_table_identity(90),
        }
        for name, mutator in identity_cases.items():
            with self.subTest(category="table_action_id", value=name):
                assert_all_fail(mutator)

    def test_normal_play_finish_and_pressure_all_fall_back_exactly(self) -> None:
        cases = (
            (_observation(), _legal(("bomb", 4), ("triple", 3))),
            (_observation(my_hand_count=4), _legal(("bomb", 4))),
            (_observation(opponent_count=2), _legal(("bomb", 4))),
            (_observation(finished=True), _legal(("bomb", 4))),
        )
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)

    def test_non_opportunity_context_and_malformed_public_inputs_fall_back(self) -> None:
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        free = _observation(); free["current_round"] = {"step_no": 7, "round_no": 2, "current_player_id": 2, "constraint": "free", "table_action": None}; free["history"] = {"actions": []}
        cases.append((free, _legal(("bomb", 4))))
        mismatch = _observation(); mismatch["my_info"] = {"player_id": 1, "team": "team_13", "hand_count": 10}
        cases.append((mismatch, _legal(("bomb", 4))))
        malformed = _observation(); malformed["history"] = {"actions": [{"bad": "history"}]}
        cases.append((malformed, _legal(("bomb", 4))))
        missing_history_field = _observation(); del missing_history_field["history"]["actions"][0]["carrier_cards"]  # type: ignore[index]
        cases.append((missing_history_field, _legal(("bomb", 4))))
        bad_history_type = _observation(); bad_history_type["history"]["actions"][0]["step_no"] = "7"  # type: ignore[index]
        cases.append((bad_history_type, _legal(("bomb", 4))))
        invalid_history_player = _observation(); invalid_history_player["history"]["actions"][0]["player_id"] = 5  # type: ignore[index]
        cases.append((invalid_history_player, _legal(("bomb", 4))))
        regressing_history = _observation(); regressing_history["history"] = {"actions": [_history_row(_action(98, "single", 1), step_no=6), _history_row(_action(99, "triple", 3), step_no=5)]}
        cases.append((regressing_history, _legal(("bomb", 4))))
        bad_team = _observation(); bad_team["other_players"][0]["team"] = "wrong"  # type: ignore[index]
        cases.append((bad_team, _legal(("bomb", 4))))
        bad_count = _observation(); bad_count["other_players"][0]["hand_count"] = "8"  # type: ignore[index]
        cases.append((bad_count, _legal(("bomb", 4))))
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)
        self.assertEqual(self._select(_observation(), [_action(1, "pass")]), 1)
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), [_action(1, "pass")]), 1)
        no_pass = [_action(2, "bomb", 4)]
        self.assertEqual(self._select(_observation(), no_pass), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass))
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), no_pass))
        malformed_action = _legal(("bomb", 4)); malformed_action[0]["action_id"] = True
        self.assertEqual(self._select(_observation(), malformed_action), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action))
        self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action), FrozenRuleBasedAIAgent(player_id=2).select_action(_observation(), malformed_action))

    def test_history_table_semantics_and_complete_action_schemas_fail_closed(self) -> None:
        cases: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        mismatch = _observation(); mismatch["history"]["actions"][0]["declared_cards"] = ["8", "8", "8"]  # type: ignore[index]
        cases.append((mismatch, _legal(("bomb", 4))))
        malformed_table = _observation(); del malformed_table["current_round"]["table_action"]["wildcard_info"]  # type: ignore[index]
        cases.append((malformed_table, _legal(("bomb", 4))))
        malformed_legal = _legal(("bomb", 4)); del malformed_legal[1]["display_text"]
        cases.append((_observation(), malformed_legal))
        for observation, actions in cases:
            with self.subTest(observation=observation):
                expected = FrozenRuleBasedAIAgent(player_id=2).select_action(observation, actions)
                self.assertEqual(self._select(observation, actions), expected)
                self.assertEqual(RuleBasedAIAgent(player_id=2).select_action(observation, actions), expected)

    def test_real_public_observation_accepts_minimal_history_schema_and_chooses_pass(self) -> None:
        game = GuanDanGame(seed=46000, current_level_rank="2")
        game.reset()
        agents = {player: FrozenRuleBasedAIAgent(player_id=player) for player in (1, 2, 3, 4)}
        for _ in range(100):
            observation = game.observe()
            legal_actions = game.legal_actions()
            current = observation["current_round"]
            player_id = observation["my_info"]["player_id"]
            if current["step_no"] == 8:
                self.assertEqual((current["round_no"], player_id), (2, 1))
                self.assertEqual({action["declared_pattern"] for action in legal_actions}, {"pass", "bomb"})
                history_row = observation["history"]["actions"][-1]
                self.assertEqual(
                    set(history_row),
                    {"step_no", "round_no", "player_id", "declared_pattern", "declared_cards", "carrier_cards"},
                )
                self.assertNotIn("wildcard_count", history_row)
                self.assertNotIn("wildcard_info", history_row)
                self.assertNotIn("display_text", history_row)
                baseline = FrozenRuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)
                default = RuleBasedAIAgent(player_id=1).select_action(observation, legal_actions)
                candidate = ConditionalPressurePassAIAgent(player_id=1).select_action(observation, legal_actions)
                patterns = {action["action_id"]: action["declared_pattern"] for action in legal_actions}
                self.assertEqual(patterns[baseline], "bomb")
                self.assertEqual(patterns[default], "pass")
                self.assertEqual(patterns[candidate], "pass")
                self.assertIn(baseline, patterns)
                self.assertIn(default, patterns)
                self.assertIn(candidate, patterns)
                return
            game.step(agents[player_id].select_action(observation, legal_actions))
        self.fail("seed_46000_public_opportunity_not_reached")

    def test_agents_share_one_public_predicate_and_evaluation_uses_frozen_baseline(self) -> None:
        self.assertIs(ConditionalPressurePassAIAgent, RuntimeConditionalPressurePassAIAgent)
        candidate_source = Path("agents/conditional_pressure_pass_ai.py").read_text(encoding="utf-8")
        rule_source = Path("agents/rule_based_ai.py").read_text(encoding="utf-8")
        policy_source = Path("agents/conditional_pressure_pass_policy.py").read_text(encoding="utf-8")
        for source in (candidate_source, rule_source, policy_source):
            self.assertNotIn("_state", source)
            self.assertNotIn("engine.state", source)
        for source in (candidate_source, policy_source):
            self.assertNotIn("evaluation.", source)
        self.assertIn("from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id", candidate_source)
        self.assertIn("from agents.conditional_pressure_pass_policy import conditional_pressure_pass_id", rule_source)
        self.assertEqual(policy_source.count("def conditional_pressure_pass_id("), 1)
        self.assertEqual(policy_source.count("def teammate_pressure_pass_id("), 1)
        self.assertIn("class FrozenRuleBasedAIAgent", rule_source)
        evaluation_source = Path("evaluation/conditional_pressure_pass.py").read_text(encoding="utf-8")
        self.assertIn("from agents.conditional_pressure_pass_ai import ConditionalPressurePassAIAgent", evaluation_source)
        self.assertIn("from agents.rule_based_ai import FrozenRuleBasedAIAgent", evaluation_source)
        self.assertNotIn("conditional_pressure_pass_id(", evaluation_source)
        for directory in ("cli", "rag"):
            for path in Path(directory).rglob("*.py"):
                self.assertNotIn("conditional_pressure_pass", path.read_text(encoding="utf-8"), str(path))
        for path in Path("integrations").rglob("*.py"):
            self.assertNotIn("evaluation.conditional_pressure_pass", path.read_text(encoding="utf-8"), str(path))


class ConditionalPressurePassBenchmarkTests(unittest.TestCase):
    def test_report_is_deterministic_aggregate_only_and_has_a_fixed_decision(self) -> None:
        kwargs = {"max_opportunities_per_game": 2, "max_game_steps": 5000, "max_rollout_steps": 5000}
        first = run_conditional_pressure_pass_benchmark((17, 18), **kwargs)
        second = run_conditional_pressure_pass_benchmark((17, 18), **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.canonical_json_bytes(), second.canonical_json_bytes())
        serialized = json.dumps(first.to_dict(), sort_keys=True)
        for forbidden in ("seed", "hand_cards", "observation", "action_id", "player_id", "snapshot"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(benchmark_decision(first), first.to_dict()["decision"])

    def test_real_seed_has_changed_public_opportunity(self) -> None:
        report = run_conditional_pressure_pass_benchmark(
            (46000,), max_opportunities_per_game=4, max_game_steps=5000, max_rollout_steps=5000,
        )
        self.assertGreater(report.opportunity_count, 0)
        self.assertGreater(report.changed_pair_count, 0)

    def test_input_validation_rejects_ambiguous_runs(self) -> None:
        for seeds in ((), (1, 1), (True,), ("1",)):
            with self.subTest(seeds=seeds):
                with self.assertRaises(ValueError):
                    run_conditional_pressure_pass_benchmark(seeds)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
