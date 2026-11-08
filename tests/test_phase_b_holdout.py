"""Synthetic policy/gate tests only: no hidden inputs and no bot execution."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import generate_hidden_maps as maps
from tools import phase_b_holdout as holdout
from tools.analyze_zoo import SINGLES


class HiddenMapTests(unittest.TestCase):
    def test_preregistered_composition(self):
        entries = maps.specs()
        self.assertEqual(len(entries), 48)
        for group in maps.SETS:
            for kind in maps.TYPES:
                self.assertEqual([e['size'] for e in entries if e['path'].startswith(f'{group}/{kind}-')],
                                 [24, 28, 32, 36, 40, 32])

    def test_private_boundary_rejects_escape_and_symlink_ancestors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                maps.private_path(root / 'runs/maps', root)
            with self.assertRaises(ValueError):
                maps.private_path(root / 'private/../outside', root)
            (root / 'outside').mkdir()
            (root / 'private').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaises(ValueError):
                maps.private_path(root / 'private/maps', root)

    def test_plan_is_written_first_and_resume_reuses_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            destination = root / 'private/maps'
            calls = []

            def generated(kind, size, seed):
                plan = json.loads((destination / 'generation-plan.json').read_text())
                self.assertEqual(len(plan['maps']), 48)
                calls.append(seed)
                text = f'SYNTHETIC {kind} {size} {seed}\n'
                metadata = {'sha256': sha256(text.encode()).hexdigest(), 'type': kind,
                            'requestedSeed': seed, 'rejectedCandidates': []}
                return SimpleNamespace(text=text, metadata=lambda: metadata)

            with patch.object(maps.secrets, 'randbits', side_effect=range(48)) as draw, \
                    patch.object(maps, 'generate', side_effect=generated), patch.object(maps, 'validate'):
                maps.build(destination, root=root)
                plan = (destination / 'generation-plan.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'destination exists'):
                    maps.build(destination, root=root)
                maps.build(destination, root=root, resume=True)
                self.assertEqual(draw.call_count, 48)
                self.assertEqual(calls[:48], calls[48:])
                self.assertEqual((destination / 'generation-plan.json').read_bytes(), plan)
                target = destination / 'calibration/open-01.map'
                target.write_text('do not replace\n')
                with self.assertRaisesRegex(ValueError, 'refusing to replace'):
                    maps.build(destination, root=root, resume=True)
                self.assertEqual(target.read_text(), 'do not replace\n')

    def test_duplicate_stops_without_drawing_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = SimpleNamespace(text='SYNTHETIC\n', metadata=lambda: {
                'sha256': sha256(b'SYNTHETIC\n').hexdigest(), 'rejectedCandidates': []})
            with patch.object(maps.secrets, 'randbits', side_effect=range(48)) as draw, \
                    patch.object(maps, 'generate', return_value=result) as generate:
                with self.assertRaisesRegex(ValueError, 'duplicate map'):
                    maps.build(root / 'private/maps', root=root)
                self.assertEqual(draw.call_count, 48)
                self.assertEqual(generate.call_count, 2)

    def test_registry_and_immutable_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / 'private/input'
            maps.immutable_write(path, b'synthetic asset\n')
            maps.immutable_write(path, b'synthetic asset\n')
            maps.register(root=root)
            registry = root / 'private/HIDDEN.sha256'
            expected = f'{sha256(path.read_bytes()).hexdigest()}  private/input\n'
            self.assertEqual(registry.read_text(), expected)
            maps.register(root=root)
            self.assertEqual(registry.read_text(), expected)
            (root / 'private/link').symlink_to(path)
            with self.assertRaises(ValueError):
                maps.register(root=root)


class HoldoutGateTests(unittest.TestCase):
    def manifest(self):
        baseline = json.loads(holdout.BASELINE.read_text())
        entries = [{**e, 'sha256': sha256(('SYNTHETIC ' + e['path']).encode()).hexdigest()}
                   for e in maps.specs()]
        catalog = {'maps': entries}
        calibration = sorted((e for e in entries if e['path'].startswith('calibration/')), key=lambda e: e['path'])
        request = deepcopy(baseline['request'])
        request['maps'] = [str(holdout.ROOT / 'private/maps' / e['path']) for e in calibration]
        request['mapHashes'] = [e['sha256'] for e in calibration]
        request['sources'] = [str(holdout.ROOT / 'bots/public' / n) for n in baseline['bots']]
        tasks = []
        for a, b in request['pairs']:
            for index, entry in enumerate(calibration):
                for swapped in (False, True):
                    task = {'players': [b, a] if swapped else [a, b], 'mapIndex': index,
                            'mapName': Path(entry['path']).name, 'mapType': entry['type'],
                            'seeds': [29, 17] if swapped else [17, 29], 'swapped': swapped}
                    task['taskId'] = sha256(json.dumps([request, task], sort_keys=True).encode()).hexdigest()
                    tasks.append(task)
        return {'bots': baseline['bots'], 'request': request, 'tasks': tasks}, catalog, baseline

    def test_exact_2208_plan_and_rejection_of_changed_seats_maps_or_seeds(self):
        manifest, catalog, baseline = self.manifest()
        holdout.validate_plan(manifest, catalog, baseline)
        for mutation in ('seeds', 'grading', 'missingSelf', 'taskId', 'source'):
            bad = deepcopy(manifest)
            if mutation == 'seeds':
                bad['tasks'][0]['seeds'] = [17, 17]
            elif mutation == 'grading':
                bad['request']['maps'][0] = bad['request']['maps'][0].replace('calibration/', 'grading/')
            elif mutation == 'missingSelf':
                bad['tasks'] = bad['tasks'][:-48]
            elif mutation == 'source':
                bad['request']['sourceHashes'][0] = 'changed'
            else:
                bad['tasks'][0]['taskId'] = 'changed'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                holdout.validate_plan(bad, catalog, baseline)

    def example(self):
        baseline = json.loads(holdout.BASELINE.read_text())
        report = deepcopy(baseline)
        report.update(expectedGames=2208, completedGames=2208)
        # Only the five requested items gate this review; public eligibility,
        # fairness and length are deliberately false here and do not gate it.
        report['eligiblePublicD6Matrix'] = False
        for k in ('fairness', 'selfMedianAtLeast120', 'selfBy60Below20'):
            report['observedChecks'][k] = False
        report['request']['SECRET_MAP_SEED'] = 'must-not-export'
        report['bootstrap']['SECRET_MAP_SEED'] = 'must-not-export'
        for row in report['matrix']:
            row['SECRET_MAP_LAYOUT'] = 'must-not-export'
        report['replayAudit'] = {'allVerified': True, 'replays': [{'verified': True}] * 2208}
        catalog = {'maps': [{**e, 'sha256': sha256(e['path'].encode()).hexdigest(),
                            'requestedSeed': 'must-not-export', 'metrics': 'must-not-export'} for e in maps.specs()]}
        m = report['bots'].index('M-balanced')
        other = report['bots'].index('Z-rush')
        rows = []
        for index in range(24):
            for _ in range(2):
                rows.append({'mapIndex': index, 'players': [m, m], 'result': {
                    'reason': 'base_destroyed' if index < 6 else 'turn_limit_score'}})
                rows.append({'mapIndex': index, 'players': [m, other], 'result': {'winner': 0}})
        return report, catalog, rows

    def test_only_requested_items_gate_and_export_is_allowlisted(self):
        report, catalog, rows = self.example()
        summary = holdout.aggregate(report, catalog, rows)
        self.assertEqual(summary['decision'], 'pass')
        self.assertEqual(len(summary['checks10_2']), 5)
        self.assertNotIn('must-not-export', json.dumps(summary))
        self.assertNotIn('eligiblePublicD6Matrix', summary)
        self.assertEqual(summary['balancedSelf']['baseEndingFractionCI95'][0], 1 / 12)

    def test_any_requested_failure_or_audit_failure_stops(self):
        report, catalog, rows = self.example()
        for key in ('eachSingleLosesToAnother', 'balancedOverall70', 'balancedEveryType55'):
            bad = deepcopy(report)
            bad['rateChecks']['winRate'][key] = False
            self.assertEqual(holdout.aggregate(bad, catalog, rows)['decision'], 'stop')
        for key in ('drawRateBelow10', 'bothEndings20To80'):
            bad = deepcopy(report)
            bad['observedChecks'][key] = False
            self.assertEqual(holdout.aggregate(bad, catalog, rows)['decision'], 'stop')
        bad = deepcopy(report)
        bad['replayAudit']['allVerified'] = False
        self.assertEqual(holdout.aggregate(bad, catalog, rows)['decision'], 'stop')
        bad = deepcopy(report)
        next(r for r in bad['matrix'] if r['bot'] == 'M-balanced' and r['opponent'] == SINGLES[0]
             and r['mapType'] == 'maze')['winRate'] = .4
        self.assertEqual(holdout.aggregate(bad, catalog, rows)['decision'], 'stop')

    def test_incomplete_does_not_publish_a_partial_matrix(self):
        report, catalog, rows = self.example()
        report.update(complete=False, completedGames=2207)
        summary = holdout.aggregate(report, catalog, rows)
        self.assertEqual(summary['decision'], 'stop')
        self.assertNotIn('matrix', summary)


if __name__ == '__main__':
    unittest.main()
