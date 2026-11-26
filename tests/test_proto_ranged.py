from pathlib import Path
import unittest

from arena.games.outpost import Outpost
from arena.games.outpost.rules import Rules, load_prototype
from tests.helpers import fixture_map, settle

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT/'rules/proto-ranged-1.json'


class RangedPrototypeTests(unittest.TestCase):
    def start(self, extra=(), *, prototype=True):
        self.game = Outpost()
        self.state = self.game.new_match(fixture_map(extra=extra), load_prototype(RULES) if prototype else {}, [17,29])
        self.state.units.clear()
        self.home, self.away = self.state.players

    def parse(self, a):
        return self.game.parse_orders(self.state, 0, a)

    def step(self, a, b=None):
        return settle(self.game, self.state, a, b or [])

    def test_opt_in_and_no_combining_rulesets(self):
        rules = load_prototype(RULES)
        self.assertEqual(Rules.from_dict(rules).name, 'proto-ranged-1')
        with self.assertRaises(ValueError):
            Rules.from_dict({**rules, 'TOWER_ACTIVATION_COST':4})
        with self.assertRaises(ValueError):
            Rules.from_dict({'RANGED_COST':100})
        self.start(prototype=False)
        _, warnings = self.parse(['UNLOCK R', 'SPAWN R 2 1'])
        self.assertEqual([w.code for w in warnings], ['BAD_SYNTAX','BAD_UNIT_TYPE'])
        self.assertFalse(any(s.startswith('TECH ') for s in self.game.observation(self.state,0)))
        self.assertNotIn('rangedPlayers', self.game.snapshot(self.state))

    def test_unlock_is_public_one_time_and_consumes_production_but_not_fire(self):
        self.start()
        self.state.add_unit(1,'W',(2,3))
        _, warnings = self.parse(['SPAWN R 2 1'])
        self.assertEqual([w.code for w in warnings], ['TECH_LOCKED'])
        events = self.step(['UNLOCK R','SPAWN W 2 1','FIRE 2 3'])
        self.assertIn('TECH 0 R 1',self.game.observation(self.state,1))
        self.assertIn('TECH 1 R 0',self.game.observation(self.state,0))
        self.assertIn((3,'UNLOCKED',(0,'R')),[(e.phase,e.kind,e.values) for e in events])
        self.assertEqual(self.home.energy,340)
        self.assertEqual(len(self.state.units),1)
        self.assertEqual(next(iter(self.state.units.values())).hp,50)
        self.assertEqual(self.game.snapshot(self.state)['rangedPlayers'],[0])
        self.step(['SPAWN R 2 1'])
        self.assertEqual(self.home.energy,240)
        self.assertEqual([(u.kind,u.hp) for u in self.state.units.values() if u.owner == 0],[('R',60)])
        _, repeat = self.parse(['UNLOCK R'])
        self.assertEqual([w.code for w in repeat],['ALREADY_UNLOCKED'])

    def test_base_death_preempts_unlock_and_joint_attack_is_simultaneous(self):
        self.start()
        self.home.base_hp = 20
        unit = self.state.add_unit(1,'S',(2,3))
        self.step(['UNLOCK R'],[f'ATTACK {unit.id} 2 2'])
        self.assertEqual(self.game.result(self.state).winner,1)
        self.assertEqual((self.home.energy,self.state.ranged_players),(500,set()))
        self.start()
        a = self.state.add_unit(0,'R',(4,4))
        b = self.state.add_unit(1,'R',(6,4))
        a.hp = b.hp = 15
        self.step([f'ATTACK {a.id} 6 4'],[f'ATTACK {b.id} 4 4'])
        self.assertEqual(self.state.units,{})

    def test_two_step_shots_respect_terrain_and_melee_stays_adjacent(self):
        self.start(extra=[(5,4,'#')])
        a = self.state.add_unit(0,'R',(4,4))
        other = self.state.add_unit(1,'W',(6,4))
        _, warnings = self.parse([f'ATTACK {a.id} 6 4'])
        self.assertEqual([w.code for w in warnings],['RANGE_BLOCKED'])
        other.x, other.y=5,5
        obstruction = self.state.add_unit(0,'S',(4,5))
        self.step([f'ATTACK {a.id} 5 5'])
        self.assertEqual(other.hp,45)  # The open path through (4,5) is occupied, not blocked.
        self.state.units.pop(obstruction.id)
        melee = self.state.add_unit(0,'S',(3,5))
        _, warnings = self.parse([f'ATTACK {melee.id} 5 5'])
        self.assertEqual([w.code for w in warnings],['NOT_ADJACENT'])

    def test_tower_scoring_does_not_require_energy(self):
        self.start()
        builder = self.state.add_unit(0,'W',(10,9))
        self.step([f'BUILD {builder.id} 10 8'])
        self.assertEqual((self.home.score,self.home.energy),(1,350))
        self.step([])
        self.assertEqual((self.home.score,self.home.energy),(2,350))
