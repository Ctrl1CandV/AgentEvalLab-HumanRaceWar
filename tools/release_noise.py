"""One grading run with the work order's six trusted CPU-only load processes."""
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

from arena.grade import grade


@contextmanager
def cpu_load(count=6):
    processes=[]
    try:
        for _ in range(count):
            processes.append(subprocess.Popen([sys.executable,'-B','-c','while True: pass'],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        yield
    finally:
        for worker in processes:
            if worker.poll() is None: worker.terminate()
        for worker in processes:
            try: worker.wait(timeout=4)
            except subprocess.TimeoutExpired:
                worker.kill();worker.wait()


def main():
    import argparse, json
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('submission','ladder','maps','fixed-timing','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    with cpu_load():
        value=grade(args.submission,args.ladder,args.maps,args.out,fixed_timing=args.fixed_timing)
    print(json.dumps({k:value[k] for k in ('status','headline','headlineOutcomeOnly','games','wallSeconds')},indent=2))
    return 0 if value['status']=='complete' else 2


if __name__=='__main__': raise SystemExit(main())
