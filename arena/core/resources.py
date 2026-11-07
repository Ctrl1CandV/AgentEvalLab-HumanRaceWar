"""Cooperating-process CPU leases. Trusted batch workers inherit lease FDs.
Locks release after controller AND workers exit; bot launchers close those FDs.

They exclude other arena jobs, not unrelated user/OS workloads. No threads are
used around the launcher's preexec_fn. Lock files contain no credentials.
"""
from contextlib import AbstractContextManager
import fcntl
import os
from pathlib import Path
import stat
import time

from .sandbox import InfrastructureError


def lock_directory():
    # All cooperating arena commands must use the same TMPDIR on a host.
    directory = Path(os.environ.get('TMPDIR') or '/tmp') / f'hrw-cpu-locks-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise InfrastructureError('unsafe global resource-lock directory')
    return directory


def open_lock(directory, name):
    fd = os.open(directory / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        os.close(fd)
        raise InfrastructureError('unsafe resource lock file')
    return fd


class CompileLease(AbstractContextManager):
    """One compiler at a time across cooperating arena processes, not per cache."""
    def __init__(self):
        self.fd = open_lock(lock_directory(), 'compile')
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except BaseException:
            os.close(self.fd)
            raise

    def __exit__(self, *args):
        os.close(self.fd)


class CpuLease(AbstractContextManager):
    def __init__(self, workers: int, *, exact=None, reserve_runner=True, runner_count=1, timeout=30.0):
        self.mask = set(os.sched_getaffinity(0))
        runners = runner_count if reserve_runner else 0
        if type(runners) is not int or runners < 0:
            raise ValueError('invalid runner CPU count')
        if type(workers) is not int or workers < 1 or workers+runners > len(self.mask):
            raise ValueError('not enough CPUs for workers and an independent runner')
        if exact is not None and (len(exact) != workers or len(set(exact)) != workers
                                  or not set(exact) <= self.mask):
            raise ValueError('invalid requested CPU pool')
        directory = lock_directory()
        self.files = []
        self.cpus = []
        self.runners = []
        deadline = time.monotonic()+timeout
        while True:
            acquired = []
            requested = list(exact) if exact is not None else sorted(self.mask)
            if exact is not None and reserve_runner:
                requested += sorted(self.mask-set(exact))
            try:
                for cpu in requested:
                    fd = open_lock(directory, str(cpu))
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        os.close(fd)
                        if exact is not None and cpu in exact: break
                        continue
                    acquired.append((cpu, fd))
                    if len(acquired) == workers+runners:
                        self.cpus = [c for c, _ in acquired[:workers]]
                        self.runners = [c for c, _ in acquired[workers:]]
                        self.files = [f for _, f in acquired]
                        os.sched_setaffinity(0, set(self.runners) if self.runners else self.mask)
                        return
            finally:
                if not self.files:
                    for _, fd in acquired: os.close(fd)
            if time.monotonic() >= deadline:
                raise InfrastructureError('requested CPUs busy; no bot started')
            time.sleep(0.05)

    def __exit__(self, *args):
        os.sched_setaffinity(0, self.mask)
        for fd in self.files: os.close(fd)
        self.files = []

    @property
    def pool(self):
        return self.cpus+self.runners
