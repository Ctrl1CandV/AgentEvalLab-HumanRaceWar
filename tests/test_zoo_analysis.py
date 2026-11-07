"""Statistics only: no bot execution, no additional game samples."""
import unittest
from tools.analyze_zoo import summarize, interval, percentile


class ZooAnalysisTests(unittest.TestCase):
    def test_resampling_keeps_seats_in_the_map_cluster(self):
        paired=[(0,1.),(0,1.),(1,0.),(1,0.),(2,.5),(2,.5)]
        original=summarize(paired); duplicated=summarize(paired*2)
        self.assertEqual(original['maps'],3)
        self.assertEqual(original['scoreRate'],.5)
        self.assertEqual(original['scoreRateCI95'],duplicated['scoreRateCI95'])
        self.assertEqual(original['winRateCI95'],duplicated['winRateCI95'])
        self.assertEqual(original['wins'],2)
        self.assertEqual(original['draws'],2)
        self.assertEqual(original['losses'],2)

    def test_win_only_and_half_draw_are_explicitly_different(self):
        report=summarize([(0,1.),(0,.5),(1,.5),(1,0.)])
        self.assertEqual(report['winRate'],.25)
        self.assertEqual(report['scoreRate'],.5)
        self.assertEqual(interval((0.,0.,0.)),[0.,0.])
        self.assertEqual(interval(()),[None,None])

    def test_nearest_rank_percentile(self):
        self.assertEqual(percentile(list(range(1,101)),.95),95)
        self.assertIsNone(percentile([],.95))


if __name__=='__main__':unittest.main()
