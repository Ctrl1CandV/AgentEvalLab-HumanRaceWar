"""Summarize one immutable zoo batch, with map-cluster bootstrap and replay audit.

Run as: .venv/bin/python -m tools.analyze_zoo BATCH --out NEW_DIRECTORY
No bots are executed and different batches are never pooled.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import csv
import json
import math
from pathlib import Path
import random
import statistics

from arena.core.journal import records
from arena.tournament import fingerprint
from tools.audit_replays import audit

ROOT=Path(__file__).resolve().parents[1]
REPLICATES=4000
BOOTSTRAP_SEED=4219
SINGLES=('Z-miner','Z-rush','Z-wrush','Z-eco','Z-turtle','Z-towers','Z-harass')


def percentile(values,p):
    values=sorted(values)
    return values[max(0,math.ceil(len(values)*p)-1)] if values else None


@lru_cache(maxsize=None)
def interval(values):
    """Each value is a map-cluster mean; paired seats stay together."""
    if not values: return [None,None]
    if len(set(values))==1: return [values[0],values[0]]
    rng=random.Random(BOOTSTRAP_SEED)
    estimates=[statistics.fmean(rng.choices(values,k=len(values))) for _ in range(REPLICATES)]
    return [percentile(estimates,.025),percentile(estimates,.975)]


def summarize(entries):
    # Entries are (map index, score), score in {0,.5,1}.
    groups=defaultdict(list)
    for index,score in entries: groups[index].append(score)
    scores=[score for _,score in entries]
    n=len(scores); wins=sum(s==1 for s in scores); draws=sum(s==.5 for s in scores)
    return {'games':n,'maps':len(groups),'wins':wins,'draws':draws,'losses':n-wins-draws,
            'winRate':wins/n if n else None,'scoreRate':statistics.fmean(scores) if n else None,
            'winRateCI95':interval(tuple(sorted(statistics.fmean(s==1 for s in v) for v in groups.values()))),
            'scoreRateCI95':interval(tuple(sorted(statistics.fmean(v) for v in groups.values())))}


def relative(value):
    if isinstance(value,dict): return {k:relative(v) for k,v in value.items()}
    if isinstance(value,list): return [relative(v) for v in value]
    if isinstance(value,str) and value.startswith(str(ROOT)+'/'): return str(Path(value).relative_to(ROOT))
    return value


def analyze(batch,out,*,jobs=4):
    batch=batch.resolve(); out=out.resolve()
    manifest=json.loads((batch/'manifest.json').read_text()); request=manifest['request']
    private=ROOT/'private'
    if (batch.is_relative_to(private) or any(Path(p).resolve().is_relative_to(private)
            for p in request['sources']+request['maps'])) and not out.is_relative_to(private):
        raise ValueError('private inputs require a private report')
    if out.exists(): raise ValueError('report directory already exists; do not overwrite evidence')
    names=manifest['bots']; tasks={r['taskId']:r for r in manifest['tasks']}
    if set(names)!=set(SINGLES)|{'M-balanced','Z-idle','Z-random'} or request['sandbox']!='bwrap':
        raise ValueError('this analyzer expects the ten named zoo bots in a host-visible bwrap batch')
    rows=records(batch/'results.jsonl'); attempts=records(batch/'attempts.jsonl')
    ids=[r['taskId'] for r in rows]
    if len(ids)!=len(set(ids)) or not set(ids)<=set(tasks): raise ValueError('duplicate or unknown completed task')
    for row in rows:
        task=tasks[row['taskId']]
        if row['mapType'] not in ('open','corridor','island','maze'): raise ValueError('unknown map type')
        if any(row[k]!=task[k] for k in ('players','seeds','mapIndex')): raise ValueError('task metadata changed')
        if row['status']!='complete' or sha256(Path(row['replay']).read_bytes()).hexdigest()!=row['replaySha256']:
            raise ValueError('completed replay/status changed')
    replay_audit=audit([r['replay'] for r in rows],jobs=jobs)
    complete=set(ids)==set(tasks)
    public_hashes={sha256(p.read_bytes()).hexdigest() for p in (ROOT/'maps/public').glob('*.map')}
    report={'schemaVersion':1,'scope':'one batch only; scrimmage reports are diagnostic, never D6 acceptance',
            'batch':str(batch),'request':request,'bots':names,'expectedGames':len(tasks),'completedGames':len(rows),
            'complete':complete,'attemptCounts':dict(Counter(r['status'] for r in attempts)),
            'inputsSha256':{name:sha256((batch/name).read_bytes()).hexdigest() for name in ('manifest.json','results.jsonl','attempts.jsonl')},
            'verificationFramework':fingerprint(),'executionFramework':request['framework'],
            'replayAudit':replay_audit,'bootstrap':{'unit':'map; both swapped seats retained together',
                'replicates':REPLICATES,'seed':BOOTSTRAP_SEED,'interval':'95% percentile, nearest-rank endpoints',
                'limits':'Conditional on this map collection and these bot seeds. No multiple-testing correction or timing authentication.'},
            'rateDefinitions':{'winRate':'wins / games','scoreRate':'(wins + .5 * draws) / games'},
            'humanReview':'pending','phaseAComplete':False}
    eligible=complete and len(public_hashes)==40 and set(request['mapHashes'])==public_hashes and len(rows)==3680
    report['eligiblePublicD6Matrix']=eligible
    report['botFaultGames']=sum(any(r['result']['faults']) for r in rows)
    report['protocolWarnings']=sum(sum(r['result']['warnings']) for r in rows)
    overheads=[x for r in rows for x in r.get('turnHarnessCpuNs',[])]
    report['recordedUsage']={'botCpuNs':sum(sum(r['botCpuNs']) for r in rows) if all('botCpuNs' in r for r in rows) else None,
        'matchHarnessCpuNs':sum(r['harnessCpuNs'] for r in rows) if all('harnessCpuNs' in r for r in rows) else None,
        'turnHarnessCpuNsP95':percentile(overheads,.95),'turnHarnessCpuNsMax':max(overheads,default=None),
        'replayVerificationCpuNs':replay_audit['verificationCpuNs'],'totalCpuHours':None,
        'limits':'These counters exclude compilation, controller startup/dispatch and other uncaptured work. No RUSAGE_CHILDREN sums added.'}
    if complete:
        cells=defaultdict(list); seats=defaultdict(lambda:defaultdict(lambda:[[],[]]))
        self_rows=[]; non_idle=[]; type_diagnostics=defaultdict(lambda:Counter())
        for row in rows:
            a,b=[names[i] for i in row['players']]; result=row['result']; winner=result['winner']
            d=type_diagnostics[row['mapType']]
            d['games']+=1; d['turns']+=result['turns']; d['failedMoves']+=sum(result['failedMoves'])
            d['failedOrders']+=sum(result['failedOrders']); d['buildContested']+=sum(result['buildContested'])
            d['buildContestedSites']+=result['buildContestedSites']; d['baseEndings']+=result['reason'].endswith('base_destroyed')
            if a==b:
                if a=='M-balanced': self_rows.append(row)
                continue
            if 'Z-idle' not in (a,b): non_idle.append(row)
            for side,(bot,opponent) in enumerate(((a,b),(b,a))):
                score=.5 if winner is None else float(winner==side)
                for typ in ('all',row['mapType']): cells[bot,opponent,typ].append((row['mapIndex'],score))
                seats[bot][row['mapIndex']][side].append(score)
        matrix=[dict(bot=key[0],opponent=key[1],mapType=key[2],**summarize(value)) for key,value in sorted(cells.items())]
        lookup={(r['bot'],r['opponent'],r['mapType']):r for r in matrix}
        fairness=[]
        for bot,groups in sorted(seats.items()):
            differences=[statistics.fmean(v[0])-statistics.fmean(v[1]) for v in groups.values()]
            delta=statistics.fmean(differences); ci=interval(tuple(sorted(differences)))
            fairness.append({'bot':bot,'maps':len(groups),'seatScoreRateDifference':delta,'CI95':ci,
                             'within3PointsAndCIContainsZero':abs(delta)<=.03+1e-12 and ci[0] is not None and ci[1] is not None and ci[0]<=0<=ci[1]})
        lengths=[r['result']['turns'] for r in self_rows]
        endings=Counter(r['result']['reason'] for r in self_rows)
        base=sum(n for reason,n in endings.items() if reason.endswith('base_destroyed'))
        score=sum(n for reason,n in endings.items() if reason.startswith('turn_limit_'))
        self_summary={'games':len(self_rows),'maps':len({r['mapIndex'] for r in self_rows}),
                      'medianTurns':statistics.median(lengths) if lengths else None,
                      'by60Fraction':sum(n<=60 for n in lengths)/len(lengths) if lengths else None,
                      'endReasons':dict(endings),'baseEndingFraction':base/len(lengths) if lengths else None,
                      'turnLimitFraction':score/len(lengths) if lengths else None,
                      'seedWinners':dict(Counter('draw' if r['result']['winner'] is None else str(r['seeds'][r['result']['winner']]) for r in self_rows))}
        types=sorted({r['mapType'] for r in rows})
        rate_checks={}
        for rate in ('winRate','scoreRate'):
            counters={bot:[other for other in SINGLES if other!=bot and lookup[bot,other,'all'][rate]<.5] for bot in SINGLES}
            rate_checks[rate]={'counters':counters,'eachSingleLosesToAnother':all(counters.values()),
                'balancedOverall70':all(lookup['M-balanced',bot,'all'][rate]>=.7 for bot in SINGLES),
                'balancedEveryType55':all(lookup['M-balanced',bot,typ][rate]>=.55 for bot in SINGLES for typ in types)}
        draw_rate=sum(r['result']['winner'] is None for r in non_idle)/len(non_idle)
        checks={'fairness':all(r['within3PointsAndCIContainsZero'] for r in fairness),
                'drawRateBelow10':draw_rate<.1,'selfMedianAtLeast120':bool(lengths) and statistics.median(lengths)>=120,
                'selfBy60Below20':bool(lengths) and self_summary['by60Fraction']<.2,
                'bothEndings20To80':bool(lengths) and .2<=self_summary['baseEndingFraction']<=.8 and .2<=self_summary['turnLimitFraction']<=.8,
                'noBotFaultsOrProtocolWarnings':report['botFaultGames']==0 and report['protocolWarnings']==0}
        report.update(matrix=matrix,fairness=fairness,balancedSelf=self_summary,
                      drawRateExcludingIdleAndSameName=draw_rate,diagnosticsByMapType=dict(type_diagnostics),
                      observedChecks=checks,rateChecks=rate_checks)
        report['numericalBalanceConditionsMetUnderBothRateConventions']=all(checks.values()) and all(
            all(v[key] for key in ('eachSingleLosesToAnother','balancedOverall70','balancedEveryType55')) for v in rate_checks.values())
    else:
        report['statisticsWithheld']='Incomplete task set; missing games must not silently disappear from denominators.'
    out.mkdir(parents=True)
    groups=defaultdict(list)
    for row in rows: groups[row['mapType']].append(row)
    for typ,group in sorted(groups.items()):
        with (out/f'games-{typ}.csv').open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['taskId','matchId','attempt','map','bot0','bot1','seed0','seed1','resultJson','wallNs','harnessCpuNs','botCpuNs','replay','replaySha256'])
            for r in group:
                writer.writerow([r['taskId'],r['matchId'],r['attempt'],r['mapName'],*[names[i] for i in r['players']],*r['seeds'],
                    json.dumps(r['result'],separators=(',',':')),r['wallNs'],r.get('harnessCpuNs'),json.dumps(r.get('botCpuNs')),
                    relative(r['replay']),r['replaySha256']])
    (out/'report.json').write_text(json.dumps(relative(report),indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch',type=Path); parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args(); result=analyze(args.batch,args.out,jobs=args.jobs)
    print(json.dumps({k:v for k,v in result.items() if k in ('expectedGames','completedGames','eligiblePublicD6Matrix','observedChecks','rateChecks','balancedSelf','recordedUsage')},indent=2))
