"""Explicit public-file export for a fresh pilot/DeepSeek session; no bots.

Not a clone, no symlinks, no Git metadata/remotes, no personal config. Directory
isolation does not enforce an OS access boundary or clear a model's memory.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def safe_relative(text):
    if not isinstance(text, str) or not text or text != PurePosixPath(text).as_posix():
        raise ValueError('noncanonical material path')
    path = PurePosixPath(text)
    if (path.is_absolute() or not path.parts
            or any(p in ('.', '..') or p.casefold() in ('.git', 'private', 'runs', '.pi', '.agents', '.venv') for p in path.parts)):
        raise ValueError('non-public or escaping material path')
    return path


def declared(root, role):
    spec = json.loads((root/'package/public-files.json').read_text())
    if spec['schemaVersion'] != 1 or role not in ('pilot', 'deepseek'): raise ValueError('unknown export role/schema')
    if (set(spec['publicMapTypes']) != {'open', 'corridor', 'island', 'maze'}
            or spec['publicMapsPerType'] != 10 or len(spec['publicBotCodes']) != 10):
        raise ValueError('unexpected public catalog')
    entries = [(p, p) for p in spec['identity']]
    entries += list(spec['renamed'].items())
    for code in spec['publicBotCodes']:
        if '/' in code or code in ('.', '..'): raise ValueError('invalid public bot code')
        entries += [(f'bots/public/{code}/{name}', f'bots/public/{code}/{name}') for name in ('main.cpp', 'strategy.hpp')]
    for kind in spec['publicMapTypes']:
        entries += [(f'maps/public/{kind}-{i:02d}.map', f'maps/public/{kind}-{i:02d}.map') for i in range(1, 11)]
    entries += [(f'maps/scrimmage/{name}', f'maps/scrimmage/{name}') for name in spec['scrimmageMaps']]
    common = len(entries); entries += list(spec['roles'][role].items())
    if len({target for target, _ in entries}) != len(entries): raise ValueError('duplicate material destination')
    singles = {'rules/rules.md', 'rules/standard-1.json', 'package/workspace-README.md',
               'package/benchmark-reference.json', 'package/pilot-instructions.md', 'docs/BRIEF-DEEPSEEK.md'}
    for target, source in entries:
        safe_relative(target); relative = safe_relative(source)
        if source not in singles and not source.startswith(('arena/', 'sdk/', 'bots/public/', 'maps/public/', 'maps/scrimmage/')):
            raise ValueError('source outside public allowlist')
        if any(part.lower() in ('grade.py', 'grading.py', 'scoring.py', 'ladder.json', 'authors.md', 'agents.md') for part in relative.parts):
            raise ValueError('builder/scoring material cannot enter workspace')
        path = root/source
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('missing/nonregular/symlink source')
    return entries, common


def validate(destination, entries):
    expected = {target for target, _ in entries}|{'PUBLIC-MANIFEST.sha256'}
    actual = set()
    for path in destination.rglob('*'):
        if path.is_symlink(): raise ValueError('workspace symlink')
        if path.is_file(): actual.add(path.relative_to(destination).as_posix())
        elif not path.is_dir(): raise ValueError('special workspace object')
        if path.name.casefold() in ('.git', 'private', '.pi', '.agents'):
            raise ValueError('foreign context or Git metadata in workspace')
    if actual != expected: raise ValueError('undeclared or missing workspace files')
    listed = set()
    for line in (destination/'PUBLIC-MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1); safe_relative(name)
        if sha256((destination/name).read_bytes()).hexdigest() != digest: raise ValueError('export digest mismatch')
        if name in listed: raise ValueError('duplicate export manifest row')
        listed.add(name)
    if listed != expected-{'PUBLIC-MANIFEST.sha256'}: raise ValueError('incomplete export manifest')
    if any((parent/'.git').exists() for parent in destination.parents): raise ValueError('workspace has a Git parent')
    for folder in ('bot', 'handoff/in', 'handoff/out'):
        if not (destination/folder).is_dir() or any((destination/folder).iterdir()): raise ValueError('initial handoff/bot not empty')
    return {'files': len(actual), 'manifestEntries': len(listed), 'noGitRepositoryOrRemote': True,
            'onlyDeclaredPublicMaterials': True, 'noSymlinks': True, 'emptyBotAndHandoff': True}


def build(destination, role, *, root=ROOT):
    destination = Path(destination).absolute(); root = Path(root).absolute()
    if ('..' in destination.parts or destination.exists() or destination.is_relative_to(root)
            or root.is_relative_to(destination) or any(p.is_symlink() for p in (destination, *destination.parents))):
        raise ValueError('workspace must be a new independent non-symlink directory, not a clone/subdirectory')
    if any((p/'.git').exists() for p in destination.parents): raise ValueError('Git ancestor of workspace')
    entries, common = declared(root, role); destination.mkdir(mode=0o700)
    digests = []
    for target, source in entries:
        path = destination/target; path.parent.mkdir(parents=True, exist_ok=True)
        raw = (root/source).read_bytes()
        with path.open('xb') as stream: stream.write(raw)
        digests.append(f'{sha256(raw).hexdigest()}  {target}\n')
    with (destination/'PUBLIC-MANIFEST.sha256').open('x') as stream: stream.writelines(sorted(digests))
    for folder in ('bot', 'handoff/in', 'handoff/out'): (destination/folder).mkdir(parents=True, exist_ok=True)
    return {**validate(destination, entries), 'role': role,
            'commonMaterialSha256': sha256(''.join(sorted(digests[:common])).encode()).hexdigest(),
            'materialManifestSha256': sha256((destination/'PUBLIC-MANIFEST.sha256').read_bytes()).hexdigest(),
            'newGames': 0, 'modelSessionsStarted': 0,
            'limits': 'file/material isolation only; fresh-session/context/memory and tool restrictions must be verified at user launch'}


def smoke(destination):
    """Imports, command registration and existing public map check only."""
    python = shutil.which('python3.13')
    if python is None: raise ValueError('Python 3.13 executable missing; do not use system Python 3.10')
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
           'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
    commands = [[python, '-B', '-c', 'import sys,arena,pathlib; assert sys.version_info[:2]==(3,13); assert pathlib.Path(arena.__file__).resolve().is_relative_to(pathlib.Path.cwd())'],
                [python, '-B', '-m', 'arena', '--help'],
                [python, '-B', '-m', 'arena', 'mapcheck', 'maps/public/open-01.map']]
    for command in commands:
        result = subprocess.run(command, cwd=destination, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode: raise ValueError('public workspace import/CLI/map check failed: '+result.stderr)
    return {'importCliMapChecks': 3, 'botExecutions': 0, 'compileExecutions': 0, 'benchmarkExecutions': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=('pilot', 'deepseek'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); result = build(args.out, args.role)
    result.update(smoke(args.out)); print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
