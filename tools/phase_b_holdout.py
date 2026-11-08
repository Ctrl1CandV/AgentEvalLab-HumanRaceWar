"""Plan/run the frozen v15 holdout, then produce a private, aggregate-only summary.

Use separate plan, run and analyze invocations. All raw artifacts stay private.
The public D6 analyzer remains unchanged: 24 hidden maps are not a 40-map public
acceptance run. Only DESIGN 10.2 items 1/2/4/6/7 determine the holdout gate.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import statistics
import time

from arena.core.journal import records
from arena.tournament import fingerprint, run_tournament
from tools.analyze_zoo import SINGLES, analyze, interval
from tools.generate_hidden_maps import (ROOT, aggregate_catalog, immutable_write,
                                        json_bytes, private_path, register, validate)

BASELINE = ROOT / 'data/phase-a/matrices/zoo-standard-1-final.json'
REFERENCE = ROOT / 'inbox/bench-eval-machine-2026-11-07.json'
BATCH = ROOT / 'private/phase-b/holdout-v15'
ANALYSIS = ROOT / 'private/phase-b/holdout-v15-analysis'
MATRIX_FIELDS = ('bot', 'opponent', 'mapType', 'games', 'maps', 'wins', 'draws', 'losses',
                 'winRate', 'scoreRate', 'winRateCI95', 'scoreRateCI95')


def source_digest(path):
    hashes = []
    for p in sorted(path.rglob('*')):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise ValueError('frozen source contains a link or special file')
        if p.is_file() and '__pycache__' not in p.parts:
            hashes.append([p.relative_to(path).as_posix(), sha256(p.read_bytes()).hexdigest()])
    return sha256(json.dumps(hashes, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def frozen_inputs():
    baseline = json.loads(BASELINE.read_text())
    request = baseline['request']
    sources = [ROOT / 'bots/public' / name for name in baseline['bots']]
    ruleset = json.loads((ROOT / 'rules/standard-1.json').read_text())
    if (fingerprint() != request['framework'] or ruleset != request['ruleset']
            or [source_digest(p) for p in sources] != request['sourceHashes']
            or sha256(REFERENCE.read_bytes()).hexdigest() != request['referenceSha256']):
        raise ValueError('accepted framework/SDK, v15, standard-1 or reference changed; stop')
    return baseline, sources, ruleset


def validate_plan(manifest, catalog, baseline, *, batch=BATCH):
    private_path(batch)
    names = baseline['bots']
    request = manifest['request']
    frozen = baseline['request']
    if manifest['bots'] != names:
        raise ValueError('holdout zoo names/order changed')
    for key in ('jobs', 'pairs', 'seeds', 'sandbox', 'ruleset', 'framework', 'sourceHashes', 'referenceSha256'):
        if request[key] != frozen[key]:
            raise ValueError('holdout differs from frozen run configuration: ' + key)
    maps = sorted([e for e in catalog['maps'] if e['path'].startswith('calibration/')], key=lambda e: e['path'])
    if len(maps) != 24 or request['mapHashes'] != [e['sha256'] for e in maps]:
        raise ValueError('holdout must use all and only the 24 frozen calibration maps')
    if request['maps'] != [str(ROOT / 'private/maps' / e['path']) for e in maps]:
        raise ValueError('holdout map paths changed')
    if request['sources'] != [str(ROOT / 'bots/public' / name) for name in names]:
        raise ValueError('holdout source paths changed')
    expected = []
    pairs = list(combinations(range(10), 2)) + [(names.index('M-balanced'),) * 2]
    if request['pairs'] != [list(pair) for pair in pairs]:
        raise ValueError('holdout pairings changed')
    for a, b in pairs:
        for index, entry in enumerate(maps):
            for swapped in (False, True):
                task = {'players': [b, a] if swapped else [a, b], 'mapIndex': index,
                        'mapName': Path(entry['path']).name, 'mapType': entry['type'],
                        'seeds': [29, 17] if swapped else [17, 29], 'swapped': swapped}
                task['taskId'] = sha256(json.dumps([request, task], sort_keys=True).encode()).hexdigest()
                expected.append(task)
    if len(expected) != 2208 or manifest['tasks'] != expected:
        raise ValueError('holdout task list changed or is not exactly 2208 paired games')


def cluster_fraction(rows, predicate):
    groups = defaultdict(list)
    for row in rows:
        groups[row['mapIndex']].append(float(predicate(row)))
    return interval(tuple(sorted(statistics.fmean(v) for v in groups.values())))


def aggregate(report, catalog, rows):
    """Allowlisted public review copy; no task/map IDs, layouts, paths or seeds."""
    integrity = (report['complete'] and report['expectedGames'] == report['completedGames'] == 2208
                 and report['replayAudit']['allVerified'] and report['botFaultGames'] == 0)
    if not report['complete']:
        return {'schemaVersion': 1, 'decision': 'stop', 'integrity': False,
                'expectedGames': 2208, 'completedGames': report['completedGames'],
                'attemptCounts': report['attemptCounts'], 'statisticsWithheld': 'incomplete task set'}
    lookup = {(r['bot'], r['opponent'], r['mapType']): r for r in report['matrix']}
    types = ('open', 'corridor', 'island', 'maze')
    primary = report['rateChecks']['winRate']
    checks = {'1_eachSingleHasCounter': primary['eachSingleLosesToAnother'],
              '2_balancedOverall70AndEveryType55': primary['balancedOverall70'] and primary['balancedEveryType55'],
              '4_drawRateBelow10': report['observedChecks']['drawRateBelow10'],
              '6_bothEndings20To80': report['observedChecks']['bothEndings20To80'],
              '7_noSingleBeatsBalancedOnAnyType': all(lookup['M-balanced', b, t]['winRate'] >= .5
                                                       for b in SINGLES for t in types)}
    names = report['bots']
    self_rows = [r for r in rows if [names[i] for i in r['players']] == ['M-balanced', 'M-balanced']]
    non_idle = [r for r in rows if r['players'][0] != r['players'][1]
                and 'Z-idle' not in [names[i] for i in r['players']]]
    balanced = {k: report['balancedSelf'][k] for k in ('games', 'maps', 'medianTurns', 'by60Fraction',
                'endReasons', 'baseEndingFraction', 'turnLimitFraction')}
    balanced['baseEndingFractionCI95'] = cluster_fraction(self_rows, lambda r: r['result']['reason'].endswith('base_destroyed'))
    balanced['turnLimitFractionCI95'] = cluster_fraction(self_rows, lambda r: r['result']['reason'].startswith('turn_limit_'))
    return {'schemaVersion': 1, 'scope': 'DESIGN 11.5(8), frozen v15 on calibration; not new public D6 evidence',
            'decision': 'pass' if integrity and all(checks.values()) else 'stop',
            'integrity': integrity, 'checks10_2': checks, 'mapSets': aggregate_catalog(catalog),
            'expectedGames': report['expectedGames'], 'completedGames': report['completedGames'],
            'distinctBotGames': 2160, 'balancedSelfGames': 48,
            'attemptCounts': report['attemptCounts'],
            'botFaultGames': report['botFaultGames'], 'protocolWarnings': report['protocolWarnings'],
            'replayAudit': {'verified': sum(r['verified'] for r in report['replayAudit']['replays']),
                            'allVerified': report['replayAudit']['allVerified']},
            'bootstrap': {k: report['bootstrap'][k] for k in ('unit', 'replicates', 'seed', 'interval', 'limits')},
            'rateDefinitions': {k: report['rateDefinitions'][k] for k in ('winRate', 'scoreRate')},
            'primaryRate': 'winRate; scoreRate (half draws) reported separately, no thresholds changed',
            'counters': {b: list(primary['counters'][b]) for b in SINGLES},
            'balancedSelf': balanced,
            'drawRateExcludingIdleAndSameName': report['drawRateExcludingIdleAndSameName'],
            'drawRateCI95': cluster_fraction(non_idle, lambda r: r['result']['winner'] is None),
            'matrix': [{k: r[k] for k in MATRIX_FIELDS} for r in report['matrix']],
            'recordedUsage': {k: report['recordedUsage'][k] for k in ('botCpuNs', 'matchHarnessCpuNs',
                'replayVerificationCpuNs', 'totalCpuHours', 'limits')},
            'executionFramework': report['executionFramework'],
            'verificationFramework': report['verificationFramework'],
            'baselineReportSha256': sha256(BASELINE.read_bytes()).hexdigest(),
            'rulesSha256': sha256((ROOT / 'rules/standard-1.json').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'run', 'analyze'))
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--out', type=Path, default=ANALYSIS)
    parser.add_argument('--audit-jobs', type=int, default=4)
    args = parser.parse_args()
    batch = private_path(args.batch)
    out = private_path(args.out)
    baseline, sources, ruleset = frozen_inputs()
    catalog = validate(ROOT / 'private/maps')
    start = time.process_time_ns()
    if args.action == 'plan':
        result = run_tournament(sources, [ROOT / 'private/maps/calibration'], batch,
            jobs=6, include_self=['M-balanced'], seeds=(17, 29), reference=REFERENCE,
            sandbox='bwrap', max_tasks=0, ruleset=ruleset)
        validate_plan(json.loads((batch / 'manifest.json').read_text()), catalog, baseline, batch=batch)
    else:
        validate_plan(json.loads((batch / 'manifest.json').read_text()), catalog, baseline, batch=batch)
        if args.action == 'run':
            result = run_tournament(sources, [ROOT / 'private/maps/calibration'], batch,
                jobs=6, include_self=['M-balanced'], seeds=(17, 29), reference=REFERENCE,
                sandbox='bwrap', resume=True, ruleset=ruleset)
        else:
            report = analyze(batch, out, jobs=args.audit_jobs)
            result = aggregate(report, catalog, records(batch / 'results.jsonl'))
            immutable_write(out / 'review-summary.json', json_bytes(result))
    timing = {'action': args.action, 'processCpuNs': time.process_time_ns() - start,
              'scope': 'this controller/analysis process only, excluding children; run includes bench harness',
              'totalCpuHours': None, 'compileCpuHours': None}
    receipts = batch / 'control-usage'
    number = len(list(receipts.glob('*.json')))
    immutable_write(receipts / f'{number:02d}-{args.action}.json', json_bytes(timing))
    result['registry'] = register()
    # Deliberately omit the matrix from console output; the review copy is on disk.
    print(json.dumps({k: v for k, v in result.items() if k != 'matrix'}, indent=2))


if __name__ == '__main__':
    main()
