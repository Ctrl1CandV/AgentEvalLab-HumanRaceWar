"""Outpost replay adapter. Verification executes engine actions, never bots."""
from __future__ import annotations

from dataclasses import asdict
import gzip
from hashlib import sha256
import json
from pathlib import Path

from arena import __version__
from arena.core.replay import ReplayError, normalized
from arena.games.outpost import Outpost
from arena.games.outpost.metrics import Metrics


def invalid_events(state):
    return [asdict(e) for e in state.last_events if e.kind == "INVALID"]


def outcome(game, state, faults=None):
    if faults is None:
        result = game.result(state)
        if result is None:
            raise ReplayError("missing terminal game result")
        result = asdict(result)
    else:
        survivors = [p for p, fault in enumerate(faults) if not fault]
        result = {"winner": survivors[0] if len(survivors) == 1 else None,
                  "reason": "bot_fault", "turns": state.turn,
                  "scores": [p.score for p in state.players], "deposited": [p.deposited for p in state.players],
                  "base_hp": [p.base_hp for p in state.players]}
    return normalized({**result, "faults": faults or [None]*len(state.players),
                       "timeouts": [int(bool(f and "timeout" in f)) for f in (faults or [None]*len(state.players))],
                       "warnings": [p.warnings for p in state.players],
                       "damageDealt": [p.damage_dealt for p in state.players]})


def verify(path: Path, show_turn: int | None = None) -> dict:
    """Validate transcript/accepted orders/events/hashes/result, not timing truth.

    Unknown additive fields are ignored. Missing/duplicate terminal records,
    truncated gzip, altered rules/map/actions/results are rejected.
    """
    try:
        return _verify(path, show_turn)
    except (OSError, EOFError, ValueError, KeyError, TypeError, IndexError) as error:
        raise ReplayError(f"invalid replay: {error}") from error


def _verify(path: Path, show_turn: int | None) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        # Bound decoded record size as well as total number of records.
        def read_record():
            raw = stream.readline(2*1024*1024+1)
            if len(raw) > 2*1024*1024:
                raise ReplayError("record too large")
            if not raw:
                return None
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ReplayError("record must be an object")
            return value

        header = read_record()
        if header is None:
            raise ReplayError("empty replay")
        if (header["type"] != "header" or header["replayVersion"] != 1 or header["game"] != "outpost"
                or header["engineVersion"] != __version__):
            raise ReplayError("unsupported replay/engine/game version")
        if sha256(header["map"].encode()).hexdigest() != header["mapSha256"]:
            raise ReplayError("map digest mismatch")
        game = Outpost(header["limits"])
        state = game.new_match(header["map"], header["params"], header["seeds"])
        if header.get("metricsVersion", 1) not in (1, 2):
            raise ReplayError("unsupported metrics version")
        metrics = Metrics(state) if header.get("metricsVersion", 1) == 2 else None
        if game.state_hash(state) != header["initialStateHash"] or header["ruleset"] != state.rules.name:
            raise ReplayError("initial state mismatch")
        faults = header.get("compileFaults")
        if not faults or not any(faults):
            faults = None
        initialized = False
        terminal = False
        result = None
        summaries = []
        board = game.render(state) if show_turn == 0 else None
        for _ in range(state.rules["TURNS"]+4):
            row = read_record()
            if row is None:
                break
            if terminal:
                raise ReplayError("data after result")
            kind = row["type"]
            if kind == "init":
                if initialized or state.turn or faults:
                    raise ReplayError("unexpected init record")
                initialized = True
                if len(row["replies"]) != len(state.players):
                    raise ReplayError("wrong init player count")
                fs = [r["fault"] for r in row["replies"]]
                faults = fs if any(fs) else None
            elif kind in ("turn", "fault"):
                if not initialized or faults or game.result(state) is not None or row["turn"] != state.turn+1:
                    raise ReplayError("unexpected turn/fault")
                if len(row["replies"]) != len(state.players):
                    raise ReplayError("wrong turn player count")
                fs = [r["fault"] for r in row["replies"]]
                if kind == "fault":
                    if not any(fs):
                        raise ReplayError("fault without faults")
                    faults = fs
                else:
                    if any(fs):
                        raise ReplayError("settled a faulting turn")
                    packets = [game.parse_orders(state, p, r["lines"])[0] for p, r in enumerate(row["replies"])]
                    accepted = [[asdict(o) for o in p.commands] for p in packets]
                    if normalized(accepted) != row["accepted"]:
                        raise ReplayError("accepted orders mismatch")
                    game.step(state, packets)
                    if metrics is not None:
                        metrics.observe(state, packets)
                    if normalized(invalid_events(state)) != row["invalid"]:
                        raise ReplayError("invalid orders mismatch")
                    if show_turn == state.turn:
                        board = game.render(state)
                    if state.turn % 25 == 0 or game.result(state) is not None:
                        summaries.append({"turn": state.turn, "players": [
                            {"energy": p.energy, "score": p.score,
                             "units": sum(u.owner == p.id for u in state.units.values()),
                             "towers": sum(t.owner == p.id for t in state.towers.values())} for p in state.players]})
            elif kind == "result":
                result = outcome(game, state, faults)
                if metrics is not None:
                    result.update(metrics.result())
                if row["result"] != result:
                    raise ReplayError("result mismatch")
                terminal = True
            else:
                raise ReplayError("unexpected record type")
            if row["stateHash"] != game.state_hash(state):
                raise ReplayError(f"state hash mismatch after turn {state.turn}")
        else:
            raise ReplayError("too many replay records")
        if not terminal:
            raise ReplayError("incomplete replay (no result)")
        if show_turn is not None and board is None:
            raise ReplayError("requested turn not present")
        return {"verified": True, "turns": state.turn, "result": result, "summary": summaries, "board": board}
