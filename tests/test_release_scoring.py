import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from arena.grade import grade, grading_lock
from arena.ladder import Ladder, Member
from arena.scoring import Config, fixed_elo, load_config, raw_game, summarize
from arena.scrimmage import loss_priority
from arena.tournament import run_tournament
from tools.prepare_author_workspace import build, smoke

ROOT=Path(__file__).resolve().parents[1]
P1=Config(.25,{'tower':.4,'deposit':.3,'damage':.3})


class ReleaseScoring(unittest.TestCase):
    def setup_ladder(self):
        a=Member('a',Path('a'),'a','cpp',0,tuple(range(7)))
        b=Member('b',Path('b'),'b','cpp',100,tuple(range(7,14)))
        c=Member('c',Path('c'),'c','cpp',200,tuple(range(14,21)))
        return Ladder('1.0.0',((a,b),(c,)),(17,29),(),{'gaps':[150]})

    def test_level_weights_and_map_cluster_interval(self):
        ladder=self.setup_ladder()
        results={'a':{'winner':0},'b':{'winner':1},'c':{'winner':0}}
        games=[]
        for m in ladder.members:
            for slot in m.slots:
                for seat in (0,1):
                    w=results[m.code]['winner']; tied=.5 if w is None else float(w)
                    result={'winner':seat if w==0 else 1-seat,'reason':'turn_limit_score','scores':[0,0],
                            'deposited':[0,0],'damageEffective':[0,0],'faults':[None,None],'warnings':[0,0],'turns':300}
                    row=raw_game(m.code,slot,seat,result,300)
                    self.assertEqual(row['outcome'],1-tied)
                    games.append(row)
        r=summarize(games,ladder,P1,samples=100)
        self.assertEqual((r['games'],r['headlineOutcomeOnly'],r['highestHalfLevel']),(42,.75,'L1'))
        self.assertEqual(r['outcomeInterval95'],[.75,.75])
        self.assertEqual(r['headline'],.6875)
        incomplete=summarize(games[:-1],ladder,P1,samples=10)
        self.assertEqual(incomplete['infraErrors'],1)
        self.assertIsNone(incomplete['headline']); self.assertIsNone(incomplete['headlineOutcomeOnly'])
        self.assertEqual(incomplete['levels'][1]['games'],13)
        with self.assertRaises(ValueError): summarize(games+[games[0]],ladder,P1,samples=10)

    def test_fixed_elo_keeps_separation_and_does_not_change_opponent_ratings(self):
        self.assertEqual(fixed_elo([(100,14,0)]),'-infinity')
        self.assertEqual(fixed_elo([(100,14,14)]),'+infinity')
        self.assertAlmostEqual(fixed_elo([(100,14,7)]),100,places=5)
        self.assertAlmostEqual(fixed_elo([(10,5,3),(210,5,2)]),110,places=5)

    def test_grade_report_uses_the_config_metadata_and_actual_lock_directory(self):
        shipped = load_config(ROOT/'arena/scoring.json')
        self.assertEqual((shipped.proposal, shipped.status), ('P1', 'frozen for ladder 1.0.0 (user 2026-11-26)'))
        self.assertEqual((shipped.weight, shipped.metrics), (P1.weight, P1.metrics))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            out, locks = root/'private/grade.json', root/'locks'
            cfg = root/'scoring.json'
            data = json.loads((ROOT/'arena/scoring.json').read_bytes())
            data.update(proposal='fixture', status='fixture status')
            cfg.write_text(json.dumps(data))
            timing = SimpleNamespace(sandbox='bwrap', locked_budget={}, lock_sha256='fixture', factor=1)
            with (patch('arena.grade.ROOT', root), patch('arena.grade.load_ladder', return_value=self.setup_ladder()),
                  patch('arena.grade.checked_maps', return_value=()), patch('arena.grade.Calibration.load', return_value=timing),
                  patch('arena.grade.run_tournament', return_value={'infraErrorAttempts': 0}),
                  patch('arena.grade.gather', return_value=[]), patch.dict(os.environ, HRW_LOCK_DIR=str(locks))):
                result = grade(root/'bot', root/'ladder.json', root/'maps', out,
                               fixed_timing=root/'timing.json', config_path=cfg)
            self.assertEqual(json.loads(out.read_bytes()), result)
            self.assertEqual((result['scoringProposal'], result['scoringStatus'], result['lockDirectory']),
                             ('fixture', 'fixture status', str(locks)))

    def test_practice_loss_order(self):
        events=[{'game':1,'outcome':'loss','ending':'turn_limit_score','turns':300,'seat':1,'towerScore':[300,5]},
                {'game':2,'outcome':'loss','ending':'base_destroyed','turns':99,'seat':0,'towerScore':[5,13]},
                {'game':3,'outcome':'loss','ending':'base_destroyed','turns':55,'seat':1,'towerScore':[10,3]},
                {'game':4,'outcome':'loss','ending':'turn_limit_score','turns':300,'seat':1,'towerScore':[6,5]}]
        self.assertEqual([g['game'] for g in sorted(events,key=loss_priority)],[3,2,1,4])

    def test_second_grade_waits_for_first(self):
        attempting=threading.Event(); acquired=threading.Event()
        def second():
            attempting.set()
            with grading_lock(): acquired.set()
        with grading_lock():
            thread=threading.Thread(target=second)
            thread.start()
            self.assertTrue(attempting.wait(2))
            self.assertFalse(acquired.wait(.1))
        thread.join(2)
        self.assertTrue(acquired.is_set())

    def test_tournament_only_assigns_each_pair_its_fixed_maps(self):
        with TemporaryDirectory() as t:
            t=Path(t); dst=t/'plan'
            sources=[ROOT/'bots/public'/c for c in ('Z-idle','Z-eco','Z-harass')]
            maps=[ROOT/'maps/public'/f'open-{i:02}.map' for i in range(1,4)]
            r=run_tournament(sources,maps,dst,jobs=1,pairings=[(0,2),(0,1)],pair_maps={(0,1):(2,),(0,2):(0,1)},
                             submission_index=0,max_tasks=0)
            tasks=json.loads((dst/'manifest.json').read_bytes())['tasks']
            self.assertEqual(r['tasks'],6)
            self.assertEqual([(x['players'],x['mapIndex'],x['seeds']) for x in tasks],
                [([0,1],2,[17,29]),([1,0],2,[29,17]),([0,2],0,[17,29]),([2,0],0,[29,17]),
                 ([0,2],1,[17,29]),([2,0],1,[29,17])])
            with self.assertRaises(ValueError):
                run_tournament(sources,maps,t/'bad',jobs=1,pairings=[(0,1)],pair_maps={(0,1):(0,0)},max_tasks=0)

    def test_release_export_is_public_scrimmage_without_grading_implementation(self):
        with TemporaryDirectory() as t:
            out=Path(t)/'release'
            r=build(out,'release')
            self.assertTrue(r['onlyDeclaredPublicMaterials'])
            for p in ('private','reports','arena/grade.py','arena/scoring.json','arena/scoring.py',
                      'arena/ladder.py','arena/calibrate.py','bots/prototypes','rules/proto-ranged-1.json'):
                self.assertFalse((out/p).exists(),p)
            self.assertTrue((out/'arena/scrimmage.py').exists())
            self.assertTrue((out/'TASK-PHASE1.md').exists() and (out/'TASK-PHASE2.md').exists())
            self.assertEqual(smoke(out)['compileExecutions'],0)
