"""D1: preregister 80 selection-only dev maps; no games, tuning or new profile."""
from collections import Counter
from hashlib import sha256
import argparse
import json
from pathlib import Path
import secrets
import time

from arena.games.outpost.mapgen import GENERATOR_VERSION, TYPES, generate, inspect_layout
from arena.games.outpost.maps import parse_map
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path, register
from tools.prepare_final_holdout import existing_assets as first_four_sets
from tools.prepare_final_holdout import independent_layout, distribution, used_seeds

DESTINATION = ROOT/'private/dev-maps'


def specs():
    # First ten within each type: 40-map first stage, already balanced by size.
    return [{'path': f'dev/{kind}-{i:02d}.map', 'type': kind, 'size': size, 'selectionStage': 1 if i <= 10 else 2}
            for kind in TYPES for i, size in enumerate((24, 28, 32, 36, 40)*4, 1)]


def existing_assets(root):
    entries = first_four_sets(root); folder = root/'private/holdout-maps'
    catalog = json.loads((folder/'catalog.json').read_text())
    if catalog['generatorVersion'] != GENERATOR_VERSION or len(catalog['maps']) != 24:
        raise ValueError('final holdout catalog changed')
    for entry in catalog['maps']:
        path = private_path(folder/entry['path'], root)
        if sha256(path.read_bytes()).hexdigest() != entry['sha256']: raise ValueError('existing holdout changed')
        entries.append({'mapSet': 'holdout', 'file': path, **entry})
    if len(entries) != 116 or len({e['sha256'] for e in entries}) != 116:
        raise ValueError('existing map sets incomplete or duplicate')
    return entries


def prerequisites(root):
    frozen = json.loads((root/'private/holdout-maps/generation-plan.json').read_text())['inputsSha256']
    for name in ('arena/games/outpost/mapgen.py', 'arena/games/outpost/maps.py', 'tools/prepare_final_holdout.py'):
        if sha256((root/name).read_bytes()).hexdigest() != frozen[name]:
            raise ValueError('frozen v2 generator/layout checker changed')
    files = ('maps/catalog.json', 'private/maps/catalog.json', 'private/holdout-maps/catalog.json',
             'private/holdout-maps/generation-plan.json',
             'arena/games/outpost/mapgen.py', 'arena/games/outpost/maps.py',
             'tools/prepare_final_holdout.py', 'tools/prepare_dev_maps.py',
             'inbox/2026-11-09-phase-b-mid-review.md')
    return {p: sha256((root/p).read_bytes()).hexdigest() for p in files}


def plan(destination=DESTINATION, *, root=ROOT):
    destination = private_path(destination, root)
    if destination.exists(): raise ValueError('dev plan already exists; never redraw')
    old = used_seeds(existing_assets(root)); inputs = prerequisites(root)
    entries = [{**e, 'seed': secrets.randbits(64)} for e in specs()]
    seeds = [e['seed'] for e in entries]
    collision = len(set(seeds)) != 80 or bool(set(seeds) & old)
    value = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION, 'maps': entries,
             'inputsSha256': inputs, 'initialSeedCollision': collision,
             'use': 'version selection and provisional BT only; never automatic tuning, formal calibration, final holdout or grading',
             'selection': 'one draw per slot; unchanged v2 layout-only rejection; collisions/exhaustion stop, no replacement draw'}
    immutable_write(destination/'generation-plan.json', json_bytes(value))
    receipt = register(root=root)
    if collision: raise ValueError('seed collision retained in registered plan; stop without replacement')
    return {'plannedMaps': 80, 'registeredBeforeGeneration': True, **receipt}


def check_plan(destination, root):
    path = destination/'generation-plan.json'; raw = path.read_bytes(); value = json.loads(raw)
    if f'{sha256(raw).hexdigest()}  {path.relative_to(root).as_posix()}' not in (root/'private/HIDDEN.sha256').read_text().splitlines():
        raise ValueError('plan not registered with current bytes')
    if (value['generatorVersion'] != GENERATOR_VERSION or value['inputsSha256'] != prerequisites(root)
            or [{k: e[k] for k in ('path', 'type', 'size', 'selectionStage')} for e in value['maps']] != specs()):
        raise ValueError('dev plan/prerequisites changed')
    seeds = [e['seed'] for e in value['maps']]
    if (value['initialSeedCollision'] or len(set(seeds)) != 80
            or any(type(s) is not int or not 0 <= s < 2**64 for s in seeds)
            or set(seeds) & used_seeds(existing_assets(root))):
        raise ValueError('invalid/colliding dev seeds')
    return value


def summarize(rows):
    def selected_stats(selected):
        return {'maps': len(selected), 'allLayoutsPassed': all(r['metrics']['passed'] for r in selected),
                **{k: distribution([r['metrics'][k] for r in selected]) for k in
                   ('basePath', 'normalizedBasePath', 'singleCellBottlenecks', 'baseRouteBottlenecks')},
                **{k: distribution([v for r in selected for v in r['metrics'][k]]) for k in ('homeOreWalks', 'towerOreWalks')}}
    return {'maps': len(rows), 'types': dict(Counter(r['type'] for r in rows)),
            'sizes': dict(Counter(r['size'] for r in rows)),
            'mapSetSha256': sha256(''.join(sorted(r['sha256'] for r in rows)).encode()).hexdigest(),
            'overall': selected_stats(rows),
            'byType': {k: selected_stats([r for r in rows if r['type'] == k]) for k in TYPES},
            'bySize': {str(k): selected_stats([r for r in rows if r['size'] == k]) for k in (24, 28, 32, 36, 40)},
            'stageOneTypes': dict(Counter(r['type'] for r in rows if r['selectionStage'] == 1)),
            'stageOneSizes': dict(Counter(r['size'] for r in rows if r['selectionStage'] == 1))}


def build(destination=DESTINATION, *, root=ROOT):
    destination = private_path(destination, root); start = time.process_time_ns()
    planned = check_plan(destination, root)
    if (destination/'catalog.json').exists(): raise ValueError('dev maps already built; never regenerate')
    old = existing_assets(root); seen = {e['sha256'] for e in old}; old_seeds = used_seeds(old)
    planned_seeds = {e['seed'] for e in planned['maps']}; entries = []
    for entry in planned['maps']:
        generated = generate(entry['type'], entry['size'], entry['seed']); metadata = generated.metadata()
        candidate_seeds = used_seeds([metadata])
        if (metadata['sha256'] in seen or candidate_seeds & old_seeds
                or candidate_seeds & (planned_seeds-{entry['seed']})):
            raise ValueError('duplicate map or seed chain; stop without replacement')
        seen.add(metadata['sha256']); old_seeds.update(candidate_seeds)
        immutable_write(private_path(destination/entry['path'], root), generated.text.encode())
        entries.append({k: entry[k] for k in ('path', 'type', 'size', 'selectionStage')} | metadata)
    catalog = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION,
               'planSha256': sha256((destination/'generation-plan.json').read_bytes()).hexdigest(), 'maps': entries}
    immutable_write(destination/'catalog.json', json_bytes(catalog))
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*.map')} != {e['path'] for e in entries}:
        raise ValueError('unplanned dev files')
    rows = []
    for entry, request in zip(entries, planned['maps']):
        raw = (destination/entry['path']).read_bytes(); board = parse_map(raw.decode())
        primary, independent = inspect_layout(board), independent_layout(board)
        if (not primary['passed'] or not independent['passed'] or primary['basePath'] != independent['basePath']
                or sorted(r['walk'] for r in primary['homeOreWalks']) != sorted(independent['homeOreWalks'])
                or Counter(r['nearestNearOreWalk'] for r in primary['towerOreWalks']) != Counter(independent['towerOreWalks'])
                or generate(entry['type'], entry['size'], request['seed']).text.encode() != raw):
            raise ValueError('layout/independent/regeneration check failed; preserve and stop')
        rows.append({k: entry[k] for k in ('path', 'type', 'size', 'selectionStage', 'sha256')} | {'metrics': independent})
    if existing_assets(root) != old: raise ValueError('pre-existing maps changed during dev preparation')
    immutable_write(destination/'layout-rows.json', json_bytes(rows))
    result = {'schemaVersion': 1, 'scope': '80 dev selection maps; zero games; not algorithm tuning', **summarize(rows),
              'validation': {'allSixSetsDisjoint': len(seen) == 196, 'existingMapsUnchanged': 116,
                             'newMapRegenerationIdentical': True,
                             'independentHomeWalkChecks': sum(len(r['metrics']['homeOreWalks']) for r in rows),
                             'independentTowerWalkChecks': sum(len(r['metrics']['towerOreWalks']) for r in rows),
                             'rejectedLayoutCandidates': sum(len(e['rejectedCandidates']) for e in entries), 'newGames': 0},
              'usage': {'processCpuNs': time.process_time_ns()-start, 'fullPhaseCpuHours': None,
                        'scope': 'map generation, primary/independent checks and regeneration; excludes plan/registry; no bots'}}
    if not result['validation']['allSixSetsDisjoint']: raise ValueError('map duplication')
    immutable_write(destination/'summary.json', json_bytes(result))
    immutable_write(root/'data/phase-b/dev-maps.json', json_bytes({**result, 'publication': 'aggregate-only; no map ids, layouts or seeds'}))
    return {'validation': result['validation'], 'usage': result['usage'], **register(root=root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'build')); args = parser.parse_args()
    print(json.dumps(plan() if args.action == 'plan' else build(), indent=2))


if __name__ == '__main__': main()
