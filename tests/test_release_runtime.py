"""Fault-to-score integration checks; every test bot is sandboxed by arena."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arena.core.sandbox import InfrastructureError
from arena.core.transport import Connection
from arena.match import play
from arena.scoring import Config, raw_game, process
from arena.scrimmage import export_replay
from tests.helpers import fixture_map

IDLE='''import sys
for line in sys.stdin:
    if line.strip() == 'END':
        print('READY',flush=True)
        break
for line in sys.stdin:
    if line.strip() == 'END': print('END',flush=True)
'''
BEFORE_TURN='''import sys
for line in sys.stdin:
    if line.strip() == 'END':
        print('READY',flush=True)
        break
for line in sys.stdin:
    if line.strip() == 'END':
        break
'''
P1=Config(.25,{'tower':.4,'deposit':.3,'damage':.3})


class ReleaseRuntime(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.src=self.root/'testbot'; self.src.mkdir()
        self.idle=self.root/'idle'; self.idle.mkdir(); (self.idle/'main.py').write_text(IDLE)

    def run_match(self,code,cpp=False):
        (self.src/('main.cpp' if cpp else 'main.py')).write_text(code)
        result=play([self.src,self.idle],fixture_map(),self.root/'run',[17,29],sandbox='bwrap',
                    limits={'TURN_CPU_MS':20,'INIT_CPU_MS':200,'BANK_MS':10})
        self.assertEqual(result['status'],'complete')
        row=result['result']
        return raw_game('opponent',0,0,row,300),result

    def test_compile_failure_counts_as_loss_and_zero_process(self):
        game,_=self.run_match('int main() { invalid C++ }\n',cpp=True)
        self.assertEqual((game['fault'],game['outcome'],process(game,P1)),('compile_failed',0,0))

    def test_startup_failure_counts_as_loss(self):
        game,_=self.run_match('raise SystemExit(5)\n')
        self.assertTrue(game['fault']); self.assertEqual((game['outcome'],process(game,P1)),(0,0))

    def test_crash_after_ready_counts_as_loss(self):
        game,receipt=self.run_match(BEFORE_TURN+'raise SystemExit(7)\n')
        self.assertTrue(game['fault']); self.assertEqual((game['outcome'],process(game,P1)),(0,0))
        self.assertNotIn('timeout',game['fault'])

    def test_timeout_counts_as_loss(self):
        game,_=self.run_match(BEFORE_TURN+'while True:\n    pass\n')
        self.assertIn('timeout',game['fault']); self.assertEqual((game['outcome'],process(game,P1)),(0,0))

    def test_bad_utf8_is_a_warning_not_a_loss_and_replay_export_stays_verifiable(self):
        game,receipt=self.run_match(BEFORE_TURN+"sys.stdout.buffer.write(b'\\xff\\nEND\\n'); sys.stdout.buffer.flush()\n"+IDLE[IDLE.index('for line in sys.stdin:',IDLE.index('break')+5):])
        self.assertEqual((game['fault'],game['outcome'],process(game,P1),game['warningCount']),(None,.5,.5,1))
        export_replay(Path(receipt['replay']),self.root/'sanitized.hrw.jsonl.gz',['submission','Z-eco'])

    def test_long_line_is_a_warning_not_a_loss(self):
        rest=IDLE[IDLE.index('for line in sys.stdin:',IDLE.index('break')+5):]
        game,_=self.run_match(BEFORE_TURN+"print('x'*300); print('END',flush=True)\n"+rest)
        self.assertEqual((game['fault'],game['outcome'],process(game,P1),game['warningCount']),(None,.5,.5,1))

    def test_standard_infrastructure_retry_does_not_score_the_failed_attempt(self):
        toggled=False
        def first_failure_then_real(*args,**kwargs):
            nonlocal toggled
            if not toggled:
                toggled=True
                raise InfrastructureError('trusted test injection before a bot connection')
            return Connection(*args,**kwargs)
        with patch('arena.match.Connection',side_effect=first_failure_then_real):
            game,receipt=self.run_match(IDLE)
        self.assertEqual(receipt['attempt'],1)
        self.assertEqual((game['fault'],game['outcome'],process(game,P1)),(None,.5,.5))
        ledger=list((self.root/'run').glob('*/results.jsonl'))
        self.assertEqual(len(ledger),1)
        import json
        self.assertEqual([json.loads(line)['status'] for line in ledger[0].read_bytes().splitlines()],['infra_error','complete'])
