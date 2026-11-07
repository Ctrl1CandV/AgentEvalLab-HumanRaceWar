"""Bounded DESIGN 6.4 measurements on the development host, not the evaluation host.

All benchmark bots and C++ compilation go through bwrap. Synthetic engine inputs
are trusted fixtures, not a bot or a balance game. Existing outputs are retained.
Run only after other arena campaigns finish (host/VM background load is external).
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import statistics
import time

from arena.core.benchmark import run_benchmark, workload_digest
from arena.core.journal import records
from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, prepare
from arena.core.timing import Calibration
from arena.games.outpost import Outpost
from arena.games.outpost.model import DIRECTIONS, distance
from arena.match import play
from arena.tournament import fingerprint, run_tournament
from tools.audit_replays import audit

ROOT = Path(__file__).resolve().parents[1]
SPINNER = r'''#include <hrw.hpp>
#include <ctime>
int main() {
    auto setup=hrw::read_setup(); hrw::ready(); hrw::Turn turn;
    while (hrw::read_turn(turn)) {
        const auto begin=std::clock();
        const auto ticks=(CLOCKS_PER_SEC/1000)*setup.limits.at("TURN_CPU_MS");
        while (std::clock()-begin<ticks) {}
        hrw::send({});
    }
}
'''


def distribution(values):
    values = sorted(values)
    return {'n': len(values), 'min': values[0], 'median': statistics.median(values),
            'mean': statistics.fmean(values), 'p95': values[math.ceil(.95*len(values))-1], 'max': values[-1]}


def engine_samples(map_path, out):
    game = Outpost()
    state = game.new_match(map_path.read_text(), {}, [17, 29])
    state.units.clear()
    # Cluster near mines, then around other open cells, to exercise mining,
    # movement conflicts and combat, not only 80 idle entities.
    ground = [(x, y) for y, row in enumerate(state.map.rows) for x, c in enumerate(row) if c == '.']
    ground.sort(key=lambda p: (min(distance(p, o) for o in state.ore), p[1], p[0]))
    for i, p in enumerate(ground[:80]):
        state.add_unit(i % 2, 'W' if i % 4 < 2 else 'S', p)
    assert len(state.units) == 80 and state.map.width == state.map.height == 40
    fixtures = []
    for phase in range(4):
        lines = [[], []]
        for u in state.units.values():
            adjacent_enemy = next((v for v in state.units.values() if v.owner != u.owner and distance(u.pos, v.pos) == 1), None)
            ore = next((p for p in state.ore if distance(p, u.pos) == 1), None)
            if phase == 0 and adjacent_enemy:
                line = f'ATTACK {u.id} {adjacent_enemy.x} {adjacent_enemy.y}'
            elif phase == 1 and u.kind == 'W' and ore:
                line = f'MINE {u.id} {ore[0]} {ore[1]}'
            else:
                line = f'MOVE {u.id} {list(DIRECTIONS)[(u.id//2 + phase) % 4]}'
            lines[u.owner].append(line)
        fixtures.append(lines)
    (out / 'engine-fixture.json').write_text(json.dumps({'map': map_path.read_text(),
        'units': [vars(u) for u in state.units.values()], 'orders': fixtures}, indent=2) + '\n')
    runs = []
    with CpuLease(1) as lease:
        for repeat in range(3):
            cpu, wall = [], []
            for i in range(1030):
                # Rules/map are immutable; Rules contains a non-pickleable mappingproxy.
                current = deepcopy(state, {id(state.rules): state.rules, id(state.map): state.map})
                lines = fixtures[i % len(fixtures)]
                a, b = time.process_time_ns(), time.perf_counter_ns()
                orders = [game.parse_orders(current, p, lines[p])[0] for p in (0, 1)]
                game.step(current, orders)
                game.state_hash(current)
                for p in (0, 1):
                    game.observation(current, p)
                c, d = time.process_time_ns()-a, time.perf_counter_ns()-b
                if i >= 30:
                    cpu.append(c); wall.append(d)
            runs.append({'repeat': repeat, 'cpuNs': cpu, 'wallNs': wall,
                         'cpuDistributionNs': distribution(cpu), 'wallDistributionNs': distribution(wall)})
        cpus = lease.runners
    return {'map': str(map_path.relative_to(ROOT)), 'mapSha256': sha256(map_path.read_bytes()).hexdigest(),
            'unitsBeforeEveryStep': 80, 'width': 40, 'height': 40, 'runnerCpus': cpus,
            'scope': 'parse both players + step + hash + both observations; deepcopy/reset excluded; 30 warmup, 1000 samples x 3',
            'runs': runs, 'allCpuP95Within2ms': all(r['cpuDistributionNs']['p95'] <= 2_000_000 for r in runs),
            'allWallP95Within2ms': all(r['wallDistributionNs']['p95'] <= 2_000_000 for r in runs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    maps = [p for p in sorted((ROOT / 'maps/public').glob('*.map')) if p.read_text().splitlines()[0] == 'MAP 40 40']
    map_path = next(p for p in maps if p.name.startswith('open-'))
    cpu_model = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name'))
    report = {'schemaVersion': 1, 'scope': 'development-host local efficiency; evaluation-host reference unavailable',
              'framework': fingerprint(), 'python': platform.python_version(), 'kernel': platform.release(),
              'machine': {'cpu': cpu_model, 'availableCpus': sorted(os.sched_getaffinity(0)),
                          'memoryBytes': os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')},
              'formalSpeedFactor': None, 'totalCpuHours': None}
    report['engine'] = engine_samples(map_path, out)
    (out / 'engine-report.json').write_text(json.dumps(report, indent=2) + '\n')
    # Bench saves all raw samples. Its local idle reference is NOT a formal one.
    bench = run_benchmark(out / 'bench-single', jobs=1)
    calibration = Calibration.load(Path(bench['resultFile']), workload_digest(), jobs=1)
    sources = []
    for name in ('full-budget-a', 'full-budget-b'):
        source = out / name; source.mkdir(); (source / 'main.cpp').write_text(SPINNER)
        sources.append(source)
    with CpuLease(1) as lease:
        launcher = Bubblewrap(); launcher.cpus = lease.cpus
        prepared = prepare(sources[0], out / 'prepared', launcher, lease.cpus[0])
        if prepared.compile_fault:
            raise RuntimeError(prepared.compile_fault)
    rows = []
    for index in range(3):
        rows.append(play(sources, map_path.read_text(), out / 'single-matches', [17, 29],
                         prepared=[prepared, prepared], calibration=calibration))
    run_tournament(sources, maps[:3], out / 'six-jobs', jobs=6)
    batch_rows = records(out / 'six-jobs/results.jsonl')
    all_rows = rows + batch_rows
    report['replayAudit'] = audit([r['replay'] for r in all_rows if r['status'] == 'complete'])
    groups = {}
    for name, group in (('jobs1', rows), ('jobs6', batch_rows)):
        overheads = [n for r in group for n in r['turnHarnessCpuNs']]
        groups[name] = {'games': len(group), 'complete300NoFault': all(r['status'] == 'complete' and
            r['result']['turns'] == 300 and not any(r['result']['faults']) for r in group),
            'wallSeconds': [r['wallNs']/1e9 for r in group],
            'allGamesWithin35Seconds': all(r['wallNs'] <= 35e9 for r in group),
            'turnHarnessCpuNs': distribution(overheads),
            'allTurnHarnessCpuWithin3ms': all(n <= 3_000_000 for n in overheads),
            'botCpuSeconds': [sum(r['botCpuNs'])/1e9 for r in group],
            'harnessCpuSeconds': sum(r['harnessCpuNs'] for r in group)/1e9,
            'limits': 'Harness CPU includes engine/I/O/recording, excludes bot CPU. Wall includes launch/clone/cleanup, excludes prior cached compilation. Spinner uses at least the rounded calibrated budget; clock granularity and reply parsing may overshoot, charged to BANK. VM/OS scheduling can inflate wall.'}
    report['fullBudgetMatches'] = groups
    report['singleCalibration'] = bench
    report['sixJobSummary'] = json.loads((out / 'six-jobs/summary.json').read_text())
    report['sixJobCalibration'] = json.loads((out / 'six-jobs/timing-selection.json').read_text())
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(groups, indent=2))


if __name__ == '__main__':
    main()
