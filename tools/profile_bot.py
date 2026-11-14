"""Opt-in CPU profile frontend and byte/header-only telemetry reduction.

No source is decoded or imported. Raw CPU samples/exceedances stay local; the
reducer does not run bots or step the engine and is not replay semantic proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path
import sqlite3
import sys

from arena.core.journal import atomic_json
from tools import experiment, experiment_plan as plan


def local_artifact(path, batch):
    p = Path(path)
    if not p.is_absolute():
        raise ValueError('absolute standard artifact path required')
    if p.resolve() != p or not p.is_relative_to(batch) or p.is_symlink():
        raise ValueError('artifact escaped the local batch')
    return p


def statistics(database, label, phase):
    n, maximum = database.execute('SELECT COUNT(*),MAX(cpu) FROM samples WHERE label=? AND phase=?',
                                  (label, phase)).fetchone()
    def quantile(q):
        if not n:
            return None
        value = database.execute('SELECT cpu FROM samples WHERE label=? AND phase=? ORDER BY cpu LIMIT 1 OFFSET ?',
                                 (label, phase, max(0, math.ceil(q*n)-1))).fetchone()[0]
        return value/1e6
    return {'count': n, 'p50Ms': quantile(.5), 'p99Ms': quantile(.99),
            'maxMs': None if maximum is None else maximum/1e6}


def collect(out, *, report_name='profile'):
    frame, digest = plan.verify_frame(out); root = plan.safe_path(out); batch = root/'batch'
    if not isinstance(report_name, str) or not plan.LABEL.fullmatch(report_name) or report_name == 'inputs':
        raise ValueError('safe fresh report name required')
    run = plan.load_json(root/'run.json')
    if run['frameSha256'] != digest or run['implementationSha256'] != frame['implementationSha256']:
        raise ValueError('run/frame identity changed')
    log = experiment.verify_log(root/'run-log.jsonl', expected_head=run['logHeadSha256'], expected_count=run['logRows'])
    if log[0]['payload']['frameSha256'] != digest or log[-1]['payload']['status'] != run['status']:
        raise ValueError('run log does not bind this result')
    if plan.load_json(batch/'manifest.json') != experiment.expected_manifest(frame):
        raise ValueError('standard manifest identity changed')
    tasks = {t['taskId']: t for t in experiment.expected_manifest(frame)['tasks']}
    attempts = experiment.Tail(batch/'attempts.jsonl').poll(final=True)
    results = experiment.Tail(batch/'results.jsonl').poll(final=True)
    executions = experiment.Tail(batch/'executions.jsonl').poll(final=True)
    if len({r['taskId'] for r in results}) != len(results) or len(results) != run['completedGames']:
        raise ValueError('completed result set changed')
    # Rebind every durable row to its externally anchored hash-chain observation.
    for kind, rows in (('attempts', attempts), ('results', results), ('executions', executions)):
        recorded = [r['payload']['standardRowSha256'] for r in log if r['event'] == kind]
        if recorded != [sha256(plan.canonical(r)).hexdigest() for r in rows]:
            raise ValueError('standard journal changed after supervision')
    report = root/report_name
    if report.exists() or report.resolve() != report:
        raise ValueError('fresh local report directory required')
    report.mkdir(mode=0o700)
    database = sqlite3.connect(report/'cpu.sqlite3')
    database.execute('CREATE TABLE samples(label TEXT, phase TEXT, cpu INTEGER)')
    database.execute('CREATE INDEX rank_samples ON samples(label,phase,cpu)')
    cpus = {b['label']: set() for b in frame['bots']}
    faults = Counter(); compile_faults = Counter(); exceedances = Counter()
    seen = set(); missing = 0; partial = 0; verified = 0
    timing = frame['timingHeader']; limits = timing['fixedRuntime']['limits']
    expected_joint = [sha256(f"{b['sha256']}:{frame['sdkSha256'][b['language']]}".encode()).hexdigest()
                      for b in frame['bots']]
    try:
        with (report/'exceedances.jsonl').open('x') as excess:
            for row in attempts:
                task = tasks.get(row['taskId'])
                if task is None:
                    raise ValueError('unknown attempt task')
                work = local_artifact(row['directory'], batch)
                paths = [local_artifact(row['replay'], batch)] if row.get('replay') else list(work.glob('*.hrw.jsonl.gz'))
                if len(paths) > 1:
                    raise ValueError('ambiguous attempt replay')
                if not paths:
                    if row['status'] == 'complete':
                        raise ValueError('complete attempt has no replay')
                    missing += 1; continue
                job = plan.load_json(local_artifact(work.parents[2]/'job.json', batch))
                if (job['taskId'] != task['taskId'] or job['seeds'] != task['seeds']
                        or job['framework'] != frame['frameworkSha256'] or job['sandbox'] != 'bwrap'
                        or job['allocation']['jobs'] != frame['spec']['jobs']
                        or job['allocation']['pool'] != timing['cpus']
                        or job['sources'] != [str(plan.ROOT/frame['bots'][i]['frozen']) for i in task['players']]):
                    raise ValueError('worker allocation/source contract changed')
                path = local_artifact(paths[0], batch)
                if str(path) in seen:
                    raise ValueError('replay reused by multiple attempts')
                seen.add(str(path)); raw_hash = plan.digest_file(path)
                if row.get('replaySha256') and raw_hash != row['replaySha256']:
                    raise ValueError('replay changed')
                totals = [0, 0]; terminal = None; initialization = 0; turns = 0; damaged = False
                try:
                    with gzip.open(path, 'rt') as stream:
                        head = json.loads(next(stream))
                        if (head['type'] != 'header' or head['taskId'] != task['taskId'] or head['sandbox'] != 'bwrap'
                                or head['mapSha256'] != frame['maps'][task['mapIndex']]['sha256']
                                or sha256(head['map'].encode()).hexdigest() != head['mapSha256']
                                or head['seeds'] != task['seeds'] or head['timingCalibration'] != timing
                                or head['limits'] != limits or head['params']['TURNS'] != 300
                                or head['wallMarginMs'] != timing['fixedRuntime']['wallMarginMs']
                                or head['cpuHardLimitSeconds'] != timing['fixedRuntime']['cpuHardLimitSeconds']
                                or len(head['cpus']) != 2 or len(set(head['cpus'])) != 2
                                or any(type(cpu) is not int for cpu in head['cpus'])
                                or head['cpus'] != job['allocation']['bots']
                                or head['runnerCpus'] != job['allocation']['runners']
                                or not set(head['cpus']) <= set(timing['cpus'])
                                or set(head['runnerCpus']) & set(timing['cpus'])):
                            raise ValueError('replay timing/map/CPU identity changed')
                        for side, player in enumerate(task['players']):
                            bot = frame['bots'][player]
                            if (head['bots'][side]['sha256'] != expected_joint[player]
                                    or head['bots'][side]['code'] != bot['label']
                                    or head['bots'][side]['language'] != bot['language']):
                                raise ValueError('replay bot/source/SDK identity changed')
                            cpus[bot['label']].add(head['cpus'][side])
                            if head['compileFaults'][side]: compile_faults[bot['label']] += 1
                        for record in map(json.loads, stream):
                            kind = record['type']
                            if kind in ('init', 'turn', 'fault'):
                                if terminal is not None or len(record['replies']) != 2:
                                    raise ValueError('malformed reply sequence')
                                if kind == 'init':
                                    initialization += 1
                                    if initialization != 1 or turns:
                                        raise ValueError('duplicate or late initialization')
                                else:
                                    if initialization != 1 or record['turn'] != turns+1:
                                        raise ValueError('noncontiguous TURN/fault telemetry')
                                    if kind == 'turn': turns += 1
                                phase = 'INIT' if kind == 'init' else 'TURN'
                                limit = limits['INIT_CPU_MS' if phase == 'INIT' else 'TURN_CPU_MS']*10**6
                                for side, reply in enumerate(record['replies']):
                                    value = reply['cpu_ns']
                                    if type(value) is not int or not 0 <= value <= 2**63-1:
                                        raise ValueError('invalid CPU telemetry')
                                    label = frame['bots'][task['players'][side]]['label']
                                    totals[side] += value
                                    database.execute('INSERT INTO samples VALUES (?,?,?)', (label, phase, value))
                                    if reply.get('fault'): faults[label] += 1
                                    if value > limit:
                                        exceedances[(label, phase)] += 1
                                        excess.write(json.dumps({'taskId': task['taskId'], 'attempt': row['attempt'],
                                            'label': label, 'phase': phase, 'turn': None if phase == 'INIT' else record['turn'],
                                            'cpuNs': value, 'limitNs': limit, 'cpu': head['cpus'][side],
                                            'fault': reply.get('fault')})+'\n')
                            elif kind == 'result':
                                if terminal is not None:
                                    raise ValueError('duplicate terminal record')
                                terminal = record['result']
                except (EOFError, gzip.BadGzipFile, json.JSONDecodeError):
                    if row['status'] == 'complete':
                        raise
                    damaged = True
                if row['status'] == 'complete':
                    if terminal != row['result'] or totals != row['botCpuNs'] or turns != row['result']['turns']:
                        raise ValueError('replay terminal/CPU totals changed')
                    verified += 1
                elif damaged or terminal is None:
                    partial += 1
        database.commit()
        summary = {'schemaVersion': 1, 'status': run['status'], 'frameSha256': digest,
                   'implementationSha256': frame['implementationSha256'], 'declaredJobs': frame['spec']['jobs'],
                   'configuredBotCpuPool': timing['cpus'], 'configuredConcurrencyNotConstantOccupancy': True,
                   'completedGames': len(results), 'attemptsObserved': len(attempts),
                   'completeReplaysHeaderAndCpuChecked': verified, 'partialAttemptReplays': partial,
                   'attemptsWithoutReplay': missing, 'quantiles': 'exact nearest-rank; on-disk SQLite sorting',
                   'labels': {b['label']: {'TURN': statistics(database, b['label'], 'TURN'),
                                          'INIT': statistics(database, b['label'], 'INIT'),
                                          'cpuIds': sorted(cpus[b['label']]), 'faultReplies': faults[b['label']],
                                          'compileFaultGames': compile_faults[b['label']],
                                          'overTurnCpuReplies': exceedances[(b['label'], 'TURN')],
                                          'overInitCpuReplies': exceedances[(b['label'], 'INIT')]} for b in frame['bots']},
                   'overLimitMeaning': 'CPU above the nominal TURN limit may legally consume BANK; it is not itself a timeout.',
                   'replaySemanticsVerified': False,
                   'scope': 'local diagnostic telemetry only; no bot-source interpretation, engine stepping or score'}
        atomic_json(report/'summary.json', summary)
        return summary
    finally:
        database.close()


def build_spec(bot, opponents, maps, timing, jobs, *, identifier='profile', approval_path=None):
    sources = [plan.safe_path(bot), *[plan.safe_path(p) for p in opponents]]
    map_paths = [plan.safe_path(p) for p in maps]
    if not all(plan.public_bot(p) for p in sources[1:]) or not all(plan.public_map(p) for p in map_paths):
        raise ValueError('profile uses public opponents and public/scrimmage maps only')
    if not plan.public_bot(sources[0]):
        if not sources[0].is_relative_to(plan.ROOT/'private/ladder'):
            raise ValueError('profile target outside public/received ladder roots')
        if approval_path is None:
            raise ValueError('nonpublic profiling requires completed tool acceptance first')
    if approval_path is not None:
        plan.approval(approval_path)
    labels = ['target', *[f'ref{i}' for i in range(len(opponents))]]
    count = 2*len(opponents)*len(maps)
    lock = plan.safe_path(timing)
    return {'schemaVersion': 1, 'id': identifier, 'purpose': 'diagnostic' if approval_path else 'acceptance',
            'bots': [{'label': label, 'path': p.relative_to(plan.ROOT).as_posix(), 'sha256': plan.source_digest(p)}
                     for label, p in zip(labels, sources)],
            'maps': [{'path': p.relative_to(plan.ROOT).as_posix(), 'sha256': plan.digest_file(p)} for p in map_paths],
            'pairs': [['target', label] for label in labels[1:]], 'jobs': jobs, 'seeds': [17, 29],
            'timing': {'path': timing, 'sha256': plan.digest_file(lock)},
            'caps': {'games': count, 'compiles': sum(not (p/'main.py').is_file() for p in sources),
                     'botStarts': 8*count, 'wallSeconds': 600},
            'stop': {'onFrameworkError': True, 'maxBotFaultGames': 0}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bot'); parser.add_argument('--opponents', nargs='+'); parser.add_argument('--maps', nargs='+')
    parser.add_argument('--timing'); parser.add_argument('--jobs', type=int, default=1); parser.add_argument('--out')
    parser.add_argument('--approval'); parser.add_argument('--enable-experimental', action='store_true')
    parser.add_argument('--from-experiment'); parser.add_argument('--report-name', default='profile')
    args = parser.parse_args(argv)
    try:
        if args.from_experiment:
            result = collect(args.from_experiment, report_name=args.report_name)
        else:
            if not all((args.bot, args.opponents, args.maps, args.timing, args.out)):
                parser.error('bot/opponents/maps/timing/out required')
            spec = build_spec(args.bot, args.opponents, args.maps, args.timing, args.jobs, approval_path=args.approval)
            frame, digest = plan.freeze(spec, args.out, approval_path=args.approval)
            if not args.enable_experimental:
                print(json.dumps({'out': args.out, 'frameSha256': digest, 'executed': False})); return 0
            experiment.execute(frame['root'], digest, enable_experimental=True)
            result = collect(frame['root'], report_name=args.report_name)
        print(json.dumps(result)); return 0 if result['status'] == 'complete' else 2
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
