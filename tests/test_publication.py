"""Publication checks inspect metadata only; no bot/benchmark execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.publication import path_problem, payload_problem, summarize

ROOT = Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):
    def test_raw_artifact_paths_are_rejected_regardless_of_size(self):
        for path in ('replays/sample.hrw.jsonl.gz', 'elsewhere/result.jsonl',
                     'data/zoo/games-open.csv', 'data/phase-a-final-validation/attempts-001.json',
                     'data/phase-a-validation-replays-001.json', 'runs/report.json'):
            with self.subTest(path=path):
                self.assertIsNotNone(path_problem(path))
        self.assertIsNone(path_problem('replays/README.md'))

    def test_renaming_game_records_does_not_make_them_summaries(self):
        for row in ({'matchId': 'synthetic'}, {'resultJson': '{}'},
                    {'winner': 0, 'reason': 'bot_fault', 'turns': 0, 'scores': [0, 0]},
                    {'path': 'replays/example.hrw.jsonl.gz', 'sha256': 'dummy'}):
            with self.subTest(row=row):
                self.assertIsNotNone(payload_problem('data/innocent.json', json.dumps({'nested': [row]}).encode()))
        self.assertIsNotNone(payload_problem('data/innocent.csv', b'map,seed0,resultJson\na,17,{}\n'))
        self.assertIsNotNone(payload_problem('logs/failure.log', b"AssertionError: {'matchId': 'synthetic'}"))
        embedded = json.dumps({'stdout': json.dumps({'matchId': 'synthetic'})}).encode()
        self.assertIsNotNone(payload_problem('data/wrapped.json', embedded))

    def test_summary_retains_failure_counts_and_matrix_without_game_rows(self):
        original = {'attemptCounts': {'complete': 8, 'infra_error': 2},
                    'matrix': [{'bot': 'A', 'opponent': 'B', 'games': 8, 'wins': 3, 'losses': 5}],
                    'replayAudit': {'count': 8, 'allVerified': True,
                                    'replays': [{'path': 'one.hrw.jsonl.gz'}]},
                    'newAttempts': [{'matchId': 'synthetic', 'status': 'infra_error'}]}
        omissions = {}
        review = summarize(original, omissions)
        assert isinstance(review, dict)
        self.assertEqual(review['attemptCounts'], original['attemptCounts'])
        self.assertEqual(review['matrix'], original['matrix'])
        self.assertNotIn('replays', review['replayAudit'])
        self.assertIn('newAttempts', omissions)
        self.assertIsNone(payload_problem('data/report.json', json.dumps(review).encode()))
        self.assertEqual(len(original['newAttempts']), 1)  # full local input untouched

    def test_per_game_measurements_become_aggregate_ranges(self):
        omissions = {}
        review = summarize({'wallSeconds': [2.0, 4.0]}, omissions)
        self.assertEqual(review, {'wallSecondsSummary': {'count': 2, 'min': 2.0, 'max': 4.0, 'mean': 3.0}})
        self.assertIsNone(payload_problem('data/report.json', json.dumps(review).encode()))

    def test_cli_checks_staged_bytes_not_clean_working_copy(self):
        root = ROOT/'runs/development/publication-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            work = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(work)], check=True)
            path = work/'data/report.json'
            path.parent.mkdir()
            path.write_text('{"matchId":"synthetic-only"}')
            subprocess.run(['git', 'add', 'data/report.json'], cwd=work, check=True)
            path.write_text('{"completedGames":8}')
            command = [sys.executable, str(ROOT/'tools/publication.py'), '--staged']
            rejected = subprocess.run(command, cwd=work, capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 1, rejected.stderr)
            subprocess.run(['git', 'add', 'data/report.json'], cwd=work, check=True)
            accepted = subprocess.run(command, cwd=work, capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)


if __name__ == '__main__':
    unittest.main()
