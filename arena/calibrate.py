"""Replay the same adjacent schedule as the development-host reference."""
from collections import Counter
from hashlib import sha256
import json
from math import isfinite, ulp
from pathlib import Path
from statistics import fmean
from time import monotonic

from arena import __version__
from arena.core.benchmark import workload_digest
from arena.core.journal import atomic_json, records
from arena.core.resources import lock_directory
from arena.core.sandbox import ROOT
from arena.core.timing import Calibration
from arena.ladder import checked_maps, load_ladder, private_path
from arena.tournament import run_tournament
from tools.provisional_bt import fit


def identity(ladder, ladder_bytes):
    return {'schemaVersion': 1, 'ladderVersion': ladder.version, 'engineVersion': __version__,
            'ladderSha256': sha256(ladder_bytes).hexdigest(),
            'calibrationMapsSha256': [m['sha256'] for m in ladder.calibration['maps']],
            'sourceHashes': [m.source_hash for m in ladder.members]}


def schedule(ladder):
    """The batch IDs bind host paths and timing. Compare by portable slot IDs."""
    ids = {m.code: i for i, m in enumerate(ladder.members)}
    pairs = sorted(tuple(sorted((ids[a], ids[b]))) for a, b in ladder.calibration['pairings'])
    tasks = {}
    for a, b in pairs:
        members = [ladder.members[i].code for i in (a, b)]
        for index, m in enumerate(ladder.calibration['maps']):
            digest = m['sha256']
            for seat, players in enumerate(((a, b), (b, a))):
                slot = ['hrw-adjacent-v1', members, digest, seat, ladder.seeds]
                key = sha256(json.dumps(slot, separators=(',', ':')).encode()).hexdigest()
                tasks[players, index] = {'taskId': key, 'players': [ladder.members[i].code for i in players],
                                         'mapSha256': digest, 'seat': seat}
    return pairs, tasks


def finite(value):
    return type(value) in (int, float) and isfinite(value)


def write_reference(path, reference):
    body = (json.dumps(reference, indent=2, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(body)


def read_reference(path, expected_identity, slots, ladder):
    ref = json.loads(path.read_bytes())
    for key, value in expected_identity.items():
        if not isinstance(ref, dict) or ref.get(key) != value:
            raise ValueError(f'adjacent reference configuration mismatch: {key}')
    planned = {game['taskId']: game for game in slots.values()}
    games = ref.get('games')
    if not isinstance(games, list) or len(games) != len(planned):
        raise ValueError('adjacent reference must contain the complete fixed schedule')
    seen = set()
    for game in games:
        task_id = game.get('taskId') if isinstance(game, dict) else None
        if (not isinstance(task_id, str) or task_id in seen or task_id not in planned
                or any(game.get(k) != v for k, v in planned[task_id].items())
                or not valid_winner(game.get('winner')) or 'winner' not in game
                or not valid_faults(game.get('faults'))):
            raise ValueError('adjacent reference has an invalid result or schedule slot')
        seen.add(task_id)
    if ref.get('faultGames') != fault_games(games):
        raise ValueError('adjacent reference fault count does not match its games')
    pairs = ref.get('pairs')
    tiers = {m.code: i for i, level in enumerate(ladder.levels) for m in level}
    counts = Counter(pair_index(tiers, g['players']) for g in slots.values())
    if not isinstance(pairs, list) or len(pairs) != len(ladder.levels) - 1:
        raise ValueError('adjacent reference is missing tier pairs')
    for i, pair in enumerate(pairs):
        if (not isinstance(pair, dict) or (pair.get('lower'), pair.get('upper')) != (f'L{i}', f'L{i+1}')
                or pair.get('games') != counts[i] or not finite(pair.get('scoreRate'))
                or not 0 <= pair['scoreRate'] <= 1 or 'eloGap' not in pair
                or (pair['eloGap'] is not None and not finite(pair['eloGap']))):
            raise ValueError('adjacent reference has an invalid tier-pair summary')
    return ref


def valid_winner(winner):
    return winner is None or (type(winner) is int and winner in (0, 1))


def valid_faults(faults):
    return isinstance(faults, list) and len(faults) == 2 and all(f is None or isinstance(f, str) for f in faults)


def fault_games(games):
    ids = sorted(game['taskId'] for game in games if any(game['faults']))
    return {'count': len(ids), 'taskIds': ids}


def pair_index(tiers, players):
    return min(tiers[p] for p in players)


def summarize_adjacent(ladder, games, complete):
    codes = [m.code for m in ladder.members]
    ids = {code: i for i, code in enumerate(codes)}
    tiers = {m.code: i for i, level in enumerate(ladder.levels) for m in level}
    matrix = [[0.0] * len(codes) for _ in codes]
    total, upper = Counter(), Counter()
    for game in games:
        a, b = game['players']
        w = game['winner']
        left = .5 if w is None else float(w == 0)
        i, j = ids[a], ids[b]
        matrix[i][j] += left
        matrix[j][i] += 1 - left
        k = pair_index(tiers, (a, b))
        total[k] += 1
        upper[k] += left if tiers[a] > tiers[b] else 1 - left
    values = fit(matrix, ids['M-balanced'])['elo'] if complete else [None] * len(codes)
    ratings = dict(zip(codes, values, strict=True))
    centers = []
    for level in ladder.levels:
        values = [ratings[m.code] for m in level]
        centers.append(fmean(values) if all(map(finite, values)) else None)
    pairs = []
    for i, (low, high) in enumerate(zip(centers, centers[1:])):
        pairs.append({'lower': f'L{i}', 'upper': f'L{i+1}',
                      'eloGap': high - low if low is not None and high is not None else None,
                      'scoreRate': upper[i] / total[i] if total[i] else None, 'games': total[i]})
    return {'games': games, 'ratings': ratings, 'pairs': pairs, 'faultGames': fault_games(games)}


def compare(ladder, current, reference, *, expected):
    tiers = {m.code: i for i, level in enumerate(ladder.levels) for m in level}
    previous = {g['taskId']: g['winner'] for g in reference['games']}
    matches, compared = Counter(), Counter()
    for game in current['games']:
        i = pair_index(tiers, game['players'])
        matches[i] += game['winner'] == previous[game['taskId']]
        compared[i] += 1

    def agreement(same, count):
        return {'same': same, 'compared': count, 'rate': same / count if count else None}

    comparison, pair_agreement = [], []
    for i, (new, old) in enumerate(zip(current['pairs'], reference['pairs'], strict=True)):
        elo_delta = new['eloGap'] - old['eloGap'] if finite(new['eloGap']) and finite(old['eloGap']) else None
        score_delta = None if new['scoreRate'] is None else new['scoreRate'] - old['scoreRate']
        # One ULP at 1 covers subtraction rounding in rates at the inclusive .05 boundary.
        consistent = (abs(elo_delta) <= 50 if elo_delta is not None else
                      score_delta is not None and abs(score_delta) <= .05 + ulp(1.0))
        pair = {'lower': new['lower'], 'upper': new['upper']}
        comparison.append({**pair, 'gate': i >= 2, 'consistent': consistent,
                           'referenceEloGap': old['eloGap'], 'eloGap': new['eloGap'], 'eloDelta': elo_delta,
                           'referenceScoreRate': old['scoreRate'], 'scoreRate': new['scoreRate'],
                           'scoreDelta': score_delta, 'games': new['games']})
        pair_agreement.append({**pair, **agreement(matches[i], compared[i])})
    fault_limit = reference['faultGames']['count'] + 2
    passed = (len(current['games']) == expected and current['faultGames']['count'] <= fault_limit
              and all(row['consistent'] for row in comparison if row['gate']))
    return {'comparisons': comparison, 'gameAgreement': {**agreement(sum(matches.values()), sum(compared.values())),
                                                         'pairs': pair_agreement},
            'referenceFaultGames': reference['faultGames']['count'], 'faultLimit': fault_limit, 'passed': passed}


def collect_games(batch, run, slots, expected_identity):
    plan = json.loads((batch/'manifest.json').read_bytes())
    request = plan['request']
    if (request['sourceHashes'] != expected_identity['sourceHashes']
            or request['mapHashes'] != expected_identity['calibrationMapsSha256']):
        raise ValueError('adjacent calibration input bytes changed')
    tasks = {t['taskId']: t for t in plan['tasks']}
    planned = {(tuple(t['players']), t['mapIndex']) for t in tasks.values()}
    rows = records(batch/'results.jsonl')
    if len(tasks) != len(slots) or len(tasks) != run['tasks'] or planned != slots.keys() or len(rows) != run['completed']:
        raise ValueError('adjacent calibration shape changed')
    games = {}
    for row in rows:
        t = tasks[row['taskId']]
        k = tuple(t['players']), t['mapIndex']
        result = row['result']
        if (k in games or row['status'] != 'complete' or any(row[key] != value for key, value in t.items())
                or not valid_winner(result['winner']) or not valid_faults(result['faults'])):
            raise ValueError('unexpected or duplicate calibration result')
        games[k] = {**slots[k], 'winner': result['winner'], 'reason': result['reason'],
                    'turns': result['turns'], 'faults': result['faults']}
    return [games[k] for k in slots if k in games]


def calibrate(ladder_path, maps, out, *, fixed_timing, jobs=6, resume=False, reference=None, write_reference_path=None):
    started = monotonic()
    root = ROOT/'private'
    out = private_path(root, out, exists=False)
    ladder = load_ladder(ladder_path, root)
    paths = checked_maps(root, maps, ladder.calibration['maps'])
    bound = identity(ladder, ladder_path.read_bytes())
    pairs, slots = schedule(ladder)
    previous = None
    if write_reference_path is not None:
        if reference is not None:
            raise ValueError('choose a new adjacent reference OR compare against one')
        write_reference_path = private_path(root, write_reference_path, exists=False)
        if write_reference_path.exists():
            raise FileExistsError(write_reference_path)
        if write_reference_path in (out/'results.json', out/'ratings-private.json'):
            raise ValueError('the reference path must differ from the calibration reports')
    else:
        reference = reference or root/'ladder/adjacent-reference-1.0.0.json'
        previous = read_reference(private_path(root, reference), bound, slots, ladder)
    batch = out/'batch'
    if (batch/'manifest.json').is_file() != resume:
        raise ValueError('calibration resume requires its original batch')
    timing = Calibration.load(fixed_timing, workload_digest(), jobs=jobs)
    if timing.sandbox != 'bwrap' or timing.locked_budget is None:
        raise ValueError('calibration requires the host-local offline fixed timing lock')
    locks = str(lock_directory().absolute())
    run = run_tournament([m.source for m in ladder.members], paths, batch, jobs=jobs, sandbox='bwrap',
        fixed_timing=fixed_timing, seeds=ladder.seeds, pairings=pairs, resume=resume,
        trusted_cache=root/'runtime-cache/release-grade')
    games = collect_games(batch, run, slots, bound)
    expected = len(slots)
    complete = len(games) == expected
    panel = summarize_adjacent(ladder, games, complete)
    timing_lock = {'sha256': timing.lock_sha256, 'jobs': timing.jobs, 'speedFactor': timing.factor,
                   'limits': timing.locked_budget['limits']}
    result = {'schemaVersion': 1, 'mode': 'adjacent', 'ladderVersion': ladder.version, 'engineVersion': __version__,
              'games': len(games), 'expected': expected, 'infraErrors': expected - len(games),
              'infraRetryAttempts': run['infraErrorAttempts'], 'lockDirectory': locks, 'timingLock': timing_lock,
              'pairs': panel['pairs'], 'faultGames': panel['faultGames']}
    if previous is None:
        if complete:
            write_reference(write_reference_path, {**bound, 'timingLock': timing_lock, **panel})
        result.update(referenceWritten=complete, passed=complete)
    else:
        result.update(compare(ladder, panel, previous, expected=expected))
    result['wallSeconds'] = monotonic() - started
    atomic_json(out/'results.json', result)
    atomic_json(out/'ratings-private.json', panel['ratings'])
    return result


def register(commands):
    p = commands.add_parser('calibrate', help='compare adjacent ladder games with the development-host reference')
    p.add_argument('--mode', choices=['adjacent'], default='adjacent')
    p.add_argument('--ladder', type=Path, default=ROOT/'private/ladder/ladder-1.0.0.json')
    p.add_argument('--maps', type=Path, default=ROOT/'private/maps/calibration')
    p.add_argument('--fixed-timing', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=6)
    p.add_argument('--resume', action='store_true')
    references = p.add_mutually_exclusive_group()
    references.add_argument('--write-reference', type=Path, help='write a new private adjacent reference')
    references.add_argument('--reference', type=Path, help='use the supplied or default private adjacent reference')
    p.set_defaults(handler=cli)


def cli(args):
    result = calibrate(args.ladder, args.maps, args.out, fixed_timing=args.fixed_timing, jobs=args.jobs,
                       resume=args.resume, reference=args.reference, write_reference_path=args.write_reference)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['passed'] else 2
