"""Replay-only opening diagnostics: all rush/harass and eco/harass pairings.

First contact means a soldier ATTACKing another soldier (not base FIRE).
Economy samples count units after settlement; first-contact strength is before it.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import statistics
import time

from arena.core.journal import records
from arena.core.sandbox import ROOT
from arena.games.outpost import Outpost
from arena.games.outpost.model import distance
from tools.analyze_zoo import relative


def inspect(row, focus):
    path = Path(row['replay'])
    if sha256(path.read_bytes()).hexdigest() != row['replaySha256']:
        raise ValueError('replay digest mismatch')
    result = {'taskId': row['taskId'], 'map': row['mapName'], 'focusSide': focus,
              'result': row['result'], 'firstSoldierContact': None, 'firstFocusSoldier': None,
              'focus24Workers': None, 'firstFocusWorkerDeath': None,
              'soldierAttackCounts': [Counter(), Counter()], 'losses': [Counter(), Counter()],
              'samples': [], 'replay': row['replay'], 'replaySha256': row['replaySha256']}
    with gzip.open(path, 'rt') as stream:
        header = json.loads(next(stream))
        game = Outpost(header['limits'])
        state = game.new_match(header['map'], header['params'], header['seeds'])
        for text in stream:
            rec = json.loads(text)
            if rec['type'] != 'turn': continue
            before = dict(state.units)
            at = {u.pos: u for u in before.values()}
            packets = [game.parse_orders(state, p, r['lines'])[0] for p, r in enumerate(rec['replies'])]
            for p, packet in enumerate(packets):
                for order in packet.commands:
                    if order.op != 'ATTACK' or order.unit_id is None or before[order.unit_id].kind != 'S': continue
                    target = at.get(order.pos)
                    kind = target.kind if target else 'B' if order.pos in state.map.bases else 'T'
                    result['soldierAttackCounts'][p][kind] += 1
                    if result['firstSoldierContact'] is None and target and target.kind == 'S':
                        result['firstSoldierContact'] = {'turn': rec['turn'],
                            'soldiers': [sum(u.owner == q and u.kind == 'S' for u in before.values()) for q in (0, 1)],
                            'local': [sum(u.owner == q and u.kind == 'S' and distance(u.pos, target.pos) <= 4
                                          for u in before.values()) for q in (0, 1)],
                            'units': [asdict(u) for u in before.values()], 'orders': [r['lines'] for r in rec['replies']]}
            events = game.step(state, packets)
            if game.state_hash(state) != rec['stateHash']: raise ValueError('state hash mismatch')
            workers = sum(u.owner == focus and u.kind == 'W' for u in state.units.values())
            if workers >= 24 and result['focus24Workers'] is None: result['focus24Workers'] = state.turn
            for event in events:
                v = event.values
                if event.kind == 'SPAWN' and v[1] == focus and v[2] == 'S' and result['firstFocusSoldier'] is None:
                    result['firstFocusSoldier'] = state.turn
                if event.kind == 'DEATH' and v[0] == 'U':
                    unit = before[int(v[2])]
                    result['losses'][unit.owner][unit.kind] += 1
                    if unit.owner == focus and unit.kind == 'W' and result['firstFocusWorkerDeath'] is None:
                        result['firstFocusWorkerDeath'] = state.turn
            if state.turn in (25, 40, 50, 60, 75, 95, 120):
                result['samples'].append({'turn': state.turn, 'workers': workers,
                    'soldiers': [sum(u.owner == q and u.kind == 'S' for u in state.units.values()) for q in (focus, 1-focus)],
                    'energy': state.players[focus].energy, 'deposited': state.players[focus].deposited})
    return result


def summarize(rows):
    result = {'games': len(rows), 'milestones': {}, 'samples': {}}
    for field in ('firstFocusSoldier', 'focus24Workers', 'firstFocusWorkerDeath'):
        values = [r[field] for r in rows if r[field] is not None]
        result['milestones'][field] = {'observedGames': len(values), 'median': statistics.median(values) if values else None}
    contacts = [r for r in rows if r['firstSoldierContact'] is not None]
    result['firstSoldierContact'] = {'games': len(contacts),
        'medianTurn': statistics.median(r['firstSoldierContact']['turn'] for r in contacts) if contacts else None,
        'focusWorkerKilledBeforeContact': sum(r['firstFocusWorkerDeath'] is not None and
            r['firstFocusWorkerDeath'] < r['firstSoldierContact']['turn'] for r in contacts),
        'globalMedianFocusHarass': [statistics.median(r['firstSoldierContact']['soldiers'][r['focusSide'] if side == 0 else 1-r['focusSide']] for r in contacts) for side in (0, 1)] if contacts else None,
        'localMedianFocusHarass': [statistics.median(r['firstSoldierContact']['local'][r['focusSide'] if side == 0 else 1-r['focusSide']] for r in contacts) for side in (0, 1)] if contacts else None}
    for turn in (25, 40, 50, 60, 75, 95, 120):
        samples = [s for r in rows for s in r['samples'] if s['turn'] == turn]
        if samples:
            result['samples'][str(turn)] = {'gamesPresent': len(samples), **{
                key: statistics.median(s[key] for s in samples) for key in ('workers', 'energy', 'deposited')},
                'soldiersFocusHarass': [statistics.median(s['soldiers'][p] for s in samples) for p in (0, 1)]}
    return result


def analyze(batch, out):
    if out.exists(): raise ValueError('refusing to overwrite diagnostics')
    manifest = json.loads((batch/'manifest.json').read_text()); names = manifest['bots']
    inputs = [batch, *map(Path, manifest['request']['sources']+manifest['request']['maps'])]
    if any(p.resolve().is_relative_to(ROOT/'private') for p in inputs) and not out.resolve().is_relative_to(ROOT/'private'):
        raise ValueError('private inputs require private output')
    completed = records(batch/'results.jsonl')
    if len(completed) != len(manifest['tasks']): raise ValueError('incomplete matrix')
    out.mkdir(parents=True); start = time.process_time_ns()
    report = {'schemaVersion': 1, 'batch': str(batch), 'scope': __doc__, 'byFocus': {}, 'files': {}}
    for focus in ('Z-rush', 'Z-eco'):
        selected = [r for r in completed if {names[p] for p in r['players']} == {focus, 'Z-harass'}]
        rows = [inspect(r, [names[p] for p in r['players']].index(focus)) for r in selected]
        path = out/f'{focus}.json'; path.write_text(json.dumps(relative(rows), separators=(',', ':'))+'\n')
        report['files'][focus] = {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
        report['byFocus'][focus] = summarize(rows)
    report['analysisCpuNs'] = time.process_time_ns()-start
    (out/'report.json').write_text(json.dumps(relative(report), indent=2)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch', type=Path); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); print(json.dumps(analyze(a.batch, a.out)['byFocus'], indent=2))
