"""Recomputable outcome/process scores, with the original paired-map bootstrap."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
import json
from math import ceil, isclose
from pathlib import Path
from random import Random
from statistics import fmean

METRICS = ('tower','deposit','damage')


@dataclass(frozen=True)
class Config:
    weight: float
    metrics: dict[str, float]


def load_config(path: Path) -> Config:
    obj = json.loads(path.read_bytes())
    w, weights = obj['processWeight'],obj['metricWeights']
    if (obj.get('schemaVersion')!=1 or type(w) not in (int,float) or not (w==0 or .2<=w<=.3)
            or set(weights)!=set(METRICS) or any(type(x) not in (int,float) or not 0<=x<=1 for x in weights.values())
            or not isclose(sum(weights.values()),1,rel_tol=0,abs_tol=1e-10)):
        raise ValueError('invalid scoring proposal')
    return Config(w,weights)


def shares(result: dict, seat: int, turn_limit: int) -> dict:
    peer = 1-seat
    def share(key):
        pair = result[key]
        return pair[seat]/(pair[seat]+pair[peer]) if sum(pair) else .5
    winner = result['winner']
    return {'tower':share('scores'), 'deposit':share('deposited'), 'damage':share('damageEffective'),
            'survival':1.0 if winner in (None,seat) else result['turns']/turn_limit}


def raw_game(opponent, map_slot, seat, result, turn_limit):
    win = result['winner']
    fault = result['faults'][seat]
    return {'opponent':opponent,'mapSlot':map_slot,'seat':seat,
            'outcome':.5 if win is None else float(win==seat), 'shares':shares(result,seat,turn_limit),
            'baseWin':win==seat and result['reason']=='base_destroyed',
            'fault':fault, 'warningCount':result['warnings'][seat], 'endReason':result['reason']}


def process(game, config):
    if game['fault']:
        return 0.0
    if game['baseWin']:
        return 1.0
    return sum(config.metrics[k]*game['shares'][k] for k in METRICS)


def percentile(values,p):
    if not values:
        return None
    ordered=sorted(values,key=lambda v: float(v) if not isinstance(v,str) else {
        '-infinity':float('-inf'),'+infinity':float('inf')}[v])
    return ordered[max(0,ceil(p*len(ordered))-1)]


@lru_cache(maxsize=4)
def resamples(count=24, samples=4000, seed=4219):
    r=Random(seed)
    draws=[]
    for _ in range(samples):
        weights=[0]*count
        for _ in range(count):
            weights[r.randrange(count)]+=1
        draws.append(tuple(weights))
    return tuple(draws)


@lru_cache(maxsize=100_000)
def expected(elo, opponent):
    return 1/(1+10**((opponent-elo)/400))


def fixed_elo(counts_at_elo):
    """Fit one rating against frozen opponents. Report true separated limits."""
    games=sum(n for _,n,_ in counts_at_elo)
    wins=sum(p for _,_,p in counts_at_elo)
    if not games:
        return None
    if wins==0: return '-infinity'
    if wins==games: return '+infinity'
    lo=min(e for e,_,_ in counts_at_elo)-8000
    hi=max(e for e,_,_ in counts_at_elo)+8000
    for _ in range(36):
        mid=(lo+hi)/2
        predicted=sum(n*expected(mid,elo) for elo,n,_ in counts_at_elo if n)
        if predicted>wins: hi=mid
        else: lo=mid
    return (lo+hi)/2


def make_panel(games, ladder, config):
    groups=defaultdict(lambda:defaultdict(list))
    seen=set()
    slots={m.code:set(m.slots) for m in ladder.members}
    for game in games:
        c,m,seat=game['opponent'],game['mapSlot'],game['seat']
        if m not in slots.get(c,set()) or seat not in (0,1) or (c,m,seat) in seen:
            raise ValueError('duplicate or unscheduled scoring slot')
        seen.add((c,m,seat))
        groups[c][m].append(game)
    panel=[]
    for level in ladder.levels:
        tier=[]
        for member in level:
            cells=[]
            for m in member.slots:
                rows=groups[member.code].get(m,[])
                if rows:
                    cells.append((m,len(rows),sum(g['outcome'] for g in rows),sum(process(g,config) for g in rows)))
            tier.append((member.elo,cells))
        panel.append(tier)
    return panel


def draw_score(panel,weights,config,*,with_elo=False):
    """Reject a replicate with any unobserved member, as in B item 5/6."""
    outcome, process_, opponents = [],[],[]
    for tier in panel:
        a,b=[],[]
        for rating,cells in tier:
            n=o=p=0
            for slot,games,points,other in cells:
                k=weights[slot]
                n+=k*games; o+=k*points; p+=k*other
            if not n: return None
            a.append(o/n); b.append(p/n)
            if with_elo: opponents.append((rating,n,o))
        outcome.append(fmean(a));process_.append(fmean(b))
    return (fmean(outcome), fmean(process_), fixed_elo(opponents) if with_elo else None)


def point_levels(games,ladder,config):
    by=defaultdict(list)
    for g in games: by[g['opponent']].append(g)
    result=[]
    for i,tier in enumerate(ladder.levels):
        panels=[by[m.code] for m in tier if by[m.code]]
        o=fmean(fmean(g['outcome'] for g in p) for p in panels) if panels else None
        proc=fmean(fmean(process(g,config) for g in p) for p in panels) if panels else None
        wdl=Counter(g['outcome'] for p in panels for g in p)
        score=(1-config.weight)*o+config.weight*proc if o is not None else None
        result.append({'level':f'L{i}','score':score,'outcome':o,'process':proc,
            'games':sum(wdl.values()),'w':wdl[1.0],'d':wdl[.5],'l':wdl[0.0]})
    return result


def summarize(games,ladder,config,*,samples=4000,elo=True):
    panel=make_panel(games,ladder,config)
    levels=point_levels(games,ladder,config)
    missing=len(ladder.members)*14-len(games)
    best=next((l['level'] for l in reversed(levels) if l['outcome'] is not None and l['outcome']>=.5),None)
    point=None if missing else draw_score(panel,[1]*24,config,with_elo=elo)
    valid=[d for weights in resamples(samples=samples) if (d:=draw_score(panel,weights,config,with_elo=elo)) is not None] if point else []
    bounds=lambda v:[percentile(v,.025),percentile(v,.975)]
    combined=lambda d:(1-config.weight)*d[0]+config.weight*d[1]
    eb=bounds([x[2] for x in valid]) if valid and elo else [None,None]
    return {'headline':combined(point) if point else None,'headlineOutcomeOnly':point[0] if point else None,
            'headlineProcess':point[1] if point else None,
            'interval95':bounds([combined(d) for d in valid]),'outcomeInterval95':bounds([d[0] for d in valid]),
            'processInterval95':bounds([d[1] for d in valid]),
            'elo':{'value':point[2] if point else None,'low':eb[0],'high':eb[1]},
            'bootstrap':{'seed':4219,'valid':len(valid),'unidentified':samples-len(valid),'samples':samples},
            'levels':levels,'highestHalfLevel':best,'games':len(games),'infraErrors':missing,
            'faults':{'compile':any(g['fault']=='compile_failed' for g in games),
                'timeout':sum(bool(g['fault'] and 'timeout' in g['fault']) for g in games),
                'crash':sum(bool(g['fault'] and g['fault']!='compile_failed' and 'timeout' not in g['fault']) for g in games),
                'warnings':sum(g['warningCount'] for g in games)}}
