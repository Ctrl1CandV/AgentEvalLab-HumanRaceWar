"""Locked, fsynced JSONL. Torn tails are archived before recovery, never hidden."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
from uuid import uuid4


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0, 2)
        size = stream.tell()
        if size:
            stream.seek(size-1)
            if stream.read(1) != b'\n':
                # A killed writer may leave an incomplete last record. Preserve
                # its exact bytes, then remove only that uncommitted suffix.
                stream.seek(0)
                raw = stream.read()
                end = raw.rfind(b'\n')+1
                tail = path.with_name(path.name+'.torn-'+uuid4().hex)
                with tail.open('xb') as out:
                    out.write(raw[end:]); out.flush(); os.fsync(out.fileno())
                stream.truncate(end); stream.flush(); os.fsync(stream.fileno())
        yield stream


def append(path: Path, row: dict):
    data = (json.dumps(row, ensure_ascii=True, separators=(',', ':'))+'\n').encode()
    with locked(path) as stream:
        stream.seek(0, 2); stream.write(data); stream.flush(); os.fsync(stream.fileno())


def records(path: Path):
    if not path.exists(): return []
    with locked(path) as stream:
        stream.seek(0)
        return [json.loads(line) for line in stream]


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp-'+uuid4().hex)
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
