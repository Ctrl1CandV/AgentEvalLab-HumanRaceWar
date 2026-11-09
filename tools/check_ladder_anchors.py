"""Read-only B setup check for the two named, frozen L0 anchors.

A two-bot Bradley-Terry estimate is a diagnostic, NOT a substitute for the full
ladder fit. A large conflict between named anchors and the within-level target
requires a composition decision; this tool never changes membership or gates.
"""
from collections import defaultdict
import json
import math
import statistics
import time

from tools.analyze_zoo import interval
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes
from tools.review_holdout import CONTROL, archives, paired_counts


def pair_elo(score):
    if not 0 <= score <= 1 or not math.isfinite(score): raise ValueError('score outside [0,1]')
    if score in (0, 1): return {'value': None, 'unbounded': 'positive' if score == 1 else 'negative'}
    return {'value': 400*math.log10(score/(1-score)), 'unbounded': None}


def summarize_pair(pairs):
    counts = paired_counts(pairs)
    scores = [[{'W': 1., 'D': .5, 'L': 0.}[v] for v in pair] for pair in pairs]
    values = [v for pair in scores for v in pair]
    if not values: raise ValueError('missing pair data')
    rate = statistics.fmean(values)
    bounds = interval(tuple(sorted(statistics.fmean(v) for v in scores)))
    return {**counts, 'games': len(values), 'wins': sum(v == 1 for v in values),
            'draws': sum(v == .5 for v in values), 'losses': sum(v == 0 for v in values),
            'scoreRate': rate, 'mapClusterCI95': bounds, 'twoBotEloDifference': pair_elo(rate),
            'transformedCI95': [pair_elo(v) for v in bounds]}


def main():
    start = time.process_time_ns(); results = []; inputs = {}
    for data in archives():
        if data['revision'] != 'v15': continue
        names = data['manifest']['bots']; by_map = defaultdict(list)
        for row in data['rows']:
            players = [names[i] for i in row['players']]
            if set(players) != {'Z-miner', 'Z-random'}: continue
            side = players.index('Z-miner'); winner = row['result']['winner']
            by_map[row['mapIndex']].append('D' if winner is None else 'W' if winner == side else 'L')
        summary = summarize_pair(list(by_map.values()))
        cell = next(c for c in data['report']['matrix'] if (c['bot'], c['opponent'], c['mapType']) == ('Z-miner','Z-random','all'))
        if any(summary[k] != cell[k] for k in ('games','wins','draws','losses','scoreRate')) or summary['mapClusterCI95'] != cell['scoreRateCI95']:
            raise ValueError('independent anchor counts differ from archive')
        results.append({'mapSet': data['mapSet'], **summary})
        inputs[data['mapSet']] = data['report']['inputsSha256']
    report = {'schemaVersion': 1, 'scope': __doc__, 'focus': 'Z-miner vs Z-random, frozen v15; no new games',
        'design': {'namedL0': ['Z-random','Z-miner'], 'withinLevelMaximumEloDifference': 80,
                   'twoBotExpectedScoreAt80': 1/(1+10**(-80/400))},
        'datasets': results, 'fullLadderCalibrationPerformed': False,
        'decision': 'needs composition review before ladder construction; do not relabel pairwise diagnostics as a full ladder gate failure',
        'requestedDecision': 'whether L0 membership may change while preserving frozen v15 zoo and the existing 80 Elo target; no exception applied',
        'usage': {'processCpuNs': time.process_time_ns()-start, 'fullPhaseCpuHours': None, 'scope': 'archive validation and pairwise/map-cluster diagnostic only; no bots'}}
    immutable_write(CONTROL/'ladder-anchor-preflight.json', json_bytes({**report, 'inputsSha256': inputs}))
    immutable_write(ROOT/'data/phase-b/ladder-anchor-preflight.json', json_bytes(report))
    print(json.dumps({'datasets': results, 'decision': report['decision'], 'usage': report['usage']}, indent=2))


if __name__ == '__main__':
    main()
