"""Public-only runtime assembly for the exact confidence contract."""

from __future__ import annotations

from agents.card_allocations import enumerate_card_allocations
from agents.card_belief import build_card_belief
from agents.card_confidence import CardConfidenceState, build_card_confidence
from agents.card_constraints import build_card_constraints
from agents.game_phase import CRITICAL_ENDGAME, GamePhaseContext


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _unavailable(phase: object, diagnostic: str) -> CardConfidenceState:
    return CardConfidenceState(
        phase=phase if isinstance(phase, str) else "",
        status="unavailable",
        source="none",
        calibration_scope="none",
        external_unknown_count=0,
        physical_assignment_count=0,
        players=(),
        diagnostics=(diagnostic,),
    )


def build_runtime_card_confidence(
    observation: dict[str, object],
    phase_context: GamePhaseContext,
    *,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> CardConfidenceState:
    """Assemble confidence once from an already-classified public position."""

    for name, value in (
        ("max_external_cards", max_external_cards),
        ("max_search_nodes", max_search_nodes),
        ("max_solutions", max_solutions),
    ):
        if not _is_positive_int(value):
            raise ValueError(f"{name} must be a positive integer")
    if max_external_cards > 12:
        raise ValueError("max_external_cards must not exceed 12")

    if not isinstance(phase_context, GamePhaseContext):
        return _unavailable("", "invalid_phase_context")
    if phase_context.phase != CRITICAL_ENDGAME:
        return _unavailable(phase_context.phase, "unsupported_phase")

    try:
        card_belief = build_card_belief(observation, phase_context)
        constraints = build_card_constraints(card_belief)
        allocation = enumerate_card_allocations(
            card_belief,
            constraints,
            max_external_cards=max_external_cards,
            max_search_nodes=max_search_nodes,
            max_solutions=max_solutions,
        )
        return build_card_confidence(card_belief, constraints, allocation)
    except Exception:
        return _unavailable(phase_context.phase, "pipeline_error")
