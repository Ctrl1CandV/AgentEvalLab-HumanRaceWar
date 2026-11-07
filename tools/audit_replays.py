"""Mechanically audit existing replays; never start bots or count replays as new games."""
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
import time
from typing import TypedDict

from arena.core.resources import CpuLease
from arena.games.outpost.replay import verify


class AuditRow(TypedDict):
    path: str
    sha256: str
    verified: bool
    verificationCpuNs: int
    error: str | None


def _pin(queue):
    os.sched_setaffinity(0,{queue.get()})


def _verify(path):
    before=time.process_time_ns()
    p=Path(path)
    row: AuditRow={'path':str(p),'sha256':sha256(p.read_bytes()).hexdigest(),
                   'verified':False,'verificationCpuNs':0,'error':None}
    try:
        verify(p)
        row['verified']=True
    except Exception as error:
        row.update(verified=False,error=f'{type(error).__name__}: {error}')
    row['verificationCpuNs']=time.process_time_ns()-before
    return row


def audit(paths,*,jobs=4):
    paths=sorted({str(Path(p).resolve()) for p in paths})
    if not paths: return {'replays':[],'allVerified':True,'verificationCpuNs':0}
    count=min(jobs,len(paths)); start=time.monotonic_ns()
    context=multiprocessing.get_context('spawn')
    with CpuLease(count) as lease:
        queue=context.SimpleQueue()
        for cpu in lease.cpus: queue.put(cpu)
        with ProcessPoolExecutor(count,mp_context=context,initializer=_pin,initargs=(queue,)) as pool:
            rows=list(pool.map(_verify,paths))
        queue.close()
    return {'replays':rows,'allVerified':all(r['verified'] for r in rows),
            'verificationCpuNs':sum(r['verificationCpuNs'] for r in rows),
            'wallNs':time.monotonic_ns()-start,
            'scope':'Current verifier checks transcript semantics; not timing authenticity or an independent-machine rerun.'}
