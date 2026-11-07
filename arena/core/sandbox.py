"""Linux bubblewrap launcher. Never falls back to host/plain execution."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
from typing import IO

ROOT = Path(__file__).resolve().parents[2]
STARTED = b"HRW_SANDBOX_STARTED\n"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "TMPDIR": "/tmp", "TMP": "/tmp", "TEMP": "/tmp",
       "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
       "PYTHONPATH": "/sdk"}


class InfrastructureError(RuntimeError):
    pass


@dataclass
class Bot:
    code: str
    digest: str
    directory: Path
    language: str
    command: list[str]
    compile_fault: str | None = None


def snapshot(source: Path, target: Path) -> str:
    """Freeze the explicitly supplied bot/SDK; reject links and special files."""
    source = source.resolve()
    target.mkdir(parents=True, exist_ok=False)
    hashes = []
    total = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if "__pycache__" in relative.parts:
            continue
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError("bot/SDK snapshots may not contain links or special files")
        dest = target / relative
        if path.is_dir():
            dest.mkdir(exist_ok=True)
        else:
            size = path.stat().st_size
            total += size
            if size > 16*1024*1024 or total > 64*1024*1024:
                raise ValueError("bot/SDK source snapshot too large")
            data = path.read_bytes()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            hashes.append([relative.as_posix(), sha256(data).hexdigest()])
    return sha256(json.dumps(hashes, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


class Bubblewrap:
    def __init__(self):
        executable = shutil.which("bwrap", path="/usr/bin:/bin")
        if executable is None:
            raise InfrastructureError("bubblewrap missing; install only with user approval")
        self.executable = executable
        self.runtime = Path(sys.base_prefix).resolve()
        self.python_name = Path(sys.executable).resolve().name
        self.cpus = sorted(os.sched_getaffinity(0))

    def argv(self, bot: Path, sdk: Path, command: list[str], build: Path | None = None,
             writable_build: bool = False) -> list[str]:
        args = [self.executable, "--unshare-all", "--die-with-parent", "--new-session",
                "--cap-drop", "ALL", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        # No host /etc, HOME, project root, credentials, or other bots.
        for path in ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32"):
            args += ["--ro-bind-try", path, path]
        args += ["--ro-bind", str(self.runtime), "/runtime", "--ro-bind", str(bot), "/bot",
                 "--ro-bind", str(sdk), "/sdk", "--ro-bind", str(Path(__file__).with_name("sandbox_exec.py")),
                 "/launcher.py", "--chdir", "/bot", "--clearenv"]
        for name, value in ENV.items():
            args += ["--setenv", name, value]
        if build is not None:
            args += ["--bind" if writable_build else "--ro-bind", str(build), "/build"]
        return [*args, "--", f"/runtime/bin/{self.python_name}", "-I", "-S", "/launcher.py", *command]

    def launch(self, bot: Path, sdk: Path, command: list[str], cpu: int, *, build: Path | None = None,
               cpu_seconds: int = 40, stdout: int | IO = subprocess.PIPE,
               stderr: int | IO = subprocess.PIPE, writable_build: bool = False):
        if cpu not in self.cpus:
            raise InfrastructureError("CPU not available in current affinity mask")

        def limits():
            os.sched_setaffinity(0, {cpu})
            for kind, value in ((resource.RLIMIT_AS, 512*1024*1024), (resource.RLIMIT_FSIZE, 16*1024*1024),
                                (resource.RLIMIT_NOFILE, 64), (resource.RLIMIT_CPU, cpu_seconds),
                                (resource.RLIMIT_CORE, 0)):
                resource.setrlimit(kind, (value, value))

        try:
            # Serial launcher only: preexec_fn must not be used by a threaded scheduler.
            return subprocess.Popen(self.argv(bot, sdk, command, build, writable_build), stdin=subprocess.PIPE,
                                    stdout=stdout, stderr=stderr, env=ENV, close_fds=True,
                                    start_new_session=True, preexec_fn=limits)
        except (OSError, subprocess.SubprocessError) as error:
            raise InfrastructureError(f"sandbox launch failed: {type(error).__name__}") from error


def stop(process: subprocess.Popen, *, close_streams: bool = True) -> None:
    # Kill the bwrap process group; namespace init death also kills all descendants.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    if close_streams:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def prepare(source: Path, directory: Path, launcher: Bubblewrap, cpu: int) -> Bot:
    if not source.is_dir() or (source / "main.py").is_file() == bool(list(source.glob("*.cpp"))):
        raise ValueError("bot directory must contain main.py OR top-level *.cpp")
    directory.mkdir(parents=True, exist_ok=False)
    digest = snapshot(source, directory / "source")
    frozen = directory / "source"
    python = (frozen / "main.py").is_file()
    cpp = sorted(frozen.glob("*.cpp"))
    if python == bool(cpp):
        raise ValueError("bot directory must contain main.py OR top-level *.cpp")
    language = "python" if python else "cpp"
    sdk_hash = snapshot(ROOT / "sdk" / language, directory / "sdk")
    # Identity includes public SDK bytes, not only the user source.
    digest = sha256(f"{digest}:{sdk_hash}".encode()).hexdigest()
    bot = Bot(source.name, digest, directory, language,
              [f"/runtime/bin/{launcher.python_name}", "-s", "-B", "-u", "/bot/main.py"] if python else ["/build/bot"])
    if cpp:
        build = directory / "build"
        build.mkdir()
        args = ["/usr/bin/g++", "-O2", "-std=gnu++20", "-I/sdk", "-o", "/build/bot",
                *(f"/bot/{p.name}" for p in cpp)]
        start = time.monotonic()
        with (directory / "compile.stdout").open("wb") as out, (directory / "compile.stderr").open("wb") as err:
            process = launcher.launch(frozen, directory / "sdk", args, cpu, build=build,
                                      cpu_seconds=60, stdout=out, stderr=err, writable_build=True)
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                bot.compile_fault = "compile_timeout"
            finally:
                stop(process)
        with (directory / "compile.stdout").open("rb") as stream:
            started = stream.read(len(STARTED)) == STARTED
        if not started or process.returncode == 125:
            raise InfrastructureError("compiler sandbox preparation failed; see compile logs")
        if process.returncode != 0:
            bot.compile_fault = bot.compile_fault or "compile_failed"
        executable = build / "bot"
        if not bot.compile_fault and (executable.is_symlink() or not executable.is_file()):
            bot.compile_fault = "compile_missing_output"
        (directory / "compile.json").write_text(json.dumps({"returncode": process.returncode,
            "fault": bot.compile_fault, "wallSeconds": time.monotonic()-start,
            "cpuSeconds": None, "sandbox": "bwrap"}, indent=2)+"\n")
    return bot


class CpuClock:
    """Sample process clocks (all threads), including visible descendants.

    Retain last samples after exits. Very short-lived children may escape sampling;
    v1 bots are single-process. This is not full process-tree accounting acceptance.
    """
    def __init__(self, pid: int):
        self.pid = pid
        self.samples: dict[int, int] = {}
        self.fallback = False

    def read_ns(self) -> int:
        pending, seen = [self.pid], set()
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                for task in Path(f"/proc/{pid}/task").iterdir():
                    try:
                        pending.extend(map(int, (task / "children").read_text().split()))
                    except (FileNotFoundError, ProcessLookupError):
                        pass
                try:
                    value = time.clock_gettime_ns(((~pid) << 3) | 2)
                except OSError:
                    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                    value = (int(fields[11])+int(fields[12])) * 1_000_000_000 // os.sysconf("SC_CLK_TCK")
                    self.fallback = True
                self.samples[pid] = max(self.samples.get(pid, 0), value)
            except (FileNotFoundError, ProcessLookupError):
                pass
            except PermissionError as error:
                raise InfrastructureError("cannot measure sandbox CPU") from error
        return sum(self.samples.values())
