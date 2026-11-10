"""Validate and archive an author's delivery without importing or executing bot code.

Original bytes/layout are retained under private/. This is intake, not runtime
approval, authorship verification, or strength evaluation.
"""
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat

from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path
from tools.phase_b_holdout import source_digest

MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


def relative_name(text):
    p = PurePosixPath(text)
    if (not text or not p.parts or p.is_absolute() or p.as_posix() != text or '\\' in text
            or any(part in ('', '.', '..') for part in p.parts) or any(ord(c) < 32 for c in text)):
        raise ValueError('noncanonical delivery path')
    return text


def inventory(folder):
    folder = folder.absolute()
    if any(p.is_symlink() for p in (folder, *folder.parents)) or not folder.is_dir():
        raise ValueError('delivery root must be a real directory')
    files = {}; total = 0
    for parent, dirs, names in os.walk(folder, followlinks=False):
        for name in dirs + names:
            path = Path(parent) / name; rel = relative_name(path.relative_to(folder).as_posix())
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError('links and special files are forbidden')
            if stat.S_ISDIR(info.st_mode):
                if rel != 'bot' and not rel.startswith('bot/'):
                    raise ValueError('unexpected delivery directory')
                continue
            if info.st_size > MAX_FILE:
                raise ValueError('delivery file too large')
            if rel not in ('NOTES.md', 'SHA256SUMS') and not rel.startswith('bot/'):
                raise ValueError('unexpected delivery file')
            total += info.st_size
            if total > MAX_TOTAL: raise ValueError('delivery too large')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError('delivery changed while opening')
                body = stream.read(MAX_FILE + 1)
            if len(body) != info.st_size: raise ValueError('delivery changed while reading')
            files[rel] = body
    if not {'NOTES.md', 'SHA256SUMS'} <= files.keys() or not (folder/'bot').is_dir():
        raise ValueError('missing bot, notes, or checksum list')
    bot_files = {p for p in files if p.startswith('bot/')}
    python = 'bot/main.py' in bot_files
    cpp = any(PurePosixPath(p).parent == PurePosixPath('bot') and p.endswith('.cpp') for p in bot_files)
    if python == cpp: raise ValueError('exactly one Python/C++ entry format is required')
    declared = {}
    for line in files['SHA256SUMS'].decode('utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *](.+)', line)
        if not match: raise ValueError('malformed SHA256SUMS')
        expected, name = match.groups(); relative_name(name)
        if not name.startswith('bot/') or name in declared: raise ValueError('duplicate/non-bot checksum entry')
        declared[name] = expected.lower()
    if set(declared) != bot_files: raise ValueError('checksum coverage differs from bot files')
    if any(sha256(files[p]).hexdigest() != expected for p, expected in declared.items()):
        raise ValueError('bot checksum mismatch')
    files['NOTES.md'].decode('utf-8')
    return files


def receive(source, destination, receipt, *, root=ROOT):
    destination = private_path(destination, root); receipt = private_path(receipt, root)
    if destination.exists() or receipt.exists(): raise ValueError('delivery already received; never overwrite it')
    files = inventory(source)
    # Check a second time before copying; mutations are rejected, not repaired.
    if inventory(source) != files: raise ValueError('delivery changed during validation')
    destination.mkdir(parents=True, exist_ok=False)
    for path, body in sorted(files.items()): immutable_write(destination/path, body)
    if inventory(destination) != files: raise ValueError('archived delivery differs')
    result = {'acceptedAsImmutableArchive': True, 'source': str(source.absolute()),
              'destination': str(destination), 'files': len(files), 'bytes': sum(map(len, files.values())),
              'fileSha256': {p: sha256(body).hexdigest() for p, body in sorted(files.items())},
              'botSourceSha256': source_digest(destination/'bot'), 'originalBytesPreserved': True,
              'codeModified': False, 'runtimeChecked': False, 'strengthEvaluated': False,
              'authorshipOrSessionIndependenceVerified': False}
    immutable_write(receipt, json_bytes(result))
    return result
