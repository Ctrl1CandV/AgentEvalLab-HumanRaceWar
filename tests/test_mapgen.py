"""Trusted deterministic generator/profile checks; no bot execution here."""
from collections import Counter, deque
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from arena.games.outpost import Outpost
from arena.games.outpost.mapgen import CandidateRejected, Layout, SplitMix64, TYPES, generate, inspect_layout
from arena.games.outpost.maps import map_text, parse_map
from tests.helpers import fixture_map
from tools.generate_public_maps import build

ROOT = Path(__file__).resolve().parents[1]


class MapGeneratorTests(unittest.TestCase):
    def test_splitmix64_reference_vectors(self):
        rng = SplitMix64(0)
        self.assertEqual([rng.next() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])
        with patch.object(rng, "next", side_effect=[0, (1 << 64)-1]) as draw:
            self.assertEqual(rng.below(3), 0)
            self.assertEqual(draw.call_count, 2)
        for invalid in (0, -1, 2**64+1):
            with self.assertRaises(ValueError):
                rng.below(invalid)

    def test_generator_rejects_invalid_configuration(self):
        for kind, size, seed in (("invalid", 32, 0), ("open", 23, 0), ("open", 41, 0),
                                 ("open", True, 0), ("open", 32, -1), ("open", 32, 2**64),
                                 ("open", 32, True)):
            with self.subTest(kind=kind, size=size, seed=seed), self.assertRaises(ValueError):
                generate(kind, size, seed)
        with self.assertRaises(ValueError):
            generate("open", 32, 1, max_attempts=0)

    def test_all_types_and_sizes_have_exact_resource_profile(self):
        for kind in TYPES:
            for size in range(24, 41):
                with self.subTest(kind=kind, size=size):
                    generated = generate(kind, size, 7)
                    board = parse_map(generated.text)
                    self.assertTrue(inspect_layout(board)["passed"])
                    self.assertEqual(len(board.initial_ore), 42)
                    self.assertEqual(sum(n for _, _, n in board.initial_ore), 22800)
                    self.assertEqual(sum(row.count("S") for row in board.rows), 10)
                    state = Outpost().new_match(generated.text, {}, [1, 2])
                    self.assertEqual(len(state.units), 4)
                    self.assertEqual(generated.text, map_text(board))
                    # Independent flood fill, not the generator's traversal.
                    ground = {(x, y) for y, row in enumerate(board.rows) for x, c in enumerate(row) if c == "."}
                    seen = {min(ground)}
                    queue = deque(seen)
                    while queue:
                        x, y = queue.popleft()
                        for pos in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                            if pos in ground and pos not in seen:
                                seen.add(pos)
                                queue.append(pos)
                    self.assertEqual(seen, ground)

    def test_fixed_seed_maps_are_byte_stable(self):
        expected = {
            "open": "5dfe7525c02e7f1ae6aa9f4fc4ecad88772ced5e5436ae5a332edc0347f712c8",
            "corridor": "e83e661a53bd70c35300818acd4420c123f8cc739061b71f07a10d05542c81cc",
            "island": "872ce711ba0dbabe2d0c148f0406a1881e0c953c149e634850ccd8431851b6dd",
            "maze": "eee923590e57aa2aef1d1ae17a39f908c650e6e6cac31ec435ce1f89dc3b1639",
        }
        for kind, digest in expected.items():
            result = generate(kind, 32, 7)
            self.assertEqual(result.metadata()["sha256"], digest)
            self.assertEqual(result.text, generate(kind, 32, 7).text)

    def test_types_are_distinct_not_just_labels(self):
        maps = [generate(kind, 32, 7) for kind in TYPES]
        self.assertEqual(len({m.text for m in maps}), 4)
        walls = [m.metrics["wallCells"] for m in maps]
        self.assertEqual(walls, sorted(set(walls)))
        self.assertGreater(maps[-1].metrics["basePath"], maps[0].metrics["basePath"])

    def test_retry_advances_seed_and_preserves_rejection_reason(self):
        original = Layout.terrain
        def terrain(layout, kind):
            if layout.rng.state == 7:
                raise CandidateRejected("injected_rejection")
            return original(layout, kind)
        with patch.object(Layout, "terrain", terrain):
            result = generate("open", 32, 7)
        self.assertEqual(result.accepted_seed, 8)
        self.assertEqual(result.rejected, ({"seed": 7, "reason": "injected_rejection"},))
        self.assertEqual(result.text, generate("open", 32, 8).text)

    def test_retries_are_bounded_not_an_infinite_search(self):
        with patch.object(Layout, "terrain", side_effect=CandidateRejected("injected")) as terrain:
            with self.assertRaisesRegex(ValueError, "no valid map in 2 candidates"):
                generate("maze", 24, 7, max_attempts=2)
            self.assertEqual(terrain.call_count, 2)

    def test_disconnected_ground_and_short_base_path_are_rejected(self):
        disconnected = parse_map(fixture_map(extra=[(0, 0, "."), (1, 0, "#"), (0, 1, "#")]))
        self.assertFalse(inspect_layout(disconnected)["checks"]["groundConnected"])
        short = parse_map(fixture_map(base=(10, 10)))
        self.assertFalse(inspect_layout(short)["checks"]["basePath"])

    def test_spawn_ground_and_depot_separation_are_checked(self):
        blocked = parse_map(fixture_map(extra=[(1, 2, "#"), (2, 1, "#"), (3, 2, "#"), (2, 3, "#"), (0, 2, "#")]))
        self.assertFalse(inspect_layout(blocked)["checks"]["spawnGround"])
        smoke = inspect_layout(parse_map(fixture_map()))
        self.assertFalse(smoke["checks"]["depotOreSeparation"])
        self.assertFalse(smoke["checks"]["homeOre"])
        self.assertFalse(smoke["checks"]["towerSites"])

    def test_resource_amount_changes_are_detected(self):
        board = parse_map(generate("open", 24, 0).text)
        bad = replace(board, initial_ore=tuple((x, y, n+1) for x, y, n in board.initial_ore))
        metrics = inspect_layout(parse_map(map_text(bad)))
        self.assertFalse(metrics["checks"]["homeOre"])
        self.assertFalse(metrics["checks"]["middleOre"])
        self.assertFalse(metrics["checks"]["centerOre"])

    def test_checked_in_catalog_is_complete_unique_and_regenerates(self):
        catalog = json.loads((ROOT / "maps/catalog.json").read_text())
        self.assertEqual(len(catalog["maps"]), 44)
        self.assertEqual(Counter(e["type"] for e in catalog["maps"] if e["path"].startswith("public/")),
                         dict.fromkeys(TYPES, 10))
        self.assertEqual(Counter(e["type"] for e in catalog["maps"] if e["path"].startswith("scrimmage/")),
                         dict.fromkeys(TYPES, 1))
        self.assertEqual(len({e["sha256"] for e in catalog["maps"]}), 44)
        for entry in catalog["maps"]:
            data = (ROOT / "maps" / entry["path"]).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), entry["sha256"])
            regenerated = generate(entry["type"], entry["size"], entry["requestedSeed"])
            self.assertEqual(regenerated.text.encode(), data)
            self.assertEqual(inspect_layout(parse_map(data.decode())), entry["metrics"])
            self.assertTrue(entry["metrics"]["passed"])

    def test_asset_builder_is_idempotent_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "maps"
            first = build(destination)
            self.assertEqual(first, build(destination))
            target = destination / "public/open-01.map"
            target.write_text("user modification\n")
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                build(destination)
            self.assertEqual(target.read_text(), "user modification\n")
