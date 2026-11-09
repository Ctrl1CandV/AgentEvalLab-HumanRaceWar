"""Seal one archived batch's actual timing, without executing bots or benchmarks.

The source batch must be complete and use a single timing epoch. Every replay
header and digest is checked, so a latest benchmark cannot stand in for mixed
historical budgets. The raw timing record remains in runs/ or private/.
"""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from arena.core.benchmark import workload_digest
from arena.core.journal import records
from arena.core.sandbox import ROOT
from arena.core.timing import Calibration, freeze_calibration
from arena.games.outpost import Outpost


def freeze_batch(batch: Path, out: Path):
    batch, out = batch.resolve(), out.resolve()
    if not any(out.is_relative_to(ROOT / p) for p in ('runs', 'private')):
        raise ValueError('raw timing snapshots must remain local')
    if batch.is_relative_to(ROOT / 'private') and not out.is_relative_to(ROOT / 'private'):
        raise ValueError('hidden timing provenance must stay private')
    if out.exists():
        raise ValueError('timing snapshot already exists; never overwrite')
    manifest = json.loads((batch / 'manifest.json').read_text())
    selection = json.loads((batch / 'timing-selection.json').read_text())
    source = Path(selection['resultFile'])
    if source.resolve().is_relative_to(ROOT / 'private') and not out.is_relative_to(ROOT / 'private'):
        raise ValueError('hidden timing report must stay private')
    jobs = manifest['request']['jobs']
    calibration = Calibration.load(source, workload_digest(), jobs=jobs)
    if calibration.sandbox != manifest['request']['sandbox']:
        raise ValueError('baseline timing backend differs from manifest')
    rows = records(batch / 'results.jsonl')
    if (len(rows) != len(manifest['tasks']) or not rows
            or {r['taskId'] for r in rows} != {t['taskId'] for t in manifest['tasks']}):
        raise ValueError('baseline batch incomplete or duplicate tasks')
    content = source.read_bytes() if calibration.locked_budget is not None else None
    for row in rows:
        replay = Path(row['replay'])
        if sha256(replay.read_bytes()).hexdigest() != row['replaySha256']:
            raise ValueError('baseline replay changed')
        with gzip.open(replay, 'rt') as stream:
            header = json.loads(next(stream))
        if content is None:
            content = (json.dumps(freeze_calibration(source, workload_digest(), jobs=jobs,
                base_limits=Outpost().limits, turns=header['params']['TURNS']), sort_keys=True, indent=2) + '\n').encode()
        fixed = Calibration.from_bytes(content, workload_digest(), jobs=jobs)
        assert fixed.locked_budget is not None
        budget = fixed.locked_budget
        timing = header.get('timingCalibration')
        if (not isinstance(timing, dict) or timing.get('reportSha256') != calibration.report_sha256
                or timing.get('jobs') != jobs or tuple(timing.get('cpus', ())) != calibration.cpus
                or header['speedFactor'] != fixed.factor or header['sandbox'] != fixed.sandbox
                or header['params']['TURNS'] != budget['turns']
                or any(header[k] != budget[k] for k in ('limits', 'wallMarginMs', 'cpuHardLimitSeconds'))):
            raise ValueError('mixed/changed baseline timing; cannot silently select an epoch')
    assert content is not None
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as stream:
        stream.write(content)
    return {'headersChecked': len(rows), 'jobs': jobs, 'speedFactor': calibration.factor,
            'timingLockSha256': sha256(content).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(freeze_batch(args.batch, args.out), indent=2))
