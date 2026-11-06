"""Deterministic Outpost settlement in the nine DESIGN §4.4 phases.

No processes, clocks, random numbers, network or third-party dependencies.
All instructions are checked against the same start-of-turn state.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import asdict
from hashlib import sha256
import json

from arena.core.game import Event, Result, Warning
from .maps import parse_map
from .model import DIRECTIONS, Order, Orders, Player, State, Tower, Unit, distance
from .orders import parse_orders, target_at, target_owner, validate
from .rules import Rules

DEFAULT_LIMITS = {"TURN_CPU_MS": 100, "INIT_CPU_MS": 2000, "BANK_MS": 3000}


def event_key(event: Event) -> tuple:
    return event.phase, event.kind, -1 if event.audience is None else event.audience, event.values


class Outpost:
    id = "outpost"

    def __init__(self, limits: Mapping[str, int] | None = None):
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        if self.limits.keys() != DEFAULT_LIMITS.keys() or any(
            type(value) is not int or value <= 0 for value in self.limits.values()
        ):
            raise ValueError("limits must be positive integer milliseconds")

    def new_match(self, map_text: str, ruleset: dict, seeds: list[int]) -> State:
        board = parse_map(map_text)
        rules = Rules.from_dict(ruleset)
        if len(seeds) != len(board.bases) or any(type(seed) is not int or seed < 0 for seed in seeds):
            raise ValueError("one nonnegative integer seed per player is required")
        players = [Player(i, *pos, rules["BASE_HP"], rules["START_ENERGY"])
                   for i, pos in enumerate(board.bases)]
        state = State(board, rules, tuple(seeds), players,
                      ore={(x, y): n for x, y, n in board.initial_ore},
                      bank_ms=[self.limits["BANK_MS"] for _ in players])
        initial_positions = set()
        for player in players:
            # Local orientation reverses under a 180-degree rotation. Player ID
            # never determines the spatial tie break. See implementation notes.
            sign = 1 if (player.y, player.x) < (
                board.height - 1 - player.y, board.width - 1 - player.x
            ) else -1
            candidates = [(x, y) for y in range(board.height) for x in range(board.width)
                          if board.terrain((x, y)) == "."
                          and distance(player.pos, (x, y)) <= rules["SPAWN_RANGE"]]
            candidates.sort(key=lambda pos: (
                distance(player.pos, pos), sign * (pos[1] - player.y), sign * (pos[0] - player.x)
            ))
            selected = candidates[:rules["START_WORKERS"]]
            if len(selected) != rules["START_WORKERS"] or initial_positions.intersection(selected):
                raise ValueError("not enough disjoint initial worker positions")
            initial_positions.update(selected)
            for pos in selected:
                state.add_unit(player.id, "W", pos)
        return state

    @staticmethod
    def _check_player(state: State, player: int) -> None:
        if not 0 <= player < len(state.players):
            raise ValueError("unknown player")

    def init_message(self, state: State, player: int) -> list[str]:
        self._check_player(state, player)
        lines = ["HRW 1", f"RULESET {state.rules.name}", f"YOU {player}", f"SEED {state.seeds[player]}"]
        lines.extend(f"PARAM {key} {value}" for key, value in state.rules.values.items())
        lines.extend(f"LIMIT {key} {value}" for key, value in self.limits.items())
        lines.extend([f"MAP {state.map.width} {state.map.height}", *state.map.rows])
        lines.extend(f"ORE {x} {y} {n}" for x, y, n in state.map.initial_ore)
        return [*lines, "END"]

    def observation(self, state: State, player: int) -> list[str]:
        self._check_player(state, player)
        lines = [f"TURN {state.turn + 1}"]
        lines.extend(f"PLAYER {p.id} {p.energy} {p.score} {p.base_hp} {p.deposited}" for p in state.players)
        lines.extend(f"UNIT {u.id} {u.owner} {u.kind} {u.x} {u.y} {u.hp} {u.carry}"
                     for u in sorted(state.units.values(), key=lambda unit: unit.id))
        lines.extend(f"TOWER {t.x} {t.y} {t.owner} {t.hp}"
                     for _, t in sorted(state.towers.items()))
        lines.extend(f"ORE {x} {y} {n}" for (x, y), n in sorted(state.ore.items()) if n > 0)
        lines.extend("EVENT " + event.kind + " " + " ".join(map(str, event.values))
                     for event in state.last_events if event.audience in (None, player))
        return [*lines, f"BANK {state.bank_ms[player]}", "END"]

    def parse_orders(self, state: State, player: int, lines: list[str]) -> tuple[Orders, list[Warning]]:
        return parse_orders(state, player, lines)

    @staticmethod
    def _invalid(state: State, phase: int, player: int, line: int, code: str) -> None:
        state.players[player].warnings += 1
        state.last_events.append(Event(phase, "INVALID", (phase, line, code), player))

    def _living_orders(
        self, state: State, commands: list[tuple[int, Order]], op: str, phase: int
    ) -> Iterator[tuple[int, Order, Unit]]:
        for player, order in commands:
            if order.op != op:
                continue
            if order.unit_id is None or order.unit_id not in state.units:
                self._invalid(state, phase, player, order.line, "ACTOR_DEAD")
            else:
                yield player, order, state.units[order.unit_id]

    def step(self, state: State, orders: list[Orders]) -> list[Event]:
        if state.outcome is not None:
            raise ValueError("match already ended")
        if len(orders) != len(state.players):
            raise ValueError("one order packet per player is required")
        # Guard the trusted runner API before any mutation. Hostile text has
        # already been turned into warnings by parse_orders, never exceptions.
        occupied = state.occupied()
        commands = []
        for player, packet in enumerate(orders):
            if packet.player != player or packet.turn != state.turn + 1:
                raise ValueError("wrong player or stale order packet")
            seen = set()
            population = sum(u.owner == player for u in state.units.values())
            for order in packet.commands:
                slot = order.unit_id if order.unit_id is not None else order.op
                if slot in seen or validate(state, player, order, occupied, population) is not None:
                    raise ValueError("orders must be parsed against the current state")
                seen.add(slot)
                commands.append((player, order))
        state.turn += 1
        state.last_events = []
        for packet in orders:
            for warning in packet.warnings:
                self._invalid(state, 1, packet.player, warning.line, warning.code)
        self._attack(state, commands, occupied)
        alive = [player for player in state.players if player.base_hp > 0]
        if len(alive) < len(state.players):
            self._finish(state, alive[0].id if len(alive) == 1 else None,
                         "base_destroyed" if len(alive) == 1 else "mutual_base_destroyed")
        else:
            self._spawn(state, commands)
            self._move(state, commands)
            self._mine(state, commands)
            self._deposit(state)
            self._build(state, commands)
            self._regenerate(state)
            for tower in state.towers.values():
                state.players[tower.owner].score += state.rules["TOWER_POINTS"]
            if state.turn >= state.rules["TURNS"]:
                self._turn_limit(state)
        state.last_events.sort(key=event_key)
        return list(state.last_events)

    def _attack(self, state: State, commands: list[tuple[int, Order]], occupied: dict) -> None:
        hits = defaultdict(list)
        targets = {}
        for player, order in commands:
            if order.op not in ("ATTACK", "FIRE"):
                continue
            target = target_at(state, order.pos, occupied)
            assert target is not None  # Validated at turn start.
            if isinstance(target, Unit):
                key = ("U", target.id)
            elif isinstance(target, Tower):
                key = ("T", target.x, target.y)
            else:
                key = ("B", target.id)
            targets[key] = target
            source = -1 if order.op == "FIRE" else order.unit_id
            assert source is not None
            damage = (state.rules["BASE_FIRE_DMG"] if order.op == "FIRE"
                      else state.rules.unit_value(state.units[source].kind, "DMG"))
            hits[key].append((player, source, damage))
        for key in sorted(hits):
            target = targets[key]
            contributions = hits[key]
            amount = sum(damage for _, _, damage in contributions)
            if isinstance(target, Player):
                target.base_hp = max(0, target.base_hp - amount)
                hp = target.base_hp
            else:
                target.hp = max(0, target.hp - amount)
                hp = target.hp
            owner = target_owner(target)
            uid = target.id if isinstance(target, Unit) else -1
            for player, source, damage in contributions:
                state.players[player].damage_dealt += damage
                state.last_events.append(Event(2, "DAMAGE", (
                    player, source, key[0], owner, uid, target.x, target.y, damage, hp
                )))
            if hp == 0:
                state.last_events.append(Event(2, "DEATH", (key[0], owner, uid, target.x, target.y)))
        # Remove only after every hit has landed; dead attackers still attack.
        state.units = {uid: unit for uid, unit in state.units.items() if unit.hp > 0}
        state.towers = {pos: tower for pos, tower in state.towers.items() if tower.hp > 0}

    def _spawn(self, state: State, commands: list[tuple[int, Order]]) -> None:
        by_cell = defaultdict(list)
        for player, order in commands:
            if order.op == "SPAWN":
                by_cell[order.pos].append((player, order))
        for pos, attempts in sorted(by_cell.items()):
            if len(attempts) > 1:
                for player, order in attempts:
                    self._invalid(state, 3, player, order.line, "SPAWN_CONTESTED")
                continue
            player, order = attempts[0]
            assert order.kind is not None
            state.players[player].energy -= state.rules.unit_value(order.kind, "COST")
            unit = state.add_unit(player, order.kind, pos)
            state.last_events.append(Event(3, "SPAWN", (
                unit.id, player, unit.kind, *pos, unit.hp
            )))

    def _move(self, state: State, commands: list[tuple[int, Order]]) -> None:
        moves = {}
        actors = {}
        for player, order, unit in self._living_orders(state, commands, "MOVE", 4):
            assert order.direction is not None
            dx, dy = DIRECTIONS[order.direction]
            target = (unit.x + dx, unit.y + dy)
            if state.map.terrain(target) != ".":
                self._invalid(state, 4, player, order.line, "MOVE_NOT_GROUND")
            else:
                moves[unit.id] = target
                actors[unit.id] = (player, order)
        destinations = defaultdict(list)
        for uid, target in moves.items():
            destinations[target].append(uid)
        failed = {uid: "MOVE_CONTESTED" for group in destinations.values() if len(group) > 1 for uid in group}
        occupied = state.occupied()
        # Contested destinations have already failed; they do not create swaps.
        for uid, target in moves.items():
            other = occupied.get(target)
            if (uid not in failed and other is not None and other.id not in failed
                    and moves.get(other.id) == state.units[uid].pos):
                failed[uid] = failed[other.id] = "MOVE_SWAP"
        active = {uid: pos for uid, pos in moves.items() if uid not in failed}
        while True:
            blocked = [uid for uid, pos in active.items()
                       if pos in occupied and occupied[pos].id not in active]
            if not blocked:
                break
            for uid in blocked:
                failed[uid] = "MOVE_BLOCKED"
                del active[uid]
        for uid, code in sorted(failed.items()):
            player, order = actors[uid]
            self._invalid(state, 4, player, order.line, code)
        for uid, (x, y) in active.items():
            state.units[uid].x, state.units[uid].y = x, y

    def _mine(self, state: State, commands: list[tuple[int, Order]]) -> None:
        groups = defaultdict(list)
        for _, order, unit in self._living_orders(state, commands, "MINE", 5):
            want = min(state.rules["MINE_RATE"], state.rules["CARRY_MAX"] - unit.carry)
            groups[order.pos].append((unit, want))
        for pos, requests in groups.items():
            stock = state.ore[pos]
            if sum(want for _, want in requests) <= stock:
                for unit, want in requests:
                    unit.carry += want
                    state.ore[pos] -= want
            else:
                share = stock // len(requests)
                for unit, want in requests:
                    unit.carry += min(want, share)
                state.ore[pos] = 0  # All remainder is discarded, even capacity-limited shares.

    @staticmethod
    def _deposit(state: State) -> None:
        depots = defaultdict(list)
        for player in state.players:
            depots[player.id].append(player.pos)
        for tower in state.towers.values():
            depots[tower.owner].append(tower.pos)
        for unit in state.units.values():
            if unit.kind == "W" and unit.carry and any(
                distance(unit.pos, pos) == 1 for pos in depots[unit.owner]
            ):
                owner = state.players[unit.owner]
                owner.energy += unit.carry
                owner.deposited += unit.carry
                state.last_events.append(Event(6, "DEPOSIT", (unit.id, unit.owner, unit.carry)))
                unit.carry = 0

    def _build(self, state: State, commands: list[tuple[int, Order]]) -> None:
        groups = defaultdict(list)
        for player, order, unit in self._living_orders(state, commands, "BUILD", 7):
            groups[order.pos].append((player, order, unit))
        selected = []
        for pos, attempts in sorted(groups.items()):
            if len({player for player, _, _ in attempts}) > 1:
                for player, order, _ in attempts:
                    self._invalid(state, 7, player, order.line, "BUILD_CONTESTED")
                continue
            attempts.sort(key=lambda attempt: attempt[2].id)
            selected.append(attempts[0])
            for player, order, _ in attempts[1:]:
                self._invalid(state, 7, player, order.line, "BUILD_REDUNDANT")
        for player, order, unit in sorted(selected, key=lambda attempt: (attempt[0], attempt[2].id)):
            owner = state.players[player]
            if owner.energy < state.rules["TOWER_COST"]:
                self._invalid(state, 7, player, order.line, "NO_ENERGY")
                continue
            owner.energy -= state.rules["TOWER_COST"]
            x, y = order.pos
            tower = Tower(player, x, y, state.rules["TOWER_HP"])
            state.towers[order.pos] = tower
            state.last_events.append(Event(7, "BUILD", (tower.x, tower.y, player, tower.hp)))

    @staticmethod
    def _regenerate(state: State) -> None:
        for unit in state.units.values():
            if distance(unit.pos, state.players[unit.owner].pos) <= state.rules["REGEN_RANGE"]:
                unit.hp = min(state.rules.unit_value(unit.kind, "HP"), unit.hp + state.rules["REGEN_HP"])

    @staticmethod
    def _finish(state: State, winner: int | None, reason: str) -> None:
        state.outcome = Result(winner, reason, state.turn, tuple(p.score for p in state.players),
                               tuple(p.deposited for p in state.players), tuple(p.base_hp for p in state.players))

    def _turn_limit(self, state: State) -> None:
        candidates = list(state.players)
        for field, reason in (("score", "turn_limit_score"), ("deposited", "turn_limit_deposit"),
                              ("base_hp", "turn_limit_hp")):
            best = max(getattr(p, field) for p in candidates)
            candidates = [p for p in candidates if getattr(p, field) == best]
            if len(candidates) == 1:
                self._finish(state, candidates[0].id, reason)
                return
        self._finish(state, None, "turn_limit_draw")

    @staticmethod
    def result(state: State) -> Result | None:
        return state.outcome

    @staticmethod
    def snapshot(state: State) -> dict:
        """Canonical semantic state; runtime BANK values are deliberately excluded."""
        return {
            "game": "outpost", "stateSchema": 1, "ruleset": state.rules.name,
            "params": dict(state.rules.values), "map": asdict(state.map),
            "seeds": state.seeds, "turn": state.turn,
            "players": [asdict(p) for p in state.players],
            "units": [asdict(u) for _, u in sorted(state.units.items())],
            "towers": [asdict(t) for _, t in sorted(state.towers.items())],
            "ore": [(x, y, n) for (x, y), n in sorted(state.ore.items())],
            "events": [asdict(e) for e in sorted(state.last_events, key=event_key)],
            "result": None if state.outcome is None else asdict(state.outcome),
        }

    def state_hash(self, state: State) -> str:
        payload = json.dumps(self.snapshot(state), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return sha256(payload.encode("ascii")).hexdigest()[:16]

    @staticmethod
    def render(state: State) -> str:
        board = [list(row) for row in state.map.rows]
        for tower in state.towers.values():
            board[tower.y][tower.x] = "T" if tower.owner == 0 else "t"
        for unit in state.units.values():
            board[unit.y][unit.x] = unit.kind if unit.owner == 0 else unit.kind.lower()
        header = [f"TURN {state.turn}"]
        header.extend(f"P{p.id} energy={p.energy} score={p.score} hp={p.base_hp} deposited={p.deposited}"
                      for p in state.players)
        return "\n".join([*header, *("".join(row) for row in board)])
