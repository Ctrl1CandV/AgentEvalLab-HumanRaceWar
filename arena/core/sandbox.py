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
import tempfile
from typing import IO

from .seccomp import runtime_filter

ROOT = Path(__file__).resolve().parents[2]
STARTED = b"HRW_SANDBOX_STARTED\n"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "TMPDIR": "/tmp", "TMP": "/tmp", "TEMP": "/tmp",
       "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
       "PYTHONPATH": "/sdk"}


class InfrastructureError(RuntimeError):
    pass


class SubmissionError(ValueError):
    """Invalid untrusted source, not an infrastructure failure."""


@dataclass
class Bot:
    code: str
    digest: str | None
    directory: Path
    language: str
    command: list[str]
    compile_fault: str | None = None
    validation_error: str | None = None


def snapshot(source: Path, target: Path) -> str:
    """Freeze the explicitly supplied bot/SDK; reject links and special files."""
    if source.is_symlink() or not source.is_dir():
        raise SubmissionError("source must be a directory, not a symbolic link")
    source = source.resolve()
    target.mkdir(parents=True, exist_ok=False)
    hashes = []
    total = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise SubmissionError("bot/SDK snapshots may not contain links or special files")
        if "__pycache__" in relative.parts:
            continue
        dest = target / relative
        if path.is_dir():
            dest.mkdir(exist_ok=True)
        else:
            size = path.stat().st_size
            total += size
            if size > 16*1024*1024 or total > 64*1024*1024:
                raise SubmissionError(f"source exceeds 16 MiB per file or 64 MiB total: {relative.as_posix()!r}, file={size}, total={total}")
            data = path.read_bytes()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            hashes.append([relative.as_posix(), sha256(data).hexdigest()])
    return sha256(json.dumps(hashes, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


class Bubblewrap:
    def __init__(self):
        if os.geteuid() == 0:
            raise InfrastructureError("unprivileged host UID required for the sandbox task limit")
        executable = shutil.which("bwrap", path="/usr/bin:/bin")
        if executable is None:
            raise InfrastructureError("bubblewrap missing; install only with user approval")
        self.executable = executable
        self.runtime = Path(sys.base_prefix).resolve()
        self.python_name = Path(sys.executable).resolve().name
        self.cpus = sorted(os.sched_getaffinity(0))

    def argv(self, bot: Path, sdk: Path, command: list[str], build: Path | None = None,
             writable_build: bool = False, seccomp_fd: int | None = None) -> list[str]:
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
        if writable_build:
            # Compiler temporaries live on disk, not in an unbounded RAM tmpfs.
            assert build is not None
            scratch = build / "tmp"
            scratch.mkdir(exist_ok=True)
            args += ["--bind", str(scratch), "/tmp"]
        else:
            args += ["--remount-ro", "/tmp", "--remount-ro", "/dev"]
            if seccomp_fd is not None:
                args += ["--seccomp", str(seccomp_fd)]
        # bwrap's synthetic root is itself a tmpfs owned by the sandbox user.
        # Lock it too: read-only /tmp alone still allowed allocations at /file.
        args += ["--remount-ro", "/"]
        mode = "compile" if writable_build else "runtime"
        return [*args, "--", f"/runtime/bin/{self.python_name}", "-I", "-S", "/launcher.py", mode, *command]

    def launch(self, bot: Path, sdk: Path, command: list[str], cpu: int, *, build: Path | None = None,
               cpu_seconds: int = 40, stdout: int | IO = subprocess.PIPE,
               stderr: int | IO = subprocess.PIPE, writable_build: bool = False):
        if cpu not in self.cpus:
            raise InfrastructureError("CPU not available in current affinity mask")

        def limits():
            os.sched_setaffinity(0, {cpu})
            address_space = (2048 if writable_build else 512)*1024*1024
            for kind, value in ((resource.RLIMIT_AS, address_space), (resource.RLIMIT_FSIZE, 16*1024*1024),
                                (resource.RLIMIT_NOFILE, 64), (resource.RLIMIT_CPU, cpu_seconds),
                                (resource.RLIMIT_CORE, 0)):
                resource.setrlimit(kind, (value, value))

        try:
            # Serial launcher only: use process workers, never a threaded scheduler.
            with tempfile.TemporaryFile() as policy:
                if not writable_build:
                    policy.write(runtime_filter())
                    policy.flush()
                    policy.seek(0)
                fd = policy.fileno() if not writable_build else None
                return subprocess.Popen(self.argv(bot, sdk, command, build, writable_build, fd),
                                        stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, env=ENV,
                                        close_fds=True, pass_fds=() if fd is None else (fd,),
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
    directory.mkdir(parents=True, exist_ok=False)
    frozen = directory / "source"
    try:
        if not source.is_dir() or (source / "main.py").is_file() == bool(list(source.glob("*.cpp"))):
            raise SubmissionError("bot directory must contain main.py OR top-level *.cpp, not both")
        digest = snapshot(source, frozen)
        python = (frozen / "main.py").is_file()
        cpp = sorted(frozen.glob("*.cpp"))
        if python == bool(cpp):
            raise SubmissionError("bot directory must contain main.py OR top-level *.cpp, not both")
    except SubmissionError as error:
        reason = str(error)
        (directory / "validation.json").write_text(json.dumps({"valid": False, "reason": reason})+"\n")
        # No invented content digest when an unsafe/oversized tree was rejected.
        return Bot(source.name, None, directory, "invalid", [], "compile_failed", reason)
    (directory / "validation.json").write_text(json.dumps({"valid": True, "reason": None})+"\n")
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
        if not started:
            raise InfrastructureError("compiler sandbox preparation failed; see compile logs")
        if process.returncode != 0:
            bot.compile_fault = bot.compile_fault or "compile_failed"
        executable = build / "bot"
        if not bot.compile_fault and (executable.is_symlink() or not executable.is_file()):
            bot.compile_fault = "compile_missing_output"
        (directory / "compile.json").write_text(json.dumps({"returncode": process.returncode,
            "fault": bot.compile_fault, "wallSeconds": time.monotonic()-start,
            "cpuSeconds": None, "sandbox": "bwrap", "addressSpaceBytes": 2*1024**3}, indent=2)+"\n")
    return bot


class CpuClock:
    """Process clocks include live AND exited threads; retain exited processes.

    Runtime seccomp forbids bot child processes. Only trusted bwrap leaders fork,
    so follow leaders' children, not every bot thread on every 2 ms poll.
    Missing proc interfaces on a live process fail closed.
    """
    def __init__(self, pid: int):
        self.pid = pid
        self.samples: dict[int, int] = {}
        self.fallback = False
        self.observed_descendant = False

    def read_ns(self) -> int:
        pending, seen = [self.pid], set()
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                children = Path(f"/proc/{pid}/task/{pid}/children").read_text()
                pending.extend(map(int, children.split()))
                self.observed_descendant |= pid != self.pid
                try:
                    value = time.clock_gettime_ns(((~pid) << 3) | 2)
                except OSError:
                    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                    value = (int(fields[11])+int(fields[12])) * 1_000_000_000 // os.sysconf("SC_CLK_TCK")
                    self.fallback = True
                self.samples[pid] = max(self.samples.get(pid, 0), value)
            except (FileNotFoundError, ProcessLookupError) as error:
                if Path(f"/proc/{pid}").exists():
                    raise InfrastructureError("missing CPU/proc interface for a live sandbox process") from error
            except PermissionError as error:
                raise InfrastructureError("cannot measure sandbox CPU") from error
        return sum(self.samples.values())
