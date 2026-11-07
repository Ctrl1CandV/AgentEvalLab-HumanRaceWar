"""One bounded six-slot sandbox timeout/cleanup campaign; no host fault injection."""
import argparse
import json
from pathlib import Path
import time

from arena.core.journal import records
from arena.tournament import run_tournament
from tools.audit_replays import audit

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''import hrw,threading,resource,ctypes,errno
hrw.read_setup();hrw.ready();hrw.read_turn()
assert resource.getrlimit(resource.RLIMIT_NPROC)==(16,16)
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(1,0,0,0,0)==-1 and ctypes.get_errno()==errno.EPERM
threading.stack_size(262144)
event=threading.Event();threads=[]
for i in range(32):
 try:
  t=threading.Thread(target=event.wait,daemon=True);t.start();threads.append(t)
 except RuntimeError: break
assert 1<=len(threads)<=15
# Deliberately exhaust CPU bank. Maximum 12 bots, each one bound CPU,
# 16 kernel tasks and 512MiB AS; no host OOM or unbounded process creation.
while True: pass
'''


def process_state(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    sources = []
    for name in ('threaded-timeout-a', 'threaded-timeout-b'):
        p = out/name; p.mkdir(); (p/'main.py').write_text(PROBE); sources.append(p)
    maps = sorted((ROOT/'maps/scrimmage').glob('*.map'))[:3]
    summary = run_tournament(sources, maps, out/'batch', jobs=6)
    rows = records(out/'batch/results.jsonl')
    pids = {pid for row in rows for pid in row.get('sandboxPids', [])}
    deadline = time.monotonic()+3
    while any(process_state(p) not in (None, 'Z') for p in pids) and time.monotonic()<deadline:
        time.sleep(.02)
    report = {'scope': 'bounded 6 concurrent games/12 bots; threaded timeout and cleanup',
              'summary': summary, 'results': [{'taskId': r['taskId'], 'result': r['result'],
                  'botCpuNs': r['botCpuNs'], 'harnessCpuNs': r['harnessCpuNs'], 'wallNs': r['wallNs'],
                  'replay': r['replay']} for r in rows],
              'sandboxPidStatesAfterCompletion': {str(pid): process_state(pid) for pid in sorted(pids)},
              'replayAudit': audit([r['replay'] for r in rows]),
              'allCorrectTimeouts': len(rows)==6 and all(r['result']['turns']==0 and
                  r['result']['faults']==['cpu_timeout', 'cpu_timeout'] for r in rows),
              'allKnownLeadersStopped': all(process_state(pid) in (None, 'Z') for pid in pids),
              'limits': 'Leader/namespace cleanup plus separate descendant probes; not all kernel attack surfaces or hard aggregate compiler resources.',
              'totalCpuHours': None}
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('allCorrectTimeouts','allKnownLeadersStopped')}, indent=2))


if __name__ == '__main__':
    main()
