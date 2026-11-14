"""User-run T6 acceptance: dry by default; CA-reviewed exclusive window required.

Normal AND queued in-flight-stop cases, plus trusted signal/abnormal-exit fixtures,
are mandatory. Dedicated child subreapers supply independent whole-tree evidence;
the generic experiment's controller exit alone is never sufficient.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from arena.core.journal import atomic_json
from arena.core.sandbox import parent_death_guard
from arena.games.outpost.replay import verify
from arena.tournament import fingerprint
from tools import experiment, experiment_plan as plan, profile_bot, process_evidence as evidence


def acceptance_specs():
    normal = [(1, profile_bot.build_spec('bots/public/M-balanced', ['bots/public/Z-harass'],
               ['maps/public/open-01.map'], 'package/claude-timing-jobs1.json', 1, identifier='accept-jobs1')),
              (6, profile_bot.build_spec('bots/public/M-balanced', ['bots/public/Z-rush'],
               ['maps/public/open-01.map','maps/public/corridor-01.map','maps/scrimmage/island-01.map'],
               'package/claude-timing-jobs6.json', 6, identifier='accept-jobs6'))]
    result = [('normal',jobs,spec) for jobs,spec in normal]
    for jobs,_ in normal:
        maps = ['maps/public/open-01.map'] if jobs == 1 else [
            'maps/public/open-01.map','maps/public/corridor-01.map','maps/scrimmage/island-01.map','maps/public/maze-01.map']
        spec = profile_bot.build_spec('bots/public/M-balanced',['bots/public/Z-harass'],maps,
                    f'package/claude-timing-jobs{jobs}.json',jobs,identifier=f'accept-stop-jobs{jobs}')
        spec['stop']['afterActiveWorkers'] = jobs
        if jobs == 6: spec['stop']['controllerExitOnAck'] = True
        result.append(('inflight-stop',jobs,spec))
    return result


def case_child(out):
    """Dedicated CLI child only: subreaping does not alter the caller's process."""
    root = plan.safe_path(out); ticket = plan.load_json(root/'acceptance-case-ticket.json')
    if (ticket['parentPid'] != os.getppid() or ticket['implementationSha256'] != plan.implementation_digest()
            or ticket['exclusiveWindowConfirmed'] is not True):
        raise ValueError('missing live acceptance parent/version/window')
    subreaper = evidence.enable_subreaper()
    result = {'kind': ticket['kind'], 'passed': False, 'subreaper': subreaper}
    try:
        frame,digest = plan.verify_frame(out)
        runtime = experiment.execute(out,digest,enable_experimental=True)
        settled = evidence.settle_descendants(timeout=5)
        result.update(settled)
        result.update({'jobs':frame['spec']['jobs'],'plannedGames':frame['games'],
            'completedGames':runtime['completedGames'],'status':runtime['status'],'reason':runtime['reason'],
            'controllerReaped':runtime['controllerReaped'],'genericDescendantCleanupState':runtime['descendantCleanupState'],
            'controllerReturncode':runtime['returncode'],
            'abnormalControllerExitTested':frame['spec']['stop'].get('controllerExitOnAck') is True,
            'overlap':runtime['workerOverlap'],'stopAcknowledged':runtime['stopAcknowledged'],
            'noDispatchAfterAck':runtime['noDispatchAfterAck'],
            'activeWorkerDeadlineArmed':runtime['activeWorkerDeadlineArmed']})
        jobs = list((root/'batch').glob('tasks/*/*/job.json'))
        started = list((root/'batch').glob('tasks/*/*/started.json'))
        result['startedWorkers'] = len(started)
        result['startedWorkersReaped'] = bool(started) and settled['noChildrenAndECHILD']
        result['unstartedPlannedTasks'] = frame['games']-len(jobs)
        summary = profile_bot.collect(out)
        rows = experiment.Tail(root/'batch/results.jsonl').poll(final=True)
        fresh = 0; reused = 0
        for row in rows:
            replay = profile_bot.local_artifact(row['replay'],root/'batch')
            if plan.digest_file(replay) != row['replaySha256']: raise ValueError('replay changed')
            if row.get('replayVerifiedOnIngest'): reused += 1
            else: verify(replay); fresh += 1
        misses = [not plan.load_json(p)['hit'] for p in (root/'batch/preparations').glob('*/*/cache.json')]
        if sum(misses) > frame['spec']['caps']['compiles'] or (root/'batch/bench').exists():
            raise ValueError('compile cap/no-benchmark contract failed')
        if any(any(r['result'].get('faults') or []) for r in rows): raise ValueError('completed acceptance game faulty')
        result.update({'auditedReplays':fresh+reused,'newReplayAudits':fresh,
            'standardIngestAuditReceiptsReused':reused,'compileCacheMissReceipts':sum(misses),
            'headersAndCpuTotalsChecked':summary['completeReplaysHeaderAndCpuChecked'],
            'logVerified':True,'cpuSummary':summary['labels'],'fixedLockSha256':frame['spec']['timing']['sha256'],
            'partialAttemptReplays':summary['partialAttemptReplays'],'missingHeaderReplays':summary['attemptsWithoutReplayHeader']})
        if result['kind'] == 'normal':
            if runtime['status'] != 'complete' or any(v['TURN']['count'] == 0 for v in summary['labels'].values()):
                raise ValueError('normal case incomplete or no TURN telemetry')
        else:
            if (runtime['status'] != 'stopped' or runtime['reason'] != 'wall-limit' or runtime['activeWorkerDeadlineArmed'] is not True
                    or runtime['stopAcknowledged'] is not True or runtime['noDispatchAfterAck'] is not True
                    or runtime['workerOverlap']['activeCount'] < frame['spec']['jobs']
                    or not runtime['workerOverlap']['positiveOverlap'] or result['unstartedPlannedTasks'] < 1):
                raise ValueError('in-flight stop/queue/overlap evidence incomplete')
            if frame['spec']['stop'].get('controllerExitOnAck') and runtime['returncode'] != 70:
                raise ValueError('abnormal controller exit was not observed')
        if (not runtime['controllerReaped'] or settled['descendantCleanupState'] != 'confirmed'
                or not settled['noChildrenAndECHILD'] or settled['safetyCleanupPerformed']):
            raise ValueError('controller exit alone does not confirm descendant cleanup')
        result['passed'] = True
    except Exception as error:
        result['errorType'] = type(error).__name__; result['message'] = str(error)
    finally:
        result['finalSafetySweep'] = evidence.settle_descendants(timeout=.1)
        if not result['finalSafetySweep']['noChildrenAndECHILD'] or result['finalSafetySweep']['safetyCleanupPerformed']:
            result['passed'] = False
        atomic_json(root/'case-summary.json',result)
    return 0 if result['passed'] else 2


def invoke_case(folder, kind, spec):
    root = plan.ROOT/folder
    atomic_json(root/'acceptance-case-ticket.json',{'parentPid':os.getpid(),'kind':kind,
                'implementationSha256':plan.implementation_digest(),'exclusiveWindowConfirmed':True})
    parent = os.getpid()
    with (root/'case.stdout').open('xb') as stdout,(root/'case.stderr').open('xb') as stderr:
        process = subprocess.Popen([sys.executable,'-B','-m','tools.accept_t6','--_case',folder],
                    cwd=plan.ROOT,env=evidence.safe_env(),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                    start_new_session=True,preexec_fn=lambda:parent_death_guard(parent))
        try: code = process.wait(timeout=spec['caps']['wallSeconds']+90)
        except BaseException:
            process.kill(); process.wait(timeout=5)
            raise
    value = plan.load_json(root/'case-summary.json')
    if code != 0 or value.get('passed') is not True: raise ValueError('acceptance case failed; artifacts retained')
    return value


def invoke_fixture(mode, artifact_root):
    parent = os.getpid()
    try:
        result = subprocess.run([sys.executable,'-B','-m','tools.process_evidence','--fixture',mode],
                    cwd=plan.ROOT,env=evidence.safe_env(),stdin=subprocess.DEVNULL,capture_output=True,text=True,
                    timeout=20,check=False,preexec_fn=lambda:parent_death_guard(parent))
    except subprocess.TimeoutExpired as error:
        atomic_json(artifact_root/f'fixture-{mode}-transport.json',
                    {'timeout':True,'stdout':str(error.stdout),'stderr':str(error.stderr)})
        raise
    atomic_json(artifact_root/f'fixture-{mode}-transport.json',
                {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    value = json.loads(result.stdout)
    if result.returncode != 0 or value.get('passed') is not True: raise ValueError('trusted lifecycle fixture failed')
    return value


def run(out, *, execute=False, reviewed_sha256=None, exclusive_window=False):
    current = plan.implementation_digest()
    if execute and (reviewed_sha256 != current or not exclusive_window):
        raise ValueError('explicit current CA-reviewed digest and an exclusive author/evaluator-idle window are required')
    specs = acceptance_specs()
    reserved = {'compiles':sum(s['caps']['compiles'] for _,_,s in specs),
                'botStarts':sum(s['caps']['botStarts'] for _,_,s in specs),'games':sum(s['caps']['games'] for _,_,s in specs)}
    if reserved['compiles']*2 > 40 or reserved['botStarts']*2 > 400: raise ValueError('two-delivery T6 cap exceeded')
    if not execute:
        return {'schemaVersion':1,'executed':False,'implementationSha256':current,'frameworkSha256':fingerprint(plan.ROOT),
                'perInvocationReservations':reserved,'cases':[{'kind':k,'jobs':j,'plannedGames':s['caps']['games']} for k,j,s in specs],
                'instruction':'After CA approval run ONCE in an author/evaluator-idle window; normal cases alone cannot pass.'}
    root = plan.safe_path(out,exists=False)
    if root.exists() or not root.is_relative_to(plan.ROOT/'runs'): raise ValueError('fresh runs/ directory required')
    root.mkdir(parents=True,mode=0o700)
    before=time.process_time_ns();wall=time.monotonic_ns()
    result={'schemaVersion':1,'acceptanceEvidenceVersion':2,'implementationSha256':current,'frameworkSha256':fingerprint(plan.ROOT),
            'passed':False,'executed':True,'evidenceKind':'public-bwrap-acceptance','perInvocationReservations':reserved,
            'cases':[],'trustedProcessFixtures':[],'benchmarks':0,'scoringGames':0,'caseGuardianLaunchAttempts':0,
            'scope':'Public acceptance only; not strength evidence, CPU occupancy proof or scoring permission.'}
    try:
        for mode in ('int','term','kill','abnormal'):
            value=invoke_fixture(mode,root);result['trustedProcessFixtures'].append(value)
            atomic_json(root/f'fixture-{mode}.json',value)
        bad=json.loads(json.dumps(specs[0][2]));bad['bots'][0]['sha256']='0'*64
        try: plan.freeze(bad,(root/'bad-hash').relative_to(plan.ROOT).as_posix())
        except ValueError:result['wrongSourceHashRejected']=True
        else:raise ValueError('wrong source digest accepted')
        for kind,jobs,spec in specs:
            folder=(root/f'{kind}-jobs{jobs}').relative_to(plan.ROOT).as_posix()
            _,digest=plan.freeze(spec,folder)
            try:experiment.execute(folder,digest)
            except ValueError:pass
            else:raise ValueError('runtime not disabled by default')
            result['caseGuardianLaunchAttempts']+=1
            result['cases'].append(invoke_case(folder,kind,spec))
            atomic_json(root/'acceptance-summary.json',result)
        plan.validate_acceptance_cases(result)
        result['passed']=True
    except Exception as error:
        result['errorType']=type(error).__name__;result['message']=str(error)
    finally:
        result['measuredScriptCpuSeconds']=(time.process_time_ns()-before)/1e9
        result['scriptWallSeconds']=(time.monotonic_ns()-wall)/1e9
        result['wholeProcessTreeCpuSeconds']=None
        atomic_json(root/'acceptance-summary.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--_case',help=argparse.SUPPRESS)
    parser.add_argument('--out',default='runs/t6-acceptance02');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--reviewed-sha256');parser.add_argument('--exclusive-window',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args._case:return case_child(args._case)
        result=run(args.out,execute=args.execute,reviewed_sha256=args.reviewed_sha256,exclusive_window=args.exclusive_window)
        print(json.dumps(result,indent=2));return 0 if not args.execute or result['passed'] else 2
    except (OSError,ValueError) as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)}),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
