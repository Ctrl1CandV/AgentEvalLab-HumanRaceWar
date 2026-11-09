"""Analytic/graph/bootstrap checks; no bots or hidden inputs."""
import math
import unittest
from tools.provisional_bt import bootstrap, fit, percentile


class ProvisionalBTTests(unittest.TestCase):
    def test_two_player_closed_form_and_anchor_swap(self):
        counts = [[0, 75], [25, 0]]
        value = 400*math.log10(3)
        self.assertAlmostEqual(fit(counts)['elo'][1], -value, places=6)
        self.assertAlmostEqual(fit(counts, 1)['elo'][0], value, places=6)
        self.assertTrue(fit(counts)['finiteFullMLE'])

    def test_cycle_and_fractional_draw_scores(self):
        counts = [[0, 8.5, 2.5], [2.5, 0, 8.5], [8.5, 2.5, 0]]
        self.assertEqual(fit(counts)['elo'], [0.0, 0.0, 0.0])
        self.assertEqual(fit([[0, 2.5], [2.5, 0]])['elo'], [0.0, 0.0])

    def test_separation_does_not_get_fake_finite_rating(self):
        result = fit([[0, 8, 10], [2, 0, 10], [0, 0, 0]])
        self.assertFalse(result['finiteFullMLE'])
        self.assertEqual(result['anchorComponent'], [0, 1])
        self.assertEqual(result['elo'][2], '-infinity')
        self.assertAlmostEqual(result['elo'][1], -400*math.log10(4), places=6)
        self.assertEqual(fit([[0, 0], [1, 0]])['elo'], [0, '+infinity'])

    def test_disconnected_and_incomparable_are_unidentified(self):
        self.assertEqual(fit([[0, 0], [0, 0]])['elo'], [0, None])
        # Both 0 and 1 beat 2; their relative location is not identified.
        self.assertEqual(fit([[0, 0, 1], [0, 0, 1], [0, 0, 0]])['elo'], [0, None, '-infinity'])

    def test_simulated_exact_bt_odds_and_permutation(self):
        strength = [1, 2, 4, 8]
        counts = [[0 if i == j else 100*strength[i]/(strength[i]+strength[j])
                   for j in range(4)] for i in range(4)]
        result = fit(counts)['elo']
        for i, s in enumerate(strength): self.assertAlmostEqual(result[i], 400*math.log10(s), places=6)
        order = [2, 3, 1, 0]
        permuted = fit([[counts[i][j] for j in order] for i in order], order.index(0))['elo']
        for i, value in enumerate(permuted): self.assertAlmostEqual(value, result[order[i]], places=6)

    def test_newton_matches_independent_mm_for_nontransitive_counts(self):
        counts = [[0, 31.5, 12], [8.5, 0, 21], [28, 19, 0]]
        strengths = [1.0]*3; error = math.inf
        for _ in range(10000):
            new = [sum(counts[i])/sum((counts[i][j]+counts[j][i])/(strengths[i]+strengths[j])
                   for j in range(3) if j != i) for i in range(3)]
            new = [v/new[0] for v in new]
            error = max(abs(math.log(a/b)) for a, b in zip(new, strengths)); strengths = new
            if error < 1e-12: break
        self.assertLess(error, 1e-12)
        for actual, weight in zip(fit(counts)['elo'], strengths):
            self.assertAlmostEqual(actual, 400*math.log10(weight), places=6)

    def test_common_map_resampling_retains_separated_draws(self):
        clusters = [[[0, 2], [0, 0]], [[0, 0], [2, 0]]]
        result = bootstrap(clusters, samples=200, seed=4219)
        self.assertEqual(result, bootstrap(clusters, samples=200, seed=4219))
        self.assertEqual(result['ratings'][1]['interval95'], ['-infinity', '+infinity'])
        self.assertGreater(result['ratings'][1]['negativeInfiniteSamples'], 0)
        self.assertGreater(result['ratings'][1]['positiveInfiniteSamples'], 0)
        self.assertEqual(len(result['rawElo'][1]), 200)
        self.assertEqual(result['ratings'][0]['interval95'], [0, 0])

    def test_unidentified_bootstrap_not_silently_omitted(self):
        result = bootstrap([[[0, 0], [0, 0]]], samples=5)
        self.assertIsNone(result['ratings'][1]['interval95'])
        self.assertEqual(result['ratings'][1]['unidentifiedSamples'], 5)
        self.assertEqual(percentile(['+infinity', 0, '-infinity'], .5), 0)

    def test_invalid_values_and_self_play_are_rejected(self):
        for value in ([], [[0, 1]], [[1]], [[0, -1], [1, 0]],
                      [[0, True], [1, 0]], [[0, float('nan')], [1, 0]]):
            with self.assertRaises(ValueError): fit(value)
        with self.assertRaises(ValueError): fit([[0]], True)
        with self.assertRaises(ValueError): bootstrap([], samples=5)


if __name__ == '__main__': unittest.main()
