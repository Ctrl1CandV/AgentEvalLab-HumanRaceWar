"""Trusted, single-threaded batch worker. Never invoked as a bot."""
import ctypes
import json
import os
from pathlib import Path
import signal
import sys

from arena.core.benchmark import workload_digest
from arena.core.journal import atomic_json
from arena.core.sandbox import Bot
from arena.core.timing import Calibration
from arena.match import play


def main():
    def interrupted(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parent = os.getppid()
    if ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0):
        raise RuntimeError('cannot arrange worker death on parent exit')
    if parent == 1 or os.getppid() != parent: return 3
    job = json.loads(Path(sys.argv[1]).read_text())
    allocation = job['allocation']
    os.sched_setaffinity(0, set(allocation['runners']))
    calibration = Calibration.load(Path(job['timing']),workload_digest(),jobs=allocation['jobs']) if job['timing'] else None
    bots = [Bot(**{**b,'directory':Path(b['directory'])}) for b in job['prepared']]
    try:
        row = play([Path(p) for p in job['sources']],Path(job['map']).read_text(),Path(job['out']),job['seeds'],
                   calibration=calibration,sandbox=job['sandbox'],prepared=bots,ruleset=job['ruleset'],retries=job['retries'],
                   task_id=job['taskId'],_allocation=allocation)
        atomic_json(Path(job['reply']),row)
        return 0 if row['status']=='complete' else 2
    except BaseException as error:
        atomic_json(Path(job['reply']),{'status':'interrupted' if isinstance(error,KeyboardInterrupt) else 'worker_error',
                                       'taskId':job['taskId'],'error':type(error).__name__})
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
