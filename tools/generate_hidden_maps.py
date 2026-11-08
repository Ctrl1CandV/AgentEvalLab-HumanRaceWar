"""Freeze the two Phase-B map sets offline, exclusively under private/.

The plan (including all seeds) is persisted before generation. Only layout
invalidity can advance a seed inside the unchanged v2 generator. Duplicate maps
or exhausted candidates stop the build; they never trigger a fresh random draw.
No bots, compilers or network are used. stdout contains aggregate counts only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import secrets
import time

from arena.games.outpost.mapgen import GENERATOR_VERSION, TYPES, generate, inspect_layout
from arena.games.outpost.maps import parse_map

ROOT = Path(__file__).resolve().parents[1]
SETS = ('calibration', 'grading')
SIZES = (24, 28, 32, 36, 40, 32)


def private_path(path: Path, root: Path = ROOT) -> Path:
    """Reject escapes and symlinks, including in parents of a new destination."""
    path = path.absolute()
    private = root.absolute() / 'private'
    if not path.is_relative_to(private) or '..' in path.parts:
        raise ValueError('hidden artifacts must stay under private/')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('private artifact paths may not contain symbolic links')
    return path


def specs():
    return [{'path': f'{group}/{kind}-{index:02d}.map', 'type': kind, 'size': size}
            for group in SETS for kind in TYPES for index, size in enumerate(SIZES, 1)]


def immutable_write(path: Path, data: bytes):
    if path.is_symlink() or (path.exists() and path.read_bytes() != data):
        raise ValueError('refusing to replace an existing hidden asset')
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def public_hashes(root):
    return {sha256(p.read_bytes()).hexdigest()
            for group in ('public', 'scrimmage') for p in (root / 'maps' / group).glob('*.map')}


def validate(destination: Path, *, root: Path = ROOT):
    destination = private_path(destination, root)
    catalog = json.loads((destination / 'catalog.json').read_text())
    plan = json.loads((destination / 'generation-plan.json').read_text())
    expected = specs()
    if (plan['generatorVersion'] != GENERATOR_VERSION or catalog['generatorVersion'] != GENERATOR_VERSION
            or [{k: e[k] for k in ('path', 'type', 'size')} for e in plan['maps']] != expected
            or [{k: e[k] for k in ('path', 'type', 'size')} for e in catalog['maps']] != expected
            or catalog['planSha256'] != sha256((destination / 'generation-plan.json').read_bytes()).hexdigest()):
        raise ValueError('hidden map plan/catalog changed')
    seen = public_hashes(root)
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*.map')}
    if actual != {e['path'] for e in expected}:
        raise ValueError('hidden map files differ from the frozen plan')
    for entry, planned in zip(catalog['maps'], plan['maps']):
        path = private_path(destination / entry['path'], root)
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        board = parse_map(data.decode())
        metrics = inspect_layout(board)
        if (digest != entry['sha256'] or digest in seen or not metrics['passed']
                or metrics != entry['metrics'] or board.width != entry['size'] or board.height != entry['size']
                or entry['requestedSeed'] != planned['seed']):
            raise ValueError('hidden map failed digest/layout/disjointness validation')
        seen.add(digest)
    return catalog


def build(destination: Path, *, root: Path = ROOT, resume=False):
    destination = private_path(destination, root)
    plan_path = destination / 'generation-plan.json'
    if destination.exists() and not resume:
        raise ValueError('map destination exists; resume the same plan, never redraw it')
    if resume and not plan_path.is_file():
        raise ValueError('no frozen generation plan to resume')
    start = time.process_time_ns()
    if not resume:
        plan = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION,
                'selection': 'preregistered sizes; independent OS-entropy seeds; layout-only rejection; no outcome selection',
                'maps': [{**entry, 'seed': secrets.randbits(64)} for entry in specs()]}
        immutable_write(plan_path, json_bytes(plan))
    plan = json.loads(plan_path.read_text())
    if (plan['generatorVersion'] != GENERATOR_VERSION
            or [{k: e[k] for k in ('path', 'type', 'size')} for e in plan['maps']] != specs()):
        raise ValueError('frozen generation plan changed')
    seen = public_hashes(root)
    entries = []
    for planned in plan['maps']:
        generated = generate(planned['type'], planned['size'], planned['seed'])
        metadata = generated.metadata()
        if metadata['sha256'] in seen:
            raise ValueError('duplicate map: stop without redrawing a seed')
        seen.add(metadata['sha256'])
        immutable_write(private_path(destination / planned['path'], root), generated.text.encode())
        entries.append({'path': planned['path'], 'size': planned['size'], **metadata})
    catalog = {'schemaVersion': 1, 'generatorVersion': GENERATOR_VERSION,
               'planSha256': sha256(plan_path.read_bytes()).hexdigest(),
               'profile': 'unchanged v2; D5 and approved I11; all 48 layouts unique and disjoint from public/scrimmage',
               'maps': entries}
    immutable_write(destination / 'catalog.json', json_bytes(catalog))
    validate(destination, root=root)
    receipt = {'maps': len(entries), 'mapsPerSet': 24, 'mapsPerTypePerSet': 6,
               'rejectedCandidates': sum(len(e['rejectedCandidates']) for e in entries),
               'catalogSha256': sha256((destination / 'catalog.json').read_bytes()).hexdigest(),
               'generationProcessCpuNs': time.process_time_ns() - start,
               'scope': 'generation and full layout/digest validation in this invocation; no bot CPU'}
    # Resuming preserves earlier timing evidence as well as the original maps.
    count = len(list(destination.glob('build-receipt-*.json')))
    immutable_write(destination / f'build-receipt-{count:02d}.json', json_bytes(receipt))
    return receipt


def register(*, root: Path = ROOT):
    """Snapshot every current private regular file, excluding this registry itself.

    Run only at a quiescent checkpoint. Map immutability is checked separately;
    append-only match ledgers acquire new digests at later checkpoints.
    """
    private = private_path(root / 'private', root)
    lines = []
    for path in sorted(private.rglob('*')):
        private_path(path, root)
        if path.name == 'HIDDEN.sha256' and path.parent == private:
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('non-regular private artifact')
        lines.append(f'{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n')
    target = private / 'HIDDEN.sha256'
    temporary = private / '.HIDDEN.sha256.pending'
    with temporary.open('x') as stream:
        stream.writelines(lines)
    temporary.replace(target)
    return {'registeredFiles': len(lines)}


def aggregate_catalog(catalog):
    """Explicit aggregate allowlist: never export seeds, paths or layout metrics."""
    return {group: {'maps': 24, 'types': dict(Counter(e['type'] for e in catalog['maps']
                            if e['path'].startswith(group + '/'))),
                    'mapSetSha256': sha256(''.join(sorted(e['sha256'] for e in catalog['maps']
                            if e['path'].startswith(group + '/'))).encode()).hexdigest()}
            for group in SETS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'private/maps')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    result = build(args.out, resume=args.resume)
    result.update(register())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
