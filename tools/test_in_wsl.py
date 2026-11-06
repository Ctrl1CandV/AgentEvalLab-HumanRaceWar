"""Copy only public engine/test source to a temporary WSL directory and test.

No mounts, installation, bot execution or network access. This trusted developer
utility runs on the Windows host; all engine tests run in WSL. Python 3.10 runs
are development checks only. Pass --python python3.13 when it becomes available.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import tarfile

DRIVER = r'''
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

runs = []
with tempfile.TemporaryDirectory(prefix="hrw-engine-") as directory:
    root = Path(directory)
    with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()), mode="r:") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts or member.size > 2 * 1024 * 1024:
                raise ValueError("unexpected test archive member")
            target = root.joinpath(*name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("missing test archive member")
            target.write_bytes(source.read())
    for label, pattern, seed in (
        ("full-seed-0", "test_*.py", "0"),
        ("full-seed-1", "test_*.py", "1"),
        ("determinism", "test_determinism.py", "0"),
        ("protocol", "test_protocol.py", "0"),
    ):
        proc = subprocess.run(
            [sys.executable, "tools/run_tests.py", "--json", "--pattern", pattern],
            cwd=root, capture_output=True, text=True, timeout=120,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONHASHSEED": seed},
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError("test process failed outside unittest")
        result = json.loads(proc.stdout)
        result.update(label=label, pythonHashSeed=seed, exitCode=proc.returncode)
        runs.append(result)
print(json.dumps(runs, ensure_ascii=True))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution", default="Ubuntu-22.04")
    parser.add_argument("--python", default="python3")
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "arena").rglob("*.py"))
    files += [root / "tests" / name for name in (
        "__init__.py", "helpers.py", "test_rules.py", "test_protocol.py", "test_determinism.py"
    )]
    files.extend([root / "tools/run_tests.py", root / "rules/rules.md"])
    archive = io.BytesIO()
    inputs = {}
    with tarfile.open(fileobj=archive, mode="w:") as output:
        for path in sorted(files):
            if path.is_symlink():
                raise ValueError("test inputs must not be symbolic links")
            name = path.relative_to(root).as_posix()
            content = path.read_bytes()
            inputs[name] = sha256(content).hexdigest()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(content), 0o644
            output.addfile(info, io.BytesIO(content))
    proc = subprocess.run(
        ["wsl.exe", "-d", args.distribution, "--exec", args.python, "-c", DRIVER],
        input=archive.getvalue(), capture_output=True, timeout=540,
    )
    if proc.returncode != 0:
        # Do not persist raw environment/launcher stderr in public reports.
        print("WSL test launcher failed; no successful test report written. Check interpreter/WSL availability.")
        return 2
    runs = json.loads(proc.stdout)
    logs = {
        "full-seed-0": "engine-tests.log", "full-seed-1": "engine-tests-seed1.log",
        "determinism": "determinism.log", "protocol": "robustness.log",
    }
    for run in runs:
        log = run.pop("log")
        filename = logs[run["label"]]
        (root / "logs" / filename).write_text(
            "DEVELOPMENT CHECK ONLY: trusted engine; no bot processes, replay files or sandbox acceptance.\n"
            + f"Python {run['python']}; {run['system']}; PYTHONHASHSEED={run['pythonHashSeed']}\n"
            + "Raw-byte streams, crash/timeout handling and output flooding are NOT tested.\n\n" + log,
            encoding="utf-8", newline="\n",
        )
        run["logFile"] = "logs/" + filename
    report = {
        "schemaVersion": 1,
        "scope": "A1 development validation, not phase-A acceptance",
        "startedAt": started_at,
        "launcherSha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "environmentFile": "data/environment.json",
        "speedFactor": None,
        "inputsSha256": inputs,
        "testArchiveSha256": sha256(archive.getvalue()).hexdigest(),
        "runs": runs,
        "measuredTestProcessCpuSeconds": sum(run["measuredTestProcessCpuSeconds"] for run in runs),
        "passed": all(run["passed"] and run["exitCode"] == 0 for run in runs),
        "botExecutions": 0,
    }
    text = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    (root / "data/engine-tests.json").write_text(text, encoding="utf-8", newline="\n")
    history = root / "runs/development/test-history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=True) + "\n")
    for run in runs:
        print(f"{run['label']}: {run['testsRun']} tests, passed={run['passed']}, Python {run['python']}")
    print("Saved data/engine-tests.json and explicitly scoped logs/; retained local test history.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
