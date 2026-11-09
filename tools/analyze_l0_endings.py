"""Verify the user's L0 explanation from existing v15 outcomes, not new games.

The old pairwise preflight is retained as historical evidence. This analysis
checks the actual terminal tiebreakers; it does not calibrate a complete ladder.
"""
from collections import Counter
from hashlib import sha256
import json
import statistics
import time

from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes
from tools.review_holdout import archives


def summarize(rows, names):
    selected = [r for r in rows if {names[i] for i in r['players']} == {'Z-miner', 'Z-random'}]
    if not selected: raise ValueError('missing L0 pairing')
    counts = Counter(); reasons = Counter(); by_winner = Counter(); turns = []
    for row in selected:
        result = row['result']; side = [names[i] for i in row['players']].index('Z-miner')
        if row['status'] != 'complete' or any(result['faults']): raise ValueError('faulted/incomplete L0 evidence')
        reason = result['reason']; reasons[reason] += 1; turns.append(result['turns'])
        winner = result['winner']; by_winner['draw' if winner is None else names[row['players'][winner]]] += 1
        if reason.startswith('turn_limit_'):
            values = list(zip(result['scores'], result['deposited'], result['base_hp']))
            expected = None if values[0] == values[1] else int(values[1] > values[0])
            decisive = next((field for field, key in (('score','scores'), ('deposit','deposited'), ('hp','base_hp'))
                             if result[key][0] != result[key][1]), 'draw')
            if expected != winner or reason != 'turn_limit_'+decisive:
                raise ValueError('terminal winner/reason disagrees with the game tiebreak order')
            counts['turnLimitGames'] += 1
            if winner == side and reason == 'turn_limit_deposit' and result['scores'] == [0, 0]:
                counts['minerWinsOnDepositsWithBothTowerScoresZero'] += 1
            if winner == 1-side and reason == 'turn_limit_score' and result['scores'][side] == 0 and result['scores'][1-side] > 0:
                counts['randomWinsOnPositiveTowerScore'] += 1
        counts['baseDestroyedGames'] += reason in ('base_destroyed', 'mutual_base_destroyed')
        counts['bothBasesSurvivedGames'] += all(hp > 0 for hp in result['base_hp'])
    return {'games': len(selected), 'endReasons': dict(reasons), 'winnerCounts': dict(by_winner),
        'turns': {'min': min(turns), 'median': statistics.median(turns), 'max': max(turns)}, **dict(counts)}


def main():
    start = time.process_time_ns(); datasets = []; inputs = {}
    for data in archives():
        if data['revision'] != 'v15': continue
        result = summarize(data['rows'], data['manifest']['bots'])
        if result['games'] != (80 if data['mapSet'] == 'public' else 48): raise ValueError('incomplete archived pairing')
        for row in data['rows']:
            if {data['manifest']['bots'][i] for i in row['players']} == {'Z-miner', 'Z-random'}:
                if sha256((ROOT/row['replay']).read_bytes()).hexdigest() != row['replaySha256']:
                    raise ValueError('previously audited replay changed')
        datasets.append({'mapSet': data['mapSet'], **result})
        inputs[data['mapSet']] = data['report']['inputsSha256']
    report = {'schemaVersion': 1, 'scope': __doc__, 'datasets': datasets, 'newGames': 0,
        'decision': 'retain original v15 L0 bots; internal L0 wins/Elo are diagnostic, not an equal-strength gate, as clarified by the user',
        'limits': 'No claim of equal overall strength. Keep all outcomes and include L0 in whole-ladder diagnostics; no exemption inferred for other levels or other requirements.',
        'usage': {'processCpuNs': time.process_time_ns()-start, 'botCpuNs': 0, 'fullPhaseCpuHours': None,
                  'scope': 'archive/digest and terminal-result aggregation only; no bots, benchmarks, or engine replay'}}
    immutable_write(ROOT/'private/phase-b/l0-resolution/report.json', json_bytes({**report, 'inputsSha256': inputs}))
    immutable_write(ROOT/'data/phase-b/l0-resolution.json', json_bytes(report))
    print(json.dumps({'datasets': datasets, 'usage': report['usage']}, indent=2))


if __name__ == '__main__':
    main()
