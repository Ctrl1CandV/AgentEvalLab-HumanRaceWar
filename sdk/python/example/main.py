"""Small mining/transport example, not a calibrated ladder opponent."""
import hrw

setup = hrw.read_setup()
hrw.ready()
base = setup.bases()[setup.you]
returning = set()
while (turn := hrw.read_turn()) is not None:
    orders = []
    own = [u for u in turn.units if u.owner == setup.you]
    occupied = {u.pos for u in turn.units}
    reserved = set()
    depots = [base, *((x, y) for x, y, owner, _ in turn.towers if owner == setup.you)]
    for unit in own:
        if unit.kind != "W":
            continue  # Deliberately weak: soldiers stay home.
        if unit.carry == setup.params["CARRY_MAX"]:
            returning.add(unit.id)
        if unit.carry == 0:
            returning.discard(unit.id)
        home = unit.id in returning or (unit.carry > 0 and not turn.ore)
        targets = depots if home else list(turn.ore)
        if not home:
            adjacent = next((p for p in targets if hrw.distance(p, unit.pos) == 1), None)
            if adjacent is not None:
                orders.append(f"MINE {unit.id} {adjacent[0]} {adjacent[1]}")
                continue
        goals = [p for target in targets for _, p in hrw.neighbors(target)]
        distances = hrw.bfs(setup.rows, goals, (occupied - {unit.pos}) | reserved)
        options = [(distances[p], direction, p) for direction, p in hrw.neighbors(unit.pos)
                   if p in distances and p not in occupied and p not in reserved]
        if unit.pos in distances and distances[unit.pos] > 0 and options:
            _, direction, p = min(options)
            orders.append(f"MOVE {unit.id} {direction}")
            reserved.add(p)
    energy = turn.players[setup.you][0]
    if turn.number % 30 == 0 and energy >= setup.params["SOLDIER_COST"] and len(own) < setup.params["POP_CAP"]:
        cells = [(x, y) for y, row in enumerate(setup.rows) for x, c in enumerate(row)
                 if c == "." and (x, y) not in occupied | reserved
                 and hrw.distance(base, (x, y)) <= setup.params["SPAWN_RANGE"]]
        if cells:
            x, y = min(cells, key=lambda p: (hrw.distance(base, p), p))
            orders.append(f"SPAWN S {x} {y}")
    hrw.send(orders)
