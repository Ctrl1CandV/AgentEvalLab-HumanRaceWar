"""T6-only durable launch-attempt counters; no changes to arena on disk.

Counts are non-refundable calls submitted to Bubblewrap.launch, including failed
calls, not proof that exec/READY succeeded. Cache hits never call the launcher.
Admission closes before signalling; counters settle under lock after stopping.
A stalled launch lock cannot delay the controller's interrupt/kill sequence.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from arena.core.journal import atomic_json
from arena.core.sandbox import Bubblewrap, InfrastructureError

SOURCE = Path(__file__).resolve()
ROOT = SOURCE.parents[1]
IMPORTED_SHA256 = sha256(SOURCE.read_bytes()).hexdigest()
BASIS = 'durable launcher-call attempts, including failures; no refunds; cache hits excluded'


class LaunchCounts:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root/'launch-counts.json'
        self.lock = self.root/'launch-counts.lock'
        self.gate = self.root/'launch-counts.closed'

    def create(self, compiles, bot_starts):
        if self.path.exists() or self.lock.exists() or self.gate.exists():
            raise ValueError('fresh launch counters required')
        with self.lock.open('xb'):
            pass
        atomic_json(self.path, {'schemaVersion': 1, 'compiles': 0, 'botStarts': 0,
                               'compileLimit': compiles, 'botStartLimit': bot_starts, 'closed': False})

    @contextmanager
    def locked(self, *, timeout=None):
        if self.lock.is_symlink() or self.path.is_symlink() or self.gate.is_symlink():
            raise ValueError('unsafe launch counters')
        with self.lock.open('r+b') as stream:
            if timeout is None:
                fcntl.flock(stream, fcntl.LOCK_EX)
            else:
                deadline = None
                while True:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if deadline is None: deadline = time.monotonic()+timeout
                        if time.monotonic() >= deadline:
                            raise TimeoutError('launch counter lock did not settle')
                        time.sleep(.01)
            value = json.loads(self.path.read_bytes())
            if (set(value) != {'schemaVersion','compiles','botStarts','compileLimit','botStartLimit','closed'}
                    or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                    or type(value['closed']) is not bool
                    or any(type(value[k]) is not int or value[k] < 0
                           for k in ('compiles','botStarts','compileLimit','botStartLimit'))
                    or value['compiles'] > value['compileLimit'] or value['botStarts'] > value['botStartLimit']):
                raise ValueError('invalid launch counters')
            yield value

    def launch(self, compile_call, call):
        key, limit = ('compiles','compileLimit') if compile_call else ('botStarts','botStartLimit')
        with self.locked() as value:
            if self.gate.exists() or value['closed'] or value[key] >= value[limit]:
                raise InfrastructureError('T6 launch gate closed or count cap reached')
            value[key] += 1
            atomic_json(self.path, value)
            # Hold through Popen; stopping must not wait for this lock before signalling.
            return call()

    def begin_close(self):
        if self.gate.is_symlink():
            raise ValueError('unsafe launch counter gate')
        try:
            with self.gate.open('xb') as stream:
                stream.write(b'closed\n'); stream.flush()
        except FileExistsError:
            pass

    def close(self, *, timeout=5):
        self.begin_close()
        with self.locked(timeout=timeout) as value:
            if not value['closed']:
                value['closed'] = True
                atomic_json(self.path, value)
            return {'compiles': value['compiles'], 'botStarts': value['botStarts'],
                    'countBasis': BASIS, 'closed': True,
                    'stateSha256': sha256(self.path.read_bytes()).hexdigest()}


def totals(roots):
    """Include failed cases too; close every created gate before summing."""
    values = []
    for root in roots:
        counts = LaunchCounts(root)
        if counts.path.exists():
            values.append(counts.close())
        elif counts.lock.exists():
            raise ValueError('incomplete counter initialization')
    return {'compiles': sum(v['compiles'] for v in values),
            'botStarts': sum(v['botStarts'] for v in values), 'launchCountBasis': BASIS}


def worker_argv(args, root):
    """Only replace the standard trusted worker entrypoint; preserve job argv/cwd."""
    if not isinstance(args, (list, tuple)) or len(args) != 4 or list(args[:3]) != [sys.executable,'-m','arena.worker']:
        return args
    bootstrap = ('import sys; from pathlib import Path; from hashlib import sha256\n'
                 f'if sha256(Path({str(SOURCE)!r}).read_bytes()).hexdigest() != {IMPORTED_SHA256!r}: '
                 'raise SystemExit("T6 worker counter source changed")\n'
                 f'sys.path.append({str(ROOT)!r})\n'
                 'from tools.runtime_counts import instrument; from arena.worker import main\n'
                 'with instrument(sys.argv[2]): raise SystemExit(main())')
    return [sys.executable,'-B','-c',bootstrap,args[3],str(root)]


@contextmanager
def instrument(root, *, workers=False):
    """Trusted single-threaded controller/worker scope; do not use in bot code."""
    counts = LaunchCounts(root)
    original_launch, original_popen = Bubblewrap.launch, subprocess.Popen

    def launch(launcher, *args, **kwargs):
        return counts.launch(kwargs.get('writable_build', False),
                             lambda: original_launch(launcher, *args, **kwargs))

    def popen(args, *positional, **kwargs):
        return original_popen(worker_argv(args, root), *positional, **kwargs)

    setattr(Bubblewrap, 'launch', launch)
    if workers:
        subprocess.Popen = popen
    try:
        yield
    finally:
        setattr(Bubblewrap, 'launch', original_launch)
        if workers:
            subprocess.Popen = original_popen
