"""Replay-derived raw diagnostics. No scoring formula or state-hash changes."""
from collections import defaultdict


class Metrics:
    def __init__(self, state):
        n = len(state.players)
        self.warnings = [0]*n
        self.failed = [0]*n
        self.moves = [0]*n
        self.contested = [0]*n
        self.effective = [0]*n
        self.contested_sites = 0
        self.remember(state)

    def remember(self, state):
        self.hp = {('U', u.owner, u.id, u.x, u.y): u.hp for u in state.units.values()}
        self.hp.update({('T', t.owner, -1, t.x, t.y): t.hp for t in state.towers.values()})
        self.hp.update({('B', p.id, -1, p.x, p.y): p.base_hp for p in state.players})

    def observe(self, state, packets):
        hits = defaultdict(int)
        sites = set()
        by_line = [{o.line: o for o in p.commands} for p in packets]
        for event in state.last_events:
            if event.kind == 'DAMAGE':
                attacker, _, kind, owner, uid, x, y, damage, _ = event.values
                hits[(attacker, kind, owner, uid, x, y)] += damage
            elif event.kind == 'INVALID':
                phase, line, code = event.values
                player = event.audience
                assert player is not None
                if phase == 1:
                    self.warnings[player] += 1
                else:
                    self.failed[player] += 1
                    self.moves[player] += int(phase == 4)
                if code == 'BUILD_CONTESTED':
                    self.contested[player] += 1
                    sites.add(by_line[player][line].pos)
        # Outpost is two-player: every hostile hit on a target has one owner.
        for (attacker, *target), amount in hits.items():
            self.effective[attacker] += min(self.hp[tuple(target)], amount)
        self.contested_sites += len(sites)
        self.remember(state)

    def result(self):
        return {'warnings': self.warnings, 'failedOrders': self.failed, 'failedMoves': self.moves,
                'buildContested': self.contested, 'buildContestedSites': self.contested_sites,
                'damageEffective': self.effective}
