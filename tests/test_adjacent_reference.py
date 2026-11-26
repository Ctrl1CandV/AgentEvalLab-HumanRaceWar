"""Migration reference and gates, using no bots or real maps."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from arena.calibrate import compare, identity, read_reference, schedule, summarize_adjacent, write_reference
from arena.ladder import Ladder, Member


class AdjacentReferenceTests(unittest.TestCase):
    def setUp(self):
        codes = ['M-balanced' if i == 5 else f'm{i}' for i in range(13)]
        levels = tuple((Member(code, Path('/devhost')/code, code, 'cpp', 0, ()),) for code in codes)
        self.ladder = Ladder('1.0.0', levels, (17, 29), (), {
            'pairings': list(zip(codes, codes[1:])),
            'maps': [{'sha256': 'c'*64}, {'sha256': 'd'*64}],
        })
        self.bound = identity(self.ladder, b'unchanged frozen ladder')
        _, self.slots = schedule(self.ladder)
        self.games = [{**g, 'winner': None, 'reason': 'turn_limit_tie', 'turns': 300,
                       'faults': [None, None]} for g in self.slots.values()]
        self.panel = summarize_adjacent(self.ladder, self.games, True)

    def comparison(self, current, reference=None):
        return compare(self.ladder, current, reference or self.panel, expected=len(self.slots))

    def test_reference_round_trip_and_refuses_overwrite(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/'private'/'reference.json'
            reference = {**self.bound, 'timingLock': {'jobs': 6}, **self.panel}
            write_reference(path, reference)
            self.assertEqual(read_reference(path, self.bound, self.slots, self.ladder), reference)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_reference(path, {**reference, 'engineVersion': 'changed'})
            self.assertEqual(path.read_bytes(), before)

    def test_reference_rejects_each_config_mismatch(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/'ref.json'
            write_reference(path, {**self.bound, **self.panel})
            for k in ('ladderSha256', 'calibrationMapsSha256', 'sourceHashes', 'engineVersion'):
                with self.subTest(field=k), self.assertRaisesRegex(ValueError, k):
                    read_reference(path, {**self.bound, k: 'different'}, self.slots, self.ladder)

    def test_task_ids_are_portable_but_bind_map_seat_and_seed(self):
        other = replace(self.ladder, levels=tuple(tuple(replace(m, source=Path('/new-host')/m.code) for m in tier)
                                                  for tier in self.ladder.levels))
        self.assertEqual(schedule(other)[1], self.slots)
        self.assertEqual(len({g['taskId'] for g in self.slots.values()}), len(self.slots))
        other = replace(other, seeds=(29, 17))
        self.assertTrue({g['taskId'] for g in self.slots.values()}.isdisjoint(
            g['taskId'] for g in schedule(other)[1].values()))

    def test_l0_negative_infinity_and_bottom_two_pairs_are_diagnostic(self):
        games = deepcopy(self.games)
        for game in games:
            if 'm0' in game['players']:
                game['winner'] = game['players'].index('m1')
        panel = summarize_adjacent(self.ladder, games, True)
        self.assertEqual(panel['ratings']['m0'], '-infinity')
        self.assertIsNone(panel['pairs'][0]['eloGap'])
        self.assertEqual(panel['pairs'][0]['scoreRate'], 1)
        result = self.comparison(panel)
        self.assertEqual([r['gate'] for r in result['comparisons']], [False, False]+[True]*10)
        self.assertFalse(result['comparisons'][0]['consistent'])
        self.assertTrue(result['passed'])

    def test_nonfinite_pair_uses_inclusive_score_rate_delta(self):
        current = deepcopy(self.panel)
        current['pairs'][2].update(eloGap=None, scoreRate=.55)
        ref = deepcopy(self.panel)
        ref['pairs'][2]['scoreRate'] = .5
        good = self.comparison(current, ref)
        self.assertTrue(good['passed'])
        self.assertIsNone(good['comparisons'][2]['eloDelta'])
        self.assertAlmostEqual(good['comparisons'][2]['scoreDelta'], .05)
        current['pairs'][2]['scoreRate'] = .5501
        self.assertFalse(self.comparison(current, ref)['passed'])
        self.assertFalse(self.comparison(ref, current)['passed'])

    def test_finite_pair_uses_inclusive_elo_delta(self):
        current = deepcopy(self.panel)
        current['pairs'][2]['eloGap'] = 50
        self.assertTrue(self.comparison(current)['passed'])
        current['pairs'][2]['eloGap'] = 50.01
        self.assertFalse(self.comparison(current)['passed'])

    def test_one_missing_game_fails(self):
        current = summarize_adjacent(self.ladder, self.games[:-1], False)
        self.assertFalse(self.comparison(current)['passed'])

    def test_fault_limit_is_two_above_reference(self):
        games = deepcopy(self.games)
        for i in range(4):
            games[i]['faults'] = ['turn_timeout', None]
        ref = summarize_adjacent(self.ladder, [games[0], *self.games[1:]], True)
        self.assertEqual(ref['faultGames']['count'], 1)
        at_limit = self.comparison(summarize_adjacent(self.ladder, games[:3]+self.games[3:], True), ref)
        self.assertEqual(at_limit['faultLimit'], 3)
        self.assertTrue(at_limit['passed'])
        self.assertFalse(self.comparison(summarize_adjacent(self.ladder, games, True), ref)['passed'])

    def test_game_agreement_compares_task_ids_including_ties(self):
        games = deepcopy(self.games)
        games[0]['winner'] = 0
        games[4]['winner'] = 1
        result = self.comparison(summarize_adjacent(self.ladder, list(reversed(games)), True))['gameAgreement']
        self.assertEqual((result['same'], result['compared']), (len(games)-2, len(games)))
        self.assertEqual(result['rate'], (len(games)-2)/len(games))
        self.assertEqual([(p['same'], p['compared']) for p in result['pairs']][:3], [(3,4), (3,4), (4,4)])
