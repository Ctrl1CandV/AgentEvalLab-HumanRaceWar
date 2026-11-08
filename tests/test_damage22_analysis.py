"""Synthetic paired-statistic and transcript tests, never bot execution."""
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tests.helpers import STARTING_RULES
from tests.synthetic_replay import legacy_replay
from tools.analyze_damage22 import (cohort_metrics, distribution, inspect_trajectory, matched_rows,
                                    matrix_changes, paired_stats, trajectory_summary)


class Damage22AnalysisTests(unittest.TestCase):
    def test_pairing_uses_map_content_seats_and_seeds_not_task_id_or_order(self):
        manifest = {'bots': ['A', 'B'], 'request': {'mapHashes': ['map-a', 'map-b']}}
        rows = [{'mapIndex': i, 'players': [0, 1], 'seeds': [17, 29], 'taskId': f'old{i}'} for i in range(2)]
        new = [{**r, 'taskId': 'new' + r['taskId']} for r in reversed(rows)]
        pairs = matched_rows(rows, new, manifest, manifest)
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(o['mapIndex'] == n['mapIndex'] for _, o, n in pairs))
        for bad in (new[:-1], [new[0], new[0]], [{**new[0], 'seeds': [29, 17]}, new[1]]):
            with self.assertRaises(ValueError):
                matched_rows(rows, bad, manifest, manifest)

    def test_difference_intervals_keep_swapped_seats_clustered(self):
        entries = [('a', 0., 1.), ('a', 0., 1.), ('b', 1., 0.), ('b', 1., 0.),
                   ('c', 0., 0.), ('c', 0., 0.)]
        report = paired_stats(entries)
        self.assertEqual(report['winRateDelta'], 0.)
        self.assertEqual(report['transitions'], {'L->L': 2, 'L->W': 2, 'W->L': 2})
        self.assertEqual((report['improvedMaps'], report['worsenedMaps'], report['unchangedMaps']), (1, 1, 1))
        self.assertEqual(report['winRateDeltaCI95'], paired_stats(entries * 2)['winRateDeltaCI95'])

    def test_draws_distinguish_win_rate_from_score_rate(self):
        r = paired_stats([('a', 0., .5), ('a', 0., .5)])
        self.assertEqual(r['winRateDelta'], 0.)
        self.assertEqual(r['scoreRateDelta'], .5)
        self.assertEqual(r['winRateDeltaCI95'], [0., 0.])

    def test_all_directions_and_types_reported_without_self_seed_bias(self):
        old = {'mapType': 'maze', 'result': {'winner': 0}}
        new = {'mapType': 'maze', 'result': {'winner': 1}}
        rows = matrix_changes([(('map', ('A', 'B'), (17, 29)), old, new),
                               (('map', ('A', 'A'), (17, 29)), old, new)])
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['mapType'] for r in rows}, {'all', 'maze'})
        self.assertEqual({r['bot']: r['winRateDelta'] for r in rows}, {'A': -1., 'B': 1.})

    def test_missing_milestones_not_imputed_at_turn_limit(self):
        self.assertEqual(distribution([None, 12], 2)['observedGames'], 1)
        self.assertEqual(distribution([None, 12], 2)['median'], 12)
        self.assertIsNone(distribution([None], 1)['median'])
        with tempfile.TemporaryDirectory() as d:
            path = legacy_replay(Path(d) / 'synthetic.gz')
            row = {'taskId': 'synthetic', 'mapType': 'open', 'mapIndex': 0, 'replay': str(path),
                   'replaySha256': sha256(path.read_bytes()).hexdigest(),
                   'result': {'winner': None, 'reason': 'turn_limit_draw', 'turns': 300}}
            job = {'row': row, 'side': 0, 'group': 'synthetic', 'revision': 'baseline',
                   'focus': 'A', 'opponent': 'B', 'rules': STARTING_RULES}
            r = inspect_trajectory(job)
            self.assertEqual(r['firstSoldier'], [1, None])
            self.assertIsNone(r['firstSoldierContact'])
            self.assertEqual(r['firstBaseHit'], [None, None])
            s = trajectory_summary([r])
            self.assertEqual(s['firstBaseHit'][0]['observedGames'], 0)
            self.assertEqual(s['samples']['25']['gamesPresent'], 1)
            contacted = {**r, 'firstBaseHit': [200, None]}
            c = cohort_metrics([(r, contacted), (r, r), (contacted, r)])
            self.assertEqual(c['baseContactGainedGames'], 1)
            self.assertEqual(c['baseContactLostGames'], 1)
            self.assertEqual(c['revisions']['candidate']['focusFirstBaseHit']['observedGames'], 1)
            self.assertEqual(c['revisions']['candidate']['focusFirstBaseHit']['median'], 200)
            self.assertEqual(c['firstContactSameGames'], 3)
            with self.assertRaisesRegex(ValueError, 'PARAM'):
                inspect_trajectory({**job, 'rules': {**STARTING_RULES, 'SOLDIER_DMG': 22}})


if __name__ == '__main__':
    unittest.main()
