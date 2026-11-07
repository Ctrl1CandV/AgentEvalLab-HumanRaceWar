"""Replay diagnostic definitions and the authorized worker-survival candidate."""
import unittest

from arena.games.outpost.rules import Rules
from tests.helpers import fresh, settle
from tools.analyze_harassment import home_walks, local_soldiers, summarize


class HarassmentAnalysisTests(unittest.TestCase):
    def test_local_counts_are_soldiers_only_and_radius_four(self):
        _, state = fresh()
        state.add_unit(0, 'S', (5, 5))
        state.add_unit(1, 'S', (9, 5))
        state.add_unit(1, 'S', (10, 5))
        state.add_unit(1, 'W', (6, 5))
        self.assertEqual(local_soldiers(state.units, (5, 5)), [1, 1])

    def test_home_walk_uses_terrain_and_counts_first_step(self):
        _, state = fresh(extra=[(3, 2, '#')])
        walks = home_walks(state, 0)
        self.assertEqual(walks[(2, 3)], 1)
        self.assertEqual(walks[(4, 2)], 4)
        self.assertNotIn((3, 2), walks)

    def test_contact_ratio_is_per_sample_not_ratio_of_medians(self):
        row = {'harassSide': 1, 'result': {'winner': 1, 'reason': 'base_destroyed'},
               'workerDeaths': [], 'samples': [], 'soldierContacts': [
                   {'globalSoldiers': [2, 4], 'localSoldiers': [1, 2]},
                   {'globalSoldiers': [8, 8], 'localSoldiers': [0, 1]}]}
        report = summarize([row])
        self.assertEqual(report['contactGlobalHarassToOpponentRatioMedian'], 1.5)
        self.assertEqual(report['contactRatioZeroDenominatorLocal'], 1)
        self.assertEqual(report['contactLocalHarassToOpponentRatioMedian'], 2)

    def test_worker_candidate_survives_two_hits_without_reversing_single_duel(self):
        for rules, alive_after_two, soldier_hp in (({}, False, 90),
                ({'WORKER_HP': 60, 'WORKER_DMG': 10}, True, 70)):
            with self.subTest(rules=rules):
                game, state = fresh()
                state.rules = Rules.from_dict(rules)
                worker = state.add_unit(0, 'W', (5, 5))
                soldier = state.add_unit(1, 'S', (6, 5))
                for _ in range(2):
                    settle(game, state, [f'ATTACK {worker.id} 6 5'], [f'ATTACK {soldier.id} 5 5'])
                self.assertEqual(worker.id in state.units, alive_after_two)
                if alive_after_two:
                    settle(game, state, [f'ATTACK {worker.id} 6 5'], [f'ATTACK {soldier.id} 5 5'])
                self.assertNotIn(worker.id, state.units)
                self.assertEqual(state.units[soldier.id].hp, soldier_hp)


if __name__ == '__main__':
    unittest.main()
