import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

from agents.deepseek_client import DeepSeekClient
from agents.game_phase import (
    CRITICAL_ENDGAME,
    ENDGAME,
    MIDGAME,
    NEAR_OPEN_ENDGAME,
    OPENING,
    classify_game_phase,
)
from agents.opening_strategy import OpeningFormulaStrategy
from agents.rag_advisor import RAGAdvisor
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


def _action(action_id: int, pattern: str = "single") -> dict[str, object]:
    return {
        "action_id": action_id,
        "declared_pattern": pattern,
        "declared_cards": ["9"] if pattern != "pass" else [],
        "carrier_cards": ["9S"] if pattern != "pass" else [],
        "wildcard_count": 0,
        "wildcard_info": [],
        "display_text": pattern,
    }


def _observation(
    *,
    history_count: int = 0,
    step_no: int | None = None,
    my_hand_count: int = 20,
    other_hand_counts: tuple[int, int, int] = (20, 20, 20),
    finished_indexes: tuple[int, ...] = (),
) -> dict[str, object]:
    resolved_step_no = history_count if step_no is None else step_no
    finish_order = [index + 2 for index in finished_indexes]
    return {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": ["3S"] * my_hand_count,
            "hand_count": my_hand_count,
            "remaining_single_card_count": 4,
        },
        "current_round": {
            "step_no": resolved_step_no,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {
                "player_id": index + 2,
                "team": "1&3" if index == 1 else "2&4",
                "hand_count": hand_count,
                "finished": index in finished_indexes,
                "finish_rank": 1 if index in finished_indexes else None,
            }
            for index, hand_count in enumerate(other_hand_counts)
        ],
        "history": {
            "actions": [{"step_no": index + 1} for index in range(history_count)],
            "finish_order": finish_order,
        },
    }


def _real_advisor() -> RAGAdvisor:
    loader = KnowledgeBaseLoader(Path("rag"))
    return RAGAdvisor(KnowledgeRetriever(loader.load_all_documents()))


class TestGamePhase(unittest.TestCase):
    def test_history_zero_and_eight_are_opening(self) -> None:
        for history_count in (0, 8):
            with self.subTest(history_count=history_count):
                context = classify_game_phase(_observation(history_count=history_count, my_hand_count=18, other_hand_counts=(16, 16, 16)))
                self.assertEqual(context.phase, OPENING)

    def test_history_nine_is_midgame(self) -> None:
        context = classify_game_phase(_observation(history_count=9, my_hand_count=20, other_hand_counts=(20, 20, 20)))
        self.assertEqual(context.phase, MIDGAME)

    def test_inconsistent_history_and_step_no_use_later_progress(self) -> None:
        for history_count, step_no in ((9, 0), (0, 9)):
            with self.subTest(history_count=history_count, step_no=step_no):
                context = classify_game_phase(_observation(history_count=history_count, step_no=step_no))
                self.assertEqual(context.history_action_count, 9)
                self.assertEqual(context.phase, MIDGAME)

    def test_my_nine_cards_is_endgame(self) -> None:
        self.assertEqual(classify_game_phase(_observation(my_hand_count=9)).phase, ENDGAME)

    def test_other_player_with_five_cards_is_endgame(self) -> None:
        self.assertEqual(
            classify_game_phase(_observation(other_hand_counts=(5, 20, 20))).phase,
            ENDGAME,
        )

    def test_finished_player_is_endgame(self) -> None:
        context = classify_game_phase(_observation(other_hand_counts=(0, 20, 20), finished_indexes=(0,)))
        self.assertEqual(context.phase, ENDGAME)
        self.assertEqual(context.finished_player_count, 1)

    def test_external_count_twenty_is_near_open_endgame(self) -> None:
        context = classify_game_phase(_observation(history_count=9, other_hand_counts=(7, 7, 6)))
        self.assertEqual(context.external_unknown_count, 20)
        self.assertEqual(context.phase, NEAR_OPEN_ENDGAME)

    def test_external_count_twelve_is_critical_endgame(self) -> None:
        context = classify_game_phase(_observation(history_count=9, other_hand_counts=(4, 4, 4)))
        self.assertEqual(context.external_unknown_count, 12)
        self.assertEqual(context.phase, CRITICAL_ENDGAME)

    def test_priority_and_serializable_immutable_context(self) -> None:
        opening = classify_game_phase(_observation())
        endgame = classify_game_phase(_observation(my_hand_count=9))
        near = classify_game_phase(_observation(history_count=9, my_hand_count=9, other_hand_counts=(7, 7, 6)))
        critical = classify_game_phase(_observation(history_count=9, my_hand_count=9, other_hand_counts=(4, 4, 4)))

        self.assertEqual(opening.phase, OPENING)
        self.assertEqual(endgame.phase, ENDGAME)
        self.assertEqual(near.phase, NEAR_OPEN_ENDGAME)
        self.assertEqual(critical.phase, CRITICAL_ENDGAME)
        self.assertEqual(json.loads(json.dumps(opening.to_dict()))["phase"], OPENING)
        with self.assertRaises(FrozenInstanceError):
            opening.phase = MIDGAME  # type: ignore[misc]

    def test_opening_rag_pruning_and_prompt_share_one_context(self) -> None:
        observation = _observation()
        legal_actions = [_action(1), _action(2, "pair")]
        phase_context = classify_game_phase(observation)

        self.assertTrue(
            OpeningFormulaStrategy()._is_applicable(
                observation,
                legal_actions,
                phase_context=phase_context,
            )
        )
        scene_tags = RAGAdvisor._scene_tags(observation, legal_actions, phase_context=phase_context)
        self.assertEqual(scene_tags["phase"], phase_context.phase)

        captured: list[str] = []
        original = DeepSeekClient._lead_pruned_actions

        def record_phase(actions: list[dict[str, object]], phase: str) -> list[dict[str, object]]:
            captured.append(phase)
            return original(actions, phase)

        with mock.patch.object(DeepSeekClient, "_lead_pruned_actions", side_effect=record_phase):
            DeepSeekClient._prune_legal_actions(
                legal_actions,
                "free",
                step_no=0,
                hand_count=20,
                phase_context=phase_context,
            )

        self.assertEqual(captured, [phase_context.phase])
        prompt = DeepSeekClient._build_structured_prompt(
            my_info=dict(observation["my_info"]),
            current_round=dict(observation["current_round"]),
            other_players=list(observation["other_players"]),
            history=dict(observation["history"]),
            legal_actions=legal_actions,
            phase_context=phase_context,
        )
        self.assertIn(f"统一局面阶段：{phase_context.phase}", prompt)

    def test_near_and_critical_endgame_inherit_endgame_rag_entries(self) -> None:
        advisor = _real_advisor()
        for observation, expected_phase in (
            (_observation(history_count=9, other_hand_counts=(7, 7, 6)), NEAR_OPEN_ENDGAME),
            (_observation(history_count=9, other_hand_counts=(4, 4, 4)), CRITICAL_ENDGAME),
        ):
            with self.subTest(phase=expected_phase):
                phase_context = classify_game_phase(observation)
                context = advisor.get_rag_context(
                    observation=observation,
                    legal_actions=[_action(1)],
                    hand_eval={"label": "medium"},
                    phase_context=phase_context,
                    top_k=3,
                )
                hit_ids = [str(item["source_id"]) for item in context["experience_hits"]]
                self.assertEqual(context["scene_tags"]["phase"], expected_phase)
                self.assertIn("exp_endgame_run_out_001", hit_ids)


if __name__ == "__main__":
    unittest.main()
