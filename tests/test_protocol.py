from __future__ import annotations

import unittest

from arena.games.outpost import Outpost
from arena.games.outpost.model import Tower
from arena.games.outpost.orders import MAX_LINE_BYTES, MAX_TURN_BYTES, MAX_TURN_LINES
from arena.games.outpost.rules import PARAMETERS
from tests.helpers import STARTING_RULES, fixture_map, fresh, settle


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.game, self.state = fresh()
        self.unit = self.state.add_unit(0, "W", (6, 6))
        self.enemy = self.state.add_unit(1, "W", (7, 6))

    def parse(self, lines):
        return self.game.parse_orders(self.state, 0, lines)

    def test_init_contains_all_parameters_and_limits(self):
        lines = self.game.init_message(self.state, 0)
        self.assertEqual(lines[:4], ["HRW 1", "RULESET standard-1", "YOU 0", "SEED 17"])
        params = {line.split()[1]: int(line.split()[2]) for line in lines if line.startswith("PARAM ")}
        self.assertEqual(params, STARTING_RULES)
        current = self.game.new_match(fixture_map(), {}, [17, 29])
        current_params = {line.split()[1]: int(line.split()[2])
                          for line in self.game.init_message(current, 0) if line.startswith("PARAM ")}
        self.assertEqual(current_params, {key: values[0] for key, values in PARAMETERS.items()})
        self.assertIn("LIMIT TURN_CPU_MS 100", lines)
        self.assertIn("LIMIT INIT_CPU_MS 2000", lines)
        self.assertIn("LIMIT BANK_MS 3000", lines)
        self.assertEqual(lines[-1], "END")
        self.assertIn("MAP 24 24", lines)
        for bad in (-1, 2):
            with self.assertRaises(ValueError):
                self.game.init_message(self.state, bad)

    def test_limits_are_explicit_not_hashed_rule_state(self):
        game = Outpost({"TURN_CPU_MS": 200, "BANK_MS": 6000})
        state = game.new_match(fixture_map(), {}, [17, 29])
        self.assertIn("LIMIT TURN_CPU_MS 200", game.init_message(state, 0))
        before = game.state_hash(state)
        state.bank_ms[0] = 5000
        self.assertEqual(game.state_hash(state), before)
        self.assertIn("BANK 5000", game.observation(state, 0))
        for overrides in ({"BANK_MS": 0}, {"X": 1}, {"BANK_MS": True}):
            with self.assertRaises(ValueError):
                Outpost(overrides)

    def test_observation_full_information_ore_filter_and_bank(self):
        self.state.ore[8, 8] = 0
        self.state.towers[10, 8] = Tower(1, 10, 8, 250)
        self.state.bank_ms[0] = 2100
        lines = self.game.observation(self.state, 0)
        self.assertEqual(lines[0], "TURN 1")
        self.assertIn("PLAYER 1 300 0 1000 0", lines)
        self.assertIn(f"UNIT {self.enemy.id} 1 W 7 6 40 0", lines)
        self.assertIn("TOWER 10 8 1 250", lines)
        self.assertNotIn("ORE 8 8 0", lines)
        self.assertEqual(lines[-2:], ["BANK 2100", "END"])

    def test_invalid_events_are_private_other_events_public(self):
        settle(self.game, self.state, ["bad", f"ATTACK {self.unit.id} 7 6"], ["wrong"])
        a = self.game.observation(self.state, 0)
        b = self.game.observation(self.state, 1)
        self.assertEqual(sum(line.startswith("EVENT INVALID") for line in a), 1)
        self.assertEqual(sum(line.startswith("EVENT INVALID") for line in b), 1)
        self.assertEqual([s for s in a if s.startswith("EVENT DAMAGE")], [s for s in b if s.startswith("EVENT DAMAGE")])
        self.assertEqual([p.warnings for p in self.state.players], [1, 1])

    def test_parse_does_not_mutate_state_or_count_warnings_twice(self):
        before = self.game.state_hash(self.state)
        orders, warnings = self.parse(["nonsense", f"MOVE {self.unit.id} N"])
        self.assertEqual(self.game.state_hash(self.state), before)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(orders.commands), 1)
        self.game.step(self.state, [orders, self.game.parse_orders(self.state, 1, [])[0]])
        self.assertEqual(self.state.players[0].warnings, 1)

    def test_first_well_formed_own_command_wins_even_if_illegal(self):
        commands, warnings = self.parse([f"ATTACK {self.unit.id} 20 20", f"MOVE {self.unit.id} N"])
        self.assertFalse(commands.commands)
        self.assertEqual([w.code for w in warnings], ["NOT_ADJACENT", "DUPLICATE"])

    def test_syntax_error_does_not_claim_slot(self):
        commands, warnings = self.parse([f"MOVE {self.unit.id}", f"MOVE {self.unit.id} N"])
        self.assertEqual(len(commands.commands), 1)
        self.assertEqual([w.code for w in warnings], ["BAD_SYNTAX"])

    def test_first_valid_order_and_independent_base_slots(self):
        commands, warnings = self.parse([f"MOVE {self.unit.id} N", f"MOVE {self.unit.id} S",
                                        "SPAWN W 3 2", "SPAWN S 2 3", "FIRE 4 2", "FIRE 3 2"])
        self.assertEqual([c.op for c in commands.commands], ["MOVE", "SPAWN"])
        self.assertEqual([w.code for w in warnings], ["DUPLICATE", "DUPLICATE", "NOT_ENEMY_UNIT", "DUPLICATE"])

    def test_unknown_enemy_and_missing_units_are_not_accepted(self):
        commands, warnings = self.parse([f"MOVE {self.enemy.id} N", "MOVE -1 N", "MOVE 999999 N"])
        self.assertFalse(commands.commands)
        self.assertEqual([w.code for w in warnings], ["NOT_OWN_UNIT"] * 3)

    def test_whitespace_crlf_blank_lines_and_end(self):
        commands, warnings = self.parse(["\r\n", f"  MOVE\t{self.unit.id} N \r\n", " END \n", "BAD"])
        self.assertEqual(len(commands.commands), 1)
        self.assertFalse(warnings)

    def test_bad_lines_are_independent_not_a_forfeit(self):
        garbage = ["?", "\x00", "\ud800", "\ufffd", "MOVE 1.5 N", "MOVE 1_0 N", "MOVE ١ N",
                   "MOVE 1 N extra", "ATTACK 1 x 2", "\nMOVE 0 N", "READY", "END extra", "⚠"]
        commands, warnings = self.parse(garbage + [f"MOVE {self.unit.id} N"])
        self.assertEqual(len(warnings), len(garbage))
        self.assertEqual(len(commands.commands), 1)
        self.game.step(self.state, [commands, self.game.parse_orders(self.state, 1, [])[0]])
        self.assertIsNone(self.state.outcome)
        self.assertEqual(self.unit.pos, (6, 5))

    def test_bad_direction_is_a_warning(self):
        commands, warnings = self.parse([f"MOVE {self.unit.id} NE"])
        self.assertFalse(commands.commands)
        self.assertEqual(warnings[0].code, "BAD_DIRECTION")

    def test_line_limit_is_utf8_bytes_not_codepoints(self):
        for raw in ("x" * (MAX_LINE_BYTES + 1), "中" * 86):
            with self.subTest(length=len(raw)):
                commands, warnings = self.parse([raw, f"MOVE {self.unit.id} N"])
                self.assertEqual(warnings[0].code, "LINE_TOO_LONG")
                self.assertEqual(len(commands.commands), 1)
        raw = (f"MOVE {self.unit.id} N").ljust(MAX_LINE_BYTES) + "\r\n"
        self.assertFalse(self.parse([raw])[1])

    def test_turn_line_limit(self):
        commands, warnings = self.parse([""] * MAX_TURN_LINES + [f"MOVE {self.unit.id} N"])
        self.assertFalse(commands.commands)
        self.assertEqual([w.code for w in warnings], ["TOO_MANY_LINES"])

    def test_turn_byte_limit_and_huge_single_line(self):
        commands, warnings = self.parse(["x" * 256] * 300 + [f"MOVE {self.unit.id} N"])
        self.assertFalse(commands.commands)
        self.assertEqual(warnings[-1].code, "TOO_MANY_BYTES")
        self.assertLessEqual(len(warnings), 256)
        commands, warnings = self.parse(["x" * (MAX_TURN_BYTES * 2)])
        self.assertFalse(commands.commands)
        self.assertEqual([w.code for w in warnings], ["TOO_MANY_BYTES"])

    def test_fire_cannot_target_towers_or_bases(self):
        self.state.towers[3, 2] = Tower(1, 3, 2, 300)
        for line in ("FIRE 3 2", "FIRE 21 21"):
            self.assertEqual(self.parse([line])[1][0].code, "NOT_ENEMY_UNIT")

    def test_ascii_renderer_contains_positions_and_counters(self):
        self.state.towers[10, 8] = Tower(1, 10, 8, 300)
        lines = self.game.render(self.state).splitlines()
        self.assertEqual(lines[0], "TURN 0")
        self.assertIn("energy=300", lines[1])
        rows = lines[3:]
        self.assertEqual((len(rows), len(rows[0])), (24, 24))
        self.assertEqual((rows[6][6], rows[6][7], rows[8][10], rows[2][2]), ("W", "w", "t", "0"))
