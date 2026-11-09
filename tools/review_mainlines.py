"""Mid-review L1-L6: read archived games; no bot, compiler, bench or replay execution.

All pair-specific/raw results stay private. The public output uses an explicit
aggregate allowlist, never revealing a hidden-line/public-opponent relationship.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path
import random
import subprocess
import time

from arena.core.benchmark import workload_digest
from arena.core.machine import machine_info, machine_fingerprint
from arena.core.timing import bind_legacy_calibration
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path
from tools.phase_b_holdout import source_digest
from tools.provisional_bt import fit, bootstrap, percentile

OUT = ROOT/'private/phase-b/mid-review-step0'
LOCK = ROOT/'private/phase-b/ladder-dev01/batch/timing-lock.json'


def archive(folder, expected):
    manifest = json.loads((folder/'manifest.json').read_text())
    rows = [json.loads(line) for line in (folder/'results.jsonl').read_text().splitlines()]
    tasks = {r['taskId']: r for r in manifest['tasks']}
    if len(tasks) != expected or len(rows) != expected or {r['taskId'] for r in rows} != tasks.keys():
        raise ValueError('incomplete/duplicate archived tasks')
    for row in rows:
        if row['status'] != 'complete' or any(row['result']['faults']) or any(row['result']['warnings']):
            raise ValueError('archive contains a fault/warning; report rather than silently omit')
        if any(row[k] != v for k, v in tasks[row['taskId']].items()):
            raise ValueError('archive task identity mismatch')
    for path, digest in zip(manifest['request']['sources'], manifest['request']['sourceHashes']):
        if source_digest(Path(path)) != digest: raise ValueError('archived source changed')
    for path, digest in zip(manifest['request']['maps'], manifest['request']['mapHashes']):
        if sha256(Path(path).read_bytes()).hexdigest() != digest: raise ValueError('archived map changed')
    return manifest, rows


def grouped_scores(rows, player, opponent):
    groups = defaultdict(dict)
    for row in rows:
        if set(row['players']) != {player, opponent}: continue
        side = row['players'].index(player); index = row['mapIndex']
        if side in groups[index]: raise ValueError('duplicate seat')
        winner = row['result']['winner']
        groups[index][side] = 1 if winner is None else 2 if winner == side else 0
    if len(groups) != 24 or any(set(v) != {0, 1} for v in groups.values()):
        raise ValueError('missing map/seat in paired archive')
    return [tuple(groups[k][i] for i in (0, 1)) for k in sorted(groups)]


def pair_counts(groups):
    return {'maps': len(groups), 'bothWin': sum(g == (2, 2) for g in groups),
            'bothLose': sum(g == (0, 0) for g in groups),
            'splitWinLoss': sum(sorted(g) == [0, 2] for g in groups),
            'mapsWithDraw': sum(1 in g for g in groups),
            'scoreRate': sum(sum(g) for g in groups)/(4*len(groups))}


def changes_to_half(groups, strict=False):
    need = 2*len(groups)+int(strict)-sum(sum(g) for g in groups)
    if need <= 0: return 0
    for count, improvement in enumerate(sorted((4-sum(g) for g in groups), reverse=True), 1):
        need -= improvement
        if need <= 0: return count
    raise ValueError('unreachable score threshold')


def paired_interval(groups):
    rng = random.Random(4219); n = len(groups)
    samples = [sum(sum(groups[rng.randrange(n)]) for _ in range(n))/(4*n) for _ in range(4000)]
    return [percentile(samples, .025), percentile(samples, .975)]


def inspect_replay(manifest, row, *, collect=False):
    path = private_path(Path(row['replay']))
    if sha256(path.read_bytes()).hexdigest() != row['replaySha256']: raise ValueError('replay changed')
    values = [[], []]; totals = [0, 0]; turns = 0; terminal = None
    with gzip.open(path, 'rt') as stream:
        head = json.loads(next(stream))
        if (head['taskId'] != row['taskId'] or head['mapSha256'] != manifest['request']['mapHashes'][row['mapIndex']]
                or head['seeds'] != row['seeds'] or head['sandbox'] != 'bwrap'):
            raise ValueError('replay header mismatch')
        for record in map(json.loads, stream):
            if record['type'] in ('init', 'turn'):
                if record['type'] == 'turn':
                    turns += 1
                    if record['turn'] != turns: raise ValueError('noncontiguous turns')
                for side, reply in enumerate(record['replies']):
                    value = reply['cpu_ns']
                    if type(value) is not int or value < 0 or reply['fault'] is not None: raise ValueError('invalid reply CPU/fault')
                    totals[side] += value
                    if collect and record['type'] == 'turn': values[side].append(value)
            if record['type'] == 'result':
                if terminal is not None: raise ValueError('duplicate terminal record')
                terminal = record['result']
    if terminal != row['result'] or turns != row['result']['turns'] or totals != row['botCpuNs']:
        raise ValueError('replay result/turn/CPU totals disagree')
    return values


def seed_swaps(manifest, rows, player):
    selected = [r for r in rows if r['players'] == [player, player]]
    groups = defaultdict(list)
    for row in selected:
        inspect_replay(manifest, row); groups[row['mapIndex']].append(row)
    if len(groups) != 24 or any(len(v) != 2 for v in groups.values()): raise ValueError('missing self-play seed pair')
    changed = 0
    for pair in groups.values():
        a, b = sorted(pair, key=lambda r: r['swapped'])
        if a['seeds'] != b['seeds'][::-1] or len(set(a['seeds'])) != 2: raise ValueError('not joint seed swap')
        changed += a['result']['winner'] != b['result']['winner']
    return {'usesSeed': True, 'archivedGames': len(selected), 'jointSeedSwapMapPairs': len(groups),
            'changedPhysicalSeatWinnerPairs': changed, 'gamesInChangedPairs': 2*changed,
            'singleSideSeedChangeOnlyResult': None,
            'limits': 'both seeds exchanged, compared at the same physical seat; not one-sided seed intervention or extra independent maps'}


def main():
    start = time.process_time_ns(); out = private_path(OUT)
    if (out/'analysis.json').exists(): raise ValueError('analysis already exists; preserve original result')
    paths = [ROOT/f'private/phase-b/ladder-dev{v}/batch' for v in ('02', '03', '04')]
    files = [out/'PLAN.md', LOCK, ROOT/'data/phase-b/mainlines-dev01.json', Path(__file__),
             ROOT/'tools/provisional_bt.py', ROOT/'arena/core/timing.py', ROOT/'arena/core/machine.py']
    files += [p/n for p in paths for n in ('manifest.json', 'results.jsonl')]
    mpath = ROOT/'private/phase-b/holdout-v15'
    files += [mpath/n for n in ('manifest.json', 'results.jsonl')]
    immutable_write(out/'analysis-plan.json', json_bytes({
        'gitHead': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'publicWorktreeDirty': bool(subprocess.check_output(['git', 'status', '--porcelain'])),
        'inputsSha256': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files},
        'newGames': 0, 'bootstrapSamples': 4000, 'bootstrapSeed': 4219,
        'scope': 'requested retrospective archive analysis; plan recorded before this analysis, not before historical games'}))
    manifest, rows = archive(paths[0], 1872); names = manifest['bots']
    if names[:4] != ['A-r02', 'E-r02', 'C-r02', 'M-balanced']: raise ValueError('unexpected retained catalog')
    cells = []
    for player in range(3):
        for opponent in range(3, 13):
            groups = grouped_scores(rows, player, opponent)
            cells.append({'code': names[player], 'opponent': names[opponent], **pair_counts(groups)})
    l1 = {'pairCells': len(cells), 'mapsPerCell': 24, 'bothSeatsAllWinCells': sum(c['bothWin'] == 24 for c in cells),
          'bothSeatsAllLoseCells': sum(c['bothLose'] == 24 for c in cells),
          'cellsWithSplitWinLossMap': sum(c['splitWinLoss'] > 0 for c in cells),
          'cellsWithDrawMap': sum(c['mapsWithDraw'] > 0 for c in cells),
          'nonsaturatedCells': sum(0 < c['scoreRate'] < 1 for c in cells),
          'publication': 'counts only; no hidden-line/opponent associations'}
    eligible = sorted({c['opponent'] for c in cells if 0 < c['scoreRate'] < 1}-{'M-balanced'})
    immutable_write(out/'fixed-pools.json', json_bytes({'selection': 'union of nonzero/nonperfect r02 zoo cells; M mandatory; other retained lines mandatory',
        'pools': {names[i]: ['M-balanced', *[n for n in names[:3] if n != names[i]], *eligible] for i in range(3)},
        'deepseekFirstPool': ['M-balanced', *names[:3], *eligible]}))
    cpu = [[] for _ in range(3)]; appearances = Counter()
    for row in rows:
        values = inspect_replay(manifest, row, collect=True)
        for side, player in enumerate(row['players']):
            if player < 3: cpu[player].extend(values[side]); appearances[player] += 1
    l2 = [{'code': names[i], 'botGameAppearances': appearances[i], 'turnReplies': len(values),
           'p50CpuMs': percentile(values, .5)/1e6, 'p95CpuMs': percentile(values, .95)/1e6,
           'maxCpuMs': max(values)/1e6} for i, values in enumerate(cpu)]
    l3 = [{'code': names[i], **seed_swaps(manifest, rows, i)} for i in range(3)]
    mm, mr = archive(mpath, 2208); mi = mm['bots'].index('M-balanced')
    if mm['request']['sourceHashes'][mi] != manifest['request']['sourceHashes'][3]: raise ValueError('M source differs')
    l3.append({'code': 'M-balanced', **seed_swaps(mm, mr, mi)})
    l4 = []
    for revision, path in zip(('03', '04'), paths[1:]):
        other, data = archive(path, 1872)
        for i, code in enumerate(other['bots'][:3]):
            base = other['bots'].index(names[i]); groups = grouped_scores(data, i, base)
            for row in data:
                if set(row['players']) == {i, base}: inspect_replay(other, row)
            l4.append({'code': code, 'retained': names[i], **pair_counts(groups),
                       'minimumMapChangesTo50Percent': changes_to_half(groups),
                       'minimumMapChangesAbove50Percent': changes_to_half(groups, strict=True),
                       'scoreRateInterval95': paired_interval(groups)})
    raw = LOCK.read_bytes(); evidence = (ROOT/'data/phase-b/mainlines-dev01.json').read_bytes()
    bound = bind_legacy_calibration(raw, evidence, workload_digest(), jobs=6)
    immutable_write(out/'timing-lock-machine-bound.json', json_bytes(bound))
    old_machine = json.loads(json.loads(raw)['benchmarkJson'])['machine']; current = machine_info()
    l5 = {'origin': old_machine, 'current': current, 'fingerprint': machine_fingerprint(current),
          'legacyLogicalCpusEvidence': {'file': 'data/phase-b/mainlines-dev01.json', 'logicalCpus': 20,
                                       'sha256': sha256(evidence).hexdigest()},
          'originLeasedCpuCountIsNotHostCount': len(old_machine['availableCpus']),
          'legacyLockSha256': sha256(raw).hexdigest(), 'boundLockSha256': sha256(json_bytes(bound)).hexdigest(),
          'originBenchmarkBytesUnchanged': True, 'allBudgetsUnchanged': True, 'timingRemeasured': False}
    n = 13; clusters = [[[0.0]*n for _ in range(n)] for _ in range(24)]; games = 0
    for row in rows:
        a, b = row['players']
        if max(a, b) >= n or a == b: continue
        games += 1; winner = row['result']['winner']; target = clusters[row['mapIndex']]
        if winner is None: target[a][b] += .5; target[b][a] += .5
        elif winner == 0: target[a][b] += 1
        else: target[b][a] += 1
    if games != 1584: raise ValueError('unexpected provisional BT sample')
    counts = [[sum(c[i][j] for c in clusters) for j in range(n)] for i in range(n)]
    point = fit(counts, 3); resampled = bootstrap(clusters, 3)
    ratings = [{'code': names[i], 'eloRelativeToM': point['elo'][i], **resampled['ratings'][i]} for i in range(n)]
    l6 = {'games': games, 'maps': 24, 'reference': 'M-balanced=0', 'formalCalibration': False,
          'finiteFullMLE': point['finiteFullMLE'], 'anchorComponentSize': len(point['anchorComponent']),
          'maxScoreResidual': point['maxScoreResidual'], 'ratings': ratings,
          **{k: resampled[k] for k in ('samples', 'seed', 'finiteFullMLEReplicates', 'method')},
          'limits': 'existing development-selected maps; no zoo-only edges; separation explicitly retained; not formal levels or independent validation'}
    public = {'schemaVersion': 1, 'scope': '2026-11-09 mid-review step0 L1-L6, existing archives only',
              'newGames': 0, 'L1': l1, 'L2': l2, 'L3': l3, 'L4': l4, 'L5': l5, 'L6': l6,
              'validation': {'dev02ReplaysReadAndDigestChecked': len(rows), 'directRevisionReplaysChecked': 288,
                             'engineReexecutions': 0, 'botExecutions': 0,
                             'seedUse': 'source inspection, tied to unchanged archived source digests; joint seed-swap result check only'},
              'usage': {'analysisProcessCpuNs': time.process_time_ns()-start, 'botCpuNsThisAnalysis': 0,
                        'fullPhaseCpuHours': None}}
    immutable_write(out/'analysis.json', json_bytes({'public': public, 'L1Cells': cells, 'btCounts': counts,
                    'btClusters': clusters, 'btPoint': point, 'btBootstrap': resampled}))
    immutable_write(ROOT/'data/phase-b/mid-review.json', json_bytes(public))
    print(json.dumps({'completed': ['L1', 'L2', 'L3', 'L4', 'L5', 'L6'], 'newGames': 0,
                      'fullGraphFiniteMLE': point['finiteFullMLE'], 'usage': public['usage']}))


if __name__ == '__main__': main()
