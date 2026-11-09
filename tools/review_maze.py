"""N2: inspect the 32 archived baseline maze transcripts, never play new games.

A diagnostic-only copy of the public v15 M emits per-turn target counts to stderr.
It receives ONLY observations reconstructed from the archived transcript. All
stdout must match the archived reply before the original orders are replayed.
Compilation and this passive bot probe run in offline bwrap; all raw output is
private. The frozen public bot and all archived results remain untouched.
"""
from collections import defaultdict
import gzip
from hashlib import sha256
import json
import statistics
import time

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, clone_prepared, prepare
from arena.core.transport import Connection, exchange
from arena.games.outpost import Outpost
from tools.analyze_zoo import percentile
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path
from tools.phase_b_holdout import source_digest
from tools.review_holdout import CONTROL, archives

OUT = CONTROL / 'maze-diagnosis'


def instrument(source):
    replacements = (
        ('#include <tuple>', '#include <tuple>\n#include <iostream>'),
        ('        std::vector<std::string> out;', '        std::vector<std::string> out;\n        int reviewBaseTargets=0, reviewTowerTargets=0;'),
        ('                out.push_back(command("ATTACK",u.id,target->pos));',
         '                if (u.kind=="S") { reviewBaseTargets+=target->kind==\'B\'; reviewTowerTargets+=target->kind==\'T\'; }\n'
         '                out.push_back(command("ATTACK",u.id,target->pos));'),
        ('            } else move(u,adjacent(goal));',
         '            } else {\n'
         '                if (u.kind=="S") {\n'
         '                    reviewBaseTargets+=goal==enemy;\n'
         '                    reviewTowerTargets+=std::any_of(targets.begin(),targets.end(),[&](const auto& t){return t.kind==\'T\' && t.pos==goal;});\n'
         '                }\n'
         '                move(u,adjacent(goal));\n'
         '            }'),
        ('        return out;\n    }\n};',
         '        std::cerr << "REVIEW_N2 " << turn.number << " " << ownTowers << " " << enemyTowers << " " << soldiers.size() << " " << reviewBaseTargets << " " << reviewTowerTargets << "\\n";\n'
         '        return out;\n    }\n};'),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError('v15 instrumentation anchor changed')
        source = source.replace(old, new)
    return source


def parse_intents(stderr, turns):
    result = {}
    for line in stderr.decode().splitlines():
        words = line.split()
        if len(words) != 7 or words[0] != 'REVIEW_N2':
            raise ValueError('unexpected/truncated diagnostic stderr')
        turn, own, enemy, soldiers, base, towers = map(int, words[1:])
        if turn in result or min(own, enemy, soldiers, base, towers) < 0 or base+towers > soldiers:
            raise ValueError('invalid/duplicate target counts')
        result[turn] = {'own': own, 'enemy': enemy, 'soldiers': soldiers, 'base': base, 'towers': towers}
    if set(result) != set(range(1, turns+1)):
        raise ValueError('missing or additional target observations')
    return result


def inspect(row, side, bot, launcher, cpu, work):
    replay = ROOT / row['replay']
    if sha256(replay.read_bytes()).hexdigest() != row['replaySha256']:
        raise ValueError('baseline replay changed')
    prepared = clone_prepared(bot, work)
    stats = {'taskId': row['taskId'], 'outcome': 'D' if row['result']['winner'] is None else 'W' if row['result']['winner'] == side else 'L',
             'turns': row['result']['turns'], 'after80Turns': 0, 'towerDeficitTurns': 0,
             'enemyTowersDestroyed': 0, 'enemyTowersDestroyedAfter80': 0, 'peakTowers': [0, 0],
             'baseHitTurns': 0, 'botDiagnosticCpuNs': 0, 'stdoutMatchedTurns': 0}
    tower_counts = {}
    with gzip.open(replay, 'rt') as stream:
        header = json.loads(next(stream))
        game = Outpost(header['limits']); state = game.new_match(header['map'], header['params'], header['seeds'])
        bank = [header['limits']['BANK_MS']*1_000_000]*2
        conn = Connection(prepared, launcher, cpu, header['cpuHardLimitSeconds'])
        try:
            for text in stream:
                rec = json.loads(text)
                if rec['type'] == 'init':
                    reply = exchange([conn], [game.init_message(state, side)], [header['limits']['INIT_CPU_MS']],
                                     [header['limits']['INIT_CPU_MS']+header['wallMarginMs']], b'READY')[0]
                    if reply.fault or reply.lines != rec['replies'][side]['lines']:
                        raise ValueError('diagnostic READY differs from archive')
                    stats['botDiagnosticCpuNs'] += reply.cpu_ns
                    bank = rec['bankNs']
                elif rec['type'] == 'turn':
                    turn = rec['turn']
                    before = [sum(t.owner == p for t in state.towers.values()) for p in (side, 1-side)]
                    tower_counts[turn] = before
                    for p in (0, 1): stats['peakTowers'][p] = max(stats['peakTowers'][p], before[p])
                    if turn > 80:
                        stats['after80Turns'] += 1
                        stats['towerDeficitTurns'] += before[0] < before[1]
                    message = [f'BANK {bank[side]//1_000_000}' if line.startswith('BANK ') else line for line in game.observation(state, side)]
                    allowed = header['limits']['TURN_CPU_MS'] + bank[side]/1_000_000
                    reply = exchange([conn], [message], [allowed], [allowed+header['wallMarginMs']])[0]
                    if reply.fault or reply.lines != rec['replies'][side]['lines']:
                        immutable_write(work/'reply-mismatch.json', json_bytes({'turn': turn, 'reply': reply.record(), 'expected': rec['replies'][side]['lines']}))
                        raise ValueError('diagnostic output differs; do not infer target intent')
                    stats['stdoutMatchedTurns'] += 1
                    stats['botDiagnosticCpuNs'] += reply.cpu_ns
                    packets = [game.parse_orders(state, p, r['lines'])[0] for p, r in enumerate(rec['replies'])]
                    events = game.step(state, packets)  # ORIGINAL recorded orders, never diagnostic choices
                    if game.state_hash(state) != rec['stateHash']:
                        raise ValueError('baseline state hash mismatch')
                    destroyed = sum(e.kind == 'DEATH' and e.values[0] == 'T' and e.values[1] == 1-side for e in events)
                    stats['enemyTowersDestroyed'] += destroyed
                    if turn > 80: stats['enemyTowersDestroyedAfter80'] += destroyed
                    stats['baseHitTurns'] += any(e.kind == 'DAMAGE' and e.values[0] == side and e.values[2] == 'B' for e in events)
                    for p, player in enumerate((side, 1-side)):
                        stats['peakTowers'][p] = max(stats['peakTowers'][p], sum(t.owner == player for t in state.towers.values()))
                    bank = rec['bankNs']
                elif rec['type'] == 'fault':
                    raise ValueError('unexpected faulted baseline')
        finally:
            conn.close()
    intents = parse_intents(conn.stderr, stats['turns'])
    if any([r['own'], r['enemy']] != tower_counts[t] for t, r in intents.items()):
        raise ValueError('diagnostic tower observations differ from engine')
    stats['baseTargetTurnsAfter80'] = sum(r['base'] > 0 for t, r in intents.items() if t > 80)
    stats['towerTargetTurnsAfter80'] = sum(r['towers'] > 0 for t, r in intents.items() if t > 80)
    total = sum(r['soldiers'] for t, r in intents.items() if t > 80)
    stats['baseTargetSoldierFractionAfter80'] = sum(r['base'] for t, r in intents.items() if t > 80)/total if total else None
    for field, count in (('towerDeficitFractionAfter80', 'towerDeficitTurns'), ('baseTargetTurnFractionAfter80', 'baseTargetTurnsAfter80'),
                         ('towerTargetTurnFractionAfter80', 'towerTargetTurnsAfter80')):
        stats[field] = stats[count]/stats['after80Turns'] if stats['after80Turns'] else None
    immutable_write(work/'intents.json', json_bytes(intents))
    return stats


def distribution(values):
    observed = [v for v in values if v is not None]
    return {'games': len(values), 'observedGames': len(observed), 'median': statistics.median(observed) if observed else None,
            'min': min(observed) if observed else None, 'p25': percentile(observed, .25), 'p75': percentile(observed, .75),
            'max': max(observed) if observed else None}


def summarize(rows):
    fields = ('towerDeficitFractionAfter80', 'enemyTowersDestroyed', 'enemyTowersDestroyedAfter80',
              'baseTargetTurnFractionAfter80', 'baseTargetSoldierFractionAfter80', 'towerTargetTurnFractionAfter80', 'baseHitTurns', 'turns')
    return {'games': len(rows), **{k: distribution([r[k] for r in rows]) for k in fields},
            'peakTowers': [distribution([r['peakTowers'][p] for r in rows]) for p in (0, 1)],
            'destroyedAtLeastOneTowerGames': sum(r['enemyTowersDestroyed'] > 0 for r in rows),
            'towerDeficitOverHalfOfPost80Games': sum(r['towerDeficitFractionAfter80'] is not None and r['towerDeficitFractionAfter80'] > .5 for r in rows)}


def main():
    start = time.process_time_ns()
    margins = json.loads((ROOT/'data/phase-b/margins.json').read_text())
    if not margins['allFailedItemsWithinOneMap']:
        raise ValueError('N1 stop condition; no N2 probe')
    private_path(OUT)
    if OUT.exists(): raise ValueError('diagnostics already exist; never overwrite')
    datasets = [d for d in archives() if d['revision'] == 'v15']
    original = ROOT/'bots/public/M-balanced'
    for d in datasets:
        i = d['manifest']['bots'].index('M-balanced')
        if source_digest(original) != d['manifest']['request']['sourceHashes'][i]:
            raise ValueError('public M is not frozen v15')
    source = OUT/'source'
    immutable_write(source/'main.cpp', (original/'main.cpp').read_bytes())
    immutable_write(source/'strategy.hpp', instrument((original/'strategy.hpp').read_text()).encode())
    rows = []
    with CpuLease(1) as lease:
        launcher = Bubblewrap(); launcher.cpus = lease.cpus
        bot = prepare(source, OUT/'prepared', launcher, lease.cpus[0])
        if bot.compile_fault: raise ValueError('diagnostic compilation failed; evidence retained')
        for d in datasets:
            names = d['manifest']['bots']
            selected = [r for r in d['rows'] if r['mapType'] == 'maze' and {names[i] for i in r['players']} == {'M-balanced', 'Z-towers'}]
            if len(selected) != (20 if d['mapSet'] == 'public' else 12): raise ValueError('wrong baseline diagnostic cohort')
            for row in selected:
                side = [names[i] for i in row['players']].index('M-balanced')
                stats = inspect(row, side, bot, launcher, lease.cpus[0], OUT/'probes'/row['taskId'])
                rows.append({'mapSet': d['mapSet'], **stats})
    immutable_write(OUT/'rows.json', json_bytes(rows))
    groups = defaultdict(list)
    for row in rows:
        for outcome in ('all', row['outcome']): groups[row['mapSet'], outcome].append(row)
    summary = {'schemaVersion': 1, 'scope': 'N2 baseline-only passive replay probes; no newly played games or candidate bot',
        'definitions': {'post80': 'turns 81 through recorded terminal turn, counts before actions',
            'baseTargetTurnFraction': 'at least one soldier attacking enemy base or invoking movement with final strategic goal=enemy base; excludes rally/guards and local target diversions',
            'soldierWeightedFraction': 'base-target soldier turns / all live M soldier turns after 80',
            'enemyTowersDestroyed': 'enemy-owned tower DEATH events across whole transcript; post80 count also reported',
            'limits': 'stdout exactly matches each archived reply and engine hashes; intent measures chosen goals, not successful movement; two seats are not independent maps'},
        'groups': [{'mapSet': g, 'outcome': o, **summarize(v)} for (g, o), v in sorted(groups.items())],
        'validation': {'transcripts': len(rows), 'matchedStdoutTurns': sum(r['stdoutMatchedTurns'] for r in rows),
                       'allStdoutAndStateHashesMatch': True, 'frozenMChanged': False},
        'usage': {'processCpuNs': time.process_time_ns()-start, 'diagnosticBotCpuNs': sum(r['botDiagnosticCpuNs'] for r in rows),
                  'compilationCpuHours': None, 'fullCpuHours': None, 'scope': 'passive diagnostic only, not new games; host excludes children'}}
    immutable_write(OUT/'summary.json', json_bytes(summary))
    immutable_write(ROOT/'data/phase-b/maze-hypothesis.json', json_bytes({**summary, 'publication': 'aggregate-only diagnostic evidence'}))
    print(json.dumps({'validation': summary['validation'], 'usage': summary['usage']}, indent=2))


if __name__ == '__main__':
    main()
