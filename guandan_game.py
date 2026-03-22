"""
掼蛋游戏 - 多智能体博弈项目
"""
from enum import Enum
from typing import List, Optional, Tuple
from collections import Counter
import random



class Suit(Enum):
    """花色枚举"""
    SPADE = "♠"    # 黑桃
    HEART = "♥"    # 红桃
    CLUB = "♣"     # 梅花
    DIAMOND = "♦"  # 方块
    JOKER = "JOKER"  # 大小王

class Card:
    """扑克牌类"""

    # 点数映射（3-10, J, Q, K, A, 2, 小王, 大王）
    RANK_VALUES = {
        '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
        'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15,
        'small_joker': 16, 'big_joker': 17
    }

    def __init__(self, rank: str, suit: Optional[Suit] = None):
        """
        初始化一张牌
        :param rank: 点数 ('3'-'10', 'J', 'Q', 'K', 'A', '2', 'small_joker', 'big_joker')
        :param suit: 花色 (Suit枚举，王牌为None)
        """
        self.rank = rank
        self.suit = suit
        self.value = self.RANK_VALUES[rank]

    def __repr__(self):
        if self.rank in ['small_joker', 'big_joker']:
            return f"{self.rank}"
        return f"{self.suit.value}{self.rank}"

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))
class Player:
    """玩家类"""
    def __init__(self, player_id: int, name: str):
        """
        初始化玩家
        :param player_id: 玩家ID
        :param name: 玩家名称
        """
        self.player_id = player_id
        self.name = name
        self.hand: List[Card] = []  # 手牌

    def receive_cards(self, cards: List[Card]):
        """接收发到的牌"""
        self.hand.extend(cards)
        self.sort_hand()

    def sort_hand(self):
        """整理手牌（按点数排序）"""
        self.hand.sort(key=lambda card: card.value)

    def __repr__(self):
        return f"Player({self.name}, {len(self.hand)} cards)"

class GameState:
    """游戏状态类"""

    def __init__(self, num_players: int = 4):
        """
        初始化游戏状态
        :param num_players: 玩家数量（默认4人）
        """
        self.num_players = num_players
        self.players: List[Player] = []
        self.deck: List[Card] = []
        self.current_player_idx = 0

    def add_player(self, player: Player):
        """添加玩家"""
        if len(self.players) < self.num_players:
            self.players.append(player)

    def initialize_deck(self):
        """初始化牌堆（两副牌，共108张）"""
        self.deck = create_deck()
        random.shuffle(self.deck)

    def deal_cards(self):
        """发牌给所有玩家"""
        if not self.deck:
            self.initialize_deck()

        cards_per_player = len(self.deck) // self.num_players

        for i, player in enumerate(self.players):
            start_idx = i * cards_per_player
            end_idx = start_idx + cards_per_player
            player.receive_cards(self.deck[start_idx:end_idx])

    def __repr__(self):
        return f"GameState({self.num_players} players, {len(self.deck)} cards in deck)"


# ==================== 牌堆生成函数 ====================

def create_deck() -> List[Card]:
    """
    创建两副牌（共108张）
    每副牌包含：52张普通牌 + 2张王牌 = 54张
    两副牌共：108张
    """
    deck = []
    ranks = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
    suits = [Suit.SPADE, Suit.HEART, Suit.CLUB, Suit.DIAMOND]

    # 创建两副牌
    for _ in range(2):
        # 添加普通牌（每种花色13张）
        for suit in suits:
            for rank in ranks:
                deck.append(Card(rank, suit))

        # 添加大小王
        deck.append(Card('small_joker', None))
        deck.append(Card('big_joker', None))

    return deck


# ==================== 牌型检测函数 ====================

def detect_single(cards: List[Card]) -> bool:
    """检测是否为单张"""
    return len(cards) == 1


def detect_pair(cards: List[Card]) -> bool:
    """检测是否为对子（两张相同点数）"""
    if len(cards) != 2:
        return False
    return cards[0].rank == cards[1].rank


def detect_triple(cards: List[Card]) -> bool:
    """检测是否为三张（三张相同点数）"""
    if len(cards) != 3:
        return False
    return cards[0].rank == cards[1].rank == cards[2].rank


def detect_bomb(cards: List[Card]) -> Tuple[bool, int]:
    """
    检测是否为炸弹（4张以上相同点数）
    :param cards: 要检测的牌
    :return: (是否为炸弹, 炸弹张数)
    """
    if len(cards) < 4:
        return False, 0

    # 统计每个点数的数量
    rank_counter = Counter([card.rank for card in cards])

    # 检查是否所有牌都是同一点数
    if len(rank_counter) == 1:
        count = rank_counter.most_common(1)[0][1]
        if count >= 4:
            return True, count

    return False, 0


def detect_three_with_two(cards: List[Card]) -> bool:
    """
    检测是否为三带二（3张相同点数 + 2张相同点数）
    :param cards: 要检测的牌
    :return: 是否为三带二
    """
    if len(cards) != 5:
        return False

    rank_counter = Counter([card.rank for card in cards])
    counts = sorted(rank_counter.values())

    # 必须是2张和3张的组合
    return counts == [2, 3]


def detect_consecutive_pairs(cards: List[Card]) -> Tuple[bool, int]:
    """
    检测是否为三连对（3对以上连续的对子）
    :param cards: 要检测的牌
    :return: (是否为三连对, 对子数量)
    """
    if len(cards) < 6 or len(cards) % 2 != 0:
        return False, 0

    rank_counter = Counter([card.rank for card in cards])

    # 检查是否所有点数都是2张
    if not all(count == 2 for count in rank_counter.values()):
        return False, 0

    # 获取所有点数并排序
    ranks = sorted([Card.RANK_VALUES[rank] for rank in rank_counter.keys()])

    # 检查是否连续
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] != 1:
            return False, 0

    return True, len(ranks)


def detect_steel_plate(cards: List[Card]) -> Tuple[bool, int]:
    """
    检测是否为钢板/飞机（2组以上连续的三张）
    :param cards: 要检测的牌
    :return: (是否为钢板, 三张组数)
    """
    if len(cards) < 6 or len(cards) % 3 != 0:
        return False, 0

    rank_counter = Counter([card.rank for card in cards])

    # 检查是否所有点数都是3张
    if not all(count == 3 for count in rank_counter.values()):
        return False, 0

    # 获取所有点数并排序
    ranks = sorted([Card.RANK_VALUES[rank] for rank in rank_counter.keys()])

    # 检查是否连续
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] != 1:
            return False, 0

    return True, len(ranks)


def detect_straight(cards: List[Card]) -> Tuple[bool, int]:
    """
    检测是否为顺子（5张以上连续的单张）
    :param cards: 要检测的牌
    :return: (是否为顺子, 顺子长度)
    """
    if len(cards) < 5:
        return False, 0

    # 获取所有点数值并排序
    values = sorted([card.value for card in cards])

    # 检查是否有重复
    if len(values) != len(set(values)):
        return False, 0

    # 检查是否连续
    for i in range(len(values) - 1):
        if values[i + 1] - values[i] != 1:
            return False, 0

    return True, len(values)


def detect_straight_flush(cards: List[Card]) -> Tuple[bool, int]:
    """
    检测是否为同花顺（5张以上同花色的连续牌）
    :param cards: 要检测的牌
    :return: (是否为同花顺, 顺子长度)
    """
    if len(cards) < 5:
        return False, 0

    # 检查是否所有牌都是同一花色
    suits = [card.suit for card in cards if card.suit is not None]
    if len(suits) != len(cards) or len(set(suits)) != 1:
        return False, 0

    # 检查是否为顺子
    return detect_straight(cards)


def detect_joker_bomb(cards: List[Card]) -> bool:
    """
    检测是否为王炸（大王+小王）
    :param cards: 要检测的牌
    :return: 是否为王炸
    """
    if len(cards) != 2:
        return False

    ranks = sorted([card.rank for card in cards])
    return ranks == ['big_joker', 'small_joker']


# ==================== 出牌组合生成 ====================

def generate_all_combinations(hand: List[Card]) -> List[List[Card]]:
    """
    生成首家出牌的所有可能组合
    :param hand: 手牌
    :return: 所有可能的出牌组合列表
    """
    combinations = []

    # 1. 单张
    for card in hand:
        combinations.append([card])

    # 2. 对子
    rank_groups = {}
    for card in hand:
        if card.rank not in rank_groups:
            rank_groups[card.rank] = []
        rank_groups[card.rank].append(card)

    for rank, cards in rank_groups.items():
        if len(cards) >= 2:
            combinations.append(cards[:2])

    # 3. 三张
    for rank, cards in rank_groups.items():
        if len(cards) >= 3:
            combinations.append(cards[:3])

    # 4. 炸弹（4张以上）
    for rank, cards in rank_groups.items():
        if len(cards) >= 4:
            for i in range(4, len(cards) + 1):
                combinations.append(cards[:i])

    # 5. 三带二（简化版，只检测基本组合）
    for rank1, cards1 in rank_groups.items():
        if len(cards1) >= 3:
            for rank2, cards2 in rank_groups.items():
                if rank1 != rank2 and len(cards2) >= 2:
                    combinations.append(cards1[:3] + cards2[:2])

    # 6. 王炸
    jokers = [card for card in hand if card.rank in ['small_joker', 'big_joker']]
    if len(jokers) == 2:
        combinations.append(jokers)

    return combinations


# ==================== 跟牌检测 ====================

def can_beat(current_cards: List[Card], previous_cards: List[Card]) -> bool:
    """
    检测当前出牌是否能管上上家的牌
    :param current_cards: 当前要出的牌
    :param previous_cards: 上家出的牌
    :return: 是否能管上
    """
    # 王炸可以管任何牌
    if detect_joker_bomb(current_cards):
        return True

    # 炸弹可以管非炸弹的牌
    is_current_bomb, current_bomb_count = detect_bomb(current_cards)
    is_prev_bomb, prev_bomb_count = detect_bomb(previous_cards)

    if is_current_bomb:
        if not is_prev_bomb:
            return True
        # 炸弹管炸弹：张数多的管张数少的，张数相同比点数
        if current_bomb_count > prev_bomb_count:
            return True
        elif current_bomb_count == prev_bomb_count:
            return current_cards[0].value > previous_cards[0].value
        return False

    # 如果上家是炸弹或王炸，只能用更大的炸弹或王炸管
    if is_prev_bomb or detect_joker_bomb(previous_cards):
        return False

    # 牌型必须相同
    if len(current_cards) != len(previous_cards):
        return False

    # 单张
    if detect_single(current_cards) and detect_single(previous_cards):
        return current_cards[0].value > previous_cards[0].value

    # 对子
    if detect_pair(current_cards) and detect_pair(previous_cards):
        return current_cards[0].value > previous_cards[0].value

    # 三张
    if detect_triple(current_cards) and detect_triple(previous_cards):
        return current_cards[0].value > previous_cards[0].value

    # 三带二
    if detect_three_with_two(current_cards) and detect_three_with_two(previous_cards):
        current_rank_counter = Counter([card.rank for card in current_cards])
        prev_rank_counter = Counter([card.rank for card in previous_cards])
        current_three_rank = [rank for rank, count in current_rank_counter.items() if count == 3][0]
        prev_three_rank = [rank for rank, count in prev_rank_counter.items() if count == 3][0]
        return Card.RANK_VALUES[current_three_rank] > Card.RANK_VALUES[prev_three_rank]

    # 顺子
    is_current_straight, current_len = detect_straight(current_cards)
    is_prev_straight, prev_len = detect_straight(previous_cards)
    if is_current_straight and is_prev_straight and current_len == prev_len:
        return max(card.value for card in current_cards) > max(card.value for card in previous_cards)

    # 同花顺
    is_current_sf, current_sf_len = detect_straight_flush(current_cards)
    is_prev_sf, prev_sf_len = detect_straight_flush(previous_cards)
    if is_current_sf and is_prev_sf and current_sf_len == prev_sf_len:
        return max(card.value for card in current_cards) > max(card.value for card in previous_cards)

    # 三连对
    is_current_cp, current_cp_count = detect_consecutive_pairs(current_cards)
    is_prev_cp, prev_cp_count = detect_consecutive_pairs(previous_cards)
    if is_current_cp and is_prev_cp and current_cp_count == prev_cp_count:
        return max(card.value for card in current_cards) > max(card.value for card in previous_cards)

    # 钢板
    is_current_sp, current_sp_count = detect_steel_plate(current_cards)
    is_prev_sp, prev_sp_count = detect_steel_plate(previous_cards)
    if is_current_sp and is_prev_sp and current_sp_count == prev_sp_count:
        return max(card.value for card in current_cards) > max(card.value for card in previous_cards)

    return False


# ==================== 过牌逻辑 ====================

class PlayAction:
    """出牌动作类"""

    def __init__(self, player: Player, cards: Optional[List[Card]] = None, is_pass: bool = False):
        self.player = player
        self.cards = cards if cards else []
        self.is_pass = is_pass

    def __repr__(self):
        if self.is_pass:
            return f"{self.player.name}: 过牌"
        return f"{self.player.name}: {self.cards}"


def player_pass(player: Player) -> PlayAction:
    """玩家过牌"""
    return PlayAction(player, None, is_pass=True)


def player_play(player: Player, cards: List[Card], previous_action: Optional[PlayAction] = None) -> Optional[PlayAction]:
    """玩家出牌"""
    if previous_action is None or previous_action.is_pass:
        return PlayAction(player, cards, is_pass=False)
    if can_beat(cards, previous_action.cards):
        for card in cards:
            if card in player.hand:
                player.hand.remove(card)
        return PlayAction(player, cards, is_pass=False)
    return None


# ==================== 测试/演示代码 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("掼蛋游戏 - 测试演示")
    print("=" * 50)

    # 1. 创建牌堆
    print("\n1. 创建牌堆（两副牌，共108张）")
    deck = create_deck()
    print(f"牌堆总数: {len(deck)} 张")
    print(f"前10张牌: {deck[:10]}")

    # 2. 创建游戏和玩家
    print("\n2. 创建游戏和玩家")
    game = GameState(num_players=4)
    for i in range(4):
        player = Player(i, f"玩家{i+1}")
        game.add_player(player)
    print(f"游戏状态: {game}")

    # 3. 发牌
    print("\n3. 发牌")
    game.initialize_deck()
    game.deal_cards()
    for player in game.players:
        print(f"{player.name}: {len(player.hand)} 张牌")
        print(f"  手牌: {player.hand}")

    # 4. 测试牌型检测
    print("\n4. 测试牌型检测")

    for player in game.players:
        print(f"\n{player.name}的手牌分析:")

        # 统计点数
        rank_counter = Counter([card.rank for card in player.hand])

        # 检测对子
        pairs = [rank for rank, count in rank_counter.items() if count >= 2]
        if pairs:
            print(f"  对子: {pairs}")

        # 检测三张
        triples = [rank for rank, count in rank_counter.items() if count >= 3]
        if triples:
            print(f"  三张: {triples}")

        # 检测炸弹
        bombs = [rank for rank, count in rank_counter.items() if count >= 4]
        if bombs:
            print(f"  炸弹: {bombs} (张数: {[rank_counter[rank] for rank in bombs]})")

        # 检测王牌
        jokers = [card for card in player.hand if card.rank in ['small_joker', 'big_joker']]
        if len(jokers) == 2:
            print(f"  王炸: 有")
        elif jokers:
            print(f"  王牌: {[card.rank for card in jokers]}")

        # 检测三带二
        for rank1, count1 in rank_counter.items():
            if count1 >= 3:
                for rank2, count2 in rank_counter.items():
                    if rank1 != rank2 and count2 >= 2:
                        print(f"  三带二: {rank1}(3张) + {rank2}(2张)")
                        break
                break

        # 检测顺子（5张以上连续）
        sorted_values = sorted(set([card.value for card in player.hand]))
        for i in range(len(sorted_values) - 4):
            if all(sorted_values[i+j+1] - sorted_values[i+j] == 1 for j in range(4)):
                straight_len = 5
                while i + straight_len < len(sorted_values) and sorted_values[i+straight_len] - sorted_values[i+straight_len-1] == 1:
                    straight_len += 1
                print(f"  顺子: 长度{straight_len}")
                break

        # 检测三连对
        pair_ranks = sorted([Card.RANK_VALUES[rank] for rank, count in rank_counter.items() if count >= 2])
        for i in range(len(pair_ranks) - 2):
            if pair_ranks[i+1] == pair_ranks[i] + 1 and pair_ranks[i+2] == pair_ranks[i] + 2:
                consecutive_count = 3
                while i + consecutive_count < len(pair_ranks) and pair_ranks[i+consecutive_count] == pair_ranks[i+consecutive_count-1] + 1:
                    consecutive_count += 1
                print(f"  三连对: {consecutive_count}对")
                break

        # 检测钢板
        triple_ranks = sorted([Card.RANK_VALUES[rank] for rank, count in rank_counter.items() if count >= 3])
        for i in range(len(triple_ranks) - 1):
            if triple_ranks[i+1] == triple_ranks[i] + 1:
                steel_count = 2
                while i + steel_count < len(triple_ranks) and triple_ranks[i+steel_count] == triple_ranks[i+steel_count-1] + 1:
                    steel_count += 1
                print(f"  钢板: {steel_count}组")
                break

   
    # 5. 测试跟牌检测
    print("\n5. 测试跟牌检测")
    card_a = [Card('A', Suit.SPADE)]
    card_k = [Card('K', Suit.HEART)]
    print(f"  A能否管K: {can_beat(card_a, card_k)}")

    pair_q = [Card('Q', Suit.SPADE), Card('Q', Suit.HEART)]
    pair_j = [Card('J', Suit.CLUB), Card('J', Suit.DIAMOND)]
    print(f"  QQ能否管JJ: {can_beat(pair_q, pair_j)}")

    # 6. 测试过牌逻辑
    print("\n6. 测试过牌逻辑")
    test_player = Player(0, "测试玩家")
    test_player.hand = [Card('A', Suit.SPADE), Card('K', Suit.HEART)]

    # 过牌
    pass_action = player_pass(test_player)
    print(f"  {pass_action}")

    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)
