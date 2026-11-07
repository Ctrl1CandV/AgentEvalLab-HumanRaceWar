"""Independent walking-distance checks for D5; no bot execution."""
from collections import deque
from pathlib import Path
import unittest

from arena.games.outpost.maps import parse_map
from arena.games.outpost.mapgen import inspect_layout
from tests.helpers import fixture_map

ROOT = Path(__file__).resolve().parents[1]


def neighbors(p):
    x, y = p
    return ((x-1, y), (x+1, y), (x, y-1), (x, y+1))


def walk(board, start):
    ground = {(x, y) for y, row in enumerate(board.rows) for x, c in enumerate(row) if c == "."}
    distances = {p: 0 for p in neighbors(start) if p in ground}
    q = deque(distances)
    while q:
        p = q.popleft()
        for n in neighbors(p):
            if n in ground and n not in distances:
                distances[n] = distances[p]+1
                q.append(n)
    return distances


def to_feature(distances, feature):
    return min((distances[p] for p in neighbors(feature) if p in distances), default=None)


class WalkingMapTests(unittest.TestCase):
    def test_all_assets_satisfy_independent_home_and_tower_walk_limits(self):
        violations = []
        for path in sorted((ROOT / "maps").glob('*/*.map')):
            board = parse_map(path.read_text())
            ore = [(x, y) for x, y, _ in board.initial_ore]
            for base in board.bases:
                d = walk(board, base)
                for p in ore:
                    if 4 <= abs(p[0]-base[0])+abs(p[1]-base[1]) <= 8:
                        value = to_feature(d, p)
                        if value is None or value > 12:
                            violations.append((path.name, "home", p, value))
            sites = [(x, y) for y, row in enumerate(board.rows) for x, c in enumerate(row) if c == 'S']
            near = 0
            for site in sites:
                d = walk(board, site)
                near += any(3 <= abs(p[0]-site[0])+abs(p[1]-site[1]) <= 5
                            and (value := to_feature(d, p)) is not None and value <= 6 for p in ore)
            if near*2 < len(sites): violations.append((path.name, "tower", near, len(sites)))
        self.assertEqual(violations, [])

    def test_manhattan_near_home_ore_across_a_wall_is_rejected(self):
        extra = [(4, y, '#') for y in range(15)] + [(6, 2, 'O')]
        board = parse_map(fixture_map(extra=extra))
        value = to_feature(walk(board, board.bases[0]), (6, 2))
        assert value is not None
        self.assertGreater(value, 12)
        self.assertFalse(inspect_layout(board)['checks']['homeWalk'])

    def test_tower_must_be_walk_near_the_same_manhattan_near_ore(self):
        extra = [(6, y, '#') for y in range(15)] + [(5, 2, 'O'), (8, 2, 'S')]
        board = parse_map(fixture_map(extra=extra))
        metrics = inspect_layout(board)
        self.assertGreater(metrics['nearOreSitesManhattan'], metrics['nearOreSites'])
        self.assertFalse(metrics['checks']['towerSites'])


if __name__ == '__main__':
    unittest.main()
