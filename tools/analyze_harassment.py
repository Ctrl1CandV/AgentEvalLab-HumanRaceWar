"""Replay-only causal diagnostics for one zoo version; never runs a bot.

Inspect every Z-harass game, not selected wins. Contacts are target-turn samples,
not independent battles; local strength is soldier count within L1 radius four.
"""
import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from hashlib import sha256
import gzip
import json
from pathlib import Path
import statistics
import time

from arena.core.journal import records
from arena.games.outpost import Outpost
from arena.games.outpost.model import distance
from tools.analyze_zoo import relative


def home_walks(state, side):
    home = state.players[side].pos
    d = {}
    queue = deque([(home, 0)])
    while queue:
        (x, y), length = queue.popleft()
        for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if q not in d and state.map.terrain(q) == '.':
                d[q] = length+1
                queue.append((q, length+1))
    return d


def local_soldiers(units, position):
    return [sum(u.owner == side and u.kind == 'S' and distance(u.pos, position) <= 4
                for u in units.values()) for side in (0, 1)]


def inspect(job):
    row, side = job
    start = time.process_time_ns()
    path = Path(row['replay'])
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != row['replaySha256']:
        raise ValueError('replay bytes changed')
    with gzip.open(path, 'rt') as stream:
        header = json.loads(next(stream))
        game = Outpost(header['limits'])
        state = game.new_match(header['map'], header['params'], header['seeds'])
        walks = [home_walks(state, p) for p in (0, 1)]
        deaths, contacts, samples = [], [], []
        for text in stream:
            turn = json.loads(text)
            if turn['type'] != 'turn':
                continue
            units = {uid: replace(u) for uid, u in state.units.items()}
            soldiers = [sum(u.owner == p and u.kind == 'S' for u in units.values()) for p in (0, 1)]
            packets = [game.parse_orders(state, p, r['lines'])[0] for p, r in enumerate(turn['replies'])]
            commands = {o.unit_id: o.op for packet in packets for o in packet.commands if o.unit_id is not None}
            events = game.step(state, packets)
            if game.state_hash(state) != turn['stateHash']:
                raise ValueError('state hash mismatch')
            attacked = set()
            for e in events:
                if e.kind == 'DAMAGE' and e.values[2] == 'U':
                    attacked.add(int(e.values[4]))
                if e.kind == 'DEATH' and e.values[0] == 'U':
                    u = units[int(e.values[2])]
                    if u.kind == 'W':
                        deaths.append({'turn': state.turn, 'owner': u.owner, 'unit': u.id, 'position': u.pos,
                            'homeL1': distance(u.pos, state.players[u.owner].pos), 'homeWalk': walks[u.owner].get(u.pos),
                            'carryLost': u.carry, 'order': commands.get(u.id, 'NONE'),
                            'globalSoldiers': soldiers, 'localSoldiers': local_soldiers(units, u.pos)})
            for uid in sorted(attacked):
                u = units[uid]
                if u.kind == 'S':
                    contacts.append({'turn': state.turn, 'targetOwner': u.owner, 'globalSoldiers': soldiers,
                                     'localSoldiers': local_soldiers(units, u.pos)})
            if state.turn % 25 == 0:
                samples.append({'turn': state.turn, 'workers': [sum(u.owner == p and u.kind == 'W' for u in state.units.values()) for p in (0, 1)],
                    'soldiers': [sum(u.owner == p and u.kind == 'S' for u in state.units.values()) for p in (0, 1)],
                    'deposited': [p.deposited for p in state.players], 'energy': [p.energy for p in state.players]})
    return {'taskId': row['taskId'], 'map': row['mapName'], 'mapType': row['mapType'], 'harassSide': side,
            'replay': row['replay'], 'replaySha256': row['replaySha256'], 'result': row['result'],
            'workerDeaths': deaths, 'soldierContacts': contacts, 'samples': samples,
            'analysisCpuNs': time.process_time_ns()-start}


def median(values):
    return statistics.median(values) if values else None


def summarize(rows):
    deaths = [(r, d) for r in rows for d in r['workerDeaths'] if d['owner'] != r['harassSide']]
    contacts = [(r, c) for r in rows for c in r['soldierContacts']]
    wins = [r for r in rows if r['result']['winner'] == r['harassSide']]
    return {'games': len(rows), 'harassWins': len(wins), 'winReasons': dict(Counter(r['result']['reason'] for r in wins)),
        'victimWorkerDeaths': len(deaths), 'workerDeathHomeL1Median': median([d['homeL1'] for _, d in deaths]),
        'workerDeathHomeWalkMedian': median([d['homeWalk'] for _, d in deaths if d['homeWalk'] is not None]),
        'workerDeathsWithinBaseFireRange2': sum(d['homeL1'] <= 2 for _, d in deaths),
        'workerDeathsWithinHomeL1_8': sum(d['homeL1'] <= 8 for _, d in deaths),
        'workerDeathsWithNoFriendlySoldierWithin4': sum(d['localSoldiers'][1-r['harassSide']] == 0 for r, d in deaths),
        'workerDeathOrders': dict(Counter(d['order'] for _, d in deaths)),
        'soldierTargetTurnContacts': len(contacts),
        'contactGlobalSoldiersHarassMedian': median([c['globalSoldiers'][r['harassSide']] for r, c in contacts]),
        'contactGlobalSoldiersOpponentMedian': median([c['globalSoldiers'][1-r['harassSide']] for r, c in contacts]),
        'contactLocalSoldiersHarassMedian': median([c['localSoldiers'][r['harassSide']] for r, c in contacts]),
        'contactLocalSoldiersOpponentMedian': median([c['localSoldiers'][1-r['harassSide']] for r, c in contacts]),
        'contactGlobalHarassToOpponentRatioMedian': median([c['globalSoldiers'][r['harassSide']]/c['globalSoldiers'][1-r['harassSide']] for r,c in contacts if c['globalSoldiers'][1-r['harassSide']] > 0]),
        'contactLocalHarassToOpponentRatioMedian': median([c['localSoldiers'][r['harassSide']]/c['localSoldiers'][1-r['harassSide']] for r,c in contacts if c['localSoldiers'][1-r['harassSide']] > 0]),
        'contactRatioZeroDenominatorGlobal': sum(c['globalSoldiers'][1-r['harassSide']] == 0 for r,c in contacts),
        'contactRatioZeroDenominatorLocal': sum(c['localSoldiers'][1-r['harassSide']] == 0 for r,c in contacts),
        'contactHarassGlobalAdvantageFraction': sum(c['globalSoldiers'][r['harassSide']] > c['globalSoldiers'][1-r['harassSide']] for r,c in contacts)/len(contacts) if contacts else None,
        'contactHarassLocalAdvantageFraction': sum(c['localSoldiers'][r['harassSide']] > c['localSoldiers'][1-r['harassSide']] for r,c in contacts)/len(contacts) if contacts else None,
        'turnSamples': {str(t): {'gamesPresent': len(s), 'harassSoldiersMedian': median([v['soldiers'][r['harassSide']] for r,v in s]),
                               'opponentSoldiersMedian': median([v['soldiers'][1-r['harassSide']] for r,v in s]),
                               'harassDepositMedian': median([v['deposited'][r['harassSide']] for r,v in s]),
                               'opponentDepositMedian': median([v['deposited'][1-r['harassSide']] for r,v in s])}
            for t in (25,50,75,100,150) if (s := [(r,v) for r in rows for v in r['samples'] if v['turn']==t])}}


def analyze(batch, out, jobs):
    if out.exists(): raise ValueError('refusing to overwrite diagnostics')
    manifest = json.loads((batch/'manifest.json').read_text())
    private = Path(__file__).resolve().parents[1]/'private'
    inputs = [batch, *map(Path, manifest['request']['sources']+manifest['request']['maps'])]
    if any(p.resolve().is_relative_to(private) for p in inputs) and not out.resolve().is_relative_to(private):
        raise ValueError('private inputs require private output')
    names = manifest['bots']; index = names.index('Z-harass')
    rows = records(batch/'results.jsonl')
    selected = [r for r in rows if index in r['players'] and r['players'][0] != r['players'][1]]
    if len(rows) != len(manifest['tasks']) or len({r['taskId'] for r in rows}) != len(rows):
        raise ValueError('incomplete/duplicate matrix')
    groups = defaultdict(list)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for row, result in zip(selected, pool.map(inspect, [(r, r['players'].index(index)) for r in selected])):
            other = names[row['players'][1-result['harassSide']]]
            groups[other].append(result)
    out.mkdir(parents=True)
    report = {'schemaVersion': 1, 'batch': str(batch), 'games': len(selected),
        'scope': 'All harassment games in this immutable matrix; replay-only, hash-checked; contacts are target-turns, not independent battles.',
        'distanceDefinitions': {'homeL1': 'Manhattan distance from base', 'homeWalk': 'shortest terrain walk from base (first adjacent ground costs one)',
                                'localSoldiers': 'pre-attack living soldier counts within Manhattan radius 4 of target; not path-aware'},
        'byOpponent': {}, 'sourceFiles': {}, 'analysisCpuNs': sum(r['analysisCpuNs'] for rs in groups.values() for r in rs)}
    for name, results in sorted(groups.items()):
        # Raw target-turn contacts are large; each opponent gets a separate local
        # file. Public evidence retains per-game summaries and worker deaths.
        raw_path = batch/f'harassment-{name}.json'
        with raw_path.open('x') as stream: json.dump(relative(results), stream)
        public = [{k:v for k,v in r.items() if k != 'soldierContacts'} for r in results]
        path = out/f'{name}.json'
        path.write_text(json.dumps(relative(public), separators=(',', ':'))+'\n')
        report['sourceFiles'][name] = {'raw': relative(str(raw_path)), 'sha256': sha256(raw_path.read_bytes()).hexdigest()}
        report['byOpponent'][name] = {'all': summarize(results), 'byType': {
            t: summarize([r for r in results if r['mapType'] == t]) for t in ('open','corridor','island','maze')}}
    (out/'report.json').write_text(json.dumps(relative(report), indent=2)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch', type=Path); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    a = p.parse_args(); r = analyze(a.batch, a.out, a.jobs)
    print(json.dumps({name:v['all'] for name,v in r['byOpponent'].items()}, indent=2))
