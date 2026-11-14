"""Linux-owned process evidence and trusted, non-bot signal fixtures.

No bot code, sandbox, compilation, CPU lease or engine calls. Subreaping is
process-local and used only by dedicated acceptance/fixture child processes.
Never signal a PID obtained from a standard journal or sidecar file.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, TypeGuard


def safe_env():
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONHASHSEED': '0',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        if key in os.environ: env[key] = os.environ[key]
    return env


def identity(pid):
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'parentPid': int(fields[1]), 'startTicks': int(fields[19]), 'state': fields[0]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def live(value) -> TypeGuard[dict[str, Any]]:
    return value is not None and value['state'] not in ('Z', 'X')


def overlap_snapshot(batch, controller_pid):
    """Two-pass brackets prove an overlap interval, not constant occupancy."""
    candidates = []
    for path in sorted(Path(batch).glob('tasks/*/*/started.json')):
        if path.resolve() != path: raise ValueError('unsafe worker receipt')
        row = json.loads(path.read_bytes()); pid = row['workerPid']
        if type(pid) is not int: raise ValueError('invalid worker PID metadata')
        before = identity(pid); stamp = time.monotonic_ns()
        if live(before) and before['parentPid'] == controller_pid:
            # A live Python worker alone does not prove two bots overlap.
            sandbox_records = sorted(path.parent.glob('matches/*/attempt-*/sandbox-pids.json'))
            if not sandbox_records: continue
            pids = json.loads(sandbox_records[-1].read_bytes()).get('pids', [])
            if len(pids) != 2 or len(set(pids)) != 2: continue
            pair = []
            for sandbox_pid in pids:
                value = identity(sandbox_pid)
                if not live(value) or value['parentPid'] != pid: break
                descendants = owned_descendants(sandbox_pid)
                leaves = [r for r in descendants if live(r) and not owned_child_pids(r['pid'])]
                if not leaves: break
                pair.append({'sandbox': value, 'leaf': leaves[-1]})
            if len(pair) == 2: candidates.append((path, before, time.monotonic_ns(), pair))
    records = []
    for path, before, stamp, pair in candidates:
        end = time.monotonic_ns()
        after = identity(before['pid'])
        confirmed = live(after) and after['parentPid'] == controller_pid and after['startTicks'] == before['startTicks']
        for member in pair:
            for value in member.values():
                current = identity(value['pid'])
                confirmed = (confirmed and live(current) and current['startTicks'] == value['startTicks']
                             and current['parentPid'] == value['parentPid'])
        if confirmed:
            records.append({'receipt': path.relative_to(batch).as_posix(), 'pid': before['pid'],
                            'startTicks': before['startTicks'], 'beforeNs': stamp, 'afterNs': end,
                            'sandboxAndLeafPairs': pair})
    start = max((r['beforeNs'] for r in records), default=0)
    end = min((r['afterNs'] for r in records), default=0)
    return {'activeCount': len(records), 'overlapStartMonotonicNs': start,
            'overlapEndMonotonicNs': end, 'positiveOverlap': bool(records) and end > start,
            'workers': records, 'scope': 'same-controller workers with two live sandbox/leaf process pairs; not CPU occupancy'}


def stop_process(process, *, interrupt_seconds: float = 15, terminate_seconds: float = 5):
    events = []
    if process.poll() is None:
        for name, send, wait in (('SIGINT', lambda: process.send_signal(signal.SIGINT), interrupt_seconds),
                                 ('SIGTERM', process.terminate, terminate_seconds),
                                 ('SIGKILL', process.kill, 5)):
            if process.poll() is not None: break
            try: send()
            except ProcessLookupError: pass
            events.append({'signal': name, 'timeNs': time.time_ns()})
            try: process.wait(timeout=wait)
            except subprocess.TimeoutExpired: continue
            break
    return {'controllerReaped': process.poll() is not None, 'signals': events,
            'descendantCleanupState': 'unknown',
            'descendantCleanupScope': 'controller Popen alone cannot establish descendant exit'}


def enable_subreaper():
    value = ctypes.c_int()
    library = ctypes.CDLL(None, use_errno=True)
    if library.prctl(37, ctypes.byref(value), 0, 0, 0) or library.prctl(36, 1, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'dedicated acceptance child needs Linux subreaper support')
    return {'enabled': True, 'previous': value.value, 'pid': os.getpid(),
            'scope': 'dedicated child process only; no global host or sandbox settings changed'}


def owned_child_pids(pid):
    result = set()
    root = Path(f'/proc/{pid}/task')
    try: tasks = list(root.iterdir())
    except FileNotFoundError: return []
    for task in tasks:
        try: result.update(int(p) for p in (task/'children').read_text().split())
        except FileNotFoundError: pass
    return sorted(result)


def children():
    return owned_child_pids(os.getpid())


def owned_descendants(pid):
    records = []; pending = [pid]; seen = set()
    while pending:
        parent = pending.pop()
        if parent in seen: continue
        seen.add(parent)
        for child in owned_child_pids(parent):
            value = identity(child)
            if value is not None and value['parentPid'] == parent:
                records.append(value); pending.append(child)
    return records


def settle_descendants(*, timeout: float = 5):
    """Only call in our isolated subreaper. ECHILD + empty census proves exit.

    Safety cleanup after timeout cannot turn a failed graceful check into PASS.
    Signals target verified kernel children of THIS process, never sidecar PIDs.
    """
    enabled = ctypes.c_int()
    if ctypes.CDLL(None, use_errno=True).prctl(37, ctypes.byref(enabled), 0, 0, 0) or enabled.value != 1:
        raise ValueError('whole-tree evidence requires our dedicated child subreaper')
    deadline = time.monotonic()+timeout; reaped = []; forced = False; residual = []
    safety_deadline = None
    while True:
        while True:
            try: pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError: pid = 0; break
            if not pid: break
            reaped.append({'pid': pid, 'waitStatus': status})
        current = children()
        if not current:
            try: pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return {'descendantCleanupState': 'confirmed' if not forced else 'forced-safety-cleanup',
                        'noChildrenAndECHILD': True, 'reaped': reaped,
                        'residualBeforeSafetyCleanup': residual, 'safetyCleanupPerformed': forced}
            if pid: reaped.append({'pid': pid, 'waitStatus': status}); continue
        now = time.monotonic()
        if now >= deadline:
            if not forced:
                forced = True; residual = current; safety_deadline = now+5
            for pid in current:
                value = identity(pid)
                if value is not None and value['parentPid'] == os.getpid():
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
            if safety_deadline is not None and now >= safety_deadline:
                return {'descendantCleanupState': 'unknown', 'noChildrenAndECHILD': False,
                        'reaped': reaped, 'residualBeforeSafetyCleanup': residual,
                        'safetyCleanupPerformed': True, 'remainingKernelChildren': children()}
        time.sleep(.01)


FIXTURE = """import os,signal,time
MODE = {mode!r}
GUARDIAN = {guardian}
INITIAL_PARENT = os.getppid()
signal.signal(signal.SIGINT,signal.default_int_handler)
signal.signal(signal.SIGTERM,signal.SIG_DFL)
if MODE in ('term','kill'): signal.signal(signal.SIGINT,signal.SIG_IGN)
if MODE == 'kill': signal.signal(signal.SIGTERM,signal.SIG_IGN)
print('READY',flush=True)
while os.getppid() in (INITIAL_PARENT,GUARDIAN): time.sleep(.02)
"""


def signal_fixture(mode):
    """Caller must be a dedicated fixture subprocess, never a bot process."""
    if mode not in ('int', 'term', 'kill', 'abnormal'): raise ValueError('unknown trusted fixture')
    subreaper = enable_subreaper()
    if mode == 'abnormal':
        # A controller exits abnormally leaving an idle trusted child; no bot is involved.
        code = ("import subprocess,sys,os\np=subprocess.Popen([sys.executable,'-B','-c',"
                +repr(FIXTURE.format(mode='kill',guardian=os.getpid()))+"],stdout=subprocess.PIPE,text=True)\n"
                "assert p.stdout.readline().strip()=='READY'\nprint('CHILD:'+str(p.pid),flush=True)\nos._exit(7)\n")
    else: code = FIXTURE.format(mode=mode,guardian=os.getpid())
    stderr = tempfile.TemporaryFile()
    process = subprocess.Popen([sys.executable, '-B', '-c', code], env=safe_env(),
                               stdout=subprocess.PIPE, stderr=stderr, text=True)
    recorded = False
    try:
        if mode == 'abnormal':
            process.wait(timeout=5)
            assert process.stdout is not None
            child_announced = process.stdout.readline().startswith('CHILD:')
            controller = {'controllerReaped': True, 'returncode': process.returncode,
                          'trustedChildReadyAcknowledged': child_announced, 'descendantCleanupState': 'unknown', 'signals': []}
            # Prove that controller exit by itself did not mean child cleanup.
            deadline = time.monotonic()+2
            while not children() and time.monotonic() < deadline: time.sleep(.01)
            residual_seen = bool(children())
            settled = settle_descendants(timeout=.1)
            passed = (process.returncode == 7 and child_announced and residual_seen
                      and settled['descendantCleanupState'] == 'forced-safety-cleanup'
                      and settled['noChildrenAndECHILD'])
        else:
            import selectors
            with selectors.DefaultSelector() as selector:
                assert process.stdout is not None
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=5) or process.stdout.readline().strip() != 'READY':
                    raise ValueError('trusted fixture failed to become ready')
            controller = stop_process(process, interrupt_seconds=.1, terminate_seconds=.1)
            settled = settle_descendants(timeout=1)
            names = [event['signal'] for event in controller['signals']]
            expected = {'int': ['SIGINT'], 'term': ['SIGINT','SIGTERM'], 'kill': ['SIGINT','SIGTERM','SIGKILL']}
            passed = names == expected[mode] and controller['controllerReaped'] and settled['noChildrenAndECHILD']
        stderr.seek(0); captured_stderr = stderr.read(65536).decode('utf-8',errors='replace')
        recorded = True
        return {'mode': mode, 'passed': passed, 'controller': controller, 'descendants': settled,
                'fixtureStderr': captured_stderr,
                'subreaper': subreaper, 'trustedFixtureProcessReservation': 2 if mode == 'abnormal' else 1,
                'botStarts': 0, 'scope': 'trusted Python signal/lifecycle fixture; no bot/sandbox/CPU lease'}
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)
        if process.stdout is not None: process.stdout.close()
        settle_descendants(timeout=.1)
        if not recorded:
            stderr.seek(0)
            print(stderr.read(65536).decode('utf-8',errors='replace'),file=sys.stderr)
        stderr.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', choices=('int','term','kill','abnormal'), required=True)
    args = parser.parse_args()
    result = signal_fixture(args.fixture)
    print(json.dumps(result)); return 0 if result['passed'] else 2


if __name__ == '__main__': raise SystemExit(main())
