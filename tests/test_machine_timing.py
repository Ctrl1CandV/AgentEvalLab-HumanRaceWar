"""M1 hardware binding regressions: no bots, compilation or measurement."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arena.core import timing
from arena.core.benchmark import workload_digest
from arena.games.outpost import Outpost


def host_record():
    cpu = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
               if line.startswith('model name'))
    return {'cpu': cpu, 'logicalCpus': os.cpu_count(), 'architecture': platform.machine(),
            'kernel': platform.release(), 'memoryBytes': os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')}


class MachineTimingTests(unittest.TestCase):
    def benchmark(self):
        return {'schemaVersion': 1, 'status': 'complete', 'jobs': 1,
                'cpus': sorted(os.sched_getaffinity(0))[:2], 'sandbox': 'bwrap',
                'workloadSha256': workload_digest(), 'reference': {'cpuNs': 100},
                'loadedMedianCpuNs': 150, 'speedFactor': 1.5, 'machine': host_record()}

    def lock(self):
        with TemporaryDirectory() as d:
            path = Path(d)/'bench.json'; path.write_text(json.dumps(self.benchmark()))
            return timing.freeze_calibration(path, workload_digest(), jobs=1,
                                             base_limits=Outpost().limits, turns=300)

    def test_foreign_machine_rejected_even_with_same_cpu_pool_and_consistent_hashes(self):
        value = self.lock(); benchmark = json.loads(value['benchmarkJson'])
        benchmark['machine']['cpu'] += ' OTHER MACHINE'
        value['benchmarkJson'] = json.dumps(benchmark)
        value['benchmarkSha256'] = sha256(value['benchmarkJson'].encode()).hexdigest()
        if 'machineFingerprint' in value:
            value['machineFingerprint']['cpu'] = benchmark['machine']['cpu']
        with self.assertRaisesRegex(ValueError, 'machine'):
            timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)

    def test_cpu_count_memory_class_and_architecture_are_checked(self):
        for key in ('logicalCpus', 'memoryBytes', 'architecture'):
            value = self.lock(); bench = json.loads(value['benchmarkJson'])
            if key == 'logicalCpus': bench['machine'][key] += 1
            elif key == 'memoryBytes': bench['machine'][key] += 2*(1 << 30)
            else: bench['machine'][key] += '-other'
            value['benchmarkJson'] = json.dumps(bench)
            value['benchmarkSha256'] = sha256(value['benchmarkJson'].encode()).hexdigest()
            value['machineFingerprint'] = timing.machine_fingerprint(bench['machine'])
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'machine'):
                timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)

    def test_local_machine_and_minor_memory_variation_do_not_remeasure(self):
        value = self.lock(); current = host_record()
        current['kernel'] = 'different diagnostic-only kernel'; current['memoryBytes'] += 1024
        with patch('arena.core.machine.machine_info', return_value=current), \
                patch('arena.tournament.run_benchmark', side_effect=AssertionError('no measurement')):
            result = timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)
        self.assertEqual(result.factor, 1.5)
        self.assertEqual(value['schemaVersion'], 2)
        self.assertEqual(value['budget']['limits']['TURN_CPU_MS'], 150)

    def test_missing_invalid_inventory_and_binding_are_rejected(self):
        for key in ('cpu', 'logicalCpus', 'memoryBytes', 'architecture'):
            bench = self.benchmark(); del bench['machine'][key]
            with TemporaryDirectory() as d:
                path = Path(d)/'bench.json'; path.write_text(json.dumps(bench))
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'machine'):
                    timing.freeze_calibration(path, workload_digest(), jobs=1,
                                              base_limits=Outpost().limits, turns=300)
        for bad in (True, 20.0, 0, None):
            value = self.lock(); value['machineFingerprint']['logicalCpus'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)

    def legacy(self):
        value = self.lock(); value.pop('machineFingerprint'); value['schemaVersion'] = 1
        bench = json.loads(value['benchmarkJson']); del bench['machine']['logicalCpus']
        bench['machine']['availableCpus'] = bench['cpus']+[2]  # leased pool, NOT host total
        value['benchmarkJson'] = json.dumps(bench)
        value['benchmarkSha256'] = sha256(value['benchmarkJson'].encode()).hexdigest()
        raw = json.dumps(value).encode()
        evidence = {'fixedBudget': {'lockSha256': sha256(raw).hexdigest()},
                    'machine': {'logicalCpus': os.cpu_count()}}
        return raw, json.dumps(evidence).encode()

    def test_legacy_binding_preserves_all_origin_bytes_and_budget(self):
        raw, evidence = self.legacy(); old = json.loads(raw)
        with self.assertRaisesRegex(ValueError, 'machine binding'):
            timing.Calibration.from_bytes(raw, workload_digest(), jobs=1)
        value = timing.bind_legacy_calibration(raw, evidence, workload_digest(), jobs=1)
        for key in ('budget', 'benchmarkJson', 'benchmarkSha256'):
            self.assertEqual(value[key], old[key])
        self.assertEqual(value['legacyOrigin']['lockJson'].encode(), raw)
        self.assertEqual(value['legacyOrigin']['evidenceJson'].encode(), evidence)
        self.assertEqual(value['machineFingerprint']['logicalCpus'], os.cpu_count())
        result = timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)
        self.assertEqual(result.report_sha256, old['benchmarkSha256'])

    def test_legacy_evidence_cannot_be_missing_mismatched_or_rebound(self):
        raw, evidence = self.legacy()
        for bad in ({}, {'fixedBudget': {'lockSha256': 'wrong'}, 'machine': {'logicalCpus': os.cpu_count()}},
                    {'fixedBudget': {'lockSha256': sha256(raw).hexdigest()}, 'machine': {'logicalCpus': 1}}):
            with self.assertRaises(ValueError):
                timing.bind_legacy_calibration(raw, json.dumps(bad).encode(), workload_digest(), jobs=1)
        value = timing.bind_legacy_calibration(raw, evidence, workload_digest(), jobs=1)
        value['legacyOrigin']['lockJson'] += ' '
        with self.assertRaises(ValueError):
            timing.Calibration.from_bytes(json.dumps(value).encode(), workload_digest(), jobs=1)
        with self.assertRaises(ValueError):
            timing.bind_legacy_calibration(json.dumps(self.lock()).encode(), evidence, workload_digest(), jobs=1)

    def test_foreign_fixed_plan_is_rejected_before_writing_any_batch(self):
        from arena.tournament import run_tournament
        from arena.core.sandbox import ROOT
        value = self.lock()
        with TemporaryDirectory() as d:
            path = Path(d)/'lock.json'; path.write_text(json.dumps(value))
            out = Path(d)/'batch'; different = host_record(); different['logicalCpus'] += 1
            with patch('arena.core.machine.machine_info', return_value=different), \
                    patch('arena.tournament.run_benchmark', side_effect=AssertionError('no measurement')):
                with self.assertRaisesRegex(ValueError, 'machine'):
                    run_tournament([ROOT/'sdk/python/example', ROOT/'sdk/cpp/example'],
                                   [ROOT/'maps/scrimmage/open-01.map'], out,
                                   jobs=1, fixed_timing=path, max_tasks=0)
            self.assertFalse(out.exists())

    def test_valid_fixed_planning_still_binds_resume_to_exact_lock(self):
        from tests.test_fixed_timing import FixedTimingTests
        # These existing regression methods only plan or inspect synthetic headers.
        names = ('test_lock_preserves_source_factor_and_exact_integer_budgets',
                 'test_rejects_tampered_report_limits_backend_concurrency_and_turns',
                 'test_lock_is_bound_to_manifest_and_cannot_change_on_resume',
                 'test_archive_import_checks_all_headers_and_rejects_mixed_epochs')
        for name in names:
            case = FixedTimingTests(name); result = unittest.TestResult(); case.run(result)
            with self.subTest(existingRegression=name):
                self.assertTrue(result.wasSuccessful(), result.errors+result.failures)


if __name__ == '__main__': unittest.main()
