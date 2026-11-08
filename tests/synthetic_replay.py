"""Generate a small legacy-format fixture locally; never execute a bot.

The orders and terminal result are synthetic test inputs, not evidence from an
experiment. No real game replay is required by a fresh checkout.
"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from arena import __version__
from arena.core.replay import Writer, normalized
from arena.games.outpost import Outpost
from arena.games.outpost.replay import invalid_events
from tests.helpers import STARTING_RULES, fixture_map


def legacy_replay(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = fixture_map()
    game = Outpost()
    state = game.new_match(text, STARTING_RULES, [17, 29])
    writer = Writer(path)
    try:
        writer.write({'type': 'header', 'replayVersion': 1, 'game': 'outpost',
                      'engineVersion': __version__, 'map': text,
                      'mapSha256': sha256(text.encode()).hexdigest(), 'limits': {},
                      'params': STARTING_RULES, 'seeds': [17, 29],
                      'initialStateHash': game.state_hash(state), 'ruleset': 'standard-1',
                      'fixture': 'synthetic; no bots, timings or experiment results'})
        writer.write({'type': 'init', 'replies': [{'fault': None}, {'fault': None}],
                      'stateHash': game.state_hash(state)})
        for turn in range(1, 301):
            replies = [{'lines': ['SPAWN S 2 4'] if turn == 1 else [], 'fault': None},
                       {'lines': [], 'fault': None}]
            packets = [game.parse_orders(state, p, r['lines'])[0] for p, r in enumerate(replies)]
            accepted = normalized([[asdict(order) for order in packet.commands] for packet in packets])
            game.step(state, packets)
            writer.write({'type': 'turn', 'turn': turn, 'replies': replies,
                          'accepted': accepted, 'invalid': normalized(invalid_events(state)),
                          'stateHash': game.state_hash(state)})
        # Pin the old result schema independently of the current replay adapter.
        writer.write({'type': 'result', 'stateHash': game.state_hash(state), 'result': {
            'winner': None, 'reason': 'turn_limit_draw', 'turns': 300,
            'scores': [0, 0], 'deposited': [0, 0], 'base_hp': [1000, 1000],
            'faults': [None, None], 'timeouts': [0, 0], 'warnings': [0, 0],
            'damageDealt': [0, 0],
        }})
    finally:
        writer.close()
    return path
