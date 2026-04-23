"""Minimal evaluation framework for local vs DeepSeek+RAG baseline agents."""

from argparse import ArgumentParser
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.rag_advisor import RAGAdvisor
from agents.deepseek_client import DeepSeekClient
from agents.rule_based_ai import RuleBasedAIAgent
from engine.actions import Action, ActionType
from engine.cards import Card
from engine.game import FourAIGameRunner, build_initial_state
from engine.logging_utils import DebugLogger
from engine.patterns import PatternType
from engine.rules import BaseRuleEngine
from engine.state import GameState, PlayerState, TableConstraint
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever
from agents.base import AgentContext


ModeName = str
AdvisorFactory = Callable[[int], object | None]


@dataclass(frozen=True)
class HumanlikenessScenario:
    name: str
    state: GameState
    legal_actions: tuple[Action, ...]
    better_set: set[tuple[str, str | None, tuple[str, ...]]]
    worse_set: set[tuple[str, str | None, tuple[str, ...]]]
    repeats: int = 5


def _build_rag_advisor() -> RAGAdvisor:
    loader = KnowledgeBaseLoader(PROJECT_ROOT / "rag")
    retriever = KnowledgeRetriever(loader.load_all_documents())
    return RAGAdvisor(retriever)


def _state_with_hand(
    hand: tuple[Card, ...],
    *,
    with_table: bool = False,
    leading_action: Action | None = None,
) -> GameState:
    players = (
        PlayerState(player_id=0, hand_cards=hand),
        PlayerState(player_id=1, hand_cards=()),
        PlayerState(player_id=2, hand_cards=()),
        PlayerState(player_id=3, hand_cards=()),
    )
    table = TableConstraint()
    if with_table:
        default_lead = Action(
            player_id=1,
            action_type=ActionType.PLAY,
            cards=(Card(rank="6", suit="S"),),
            declared_pattern=PatternType.SINGLE,
        )
        table = TableConstraint(
            leading_action=leading_action or default_lead,
            required_pattern=(leading_action.declared_pattern if leading_action else PatternType.SINGLE),
            min_strength_hint=6,
        )
    return GameState(players=players, current_player_id=0, table_constraint=table)


def _action_signature(action: Action) -> tuple[str, str | None, tuple[str, ...]]:
    return (
        action.action_type.value,
        action.declared_pattern.value if action.declared_pattern else None,
        tuple(sorted(f"{card.rank}{card.suit or ''}" for card in action.cards)),
    )


def _build_humanlikeness_scenarios() -> tuple[HumanlikenessScenario, ...]:
    scenarios: list[HumanlikenessScenario] = []

    # 1) 有明显顺子时，不应长期只出散单
    state_straight = _state_with_hand(
        (
            Card(rank="3", suit="S"),
            Card(rank="4", suit="S"),
            Card(rank="5", suit="S"),
            Card(rank="6", suit="S"),
            Card(rank="7", suit="S"),
            Card(rank="9", suit="H"),
        )
    )
    straight_action = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="3", suit="S"),
            Card(rank="4", suit="S"),
            Card(rank="5", suit="S"),
            Card(rank="6", suit="S"),
            Card(rank="7", suit="S"),
        ),
        PatternType.STRAIGHT,
    )
    single_low = Action(0, ActionType.PLAY, (Card(rank="3", suit="S"),), PatternType.SINGLE)
    single_high = Action(0, ActionType.PLAY, (Card(rank="9", suit="H"),), PatternType.SINGLE)
    legal_straight = (single_low, single_high, straight_action)
    scenarios.append(
        HumanlikenessScenario(
            name="prefer_straight_over_scattered_singles",
            state=state_straight,
            legal_actions=legal_straight,
            better_set={_action_signature(straight_action)},
            worse_set={_action_signature(single_low), _action_signature(single_high)},
            repeats=8,
        )
    )

    # 2) 有明显连对时，不应优先拆成对子
    state_pair_straight = _state_with_hand(
        (
            Card(rank="4", suit="S"),
            Card(rank="4", suit="H"),
            Card(rank="5", suit="S"),
            Card(rank="5", suit="H"),
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="9", suit="C"),
        )
    )
    pair_4 = Action(0, ActionType.PLAY, (Card(rank="4", suit="S"), Card(rank="4", suit="H")), PatternType.PAIR)
    pair_6 = Action(0, ActionType.PLAY, (Card(rank="6", suit="S"), Card(rank="6", suit="H")), PatternType.PAIR)
    pair_straight = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="4", suit="S"),
            Card(rank="4", suit="H"),
            Card(rank="5", suit="S"),
            Card(rank="5", suit="H"),
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
        ),
        PatternType.PAIR_STRAIGHT,
    )
    legal_pair_straight = (pair_4, pair_6, pair_straight)
    scenarios.append(
        HumanlikenessScenario(
            name="prefer_pair_straight_over_split_pairs",
            state=state_pair_straight,
            legal_actions=legal_pair_straight,
            better_set={_action_signature(pair_straight)},
            worse_set={_action_signature(pair_4), _action_signature(pair_6)},
            repeats=8,
        )
    )

    # 3) 有明显三带二时，不应只出三张
    state_twp = _state_with_hand(
        (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="6", suit="D"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
            Card(rank="Q", suit="C"),
        )
    )
    triple_only = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="6", suit="D"),
        ),
        PatternType.TRIPLE,
    )
    pair_only = Action(0, ActionType.PLAY, (Card(rank="9", suit="S"), Card(rank="9", suit="H")), PatternType.PAIR)
    triple_with_pair = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="6", suit="S"),
            Card(rank="6", suit="H"),
            Card(rank="6", suit="D"),
            Card(rank="9", suit="S"),
            Card(rank="9", suit="H"),
        ),
        PatternType.TRIPLE_WITH_PAIR,
    )
    legal_twp = (triple_only, pair_only, triple_with_pair)
    scenarios.append(
        HumanlikenessScenario(
            name="prefer_triple_with_pair_over_plain_triple",
            state=state_twp,
            legal_actions=legal_twp,
            better_set={_action_signature(triple_with_pair)},
            worse_set={_action_signature(triple_only)},
            repeats=8,
        )
    )

    # 4) 有合理非炸弹动作时，不应无意义先炸
    state_no_bomb = _state_with_hand(
        (
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="J", suit="S"),
            Card(rank="Q", suit="S"),
            Card(rank="Q", suit="H"),
            Card(rank="Q", suit="C"),
            Card(rank="Q", suit="D"),
        )
    )
    single_safe = Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE)
    straight_safe = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="7", suit="S"),
            Card(rank="8", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="10", suit="S"),
            Card(rank="J", suit="S"),
        ),
        PatternType.STRAIGHT,
    )
    bomb_q = Action(
        0,
        ActionType.PLAY,
        (
            Card(rank="Q", suit="S"),
            Card(rank="Q", suit="H"),
            Card(rank="Q", suit="C"),
            Card(rank="Q", suit="D"),
        ),
        PatternType.BOMB,
    )
    legal_no_bomb = (single_safe, straight_safe, bomb_q)
    scenarios.append(
        HumanlikenessScenario(
            name="avoid_unnecessary_bomb_when_safe_alternatives_exist",
            state=state_no_bomb,
            legal_actions=legal_no_bomb,
            better_set={_action_signature(single_safe), _action_signature(straight_safe)},
            worse_set={_action_signature(bomb_q)},
            repeats=8,
        )
    )

    # 5/6) 固定残局风格：跟牌时优先低成本合法动作（当前已接入经验）
    lead_single = Action(
        player_id=1,
        action_type=ActionType.PLAY,
        cards=(Card(rank="6", suit="S"),),
        declared_pattern=PatternType.SINGLE,
    )
    state_endgame = _state_with_hand(
        (
            Card(rank="7", suit="S"),
            Card(rank="9", suit="S"),
            Card(rank="A", suit="S"),
        ),
        with_table=True,
        leading_action=lead_single,
    )
    low_follow = Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE)
    high_follow = Action(0, ActionType.PLAY, (Card(rank="A", suit="S"),), PatternType.SINGLE)
    pass_action = Action(0, ActionType.PASS, (), None)
    legal_endgame = (pass_action, low_follow, high_follow)
    scenarios.append(
        HumanlikenessScenario(
            name="endgame_follow_prefers_lower_cost_control",
            state=state_endgame,
            legal_actions=legal_endgame,
            better_set={_action_signature(low_follow)},
            worse_set={_action_signature(high_follow), _action_signature(pass_action)},
            repeats=8,
        )
    )

    # 6) 固定局面稳定性：输出应稳定或始终落在预定义合理集合内
    state_stability = _state_with_hand((Card(rank="7", suit="S"), Card(rank="9", suit="S")))
    single_7 = Action(0, ActionType.PLAY, (Card(rank="7", suit="S"),), PatternType.SINGLE)
    single_9 = Action(0, ActionType.PLAY, (Card(rank="9", suit="S"),), PatternType.SINGLE)
    legal_stability = (single_7, single_9)
    scenarios.append(
        HumanlikenessScenario(
            name="fixed_state_stability_or_reasonable_set",
            state=state_stability,
            legal_actions=legal_stability,
            better_set={_action_signature(single_7), _action_signature(single_9)},
            worse_set=set(),
            repeats=10,
        )
    )

    return tuple(scenarios)


def evaluate_humanlikeness_fixed_scenarios(
    mode: ModeName,
    deepseek_advisor_factory: AdvisorFactory | None = None,
) -> dict[str, object]:
    scenarios = _build_humanlikeness_scenarios()

    rag_advisor = _build_rag_advisor() if mode == "deepseek_rag_baseline" else None
    deepseek_enabled = mode == "deepseek_rag_baseline"

    scenario_results: dict[str, dict[str, object]] = {}
    total_better_hits = 0
    total_worse_hits = 0
    total_choices = 0
    all_in_better_count = 0
    stable_count = 0
    rule_gap_likely: list[str] = []

    for scenario in scenarios:
        outputs: list[tuple[str, str | None, tuple[str, ...]]] = []
        legal_signatures = {_action_signature(action) for action in scenario.legal_actions}
        if not (scenario.better_set & legal_signatures):
            rule_gap_likely.append(scenario.name)

        for i in range(scenario.repeats):
            advisor = deepseek_advisor_factory(0) if (deepseek_enabled and deepseek_advisor_factory) else None
            agent = RuleBasedAIAgent(
                player_id=0,
                name=f"{mode}-scenario-agent",
                rag_advisor=rag_advisor,
                deepseek_enabled=deepseek_enabled,
                deepseek_action_advisor=advisor,
            )
            chosen = agent.select_action(
                scenario.state,
                scenario.legal_actions,
                context=AgentContext(step_no=7000 + i),
            )
            outputs.append(_action_signature(chosen))

        better_hits = sum(1 for out in outputs if out in scenario.better_set)
        worse_hits = sum(1 for out in outputs if out in scenario.worse_set)
        in_better_all = all(out in scenario.better_set for out in outputs)
        stable = len(set(outputs)) == 1

        total_better_hits += better_hits
        total_worse_hits += worse_hits
        total_choices += len(outputs)
        if in_better_all:
            all_in_better_count += 1
        if stable:
            stable_count += 1

        scenario_results[scenario.name] = {
            "repeats": scenario.repeats,
            "better_hit_rate": (better_hits / scenario.repeats) if scenario.repeats else 0.0,
            "worse_hit_rate": (worse_hits / scenario.repeats) if scenario.repeats else 0.0,
            "all_in_better_set": in_better_all,
            "stable_output": stable,
        }

    return {
        "mode": mode,
        "total_scenarios": len(scenarios),
        "overall_better_hit_rate": (total_better_hits / total_choices) if total_choices else 0.0,
        "overall_worse_hit_rate": (total_worse_hits / total_choices) if total_choices else 0.0,
        "all_in_better_set_scenarios": all_in_better_count,
        "stable_scenarios": stable_count,
        "rule_gap_likely_scenarios": rule_gap_likely,
        "scenarios": scenario_results,
    }


def evaluate_humanlikeness_compare(
    deepseek_advisor_factory: AdvisorFactory | None = None,
) -> dict[str, dict[str, object]]:
    local = evaluate_humanlikeness_fixed_scenarios(mode="local_rule_based")
    deepseek = evaluate_humanlikeness_fixed_scenarios(
        mode="deepseek_rag_baseline",
        deepseek_advisor_factory=deepseek_advisor_factory,
    )
    return {
        "local_rule_based": local,
        "deepseek_rag_baseline": deepseek,
    }


def _build_agents(mode: ModeName, deepseek_advisor_factory: AdvisorFactory | None) -> tuple[RuleBasedAIAgent, ...]:
    if mode == "local_rule_based":
        return tuple(
            RuleBasedAIAgent(player_id=i, name=f"local-ai-{i}", deepseek_enabled=False)
            for i in range(4)
        )

    if mode == "deepseek_rag_baseline":
        rag_advisor = _build_rag_advisor()
        return tuple(
            RuleBasedAIAgent(
                player_id=i,
                name=f"deepseek-rag-ai-{i}",
                rag_advisor=rag_advisor,
                deepseek_enabled=True,
                deepseek_action_advisor=(deepseek_advisor_factory(i) if deepseek_advisor_factory else None),
            )
            for i in range(4)
        )

    raise ValueError(f"unsupported mode: {mode}")


def _merge_status_counts(total: dict[str, int], part: dict[str, int]) -> None:
    for key, value in part.items():
        total[key] = total.get(key, 0) + int(value)


def run_deepseek_call_verification(
    games: int,
    seed_start: int,
    max_steps: int,
    deepseek_advisor_factory: AdvisorFactory | None = None,
) -> dict[str, object]:
    from config import AppConfig

    cfg = AppConfig.from_env()
    has_api_key = bool(cfg.deepseek_api_key)

    suggest_action_calls = 0
    transport_calls = 0
    deepseek_client_created_count = 0
    model_status_counts: dict[str, int] = {}

    class _AdvisorProbe:
        def __init__(self, inner: object) -> None:
            self._inner = inner

        def suggest_action(self, state, legal_actions, context, rag_context=None):
            nonlocal suggest_action_calls
            suggest_action_calls += 1
            return self._inner.suggest_action(
                state=state,
                legal_actions=legal_actions,
                context=context,
                rag_context=rag_context,
            )

    for game_index in range(games):
        seed = seed_start + game_index
        agents = _build_agents("deepseek_rag_baseline", deepseek_advisor_factory=deepseek_advisor_factory)

        for agent in agents:
            advisor = getattr(agent, "_deepseek_action_advisor", None)
            if isinstance(advisor, DeepSeekClient):
                deepseek_client_created_count += 1
                original_transport = advisor._transport

                def _wrapped_transport(request, timeout, _inner=original_transport):
                    nonlocal transport_calls
                    transport_calls += 1
                    return _inner(request, timeout)

                advisor._transport = _wrapped_transport

            if advisor is not None:
                agent._deepseek_action_advisor = _AdvisorProbe(advisor)

        logger = DebugLogger()
        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=(agents[0], agents[1], agents[2], agents[3]),
            debug_logger=logger,
            max_steps=max_steps,
        )
        _ = runner.run_one_game(build_initial_state(seed=seed))

        for agent in agents:
            _merge_status_counts(model_status_counts, agent.get_model_status_counts())

    blocked_reasons: list[str] = []
    if not has_api_key and deepseek_client_created_count == 0 and transport_calls == 0:
        blocked_reasons.append("missing_api_key")
    if model_status_counts.get("enabled_without_adapter_fallback", 0) > 0:
        blocked_reasons.append("enabled_without_adapter_fallback")
    if transport_calls == 0:
        blocked_reasons.append("transport_not_triggered")

    # keep deterministic and concise
    blocked_reasons = sorted(set(blocked_reasons))

    return {
        "mode": "deepseek_rag_baseline",
        "deepseek_enabled_requested": True,
        "has_api_key": has_api_key,
        "deepseek_client_created_count": deepseek_client_created_count,
        "suggest_action_calls": suggest_action_calls,
        "transport_calls": transport_calls,
        "model_status_counts": {
            "accepted_legal_suggestion": model_status_counts.get("accepted_legal_suggestion", 0),
            "rejected_non_legal_suggestion": model_status_counts.get("rejected_non_legal_suggestion", 0),
            "rejected_degradation_fallback": model_status_counts.get("rejected_degradation_fallback", 0),
            "empty_response_fallback": model_status_counts.get("empty_response_fallback", 0),
            "fallback_error": model_status_counts.get("fallback_error", 0),
            "enabled_without_adapter_fallback": model_status_counts.get("enabled_without_adapter_fallback", 0),
        },
        "blocked_reasons": blocked_reasons,
        "http_called": transport_calls > 0,
    }


def _init_summary(mode: ModeName, games: int) -> dict[str, object]:
    return {
        "mode": mode,
        "total_games": games,
        "wins": {str(i): 0 for i in range(4)},
        "illegal_action_rate": 0.0,
        "average_steps": 0.0,
        "deepseek_accepted_count": 0,
        "deepseek_rejected_count": 0,
        "fallback_count": 0,
        "fallback_breakdown": {
            "empty_response_fallback": 0,
            "fallback_error": 0,
            "rejected_degradation_fallback": 0,
        },
    }


def _collect_step_metrics(logger: DebugLogger) -> tuple[int, int, int]:
    step_events = [event for event in logger.events if event.event_type == "step"]
    total_steps = len(step_events)
    illegal_steps = 0
    for event in step_events:
        payload = event.payload
        if payload.get("chosen_action") not in payload.get("legal_actions", []):
            illegal_steps += 1
    return total_steps, illegal_steps, len(step_events)


def _collect_model_metrics(agents: tuple[RuleBasedAIAgent, ...]) -> tuple[int, int, dict[str, int]]:
    accepted = 0
    rejected = 0
    fallback = {
        "empty_response_fallback": 0,
        "fallback_error": 0,
        "rejected_degradation_fallback": 0,
    }
    for agent in agents:
        counts = agent.get_model_status_counts()
        accepted += counts.get("accepted_legal_suggestion", 0)
        rejected += counts.get("rejected_non_legal_suggestion", 0)
        rejected += counts.get("rejected_degradation_fallback", 0)
        fallback["empty_response_fallback"] += counts.get("empty_response_fallback", 0)
        fallback["fallback_error"] += counts.get("fallback_error", 0)
        fallback["rejected_degradation_fallback"] += counts.get("rejected_degradation_fallback", 0)
    return accepted, rejected, fallback


def evaluate_mode(
    mode: ModeName,
    games: int,
    seed_start: int,
    max_steps: int,
    deepseek_advisor_factory: AdvisorFactory | None = None,
) -> dict[str, object]:
    summary = _init_summary(mode=mode, games=games)
    total_steps = 0
    illegal_steps = 0

    for game_index in range(games):
        seed = seed_start + game_index
        agents = _build_agents(mode=mode, deepseek_advisor_factory=deepseek_advisor_factory)
        logger = DebugLogger()
        runner = FourAIGameRunner(
            rule_engine=BaseRuleEngine(),
            agents=(agents[0], agents[1], agents[2], agents[3]),
            debug_logger=logger,
            max_steps=max_steps,
        )
        final_state = runner.run_one_game(build_initial_state(seed=seed))

        winner = final_state.winner_player_id
        if winner is not None:
            summary["wins"][str(winner)] += 1

        game_steps, game_illegal_steps, _ = _collect_step_metrics(logger)
        total_steps += game_steps
        illegal_steps += game_illegal_steps

        accepted, rejected, fallback_breakdown = _collect_model_metrics(agents)
        summary["deepseek_accepted_count"] += accepted
        summary["deepseek_rejected_count"] += rejected
        for key in fallback_breakdown:
            summary["fallback_breakdown"][key] += fallback_breakdown[key]

    summary["average_steps"] = (total_steps / games) if games > 0 else 0.0
    summary["illegal_action_rate"] = (illegal_steps / total_steps) if total_steps > 0 else 0.0
    summary["fallback_count"] = sum(summary["fallback_breakdown"].values())
    return summary


def evaluate_modes(
    games: int,
    seed_start: int,
    max_steps: int,
    modes: tuple[ModeName, ...] = ("local_rule_based", "deepseek_rag_baseline"),
    deepseek_advisor_factory: AdvisorFactory | None = None,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for mode in modes:
        results[mode] = evaluate_mode(
            mode=mode,
            games=games,
            seed_start=seed_start,
            max_steps=max_steps,
            deepseek_advisor_factory=deepseek_advisor_factory,
        )
    return results


def _print_human(results: dict[str, dict[str, object]]) -> None:
    for mode, summary in results.items():
        print(f"\n=== {mode} ===")
        print(f"总对局数: {summary['total_games']}")
        print(f"胜负结果统计: {summary['wins']}")
        print(f"非法动作率: {summary['illegal_action_rate']:.6f}")
        print(f"平均步数: {summary['average_steps']:.2f}")
        print(f"DeepSeek 建议采纳次数: {summary['deepseek_accepted_count']}")
        print(f"DeepSeek 建议被拒绝次数: {summary['deepseek_rejected_count']}")
        print(f"fallback 次数: {summary['fallback_count']}")
        print(f"fallback 分解: {summary['fallback_breakdown']}")


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Evaluate local rule-based vs DeepSeek+RAG baseline AI.")
    parser.add_argument("--games", type=int, default=10, help="Number of games per mode.")
    parser.add_argument("--seed-start", type=int, default=1000, help="Start seed for evaluation.")
    parser.add_argument("--max-steps", type=int, default=12000, help="Per-game max step guard.")
    parser.add_argument(
        "--mode",
        choices=["all", "local_rule_based", "deepseek_rag_baseline"],
        default="all",
        help="Evaluation mode selection.",
    )
    parser.add_argument("--json", action="store_true", help="Print summary in JSON format.")
    parser.add_argument(
        "--verify-deepseek-call",
        action="store_true",
        help="Run minimal DeepSeek call verification and print call/fallback evidence.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.verify_deepseek_call:
        verify = run_deepseek_call_verification(
            games=args.games,
            seed_start=args.seed_start,
            max_steps=args.max_steps,
        )
        if args.json:
            print(json.dumps(verify, ensure_ascii=False, indent=2))
        else:
            print("\n=== deepseek_call_verification ===")
            print(f"deepseek_enabled_requested: {verify['deepseek_enabled_requested']}")
            print(f"has_api_key: {verify['has_api_key']}")
            print(f"deepseek_client_created_count: {verify['deepseek_client_created_count']}")
            print(f"suggest_action_calls: {verify['suggest_action_calls']}")
            print(f"transport_calls: {verify['transport_calls']}")
            print(f"http_called: {verify['http_called']}")
            print(f"model_status_counts: {verify['model_status_counts']}")
            print(f"blocked_reasons: {verify['blocked_reasons']}")
        return 0

    modes = (
        ("local_rule_based", "deepseek_rag_baseline")
        if args.mode == "all"
        else (args.mode,)
    )

    results = evaluate_modes(
        games=args.games,
        seed_start=args.seed_start,
        max_steps=args.max_steps,
        modes=modes,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_human(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
