"""Replay-only stationary-unit diagnostics; never executes strategy code."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import json
from pathlib import Path

from arena.games.outpost import Outpost


def inspect(path, player=0):
    with gzip.open(path, 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    header = rows[0]
    game = Outpost(header['limits'])
    state = game.new_match(header['map'], header['params'], header['seeds'])
    still, longest, counts = Counter(), {}, {}
    samples = []
    for row in rows:
        if row['type'] != 'turn':
            continue
        previous = {u.id: u.pos for u in state.units.values()}
        orders = [game.parse_orders(state, p, r['lines'])[0] for p, r in enumerate(row['replies'])]
        commands = {o.unit_id: o for o in orders[player].commands if o.unit_id is not None}
        game.step(state, orders)
        for u in state.units.values():
            if u.owner != player:
                continue
            still[u.id] = still[u.id] + 1 if previous.get(u.id) == u.pos else 0
            command = commands.get(u.id)
            counts.setdefault(u.id, Counter())[command.op if command else 'NONE'] += 1
            if still[u.id] > longest.get(u.id, {}).get('stationaryTurns', -1):
                longest[u.id] = {**asdict(u), 'stationaryTurns': still[u.id], 'endTurn': state.turn}
        if state.turn % 25 == 0:
            samples.append({'turn': state.turn, 'players': [asdict(p) for p in state.players],
                            'units': [asdict(u) for u in state.units.values()],
                            'towers': [asdict(t) for t in state.towers.values()],
                            'orders': row['replies'][player]['lines'], 'board': game.render(state)})
    return {'scope': 'existing replay only; stationary miners/guards need interpretation, not automatically bugs',
            'replay': str(path), 'player': player, 'result': rows[-1],
            'longestStationary': sorted(longest.values(), key=lambda r: -r['stationaryTurns']),
            'commandCounts': counts, 'samples': samples, 'finalBoard': game.render(state)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('replay', type=Path)
    parser.add_argument('--player', type=int, default=0)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.replay, args.player)
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['longestStationary'][:10], indent=2))
