"""Opt-in, byte-only experiment contracts. No bot execution or benchmarking here."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

from arena.core.benchmark import workload_digest
from arena.core.sandbox import snapshot
from arena.core.timing import Calibration
from arena.games.outpost.maps import parse_map
from arena.tournament import fingerprint, selected_pairings

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ('tools/experiment_plan.py', 'tools/experiment.py',
                  'tools/profile_bot.py', 'tools/accept_t6.py')
LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')
SENSITIVE = {'.git', '.pi', '.agents', '.ssh', '.aws', '.config', '.venv',
             'auth.json', 'credentials.json', '.netrc', '.npmrc', '.pypirc', '.azure',
             '.git-credentials', 'id_rsa', 'id_ed25519'}


def sensitive(part):
    value = part.casefold()
    return (value in SENSITIVE or value == '.env' or value.startswith('.env.')
            or value.endswith(('.pem', '.key', '.p12', '.pfx')))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def load_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 8*1024*1024:
        raise ValueError('expected a bounded regular JSON file')
    return json.loads(p.read_bytes(), object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('unexpected/missing contract fields')


def integer(value, low=0, high=10**9):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('integer contract value out of range')
    return value


def hexadecimal(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError('invalid SHA-256')
    return value


def safe_path(text, *, exists=True):
    if not isinstance(text, str) or not text or PurePosixPath(text).as_posix() != text:
        raise ValueError('canonical project-relative path required')
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(p in ('.', '..') or sensitive(p) for p in rel.parts):
        raise ValueError('escaping or sensitive path')
    path = ROOT.joinpath(*rel.parts)
    if path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symbolic links are not experiment inputs/outputs')
    if exists and not path.exists():
        raise ValueError('missing experiment input')
    return path


def digest_file(path):
    p = Path(path)
    before = p.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('regular input required')
    value = sha256(p.read_bytes()).hexdigest()
    after = p.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('input changed while hashing')
    return value


def source_digest(path):
    """Same path/hash identity as standard snapshot; never decode/import source."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('regular bot directory required')
    rows = []; total = 0
    for item in sorted(path.rglob('*')):
        rel = item.relative_to(path)
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise ValueError('source contains link/special file')
        if any(sensitive(p) for p in rel.parts):
            raise ValueError('source contains personal/configuration material')
        if '__pycache__' in rel.parts:
            continue
        if item.is_file():
            size = item.stat().st_size; total += size
            if size > 16*1024*1024 or total > 64*1024*1024:
                raise ValueError('standard source size limit exceeded')
            rows.append([rel.as_posix(), digest_file(item)])
    return sha256(json.dumps(rows, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def implementation_digest():
    base = Path(__file__).resolve().parents[1]
    digest = sha256(canonical([[name, digest_file(base/name)] for name in IMPLEMENTATION])).hexdigest()
    if '_IMPORTED_DIGEST' in globals() and digest != _IMPORTED_DIGEST:
        raise ValueError('tool source changed after import; stop and start a newly frozen version')
    return digest


def public_bot(path):
    catalog = load_json(ROOT/'package/public-files.json')['publicBotCodes']
    return path.parent == ROOT/'bots/public' and path.name in catalog


def public_map(path):
    return path.parent in (ROOT/'maps/public', ROOT/'maps/scrimmage') and path.suffix == '.map'


def approval(path):
    """Human-issued receipt, not a signature or an automatically granted approval."""
    p = safe_path(path)
    if not p.is_relative_to(ROOT/'runs') and not p.is_relative_to(ROOT/'private'):
        raise ValueError('approval receipts stay local')
    r = load_json(p)
    keys(r, ('schemaVersion', 'implementationSha256', 'frameworkSha256',
             'caReviewAccepted', 'operatorAcceptancePassed', 'evidencePath', 'evidenceSha256'))
    if (type(r['schemaVersion']) is not int or r['schemaVersion'] != 1 or r['implementationSha256'] != implementation_digest()
            or r['frameworkSha256'] != fingerprint(ROOT) or r['caReviewAccepted'] is not True
            or r['operatorAcceptancePassed'] is not True):
        raise ValueError('current CA review and operator acceptance are required')
    evidence = safe_path(r['evidencePath'])
    if not evidence.is_relative_to(ROOT/'runs') or digest_file(evidence) != hexadecimal(r['evidenceSha256']):
        raise ValueError('acceptance evidence changed or is not local')
    e = load_json(evidence)
    if (e.get('passed') is not True or e.get('executed') is not True
            or e.get('evidenceKind') != 'public-bwrap-acceptance' or e.get('syntheticFixture') is True
            or e.get('implementationSha256') != implementation_digest()
            or e.get('frameworkSha256') != fingerprint(ROOT)):
        raise ValueError('acceptance evidence does not cover an actual run of this implementation')
    cases = e.get('cases')
    if (not isinstance(cases, list) or len(cases) != 2
            or any(not isinstance(c, dict) for c in cases)
            or any(type(c.get(k)) is not int for c in cases
                   for k in ('jobs', 'completedGames', 'auditedReplays', 'headersAndCpuTotalsChecked'))
            or [(c.get('jobs'), c.get('completedGames')) for c in cases] != [(1, 2), (6, 6)]
            or any(c.get('auditedReplays') != c['completedGames']
                   or c.get('headersAndCpuTotalsChecked') != c['completedGames']
                   or c.get('logVerified') is not True for c in cases)):
        raise ValueError('acceptance evidence is incomplete')
    return digest_file(p)


def validate_spec(spec, out, *, approval_path=None, fresh=True):
    keys(spec, ('schemaVersion', 'id', 'purpose', 'bots', 'maps', 'pairs', 'seeds', 'jobs', 'timing', 'caps', 'stop'))
    if (type(spec['schemaVersion']) is not int or spec['schemaVersion'] != 1 or not isinstance(spec['id'], str) or not LABEL.fullmatch(spec['id'])
            or spec['purpose'] not in ('acceptance', 'diagnostic')):
        raise ValueError('unsupported contract; no scoring mode')
    integer(spec['jobs'], 1, 6)
    if (not isinstance(spec['seeds'], list) or len(spec['seeds']) != 2
            or any(type(n) is not int or n < 0 for n in spec['seeds'])):
        raise ValueError('two nonnegative identity seeds required')
    if not isinstance(spec['bots'], list) or not 1 <= len(spec['bots']) <= 32:
        raise ValueError('bounded nonempty bot catalog required')
    labels = []; sources = []
    for bot in spec['bots']:
        keys(bot, ('label', 'path', 'sha256'))
        if not isinstance(bot['label'], str) or not LABEL.fullmatch(bot['label']) or bot['label'] in labels:
            raise ValueError('labels must be safe and unique')
        labels.append(bot['label']); hexadecimal(bot['sha256']); source = safe_path(bot['path'], exists=fresh)
        if not (public_bot(source) or source.is_relative_to(ROOT/'private/ladder')):
            raise ValueError('bot must be in the public catalog or received private ladder')
        sources.append(source)
    if not isinstance(spec['maps'], list) or not 1 <= len(spec['maps']) <= 4096:
        raise ValueError('bounded nonempty map list required')
    maps = []
    for entry in spec['maps']:
        keys(entry, ('path', 'sha256')); hexadecimal(entry['sha256']); p = safe_path(entry['path'], exists=fresh)
        if not (public_map(p) or p.is_relative_to(ROOT/'private')) or p.suffix != '.map':
            raise ValueError('map outside approved material roots')
        maps.append(p)
    if len({x['sha256'] for x in spec['maps']}) != len(maps):
        raise ValueError('duplicate map contents are not independent samples')
    if not isinstance(spec['pairs'], list):
        raise ValueError('explicit label pairings required')
    indexed = []
    for pair in spec['pairs']:
        if not isinstance(pair, list) or len(pair) != 2 or any(x not in labels for x in pair):
            raise ValueError('unknown pair label')
        indexed.append([labels.index(x) for x in pair])
    pairs = selected_pairings(len(labels), indexed)
    if spec['seeds'][0] == spec['seeds'][1] and any(a == b for a, b in pairs):
        raise ValueError('self play requires different seeds')
    keys(spec['timing'], ('path', 'sha256'))
    lock = safe_path(spec['timing']['path'], exists=fresh); hexadecimal(spec['timing']['sha256'])
    if not (lock.is_relative_to(ROOT/'package') or lock.is_relative_to(ROOT/'private')
            or lock.is_relative_to(ROOT/'runs')):
        raise ValueError('fixed lock outside material roots')
    keys(spec['caps'], ('games', 'compiles', 'botStarts', 'wallSeconds'))
    for key in spec['caps']:
        integer(spec['caps'][key], 1 if key in ('games', 'botStarts', 'wallSeconds') else 0,
                10000 if key == 'games' else 10**9)
    if spec['caps']['wallSeconds'] > 7200:
        raise ValueError('maximum single experiment window is two hours')
    games = 2*len(maps)*len(pairs)
    if games > spec['caps']['games'] or 8*games > spec['caps']['botStarts']:
        raise ValueError('caps must reserve the whole plan and all three standard infrastructure retries')
    keys(spec['stop'], ('onFrameworkError', 'maxBotFaultGames'))
    if spec['stop']['onFrameworkError'] is not True:
        raise ValueError('framework terminal errors cannot be ignored')
    if spec['stop']['maxBotFaultGames'] is not None:
        integer(spec['stop']['maxBotFaultGames'])
    out = safe_path(out, exists=False)
    if (fresh and out.exists()) or not (out.is_relative_to(ROOT/'runs') or out.is_relative_to(ROOT/'private')):
        raise ValueError('fresh local-only output directory required; no resume')
    inputs = [*sources, *maps, lock]
    if any(out == p or out.is_relative_to(p) or p.is_relative_to(out) for p in inputs):
        raise ValueError('output/input trees overlap')
    private = any(p.is_relative_to(ROOT/'private') for p in inputs)
    if private and not out.is_relative_to(ROOT/'private'):
        raise ValueError('private inputs require private output')
    approved = approval(approval_path) if approval_path is not None else None
    if approved is None and (spec['purpose'] != 'acceptance' or
                             not all(public_bot(p) for p in sources) or not all(public_map(p) for p in maps)):
        raise ValueError('before acceptance only public-bot/public-map acceptance experiments may execute or freeze')
    return out, sources, maps, lock, pairs, games, approved


def readonly_tree(root):
    for p in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if p.is_symlink() or not (p.is_file() or p.is_dir()):
            raise ValueError('unsafe frozen object')
        os.chmod(p, stat.S_IMODE(p.stat().st_mode) & ~0o222)
    os.chmod(root, stat.S_IMODE(root.stat().st_mode) & ~0o222)


def freeze(spec, out, *, approval_path=None):
    out, sources, maps, lock, pairs, games, approved = validate_spec(spec, out, approval_path=approval_path)
    # No source body is read until scope, paths, privacy and approval are checked.
    before = fingerprint(ROOT)
    lock_raw = lock.read_bytes()
    if sha256(lock_raw).hexdigest() != spec['timing']['sha256']:
        raise ValueError('fixed lock digest mismatch')
    cal = Calibration.from_bytes(lock_raw, workload_digest(), jobs=spec['jobs'])
    if cal.sandbox != 'bwrap' or cal.locked_budget is None or cal.locked_budget['turns'] != 300:
        raise ValueError('standard-1 machine-bound bwrap fixed lock required')
    for row, p in zip(spec['bots'], sources):
        if source_digest(p) != row['sha256']:
            raise ValueError('bot label/source digest mismatch')
    for row, p in zip(spec['maps'], maps):
        if digest_file(p) != row['sha256']:
            raise ValueError('map digest mismatch')
        parse_map(p.read_text())
    cpp = sum(not (p/'main.py').is_file() for p in sources)
    for p in sources:
        if (p/'main.py').is_file() == bool(list(p.glob('*.cpp'))):
            raise ValueError('one standard source language/entrypoint required')
    if cpp > spec['caps']['compiles']:
        raise ValueError('compile reservation is too small')
    out.mkdir(parents=True, mode=0o700)
    inputs = out/'inputs'; inputs.mkdir()
    bots = []
    for row, p in zip(spec['bots'], sources):
        target = inputs/'bots'/row['label']
        if snapshot(p, target) != row['sha256']:
            raise ValueError('source changed during frozen copy; partial artifacts retained')
        language = 'python' if (target/'main.py').is_file() else 'cpp'
        bots.append({**row, 'frozen': target.relative_to(ROOT).as_posix(), 'language': language})
    frozen_maps = []
    for index, (row, p) in enumerate(zip(spec['maps'], maps)):
        target = inputs/'maps'/str(index)/p.name; target.parent.mkdir(parents=True)
        raw = p.read_bytes()
        if sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('map changed during frozen copy')
        target.write_bytes(raw)
        frozen_maps.append({**row, 'frozen': target.relative_to(ROOT).as_posix()})
    (inputs/'timing-lock.json').write_bytes(lock_raw)
    sdk = {language: source_digest(ROOT/'sdk'/language) for language in {b['language'] for b in bots}}
    if fingerprint(ROOT) != before:
        raise ValueError('framework changed during freeze')
    frame = {'schemaVersion': 1, 'spec': spec, 'bots': bots, 'maps': frozen_maps,
             'pairs': pairs, 'games': games, 'reservedCompiles': cpp,
             'frameworkSha256': before, 'implementationSha256': implementation_digest(),
             'sdkSha256': sdk, 'timingHeader': cal.header(), 'approvalSha256': approved,
             'approvalPath': approval_path, 'root': out.relative_to(ROOT).as_posix()}
    (inputs/'frame.json').write_bytes(canonical(frame)+b'\n')
    readonly_tree(inputs)
    return json.loads(canonical(frame)), digest_file(inputs/'frame.json')


def verify_frame(out):
    out = safe_path(out)
    for p in (out/'inputs', *(out/'inputs').rglob('*')):
        if p.is_symlink() or not (p.is_file() or p.is_dir()) or p.stat().st_mode & 0o222:
            raise ValueError('frozen input set must remain regular and read-only')
    frame = load_json(out/'inputs/frame.json')
    keys(frame, ('schemaVersion', 'spec', 'bots', 'maps', 'pairs', 'games', 'reservedCompiles',
                 'frameworkSha256', 'implementationSha256', 'sdkSha256', 'timingHeader',
                 'approvalSha256', 'approvalPath', 'root'))
    if (type(frame['schemaVersion']) is not int or frame['schemaVersion'] != 1 or frame['root'] != out.relative_to(ROOT).as_posix()
            or frame['implementationSha256'] != implementation_digest()
            or frame['frameworkSha256'] != fingerprint(ROOT)):
        raise ValueError('frozen runtime/tool identity changed')
    _, _, _, _, pairs, games, approved = validate_spec(
        frame['spec'], frame['root'], approval_path=frame['approvalPath'], fresh=False)
    if frame['pairs'] != [list(p) for p in pairs] or frame['games'] != games or approved != frame['approvalSha256']:
        raise ValueError('frozen schedule or approval changed')
    if (not isinstance(frame['bots'], list) or not isinstance(frame['maps'], list)
            or len(frame['bots']) != len(frame['spec']['bots']) or len(frame['maps']) != len(frame['spec']['maps'])):
        raise ValueError('frozen catalog changed')
    cpp = 0
    for row, declared in zip(frame['bots'], frame['spec']['bots']):
        keys(row, ('label', 'path', 'sha256', 'frozen', 'language'))
        if any(row[k] != declared[k] for k in declared):
            raise ValueError('frozen label declaration changed')
        p = safe_path(row['frozen'])
        language = 'python' if (p/'main.py').is_file() else 'cpp'
        cpp += language == 'cpp'
        if (p != out/'inputs/bots'/row['label'] or source_digest(p) != row['sha256']
                or row['language'] != language
                or (p/'main.py').is_file() == bool(list(p.glob('*.cpp')))):
            raise ValueError('frozen bot label binding changed')
    if cpp != frame['reservedCompiles'] or cpp > frame['spec']['caps']['compiles']:
        raise ValueError('compile reservation changed')
    if not isinstance(frame['sdkSha256'], dict) or set(frame['sdkSha256']) != {b['language'] for b in frame['bots']}:
        raise ValueError('SDK catalog changed')
    for index, (row, declared) in enumerate(zip(frame['maps'], frame['spec']['maps'])):
        keys(row, ('path', 'sha256', 'frozen'))
        p = safe_path(row['frozen'])
        if (any(row[k] != declared[k] for k in declared)
                or p != out/'inputs/maps'/str(index)/Path(row['path']).name
                or digest_file(p) != row['sha256']):
            raise ValueError('frozen map changed')
    lock = out/'inputs/timing-lock.json'
    if digest_file(lock) != frame['spec']['timing']['sha256']:
        raise ValueError('frozen lock changed')
    cal = Calibration.from_bytes(lock.read_bytes(), workload_digest(), jobs=frame['spec']['jobs'])
    if json.loads(canonical(cal.header())) != frame['timingHeader']:
        raise ValueError('frozen calibration changed')
    for language, digest in frame['sdkSha256'].items():
        if source_digest(ROOT/'sdk'/language) != digest:
            raise ValueError('SDK changed')
    if frame['approvalPath'] is not None and approval(frame['approvalPath']) != frame['approvalSha256']:
        raise ValueError('approval receipt changed')
    return frame, digest_file(out/'inputs/frame.json')


# Pin code at import, not after a potentially concurrent edit during execution.
_IMPORTED_DIGEST = implementation_digest()
