"""Public zoo source consistency and an actual swapped-seat strategy regression."""
from hashlib import sha256
import gzip
import json
from pathlib import Path
import unittest
from uuid import uuid4

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, prepare
from arena.match import play
from tools.generate_zoo import STYLES

ROOT=Path(__file__).resolve().parents[1]


def rotate(line,width,height):
    f=line.split(); kind=f[0]
    if kind=='END': return line
    if kind=='MOVE': f[1]=str(int(f[1])^1); f[2]={'N':'S','S':'N','E':'W','W':'E'}[f[2]]
    else:
        offset=1 if kind=='FIRE' else 2
        if kind in ('ATTACK','MINE','BUILD'): f[1]=str(int(f[1])^1)
        f[offset]=str(width-1-int(f[offset])); f[offset+1]=str(height-1-int(f[offset+1]))
    return ' '.join(f)


def turns(path):
    with gzip.open(path,'rt') as stream: return [row for row in map(json.loads,stream) if row['type']=='turn']


class ZooTests(unittest.TestCase):
    def test_catalog_standalone_sources_match_template_and_configs(self):
        catalog=json.loads((ROOT/'bots/catalog.json').read_text())
        self.assertEqual(set(STYLES),{b['name'] for b in catalog['bots']})
        self.assertEqual(len(STYLES),10)
        template=(ROOT/'tools/zoo_strategy.hpp').read_bytes()
        self.assertEqual(sha256(template).hexdigest(),catalog['strategyTemplateSha256'])
        for bot in catalog['bots']:
            self.assertEqual(list(STYLES[bot['name']]),bot['configuration'])
            for file,digest in bot['sourceSha256'].items():
                self.assertEqual(sha256((ROOT/bot['path']/file).read_bytes()).hexdigest(),digest)
            self.assertEqual((ROOT/bot['path']/'strategy.hpp').read_bytes(),template)

    def test_random_and_miner_swapped_seats_rotate_every_command(self):
        out=ROOT/'runs/development/zoo-tests'/uuid4().hex; out.mkdir(parents=True)
        sources=[ROOT/'bots/public'/name for name in ('Z-random','Z-miner')]
        with CpuLease(1) as lease:
            launcher=Bubblewrap(); launcher.cpus=lease.cpus
            prepared=[prepare(p,out/f'prepared-{i}',launcher,lease.cpus[0]) for i,p in enumerate(sources)]
        text=(ROOT/'maps/scrimmage/open-01.map').read_text()
        a=play(sources,text,out/'matches',[17,29],prepared=prepared)
        b=play(sources[::-1],text,out/'matches',[29,17],prepared=prepared[::-1])
        for r in (a,b): self.assertEqual(r['result']['faults'],[None,None])
        aa,bb=turns(a['replay']),turns(b['replay'])
        self.assertEqual(len(aa),len(bb))
        width,height=map(int,text.splitlines()[0].split()[1:])
        for x,y in zip(aa,bb):
            for player in (0,1):
                expected=[rotate(line,width,height) for line in x['replies'][player]['lines']]
                self.assertEqual(expected,y['replies'][1-player]['lines'],f'turn {x["turn"]}, player {player}')


if __name__=='__main__': unittest.main()
