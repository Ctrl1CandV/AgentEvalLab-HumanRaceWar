"""Raw metrics, global CPU leases, cache, checks and resumable batches."""
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.check import check
from arena.core.cache import CompileCache
from arena.core.journal import append, records
from arena.core.plain import Plain
from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, InfrastructureError, prepare
from arena.games.outpost.metrics import Metrics
from arena.games.outpost.replay import verify
from arena.tournament import run_tournament
from tests.helpers import fresh, settle
from tools.test_outer_plain import run as outer_plain

ROOT=Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ROOT/'runs/development/platform-tests'/uuid4().hex
        cls.root.mkdir(parents=True)

    def test_raw_metrics_split_failures_and_cap_overkill_without_changing_state(self):
        game,state=fresh()
        target=state.add_unit(1,'W',(7,7)); target.hp=1
        troops=[state.add_unit(0,'S',pos) for pos in ((6,7),(8,7),(7,6),(7,8))]
        metrics=Metrics(state)
        packets=[game.parse_orders(state,0,[f'ATTACK {u.id} 7 7' for u in troops]+['NONSENSE'])[0],
                 game.parse_orders(state,1,[])[0]]
        game.step(state,packets); before=game.state_hash(state); metrics.observe(state,packets)
        self.assertEqual(game.state_hash(state),before)
        self.assertEqual(state.players[0].damage_dealt,80)
        self.assertEqual(metrics.result()['damageEffective'],[1,0])
        self.assertEqual(metrics.result()['warnings'],[1,0])
        game,state=fresh()
        a=state.add_unit(0,'W',(5,5)); state.add_unit(0,'W',(6,5))
        metrics=Metrics(state)
        packets=[game.parse_orders(state,0,[f'MOVE {a.id} E'])[0],game.parse_orders(state,1,[])[0]]
        game.step(state,packets); metrics.observe(state,packets)
        self.assertEqual(metrics.result()['failedMoves'],[1,0])
        self.assertEqual(metrics.result()['failedOrders'],[1,0])
        self.assertEqual(metrics.result()['warnings'],[0,0])

    def test_contested_site_counts_events_and_unique_site_separately(self):
        game,state=fresh(extra=[(5,5,'S')])
        a=state.add_unit(0,'W',(4,5)); b=state.add_unit(1,'W',(6,5))
        metrics=Metrics(state)
        packets=[game.parse_orders(state,p,[f'BUILD {u.id} 5 5'])[0] for p,u in enumerate((a,b))]
        game.step(state,packets); metrics.observe(state,packets)
        self.assertEqual(metrics.result()['buildContested'],[1,1])
        self.assertEqual(metrics.result()['buildContestedSites'],1)

    def test_leases_exclude_busy_cpus_and_restore_affinity_on_exception(self):
        mask=os.sched_getaffinity(0)
        with self.assertRaisesRegex(RuntimeError,'test exit'):
            with CpuLease(1) as lease:
                self.assertFalse(set(lease.cpus)&set(lease.runners))
                self.assertEqual(os.sched_getaffinity(0),set(lease.runners))
                os.sched_setaffinity(0,mask)
                with self.assertRaises(InfrastructureError): CpuLease(1,exact=lease.cpus,timeout=0)
                raise RuntimeError('test exit')
        self.assertEqual(os.sched_getaffinity(0),mask)
        with CpuLease(1): pass

    def test_journal_recovers_torn_tail_without_losing_evidence(self):
        path=self.root/'torn.jsonl'
        append(path,{'task':'done'})
        with path.open('ab') as f: f.write(b'{"task":"interrupted')
        append(path,{'task':'next'})
        self.assertEqual(records(path),[{'task':'done'},{'task':'next'}])
        tails=list(path.parent.glob(path.name+'.torn-*'))
        self.assertEqual(len(tails),1)
        self.assertEqual(tails[0].read_bytes(),b'{"task":"interrupted')
        with path.open('ab') as f: f.write(b'not json\n')
        with self.assertRaises(ValueError): records(path)

    def test_cpp_cache_hits_and_corruption_is_not_silently_used(self):
        cache=CompileCache(self.root/'cache')
        with CpuLease(1) as lease:
            launcher=Bubblewrap(); launcher.cpus=lease.cpus
            first=prepare(ROOT/'sdk/cpp/example',self.root/'compile1',launcher,lease.cpus[0],cache=cache)
            self.assertIsNone(first.compile_fault)
            with patch.object(launcher,'launch',side_effect=AssertionError('cache must not compile')):
                second=prepare(ROOT/'sdk/cpp/example',self.root/'compile2',launcher,lease.cpus[0],cache=cache)
            self.assertEqual(first.digest,second.digest)
            self.assertTrue(json.loads((second.directory/'cache.json').read_text())['hit'])
            metadata=json.loads((first.directory/'cache.json').read_text())
            (cache.root/metadata['key']/'bot').write_bytes(b'corrupt')
            with self.assertRaises(InfrastructureError):
                prepare(ROOT/'sdk/cpp/example',self.root/'compile3',launcher,lease.cpus[0],cache=cache)

    def test_check_valid_and_invalid_sources_and_plain_refuses_this_host(self):
        row=check(ROOT/'sdk/python/example',self.root/'checks')
        self.assertTrue(row['passed']); self.assertEqual(row['turns'],5)
        bad=self.root/'bad'; bad.mkdir()
        row=check(bad,self.root/'checks')
        self.assertFalse(row['passed']); self.assertEqual(row['compileFault'],'compile_failed')
        with self.assertRaises(InfrastructureError): Plain()

    def test_plain_python_cpp_only_inside_real_outer_sandbox(self):
        row=outer_plain(self.root/'outer')
        self.assertTrue(row['passed'],row['directory'])
        self.assertEqual(row['match']['result']['faults'],[None,None])

    def test_interrupted_controller_cleans_workers_and_resumes_same_tasks(self):
        slow=self.root/'slow'; slow.mkdir()
        (slow/'main.py').write_text('import hrw,time\nhrw.read_setup(); hrw.ready()\nwhile hrw.read_turn() is not None:\n time.sleep(.02)\n hrw.send([])\n')
        # Same basename is valid: the plan disambiguates labels, not submissions.
        fast=self.root/'other'/'slow'; fast.mkdir(parents=True)
        (fast/'main.py').write_text('import hrw\nhrw.read_setup(); hrw.ready()\nwhile hrw.read_turn() is not None: hrw.send([])\n')
        out=self.root/'interrupt'
        args=[sys.executable,'-m','arena','tournament','--bots',str(slow),str(fast),
              '--maps',str(ROOT/'maps/scrimmage/open-01.map'),'--jobs','1','--out',str(out)]
        with (self.root/'interrupt.stdout').open('wb') as stdout,(self.root/'interrupt.stderr').open('wb') as stderr:
            process=subprocess.Popen(args,cwd=ROOT,stdout=stdout,stderr=stderr)
            try:
                deadline=time.monotonic()+20
                started=[]
                while time.monotonic()<deadline and process.poll() is None:
                    started=list(out.glob('tasks/*/*/started.json'))
                    if started and list(out.glob('tasks/*/*/matches/*/attempt-0/*.gz')): break
                    time.sleep(.02)
                self.assertTrue(started)
                pid=json.loads(started[0].read_text())['workerPid']
                process.terminate(); process.wait(timeout=10)
                def process_state():
                    try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
                    except FileNotFoundError: return None
                deadline=time.monotonic()+10
                while process_state() not in (None,'Z') and time.monotonic()<deadline:
                    time.sleep(.02)
                # An external reaper may retain a zombie briefly; it has no
                # runnable threads or inherited lock descriptors.
                self.assertIn(process_state(),(None,'Z'))
            finally:
                if process.poll() is None: process.terminate(); process.wait(timeout=10)
        result=run_tournament([slow,fast],[ROOT/'maps/scrimmage/open-01.map'],out,jobs=1,resume=True)
        self.assertEqual(result['completed'],2,result)
        self.assertEqual(len(records(out/'results.jsonl')),2)
        attempts=records(out/'attempts.jsonl')
        self.assertGreaterEqual(sum(r['status']=='infra_error' for r in attempts),1)
        for row in attempts:
            for pid in row.get('sandboxPids',[]): self.assertFalse(Path(f'/proc/{pid}').exists())

    def test_legacy_replay_still_verifies(self):
        self.assertTrue(verify(ROOT/'replays/runtime-smoke.hrw.jsonl.gz')['verified'])

    def test_batch_two_slots_swapped_seeds_resume_skip_and_manifest_guard(self):
        out=self.root/'batch'
        sources=[ROOT/'sdk/python/example',self.root/'cpp-example']
        sources[1].mkdir(); (sources[1]/'main.cpp').write_bytes((ROOT/'sdk/cpp/example/main.cpp').read_bytes())
        maps=[ROOT/'maps/scrimmage/open-01.map',ROOT/'maps/scrimmage/maze-01.map']
        first=run_tournament(sources,maps,out,jobs=2,max_tasks=2)
        self.assertEqual(first['completed'],2,first)
        result=run_tournament(sources,maps,out,jobs=2,resume=True)
        self.assertEqual(result['status'],'complete',result)
        rows=records(out/'results.jsonl'); self.assertEqual(len(rows),4)
        self.assertEqual(len({r['taskId'] for r in rows}),4)
        for row in rows: self.assertTrue(verify(Path(row['replay']))['verified'])
        result=run_tournament(sources,maps,out,jobs=2,resume=True)
        self.assertEqual(result['newExecutions'],0)
        manifest=json.loads((out/'manifest.json').read_text())
        self.assertEqual([t['seeds'] for t in manifest['tasks'][:2]],[[17,29],[29,17]])
        allocations=[]
        for p in out.glob('tasks/*/*/job.json'):
            allocations.append(json.loads(p.read_text())['allocation'])
        pairs={tuple(a['bots']) for a in allocations}
        self.assertEqual(len(pairs),2)
        self.assertFalse(set(list(pairs)[0])&set(list(pairs)[1]))
        for a in allocations: self.assertFalse(set(a['pool'])&set(a['runners']))
        with self.assertRaisesRegex(ValueError,'changed'):
            run_tournament(sources,maps,out,jobs=1,resume=True)


if __name__=='__main__': unittest.main()
