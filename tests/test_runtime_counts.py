"""Pure launch accounting: all launch delegates/Popen calls are synthetic."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arena.core.sandbox import Bubblewrap, InfrastructureError
from tools import runtime_counts as counts


class RuntimeCountsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.meter = counts.LaunchCounts(self.root); self.meter.create(4, 40)
        self.guard = patch('subprocess.Popen', side_effect=AssertionError('no real process permitted'))
        self.guard.start(); self.addCleanup(self.guard.stop)

    def test_calls_count_before_delegation_failures_are_not_refunded(self):
        def failed():
            self.assertEqual(json.loads(self.meter.path.read_bytes())['compiles'], 1)
            raise OSError('synthetic spawn failure')
        with self.assertRaises(OSError): self.meter.launch(True, failed)
        for _ in range(3): self.meter.launch(False, lambda: None)
        value = self.meter.close()
        self.assertEqual((value['compiles'], value['botStarts']), (1, 3))
        self.assertIn('including failures', value['countBasis'])

    def test_cache_hits_and_unstarted_tasks_do_not_create_counts(self):
        self.assertEqual(self.meter.close()['compiles'], 0)
        self.assertEqual(self.meter.close()['botStarts'], 0)

    def test_shared_instances_and_concurrent_calls_do_not_lose_updates(self):
        def call(_):
            return counts.LaunchCounts(self.root).launch(False, lambda: None)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(call, range(24)))
        self.assertEqual(self.meter.close()['botStarts'], 24)

    def test_close_blocks_late_worker_calls_and_is_idempotent(self):
        self.meter.launch(False, lambda: None)
        first = self.meter.close()
        with self.assertRaises(InfrastructureError):
            counts.LaunchCounts(self.root).launch(False, lambda: self.fail('late launch'))
        self.assertEqual(self.meter.close(), first)

    def test_closing_admission_never_waits_for_stalled_launch_lock(self):
        with self.meter.lock.open('r+b') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(self.meter.begin_close)
                    try:
                        future.result(timeout=1)
                    finally:
                        fcntl.flock(held, fcntl.LOCK_UN)
                fcntl.flock(held, fcntl.LOCK_EX)
                with self.assertRaises(TimeoutError): self.meter.close(timeout=0)
            finally:
                fcntl.flock(held, fcntl.LOCK_UN)
        self.assertTrue(self.meter.gate.exists())
        self.assertEqual(self.meter.close()['botStarts'], 0)

    def test_caps_are_checked_before_delegation(self):
        other = self.root/'limited'; other.mkdir()
        meter = counts.LaunchCounts(other); meter.create(0, 1)
        with self.assertRaises(InfrastructureError): meter.launch(True, lambda: self.fail('compile'))
        meter.launch(False, lambda: None)
        with self.assertRaises(InfrastructureError): meter.launch(False, lambda: self.fail('extra start'))
        self.assertEqual(meter.close()['botStarts'], 1)

    def test_damaged_state_is_not_repaired_or_reported_as_zero(self):
        self.meter.path.write_bytes(b'{broken')
        with self.assertRaises(ValueError): self.meter.close()
        self.assertEqual(self.meter.path.read_bytes(), b'{broken')

    def test_only_standard_worker_argv_is_wrapped_and_options_are_preserved(self):
        original = [sys.executable,'-m','arena.worker','/batch/job.json']
        options = {'cwd': '/frozen/runtime', 'pass_fds': (7, 8), 'env': {'PATH': '/usr/bin:/bin'}}
        with patch.object(subprocess, 'Popen', return_value='fake-process') as popen:
            with patch.object(Bubblewrap, 'launch', return_value='fake-sandbox') as launch:
                saved = Bubblewrap.launch
                launcher = object.__new__(Bubblewrap)
                args = (launcher, Path('/opaque-bot'), Path('/opaque-sdk'), ['synthetic'], 0)
                with counts.instrument(self.root, workers=True):
                    self.assertEqual(Bubblewrap.launch(*args, writable_build=True), 'fake-sandbox')
                    self.assertEqual(Bubblewrap.launch(*args), 'fake-sandbox')
                    self.assertEqual(subprocess.Popen(original, **options), 'fake-process')
                    rewritten = popen.call_args.args[0]
                    self.assertEqual(rewritten[-2:], ['/batch/job.json', str(self.root)])
                    self.assertIn('from arena.worker import main', rewritten[3])
                    self.assertEqual(popen.call_args.kwargs, options)
                    subprocess.Popen(['/usr/bin/bwrap', 'synthetic'])
                    self.assertEqual(popen.call_args.args[0], ['/usr/bin/bwrap', 'synthetic'])
                self.assertIs(Bubblewrap.launch, saved)
                self.assertEqual(launch.call_count, 2)
        self.assertEqual((self.meter.close()['compiles'], self.meter.close()['botStarts']), (1, 1))

    def test_frozen_worker_bootstrap_installs_accounting_without_running_worker(self):
        argv = counts.worker_argv([sys.executable,'-m','arena.worker','/batch/job.json'], self.root)
        with patch('arena.worker.main', return_value=0) as worker, patch.object(sys, 'argv', ['-c', *argv[-2:]]), \
                patch.object(sys, 'path', list(sys.path)):
            with self.assertRaises(SystemExit) as exit:
                exec(argv[3], {'__name__': '__main__'})
            self.assertEqual(exit.exception.code, 0); worker.assert_called_once_with()
        self.assertEqual(self.meter.close()['botStarts'], 0)

    def test_changed_counter_source_is_rejected_before_worker_entry(self):
        argv = counts.worker_argv([sys.executable,'-m','arena.worker','/batch/job.json'], self.root)
        code = argv[3].replace(counts.IMPORTED_SHA256, '0'*64)
        with patch('arena.worker.main', side_effect=AssertionError('must reject first')), \
                patch.object(sys, 'argv', ['-c', *argv[-2:]]):
            with self.assertRaisesRegex(SystemExit, 'counter source changed'):
                exec(code, {'__name__': '__main__'})

    def test_failed_cases_are_included_in_acceptance_total(self):
        self.meter.launch(True, lambda: None)
        self.meter.launch(False, lambda: None)
        absent = self.root/'not-started'
        result = counts.totals([self.root, absent])
        self.assertEqual((result['compiles'], result['botStarts']), (1, 1))
        self.assertTrue(self.meter.close()['closed'])


if __name__ == '__main__': unittest.main()
