"""Materialize standalone public zoo baselines and optional ranged probes."""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTS = (20, 45, 70, 95, 120, 155, 200)
RESERVES = (0, 80, 160, 320)


def fixed_codes():
    return {f'fixed-{t:03}-{r:03}': (t, r) for t in STARTS for r in RESERVES}


def build(dest: Path, *, probes: bool = False):
    bots = json.loads((ROOT/'bots/catalog.json').read_bytes())['bots']
    policy = (ROOT/'bots/prototypes/ranged/research.hpp').read_bytes()
    entries = {}
    dest.mkdir(parents=True, exist_ok=False)
    for bot in bots:
        code = bot['name']
        origin = ROOT/'bots/public'/code
        files = {f:(origin/f).read_bytes() for f in ('main.cpp','strategy.hpp')}
        if {f:sha256(raw).hexdigest() for f,raw in files.items()} != bot['sourceSha256']:
            raise ValueError(f'frozen zoo drift: {code}')
        main = files['main.cpp'].replace(b'#include "strategy.hpp"', b'#include "research.hpp"')
        if main.count(b'return zoo::run(')!=1 or main.count(b'});')!=1:
            raise ValueError(f'unexpected zoo entry point: {code}')
        main = main.replace(b'return zoo::run(', b'return research::run(')
        options = {code:b''}
        if code=='M-balanced' and probes:
            options.update({c:f', research::Policy::Fixed, {t}, {r}'.encode('ascii') for c,(t,r) in fixed_codes().items()})
            options['adaptive'] = b', research::Policy::Adaptive'
        for name, suffix in options.items():
            target=dest/name
            target.mkdir()
            entries[name]={}
            for filename, raw in {'main.cpp':main.replace(b'});',b'}'+suffix+b');'),
                                  'strategy.hpp':files['strategy.hpp'],'research.hpp':policy}.items():
                with (target/filename).open('xb') as f: f.write(raw)
                entries[name][filename]=sha256(raw).hexdigest()
    return entries


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--probes',action='store_true')
    args=parser.parse_args()
    print(json.dumps(build(args.destination,probes=args.probes),indent=2,sort_keys=True))
