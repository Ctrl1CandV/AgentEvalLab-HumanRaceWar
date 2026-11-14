"""Explicitly enabled supervisor over the unchanged standard tournament.

Fresh runs only. No scoring mode, source interpretation, benchmark, or retry of a
whole experiment. Stop observation is polling, not a zero-latency dispatch hook.
"""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from arena.core.journal import atomic_json
from arena.core.sandbox import parent_death_guard
from arena.tournament import run_tournament
from tools import experiment_plan as plan


class HashLog:
    def __init__(self, path):
        self.stream = Path(path).open('xb')
        self.previous = '0'*64
        self.count = 0

    def append(self, event, payload):
        row = {'seq': self.count, 'previousSha256': self.previous, 'event': event,
               'timeNs': time.time_ns(), 'payload': payload}
        row['sha256'] = sha256(plan.canonical(row)).hexdigest()
        self.stream.write(plan.canonical(row)+b'\n'); self.stream.flush(); os.fsync(self.stream.fileno())
        self.previous = row['sha256']; self.count += 1

    def close(self):
        self.stream.close()


def verify_log(path, *, expected_head, expected_count):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('truncated experiment log')
    previous = '0'*64; rows = []
    for index, line in enumerate(raw.splitlines()):
        row = json.loads(line, object_pairs_hook=plan.unique_object)
        digest = row.pop('sha256')
        if (row['seq'] != index or row['previousSha256'] != previous
                or sha256(plan.canonical(row)).hexdigest() != digest):
            raise ValueError('broken experiment log chain')
        previous = digest; rows.append(row)
    if (len(rows) != expected_count or previous != expected_head or not rows
            or rows[0]['event'] != 'start' or rows[-1]['event'] != 'end'):
        raise ValueError('missing/truncated terminal log or wrong external head')
    return rows


class Tail:
    """Read standard journals without their mutating torn-tail recovery helper."""
    def __init__(self, path):
        self.path = Path(path); self.offset = 0; self.pending = b''

    def poll(self, *, final=False):
        if not self.path.exists():
            if self.offset or self.pending:
                raise ValueError('observed journal disappeared')
            return []
        if self.path.is_symlink() or self.path.stat().st_size < self.offset:
            raise ValueError('journal changed or truncated')
        with self.path.open('rb') as stream:
            stream.seek(self.offset); raw = stream.read(); self.offset += len(raw)
        data = self.pending+raw; parts = data.split(b'\n'); self.pending = parts.pop()
        if len(self.pending) > 4*1024*1024 or any(len(x) > 4*1024*1024 for x in parts):
            raise ValueError('oversized journal row')
        if final and self.pending:
            raise ValueError('incomplete standard journal suffix retained')
        return [json.loads(x, object_pairs_hook=plan.unique_object) for x in parts]


def expected_manifest(frame):
    root = plan.ROOT
    request = {'sources': [str(root/b['frozen']) for b in frame['bots']],
               'maps': [str(root/m['frozen']) for m in frame['maps']],
               'jobs': frame['spec']['jobs'], 'pairs': frame['pairs'], 'seeds': frame['spec']['seeds'],
               'sandbox': 'bwrap', 'ruleset': {}, 'framework': frame['frameworkSha256'],
               'referenceSha256': None,
               'fixedTiming': {'mode': 'import', 'sourceSha256': frame['spec']['timing']['sha256']},
               'sourceHashes': [b['sha256'] for b in frame['bots']],
               'mapHashes': [m['sha256'] for m in frame['maps']]}
    tasks = []
    for a, b in frame['pairs']:
        for index, entry in enumerate(frame['maps']):
            p = Path(entry['frozen'])
            for swapped in (False, True):
                task = {'players': [b, a] if swapped else [a, b], 'mapIndex': index,
                        'mapName': p.name, 'mapType': p.stem.split('-')[0],
                        'seeds': list(reversed(frame['spec']['seeds'])) if swapped else frame['spec']['seeds'],
                        'swapped': swapped}
                task['taskId'] = sha256(json.dumps([request, task], sort_keys=True).encode()).hexdigest()
                tasks.append(task)
    return {'schemaVersion': 1, 'request': request, 'tasks': tasks,
            'bots': [b['label'] for b in frame['bots']]}


class Observer:
    def __init__(self, out, frame, log):
        self.out = Path(out); self.frame = frame; self.log = log
        self.manifest = expected_manifest(frame)
        self.tasks = {t['taskId']: t for t in self.manifest['tasks']}
        self.tails = {name: Tail(self.out/'batch'/f'{name}.jsonl') for name in ('attempts', 'results', 'executions')}
        self.rows = {name: [] for name in self.tails}; self.attempts = set(); self.completed = set()
        self.attempt_rows = {}; self.pending_results = []; self.task_attempts = Counter()
        self.failures = Counter(); self.fault_games = 0; self.terminal_error = False
        self.manifest_checked = False

    def poll(self, *, final=False):
        manifest = self.out/'batch/manifest.json'
        if manifest.exists() and (not self.manifest_checked or final):
            if plan.load_json(manifest) != self.manifest:
                raise ValueError('actual tournament plan differs from declared identities/schedule')
            if not self.manifest_checked:
                self.log.append('standard-manifest', {'sha256': plan.digest_file(manifest)})
            self.manifest_checked = True
        elif final and self.manifest_checked:
            raise ValueError('observed manifest disappeared')
        for kind, tail in self.tails.items():
            incoming = tail.poll(final=final)
            if kind == 'results':
                incoming = self.pending_results + incoming
                self.pending_results = []
            blocked = False
            for row in incoming:
                task = self.tasks.get(row.get('taskId'))
                if task is None or not self.manifest_checked:
                    raise ValueError('unbound task in standard output')
                if kind == 'results':
                    attempt = self.attempt_rows.get((row.get('matchId'), row.get('attempt')))
                    if blocked or attempt is None:
                        if final:
                            raise ValueError('completed result has no observed attempt')
                        self.pending_results.append(row); blocked = True
                        continue
                    if attempt['status'] != 'complete' or any(row.get(k) != v for k, v in attempt.items()):
                        raise ValueError('completed result differs from its actual attempt')
                    if row['taskId'] in self.completed or any(row.get(k) != v for k, v in task.items()):
                        raise ValueError('duplicate or misbound completed result')
                    if row['status'] != 'complete':
                        raise ValueError('noncomplete result adopted as a game')
                    self.completed.add(row['taskId'])
                    self.fault_games += any(row['result'].get('faults') or [])
                if kind == 'attempts':
                    key = (row['matchId'], row['attempt'])
                    if key in self.attempts or row['status'] not in ('complete', 'infra_error', 'configuration_error'):
                        raise ValueError('duplicate/unknown attempt record')
                    plan.integer(row['attempt'], 0, 3)
                    self.attempts.add(key); self.attempt_rows[key] = row
                    self.task_attempts[row['taskId']] += 1
                    if self.task_attempts[row['taskId']] > 4:
                        raise ValueError('attempt reservation exceeded')
                    if row['status'] == 'infra_error':
                        self.failures[row['taskId']] += 1
                    self.terminal_error |= (row['status'] == 'configuration_error' or
                                            self.failures[row['taskId']] >= 4 or
                                            (row['status'] == 'infra_error' and row['matchId'].startswith('worker-')))
                if kind == 'executions' and not row.get('completed', False):
                    self.terminal_error = True
                self.rows[kind].append(row)
                self.log.append(kind, {'taskId': row['taskId'], 'standardRowSha256': sha256(plan.canonical(row)).hexdigest()})
        if self.terminal_error:
            return 'framework-error'
        maximum = self.frame['spec']['stop']['maxBotFaultGames']
        if maximum is not None and self.fault_games > maximum:
            return 'bot-fault-limit'
        if len(self.completed) > self.frame['games']:
            raise ValueError('extra completed game')
        return None


def worker(out):
    """Only an already authorized parent-owned experiment can enter this path."""
    frame, digest = plan.verify_frame(out)
    root = plan.safe_path(out); ticket = plan.load_json(root/'run-started.json')
    if os.getppid() != ticket['parentPid'] or digest != ticket['frameSha256']:
        raise ValueError('missing live parent/frame binding')
    if time.time_ns() >= ticket['deadlineEpochNs']:
        raise ValueError('experiment deadline expired before execution')
    result = run_tournament([plan.safe_path(b['frozen']) for b in frame['bots']],
                            [plan.safe_path(m['frozen']) for m in frame['maps']], root/'batch',
                            jobs=frame['spec']['jobs'], pairings=frame['pairs'], seeds=tuple(frame['spec']['seeds']),
                            sandbox='bwrap', fixed_timing=root/'inputs/timing-lock.json')
    atomic_json(root/'standard-return.json', result)
    return 0 if result['status'] == 'complete' else 2


def stop_owned(process):
    """Never signal sidecar PIDs or unrelated processes; keep normal cleanup first."""
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()


def execute(out, expected_sha256, *, enable_experimental=False):
    if not enable_experimental:
        raise ValueError('execution is disabled; explicit --enable-experimental required')
    frame, digest = plan.verify_frame(out)
    if digest != plan.hexadecimal(expected_sha256):
        raise ValueError('external frozen frame SHA-256 mismatch')
    root = plan.safe_path(out)
    started = time.monotonic()
    deadline = started+frame['spec']['caps']['wallSeconds']
    ticket = {'parentPid': os.getpid(), 'frameSha256': digest,
              'deadlineEpochNs': time.time_ns()+frame['spec']['caps']['wallSeconds']*10**9}
    # Permanent marker: failed/spawn-interrupted experiments cannot be executed a second time.
    with (root/'run-started.json').open('x') as stream:
        stream.write(json.dumps(ticket)+'\n'); stream.flush(); os.fsync(stream.fileno())
    with (root/'supervisor.lock').open('xb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = HashLog(root/'run-log.jsonl')
        log.append('start', {'frameSha256': digest, 'implementationSha256': frame['implementationSha256'],
                             'approvalSha256': frame['approvalSha256'], 'caps': frame['spec']['caps'],
                             'reservations': {'games': frame['games'], 'compiles': frame['reservedCompiles'],
                                              'botStarts': 8*frame['games']}})
        observer = Observer(root, frame, log)
        process = None; reason = None; failure = None
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONHASHSEED': '0',
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
        for key in ('TMPDIR', 'TMP', 'TEMP'):
            if key in os.environ:
                env[key] = os.environ[key]
        parent = os.getpid()
        try:
            with (root/'controller.stdout').open('xb') as stdout, (root/'controller.stderr').open('xb') as stderr:
                process = subprocess.Popen([sys.executable, '-B', '-m', 'tools.experiment', '--_worker', out],
                                           cwd=plan.ROOT, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True,
                                           preexec_fn=lambda: parent_death_guard(parent))
                log.append('controller', {'pid': process.pid})
                while True:
                    reason = observer.poll()
                    if reason is not None:
                        break
                    if time.monotonic() >= deadline:
                        reason = 'wall-limit'; break
                    if process.poll() is not None:
                        break
                    time.sleep(.1)
        except BaseException as error:
            failure = type(error).__name__; reason = 'supervisor-error'
        finally:
            if process is not None:
                try:
                    stop_owned(process)
                except BaseException as error:
                    failure = failure or type(error).__name__; reason = reason or 'cleanup-error'
            try:
                final_reason = observer.poll(final=True)
                reason = reason or final_reason
            except Exception as error:
                failure = failure or type(error).__name__; reason = reason or 'damaged-output'
            code = process.returncode if process is not None else None
            if reason is None and (code != 0 or len(observer.completed) != frame['games']):
                reason = 'incomplete-standard-batch'
            status = 'complete' if reason is None else 'stopped'
            terminal = {'status': status, 'reason': reason, 'errorType': failure, 'returncode': code,
                        'completedGames': len(observer.completed), 'plannedGames': frame['games'],
                        'cleanupConfirmed': process is None or process.poll() is not None,
                        'observedAttempts': len(observer.rows['attempts']),
                        'observedFrameworkErrors': sum(r['status'] != 'complete' for r in observer.rows['attempts']),
                        'wallSeconds': time.monotonic()-started}
            log.append('end', terminal)
            result = {**terminal, 'schemaVersion': 1, 'frameSha256': digest,
                      'implementationSha256': frame['implementationSha256'], 'frameworkSha256': frame['frameworkSha256'],
                      'logHeadSha256': log.previous, 'logRows': log.count,
                      'scope': 'non-scoring experiment; completion is not replay semantic verification or tool acceptance',
                      'replaySemanticsVerified': False}
            log.close(); atomic_json(root/'run.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--_worker', help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest='command')
    f = sub.add_parser('freeze'); f.add_argument('manifest'); f.add_argument('--out', required=True); f.add_argument('--approval')
    r = sub.add_parser('run'); r.add_argument('out'); r.add_argument('--frame-sha256', required=True)
    r.add_argument('--enable-experimental', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args._worker is not None:
            return worker(args._worker)
        if args.command == 'freeze':
            frame, digest = plan.freeze(plan.load_json(plan.safe_path(args.manifest)), args.out, approval_path=args.approval)
            print(json.dumps({'out': frame['root'], 'frameSha256': digest, 'plannedGames': frame['games'], 'executed': False}))
            return 0
        if args.command == 'run':
            result = execute(args.out, args.frame_sha256, enable_experimental=args.enable_experimental)
            print(json.dumps(result)); return 0 if result['status'] == 'complete' else 2
        parser.error('freeze or run required')
    except (OSError, ValueError) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}), file=sys.stderr)
        return 2
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
