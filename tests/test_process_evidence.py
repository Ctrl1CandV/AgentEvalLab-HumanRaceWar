"""Trusted Python process fixtures, NOT bot/bwrap/compiler/engine tests."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import process_evidence as evidence

ROOT=Path(__file__).resolve().parents[1]


class TrustedProcesses(unittest.TestCase):
    def fixture(self,mode):
        result=subprocess.run([sys.executable,'-B','-m','tools.process_evidence','--fixture',mode],
            cwd=ROOT,env=evidence.safe_env(),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertTrue(value['passed']);self.assertEqual(value['botStarts'],0)
        self.assertTrue(value['descendants']['noChildrenAndECHILD'])
        return value

    def test_real_trusted_sigint(self):
        value=self.fixture('int')
        self.assertEqual([v['signal'] for v in value['controller']['signals']],['SIGINT'])

    def test_real_trusted_sigterm_escalation(self):
        value=self.fixture('term')
        self.assertEqual([v['signal'] for v in value['controller']['signals']],['SIGINT','SIGTERM'])

    def test_real_trusted_sigkill_escalation(self):
        value=self.fixture('kill')
        self.assertEqual([v['signal'] for v in value['controller']['signals']],['SIGINT','SIGTERM','SIGKILL'])

    def test_abnormal_controller_exit_does_not_imply_child_exit(self):
        value=self.fixture('abnormal')
        self.assertEqual(value['controller']['descendantCleanupState'],'unknown')
        self.assertTrue(value['descendants']['residualBeforeSafetyCleanup'])
        self.assertEqual(value['descendants']['descendantCleanupState'],'forced-safety-cleanup')


class OverlapContracts(unittest.TestCase):
    def test_worker_without_live_sandbox_pairs_is_not_concurrency_evidence(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'tasks/t/e/started.json';p.parent.mkdir(parents=True);p.write_text('{"workerPid":1}')
            with patch.object(evidence,'identity',return_value={'pid':1,'parentPid':77,'startTicks':3,'state':'S'}):
                self.assertEqual(evidence.overlap_snapshot(root,77)['activeCount'],0)

    def test_two_pass_kernel_pairs_require_surviving_leaf_processes(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'tasks/t/e/started.json';p.parent.mkdir(parents=True);p.write_text('{"workerPid":1}')
            receipt=p.parent/'matches/m/attempt-0/sandbox-pids.json';receipt.parent.mkdir(parents=True);receipt.write_text('{"pids":[2,3]}')
            records={i:{'pid':i,'parentPid':parent,'startTicks':i,'state':'S'} for i,parent in ((1,77),(2,1),(3,1),(4,2),(5,3))}
            def descendants(pid):return [records[4 if pid==2 else 5]]
            with patch.object(evidence,'identity',side_effect=lambda pid:records[pid]),patch.object(evidence,'owned_descendants',side_effect=descendants),patch.object(evidence,'owned_child_pids',return_value=[]):
                value=evidence.overlap_snapshot(root,77)
                self.assertTrue(value['positiveOverlap']);self.assertEqual(value['activeCount'],1)
                records[4]={**records[4],'state':'Z'}
                self.assertEqual(evidence.overlap_snapshot(root,77)['activeCount'],0)


if __name__=='__main__':unittest.main()
