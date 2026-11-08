"""2026-11-07 review regressions; all bot/probe execution stays in real bwrap."""
import json
import os
from pathlib import Path
import selectors
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.sandbox import Bubblewrap, CpuClock, InfrastructureError, ROOT, prepare, stop
from arena.core.transport import Connection, exchange
from arena.games.outpost import Outpost
from arena.games.outpost.replay import verify
from arena.match import play
from tests.helpers import fixture_map
from tests.test_runtime import IDLE


class ReviewRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "runs/development/review-runtime" / uuid4().hex
        self.root.mkdir(parents=True)
        self.map = fixture_map()

    def bot(self, name, code, filename="main.py"):
        p = self.root / name
        p.mkdir()
        (p / filename).write_text(code)
        return p

    def match(self, a, b=None):
        b = b or self.bot("idle", IDLE)
        row = play([a, b], self.map, self.root / "matches", [17, 29])
        self.assertEqual(row["status"], "complete", row)
        self.assertEqual(verify(Path(row["replay"]))["result"], row["result"])
        self.assertEqual(len((Path(row["directory"]).parent / "results.jsonl").read_text().splitlines()), 1)
        return row

    def test_exit_125_on_turn_five_is_one_bot_loss_not_a_retry(self):
        code = IDLE.replace("import hrw", "import hrw, os").replace(
            "while hrw.read_turn() is not None:", "while (turn := hrw.read_turn()) is not None:\n    if turn.number == 5: os._exit(125)")
        row = self.match(self.bot("exit125", code))
        self.assertEqual(row["result"]["faults"], ["crash", None])
        self.assertEqual(row["result"]["turns"], 4)
        self.assertEqual(row["result"]["winner"], 1)

    def test_early_exit_keeps_queued_start_marker_when_stdin_breaks_first(self):
        class WriteFirstSelector(selectors.DefaultSelector):
            def select(self, timeout=None):
                return sorted(super().select(timeout), key=lambda item: item[0].data[1] != "in")

        launcher = Bubblewrap()
        game = Outpost()
        state = game.new_match(self.map, {}, [17, 29])
        records = []
        for code in (2, 125):
            with self.subTest(exit_code=code):
                bot = prepare(self.bot(f"early-exit-{code}", f"raise SystemExit({code})\n"),
                              self.root / f"prepared-{code}", launcher, launcher.cpus[0])
                conn = Connection(bot, launcher, launcher.cpus[0], 10)
                try:
                    conn.process.wait(timeout=5)  # marker is queued; stdin already broken
                    with patch("arena.core.transport.selectors.DefaultSelector", WriteFirstSelector):
                        replies = exchange([conn], [game.init_message(state, 0)], [2000], [6000], b"READY")
                    records.extend(r.record() for r in replies)
                    self.assertEqual(replies[0].fault, "crash")
                    self.assertTrue(conn.started)
                finally:
                    conn.close()
                    (self.root / "early-exit-replies.json").write_text(json.dumps(records, indent=2))

    def test_cpu_after_end_is_charged_to_next_reply(self):
        code = '''import hrw, threading, time
hrw.read_setup(); hrw.ready()
hrw.read_turn(); hrw.send([])
def work():
    time.sleep(0.04)
    begin = time.thread_time_ns()
    while time.thread_time_ns() - begin < 80000000: pass
thread = threading.Thread(target=work)
thread.start()
hrw.read_turn(); thread.join(); hrw.send([])
hrw.read_turn()
'''
        launcher = Bubblewrap()
        bot = prepare(self.bot("between-turns", code), self.root / "prepared", launcher, launcher.cpus[0])
        game = Outpost()
        state = game.new_match(self.map, {}, [17, 29])
        conn = Connection(bot, launcher, launcher.cpus[0], 10)
        records = []
        try:
            records += exchange([conn], [game.init_message(state, 0)], [2000], [2500], b"READY")
            records += exchange([conn], [game.observation(state, 0)], [1000], [1500])
            # Deliberately let work happen outside exchange(), like a slow opponent.
            time.sleep(0.25)
            records += exchange([conn], [game.observation(state, 0)], [1000], [1500])
            self.assertTrue(all(r.fault is None for r in records))
            self.assertGreater(records[-1].cpu_ns, 60_000_000)
        finally:
            conn.close()
            (self.root / "replies.json").write_text(json.dumps([r.record() for r in records], indent=2))

    def test_fork_loop_and_affinity_changes_are_denied(self):
        code = '''import os, errno, hrw
for _ in range(32):
    try:
        child = os.fork()
    except OSError as error:
        assert error.errno == errno.EPERM
    else:
        if child == 0: os._exit(0)
        os.waitpid(child, 0)
        raise AssertionError('fork was permitted')
try:
    os.sched_setaffinity(0, set(range(1024)))
except OSError as error:
    assert error.errno == errno.EPERM
else:
    raise AssertionError('affinity change was permitted')
assert len(os.sched_getaffinity(0)) == 1
'''+IDLE
        row = self.match(self.bot("syscalls", code))
        self.assertEqual(row["result"]["faults"], [None, None])

    def test_python_threads_work_but_are_bounded(self):
        code = '''import threading, resource, hrw, sys
assert resource.getrlimit(resource.RLIMIT_NPROC) == (16, 16)
threading.stack_size(262144)
event = threading.Event()
threads = []
for _ in range(48):
    try:
        t = threading.Thread(target=event.wait)
        t.start()
        threads.append(t)
    except RuntimeError:
        break
assert 1 <= len(threads) <= 15, len(threads)
print('workerThreads='+str(len(threads)), file=sys.stderr)
event.set()
for t in threads: t.join()
'''+IDLE
        row = self.match(self.bot("threads", code))
        self.assertEqual(row["result"]["faults"], [None, None])

    def test_cpp_threads_work_but_are_bounded(self):
        code = '''#include <thread>
#include <atomic>
#include <vector>
#include <sys/resource.h>
#include <cassert>
#include "hrw.hpp"
int main() {
    rlimit limit{}; getrlimit(RLIMIT_NPROC, &limit);
    assert(limit.rlim_cur == 16 && limit.rlim_max == 16);
    std::atomic<bool> done(false);
    std::vector<std::thread> threads;
    for (int i=0;i<48;++i) {
        try { threads.emplace_back([&] { while (!done) std::this_thread::yield(); }); }
        catch (const std::system_error&) { break; }
    }
    assert(!threads.empty() && threads.size() <= 15);
    std::cerr << "workerThreads=" << threads.size() << std::endl;
    done = true;
    for (auto& t : threads) t.join();
    auto setup = hrw::read_setup(); hrw::ready();
    hrw::Turn turn;
    while (hrw::read_turn(turn)) hrw::send({});
}
'''
        row = self.match(self.bot("cpp-threads", code, "main.cpp"))
        self.assertEqual(row["result"]["faults"], [None, None])

    def test_tmp_filling_bot_cannot_consume_unbounded_memory(self):
        # Even the unfixed reproduction writes at most 80 MiB, never fills RAM.
        code = '''import hrw
hrw.read_setup(); hrw.ready(); hrw.read_turn()
for i in range(5):
    with open('/tmp/fill-'+str(i), 'wb') as f:
        for _ in range(16): f.write(b'x'*1048576)
hrw.send([])
while hrw.read_turn() is not None: hrw.send([])
'''
        row = self.match(self.bot("fill-tmp", code))
        self.assertEqual(row["result"]["winner"], 1)
        self.assertIsNotNone(row["result"]["faults"][0])

    def test_compile_context_has_two_gib_address_space(self):
        launcher = Bubblewrap()
        source = self.bot("compile-probe", IDLE)
        build = self.root / "build"
        build.mkdir()
        command = [f"/runtime/bin/{launcher.python_name}", "-c",
                   "import resource; assert resource.getrlimit(resource.RLIMIT_AS)==(2147483648,2147483648)"]
        p = launcher.launch(source, ROOT / "sdk/python", command, launcher.cpus[0],
                            build=build, writable_build=True)
        try:
            out, err = p.communicate(timeout=10)
            (self.root / "compile.stdout").write_bytes(out)
            (self.root / "compile.stderr").write_bytes(err)
            self.assertEqual(p.returncode, 0, err.decode())
        finally:
            stop(p)

    def test_malformed_submission_is_compile_loss(self):
        empty = self.root / "empty"
        empty.mkdir()
        both = self.bot("both", IDLE)
        (both / "main.cpp").write_text("int main() {}\n")
        links = self.bot("links", IDLE)
        (links / "link").symlink_to(links / "main.py")
        large = self.bot("large", IDLE)
        with (large / "large.dat").open("wb") as f: f.truncate(16*1024*1024+1)
        root_link = self.root / "root-link"
        root_link.symlink_to(self.bot("link-target", IDLE), target_is_directory=True)
        total = self.bot("total-size", IDLE)
        for i in range(5):
            with (total / f"part-{i}").open("wb") as f: f.truncate(16*1024*1024)
        for source in (empty, both, links, large, total, root_link):
            with self.subTest(source=source.name):
                row = self.match(source, ROOT / "sdk/python/example")
                self.assertEqual(row["result"]["faults"], ["compile_failed", None])
                self.assertEqual(row["result"]["winner"], 1)
                self.assertEqual(row["result"]["turns"], 0)
                detail = json.loads((Path(row["directory"]) / "p0/validation.json").read_text())
                self.assertFalse(detail["valid"])
                self.assertTrue(detail["reason"])

    def test_readonly_filesystems_and_anonymous_file_bypasses(self):
        code = '''import os, errno, ctypes, hrw
for directory in ('/', '/tmp', '/dev', '/dev/shm'):
    if not os.path.isdir(directory): continue
    try:
        open(directory+'/must-not-write', 'w')
    except OSError as error:
        assert error.errno == errno.EROFS
    else:
        raise AssertionError(directory+' is writable')
try:
    os.memfd_create('must-not-allocate')
except OSError as error:
    assert error.errno == errno.EPERM
else:
    raise AssertionError('memfd is writable outside address-space budget')
libc = ctypes.CDLL(None, use_errno=True)
for call in (29, 64, 68, 240):
    assert libc.syscall(call, 0, 4096, 0o1600) == -1
    assert ctypes.get_errno() == errno.EPERM
'''+IDLE
        row = self.match(self.bot("memory-policy", code))
        self.assertEqual(row["result"]["faults"], [None, None])

    def test_live_clock_missing_children_file_fails_closed(self):
        clock = CpuClock(os.getpid())
        original = Path.read_text
        def read(path, *args, **kwargs):
            if path.name == "children": raise FileNotFoundError("injected")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read), self.assertRaises(InfrastructureError):
            clock.read_ns()


if __name__ == "__main__":
    unittest.main()
