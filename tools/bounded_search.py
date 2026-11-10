"""One-pass, integer-scored coordinate search; no bots or filesystem access.

Callers freeze inputs, run the evaluator, and retain all evaluation artifacts.
Both neighbours use the same entering incumbent; a tie retains that incumbent.
"""
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class Coordinate:
    name: str
    default: int
    step: int
    lower: int
    upper: int

    def __post_init__(self):
        if (not isinstance(self.name, str) or not self.name
                or any(type(v) is not int for v in (self.default, self.step, self.lower, self.upper))
                or self.step <= 0 or not self.lower <= self.default <= self.upper):
            raise ValueError('invalid coordinate')


def validate_vector(vector: Sequence[int], coordinates: Sequence[Coordinate]) -> tuple[int, ...]:
    if (not coordinates or len({c.name for c in coordinates}) != len(coordinates)
            or len(vector) != len(coordinates)
            or any(type(v) is not int or not c.lower <= v <= c.upper for v, c in zip(vector, coordinates))):
        raise ValueError('invalid vector/coordinate set')
    return tuple(vector)


def neighbours(vector: Sequence[int], index: int, coordinates: Sequence[Coordinate]) -> list[tuple[int, ...]]:
    vector = validate_vector(vector, coordinates)
    if type(index) is not int or not 0 <= index < len(coordinates):
        raise ValueError('invalid coordinate index')
    c = coordinates[index]
    result = []
    for offset in (-c.step, c.step):
        values = list(vector)
        values[index] += offset
        if c.lower <= values[index] <= c.upper:
            result.append(tuple(values))
    return result


def score(half_points: int, games: int) -> int:
    if (type(games) is not int or games <= 0 or type(half_points) is not int
            or not 0 <= half_points <= 2 * games):
        raise ValueError('invalid half-point score')
    return half_points


def choose(incumbent: tuple[int, ...], scores: dict[tuple[int, ...], int],
           candidates: Sequence[tuple[int, ...]]) -> tuple[int, ...]:
    if incumbent not in scores or any(c not in scores for c in candidates):
        raise ValueError('unevaluated candidate')
    if any(type(v) is not int or v < 0 for v in scores.values()):
        raise ValueError('invalid score')
    better = [c for c in candidates if scores[c] > scores[incumbent]]
    return min(better, key=lambda c: (-scores[c], c)) if better else incumbent


def search(coordinates: Sequence[Coordinate], games: int,
           evaluate: Callable[[tuple[int, ...]], int],
           on_round: Callable[[dict], None] | None = None) -> dict:
    """Evaluate at most 1+2*d vectors, exactly once each, with one fixed denominator."""
    incumbent = validate_vector(tuple(c.default for c in coordinates), coordinates)
    score(0, games)  # Reject a bad denominator before the evaluator can have side effects.
    scores = {incumbent: score(evaluate(incumbent), games)}
    rounds = []
    for index, coordinate in enumerate(coordinates):
        entering = incumbent
        candidates = neighbours(entering, index, coordinates)
        for vector in candidates:
            if vector not in scores:
                scores[vector] = score(evaluate(vector), games)
        incumbent = choose(entering, scores, candidates)
        row = {'index': index, 'coordinate': coordinate.name, 'entering': list(entering),
               'enteringHalfPoints': scores[entering],
               'candidates': [{'vector': list(v), 'halfPoints': scores[v]} for v in candidates],
               'selected': list(incumbent), 'selectedHalfPoints': scores[incumbent]}
        rounds.append(row)
        if on_round is not None:
            on_round(row)
    return {'selected': list(incumbent), 'halfPoints': scores[incumbent], 'gamesPerVector': games,
            'evaluations': [{'vector': list(v), 'halfPoints': points} for v, points in scores.items()],
            'rounds': rounds}


def early_reject(half_points: int, games: int) -> bool:
    """Strictly below 45%; an exact boundary proceeds."""
    return score(half_points, games) * 100 < 90 * games


def acceptance(direct_points: int, direct_games: int, old_pool_points: int,
               new_pool_points: int, pool_games: int, *, functional_passed: bool) -> dict:
    """Direct >=55%, fixed pool decrease <=2pp, and covered functionality passes."""
    score(direct_points, direct_games)
    score(old_pool_points, pool_games)
    score(new_pool_points, pool_games)
    if type(functional_passed) is not bool:
        raise ValueError('functional status must be boolean')
    checks = {'direct': direct_points * 100 >= 110 * direct_games,
              'fixedPool': (old_pool_points - new_pool_points) * 100 <= 4 * pool_games,
              'coveredFunctionality': functional_passed}
    return {'checks': checks, 'accepted': all(checks.values())}
