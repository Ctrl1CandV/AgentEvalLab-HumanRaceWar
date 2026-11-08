"""Opening diagnostics retain missing milestones and use settled/pre-hit timing."""
from hashlib import sha256
import gzip
import json
from pathlib import Path
import unittest
from uuid import uuid4

from tests.synthetic_replay import legacy_replay
from tools.analyze_opening import inspect, summarize

ROOT = Path(__file__).resolve().parents[1]


class OpeningAnalysisTests(unittest.TestCase):
    def test_missing_milestones_are_not_silently_new_denominators(self):
        row = {'focusSide': 1, 'firstFocusSoldier': 12, 'focus24Workers': None,
               'firstFocusWorkerDeath': 18, 'samples': [],
               'firstSoldierContact': {'turn': 20, 'soldiers': [10, 6], 'local': [3, 2]}}
        absent = {**row, 'firstFocusSoldier': None, 'firstFocusWorkerDeath': None,
                  'firstSoldierContact': None}
        report = summarize([row, absent])
        self.assertEqual(report['games'], 2)
        self.assertEqual(report['milestones']['firstFocusSoldier'], {'observedGames': 1, 'median': 12})
        self.assertEqual(report['milestones']['focus24Workers']['observedGames'], 0)
        contact = report['firstSoldierContact']
        self.assertEqual(contact['games'], 1)
        self.assertEqual(contact['focusWorkerKilledBeforeContact'], 1)
        self.assertEqual(contact['globalMedianFocusHarass'], [6, 10])

    def test_synthetic_replay_first_spawn_matches_accepted_transcript(self):
        path = legacy_replay(ROOT/'runs/development/synthetic-replay-tests'/uuid4().hex/'legacy.hrw.jsonl.gz')
        with gzip.open(path, 'rt') as stream:
            records = [json.loads(line) for line in stream]
        first = next((r['turn'] for r in records if r['type'] == 'turn'
                      and any(o['op'] == 'SPAWN' and o['kind'] == 'S' for o in r['accepted'][0])), None)
        self.assertEqual(first, 1)
        result = inspect({'taskId': 'synthetic-diagnostic', 'mapName': 'smoke.map',
                          'result': records[-1]['result'], 'replay': str(path),
                          'replaySha256': sha256(path.read_bytes()).hexdigest()}, 0)
        self.assertEqual(result['firstFocusSoldier'], first)
        self.assertTrue(result['samples'])
        self.assertTrue(all(0 <= sample['workers'] <= 40 for sample in result['samples']))


if __name__ == '__main__':
    unittest.main()
