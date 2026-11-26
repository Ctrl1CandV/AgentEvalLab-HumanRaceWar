"""Private grading entry point. Tournament remains responsible for all bot launches."""
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic

from arena import __version__
from arena.core.benchmark import workload_digest
from arena.core.journal import atomic_json, records
from arena.core.resources import lock_directory, open_lock
from arena.core.sandbox import ROOT
from arena.core.timing import Calibration
from arena.ladder import checked_maps, load_ladder, private_path
from arena.scoring import load_config, raw_game, summarize
from arena.tournament import run_tournament


@contextmanager
def grading_lock():
    fd=open_lock(lock_directory(),'one-formal-grader')
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def gather(batch,ladder,summary):
    manifest=json.loads((batch/'manifest.json').read_bytes())
    maps=manifest['request']['mapHashes']
    if list(m['sha256'] for m in ladder.grading)!=maps:
        raise ValueError('completed grading maps did not match the manifest')
    if manifest['request']['sourceHashes'][1:]!=[m.source_hash for m in ladder.members]:
        raise ValueError('completed ladder source bytes did not match the manifest')
    tasks={t['taskId']:t for t in manifest['tasks']}
    planned={(ladder.members[(t['players'][1] if t['players'][0]==0 else t['players'][0])-1].code,
              t['mapIndex'],t['players'].index(0)) for t in tasks.values()}
    expected={(m.code,s,side) for m in ladder.members for s in m.slots for side in (0,1)}
    if len(tasks)!=len(expected) or planned!=expected:
        raise ValueError('scoring batch does not cover the frozen slots')
    games=[]
    seen=set()
    for row in records(batch/'results.jsonl'):
        t=tasks[row['taskId']]
        if row['taskId'] in seen or row['status']!='complete' or any(row[key]!=value for key,value in t.items()):
            raise ValueError('grading task identity changed or was duplicated')
        seen.add(row['taskId'])
        replay=Path(row['replay']).resolve(strict=True)
        if not replay.is_relative_to(batch) or sha256(replay.read_bytes()).hexdigest()!=row['replaySha256']:
            raise ValueError('grading replay missing or changed')
        seat=row['players'].index(0)
        member=ladder.members[row['players'][1-seat]-1]
        game=raw_game(member.code,row['mapIndex'],seat,row['result'],300)
        games.append({**game,'taskId':row['taskId'],'result':row['result'],'replay':str(replay),'replaySha256':row['replaySha256']})
    if len(games)!=summary['completed']:
        raise ValueError('grading result count differs from the tournament receipt')
    return games


def grade(submission,ladder_path,maps,out,*,fixed_timing,jobs=6,config_path=None,resume=False):
    begin=monotonic()
    private=ROOT/'private'
    out=private_path(private,out,exists=False)
    if out.suffix!='.json': raise ValueError('grade --out must name a JSON file under private/')
    work=out.with_name(out.stem+'-work')
    if work.is_relative_to(submission.resolve()) or out.exists() and not resume:
        raise ValueError('choose a fresh output outside the submission, or explicitly resume')
    ladder=load_ladder(ladder_path,private)
    paths=checked_maps(private,maps,ladder.grading)
    config_path=config_path or Path(__file__).with_name('scoring.json')
    config=load_config(config_path)
    timing=Calibration.load(fixed_timing,workload_digest(),jobs=jobs)
    if timing.sandbox!='bwrap' or timing.locked_budget is None:
        raise ValueError('grade requires the host-local offline fixed timing lock')
    pairs=[(0,i) for i in range(1,len(ladder.members)+1)]
    batch=work/'batch'
    if batch.is_dir()!=resume:
        raise ValueError('grade resume must name the original batch')
    with grading_lock():
        started=monotonic()
        summary=run_tournament([submission,*[m.source for m in ladder.members]],paths,batch,
            jobs=jobs,pairings=pairs,pair_maps={p:m.slots for p,m in zip(pairs,ladder.members,strict=True)},
            seeds=ladder.seeds,sandbox='bwrap',fixed_timing=fixed_timing,submission_index=0,
            resume=resume,trusted_cache=private/'runtime-cache/release-grade')
        games=gather(batch,ladder,summary)
        report=summarize(games,ladder,config)
        report.update(schemaVersion=1,status='incomplete' if report['infraErrors'] else 'complete',
            speedFactor=timing.factor,ladderVersion=ladder.version,engineVersion=__version__,
            mapsSha256=sha256(''.join(m['sha256'] for m in ladder.grading).encode()).hexdigest(),
            timingLockSha256=timing.lock_sha256,scoringConfigSha256=sha256(config_path.read_bytes()).hexdigest(),
            replays=str(batch/'tasks'),rawResults=str(work/'games.json'),
            infraRetryAttempts=summary['infraErrorAttempts'],wallSeconds=monotonic()-started,lockWaitSeconds=started-begin)
        atomic_json(work/'games.json',games)
        atomic_json(out,report)
    return report


def register(commands):
    p=commands.add_parser('grade',help='score a submission on the frozen private ladder')
    p.add_argument('--submission',type=Path,required=True)
    p.add_argument('--ladder',type=Path,default=ROOT/'private/ladder/ladder-1.0.0.json')
    p.add_argument('--maps',type=Path,default=ROOT/'private/maps/grading')
    p.add_argument('--fixed-timing',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=6)
    p.add_argument('--resume',action='store_true')
    p.set_defaults(handler=cli)


def cli(args):
    result=grade(args.submission,args.ladder,args.maps,args.out,fixed_timing=args.fixed_timing,jobs=args.jobs,resume=args.resume)
    print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['status']=='complete' else 2
