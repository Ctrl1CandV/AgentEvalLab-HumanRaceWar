"""Review N1/N3 and conditional gates: synthetic/public aggregates only."""
from copy import deepcopy
from itertools import combinations, product
import json
import unittest

from tools.analyze_zoo import SINGLES
from tools.phase_b_holdout import BASELINE
from tools.review_holdout import margin, minimum_changes, new_holdout_checks, paired_counts


class ReviewHoldoutTests(unittest.TestCase):
    def test_strict_counter_and_inclusive_balanced_thresholds(self):
        tied = [2]*12 + [0]*12
        self.assertFalse(margin(tied, 1, 2, below=True)['passed'])
        self.assertEqual(margin(tied, 1, 2, below=True)['minimumMapsToPass'], 1)
        self.assertTrue(margin([2]*11 + [0]*13, 1, 2, below=True)['passed'])
        maze = [2, 2, 2, 0, 0, 0]
        self.assertEqual(margin(maze, 11, 20)['minimumMapsToPass'], 1)
        self.assertTrue(margin([2]*4 + [0]*2, 11, 20)['passed'])
        far = margin([2]*5 + [0], 1, 2, below=True)
        self.assertEqual(far['minimumMapsToPass'], 3)
        self.assertEqual(margin([2]*7 + [0]*33, 1, 5)['minimumMapsToPass'], 1)

    def test_greedy_map_distance_matches_exhaustive_cluster_replacement(self):
        for values in product(range(3), repeat=4):
            for increase in (False, True):
                for target in range(9):
                    expected = None
                    for n in range(5):
                        for changed in combinations(range(4), n):
                            total = sum((2 if increase else 0) if i in changed else v for i, v in enumerate(values))
                            if (total >= target if increase else total <= target):
                                expected = n; break
                        if expected is not None: break
                    self.assertEqual(minimum_changes(values, target, increase), expected)

    def test_split_and_draw_maps_are_explicit_not_half_wins(self):
        pairs = [('W', 'W'), ('L', 'L'), ('W', 'L'), ('W', 'D'), ('L', 'D'), ('D', 'D')]
        c = paired_counts(pairs)
        self.assertEqual(c['maps'], 6)
        self.assertEqual([c[k] for k in ('twoWins', 'twoLosses', 'splitWins', 'oneWinOneDraw', 'oneLossOneDraw', 'twoDraws')], [1]*6)
        self.assertEqual(sum(p.count('W') for p in pairs), 4)
        with self.assertRaises(ValueError): paired_counts([('W',)])
        with self.assertRaises(ValueError): minimum_changes([], 0, True)

    def test_new_holdout_equal_50_not_universal_but_public_gates_stay_old(self):
        report = json.loads(BASELINE.read_text())
        for c in report['matrix']:
            if c['bot'] == 'Z-harass' and c['opponent'] in SINGLES and c['opponent'] != 'Z-harass' and c['mapType'] == 'all':
                c['winRate'] = .75
        self.assertFalse(new_holdout_checks(report)['noUniversalSingle'])
        cell = next(c for c in report['matrix'] if (c['bot'], c['opponent'], c['mapType']) == ('Z-harass', 'Z-eco', 'all'))
        cell['winRate'] = .5
        self.assertTrue(new_holdout_checks(report)['noUniversalSingle'])
        # This helper never edits the public acceptance booleans.
        self.assertEqual(report['rateChecks'], json.loads(BASELINE.read_text())['rateChecks'])

    def test_upper_interval_does_not_waive_unchanged_type_point_floor(self):
        base = json.loads(BASELINE.read_text())
        for point, upper, expected_upper, expected_floor in ((.5, .54, False, True), (.5, .55, True, True), (.49, .99, True, False)):
            report = deepcopy(base)
            c = next(c for c in report['matrix'] if (c['bot'], c['opponent'], c['mapType']) == ('M-balanced', 'Z-towers', 'maze'))
            c['winRate'] = point; c['winRateCI95'] = [0., upper]
            checks = new_holdout_checks(report)
            self.assertEqual(checks['balancedTypeUpper95AtLeast55'], expected_upper)
            self.assertEqual(checks['7_typePointEstimateAtLeast50'], expected_floor)


if __name__ == '__main__':
    unittest.main()
