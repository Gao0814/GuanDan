"""Auditable public behaviour events for Step J-C2a.

This module projects only public observation history and J-A public facts into
lead/follow/pass events.  It deliberately does not rank candidates, assign
hidden cards, or produce any probability-like output.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from agents.card_belief import (
    JOKER_RANKS,
    NORMAL_RANKS,
    SUITS,
    CardBeliefState,
)


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _declared_rank(token: str) -> str | None:
    if token in JOKER_RANKS or token in NORMAL_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _carrier_rank(token: str) -> str | None:
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    return None


def _freeze_counts(counts: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(counts))


@dataclass(frozen=True, slots=True)
class PublicBehaviorEvent:
    """One valid public history action with reconstructed response context."""

    action_index: int
    step_no: int | None
    round_no: int | None
    player_id: object
    relation: str
    event_type: str
    declared_pattern: str
    declared_cards: tuple[str, ...]
    carrier_cards: tuple[str, ...]
    declared_ranks: tuple[str, ...]
    carrier_ranks: tuple[str, ...]
    declaration_differs_from_carrier: bool
    response_to_action_index: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "action_index": self.action_index,
            "step_no": self.step_no,
            "round_no": self.round_no,
            "player_id": self.player_id,
            "relation": self.relation,
            "event_type": self.event_type,
            "declared_pattern": self.declared_pattern,
            "declared_cards": list(self.declared_cards),
            "carrier_cards": list(self.carrier_cards),
            "declared_ranks": list(self.declared_ranks),
            "carrier_ranks": list(self.carrier_ranks),
            "declaration_differs_from_carrier": self.declaration_differs_from_carrier,
            "response_to_action_index": self.response_to_action_index,
        }


@dataclass(frozen=True, slots=True)
class PlayerBehaviorProfile:
    """Public action facts aggregated for one player."""

    player_id: object
    relation: str
    action_count: int
    lead_count: int
    follow_count: int
    pass_count: int
    pattern_counts: Mapping[str, int]
    released_high_value_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "relation": self.relation,
            "action_count": self.action_count,
            "lead_count": self.lead_count,
            "follow_count": self.follow_count,
            "pass_count": self.pass_count,
            "pattern_counts": dict(self.pattern_counts),
            "released_high_value_counts": dict(self.released_high_value_counts),
        }


@dataclass(frozen=True, slots=True)
class PublicSignalState:
    """Immutable public event context; it contains no hidden-card inference."""

    phase: str
    current_level_rank: str | None
    events: tuple[PublicBehaviorEvent, ...]
    players: tuple[PlayerBehaviorProfile, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "current_level_rank": self.current_level_rank,
            "events": [event.to_dict() for event in self.events],
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
        }


@dataclass(slots=True)
class _MutableProfile:
    player_id: object
    relation: str
    action_count: int = 0
    lead_count: int = 0
    follow_count: int = 0
    pass_count: int = 0
    pattern_counts: Counter[str] | None = None
    released_high_value_counts: Counter[str] | None = None
    played_cards: list[str] | None = None

    def __post_init__(self) -> None:
        self.pattern_counts = Counter() if self.pattern_counts is None else self.pattern_counts
        self.released_high_value_counts = (
            Counter()
            if self.released_high_value_counts is None
            else self.released_high_value_counts
        )
        self.played_cards = [] if self.played_cards is None else self.played_cards


def build_public_signal_state(
    observation: dict[str, object],
    card_belief: CardBeliefState,
) -> PublicSignalState:
    """Build public behaviour events without inferring hidden-card facts."""

    diagnostics: list[str] = []

    def diagnose(category: str, detail: object | None = None) -> None:
        if category not in diagnostics:
            diagnostics.append(category)
        if detail is not None:
            detailed = f"{category}:{detail}"
            if detailed not in diagnostics:
                diagnostics.append(detailed)

    my_info = observation.get("my_info", {})
    current_round = observation.get("current_round", {})
    if not isinstance(my_info, dict):
        my_info = {}
    if not isinstance(current_round, dict):
        current_round = {}

    my_level_present = "current_level_rank" in my_info
    round_level_present = "current_level_rank" in current_round
    my_level = my_info.get("current_level_rank")
    round_level = current_round.get("current_level_rank")
    if my_level_present and round_level_present and my_level != round_level:
        diagnose("level_rank_mismatch")
    selected_level = my_level if my_level_present else round_level
    current_level_rank = selected_level if selected_level in NORMAL_RANKS else None
    if selected_level is not None and current_level_rank is None:
        diagnose("invalid_level_rank")
    high_value_ranks = {"SJ", "BJ", "A", "2"}
    if current_level_rank is not None:
        high_value_ranks.add(current_level_rank)

    facts_by_player = {player.player_id: player for player in card_belief.players}
    profiles: dict[object, _MutableProfile] = {
        player.player_id: _MutableProfile(player.player_id, player.relation)
        for player in card_belief.players
    }

    def profile_for(player_id: object) -> _MutableProfile:
        profile = profiles.get(player_id)
        fact = facts_by_player.get(player_id)
        if profile is not None and fact is not None and fact.relation != "unknown":
            return profile
        diagnose("unknown_player", player_id)
        if profile is None:
            profile = _MutableProfile(player_id, "unknown")
            profiles[player_id] = profile
        else:
            profile.relation = "unknown"
        return profile

    history = observation.get("history", {})
    if not isinstance(history, dict):
        diagnose("malformed_history")
        history = {}
    history_actions = history.get("actions", [])
    if not isinstance(history_actions, list):
        diagnose("malformed_history_actions")
        history_actions = []

    events: list[PublicBehaviorEvent] = []
    active_round: int | None = None
    last_valid_round: int | None = None
    current_table_action_index: int | None = None

    def card_list(raw_action: dict[str, object], field: str, action_index: int) -> tuple[str, ...]:
        value = raw_action.get(field, [])
        if value is None:
            return ()
        if not isinstance(value, list):
            diagnose(f"malformed_{field}", action_index)
            return ()
        return tuple(str(card) for card in value)

    for action_index, raw_action in enumerate(history_actions):
        if not isinstance(raw_action, dict):
            diagnose("malformed_action", action_index)
            continue
        player_id = raw_action.get("player_id")
        declared_pattern = raw_action.get("declared_pattern")
        if player_id is None or not isinstance(declared_pattern, str) or not declared_pattern:
            diagnose("malformed_action", action_index)
            continue

        step_value = raw_action.get("step_no")
        step_no = step_value if _is_non_negative_int(step_value) else None
        if step_no is None:
            diagnose("invalid_step_no", action_index)

        round_value = raw_action.get("round_no")
        round_no = round_value if _is_non_negative_int(round_value) else None
        valid_round = round_no is not None
        if not valid_round:
            diagnose("invalid_round_no", action_index)
        else:
            if last_valid_round is not None and round_no < last_valid_round:
                diagnose("round_regression", action_index)
            if active_round != round_no:
                active_round = round_no
                current_table_action_index = None
            last_valid_round = round_no

        profile = profile_for(player_id)
        declared_cards = card_list(raw_action, "declared_cards", action_index)
        carrier_cards = card_list(raw_action, "carrier_cards", action_index)
        declared_ranks: list[str] = []
        carrier_ranks: list[str] = []
        for card in declared_cards:
            rank = _declared_rank(card)
            if rank is None:
                diagnose("unknown_declared_token", f"{action_index}:{card}")
            else:
                declared_ranks.append(rank)
        for card in carrier_cards:
            rank = _carrier_rank(card)
            if rank is None:
                diagnose("unknown_carrier_token", f"{action_index}:{card}")
            else:
                carrier_ranks.append(rank)

        is_pass = declared_pattern == "pass"
        if is_pass:
            if declared_cards or carrier_cards:
                diagnose("pass_with_cards", action_index)
            event_type = "pass"
            response_to = current_table_action_index if valid_round else None
            if response_to is None:
                diagnose("orphan_pass", action_index)
        else:
            if "carrier_cards" not in raw_action:
                diagnose("missing_carrier_cards", action_index)
            elif not isinstance(raw_action.get("carrier_cards"), list):
                # ``card_list`` already produced the detailed malformed signal.
                pass
            elif not carrier_cards:
                diagnose("empty_carrier_cards", action_index)

            response_to = current_table_action_index if valid_round else None
            event_type = "follow" if response_to is not None else "lead"
            if valid_round:
                current_table_action_index = action_index

        event = PublicBehaviorEvent(
            action_index=action_index,
            step_no=step_no,
            round_no=round_no,
            player_id=player_id,
            relation=profile.relation,
            event_type=event_type,
            declared_pattern=declared_pattern,
            declared_cards=declared_cards,
            carrier_cards=carrier_cards,
            declared_ranks=tuple(declared_ranks),
            carrier_ranks=tuple(carrier_ranks),
            declaration_differs_from_carrier=(
                Counter(declared_ranks) != Counter(carrier_ranks)
            ),
            response_to_action_index=response_to,
        )
        events.append(event)

        profile.action_count += 1
        if event_type == "lead":
            profile.lead_count += 1
        elif event_type == "follow":
            profile.follow_count += 1
        else:
            profile.pass_count += 1
        if not is_pass:
            profile.pattern_counts[declared_pattern] += 1
            profile.played_cards.extend(carrier_cards)
            for rank in carrier_ranks:
                if rank in high_value_ranks:
                    profile.released_high_value_counts[rank] += 1

    for player_id, fact in facts_by_player.items():
        profile = profiles[player_id]
        if profile.pass_count != fact.pass_count:
            diagnose("belief_pass_mismatch", player_id)
        if tuple(profile.played_cards) != fact.played_cards:
            diagnose("belief_played_cards_mismatch", player_id)

    return PublicSignalState(
        phase=card_belief.phase,
        current_level_rank=current_level_rank,
        events=tuple(events),
        players=tuple(
            PlayerBehaviorProfile(
                player_id=profile.player_id,
                relation=profile.relation,
                action_count=profile.action_count,
                lead_count=profile.lead_count,
                follow_count=profile.follow_count,
                pass_count=profile.pass_count,
                pattern_counts=_freeze_counts(profile.pattern_counts),
                released_high_value_counts=_freeze_counts(
                    profile.released_high_value_counts
                ),
            )
            for profile in profiles.values()
        ),
        diagnostics=tuple(diagnostics),
    )
