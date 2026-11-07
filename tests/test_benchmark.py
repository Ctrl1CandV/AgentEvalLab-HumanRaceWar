"""Timing regressions; benchmark, compiler and test bots execute only in bwrap."""
import gzip
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.benchmark import run_benchmark, workload_digest
from arena.core.runner import cpu_hard_limit
from arena.core.sandbox import InfrastructureError, ROOT
from arena.core.timing import Calibration, scale_limits
from arena.games.outpost.replay import verify
from arena.match import play
from tests.helpers import fixture_map
from tests.test_runtime import IDLE


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "runs/development/benchmark-tests" / uuid4().hex
        self.root.mkdir(parents=True)

    def test_all_budgets_scale_including_wall_and_hard_margin(self):
        base = {"TURN_CPU_MS": 100, "INIT_CPU_MS": 2000, "BANK_MS": 3000}
        scaled = scale_limits(base, 1.5)
        self.assertEqual(scaled, {"TURN_CPU_MS": 150, "INIT_CPU_MS": 3000, "BANK_MS": 4500})
        self.assertEqual(cpu_hard_limit(scaled, 300, 1.5), 60)
        self.assertEqual(math.ceil(500*1.5), 750)
        for value in (0, -1, float("inf"), float("nan")):
            with self.assertRaises(ValueError): scale_limits(base, value)

    def test_bad_calibration_is_rejected_before_running(self):
        p = self.root / "bad.json"
        base = {"schemaVersion": 1, "status": "complete", "workloadSha256": workload_digest(),
                "jobs": 1, "cpus": [0, 1], "reference": {"cpuNs": 100},
                "loadedMedianCpuNs": 150, "speedFactor": 1.5}
        cases = [[], {}, {**base, "jobs": 6}, {**base, "speedFactor": 2},
                 {**base, "workloadSha256": "changed"}, {**base, "reference": {"cpuNs": 0}},
                 {**base, "cpus": [0, 0]}, {**base, "status": "incomplete"}]
        for item in cases:
            p.write_text(json.dumps(item))
            with self.assertRaises(ValueError): Calibration.load(p, workload_digest(), jobs=1)

    def test_real_benchmark_barrier_artifacts_and_restored_affinity(self):
        affinity = os.sched_getaffinity(0)
        r = run_benchmark(self.root, jobs=1, samples=1)
        self.assertEqual(r["status"], "complete", r)
        self.assertEqual(os.sched_getaffinity(0), affinity)
        self.assertEqual([p["instances"] for p in r["curve"]], [1, 2])
        self.assertTrue(all(row["status"] == "complete" for row in r["runs"]))
        self.assertTrue(all(row["runnerCpu"] not in row["cpus"] for row in r["runs"]))
        self.assertEqual(r["reference"]["kind"], "local-development-idle")
        c = Calibration.load(Path(r["resultFile"]), workload_digest(), jobs=1)
        self.assertAlmostEqual(c.factor, r["loadedMedianCpuNs"]/r["reference"]["cpuNs"])
        self.assertTrue((Path(r["directory"]) / "attempts.jsonl").exists())

    def test_failed_benchmark_attempt_is_kept_not_dropped(self):
        before = os.sched_getaffinity(0)
        with patch("arena.core.benchmark.exchange", side_effect=InfrastructureError("injected benchmark failure")):
            r = run_benchmark(self.root, jobs=1, samples=1)
        self.assertEqual(r["status"], "incomplete")
        self.assertEqual(len(r["runs"]), 1)
        self.assertTrue((Path(r["directory"]) / "attempts.jsonl").exists())
        self.assertEqual(os.sched_getaffinity(0), before)
        with self.assertRaises(ValueError): Calibration.load(Path(r["resultFile"]), workload_digest(), jobs=1)

    def test_scaled_match_limits_hard_cap_and_replay_metadata(self):
        cpus = tuple(sorted(os.sched_getaffinity(0))[:2])
        c = Calibration(1, cpus, 1.5, "test-fixture", {"kind": "test-only", "cpuNs": 100}, workload_digest())
        a, b = self.root / "probe", self.root / "idle"
        a.mkdir(); b.mkdir()
        (a / "main.py").write_text('''import hrw, resource
setup = hrw.read_setup()
assert setup.limits == {'TURN_CPU_MS': 150, 'INIT_CPU_MS': 3000, 'BANK_MS': 4500}
assert resource.getrlimit(resource.RLIMIT_CPU) == (60,60)
hrw.ready()
hrw.read_turn()
raise SystemExit(3)
''')
        (b / "main.py").write_text(IDLE)
        r = play([a, b], fixture_map(), self.root / "matches", [17, 29], calibration=c, retries=0)
        self.assertEqual(r["status"], "complete", r)
        self.assertEqual(r["result"]["faults"], ["crash", None])
        self.assertEqual(verify(Path(r["replay"]))["result"], r["result"])
        with gzip.open(r["replay"], "rt") as f:
            header, init = json.loads(next(f)), json.loads(next(f))
        self.assertEqual(init["type"], "init")
        self.assertEqual([reply["fault"] for reply in init["replies"]], [None, None])
        self.assertEqual(header["wallMarginMs"], 750)
        self.assertEqual(header["cpuHardLimitSeconds"], 60)
        self.assertEqual(header["speedFactor"], 1.5)
        self.assertEqual(header["cpus"], list(cpus))
        self.assertEqual(header["timingCalibration"]["reference"]["kind"], "test-only")


if __name__ == "__main__":
    unittest.main()
