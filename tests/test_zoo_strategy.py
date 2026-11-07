"""Small strategy regressions through the real SDK/compiler/runtime in bwrap.

Artificial states isolate decisions; they are not balance games. Every input,
reply and stderr is retained, including the pre-fix failures.
"""
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from uuid import uuid4

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, prepare
from arena.core.transport import Connection, exchange
from tests.helpers import fresh
from arena.games.outpost.model import Tower

ROOT = Path(__file__).resolve().parents[1]


class ZooStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT / "runs/development/zoo-strategy-tests" / uuid4().hex
        cls.root.mkdir(parents=True)
        cls.lease = CpuLease(1)
        cls.lease.__enter__()
        cls.addClassCleanup(cls.lease.__exit__, None, None, None)
        cls.launcher = Bubblewrap()
        cls.launcher.cpus = cls.lease.cpus
        cls.bot = prepare(ROOT / "bots/public/M-balanced", cls.root / "prepared",
                          cls.launcher, cls.lease.cpus[0])
        if cls.bot.compile_fault:
            raise AssertionError(cls.bot.compile_fault)

    def probe(self, game, state, name, count=1, income=0, opponent_lines=()):
        conn = Connection(self.bot, self.launcher, self.lease.cpus[0], 10)
        evidence = {"scope": "synthetic decision probe, not a balance match",
                    "incomeAddedBetweenTurns": income, "opponentLinesEachTurn": opponent_lines, "replies": []}
        inputs = [game.init_message(state, 0)]
        try:
            reply = exchange([conn], [inputs[0]], [2000], [2500], b"READY")[0]
            self.assertIsNone(reply.fault)
            for index in range(count):
                if index:
                    state.players[0].energy += income
                message = game.observation(state, 0)
                inputs.append(message)
                reply = exchange([conn], [message], [100], [1000])[0]
                evidence["replies"].append(reply.record())
                self.assertIsNone(reply.fault)
                orders, warnings = game.parse_orders(state, 0, reply.lines)
                self.assertEqual(warnings, [])
                game.step(state, [orders, game.parse_orders(state, 1, list(opponent_lines))[0]])
            return [r["lines"] for r in evidence["replies"]]
        finally:
            conn.close()
            evidence.update(inputs=inputs, finalPlayers=[asdict(p) for p in state.players],
                            finalTowers=[asdict(t) for t in state.towers.values()],
                            stderr=conn.stderr.decode(errors="replace"))
            (self.root / f"{name}.json").write_text(json.dumps(evidence, indent=2) + "\n")

    @staticmethod
    def budget_state(near=False):
        game, state = fresh()
        workers = [(6, 6), (6, 7), (6, 8), (6, 9), (7, 6), (7, 7),
                   (7, 8), (7, 9), (9, 8), (13, 8)]
        for p in workers:
            state.add_unit(0, "W", p)
        for p in ((10, 3), (11, 3), (12, 3)):
            state.add_unit(0, "S", p)
        for p in (((6, 2), (6, 3), (6, 4), (6, 5)) if near else
                  ((18, 18), (19, 18), (18, 19), (19, 19))):
            state.add_unit(1, "S", p)
        state.players[0].energy = 100
        state.turn = 80
        return game, state

    def test_opening_military_floor_precedes_tower_expansion(self):
        game, state = fresh()
        for p in ((3, 2), (3, 3), (3, 4), (4, 3), (4, 4), (9, 8)):
            state.add_unit(0, "W", p)
        state.add_unit(0, "S", (10, 3))
        for p in ((18, 18), (19, 18), (18, 19), (19, 19), (20, 19)):
            state.add_unit(1, "S", p)
        state.players[0].energy = 100
        state.turn = 25
        replies = self.probe(game, state, "opening-military-floor")
        self.assertTrue(any(line.startswith("SPAWN S") for line in replies[0]), replies)

    def test_one_forward_depot_is_enough_until_military_parity(self):
        game, state = self.budget_state()
        state.towers[(12, 8)] = Tower(0, 12, 8, 300)
        replies = self.probe(game, state, "one-depot-before-parity")
        self.assertTrue(any(line.startswith("SPAWN S") for line in replies[0]), replies)

    def production_state(self, worker_count):
        game, state = self.budget_state()
        workers = [u for u in state.units.values() if u.owner == 0 and u.kind == "W"]
        for u in workers[worker_count:]:
            del state.units[u.id]
        for p in ((10, 8), (12, 8), (13, 15), (11, 15)):
            state.towers[p] = Tower(0, *p, 300)
        return game, state

    def test_military_shortfall_precedes_extra_workers_once_economy_exists(self):
        game, state = self.production_state(6)
        replies = self.probe(game, state, "military-before-extra-workers")
        self.assertTrue(any(line.startswith("SPAWN S") for line in replies[0]), replies)

    def test_military_matching_still_rebuilds_a_minimal_economy(self):
        game, state = self.production_state(2)
        replies = self.probe(game, state, "minimum-economy")
        self.assertTrue(any(line.startswith("SPAWN W") for line in replies[0]), replies)

    def test_remote_army_does_not_spend_waiting_builders_reserve(self):
        game, state = self.budget_state()
        replies = self.probe(game, state, "remote-budget", count=2, income=50)
        self.assertFalse(any(line.startswith("SPAWN") for line in replies[0]), replies)
        self.assertTrue(any(line.startswith("BUILD") for line in replies[1]), replies)
        self.assertEqual(len(state.towers), 1)

    def test_repeated_contested_moves_eventually_yield_and_engage(self):
        game, state = fresh()
        soldier = state.add_unit(0, "S", (10, 2))
        opponent = state.add_unit(1, "S", (12, 2))
        state.players[0].energy = 0
        state.turn = 150
        replies = self.probe(game, state, "contested-center", count=8,
                             opponent_lines=(f"MOVE {opponent.id} W",))
        self.assertTrue(any(line.startswith(f"ATTACK {soldier.id} ")
                            for reply in replies for line in reply), replies)

    def test_occupied_enemy_base_ports_do_not_stop_distant_advance(self):
        game, state = fresh()
        soldier = state.add_unit(0, "S", (10, 2))
        for p in ((21, 20), (22, 21), (21, 22), (20, 21)):
            state.add_unit(1, "W", p)
        state.players[0].energy = 0
        state.turn = 150
        before = abs(soldier.x - 21) + abs(soldier.y - 21)
        replies = self.probe(game, state, "occupied-base-ports")
        self.assertTrue(any(line.startswith(f"MOVE {soldier.id} ") for line in replies[0]), replies)
        self.assertLess(abs(soldier.x - 21) + abs(soldier.y - 21), before)

    def test_distant_siege_force_is_not_recalled_for_a_home_intruder(self):
        game, state = fresh()
        state.add_unit(0, "S", (4, 3))  # The ordinary home guard.
        soldier = state.add_unit(0, "S", (19, 21))
        state.add_unit(1, "S", (6, 2))
        state.players[0].energy = 0
        state.turn = 150
        before = abs(soldier.x - 21) + abs(soldier.y - 21)
        replies = self.probe(game, state, "no-global-recall")
        self.assertTrue(any(line.startswith(f"MOVE {soldier.id} ") for line in replies[0]), replies)
        self.assertLess(abs(soldier.x - 21) + abs(soldier.y - 21), before)

    def test_nearby_reinforcements_still_intercept_a_home_intruder(self):
        game, state = fresh()
        state.add_unit(0, "S", (4, 3))
        soldier = state.add_unit(0, "S", (8, 2))
        state.add_unit(1, "S", (6, 2))
        state.players[0].energy = 0
        state.turn = 150
        self.probe(game, state, "nearby-interception")
        self.assertLess(abs(soldier.x - 6) + abs(soldier.y - 2), 2)

    def test_midfield_army_answers_a_home_threat_closer_than_enemy_base(self):
        game, state = fresh()
        state.add_unit(0, "S", (4, 3))
        soldier = state.add_unit(0, "S", (15, 8))
        state.add_unit(1, "S", (6, 2))
        state.players[0].energy = 0
        state.turn = 150
        self.probe(game, state, "midfield-interception")
        self.assertLess(abs(soldier.x - 6) + abs(soldier.y - 2), 15)

    def test_tower_deficit_switches_objective_without_disabling_local_clearing(self):
        for own_tower in (False, True):
            with self.subTest(own_tower=own_tower):
                game, state = fresh()
                soldier = state.add_unit(0, "S", (11, 10))
                state.towers[(10, 8)] = Tower(1, 10, 8, 300)
                if own_tower:
                    state.towers[(13, 15)] = Tower(0, 13, 15, 300)
                state.players[0].energy = 0
                state.turn = 150
                self.probe(game, state, f"tower-objective-{own_tower}")
                if own_tower:
                    self.assertLess(abs(soldier.x - 10) + abs(soldier.y - 8), 3)
                else:
                    self.assertLess(abs(soldier.x - 21) + abs(soldier.y - 21), 21)

    def test_nearby_army_can_override_tower_reserve(self):
        game, state = self.budget_state(near=True)
        replies = self.probe(game, state, "emergency-budget")
        self.assertTrue(any(line.startswith("SPAWN S") for line in replies[0]), replies)


if __name__ == "__main__":
    unittest.main()
