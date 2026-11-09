"""Synthetic terminal-result checks; no bots or hidden inputs."""
from copy import deepcopy
import unittest

from tools.analyze_l0_endings import summarize


class L0EndingTests(unittest.TestCase):
    def example(self):
        return {'players': [0, 1], 'status': 'complete', 'result': {'faults': [None, None],
            'reason': 'turn_limit_deposit', 'turns': 300, 'scores': [0, 0],
            'deposited': [1200, 60], 'base_hp': [600, 600], 'winner': 0}}

    def test_economic_tiebreak_and_random_tower_wins_are_distinct(self):
        row = self.example(); tower = deepcopy(row)
        tower['result'].update(scores=[0, 7], reason='turn_limit_score', winner=1)
        r = summarize([row, tower], ['Z-miner', 'Z-random'])
        self.assertEqual(r['turnLimitGames'], 2)
        self.assertEqual(r['minerWinsOnDepositsWithBothTowerScoresZero'], 1)
        self.assertEqual(r['randomWinsOnPositiveTowerScore'], 1)
        self.assertEqual(r['baseDestroyedGames'], 0)
        self.assertEqual(r['bothBasesSurvivedGames'], 2)

    def test_swapping_seats_preserves_semantic_counts(self):
        row = self.example(); flipped = deepcopy(row); flipped['players'].reverse()
        for field in ('scores', 'deposited', 'base_hp'): flipped['result'][field].reverse()
        flipped['result']['winner'] = 1
        self.assertEqual(summarize([row], ['Z-miner','Z-random']), summarize([flipped], ['Z-miner','Z-random']))

    def test_inconsistent_reason_or_faulted_input_is_not_accepted(self):
        for field, value in (('winner', 1), ('reason', 'turn_limit_score'), ('faults', ['crash', None])):
            row = self.example(); row['result'][field] = value
            with self.assertRaises(ValueError): summarize([row], ['Z-miner','Z-random'])
        with self.assertRaises(ValueError): summarize([], ['Z-miner','Z-random'])

    def test_hp_tiebreak_and_mutual_base_destruction(self):
        row = self.example(); row['result'].update(deposited=[60,60], base_hp=[600,500], reason='turn_limit_hp')
        self.assertEqual(summarize([row], ['Z-miner','Z-random'])['turnLimitGames'], 1)
        row['result'].update(base_hp=[0,0], winner=None, reason='mutual_base_destroyed', turns=99)
        r = summarize([row], ['Z-miner','Z-random'])
        self.assertEqual(r['baseDestroyedGames'], 1)
        self.assertEqual(r['bothBasesSurvivedGames'], 0)


if __name__ == '__main__':
    unittest.main()
