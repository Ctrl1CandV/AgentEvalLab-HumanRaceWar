"""Small synthetic rule fixtures, not public/calibration/grading map assets."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from arena.core.game import Event
from arena.games.outpost import Outpost
from arena.games.outpost.engine import event_key
from arena.games.outpost.model import State
from arena.games.outpost.orders import decode


# Pin historical rule examples independently of balance-tuned defaults.
# Default setup/parameters and the passing full-matrix replay have separate tests.
STARTING_RULES = json.loads((Path(__file__).parent / "fixtures/starting-rules.json").read_text())


def fixture_map(base=(2, 2), extra=(), size=24) -> str:
    cells = [["."] * size for _ in range(size)]
    features = [(0, 0, "#"), (8, 8, "O"), (10, 8, "S"), (12, 8, "S"), *extra]
    for x, y, kind in features:
        cells[y][x] = cells[size - 1 - y][size - 1 - x] = kind
    x, y = base
    cells[y][x] = "0"
    cells[size - 1 - y][size - 1 - x] = "1"
    rows = ["".join(row) for row in cells]
    ores = [f"ORE {x} {y} 400" for y, row in enumerate(rows) for x, kind in enumerate(row) if kind == "O"]
    return "\n".join([f"MAP {size} {size}", *rows, *ores, "END", ""])


def fresh(**kwargs):
    game = Outpost()
    state = game.new_match(fixture_map(**kwargs), STARTING_RULES, [17, 29])
    state.units.clear()
    return game, state


def settle(game: Outpost, state: State, *lines: list[str]):
    messages = list(lines) + [[] for _ in range(len(state.players) - len(lines))]
    return game.step(state, [game.parse_orders(state, p, text)[0] for p, text in enumerate(messages)])


def flip_id(uid: int) -> int:
    return uid if uid < 0 else (uid // 2) * 2 + 1 - uid % 2


def rotate_event(event: Event, width=24, height=24) -> Event:
    v = list(event.values)

    def n(index: int) -> int:
        value = event.values[index]
        assert isinstance(value, int), "event numeric field must be an integer"
        return value

    if event.kind == "DAMAGE":
        v[0], v[1], v[3], v[4] = 1 - n(0), flip_id(n(1)), 1 - n(3), flip_id(n(4))
        v[5], v[6] = width - 1 - n(5), height - 1 - n(6)
    elif event.kind == "DEATH":
        v[1], v[2] = 1 - n(1), flip_id(n(2))
        v[3], v[4] = width - 1 - n(3), height - 1 - n(4)
    elif event.kind == "SPAWN":
        v[0], v[1] = flip_id(n(0)), 1 - n(1)
        v[3], v[4] = width - 1 - n(3), height - 1 - n(4)
    elif event.kind == "BUILD":
        v[0], v[1], v[2] = width - 1 - n(0), height - 1 - n(1), 1 - n(2)
    elif event.kind == "DEPOSIT":
        v[0], v[1] = flip_id(n(0)), 1 - n(1)
    elif event.kind != "INVALID":
        raise AssertionError("unknown event type")
    return replace(event, values=tuple(v), audience=None if event.audience is None else 1 - event.audience)


def rotate_state(state: State) -> State:
    width, height = state.map.width, state.map.height
    transformed = State(state.map, state.rules, tuple(reversed(state.seeds)), [])
    transformed.players = [replace(p, id=1 - p.id, x=width - 1 - p.x, y=height - 1 - p.y)
                           for p in reversed(state.players)]
    transformed.units = {flip_id(uid): replace(u, id=flip_id(uid), owner=1 - u.owner,
                                             x=width - 1 - u.x, y=height - 1 - u.y)
                         for uid, u in state.units.items()}
    transformed.towers = {(width - 1 - x, height - 1 - y): replace(
        t, owner=1 - t.owner, x=width - 1 - x, y=height - 1 - y
    ) for (x, y), t in state.towers.items()}
    transformed.ore = {(width - 1 - x, height - 1 - y): n for (x, y), n in state.ore.items()}
    transformed.turn = state.turn
    transformed.bank_ms = list(reversed(state.bank_ms))
    transformed.last_events = sorted((rotate_event(e, width, height) for e in state.last_events), key=event_key)
    if state.outcome is not None:
        r = state.outcome
        transformed.outcome = replace(r, winner=None if r.winner is None else 1 - r.winner,
                                      scores=tuple(reversed(r.scores)), deposited=tuple(reversed(r.deposited)),
                                      base_hp=tuple(reversed(r.base_hp)))
    return transformed


def rotate_lines(lines: list[str], width=24, height=24) -> list[str]:
    result = []
    opposite = {"N": "S", "E": "W", "S": "N", "W": "E"}
    for number, line in enumerate(lines, 1):
        try:
            order = decode(line.split(), number)
        except (ValueError, IndexError):
            result.append(line)
            continue
        order = replace(order, unit_id=None if order.unit_id is None else flip_id(order.unit_id),
                        direction=None if order.direction is None else opposite.get(order.direction, order.direction),
                        x=None if order.x is None else width - 1 - order.x,
                        y=None if order.y is None else height - 1 - order.y)
        result.append(order.to_line())
    return result
