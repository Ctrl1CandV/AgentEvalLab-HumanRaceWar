"""N2 diagnostic checks; synthetic inputs only, never access hidden maps."""
import json
import unittest
from uuid import uuid4

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, prepare
from arena.core.transport import Connection, exchange
from tests.helpers import fresh
from tools.generate_hidden_maps import ROOT
from tools.review_maze import distribution, instrument, parse_intents


class ReviewMazeTests(unittest.TestCase):
    def test_intent_parser_rejects_missing_duplicate_and_impossible_counts(self):
        good = b'REVIEW_N2 1 4 5 10 8 1\n'
        self.assertEqual(parse_intents(good, 1)[1]['base'], 8)
        for raw, turns in ((good, 2), (good+good, 1), (b'REVIEW_N2 1 4 5 10 8 3\n', 1), (b'junk\n', 1)):
            with self.assertRaises(ValueError): parse_intents(raw, turns)

    def test_instrumentation_fails_closed_on_source_drift(self):
        source = (ROOT/'bots/public/M-balanced/strategy.hpp').read_text()
        changed = instrument(source)
        self.assertIn('ownTowers>=enemyTowers', changed)
        self.assertIn('REVIEW_N2', changed)
        with self.assertRaises(ValueError): instrument(source.replace('} else move(u,adjacent(goal));', '/* changed */'))
        with self.assertRaises(ValueError): instrument(changed)

    def test_distribution_retains_missing_and_uses_sorted_nearest_rank(self):
        self.assertEqual(distribution([3, None, 1, 2]), {'games': 4, 'observedGames': 3, 'median': 2,
            'min': 1, 'p25': 1, 'p75': 3, 'max': 3})
        self.assertIsNone(distribution([])['median'])

    def test_sandboxed_probe_is_behavior_preserving_on_synthetic_observation(self):
        out = ROOT/'runs/development/review-maze-tests'/uuid4().hex
        source = out/'source'; source.mkdir(parents=True)
        original = ROOT/'bots/public/M-balanced'
        (source/'main.cpp').write_bytes((original/'main.cpp').read_bytes())
        (source/'strategy.hpp').write_text(instrument((original/'strategy.hpp').read_text()))
        game, state = fresh()
        state.add_unit(0, 'S', (10, 2))
        state.players[0].energy = 0
        outputs = []
        with CpuLease(1) as lease:
            launcher = Bubblewrap(); launcher.cpus = lease.cpus
            for name, directory in (('original', original), ('instrumented', source)):
                bot = prepare(directory, out/name, launcher, lease.cpus[0])
                self.assertIsNone(bot.compile_fault)
                conn = Connection(bot, launcher, lease.cpus[0], 10)
                evidence = []
                try:
                    init = exchange([conn], [game.init_message(state, 0)], [2000], [2500], b'READY')[0]
                    self.assertIsNone(init.fault); evidence.append(init.record())
                    reply = exchange([conn], [game.observation(state, 0)], [100], [1000])[0]
                    self.assertIsNone(reply.fault); evidence.append(reply.record())
                    outputs.append(reply.lines)
                finally:
                    conn.close()
                    (out/f'{name}-probe.json').write_text(json.dumps({'inputs': [game.init_message(state, 0), game.observation(state, 0)], 'replies': evidence, 'stderr': conn.stderr.decode()}, indent=2)+'\n')
                if name == 'instrumented':
                    self.assertEqual(parse_intents(conn.stderr, 1)[1]['soldiers'], 1)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == '__main__':
    unittest.main()
