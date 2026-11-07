"""Bounded nonblocking pipe exchange for concurrently thinking sandboxed bots."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import selectors
import time

from .sandbox import Bot, Bubblewrap, CpuClock, InfrastructureError, STARTED, stop

MAX_BYTES = 64*1024


class Frame:
    """Keep a bounded raw prefix, but continue draining until a physical marker."""
    def __init__(self, marker: bytes):
        self.marker = marker
        self.raw = bytearray()
        self.line = bytearray()
        self.long = False
        self.done = False

    def feed(self, data: bytes) -> bytes:
        for i, byte in enumerate(data):
            if len(self.raw) <= MAX_BYTES:
                self.raw.append(byte)
            if byte == 10:
                text = self.line.removesuffix(b"\r")
                # Match the engine's whitespace/UTF-8 rules, not bytes.strip().
                decoded = text.decode("utf-8", errors="replace")
                if (not self.long and len(text) <= 256 and not any(c in decoded for c in "\r\x00\ufffd")
                        and decoded.split() == [self.marker.decode("ascii")]):
                    self.done = True
                    return data[i+1:]
                self.line.clear()
                self.long = False
            elif len(self.line) < 257:
                self.line.append(byte)
            else:
                self.long = True
        return b""

    def lines(self) -> list[str]:
        decoded = self.raw.decode("utf-8", errors="surrogateescape")
        # Each invalid byte becomes one forbidden ASCII NUL, not a three-byte
        # U+FFFD. The engine rejects that line while counting original bytes;
        # otherwise malformed text could consume the budget of later valid lines.
        text = "".join("\x00" if 0xDC80 <= ord(c) <= 0xDCFF else c for c in decoded)
        result = text.split("\n")
        if text.endswith("\n"):
            result.pop()
        return result


@dataclass
class Reply:
    lines: list[str]
    cpu_ns: int
    wall_ns: int
    fault: str | None
    clock: str

    def record(self):
        return asdict(self)


class Connection:
    def __init__(self, bot: Bot, launcher: Bubblewrap, cpu: int, cpu_seconds: int):
        self.bot = bot
        self.launched_ns = time.monotonic_ns()
        self.process = launcher.launch(bot.directory / "source", bot.directory / "sdk", bot.command, cpu,
                                       build=bot.directory / "build" if bot.language == "cpp" else None,
                                       cpu_seconds=cpu_seconds)
        assert self.process.stdin is not None and self.process.stdout is not None and self.process.stderr is not None
        self.stdin, self.stdout, self.error_stream = self.process.stdin, self.process.stdout, self.process.stderr
        for stream in (self.stdin, self.stdout, self.error_stream):
            os.set_blocking(stream.fileno(), False)
        self.clock = CpuClock(self.process.pid)
        self.pending = b""
        self.started = False
        self.handshake = Frame(STARTED.strip())
        self.stderr = bytearray()
        self.stderr_eof = False

    def close(self):
        stop(self.process, close_streams=False)
        try:
            while True:
                try:
                    data = os.read(self.error_stream.fileno(), 8192)
                except BlockingIOError:
                    break
                if not data:
                    break
                self.stderr.extend(data[:max(0, MAX_BYTES-len(self.stderr))])
        finally:
            for stream in (self.stdin, self.stdout, self.error_stream):
                stream.close()
        (self.bot.directory / "stderr.txt").write_bytes(self.stderr)


def exchange(connections: list[Connection], messages: list[list[str]], cpu_ms: list[float],
             wall_ms: list[float], marker: bytes = b"END") -> list[Reply]:
    """Send all messages without blocking, drain both streams, enforce each budget.

    The event loop performs bounded reads per fd so a flooding bot cannot starve
    its opponent. No unbounded readline()/communicate() on bot-owned pipes.
    """
    count = len(connections)
    frames = [Frame(marker) for _ in connections]
    outgoing = [memoryview(("\n".join(m)+"\n").encode()) for m in messages]
    starts = [c.launched_ns if marker == b"READY" else time.monotonic_ns() for c in connections]
    cpu_start = [0 if marker == b"READY" else c.clock.read_ns() for c in connections]
    replies: list[Reply | None] = [None] * count
    with selectors.DefaultSelector() as selector:
        for i, c in enumerate(connections):
            selector.register(c.stdin, selectors.EVENT_WRITE, (i, "in"))
            selector.register(c.stdout, selectors.EVENT_READ, (i, "out"))
            if not c.stderr_eof:
                selector.register(c.error_stream, selectors.EVENT_READ, (i, "err"))
            if c.pending:
                c.pending = frames[i].feed(c.pending)

        def unregister(stream):
            try:
                selector.unregister(stream)
            except KeyError:
                pass

        def finish(i, fault):
            c = connections[i]
            cpu = max(0, c.clock.read_ns()-cpu_start[i])
            wall = time.monotonic_ns()-starts[i]
            # Boundaries apply even when END and the timeout arrive together.
            if cpu > cpu_ms[i]*1_000_000:
                fault = "cpu_timeout"
            elif wall > wall_ms[i]*1_000_000:
                fault = "wall_timeout"
            if not c.started or c.process.poll() == 125:
                raise InfrastructureError("sandbox preparation failed (or exited 125); see attempt artifacts")
            replies[i] = Reply(frames[i].lines(), cpu, wall, fault,
                               "proc_stat" if c.clock.fallback else "process_cpu_clock")
            unregister(c.process.stdin)
            unregister(c.process.stdout)

        while any(r is None for r in replies):
            for i, c in enumerate(connections):
                if replies[i] is not None:
                    continue
                if frames[i].done:
                    finish(i, None)
                elif (c.clock.read_ns()-cpu_start[i] > cpu_ms[i]*1_000_000
                      or time.monotonic_ns()-starts[i] > wall_ms[i]*1_000_000):
                    finish(i, "timeout")
            if all(r is not None for r in replies):
                break
            for key, _ in selector.select(0.002):
                i, kind = key.data
                c = connections[i]
                if kind == "in":
                    if replies[i] is not None:
                        continue
                    try:
                        written = os.write(key.fd, outgoing[i][:8192])
                        outgoing[i] = outgoing[i][written:]
                        if not outgoing[i]:
                            unregister(key.fileobj)
                    except BrokenPipeError:
                        finish(i, "crash")
                    except BlockingIOError:
                        pass
                    continue
                try:
                    data = os.read(key.fd, 8192)
                except BlockingIOError:
                    continue
                if kind == "err":
                    c.stderr.extend(data[:max(0, MAX_BYTES-len(c.stderr))])
                    if not data:
                        c.stderr_eof = True
                        unregister(key.fileobj)
                    continue
                if replies[i] is not None:
                    continue
                if not data:
                    finish(i, "crash")
                    continue
                if not c.started:
                    data = c.handshake.feed(data)
                    if not c.handshake.done:
                        continue
                    c.started = True
                c.pending = frames[i].feed(data)
                if frames[i].done:
                    finish(i, None)
    return [r for r in replies if r is not None]
