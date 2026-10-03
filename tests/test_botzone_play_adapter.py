from __future__ import annotations

import unittest
from dataclasses import replace
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from engine.actions import ActionType
from engine.cards import Card
from engine.game import GuanDanGame
from engine.patterns import PatternType

from integrations.botzone.cards import ALL_CARDS, card_from_id, card_id_for
from integrations.botzone.models import ActionClaim, GlobalState, HistoryEntry, PlayRequest
from integrations.botzone.play_adapter import (
    AdapterError,
    NoTributeRuleBasedHandler,
    _history_entry_to_action,
    botzone_id_to_engine_card,
    encode_action_claim,
    project_decision,
    team_for_engine_player,
)
from integrations.botzone.session import HandlerContext, SessionStore, HandlerResult
from integrations.botzone.models import DealRequest


def _request(history: tuple[HistoryEntry, ...] = ()) -> PlayRequest:
    return PlayRequest(history=history, done=(), pass_on=-1, global_state=GlobalState("2", 0, None, None, False))


def _context(hand: tuple[int, ...], history: tuple[HistoryEntry, ...] = (), *, local: int = 0) -> HandlerContext:
    used = {card_id for entry in history for card_id in entry.response.action}
    protected_ranks = {card_from_id(card_id).rank for card_id in hand}
    complete_hand = list(hand)
    complete_hand.extend(
        card_id
        for card_id in range(108)
        if card_id not in used and card_id not in complete_hand and card_from_id(card_id).rank not in protected_ranks
    )
    complete_hand = complete_hand[:27]
    return HandlerContext(
        match_key="unit",
        request_digest="digest",
        request=_request(history),
        local_player_id=local,
        own_hand=tuple(complete_hand),
        history=history,
        latest_window=history[-4:],
        global_state=GlobalState("2", 0, None, None, False),
        finished=False,
    )


class BotzonePlayAdapterTests(unittest.TestCase):
    def test_done_with_missing_public_carrier_degrades_without_inventing_history(self) -> None:
        from agents.card_tracker import exact_public_hand_assignment, _validated_public_state, build_card_tracking_summary
        for local, done in ((2, 0), (1, 3)):
            with self.subTest(local=local):
                history = tuple(HistoryEntry(done, ActionClaim((i,), (i,))) for i in range(26))
                request = replace(_request(history[-4:]), done=(done,))
                context = replace(_context(tuple(range(81, 108)), local=local),
                                  request=request, history=history, latest_window=history[-4:])
                projection = project_decision(context)
                observation = dict(projection.observation)
                finished = next(p for p in observation['other_players'] if p['finished'])
                self.assertEqual(finished['hand_count'], 0)
                self.assertFalse(observation['history']['complete'])
                self.assertEqual(len(observation['history']['actions']), 26)
                self.assertIsNone(_validated_public_state(observation))
                self.assertIsNone(exact_public_hand_assignment(observation))
                self.assertIn('证据级=E0', build_card_tracking_summary(observation, list(projection.legal_actions)))
                # Missing old carriers do not change the actual latest table
                # or the canonical actions generated from the local hand.
                complete = history + (HistoryEntry(done, ActionClaim((26,), (26,))),)
                full = replace(context, history=complete, latest_window=complete[-4:],
                               request=replace(request, history=complete[-4:]))
                self.assertNotIn('complete', project_decision(full).observation['history'])
                without_done = replace(context, request=replace(request, done=()))
                self.assertEqual(projection.legal_actions, project_decision(without_done).legal_actions)
                # A fresh pass changes the window but cannot fill the missing
                # carrier or authorize a finished player to take another turn.
                shifted = history + (HistoryEntry((done + 1) % 4, ActionClaim.pass_action()),)
                shifted_context = replace(context, history=shifted, latest_window=shifted[-4:],
                                          request=replace(request, history=shifted[-4:]))
                self.assertFalse(project_decision(shifted_context).observation['history']['complete'])
                over_capacity = complete + (HistoryEntry(done, ActionClaim((27,), (27,))),)
                for bad, category in (
                    (replace(context, history=history + history[-1:], latest_window=history[-4:] + history[-1:],
                             request=replace(request, history=history[-4:] + history[-1:])), 'duplicate_public_entity'),
                    (replace(context, own_hand=context.own_hand[:-1]), 'local_hand_conservation_failed'),
                    (replace(full, request=replace(full.request, done=())), 'unfinished_zero_capacity'),
                    (replace(context, history=over_capacity, latest_window=over_capacity[-4:],
                             request=replace(request, history=over_capacity[-4:])), 'public_capacity_invalid'),
                    (replace(context, request=replace(request, done=(local,))), 'context_finished_mismatch'),
                    (replace(context, request=replace(request, done=(done, (done + 2) % 4))), 'terminal_double_down_context'),
                ):
                    with self.assertRaisesRegex(AdapterError, category):
                        project_decision(bad)

    def test_degraded_done_projection_preserves_model_choice_and_ack(self) -> None:
        history = tuple(HistoryEntry(0, ActionClaim((i,), (i,))) for i in range(26))
        request = replace(_request(history[-4:]), done=(0,))
        class Agent:
            client = SimpleNamespace(last_outcome='success')
            last_decision_source = 'model'
            pattern = 'pass'
            def select_action(self, observation, actions):
                self.selected = next(a['action_id'] for a in actions if a['declared_pattern'] == self.pattern)
                return self.selected
        agent = Agent()
        with TemporaryDirectory() as root:
            store = SessionStore(root, decision_trace_enabled=True)
            deal = DealRequest(tuple(range(81, 108)), 2, replace(request.global_state, resist=None))
            record, _ = store.prepare('unit-gap', b'deal', deal)
            store.complete_handler(store.reserve_handler(record), HandlerResult(b'[]'))
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries); store.acknowledge(deliveries)
            # Synthetic public declaration ledger; not a real rotation replay.
            record = replace(store.load('unit-gap'), stage='play', global_state=request.global_state,
                             history=history, latest_window=history[-4:])
            store.save(record)
            context = store.handler_context(record, request)
            handler = NoTributeRuleBasedHandler(lambda _: agent, agent_mode='deepseek', decision_trace_enabled=True)
            result = handler(context)
            self.assertEqual(result.decision_trace.selected_action_id, agent.selected)
            self.assertEqual(result.decision_trace.decision_source, 'model')
            store.complete_handler(store.reserve_handler(record), result)
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries); store.acknowledge(deliveries)
            self.assertEqual(store.load('unit-gap').own_hand, context.own_hand)
            self.assertIsNone(store.load('unit-gap').pending_response)
            window = (history[-1], HistoryEntry(2, ActionClaim.pass_action()),
                      HistoryEntry(3, ActionClaim.pass_action()), HistoryEntry(1, ActionClaim((27,), (27,))))
            next_request = replace(request, history=window)
            record, _ = store.prepare('unit-gap', b'next', next_request)
            agent.pattern = 'single'
            result = handler(store.handler_context(record, next_request))
            self.assertEqual(result.decision_trace.selected_action_id, agent.selected)
            self.assertEqual(result.decision_trace.decision_source, 'model')
            self.assertTrue(result.effect.action)
            store.complete_handler(store.reserve_handler(record), result)
            deliveries = store.pending_deliveries()
            store.mark_inflight(deliveries); store.acknowledge(deliveries)
            self.assertEqual(store.load('unit-gap').own_hand,
                             tuple(i for i in context.own_hand if i not in result.effect.action))

    def test_108_ids_and_teams_map_without_losing_card_faces(self) -> None:
        self.assertEqual(len(ALL_CARDS), 108)
        for source in ALL_CARDS:
            converted = botzone_id_to_engine_card(source.card_id)
            with self.subTest(card_id=source.card_id):
                self.assertEqual(converted.rank, source.rank)
                self.assertEqual(converted.suit, None if source.suit is None else source.suit.upper())
        self.assertEqual([team_for_engine_player(player) for player in (1, 2, 3, 4)], ["team_13", "team_24", "team_13", "team_24"])

    def test_free_projection_is_stable_and_binds_lowest_duplicate_identity(self) -> None:
        hand = (card_id_for("3", "h", 1), card_id_for("3", "h", 0), card_id_for("4", "d", 0))
        projection = project_decision(_context(hand))
        self.assertTrue(projection.table_view_free)
        pair = next(
            action for action_id, action in projection.provenance.items()
            if action.action_type == ActionType.PLAY
            and action.declared_pattern == PatternType.PAIR
            and all(card.rank == "3" and card.suit == "H" for card in action.carrier_cards)
        )
        encoded = encode_action_claim(pair, _context(hand).own_hand, "2")
        self.assertEqual(encoded.action, tuple(sorted(hand[:2])))
        self.assertEqual(encoded.action, encoded.claim)
        self.assertEqual([action["action_id"] for action in projection.legal_actions], list(range(1, len(projection.legal_actions) + 1)))

    def test_follow_projection_includes_pass_and_preserves_leader_constraint(self) -> None:
        leader = HistoryEntry(player_id=1, response=ActionClaim((card_id_for("3", "h"),), (card_id_for("3", "h"),)))
        projection = project_decision(_context((card_id_for("4", "d"),), (leader,)))
        self.assertFalse(projection.table_view_free)
        self.assertEqual(projection.observation["current_round"]["constraint"], "single:3")
        self.assertIn("pass", [action["declared_pattern"] for action in projection.legal_actions])

    def test_wildcard_straight_claim_avoids_accidental_straight_flush(self) -> None:
        hand = (
            card_id_for("2", "h"),
            card_id_for("3", "h"),
            card_id_for("4", "h"),
            card_id_for("5", "h"),
            card_id_for("6", "h"),
        )
        context = _context(hand)
        projection = project_decision(context)
        straight = next(
            action for action in projection.provenance.values()
            if action.declared_pattern == PatternType.STRAIGHT and action.wildcard_count == 1
        )
        encoded = encode_action_claim(straight, context.own_hand, "2")
        self.assertEqual(len(encoded.action), 5)
        self.assertNotEqual(len({botzone_id_to_engine_card(card_id).suit for card_id in encoded.claim}), 1)

    def test_double_wildcard_claims_roundtrip_and_level_rank_uses_another_suit(self) -> None:
        hand = (
            card_id_for("7", "s"), card_id_for("7", "c"), card_id_for("8", "s"),
            card_id_for("2", "h", 0), card_id_for("2", "h", 1),
        )
        context = _context(hand)
        projection = project_decision(context)
        split = next(
            action for action in projection.provenance.values()
            if action.declared_pattern == PatternType.TRIPLE_WITH_PAIR
            and action.wildcard_count == 2
            and {item.declared_as.rank for item in action.wildcard_info} == {"7", "8"}
        )
        encoded = encode_action_claim(split, context.own_hand, "2")
        self.assertEqual(len(encoded.action), 5)
        self.assertEqual(len(set(encoded.action)), 5)
        replayed = _history_entry_to_action(HistoryEntry(0, encoded), "2")
        self.assertEqual(replayed.wildcard_count, 2)
        self.assertEqual({item.declared_as.rank for item in replayed.wildcard_info}, {"7", "8"})

        level_pair = next(
            action for action in projection.provenance.values()
            if action.declared_pattern == PatternType.PAIR
            and action.wildcard_count == 1
            and all(card.rank == "2" for card in action.declared_cards)
        )
        level_claim = encode_action_claim(level_pair, context.own_hand, "2")
        self.assertIn(
            card_id_for("2", "d"),
            level_claim.claim,
        )
        self.assertNotIn(card_id_for("2", "h", 0), level_claim.claim)

    def test_natural_and_substituted_level_heart_roundtrip_without_false_wild_count(self) -> None:
        hand = (
            card_id_for("A", "h"), card_id_for("2", "h", 0), card_id_for("2", "h", 1),
            card_id_for("3", "h"), card_id_for("4", "h"),
        )
        context = _context(hand)
        projection = project_decision(context)
        action = next(
            candidate for candidate in projection.provenance.values()
            if candidate.declared_pattern == PatternType.STRAIGHT_FLUSH
            and candidate.wildcard_count == 1
            and sum(card.rank == "2" and card.suit == "H" for card in candidate.carrier_cards) == 2
            and tuple(card.rank for card in candidate.declared_cards) == ("A", "2", "3", "4", "5")
        )
        encoded = encode_action_claim(action, context.own_hand, "2")
        self.assertEqual(
            sum(card_from_id(card_id).rank == "2" and card_from_id(card_id).suit == "h" for card_id in encoded.claim),
            1,
        )
        replayed = _history_entry_to_action(HistoryEntry(0, encoded), "2")
        self.assertEqual(replayed.wildcard_count, 1)
        self.assertEqual(replayed.wildcard_info[0].carrier_card, Card("2", "H"))
        self.assertNotEqual(replayed.wildcard_info[0].declared_as, Card("2", "H"))
        self.assertEqual(
            sorted((card.rank, card.suit) for card in replayed.declared_cards),
            sorted((card_from_id(card_id).rank, card_from_id(card_id).suit.upper()) for card_id in encoded.claim),
        )

    def test_public_legal_actions_match_a_constructed_public_engine_fixture(self) -> None:
        hand = (card_id_for("3", "h", 1), card_id_for("3", "h", 0), card_id_for("4", "d", 0))
        context = _context(hand)
        projection = project_decision(context)
        game = GuanDanGame(
            current_level_rank="2",
            starting_player_id=1,
            preset_hands={
                1: tuple(botzone_id_to_engine_card(card_id) for card_id in context.own_hand),
                2: (Card("5", "S"),),
                3: (Card("6", "S"),),
                4: (Card("7", "S"),),
            },
        )
        game.reset()
        self.assertEqual([dict(action) for action in projection.legal_actions], game.legal_actions())


if __name__ == "__main__":
    unittest.main()
