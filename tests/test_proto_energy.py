import json
from pathlib import Path
import unittest

from arena.games.outpost import Outpost
from arena.games.outpost.model import Tower
from arena.games.outpost.rules import Rules, load_prototype
from tests.helpers import fixture_map, settle

ROOT = Path(__file__).resolve().parents[1]
PRICE = 'TOWER_ACTIVATION_COST'


class PaidTowerTests(unittest.TestCase):
    def setUp(self):
        self.game = Outpost()
        self.state = self.game.new_match(fixture_map(extra=[(7, 7, 'S')]), {PRICE: 4}, [17, 29])
        self.home, self.away = self.state.players
        self.site = (7, 7)
        self.another = (16, 16)
        self.add_tower(self.site)
        self.add_tower(self.another)

    def add_tower(self, pos, owner=0, hp=300):
        self.state.towers[pos] = Tower(owner, *pos, hp)

    def step(self, a=(), b=()):
        return settle(self.game, self.state, list(a), list(b))

    def test_named_ruleset_opt_in_and_strict_prices(self):
        prices = (2, 4, 8)
        for config, price in zip(('low', '', 'high'), prices, strict=True):
            suffix = f'-{config}' if config else ''
            path = ROOT/f'rules/proto-energy-1{suffix}.json'
            self.assertEqual(json.loads(path.read_text()), {PRICE: price})
            self.assertEqual(Rules.from_dict(load_prototype(path)).name, 'proto-energy-1')
        for invalid in (False, True, 0, -1, 201, 4.0, '4'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Rules.from_dict({PRICE: invalid})
        with self.assertRaises(ValueError):
            load_prototype(ROOT/'rules/standard-1.json')
        init = self.game.init_message(self.state, 0)
        self.assertIn('RULESET proto-energy-1', init)
        self.assertIn(f'PARAM {PRICE} 4', init)

    def test_standard_preserves_automatic_score_and_rejects_activation(self):
        self.state = self.game.new_match(fixture_map(), {}, [17, 29])
        self.add_tower(self.site)
        packet, warnings = self.game.parse_orders(self.state, 0, ['ACTIVATE 7 7'])
        self.assertEqual(packet.commands, ())
        self.assertEqual([(warning.line, warning.code) for warning in warnings], [(1, 'BAD_SYNTAX')])
        self.step()
        self.assertEqual(self.state.players[0].score, 1)
        self.assertEqual(self.state.players[0].energy, 500)
        self.assertNotIn(f'PARAM {PRICE} 4', self.game.init_message(self.state, 0))

    def test_no_instruction_no_score_and_partial_purchase_follows_reply_order(self):
        self.home.energy = 7
        self.step()
        self.assertEqual((self.home.energy, self.home.score), (7, 0))
        events = self.step(['ACTIVATE 16 16', 'ACTIVATE 7 7'])
        self.assertEqual((self.home.energy, self.home.score), (3, 1))
        self.assertEqual([(e.phase, e.kind, e.values) for e in events], [(9, 'ACTIVATED', (16, 16, 0, 4))])

    def test_duplicate_and_enemy_tower_rejected_only_on_their_lines(self):
        self.add_tower(self.another, owner=1)
        packet, warnings = self.game.parse_orders(self.state, 0, [
            'ACTIVATE 16 16', 'ACTIVATE 7 7', 'ACTIVATE 7 7', 'ACTIVATE 8 8'])
        self.assertEqual([o.to_line() for o in packet.commands], ['ACTIVATE 7 7'])
        self.assertEqual([(w.line, w.code) for w in warnings], [
            (1, 'NOT_OWN_TOWER'), (3, 'DUPLICATE'), (4, 'NOT_OWN_TOWER')])

    def test_spawns_deposits_builds_resolve_before_payment(self):
        self.state.units.clear()
        depot = self.state.add_unit(0, 'W', (7, 8))
        depot.carry = 3
        # The second site is empty at turn start; it can be built but not activated.
        self.state.towers.pop(self.another)
        builder = self.state.add_unit(0, 'W', (16, 15))
        self.assertEqual(self.state.map.terrain(self.another), 'S')
        self.home.energy = 40 + 150 + 1
        self.step(['SPAWN W 2 1', f'BUILD {builder.id} 16 16',
                   'ACTIVATE 7 7', 'ACTIVATE 16 16'])
        self.assertEqual((self.home.energy, self.home.score, self.home.deposited), (0, 1, 3))
        self.assertIn(self.another, self.state.towers)
        self.assertEqual(self.home.warnings, 1)

    def test_destroyed_tower_does_not_charge_even_if_other_towers_do(self):
        self.add_tower(self.site, hp=20)
        invader = self.state.add_unit(1, 'S', (7, 8))
        self.step(['ACTIVATE 7 7', 'ACTIVATE 16 16'], [f'ATTACK {invader.id} 7 7'])
        self.assertNotIn(self.site, self.state.towers)
        self.assertEqual((self.home.energy, self.home.score, self.home.warnings), (496, 1, 0))

    def test_base_destruction_still_ends_before_payment_and_scores(self):
        self.away.base_hp = 20
        ground = next(u.pos for u in self.state.units.values() if u.owner == 1)
        self.state.units = {u.id: u for u in self.state.units.values() if u.pos != ground}
        soldier = self.state.add_unit(0, 'S', ground)
        self.step(['ACTIVATE 7 7', f'ATTACK {soldier.id} {self.away.x} {self.away.y}'])
        self.assertEqual((self.home.energy, self.home.score), (500, 0))
        self.assertEqual(self.state.outcome.reason, 'base_destroyed')

    def test_final_round_uses_existing_score_then_deposit_tiebreaks(self):
        self.add_tower(self.another, owner=1)
        self.home.deposited = 1
        self.state.turn = 299
        self.step(['ACTIVATE 7 7'], ['ACTIVATE 16 16'])
        self.assertEqual(self.state.outcome.scores, (1, 1))
        self.assertEqual((self.state.outcome.winner, self.state.outcome.reason), (0, 'turn_limit_deposit'))
