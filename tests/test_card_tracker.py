import unittest
from agents.card_tracker import CardTracker

class TestCardTracker(unittest.TestCase):
    def test_tracker_initialization(self):
        tracker = CardTracker("2")
        self.assertEqual(tracker.current_level_rank, "2")
        self.assertEqual(tracker.tracking_mode, "top4")
        self.assertEqual(tracker.focus_set, {"BJ", "SJ", "A", "2"})
    
    def test_tracker_counts_and_replenishes(self):
        tracker = CardTracker("10")
        self.assertEqual(tracker.focus_set, {"BJ", "SJ", "A", "10"})
        # 10 is the level rank, so focus_set initially has 4.
        
        my_hand = ["2H", "3D", "BJ"]
        history = [
            {
                "declared_pattern": "single",
                "declared_cards": ["10H"]
            },
            {
                "declared_pattern": "pair",
                "declared_cards": ["AS", "AH"]
            }
        ]
        
        tracker.update(history, my_hand)
        summary = tracker.get_summary(my_hand)
        
        self.assertEqual(tracker.seen_count["10"], 1)
        self.assertEqual(tracker.seen_count["A"], 2)
        self.assertIn("BJ:1", summary)
        self.assertIn("SJ:2", summary)
        self.assertIn("10:7", summary)
        self.assertIn("A:6", summary)

    def test_tracker_prefers_carrier_cards_for_wildcard_history(self):
        tracker = CardTracker("2")
        history = [
            {
                "declared_pattern": "straight",
                "declared_cards": ["7", "8", "9", "10", "J"],
                "carrier_cards": ["7S", "8S", "9S", "10S", "2H"],
                "wildcard_count": 1,
                "wildcard_info": [{"carrier_card": "2H", "declared_as": "J"}],
            }
        ]

        tracker.update(history, [])

        self.assertEqual(tracker.seen_count["2"], 1)
        self.assertEqual(tracker.seen_count["7"], 1)
        self.assertEqual(tracker.seen_count["8"], 1)
        self.assertEqual(tracker.seen_count["9"], 1)
        self.assertEqual(tracker.seen_count["10"], 1)
        self.assertEqual(tracker.seen_count.get("J", 0), 0)
        self.assertEqual(tracker.total_out, 5)

    def test_tracker_falls_back_to_declared_cards_for_legacy_history(self):
        tracker = CardTracker("2")
        history = [
            {
                "declared_pattern": "pair",
                "declared_cards": ["AS", "AH"],
            }
        ]

        tracker.update(history, [])

        self.assertEqual(tracker.seen_count["A"], 2)
        self.assertEqual(tracker.total_out, 2)

    def test_tracker_mode_switch(self):
        tracker = CardTracker("5")
        
        # force total_left <= 20
        # total_left = 108 - total_out - len(my_hand)
        # we will set 88 cards out, so 108 - 88 - 0 = 20
        history_actions = []
        for _ in range(22):
            history_actions.append({
                "declared_pattern": "bomb",
                "declared_cards": ["2S", "2H", "2C", "2D"] 
            })
            
        tracker.update(history_actions, [])
        self.assertEqual(tracker.tracking_mode, "full")
        self.assertIn("Full", tracker.get_summary([]))

if __name__ == "__main__":
    unittest.main()
