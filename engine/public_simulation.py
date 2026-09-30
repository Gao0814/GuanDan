"""Finite hypothetical continuations; never an endgame proof interface."""

from copy import deepcopy
from time import monotonic
from contextlib import contextmanager

from engine.public_endgame import _InvalidPosition, _SearchBudgetExceeded, _rebuild_public_game
from engine.rules import _simulation_budget


class SimulationBudget:
    """One shared work/time allowance for rebuilding and all continuations."""

    def __init__(self, deadline: float, max_work: int = 45000, cancelled=None) -> None:
        self.deadline = deadline
        self.max_work = max_work
        self.work = 0
        self.cancelled = cancelled

    def check(self) -> None:
        self.work += 1
        if (self.work > self.max_work or monotonic() >= self.deadline
                or (self.cancelled is not None and self.cancelled())):
            raise TimeoutError("simulation_budget")

    @contextmanager
    def scope(self):
        self.check()
        token = _simulation_budget.set(self)
        try:
            yield
            self.check()
        finally:
            _simulation_budget.reset(token)


class PublicSimulation:
    """Expose only each acting seat's public payload and engine-generated IDs."""

    def __init__(self, observation: dict, canonical_actions: list,
                 hypothetical_hands: dict, *, budget: SimulationBudget) -> None:
        self.__budget = budget
        with budget.scope():
            self.__game = _rebuild_public_game(
                observation, canonical_actions, hypothetical_hands, deadline=budget.deadline,
                max_cards=108, max_hand=27,
            )

    def fork(self) -> "PublicSimulation":
        self.__check()
        clone = object.__new__(PublicSimulation)
        clone.__budget = self.__budget
        clone.__game = deepcopy(self.__game)
        return clone

    def __check(self) -> None:
        self.__budget.check()

    def observe(self) -> dict:
        self.__check()
        with self.__budget.scope():
            result = self.__game.observe()
        self.__check()
        return result

    def legal_actions(self) -> list:
        self.__check()
        with self.__budget.scope():
            result = self.__game.legal_actions()
        self.__check()
        return result

    def step(self, action_id: int) -> dict:
        self.__check()
        with self.__budget.scope():
            result = self.__game.step(action_id)
        self.__check()
        return result


def rebuild_hypothetical_position(observation: dict, canonical_actions: list,
                                  hypothetical_hands: dict, *, budget: SimulationBudget) -> PublicSimulation:
    """Reject invalid public ledgers/roots; supplied hands remain hypotheses."""
    try:
        return PublicSimulation(observation, canonical_actions, hypothetical_hands, budget=budget)
    except _SearchBudgetExceeded as exc:
        raise TimeoutError("simulation_budget") from exc
    except _InvalidPosition as exc:
        raise ValueError("simulation_public_position_invalid") from exc
