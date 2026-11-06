"""Bounded, side-effect-free line parsing and start-of-turn validation."""
from __future__ import annotations

from arena.core.game import Warning
from .model import DIRECTIONS, Order, Orders, Player, State, Tower, Unit, distance
from .rules import UNIT_TYPES

MAX_LINE_BYTES = 256
MAX_TURN_LINES = 1000
MAX_TURN_BYTES = 64 * 1024


def integer(text: str) -> int:
    digits = text[1:] if text.startswith(("+", "-")) else text
    if not digits or not digits.isascii() or not digits.isdecimal():
        raise ValueError("expected decimal integer")
    return int(text)


def decode(parts: list[str], line: int) -> Order:
    op = parts[0]
    if op == "MOVE" and len(parts) == 3:
        return Order(op, unit_id=integer(parts[1]), direction=parts[2], line=line)
    if op in ("ATTACK", "MINE", "BUILD") and len(parts) == 4:
        return Order(op, unit_id=integer(parts[1]), x=integer(parts[2]),
                     y=integer(parts[3]), line=line)
    if op == "SPAWN" and len(parts) == 4:
        return Order(op, kind=parts[1], x=integer(parts[2]), y=integer(parts[3]), line=line)
    if op == "FIRE" and len(parts) == 3:
        return Order(op, x=integer(parts[1]), y=integer(parts[2]), line=line)
    raise ValueError("unknown command or wrong field count")


def target_at(state: State, pos: tuple[int, int], occupied: dict) -> Unit | Tower | Player | None:
    if pos in occupied:
        return occupied[pos]
    if pos in state.towers:
        return state.towers[pos]
    return next((player for player in state.players if player.pos == pos), None)


def target_owner(target: Unit | Tower | Player) -> int:
    return target.id if isinstance(target, Player) else target.owner


def validate(state: State, player: int, order: Order, occupied: dict, population: int) -> str | None:
    rules = state.rules
    owner = state.players[player]
    if order.unit_id is not None:
        unit = state.units.get(order.unit_id)
        if unit is None or unit.owner != player:
            return "NOT_OWN_UNIT"
        if order.op == "MOVE":
            return None if order.direction in DIRECTIONS else "BAD_DIRECTION"
        if distance(unit.pos, order.pos) != 1:
            return "NOT_ADJACENT"
        if order.op == "ATTACK":
            target = target_at(state, order.pos, occupied)
            if target is None or target_owner(target) == player:
                return "NOT_ENEMY_TARGET"
        elif order.op == "MINE":
            if not UNIT_TYPES[unit.kind].can_mine:
                return "CANNOT_MINE"
            if state.ore.get(order.pos, 0) <= 0:
                return "NO_ORE"
            if unit.carry >= rules["CARRY_MAX"]:
                return "CARRY_FULL"
        elif order.op == "BUILD":
            if not UNIT_TYPES[unit.kind].can_build:
                return "CANNOT_BUILD"
            if state.map.terrain(order.pos) != "S" or order.pos in state.towers:
                return "NOT_EMPTY_SITE"
        else:
            return "BAD_COMMAND"
        return None
    if order.op == "SPAWN":
        if order.kind is None or order.kind not in UNIT_TYPES:
            return "BAD_UNIT_TYPE"
        if state.map.terrain(order.pos) != "." or order.pos in occupied:
            return "NOT_EMPTY_GROUND"
        if distance(owner.pos, order.pos) > rules["SPAWN_RANGE"]:
            return "OUT_OF_RANGE"
        if population >= rules["POP_CAP"]:
            return "POP_CAP"
        if owner.energy < rules.unit_value(order.kind, "COST"):
            return "NO_ENERGY"
        return None
    if order.op == "FIRE":
        target = occupied.get(order.pos)
        if target is None or target.owner == player:
            return "NOT_ENEMY_UNIT"
        if distance(owner.pos, order.pos) > rules["BASE_FIRE_RANGE"]:
            return "OUT_OF_RANGE"
        return None
    return "BAD_COMMAND"


def parse_orders(state: State, player: int, lines: list[str]) -> tuple[Orders, list[Warning]]:
    if not 0 <= player < len(state.players):
        raise ValueError("unknown player")
    occupied = state.occupied()
    population = sum(unit.owner == player for unit in state.units.values())
    seen: set[int | str] = set()
    commands = []
    warnings = []
    total_bytes = 0

    def warn(line: int, code: str) -> None:
        warnings.append(Warning(player, line, code))

    for number, raw in enumerate(lines, 1):
        if number > MAX_TURN_LINES:
            warn(number, "TOO_MANY_LINES")
            break
        # Avoid allocating an arbitrarily large encoded copy. The stream reader
        # will enforce its own bounds before handing strings to this function.
        if len(raw) > MAX_TURN_BYTES:
            warn(number, "TOO_MANY_BYTES")
            break
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError:
            total_bytes += len(raw) + 1
            warn(number, "BAD_UTF8")
            if total_bytes > MAX_TURN_BYTES:
                warn(number, "TOO_MANY_BYTES")
                break
            continue
        total_bytes += len(encoded) + (0 if raw.endswith("\n") else 1)
        if total_bytes > MAX_TURN_BYTES:
            warn(number, "TOO_MANY_BYTES")
            break
        # Only the physical line terminator is removed; embedded newlines fail.
        text = raw.removesuffix("\n").removesuffix("\r")
        if len(text.encode("utf-8")) > MAX_LINE_BYTES:
            warn(number, "LINE_TOO_LONG")
            continue
        if "\n" in text or "\r" in text or "\x00" in text or "\ufffd" in text:
            warn(number, "BAD_TEXT")
            continue
        parts = text.split()
        if not parts:
            continue
        if parts == ["END"]:
            break
        try:
            order = decode(parts, number)
        except ValueError:
            warn(number, "BAD_SYNTAX")
            continue
        # The first well-formed command referring to one's own live unit (or
        # own base slot) claims that slot, even if semantic validation fails.
        if order.unit_id is not None:
            unit = state.units.get(order.unit_id)
            if unit is None or unit.owner != player:
                warn(number, "NOT_OWN_UNIT")
                continue
            slot: int | str = order.unit_id
        else:
            slot = order.op  # FIRE and SPAWN are independent base slots.
        if slot in seen:
            warn(number, "DUPLICATE")
            continue
        seen.add(slot)
        error = validate(state, player, order, occupied, population)
        if error is not None:
            warn(number, error)
        else:
            commands.append(order)
    return Orders(player, state.turn + 1, tuple(commands), tuple(warnings)), warnings
