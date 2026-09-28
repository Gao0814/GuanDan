from __future__ import annotations

import random
import re
import unittest
from collections import Counter
from copy import deepcopy

from agents.card_tracker import CardTracker, _action_record, build_card_tracking_summary
from engine.cards import Card, build_double_deck
from engine.game import GuanDanGame


def _card(token: str) -> Card:
    if token in {"SJ", "BJ"}:
        return Card(token)
    return Card(token[:-1], token[-1])


def _game_with_pair_straight() -> GuanDanGame:
    deck = build_double_deck()
    target = [_card(token) for token in ("4S", "4H", "5S", "5H", "6S", "6H", "3S", "SJ")]
    for card in target:
        deck.remove(card)
    filler = []
    for card in tuple(deck):
        if card.rank in {"8", "10", "Q", "A", "2"} and not (card.rank == "2" and card.suit == "H"):
            filler.append(card)
            deck.remove(card)
            if len(filler) == 19:
                break
    own = target + filler
    remaining = deck
    hands = {
        1: tuple(own),
        2: tuple(remaining[:27]),
        3: tuple(remaining[27:54]),
        4: tuple(remaining[54:81]),
    }
    return GuanDanGame(preset_hands=hands, current_level_rank="2", starting_player_id=1)


def _game_with_all_jokers() -> GuanDanGame:
    deck = build_double_deck()
    jokers = [card for card in deck if card.rank in {"SJ", "BJ"}]
    fillers = [card for card in deck if card.rank not in {"SJ", "BJ"}][:23]
    own = jokers + fillers
    for card in own:
        deck.remove(card)
    return GuanDanGame(
        preset_hands={
            1: tuple(own), 2: tuple(deck[:27]),
            3: tuple(deck[27:54]), 4: tuple(deck[54:81]),
        },
        current_level_rank="2",
        starting_player_id=1,
    )


def _action(actions: list[dict[str, object]], predicate):
    return next(action for action in actions if predicate(action))


def _greedy_state(stop_finish_count: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    game = GuanDanGame(seed=0, current_level_rank="2")
    game.reset()
    for _ in range(300):
        observation = game.observe()
        actions = game.legal_actions()
        finished = observation["history"]["finish_order"]
        if len(finished) == stop_finish_count:
            hand_count = observation["my_info"]["hand_count"]
            playable = [
                action for action in actions
                if action["declared_pattern"] != "pass"
                and len(action["carrier_cards"]) < hand_count
            ]
            if playable:
                return observation, actions
            passes = [action for action in actions if action["declared_pattern"] == "pass"]
            if passes:
                game.step(passes[0]["action_id"])
                continue
            break

        hand_count = observation["my_info"]["hand_count"]
        playable = [action for action in actions if action["declared_pattern"] != "pass"]
        if playable:
            selected = max(
                playable,
                key=lambda action: (
                    len(action["carrier_cards"]),
                    action["declared_pattern"] in {"bomb", "straight_flush", "joker_bomb"},
                    -action["action_id"],
                ),
            )
        else:
            selected = _action(actions, lambda action: action["declared_pattern"] == "pass")
        game.step(selected["action_id"])
    raise AssertionError("fixed legal rollout did not reach the requested finish count")


def _urgent_multiplayer_pair_straight_state() -> tuple[dict[str, object], list[dict[str, object]]]:
    deck = build_double_deck()
    target = [_card(token) for token in ("4S", "4H", "5S", "5H", "6S", "6H", "3S", "SJ")]
    for card in target:
        deck.remove(card)
    random.Random(16).shuffle(deck)
    own = target + deck[: 27 - len(target)]
    remaining = deck[27 - len(target) :]
    game = GuanDanGame(
        preset_hands={
            1: tuple(own), 2: tuple(remaining[:27]),
            3: tuple(remaining[27:54]), 4: tuple(remaining[54:81]),
        },
        current_level_rank="2",
        starting_player_id=1,
    )
    game.reset()
    protected = {"4S", "4H", "5S", "5H", "6S", "6H"}
    for _ in range(180):
        observation = game.observe()
        actions = game.legal_actions()
        if not actions:
            break
        player_id = observation["my_info"]["player_id"]
        table_action = observation["current_round"]["table_action"]
        active_other_counts = [
            player["hand_count"] for player in observation["other_players"]
            if not player["finished"]
        ]
        patterns = {action["declared_pattern"] for action in actions}
        if (
            player_id == 1 and table_action is None
            and len(observation["history"]["finish_order"]) <= 1
            and min(active_other_counts, default=99) <= 1
            and {"pair_straight", "single"}.issubset(patterns)
        ):
            return observation, actions

        if player_id == 1 and table_action is not None:
            selected = next((action for action in actions if action["declared_pattern"] == "pass"), None)
            if selected is None:
                selected = max(actions, key=lambda action: len(action["carrier_cards"]))
        elif player_id == 1:
            choices = [
                action for action in actions
                if action["declared_pattern"] != "pass"
                and not (set(action["carrier_cards"]) & protected)
            ]
            selected = max(choices or actions, key=lambda action: (len(action["carrier_cards"]), -action["action_id"]))
        else:
            choices = [action for action in actions if action["declared_pattern"] != "pass"]
            selected = max(choices, key=lambda action: (len(action["carrier_cards"]), -action["action_id"])) if choices else next(
                action for action in actions if action["declared_pattern"] == "pass"
            )
        game.step(selected["action_id"])
    raise AssertionError("fixed legal rollout did not reach the urgent multiplayer comparison")


class TestCardTracker(unittest.TestCase):
    def test_candidate_size_validation_matches_legal_joker_bomb_and_pair_straight(self) -> None:
        joker_game = _game_with_all_jokers()
        joker_observation = joker_game.reset()
        joker_hand = Counter(joker_observation["my_info"]["hand_cards"])
        joker_action = _action(
            joker_game.legal_actions(), lambda item: item["declared_pattern"] == "joker_bomb"
        )
        self.assertEqual(len(joker_action["carrier_cards"]), 4)
        self.assertIsNotNone(_action_record(joker_action, joker_hand))
        forged_joker = dict(joker_action)
        forged_joker["carrier_cards"] = joker_action["carrier_cards"][:2]
        forged_joker["declared_cards"] = joker_action["declared_cards"][:2]
        self.assertIsNone(_action_record(forged_joker, joker_hand))

        pair_game = _game_with_pair_straight()
        pair_observation = pair_game.reset()
        pair_hand = Counter(pair_observation["my_info"]["hand_cards"])
        pair_action = _action(
            pair_game.legal_actions(), lambda item: item["declared_pattern"] == "pair_straight"
        )
        self.assertEqual(len(pair_action["carrier_cards"]), 6)
        self.assertIsNotNone(_action_record(pair_action, pair_hand))
        remaining_cards = list(pair_observation["my_info"]["hand_cards"])
        for carrier in pair_action["carrier_cards"]:
            remaining_cards.remove(carrier)
        extra_cards = remaining_cards[:2]
        forged_pair = dict(pair_action)
        forged_pair["carrier_cards"] = list(pair_action["carrier_cards"]) + extra_cards
        forged_pair["declared_cards"] = list(pair_action["declared_cards"]) + [
            card[:-1] for card in extra_cards
        ]
        self.assertIsNone(_action_record(forged_pair, pair_hand))

    def test_legal_four_joker_bomb_history_keeps_exact_public_pool(self) -> None:
        game = _game_with_all_jokers()
        game.reset()
        action = _action(game.legal_actions(), lambda item: item["declared_pattern"] == "joker_bomb")
        self.assertEqual(len(action["carrier_cards"]), 4)
        game.step(action["action_id"])

        observation = game.observe()
        legal_actions = game.legal_actions()
        summary = build_card_tracking_summary(observation, legal_actions)

        self.assertEqual(observation["my_info"]["player_id"], 2)
        self.assertIn("证据级=E1精确牌池/多人未分配", summary)
        self.assertIn("已出4、本家持有27、外部未见77", summary)

    def test_forged_two_card_joker_bomb_and_eight_card_pair_straight_fail_closed(self) -> None:
        joker_game = _game_with_all_jokers()
        joker_game.reset()
        joker_action = _action(
            joker_game.legal_actions(), lambda item: item["declared_pattern"] == "joker_bomb"
        )
        joker_game.step(joker_action["action_id"])
        forged_joker = deepcopy(joker_game.observe())
        forged_joker_action = forged_joker["history"]["actions"][-1]
        forged_joker_action["carrier_cards"] = ["SJ", "BJ"]
        forged_joker_action["declared_cards"] = ["SJ", "BJ"]
        player_one = next(player for player in forged_joker["other_players"] if player["player_id"] == 1)
        player_one["hand_count"] = 25
        joker_summary = build_card_tracking_summary(forged_joker, joker_game.legal_actions())
        self.assertIn("证据级=E0", joker_summary)
        self.assertNotIn("M3候选对照", joker_summary)

        pair_game = _game_with_pair_straight()
        pair_initial = pair_game.reset()
        pair_action = _action(
            pair_game.legal_actions(), lambda item: item["declared_pattern"] == "pair_straight"
        )
        remaining_cards = list(pair_initial["my_info"]["hand_cards"])
        for carrier in pair_action["carrier_cards"]:
            remaining_cards.remove(carrier)
        pair_game.step(pair_action["action_id"])
        forged_pair = deepcopy(pair_game.observe())
        forged_pair_action = forged_pair["history"]["actions"][-1]
        extra_cards = remaining_cards[:2]
        forged_carriers = list(forged_pair_action["carrier_cards"]) + extra_cards
        forged_pair_action["carrier_cards"] = forged_carriers
        forged_pair_action["declared_cards"] = list(forged_pair_action["declared_cards"]) + [
            card[:-1] for card in extra_cards
        ]
        player_one = next(player for player in forged_pair["other_players"] if player["player_id"] == 1)
        player_one["hand_count"] -= 2
        pair_summary = build_card_tracking_summary(forged_pair, pair_game.legal_actions())
        self.assertIn("证据级=E0", pair_summary)
        self.assertNotIn("M3候选对照", pair_summary)

    def test_exact_public_pool_compares_only_displayed_candidates_and_corrects_bomb_scope(self) -> None:
        game = _game_with_pair_straight()
        observation = game.reset()
        legal_actions = game.legal_actions()
        tracker = CardTracker("2")
        tracker.update(
            list(observation["history"]["actions"]),
            list(observation["my_info"]["hand_cards"]),
            observation=observation,
            legal_actions=legal_actions,
        )
        summary = tracker.get_summary(list(observation["my_info"]["hand_cards"]))

        self.assertIn("证据级=E1精确牌池/多人未分配", summary)
        self.assertIn("已出0、本家持有27、外部未见81", summary)
        self.assertIn("对手余54张可能持有", summary)
        self.assertIn("队友余27张可能持有", summary)
        self.assertIn("可能持牌人=玩家2(对手,余27张)", summary)
        self.assertIn("玩家3(队友,余27张)", summary)
        self.assertIn("当前无公开1–2张对手", summary)
        self.assertIn("自然连对出后仍保留高点候选且余组更轻", summary)
        self.assertIn("小单保组路线仍须比较", summary)
        self.assertNotIn("已确认持有人", summary)
        self.assertIn("同花顺是独立炸弹类别", summary)
        self.assertNotIn("当前最大牌", summary)
        self.assertNotIn("不存在其他炸弹", summary)
        self.assertNotIn("概率", summary)
        self.assertLessEqual(len(summary), 1_350)

        ids = {action["action_id"] for action in legal_actions}
        comparisons = [line for line in summary.splitlines() if line.startswith("M3候选对照")]
        self.assertTrue(any("pair_straight" in line and "single" in line for line in comparisons))
        self.assertLessEqual(len(comparisons), 2)
        pair_line = next(line for line in comparisons if "pair_straight" in line)
        self.assertIn("出后资源=余21张/同点结构(孤张2/对子0/三张1/四张以上4)", pair_line)
        self.assertIn("另一候选出后=余26张/同点结构(孤张1/对子3/三张1/四张以上4)", pair_line)
        for line in comparisons:
            self.assertTrue(all(int(value) in ids for value in re.findall(r"action_id=(\d+)", line)))
            self.assertIn("同点结构", line)
            self.assertIn("保留高点候选", line)
            if "single" in line:
                self.assertIn("较高点数候选=", line)
            if "pair_straight" in line:
                self.assertIn("不把牌数优势当作固定指令", line)
            else:
                self.assertIn("不固定偏向任一路线", line)

    def test_midgame_public_play_and_capacity_change_control_comparison(self) -> None:
        game = _game_with_pair_straight()
        observation = game.reset()
        actions = game.legal_actions()
        lead = _action(
            actions,
            lambda item: item["declared_pattern"] == "single" and item["carrier_cards"] == ["3S"],
        )
        game.step(lead["action_id"])

        actions = game.legal_actions()
        response = min(
            (
                item for item in actions
                if item["declared_pattern"] == "single"
                and item["declared_cards"][0] != "3"
            ),
            key=lambda item: item["action_id"],
        )
        game.step(response["action_id"])
        for _ in (3, 4):
            actions = game.legal_actions()
            game.step(_action(actions, lambda item: item["declared_pattern"] == "pass")["action_id"])

        # The original leader declines the response; the other player then
        # receives a free lead while the high card is now public history.
        actions = game.legal_actions()
        game.step(_action(actions, lambda item: item["declared_pattern"] == "pass")["action_id"])

        observation = game.observe()
        actions = game.legal_actions()
        self.assertEqual(observation["my_info"]["player_id"], 2)
        self.assertIsNone(observation["current_round"]["table_action"])
        summary = build_card_tracking_summary(observation, actions)

        self.assertIn("证据级=E1精确牌池/多人未分配", summary)
        self.assertIn("外部未见80", summary)
        self.assertIn("外部仍见更高单张牌池=", summary)
        self.assertIn("归属未知", summary)
        self.assertIn("队友余27张可能持有", summary)
        self.assertNotIn("已确认持有人", summary)
        self.assertIn("M3候选对照", summary)

    def test_missing_carrier_and_capacity_mismatch_fail_closed(self) -> None:
        game = _game_with_pair_straight()
        observation = game.reset()
        actions = game.legal_actions()

        missing_carrier = dict(observation)
        missing_carrier["history"] = {
            "actions": [{"player_id": 2, "declared_pattern": "single", "declared_cards": ["A"]}],
            "finish_order": [],
        }
        summary = build_card_tracking_summary(missing_carrier, actions)
        self.assertIn("证据级=E0", summary)
        self.assertNotIn("M3候选对照", summary)
        self.assertNotIn("高于", summary)

        unknown_pattern = dict(observation)
        unknown_pattern["history"] = {
            "actions": [{"player_id": 2, "declared_pattern": "unknown", "carrier_cards": []}],
            "finish_order": [],
        }
        summary = build_card_tracking_summary(unknown_pattern, actions)
        self.assertIn("证据级=E0", summary)

        capacity_mismatch = dict(observation)
        capacity_mismatch["other_players"] = [dict(player) for player in observation["other_players"]]
        capacity_mismatch["other_players"][0]["hand_count"] = 26
        summary = build_card_tracking_summary(capacity_mismatch, actions)
        self.assertIn("证据级=E0", summary)
        self.assertNotIn("唯一归属", summary)

    def test_unique_external_hand_uses_engine_query_for_immediate_takeover(self) -> None:
        observation, legal_actions = _greedy_state(2)
        summary = build_card_tracking_summary(observation, legal_actions)

        self.assertIn("证据级=E2唯一归属", summary)
        self.assertIn("已确认持有人=对手玩家", summary)
        self.assertIn("M3唯一归属核验 action_id=", summary)
        self.assertIn("可立即压过牌型=", summary)
        self.assertIn("已知高点资源", summary)
        self.assertIn("不推出胜负或后续牌权", summary)
        ids = {action["action_id"] for action in legal_actions}
        line = next(line for line in summary.splitlines() if line.startswith("M3唯一归属核验"))
        self.assertTrue(all(int(value) in ids for value in re.findall(r"action_id=(\d+)", line)))

    def test_multiplayer_endgame_keeps_owner_unknown(self) -> None:
        observation, legal_actions = _greedy_state(1)
        summary = build_card_tracking_summary(observation, legal_actions)

        self.assertIn("证据级=E1精确牌池/多人未分配", summary)
        self.assertIn("归属未确认", summary)
        self.assertNotIn("已确认持有人", summary)
        self.assertNotIn("唯一归属核验", summary)
        self.assertNotIn("必胜", summary)

    def test_urgent_opponent_comparison_surfaces_high_single_alongside_pair_straight(self) -> None:
        observation, legal_actions = _urgent_multiplayer_pair_straight_state()
        summary = build_card_tracking_summary(observation, legal_actions)

        self.assertIn("证据级=E1精确牌池/多人未分配", summary)
        self.assertIn("对手余3张可能持有", summary)
        self.assertIn("公开紧迫对手最少余=1张", summary)
        self.assertIn("M3候选对照", summary)
        self.assertIn("当前有公开紧迫对手", summary)
        self.assertIn("实际高单候选的即时拦截价值", summary)
        self.assertRegex(summary, r"pair_straight 4 4 5 5 6 6")
        self.assertRegex(summary, r"vs action_id=\d+\(single BJ\)")
        self.assertTrue(
            any(
                "pair_straight" in line and "single BJ" in line
                for line in summary.splitlines()
                if line.startswith("M3候选对照")
            )
        )

    def test_legacy_tracker_without_complete_observation_does_not_claim_card_facts(self) -> None:
        tracker = CardTracker("2")
        tracker.update([{"declared_pattern": "single", "declared_cards": ["BJ"]}], ["3S"])
        summary = tracker.get_summary(["3S"])
        self.assertIn("证据级=E0", summary)
        self.assertNotIn("BJ×", summary)


if __name__ == "__main__":
    unittest.main()
