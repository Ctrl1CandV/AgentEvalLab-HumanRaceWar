from __future__ import annotations

from dataclasses import replace
from itertools import product
import unittest

from arena.games.outpost import Outpost
from arena.games.outpost.engine import event_key
from arena.games.outpost.model import Tower
from tests.helpers import fixture_map, fresh, rotate_event, rotate_lines, rotate_state, settle


class DeterminismTests(unittest.TestCase):
    def test_initial_setup_rotates_with_players_and_seeds(self):
        game = Outpost()
        a = game.new_match(fixture_map(), {}, [17, 29])
        b = game.new_match(fixture_map(), {}, [29, 17])
        self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))
        self.assertEqual(game.snapshot(rotate_state(rotate_state(a))), game.snapshot(a))
        # Pinned development format, also checked in separate hash-seed processes.
        self.assertEqual(game.state_hash(a), "0b7021bc7f2363b1")

    def test_same_fixed_instruction_transcript_has_same_hash_every_turn(self):
        game = Outpost()
        a = game.new_match(fixture_map(), {}, [17, 29])
        b = game.new_match(fixture_map(), {}, [17, 29])
        hashes = []
        for turn in range(80):
            direction = ("E", "S", "W", "N")[turn % 4]
            left = [f"MOVE 0 {direction}", "MOVE 2 E", "SPAWN W 3 2", "FIRE 4 2"]
            right = ["MOVE 1 W", "MOVE 3 N", "SPAWN S 20 21", "bad"]
            settle(game, a, left, right)
            settle(game, b, left, right)
            self.assertEqual(game.state_hash(a), game.state_hash(b), f"turn {turn + 1}")
            hashes.append(game.state_hash(a))
        self.assertEqual(len(set(hashes)), 80)
        self.assertRegex(hashes[-1], "^[0-9a-f]{16}$")
        self.assertEqual(hashes[-1], "daa49b005ded38f4")

    def test_hash_does_not_depend_on_dictionary_or_event_insertion_order(self):
        game, a = fresh()
        for owner, pos in ((0, (7, 8)), (1, (8, 7)), (0, (3, 2)), (1, (20, 21))):
            a.add_unit(owner, "W", pos).carry = 30
        a.towers[10, 8] = Tower(0, 10, 8, 300)
        a.towers[12, 8] = Tower(1, 12, 8, 300)
        settle(game, a, ["bad"], ["bad"])
        b = rotate_state(rotate_state(a))
        b.units = dict(reversed(list(b.units.items())))
        b.towers = dict(reversed(list(b.towers.items())))
        b.ore = dict(reversed(list(b.ore.items())))
        b.last_events.reverse()
        self.assertEqual(game.state_hash(a), game.state_hash(b))
        settle(game, a, [], [])
        settle(game, b, [], [])
        self.assertEqual(game.state_hash(a), game.state_hash(b))

    def test_every_event_kind_and_phase_is_symmetric_in_asymmetric_position(self):
        game, a = fresh()
        mine0 = a.add_unit(0, "W", (7, 8))
        mine1 = a.add_unit(1, "W", (8, 7))
        build0 = a.add_unit(0, "W", (9, 8))
        build1 = a.add_unit(1, "W", (12, 7))
        fight0 = a.add_unit(0, "S", (6, 6))
        fight1 = a.add_unit(1, "S", (7, 6))
        fight0.hp = fight1.hp = 20
        a.add_unit(0, "W", (3, 2)).carry = 30
        a.add_unit(1, "W", (20, 21)).carry = 30
        mover = a.add_unit(0, "W", (4, 2))
        a.add_unit(0, "W", (20, 20))
        a.add_unit(1, "W", (3, 3))
        a.players[0].energy = 150
        a.ore[8, 8] = 5
        b = rotate_state(a)
        left = [f"MINE {mine0.id} 8 8", f"BUILD {build0.id} 10 8", f"ATTACK {fight0.id} 7 6",
                f"MOVE {mover.id} W", "SPAWN W 2 3", "FIRE 3 3", "bad"]
        right = [f"MINE {mine1.id} 8 8", f"BUILD {build1.id} 12 8", f"ATTACK {fight1.id} 6 6",
                 "SPAWN S 21 20", "FIRE 20 20"]
        for _ in range(2):
            events = settle(game, a, left, right)
            mirrored_events = settle(game, b, rotate_lines(right), rotate_lines(left))
            self.assertEqual(sorted((rotate_event(e) for e in events), key=event_key), mirrored_events)
            self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))
            if a.turn == 1:
                self.assertEqual({e.kind for e in events}, {"DAMAGE", "DEATH", "SPAWN", "BUILD", "DEPOSIT", "INVALID"})

    def test_unit_id_build_priority_is_symmetric(self):
        game, a = fresh()
        first = a.add_unit(0, "W", (9, 8))
        second = a.add_unit(0, "W", (12, 7))
        a.players[0].energy = 150
        b = rotate_state(a)
        lines = [f"BUILD {second.id} 12 8", f"BUILD {first.id} 10 8"]
        settle(game, a, lines, [])
        settle(game, b, [], rotate_lines(lines))
        self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))

    def test_terminal_results_are_symmetric(self):
        for mutual in (False, True):
            game, a = fresh()
            u = a.add_unit(0, "S", (20, 21))
            v = a.add_unit(1, "S", (3, 2))
            a.players[1].base_hp = 20
            if mutual:
                a.players[0].base_hp = 20
            b = rotate_state(a)
            left, right = [f"ATTACK {u.id} 21 21"], [f"ATTACK {v.id} 2 2"]
            settle(game, a, left, right)
            settle(game, b, rotate_lines(right), rotate_lines(left))
            self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))
        for score, deposited, hp in ((1, 0, 1000), (0, 10, 1000), (0, 0, 900), (0, 0, 1000)):
            game, a = fresh()
            a.turn = 299
            a.players[0].score, a.players[0].deposited, a.players[0].base_hp = score, deposited, hp
            b = rotate_state(a)
            settle(game, a, [], [])
            settle(game, b, [], [])
            self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))

    def test_all_625_four_unit_move_combinations_are_symmetric_and_nonoverlapping(self):
        game, template = fresh()
        for owner, pos in ((0, (6, 6)), (1, (7, 6)), (0, (7, 7)), (1, (6, 7))):
            template.add_unit(owner, "W", pos)
        ids = list(template.units)
        for directions in product((None, "N", "E", "S", "W"), repeat=4):
            with self.subTest(directions=directions):
                a = rotate_state(rotate_state(template))
                b = rotate_state(a)
                lines = [[], []]
                for uid, direction in zip(ids, directions):
                    if direction is not None:
                        lines[a.units[uid].owner].append(f"MOVE {uid} {direction}")
                settle(game, a, *lines)
                settle(game, b, rotate_lines(lines[1]), rotate_lines(lines[0]))
                self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(b))
                self.assertEqual(len({u.pos for u in a.units.values()}), 4)
                self.assertTrue(all(a.map.terrain(u.pos) == "." for u in a.units.values()))

    def test_malformed_text_fuzz_never_changes_legal_state_invariants(self):
        # Deterministic parser test data, not a bot or an autonomous strategy.
        word = 123456789
        alphabet = "MOVE ATTACK MINE BUILD SPAWN FIRE END0123456789\x00\n\r\ud800中"
        for sample in range(200):
            lines = []
            for _ in range(6):
                chars = []
                for _ in range(sample % 270):
                    word = (1664525 * word + 1013904223) & 0xffffffff
                    chars.append(alphabet[word % len(alphabet)])
                lines.append("".join(chars))
            game, state = fresh()
            settle(game, state, lines, list(reversed(lines)))
            self.assertEqual(state.turn, 1)
            self.assertEqual([p.energy for p in state.players], [300, 300])
            self.assertFalse(state.units)
            self.assertIsNone(state.outcome)

    def test_unparsed_structured_orders_are_rejected_without_mutation(self):
        game, state = fresh()
        a = state.add_unit(0, "W", (6, 6))
        packet = game.parse_orders(state, 0, [f"MOVE {a.id} N"])[0]
        opponent = game.parse_orders(state, 1, [])[0]
        invalid = replace(packet, commands=(replace(packet.commands[0], direction="BAD"),))
        before = game.state_hash(state)
        with self.assertRaises(ValueError):
            game.step(state, [invalid, opponent])
        self.assertEqual(game.state_hash(state), before)
