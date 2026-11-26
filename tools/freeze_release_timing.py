"""Freeze an existing host-local benchmark; no benchmark or bots are run here."""
import argparse
import json
from pathlib import Path

from arena.core.benchmark import workload_digest
from arena.core.sandbox import ROOT
from arena.core.timing import freeze_calibration
from arena.games.outpost import Outpost


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bench',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=6)
    args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(ROOT/'private'):
        parser.error('keep host-specific locks under private/')
    lock=freeze_calibration(args.bench,workload_digest(),jobs=args.jobs,base_limits=Outpost().limits,turns=300)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:
        json.dump(lock,stream,sort_keys=True,indent=2);stream.write('\n')
    print(out)


if __name__=='__main__': main()
