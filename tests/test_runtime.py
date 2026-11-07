"""Trusted harness tests; every example/fault bot and C++ compile runs in bwrap.

Artifacts (including every failed attempt) remain in runs/development/runtime/.
Sandbox unavailability is a failure, never a fallback or a silent skip.
"""
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.replay import ReplayError
from arena.games.outpost.replay import verify
from arena.core.sandbox import Bubblewrap, ENV, ROOT, snapshot
from arena.core.transport import Frame
from arena.match import play
from tests.helpers import fixture_map

IDLE = '''import hrw
s = hrw.read_setup()
hrw.ready()
while hrw.read_turn() is not None:
    hrw.send([])
'''


class FrameTests(unittest.TestCase):
    def test_fragmented_crlf_and_leftover(self):
        frame = Frame(b"END")
        self.assertEqual(frame.feed(b"MOVE 0 N\r\nE"), b"")
        self.assertFalse(frame.done)
        self.assertEqual(frame.feed(b"ND\r\nNEXT\n"), b"NEXT\n")
        self.assertEqual(frame.lines(), ["MOVE 0 N\r", "END\r"])

    def test_huge_line_discard_is_bounded_and_marker_recovers(self):
        frame = Frame(b"END")
        for _ in range(1000):
            frame.feed(b"x"*8192)
        self.assertLessEqual(len(frame.raw), 65537)
        self.assertLessEqual(len(frame.line), 257)
        frame.feed(b"\nEND\n")
        self.assertTrue(frame.done)

    def test_long_fake_end_not_a_marker(self):
        frame = Frame(b"END")
        frame.feed(b" "*254+b"END\n")
        self.assertFalse(frame.done)
        frame.feed(b"END\n")
        self.assertTrue(frame.done)

    def test_marker_uses_engine_whitespace_and_rejects_bad_text(self):
        frame = Frame(b"END")
        frame.feed(b"\rEND\n")
        self.assertFalse(frame.done)
        frame.feed("\u2003END\u2003\n".encode())
        self.assertTrue(frame.done)

    def test_invalid_utf8_does_not_expand_transport_byte_budget(self):
        from arena.games.outpost import Outpost
        game = Outpost()
        state = game.new_match(fixture_map(), {}, [1, 2])
        frame = Frame(b"END")
        frame.feed((b"\xff"*250+b"\n")*100+b"MOVE 0 E\nEND\n")
        packet, warnings = game.parse_orders(state, 0, frame.lines())
        self.assertEqual([o.to_line() for o in packet.commands], ["MOVE 0 E"])
        self.assertEqual(len(warnings), 100)
        self.assertEqual({w.code for w in warnings}, {"BAD_TEXT"})

    def test_launcher_has_no_host_environment_or_home_bind(self):
        launcher = Bubblewrap()
        args = launcher.argv(Path("/example/bot"), Path("/example/sdk"), ["/usr/bin/true"])
        self.assertIn("--unshare-all", args)
        self.assertIn("--clearenv", args)
        self.assertNotIn(str(Path.home()), args)
        self.assertNotIn(str(ROOT), args)
        self.assertNotIn("--share-net", args)
        self.assertEqual(ENV["HOME"], "/tmp")


class SandboxMatchTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "runs/development/runtime" / uuid4().hex
        self.root.mkdir(parents=True)
        self.map = fixture_map(extra=[(6, 2, "O")])

    def bot(self, name, code, filename="main.py"):
        path = self.root / name
        path.mkdir()
        (path / filename).write_text(code)
        return path

    def match(self, a, b, limits=None):
        result = play([a, b], self.map, self.root / "matches", [17, 29], limits=limits, retries=0)
        self.assertEqual(result["status"], "complete", result)
        checked = verify(Path(result["replay"]))
        self.assertEqual(checked["result"], result["result"])
        return result

    def test_python_cpp_examples_full_match_and_replay_tamper(self):
        row = self.match(ROOT / "sdk/python/example", ROOT / "sdk/cpp/example")
        self.assertEqual(row["result"]["turns"], 300)
        self.assertTrue(all(n > 0 for n in row["result"]["deposited"]))
        self.assertEqual(row["result"]["faults"], [None, None])
        self.assertTrue(verify(Path(row["replay"]), 25)["board"].startswith("TURN 25"))
        self.assertEqual(len(verify(Path(row["replay"]))["summary"]), 12)
        with gzip.open(row["replay"], "rt") as stream:
            rows = [json.loads(line) for line in stream]
        for label, mutate in (
            ("hash", lambda rs: rs[2].update(stateHash="0"*16)),
            ("map", lambda rs: rs[0].update(mapSha256="0"*64)),
            ("orders", lambda rs: rs[2]["accepted"][0].append({})),
            ("warnings", lambda rs: rs[2].update(invalid=[{}])),
            ("result", lambda rs: rs[-1]["result"].update(winner=99)),
            ("duplicate", lambda rs: rs.append(rs[-1])),
            ("incomplete", lambda rs: rs.pop()),
        ):
            clone = json.loads(json.dumps(rows))
            mutate(clone)
            damaged = self.root / f"{label}.hrw.jsonl.gz"
            with gzip.open(damaged, "wt") as stream:
                stream.write("".join(json.dumps(r)+"\n" for r in clone))
            with self.subTest(label=label), self.assertRaises(ReplayError):
                verify(damaged)

    def test_idle_loses_to_miner(self):
        row = self.match(self.bot("idle", IDLE), ROOT / "sdk/python/example")
        self.assertEqual(row["result"]["winner"], 1)
        self.assertEqual(row["result"]["deposited"][0], 0)

    def test_crashes_same_round_draw_and_one_crash_loses(self):
        crashing = self.bot("crash", 'import hrw\nhrw.read_setup()\nhrw.ready()\nhrw.read_turn()\nraise SystemExit(3)\n')
        idle = self.bot("idle", IDLE)
        one = self.match(crashing, idle)
        self.assertEqual(one["result"]["winner"], 1)
        both = self.match(crashing, crashing)
        self.assertIsNone(both["result"]["winner"])
        self.assertEqual(both["result"]["turns"], 0)
        self.assertEqual(both["result"]["faults"], ["crash", "crash"])

    def test_cpu_and_wall_timeouts(self):
        idle = self.bot("idle", IDLE)
        for name, action, expected in (("loop", "while True: pass", "cpu_timeout"),
                                       ("sleep", "import time; time.sleep(5)", "wall_timeout")):
            bot = self.bot(name, 'import hrw\nhrw.read_setup()\nhrw.ready()\nhrw.read_turn()\n'+action+'\n')
            row = self.match(bot, idle, {"TURN_CPU_MS": 10, "BANK_MS": 20})
            self.assertEqual(row["result"]["faults"][0], expected)
            self.assertEqual(row["result"]["winner"], 1)

    def test_init_timeout_and_missing_ready_are_bot_faults(self):
        idle = self.bot("idle", IDLE)
        for name, code, expected in (("no-ready", "raise SystemExit(2)\n", "crash"),
                                     ("init-loop", "while True: pass\n", "cpu_timeout")):
            row = self.match(self.bot(name, code), idle, {"INIT_CPU_MS": 200})
            self.assertEqual(row["result"]["faults"], [expected, None])
            self.assertEqual(row["result"]["turns"], 0)

    def test_missing_end_flood_times_out_without_unbounded_storage(self):
        code = ('import hrw, os\nhrw.read_setup()\nhrw.ready()\nhrw.read_turn()\n'
                'while True: os.write(1, b"x"*8192)\n')
        row = self.match(self.bot("endless", code), self.bot("idle", IDLE),
                         {"TURN_CPU_MS": 10, "BANK_MS": 20})
        self.assertIn(row["result"]["faults"][0], ("cpu_timeout", "wall_timeout"))
        self.assertEqual(row["result"]["winner"], 1)

    def test_bank_is_consumed_only_by_excess_and_never_refilled(self):
        code = '''import hrw, time
hrw.read_setup()
hrw.ready()
while (t := hrw.read_turn()) is not None:
    if t.number % 2:
        start = time.process_time_ns()
        while time.process_time_ns()-start < 25000000: pass
    hrw.send([])
'''
        row = self.match(self.bot("bank", code), self.bot("idle", IDLE),
                         {"TURN_CPU_MS": 10, "BANK_MS": 60})
        self.assertEqual(row["result"]["faults"][0], "cpu_timeout")
        with gzip.open(row["replay"], "rt") as stream:
            turns = [r for line in stream if (r := json.loads(line))["type"] in ("turn", "fault")]
        bank = 60_000_000
        for turn in turns:
            bank -= max(0, turn["replies"][0]["cpu_ns"]-10_000_000)
            self.assertEqual(turn["bankNs"][0], bank)
        self.assertGreaterEqual(len(turns), 3)

    def test_compile_failure_is_bot_loss_and_preserved(self):
        cpp = self.bot("bad-cpp", "this is not C++;\n", "main.cpp")
        row = self.match(cpp, self.bot("idle", IDLE))
        self.assertEqual(row["result"]["faults"], ["compile_failed", None])
        self.assertEqual(row["result"]["winner"], 1)
        self.assertTrue((Path(row["directory"]) / "p0/compile.stderr").is_file())

    def test_malformed_and_flood_output_is_bounded_without_forfeit(self):
        code = '''import hrw, os
hrw.read_setup()
hrw.ready()
while hrw.read_turn() is not None:
    os.write(2, b'e'*70000)
    os.write(1, b'\\xff\\nBAD\\nx'*40000+b'\\nEND\\n')
'''
        row = self.match(self.bot("malformed", code), self.bot("idle", IDLE))
        self.assertEqual(row["result"]["turns"], 300)
        self.assertEqual(row["result"]["faults"], [None, None])
        self.assertGreater(row["result"]["warnings"][0], 0)
        self.assertEqual((Path(row["directory"]) / "p0/stderr.txt").stat().st_size, 65536)

    def test_live_isolation_resources_and_cross_namespace_clock(self):
        # This code is executed ONLY by the bwrap launcher, never imported here.
        code = f'''import hrw, os, resource, socket, time
assert not os.path.exists({str(Path.home())!r})
assert not os.path.exists({str(ROOT)!r})
assert not os.path.exists('/other-bot')
assert os.environ.get('HRW_HOST_SENTINEL') is None
assert len(os.sched_getaffinity(0)) == 1
assert resource.getrlimit(resource.RLIMIT_AS) == (536870912, 536870912)
assert resource.getrlimit(resource.RLIMIT_NOFILE) == (64, 64)
assert resource.getrlimit(resource.RLIMIT_FSIZE) == (16777216, 16777216)
try:
    open('/bot/write-test', 'w')
except OSError:
    pass
else:
    raise AssertionError('bot source is writable')
assert [name for _, name in socket.if_nameindex()] == ['lo']
hrw.read_setup()
hrw.ready()
while hrw.read_turn() is not None:
    begin = time.process_time_ns()
    while time.process_time_ns()-begin < 1000000: pass
    hrw.send([])
'''
        with patch.dict("os.environ", {"HRW_HOST_SENTINEL": "must-not-inherit"}):
            row = self.match(self.bot("probe", code), self.bot("idle", IDLE))
        with gzip.open(row["replay"], "rt") as stream:
            turns = [r for line in stream if (r := json.loads(line))["type"] == "turn"]
        self.assertTrue(all(r["replies"][0]["clock"] == "process_cpu_clock" for r in turns))
        self.assertGreater(sum(r["replies"][0]["cpu_ns"] for r in turns), 250_000_000)

    def test_missing_bwrap_is_infra_and_retries_are_archived(self):
        bot = self.bot("idle", IDLE)
        with patch("arena.core.sandbox.shutil.which", return_value=None):
            row = play([bot, bot], self.map, self.root / "missing", [1, 2])
        self.assertEqual(row["status"], "infra_error")
        records = Path(row["directory"]).parent / "results.jsonl"
        self.assertEqual(len(records.read_text().splitlines()), 4)
        self.assertNotIn("result", row)

    def test_real_sandbox_preparation_error_is_not_a_bot_loss(self):
        bot = self.bot("idle", IDLE)
        with patch.object(Bubblewrap, "argv", return_value=["/usr/bin/bwrap", "--ro-bind", "/nonexistent-hrw", "/bot", "--", "/usr/bin/true"]):
            row = play([bot, bot], self.map, self.root / "bad-sandbox", [1, 2], retries=0)
        self.assertEqual(row["status"], "infra_error")
        self.assertNotIn("result", row)
        self.assertTrue((Path(row["directory"]) / "p0/stderr.txt").exists())

    def test_snapshot_rejects_symlinks(self):
        source = self.bot("links", IDLE)
        (source / "linked").symlink_to(source / "main.py")
        with self.assertRaises(ValueError):
            snapshot(source, self.root / "snapshot")
