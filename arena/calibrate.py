"""Adjacent-level migration check. Frozen legacy fitting method, no grading maps."""
import json
from math import isfinite
from pathlib import Path
from statistics import fmean
from time import monotonic

from arena.core.journal import atomic_json, records
from arena.core.sandbox import ROOT
from arena.ladder import checked_maps, load_ladder, private_path
from arena.tournament import run_tournament
from tools.provisional_bt import fit


def compare(ladder,elo):
    centers=[]
    cursor=0
    for level in ladder.levels:
        ratings=elo[cursor:cursor+len(level)]
        centers.append(fmean(ratings) if all(type(x) in (float,int) and isfinite(x) for x in ratings) else None)
        cursor+=len(level)
    comparisons=[]
    for i,(left,right,old) in enumerate(zip(centers[:-1],centers[1:],ladder.calibration['gaps'],strict=True)):
        gap=None if left is None or right is None else right-left
        delta=None if gap is None else gap-old
        comparisons.append({'lower':f'L{i}','upper':f'L{i+1}','formalGap':old,'newGap':gap,'delta':delta,
                            'consistent':delta is not None and abs(delta)<=50})
    return comparisons


def calibrate(ladder_path,maps,out,*,fixed_timing,jobs=6,resume=False):
    started=monotonic()
    root=ROOT/'private'
    out=private_path(root,out,exists=False)
    ladder=load_ladder(ladder_path,root)
    paths=checked_maps(root,maps,ladder.calibration['maps'])
    if (out/'batch'/'manifest.json').is_file()!=resume:
        raise ValueError('calibration resume requires its original batch')
    ids={m.code:i for i,m in enumerate(ladder.members)}
    pairs=[[ids[a],ids[b]] for a,b in ladder.calibration['pairings']]
    batch=out/'batch'
    run=run_tournament([m.source for m in ladder.members],paths,batch,jobs=jobs,
        sandbox='bwrap',fixed_timing=fixed_timing,seeds=ladder.seeds,pairings=pairs,resume=resume,
        trusted_cache=root/'runtime-cache/release-grade')
    matrix=[[0.0]*len(ids) for _ in ids]
    rows=records(batch/'results.jsonl')
    expected=24*len(pairs)
    if len(rows)!=run['completed'] or run['tasks']!=expected:
        raise ValueError('adjacent calibration shape changed')
    plan=json.loads((batch/'manifest.json').read_bytes())
    if plan['request']['sourceHashes']!=[m.source_hash for m in ladder.members]:
        raise ValueError('adjacent calibration source bytes changed')
    task={t['taskId']:t for t in plan['tasks']}; seen=set()
    for row in rows:
        k=row['taskId']
        if k in seen or row['status']!='complete' or any(row[key]!=value for key,value in task[k].items()):
            raise ValueError('unexpected or duplicate calibration result')
        seen.add(k)
        a,b=row['players']; w=row['result']['winner']
        matrix[a][b]+=.5 if w is None else float(w==0)
        matrix[b][a]+=.5 if w is None else float(w==1)
    if len(rows)==expected:
        ratings=fit(matrix,ids['M-balanced'])['elo']
    else:
        ratings=[None]*len(ids)
    comparisons=compare(ladder,ratings)
    result={'schemaVersion':1,'mode':'adjacent','ladderVersion':ladder.version,'games':len(rows),'expected':expected,
            'infraErrors':expected-len(rows),'infraRetryAttempts':run['infraErrorAttempts'],
            'toleranceElo':50,'comparisons':comparisons,'passed':all(c['consistent'] for c in comparisons),
            'wallSeconds':monotonic()-started}
    atomic_json(out/'results.json',result)
    atomic_json(out/'ratings-private.json',dict(zip(ids,ratings,strict=True)))
    return result


def register(commands):
    p=commands.add_parser('calibrate',help='verify adjacent ladder gaps on the evaluation host')
    p.add_argument('--mode',choices=['adjacent'],default='adjacent')
    p.add_argument('--ladder',type=Path,default=ROOT/'private/ladder/ladder-1.0.0.json')
    p.add_argument('--maps',type=Path,default=ROOT/'private/maps/calibration')
    p.add_argument('--fixed-timing',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=6)
    p.add_argument('--resume',action='store_true')
    p.set_defaults(handler=cli)


def cli(args):
    r=calibrate(args.ladder,args.maps,args.out,fixed_timing=args.fixed_timing,jobs=args.jobs,resume=args.resume)
    print(json.dumps(r,indent=2,allow_nan=False))
    return 0 if r['passed'] else 2
