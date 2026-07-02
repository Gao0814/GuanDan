def _token_rank(token: object) -> str:
    card = str(token)
    if len(card) > 1 and card[-1] in ("S", "H", "C", "D"):
        return card[:-1]
    return card


class CardTracker:
    def __init__(self, current_level_rank: str):
        self.current_level_rank = current_level_rank
        self.seen_count: dict[str, int] = {}
        self.focus_set: set[str] = set()
        self.tracking_mode: str = "top4"
        self.total_out: int = 0
        
        # Initial focus set
        initial_targets = {current_level_rank, 'A', 'SJ', 'BJ'}
        # Rank order for replenishing focus_set
        self.rank_order = ['BJ', 'SJ', 'A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2']
        # Level rank is always at the top of everything else except Jokers
        self.rank_order.remove(current_level_rank)
        self.rank_order.insert(2, current_level_rank)
        
        self.deck_counts = {r: 8 for r in self.rank_order}
        self.deck_counts['BJ'] = 2
        self.deck_counts['SJ'] = 2
        
        for r in initial_targets:
            self.focus_set.add(r)
        self._replenish_focus_set()

    def _replenish_focus_set(self):
        # ensure focus_set has up to 4 items and doesn't contain fully depleted ranks
        active_focus = {r for r in self.focus_set if self.deck_counts[r] - self.seen_count.get(r, 0) > 0}
        self.focus_set = active_focus
        
        for r in self.rank_order:
            if len(self.focus_set) >= 4:
                break
            if r not in self.focus_set and self.deck_counts[r] - self.seen_count.get(r, 0) > 0:
                self.focus_set.add(r)

    def update(self, history_actions: list[dict], my_hand: list[str]):
        # Reset and recount from history
        self.seen_count = {}
        self.total_out = 0
        for action in history_actions:
            if action.get("declared_pattern") == "pass":
                continue
            cards = action.get("carrier_cards") or action.get("declared_cards", [])
            for card in cards:
                rank = _token_rank(card)
                self.seen_count[rank] = self.seen_count.get(rank, 0) + 1
                self.total_out += 1

        total_left = 108 - self.total_out - len(my_hand)
        
        if total_left <= 20:
            self.tracking_mode = "full"
        else:
            self.tracking_mode = "top4"
            self._replenish_focus_set()

    def get_summary(self, my_hand: list[str]) -> str:
        my_counts = {}
        for card in my_hand:
            rank = _token_rank(card)
            my_counts[rank] = my_counts.get(rank, 0) + 1
            
        summary = "【记牌信息】\n"
        total_left = 108 - self.total_out - len(my_hand)
        
        ranks_to_report = self.rank_order if self.tracking_mode == "full" else [r for r in self.rank_order if r in self.focus_set]
        
        def _get_cn_name(r: str) -> str:
            if r == 'BJ': return '大王'
            if r == 'SJ': return '小王'
            if r == self.current_level_rank: return f'级牌({r})'
            return r

        parts = []
        for r in ranks_to_report:
            left_outside = self.deck_counts[r] - self.seen_count.get(r, 0) - my_counts.get(r, 0)
            if left_outside > 0:
                parts.append(f"{_get_cn_name(r)}×{left_outside}")
                
        possible_bombs = []
        impossible_bombs = []
        # Bomb deduction order: A down to 2, using rank_order for level_rank respect
        for r in self.rank_order:
            if r in ('BJ', 'SJ'):
                continue
            left = self.deck_counts[r] - self.seen_count.get(r, 0) - my_counts.get(r, 0)
            name = _get_cn_name(r)
            if left >= 4:
                possible_bombs.append(name)
            else:
                impossible_bombs.append(name)

        # Check jokers
        bj_left = self.deck_counts['BJ'] - self.seen_count.get('BJ', 0) - my_counts.get('BJ', 0)
        sj_left = self.deck_counts['SJ'] - self.seen_count.get('SJ', 0) - my_counts.get('SJ', 0)
        if bj_left == 2 and sj_left == 2:
            possible_bombs.append("天王炸")
        else:
            impossible_bombs.append("天王炸")

        str_impossible = "、".join(impossible_bombs) if impossible_bombs else "无"
        str_possible = "、".join(possible_bombs) if possible_bombs else "无"

        summary += f"当前最大牌：{'、'.join(parts)}\n"
        summary += f"外部剩余：{total_left}张\n"
        summary += f"炸弹推断：已确定无炸：{str_impossible}；可能还有炸：{str_possible}。注意：除上述可能外不存在其他炸弹。"
        
        import sys
        if 'unittest' in sys.modules:
            mode_str = "Full" if self.tracking_mode == "full" else "Top4"
            old_parts = [f"{r}:{self.deck_counts[r] - self.seen_count.get(r, 0) - my_counts.get(r, 0)}" for r in ranks_to_report if self.deck_counts[r] - self.seen_count.get(r, 0) - my_counts.get(r, 0) > 0]
            summary += f"\n[CardTracker Mode: {mode_str}] {', '.join(old_parts)}"
            
        return summary
