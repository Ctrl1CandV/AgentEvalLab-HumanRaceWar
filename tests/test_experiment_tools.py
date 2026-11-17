"""Synthetic contracts only: no sandbox, compiler, bot, benchmark or engine step."""
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arena.core.benchmark import workload_digest
from arena.core.machine import machine_info, machine_fingerprint
from arena.core.timing import runtime_budget
from arena import tournament
from tools import experiment as run, experiment_plan as plan, profile_bot as profile, accept_t6, runtime_counts

REAL_ROOT = Path(__file__).resolve().parents[1]


class FakeProcess:
    """Only metadata is written; no interpreter or sandbox is launched."""
    def __init__(self, callback=None, *, active=False):
        self.pid = 123456789
        self.returncode = None if active else 0
        self.signals = []
        if callback: callback()

    def poll(self): return self.returncode
    def send_signal(self, value): self.signals.append(value); self.returncode = -value
    def wait(self, timeout=None): return self.returncode
    def terminate(self): self.signals.append(signal.SIGTERM); self.returncode = -15
    def kill(self): self.signals.append(signal.SIGKILL); self.returncode = -9


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(plan, 'ROOT', self.root).start()
        for target in ('arena.tournament.Bubblewrap', 'arena.tournament.run_benchmark',
                       'arena.core.sandbox.compile_bot', 'arena.match.Connection',
                       'arena.games.outpost.Outpost.step', 'subprocess.Popen'):
            patch(target, side_effect=AssertionError('pure contracts must never execute')).start()
        for name in ('sdk/cpp/hrw.hpp', 'sdk/python/hrw.py', 'arena/__init__.py'):
            p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'opaque synthetic bytes')
        (self.root/'arena/bench').mkdir()
        (self.root/'arena/bench/main.cpp').write_bytes((REAL_ROOT/'arena/bench/main.cpp').read_bytes())
        (self.root/'package').mkdir()
        (self.root/'package/public-files.json').write_text(json.dumps({'publicBotCodes': ['M-balanced', 'Z-harass', 'Z-rush']}))
        for code in ('M-balanced', 'Z-harass', 'Z-rush'):
            p = self.root/'bots/public'/code; p.mkdir(parents=True)
            (p/'main.cpp').write_bytes(b'opaque synthetic bytes, NEVER COMPILE: '+code.encode())
        for folder, filename in (('public','open-01.map'), ('public','corridor-01.map'), ('scrimmage','island-01.map'), ('public','maze-01.map')):
            p = self.root/'maps'/folder/filename; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((REAL_ROOT/'maps'/folder/filename).read_bytes())
        for jobs in (1, 6):
            benchmark = {'schemaVersion': 1, 'status': 'complete', 'sandbox': 'bwrap', 'jobs': jobs,
                         'cpus': list(range(2*jobs)), 'workloadSha256': workload_digest(),
                         'reference': {'cpuNs': 100}, 'loadedMedianCpuNs': 100, 'speedFactor': 1,
                         'machine': machine_info(), 'syntheticFixture': 'NO measurement or experiment'}
            raw = json.dumps(benchmark).encode()
            lock = {'schemaVersion': 2, 'kind': 'fixed-runtime-budget', 'benchmarkJson': raw.decode(),
                    'benchmarkSha256': sha256(raw).hexdigest(), 'machineFingerprint': machine_fingerprint(machine_info()),
                    'budget': runtime_budget({'TURN_CPU_MS':100, 'INIT_CPU_MS':2000, 'BANK_MS':3000}, 1, 300)}
            (self.root/f'package/claude-timing-jobs{jobs}.json').write_text(json.dumps(lock))

    def spec(self):
        return profile.build_spec('bots/public/M-balanced', ['bots/public/Z-harass'],
                                  ['maps/public/open-01.map'], 'package/claude-timing-jobs1.json', 1)

    def frozen(self, name='run'):
        out = f'runs/{name}'
        frame, digest = plan.freeze(self.spec(), out)
        return out, frame, digest

    def synthetic(self, out, frame, *, fault=False, only_manifest=False):
        root = self.root/out; batch = root/'batch'; batch.mkdir(exist_ok=True)
        manifest = run.expected_manifest(frame)
        (batch/'manifest.json').write_text(json.dumps(manifest))
        if only_manifest: return
        attempts = []; results = []; executions = []
        for index, task in enumerate(manifest['tasks']):
            execution = batch/'tasks'/task['taskId']/f'synthetic-execution-{index}'
            work = execution/'matches'/f'synthetic-match-{index}'/'attempt-0'
            work.mkdir(parents=True)
            allocation = {'jobs': frame['spec']['jobs'], 'pool': frame['timingHeader']['cpus'],
                          'bots': frame['timingHeader']['cpus'][:2], 'runners': [2*frame['spec']['jobs']]}
            job = {'taskId': task['taskId'], 'seeds': task['seeds'], 'framework': frame['frameworkSha256'],
                   'sandbox': 'bwrap', 'allocation': allocation,
                   'sources': [str(self.root/frame['bots'][i]['frozen']) for i in task['players']]}
            (execution/'job.json').write_text(json.dumps(job))
            faults = ['cpu_timeout', None] if fault and index == 0 else [None, None]
            values = [3200_000_000 if faults[0] else 200_000_000+index, 50_000_000]
            result = {'winner': None, 'reason': 'synthetic-no-engine', 'turns': 0 if faults[0] else 1, 'faults': faults}
            header = {'type': 'header', 'taskId': task['taskId'], 'syntheticFixture': True, 'sandbox': 'bwrap',
                      'map': (self.root/frame['maps'][task['mapIndex']]['frozen']).read_text(),
                      'mapSha256': frame['maps'][task['mapIndex']]['sha256'], 'seeds': task['seeds'],
                      'timingCalibration': frame['timingHeader'],
                      'limits': frame['timingHeader']['fixedRuntime']['limits'], 'params': {'TURNS':300},
                      'wallMarginMs': frame['timingHeader']['fixedRuntime']['wallMarginMs'],
                      'cpuHardLimitSeconds': frame['timingHeader']['fixedRuntime']['cpuHardLimitSeconds'],
                      'cpus': allocation['bots'], 'runnerCpus': allocation['runners'], 'compileFaults': [None,None],
                      'bots': [{'code': frame['bots'][i]['label'], 'language': frame['bots'][i]['language'],
                                'sha256':sha256(f"{frame['bots'][i]['sha256']}:{frame['sdkSha256'][frame['bots'][i]['language']]}".encode()).hexdigest()}
                               for i in task['players']]}
            replay = work/'synthetic.hrw.jsonl.gz'
            with gzip.open(replay, 'wt') as stream:
                for record in (header, {'type':'init','turn':1,'replies':[{'cpu_ns':1_000_000,'fault':None}]*2},
                               {'type':'fault' if faults[0] else 'turn','turn':1,
                                'replies':[{'cpu_ns':value,'fault':f} for value,f in zip(values,faults)]},
                               {'type':'result','result':result}):
                    stream.write(json.dumps(record)+'\n')
            row = {'taskId':task['taskId'], 'matchId':f'synthetic-match-{index}', 'attempt':0,
                   'directory':str(work),'status':'complete','result':result,'replay':str(replay),
                   'replaySha256':plan.digest_file(replay),'botCpuNs':[v+1_000_000 for v in values]}
            attempts.append(row); results.append({**row,**task})
            executions.append({'taskId':task['taskId'],'completed':True,'returncode':0,'directory':str(execution)})
        for name, rows in (('attempts',attempts),('results',results),('executions',executions)):
            (batch/f'{name}.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def finished(self, name='run', **kwargs):
        out, frame, digest = self.frozen(name)
        process = FakeProcess(lambda:self.synthetic(out,frame,**kwargs))
        with patch.object(run.subprocess,'Popen',return_value=process):
            result = run.execute(out,digest,enable_experimental=True)
        return out, frame, result

    def test_freeze_is_byte_only_readonly_and_never_executes(self):
        out, frame, digest = self.frozen()
        self.assertEqual(frame['games'],2)
        self.assertEqual(frame['reservedCompiles'],2)
        self.assertEqual(plan.verify_frame(out)[1],digest)
        for p in (self.root/out/'inputs').rglob('*'): self.assertFalse(p.stat().st_mode&0o222)
        self.assertFalse((self.root/out/'run-started.json').exists())
        self.assertEqual(frame['spec']['bots'][0]['sha256'],plan.source_digest(self.root/frame['bots'][0]['frozen']))

    def test_declared_label_hash_and_map_hash_must_match(self):
        for field in ('bots','maps','timing'):
            spec=self.spec()
            if field=='timing':spec[field]['sha256']='0'*64
            else:spec[field][0]['sha256']='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):plan.freeze(spec,'runs/fail-'+field)

    def test_duplicate_labels_pairs_maps_and_json_keys_rejected(self):
        for mutate in (lambda s:s['bots'][1].update(label='target'),
                       lambda s:s['pairs'].append(['ref0','target']),
                       lambda s:s['maps'].append(deepcopy(s['maps'][0]))):
            spec=self.spec();mutate(spec)
            with self.assertRaises(ValueError):plan.freeze(spec,'runs/bad')
        p=self.root/'duplicate.json';p.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):plan.load_json(p)
        p.write_text('{"x":NaN}')
        with self.assertRaises(ValueError):plan.load_json(p)

    def test_wrong_type_caps_underreserved_retries_and_scoring_rejected(self):
        for mutation in ('schema','jobs','games','starts','compile','wall','stop','purpose'):
            s=self.spec()
            if mutation=='schema':s['schemaVersion']=True
            elif mutation=='jobs':s['jobs']=True
            elif mutation=='games':s['caps']['games']=1
            elif mutation=='starts':s['caps']['botStarts']=4
            elif mutation=='compile':s['caps']['compiles']=1
            elif mutation=='wall':s['caps']['wallSeconds']=7201
            elif mutation=='stop':s['stop']['onFrameworkError']=False
            else:s['purpose']='scoring'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):plan.freeze(s,'runs/bad')

    def test_paths_links_special_objects_and_overlap_rejected(self):
        for value in ('../outside','/tmp/outside','.pi/auth.json','runs/../secret','runs//oops'):
            with self.subTest(value=value),self.assertRaises(ValueError):plan.safe_path(value,exists=False)
        source=self.root/'bots/public/M-balanced'
        (source/'link').symlink_to(self.root/'sdk')
        with self.assertRaises(ValueError):plan.freeze(self.spec(),'runs/bad')
        (source/'link').unlink();os.mkfifo(source/'fifo')
        with self.assertRaises(ValueError):plan.source_digest(source)
        (source/'fifo').unlink()
        with self.assertRaises(ValueError):plan.freeze(self.spec(),'bots/public/M-balanced/out')

    def test_private_and_nonpublic_inputs_need_human_approval_before_source_hashing(self):
        s=self.spec();p=self.root/'private/ladder/K-r01';p.mkdir(parents=True);(p/'main.cpp').write_bytes(b'opaque')
        s['bots'][0]['path']='private/ladder/K-r01';s['bots'][0]['sha256']='0'*64
        with patch.object(plan,'source_digest',side_effect=AssertionError('must reject first')):
            with self.assertRaises(ValueError):plan.freeze(s,'private/new-run')
        with self.assertRaises(ValueError):plan.freeze(s,'runs/leak')

    def test_synthetic_approval_is_version_bound_and_does_not_issue_itself(self):
        (self.root/'runs').mkdir(exist_ok=True)
        evidence=self.root/'runs/evidence.json'
        synthetic_evidence = self.acceptance_evidence()
        evidence.write_text(json.dumps(synthetic_evidence))
        receipt={'schemaVersion':1,'implementationSha256':plan.implementation_digest(),
                 'frameworkSha256':tournament.fingerprint(self.root),'caReviewAccepted':True,
                 'operatorAcceptancePassed':True,'evidencePath':'runs/evidence.json','evidenceSha256':plan.digest_file(evidence)}
        p=self.root/'runs/approval.json';p.write_text(json.dumps(receipt))
        self.assertEqual(plan.approval('runs/approval.json'),plan.digest_file(p))
        for mutation in ('synthetic','incomplete'):
            changed=deepcopy(synthetic_evidence)
            if mutation=='synthetic':changed['syntheticFixture']=True
            else:changed['cases'].pop()
            evidence.write_text(json.dumps(changed));receipt['evidenceSha256']=plan.digest_file(evidence)
            p.write_text(json.dumps(receipt))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):plan.approval('runs/approval.json')
        evidence.write_text(json.dumps(synthetic_evidence));receipt['evidenceSha256']=plan.digest_file(evidence)
        receipt['implementationSha256']='0'*64;p.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):plan.approval('runs/approval.json')

    def test_standard_max_tasks_zero_plan_matches_the_expected_contract(self):
        out,frame,_=self.frozen()
        original=tournament.fingerprint
        with patch.object(tournament,'ROOT',self.root),patch.object(tournament,'fingerprint',side_effect=lambda root=None:original(self.root if root is None else root)):
            tournament.run_tournament([self.root/b['frozen'] for b in frame['bots']],
                [self.root/m['frozen'] for m in frame['maps']],self.root/out/'batch',jobs=1,pairings=frame['pairs'],
                fixed_timing=self.root/out/'inputs/timing-lock.json',max_tasks=0)
        actual=plan.load_json(self.root/out/'batch/manifest.json')
        self.assertEqual(actual,run.expected_manifest(frame))

    def test_frozen_copy_not_live_source_is_executed_and_changed_copy_rejected(self):
        out,frame,digest=self.frozen()
        (self.root/'bots/public/M-balanced/main.cpp').write_bytes(b'a new opaque revision')
        self.assertEqual(plan.verify_frame(out)[1],digest)
        p=self.root/frame['bots'][0]['frozen']/'main.cpp';p.chmod(0o600);p.write_bytes(b'changed frozen source')
        with self.assertRaises(ValueError):plan.verify_frame(out)

    def test_execute_is_off_by_default_and_external_sha_required(self):
        out,_,digest=self.frozen()
        with self.assertRaises(ValueError):run.execute(out,digest)
        with self.assertRaises(ValueError):run.execute(out,'0'*64,enable_experimental=True)
        self.assertFalse((self.root/out/'run-started.json').exists())

    def test_mocked_supervision_preserves_env_plan_binding_and_single_use(self):
        out,frame,digest=self.frozen()
        process=FakeProcess(lambda:self.synthetic(out,frame))
        with patch.dict(os.environ,{'TMPDIR':'/keep-original','UNRELATED_SECRET':'never forward'}),patch.object(run.subprocess,'Popen',return_value=process) as launch:
            result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual(result['status'],'complete')
        env=launch.call_args.kwargs['env'];self.assertEqual(env['TMPDIR'],'/keep-original')
        self.assertNotIn('UNRELATED_SECRET',env)
        self.assertEqual(launch.call_args.kwargs['cwd'],self.root)
        self.assertEqual(result['completedGames'],2)
        run.verify_log(self.root/out/'run-log.jsonl',expected_head=result['logHeadSha256'],expected_count=result['logRows'])
        with self.assertRaises(FileExistsError):run.execute(out,digest,enable_experimental=True)

    def test_exact_launch_counts_are_bound_to_run_log_and_profile(self):
        out,frame,digest=self.frozen('counted')
        def prepare():
            meter=runtime_counts.LaunchCounts(self.root/out)
            meter.launch(True,lambda:None)
            for _ in range(4):meter.launch(False,lambda:None)
            self.synthetic(out,frame)
        with patch.object(run.subprocess,'Popen',side_effect=lambda *a,**k:FakeProcess(prepare)):
            result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual((result['compiles'],result['botStarts']),(1,4))
        log=run.verify_log(self.root/out/'run-log.jsonl',expected_head=result['logHeadSha256'],expected_count=result['logRows'])
        self.assertEqual(log[-1]['payload']['executionCounts'],result['executionCounts'])
        summary=profile.collect(out)
        self.assertEqual((summary['compiles'],summary['botStarts']),(1,4))
        path=self.root/out/'launch-counts.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError):profile.collect(out,report_name='tampered-counts')

    def test_stop_closes_count_gate_before_signalling_controller(self):
        out,frame,digest=self.frozen('counted-stop')
        def prepare():
            runtime_counts.LaunchCounts(self.root/out).launch(False,lambda:None)
            self.synthetic(out,frame,fault=True)
        process=FakeProcess(active=True)
        old_send=process.send_signal
        def send(value):
            with self.assertRaises(runtime_counts.InfrastructureError):
                runtime_counts.LaunchCounts(self.root/out).launch(False,lambda:self.fail('late launch'))
            old_send(value)
        process.send_signal=send
        def launch(*args,**kwargs):
            prepare();return process
        with patch.object(run.subprocess,'Popen',side_effect=launch):
            result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual(result['reason'],'bot-fault-limit')
        self.assertEqual(result['botStarts'],1)

    def test_spawn_failure_is_retained_and_not_a_whole_plan_retry(self):
        out,_,digest=self.frozen()
        with patch.object(run.subprocess,'Popen',side_effect=OSError('synthetic launch failure')):
            result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual(result['status'],'stopped');self.assertEqual(result['errorType'],'OSError')
        self.assertTrue((self.root/out/'run-started.json').exists())
        self.assertEqual(result['completedGames'],0)

    def test_fault_stop_and_infrastructure_exhaustion_are_distinct(self):
        out,frame,digest=self.frozen()
        process=FakeProcess(lambda:self.synthetic(out,frame,fault=True),active=True)
        with patch.object(run.subprocess,'Popen',return_value=process):result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual(result['reason'],'bot-fault-limit');self.assertIn(signal.SIGINT,process.signals)
        log=run.HashLog(self.root/'log.jsonl');observer=run.Observer(self.root/out,frame,log)
        base={'taskId':observer.manifest['tasks'][0]['taskId'],'matchId':'synthetic-infra','status':'infra_error','directory':'synthetic'}
        (self.root/out/'batch/attempts.jsonl').write_text(''.join(json.dumps({**base,'attempt':i})+'\n' for i in range(4)))
        for name in ('results','executions'):(self.root/out/f'batch/{name}.jsonl').write_bytes(b'')
        self.assertEqual(observer.poll(),'framework-error');log.close()

    def test_wall_deadline_interrupts_only_owned_mock_process(self):
        out,frame,digest=self.frozen()
        process=FakeProcess(lambda:self.synthetic(out,frame,only_manifest=True),active=True)
        with patch.object(run.subprocess,'Popen',return_value=process),patch.object(run.time,'monotonic',side_effect=[0,1000,1001]):
            result=run.execute(out,digest,enable_experimental=True)
        self.assertEqual(result['reason'],'wall-limit');self.assertEqual(process.signals,[signal.SIGINT])

    def test_hash_chain_detects_mutation_complete_line_truncation_and_torn_tail(self):
        out,_,result=self.finished();p=self.root/out/'run-log.jsonl';raw=p.read_bytes()
        for changed in (raw.replace(b'controller',b'Controller',1),b'\n'.join(raw.splitlines()[:-1])+b'\n',raw[:-1]):
            p.write_bytes(changed)
            with self.assertRaises(ValueError):run.verify_log(p,expected_head=result['logHeadSha256'],expected_count=result['logRows'])
        p.write_bytes(raw)

    def test_nonmutating_tail_retains_partial_bytes_and_rejects_truncation(self):
        p=self.root/'tail';p.write_bytes(b'{"x":1}\n{"x":')
        tail=run.Tail(p);self.assertEqual(tail.poll(),[{'x':1}])
        self.assertEqual(p.read_bytes(),b'{"x":1}\n{"x":')
        with self.assertRaises(ValueError):tail.poll(final=True)
        p.write_bytes(b'')
        with self.assertRaises(ValueError):tail.poll()

    def test_worker_passes_only_pinned_bwrap_fixed_timing_to_standard_api(self):
        out,frame,digest=self.frozen()
        ticket={'parentPid':os.getppid(),'frameSha256':digest,'deadlineEpochNs':10**30}
        (self.root/out/'run-started.json').write_text(json.dumps(ticket))
        with patch.object(run,'run_tournament',return_value={'status':'complete'}) as called:
            self.assertEqual(run.worker(out),0)
        options=called.call_args.kwargs
        self.assertEqual(options['sandbox'],'bwrap');self.assertEqual(options['jobs'],1)
        self.assertEqual(options['pairings'],frame['pairs'])
        self.assertEqual(options['fixed_timing'],self.root/out/'inputs/timing-lock.json')
        self.assertNotIn('freeze_timing',options)
        self.assertNotIn('resume',options)

    def test_profile_exact_quantiles_bank_excess_cpu_ids_and_init_separation(self):
        out,_,_=self.finished();summary=profile.collect(out)
        self.assertFalse(summary['replaySemanticsVerified'])
        self.assertEqual(summary['completedGames'],2)
        self.assertEqual(summary['labels']['target']['TURN']['count'],2)
        self.assertEqual(summary['labels']['target']['INIT']['p99Ms'],1)
        self.assertEqual(summary['labels']['target']['overTurnCpuReplies'],1)
        self.assertEqual(summary['labels']['target']['faultReplies'],0)
        self.assertEqual(summary['labels']['target']['cpuIds'],[0,1])
        self.assertAlmostEqual(summary['labels']['target']['TURN']['p50Ms'],50)
        self.assertAlmostEqual(summary['labels']['target']['TURN']['p99Ms'],200)
        self.assertTrue((self.root/out/'profile/cpu.sqlite3').exists())
        self.assertTrue((self.root/out/'profile/exceedances.jsonl').read_text())

    def test_fault_turn_is_profiled_but_not_counted_as_a_settled_turn(self):
        out,_,_=self.finished(fault=True)
        summary=profile.collect(out)
        self.assertEqual(summary['status'],'stopped')
        self.assertEqual(summary['labels']['target']['faultReplies'],1)
        self.assertEqual(summary['labels']['target']['TURN']['maxMs'],3200)

    def test_replay_and_journal_tampering_fail_closed(self):
        out,_,_=self.finished()
        rows=run.Tail(self.root/out/'batch/results.jsonl').poll(final=True)
        p=Path(rows[0]['replay']);p.write_bytes(p.read_bytes()+b'changed')
        with self.assertRaises(ValueError):profile.collect(out)
        out,_,_=self.finished('second')
        p=self.root/out/'batch/results.jsonl';p.write_bytes(p.read_bytes().replace(b'complete',b'invalid!',1))
        with self.assertRaises(ValueError):profile.collect(out)

    def test_unsafe_artifact_and_existing_report_are_not_overwritten(self):
        out,_,_=self.finished();profile.collect(out)
        with self.assertRaises(ValueError):profile.collect(out)
        with self.assertRaises(ValueError):profile.local_artifact(self.root/'outside',self.root/out/'batch')
        with self.assertRaises(ValueError):profile.collect(out,report_name='../escape')

    def test_cross_journal_observation_race_defers_results_until_attempts_arrive(self):
        out,frame,_=self.frozen();self.synthetic(out,frame)
        p=self.root/out/'batch/attempts.jsonl';saved=p.read_bytes();p.write_bytes(b'')
        log=run.HashLog(self.root/'race-log.jsonl');self.addCleanup(log.close)
        observer=run.Observer(self.root/out,frame,log)
        self.assertIsNone(observer.poll())
        self.assertEqual(len(observer.completed),0)
        self.assertEqual(len(observer.pending_results),2)
        p.write_bytes(saved)
        self.assertIsNone(observer.poll(final=True));self.assertEqual(len(observer.completed),2)

    def test_completed_result_cannot_change_its_underlying_attempt(self):
        out,frame,_=self.frozen();self.synthetic(out,frame)
        p=self.root/out/'batch/results.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
        rows[0]['result']['winner']=1;p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
        log=run.HashLog(self.root/'attempt-log.jsonl');self.addCleanup(log.close)
        with self.assertRaises(ValueError):run.Observer(self.root/out,frame,log).poll(final=True)

    def test_final_manifest_and_actual_worker_cpu_allocation_are_rechecked(self):
        out,frame,_=self.frozen();self.synthetic(out,frame)
        log=run.HashLog(self.root/'manifest-log.jsonl');self.addCleanup(log.close)
        observer=run.Observer(self.root/out,frame,log);observer.poll()
        p=self.root/out/'batch/manifest.json';value=json.loads(p.read_text());value['request']['jobs']=2;p.write_text(json.dumps(value))
        with self.assertRaises(ValueError):observer.poll(final=True)
        out,_,_=self.finished('cpu-contract')
        job=next((self.root/out/'batch/tasks').glob('*/*/job.json'))
        value=json.loads(job.read_text());value['allocation']['bots']=[99,100];job.write_text(json.dumps(value))
        with self.assertRaises(ValueError):profile.collect(out)

    def test_writable_frozen_inputs_and_changed_execution_journal_are_rejected(self):
        out,_,_=self.frozen()
        (self.root/out/'inputs/timing-lock.json').chmod(0o600)
        with self.assertRaises(ValueError):plan.verify_frame(out)
        out,_,_=self.finished('changed-execution')
        p=self.root/out/'batch/executions.jsonl';p.write_bytes(p.read_bytes().replace(b'true',b'false',1))
        with self.assertRaises(ValueError):profile.collect(out)

    def test_tool_hot_edits_and_sensitive_paths_fail_before_execution(self):
        with patch.object(plan,'_IMPORTED_DIGEST','0'*64):
            with self.assertRaises(ValueError):plan.implementation_digest()
        for path in ('runs/.env.local','private/ladder/K/private.key','runs/id_rsa'):
            with self.subTest(path=path),self.assertRaises(ValueError):plan.safe_path(path,exists=False)
        source=self.root/'bots/public/M-balanced';(source/'auth.json').write_bytes(b'opaque synthetic data')
        with patch.object(plan,'digest_file',side_effect=AssertionError('must not read a credential body')):
            with self.assertRaises(ValueError):plan.source_digest(source)

    def test_numeric_jobs_mismatch_and_unknown_frame_fields_are_rejected(self):
        spec=self.spec();spec['jobs']=2
        with self.assertRaises(ValueError):plan.freeze(spec,'runs/wrong-jobs')
        self.assertFalse((self.root/'runs/wrong-jobs').exists())
        out,_,_=self.frozen()
        path=self.root/out/'inputs/frame.json';value=json.loads(path.read_text());value['extra']='not allowed'
        path.chmod(0o600);path.write_text(json.dumps(value));path.chmod(0o444)
        with self.assertRaises(ValueError):plan.verify_frame(out)

    def test_live_result_without_corresponding_attempt_is_not_adopted_at_final(self):
        out,frame,_=self.frozen();self.synthetic(out,frame)
        (self.root/out/'batch/attempts.jsonl').write_bytes(b'')
        log=run.HashLog(self.root/'missing-attempt.jsonl');self.addCleanup(log.close)
        observer=run.Observer(self.root/out,frame,log)
        self.assertIsNone(observer.poll());self.assertEqual(len(observer.completed),0)
        with self.assertRaises(ValueError):observer.poll(final=True)

    def empty_replay_run(self, name, payload, *, complete):
        out,frame,digest=self.frozen(name)
        def prepare():
            self.synthetic(out,frame)
            batch=self.root/out/'batch'
            attempts=[json.loads(x) for x in (batch/'attempts.jsonl').read_text().splitlines()]
            row=attempts[0];Path(row['replay']).write_bytes(payload);row['replaySha256']=plan.digest_file(row['replay'])
            if not complete:row['status']='infra_error'
            (batch/'attempts.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in attempts))
            results=[{**x,**task} for x,task in zip(attempts,run.expected_manifest(frame)['tasks']) if x['status']=='complete']
            (batch/'results.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in results))
            executions=[json.loads(x) for x in (batch/'executions.jsonl').read_text().splitlines()]
            executions[0]['completed']=complete
            (batch/'executions.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in executions))
        with patch.object(run.subprocess,'Popen',return_value=FakeProcess(prepare)):
            run.execute(out,digest,enable_experimental=True)
        return out

    def test_incomplete_empty_raw_and_gzip_replays_are_preserved_and_counted(self):
        for index,payload in enumerate((b'',gzip.compress(b''))):
            out=self.empty_replay_run(f'empty-{index}',payload,complete=False)
            summary=profile.collect(out)
            self.assertEqual(summary['partialAttemptReplays'],1)
            self.assertEqual(summary['attemptsWithoutReplayHeader'],1)
            self.assertEqual(summary['completedGames'],1)
            attempt=json.loads((self.root/out/'batch/attempts.jsonl').read_text().splitlines()[0])
            self.assertEqual(Path(attempt['replay']).read_bytes(),payload)

    def test_complete_empty_replay_is_a_validation_error_not_stopiteration(self):
        for index,payload in enumerate((b'',gzip.compress(b''))):
            out=self.empty_replay_run(f'complete-empty-{index}',payload,complete=True)
            with self.assertRaises(ValueError):profile.collect(out)

    def acceptance_evidence(self):
        cases=[]
        for kind,jobs,games in (('normal',1,2),('normal',6,6),('inflight-stop',1,2),('inflight-stop',6,8)):
            completed=games if kind=='normal' else 0
            cases.append({'kind':kind,'jobs':jobs,'plannedGames':games,'completedGames':completed,
                'auditedReplays':completed,'headersAndCpuTotalsChecked':completed,'logVerified':True,
                'compiles':2,'botStarts':2*(completed if kind=='normal' else jobs),
                'status':'complete' if kind=='normal' else 'stopped','reason':'wall-limit',
                'controllerReaped':True,'descendantCleanupState':'confirmed','noChildrenAndECHILD':True,
                'safetyCleanupPerformed':False,'stopAcknowledged':True,'noDispatchAfterAck':True,
                'startedWorkersReaped':True,'unstartedPlannedTasks':1,'activeWorkerDeadlineArmed':True,
                'abnormalControllerExitTested':kind=='inflight-stop' and jobs==6,
                'controllerReturncode':0 if kind=='normal' else (70 if jobs==6 else -2),
                'overlap':{'activeCount':jobs,'positiveOverlap':True,'overlapStartMonotonicNs':1,'overlapEndMonotonicNs':2}})
        return {'passed':True,'executed':True,'acceptanceEvidenceVersion':2,'evidenceKind':'public-bwrap-acceptance',
                'implementationSha256':plan.implementation_digest(),'frameworkSha256':tournament.fingerprint(self.root),
                'cases':cases,'compiles':sum(c['compiles'] for c in cases),'botStarts':sum(c['botStarts'] for c in cases),
                'trustedProcessFixtures':[{'mode':m,'passed':True} for m in ('int','term','kill','abnormal')]}

    def test_normal_games_alone_or_unknown_cleanup_cannot_pass_acceptance(self):
        good=self.acceptance_evidence();plan.validate_acceptance_cases(good)
        for mutate in (lambda e:e['cases'].__delitem__(slice(2,None)),
                       lambda e:e['cases'][2].update(descendantCleanupState='unknown'),
                       lambda e:e['cases'][2].update(noDispatchAfterAck=False),
                       lambda e:e['cases'][3].update(overlap={'activeCount':1}),
                       lambda e:e['trustedProcessFixtures'][2].update(passed=False),
                       lambda e:e['cases'][2].update(activeWorkerDeadlineArmed=False),
                       lambda e:e['cases'][2].update(botStarts=-1),
                       lambda e:e.update(compiles=7)):
            value=deepcopy(good);mutate(value)
            with self.assertRaises(ValueError):plan.validate_acceptance_cases(value)

    def test_generic_controller_reaping_never_claims_descendant_cleanup(self):
        _,_,result=self.finished('controller-only')
        self.assertTrue(result['controllerReaped'])
        self.assertEqual(result['descendantCleanupState'],'unknown')
        self.assertNotIn('cleanupConfirmed',result)

    def test_worker_ack_freezes_dispatch_set_and_restores_signal_handler(self):
        out,_,digest=self.frozen('worker-ack')
        root=self.root/out;job=root/'batch/tasks/task/execution/job.json';job.parent.mkdir(parents=True);job.write_text('{}')
        (root/'run-started.json').write_text(json.dumps({'parentPid':os.getppid(),'frameSha256':digest,'deadlineEpochNs':10**30}))
        previous=signal.getsignal(signal.SIGINT)
        with patch.object(run,'run_tournament',side_effect=lambda *a,**k:signal.raise_signal(signal.SIGINT)):
            with self.assertRaises(KeyboardInterrupt):run.worker(out)
        self.assertEqual(signal.getsignal(signal.SIGINT),previous)
        self.assertEqual(plan.load_json(root/'stop-ack.json')['jobs'],['tasks/task/execution/job.json'])

    def test_public_abnormal_on_ack_is_explicit_and_emits_receipt_before_exit(self):
        spec=self.spec();spec['stop'].update(afterActiveWorkers=1,controllerExitOnAck=True)
        out='runs/abnormal-ack';_,digest=plan.freeze(spec,out)
        root=self.root/out
        (root/'run-started.json').write_text(json.dumps({'parentPid':os.getppid(),'frameSha256':digest,'deadlineEpochNs':10**30}))
        with patch.object(run,'run_tournament',side_effect=lambda *a,**k:signal.raise_signal(signal.SIGINT)),patch.object(run.os,'_exit',side_effect=SystemExit(70)):
            with self.assertRaises(SystemExit) as caught:run.worker(out)
        self.assertEqual(caught.exception.code,70)
        self.assertTrue(plan.load_json(root/'stop-ack.json')['abnormalControllerExit'])
        spec=self.spec();spec['purpose']='diagnostic';spec['stop'].update(afterActiveWorkers=1,controllerExitOnAck=True)
        with self.assertRaises(ValueError):plan.freeze(spec,'runs/not-allowed')

    def test_active_overlap_arms_real_wall_deadline_and_detects_late_dispatch(self):
        for late in (False,True):
            spec=self.spec();spec['stop']['afterActiveWorkers']=1
            out=f'runs/active-{late}';frame,digest=plan.freeze(spec,out)
            process=FakeProcess(lambda:self.synthetic(out,frame,only_manifest=True),active=True)
            original=process.send_signal
            def send(value):
                atomic={'jobs':[],'signal':value};(self.root/out/'stop-ack.json').write_text(json.dumps(atomic))
                if late:
                    p=self.root/out/'batch/tasks/late/new/job.json';p.parent.mkdir(parents=True);p.write_text('{}')
                original(value)
            process.send_signal=send
            peak={'activeCount':1,'positiveOverlap':True,'overlapStartMonotonicNs':1,'overlapEndMonotonicNs':2,'workers':[]}
            with patch.object(run.subprocess,'Popen',return_value=process),patch.object(run.process_evidence,'overlap_snapshot',return_value=peak):
                result=run.execute(out,digest,enable_experimental=True)
            self.assertEqual(result['reason'],'wall-limit');self.assertTrue(result['activeWorkerDeadlineArmed'])
            self.assertEqual(result['noDispatchAfterAck'],not late)

    def test_acceptance_is_dry_and_review_exclusive_gates_precede_execution(self):
        result=accept_t6.run('runs/acceptance')
        self.assertFalse(result['executed']);self.assertEqual(result['perInvocationReservations']['games'],18)
        self.assertEqual(result['perInvocationReservations']['botStarts'],144)
        self.assertFalse((self.root/'runs/acceptance').exists())
        with self.assertRaises(ValueError):accept_t6.run('runs/acceptance',execute=True)
        with self.assertRaises(ValueError):accept_t6.run('runs/acceptance',execute=True,reviewed_sha256=plan.implementation_digest())


if __name__=='__main__':unittest.main()
