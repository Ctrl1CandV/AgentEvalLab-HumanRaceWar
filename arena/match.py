"""Outpost match orchestration; generic lifecycle and sandboxing live in core."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import traceback
from uuid import uuid4

from arena import __version__
from arena.core.replay import Writer
from arena.core.runner import cpu_hard_limit, run
from arena.core.sandbox import Bubblewrap, InfrastructureError, prepare
from arena.core.transport import Connection
from arena.games.outpost import Outpost
from arena.games.outpost.replay import invalid_events, outcome


def append_result(path: Path, row: dict):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=True)+"\n")
        stream.flush()
        os.fsync(stream.fileno())


def play(sources: list[Path], map_text: str, out: Path, seeds: list[int], *, limits=None,
         retries: int = 3) -> dict:
    game = Outpost(limits)
    # Validate user inputs before allocating an attempted game.
    initial = game.new_match(map_text, {}, seeds)
    if len(sources) != len(initial.players):
        raise ValueError("one bot per player required")
    if not 0 <= retries <= 3:
        raise ValueError("retries must be between zero and three")
    sources = [p.absolute() for p in sources]
    out = out.resolve()
    private = Path(__file__).resolve().parents[1] / "private"
    if any(p.resolve().is_relative_to(private) for p in sources) and not out.is_relative_to(private):
        raise ValueError("hidden bot artifacts must stay under private/")
    run_id = uuid4().hex
    directory = out / run_id
    directory.mkdir(parents=True, exist_ok=False)
    last = None
    for attempt in range(retries+1):
        work = directory / f"attempt-{attempt}"
        work.mkdir()
        connections = []
        writer = None
        row = {"matchId": run_id, "attempt": attempt, "directory": str(work), "status": "infra_error"}
        try:
            launcher = Bubblewrap()
            if len(launcher.cpus) < len(sources):
                raise InfrastructureError("not enough distinct CPUs for this match")
            bots = [prepare(source, work / f"p{p}", launcher, launcher.cpus[p]) for p, source in enumerate(sources)]
            if any(bot.compile_fault and source.resolve().is_relative_to(private)
                   for bot, source in zip(bots, sources)):
                raise ValueError("hidden ladder bot is invalid; see private attempt artifacts")
            state = game.new_match(map_text, {}, seeds)
            replay = work / f"{run_id}.hrw.jsonl.gz"
            writer = Writer(replay)
            compile_faults = [b.compile_fault for b in bots]
            writer.write({"type": "header", "replayVersion": 1, "engineVersion": __version__, "game": game.id,
                "ruleset": state.rules.name, "params": dict(state.rules.values), "map": map_text,
                "mapSha256": sha256(map_text.encode()).hexdigest(),
                "bots": [{"code": b.code, "sha256": b.digest, "language": b.language,
                          "validationError": b.validation_error} for b in bots],
                "seeds": seeds, "limits": game.limits, "speedFactor": None,
                "timingCalibration": "unscaled development limits; benchmark pending",
                "startedAt": datetime.now(timezone.utc).isoformat(), "sandbox": "bwrap",
                "runtimePolicy": {"version": 2, "singleProcess": True, "maxThreads": 16,
                                  "tmp": "read-only", "cpuAccounting": "READY/END cumulative differences"},
                "cpus": launcher.cpus[:len(sources)], "compileFaults": compile_faults,
                "initialStateHash": game.state_hash(state)})
            faults = compile_faults if any(compile_faults) else None

            def record(kind, replies, packets, bank):
                assert writer is not None
                record = {"type": kind, "turn": state.turn if kind == "turn" else state.turn+1,
                          "replies": [r.record() for r in replies], "bankNs": bank,
                          "stateHash": game.state_hash(state)}
                if packets is not None:
                    record["accepted"] = [[asdict(o) for o in p.commands] for p in packets]
                    record["invalid"] = invalid_events(state)
                writer.write(record)

            if faults is None:
                for p, bot in enumerate(bots):
                    connections.append(Connection(bot, launcher, launcher.cpus[p], cpu_hard_limit(game.limits, state.rules["TURNS"])))
                failed = run(game, state, connections, game.limits, record)
                faults = [r.fault for r in failed] if failed is not None else None
            result = outcome(game, state, faults)
            writer.write({"type": "result", "result": result, "stateHash": game.state_hash(state)})
            row.update(status="complete", result=result, replay=str(replay))
        except Exception as error:
            # Preserve partial streams and failures. No bot earns a win from a
            # framework exception. Configuration errors are not silently retried.
            row["error"] = type(error).__name__
            (work / "error.log").write_text(traceback.format_exc())
            if writer is not None:
                writer.write({"type": "infrastructure_error", "error": type(error).__name__})
            if isinstance(error, ValueError) and not isinstance(error, InfrastructureError):
                row["status"] = "configuration_error"
        finally:
            for connection in connections:
                connection.close()
            if writer is not None:
                writer.close()
            (work / "result.json").write_text(json.dumps(row, indent=2)+"\n")
            append_result(directory / "results.jsonl", row)
        last = row
        if row["status"] != "infra_error":
            break
    assert last is not None
    return last
