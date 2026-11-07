"""Second A review: TMPDIR leases and serialized, bounded sandbox compilation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core import resources
from arena.core.sandbox import Bubblewrap, ROOT, STARTED, stop


class ReviewBalanceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'runs/development/review-balance-tests' / uuid4().hex
        self.root.mkdir(parents=True)

    def test_cpu_lock_respects_tmpdir(self):
        with patch.dict(os.environ, {'TMPDIR': str(self.root)}):
            with resources.CpuLease(1) as lease:
                expected = self.root / f'hrw-cpu-locks-{os.getuid()}'
                self.assertTrue(expected.is_dir())
                self.assertTrue(all(Path(os.readlink(f'/proc/self/fd/{fd}')).parent == expected
                                    for fd in lease.files))

    def test_empty_tmpdir_falls_back_to_tmp(self):
        with patch.dict(os.environ, {'TMPDIR': ''}):
            with resources.CpuLease(1) as lease:
                expected = Path('/tmp') / f'hrw-cpu-locks-{os.getuid()}'
                self.assertEqual(Path(os.readlink(f'/proc/self/fd/{lease.files[0]}')).parent, expected)

    def test_compile_limits_inside_real_bwrap(self):
        source = self.root / 'source'; source.mkdir()
        build = self.root / 'build'; build.mkdir()
        code = ('import json,resource; print(json.dumps({name:resource.getrlimit(getattr(resource,name)) '
                'for name in ("RLIMIT_NPROC","RLIMIT_AS","RLIMIT_FSIZE","RLIMIT_CPU")}))')
        with resources.CpuLease(1) as lease:
            launcher = Bubblewrap(); launcher.cpus = lease.cpus
            process = launcher.launch(source, ROOT / 'sdk/python',
                [f'/runtime/bin/{launcher.python_name}', '-c', code], lease.cpus[0],
                build=build, writable_build=True, cpu_seconds=60)
            try:
                out, err = process.communicate(timeout=10)
            finally:
                stop(process)
        (self.root / 'compile.stdout').write_bytes(out)
        (self.root / 'compile.stderr').write_bytes(err)
        self.assertEqual(process.returncode, 0, err)
        self.assertTrue(out.startswith(STARTED))
        limits = json.loads(out[len(STARTED):])
        self.assertEqual(limits, {'RLIMIT_NPROC': [16, 16], 'RLIMIT_AS': [2*1024**3]*2,
                                 'RLIMIT_FSIZE': [64*1024**2]*2, 'RLIMIT_CPU': [60, 60]})

    def test_prepare_waits_for_machine_compile_lock(self):
        # Trusted driver only. The submitted C++ is compiled exclusively by bwrap.
        code = '''import json,os,sys
from pathlib import Path
from arena.core.sandbox import Bubblewrap,ROOT,prepare
root=Path(sys.argv[1]); launcher=Bubblewrap()
original=launcher.launch
def observed(*a,**kw):
 (root/'launched').write_text('yes')
 return original(*a,**kw)
launcher.launch=observed
(root/'attempt').write_text('yes')
bot=prepare(ROOT/'sdk/cpp/example',root/'prepared',launcher,min(os.sched_getaffinity(0)))
(root/'result.json').write_text(json.dumps({'fault':bot.compile_fault}))
'''
        process = None
        with patch.dict(os.environ, {'TMPDIR': str(self.root)}):
            try:
                with resources.CompileLease():
                    process = subprocess.Popen([sys.executable, '-c', code, str(self.root)],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
                    deadline = time.monotonic()+10
                    while not (self.root/'attempt').exists() and process.poll() is None and time.monotonic()<deadline:
                        time.sleep(.01)
                    self.assertTrue((self.root/'attempt').exists())
                    time.sleep(.15)
                    self.assertIsNone(process.poll())
                    self.assertFalse((self.root/'launched').exists())
                out, err = process.communicate(timeout=60)
                (self.root/'driver.stdout').write_bytes(out); (self.root/'driver.stderr').write_bytes(err)
                self.assertEqual(process.returncode, 0, err)
                self.assertIsNone(json.loads((self.root/'result.json').read_text())['fault'])
                self.assertTrue((self.root/'launched').exists())
            finally:
                if process is not None and process.poll() is None:
                    process.terminate(); process.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
