"""Review-only publication checks; full game evidence stays on the developer host.

This is a packaging policy, not a game validator. It preserves aggregate counts,
matrices, intervals and test diagnostics, but rejects raw games and their indexes.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import PurePosixPath
import re
import subprocess


LOCAL_SECTIONS = {
    'attempts', 'newAttempts', 'directedGames', 'targeted', 'replayInspection',
    'publicSmoke', 'publicReplayChecks', 'nonMatchFixtureLedgers',
    'unrecordedOriginalWorkerStarts', 'attemptIndexes', 'attemptsIndexes',
    'replaysIndexes', 'storedDuplicateArtifacts',
}
PER_GAME_SERIES = {
    'wallSeconds', 'botCpuSeconds', 'calibratedTurnCpuMs', 'wallLimitSeconds',
    'jobs1GameWallSeconds', 'jobs6GameWallSeconds',
}


def path_problem(path: str) -> str | None:
    p = PurePosixPath(path)
    if p.parts and p.parts[0] in ('private', 'runs', '.venv'):
        return 'local-only directory'
    if path.startswith('replays/') and path != 'replays/README.md':
        return 'replays are local-only, including public-bot examples'
    if path.endswith(('.hrw.jsonl.gz', '.jsonl', '.sqlite', '.sqlite3')):
        return 'raw replay/result database'
    if path.startswith('data/'):
        if p.name.startswith('games-') and p.suffix == '.csv':
            return 'per-game CSV'
        if re.fullmatch(r'(?:phase-a-validation-)?(?:attempts|replays)-\d+\.json', p.name):
            return 'per-game audit index'
    return None


def record_problem(value: dict) -> str | None:
    if {'matchId', 'match_id', 'taskId', 'resultJson'} & value.keys():
        return 'individual match/task record'
    if {'winner', 'reason', 'turns', 'scores'} <= value.keys():
        return 'individual game result'
    if isinstance(value.get('type'), str) and value['type'] in ('header', 'turn', 'fault', 'init', 'result') and (
            'stateHash' in value or 'initialStateHash' in value):
        return 'replay record'
    if any(key.endswith('.hrw.jsonl.gz') or re.search(
            r'/matches/[0-9a-f]{32}/attempt-\d+(?:/|$)', key) for key in value):
        return 'per-game digest mapping'
    for key in ('replay', 'hostReplay', 'path', 'directory'):
        path = value.get(key)
        if isinstance(path, str) and (path.endswith('.hrw.jsonl.gz') or re.search(
                r'/matches/[0-9a-f]{32}/attempt-\d+(?:/|$)', path)):
            return 'individual replay/attempt reference'
    return None


def forbidden_sections(path: tuple[str, ...], key: str, value) -> bool:
    if key in LOCAL_SECTIONS and isinstance(value, (dict, list)):
        return True
    if key in ('replays', 'indexes') and isinstance(value, list):
        return True
    if path == ('calibratedMapIntegration',) and key == 'runs':
        return True
    return False


def summarize(value, omissions: dict[str, int], path: tuple[str, ...] = ()):
    """Return a derived review copy, never modify the supplied full evidence."""
    if isinstance(value, dict):
        if record_problem(value):
            omissions['/'.join(path) or '<root>'] = omissions.get('/'.join(path) or '<root>', 0) + 1
            return None
        result = {}
        for key, item in value.items():
            where = (*path, key)
            if forbidden_sections(path, key, item):
                omissions['/'.join(where)] = len(item)
            elif key in PER_GAME_SERIES and isinstance(item, list) and item and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) for v in item):
                result[key + 'Summary'] = {'count': len(item), 'min': min(item),
                                          'max': max(item), 'mean': sum(item) / len(item)}
                omissions['/'.join(where)] = len(item)
            else:
                child = summarize(item, omissions, where)
                if child is not None or item is None:
                    result[key] = child
        return result
    if isinstance(value, list):
        items = [summarize(item, omissions, (*path, '<item>')) for item in value]
        kept = [item for old, item in zip(value, items) if item is not None or old is None]
        return kept if kept or not value else None
    return value


def payload_problem(path: str, body: bytes) -> str | None:
    problem = path_problem(path)
    if problem:
        return problem
    if path.startswith(('data/', 'logs/')) and path.endswith(('.json', '.csv', '.log')):
        # Diagnostic logs can embed a repr/JSON record even without a JSON schema.
        if re.search(rb'''["'](?:matchId|taskId|resultJson)\\*["']\s*:''', body):
            return 'embedded individual match/task record'
    if not path.startswith('data/'):
        return None
    if path.endswith('.csv'):
        header = next(csv.reader(io.StringIO(body.decode('utf-8'))), [])
        if set(header) & {'matchId', 'taskId', 'resultJson', 'replay', 'seed0', 'seed1'}:
            return 'per-game CSV columns'
    if not path.endswith('.json'):
        return None
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        return 'invalid review JSON'

    def inspect(item, at=()):
        if isinstance(item, dict):
            if problem := record_problem(item):
                return problem
            for key, child in item.items():
                if forbidden_sections(at, key, child):
                    return 'local-only evidence section: ' + key
                if key in PER_GAME_SERIES and isinstance(child, list):
                    return 'per-game measurement series: ' + key
                if problem := inspect(child, (*at, key)):
                    return problem
        elif isinstance(item, list):
            for child in item:
                if problem := inspect(child, (*at, '<item>')):
                    return problem
        return None

    return inspect(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', required=True)
    parser.parse_args()
    paths = subprocess.check_output([
        'git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'
    ]).decode().split('\0')
    failed = False
    for path in filter(None, paths):
        body = subprocess.check_output(['git', 'show', ':' + path])
        if problem := payload_problem(path, body):
            print(f'publication: {path}: {problem}; keep full evidence locally and publish a summary')
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
