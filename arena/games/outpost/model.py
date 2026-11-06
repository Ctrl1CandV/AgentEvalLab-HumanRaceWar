"""Integer-only mutable match state and immutable order records."""
from __future__ import annotations

from dataclasses import dataclass, field

from arena.core.game import Event, Result, Warning
from .rules import Rules

Position = tuple[int, int]
DIRECTIONS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


def distance(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass(frozen=True)
class Map:
    width: int
    height: int
    rows: tuple[str, ...]
    initial_ore: tuple[tuple[int, int, int], ...]
    bases: tuple[Position, ...]

    def terrain(self, pos: Position) -> str:
        x, y = pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return "#"
        return self.rows[y][x]


@dataclass
class Player:
    id: int
    x: int
    y: int
    base_hp: int
    energy: int
    score: int = 0
    deposited: int = 0
    next_serial: int = 0
    damage_dealt: int = 0  # Raw commanded damage, including overkill; not a frozen score.
    warnings: int = 0

    @property
    def pos(self) -> Position:
        return self.x, self.y


@dataclass
class Unit:
    id: int
    owner: int
    kind: str
    x: int
    y: int
    hp: int
    carry: int = 0

    @property
    def pos(self) -> Position:
        return self.x, self.y


@dataclass
class Tower:
    owner: int
    x: int
    y: int
    hp: int

    @property
    def pos(self) -> Position:
        return self.x, self.y


@dataclass(frozen=True)
class Order:
    op: str
    unit_id: int | None = None
    direction: str | None = None
    kind: str | None = None
    x: int | None = None
    y: int | None = None
    line: int = 0

    @property
    def pos(self) -> Position:
        assert self.x is not None and self.y is not None
        return self.x, self.y

    def to_line(self) -> str:
        if self.op == "MOVE":
            return f"MOVE {self.unit_id} {self.direction}"
        if self.op == "SPAWN":
            return f"SPAWN {self.kind} {self.x} {self.y}"
        if self.op == "FIRE":
            return f"FIRE {self.x} {self.y}"
        return f"{self.op} {self.unit_id} {self.x} {self.y}"


@dataclass(frozen=True)
class Orders:
    player: int
    turn: int
    commands: tuple[Order, ...]
    warnings: tuple[Warning, ...] = ()


@dataclass
class State:
    map: Map
    rules: Rules
    seeds: tuple[int, ...]
    players: list[Player]
    units: dict[int, Unit] = field(default_factory=dict)
    towers: dict[Position, Tower] = field(default_factory=dict)
    ore: dict[Position, int] = field(default_factory=dict)
    turn: int = 0  # Number of completed turns; the first observation is TURN 1.
    bank_ms: list[int] = field(default_factory=list)  # Runner-owned, excluded from rule hashes.
    last_events: list[Event] = field(default_factory=list)
    outcome: Result | None = None

    def add_unit(self, player: int, kind: str, pos: Position) -> Unit:
        owner = self.players[player]
        uid = owner.next_serial * len(self.players) + player
        owner.next_serial += 1
        unit = Unit(uid, player, kind, *pos, self.rules.unit_value(kind, "HP"))
        self.units[uid] = unit
        return unit

    def occupied(self) -> dict[Position, Unit]:
        return {unit.pos: unit for unit in self.units.values()}
