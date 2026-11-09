"""N1/N3: read archived evidence only; no games, benchmarks, or map generation."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import time

from arena.core.journal import records
from arena.games.outpost.maps import parse_map
from arena.tournament import fingerprint
from tools.analyze_zoo import SINGLES
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path
from tools.phase_b_damage22 import summary_checks

CONTROL = ROOT / 'private/phase-b/review-2026-11-08'
ARCHIVES = (
    ('public', 'v15', ROOT/'runs/development/zoo-standard-1-final', ROOT/'data/phase-a/matrices/zoo-standard-1-final.json'),
    ('calibration', 'v15', ROOT/'private/phase-b/holdout-v15', ROOT/'private/phase-b/holdout-v15-analysis/report.json'),
    ('public', 'D22', ROOT/'runs/development/phase-b-damage22-public', ROOT/'runs/development/phase-b-damage22-public-analysis/report.json'),
    ('calibration', 'D22', ROOT/'private/phase-b/damage22/calibration', ROOT/'private/phase-b/damage22/calibration-analysis/report.json'),
)
TYPES = ('open', 'corridor', 'island', 'maze')
ALLOWED_RUNTIME_CHANGES = {'arena/core/timing.py', 'arena/tournament.py', 'arena/match.py', 'arena/__main__.py'}


def archives():
    datasets = []
    for group, revision, batch, report_path in ARCHIVES:
        report = json.loads(report_path.read_text())
        if not report['complete'] or not report['replayAudit']['allVerified']:
            raise ValueError('archived analysis incomplete or not replay-audited')
        for name in ('manifest.json', 'results.jsonl', 'attempts.jsonl'):
            if sha256((batch/name).read_bytes()).hexdigest() != report['inputsSha256'][name]:
                raise ValueError('archived input digest changed')
        manifest = json.loads((batch/'manifest.json').read_text())
        if fingerprint(batch/'runtime') != manifest['request']['framework']:
            raise ValueError('archived execution framework changed')
        # R1 legitimately changes scheduling/timing, not the game or SDK. Do not
        # weaken the old freeze check or rewrite its recorded framework digest.
        for base in ('arena', 'sdk'):
            old = {p.relative_to(batch/'runtime').as_posix(): p.read_bytes()
                   for p in (batch/'runtime'/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            now = {p.relative_to(ROOT).as_posix(): p.read_bytes()
                   for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            if set(old) != set(now) or any(old[p] != now[p] for p in old if p not in ALLOWED_RUNTIME_CHANGES):
                raise ValueError('game/SDK changed outside the approved R1 runtime files')
        rows = records(batch/'results.jsonl')
        tasks = {t['taskId']: t for t in manifest['tasks']}
        if len(rows) != len(tasks) or {r['taskId'] for r in rows} != tasks.keys():
            raise ValueError('missing or duplicate archived games')
        for row in rows:
            if row['status'] != 'complete' or any(row[k] != v for k, v in tasks[row['taskId']].items()):
                raise ValueError('archived task identity mismatch')
        metadata = {}
        for index, digest in enumerate(manifest['request']['mapHashes']):
            text = (batch/'runtime'/f'map-{index}.map').read_text()
            if sha256(text.encode()).hexdigest() != digest:
                raise ValueError('archived map changed')
            m = parse_map(text)
            metadata[index] = {'type': next(t['mapType'] for t in tasks.values() if t['mapIndex'] == index),
                               'size': m.width, 'height': m.height}
        datasets.append({'mapSet': group, 'revision': revision, 'batch': batch, 'report': report,
                         'manifest': manifest, 'rows': rows, 'metadata': metadata})
    return datasets


def minimum_changes(values, target, increase):
    """Smallest number of two-seat clusters to replace by both-win/both-not-win.

This is a sensitivity calculation, NOT an instruction to alter evidence or a
probability estimate. Each cluster has capacity 0..2 (draws are not wins).
"""
    if not values or any(type(v) is not int or not 0 <= v <= 2 for v in values):
        raise ValueError('need nonempty two-seat win counts')
    deficit = target-sum(values) if increase else sum(values)-target
    if deficit <= 0:
        return 0
    capacities = sorted((2-v if increase else v for v in values), reverse=True)
    total = 0
    for n, capacity in enumerate(capacities, 1):
        total += capacity
        if total >= deficit:
            return n
    return None


def margin(values, numerator, denominator, *, below=False):
    games = 2*len(values)
    boundary = (numerator*games + denominator-1)//denominator
    if below:
        passed = sum(values) < boundary
        to_pass = minimum_changes(values, boundary-1, False)
        to_fail = minimum_changes(values, boundary, True)
    else:
        passed = sum(values) >= boundary
        to_pass = minimum_changes(values, boundary, True)
        to_fail = minimum_changes(values, boundary-1, False)
    return {'passed': passed, 'minimumMapsToPass': to_pass, 'minimumMapsToFail': to_fail,
            'wins': sum(values), 'games': games, 'maps': len(values),
            'threshold': {'numerator': numerator, 'denominator': denominator, 'comparison': '<' if below else '>='}}


def paired_counts(pairs):
    counts = Counter(''.join(sorted(v)) for v in pairs)
    if any(len(v) != 2 or set(v)-set('WLD') for v in pairs):
        raise ValueError('exactly two outcomes per map required')
    return {'maps': len(pairs), 'twoWins': counts['WW'], 'twoLosses': counts['LL'],
            'splitWins': counts['LW'], 'oneWinOneDraw': counts['DW'],
            'oneLossOneDraw': counts['DL'], 'twoDraws': counts['DD']}


def pair_groups(dataset):
    names = dataset['manifest']['bots']
    groups = defaultdict(lambda: defaultdict(list))
    for row in dataset['rows']:
        a, b = (names[i] for i in row['players'])
        for side, bot, opponent in ((0, a, b), (1, b, a)):
            if opponent not in SINGLES or bot not in (*SINGLES, 'M-balanced') or bot == opponent:
                continue
            winner = row['result']['winner']
            groups[bot, opponent][row['mapIndex']].append('D' if winner is None else 'W' if winner == side else 'L')
    if len(groups) != 49:
        raise ValueError('missing mandatory single/M pairings')
    if any(len(v) != 2 for maps in groups.values() for v in maps.values()):
        raise ValueError('missing swapped seat')
    return groups


def new_holdout_checks(report):
    cells = {(c['bot'], c['opponent'], c['mapType']): c for c in report['matrix']}
    return {'noUniversalSingle': not any(all(cells[b, o, 'all']['winRate'] > .5 for o in SINGLES if o != b) for b in SINGLES),
            'balancedOverall70': all(cells['M-balanced', o, 'all']['winRate'] >= .7 for o in SINGLES),
            'balancedTypeUpper95AtLeast55': all(cells['M-balanced', o, t]['winRateCI95'][1] >= .55 for o in SINGLES for t in TYPES),
            '4_drawRate': report['observedChecks']['drawRateBelow10'],
            '6_endings': report['observedChecks']['bothEndings20To80'],
            '7_typePointEstimateAtLeast50': all(cells['M-balanced', o, t]['winRate'] >= .5 for o in SINGLES for t in TYPES)}


def analyze_margins(datasets):
    result = {'schemaVersion': 1, 'scope': 'N1; four archived v15/D22 datasets, no new games',
        'method': 'minimum existing two-seat map clusters whose outcomes would need to change; no maps/data changed; draws retained and not wins',
        'activationMeaning': 'user-approved discrete sensitivity condition, not proof that strategic defects or sampling error are absent',
        'datasets': [], 'failedItems': []}
    n3 = {'schemaVersion': 1, 'scope': 'N3 baseline v15 only; focus=Z-eco vs Z-harass; all maps retained', 'datasets': []}
    for dataset in datasets:
        group, revision = dataset['mapSet'], dataset['revision']
        output = {'mapSet': group, 'revision': revision, 'pairs': [], 'originalGates': summary_checks(dataset['report'], group)}
        checks = {}
        for (bot, opponent), maps in sorted(pair_groups(dataset).items()):
            parts = defaultdict(dict)
            for index, outcomes in maps.items():
                meta = dataset['metadata'][index]
                for typ, size in (('all', 'all'), (meta['type'], 'all'), ('all', meta['size']), (meta['type'], meta['size'])):
                    parts[typ, size][index] = outcomes
            cells = []
            for (typ, size), by_map in sorted(parts.items(), key=lambda p: str(p[0])):
                cell = {'mapType': typ, 'size': size, **paired_counts(list(by_map.values()))}
                # Size slices describe composition; they are not extra gates.
                if size == 'all' and (bot == 'M-balanced' or typ == 'all'):
                    values = [v.count('W') for v in by_map.values()]
                    threshold = (7, 10) if typ == 'all' else (11, 20)
                    m = margin(values, *threshold) if bot == 'M-balanced' else margin(values, 1, 2, below=True)
                    cell['margin'] = m
                    checks[bot, opponent, typ] = m
                cells.append(cell)
            output['pairs'].append({'bot': bot, 'opponent': opponent, 'counts': cells})
            if bot == 'Z-eco' and opponent == 'Z-harass' and revision == 'v15':
                n3['datasets'].append({'mapSet': group, 'counts': [c for c in cells if c['size'] == 'all']})
        failures = []
        for bot in SINGLES:
            options = [(o, checks[bot, o, 'all']) for o in SINGLES if o != bot]
            if not any(m['passed'] for _, m in options):
                best = min(m['minimumMapsToPass'] for _, m in options)
                failures.append({'condition': '1', 'bot': bot, 'minimumMapsToPass': best,
                    'closestOpponents': [o for o, m in options if m['minimumMapsToPass'] == best]})
        for (bot, opponent, typ), m in checks.items():
            if bot == 'M-balanced' and not m['passed']:
                failures.append({'condition': '2', 'bot': bot, 'opponent': opponent, 'mapType': typ, **m})
        self_maps = defaultdict(list)
        names = dataset['manifest']['bots']
        for row in dataset['rows']:
            if [names[i] for i in row['players']] == ['M-balanced', 'M-balanced']:
                reason = row['result']['reason']
                if reason != 'base_destroyed' and not reason.startswith('turn_limit_'):
                    raise ValueError('unexpected self-play ending')
                self_maps[row['mapIndex']].append(int(reason == 'base_destroyed'))
        if any(len(v) != 2 for v in self_maps.values()):
            raise ValueError('incomplete self-play maps')
        values = [sum(v) for v in self_maps.values()]
        lower = margin(values, 1, 5)
        upper = margin([2-v for v in values], 1, 5)
        output['selfEndingSensitivity'] = {'baseAtLeast20': lower, 'turnLimitAtLeast20': upper}
        if not lower['passed'] or not upper['passed']:
            failures.append({'condition': '6', 'minimumMapsToPass': max(lower['minimumMapsToPass'], upper['minimumMapsToPass'])})
        if not output['originalGates']['integrity'] or not output['originalGates']['conditions']['4'] or not output['originalGates']['conditions']['7']:
            raise ValueError('unhandled integrity/draw/map-dominance failure; stop')
        result['failedItems'].extend({'mapSet': group, 'revision': revision, **f} for f in failures)
        result['datasets'].append(output)
    result['allFailedItemsWithinOneMap'] = all(f['minimumMapsToPass'] <= 1 for f in result['failedItems'])
    result['newStandardActivated'] = result['allFailedItemsWithinOneMap']
    if result['newStandardActivated']:
        original = next(d for d in datasets if (d['mapSet'], d['revision']) == ('calibration', 'v15'))
        result['originalCalibrationUnderNewStandard'] = new_holdout_checks(original['report'])
    result['candidateDecision'] = 'D22 remains rejected; public gates unchanged; no further game parameter tuning'
    return result, n3


def main():
    start = time.process_time_ns()
    private_path(CONTROL)
    if (CONTROL/'margins.json').exists():
        raise ValueError('existing analysis; never overwrite')
    datasets = archives()
    margins, n3 = analyze_margins(datasets)
    usage = {'processCpuNs': time.process_time_ns()-start, 'scope': 'N1/N3 archive validation and aggregation only; no bots/benchmarks', 'fullCpuHours': None}
    margins['usage'] = usage
    immutable_write(CONTROL/'margins.json', json_bytes(margins))
    # Public copies are independently serialized summaries, not raw/renamed ledgers.
    public = {**margins, 'publication': 'aggregate-only review copy; no map/task identifiers'}
    immutable_write(ROOT/'data/phase-b/margins.json', (json.dumps(public, separators=(',', ':'))+'\n').encode())
    immutable_write(ROOT/'data/phase-b/type-counters.json', json_bytes(n3))
    print(json.dumps({'failedItems': margins['failedItems'], 'newStandardActivated': margins['newStandardActivated'],
                      'originalCalibrationUnderNewStandard': margins.get('originalCalibrationUnderNewStandard'), 'usage': usage}, indent=2))


if __name__ == '__main__':
    main()
