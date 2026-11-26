"""Twelve public practice games and a feedback-only export. No scoring imports."""
from collections import Counter
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from arena.core.journal import atomic_json, records
from arena.core.sandbox import ROOT
from arena.games.outpost.replay import verify
from arena.tournament import run_tournament

OPPONENTS=('Z-eco','Z-harass','Z-miner')
MAPS=('corridor-01.map','open-01.map')
HEADER_PUBLIC={'type','replayVersion','engineVersion','game','map','mapSha256','limits',
               'params','seeds','initialStateHash','ruleset','compileFaults'}
RESULT_PUBLIC={'winner','reason','turns','scores','deposited','base_hp','faults','timeouts','warnings','damageDealt'}


def export_replay(source, target, codes):
    """A complete v1-metrics replay without host paths or v2 scoring inputs."""
    with gzip.open(source,'rt',encoding='utf-8') as original, gzip.open(target,'xt',encoding='utf-8') as cleaned:
        header=json.loads(next(original))
        public={k:v for k,v in header.items() if k in HEADER_PUBLIC}
        public['bots']=[{'code':code,'sha256':b['sha256']} for code,b in zip(codes,header['bots'],strict=True)]
        cleaned.write(json.dumps(public)+'\n')
        for text in original:
            row=json.loads(text)
            if row['type']=='result':
                result=row['result']
                row['result']={k:v for k,v in result.items() if k in RESULT_PUBLIC}
                row['result']['warnings']=[a+b for a,b in zip(result['warnings'],result['failedOrders'],strict=True)]
                text=json.dumps(row)+'\n'
            cleaned.write(text)
    verify(target)


def loss_priority(game):
    if game['outcome']!='loss': return None
    if game['ending']=='base_destroyed': return (0,game['turns'],game['game'])
    if game['ending'].startswith('turn_limit_'):
        s=game['seat']
        return (1,game['towerScore'][s]-game['towerScore'][1-s],game['game'])
    return None  # bot faults are in the diagnostic table, not fabricated losses by score


def scrimmage(submission: Path, out: Path, *, fixed_timing: Path, jobs=6, opponents=None, maps=None):
    pub=ROOT/'bots/public'; exercises=ROOT/'maps/scrimmage'
    opponents=tuple(opponents or (pub/c for c in OPPONENTS))
    maps=tuple(maps or (exercises/c for c in MAPS))
    def known(paths,parent):
        return all(p.absolute().parent==parent and not p.is_symlink() and p.resolve(strict=True).parent==parent for p in paths)
    if (len({p.name for p in opponents})!=3 or len(opponents)!=3 or not known(opponents,pub)
            or len({p.name for p in maps})!=2 or len(maps)!=2 or not known(maps,exercises)):
        raise ValueError('scrimmage needs three different public opponents and two public exercise maps')
    out=out.resolve()
    if out.exists() or out.is_relative_to(submission.resolve()):
        raise ValueError('choose a fresh practice feedback directory outside the submitted bot')
    # Do not put worker artifacts, host paths, or raw metrics in the feedback folder.
    rid=uuid4().hex
    runs=ROOT/'private' if submission.resolve().is_relative_to(ROOT/'private') or fixed_timing.resolve().is_relative_to(ROOT/'private') else ROOT/'runs'
    batch=runs/'scrimmage-raw'/rid
    summary=run_tournament([submission,*opponents],maps,batch,jobs=jobs,focus=0,seeds=[17,29],
        sandbox='bwrap',fixed_timing=fixed_timing,submission_index=0)
    rows=sorted(records(batch/'results.jsonl'),key=lambda r:(max(r['players']),r['mapIndex'],r['swapped']))
    if len(rows)!=summary['completed']:
        raise ValueError('inconsistent scrimmage completion receipt')
    info=[]; snapshots=[]; losses=[]; seen=set()
    for game_id,row in enumerate(rows,1):
        s=row['players'].index(0); i=row['players'][1-s]
        slot=(i,row['mapIndex'],s)
        if slot in seen: raise ValueError('duplicate practice slot')
        seen.add(slot)
        path=Path(row['replay']).resolve(strict=True)
        if not path.is_relative_to(batch) or sha256(path.read_bytes()).hexdigest()!=row['replaySha256']:
            raise ValueError('practice replay missing or changed')
        def capture(state):
            if state.turn%25: return
            units=Counter((u.owner,u.kind) for u in state.units.values())
            towers=Counter(t.owner for t in state.towers.values())
            for p in state.players:
                snapshots.append([game_id,state.turn,p.id,p.energy,p.score,p.base_hp,p.deposited,
                                  units[p.id,'W'],units[p.id,'S'],towers[p.id]])
        result=verify(path,on_state=capture)['result']
        if result!=row['result']: raise ValueError('practice ledger/replay disagreement')
        winner=result['winner']; opponent=opponents[i-1].name
        record={'game':game_id,'opponent':opponent,'map':maps[row['mapIndex']].name,'seat':s,
                'outcome':'draw' if winner is None else 'win' if winner==s else 'loss',
                'ending':result['reason'],'turns':result['turns'],'towerScore':result['scores'],
                'deposited':result['deposited'],'baseHp':result['base_hp'],'timeouts':result['timeouts'],
                'compileFailures':[int(f=='compile_failed') for f in result['faults']],
                'crashes':[int(bool(f and f!='compile_failed' and 'timeout' not in f)) for f in result['faults']],
                'warnings':result['warnings']}
        info.append(record)
        priority=loss_priority(record)
        if priority is not None:
            codes=['submission' if j==s else opponent for j in (0,1)]
            losses.append((priority,game_id,path,codes))
    out.mkdir(parents=True,exist_ok=False)
    chosen=[]
    for _,game_id,path,codes in sorted(losses)[:3]:
        dest=out/f'loss-{game_id:02}.hrw.jsonl.gz'
        export_replay(path,dest,codes)
        chosen.append(dest.name)
    status='complete' if len(info)==12 else 'incomplete'
    if len(info)>12 or summary['tasks']!=12:
        raise ValueError('invalid practice batch shape')
    report={'schemaVersion':1,'status':status,'games':info,'completed':len(info),'expected':12,
            'infraErrors':12-len(info),'worstLossReplays':chosen}
    atomic_json(out/'results.json',report)
    with (out/'turns.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['game','turn','player','energy','towerScore','baseHp','deposited','workers','soldiers','towers'])
        w.writerows(snapshots)
    with (out/'results.md').open('x',encoding='utf-8') as f:
        f.write(f'# 公开练习赛\n\n已完成 {len(info)} / 12 局。以下双方数据按 0、1 号玩家顺序列出。\n\n')
        f.write('| 对手 | 地图 | 座位 | 胜负 | 结束原因 | 塔分 | 卸货 | 基地生命 | 超时 | 崩溃 | 编译失败 | 警告 |\n')
        f.write('| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n')
        for g in info:
            keys=('opponent','map','seat','outcome','ending','towerScore','deposited','baseHp',
                  'timeouts','crashes','compileFailures','warnings')
            f.write('| '+' | '.join(str(g[k]) for k in keys)+' |\n')
    return report


def register(commands):
    p=commands.add_parser('scrimmage',help='run twelve public practice games and export feedback')
    p.add_argument('--submission',type=Path,required=True)
    p.add_argument('--opponents',type=Path,nargs=3)
    p.add_argument('--maps',type=Path,nargs=2)
    p.add_argument('--fixed-timing',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=6)
    p.add_argument('--out',type=Path,required=True)
    p.set_defaults(handler=cli)


def cli(args):
    r=scrimmage(args.submission,args.out,fixed_timing=args.fixed_timing,jobs=args.jobs,
                opponents=args.opponents,maps=args.maps)
    print(json.dumps({k:r[k] for k in ('status','completed','expected','infraErrors')},indent=2))
    return 0 if r['status']=='complete' else 2
