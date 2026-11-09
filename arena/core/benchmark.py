"""Fixed offline benchmark, compiled once and run at the actual worker load."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import statistics
import time
import traceback
from uuid import uuid4

from .sandbox import Bubblewrap, InfrastructureError, ROOT, prepare
from .resources import CpuLease
from .machine import machine_info
from .transport import Connection, exchange

SOURCE = ROOT / "arena/bench"


def workload_digest() -> str:
    return sha256((SOURCE / "main.cpp").read_bytes()).hexdigest()


def run_benchmark(out: Path, *, jobs: int = 6, samples: int = 3,
                  reference: Path | None = None, sweep: bool = False, sandbox='bwrap', _cpu_pool=None) -> dict:
    if sandbox not in ('bwrap','plain'): raise ValueError('unknown benchmark backend')
    if sandbox == 'plain' and 2*jobs+1>8: raise ValueError('plain workspace benchmark exceeds 8 CPUs')
    if _cpu_pool is not None:
        return _run_benchmark(out, jobs, samples, reference, sweep, _cpu_pool, sandbox)
    capacity = len(os.sched_getaffinity(0))
    if sandbox == 'plain': capacity = min(8, capacity)
    workers = capacity if sweep else 2*jobs
    with CpuLease(workers, reserve_runner=not sweep) as lease:
        return _run_benchmark(out, jobs, samples, reference, sweep, lease.pool, sandbox)


def _run_benchmark(out, jobs, samples, reference, sweep, pool, sandbox):
    if sandbox == 'bwrap': launcher = Bubblewrap()
    else:
        from .plain import Plain
        launcher = Plain()
    launcher.cpus = list(pool)
    available = launcher.cpus
    if type(jobs) is not int or jobs < 1 or 2*jobs >= len(available):
        raise ValueError("bench needs 2*jobs worker CPUs plus a separate runner CPU")
    if type(samples) is not int or not 1 <= samples <= 9:
        raise ValueError("samples must be between 1 and 9")
    reference_data = None
    if reference is not None:
        raw_reference = reference.read_bytes()
        r = json.loads(raw_reference)
        if (not isinstance(r, dict) or r.get("status") != "complete"
                or r.get("workloadSha256") != workload_digest()
                or not isinstance(r.get("singleInstance"), dict) or not isinstance(r.get("machine"), dict)):
            raise ValueError("reference must contain the same workload's successful idle single-instance sample")
        ns = r["singleInstance"].get("medianCpuNs")
        if type(ns) not in (int, float) or not math.isfinite(ns) or ns <= 0:
            raise ValueError("invalid idle reference CPU time")
        reference_data = {"kind": "operator-supplied-evaluation-idle", "cpuNs": ns,
                          "reportSha256": sha256(raw_reference).hexdigest(), "machine": r["machine"]}
    directory = out.resolve() / uuid4().hex
    directory.mkdir(parents=True)
    report = {"schemaVersion": 1, "status": "incomplete", "sandbox": sandbox, "scope": "CPU load calibration, not full efficiency acceptance",
              "workloadSha256": workload_digest(), "jobs": jobs, "samples": samples,
              "cpus": available[:2*jobs], "startedAt": datetime.now(timezone.utc).isoformat(),
              "directory": str(directory), "machine": {**machine_info(), "availableCpus": available},
              "runs": [], "curve": []}
    start_cpu = time.process_time_ns()
    mask = os.sched_getaffinity(0)
    checksum = None
    try:
        bot = prepare(SOURCE, directory / "compiled", launcher, available[0])
        if bot.compile_fault:
            raise InfrastructureError("trusted benchmark compilation failed; see saved compiler output")
        counts = [1, 2*jobs]
        if sweep:
            counts = sorted(set(counts + [n for n in (1, 2, 6, 12, 16, 20) if n <= len(available)]))
        for count in counts:
            cpus = available[:count]
            runner_cpu = available[count] if count < len(available) else None
            by_cpu = {cpu: [] for cpu in cpus}
            for sample in range(samples):
                attempt = directory / f"n{count}-sample{sample}"
                attempt.mkdir()
                row = {"instances": count, "sample": sample, "status": "incomplete", "cpus": cpus,
                       "runnerCpu": runner_cpu, "fullSaturationDiagnostic": runner_cpu is None,
                       "directory": str(attempt)}
                report["runs"].append(row)
                connections = []
                try:
                    os.sched_setaffinity(0, {runner_cpu} if runner_cpu is not None else mask)
                    for cpu in cpus:
                        # Share only this trusted benchmark's immutable snapshot/executable.
                        connection = Connection(bot, launcher, cpu, 30)
                        connections.append(connection)
                        worker_dir = attempt / f"cpu{cpu}"
                        worker_dir.mkdir()
                        connection.bot = replace(bot, directory=worker_dir)
                    ready = exchange(connections, [["BENCH"] for _ in cpus],
                                     [2000]*count, [5000]*count, b"READY")
                    row["ready"] = [r.record() for r in ready]
                    if any(r.fault for r in ready):
                        raise InfrastructureError("benchmark initialization failed")
                    # All processes have reached READY before any sees GO.
                    replies = exchange(connections, [["GO"] for _ in cpus], [15000]*count, [20000]*count)
                    row["replies"] = [r.record() for r in replies]
                    values = []
                    for cpu, reply in zip(cpus, replies):
                        lines = [line.split() for line in reply.lines if line.startswith("BENCH ")]
                        if reply.fault or len(lines) != 1 or len(lines[0]) != 3:
                            raise InfrastructureError("benchmark reply failed or malformed")
                        ns, value = map(int, lines[0][1:])
                        if ns < 1_000_000 or (checksum is not None and value != checksum):
                            raise InfrastructureError("benchmark result is inconsistent")
                        checksum = value
                        by_cpu[cpu].append(ns)
                        values.append(ns)
                    row.update(status="complete", cpuNs=values, checksum=checksum)
                finally:
                    for connection in connections:
                        connection.close()
                    (attempt / "result.json").write_text(json.dumps(row, indent=2)+"\n")
                    with (directory / "attempts.jsonl").open("a") as f:
                        f.write(json.dumps(row)+"\n")
                    os.sched_setaffinity(0, mask)
            combined = [value for values in by_cpu.values() for value in values]
            point = {"instances": count, "medianCpuNs": statistics.median(combined),
                     "minCpuNs": min(combined), "maxCpuNs": max(combined),
                     "byCpuMedianNs": {str(cpu): statistics.median(values) for cpu, values in by_cpu.items()},
                     "runnerCpu": runner_cpu}
            report["curve"].append(point)
        idle = next(p for p in report["curve"] if p["instances"] == 1)
        loaded = next(p for p in report["curve"] if p["instances"] == 2*jobs)
        reference_data = reference_data or {"kind": "local-development-idle", "cpuNs": idle["medianCpuNs"],
                                           "machine": report["machine"]}
        report.update(status="complete", singleInstance=idle, reference=reference_data,
                      loadedMedianCpuNs=loaded["medianCpuNs"],
                      speedFactor=loaded["medianCpuNs"] / reference_data["cpuNs"], checksum=checksum)
    except Exception as error:
        report["error"] = type(error).__name__
        (directory / "error.log").write_text(traceback.format_exc())
    finally:
        os.sched_setaffinity(0, mask)
        report["measuredHarnessCpuSeconds"] = (time.process_time_ns()-start_cpu)/1e9
        report["recordedBenchmarkCpuSeconds"] = sum(sum(r.get("cpuNs", [])) for r in report["runs"])/1e9
        report["resultFile"] = str(directory / "result.json")
        Path(report["resultFile"]).write_text(json.dumps(report, indent=2)+"\n")
    return report
