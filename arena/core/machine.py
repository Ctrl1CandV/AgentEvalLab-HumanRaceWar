"""Non-secret hardware metadata; affinity/leased CPUs are NOT CPU inventory."""
import os
from pathlib import Path
import platform


def machine_info() -> dict:
    cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                if line.startswith('model name')), 'unknown')
    return {'cpu': cpu, 'logicalCpus': os.cpu_count(), 'architecture': platform.machine(),
            'kernel': platform.release(), 'memoryBytes': os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')}


def machine_fingerprint(machine) -> dict:
    if (not isinstance(machine, dict) or any(not isinstance(machine.get(k), str)
            or not machine[k].strip() or machine[k] == 'unknown' for k in ('cpu', 'architecture'))
            or any(type(machine.get(k)) is not int or machine[k] <= 0 for k in ('logicalCpus', 'memoryBytes'))):
        raise ValueError('missing/invalid machine inventory; leased CPUs cannot substitute for logical CPU count')
    gib = 1 << 30
    # Rounded-up GiB of visible physical memory, not free/available memory.
    # Kernel version is recorded for diagnostics, but is not a hardware identity.
    return {'cpu': machine['cpu'].strip(), 'architecture': machine['architecture'],
            'logicalCpus': machine['logicalCpus'], 'visibleMemoryGiB': (machine['memoryBytes']+gib-1)//gib}


def require_local_machine(expected: dict):
    if expected != machine_fingerprint(machine_info()):
        raise ValueError('fixed timing machine fingerprint differs; benchmark and freeze on this host, '
                         'never reuse another machine\'s budget')
