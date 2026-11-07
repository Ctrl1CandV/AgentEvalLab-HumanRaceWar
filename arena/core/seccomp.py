"""Runtime-only Linux x86-64 classic BPF policy; no third-party dependency.

The compiler is trusted tooling and needs subprocesses, so gets a separate mode.
Unknown architectures fail closed. x32/i386 cannot bypass the x86-64 policy.
"""
import errno
import platform
import struct


def runtime_filter() -> bytes:
    if platform.machine() != "x86_64":
        raise RuntimeError("runtime seccomp policy currently supports only Linux x86-64")
    allow, kill, error = 0x7FFF0000, 0x80000000, 0x00050000
    rows = [(0x20, 0, 0, 4),                 # seccomp_data.arch
            (0x15, 1, 0, 0xC000003E),      # AUDIT_ARCH_X86_64
            (0x06, 0, 0, kill),
            (0x20, 0, 0, 0),               # seccomp_data.nr
            (0x35, 0, 1, 0x40000000),      # reject x32 syscall numbers
            (0x06, 0, 0, kill)]
    # fork, vfork, sched_setaffinity, ptrace, process_vm_{readv,writev},
    # unshare, setns, memfd_create and SysV shared-memory allocation.
    # Together with read-only /tmp and /dev, shared-memory files cannot evade AS.
    for syscall in (57, 58, 203, 101, 310, 311, 272, 308, 319, 29):
        rows += [(0x15, 0, 1, syscall), (0x06, 0, 0, error | errno.EPERM)]
    # glibc falls back to clone when clone3 reports ENOSYS (also for std::thread).
    rows += [(0x15, 0, 1, 435), (0x06, 0, 0, error | errno.ENOSYS),
             (0x15, 0, 4, 56),              # clone
             (0x20, 0, 0, 16),              # args[0], low 32 bits: clone flags
             (0x45, 1, 0, 0x00010000),      # CLONE_THREAD required
             (0x06, 0, 0, error | errno.EPERM),
             (0x06, 0, 0, allow),
             (0x06, 0, 0, allow)]
    return b"".join(struct.pack("=HBBI", *row) for row in rows)
