"""Outpost match orchestration; all bot execution goes through a launcher."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import time
import traceback
from uuid import uuid4

from arena import __version__
from arena.core.journal import append as append_result
from arena.core.replay import Writer
from arena.core.resources import CpuLease
from arena.core.runner import cpu_hard_limit, run
from arena.core.sandbox import Bubblewrap, InfrastructureError, prepare, clone_prepared
from arena.core.transport import Connection
from arena.core.timing import Calibration, scale_limits
from arena.games.outpost import Outpost
from arena.games.outpost.metrics import Metrics
from arena.games.outpost.replay import invalid_events, outcome


def play(sources: list[Path], map_text: str, out: Path, seeds: list[int], *, limits=None,
         retries: int = 3, calibration: Calibration | None = None, sandbox='bwrap',
         prepared=None, ruleset=None, task_id=None, _allocation=None) -> dict:
    """Standalone calls lease CPUs; trusted batch workers receive a leased slot."""
    if sandbox not in ('bwrap', 'plain'): raise ValueError('unknown sandbox backend')
    if _allocation is None:
        if calibration is not None and calibration.jobs != 1:
            raise ValueError('standalone match requires a jobs=1 benchmark, not batch-load calibration')
        with CpuLease(len(sources), exact=calibration.cpus if calibration else None) as lease:
            allocation = {'jobs':1, 'pool':lease.cpus, 'bots':lease.cpus, 'runners':lease.runners}
            return _play(sources,map_text,out,seeds,limits=limits,retries=retries,calibration=calibration,
                         sandbox=sandbox,prepared=prepared,ruleset=ruleset,task_id=task_id,allocation=allocation)
    return _play(sources,map_text,out,seeds,limits=limits,retries=retries,calibration=calibration,
                 sandbox=sandbox,prepared=prepared,ruleset=ruleset,task_id=task_id,allocation=_allocation)


def _play(sources, map_text, out, seeds, *, limits, retries, calibration, sandbox, prepared, ruleset,
          task_id, allocation):
    game = Outpost(limits)
    factor = calibration.factor if calibration else 1.0
    if calibration:
        if (calibration.jobs != allocation['jobs'] or tuple(allocation['pool']) != calibration.cpus
                or calibration.sandbox != sandbox):
            raise ValueError('calibration does not match batch allocation/concurrency')
        game = Outpost(scale_limits(game.limits, factor))
    wall_margin_ms = math.ceil(500*factor)
    initial = game.new_match(map_text, ruleset or {}, seeds)
    if prepared is not None and len(prepared) != len(sources): raise ValueError('prepared bot count mismatch')
    if len(sources) != len(initial.players) or len(allocation['bots']) != len(sources):
        raise ValueError('one bot and exclusive CPU per player required')
    if set(allocation['bots']) & set(allocation['runners']) or not set(allocation['bots']) <= set(allocation['pool']):
        raise ValueError('overlapping/invalid worker CPU assignment')
    if not 0 <= retries <= 3: raise ValueError('retries must be between zero and three')
    sources = [p.absolute() for p in sources]
    out = out.resolve()
    private = Path(__file__).resolve().parents[1]/'private'
    if any(p.resolve().is_relative_to(private) for p in sources) and not out.is_relative_to(private):
        raise ValueError('hidden bot artifacts must stay under private/')
    run_id = uuid4().hex
    directory = out/run_id
    directory.mkdir(parents=True, exist_ok=False)
    last = None
    for attempt in range(retries+1):
        start_cpu, start_wall = time.process_time_ns(), time.monotonic_ns()
        work = directory/f'attempt-{attempt}'; work.mkdir()
        connections, writer = [], None
        row = {'matchId':run_id,'attempt':attempt,'directory':str(work),'status':'infra_error','taskId':task_id}
        try:
            if sandbox == 'bwrap': launcher = Bubblewrap()
            else:
                from arena.core.plain import Plain
                launcher = Plain()
            launcher.cpus = list(allocation['pool'])
            bots = ([clone_prepared(bot,work/f'p{p}') for p,bot in enumerate(prepared)] if prepared is not None
                    else [prepare(source,work/f'p{p}',launcher,allocation['bots'][p]) for p,source in enumerate(sources)])
            if any(bot.compile_fault and source.resolve().is_relative_to(private) for bot,source in zip(bots,sources)):
                raise ValueError('hidden ladder bot is invalid; see private attempt artifacts')
            state = game.new_match(map_text,ruleset or {},seeds)
            metrics = Metrics(state)
            replay = work/f'{run_id}.hrw.jsonl.gz'
            writer = Writer(replay)
            compile_faults = [b.compile_fault for b in bots]
            writer.write({'type':'header','replayVersion':1,'metricsVersion':2,'engineVersion':__version__,'game':game.id,
                'ruleset':state.rules.name,'params':dict(state.rules.values),'map':map_text,
                'mapSha256':sha256(map_text.encode()).hexdigest(),
                'bots':[{'code':b.code,'sha256':b.digest,'language':b.language,'validationError':b.validation_error} for b in bots],
                'seeds':seeds,'limits':game.limits,'speedFactor':factor if calibration else None,
                'timingCalibration':calibration.header() if calibration else 'unscaled development limits; no calibration supplied',
                'wallMarginMs':wall_margin_ms,'cpuHardLimitSeconds':cpu_hard_limit(game.limits,state.rules['TURNS'],factor),
                'startedAt':datetime.now(timezone.utc).isoformat(),'sandbox':sandbox,
                'runtimePolicy':{'version':3,'singleProcess':True,'maxThreads':16,
                    'rootTmpDev':'read-only' if sandbox=='bwrap' else 'outer-sandbox policy; no inner filesystem isolation',
                    'tmp':'read-only' if sandbox=='bwrap' else 'outer-sandbox policy',
                    'cpuAccounting':'READY/END cumulative differences'},
                'cpus':allocation['bots'],'runnerCpus':allocation['runners'],'taskId':task_id,
                'compileFaults':compile_faults,'initialStateHash':game.state_hash(state)})
            faults = compile_faults if any(compile_faults) else None
            row['botCpuNs'] = [0]*len(bots)
            row['turnHarnessCpuNs'] = []

            def record(kind, replies, packets, bank):
                assert writer is not None
                for player, reply in enumerate(replies): row['botCpuNs'][player] += reply.cpu_ns
                rec = {'type':kind,'turn':state.turn if kind=='turn' else state.turn+1,
                       'replies':[r.record() for r in replies],'bankNs':bank,'stateHash':game.state_hash(state)}
                if packets is not None:
                    metrics.observe(state, packets)
                    rec['accepted'] = [[asdict(o) for o in p.commands] for p in packets]
                    rec['invalid'] = invalid_events(state)
                writer.write(rec)

            if faults is None:
                for p,bot in enumerate(bots):
                    connections.append(Connection(bot,launcher,allocation['bots'][p],cpu_hard_limit(game.limits,state.rules['TURNS'],factor)))
                    row['sandboxPids'] = [c.process.pid for c in connections]
                failed = run(game,state,connections,game.limits,record,wall_margin_ms=wall_margin_ms,
                             overheads=row['turnHarnessCpuNs'])
                faults = [r.fault for r in failed] if failed is not None else None
            result = {**outcome(game,state,faults), **metrics.result()}
            writer.write({'type':'result','result':result,'stateHash':game.state_hash(state)})
            row.update(status='complete',result=result,replay=str(replay))
        except Exception as error:
            row['error'] = type(error).__name__
            (work/'error.log').write_text(traceback.format_exc())
            if writer is not None: writer.write({'type':'infrastructure_error','error':type(error).__name__})
            if isinstance(error,ValueError) and not isinstance(error,InfrastructureError): row['status']='configuration_error'
        finally:
            cleanup = []
            for connection in connections:
                try: connection.close()
                except Exception as error: cleanup.append(type(error).__name__)
            if writer is not None:
                try: writer.close()
                except Exception as error: cleanup.append(type(error).__name__)
            if cleanup: row.update(status='infra_error',cleanupErrors=cleanup)
            if row.get('replay') and not cleanup:
                row['replaySha256'] = sha256(Path(row['replay']).read_bytes()).hexdigest()
            row.update(harnessCpuNs=time.process_time_ns()-start_cpu,wallNs=time.monotonic_ns()-start_wall)
            (work/'result.json').write_text(json.dumps(row,indent=2)+'\n')
            append_result(directory/'results.jsonl',row)
        last = row
        if row['status'] != 'infra_error': break
    assert last is not None
    return last
