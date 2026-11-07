"""HRW v1 I/O and geometry only; no strategy and no third-party dependencies."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import sys
from typing import TextIO

Position = tuple[int, int]
DIRECTIONS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


def neighbors(pos: Position):
    for direction, (dx, dy) in DIRECTIONS.items():
        yield direction, (pos[0] + dx, pos[1] + dy)


def distance(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def bfs(rows: list[str], starts, blocked=()) -> dict[Position, int]:
    """Multi-source ground distances. Occupancy is optional, not a policy."""
    forbidden = set(blocked)
    distances = {p: 0 for p in starts if 0 <= p[1] < len(rows)
                 and 0 <= p[0] < len(rows[p[1]]) and rows[p[1]][p[0]] == "." and p not in forbidden}
    queue = deque(distances)
    while queue:
        p = queue.popleft()
        for _, q in neighbors(p):
            x, y = q
            if (0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] == "."
                    and q not in forbidden and q not in distances):
                distances[q] = distances[p] + 1
                queue.append(q)
    return distances


@dataclass
class Setup:
    version: int = 0
    ruleset: str = ""
    you: int = -1
    seed: int = 0
    params: dict[str, int] = field(default_factory=dict)
    limits: dict[str, int] = field(default_factory=dict)
    rows: list[str] = field(default_factory=list)
    ore: dict[Position, int] = field(default_factory=dict)

    def bases(self) -> dict[int, Position]:
        return {int(c): (x, y) for y, row in enumerate(self.rows)
                for x, c in enumerate(row) if c.isascii() and c.isdigit()}


@dataclass
class Unit:
    id: int
    owner: int
    kind: str
    x: int
    y: int
    hp: int
    carry: int

    @property
    def pos(self) -> Position:
        return self.x, self.y


@dataclass
class Turn:
    number: int = 0
    players: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)
    units: list[Unit] = field(default_factory=list)
    towers: list[tuple[int, int, int, int]] = field(default_factory=list)
    ore: dict[Position, int] = field(default_factory=dict)
    events: list[list[str]] = field(default_factory=list)
    bank: int = 0


def message(stream: TextIO) -> list[str] | None:
    lines = []
    for raw in stream:
        text = raw.strip()
        if text == "END":
            return lines
        if text:
            lines.append(text)
    if lines:
        raise EOFError("message ended before END")
    return None


def read_setup(stream: TextIO | None = None) -> Setup:
    lines = message(stream or sys.stdin)
    if lines is None:
        raise EOFError("missing setup")
    setup = Setup()
    iterator = iter(lines)
    for line in iterator:
        p = line.split()
        match p[0]:
            case "HRW": setup.version = int(p[1])
            case "RULESET": setup.ruleset = p[1]
            case "YOU": setup.you = int(p[1])
            case "SEED": setup.seed = int(p[1])
            case "PARAM": setup.params[p[1]] = int(p[2])
            case "LIMIT": setup.limits[p[1]] = int(p[2])
            case "MAP": setup.rows = [next(iterator) for _ in range(int(p[2]))]
            case "ORE": setup.ore[int(p[1]), int(p[2])] = int(p[3])
    return setup


def read_turn(stream: TextIO | None = None) -> Turn | None:
    lines = message(stream or sys.stdin)
    if lines is None:
        return None
    turn = Turn()
    for line in lines:
        p = line.split()
        match p[0]:
            case "TURN": turn.number = int(p[1])
            case "PLAYER": turn.players[int(p[1])] = (int(p[2]), int(p[3]), int(p[4]), int(p[5]))
            case "UNIT": turn.units.append(Unit(int(p[1]), int(p[2]), p[3], *map(int, p[4:8])))
            case "TOWER": turn.towers.append((int(p[1]), int(p[2]), int(p[3]), int(p[4])))
            case "ORE": turn.ore[int(p[1]), int(p[2])] = int(p[3])
            case "EVENT": turn.events.append(p[1:])
            case "BANK": turn.bank = int(p[1])
    return turn


def ready(stream: TextIO | None = None) -> None:
    print("READY", file=stream or sys.stdout, flush=True)


def send(orders, stream: TextIO | None = None) -> None:
    print("\n".join([*orders, "END"]), file=stream or sys.stdout, flush=True)
