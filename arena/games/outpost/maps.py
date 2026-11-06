"""Map file parsing, not the map generator or balance validator.

Files reuse MAP/ORE/END records from the init protocol. Trusted malformed map
files are configuration errors; bot output never goes through this parser.
"""
from __future__ import annotations

from .model import Map


def parse_map(text: str) -> Map:
    lines = text.splitlines()
    if not lines or len(lines[0].split()) != 3:
        raise ValueError("map must begin with MAP <width> <height>")
    tag, width_text, height_text = lines[0].split()
    if tag != "MAP":
        raise ValueError("map must begin with MAP")
    width, height = int(width_text), int(height_text)
    if not (24 <= width <= 40 and 24 <= height <= 40):
        raise ValueError("map dimensions must be in [24, 40]")
    rows = tuple(lines[1:height + 1])
    if len(rows) != height or any(len(row) != width for row in rows):
        raise ValueError("wrong number or width of map rows")
    if any(set(row) - set(".#OS01") for row in rows):
        raise ValueError("unknown map symbol")
    bases = []
    for player in ("0", "1"):  # Outpost v1 has two players; framework contracts do not.
        found = [(x, y) for y, row in enumerate(rows)
                 for x, cell in enumerate(row) if cell == player]
        if len(found) != 1:
            raise ValueError("exactly one base per player is required")
        bases.append(found[0])
    swap = str.maketrans("01", "10")
    if tuple(row[::-1].translate(swap) for row in reversed(rows)) != rows:
        raise ValueError("map must be rotationally symmetric, with bases swapped")
    ore = {}
    ended = False
    for line in lines[height + 1:]:
        if ended:
            if line.strip():
                raise ValueError("data after map END")
            continue
        parts = line.split()
        if parts == ["END"]:
            ended = True
            continue
        if len(parts) != 4 or parts[0] != "ORE":
            raise ValueError("expected ORE <x> <y> <amount> or END")
        x, y, amount = map(int, parts[1:])
        if not (0 <= x < width and 0 <= y < height) or rows[y][x] != "O":
            raise ValueError("ORE must refer to an ore cell")
        if amount < 0 or (x, y) in ore:
            raise ValueError("duplicate or negative ORE")
        ore[x, y] = amount
    if not ended:
        raise ValueError("missing map END")
    expected = {(x, y) for y, row in enumerate(rows)
                for x, cell in enumerate(row) if cell == "O"}
    if ore.keys() != expected:
        raise ValueError("each ore cell needs exactly one ORE record")
    if any(ore[width - 1 - x, height - 1 - y] != amount
           for (x, y), amount in ore.items()):
        raise ValueError("ore amounts must be rotationally symmetric")
    return Map(width, height, rows,
               tuple((x, y, n) for (x, y), n in sorted(ore.items())), tuple(bases))


def map_text(board: Map) -> str:
    lines = [f"MAP {board.width} {board.height}", *board.rows]
    lines.extend(f"ORE {x} {y} {n}" for x, y, n in board.initial_ore)
    return "\n".join([*lines, "END", ""])
