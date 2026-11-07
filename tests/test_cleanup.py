"""Crash-window regressions; every untrusted probe still runs inside bwrap."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from arena.core.journal import records
from arena.core.sandbox import InfrastructureError
from arena.match import play
from arena.tournament import run_tournament

ROOT=Path(__file__).resolve().parents[1]
IDLE='import hrw\nhrw.read_setup();hrw.ready()\nwhile hrw.read_turn() is not None: hrw.send([])\n'


def state(pid):
    try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
    except FileNotFoundError: return None


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'runs/development/cleanup-tests'/uuid4().hex; self.root.mkdir(parents=True)
        self.a=self.root/'a'; self.b=self.root/'b'
        for path in (self.a,self.b):
            path.mkdir(); (path/'main.py').write_text(IDLE)
        self.map=ROOT/'maps/scrimmage/open-01.map'

    def test_worker_spawn_failure_is_a_retained_infrastructure_attempt(self):
        original=subprocess.Popen
        def fail_worker(args,**kwargs):
            if args[1:3]==['-m','arena.worker']: raise OSError('injected worker spawn failure')
            return original(args,**kwargs)
        out=self.root/'batch'
        with patch('arena.tournament.subprocess.Popen',side_effect=fail_worker):
            for attempt in range(4):
                try: run_tournament([self.a,self.b],[self.map],out,jobs=1,max_tasks=1,resume=attempt>0)
                except (OSError,InfrastructureError): pass
        attempts=records(out/'attempts.jsonl')
        self.assertEqual(len(attempts),4)
        self.assertEqual({r['status'] for r in attempts},{'infra_error'})
        self.assertEqual(len({r['taskId'] for r in attempts}),1)
        self.assertEqual(len(records(out/'executions.jsonl')),4)
        report=run_tournament([self.a,self.b],[self.map],out,jobs=1,resume=True)
        self.assertEqual(report['status'],'incomplete')
        self.assertEqual(report['completed'],1)
        self.assertEqual(report['remaining'],1)
        self.assertEqual(len(records(out/'attempts.jsonl')),5)

    def test_changed_frozen_map_is_configuration_error_not_a_bot_loss(self):
        out=self.root/'changed-map'
        run_tournament([self.a,self.b],[self.map],out,jobs=1,max_tasks=0)
        (out/'runtime/map-0.map').write_text((ROOT/'maps/scrimmage/maze-01.map').read_text())
        report=run_tournament([self.a,self.b],[self.map],out,jobs=1,resume=True)
        self.assertEqual(report['completed'],0)
        self.assertEqual(report['remaining'],2)
        rows=records(out/'attempts.jsonl')
        self.assertEqual(len(rows),2)
        self.assertEqual({r['status'] for r in rows},{'configuration_error'})
        again=run_tournament([self.a,self.b],[self.map],out,jobs=1,resume=True)
        self.assertEqual(again['newExecutions'],0)
        self.assertEqual(len(records(out/'attempts.jsonl')),2)

    def test_bot_cannot_clear_parent_death_signal(self):
        (self.a/'main.py').write_text('import ctypes,errno\nc=ctypes.CDLL(None,use_errno=True)\n'
            'assert c.prctl(1,0,0,0,0)==-1 and ctypes.get_errno()==errno.EPERM\n'+IDLE)
        result=play([self.a,self.b],self.map.read_text(),self.root/'matches',[17,29])
        self.assertEqual(result['result']['faults'],[None,None])

    def test_parent_dies_in_preexec_before_bwrap_can_install_its_guard(self):
        (self.a/'main.py').write_text('import time\nwhile True: time.sleep(.1)\n')
        # Trusted harness injection delays before exec, not untrusted host code.
        helper='''import json,os,sys,time
from pathlib import Path
from arena.core.sandbox import Bubblewrap,prepare
from arena.core.journal import atomic_json
source,work,probe=map(Path,sys.argv[1:])
launcher=Bubblewrap(); cpu=launcher.cpus[0]
bot=prepare(source,work,launcher,cpu)
original=os.sched_setaffinity
def delayed(pid,mask):
 atomic_json(probe,{'pid':os.getpid()})
 time.sleep(.4)
 original(pid,mask)
os.sched_setaffinity=delayed
with (work/'probe.stdout').open('wb') as out,(work/'probe.stderr').open('wb') as err:
 p=launcher.launch(bot.directory/'source',bot.directory/'sdk',bot.command,cpu,stdout=out,stderr=err)
 p.wait()
'''
        probe=self.root/'child.json'; child=None
        with (self.root/'helper.stdout').open('wb') as stdout,(self.root/'helper.stderr').open('wb') as stderr:
            parent=subprocess.Popen([sys.executable,'-c',helper,str(self.a),str(self.root/'prepared'),str(probe)],
                                    cwd=ROOT,stdout=stdout,stderr=stderr)
            try:
                deadline=time.monotonic()+10
                while not probe.exists() and parent.poll() is None and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(probe.exists())
                child=json.loads(probe.read_text())['pid']
                parent.kill(); parent.wait(timeout=10)
                deadline=time.monotonic()+2
                while state(child) not in (None,'Z') and time.monotonic()<deadline: time.sleep(.02)
                self.assertIn(state(child),(None,'Z'))
            finally:
                if parent.poll() is None: parent.kill(); parent.wait(timeout=10)
                if child and state(child) not in (None,'Z'):
                    try: os.killpg(child,signal.SIGKILL)
                    except ProcessLookupError: pass

    def test_sigkill_worker_recovers_unrecorded_attempt_before_resuming(self):
        (self.a/'main.py').write_text(IDLE.replace('hrw.send([])','__import__("time").sleep(.01);hrw.send([])'))
        out=self.root/'batch'
        args=[sys.executable,'-m','arena','tournament','--bots',str(self.a),str(self.b),'--maps',str(self.map),
              '--jobs','1','--max-tasks','1','--out',str(out)]
        with (self.root/'controller.stdout').open('wb') as stdout,(self.root/'controller.stderr').open('wb') as stderr:
            parent=subprocess.Popen(args,cwd=ROOT,stdout=stdout,stderr=stderr)
            try:
                deadline=time.monotonic()+20; replays=[]
                while parent.poll() is None and time.monotonic()<deadline:
                    replays=list(out.glob('tasks/*/*/matches/*/attempt-0/*.gz'))
                    if replays: break
                    time.sleep(.01)
                self.assertTrue(replays)
                pid_files=list(out.glob('tasks/*/*/matches/*/attempt-0/sandbox-pids.json'))
                start=next(out.glob('tasks/*/*/started.json'))
                os.kill(json.loads(start.read_text())['workerPid'],signal.SIGKILL)
                parent.wait(timeout=15)
                attempts=records(out/'attempts.jsonl')
                self.assertEqual(len(attempts),1)
                self.assertEqual(attempts[0]['status'],'infra_error')
                self.assertTrue(attempts[0]['recovered'])
                for pid_file in pid_files:
                    for pid in json.loads(pid_file.read_text())['pids']:
                        self.assertIn(state(pid),(None,'Z'))
            finally:
                if parent.poll() is None: parent.terminate(); parent.wait(timeout=15)
        report=run_tournament([self.a,self.b],[self.map],out,jobs=1,resume=True)
        self.assertEqual(report['completed'],2,report)
        self.assertEqual(len(records(out/'attempts.jsonl')),3)


if __name__=='__main__': unittest.main()
