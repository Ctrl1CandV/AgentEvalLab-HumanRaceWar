"""R1: immutable budgets for paired/calibration batches, never host bot execution."""
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core import timing
from arena.core.benchmark import workload_digest
from arena.core.journal import append, records
from arena.core.sandbox import ROOT
from arena.games.outpost import Outpost
from arena.tournament import run_tournament
from tools.freeze_batch_timing import freeze_batch


class FixedTimingTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'runs/development/fixed-timing-tests' / uuid4().hex
        self.root.mkdir(parents=True)
        self.bench = self.root / 'bench.json'
        self.bench.write_text(json.dumps({'schemaVersion': 1, 'status': 'complete', 'jobs': 1,
            'cpus': sorted(os.sched_getaffinity(0))[:2], 'sandbox': 'bwrap', 'workloadSha256': workload_digest(),
            'reference': {'cpuNs': 100}, 'loadedMedianCpuNs': 150, 'speedFactor': 1.5}))

    def lock(self):
        value = timing.freeze_calibration(self.bench, workload_digest(), jobs=1,
                                          base_limits=Outpost().limits, turns=300)
        path = self.root / 'timing-lock.json'
        path.write_text(json.dumps(value))
        return path, value

    def test_lock_preserves_source_factor_and_exact_integer_budgets(self):
        path, value = self.lock()
        original = timing.Calibration.load(self.bench, workload_digest(), jobs=1)
        fixed = timing.Calibration.load(path, workload_digest(), jobs=1)
        self.assertEqual(fixed.factor, original.factor)
        self.assertEqual(fixed.report_sha256, original.report_sha256)
        self.assertEqual(fixed.cpus, original.cpus)
        assert fixed.locked_budget is not None
        self.assertEqual(fixed.locked_budget['limits'], {'TURN_CPU_MS': 150, 'INIT_CPU_MS': 3000, 'BANK_MS': 4500})
        self.assertEqual(fixed.locked_budget['wallMarginMs'], 750)
        self.assertIsNotNone(fixed.lock_sha256)
        self.bench.unlink()  # the original bytes are sealed inside the lock
        self.assertEqual(timing.Calibration.load(path, workload_digest(), jobs=1).factor, 1.5)
        self.assertEqual(value['kind'], 'fixed-runtime-budget')

    def test_rejects_tampered_report_limits_backend_concurrency_and_turns(self):
        path, value = self.lock()
        for key, bad_value in [('limits', {'TURN_CPU_MS': 151, 'INIT_CPU_MS': 3000, 'BANK_MS': 4500}),
                               ('limits', {'TURN_CPU_MS': 150.0, 'INIT_CPU_MS': 3000, 'BANK_MS': 4500}),
                               ('wallMarginMs', 750.0), ('wallMarginMs', 751), ('cpuHardLimitSeconds', 999), ('turns', True)]:
            bad = deepcopy(value); bad['budget'][key] = bad_value
            path.write_text(json.dumps(bad))
            with self.subTest(key=key), self.assertRaises(ValueError):
                timing.Calibration.load(path, workload_digest(), jobs=1)
        bad = deepcopy(value); bad['benchmarkJson'] += ' '
        path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError): timing.Calibration.load(path, workload_digest(), jobs=1)
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): timing.Calibration.load(path, workload_digest(), jobs=2)
        with self.assertRaises(ValueError):
            run_tournament([ROOT/'sdk/python/example', ROOT/'sdk/cpp/example'],
                [ROOT/'maps/scrimmage/open-01.map'], self.root/'bad-turns', jobs=1,
                fixed_timing=path, ruleset={'TURNS': 200}, max_tasks=0)
        with self.assertRaises(ValueError):
            run_tournament([ROOT/'sdk/python/example', ROOT/'sdk/cpp/example'],
                [ROOT/'maps/scrimmage/open-01.map'], self.root/'bad-backend', jobs=1,
                fixed_timing=path, sandbox='plain', max_tasks=0)

    def test_lock_is_bound_to_manifest_and_cannot_change_on_resume(self):
        path, value = self.lock()
        args = ([ROOT/'sdk/python/example', ROOT/'sdk/cpp/example'],
                [ROOT/'maps/scrimmage/open-01.map'], self.root/'planned')
        with patch('arena.tournament.run_benchmark', side_effect=AssertionError('no measurement')):
            run_tournament(*args, jobs=1, fixed_timing=path, max_tasks=0)
            value['note'] = 'changed lock identity'
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'changed'):
                run_tournament(*args, jobs=1, fixed_timing=path, max_tasks=0, resume=True)

    def test_archive_import_checks_all_headers_and_rejects_mixed_epochs(self):
        batch = self.root/'archive'; batch.mkdir()
        (batch/'manifest.json').write_text(json.dumps({'request': {'jobs': 1, 'sandbox': 'bwrap'},
                                                      'tasks': [{'taskId': 'a'}, {'taskId': 'b'}]}))
        (batch/'timing-selection.json').write_text(json.dumps({'resultFile': str(self.bench)}))
        original = timing.Calibration.load(self.bench, workload_digest(), jobs=1)
        _, lock = self.lock()
        for name in ('a', 'b'):
            header = {'type': 'header', 'params': {'TURNS': 300}, 'sandbox': 'bwrap',
                      'timingCalibration': original.header(), 'speedFactor': original.factor,
                      **{k: lock['budget'][k] for k in ('limits', 'wallMarginMs', 'cpuHardLimitSeconds')}}
            replay = batch/(name+'.gz')
            with gzip.open(replay, 'wt') as stream: stream.write(json.dumps(header)+'\n')
            append(batch/'results.jsonl', {'taskId': name, 'replay': str(replay),
                                          'replaySha256': sha256(replay.read_bytes()).hexdigest()})
        out = self.root/'imported.json'
        self.assertEqual(freeze_batch(batch, out)['headersChecked'], 2)
        with self.assertRaises(ValueError): freeze_batch(batch, out)
        replay = batch/'b.gz'
        header['speedFactor'] = 1.6
        with gzip.open(replay, 'wt') as stream: stream.write(json.dumps(header)+'\n')
        rows = records(batch/'results.jsonl'); rows[1]['replaySha256'] = sha256(replay.read_bytes()).hexdigest()
        (batch/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaisesRegex(ValueError, 'mixed'):
            freeze_batch(batch, self.root/'mixed.json')
        self.assertFalse((self.root/'mixed.json').exists())

    def test_real_bwrap_freeze_once_resume_and_paired_batch_never_remeasure(self):
        sources = []
        for name in ('a', 'b'):
            p = self.root / name; p.mkdir()
            (p/'main.py').write_text('import hrw\nhrw.read_setup(); hrw.ready()\nwhile hrw.read_turn() is not None: hrw.send([])\n')
            sources.append(p)
        maps = [ROOT/'maps/scrimmage/open-01.map']
        first = self.root/'first'
        result = run_tournament(sources, maps, first, jobs=1, freeze_timing=True,
                                ruleset={'TURNS': 200}, max_tasks=1)
        self.assertEqual(result['completed'], 1)
        lock = first/'timing-lock.json'
        digest = timing.Calibration.load(lock, workload_digest(), jobs=1).lock_sha256
        with patch('arena.tournament.run_benchmark', side_effect=AssertionError('must reuse fixed timing')):
            result = run_tournament(sources, maps, first, jobs=1, freeze_timing=True,
                                    ruleset={'TURNS': 200}, resume=True)
            self.assertEqual(result['completed'], 2)
            result = run_tournament(sources, maps, self.root/'paired', jobs=1, fixed_timing=lock,
                                    ruleset={'TURNS': 200})
            self.assertEqual(result['completed'], 2)
        headers = []
        for batch in (first, self.root/'paired'):
            for row in records(batch/'results.jsonl'):
                self.assertEqual(row['result']['faults'], [None, None])
                with gzip.open(row['replay'], 'rt') as stream: headers.append(json.loads(next(stream)))
        for header in headers:
            self.assertEqual(header['timingCalibration']['fixedRuntime']['lockSha256'], digest)
            for key in ('limits', 'speedFactor', 'wallMarginMs', 'cpuHardLimitSeconds'):
                self.assertEqual(header[key], headers[0][key])
        self.assertFalse((self.root/'paired'/'bench').exists())


if __name__ == '__main__':
    unittest.main()
