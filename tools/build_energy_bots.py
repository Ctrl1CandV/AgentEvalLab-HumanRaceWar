"""Build source directories for the public energy prototype, without running bots."""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTS = (1, 45, 90, 135, 180, 225, 270)
RESERVES = (0, 80, 160, 320)


def fixed_codes():
    return {f'fixed-{t:03}-{r:03}': (t, r) for t in STARTS for r in RESERVES}


def build(dest: Path, *, probes: bool = False):
    """Materialize a fresh directory of standalone sources; keep frozen zoo intact."""
    catalog = json.loads((ROOT/'bots/catalog.json').read_bytes())['bots']
    activation = (ROOT/'bots/prototypes/energy/activation.hpp').read_bytes()
    entries = {}
    dest.mkdir(parents=True, exist_ok=False)
    for bot in catalog:
        name = bot['name']
        base = ROOT/'bots/public'/name
        frozen = {filename: (base/filename).read_bytes() for filename in ('main.cpp','strategy.hpp')}
        if {f: sha256(data).hexdigest() for f,data in frozen.items()} != bot['sourceSha256']:
            raise ValueError(f'frozen zoo drift: {name}')
        baseline = frozen['main.cpp'].replace(b'#include "strategy.hpp"', b'#include "activation.hpp"')
        if baseline.count(b'return zoo::run(') != 1 or baseline.count(b'});') != 1:
            raise ValueError(f'unexpected zoo entry point: {name}')
        baseline = baseline.replace(b'return zoo::run(', b'return activation::run(')
        variants = {name: b''}
        if probes and name == 'M-balanced':
            variants |= {
                code: f', activation::Policy::Fixed, {start}, {reserve}'.encode('ascii')
                for code,(start,reserve) in fixed_codes().items()
            }
            variants['adaptive'] = b', activation::Policy::Adaptive'
        for code,policy in variants.items():
            target = dest/code
            target.mkdir()
            files = {'main.cpp':baseline.replace(b'});', b'}'+policy+b');'),
                     'strategy.hpp':frozen['strategy.hpp'], 'activation.hpp':activation}
            for filename, data in files.items():
                with (target/filename).open('xb') as stream:
                    stream.write(data)
            entries[code] = {f:sha256(data).hexdigest() for f,data in files.items()}
    return entries


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--probes', action='store_true', help='also build fixed and adaptive M-based experiment probes')
    args = parser.parse_args()
    print(json.dumps(build(args.destination, probes=args.probes), indent=2, sort_keys=True))
