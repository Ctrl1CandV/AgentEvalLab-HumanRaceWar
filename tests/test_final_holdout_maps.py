"""Final holdout guards and independent geometry: no real hidden assets."""
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from arena.games.outpost.maps import parse_map
from arena.games.outpost.mapgen import inspect_layout
from tools import prepare_final_holdout as holdout


class FinalHoldoutMapTests(unittest.TestCase):
    def test_composition_matches_original_calibration_sizes(self):
        self.assertEqual(len(holdout.specs()), 24)
        for kind in holdout.TYPES:
            self.assertEqual([e['size'] for e in holdout.specs() if e['type'] == kind], [24, 28, 32, 36, 40, 32])

    def test_plan_registered_before_any_generation_and_no_redraw(self):
        with TemporaryDirectory() as d, patch.object(holdout, 'prerequisites', return_value={}), \
                patch.object(holdout, 'existing_assets', return_value=[]), \
                patch.object(holdout.secrets, 'randbits', side_effect=range(24)) as draw, \
                patch.object(holdout, 'generate') as generate:
            root = Path(d); destination = root/'private/holdout'
            holdout.plan(destination, root=root)
            self.assertEqual(draw.call_count, 24); generate.assert_not_called()
            self.assertEqual(len(holdout.check_plan(destination, root)['maps']), 24)
            original = (destination/'generation-plan.json').read_bytes()
            with self.assertRaises(ValueError): holdout.plan(destination, root=root)
            self.assertEqual((destination/'generation-plan.json').read_bytes(), original)
            value = json.loads(original); value['maps'][0]['seed'] = 999
            (destination/'generation-plan.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'not registered'): holdout.build(destination, root=root)
            generate.assert_not_called()

    def test_seed_collision_stops_without_a_second_draw(self):
        with TemporaryDirectory() as d, patch.object(holdout, 'prerequisites', return_value={}), \
                patch.object(holdout, 'existing_assets', return_value=[]), \
                patch.object(holdout.secrets, 'randbits', return_value=7) as draw:
            with self.assertRaisesRegex(ValueError, 'collision'):
                holdout.plan(Path(d)/'private/holdout', root=Path(d))
            self.assertEqual(draw.call_count, 24)

    def test_duplicate_map_stops_without_replacement(self):
        with TemporaryDirectory() as d, patch.object(holdout, 'prerequisites', return_value={}), \
                patch.object(holdout, 'existing_assets', return_value=[]), \
                patch.object(holdout.secrets, 'randbits', side_effect=range(24)) as draw:
            root = Path(d); destination = root/'private/holdout'
            holdout.plan(destination, root=root)
            candidate = SimpleNamespace(text='synthetic map\n', metadata=lambda: {
                'sha256': sha256(b'synthetic map\n').hexdigest(), 'acceptedSeed': 100})
            with patch.object(holdout, 'generate', return_value=candidate) as generate:
                with self.assertRaisesRegex(ValueError, 'duplicate map'): holdout.build(destination, root=root)
                self.assertEqual(generate.call_count, 2)
            self.assertEqual(draw.call_count, 24)
            self.assertEqual(len(list(destination.rglob('*.map'))), 1)
            self.assertFalse((destination/'catalog.json').exists())

    def test_cut_vertices_match_exhaustive_removal_on_all_small_grids(self):
        def components(ground):
            remaining = set(ground); count = 0
            while remaining:
                queue = [remaining.pop()]; count += 1
                while queue:
                    p = queue.pop()
                    for q in holdout.neighbors(p):
                        if q in remaining: remaining.remove(q); queue.append(q)
            return count
        cells = [(x, y) for x in range(3) for y in range(3)]
        for size in range(10):
            for selected in combinations(cells, size):
                ground = set(selected); before = components(ground)
                expected = {p for p in ground if components(ground-{p}) > before}
                self.assertEqual(holdout.cut_vertices(ground), expected)

    def test_independent_checks_match_all_public_and_scrimmage_assets(self):
        for path in sorted((holdout.ROOT/'maps').glob('*/*.map')):
            board = parse_map(path.read_text()); primary = inspect_layout(board)
            independent = holdout.independent_layout(board)
            self.assertTrue(independent['passed'], path)
            self.assertEqual(independent['basePath'], primary['basePath'])
            self.assertEqual(sorted(independent['homeOreWalks']), sorted(r['walk'] for r in primary['homeOreWalks']))
            self.assertEqual(independent['groundCells'], primary['groundCells'])

    def test_independent_symmetry_detects_resource_mismatch(self):
        board = parse_map((holdout.ROOT/'maps/public/open-01.map').read_text())
        x, y, amount = board.initial_ore[0]
        changed = replace(board, initial_ore=((x, y, amount+1), *board.initial_ore[1:]))
        self.assertFalse(holdout.independent_layout(changed)['checks']['symmetry'])

    def test_public_summary_is_aggregate_allowlist(self):
        board = parse_map((holdout.ROOT/'maps/public/open-01.map').read_text())
        metrics = holdout.independent_layout(board)
        rows = [{'mapSet': group, 'type': kind, 'size': 24, 'sha256': 'synthetic', 'path': 'SECRET_PATH',
                 'seed': 'SECRET_SEED', 'metrics': metrics} for group in ('public','scrimmage','calibration','grading','holdout') for kind in holdout.TYPES]
        result = holdout.aggregate(rows)
        self.assertEqual(result['maps'], 20)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('path', result['sets'][0])


if __name__ == '__main__':
    unittest.main()
