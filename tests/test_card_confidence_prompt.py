from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest

from agents.card_confidence import CardConfidenceState, PlayerCardConfidence, RankMarginalConfidence
from agents.card_confidence_prompt import (
    CARD_CONFIDENCE_PROMPT_MAX_CHARS,
    CardConfidencePromptPayload,
    build_card_confidence_prompt_payload,
)


def _state() -> CardConfidenceState:
    denominator = 6
    ranks_two = (
        RankMarginalConfidence("3", 3, 3, denominator),
        RankMarginalConfidence("4", 0, 0, denominator),
    )
    ranks_three = (
        RankMarginalConfidence("3", 3, 3, denominator),
        RankMarginalConfidence("4", 6, 12, denominator),
    )
    return CardConfidenceState(
        phase="critical_endgame",
        status="available",
        source="physical_assignment_marginal_v1",
        calibration_scope="critical_endgame_policy_diverse_v1",
        external_unknown_count=8,
        physical_assignment_count=denominator,
        players=(
            PlayerCardConfidence(2, 4, ranks_two),
            PlayerCardConfidence(3, 4, ranks_three),
        ),
        diagnostics=(),
    )


class CardConfidencePromptTests(unittest.TestCase):
    def test_exact_fixed_snapshot_and_fraction_formatting(self) -> None:
        payload = build_card_confidence_prompt_payload(_state())
        expected = (
            "范围：critical_endgame_policy_diverse_v1\n"
            "说明：以下是公开硬约束下等权物理分配的组合边际，不是隐藏牌事实；P=至少持有一张，E=期望张数。\n"
            "玩家2（余4张）：3[P=1/2,E=1/2]；4[P=0,E=0]\n"
            "玩家3（余4张）：3[P=1/2,E=1/2]；4[P=1,E=2]"
        )
        self.assertEqual(payload.status, "ready")
        self.assertEqual(payload.text, expected)
        self.assertEqual(payload.char_count, len(expected))
        self.assertEqual(payload.source, "physical_assignment_marginal_v1")
        self.assertEqual(payload.calibration_scope, "critical_endgame_policy_diverse_v1")
        self.assertEqual(payload.diagnostics, ())
        self.assertNotIn(".", payload.text)

    def test_order_immutability_json_and_repeatability(self) -> None:
        payload = build_card_confidence_prompt_payload(_state())
        self.assertLess(payload.text.index("玩家2"), payload.text.index("玩家3"))
        self.assertLess(payload.text.index("3[P="), payload.text.index("4[P="))
        self.assertEqual(payload, build_card_confidence_prompt_payload(_state()))
        self.assertIsInstance(json.dumps(payload.to_dict(), allow_nan=False), str)
        self.assertIn("__slots__", CardConfidencePromptPayload.__dict__)
        with self.assertRaises(FrozenInstanceError):
            payload.status = "omitted"  # type: ignore[misc]

    def test_unavailable_metadata_and_confidence_diagnostics_are_omitted(self) -> None:
        state = _state()
        cases = (
            (replace(state, status="unavailable"), "confidence_unavailable"),
            (replace(state, phase="near_open_endgame"), "invalid_phase"),
            (replace(state, source="other"), "invalid_source"),
            (replace(state, calibration_scope="other"), "invalid_calibration_scope"),
            (replace(state, diagnostics=("bad",)), "confidence_diagnostics_present"),
        )
        for malformed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                payload = build_card_confidence_prompt_payload(malformed)
                self.assertEqual(payload.status, "omitted")
                self.assertEqual(payload.text, "")
                self.assertEqual(payload.char_count, 0)
                self.assertEqual(payload.source, "none")
                self.assertEqual(payload.calibration_scope, "none")
                self.assertIn(diagnostic, payload.diagnostics)

    def test_counts_players_capacities_and_ranks_fail_closed(self) -> None:
        state = _state()
        player = state.players[0]
        rank = player.ranks[0]
        cases = tuple(
            (replace(state, external_unknown_count=value), "invalid_external_unknown_count")
            for value in (0, -1, 1.5, True)
        ) + tuple(
            (replace(state, physical_assignment_count=value), "invalid_denominator")
            for value in (0, -1, 1.5, True)
        ) + (
            (replace(state, players=[]), "invalid_player"),  # type: ignore[arg-type]
            (replace(state, players=()), "invalid_player"),
            (replace(state, players=(replace(player, player_id=5), *state.players[1:])), "invalid_player"),
            (replace(state, players=(replace(player, player_id=True), *state.players[1:])), "invalid_player"),
            (replace(state, players=(player, replace(state.players[1], player_id=2))), "duplicate_player"),
            (replace(state, players=(replace(player, remaining_capacity=0), *state.players[1:])), "invalid_capacity"),
            (replace(state, players=(replace(player, remaining_capacity=True), *state.players[1:])), "invalid_capacity"),
            (replace(state, players=(replace(player, remaining_capacity=3), *state.players[1:])), "capacity_mismatch"),
            (replace(state, players=(replace(player, ranks=[]), *state.players[1:])), "invalid_rank_order"),  # type: ignore[arg-type]
            (replace(state, players=(replace(player, ranks=()), *state.players[1:])), "invalid_rank_order"),
            (replace(state, players=(replace(player, ranks=(player.ranks[1], player.ranks[0])), *state.players[1:])), "invalid_rank_order"),
            (replace(state, players=(replace(player, ranks=(rank, rank)), *state.players[1:])), "duplicate_rank"),
            (replace(state, players=(replace(player, ranks=(replace(rank, rank="X"), player.ranks[1])), *state.players[1:])), "invalid_rank_order"),
            (replace(state, players=(replace(player, ranks=(rank,)), *state.players[1:])), "rank_set_mismatch"),
        )
        for malformed, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                payload = build_card_confidence_prompt_payload(malformed)
                self.assertEqual(payload.status, "omitted")
                self.assertEqual(payload.text, "")
                self.assertIn(diagnostic, payload.diagnostics)

    def test_marginals_fail_closed_without_partial_text(self) -> None:
        state = _state()
        player = state.players[0]
        rank = player.ranks[0]
        malformed_ranks = [
            replace(rank, denominator=5),
            *(replace(rank, presence_numerator=value) for value in (-1, 7, 1.5, "1", None, True)),
            *(replace(rank, expected_copy_numerator=value) for value in (-1, 25, 1.5, "1", None, True)),
        ]
        for malformed_rank in malformed_ranks:
            with self.subTest(rank=malformed_rank):
                malformed = replace(
                    state,
                    players=(replace(player, ranks=(malformed_rank, player.ranks[1])), *state.players[1:]),
                )
                payload = build_card_confidence_prompt_payload(malformed)
                self.assertEqual(payload.status, "omitted")
                self.assertEqual(payload.text, "")
                self.assertIn("invalid_rank_marginal", payload.diagnostics)

    def test_budget_is_hard_and_call_parameters_are_strict(self) -> None:
        state = _state()
        payload = build_card_confidence_prompt_payload(state)
        self.assertEqual(
            build_card_confidence_prompt_payload(state, max_chars=payload.char_count).status,
            "ready",
        )
        exceeded = build_card_confidence_prompt_payload(state, max_chars=payload.char_count - 1)
        self.assertEqual(exceeded.status, "omitted")
        self.assertEqual(exceeded.text, "")
        self.assertEqual(exceeded.diagnostics, ("prompt_budget_exceeded",))
        for value in (0, -1, 1.5, True, CARD_CONFIDENCE_PROMPT_MAX_CHARS + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_card_confidence_prompt_payload(state, max_chars=value)

    def test_invalid_state_and_source_boundaries(self) -> None:
        payload = build_card_confidence_prompt_payload(object())  # type: ignore[arg-type]
        self.assertEqual(payload.to_dict(), {
            "status": "omitted", "text": "", "char_count": 0,
            "source": "none", "calibration_scope": "none",
            "diagnostics": ["invalid_confidence_state"],
        })
        source = Path("agents/card_confidence_prompt.py").read_text(encoding="utf-8")
        for forbidden in ("observation", "history", "ground_truth", "game._state", "evaluation", "engine", "deepseek", "rag"):
            self.assertNotIn(forbidden, source)
        for path in ("agents/rag_advisor.py", "cli/run_4ai_debug.py", "engine/game.py"):
            self.assertNotIn("card_confidence_prompt", Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
