"""Bounded real-sandbox resource/cleanup probes, not a claim of complete security.

No fork bomb, host OOM, credential access or network contact. Compile-tree
inspection checks the approved per-process/task contract, not aggregate cgroups.
"""
import json
import os
from pathlib import Path
import selectors
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, ROOT, prepare, stop
from arena.core.transport import Connection, exchange
from arena.games.outpost import Outpost
from tests.helpers import fixture_map
from tests.test_cleanup import state as process_state


class SecurityAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'runs/development/security-acceptance-tests' / uuid4().hex
        self.root.mkdir(parents=True)
        self.lease = CpuLease(1)
        self.addCleanup(self.lease.__exit__, None, None, None)
        self.launcher = Bubblewrap()
        self.launcher.cpus = self.lease.cpus

    def probe(self, name, code):
        source = self.root / name; source.mkdir()
        (source / 'main.py').write_text(code)
        bot = prepare(source, self.root / 'prepared', self.launcher, self.lease.cpus[0])
        game = Outpost(); state = game.new_match(fixture_map(), {}, [17, 29])
        conn = Connection(bot, self.launcher, self.lease.cpus[0], 10)
        replies = []
        try:
            replies += exchange([conn], [game.init_message(state, 0)], [2000], [2500], b'READY')
            replies += exchange([conn], [game.observation(state, 0)], [500], [1500])
        finally:
            conn.close()
            (self.root / 'probe.json').write_text(json.dumps({'replies': [r.record() for r in replies],
                'stderr': conn.stderr.decode(errors='replace'), 'sandboxPid': conn.process.pid,
                'stateAfterClose': process_state(conn.process.pid)}, indent=2) + '\n')
        self.assertTrue(all(r.fault is None for r in replies), replies)
        self.assertIn(process_state(conn.process.pid), (None, 'Z'))
        return replies

    def test_busy_reply_does_not_require_submillisecond_proc_scans(self):
        source = self.root / 'busy'; source.mkdir()
        (source / 'main.py').write_text('''import hrw,time
hrw.read_setup();hrw.ready();hrw.read_turn()
a=time.process_time_ns()
while time.process_time_ns()-a<100000000: pass
hrw.send([]);hrw.read_turn()
''')
        bot = prepare(source, self.root / 'prepared', self.launcher, self.lease.cpus[0])
        game = Outpost(); state = game.new_match(fixture_map(), {}, [17, 29])
        conn = Connection(bot, self.launcher, self.lease.cpus[0], 10)
        try:
            ready = exchange([conn], [game.init_message(state, 0)], [2000], [2500], b'READY')[0]
            self.assertIsNone(ready.fault)
            with patch.object(conn.clock, 'read_ns', wraps=conn.clock.read_ns) as reads:
                reply = exchange([conn], [game.observation(state, 0)], [500], [1500])[0]
            (self.root / 'poll-count.json').write_text(json.dumps({'calls': reads.call_count,
                'reply': reply.record()}, indent=2)+'\n')
            self.assertIsNone(reply.fault)
            self.assertGreater(reply.cpu_ns, 95_000_000)
            self.assertLess(reads.call_count, 35)
        finally:
            conn.close()

    def test_watchdog_wait_is_clamped_to_short_wall_deadline(self):
        source = self.root / 'sleep'; source.mkdir()
        (source / 'main.py').write_text('import hrw,time\nhrw.read_setup();hrw.ready();hrw.read_turn();time.sleep(.2);hrw.send([])\n')
        bot = prepare(source, self.root / 'prepared', self.launcher, self.lease.cpus[0])
        game = Outpost(); state = game.new_match(fixture_map(), {}, [17, 29])
        conn = Connection(bot, self.launcher, self.lease.cpus[0], 10)
        waits = []
        original = selectors.DefaultSelector.select
        def select(selector, timeout=None):
            waits.append(timeout)
            return original(selector, timeout)
        try:
            ready = exchange([conn], [game.init_message(state, 0)], [2000], [2500], b'READY')[0]
            self.assertIsNone(ready.fault)
            with patch.object(selectors.DefaultSelector, 'select', select):
                reply = exchange([conn], [game.observation(state, 0)], [1000], [5])[0]
            (self.root / 'short-deadline.json').write_text(json.dumps({'waitSeconds': waits,
                'reply': reply.record()}, indent=2)+'\n')
            self.assertEqual(reply.fault, 'wall_timeout')
            self.assertTrue(waits)
            self.assertTrue(all(0 <= t <= .005 for t in waits))
        finally:
            conn.close()

    def test_address_space_and_descriptors_are_hard_limited(self):
        self.probe('as-fd', '''import hrw, resource, errno, os
assert resource.getrlimit(resource.RLIMIT_AS) == (512*1024**2,)*2
try: memory=bytearray(600*1024**2)
except MemoryError: pass
else: raise AssertionError('address-space cap did not reject 600MiB')
fds=[]
try:
 for i in range(80): fds.append(os.open('/dev/null',os.O_RDONLY))
except OSError as error: assert error.errno==errno.EMFILE
else: raise AssertionError('descriptor cap absent')
for fd in fds: os.close(fd)
hrw.read_setup();hrw.ready();hrw.read_turn();hrw.send([]);hrw.read_turn()
''')

    def test_exited_thread_cpu_is_not_lost(self):
        replies = self.probe('exited-threads', '''import hrw, threading, time
hrw.read_setup();hrw.ready();hrw.read_turn()
def work():
 start=time.thread_time_ns()
 while time.thread_time_ns()-start<3000000: pass
for i in range(24):
 thread=threading.Thread(target=work);thread.start();thread.join()
hrw.send([]);hrw.read_turn()
''')
        self.assertGreater(replies[1].cpu_ns, 65_000_000)

    def test_no_network_or_host_paths_and_runtime_code_is_readonly(self):
        self.probe('isolation', '''import hrw, os, errno, socket
# bwrap adds PWD for its --chdir, not inherited host configuration.
assert set(os.environ)=={'PATH','HOME','PWD','TMPDIR','TMP','TEMP','LANG','LC_ALL','PYTHONHASHSEED','PYTHONDONTWRITEBYTECODE','PYTHONPATH'}, sorted(os.environ)
assert os.environ['PWD']=='/bot'
assert not os.path.exists('/etc/passwd') and not os.path.exists('/home/claude-dev')
assert {x.split(':')[0].strip() for x in open('/proc/net/dev').read().splitlines()[2:]}=={'lo'}
# Only a documentation-only TEST-NET address, no host/external contact possible.
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
try: s.connect(('192.0.2.1',9))
except OSError as error: assert error.errno in (errno.ENETUNREACH,errno.EPERM)
else: raise AssertionError('external route exists')
s.close()
for path in ('/bot/main.py','/sdk/hrw.py'):
 try: open(path,'a')
 except OSError as error: assert error.errno==errno.EROFS
 else: raise AssertionError('readonly mount was writable')
hrw.read_setup();hrw.ready();hrw.read_turn();hrw.send([]);hrw.read_turn()
''')

    def test_bounded_compile_tree_is_removed_on_stop_and_records_limits(self):
        source = self.root / 'source'; source.mkdir()
        build = self.root / 'build'; build.mkdir()
        code = '''import json,os,resource,time
for i in range(2):
 pid=os.fork()
 if pid==0:
  memory=bytearray(8*1024**2)
  time.sleep(30)
  os._exit(0)
print(json.dumps({'ready':True,'addressSpace':resource.getrlimit(resource.RLIMIT_AS),
 'tasks':resource.getrlimit(resource.RLIMIT_NPROC),'affinity':sorted(os.sched_getaffinity(0))}),flush=True)
time.sleep(30)
'''
        command = [f'/runtime/bin/{self.launcher.python_name}', '-c', code]
        p = self.launcher.launch(source, ROOT / 'sdk/python', command, self.lease.cpus[0],
                                 build=build, writable_build=True, cpu_seconds=5)
        observed = {}; stdout = bytearray()
        try:
            assert p.stdout is not None
            os.set_blocking(p.stdout.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(p.stdout, selectors.EVENT_READ)
                deadline = time.monotonic()+5
                while b'"ready": true' not in stdout and time.monotonic()<deadline:
                    for key, _ in selector.select(.02):
                        stdout.extend(os.read(key.fd, 4096))
            self.assertIn(b'"ready": true', stdout)
            pending = [p.pid]
            while pending:
                pid = pending.pop()
                if pid in observed: continue
                proc = Path(f'/proc/{pid}')
                children = [int(x) for x in (proc/'task'/str(pid)/'children').read_text().split()]
                pending.extend(children)
                observed[pid] = {'children': children, 'affinity': sorted(os.sched_getaffinity(pid)),
                                 'status': (proc/'status').read_text()}
            self.assertGreaterEqual(len(observed), 4)
            self.assertTrue(all(v['affinity']==[self.lease.cpus[0]] for v in observed.values()))
        finally:
            stop(p)
            deadline = time.monotonic()+2
            while any(process_state(pid) not in (None, 'Z') for pid in observed) and time.monotonic()<deadline:
                time.sleep(.01)
            after = {pid: process_state(pid) for pid in observed}
            (self.root / 'compile-tree.json').write_text(json.dumps({'stdout': stdout.decode(errors='replace'),
                'processes': observed, 'afterStop': after, 'aggregateHardLimitImplemented': False,
                'limits': 'Finite two-child diagnostic. AS=2GiB per process and NPROC=16; no aggregate memory/CPU/disk claim. Approved review contract uses serialized trusted compilation.'}, indent=2)+'\n')
        self.assertTrue(all(s in (None, 'Z') for s in after.values()), after)
        detail = json.loads(stdout.decode().splitlines()[1])
        self.assertEqual(detail['addressSpace'], [2*1024**3]*2)
        self.assertEqual(detail['tasks'], [16, 16])


if __name__ == '__main__':
    unittest.main()
