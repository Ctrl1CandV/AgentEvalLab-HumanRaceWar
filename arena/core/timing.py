"""Load-bound timing calibration metadata and consistently scaled budgets."""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path


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

    def header(self) -> dict:
        return {"jobs": self.jobs, "cpus": self.cpus, "speedFactor": self.factor,
                "reportSha256": self.report_sha256, "reference": self.reference,
                "workloadSha256": self.workload_sha256}

    @classmethod
    def load(cls, path: Path, workload_sha256: str, *, jobs: int) -> "Calibration":
        raw = path.read_bytes()
        r = json.loads(raw)
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
        return cls(jobs, tuple(cpus), factor, sha256(raw).hexdigest(), reference, workload_sha256)
