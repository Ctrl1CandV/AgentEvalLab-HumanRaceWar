from __future__ import annotations

from pathlib import Path
import json
import re
import unittest
from typing import MutableMapping, cast

from arena.games.outpost import Outpost
from arena.games.outpost.maps import map_text, parse_map
from arena.games.outpost.model import Tower, distance
from arena.games.outpost.rules import PARAMETERS, Rules
from tests.helpers import fixture_map, fresh, settle


class RuleCase(unittest.TestCase):
    def setUp(self):
        self.game, self.state = fresh()

    def unit(self, owner, pos, kind="W", hp=None, carry=0):
        unit = self.state.add_unit(owner, kind, pos)
        if hp is not None:
            unit.hp = hp
        unit.carry = carry
        return unit

    def play(self, a=(), b=()):
        return settle(self.game, self.state, list(a), list(b))

    def parse(self, lines, player=0):
        return self.game.parse_orders(self.state, player, list(lines))


class MapAndSetupTests(unittest.TestCase):
    def test_appendix_defaults_and_ranges(self):
        defaults = Rules.from_dict({})
        # Independent contract copied from DESIGN appendix A, not generated from code.
        expected = {
            "TURNS": 300, "START_ENERGY": 500, "START_WORKERS": 4, "POP_CAP": 40,
            "BASE_HP": 600, "BASE_FIRE_DMG": 10, "BASE_FIRE_RANGE": 2, "SPAWN_RANGE": 2,
            "REGEN_HP": 5, "REGEN_RANGE": 2, "WORKER_COST": 40, "WORKER_HP": 60,
            "WORKER_DMG": 10, "MINE_RATE": 10, "CARRY_MAX": 60, "SOLDIER_COST": 80,
            "SOLDIER_HP": 100, "SOLDIER_DMG": 20, "TOWER_COST": 150, "TOWER_HP": 300,
            "TOWER_POINTS": 1,
        }
        self.assertEqual(dict(defaults.values), expected)
        for name, (value, low, high) in PARAMETERS.items():
            self.assertEqual(defaults[name], value)
            self.assertEqual(Rules.from_dict({name: low})[name], low)
            self.assertEqual(Rules.from_dict({name: high})[name], high)
            for invalid in (low - 1, high + 1, True, 1.5, "100"):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    Rules.from_dict({name: invalid})
        with self.assertRaises(ValueError):
            Rules.from_dict({"UNDECLARED": 1})
        with self.assertRaises(TypeError):
            cast(MutableMapping[str, int], defaults.values)["TURNS"] = 200

    def test_rules_document_parameters_match_engine(self):
        text = (Path(__file__).resolve().parents[1] / "rules/rules.md").read_text(encoding="utf-8")
        documented = {}
        for name, number in re.findall(r"\b([A-Z][A-Z_]+)\s+(\d+)\b", text):
            if name in PARAMETERS:
                value = int(number)
                self.assertEqual(value, PARAMETERS[name][0], f"documented {name}")
                documented[name] = value
        self.assertEqual(documented, dict(Rules.from_dict({}).values))

    def test_frozen_defaults_match_the_actual_full_matrix_configuration(self):
        root = Path(__file__).resolve().parents[1]
        params = json.loads((root / "rules/standard-1.json").read_text())
        report = json.loads((root / "data/phase-a/matrices/zoo-standard-1-final.json").read_text())
        self.assertEqual(params, report["request"]["ruleset"])
        self.assertEqual(dict(Rules.from_dict({}).values), params)
        # Real replay/header comparison is retained in local Phase-A evidence.
        # A clean review checkout needs only the frozen batch configuration.

    def test_map_round_trip(self):
        board = parse_map(fixture_map())
        self.assertEqual(parse_map(map_text(board)), board)
        self.assertEqual(board.terrain((-1, 3)), "#")
        self.assertEqual(board.terrain((24, 3)), "#")
        self.assertEqual(board.terrain((8, 8)), "O")

    def test_map_rejects_configuration_errors(self):
        text = fixture_map()
        rows = text.splitlines()
        cases = [text.replace("MAP 24 24", "MAP 23 24"),
                 text.replace("MAP 24 24", "MAP 41 24"),
                 text.replace("MAP 24 24", "BAD 24 24"),
                 text.replace("ORE 8 8 400", "ORE 8 8 -1"),
                 text.replace("ORE 8 8 400", "ORE 8 8 399"),
                 text.replace("ORE 8 8 400", "ORE 7 8 400"),
                 text.replace("ORE 8 8 400\n", ""),
                 text.replace("END", "ORE 8 8 400\nEND"),
                 text.replace("END", ""), text + "stray\n",
                 text.replace("0", "1", 1), text.replace("#", "?", 1),
                 text.replace("#", ".", 1), "\n".join([rows[0], *rows[2:]])]
        for index, value in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                parse_map(value)

    def test_initial_units_and_defaults(self):
        game = Outpost()
        state = game.new_match(fixture_map(), {}, [17, 29])
        self.assertEqual(state.turn, 0)
        self.assertIsNone(game.result(state))
        self.assertEqual(len(state.units), 8)
        self.assertEqual([p.energy for p in state.players], [500, 500])
        self.assertEqual([p.base_hp for p in state.players], [600, 600])
        self.assertEqual([u.pos for u in state.units.values()],
                         [(2, 1), (1, 2), (3, 2), (2, 3), (21, 22), (22, 21), (20, 21), (21, 20)])
        for unit in state.units.values():
            self.assertEqual(unit.id % 2, unit.owner)
            self.assertEqual((unit.kind, unit.hp, unit.carry), ("W", 60, 0))
            self.assertLessEqual(distance(unit.pos, state.players[unit.owner].pos), 2)

    def test_start_workers_range_and_seed_validation(self):
        game = Outpost()
        state = game.new_match(fixture_map(), {"START_WORKERS": 4, "SPAWN_RANGE": 1}, [0, 1])
        self.assertEqual(len(state.units), 8)
        for seeds in ([1], [1, 2, 3], [-1, 0], [True, 0]):
            with self.assertRaises(ValueError):
                game.new_match(fixture_map(), {}, seeds)

    def test_initial_placement_rejects_insufficient_ground(self):
        text = fixture_map(extra=((1, 2, "#"), (2, 1, "#"), (3, 2, "#"), (2, 3, "#")))
        with self.assertRaises(ValueError):
            Outpost().new_match(text, {"SPAWN_RANGE": 1}, [0, 0])


class AttackTests(RuleCase):
    def test_simultaneous_lethal_attacks(self):
        a = self.unit(0, (6, 6), "S", hp=20)
        b = self.unit(1, (7, 6), "S", hp=20)
        events = self.play([f"ATTACK {a.id} 7 6"], [f"ATTACK {b.id} 6 6"])
        self.assertFalse(self.state.units)
        self.assertEqual(sum(e.kind == "DEATH" for e in events), 2)
        self.assertEqual([p.damage_dealt for p in self.state.players], [20, 20])

    def test_focus_fire_aggregates_damage_and_records_overkill(self):
        a = self.unit(0, (6, 6), "S")
        c = self.unit(0, (7, 5), "S")
        b = self.unit(1, (7, 6), hp=30)
        events = self.play([f"ATTACK {a.id} 7 6", f"ATTACK {c.id} 7 6"])
        self.assertNotIn(b.id, self.state.units)
        self.assertEqual(self.state.players[0].damage_dealt, 40)
        self.assertEqual(sum(e.kind == "DEATH" for e in events), 1)
        self.assertEqual([e.values[-1] for e in events if e.kind == "DAMAGE"], [0, 0])

    def test_attack_hits_start_position_before_move(self):
        a = self.unit(0, (6, 6), "S")
        b = self.unit(1, (7, 6), "S")
        self.play([f"ATTACK {a.id} 7 6"], [f"MOVE {b.id} E"])
        self.assertEqual((b.hp, b.pos), (80, (8, 6)))

    def test_killed_actor_cannot_move_mine_or_build(self):
        for command, pos, target in (("MOVE {id} S", (7, 8), (7, 7)),
                                      ("MINE {id} 8 8", (7, 8), (7, 7)),
                                      ("BUILD {id} 10 8", (9, 8), (9, 7))):
            with self.subTest(command=command):
                self.setUp()
                victim = self.unit(0, pos, hp=20)
                attacker = self.unit(1, target, "S")
                self.play([command.format(id=victim.id)], [f"ATTACK {attacker.id} {pos[0]} {pos[1]}"])
                self.assertNotIn(victim.id, self.state.units)
                self.assertEqual(self.state.ore[8, 8], 400)
                self.assertFalse(self.state.towers)
                self.assertIn("ACTOR_DEAD", [e.values[-1] for e in self.state.last_events if e.kind == "INVALID"])

    def test_base_fire_can_accompany_spawn(self):
        enemy = self.unit(1, (4, 2), "S")
        self.play(["FIRE 4 2", "SPAWN W 3 2"])
        self.assertEqual(enemy.hp, 90)
        self.assertEqual(self.state.players[0].energy, 250)
        self.assertEqual(sum(u.owner == 0 for u in self.state.units.values()), 1)

    def test_fire_and_attack_sum_and_base_fire_is_not_automatic(self):
        attacker = self.unit(0, (3, 2))
        enemy = self.unit(1, (4, 2), "S")
        self.play([f"ATTACK {attacker.id} 4 2", "FIRE 4 2"])
        self.assertEqual(enemy.hp, 85)
        self.play()
        self.assertEqual(enemy.hp, 85)

    def test_base_death_ends_before_production_movement_deposit_and_scoring(self):
        attacker = self.unit(0, (20, 21), "S")
        carrier = self.unit(1, (22, 21), carry=30)
        self.state.towers[10, 8] = Tower(0, 10, 8, 300)
        self.state.players[1].base_hp = 20
        self.play([f"ATTACK {attacker.id} 21 21", "SPAWN S 3 2"], [f"MOVE {carrier.id} N"])
        result = self.game.result(self.state)
        assert result is not None
        self.assertEqual((result.winner, result.reason, result.turns), (0, "base_destroyed", 1))
        self.assertEqual(self.state.players[0].energy, 300)
        self.assertEqual(self.state.players[0].score, 0)
        self.assertEqual((carrier.pos, carrier.carry), ((22, 21), 30))
        self.assertEqual(self.state.players[1].deposited, 0)

    def test_simultaneous_base_death_is_draw_and_bases_still_fire(self):
        a = self.unit(0, (20, 21), "S")
        b = self.unit(1, (3, 2), "S")
        for p in self.state.players:
            p.base_hp = 20
        self.play([f"ATTACK {a.id} 21 21", "FIRE 3 2"], [f"ATTACK {b.id} 2 2", "FIRE 20 21"])
        result = self.game.result(self.state)
        assert result is not None
        self.assertEqual((result.winner, result.reason), (None, "mutual_base_destroyed"))
        self.assertEqual((a.hp, b.hp), (90, 90))

    def test_destroyed_tower_becomes_empty_but_cannot_be_rebuilt_this_turn(self):
        self.state.towers[10, 8] = Tower(1, 10, 8, 20)
        attacker = self.unit(0, (9, 8), "S")
        builder = self.unit(0, (10, 7))
        self.play([f"ATTACK {attacker.id} 10 8", f"BUILD {builder.id} 10 8"])
        self.assertNotIn((10, 8), self.state.towers)
        self.assertEqual(self.state.map.terrain((10, 8)), "S")
        self.play([f"BUILD {builder.id} 10 8"])
        self.assertEqual(self.state.towers[10, 8].owner, 0)

    def test_only_manhattan_adjacent_enemy_targets_are_legal(self):
        unit = self.unit(0, (6, 6))
        self.unit(0, (7, 6))
        self.unit(1, (7, 7))
        for x, y in ((7, 6), (7, 7), (5, 6), (-100, 6)):
            orders, warnings = self.parse([f"ATTACK {unit.id} {x} {y}"])
            self.assertFalse(orders.commands)
            self.assertEqual(len(warnings), 1)


class SpawnTests(RuleCase):
    def test_spawn_cost_types_and_hp(self):
        self.play(["SPAWN W 3 2"])
        self.play(["SPAWN S 2 3"])
        self.assertEqual(self.state.players[0].energy, 150)
        self.assertEqual(sorted((u.kind, u.hp) for u in self.state.units.values()), [("S", 100), ("W", 40)])

    def test_spawn_shared_target_both_fail_without_cost(self):
        self.game, self.state = fresh(base=(10, 11))
        self.play(["SPAWN W 12 11"], ["SPAWN S 12 11"])
        self.assertFalse(self.state.units)
        self.assertEqual([p.energy for p in self.state.players], [300, 300])
        self.assertEqual([p.next_serial for p in self.state.players], [2, 2])

    def test_spawn_rejects_start_occupied_even_if_unit_moves(self):
        unit = self.unit(0, (3, 2))
        self.play([f"MOVE {unit.id} E", "SPAWN W 3 2"])
        self.assertEqual(len(self.state.units), 1)
        self.assertEqual(unit.pos, (4, 2))
        self.assertEqual(self.state.players[0].energy, 300)

    def test_spawn_rejects_start_occupied_even_if_unit_dies(self):
        enemy = self.unit(1, (3, 2), hp=10)
        self.play(["FIRE 3 2", "SPAWN W 3 2"])
        self.assertNotIn(enemy.id, self.state.units)
        self.assertFalse(self.state.units)
        self.assertEqual(self.state.players[0].energy, 300)

    def test_spawn_cannot_use_later_deposit(self):
        self.state.players[0].energy = 49
        self.unit(0, (2, 3), carry=60)
        self.play(["SPAWN W 3 2"])
        self.assertEqual(len(self.state.units), 1)
        self.assertEqual(self.state.players[0].energy, 109)

    def test_spawn_validation(self):
        for line in ("SPAWN X 3 2", "SPAWN W 2 2", "SPAWN W 5 2", "SPAWN W -1 2", "SPAWN W 8 8"):
            with self.subTest(line=line):
                orders, warnings = self.parse([line])
                self.assertFalse(orders.commands)
                self.assertEqual(len(warnings), 1)
        self.state.players[0].energy = 99
        self.assertEqual(self.parse(["SPAWN S 3 2"])[1][0].code, "NO_ENERGY")

    def test_population_cap_is_start_of_turn(self):
        for y in range(5, 7):
            for x in range(1, 21):
                self.unit(0, (x, y))
        victim = next(iter(self.state.units.values()))
        victim.hp = 20
        enemy = self.unit(1, (victim.x, victim.y - 1), "S")
        self.play(["SPAWN W 3 2"], [f"ATTACK {enemy.id} {victim.x} {victim.y}"])
        self.assertEqual(sum(u.owner == 0 for u in self.state.units.values()), 39)
        self.assertEqual(self.state.players[0].energy, 300)

    def test_unit_ids_never_reused_and_other_players_spawns_do_not_change_local_order(self):
        self.play(["SPAWN W 3 2"], ["SPAWN W 20 21"])
        first_ids = set(self.state.units)
        self.state.units.clear()
        self.play(["SPAWN W 3 2"])
        self.assertFalse(first_ids.intersection(self.state.units))
        self.assertTrue(all(uid % 2 == 0 for uid in self.state.units))


class MovementTests(RuleCase):
    def test_move_cardinals_and_no_order_means_stay(self):
        unit = self.unit(0, (6, 6))
        for direction, pos in (("N", (6, 5)), ("E", (7, 5)), ("S", (7, 6)), ("W", (6, 6))):
            self.play([f"MOVE {unit.id} {direction}"])
            self.assertEqual(unit.pos, pos)
        self.play()
        self.assertEqual(unit.pos, (6, 6))

    def test_all_non_ground_and_off_map_are_blocked(self):
        for pos, direction in (((0, 1), "N"), ((7, 8), "E"), ((9, 8), "E"), ((3, 2), "W"), ((0, 3), "W")):
            with self.subTest(pos=pos):
                self.setUp()
                unit = self.unit(0, pos)
                self.play([f"MOVE {unit.id} {direction}"])
                self.assertEqual(unit.pos, pos)

    def test_tower_and_depleted_ore_remain_impassable(self):
        self.state.ore[8, 8] = 0
        self.state.towers[10, 8] = Tower(0, 10, 8, 300)
        a = self.unit(0, (7, 8))
        b = self.unit(0, (10, 7))
        self.play([f"MOVE {a.id} E", f"MOVE {b.id} S"])
        self.assertEqual((a.pos, b.pos), ((7, 8), (10, 7)))

    def test_contested_destination_fails_for_all_owners(self):
        a = self.unit(0, (5, 6))
        b = self.unit(0, (6, 5))
        c = self.unit(1, (7, 6))
        self.play([f"MOVE {a.id} E", f"MOVE {b.id} S"], [f"MOVE {c.id} W"])
        self.assertEqual((a.pos, b.pos, c.pos), ((5, 6), (6, 5), (7, 6)))

    def test_two_unit_swap_fails(self):
        a = self.unit(0, (6, 6))
        b = self.unit(1, (7, 6))
        self.play([f"MOVE {a.id} E"], [f"MOVE {b.id} W"])
        self.assertEqual((a.pos, b.pos), ((6, 6), (7, 6)))

    def test_failure_propagates_through_entire_chain(self):
        units = [self.unit(0, (x, 6)) for x in range(3, 8)]
        self.play([f"MOVE {u.id} E" for u in units[:-1]])
        self.assertEqual([u.pos for u in units], [(x, 6) for x in range(3, 8)])

    def test_contested_swap_then_blockage_uses_ordered_phases(self):
        a = self.unit(0, (6, 6))
        b = self.unit(1, (7, 6))
        c = self.unit(0, (7, 5))
        self.play([f"MOVE {a.id} E", f"MOVE {c.id} S"], [f"MOVE {b.id} W"])
        codes = [e.values[-1] for e in self.state.last_events if e.kind == "INVALID"]
        self.assertEqual(sorted(codes), ["MOVE_BLOCKED", "MOVE_CONTESTED", "MOVE_CONTESTED"])

    def test_chain_into_empty_space_succeeds(self):
        units = [self.unit(0, (x, 6)) for x in range(3, 8)]
        self.play([f"MOVE {u.id} E" for u in units])
        self.assertEqual([u.pos for u in units], [(x, 6) for x in range(4, 9)])

    def test_four_unit_rotation_succeeds_across_players(self):
        a = self.unit(0, (6, 6))
        b = self.unit(1, (7, 6))
        c = self.unit(0, (7, 7))
        d = self.unit(1, (6, 7))
        self.play([f"MOVE {a.id} E", f"MOVE {c.id} W"], [f"MOVE {b.id} S", f"MOVE {d.id} N"])
        self.assertEqual((a.pos, b.pos, c.pos, d.pos), ((7, 6), (7, 7), (6, 7), (6, 6)))

    def test_newborn_blocks_movement(self):
        unit = self.unit(0, (4, 2))
        self.play([f"MOVE {unit.id} W", "SPAWN W 3 2"])
        self.assertEqual(unit.pos, (4, 2))
        self.assertEqual(len(self.state.units), 2)

    def test_attack_death_frees_movement_destination(self):
        a = self.unit(0, (5, 6))
        killer = self.unit(0, (6, 5), "S")
        self.unit(1, (6, 6), hp=20)
        self.play([f"MOVE {a.id} E", f"ATTACK {killer.id} 6 6"])
        self.assertEqual(a.pos, (6, 6))


class MiningAndDepositTests(RuleCase):
    def test_mine_rate_and_carry_limit(self):
        unit = self.unit(0, (7, 8))
        self.play([f"MINE {unit.id} 8 8"])
        self.assertEqual((unit.carry, self.state.ore[8, 8]), (10, 390))
        unit.carry = 57
        self.play([f"MINE {unit.id} 8 8"])
        self.assertEqual((unit.carry, self.state.ore[8, 8]), (60, 387))
        self.assertEqual(self.parse([f"MINE {unit.id} 8 8"])[1][0].code, "CARRY_FULL")

    def test_scarce_ore_is_equal_share_with_remainder_discarded(self):
        a = self.unit(0, (7, 8))
        b = self.unit(1, (8, 7))
        c = self.unit(1, (9, 8))
        self.state.ore[8, 8] = 8
        self.play([f"MINE {a.id} 8 8"], [f"MINE {b.id} 8 8", f"MINE {c.id} 8 8"])
        self.assertEqual((a.carry, b.carry, c.carry, self.state.ore[8, 8]), (2, 2, 2, 0))
        self.assertEqual(self.parse([f"MINE {a.id} 8 8"])[1][0].code, "NO_ORE")

    def test_capacity_limited_share_is_not_redistributed(self):
        a = self.unit(0, (7, 8), carry=59)
        b = self.unit(1, (8, 7))
        self.state.ore[8, 8] = 5
        self.play([f"MINE {a.id} 8 8"], [f"MINE {b.id} 8 8"])
        self.assertEqual((a.carry, b.carry, self.state.ore[8, 8]), (60, 2, 0))

    def test_exact_and_abundant_ore_do_not_discard_anything(self):
        a = self.unit(0, (7, 8))
        b = self.unit(1, (8, 7))
        self.state.ore[8, 8] = 20
        self.play([f"MINE {a.id} 8 8"], [f"MINE {b.id} 8 8"])
        self.assertEqual((a.carry, b.carry, self.state.ore[8, 8]), (10, 10, 0))

    def test_killed_miner_does_not_share_scarce_ore(self):
        a = self.unit(0, (7, 8), hp=20)
        b = self.unit(1, (8, 7))
        killer = self.unit(1, (7, 7), "S")
        self.state.ore[8, 8] = 8
        self.play([f"MINE {a.id} 8 8"], [f"MINE {b.id} 8 8", f"ATTACK {killer.id} 7 8"])
        self.assertEqual(b.carry, 8)

    def test_only_workers_can_mine_or_build(self):
        unit = self.unit(0, (9, 8), "S")
        self.assertEqual(self.parse([f"MINE {unit.id} 8 8"])[1][0].code, "CANNOT_MINE")
        self.assertEqual(self.parse([f"BUILD {unit.id} 10 8"])[1][0].code, "CANNOT_BUILD")

    def test_automatic_deposit_after_movement(self):
        unit = self.unit(0, (4, 2), carry=60)
        self.play([f"MOVE {unit.id} W"])
        self.assertEqual((unit.carry, self.state.players[0].energy, self.state.players[0].deposited), (0, 360, 60))
        self.play()
        self.assertEqual(self.state.players[0].deposited, 60)

    def test_only_adjacent_friendly_depots_and_only_once(self):
        self.state.towers[10, 8] = Tower(0, 10, 8, 300)
        self.state.towers[12, 8] = Tower(0, 12, 8, 300)
        unit = self.unit(0, (11, 8), carry=60)
        enemy = self.unit(1, (10, 7), carry=60)
        distant = self.unit(0, (4, 2), carry=60)
        self.play()
        self.assertEqual((unit.carry, enemy.carry, distant.carry), (0, 60, 60))
        self.assertEqual(self.state.players[0].deposited, 60)
        self.assertEqual(self.state.players[1].deposited, 0)

    def test_destroyed_tower_cannot_receive_deposit(self):
        self.state.towers[10, 8] = Tower(0, 10, 8, 20)
        carrier = self.unit(0, (10, 7), carry=60)
        enemy = self.unit(1, (9, 8), "S")
        self.play([], [f"ATTACK {enemy.id} 10 8"])
        self.assertEqual(carrier.carry, 60)

    def test_dead_worker_cargo_is_lost(self):
        worker = self.unit(0, (3, 2), hp=20, carry=60)
        enemy = self.unit(1, (4, 2), "S")
        self.play([], [f"ATTACK {enemy.id} 3 2"])
        self.assertNotIn(worker.id, self.state.units)
        self.assertEqual(self.state.players[0].deposited, 0)


class BuildRegenAndResultTests(RuleCase):
    def test_build_cost_hp_and_immediate_score_but_deposit_next_turn(self):
        unit = self.unit(0, (9, 8), carry=60)
        self.play([f"BUILD {unit.id} 10 8"])
        self.assertEqual(self.state.towers[10, 8].hp, 300)
        self.assertEqual((self.state.players[0].energy, self.state.players[0].score, unit.carry), (150, 1, 60))
        self.play()
        self.assertEqual((self.state.players[0].energy, self.state.players[0].score, unit.carry), (210, 2, 0))

    def test_build_can_spend_same_turn_deposit(self):
        builder = self.unit(0, (9, 8))
        self.unit(0, (3, 2), carry=60)
        self.state.players[0].energy = 90
        self.play([f"BUILD {builder.id} 10 8"])
        self.assertIn((10, 8), self.state.towers)
        self.assertEqual(self.state.players[0].energy, 0)

    def test_build_competes_with_spawn_before_deposit(self):
        builder = self.unit(0, (9, 8))
        self.state.players[0].energy = 200
        self.play([f"BUILD {builder.id} 10 8", "SPAWN S 3 2"])
        self.assertFalse(self.state.towers)
        self.assertEqual(self.state.players[0].energy, 100)

    def test_build_shared_site_fails_for_both_even_if_one_cannot_pay(self):
        a = self.unit(0, (9, 8))
        b = self.unit(1, (10, 7))
        self.state.players[1].energy = 0
        self.play([f"BUILD {a.id} 10 8"], [f"BUILD {b.id} 10 8"])
        self.assertFalse(self.state.towers)
        self.assertEqual(self.state.players[0].energy, 300)

    def test_duplicate_friendly_build_pays_once(self):
        a = self.unit(0, (9, 8))
        b = self.unit(0, (10, 7))
        self.play([f"BUILD {b.id} 10 8", f"BUILD {a.id} 10 8"])
        self.assertEqual(len(self.state.towers), 1)
        self.assertEqual(self.state.players[0].energy, 150)
        invalid = [e for e in self.state.last_events if e.kind == "INVALID"]
        self.assertEqual(invalid[0].values, (7, 1, "BUILD_REDUNDANT"))

    def test_build_multiple_sites_spends_in_unit_id_order_not_line_order(self):
        a = self.unit(0, (9, 8))
        b = self.unit(0, (12, 7))
        self.state.players[0].energy = 150
        self.play([f"BUILD {b.id} 12 8", f"BUILD {a.id} 10 8"])
        self.assertEqual(set(self.state.towers), {(10, 8)})
        self.assertEqual(self.state.players[0].energy, 0)

    def test_dead_lower_id_does_not_prevent_surviving_builder(self):
        a = self.unit(0, (9, 8), hp=20)
        b = self.unit(0, (10, 7))
        enemy = self.unit(1, (9, 7), "S")
        self.play([f"BUILD {a.id} 10 8", f"BUILD {b.id} 10 8"], [f"ATTACK {enemy.id} 9 8"])
        self.assertIn((10, 8), self.state.towers)

    def test_regeneration_uses_post_move_position_and_caps_at_max(self):
        enters = self.unit(0, (5, 2), hp=39)
        leaves = self.unit(0, (2, 4), hp=20)
        enemy_near = self.unit(1, (1, 2), hp=20)
        self.play([f"MOVE {enters.id} W", f"MOVE {leaves.id} S"])
        self.assertEqual((enters.hp, leaves.hp, enemy_near.hp), (40, 20, 20))
        self.assertEqual(self.state.players[0].base_hp, 1000)

    def test_regeneration_is_after_damage_but_does_not_resurrect(self):
        survivor = self.unit(0, (3, 2), "S", hp=30)
        attacker = self.unit(1, (4, 2), "S")
        self.play([], [f"ATTACK {attacker.id} 3 2"])
        self.assertEqual(survivor.hp, 15)
        self.play([], [f"ATTACK {attacker.id} 3 2"])
        self.assertNotIn(survivor.id, self.state.units)

    def test_tower_scoring_counts_surviving_towers_not_destroyed_ones(self):
        self.state.towers[10, 8] = Tower(0, 10, 8, 20)
        self.state.towers[12, 8] = Tower(1, 12, 8, 300)
        enemy = self.unit(1, (9, 8), "S")
        self.play([], [f"ATTACK {enemy.id} 10 8"])
        self.assertEqual([p.score for p in self.state.players], [0, 1])

    def test_turn_limit_comparison_priority(self):
        cases = [((2, 0, 100), (1, 1000, 1000), 0, "turn_limit_score"),
                 ((0, 10, 100), (0, 9, 1000), 0, "turn_limit_deposit"),
                 ((0, 0, 999), (0, 0, 1000), 1, "turn_limit_hp"),
                 ((0, 0, 1000), (0, 0, 1000), None, "turn_limit_draw")]
        for left, right, winner, reason in cases:
            with self.subTest(reason=reason):
                self.setUp()
                for player, values in zip(self.state.players, (left, right)):
                    player.score, player.deposited, player.base_hp = values
                self.state.turn = 299
                self.play()
                result = self.game.result(self.state)
                assert result is not None
                self.assertEqual((result.winner, result.reason, result.turns), (winner, reason, 300))

    def test_final_turn_deposit_beats_doing_nothing(self):
        self.unit(1, (20, 21), carry=10)
        self.state.turn = 299
        self.play()
        assert self.state.outcome is not None
        self.assertEqual((self.state.outcome.winner, self.state.outcome.reason), (1, "turn_limit_deposit"))

    def test_nonterminal_and_cannot_step_ended_match(self):
        self.play()
        self.assertIsNone(self.game.result(self.state))
        self.state.turn = 299
        self.play()
        old_hash = self.game.state_hash(self.state)
        with self.assertRaises(ValueError):
            self.play()
        self.assertEqual(old_hash, self.game.state_hash(self.state))

    def test_stale_or_wrong_player_packet_fails_before_mutation(self):
        a = self.parse([])[0]
        b = self.parse([], 1)[0]
        old_hash = self.game.state_hash(self.state)
        for packets in ([b, a], [a]):
            with self.assertRaises(ValueError):
                self.game.step(self.state, packets)
            self.assertEqual(old_hash, self.game.state_hash(self.state))
        self.play()
        old_hash = self.game.state_hash(self.state)
        with self.assertRaises(ValueError):
            self.game.step(self.state, [a, b])
        self.assertEqual(old_hash, self.game.state_hash(self.state))
