"""Preregister and validate the final, unused holdout. Never launch any bot.

Separate plan/build commands enforce registration before generation. Existing
calibration/grading and their catalog remain untouched. Raw layouts, seeds and
per-map comparisons stay private; public output contains set/type/size summaries.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from hashlib import sha256
import json
import math
from pathlib import Path
import secrets
import statistics
import time

from arena.games.outpost.mapgen import GENERATOR_VERSION, TYPES, generate, inspect_layout
from arena.games.outpost.maps import parse_map
from tools.generate_hidden_maps import ROOT, SIZES, immutable_write, json_bytes, private_path, register
from tools.phase_b_holdout import source_digest

DESTINATION = ROOT/'private/holdout-maps'


def specs():
    return [{'path': f'holdout/{kind}-{i:02d}.map', 'type': kind, 'size': size}
            for kind in TYPES for i, size in enumerate(SIZES, 1)]


def existing_assets(root):
    result = []
    for folder in (root/'maps', root/'private/maps'):
        catalog = json.loads((folder/'catalog.json').read_text())
        if catalog['generatorVersion'] != GENERATOR_VERSION:
            raise ValueError('existing generator version differs')
        for entry in catalog['maps']:
            path = folder/entry['path']
            if sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('existing map digest changed')
            result.append({'mapSet': entry['path'].split('/')[0], 'file': path, **entry})
    if Counter(r['mapSet'] for r in result) != {'public': 40, 'scrimmage': 4, 'calibration': 24, 'grading': 24}:
        raise ValueError('existing four map sets incomplete')
    return result


def prerequisites(root):
    margins = json.loads((root/'data/phase-b/margins.json').read_text())
    n2 = json.loads((root/'data/phase-b/maze-hypothesis.json').read_text())
    if (not margins['newStandardActivated'] or not margins['allFailedItemsWithinOneMap']
            or not all(margins['originalCalibrationUnderNewStandard'].values())
            or n2['validation']['transcripts'] != 32 or not n2['validation']['allStdoutAndStateHashesMatch']):
        raise ValueError('N1/N2 prerequisites incomplete or failed')
    baseline = json.loads((root/'data/phase-a/matrices/zoo-standard-1-final.json').read_text())
    if (json.loads((root/'rules/standard-1.json').read_text()) != baseline['request']['ruleset']
            or [source_digest(root/'bots/public'/name) for name in baseline['bots']] != baseline['request']['sourceHashes']):
        raise ValueError('this plan retains standard-1 and all ten v15 bots')
    files = ('maps/catalog.json', 'private/maps/catalog.json', 'data/phase-b/margins.json',
             'data/phase-b/maze-hypothesis.json', 'reports/phase-B-review-analysis.md',
             'arena/games/outpost/mapgen.py', 'arena/games/outpost/maps.py', 'tools/prepare_final_holdout.py')
    return {p: sha256((root/p).read_bytes()).hexdigest() for p in files}


def used_seeds(assets):
    return {s for r in assets for s in (r['requestedSeed'], r['acceptedSeed'],
                                      *(x['seed'] for x in r['rejectedCandidates']))}


def plan(destination=DESTINATION, *, root=ROOT):
    destination = private_path(destination, root)
    if destination.exists(): raise ValueError('holdout plan already exists; never redraw')
    inputs = prerequisites(root)
    old = used_seeds(existing_assets(root))
    entries = [{**e, 'seed': secrets.randbits(64)} for e in specs()]
    seeds = [e['seed'] for e in entries]
    if len(set(seeds)) != 24 or set(seeds) & old:
        raise ValueError('seed collision; stop without replacement')
    value = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION, 'maps': entries, 'inputsSha256': inputs,
             'selection': 'one fresh entropy draw per preregistered slot; unchanged v2 layout-only candidate rejection; duplicate/exhaustion stops',
             'zoo': 'unchanged v15; N2 hypothesis not established, no optional v16 experiment',
             'use': 'layout review only now; exactly one final zoo matrix after all other B work; never tuning or grading'}
    immutable_write(destination/'generation-plan.json', json_bytes(value))
    receipt = register(root=root)  # MUST finish before any generate() call.
    return {'plannedMaps': len(entries), 'registeredBeforeGeneration': True, **receipt}


def check_plan(destination, root):
    path = destination/'generation-plan.json'
    data = path.read_bytes(); value = json.loads(data)
    entry = f'{sha256(data).hexdigest()}  {path.relative_to(root).as_posix()}'
    if entry not in (root/'private/HIDDEN.sha256').read_text().splitlines():
        raise ValueError('plan is not registered with its current bytes; no generation')
    if (value['generatorVersion'] != GENERATOR_VERSION or value['inputsSha256'] != prerequisites(root)
            or [{k: e[k] for k in ('path', 'type', 'size')} for e in value['maps']] != specs()):
        raise ValueError('holdout plan or prerequisites changed')
    seeds = [e['seed'] for e in value['maps']]
    if len(set(seeds)) != 24 or any(type(s) is not int or not 0 <= s < 2**64 for s in seeds):
        raise ValueError('invalid planned seeds')
    if set(seeds) & used_seeds(existing_assets(root)):
        raise ValueError('holdout seed was already used')
    return value


def neighbors(p):
    x, y = p
    return ((x-1, y), (x+1, y), (x, y-1), (x, y+1))


def distances(ground, starts):
    found = {p: 0 for p in starts if p in ground}; queue = deque(found)
    while queue:
        p = queue.popleft()
        for q in neighbors(p):
            if q in ground and q not in found:
                found[q] = found[p]+1; queue.append(q)
    return found


def feature_distance(found, feature):
    return min((found[p] for p in neighbors(feature) if p in found), default=None)


def cut_vertices(ground):
    """Iterative low-link DFS: no recursion limit dependent on maze depth."""
    discovered = {}; low = {}; parent = {}; children = Counter(); cuts = set()
    for start in sorted(ground):
        if start in discovered: continue
        parent[start] = None; discovered[start] = low[start] = len(discovered)
        stack = [(start, iter(q for q in neighbors(start) if q in ground))]
        while stack:
            p, adjacent = stack[-1]
            q = next(adjacent, None)
            if q is None:
                stack.pop(); ancestor = parent[p]
                if ancestor is None:
                    if children[p] > 1: cuts.add(p)
                else:
                    low[ancestor] = min(low[ancestor], low[p])
                    if parent[ancestor] is not None and low[p] >= discovered[ancestor]: cuts.add(ancestor)
            elif q not in discovered:
                parent[q] = p; children[p] += 1
                discovered[q] = low[q] = len(discovered)
                stack.append((q, iter(r for r in neighbors(q) if r in ground)))
            elif q != parent[p]:
                low[p] = min(low[p], discovered[q])
    return cuts


def independent_layout(board):
    """Recompute all layout requirements without generator geometry/check helpers."""
    ground = {(x, y) for y, row in enumerate(board.rows) for x, c in enumerate(row) if c == '.'}
    sites = [(x, y) for y, row in enumerate(board.rows) for x, c in enumerate(row) if c == 'S']
    ores = {(x, y): amount for x, y, amount in board.initial_ore}
    manhattan = lambda a, b: abs(a[0]-b[0])+abs(a[1]-b[1])
    rotate = lambda p: (board.width-1-p[0], board.height-1-p[1])
    symmetric = all(board.rows[board.height-1-y][board.width-1-x] == {'0':'1', '1':'0'}.get(c, c)
                    for y, row in enumerate(board.rows) for x, c in enumerate(row))
    symmetric &= all(ores.get(rotate(p)) == amount for p, amount in ores.items())
    base_walks = [distances(ground, neighbors(base)) for base in board.bases]
    length = feature_distance(base_walks[0], board.bases[1])
    base_path = None if length is None else length+2
    totals = Counter(); counts = Counter(); home_walks = []
    for p, amount in ores.items():
        a, b = (manhattan(p, base) for base in board.bases)
        if 4 <= min(a, b) <= 8:
            owner = int(b < a); zone = f'home{owner}'
            home_walks.append(feature_distance(base_walks[owner], p))
        elif min(a, b) > 8:
            zone = 'center' if abs(a-b) <= 4 else f'middle{int(b < a)}'
        else: zone = 'outside'
        totals[zone] += amount; counts[zone] += 1
    tower_walks = []
    for p in sites:
        found = distances(ground, neighbors(p))
        choices = [feature_distance(found, q) for q in ores if 3 <= manhattan(p, q) <= 5]
        tower_walks.append(min((v for v in choices if v is not None), default=None))
    spawn = [sum(manhattan(p, base) <= 2 for p in ground) for base in board.bases]
    deposits = [*sites, *board.bases]
    separation = min((manhattan(p, q) for p in deposits for q in ores), default=0)
    checks = {'symmetry': symmetric, 'groundConnected': bool(ground) and len(distances(ground, [min(ground)])) == len(ground),
        'basePath': base_path is not None and base_path*5 >= 6*max(board.width, board.height),
        'homeOre': all(totals[f'home{i}'] == 2400 and counts[f'home{i}'] == 6 for i in (0, 1)),
        'homeWalk': len(home_walks) == 12 and all(v is not None and v <= 12 for v in home_walks),
        'middleOre': totals['middle0'] == totals['middle1'] == 6000,
        'centerOre': totals['center'] == 6000 and totals['outside'] == 0,
        'towerSites': 8 <= len(sites) <= 12 and sum(v is not None and v <= 6 for v in tower_walks)*2 >= len(sites),
        'depotOreSeparation': separation >= 3, 'spawnGround': min(spawn) >= 8,
        'resourceAccess': all(any(q in ground for q in neighbors(p)) for p in [*deposits, *ores])}
    cuts = cut_vertices(ground)
    base_cuts = sum(feature_distance(distances(ground-{p}, neighbors(board.bases[0])), board.bases[1]) is None for p in cuts)
    return {'passed': all(checks.values()), 'checks': checks, 'basePath': base_path,
        'normalizedBasePath': base_path/max(board.width, board.height) if base_path is not None else None,
        'singleCellBottlenecks': len(cuts), 'baseRouteBottlenecks': base_cuts,
        'homeOreWalks': home_walks, 'towerOreWalks': tower_walks, 'spawnGround': spawn,
        'towerSites': len(sites), 'oreByZone': dict(totals), 'groundCells': len(ground)}


def distribution(values):
    observed = sorted(v for v in values if v is not None)
    return {'count': len(values), 'observed': len(observed), 'min': min(observed) if observed else None,
        'median': statistics.median(observed) if observed else None, 'max': max(observed) if observed else None,
        'p25': observed[max(0, math.ceil(len(observed)*.25)-1)] if observed else None,
        'p75': observed[max(0, math.ceil(len(observed)*.75)-1)] if observed else None}


def aggregate(rows):
    def summarize(selected):
        return {'maps': len(selected), 'allLayoutsPassed': all(r['metrics']['passed'] for r in selected),
            **{k: distribution([r['metrics'][k] for r in selected]) for k in
                ('basePath', 'normalizedBasePath', 'singleCellBottlenecks', 'baseRouteBottlenecks', 'towerSites', 'groundCells')},
            **{k: distribution([v for r in selected for v in r['metrics'][k]]) for k in ('homeOreWalks', 'towerOreWalks', 'spawnGround')}}
    return {'maps': len(rows), 'definitions': {'singleCellBottlenecks': 'ground-graph articulation cells; removal disconnects some ground, including side branches',
            'baseRouteBottlenecks': 'articulation cells whose removal blocks all paths between any ground neighbors of the two bases',
            'walk': 'between feature-adjacent ground cells; basePath adds the two base endpoints',
            'representation': 'same v2 profile; structural comparison only, not evidence of equal strategic difficulty'},
        'sets': [{ 'mapSet': group, 'types': dict(Counter(r['type'] for r in rows if r['mapSet'] == group)),
            'sizes': dict(Counter(r['size'] for r in rows if r['mapSet'] == group)),
            'mapSetSha256': sha256(''.join(sorted(r['sha256'] for r in rows if r['mapSet'] == group)).encode()).hexdigest(),
            'overall': summarize([r for r in rows if r['mapSet'] == group]),
            'byType': {t: summarize([r for r in rows if (r['mapSet'], r['type']) == (group, t)]) for t in TYPES},
            'bySize': {str(size): summarize([r for r in rows if r['mapSet'] == group and r['size'] == size]) for size in sorted({r['size'] for r in rows if r['mapSet'] == group})}}
            for group in ('public', 'scrimmage', 'calibration', 'grading', 'holdout')]}


def build(destination=DESTINATION, *, root=ROOT):
    destination = private_path(destination, root)
    start = time.process_time_ns(); planned = check_plan(destination, root)
    if (destination/'catalog.json').exists(): raise ValueError('holdout already built; do not regenerate')
    old = existing_assets(root); seen = {r['sha256'] for r in old}; seeds = used_seeds(old)
    entries = []
    for entry in planned['maps']:
        candidate = generate(entry['type'], entry['size'], entry['seed']); metadata = candidate.metadata()
        if metadata['sha256'] in seen or metadata['acceptedSeed'] in seeds:
            raise ValueError('duplicate map/accepted seed; stop without redrawing')
        seen.add(metadata['sha256']); seeds.add(metadata['acceptedSeed'])
        immutable_write(private_path(destination/entry['path'], root), candidate.text.encode())
        entries.append({'path': entry['path'], 'size': entry['size'], **metadata})
    catalog = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION,
        'planSha256': sha256((destination/'generation-plan.json').read_bytes()).hexdigest(), 'maps': entries}
    immutable_write(destination/'catalog.json', json_bytes(catalog))
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*.map')} != {e['path'] for e in planned['maps']}:
        raise ValueError('unplanned map files')
    rows = []
    for entry in old + [{'mapSet': 'holdout', 'file': destination/e['path'], **e} for e in entries]:
        board = parse_map(entry['file'].read_text()); primary = inspect_layout(board); independent = independent_layout(board)
        if (not primary['passed'] or not independent['passed'] or primary['basePath'] != independent['basePath']
                or sorted(r['walk'] for r in primary['homeOreWalks']) != sorted(independent['homeOreWalks'])
                or Counter(r['nearestNearOreWalk'] for r in primary['towerOreWalks']) != Counter(independent['towerOreWalks'])):
            raise ValueError('layout or independent verification failed; stop')
        rows.append({k: entry[k] for k in ('mapSet', 'type', 'size', 'path', 'sha256')} | {'metrics': independent})
    for entry, requested in zip(entries, planned['maps']):
        if generate(entry['type'], entry['size'], requested['seed']).text.encode() != (destination/entry['path']).read_bytes():
            raise ValueError('regeneration mismatch; preserve evidence and stop')
    immutable_write(destination/'layout-rows.json', json_bytes(rows))
    result = {'schemaVersion': 1, 'scope': 'final holdout preparation; no games played', **aggregate(rows),
        'validation': {'preregistered': True, 'holdoutMaps': 24, 'allFiveSetsDisjoint': len(seen) == 116,
            'independentHomeWalkChecks': sum(len(r['metrics']['homeOreWalks']) for r in rows),
            'independentTowerWalkChecks': sum(len(r['metrics']['towerOreWalks']) for r in rows), 'holdoutRegenerationIdentical': True},
        'usage': {'processCpuNs': time.process_time_ns()-start, 'scope': 'generation, two layout checkers, five-set summaries and holdout regeneration; no bots', 'fullPhaseCpuHours': None}}
    if not result['validation']['allFiveSetsDisjoint']: raise ValueError('map sets are not disjoint')
    immutable_write(destination/'summary.json', json_bytes(result))
    immutable_write(root/'data/phase-b/final-holdout-maps.json', json_bytes({**result, 'publication': 'set/type/size aggregates only; not per-map records'}))
    return {'validation': result['validation'], 'usage': result['usage'], **register(root=root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'build'))
    args = parser.parse_args()
    print(json.dumps(plan() if args.action == 'plan' else build(), indent=2))


if __name__ == '__main__':
    main()
