import unittest
from typing import Any, cast

from tools.bounded_search import Coordinate, acceptance, choose, early_reject, neighbours, search, validate_vector


class BoundedSearchTests(unittest.TestCase):
    def test_same_entering_neighbours_and_one_pass(self):
        coordinates = [Coordinate('x', 2, 1, 0, 4), Coordinate('y', 3, 2, 1, 5)]
        visited = []
        def evaluate(v):
            visited.append(v)
            return 3 * v[0] + v[1]
        result = search(coordinates, 20, evaluate)
        self.assertEqual(visited, [(2, 3), (1, 3), (3, 3), (3, 1), (3, 5)])
        self.assertEqual(result['selected'], [3, 5])
        self.assertEqual(result['rounds'][0]['entering'], [2, 3])

    def test_incumbent_retained_on_tie_and_lexicographic_better_tie(self):
        coords = [Coordinate('x', 5, 1, 3, 7)]
        self.assertEqual(search(coords, 10, lambda _: 10)['selected'], [5])
        self.assertEqual(search(coords, 10, lambda v: 10 if v == (5,) else 11)['selected'], [4])
        self.assertEqual(choose((2, 2), {(2, 2): 2, (3, 1): 4, (1, 3): 4}, [(3, 1), (1, 3)]), (1, 3))

    def test_bounds_no_extra_evaluation_and_callback(self):
        coords = [Coordinate('x', 0, 2, 0, 2), Coordinate('y', 0, 1, 0, 0)]
        visited, rounds = [], []
        def evaluate(v):
            visited.append(v)
            return sum(v)
        result = search(coords, 2, evaluate, rounds.append)
        self.assertEqual(visited, [(0, 0), (2, 0)])
        self.assertEqual(len(visited), len(set(visited)))
        self.assertEqual(result['rounds'], rounds)
        self.assertEqual(rounds[1]['candidates'], [])

    def test_six_dimensions_bounded_and_deterministic(self):
        coords = [Coordinate(str(i), 3, 1, 1, 5) for i in range(6)]
        visits = []
        def evaluate(v):
            visits.append(v)
            return sum(v)
        result = search(coords, 100, evaluate)
        self.assertEqual(len(visits), 13)
        self.assertEqual(len(set(visits)), 13)
        self.assertEqual(result['selected'], [4] * 6)
        self.assertEqual(result, search(coords, 100, lambda v: sum(v)))

    def test_invalid_vectors_and_coordinates(self):
        for args in [('x', True, 1, 0, 4), ('x', 2, 0, 0, 4), ('x', 5, 1, 0, 4), ('', 1, 1, 0, 4)]:
            with self.assertRaises(ValueError): Coordinate(*args)
        coords = [Coordinate('x', 2, 1, 0, 4)]
        for vector in [(), (True,), (1.0,), (5,)]:
            with self.assertRaises(ValueError): validate_vector(vector, coords)
        with self.assertRaises(ValueError): validate_vector((2, 2), coords * 2)
        for index in (True, -1, 1):
            with self.assertRaises(ValueError): neighbours((2,), index, coords)

    def test_invalid_scores_and_failures_propagate(self):
        coords = [Coordinate('x', 1, 1, 0, 2)]
        for value in (True, -1, 21, 1.5):
            with self.assertRaises(ValueError): search(coords, 10, lambda _: cast(Any, value))
        with self.assertRaises(ValueError): search(coords, 0, lambda _: self.fail('invalid denominator reached evaluator'))
        visited = []
        def broken(v):
            visited.append(v)
            if v == (0,): raise RuntimeError('stop')
            return 1
        with self.assertRaises(RuntimeError): search(coords, 10, broken)
        self.assertEqual(visited, [(1,), (0,)])
        with self.assertRaises(ValueError): choose((1,), {(1,): 1}, [(0,)])

    def test_early_threshold_exact_half_points(self):
        self.assertTrue(early_reject(71, 80))
        self.assertFalse(early_reject(72, 80))
        self.assertFalse(early_reject(73, 80))
        with self.assertRaises(ValueError): early_reject(161, 80)

    def test_acceptance_thresholds_and_functional_gate(self):
        self.assertFalse(acceptance(175, 160, 1000, 1000, 960, functional_passed=True)['accepted'])
        self.assertTrue(acceptance(176, 160, 1000, 962, 960, functional_passed=True)['accepted'])
        self.assertFalse(acceptance(176, 160, 1000, 961, 960, functional_passed=True)['accepted'])
        self.assertTrue(acceptance(176, 160, 100, 96, 100, functional_passed=True)['accepted'])
        self.assertFalse(acceptance(176, 160, 100, 96, 100, functional_passed=False)['accepted'])
        with self.assertRaises(ValueError): acceptance(176, 160, 100, 201, 100, functional_passed=True)
        with self.assertRaises(ValueError): acceptance(176, 160, 100, 96, 100, functional_passed=cast(Any, 1))


if __name__ == '__main__':
    unittest.main()
