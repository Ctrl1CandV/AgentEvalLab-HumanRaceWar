"""Successful C++ artifacts cached by source, SDK and compilation configuration."""
from contextlib import contextmanager
from hashlib import sha256
import fcntl
import json
from pathlib import Path
import shutil
from uuid import uuid4

from .sandbox import InfrastructureError

FLAGS = ['-O2', '-std=gnu++20', '-I/sdk', 'AS=2147483648', 'CPU=60', 'wall=60',
         'NPROC=16', 'FSIZE=67108864', 'serialized', 'cache-v2']


def compiler_identity():
    # The environment is immutable during a batch. Hash executables plus system
    # header/library metadata, invalidating normal toolchain package updates.
    paths = [Path('/usr/bin/g++'), Path('/usr/bin/as'), Path('/usr/bin/ld')]
    paths += list(Path('/usr/lib/gcc').glob('**/cc1plus'))
    digest = sha256()
    for path in sorted(paths):
        digest.update(str(path.resolve()).encode()); digest.update(path.read_bytes())
    for root in ('/usr/include/c++', '/usr/include/x86_64-linux-gnu/c++', '/usr/lib/gcc'):
        for path in sorted(Path(root).rglob('*')):
            info = path.stat()
            digest.update(f'{path}:{info.st_size}:{info.st_mtime_ns}'.encode())
    return digest.hexdigest()


class CompileCache:
    def __init__(self, root: Path, identity: str | None = None):
        self.root = root.resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.identity = identity or compiler_identity()

    @contextmanager
    def entry(self, digest):
        key = sha256(json.dumps([digest, self.identity, FLAGS], separators=(',', ':')).encode()).hexdigest()
        with (self.root/(key+'.lock')).open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield key, self.root/key

    def restore(self, entry: Path, destination: Path):
        if not entry.exists(): return False
        metadata = json.loads((entry/'metadata.json').read_text())
        binary = entry/'bot'
        if binary.is_symlink() or not binary.is_file() or sha256(binary.read_bytes()).hexdigest() != metadata['binarySha256']:
            raise InfrastructureError('compiler cache corrupt; refusing the artifact')
        (destination/'build').mkdir()
        shutil.copy2(binary, destination/'build/bot')
        for name in ('compile.json', 'compile.stdout', 'compile.stderr'):
            shutil.copyfile(entry/name, destination/name)
        return True

    def publish(self, entry: Path, directory: Path):
        temporary = self.root/(entry.name+'.pending-'+uuid4().hex)
        temporary.mkdir()
        binary = directory/'build/bot'
        shutil.copy2(binary, temporary/'bot')
        for name in ('compile.json', 'compile.stdout', 'compile.stderr'):
            shutil.copyfile(directory/name, temporary/name)
        (temporary/'metadata.json').write_text(json.dumps({'binarySha256':sha256(binary.read_bytes()).hexdigest(),
            'compilerIdentity':self.identity, 'flags':FLAGS})+'\n')
        temporary.rename(entry)
