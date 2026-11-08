"""Candidate contract and engine examples, all synthetic; no bots/hidden maps."""
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from arena.games.outpost import Outpost
from arena.games.outpost.engine import event_key
from tests.helpers import fixture_map, rotate_event, rotate_lines, rotate_state, settle
from tests import test_phase_b_holdout
from tools.phase_b_damage22 import CANDIDATE, check_candidate, check_plan, summary_checks
from tools.phase_b_holdout import BASELINE


class Damage22Tests(unittest.TestCase):
    def rules(self):
        baseline = json.loads(BASELINE.read_text())['request']['ruleset']
        return baseline, json.loads(CANDIDATE.read_text())

    def test_only_one_authorized_integer_parameter(self):
        baseline, candidate = self.rules()
        self.assertEqual(check_candidate(candidate, baseline)['SOLDIER_DMG'], 22)
        self.assertEqual(Outpost().new_match(fixture_map(), {}, [17, 29]).rules['SOLDIER_DMG'], 20)
        for bad in ({**candidate, 'TOWER_COST': 175}, {**candidate, 'SOLDIER_DMG': 23},
                    {**candidate, 'SOLDIER_DMG': 22.0}, {**candidate, 'extra': 0}):
            with self.assertRaises(ValueError):
                check_candidate(bad, baseline)

    def test_candidate_is_sent_to_bot_and_used_in_symmetric_combat(self):
        _, candidate = self.rules()
        game = Outpost()
        state = game.new_match(fixture_map(), candidate, [17, 29])
        self.assertIn('PARAM SOLDIER_DMG 22', game.init_message(state, 0))
        state.units.clear()
        a = state.add_unit(0, 'S', (6, 6)); b = state.add_unit(1, 'S', (7, 6))
        mirror = rotate_state(state)
        left, right = [f'ATTACK {a.id} 7 6'], [f'ATTACK {b.id} 6 6']
        events = settle(game, state, left, right)
        mirrored = settle(game, mirror, rotate_lines(right), rotate_lines(left))
        self.assertEqual([u.hp for u in state.units.values()], [78, 78])
        self.assertEqual(sorted((rotate_event(e) for e in events), key=event_key), mirrored)
        self.assertEqual(game.snapshot(rotate_state(state)), game.snapshot(mirror))

    def test_candidate_transcript_deterministic_and_symmetric_80_turns(self):
        _, candidate = self.rules()
        game = Outpost()
        a = game.new_match(fixture_map(), candidate, [17, 29])
        b = game.new_match(fixture_map(), candidate, [17, 29])
        mirror = game.new_match(fixture_map(), candidate, [29, 17])
        for turn in range(80):
            left = [f'MOVE 0 {("E", "S", "W", "N")[turn % 4]}', 'SPAWN S 3 2', 'bad']
            right = ['MOVE 1 W', 'SPAWN S 20 21', 'FIRE 6 6']
            events = settle(game, a, left, right)
            settle(game, b, left, right)
            mirrored = settle(game, mirror, rotate_lines(right), rotate_lines(left))
            self.assertEqual(game.state_hash(a), game.state_hash(b))
            self.assertEqual(game.snapshot(rotate_state(a)), game.snapshot(mirror))
            self.assertEqual(sorted((rotate_event(e) for e in events), key=event_key), mirrored)

    def test_matched_plan_requires_same_maps_seats_sources_and_only_damage_change(self):
        old, _, _ = test_phase_b_holdout.HoldoutGateTests().manifest()  # synthetic map identities only
        candidate = {**old['request']['ruleset'], 'SOLDIER_DMG': 22}
        new = deepcopy(old); new['request']['ruleset'] = candidate
        for task in new['tasks']:
            content = {k:v for k,v in task.items() if k != 'taskId'}
            task['taskId'] = sha256(json.dumps([new['request'], content], sort_keys=True).encode()).hexdigest()
        check_plan(new, old, candidate)
        for key in ('mapHashes', 'sourceHashes', 'seeds', 'jobs'):
            bad = deepcopy(new); bad['request'][key] = []
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_plan(bad, old, candidate)
        bad = deepcopy(new); bad['tasks'].pop()
        with self.assertRaises(ValueError):
            check_plan(bad, old, candidate)

    def test_public_and_calibration_gates_keep_their_distinct_scopes(self):
        report = json.loads(BASELINE.read_text())
        self.assertTrue(summary_checks(report, 'public')['passed'])
        report['observedChecks']['fairness'] = False
        self.assertFalse(summary_checks(report, 'public')['passed'])
        self.assertTrue(summary_checks(report, 'calibration')['passed'])
        report['rateChecks']['winRate']['balancedEveryType55'] = False
        self.assertFalse(summary_checks(report, 'calibration')['passed'])
        self.assertEqual(summary_checks({'complete': False}, 'public'), {'complete': False, 'passed': False})


if __name__ == '__main__':
    unittest.main()
