"""Load-bound timing calibration metadata and consistently scaled budgets."""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path

from .machine import machine_fingerprint, require_local_machine


def scale_limits(limits: dict[str, int], factor: float) -> dict[str, int]:
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("speed factor must be finite and positive")
    return {key: math.ceil(value*factor) for key, value in limits.items()}


@dataclass(frozen=True)
class Calibration:
    jobs: int
    cpus: tuple[int, ...]
    factor: float
    report_sha256: str
    reference: dict
    workload_sha256: str
    sandbox: str = 'bwrap'
    locked_budget: dict | None = None
    lock_sha256: str | None = None

    def header(self) -> dict:
        result = {"jobs": self.jobs, "cpus": self.cpus, "speedFactor": self.factor,
                  "reportSha256": self.report_sha256, "reference": self.reference,
                  "workloadSha256": self.workload_sha256, "sandbox": self.sandbox}
        if self.locked_budget is not None:
            result['fixedRuntime'] = {'lockSha256': self.lock_sha256, **self.locked_budget}
        return result

    @classmethod
    def load(cls, path: Path, workload_sha256: str, *, jobs: int) -> "Calibration":
        return cls.from_bytes(path.read_bytes(), workload_sha256, jobs=jobs)

    @classmethod
    def from_bytes(cls, raw: bytes, workload_sha256: str, *, jobs: int) -> "Calibration":
        r = json.loads(raw)
        if isinstance(r, dict) and r.get('kind') == 'fixed-runtime-budget':
            if r.get('schemaVersion') != 2 or not isinstance(r.get('benchmarkJson'), str):
                raise ValueError('fixed timing lacks current machine binding; bind a legacy lock with recorded '
                                 'origin evidence, or benchmark and freeze on the new host')
            benchmark = r['benchmarkJson'].encode()
            original = json.loads(benchmark)
            if (not isinstance(original, dict) or 'kind' in original
                    or sha256(benchmark).hexdigest() != r.get('benchmarkSha256')):
                raise ValueError('fixed timing benchmark changed or nested')
            inventory = original.get('machine')
            if 'legacyOrigin' in r:
                inventory = legacy_inventory(r, original)
            fingerprint = machine_fingerprint(inventory)
            binding = r.get('machineFingerprint')
            if (not isinstance(binding, dict) or binding != fingerprint
                    or any(type(binding.get(k)) is not int for k in ('logicalCpus', 'visibleMemoryGiB'))):
                raise ValueError('fixed timing machine binding does not match its origin')
            require_local_machine(fingerprint)
            calibration = cls.from_bytes(benchmark, workload_sha256, jobs=jobs)
            budget = r.get('budget')
            if not isinstance(budget, dict):
                raise ValueError('missing fixed timing budgets')
            expected = runtime_budget(budget.get('baseLimits'), calibration.factor, budget.get('turns'))
            if (budget != expected or any(type(budget[k]) is not int for k in ('wallMarginMs', 'cpuHardLimitSeconds'))
                    or any(type(n) is not int for n in budget['limits'].values())):
                raise ValueError('fixed timing budgets do not match recorded calibration')
            return replace(calibration, locked_budget=expected, lock_sha256=sha256(raw).hexdigest())
        required = {"cpus", "reference", "loadedMedianCpuNs", "speedFactor"}
        if (type(jobs) is not int or jobs < 1 or not isinstance(r, dict)
                or r.get("status") != "complete" or r.get("schemaVersion") != 1 or not required <= r.keys()):
            raise ValueError("incomplete or unsupported timing calibration")
        if r.get("workloadSha256") != workload_sha256 or type(r.get("jobs")) is not int or r["jobs"] != jobs:
            raise ValueError("timing workload/concurrency does not match the actual run")
        cpus = r["cpus"]
        if (not isinstance(cpus, list) or len(cpus) != 2*jobs
                or any(type(c) is not int or c < 0 for c in cpus) or len(set(cpus)) != len(cpus)):
            raise ValueError("invalid calibrated CPU allocation")
        reference = r["reference"]
        if not isinstance(reference, dict) or "cpuNs" not in reference:
            raise ValueError("missing timing reference")
        reference_ns, measured_ns = reference["cpuNs"], r["loadedMedianCpuNs"]
        if not all(type(n) in (int, float) and math.isfinite(n) and n > 0 for n in (reference_ns, measured_ns)):
            raise ValueError("invalid timing measurements")
        factor = measured_ns / reference_ns
        if (not math.isfinite(factor) or type(r["speedFactor"]) not in (int, float)
                or not math.isclose(r["speedFactor"], factor, rel_tol=1e-12)):
            raise ValueError("inconsistent speed factor")
        sandbox = r.get('sandbox', 'bwrap')
        if sandbox not in ('bwrap', 'plain'): raise ValueError('unknown calibration backend')
        return cls(jobs, tuple(cpus), factor, sha256(raw).hexdigest(), reference, workload_sha256, sandbox)


def runtime_budget(base_limits, factor, turns):
    from arena.core.runner import cpu_hard_limit
    if (not isinstance(base_limits, dict) or set(base_limits) != {'TURN_CPU_MS', 'INIT_CPU_MS', 'BANK_MS'}
            or any(type(n) is not int or n <= 0 for n in base_limits.values())
            or type(turns) is not int or turns <= 0):
        raise ValueError('invalid base limits or turn count for fixed timing')
    limits = scale_limits(base_limits, factor)
    return {'baseLimits': dict(base_limits), 'turns': turns, 'limits': limits,
            'wallMarginMs': math.ceil(500*factor),
            'cpuHardLimitSeconds': cpu_hard_limit(limits, turns, factor)}


def freeze_calibration(path: Path, workload_sha256: str, *, jobs: int, base_limits: dict, turns: int) -> dict:
    raw = path.read_bytes()
    calibration = Calibration.from_bytes(raw, workload_sha256, jobs=jobs)
    if calibration.locked_budget is not None:
        raise ValueError('already fixed; reuse the existing lock bytes')
    fingerprint = machine_fingerprint(json.loads(raw).get('machine'))
    require_local_machine(fingerprint)
    return {'schemaVersion': 2, 'kind': 'fixed-runtime-budget', 'benchmarkJson': raw.decode(),
            'benchmarkSha256': calibration.report_sha256, 'machineFingerprint': fingerprint,
            'budget': runtime_budget(base_limits, calibration.factor, turns)}


def legacy_inventory(record: dict, benchmark: dict) -> dict:
    """Validate a transparent migration, never invent a missing origin CPU count."""
    try:
        origin = record['legacyOrigin']
        raw, evidence_raw = origin['lockJson'].encode(), origin['evidenceJson'].encode()
        old, evidence = json.loads(raw), json.loads(evidence_raw)
        digest = sha256(raw).hexdigest()
        if (digest != origin['lockSha256'] or sha256(evidence_raw).hexdigest() != origin['evidenceSha256']
                or evidence['fixedBudget']['lockSha256'] != digest
                or old['kind'] != 'fixed-runtime-budget' or old['schemaVersion'] != 1
                or 'legacyOrigin' in old or old['budget'] != record['budget']
                or old['benchmarkJson'] != record['benchmarkJson']
                or old['benchmarkSha256'] != record['benchmarkSha256']):
            raise ValueError('legacy machine evidence or original lock changed')
        inventory = dict(benchmark['machine'])
        count = evidence['machine']['logicalCpus']
        if ('logicalCpus' in inventory and inventory['logicalCpus'] != count
                or type(count) is not int or count <= 0):
            raise ValueError('legacy machine logical CPU evidence disagrees')
        inventory['logicalCpus'] = count
        return inventory
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('missing legacy machine evidence') from error


def bind_legacy_calibration(raw: bytes, evidence_raw: bytes, workload_sha256: str, *, jobs: int) -> dict:
    """New wrapper only: preserve the old lock, benchmark and all budgets verbatim.

    Evidence must be an archived report tying the origin logical CPU count to
    this exact old lock. This is a post-hoc binding, NOT a fresh measurement.
    """
    old = json.loads(raw)
    if (not isinstance(old, dict) or old.get('kind') != 'fixed-runtime-budget'
            or old.get('schemaVersion') != 1 or 'legacyOrigin' in old):
        raise ValueError('only an unbound v1 lock can be migrated')
    value = {**old, 'schemaVersion': 2, 'legacyOrigin': {
        'lockJson': raw.decode(), 'lockSha256': sha256(raw).hexdigest(),
        'evidenceJson': evidence_raw.decode(), 'evidenceSha256': sha256(evidence_raw).hexdigest()}}
    inventory = legacy_inventory(value, json.loads(value['benchmarkJson']))
    value['machineFingerprint'] = machine_fingerprint(inventory)
    Calibration.from_bytes(json.dumps(value).encode(), workload_sha256, jobs=jobs)
    return value
