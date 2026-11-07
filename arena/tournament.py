"""Immutable round-robin plans, process slots, shared JSONL and safe resumption."""
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from arena.core.benchmark import run_benchmark, workload_digest
from arena.core.cache import CompileCache
from arena.core.journal import append, atomic_json, records
from arena.core.resources import CpuLease
from arena.core.sandbox import ROOT, Bot, Bubblewrap, InfrastructureError, parent_death_guard, prepare, snapshot
from arena.core.timing import Calibration
from arena.games.outpost.maps import parse_map
from arena.games.outpost.replay import verify


def fingerprint(root=ROOT):
    files=[]
    for base in ('arena','sdk'):
        for path in sorted((root/base).rglob('*')):
            if path.is_symlink(): raise ValueError('framework snapshot contains a symbolic link')
            if path.is_file() and '__pycache__' not in path.parts: files.append(path)
    return sha256(b''.join(str(p.relative_to(root)).encode()+p.read_bytes() for p in files)).hexdigest()


def map_files(paths):
    result = []
    for path in paths:
        result.extend(sorted(path.glob('*.map')) if path.is_dir() else [path])
    if not result: raise ValueError('no maps')
    return result


def run_tournament(sources, maps, out: Path, *, jobs=6, focus=None, include_self=(), seeds=(17,29),
                   reference=None, sandbox='bwrap', resume=False, max_tasks=None, ruleset=None):
    if sandbox not in ('bwrap','plain'): raise ValueError('unknown backend')
    if type(jobs) is not int or jobs<1 or 2*jobs>=len(os.sched_getaffinity(0)):
        raise ValueError('need 2*jobs bot CPUs and at least one separate runner CPU')
    if sandbox=='plain' and (2*jobs+1>8): raise ValueError('outer workspace tools use at most 8 CPUs; maximum 3 jobs')
    if len(seeds)!=2 or any(type(s) is not int or s<0 for s in seeds): raise ValueError('two nonnegative seeds required')
    sources=[p.absolute() for p in sources]; maps=map_files(maps); out=out.resolve()
    if any(p.resolve().is_relative_to(ROOT/'private') for p in [*sources,*maps]) and not out.is_relative_to(ROOT/'private'):
        raise ValueError('hidden batch inputs and artifacts must stay private')
    names=[p.name for p in sources]
    counts=Counter(names)
    names=[name if counts[name]==1 else f'{name}#{i}' for i,name in enumerate(names)]
    if not set(include_self)<=set(names): raise ValueError('unknown self-play bot')
    if include_self and seeds[0]==seeds[1]: raise ValueError('self-play requires different seeds')
    pairs=list(combinations(range(len(sources)),2))
    if focus is not None: pairs=[p for p in pairs if focus in p]
    pairs += [(i,i) for i,name in enumerate(names) if name in include_self]
    if not pairs: raise ValueError('no bot pairings')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'controller.lock').open('a+b') as controller:
        try: fcntl.flock(controller,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error: raise InfrastructureError('this batch already has a controller') from error
        manifest_path=out/'manifest.json'
        if manifest_path.exists() and not resume: raise ValueError('batch exists; use --resume or a new directory')
        if not manifest_path.exists() and resume: raise ValueError('no batch to resume')
        request={'sources':[str(p) for p in sources],'maps':[str(p.absolute()) for p in maps],
                 'jobs':jobs,'pairs':pairs,'seeds':list(seeds),'sandbox':sandbox,'ruleset':ruleset or {},'framework':fingerprint(),
                 'referenceSha256':sha256(reference.read_bytes()).hexdigest() if reference else None}
        # Validate source snapshots on every invocation; a resume must not mix
        # source revisions. Validation failures remain submissions, not infra wins.
        validation=out/'validation'/uuid4().hex; validation.mkdir(parents=True)
        source_hashes=[]
        from arena.core.sandbox import SubmissionError
        for i,source in enumerate(sources):
            try: source_hashes.append(snapshot(source,validation/str(i)))
            except SubmissionError as error: source_hashes.append({'invalid':str(error)})
        request['sourceHashes']=source_hashes
        map_texts=[p.read_text() for p in maps]
        for text in map_texts: parse_map(text)
        request['mapHashes']=[sha256(t.encode()).hexdigest() for t in map_texts]
        if len(set(request['mapHashes']))!=len(map_texts): raise ValueError('duplicate map contents are not independent samples')
        request=json.loads(json.dumps(request))
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text())
            if manifest['request']!=request: raise ValueError('batch inputs/configuration changed; use a new output directory')
        else:
            manifest={'schemaVersion':1,'request':request,'tasks':[],'bots':names}
            for a,b in pairs:
                for index,map_path in enumerate(maps):
                    for swapped in (False,True):
                        players=[b,a] if swapped else [a,b]
                        ss=list(reversed(seeds)) if swapped else list(seeds)
                        task={'players':players,'mapIndex':index,'mapName':map_path.name,
                              'mapType':map_path.stem.split('-')[0],'seeds':ss,'swapped':swapped}
                        task['taskId']=sha256(json.dumps([request,task],sort_keys=True).encode()).hexdigest()
                        manifest['tasks'].append(task)
            atomic_json(manifest_path,manifest)
            snapshot(ROOT/'arena',out/'runtime/arena')
            snapshot(ROOT/'sdk',out/'runtime/sdk')
            for i,text in enumerate(map_texts):
                (out/'runtime'/f'map-{i}.map').write_text(text)
        finished={r['taskId']:r for r in records(out/'results.jsonl')}
        for row in finished.values():
            if sha256(Path(row['replay']).read_bytes()).hexdigest()!=row['replaySha256']:
                raise InfrastructureError('completed replay changed; refusing to skip or overwrite evidence')
        known={(r['matchId'],r['attempt']) for r in records(out/'attempts.jsonl')}

        def ingest(task, *, settled=False, verify_complete=True):
            task_dir=out/'tasks'/task['taskId']
            if settled:
                # Only after worker exit or reacquiring its inherited CPU locks:
                # a live worker may still be finishing its durable terminal row.
                for execution in sorted(task_dir.glob('*')):
                    if not (execution/'job.json').exists(): continue
                    groups=list((execution/'matches').glob('*'))
                    for group in groups:
                        ledger=group/'results.jsonl'
                        recorded={r['attempt'] for r in records(ledger)}
                        for work in sorted(group.glob('attempt-*')):
                            number=int(work.name.removeprefix('attempt-'))
                            if number in recorded: continue
                            result_file=work/'result.json'
                            row=None
                            if result_file.exists():
                                try: row=json.loads(result_file.read_text())
                                except json.JSONDecodeError: pass  # keep the original truncated bytes
                            if row is None:
                                row={'matchId':group.name,'attempt':number,'taskId':task['taskId'],
                                     'directory':str(work),'status':'infra_error','recovered':True,
                                     'error':'worker_terminated_before_attempt_result'}
                            append(ledger,row)
                    key=('worker-'+execution.name,0)
                    if not groups and key not in known:
                        reply_file=execution/'worker-result.json'
                        reply=json.loads(reply_file.read_text()) if reply_file.exists() else {}
                        append(out/'attempts.jsonl',{'matchId':key[0],'attempt':0,'taskId':task['taskId'],
                            'directory':str(execution),'status':'configuration_error' if reply.get('error')=='ValueError' else 'infra_error',
                            'error':reply.get('error','worker_exit_without_result'),'recovered':True})
                        known.add(key)
            rows=[]
            for ledger in sorted(task_dir.glob('*/matches/*/results.jsonl')):
                for row in records(ledger):
                    if row.get('taskId')!=task['taskId']: raise InfrastructureError('task ledger identity mismatch')
                    key=(row['matchId'],row['attempt'])
                    if key not in known:
                        append(out/'attempts.jsonl',row); known.add(key)
                    rows.append(row)
            complete=[r for r in rows if r['status']=='complete']
            if complete:
                if len(complete)!=1: raise InfrastructureError('more than one completed execution for a task')
                row={**complete[0],**task}
                if task['taskId'] not in finished:
                    # Recoveries replay before adoption. Normal trusted-worker
                    # results defer the full audit, avoiding a serial engine rerun
                    # in the controller's scheduling loop.
                    if verify_complete: verify(Path(row['replay']))
                    row['replayVerifiedOnIngest']=verify_complete
                    append(out/'results.jsonl',row); finished[task['taskId']]=row
                return True
            return False

        for task in manifest['tasks']:
            if task['taskId'] not in finished: ingest(task)
        archived = records(out/'attempts.jsonl')
        failures = Counter(r.get('taskId') for r in archived if r['status']=='infra_error')
        invalid = {r.get('taskId') for r in archived if r['status']=='configuration_error'}
        pending=[t for t in manifest['tasks'] if t['taskId'] not in finished
                 and failures[t['taskId']]<4 and t['taskId'] not in invalid]
        if max_tasks is not None:
            if type(max_tasks) is not int or max_tasks<0: raise ValueError('max_tasks must be nonnegative')
            pending=pending[:max_tasks]
        executed=[]
        if pending:
            timing_path=out/'timing-selection.json'
            old_timing=json.loads(timing_path.read_text()) if timing_path.exists() else None
            prior_cal=Calibration.load(Path(old_timing['resultFile']),workload_digest(),jobs=jobs) if old_timing else None
            capacity=min(8,len(os.sched_getaffinity(0))) if sandbox=='plain' else len(os.sched_getaffinity(0))
            runner_count=min(jobs,capacity-2*jobs)
            with CpuLease(2*jobs,exact=prior_cal.cpus if prior_cal else None,runner_count=runner_count) as lease:
                for task in manifest['tasks']:
                    if task['taskId'] not in finished: ingest(task,settled=True)
                archived=records(out/'attempts.jsonl')
                failures=Counter(r.get('taskId') for r in archived if r['status']=='infra_error')
                invalid={r.get('taskId') for r in archived if r['status']=='configuration_error'}
                pending=[t for t in manifest['tasks'] if t['taskId'] not in finished
                         and failures[t['taskId']]<4 and t['taskId'] not in invalid]
                if max_tasks is not None: pending=pending[:max_tasks]
                if fingerprint(out/'runtime')!=request['framework']:
                    raise ValueError('frozen framework changed')
                if sandbox=='bwrap': launcher=Bubblewrap()
                else:
                    from arena.core.plain import Plain
                    launcher=Plain()
                launcher.cpus=lease.cpus
                prepared=[]
                cache=CompileCache(out/'cache')
                prep=out/'preparations'/uuid4().hex
                for i,source in enumerate(sources):
                    # Valid sources use the just-validated frozen copy, not a live tree.
                    if isinstance(source_hashes[i],str):
                        bot=prepare(validation/str(i),prep/str(i),launcher,lease.cpus[0],cache=cache)
                    else:
                        directory=prep/str(i); directory.mkdir(parents=True)
                        reason=source_hashes[i]['invalid']
                        atomic_json(directory/'validation.json',{'valid':False,'reason':reason})
                        bot=Bot(names[i],None,directory,'invalid',[],'compile_failed',reason)
                    bot.code=names[i]; prepared.append(bot)
                    if bot.compile_fault and source.resolve().is_relative_to(ROOT/'private'):
                        raise ValueError('hidden bot preparation failed; see private artifacts')
                report=run_benchmark(out/'bench',jobs=jobs,reference=reference,sandbox=sandbox,_cpu_pool=lease.pool)
                if report['status']!='complete': raise InfrastructureError('batch benchmark failed; attempts retained')
                if old_timing:
                    # Resumption recalibrates the same CPU pool/concurrency;
                    # record both reports and the epoch on every new replay.
                    append(out/'timing-history.jsonl',old_timing)
                atomic_json(timing_path,report)
                timing=report['resultFile']
                queue=list(pending); active={}; idle=list(range(jobs))
                start=time.monotonic()
                try:
                    while queue or active:
                        while queue and idle:
                            slot=idle.pop(0); task=queue.pop(0)
                            execution=out/'tasks'/task['taskId']/uuid4().hex; execution.mkdir(parents=True)
                            config={'taskId':task['taskId'],'controllerPid':os.getpid(),'sources':[str(sources[i]) for i in task['players']],
                                'prepared':[{**asdict(prepared[i]),'directory':str(prepared[i].directory)} for i in task['players']],
                                'map':str(out/'runtime'/f'map-{task["mapIndex"]}.map'),'seeds':task['seeds'],
                                'out':str(execution/'matches'),'reply':str(execution/'worker-result.json'),
                                'sandbox':sandbox,'ruleset':ruleset or {},'timing':timing,
                                'retries':3-failures[task['taskId']], 'framework':request['framework'],
                                'mapSha256':request['mapHashes'][task['mapIndex']],
                                'allocation':{'jobs':jobs,'pool':lease.cpus,'bots':lease.cpus[slot*2:slot*2+2],
                                              'runners':[lease.runners[slot%len(lease.runners)]]}}
                            atomic_json(execution/'job.json',config)
                            stdout=(execution/'worker.stdout').open('wb'); stderr=(execution/'worker.stderr').open('wb')
                            parent_pid=os.getpid()
                            try:
                                process=subprocess.Popen([sys.executable,'-m','arena.worker',str(execution/'job.json')],
                                    cwd=out/'runtime',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONHASHSEED':'0',
                                                         'PYTHONDONTWRITEBYTECODE':'1'},stdout=stdout,stderr=stderr,start_new_session=True,
                                    pass_fds=tuple(lease.files),preexec_fn=lambda:parent_death_guard(parent_pid))
                            except (OSError,subprocess.SubprocessError) as error:
                                key=('worker-'+execution.name,0)
                                append(out/'attempts.jsonl',{'matchId':key[0],'attempt':0,'taskId':task['taskId'],
                                    'directory':str(execution),'status':'infra_error','error':type(error).__name__})
                                known.add(key)
                                append(out/'executions.jsonl',{'taskId':task['taskId'],'directory':str(execution),
                                    'completed':False,'error':type(error).__name__,'phase':'spawn'})
                                raise InfrastructureError('worker spawn failed; attempt retained') from error
                            finally: stdout.close(); stderr.close()
                            active[slot]=(process,task,execution)
                            atomic_json(execution/'started.json',{'workerPid':process.pid,'slot':slot})
                        for slot,(process,task,execution) in list(active.items()):
                            if process.poll() is None: continue
                            success=ingest(task,settled=True,verify_complete=process.returncode!=0)
                            receipt={'taskId':task['taskId'],'returncode':process.returncode,'completed':success,
                                     'directory':str(execution),'wallSinceBatchStart':time.monotonic()-start}
                            append(out/'executions.jsonl',receipt); executed.append(receipt)
                            del active[slot]; idle.append(slot)
                        if active: time.sleep(0.01)
                finally:
                    for process,_,_ in active.values():
                        if process.poll() is None: process.terminate()
                    for process,task,execution in active.values():
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired: process.kill(); process.wait()
                        ingest(task,settled=True)
                        append(out/'executions.jsonl',{'taskId':task['taskId'],'returncode':process.returncode,
                            'completed':task['taskId'] in finished,'directory':str(execution),'interrupted':True})
        remaining=len(manifest['tasks'])-len(finished)
        summary={'schemaVersion':1,'status':'complete' if not remaining else 'incomplete','tasks':len(manifest['tasks']),
                 'completed':len(finished),'remaining':remaining,'jobs':jobs,'sandbox':sandbox,
                 'newExecutions':len(executed),'directory':str(out),'results':str(out/'results.jsonl'),
                 'infraErrorAttempts':sum(r['status']=='infra_error' for r in records(out/'attempts.jsonl'))}
        atomic_json(out/'summary.json',summary)
        return summary
