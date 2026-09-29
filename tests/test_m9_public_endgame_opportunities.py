from __future__ import annotations

import json
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.card_tracker import exact_public_hand_assignment
from agents.deepseek_ai import DeepSeekAIAgent
from agents.deepseek_client import DeepSeekClient
from agents.rule_based_ai import RuleBasedAIAgent
from engine.game import GuanDanGame
from engine.public_endgame import (
    PublicEndgameAnalysis,
    analyze_public_endgame,
)
from integrations.botzone.agent_runtime import build_agent_factory


def _rollout_to_step(
    seed: int,
    target_step: int,
) -> tuple[GuanDanGame, dict[str, object], list[dict[str, object]]]:
    game = GuanDanGame(seed=seed, current_level_rank="2")
    game.reset()
    while game.observe()["current_round"]["step_no"] < target_step:
        observation = game.observe()
        actions = game.legal_actions()
        player_id = int(observation["my_info"]["player_id"])
        game.step(RuleBasedAIAgent(player_id).select_action(observation, actions))
        if game._state.is_finished:  # noqa: SLF001 - deterministic engine fixture
            raise AssertionError("seeded game ended before requested observation")
    return game, game.observe(), game.legal_actions()


def _clone_game(game: GuanDanGame) -> GuanDanGame:
    clone = GuanDanGame(current_level_rank=game._current_level_rank)  # noqa: SLF001
    clone._state = game._require_state()  # noqa: SLF001 - engine oracle only
    clone._invalidate_legal_actions_cache()  # noqa: SLF001
    return clone


def _reference_profile(game: GuanDanGame, root_team: str) -> tuple[int, tuple[int, ...]]:
    """Exhaustively enumerate engine continuations without using M9 search code."""
    state = game._require_state()  # noqa: SLF001 - test-only continuation oracle
    if state.is_finished:
        winner = state.winner
        value = 0 if winner == "draw" else 1 if winner == root_team else -1
        return value, (value,)

    current_team = "team_13" if state.current_player_id in {1, 3} else "team_24"
    maximizing = current_team == root_team
    child_profiles = []
    for action in game.legal_actions():
        child = _clone_game(game)
        child.step(int(action["action_id"]))
        child_profiles.append(_reference_profile(child, root_team))
    guarantees = [profile[0] for profile in child_profiles]
    reachable = tuple(sorted({value for _, values in child_profiles for value in values}))
    return (max(guarantees) if maximizing else min(guarantees)), reachable


def _reference_root_profiles(
    game: GuanDanGame,
) -> tuple[
    tuple[tuple[int, int], ...],
    tuple[tuple[int, tuple[int, ...]], ...],
]:
    player_id = game._require_state().current_player_id  # noqa: SLF001
    root_team = "team_13" if player_id in {1, 3} else "team_24"
    guarantees = []
    reachable = []
    for action in game.legal_actions():
        child = _clone_game(game)
        child.step(int(action["action_id"]))
        value, outcomes = _reference_profile(child, root_team)
        action_id = int(action["action_id"])
        guarantees.append((action_id, value))
        reachable.append((action_id, outcomes))
    return tuple(guarantees), tuple(reachable)


def _fake_response_transport(captured: list[dict[str, object]]):
    def transport(request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        captured.append(payload)
        prompt = payload["messages"][1]["content"]
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        ids = [int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)]
        assert ids
        answer = ids[-1]
        event = json.dumps({"choices": [{"delta": {"content": json.dumps({"action_id": answer})}}]})
        return f"data: {event}\n\ndata: [DONE]\n\n"
    return transport


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        deepseek_api_key="synthetic-key",
        deepseek_base_url="https://example.invalid",
        deepseek_model="synthetic-model",
        deepseek_timeout=2.0,
        deepseek_max_retries=0,
        hand_evaluation_enabled=False,
        opening_formula_enabled=False,
        card_tracking_enabled=False,
    )


def _factory_agent(captured: list[dict[str, object]]):
    config = _config()
    factory = build_agent_factory(
        "deepseek",
        config_loader=lambda: config,
        client_factory=lambda **kwargs: DeepSeekClient(
            **kwargs,
            transport=_fake_response_transport(captured),
        ),
        rag_factory=lambda: None,
    )
    return config, factory


class M9PublicEndgameOpportunityTests(unittest.TestCase):
    def test_search_profiles_match_exhaustive_engine_continuations(self) -> None:
        # These generated legal games cover loss/draw floor differences,
        # pass-versus-play opportunity, multiple winning routes, aliases, and
        # a teammate-led pass reset after finish order has shortened the table.
        # The last two states have multiple independently proven winning roots.
        for seed, step in (
            (10, 86), (10, 87), (9, 78), (26, 85), (288, 83), (12, 87),
            (13, 99), (6, 93),
        ):
            with self.subTest(seed=seed, step=step):
                game, observation, actions = _rollout_to_step(seed, step)
                assignment = exact_public_hand_assignment(observation)
                self.assertIsNotNone(assignment)
                analysis = analyze_public_endgame(observation, actions, assignment)
                expected_values, expected_reachable = _reference_root_profiles(game)
                first_guaranteed = next(
                    (action_id for action_id, value in expected_values if value == 1),
                    None,
                )
                if first_guaranteed is not None:
                    self.assertEqual(analysis.status, "proven_win")
                    self.assertEqual(analysis.proven_action_id, first_guaranteed)
                    self.assertEqual(analysis.action_values, ())
                    self.assertEqual(analysis.action_reachable_values, ())
                    self.assertEqual(analysis.best_action_ids, ())
                    self.assertIsNone(analysis.unique_best_action_id)
                else:
                    self.assertEqual(analysis.status, "solved")
                    self.assertIsNone(analysis.proven_action_id)
                    self.assertEqual(analysis.action_values, expected_values)
                    self.assertEqual(analysis.action_reachable_values, expected_reachable)

    def test_any_completed_guarantee_shortcuts_even_if_other_routes_also_win(self) -> None:
        from agents.known_endgame import (
            describe_proven_endgame_choice,
            select_proven_endgame_action,
        )

        cases = (
            (10, 87, "guaranteed"),
            (13, 99, "multiple_guaranteed"),
            (6, 93, "multiple_guaranteed"),
            (9, 78, "unique_reachable"),
            (26, 85, "multiple_reachable"),
            (10, 86, "strict_floor"),
        )
        for seed, step, expected_kind in cases:
            with self.subTest(seed=seed, step=step):
                game, observation, actions = _rollout_to_step(seed, step)
                assignment = exact_public_hand_assignment(observation)
                self.assertIsNotNone(assignment)
                analysis = analyze_public_endgame(observation, actions, assignment)
                projected = DeepSeekClient._project_prompt_actions(observation, actions)
                signatures = {
                    int(action["action_id"]): DeepSeekClient._action_signature(action)
                    for action in projected
                }
                guarantees = dict(analysis.action_values)
                reachable = dict(analysis.action_reachable_values)
                selected = select_proven_endgame_action(analysis, actions, signatures)
                if expected_kind in {"guaranteed", "multiple_guaranteed"}:
                    expected_values, _ = _reference_root_profiles(game)
                    proven_ids = [action_id for action_id, value in expected_values if value == 1]
                    self.assertTrue(proven_ids)
                    if expected_kind == "multiple_guaranteed":
                        self.assertGreater(len(proven_ids), 1)
                    self.assertEqual(analysis.status, "proven_win")
                    self.assertEqual(analysis.proven_action_id, proven_ids[0])
                    self.assertEqual(selected, proven_ids[0])
                    self.assertIn(selected, {int(action["action_id"]) for action in actions})
                    expected_wording = "可保底本队胜"
                elif expected_kind == "unique_reachable":
                    self.assertEqual(analysis.status, "solved")
                    winning_routes = {
                        (signatures[action_id], guarantees[action_id], reachable[action_id])
                        for action_id in guarantees
                        if 1 in reachable[action_id]
                    }
                    self.assertEqual(len(winning_routes), 1)
                    self.assertLess(guarantees[selected], 1)
                    self.assertIn(1, reachable[selected])
                    self.assertTrue(
                        all(
                            1 not in values and 0 in values
                            for action_id, values in reachable.items()
                            if action_id != selected
                        )
                    )
                    expected_wording = "唯一存在合法本队胜局续线"
                elif expected_kind == "multiple_reachable":
                    self.assertEqual(analysis.status, "solved")
                    reachable_routes = {
                        (signatures[action_id], guarantees[action_id], reachable[action_id])
                        for action_id in guarantees
                        if 1 in reachable[action_id]
                    }
                    self.assertGreater(len(reachable_routes), 1)
                    self.assertIsNone(selected)
                    continue
                else:
                    self.assertEqual(analysis.status, "solved")
                    self.assertTrue(all(1 not in values for values in reachable.values()))
                    best_floor = max(guarantees.values())
                    best_routes = {
                        (signatures[action_id], guarantees[action_id], reachable[action_id])
                        for action_id in guarantees
                        if guarantees[action_id] == best_floor
                    }
                    self.assertEqual(len(best_routes), 1)
                    self.assertEqual(guarantees[selected], best_floor)
                    self.assertLess(best_floor, 1)
                    expected_wording = "无可达本队胜局续线"
                wording = describe_proven_endgame_choice(analysis, selected)
                self.assertIn(expected_wording, wording)
                if expected_kind == "unique_reachable":
                    self.assertIn("不保证获胜", wording)

        # The local path returns a raw canonical ID and makes the
        # non-guaranteed opportunity classification observable to callers.
        _, observation, actions = _rollout_to_step(9, 78)
        assignment = exact_public_hand_assignment(observation)
        class _NoCallClient:
            def suggest_action_id(self, **_kwargs):
                raise AssertionError("complete unique opportunity should be selected locally")

        config = _config()
        with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
            agent = DeepSeekAIAgent(
                player_id=int(observation["my_info"]["player_id"]),
                client=_NoCallClient(),  # type: ignore[arg-type]
                hand_evaluation_enabled=False,
                opening_formula_enabled=False,
            )
            selected = agent.select_action(observation, actions)
        self.assertIn(selected, {int(action["action_id"]) for action in actions})
        self.assertEqual(agent.last_decision_source, "local")
        self.assertIn("唯一存在合法本队胜局续线", agent.last_public_endgame_decision_summary)
        self.assertIn("不保证获胜", agent.last_public_endgame_decision_summary)

    def test_guaranteed_root_stops_before_searching_later_root_at_exact_budget(self) -> None:
        from engine import public_endgame

        _, observation, actions = _rollout_to_step(13, 99)
        assignment = exact_public_hand_assignment(observation)
        self.assertIsNotNone(assignment)
        baseline = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(baseline.status, "proven_win")
        self.assertEqual(baseline.proven_action_id, int(actions[0]["action_id"]))
        self.assertGreater(baseline.nodes, 0)

        original_build = public_endgame._build_public_game
        original_copy = public_endgame._copy_game
        built_games = []
        root_copies = 0

        def capture_build(*args, **kwargs):
            game = original_build(*args, **kwargs)
            built_games.append(game)
            return game

        def reject_later_root_copy(game):
            nonlocal root_copies
            if built_games and game._require_state() is built_games[0]._require_state():
                root_copies += 1
                if root_copies > 1:
                    raise AssertionError("a later root action was searched after a complete win proof")
            return original_copy(game)

        with (
            patch("engine.public_endgame._build_public_game", side_effect=capture_build),
            patch("engine.public_endgame._copy_game", side_effect=reject_later_root_copy),
        ):
            result = analyze_public_endgame(
                observation,
                actions,
                assignment,
                max_nodes=baseline.nodes,
            )

        self.assertEqual(result.status, "proven_win")
        self.assertEqual(result.proven_action_id, baseline.proven_action_id)
        self.assertEqual(root_copies, 1)

    def test_default_factory_skips_model_for_multiple_proven_routes(self) -> None:
        for seed, step in ((13, 99), (6, 93)):
            with self.subTest(seed=seed, step=step):
                game, observation, actions = _rollout_to_step(seed, step)
                assignment = exact_public_hand_assignment(observation)
                analysis = analyze_public_endgame(observation, actions, assignment)
                expected_values, _ = _reference_root_profiles(game)
                proven_ids = [action_id for action_id, value in expected_values if value == 1]
                self.assertGreater(len(proven_ids), 1)
                self.assertEqual(analysis.status, "proven_win")
                self.assertEqual(analysis.proven_action_id, proven_ids[0])

                captured: list[dict[str, object]] = []
                config, factory = _factory_agent(captured)
                with patch("agents.deepseek_ai.AppConfig.from_env", return_value=config):
                    agent = factory(int(observation["my_info"]["player_id"]))
                    selected = agent.select_action(observation, actions)

                self.assertEqual(selected, proven_ids[0])
                self.assertIn(selected, {int(action["action_id"]) for action in actions})
                self.assertEqual(agent.last_decision_source, "local")
                self.assertEqual(agent.last_public_endgame_analysis.status, "proven_win")
                self.assertIn("可保底本队胜", agent.last_public_endgame_decision_summary)
                self.assertEqual(captured, [])

    def test_equivalent_raw_ids_choose_one_stable_original_representative(self) -> None:
        from agents.known_endgame import select_proven_endgame_action

        _, observation, actions = _rollout_to_step(288, 83)
        assignment = exact_public_hand_assignment(observation)
        analysis = analyze_public_endgame(observation, actions, assignment)
        projected = DeepSeekClient._project_prompt_actions(observation, actions)
        signatures = {
            int(action["action_id"]): DeepSeekClient._action_signature(action)
            for action in projected
        }
        raw_single_ids = [
            int(action["action_id"])
            for action in actions
            if action["declared_pattern"] == "single"
        ]
        self.assertEqual(len(raw_single_ids), 2)
        self.assertEqual(signatures[raw_single_ids[0]], signatures[raw_single_ids[1]])
        self.assertEqual(
            select_proven_endgame_action(analysis, actions, signatures),
            raw_single_ids[0],
        )

    def test_default_factory_formats_unresolved_endgame_and_keeps_model_id(self) -> None:
        _, observation, actions = _rollout_to_step(6, 94)
        assignment = exact_public_hand_assignment(observation)
        solved = analyze_public_endgame(observation, actions, assignment)
        self.assertEqual(solved.status, "solved")
        from agents.known_endgame import select_proven_endgame_action

        self.assertIsNone(
            select_proven_endgame_action(
                solved,
                actions,
                {
                    int(action["action_id"]): DeepSeekClient._action_signature(action)
                    for action in DeepSeekClient._project_prompt_actions(observation, actions)
                },
            )
        )

        captured: list[dict[str, object]] = []
        config, factory = _factory_agent(captured)
        with (
            patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
            patch("engine.public_endgame.analyze_public_endgame", return_value=solved),
        ):
            agent = factory(int(observation["my_info"]["player_id"]))
            selected = agent.select_action(observation, actions)

        self.assertEqual(len(captured), 1)
        self.assertEqual(agent.last_decision_source, "model")
        prompt = captured[0]["messages"][1]["content"]
        self.assertIn("【公开确证手牌】", prompt)
        self.assertIn("【公开残局推演】", prompt)
        self.assertIn("可达{", prompt)
        candidate_section = prompt.split("【候选动作】", 1)[1].split("【规则库依据】", 1)[0]
        visible_ids = {int(value) for value in re.findall(r"action_id=(\d+)", candidate_section)}
        compared_ids = {
            int(value)
            for pair in re.findall(r"M5公开残局对照 action_id=(\d+).*?action_id=(\d+)", prompt)
            for value in pair
        }
        self.assertTrue(compared_ids)
        self.assertTrue(compared_ids.issubset(visible_ids))
        self.assertLessEqual(len(visible_ids), 80)
        self.assertIn(selected, visible_ids)
        self.assertIn(selected, {int(action["action_id"]) for action in actions})

    def test_budget_exceeded_and_oversized_exact_hands_still_reach_model_request(self) -> None:
        from engine.public_endgame import analyze_public_endgame as actual_analyze

        scenarios = ((9, 78, "node_budget"), (110, 69, "search_scope"))
        for seed, step, reason in scenarios:
            with self.subTest(seed=seed, step=step):
                _, observation, actions = _rollout_to_step(seed, step)
                assignment = exact_public_hand_assignment(observation)
                self.assertIsNotNone(assignment)
                captured: list[dict[str, object]] = []
                config, factory = _factory_agent(captured)
                if reason == "node_budget":
                    def limited(*args, **kwargs):
                        return actual_analyze(*args, **kwargs, max_nodes=1)
                    analyzer_patch = patch("engine.public_endgame.analyze_public_endgame", side_effect=limited)
                else:
                    analyzer_patch = patch("engine.public_endgame.analyze_public_endgame")

                with (
                    patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
                    analyzer_patch as analyzer,
                ):
                    agent = factory(int(observation["my_info"]["player_id"]))
                    selected = agent.select_action(observation, actions)

                self.assertEqual(len(captured), 1)
                self.assertEqual(agent.last_decision_source, "model")
                self.assertIn(selected, {int(action["action_id"]) for action in actions})
                self.assertIn("【公开确证手牌】", captured[0]["messages"][1]["content"])
                if reason == "node_budget":
                    self.assertEqual(agent.last_public_endgame_analysis.status, "budget_exceeded")
                    analyzer.assert_called_once()
                else:
                    self.assertIsNone(agent.last_public_endgame_analysis)
                    analyzer.assert_not_called()

    def test_uncertain_or_incomplete_public_assignment_is_not_disclosed(self) -> None:
        from copy import deepcopy

        _, observation, actions = _rollout_to_step(9, 78)
        truncated = deepcopy(observation)
        truncated["history"]["actions"].pop()
        self.assertIsNone(exact_public_hand_assignment(truncated))

        _, early_observation, early_actions = _rollout_to_step(1, 0)
        self.assertIsNone(exact_public_hand_assignment(early_observation))

        inconsistent_count = deepcopy(observation)
        next(row for row in inconsistent_count["other_players"] if not row["finished"])["hand_count"] += 1
        self.assertIsNone(exact_public_hand_assignment(inconsistent_count))

        scenarios = (
            (truncated, actions),
            (early_observation, early_actions),
            (inconsistent_count, actions),
        )
        for candidate_observation, candidate_actions in scenarios:
            with self.subTest(step=candidate_observation["current_round"]["step_no"]):
                captured: list[dict[str, object]] = []
                config, factory = _factory_agent(captured)
                with (
                    patch("agents.deepseek_ai.AppConfig.from_env", return_value=config),
                    patch("engine.public_endgame.analyze_public_endgame") as analyzer,
                ):
                    agent = factory(int(candidate_observation["my_info"]["player_id"]))
                    agent.select_action(candidate_observation, candidate_actions)
                prompt = captured[0]["messages"][1]["content"]
                self.assertNotIn("【公开确证手牌】", prompt)
                analyzer.assert_not_called()

    def test_explicit_time_budget_returns_no_partial_proof(self) -> None:
        _, observation, actions = _rollout_to_step(26, 85)
        assignment = exact_public_hand_assignment(observation)
        with patch("engine.public_endgame.monotonic", side_effect=(10.0, 11.0, 11.0)):
            result = analyze_public_endgame(
                observation,
                actions,
                assignment,
            )
        self.assertEqual(result.status, "budget_exceeded")
        self.assertEqual(result.action_values, ())
        self.assertEqual(result.action_reachable_values, ())


if __name__ == "__main__":
    unittest.main()
