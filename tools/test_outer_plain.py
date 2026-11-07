"""Exercise plain only within an explicit outer bwrap (never on the host)."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from arena.core.sandbox import ENV, snapshot


def run(out: Path):
    work=out.resolve()/uuid4().hex; work.mkdir(parents=True)
    workspace=work/'workspace'; workspace.mkdir()
    for name in ('arena','sdk','maps'): snapshot(ROOT/name,workspace/name)
    (workspace/'tmp').mkdir()
    marker=work/'contract.json'
    marker.write_text(json.dumps({'version':1,'network':'disabled','files':'isolated','purpose':'local-tools-only'}))
    probe='''import json,sys
from pathlib import Path
sys.path.insert(0,'/workspace')
from arena.check import check
from arena.match import play
from arena.games.outpost.replay import verify
from arena.core.benchmark import run_benchmark,workload_digest
from arena.core.timing import Calibration
base=Path('/workspace')
checks=[check(base/'sdk'/lang/'example',base/'evidence/checks',sandbox='plain') for lang in ('python','cpp')]
bench=run_benchmark(base/'evidence/bench',jobs=1,samples=1,sandbox='plain')
cal=Calibration.load(Path(bench['resultFile']),workload_digest(),jobs=1)
row=play([base/'sdk/python/example',base/'sdk/cpp/example'],(base/'maps/scrimmage/open-01.map').read_text(),base/'evidence/matches',[17,29],sandbox='plain',calibration=cal)
verified=verify(Path(row['replay']))['verified'] if row['status']=='complete' else False
report={'passed':all(r['passed'] for r in checks) and row['status']=='complete' and verified,'checks':checks,'bench':bench,'match':row,'replayVerified':verified}
print(json.dumps(report))
'''
    (workspace/'probe.py').write_text(probe)
    args=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL',
          '--proc','/proc','--dev','/dev']
    for path in ('/usr','/bin','/sbin','/lib','/lib32','/lib64','/libx32'): args+=['--ro-bind-try',path,path]
    args+=['--ro-bind',str(Path(sys.base_prefix).resolve()),'/runtime','--bind',str(workspace),'/workspace',
           '--bind',str(workspace/'tmp'),'/tmp','--ro-bind',str(marker),'/hrw-outer-sandbox.json',
           '--remount-ro','/dev','--remount-ro','/','--clearenv','--setenv','PATH','/usr/bin:/bin',
           '--chdir','/workspace','--','/runtime/bin/'+Path(sys.executable).resolve().name,'-I','-S','/workspace/probe.py']
    cpus=sorted(os.sched_getaffinity(0))[:8]
    with (work/'stdout.json').open('wb') as stdout,(work/'stderr.log').open('wb') as stderr:
        process=subprocess.run(args,env=ENV,stdout=stdout,stderr=stderr,timeout=90,
                               preexec_fn=lambda:os.sched_setaffinity(0,set(cpus)))
    report={'returncode':process.returncode,'directory':str(work),'outerSandbox':'bwrap','cpus':cpus}
    if process.returncode==0: report.update(json.loads((work/'stdout.json').read_text()))
    else: report['passed']=False
    (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    r=run(Path('runs/development/outer-plain'))
    print(json.dumps(r,indent=2))
    raise SystemExit(0 if r['passed'] else 1)
