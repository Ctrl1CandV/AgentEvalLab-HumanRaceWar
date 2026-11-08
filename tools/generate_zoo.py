"""Materialize standalone SDK-based public baselines; never execute bots here."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STYLES={
    'Z-idle':('Idle',0,0,0,0),
    'Z-random':('Random',12,0,0,0),
    'Z-miner':('Miner',2,0,0,0),
    'Z-rush':('Rush',2,0,0,0),
    'Z-wrush':('WorkerRush',0,0,0,0),
    'Z-eco':('Economy',18,0,0,95),
    'Z-turtle':('Turtle',7,0,0,300),
    'Z-towers':('Towers',14,10,10,300),
    'Z-harass':('Harass',6,0,0,0),
    'M-balanced':('Balanced',9,3,4,80),
}


def generate(*, replace=False):
    shared=(ROOT/'tools/zoo_strategy.hpp').read_bytes()
    entries=[]
    for name,(mode,workers,builders,towers,attack) in STYLES.items():
        source=('#include "strategy.hpp"\n\nint main() {\n'
                f'    return zoo::run({{zoo::Mode::{mode}, {workers}, {builders}, {towers}, {attack}}});\n'
                '}\n').encode()
        directory=ROOT/'bots/public'/name
        directory.mkdir(parents=True,exist_ok=True)
        hashes={}
        for file,data in (('main.cpp',source),('strategy.hpp',shared)):
            path=directory/file
            if path.exists() and path.read_bytes()!=data and not replace: raise ValueError(f'refusing to overwrite different zoo source: {path}')
            path.write_bytes(data); hashes[file]=sha256(data).hexdigest()
        entries.append({'name':name,'configuration':[mode,workers,builders,towers,attack],
                        'path':str(directory.relative_to(ROOT)),'sourceSha256':hashes})
    report={'schemaVersion':1,'zooVersion':15,'status':'development, not strength calibrated',
            'strategyTemplateSha256':sha256(shared).hexdigest(),'bots':entries,
            'seedPolicy':'FNV-style decimal-seed folding and SplitMix finalizer; balanced worker goal +/-1 and assault turn +/-8; tie-breaking in rotational local coordinates.'}
    path=ROOT/'bots/catalog.json'
    if path.exists() and json.loads(path.read_text())!=report and not replace: raise ValueError('refusing different existing zoo catalog')
    path.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace',action='store_true',help='explicitly replace unfrozen generated zoo sources; preserve old attempts first')
    args=parser.parse_args()
    print(json.dumps(generate(replace=args.replace),indent=2))
