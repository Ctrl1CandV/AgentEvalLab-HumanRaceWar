"""Deterministic public-map generation; no random module, bots, or network.

The generation profile uses the DESIGN starting resource totals exactly. It is
not a new restriction on user-supplied maps accepted by the game engine.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256

from .maps import map_text, parse_map
from .model import Map, Position, distance

TYPES = ("open", "corridor", "island", "maze")
MASK = (1 << 64) - 1
GENERATOR_VERSION = 1


class SplitMix64:
    def __init__(self, seed: int):
        if type(seed) is not int or not 0 <= seed <= MASK:
            raise ValueError("seed must be an unsigned 64-bit integer")
        self.state = seed

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
        return value ^ (value >> 31)

    def below(self, bound: int) -> int:
        if not 1 <= bound <= 1 << 64:
            raise ValueError("bound outside [1, 2**64]")
        threshold = (1 << 64) % bound
        while True:
            value = self.next()
            if value >= threshold:
                return value % bound

    def shuffle(self, items: list) -> None:
        for i in range(len(items)-1, 0, -1):
            j = self.below(i+1)
            items[i], items[j] = items[j], items[i]


def adjacent(pos: Position):
    x, y = pos
    return ((x, y-1), (x+1, y), (x, y+1), (x-1, y))


def distances(ground: set[Position], starts) -> dict[Position, int]:
    found = {p: 0 for p in starts if p in ground}
    queue = deque(found)
    while queue:
        p = queue.popleft()
        for q in adjacent(p):
            if q in ground and q not in found:
                found[q] = found[p]+1
                queue.append(q)
    return found


def zone(pos: Position, bases: tuple[Position, ...]) -> str:
    a, b = (distance(pos, base) for base in bases)
    if 4 <= min(a, b) <= 8:
        return "home0" if a < b else "home1"
    if min(a, b) > 8:
        if abs(a-b) <= 4:
            return "center"
        return "middle0" if a < b else "middle1"
    return "outside"


def inspect_layout(board: Map) -> dict:
    """Check DESIGN 7.2 under the documented default generation profile.

    Structural validity/symmetry is checked by parse_map before this function.
    All distance tests except basePath are Manhattan distances.
    """
    ground = {(x, y) for y, row in enumerate(board.rows) for x, cell in enumerate(row) if cell == "."}
    sites = [(x, y) for y, row in enumerate(board.rows) for x, cell in enumerate(row) if cell == "S"]
    ore = {(x, y): n for x, y, n in board.initial_ore}
    reachable = distances(ground, [min(ground)]) if ground else {}
    base_distances = distances(ground, adjacent(board.bases[0]))
    ends = [base_distances[p]+2 for p in adjacent(board.bases[1]) if p in base_distances]
    path = min(ends) if ends else None
    spawn = [sum(distance(base, p) <= 2 for p in ground) for base in board.bases]
    deposits = [*board.bases, *sites]
    separation = min((distance(p, q) for p in deposits for q in ore), default=None)
    near_sites = sum(any(3 <= distance(site, p) <= 5 for p in ore) for site in sites)
    totals = {name: 0 for name in ("home0", "home1", "middle0", "middle1", "center", "outside")}
    cells = dict.fromkeys(totals, 0)
    for p, amount in ore.items():
        name = zone(p, board.bases)
        totals[name] += amount
        cells[name] += 1
    accessible = all(any(q in ground for q in adjacent(p)) for p in [*deposits, *ore])
    checks = {
        "groundConnected": bool(ground) and len(reachable) == len(ground),
        "basePath": path is not None and path*5 >= 6*max(board.width, board.height),
        "homeOre": all(cells[f"home{p}"] == 6 and totals[f"home{p}"] == 2400 for p in (0, 1)),
        "middleOre": totals["middle0"] == totals["middle1"] == 6000,
        "centerOre": totals["center"] == 6000 and totals["outside"] == 0,
        "towerSites": 8 <= len(sites) <= 12 and near_sites*2 >= len(sites),
        "depotOreSeparation": separation is not None and separation >= 3,
        "spawnGround": min(spawn) >= 8,
        "resourceAccess": accessible,
    }
    return {"passed": all(checks.values()), "checks": checks, "groundCells": len(ground),
            "wallCells": sum(row.count("#") for row in board.rows), "basePath": path,
            "spawnGround": spawn, "oreCellsByZone": cells, "oreByZone": totals,
            "towerSites": len(sites), "nearOreSites": near_sites, "minDepotOreDistance": separation}


@dataclass(frozen=True)
class GeneratedMap:
    text: str
    kind: str
    requested_seed: int
    accepted_seed: int
    rejected: tuple[dict, ...]
    metrics: dict

    def metadata(self) -> dict:
        return {"generatorVersion": GENERATOR_VERSION, "type": self.kind,
                "requestedSeed": self.requested_seed, "acceptedSeed": self.accepted_seed,
                "rejectedCandidates": list(self.rejected), "sha256": sha256(self.text.encode()).hexdigest(),
                "metrics": self.metrics}


class CandidateRejected(ValueError):
    pass


class Layout:
    def __init__(self, size: int, rng: SplitMix64):
        self.size = size
        self.rng = rng
        self.rows = [["."]*size for _ in range(size)]
        self.bases = ((2, 2), (size-3, size-3))
        self.ore: dict[Position, int] = {}

    def mirror(self, p: Position) -> Position:
        return self.size-1-p[0], self.size-1-p[1]

    def pair(self, p: Position, cell: str) -> None:
        for x, y in (p, self.mirror(p)):
            self.rows[y][x] = cell

    def ground(self) -> set[Position]:
        return {(x, y) for y, row in enumerate(self.rows) for x, c in enumerate(row) if c == "."}

    def connected(self) -> bool:
        ground = self.ground()
        return bool(ground) and len(distances(ground, [min(ground)])) == len(ground)

    def protect_bases(self):
        for y in range(self.size):
            for x in range(self.size):
                if min(distance((x, y), b) for b in self.bases) <= 2:
                    self.rows[y][x] = "."
        for player, (x, y) in enumerate(self.bases):
            self.rows[y][x] = str(player)

    def wall_grid(self, divisions: int):
        # Paired wall coordinates give symmetric room widths even on odd sizes.
        walls = sorted({v for i in range(1, divisions//2+1)
                        for v in (self.size*i//divisions, self.size-1-self.size*i//divisions)})
        spans = list(zip([0, *(w+1 for w in walls)], [*(w-1 for w in walls), self.size-1]))
        for wall in walls:
            for p in range(self.size):
                self.pair((wall, p), "#")
                self.pair((p, wall), "#")
        return walls, spans

    def room_walls(self, maze: bool):
        n = 5 if maze else 3
        walls, spans = self.wall_grid(n)
        # Each undirected edge is generated once per 180-degree orbit.
        edges = set()
        for y in range(n):
            for x in range(n):
                for q in ((x+1, y), (x, y+1)):
                    if max(q) >= n:
                        continue
                    edge = tuple(sorted(((x, y), q)))
                    flipped = tuple(sorted((n-1-a, n-1-b) for a, b in edge))
                    edges.add(min(edge, flipped))
        choices = sorted(edges)
        self.rng.shuffle(choices)
        parents = list(range(n*n))

        def find(p):
            i = p[1]*n+p[0]
            while parents[i] != i:
                i = parents[i]
            return i

        for a, b in choices:
            ar, br = (n-1-a[0], n-1-a[1]), (n-1-b[0], n-1-b[1])
            if maze and find(a) == find(b) and find(ar) == find(br):
                continue
            if a[0] != b[0]:
                low, high = spans[a[1]]
                p = (walls[min(a[0], b[0])], low+self.rng.below(high-low+1))
            else:
                low, high = spans[a[0]]
                p = (low+self.rng.below(high-low+1), walls[min(a[1], b[1])])
            self.pair(p, ".")
            parents[find(a)] = find(b)
            parents[find(ar)] = find(br)

    def terrain(self, kind: str):
        if kind == "open":
            self.protect_bases()
            choices = [(x, y) for y in range(self.size) for x in range(self.size)
                       if (x, y) < self.mirror((x, y))
                       and min(distance((x, y), b) for b in self.bases) > 3]
            self.rng.shuffle(choices)
            placed = 0
            for p in choices:
                self.pair(p, "#")
                if self.connected():
                    placed += 2
                else:
                    self.pair(p, ".")
                if placed >= self.size*self.size//20:
                    break
        elif kind == "corridor":
            wall = self.size//3
            gap = 3+self.rng.below(self.size-6)
            for y in range(self.size):
                if y not in (gap, gap+1):
                    self.pair((wall, y), "#")
        else:
            self.room_walls(maze=kind == "maze")
        self.protect_bases()
        if not self.connected():
            raise CandidateRejected("terrain_disconnected")

    def place(self, name: str, pairs: int, amount: int = 0):
        choices = sorted(p for p in self.ground() if p < self.mirror(p))
        self.rng.shuffle(choices)
        placed = 0
        for p in choices:
            q = self.mirror(p)
            if self.rows[p[1]][p[0]] != "." or self.rows[q[1]][q[0]] != ".":
                continue
            if name == "tower":
                nearest = min(distance(p, ore) for ore in self.ore)
                if not 3 <= nearest <= 5 or min(distance(p, b) for b in self.bases) <= 2:
                    continue
            elif zone(p, self.bases).removesuffix("0").removesuffix("1") != name:
                continue
            self.pair(p, "S" if name == "tower" else "O")
            ground = self.ground()
            features = [*self.ore, p, q, *self.bases]
            if (len(distances(ground, [min(ground)])) != len(ground)
                    or not all(any(n in ground for n in adjacent(f)) for f in features)):
                self.pair(p, ".")
                continue
            if name != "tower":
                self.ore[p] = self.ore[q] = amount
            placed += 1
            if placed == pairs:
                return
        raise CandidateRejected(f"insufficient_{name}_positions")

    def board(self) -> Map:
        return Map(self.size, self.size, tuple("".join(row) for row in self.rows),
                   tuple((x, y, n) for (x, y), n in sorted(self.ore.items())), self.bases)


def generate(kind: str, size: int, seed: int, *, max_attempts: int = 128) -> GeneratedMap:
    if kind not in TYPES or type(size) is not int or not 24 <= size <= 40:
        raise ValueError("type must be open/corridor/island/maze; size must be in [24, 40]")
    SplitMix64(seed)  # Validate before attempting generation.
    if type(max_attempts) is not int or not 1 <= max_attempts <= 128:
        raise ValueError("max_attempts must be in [1, 128]")
    rejected = []
    for attempt in range(max_attempts):
        candidate_seed = (seed+attempt) & MASK
        layout = Layout(size, SplitMix64(candidate_seed))
        try:
            layout.terrain(kind)
            layout.place("home", 6, 400)
            layout.place("middle", 10, 600)
            layout.place("center", 5, 600)
            layout.place("tower", 5)
            text = map_text(layout.board())
            metrics = inspect_layout(parse_map(text))
            if not metrics["passed"]:
                raise CandidateRejected(",".join(k for k, v in metrics["checks"].items() if not v))
            return GeneratedMap(text, kind, seed, candidate_seed, tuple(rejected), metrics)
        except CandidateRejected as error:
            rejected.append({"seed": candidate_seed, "reason": str(error)})
    raise ValueError(f"no valid map in {max_attempts} candidates: {rejected}")
