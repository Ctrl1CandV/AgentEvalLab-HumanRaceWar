"""Offline environment probe. Runs trusted tools only, never bot code.

Run inside Linux/WSL with: python3 tools/check_environment.py
Output deliberately omits hostnames, user names, paths and environment variables.
A successful /bin/true probe is not a complete sandbox security acceptance test.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def command(args: list[str]) -> dict:
    if shutil.which(args[0]) is None:
        return {"available": False}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return {
            "available": True,
            "exitCode": proc.returncode,
            "firstLine": (proc.stdout or proc.stderr).splitlines()[:1],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": type(exc).__name__}


def probe() -> dict:
    linux = sys.platform == "linux"
    cpu_model = None
    memory_kib = None
    os_release = None
    if linux:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                memory_kib = int(line.split()[1])
                break
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                os_release = line.split("=", 1)[1].strip('"')
                break
    versions = {
        "python313": command(["python3.13", "--version"]),
        "gcc11": command(["g++-11", "--version"]),
        "bubblewrap": command(["bwrap", "--version"]),
    }
    sandbox = {"tested": False}
    if linux and shutil.which("bwrap"):
        args = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session"]
        for directory in ("/usr", "/bin", "/lib", "/lib64"):
            args.extend(["--ro-bind-try", directory, directory])
        args.extend(["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"])
        args.extend(["--clearenv", "--", "/bin/true"])
        sandbox = {"tested": True, "trustedCommand": "/bin/true", **command(args)}
    return {
        "schemaVersion": 1,
        "system": platform.system(),
        "kernel": platform.release(),
        "distribution": os_release,
        "pythonRunningProbe": platform.python_version(),
        "hardware": {
            "cpuModel": cpu_model,
            "logicalCpus": os.cpu_count(),
            "memoryKiB": memory_kib,
        },
        "toolchain": versions,
        "sandboxSmoke": sandbox,
        "speedFactor": None,
        "speedFactorStatus": "not calibrated; no performance acceptance data",
        "botExecutions": 0,
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2, ensure_ascii=True))
