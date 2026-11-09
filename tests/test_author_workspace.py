"""Public-material isolation; CLI/map checks only, no bots or compilation."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools import prepare_author_workspace as work


class AuthorWorkspaceTests(unittest.TestCase):
    def test_role_overlays_common_identity_and_public_only_smoke(self):
        with TemporaryDirectory() as d:
            paths = {role: Path(d)/role for role in ('pilot', 'deepseek')}
            results = {role: work.build(path, role) for role, path in paths.items()}
            self.assertEqual(results['pilot']['commonMaterialSha256'], results['deepseek']['commonMaterialSha256'])
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
