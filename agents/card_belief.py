"""Auditable public card-pool facts for Step J-A.

This module never reads engine state or infers hidden-card ownership.  It only
accounts for cards explicitly visible in an observation payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from agents.game_phase import GamePhaseContext, classify_game_phase


NORMAL_RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
SUITS = ("S", "H", "C", "D")
JOKER_RANKS = ("SJ", "BJ")
ALL_RANKS = NORMAL_RANKS + JOKER_RANKS


def build_double_deck_token_pool() -> dict[str, int]:
    """Return the exact 108-card token pool for two standard decks."""
    pool = {f"{rank}{suit}": 2 for rank in NORMAL_RANKS for suit in SUITS}
    pool.update({rank: 2 for rank in JOKER_RANKS})
    return pool


def _rank_pool_from_tokens(token_pool: Mapping[str, int]) -> dict[str, int]:
    counts = {rank: 0 for rank in ALL_RANKS}
    for token, count in token_pool.items():
        rank = token if token in JOKER_RANKS else token[:-1]
        counts[rank] += count
    return counts


@dataclass(frozen=True, slots=True)
class PlayerPublicBelief:
    """Public facts for one player; J-A deliberately contains no guesswork."""

    player_id: object
    team: str
    relation: str
    remaining_count: int
    finished: bool
    finish_rank: object | None
    played_cards: tuple[str, ...]
    pass_count: int
    confirmed_cards: tuple[str, ...] = ()
    likely_ranks: tuple[str, ...] = ()
    confidence: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "team": self.team,
            "relation": self.relation,
            "remaining_count": self.remaining_count,
            "finished": self.finished,
            "finish_rank": self.finish_rank,
            "played_cards": list(self.played_cards),
            "pass_count": self.pass_count,
            "confirmed_cards": list(self.confirmed_cards),
            "likely_ranks": list(self.likely_ranks),
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class CardBeliefState:
    """Immutable public card-pool accounting result for one observation."""

    phase: str
    external_unknown_count: int
    unseen_cards_by_token: Mapping[str, int]
    unseen_cards_by_rank: Mapping[str, int]
    players: tuple[PlayerPublicBelief, ...]
    diagnostics: tuple[str, ...]
    token_pool_exact: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "external_unknown_count": self.external_unknown_count,
            "unseen_cards_by_token": dict(self.unseen_cards_by_token),
            "unseen_cards_by_rank": dict(self.unseen_cards_by_rank),
            "players": [player.to_dict() for player in self.players],
            "diagnostics": list(self.diagnostics),
            "token_pool_exact": self.token_pool_exact,
        }


@dataclass(slots=True)
class _MutablePlayerFacts:
    player_id: object
    team: str
    relation: str
    remaining_count: int
    finished: bool
    finish_rank: object | None
    played_cards: list[str]
    pass_count: int = 0


def _coerce_count(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _card_rank(token: str) -> str | None:
    if token in JOKER_RANKS:
        return token
    if len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS:
        return token[:-1]
    if token in ALL_RANKS:
        return token
    return None


def _is_exact_token(token: str) -> bool:
    return token in JOKER_RANKS or (
        len(token) >= 2 and token[-1] in SUITS and token[:-1] in NORMAL_RANKS
    )


def _freeze_mapping(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(values))


def build_card_belief(
    observation: dict[str, object],
    phase_context: GamePhaseContext | None = None,
) -> CardBeliefState:
    """Build Step J-A public facts from an observation and optional phase context."""
    phase_context = phase_context or classify_game_phase(observation)
    token_pool = build_double_deck_token_pool()
    rank_pool = _rank_pool_from_tokens(token_pool)
    diagnostics: list[str] = []
    token_pool_exact = True

    my_info = dict(observation.get("my_info", {}))
    history = dict(observation.get("history", {}))
    other_players = list(observation.get("other_players", []))
    my_player_id = my_info.get("player_id")
    my_team = str(my_info.get("team", ""))

    player_facts: dict[object, _MutablePlayerFacts] = {}

    def add_player(
        player_id: object,
        *,
        team: str,
        relation: str,
        remaining_count: int,
        finished: bool,
        finish_rank: object | None,
    ) -> _MutablePlayerFacts:
        existing = player_facts.get(player_id)
        if existing is not None:
            return existing
        facts = _MutablePlayerFacts(
            player_id=player_id,
            team=team,
            relation=relation,
            remaining_count=remaining_count,
            finished=finished,
            finish_rank=finish_rank,
            played_cards=[],
        )
        player_facts[player_id] = facts
        return facts

    add_player(
        my_player_id,
        team=my_team,
        relation="self",
        remaining_count=_coerce_count(my_info.get("hand_count"), default=len(list(my_info.get("hand_cards", [])))),
        finished=False,
        finish_rank=None,
    )
    for raw_player in other_players:
        if not isinstance(raw_player, dict):
            diagnostics.append("malformed_other_player")
            continue
        team = str(raw_player.get("team", ""))
        add_player(
            raw_player.get("player_id"),
            team=team,
            relation="teammate" if team and team == my_team else "opponent",
            remaining_count=_coerce_count(raw_player.get("hand_count")),
            finished=bool(raw_player.get("finished", False)),
            finish_rank=raw_player.get("finish_rank"),
        )

    def player_for_history(player_id: object) -> _MutablePlayerFacts:
        existing = player_facts.get(player_id)
        if existing is not None:
            return existing
        diagnostics.append(f"unknown_player:{player_id}")
        return add_player(
            player_id,
            team="",
            relation="unknown",
            remaining_count=0,
            finished=False,
            finish_rank=None,
        )

    finish_order = history.get("finish_order", [])
    if isinstance(finish_order, list):
        for rank, player_id in enumerate(finish_order, start=1):
            facts = player_for_history(player_id)
            facts.finished = True
            facts.finish_rank = rank
    else:
        diagnostics.append("malformed_finish_order")

    def deduct(token: object, *, source: str) -> None:
        nonlocal token_pool_exact
        card = str(token)
        rank = _card_rank(card)
        if rank is None:
            diagnostics.append(f"unknown_token:{source}:{card}")
            token_pool_exact = False
            return

        if not _is_exact_token(card):
            token_pool_exact = False
            diagnostics.append(f"rank_only_fallback:{source}:{card}")
            if rank_pool[rank] <= 0:
                diagnostics.append(f"overdraw:{source}:{card}")
                return
            rank_pool[rank] -= 1
            return

        if token_pool[card] <= 0 or rank_pool[rank] <= 0:
            token_pool_exact = False
            diagnostics.append(f"overdraw:{source}:{card}")
            return
        token_pool[card] -= 1
        rank_pool[rank] -= 1

    my_hand_cards = my_info.get("hand_cards", [])
    if not isinstance(my_hand_cards, list):
        diagnostics.append("malformed_my_hand_cards")
        my_hand_cards = []
    for card in my_hand_cards:
        deduct(card, source="my_hand")

    history_actions = history.get("actions", [])
    if not isinstance(history_actions, list):
        diagnostics.append("malformed_history_actions")
        history_actions = []
    for index, raw_action in enumerate(history_actions):
        source = f"history[{index}]"
        if not isinstance(raw_action, dict):
            diagnostics.append(f"malformed_action:{source}")
            continue
        facts = player_for_history(raw_action.get("player_id"))
        if str(raw_action.get("declared_pattern", "")) == "pass":
            facts.pass_count += 1
            continue

        if "carrier_cards" in raw_action:
            cards = raw_action.get("carrier_cards")
            if not isinstance(cards, list):
                token_pool_exact = False
                diagnostics.append(f"malformed_carrier_cards:{source}")
                continue
            if not cards:
                token_pool_exact = False
                diagnostics.append(f"empty_carrier_cards:{source}")
                continue
        elif "declared_cards" in raw_action:
            cards = raw_action.get("declared_cards")
            if not isinstance(cards, list):
                token_pool_exact = False
                diagnostics.append(f"malformed_declared_cards:{source}")
                continue
            diagnostics.append(f"legacy_declared_cards:{source}")
        else:
            token_pool_exact = False
            diagnostics.append(f"missing_cards:{source}")
            continue

        for card in cards:
            token = str(card)
            facts.played_cards.append(token)
            deduct(token, source=source)

    unseen_count = sum(rank_pool.values())
    if unseen_count != phase_context.external_unknown_count:
        diagnostics.append(
            "external_count_mismatch:"
            f"unseen={unseen_count}:external={phase_context.external_unknown_count}"
        )

    players = tuple(
        PlayerPublicBelief(
            player_id=facts.player_id,
            team=facts.team,
            relation=facts.relation,
            remaining_count=facts.remaining_count,
            finished=facts.finished,
            finish_rank=facts.finish_rank,
            played_cards=tuple(facts.played_cards),
            pass_count=facts.pass_count,
        )
        for facts in player_facts.values()
    )
    return CardBeliefState(
        phase=phase_context.phase,
        external_unknown_count=phase_context.external_unknown_count,
        unseen_cards_by_token=_freeze_mapping(token_pool),
        unseen_cards_by_rank=_freeze_mapping(rank_pool),
        players=players,
        diagnostics=tuple(diagnostics),
        token_pool_exact=token_pool_exact,
    )
