"""Game-independent append-only gzip JSONL output and replay errors."""
import gzip
import json
import os
from pathlib import Path


class ReplayError(ValueError):
    pass


def normalized(value):
    return json.loads(json.dumps(value, ensure_ascii=True))


class Writer:
    def __init__(self, path: Path):
        # Exclusive creation: prior attempts must never be silently overwritten.
        self.raw = path.open("xb")
        self.stream = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, mtime=0)

    def write(self, record: dict):
        self.stream.write((json.dumps(record, ensure_ascii=True, separators=(",", ":"))+"\n").encode())
        self.stream.flush()
        self.raw.flush()

    def close(self):
        self.stream.close()
        self.raw.flush()
        os.fsync(self.raw.fileno())
        self.raw.close()
