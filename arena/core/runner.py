"""Game-independent protocol lifecycle; launches are already sandboxed."""
from __future__ import annotations

import math
import time

from .transport import exchange


def run(game, state, connections, limits: dict[str, int], record_turn, *, wall_margin_ms: int = 500, overheads=None):
    count = len(connections)
    bank = [limits["BANK_MS"]*1_000_000 for _ in connections]
    replies = exchange(connections, [game.init_message(state, p) for p in range(count)],
                       [limits["INIT_CPU_MS"]]*count, [limits["INIT_CPU_MS"]+wall_margin_ms]*count, b"READY")
    record_turn("init", replies, None, bank)
    if any(r.fault for r in replies):
        return replies
    while game.result(state) is None:
        start_cpu = time.process_time_ns()
        messages = []
        for player in range(count):
            # BANK belongs to the runner, not deterministic game state.
            lines = game.observation(state, player)
            messages.append([f"BANK {bank[player] // 1_000_000}" if line.startswith("BANK ") else line
                             for line in lines])
        allowed = [limits["TURN_CPU_MS"] + b/1_000_000 for b in bank]
        replies = exchange(connections, messages, allowed, [v+wall_margin_ms for v in allowed])
        for p, reply in enumerate(replies):
            bank[p] -= max(0, reply.cpu_ns-limits["TURN_CPU_MS"]*1_000_000)
        if any(r.fault for r in replies):
            record_turn("fault", replies, None, bank)
            return replies
        packets = [game.parse_orders(state, p, reply.lines)[0] for p, reply in enumerate(replies)]
        game.step(state, packets)
        record_turn("turn", replies, packets, bank)
        if overheads is not None:
            overheads.append(time.process_time_ns()-start_cpu)
    return None


def cpu_hard_limit(limits: dict[str, int], turns: int, speed_factor: float = 1.0) -> int:
    return math.ceil((limits["INIT_CPU_MS"]+limits["BANK_MS"]+turns*limits["TURN_CPU_MS"])/1000
                     + 5*speed_factor)
