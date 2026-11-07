"""Run trusted unit tests and report measured usage (not a bot benchmark).

No dependencies. --json sends the test log inside a JSON object for archiving.
CPU figures separate this process from reaped children (sandbox/compile processes).
They exclude model inference, and are not performance acceptance measurements.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import platform
import resource
import sys
import time
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern=args.pattern, top_level_dir=str(root))
    stream = io.StringIO()
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    cpu_ns, wall_ns = time.process_time_ns() - cpu_start, time.perf_counter_ns() - wall_start
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "schemaVersion": 1,
        "scope": "trusted tests; runtime tests execute bots/compilers only in bwrap; not phase-A acceptance",
        "pattern": args.pattern,
        "python": platform.python_version(),
        "system": platform.system(),
        "kernel": platform.release(),
        "testsRun": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": result.wasSuccessful(),
        "measuredTestProcessCpuSeconds": cpu_ns / 1_000_000_000,
        "measuredTestWallSeconds": wall_ns / 1_000_000_000,
        "measuredReapedChildrenCpuSeconds": (children.ru_utime+children.ru_stime
                                             -child_start.ru_utime-child_start.ru_stime),
        "log": stream.getvalue(),
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(report.pop("log"), end="")
        print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
