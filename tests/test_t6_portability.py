"""Foreign-host skips are selective; malformed bindings still fail. No processes."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arena.core import machine
from tests import test_author_workspace as workspace

work = workspace.work
require_public_lock_machine = workspace.require_public_lock_machine


MACHINE_TESTS = ('test_public_lock_projection_jobs1', 'test_public_lock_projection_jobs6',
                 'test_legacy_wrapper_projection_does_not_export_its_outcomes')


class PortabilityTests(unittest.TestCase):
    def origin(self):
        lock = json.loads((work.ROOT/'package/claude-timing-jobs6.json').read_bytes())
        return json.loads(lock['benchmarkJson'])['machine']

    def test_foreign_host_skips_exactly_three_checks_without_launching(self):
        foreign = deepcopy(self.origin()); foreign['cpu'] += ' OTHER HOST'
        result = unittest.TestResult()
        with patch.object(machine, 'machine_info', return_value=foreign), \
                patch('subprocess.Popen', side_effect=AssertionError('skip before process')):
            unittest.TestSuite(workspace.AuthorWorkspaceTests(name) for name in MACHINE_TESTS).run(result)
        self.assertEqual(result.testsRun, 3)
        self.assertEqual(len(result.skipped), 3)
        self.assertEqual(result.errors+result.failures, [])

    def test_matching_machine_runs_all_three_checks(self):
        result = unittest.TestResult()
        with patch.object(machine, 'machine_info', return_value=self.origin()), \
                patch('subprocess.Popen', side_effect=AssertionError('metadata only')):
            unittest.TestSuite(workspace.AuthorWorkspaceTests(name) for name in MACHINE_TESTS).run(result)
        self.assertEqual((result.testsRun, len(result.skipped)), (3, 0))
        self.assertEqual(result.errors+result.failures, [])

    def test_each_fingerprint_component_can_require_skip_but_kernel_cannot(self):
        for key in ('cpu','architecture','logicalCpus','memoryBytes'):
            foreign = deepcopy(self.origin())
            foreign[key] = foreign[key]+' OTHER' if isinstance(foreign[key],str) else foreign[key]+(2 << 30)
            with self.subTest(key=key), patch.object(machine, 'machine_info', return_value=foreign):
                with self.assertRaises(unittest.SkipTest): require_public_lock_machine(self, 6)
        local = deepcopy(self.origin()); local['kernel'] = 'different kernel'
        with patch.object(machine, 'machine_info', return_value=local): require_public_lock_machine(self, 6)

    def test_invalid_lock_binding_is_failure_not_skip(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'package').mkdir()
            value = json.loads((work.ROOT/'package/claude-timing-jobs6.json').read_bytes())
            value['machineFingerprint']['logicalCpus'] += 1
            (root/'package/claude-timing-jobs6.json').write_text(json.dumps(value))
            with patch.object(work, 'ROOT', root):
                with self.assertRaises(AssertionError): require_public_lock_machine(self, 6)


if __name__ == '__main__': unittest.main()
