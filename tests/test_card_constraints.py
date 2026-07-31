"""Tests for Step J-B1 public card ownership constraints."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from types import MappingProxyType
import unittest

from agents.card_belief import CardBeliefState, PlayerPublicBelief
from agents.card_constraints import build_card_constraints


def _player(
    player_id: int,
    *,
    relation: str,
    remaining_count: object,
    finished: bool = False,
    pass_count: int = 0,
) -> PlayerPublicBelief:
    return PlayerPublicBelief(
        player_id=player_id,
        team="1&3" if relation in {"self", "teammate"} else "2&4",
        relation=relation,
        remaining_count=remaining_count,  # type: ignore[arg-type]
        finished=finished,
        finish_rank=None,
        played_cards=(),
        pass_count=pass_count,
    )


def _belief(
    *,
    token_counts: dict[str, int] | None = None,
    rank_counts: dict[str, int] | None = None,
    players: tuple[PlayerPublicBelief, ...] | None = None,
    token_pool_exact: bool = True,
) -> CardBeliefState:
    token_counts = {"3S": 1, "4H": 1} if token_counts is None else token_counts
    rank_counts = {"3": 1, "4": 1} if rank_counts is None else rank_counts
    players = players or (
        _player(1, relation="self", remaining_count=2),
        _player(2, relation="opponent", remaining_count=1),
        _player(3, relation="teammate", remaining_count=1),
    )
    return CardBeliefState(
        phase="midgame",
        external_unknown_count=sum(rank_counts.values()),
        unseen_cards_by_token=MappingProxyType(dict(token_counts)),
        unseen_cards_by_rank=MappingProxyType(dict(rank_counts)),
        players=players,
        diagnostics=(),
        token_pool_exact=token_pool_exact,
    )


class CardConstraintsTests(unittest.TestCase):
    def test_multiple_active_players_share_each_rank_domain(self) -> None:
        state = build_card_constraints(_belief())

        self.assertEqual(state.possible_owners_by_rank["3"], (2, 3))
        self.assertEqual(state.possible_owners_by_rank["4"], (2, 3))

    def test_exact_token_pool_creates_token_domains(self) -> None:
        state = build_card_constraints(_belief())

        self.assertEqual(state.possible_owners_by_token["3S"], (2, 3))
        self.assertEqual(state.possible_owners_by_token["4H"], (2, 3))

    def test_self_finished_and_zero_capacity_players_are_excluded(self) -> None:
        belief = _belief(players=(
            _player(1, relation="self", remaining_count=2),
            _player(2, relation="opponent", remaining_count=2),
            _player(3, relation="teammate", remaining_count=0),
            _player(4, relation="opponent", remaining_count=2, finished=True),
        ))

        state = build_card_constraints(belief)

        self.assertEqual(state.possible_owners_by_rank["3"], (2,))
        self.assertNotIn(1, state.possible_owners_by_rank["3"])
        self.assertNotIn(3, state.possible_owners_by_rank["3"])
        self.assertNotIn(4, state.possible_owners_by_rank["3"])

    def test_multiple_candidates_do_not_confirm_cards(self) -> None:
        state = build_card_constraints(_belief())

        self.assertTrue(state.is_consistent)
        self.assertTrue(all(not player.confirmed_cards for player in state.players))

    def test_single_candidate_confirms_all_token_copies(self) -> None:
        belief = _belief(
            token_counts={"3S": 2, "BJ": 1},
            rank_counts={"3": 2, "BJ": 1},
            players=(
                _player(1, relation="self", remaining_count=3),
                _player(2, relation="opponent", remaining_count=3),
                _player(3, relation="teammate", remaining_count=0),
            ),
        )

        state = build_card_constraints(belief)
        player_two = next(player for player in state.players if player.player_id == 2)

        self.assertTrue(state.is_consistent)
        self.assertEqual(player_two.confirmed_cards, ("3S", "3S", "BJ"))

    def test_capacity_mismatch_is_inconsistent_and_never_confirms(self) -> None:
        belief = _belief(players=(
            _player(1, relation="self", remaining_count=2),
            _player(2, relation="opponent", remaining_count=1),
        ))

        state = build_card_constraints(belief)

        self.assertFalse(state.is_consistent)
        self.assertTrue(any("external_capacity_mismatch" in item for item in state.diagnostics))
        self.assertTrue(all(not player.confirmed_cards for player in state.players))

    def test_inexact_token_pool_has_no_token_confirmation(self) -> None:
        state = build_card_constraints(_belief(token_pool_exact=False))

        self.assertFalse(state.token_constraints_exact)
        self.assertEqual(dict(state.possible_owners_by_token), {})
        self.assertIn("token_pool_inexact", state.diagnostics)
        self.assertTrue(all(not player.confirmed_cards for player in state.players))

    def test_unseen_cards_without_candidate_produce_diagnostics(self) -> None:
        belief = _belief(players=(
            _player(1, relation="self", remaining_count=2),
            _player(2, relation="opponent", remaining_count=0),
        ))

        state = build_card_constraints(belief)

        self.assertFalse(state.is_consistent)
        self.assertIn("no_possible_owner", state.diagnostics)
        self.assertTrue(any("empty_owner_domain" in item for item in state.diagnostics))

    def test_invalid_capacity_is_diagnosed_and_excluded(self) -> None:
        belief = _belief(players=(
            _player(1, relation="self", remaining_count=2),
            _player(2, relation="opponent", remaining_count=-1),
            _player(3, relation="teammate", remaining_count="2"),
            _player(4, relation="opponent", remaining_count=2),
        ))

        state = build_card_constraints(belief)

        self.assertFalse(state.is_consistent)
        self.assertTrue(any("invalid_remaining_capacity:2" in item for item in state.diagnostics))
        self.assertTrue(any("invalid_remaining_capacity:3" in item for item in state.diagnostics))
        self.assertEqual(state.possible_owners_by_rank["3"], (4,))

    def test_to_dict_is_json_serializable(self) -> None:
        state = build_card_constraints(_belief())

        self.assertIsInstance(json.dumps(state.to_dict()), str)

    def test_output_is_immutable_and_does_not_modify_input(self) -> None:
        belief = _belief()
        before = belief.to_dict()
        state = build_card_constraints(belief)

        with self.assertRaises(FrozenInstanceError):
            state.phase = "opening"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            state.possible_owners_by_rank["3"] = ()  # type: ignore[index]
        self.assertEqual(belief.to_dict(), before)

    def test_pass_count_does_not_shrink_hard_domains(self) -> None:
        belief = _belief()
        changed_players = tuple(
            replace(player, pass_count=player.pass_count + 7)
            if player.player_id == 2 else player
            for player in belief.players
        )

        original = build_card_constraints(belief)
        after_passes = build_card_constraints(replace(belief, players=changed_players))

        self.assertEqual(
            original.possible_owners_by_rank,
            after_passes.possible_owners_by_rank,
        )
        self.assertEqual(
            original.possible_owners_by_token,
            after_passes.possible_owners_by_token,
        )


if __name__ == "__main__":
    unittest.main()
