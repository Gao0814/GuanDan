"""Shared public hypotheses and finite continuations, never proof or selection."""

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import random
from time import monotonic

from agents.card_tracker import _validated_public_state, _history_clock_is_complete
from agents.rule_based_ai import FrozenRuleBasedAIAgent
from decision_deadline import DecisionDeadline, MODEL_RESPONSE_RESERVE_SECONDS
from engine.public_simulation import SimulationBudget, rebuild_hypothetical_position
from engine.cards import Card
from engine.rules import BaseRuleEngine


MAX_TEXT = 1800
MAX_ROOTS = 6
DEPTH = 8
SAMPLES = 2
POLICIES = ("清组", "协同留控")


@dataclass(frozen=True, slots=True)
class ContinuationReport:
    status: str
    text: str = ""
    root_ids: tuple[int, ...] = ()
    scenarios: int = 0
    depth: int = 0
    steps: int = 0
    work: int = 0
    elapsed_seconds: float = 0.0


def public_hypotheses(observation: dict, budget: SimulationBudget) -> tuple[dict[int, tuple[str, ...]], ...]:
    """Reproducible feasible assignments; no pass-derived exclusions/probability."""
    budget.check()
    state = _validated_public_state(observation)
    if state is None or not _history_clock_is_complete(observation):
        raise ValueError("incomplete_ledger")
    active_external = [p for p in state.constraints.players if p.relation != "self" and p.remaining_capacity > 0]
    if len(active_external) < 2:
        raise ValueError("external_hands_not_ambiguous")
    seed_payload = (state.my_player_id, state.level, sorted(Counter(state.my_hand).items()),
                    sorted(state.belief.unseen_cards_by_token.items()),
                    [(p.player_id, p.remaining_capacity) for p in active_external],
                    observation['current_round']['step_no'])
    seed = int.from_bytes(hashlib.sha256(json.dumps(seed_payload).encode()).digest()[:8], 'big')
    rng = random.Random(seed)
    tokens = list(state.belief.unseen_cards_by_token.keys())
    physical = [token for token in sorted(tokens) for _ in range(state.belief.unseen_cards_by_token[token])]
    results = []
    for _ in range(SAMPLES):
        budget.check()
        shuffled = physical.copy()
        rng.shuffle(shuffled)
        capacities = {int(p.player_id): p.remaining_capacity for p in active_external}
        hands = {p: [] for p in (1, 2, 3, 4)}
        hands[state.my_player_id] = list(state.my_hand)
        # Domains currently contain every live seat with capacity. Weighted
        # remaining slots avoid favouring small or large seats; reject rather
        # than relax a future restrictive domain if the finite assignment fails.
        for token in shuffled:
            budget.check()
            slots = [p for p, count in capacities.items()
                     if p in state.constraints.possible_owners_by_token[token] for _ in range(count)]
            if not slots:
                raise ValueError("infeasible_hypothesis")
            owner = rng.choice(slots)
            hands[owner].append(token)
            capacities[owner] -= 1
        if any(capacities.values()):
            raise ValueError("infeasible_hypothesis")
        results.append({p: tuple(sorted(cards)) for p, cards in hands.items()})
    # Duplicate worlds add no evidence. Never replenish according to root outcomes.
    return tuple({tuple(world.items()): world for world in results}.values())


def representative_roots(actions: list[dict], recommendation_ids=(), relation_groups=()) -> tuple[int, ...]:
    """Keep diverse displayed routes; this does not change the display set."""
    buckets = {}
    for action in actions:
        pattern = action['declared_pattern']
        control = any(t in ('2S', '2H', '2C', '2D', 'SJ', 'BJ') for t in action['carrier_cards'])
        family = ('pass' if pattern == 'pass' else pattern if pattern in ('bomb', 'straight_flush', 'joker_bomb')
                  else 'ordinary_control' if control else 'ordinary_group' if len(action['carrier_cards']) > 1 else 'ordinary_single')
        key = (family, bool(action.get('wildcard_count')))
        buckets.setdefault(key, action['action_id'])
    displayed = {a['action_id'] for a in actions}
    ordered = [a for group in relation_groups for a in group if a in displayed]
    ordered += [a for a in recommendation_ids if a in displayed]
    # Include family diversity before filling remaining relation representatives.
    family_order = ('pass', 'ordinary_group', 'bomb', 'straight_flush', 'joker_bomb',
                    'ordinary_control', 'ordinary_single')
    ids = [next(value for key, value in buckets.items() if key[0] == family)
           for family in family_order if any(key[0] == family for key in buckets)][:MAX_ROOTS]
    for action_id in ordered:
        if action_id not in ids and len(ids) < MAX_ROOTS:
            ids.append(action_id)
    return tuple(ids)


def continuation_action(observation: dict, actions: list[dict], policy: str) -> int:
    """Both policies read only the acting seat's public payload."""
    player = observation['my_info']['player_id']
    if policy == POLICIES[0]:
        return FrozenRuleBasedAIAgent(player).select_action(observation, actions)
    table = observation['current_round']['table_action']
    if table:
        leader = next((a['player_id'] for a in reversed(observation['history']['actions'])
                       if a['declared_pattern'] != 'pass'), None)
        pass_action = next((a for a in actions if a['declared_pattern'] == 'pass'), None)
        finish = next((a for a in actions if len(a['carrier_cards']) == observation['my_info']['hand_count']), None)
        if finish:
            return finish['action_id']
        if pass_action and leader is not None and leader % 2 == player % 2:
            return pass_action['action_id']
    non_pass = [a for a in actions if a['declared_pattern'] != 'pass']
    return min(non_pass or actions, key=lambda a: (
        a['declared_pattern'] in ('bomb', 'straight_flush', 'joker_bomb'),
        a.get('wildcard_count', 0),
        sum(t in ('2S', '2H', '2C', '2D', 'SJ', 'BJ') for t in a['carrier_cards']),
        -len(a['carrier_cards']), a['action_id'],
    ))['action_id']


def _counts(observation):
    return {observation['my_info']['player_id']: observation['my_info']['hand_count'],
            **{p['player_id']: p['hand_count'] for p in observation['other_players']}}


def _inventory(cards):
    counts = Counter(t if t in ('SJ', 'BJ') else t[:-1] for t in cards)
    return (sum(counts[t] for t in ('2', 'SJ', 'BJ')), sum(n == 1 for n in counts.values()),
            sum(n >= 2 for n in counts.values()), cards.count('2H'))


def _advance(world, root_id, root_player, policy, depth, initial_counts, flush_carriers=()):
    game = world.fork()
    free = clear_groups = lost_lead = 0
    table_owner = None
    root_cards = None
    root_size = steps = 0
    winner = None
    result = None
    for turn in range(depth):
        obs = game.observe()
        actor = obs['my_info']['player_id']
        actions = game.legal_actions()
        action_id = root_id if turn == 0 else continuation_action(obs, actions, policy)
        action = next(a for a in actions if a['action_id'] == action_id)
        if action['declared_pattern'] != 'pass':
            if table_owner == root_player and actor % 2 != root_player % 2:
                lost_lead += 1
            table_owner = actor
        if turn == 0:
            root_size = len(action['carrier_cards'])
        if actor == root_player:
            root_cards = list(obs['my_info']['hand_cards'])
            if turn > 0 and obs['current_round']['constraint'] == 'free':
                free += 1
                if len(action['carrier_cards']) > 1:
                    clear_groups += 1
            remaining = Counter(root_cards) - Counter(action['carrier_cards'])
            root_cards = list(remaining.elements())
        result = game.step(action_id)
        if result['round_ended']:
            table_owner = None
        steps += 1
        if result['game_over']:
            winner = result['winner']
            break
    # No winner/rank invented when depth ends. All counts are engine results.
    last_counts = result['remaining_hand_counts']
    urgent = [p for p, n in initial_counts.items() if p % 2 != root_player % 2 and 0 < n <= 5]
    urgent_progress = sum(initial_counts[p] - last_counts[p] for p in urgent)
    root_team = 'team_13' if root_player % 2 else 'team_24'
    terminal = '未终局' if winner is None else '规则平' if winner == 'draw' else '规则胜' if winner == root_team else '规则负'
    inventory = _inventory(root_cards or [])
    residual = Counter(root_cards or [])
    flushes = sum(all(n <= residual[t] for t, n in carrier.items()) for carrier in flush_carriers)
    return (initial_counts[root_player] - last_counts[root_player] - root_size,
            free, clear_groups, urgent_progress, *inventory, terminal, steps, lost_lead, flushes)


def analyze_continuations(observation: dict, canonical: list[dict], displayed: list[dict], *,
                          decision_deadline: DecisionDeadline | None = None,
                          time_budget: float = 0.8, recommendation_ids=(), relation_groups=()) -> ContinuationReport:
    start = monotonic()
    def report(status, **kwargs):
        return ContinuationReport(status, elapsed_seconds=monotonic() - start, **kwargs)
    if decision_deadline is not None:
        available = decision_deadline.remaining(reserve_seconds=MODEL_RESPONSE_RESERVE_SECONDS + 10.0)
        time_budget = min(time_budget, available)
    if time_budget < 0.05:
        return report('budget_insufficient')
    budget = SimulationBudget(start + min(time_budget, 0.8),
                              cancelled=(lambda: decision_deadline.cancelled) if decision_deadline else None)
    try:
        counts = _counts(observation)
        if (observation['current_round']['current_level_rank'] != '2'
                or sum(counts.values()) > 52 or max(counts.values()) > 16
                or len(canonical) > 120 or len(displayed) < 2
                or len(observation['history']['actions']) > 432):
            return report('outside_bounded_scope')
        if any(a not in canonical for a in displayed):
            return report('invalid_display')
        roots = representative_roots(displayed, recommendation_ids, relation_groups)
        if len(roots) < 2:
            return report('no_comparison')
        hypotheses = public_hypotheses(observation, budget)
        worlds = [rebuild_hypothetical_position(observation, canonical, hands, budget=budget) for hands in hypotheses]
        with budget.scope():
            cards = tuple(Card(t) if t in ('SJ', 'BJ') else Card(t[:-1], t[-1])
                          for t in observation['my_info']['hand_cards'])
            flush_carriers = tuple(Counter(f'{c.rank}{c.suit or ""}' for c in route.carrier_cards)
                                   for route in BaseRuleEngine().public_straight_flush_resources(cards, '2'))
        values = {root: {} for root in roots}
        steps = 0
        # Entire Cartesian block or no result: early roots never receive more
        # scenarios/policies/depth in a displayed comparison.
        for scenario, world in enumerate(worlds):
            for policy in POLICIES:
                for root in roots:
                    budget.check()
                    value = _advance(world, root, observation['my_info']['player_id'], policy, DEPTH, counts, flush_carriers)
                    values[root][scenario, policy] = value
                    steps += value[9]
        lines = ['【共同假设有界续局】',
                 f'公开条件支持的假设续局，依赖所用后续策略与有限深度：{len(worlds)}个共同场景×清组/协同留控，两策略每路线最多{DEPTH}步。不是确证、保胜或真实胜率；未算候选不更差。']
        disagreement = False
        for root in roots:
            rows = list(values[root].values())
            ranges = [str(min(r[i] for r in rows)) if min(r[i] for r in rows) == max(r[i] for r in rows)
                      else f'{min(r[i] for r in rows)}~{max(r[i] for r in rows)}' for i in range(8)]
            terminals = '/'.join(sorted({r[8] for r in rows}))
            by_policy = ['/'.join(f'{r[0]}再走,{r[1]}领,{r[3]}敌走,{r[8]}' for (s,p),r in values[root].items() if p == policy)
                         for policy in POLICIES]
            lost = f'{min(r[10] for r in rows)}~{max(r[10] for r in rows)}'
            sf = f'{min(r[11] for r in rows)}~{max(r[11] for r in rows)}'
            lines.append(f'action_id={root}：根后再走{ranges[0]}，再领{ranges[1]}次(组牌领出{ranges[2]})/敌夺本家领牌{lost}次，紧迫敌再走{ranges[3]}；余级牌王张{ranges[4]}/孤张点{ranges[5]}/成组点{ranges[6]}/配{ranges[7]}/同花顺路线{sf}；{terminals}。清组[{by_policy[0]}]；协同留控[{by_policy[1]}]')
        for first in roots:
            for second in roots:
                # Explicit opposing directions, not an averaged recommendation.
                for metric in (*range(8), 10, 11):
                    deltas = [values[first][key][metric] - values[second][key][metric] for key in values[first]]
                    if min(deltas) < 0 < max(deltas):
                        disagreement = True
                terminal_scores = {'规则负': -1, '规则平': 0, '规则胜': 1}
                deltas = [terminal_scores[values[first][key][8]] - terminal_scores[values[second][key][8]]
                          for key in values[first] if values[first][key][8] in terminal_scores and values[second][key][8] in terminal_scores]
                if deltas and min(deltas) < 0 < max(deltas):
                    disagreement = True
        lines.append('场景/策略间比较方向分歧：' + ('存在，勿据单一路径取舍。' if disagreement else '未观察到反向；有限样本不代表稳健结论。'))
        text = '\n'.join(lines)
        if len(text) > MAX_TEXT:
            return report('text_budget', work=budget.work)
        return report('ready', text=text, root_ids=roots, scenarios=len(worlds), depth=DEPTH,
                      steps=steps, work=budget.work)
    except TimeoutError:
        return report('budget_exhausted', work=budget.work)
    except (ValueError, KeyError, TypeError, StopIteration):
        return report('invalid_or_incomplete_public_position', work=budget.work)
