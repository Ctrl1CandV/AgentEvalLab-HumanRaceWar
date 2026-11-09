"""Aggregation and evidence guards on synthetic data, without running games."""
from hashlib import sha256
import gzip
from itertools import combinations, product
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import review_mainlines as review


class MainlineReviewTests(unittest.TestCase):
    def test_map_counts_preserve_draws_and_split_seats(self):
        value = review.pair_counts([(2, 2), (0, 0), (2, 0), (1, 2), (1, 1)])
        self.assertEqual((value['bothWin'], value['bothLose'], value['splitWinLoss'], value['mapsWithDraw']), (1, 1, 1, 2))
        self.assertEqual(value['scoreRate'], .55)

    def test_minimum_map_changes_against_exhaustive_small_cases(self):
        for n in range(1, 5):
            for groups in product(((0, 0), (1, 1), (2, 2), (0, 2)), repeat=n):
                for strict in (False, True):
                    target = 2*n+int(strict)
                    expected = next(k for k in range(n+1) if any(
                        sum(4 if i in subset else sum(groups[i]) for i in range(n)) >= target
                        for subset in combinations(range(n), k)))
                    self.assertEqual(review.changes_to_half(groups, strict), expected)

    def test_joint_map_interval_and_pair_completeness(self):
        self.assertEqual(review.paired_interval([(2, 0)]*24), [.5, .5])
        self.assertEqual(review.paired_interval([(2, 2)]*24), [1, 1])
        rows = [{'players': [0, 1] if side == 0 else [1, 0], 'mapIndex': i,
                 'result': {'winner': side}} for i in range(24) for side in range(2)]
        self.assertEqual(review.grouped_scores(rows, 0, 1), [(2, 2)]*24)
        with self.assertRaises(ValueError): review.grouped_scores(rows[:-1], 0, 1)
        with self.assertRaises(ValueError): review.grouped_scores(rows+[rows[0]], 0, 1)

    def test_fixed_pool_filters_saturation_for_each_line_not_the_union(self):
        names = ['p', 'q', 'r']; zoo = ['M-balanced', *[f'Z-{i}' for i in range(9)]]
        cells = [{'code': code, 'opponent': opponent,
                  'scoreRate': .5 if opponent in ('M-balanced', f'Z-{i}') else 1.0}
                 for i, code in enumerate(names) for opponent in zoo]
        result = review.select_fixed_pools(cells, names)
        for i, code in enumerate(names):
            self.assertEqual(result['pools'][code], ['M-balanced', *[n for n in names if n != code], f'Z-{i}'])
        self.assertEqual(result['deepseekFirstPool'], ['M-balanced', *names, 'Z-0', 'Z-1', 'Z-2'])
        with self.assertRaises(ValueError): review.select_fixed_pools(cells[:-1], names)
        with self.assertRaises(ValueError): review.select_fixed_pools(cells+[cells[0]], names)
        with self.assertRaises(ValueError): review.select_fixed_pools([{**cells[0], 'scoreRate': True}, *cells[1:]], names)

    def test_cpu_census_checks_digest_terminal_and_totals(self):
        with TemporaryDirectory() as d, patch.object(review, 'private_path', side_effect=lambda p: p):
            path = Path(d)/'synthetic.gz'
            head = {'type': 'header', 'taskId': 'synthetic', 'mapSha256': 'synthetic-map',
                    'seeds': [1, 2], 'sandbox': 'bwrap'}
            result = {'turns': 1, 'winner': 0}
            replies = lambda n: [{'cpu_ns': n, 'fault': None} for _ in range(2)]
            with gzip.open(path, 'wt') as stream:
                for record in (head, {'type': 'init', 'replies': replies(2)},
                               {'type': 'turn', 'turn': 1, 'replies': replies(5)},
                               {'type': 'result', 'result': result}):
                    stream.write(json.dumps(record)+'\n')
            row = {'taskId': 'synthetic', 'mapIndex': 0, 'seeds': [1, 2], 'replay': str(path),
                   'replaySha256': sha256(path.read_bytes()).hexdigest(), 'result': result, 'botCpuNs': [7, 7]}
            manifest = {'request': {'mapHashes': ['synthetic-map']}}
            self.assertEqual(review.inspect_replay(manifest, row, collect=True), [[5], [5]])
            with self.assertRaises(ValueError): review.inspect_replay(manifest, {**row, 'botCpuNs': [6, 7]})
            with self.assertRaises(ValueError): review.inspect_replay(manifest, {**row, 'replaySha256': 'bad'})
            with self.assertRaises(ValueError): review.inspect_replay(manifest, {**row, 'result': {'turns': 1, 'winner': 1}})


if __name__ == '__main__': unittest.main()
