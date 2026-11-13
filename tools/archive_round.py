"""Read-only round archives and an append-only ledger; no bot/game execution.

The legacy HIDDEN.sha256 is a one-time historical baseline, not a rolling inventory.
New rounds use separate manifests. Read-only permissions are cooperative protection,
not an OS security boundary or an externally signed provenance claim.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
ZERO = '0' * 64


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()


def sha_file(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('nonregular archive file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as handle:
        before = os.fstat(handle.fileno())
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        after = os.fstat(handle.fileno())
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('file changed during hashing')
    return digest


def local_path(root, name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or p.as_posix() != name or '..' in p.parts
            or '\\' in name or any(ord(c) < 32 for c in name)):
        raise ValueError('unsafe relative path')
    result = root / name
    if any(p.is_symlink() for p in (result, *result.parents)):
        raise ValueError('archive paths may not contain symlinks')
    return result


def inventory(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('archive must be a real directory')
    entries = []
    directories = [directory]
    for parent, dirs, files in os.walk(directory, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                directories.append(path)
            elif stat.S_ISREG(info.st_mode):
                entries.append({'path': path.relative_to(directory).as_posix(),
                                'sha256': sha_file(path), 'bytes': info.st_size})
            else:
                raise ValueError('archive contains link or special file')
    return sorted(entries, key=lambda item: item['path']), directories


def chain(root=ROOT):
    path = root / 'private/ledger.jsonl'
    if path.is_symlink():
        raise ValueError('symlink ledger')
    payload = path.read_bytes() if path.exists() else b''
    if payload and not payload.endswith(b'\n'):
        raise ValueError('truncated ledger')
    rows = []
    seen = set()
    previous = ZERO
    for raw in payload.splitlines():
        row = json.loads(raw)
        if (encoded(row) != raw or row.get('schemaVersion') != 1
                or row.get('previousSha256') != previous or row.get('round') in seen
                or not isinstance(row.get('round'), str)
                or re.fullmatch('[0-9a-f]{64}', row.get('manifestSha256', '')) is None
                or type(row.get('files')) is not int or row['files'] < 0
                or type(row.get('bytes')) is not int or row['bytes'] < 0
                or row.get('format') not in ('sha256sum', 'round-json')):
            raise ValueError('invalid ledger row/chain')
        manifest = local_path(root, row['manifest'])
        if not manifest.is_relative_to(root / 'private'):
            raise ValueError('manifest must stay private')
        previous = hashlib.sha256(raw).hexdigest()
        seen.add(row['round'])
        rows.append(row)
    return rows, previous


def append_entry(row, *, root=ROOT):
    private = root / 'private'
    private.mkdir(exist_ok=True)
    lock_path = local_path(root, 'private/ledger.lock')
    with lock_path.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, previous = chain(root)
        if any(old['round'] == row['round'] for old in rows):
            raise ValueError('round already registered; never rewrite history')
        row = {**row, 'schemaVersion': 1, 'previousSha256': previous}
        if sha_file(local_path(root, row['manifest'])) != row['manifestSha256']:
            raise ValueError('manifest digest mismatch before append')
        ledger = local_path(root, 'private/ledger.jsonl')
        with ledger.open('ab') as handle:
            handle.write(encoded(row) + b'\n')
            handle.flush()
            os.fsync(handle.fileno())
    return {**row, 'entrySha256': hashlib.sha256(encoded(row)).hexdigest()}


def baseline(manifest, count, size, *, root=ROOT):
    if chain(root)[0]:
        raise ValueError('baseline may only initialize an empty ledger')
    path = local_path(root, manifest)
    result = append_entry({'round': 'baseline-20261113', 'format': 'sha256sum',
                           'manifest': manifest, 'manifestSha256': sha_file(path),
                           'files': count, 'bytes': size}, root=root)
    path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
    return result


def seal(directory, round_id, *, root=ROOT):
    if not isinstance(round_id, str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', round_id) is None:
        raise ValueError('invalid round ID')
    directory = Path(directory).absolute()
    relative = directory.relative_to(root).as_posix()
    local_path(root, relative)
    if not relative.startswith(('private/', 'runs/')) or directory in (
            root / 'private', root / 'private/manifests'):
        raise ValueError('seal only a specific local evidence round')
    metadata = root / 'private/manifests'
    manifest = local_path(root, 'private/manifests/' + round_id + '.json')
    if directory == metadata or directory in manifest.parents or manifest.exists():
        raise ValueError('manifest inside archive or already present')
    if any(row['round'] == round_id for row in chain(root)[0]):
        raise ValueError('round already registered')
    entries, directories = inventory(directory)
    for entry in entries:
        if sha_file(local_path(directory, entry['path'])) != entry['sha256']:
            raise ValueError('archive changed before seal')
    doc = {'schemaVersion': 1, 'directory': relative, 'files': entries}
    metadata.mkdir(exist_ok=True)
    with manifest.open('xb') as handle:
        handle.write(encoded(doc) + b'\n')
        handle.flush()
        os.fsync(handle.fileno())
    for entry in entries:
        path = directory / entry['path']
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
    manifest.chmod(0o444)
    return append_entry({'round': round_id, 'format': 'round-json',
                         'manifest': manifest.relative_to(root).as_posix(),
                         'manifestSha256': sha_file(manifest), 'files': len(entries),
                         'bytes': sum(item['bytes'] for item in entries)}, root=root)


def verify_round(round_id, *, root=ROOT):
    rows, _ = chain(root)
    row = next(item for item in rows if item['round'] == round_id)
    manifest = local_path(root, row['manifest'])
    if sha_file(manifest) != row['manifestSha256']:
        raise ValueError('manifest changed')
    if row['format'] != 'round-json':
        raise ValueError('legacy baseline is checked separately at milestones')
    doc = json.loads(manifest.read_bytes())
    directory = local_path(root, doc['directory'])
    entries, directories = inventory(directory)
    if entries != doc['files'] or len(entries) != row['files'] or sum(e['bytes'] for e in entries) != row['bytes']:
        raise ValueError('round content/file set changed')
    if any((directory / e['path']).stat().st_mode & 0o222 for e in entries) or any(
            path.stat().st_mode & 0o222 for path in directories):
        raise ValueError('round is not read-only')
    return row


def hidden_digests(root=ROOT):
    """Publication guard for legacy AND newly sealed hidden bytes, no code imports."""
    result = set()
    legacy = root / 'private/HIDDEN.sha256'
    if legacy.exists():
        with legacy.open() as handle:
            for line in handle:
                digest, _ = line.rstrip('\n').split('  ', 1)
                result.add(digest)
    for row in chain(root)[0]:
        manifest = local_path(root, row['manifest'])
        if sha_file(manifest) != row['manifestSha256']:
            raise ValueError('publication blocked: changed round manifest')
        result.add(row['manifestSha256'])
        if row['format'] == 'round-json':
            doc = json.loads(manifest.read_bytes())
            result.update(entry['sha256'] for entry in doc['files'])
    ledger = root / 'private/ledger.jsonl'
    if ledger.exists():
        result.add(sha_file(ledger))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    command = sub.add_parser('seal')
    command.add_argument('directory', type=Path)
    command.add_argument('--round', required=True)
    command = sub.add_parser('verify')
    command.add_argument('--round', required=True)
    sub.add_parser('chain')
    args = parser.parse_args()
    if args.action == 'seal':
        result = seal(args.directory, args.round)
    elif args.action == 'verify':
        result = verify_round(args.round)
    else:
        rows, head = chain()
        result = {'rounds': len(rows), 'headSha256': head}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
