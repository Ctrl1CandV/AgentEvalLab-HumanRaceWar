"""Synthetic checks for read-only pairwise L0 diagnostic; not ladder acceptance."""
import math
import unittest

from tools.check_ladder_anchors import pair_elo, summarize_pair


class LadderAnchorTests(unittest.TestCase):
    def test_exact_two_bot_bt_solution_and_symmetry(self):
        self.assertAlmostEqual(pair_elo(.875)['value'], 400*math.log10(7))
        self.assertAlmostEqual(pair_elo(.875)['value'], -pair_elo(.125)['value'])
        self.assertEqual(pair_elo(.5)['value'], 0.)

    def test_separation_is_unbounded_not_smoothed_or_capped(self):
        self.assertEqual(pair_elo(0), {'value': None, 'unbounded': 'negative'})
        self.assertEqual(pair_elo(1), {'value': None, 'unbounded': 'positive'})
        for value in (-.01, 1.01, float('nan'), float('inf')):
            with self.assertRaises(ValueError): pair_elo(value)

    def test_draw_is_half_score_and_swapped_seats_remain_one_cluster(self):
        r = summarize_pair([['W','L'], ['D','D']])
        self.assertEqual((r['maps'], r['games'], r['wins'], r['draws'], r['losses']), (2,4,1,2,1))
        self.assertEqual(r['scoreRate'], .5)
        self.assertEqual(r['mapClusterCI95'], [.5,.5])
        self.assertEqual(r['twoBotEloDifference']['value'], 0)

    def test_missing_seat_or_empty_cohort_is_rejected(self):
        with self.assertRaises(ValueError): summarize_pair([['W']])
        with self.assertRaises(ValueError): summarize_pair([])


if __name__ == '__main__':
    unittest.main()
