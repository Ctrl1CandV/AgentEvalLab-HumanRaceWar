"""DESIGN appendix A, unchanged starting values for standard-1."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

# name: (default, inclusive lower bound, inclusive upper bound)
PARAMETERS = MappingProxyType({
    "TURNS": (300, 200, 400),
    "START_ENERGY": (300, 200, 500),
    "START_WORKERS": (2, 1, 4),
    "POP_CAP": (40, 30, 60),
    "BASE_HP": (1000, 600, 2000),
    "BASE_FIRE_DMG": (10, 0, 20),
    "BASE_FIRE_RANGE": (2, 1, 3),
    "SPAWN_RANGE": (2, 1, 2),
    "REGEN_HP": (5, 0, 10),
    "REGEN_RANGE": (2, 1, 3),
    "WORKER_COST": (50, 40, 80),
    "WORKER_HP": (40, 30, 60),
    "WORKER_DMG": (5, 0, 10),
    "MINE_RATE": (10, 5, 15),
    "CARRY_MAX": (60, 30, 100),
    "SOLDIER_COST": (100, 80, 150),
    "SOLDIER_HP": (100, 80, 150),
    "SOLDIER_DMG": (20, 15, 30),
    "TOWER_COST": (150, 100, 250),
    "TOWER_HP": (300, 200, 500),
    "TOWER_POINTS": (1, 1, 1),
})


@dataclass(frozen=True)
class UnitSpec:
    prefix: str
    can_mine: bool = False
    can_build: bool = False


UNIT_TYPES = MappingProxyType({
    "W": UnitSpec("WORKER", can_mine=True, can_build=True),
    "S": UnitSpec("SOLDIER"),
})


@dataclass(frozen=True)
class Rules:
    values: Mapping[str, int]
    name: str = "standard-1"

    @classmethod
    def from_dict(cls, overrides: Mapping[str, object]) -> Rules:
        unknown = set(overrides) - PARAMETERS.keys()
        if unknown:
            raise ValueError("unknown rule parameter")
        values = {}
        for name, (default, low, high) in PARAMETERS.items():
            value = overrides.get(name, default)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
            values[name] = value
        return cls(MappingProxyType(values))

    def __getitem__(self, name: str) -> int:
        return self.values[name]

    def unit_value(self, kind: str, attribute: str) -> int:
        return self[f"{UNIT_TYPES[kind].prefix}_{attribute}"]
