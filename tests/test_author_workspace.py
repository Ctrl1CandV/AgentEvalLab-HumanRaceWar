"""Public-material isolation; CLI/map checks only, no bots or compilation."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools import prepare_author_workspace as work
from arena.core import machine


def require_public_lock_machine(case, jobs):
    value = json.loads((work.ROOT/f'package/claude-timing-jobs{jobs}.json').read_bytes())
    origin = machine.machine_fingerprint(json.loads(value['benchmarkJson'])['machine'])
    case.assertEqual(value['machineFingerprint'], origin, 'invalid public lock binding')
    if origin != machine.machine_fingerprint(machine.machine_info()):
        case.skipTest(f'jobs{jobs} public timing lock belongs to another machine')


class AuthorWorkspaceTests(unittest.TestCase):
    def test_role_overlays_common_identity_and_public_only_smoke(self):
        with TemporaryDirectory() as d:
            paths = {role: Path(d)/role for role in ('pilot', 'deepseek', 'claude')}
            results = {role: work.build(path, role) for role, path in paths.items()}
            self.assertEqual(results['pilot']['commonMaterialSha256'], results['deepseek']['commonMaterialSha256'])
            self.assertEqual(results['pilot']['commonMaterialSha256'], results['claude']['commonMaterialSha256'])
            for role, path in paths.items():
                entries, _ = work.declared(work.ROOT, role)
                for target, source in entries: self.assertEqual((path/target).read_bytes(), (work.ROOT/source).read_bytes())
                self.assertTrue(work.validate(path, entries)['noGitRepositoryOrRemote'])
                self.assertEqual(work.smoke(path)['botExecutions'], 0)
                self.assertTrue(work.validate(path, entries)['noSymlinks'])
                for name in ('private', '.git', '.pi', 'AGENTS.md', 'STATUS.md', 'data', 'reports', 'tools'):
                    self.assertFalse((path/name).exists())
            self.assertTrue((paths['pilot']/'PILOT.md').is_file())
            self.assertFalse((paths['pilot']/'docs/BRIEF-DEEPSEEK.md').exists())
            self.assertTrue((paths['deepseek']/'docs/BRIEF-DEEPSEEK.md').is_file())
            self.assertFalse((paths['deepseek']/'PILOT.md').exists())
            self.assertTrue((paths['claude']/'BRIEF-CLAUDE.md').is_file())
            self.assertFalse((paths['claude']/'docs/BRIEF-DEEPSEEK.md').exists())
            self.assertFalse((paths['claude']/'PILOT.md').exists())
            self.assertTrue((paths['claude']/'budget-lock-jobs1.json').is_file())
            self.assertTrue((paths['claude']/'budget-lock-jobs6.json').is_file())

    def test_claude_keeps_exact_common_allowlist(self):
        old, old_count = work.declared(work.ROOT, 'deepseek')
        new, new_count = work.declared(work.ROOT, 'claude')
        self.assertEqual(old_count, new_count)
        self.assertEqual(old[:old_count], new[:new_count])
        self.assertEqual({target for target, _ in new[new_count:]},
                         {'BRIEF-CLAUDE.md', 'budget-lock-jobs1.json', 'budget-lock-jobs6.json'})

    def check_public_lock_projection(self, jobs):
        from arena.core.benchmark import workload_digest
        from arena.core.timing import Calibration
        require_public_lock_machine(self, jobs)
        value = json.loads((work.ROOT/f'package/claude-timing-jobs{jobs}.json').read_bytes())
        benchmark = json.loads(value['benchmarkJson'])
        marker = 'HIDDEN-EVALUATION-DO-NOT-EXPORT'
        benchmark.update(directory=marker, runs=[{'result': marker}], curve=marker)
        benchmark['reference']['privateExtra'] = marker
        benchmark['machine']['privateExtra'] = marker
        value['benchmarkJson'] = json.dumps(benchmark)
        value['benchmarkSha256'] = sha256(value['benchmarkJson'].encode()).hexdigest()
        raw = json.dumps(value).encode()
        projected = work.public_timing_lock(raw, jobs=jobs)
        self.assertNotIn(marker, projected.decode())
        public = json.loads(projected)
        self.assertEqual(public['sourceLockSha256'], sha256(raw).hexdigest())
        self.assertEqual(public['sourceBenchmarkSha256'], value['benchmarkSha256'])
        self.assertEqual(public['machineFingerprint'], value['machineFingerprint'])
        before = Calibration.from_bytes(raw, workload_digest(), jobs=jobs)
        after = Calibration.from_bytes(projected, workload_digest(), jobs=jobs)
        self.assertEqual((before.factor, before.cpus, before.locked_budget),
                         (after.factor, after.cpus, after.locked_budget))
        self.assertFalse(set(json.loads(public['benchmarkJson'])) & {'runs', 'curve', 'directory', 'resultFile'})

    def test_public_lock_projection_jobs1(self):
        self.check_public_lock_projection(1)

    def test_public_lock_projection_jobs6(self):
        self.check_public_lock_projection(6)

    def test_legacy_wrapper_projection_does_not_export_its_outcomes(self):
        require_public_lock_machine(self, 6)
        from arena.core.benchmark import workload_digest
        from arena.core.timing import bind_legacy_calibration
        value = json.loads((work.ROOT/'package/claude-timing-jobs6.json').read_bytes())
        benchmark = json.loads(value['benchmarkJson'])
        count = benchmark['machine'].pop('logicalCpus')
        old = {'schemaVersion': 1, 'kind': 'fixed-runtime-budget', 'budget': value['budget'],
               'benchmarkJson': json.dumps(benchmark)}
        old['benchmarkSha256'] = sha256(old['benchmarkJson'].encode()).hexdigest()
        raw = json.dumps(old).encode()
        evidence = {'fixedBudget': {'lockSha256': sha256(raw).hexdigest()},
                    'machine': {'logicalCpus': count}, 'outcomes': 'HIDDEN-OUTCOME-SENTINEL'}
        bound = bind_legacy_calibration(raw, json.dumps(evidence).encode(), workload_digest(), jobs=6)
        projected = work.public_timing_lock(json.dumps(bound).encode(), jobs=6)
        self.assertNotIn('HIDDEN-OUTCOME-SENTINEL', projected.decode())
        self.assertNotIn('legacyOrigin', projected.decode())
        self.assertEqual(json.loads(projected)['budget'], value['budget'])

    def test_projection_rejects_wrong_concurrency_budget_machine_and_unbound_lock(self):
        raw = (work.ROOT/'package/claude-timing-jobs6.json').read_bytes()
        with self.assertRaises(ValueError): work.public_timing_lock(raw, jobs=1)
        for mutation in ('budget', 'machine', 'schema'):
            with self.subTest(mutation=mutation):
                value = json.loads(raw)
                if mutation == 'budget': value['budget']['limits']['TURN_CPU_MS'] += 1
                elif mutation == 'machine': value['machineFingerprint']['logicalCpus'] += 1
                else: value['schemaVersion'] = 1
                with self.assertRaises(ValueError): work.public_timing_lock(json.dumps(value).encode(), jobs=6)

    def test_existing_directory_and_repo_subdirectory_are_not_overwritten(self):
        with TemporaryDirectory() as d:
            path = Path(d)/'existing'; path.mkdir(); (path/'user.txt').write_text('keep')
            with self.assertRaises(ValueError): work.build(path, 'pilot')
            self.assertEqual((path/'user.txt').read_text(), 'keep')
        with self.assertRaises(ValueError): work.build(work.ROOT/'runs/forbidden-export', 'pilot')

    def test_parent_git_and_symlinks_rejected(self):
        with TemporaryDirectory() as d:
            parent = Path(d); (parent/'.git').mkdir()
            with self.assertRaises(ValueError): work.build(parent/'workspace', 'deepseek')
        with TemporaryDirectory() as d:
            root = Path(d)/'source'; (root/'package').mkdir(parents=True); (root/'rules').mkdir()
            spec = json.loads((work.ROOT/'package/public-files.json').read_text())
            spec['identity'] = []; spec['renamed'] = {'rules.md': 'rules/rules.md'}
            (root/'package/public-files.json').write_text(json.dumps(spec))
            (root/'rules/rules.md').symlink_to(work.ROOT/'rules/rules.md')
            with self.assertRaisesRegex(ValueError, 'symlink'): work.declared(root, 'pilot')

    def test_private_paths_and_traversal_rejected(self):
        for path in ('private/a.py', 'runs/a', '../a', '/a', 'arena/../../secret', '.git/config', '.pi/settings.json'):
            with self.subTest(path=path), self.assertRaises(ValueError): work.safe_relative(path)

    def test_extra_file_and_missing_manifest_entry_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d)/'pilot'; work.build(path, 'pilot'); entries, _ = work.declared(work.ROOT, 'pilot')
            manifest = path/'PUBLIC-MANIFEST.sha256'; original = manifest.read_text()
            manifest.write_text('\n'.join(original.splitlines()[:-1])+'\n')
            with self.assertRaisesRegex(ValueError, 'manifest'): work.validate(path, entries)
            manifest.write_text(original); (path/'grading.py').write_text('not allowed')
            with self.assertRaisesRegex(ValueError, 'undeclared'): work.validate(path, entries)

    def test_public_reference_is_existing_measurement_not_a_new_benchmark(self):
        original_path = work.ROOT/'inbox/bench-eval-machine-2026-11-07.json'
        original = json.loads(original_path.read_text())
        public = json.loads((work.ROOT/'package/benchmark-reference.json').read_text())
        self.assertEqual(public['sourceReportSha256'], sha256(original_path.read_bytes()).hexdigest())
        self.assertEqual(public['workloadSha256'], original['workloadSha256'])
        self.assertEqual(public['singleInstance']['medianCpuNs'], original['singleInstance']['medianCpuNs'])
        self.assertFalse(set(public)&{'runs', 'curve', 'directory', 'resultFile'})


if __name__ == '__main__': unittest.main()
