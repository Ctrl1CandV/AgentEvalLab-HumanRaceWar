"""Contracts shared by games, runners and replay consumers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar


@dataclass(frozen=True)
class Warning:
    player: int
    line: int
    code: str


@dataclass(frozen=True)
class Event:
    phase: int
    kind: str
    values: tuple[int | str, ...]
    audience: int | None = None  # None: public; otherwise visible only to this player.


@dataclass(frozen=True)
class Result:
    winner: int | None
    reason: str
    turns: int
    scores: tuple[int, ...]
    deposited: tuple[int, ...]
    base_hp: tuple[int, ...]


StateT = TypeVar("StateT")
OrdersT = TypeVar("OrdersT")


class Game(Protocol[StateT, OrdersT]):
    id: str

    def new_match(self, map_text: str, ruleset: dict, seeds: list[int]) -> StateT: ...
    def init_message(self, state: StateT, player: int) -> list[str]: ...
    def observation(self, state: StateT, player: int) -> list[str]: ...
    def parse_orders(
        self, state: StateT, player: int, lines: list[str]
    ) -> tuple[OrdersT, list[Warning]]: ...
    def step(self, state: StateT, orders: list[OrdersT]) -> list[Event]: ...
    def result(self, state: StateT) -> Result | None: ...
    def state_hash(self, state: StateT) -> str: ...
    def render(self, state: StateT) -> str: ...
