"""D1 registration, split and no-redraw guards; no real private maps or bots."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from arena.games.outpost.maps import parse_map
from tools import prepare_dev_maps as dev


class DevMapTests(unittest.TestCase):
    def test_frozen_generator_changes_are_rejected_before_drawing(self):
        with TemporaryDirectory() as d:
            root = Path(d); files = ('arena/games/outpost/mapgen.py', 'arena/games/outpost/maps.py', 'tools/prepare_final_holdout.py')
            hashes = {}
            for name in files:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('frozen')
                hashes[name] = sha256(path.read_bytes()).hexdigest()
            plan = root/'private/holdout-maps/generation-plan.json'; plan.parent.mkdir(parents=True)
            plan.write_text(json.dumps({'inputsSha256': hashes}))
            (root/files[0]).write_text('changed')
            with patch.object(dev.secrets, 'randbits') as draw:
                with self.assertRaisesRegex(ValueError, 'frozen'): dev.prerequisites(root)
                draw.assert_not_called()

    def test_eighty_maps_and_balanced_forty_map_first_stage(self):
        rows = dev.specs(); self.assertEqual(len(rows), 80)
        for kind in dev.TYPES:
            self.assertEqual(Counter(r['size'] for r in rows if r['type'] == kind), {s: 4 for s in (24, 28, 32, 36, 40)})
            self.assertEqual(Counter(r['size'] for r in rows if r['type'] == kind and r['selectionStage'] == 1),
                             {s: 2 for s in (24, 28, 32, 36, 40)})

    def test_plan_precedes_generation_is_registered_and_immutable(self):
        with TemporaryDirectory() as d, patch.object(dev, 'prerequisites', return_value={}), \
                patch.object(dev, 'existing_assets', return_value=[]), \
                patch.object(dev.secrets, 'randbits', side_effect=range(80)) as draw, \
                patch.object(dev, 'generate') as generate:
            root = Path(d); destination = root/'private/dev'
            dev.plan(destination, root=root); generate.assert_not_called()
            self.assertEqual(draw.call_count, 80); self.assertEqual(len(dev.check_plan(destination, root)['maps']), 80)
            before = (destination/'generation-plan.json').read_bytes()
            with self.assertRaises(ValueError): dev.plan(destination, root=root)
            self.assertEqual((destination/'generation-plan.json').read_bytes(), before)
            value = json.loads(before); value['maps'][0]['seed'] += 1000
            (destination/'generation-plan.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'registered'): dev.build(destination, root=root)
            generate.assert_not_called()

    def test_initial_collision_is_retained_not_redrawn(self):
        with TemporaryDirectory() as d, patch.object(dev, 'prerequisites', return_value={}), \
                patch.object(dev, 'existing_assets', return_value=[]), \
                patch.object(dev.secrets, 'randbits', return_value=7) as draw:
            root = Path(d); destination = root/'private/dev'
            with self.assertRaisesRegex(ValueError, 'collision'): dev.plan(destination, root=root)
            self.assertEqual(draw.call_count, 80)
            self.assertTrue(json.loads((destination/'generation-plan.json').read_text())['initialSeedCollision'])
            with self.assertRaises(ValueError): dev.plan(destination, root=root)
            self.assertEqual(draw.call_count, 80)

    def test_duplicate_generated_map_stops_without_replacement(self):
        with TemporaryDirectory() as d, patch.object(dev, 'prerequisites', return_value={}), \
                patch.object(dev, 'existing_assets', return_value=[]), \
                patch.object(dev.secrets, 'randbits', side_effect=range(80)) as draw:
            root = Path(d); destination = root/'private/dev'; dev.plan(destination, root=root)
            def candidate(kind, size, seed):
                return SimpleNamespace(text='synthetic map\n', metadata=lambda: {
                    'sha256': sha256(b'synthetic map\n').hexdigest(), 'requestedSeed': seed,
                    'acceptedSeed': seed, 'rejectedCandidates': []})
            with patch.object(dev, 'generate', side_effect=candidate) as generate:
                with self.assertRaisesRegex(ValueError, 'duplicate'): dev.build(destination, root=root)
                self.assertEqual(generate.call_count, 2)
            self.assertEqual(draw.call_count, 80)
            self.assertEqual(len(list(destination.rglob('*.map'))), 1)
            self.assertFalse((destination/'catalog.json').exists())

    def test_summary_excludes_paths_seeds_and_individual_digests(self):
        metrics = dev.independent_layout(parse_map((dev.ROOT/'maps/public/open-01.map').read_text()))
        rows = [{**r, 'sha256': 'SECRET_MAP_DIGEST', 'seed': 'SECRET_SEED', 'path': 'SECRET_PATH', 'metrics': metrics}
                for r in dev.specs()]
        summary = dev.summarize(rows)
        self.assertNotIn('SECRET', json.dumps(summary)); self.assertEqual(summary['maps'], 80)
        self.assertEqual(sum(summary['stageOneTypes'].values()), 40)

    def test_public_size_distribution_matches_registered_slots(self):
        entries = json.loads((dev.ROOT/'maps/catalog.json').read_text())['maps']
        for kind in dev.TYPES:
            public = Counter(e['size'] for e in entries if e['path'].startswith('public/') and e['type'] == kind)
            chosen = Counter(e['size'] for e in dev.specs() if e['type'] == kind)
            self.assertEqual(chosen, {s: 2*n for s, n in public.items()})


if __name__ == '__main__': unittest.main()
