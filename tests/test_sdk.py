"""Trusted SDK parser/geometry checks; no bot strategy is imported or executed."""
import io
import unittest

from arena.games.outpost import Outpost
from sdk.python import hrw
from tests.helpers import fixture_map


class SdkTests(unittest.TestCase):
    def test_unknown_fields_geometry_and_eof(self):
        game = Outpost()
        state = game.new_match(fixture_map(), {}, [2**80, 0])
        setup = hrw.read_setup(io.StringIO("FUTURE field\n"+"\n".join(game.init_message(state, 0))+"\n"))
        self.assertEqual(setup.seed, 2**80)
        self.assertEqual(setup.bases()[0], (2, 2))
        turn = hrw.read_turn(io.StringIO("\n".join(game.observation(state, 0))+"\n"))
        assert turn is not None
        self.assertEqual(turn.units[0].id, 0)
        self.assertEqual(turn.number, 1)
        self.assertEqual(hrw.bfs(["...", ".#.", "..."], [(0, 0)])[(2, 2)], 4)
        self.assertNotIn((1, 0), hrw.bfs(["..."], [(0, 0)], [(1, 0)]))
        self.assertIsNone(hrw.read_turn(io.StringIO("")))
        with self.assertRaises(EOFError):
            hrw.read_turn(io.StringIO("TURN 1\n"))
        out = io.StringIO()
        hrw.ready(out)
        hrw.send(["MOVE 0 N"], out)
        self.assertEqual(out.getvalue(), "READY\nMOVE 0 N\nEND\n")

    def test_turn_fields_and_unknown_keyword(self):
        turn = hrw.read_turn(io.StringIO("TURN 7\nPLAYER 0 10 20 900 30\nTOWER 3 4 0 200\n"
            "UNIT 4 0 W 1 2 40 60\nORE 8 9 22\nEVENT DEPOSIT 4 0 60\n"
            "FUTURE unused\nBANK 999\nEND\n"))
        assert turn is not None
        self.assertEqual(turn.players[0], (10, 20, 900, 30))
        self.assertEqual(turn.towers, [(3, 4, 0, 200)])
        self.assertEqual(turn.units[0].pos, (1, 2))
        self.assertEqual(turn.ore, {(8, 9): 22})
        self.assertEqual(turn.events, [["DEPOSIT", "4", "0", "60"]])
        self.assertEqual(turn.bank, 999)
        self.assertEqual(hrw.distance((1, 2), (3, 5)), 5)
