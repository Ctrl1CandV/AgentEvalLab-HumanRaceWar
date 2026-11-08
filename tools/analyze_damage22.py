"""Paired comparison and full-cohort trajectory diagnostics; never execute bots.

All combined/raw artifacts stay private. Compare matched map+seat+seed tasks,
not task IDs (the candidate rules change those). No winner-based selection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
import statistics
import time

from arena.core.journal import records
from arena.core.resources import CpuLease
from arena.games.outpost import Outpost
from arena.games.outpost.model import distance
from tools.analyze_zoo import interval, percentile
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path
from tools.phase_b_damage22 import CONTROL, DESTINATIONS, inputs, summary_checks
from tools.phase_b_holdout import BASELINE, BATCH

FOCI = (('Z-eco', 'Z-rush'), ('Z-harass', 'Z-eco'), ('Z-harass', 'Z-rush'),
        ('M-balanced', 'Z-towers'), ('M-balanced', 'Z-harass'), ('M-balanced', 'M-balanced'))
SAMPLE_TURNS = (25, 40, 60, 95, 120, 200, 300)
OUT = CONTROL / 'paired-analysis'


def identity(row, manifest):
    return (manifest['request']['mapHashes'][row['mapIndex']],
            tuple(manifest['bots'][p] for p in row['players']), tuple(row['seeds']))


def matched_rows(old_rows, new_rows, old_manifest, new_manifest):
    left = {identity(r, old_manifest): r for r in old_rows}
    right = {identity(r, new_manifest): r for r in new_rows}
    if len(left) != len(old_rows) or len(right) != len(new_rows) or left.keys() != right.keys():
        raise ValueError('unmatched/duplicate baseline-candidate games')
    return [(key, left[key], right[key]) for key in sorted(left)]


def paired_stats(entries):
    """(map identity, old W/D/L score, new score); seats are clustered together."""
    groups = defaultdict(list)
    flips = Counter()
    for key, old, new in entries:
        groups[key].append(new - old)
        flips[f'{label(old)}->{label(new)}'] += 1
    deltas = [statistics.fmean(v) for v in groups.values()]
    win_deltas = defaultdict(list)
    for key, old, new in entries:
        win_deltas[key].append(float(new == 1) - float(old == 1))
    return {'games': len(entries), 'maps': len(groups), 'transitions': dict(sorted(flips.items())),
            'baselineWins': sum(o == 1 for _, o, _ in entries), 'candidateWins': sum(n == 1 for _, _, n in entries),
            'baselineDraws': sum(o == .5 for _, o, _ in entries), 'candidateDraws': sum(n == .5 for _, _, n in entries),
            'scoreRateDelta': statistics.fmean(n-o for _, o, n in entries),
            'scoreRateDeltaCI95': interval(tuple(sorted(deltas))),
            'winRateDelta': statistics.fmean(float(n == 1)-float(o == 1) for _, o, n in entries),
            'winRateDeltaCI95': interval(tuple(sorted(statistics.fmean(v) for v in win_deltas.values()))),
            'improvedMaps': sum(d > 0 for d in deltas), 'worsenedMaps': sum(d < 0 for d in deltas),
            'unchangedMaps': sum(d == 0 for d in deltas)}


def label(score):
    return 'W' if score == 1 else 'D' if score == .5 else 'L'


def score(row, side):
    winner = row['result']['winner']
    return .5 if winner is None else float(winner == side)


def matrix_changes(pairs):
    entries = defaultdict(list)
    for (map_hash, names, _), old, new in pairs:
        if old['mapType'] != new['mapType']:
            raise ValueError('map type mismatch')
        if names[0] == names[1]:
            continue
        for side in (0, 1):
            for typ in ('all', old['mapType']):
                entries[names[side], names[1-side], typ].append((map_hash, score(old, side), score(new, side)))
    return [{'bot': b, 'opponent': o, 'mapType': t, **paired_stats(v)} for (b, o, t), v in sorted(entries.items())]


def distribution(values, total):
    present = [v for v in values if v is not None]
    return {'totalGames': total, 'observedGames': len(present),
            'mean': statistics.fmean(present) if present else None,
            'median': statistics.median(present) if present else None,
            'p25': percentile(present, .25), 'p75': percentile(present, .75)}


def inspect_trajectory(job):
    """One complete transcript; missing milestones remain None (not turn 300)."""
    start = time.process_time_ns()
    row, focus = job['row'], job['side']
    p = Path(row['replay'])
    if sha256(p.read_bytes()).hexdigest() != row['replaySha256']:
        raise ValueError('diagnostic replay changed')
    result = {k: job[k] for k in ('group', 'revision', 'focus', 'opponent')}
    result.update(mapType=row['mapType'], mapIndex=row['mapIndex'], taskId=row['taskId'],
                  outcome=label(score(row, focus)), endReason=row['result']['reason'], turns=row['result']['turns'],
                  firstSoldier=[None, None], firstSoldierContact=None, soldiersAtContact=None,
                  firstBaseHit=[None, None], firstBaseReached=[None, None], firstTower=[None, None],
                  soldierAttackCounts=[Counter(), Counter()], casualties=[Counter(), Counter()],
                  soldierMoves=[0, 0], soldierFailedMoves=[0, 0], baseAttackTurns=[0, 0], samples={})
    sides = (focus, 1-focus)
    with gzip.open(p, 'rt') as stream:
        header = json.loads(next(stream))
        if header['params'] != job['rules']:
            raise ValueError('diagnostic PARAM mismatch')
        game = Outpost(header['limits'])
        state = game.new_match(header['map'], header['params'], header['seeds'])
        for text in stream:
            rec = json.loads(text)
            if rec['type'] != 'turn':
                continue
            before = dict(state.units)
            at = {u.pos: u for u in before.values()}
            packets = [game.parse_orders(state, side, reply['lines'])[0] for side, reply in enumerate(rec['replies'])]
            by_line = [{o.line: o for o in packet.commands} for packet in packets]
            contact = False
            for i, side in enumerate(sides):
                if result['firstBaseReached'][i] is None and any(
                        u.owner == side and u.kind == 'S' and distance(u.pos, state.players[1-side].pos) == 1
                        for u in before.values()):
                    result['firstBaseReached'][i] = rec['turn']
                base_attacked = False
                for order in packets[side].commands:
                    unit = before.get(order.unit_id)
                    if unit is None or unit.kind != 'S':
                        continue
                    if order.op == 'MOVE':
                        result['soldierMoves'][i] += 1
                    if order.op != 'ATTACK':
                        continue
                    target = at.get(order.pos)
                    kind = target.kind if target else 'B' if order.pos in state.map.bases else 'T'
                    result['soldierAttackCounts'][i][kind] += 1
                    contact |= kind == 'S'
                    base_attacked |= kind == 'B'
                result['baseAttackTurns'][i] += base_attacked
            if result['firstSoldierContact'] is None and contact:
                result['firstSoldierContact'] = rec['turn']
                result['soldiersAtContact'] = [sum(u.owner == side and u.kind == 'S' for u in before.values()) for side in sides]
            events = game.step(state, packets)
            if game.state_hash(state) != rec['stateHash']:
                raise ValueError('diagnostic state hash mismatch')
            for event in events:
                v = event.values
                if event.kind == 'SPAWN' and v[2] == 'S':
                    i = sides.index(v[1])
                    if result['firstSoldier'][i] is None:
                        result['firstSoldier'][i] = state.turn
                elif event.kind == 'BUILD':
                    i = sides.index(v[2])
                    if result['firstTower'][i] is None:
                        result['firstTower'][i] = state.turn
                elif event.kind == 'DAMAGE' and v[2] == 'B':
                    i = sides.index(v[0])
                    if result['firstBaseHit'][i] is None:
                        result['firstBaseHit'][i] = state.turn
                elif event.kind == 'DEATH' and v[0] == 'U':
                    unit = before[int(v[2])]
                    result['casualties'][sides.index(unit.owner)][unit.kind] += 1
                elif event.kind == 'INVALID' and v[0] == 4:
                    side = event.audience
                    assert side is not None
                    line = v[1]
                    assert isinstance(line, int)
                    order = by_line[side][line]
                    assert order.unit_id is not None
                    if before[order.unit_id].kind == 'S':
                        result['soldierFailedMoves'][sides.index(side)] += 1
            if state.turn in SAMPLE_TURNS:
                result['samples'][str(state.turn)] = [
                    {'workers': sum(u.owner == side and u.kind == 'W' for u in state.units.values()),
                     'soldiers': sum(u.owner == side and u.kind == 'S' for u in state.units.values()),
                     'towers': sum(t.owner == side for t in state.towers.values()),
                     'score': state.players[side].score, 'baseHp': state.players[side].base_hp,
                     'deposited': state.players[side].deposited} for side in sides]
        result['final'] = [{'score': state.players[s].score, 'baseHp': state.players[s].base_hp,
                            'deposited': state.players[s].deposited} for s in sides]
    result['cpuNs'] = time.process_time_ns() - start
    return result


def trajectory_summary(rows):
    n = len(rows)
    result = {'games': n, 'outcomes': dict(Counter(r['outcome'] for r in rows)),
              'endReasons': dict(Counter(r['endReason'] for r in rows)),
              'turns': distribution([r['turns'] for r in rows], n),
              'firstSoldierContact': distribution([r['firstSoldierContact'] for r in rows], n)}
    for field in ('firstSoldier', 'firstBaseHit', 'firstBaseReached', 'firstTower', 'baseAttackTurns',
                  'soldierMoves', 'soldierFailedMoves'):
        result[field] = [distribution([r[field][i] for r in rows], n) for i in (0, 1)]
    result['soldiersAtContact'] = [distribution([
        r['soldiersAtContact'][i] if r['soldiersAtContact'] is not None else None for r in rows], n) for i in (0, 1)]
    for field, kinds in (('soldierAttackCounts', ('W', 'S', 'T', 'B')), ('casualties', ('W', 'S'))):
        result[field] = [{k: distribution([r[field][i][k] for r in rows], n) for k in kinds} for i in (0, 1)]
    result['samples'] = {}
    for turn in SAMPLE_TURNS:
        present = [r['samples'][str(turn)] for r in rows if str(turn) in r['samples']]
        result['samples'][str(turn)] = {'gamesPresent': len(present), 'totalGames': n,
            'sides': [{k: distribution([s[i][k] for s in present], n)
                       for k in ('workers', 'soldiers', 'towers', 'score', 'baseHp', 'deposited')} for i in (0, 1)]}
    result['final'] = [{k: distribution([r['final'][i][k] for r in rows], n)
                        for k in ('score', 'baseHp', 'deposited')} for i in (0, 1)]
    return result


def _pin(queue):
    os.sched_setaffinity(0, {queue.get()})


def main():
    start = time.process_time_ns()
    private_path(OUT)
    if OUT.exists():
        raise ValueError('diagnostics already exist; never overwrite')
    _, candidate, baseline_manifests = inputs()
    baseline = json.loads(BASELINE.read_text())
    baseline_paths = {'public': ROOT / baseline['batch'], 'calibration': BATCH}
    result = {'schemaVersion': 1, 'candidate': 'SOLDIER_DMG 22 only; v15 unchanged',
              'scope': 'paired same-map/seat/seed developmental comparison; not fresh holdout or new baseline games',
              'groups': {}, 'trajectories': []}
    jobs = []
    OUT.mkdir(parents=True)
    for group, path in DESTINATIONS.items():
        new_manifest = json.loads((path / 'manifest.json').read_text())
        report = json.loads((path.with_name(path.name + '-analysis') / 'report.json').read_text())
        if not report['complete'] or not report['replayAudit']['allVerified']:
            raise ValueError('analysis requires complete, audited candidate matrices')
        old_manifest = baseline_manifests[group]
        old_rows = records(baseline_paths[group] / 'results.jsonl')
        new_rows = records(path / 'results.jsonl')
        # Check the actually executed candidate PARAM, map and seed in every header.
        for row in new_rows:
            with gzip.open(row['replay'], 'rt') as stream:
                header = json.loads(next(stream))
            if (header['params'] != candidate or header['seeds'] != row['seeds']
                    or header['mapSha256'] != new_manifest['request']['mapHashes'][row['mapIndex']]):
                raise ValueError('executed input mismatch')
        pairs = matched_rows(old_rows, new_rows, old_manifest, new_manifest)
        changed = sum(o['result'] != n['result'] for _, o, n in pairs)
        result['groups'][group] = {'gates': summary_checks(report, group), 'pairedGames': len(pairs),
            'anyRawResultChangedGames': changed, 'matrixChanges': matrix_changes(pairs)}
        for (map_hash, names, seeds), old, new in pairs:
            for focus, opponent in FOCI:
                if sorted(names) != sorted((focus, opponent)):
                    continue
                for revision, row, rules in (('baseline', old, old_manifest['request']['ruleset']), ('candidate', new, candidate)):
                    jobs.append({'group': group, 'revision': revision, 'focus': focus, 'opponent': opponent,
                                 'side': names.index(focus), 'row': row, 'rules': rules})
    context = multiprocessing.get_context('spawn')
    with CpuLease(4) as lease:
        queue = context.SimpleQueue()
        for cpu in lease.cpus:
            queue.put(cpu)
        with ProcessPoolExecutor(4, mp_context=context, initializer=_pin, initargs=(queue,)) as pool:
            trajectories = list(pool.map(inspect_trajectory, jobs))
        queue.close()
    immutable_write(OUT / 'trajectory-rows.json', json_bytes(trajectories))
    grouped = defaultdict(list)
    for row in trajectories:
        for typ in ('all', row['mapType']):
            grouped[row['group'], row['revision'], row['focus'], row['opponent'], typ].append(row)
    for (group, revision, focus, opponent, typ), rows in sorted(grouped.items()):
        result['trajectories'].append({'mapSet': group, 'revision': revision, 'focus': focus,
            'opponent': opponent, 'mapType': typ, **trajectory_summary(rows)})
    result['usage'] = {'trajectoryReplayCpuNs': sum(r['cpuNs'] for r in trajectories),
                      'trajectoryReplays': len(trajectories), 'controllerCpuNs': time.process_time_ns() - start,
                      'limits': 'transcript-only passes, no bot CPU; not an experiment total; no RUSAGE_CHILDREN added'}
    immutable_write(OUT / 'report.json', json_bytes(result))
    print(json.dumps({'groups': {g: {k:v for k,v in s.items() if k != 'matrixChanges'} for g,s in result['groups'].items()},
                      'usage': result['usage']}, indent=2))


def cohort_metrics(pairs):
    """Exploratory, exhaustive transition cohorts; no selected game is omitted."""
    result = {'games': len(pairs), 'firstSoldierSameGames': sum(a['firstSoldier'] == b['firstSoldier'] for a, b in pairs),
              'firstContactSameGames': sum(a['firstSoldierContact'] == b['firstSoldierContact'] for a, b in pairs),
              'contactArmySameGames': sum(a['soldiersAtContact'] == b['soldiersAtContact'] for a, b in pairs),
              'baseContactLostGames': sum(any(x is not None for x in a['firstBaseHit']) and
                                         all(x is None for x in b['firstBaseHit']) for a, b in pairs),
              'baseContactGainedGames': sum(all(x is None for x in a['firstBaseHit']) and
                                           any(x is not None for x in b['firstBaseHit']) for a, b in pairs),
              'revisions': {}}
    for index, name in enumerate(('baseline', 'candidate')):
        rows = [p[index] for p in pairs]
        result['revisions'][name] = {'anyBaseHitGames': sum(any(x is not None for x in r['firstBaseHit']) for r in rows),
            'focusBaseHitGames': sum(r['firstBaseHit'][0] is not None for r in rows),
            'focusEnemyBaseFinalHp': distribution([r['final'][1]['baseHp'] for r in rows], len(rows)),
            'focusTowerScoreMargin': distribution([r['final'][0]['score']-r['final'][1]['score'] for r in rows], len(rows)),
            'focusSoldierFailedMoves': distribution([r['soldierFailedMoves'][0] for r in rows], len(rows)),
            'focusSoldierMoves': distribution([r['soldierMoves'][0] for r in rows], len(rows)),
            'focusFirstBaseHit': distribution([r['firstBaseHit'][0] for r in rows], len(rows)),
            'turns': distribution([r['turns'] for r in rows], len(rows))}
    return result


def cohort_analysis():
    """Read stored trajectories only; no extra bot execution or engine replay."""
    start = time.process_time_ns()
    target = private_path(OUT / 'cohorts.json')
    if target.exists():
        raise ValueError('cohort report already exists')
    _, _, old_manifests = inputs()
    baseline = json.loads(BASELINE.read_text())
    old_paths = {'public': ROOT / baseline['batch'], 'calibration': BATCH}
    trajectories = json.loads((OUT / 'trajectory-rows.json').read_text())
    lookup = {(r['group'], r['revision'], r['taskId']): r for r in trajectories}
    groups = defaultdict(list)
    for group, path in DESTINATIONS.items():
        new_manifest = json.loads((path / 'manifest.json').read_text())
        pairs = matched_rows(records(old_paths[group] / 'results.jsonl'), records(path / 'results.jsonl'),
                             old_manifests[group], new_manifest)
        for _, old, new in pairs:
            a = lookup.get((group, 'baseline', old['taskId']))
            b = lookup.get((group, 'candidate', new['taskId']))
            if a is None or b is None:
                continue
            for typ in ('all', a['mapType']):
                groups[group, a['focus'], a['opponent'], typ].append((a, b))
    output = {'schemaVersion': 1, 'scope': 'post-outcome exploratory transition cohorts; all predeclared focus games retained', 'groups': []}
    for (group, focus, opponent, typ), pairs in sorted(groups.items()):
        ending = defaultdict(list); outcomes = defaultdict(list)
        for a, b in pairs:
            ending[a['endReason'] + '->' + b['endReason']].append((a, b))
            outcomes[a['outcome'] + '->' + b['outcome']].append((a, b))
        output['groups'].append({'mapSet': group, 'focus': focus, 'opponent': opponent, 'mapType': typ,
            **cohort_metrics(pairs), 'endTransitions': {k: cohort_metrics(v) for k, v in sorted(ending.items())},
            'outcomeTransitions': {k: cohort_metrics(v) for k, v in sorted(outcomes.items())}})
    output['processCpuNs'] = time.process_time_ns() - start
    immutable_write(target, json_bytes(output))
    return {'cohortGroups': len(output['groups']), 'processCpuNs': output['processCpuNs']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohorts', action='store_true', help='supplement stored diagnostics without replaying')
    args = parser.parse_args()
    if args.cohorts:
        print(json.dumps(cohort_analysis(), indent=2))
    else:
        main()
