"""Isolated strategic-pass variants for critical-endgame marginal corpora.

This evaluation-only wrapper creates a fresh public-only agent population and
a fresh :func:`run_marginal_corpus` run for every requested policy rate.  It
does not combine policy results or retain games, agents, samples, or truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from evaluation.marginal_corpus import MarginalCorpusReport, run_marginal_corpus
from evaluation.pass_policy_benchmark import StrategicPassAIAgent


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_rates(rates: Sequence[int]) -> tuple[int, ...]:
    """Validate rates locally so this wrapper has no private-helper coupling."""

    if isinstance(rates, (str, bytes)) or not isinstance(rates, Sequence) or not rates:
        raise ValueError("strategic_pass_rates must be a non-empty sequence")
    normalized = tuple(rates)
    if any(not _is_int(rate) or not 0 <= rate <= 100 for rate in normalized):
        raise ValueError("each strategic_pass_rate must be an integer from 0 to 100")
    if len(set(normalized)) != len(normalized):
        raise ValueError("strategic_pass_rates must not contain duplicates")
    return normalized


def _policy_name(rate: int) -> str:
    return "forced_only" if rate == 0 else f"strategic_pass_{rate}"


@dataclass(frozen=True, slots=True)
class PolicyVariantMarginalReport:
    """One independent policy's aggregate-only marginal corpus."""

    policy_name: str
    strategic_pass_rate: int
    strategic_pass_opportunity_count: int
    strategic_pass_count: int
    corpus: MarginalCorpusReport

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_name": self.policy_name,
            "strategic_pass_rate": self.strategic_pass_rate,
            "strategic_pass_opportunity_count": self.strategic_pass_opportunity_count,
            "strategic_pass_count": self.strategic_pass_count,
            "corpus": self.corpus.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class MarginalPolicyCorpusReport:
    """Independent corpus results keyed by caller-ordered policy name."""

    requested_policy_count: int
    by_policy: Mapping[str, PolicyVariantMarginalReport]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_policy_count": self.requested_policy_count,
            "by_policy": {
                name: report.to_dict() for name, report in self.by_policy.items()
            },
        }


def run_marginal_policy_corpus(
    seeds: Sequence[int],
    *,
    strategic_pass_rates: Sequence[int] = (0, 25, 50, 100),
    current_level_rank: str = "2",
    max_steps: int = 5000,
    max_samples_per_game: int = 128,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> MarginalPolicyCorpusReport:
    """Run isolated public-only strategic-pass marginal corpus variants.

    All non-policy inputs are forwarded unchanged to every corpus.  Each
    factory closes over only its rate and its own created-agent list, ensuring
    no game, agent, counter, or result state can cross policy boundaries.
    """

    rates = _validate_rates(strategic_pass_rates)
    by_policy: dict[str, PolicyVariantMarginalReport] = {}
    for rate in rates:
        created_agents: list[StrategicPassAIAgent] = []

        def factory(_seed: int, player_id: int) -> StrategicPassAIAgent:
            agent = StrategicPassAIAgent(
                player_id=player_id,
                strategic_pass_rate=rate,
            )
            created_agents.append(agent)
            return agent

        corpus = run_marginal_corpus(
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
        if not 0 <= pass_count <= opportunity_count:
            raise RuntimeError("strategic pass counters violate their public invariant")
        name = _policy_name(rate)
        by_policy[name] = PolicyVariantMarginalReport(
            policy_name=name,
            strategic_pass_rate=rate,
            strategic_pass_opportunity_count=opportunity_count,
            strategic_pass_count=pass_count,
            corpus=corpus,
        )

    return MarginalPolicyCorpusReport(
        requested_policy_count=len(rates),
        by_policy=MappingProxyType(dict(by_policy)),
    )
