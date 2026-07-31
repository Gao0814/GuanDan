"""Evaluation-only strategic-pass policy variants for rank benchmarks.

The strategy in this module consumes only the same public observation and
legal-action payload handed to normal agents.  It has no access to a game,
truth hands, or the benchmark's offline state extraction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from agents.base import BaseAgent
from agents.rule_based_ai import RuleBasedAIAgent
from evaluation.rank_benchmark import RankBenchmarkReport, run_rank_benchmark


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_positive_player_id(value: object) -> bool:
    return _is_int(value) and value > 0


def _valid_nonnegative_step(value: object) -> bool:
    return _is_int(value) and value >= 0


def _team_by_player(observation: Mapping[str, object]) -> dict[int, str] | None:
    my_info = observation.get("my_info")
    other_players = observation.get("other_players")
    if not isinstance(my_info, Mapping) or not isinstance(other_players, Sequence):
        return None
    result: dict[int, str] = {}
    for item in (my_info, *other_players):
        if not isinstance(item, Mapping):
            return None
        player_id = item.get("player_id")
        team = item.get("team")
        if not _valid_positive_player_id(player_id) or not isinstance(team, str) or not team:
            return None
        if player_id in result and result[player_id] != team:
            return None
        result[player_id] = team
    return result


def _latest_round_leader(
    actions: object,
    current_round_no: int,
) -> int | None:
    """Return the latest public non-pass player in the current valid round.

    A malformed action, invalid round, or round regression makes the history
    unusable instead of borrowing response context from another round.
    """

    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)):
        return None
    previous_round_no: int | None = None
    leader: int | None = None
    for action in actions:
        if not isinstance(action, Mapping):
            return None
        round_no = action.get("round_no")
        pattern = action.get("declared_pattern")
        if not _valid_positive_player_id(round_no) or not isinstance(pattern, str):
            return None
        if previous_round_no is not None and round_no < previous_round_no:
            return None
        if round_no > current_round_no:
            return None
        previous_round_no = round_no
        if round_no != current_round_no:
            continue
        if pattern != "pass":
            player_id = action.get("player_id")
            if not _valid_positive_player_id(player_id):
                return None
            leader = player_id
    return leader


def _strategic_pass_opportunity(
    observation: object,
    legal_actions: object,
    *,
    expected_player_id: int,
) -> bool:
    """Check the strictly public, enemy-single strategic-pass precondition."""

    if not isinstance(observation, Mapping) or not isinstance(legal_actions, Sequence):
        return False
    if isinstance(legal_actions, (str, bytes)):
        return False
    my_info = observation.get("my_info")
    current_round = observation.get("current_round")
    history = observation.get("history")
    if not isinstance(my_info, Mapping) or not isinstance(current_round, Mapping) or not isinstance(history, Mapping):
        return False
    player_id = my_info.get("player_id")
    step_no = current_round.get("step_no")
    round_no = current_round.get("round_no")
    table_action = current_round.get("table_action")
    if (
        not _valid_positive_player_id(player_id)
        or player_id != expected_player_id
        or not _valid_nonnegative_step(step_no)
        or not _valid_positive_player_id(round_no)
        or not isinstance(table_action, Mapping)
        or table_action.get("declared_pattern") != "single"
    ):
        return False
    teams = _team_by_player(observation)
    if teams is None or player_id not in teams:
        return False
    leader_id = _latest_round_leader(history.get("actions"), round_no)
    if leader_id is None or leader_id not in teams or teams[leader_id] == teams[player_id]:
        return False

    has_pass = False
    has_non_pass = False
    for action in legal_actions:
        if not isinstance(action, Mapping):
            return False
        pattern = action.get("declared_pattern")
        if not isinstance(pattern, str):
            return False
        if pattern == "pass":
            has_pass = True
        else:
            has_non_pass = True
    return has_pass and has_non_pass


def _pass_action_id(legal_actions: Sequence[object]) -> int | None:
    for action in legal_actions:
        if not isinstance(action, Mapping) or action.get("declared_pattern") != "pass":
            continue
        action_id = action.get("action_id")
        if _is_int(action_id):
            return action_id
    return None


@dataclass(slots=True)
class StrategicPassAIAgent(BaseAgent):
    """Public-only deterministic pressure policy used only by evaluation."""

    strategic_pass_rate: int = 0
    strategic_pass_opportunity_count: int = 0
    strategic_pass_count: int = 0

    def __post_init__(self) -> None:
        if not _is_int(self.strategic_pass_rate) or not 0 <= self.strategic_pass_rate <= 100:
            raise ValueError("strategic_pass_rate must be an integer from 0 to 100")

    @staticmethod
    def _gate(step_no: int, player_id: int) -> int:
        """A stable public gate; it deliberately excludes seed and hidden state."""

        return (37 * step_no + 17 * player_id + 11) % 100

    def select_action(
        self,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> int:
        if _strategic_pass_opportunity(
            observation,
            legal_actions,
            expected_player_id=self.player_id,
        ):
            self.strategic_pass_opportunity_count += 1
            current_round = observation["current_round"]
            my_info = observation["my_info"]
            step_no = int(current_round["step_no"])
            player_id = int(my_info["player_id"])
            if self._gate(step_no, player_id) < self.strategic_pass_rate:
                pass_action_id = _pass_action_id(legal_actions)
                if pass_action_id is not None:
                    self.strategic_pass_count += 1
                    return pass_action_id
        return RuleBasedAIAgent(player_id=self.player_id).select_action(
            observation,
            legal_actions,
        )


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


def _validate_rates(rates: Sequence[int]) -> tuple[int, ...]:
    if isinstance(rates, (str, bytes)) or not isinstance(rates, Sequence) or not rates:
        raise ValueError("strategic_pass_rates must be a non-empty sequence")
    normalized = tuple(rates)
    if any(not _is_int(rate) or not 0 <= rate <= 100 for rate in normalized):
        raise ValueError("each strategic_pass_rate must be an integer from 0 to 100")
    if len(set(normalized)) != len(normalized):
        raise ValueError("strategic_pass_rates must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class PolicyVariantRankReport:
    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    rank_benchmark: RankBenchmarkReport

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_name": self.policy_name,
            "strategic_pass_rate": self.strategic_pass_rate,
            "strategic_pass_opportunity_count": self.strategic_pass_opportunity_count,
            "strategic_pass_count": self.strategic_pass_count,
            "rank_benchmark": self.rank_benchmark.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PassPolicyBenchmarkReport:
    requested_policy_count: int
    by_policy: Mapping[str, PolicyVariantRankReport]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "by_policy": {
                name: report.to_dict() for name, report in self.by_policy.items()
            },
        }


def run_pass_policy_benchmark(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 24,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> PassPolicyBenchmarkReport:
    """Run isolated public-only policy variants over identical benchmark inputs."""

    rates = _validate_rates(strategic_pass_rates)
    by_policy: dict[str, PolicyVariantRankReport] = {}
    for rate in rates:
        created_agents: list[StrategicPassAIAgent] = []

        def factory(_seed: int, player_id: int) -> StrategicPassAIAgent:
            agent = StrategicPassAIAgent(
                player_id=player_id,
                strategic_pass_rate=rate,
            )
            created_agents.append(agent)
            return agent

        rank_benchmark = run_rank_benchmark(
            seeds,
            current_level_rank=current_level_rank,
            max_steps=max_steps,
            max_samples_per_game=max_samples_per_game,
            max_external_cards=max_external_cards,
            max_search_nodes=max_search_nodes,
            max_solutions=max_solutions,
            agent_factory=factory,
        )
        opportunity_count = sum(
            agent.strategic_pass_opportunity_count for agent in created_agents
        )
        pass_count = sum(agent.strategic_pass_count for agent in created_agents)
        name = _policy_name(rate)
        by_policy[name] = PolicyVariantRankReport(
            policy_name=name,
            strategic_pass_rate=rate,
            strategic_pass_opportunity_count=opportunity_count,
            strategic_pass_count=pass_count,
            rank_benchmark=rank_benchmark,
        )
    return PassPolicyBenchmarkReport(
        requested_policy_count=len(rates),
        by_policy=MappingProxyType(dict(by_policy)),
    )
