"""User-run, non-scoring T6 bwrap acceptance. Dry planning is the default.

Run only after CA review and while the author is not bulk testing. One fresh
invocation per delivery; all artifacts remain local. This script issues no CA
or production approval receipt and never retries an entire experiment.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from arena.core.journal import atomic_json
from arena.games.outpost.replay import verify
from arena.tournament import fingerprint
from tools import experiment, experiment_plan as plan, profile_bot


def acceptance_specs():
    return [(1, profile_bot.build_spec('bots/public/M-balanced', ['bots/public/Z-harass'],
                                      ['maps/public/open-01.map'], 'package/claude-timing-jobs1.json', 1,
                                      identifier='accept-jobs1')),
            (6, profile_bot.build_spec('bots/public/M-balanced', ['bots/public/Z-rush'],
                                      ['maps/public/open-01.map', 'maps/public/corridor-01.map',
                                       'maps/scrimmage/island-01.map'],
                                      'package/claude-timing-jobs6.json', 6, identifier='accept-jobs6'))]


def run(out, *, execute=False, reviewed_sha256=None, exclusive_window=False):
    current = plan.implementation_digest()
    if execute and (reviewed_sha256 != current or not exclusive_window):
        raise ValueError('explicit current CA-reviewed digest and an exclusive author-idle window are required')
    specs = acceptance_specs()
    reserved = {'compiles': sum(s['caps']['compiles'] for _, s in specs),
                'botStarts': sum(s['caps']['botStarts'] for _, s in specs),
                'games': sum(s['caps']['games'] for _, s in specs)}
    # Two authorized deliveries still fit well inside T6's total40/400 budget.
    if reserved['compiles']*2 > 40 or reserved['botStarts']*2 > 400:
        raise ValueError('acceptance reservation exceeds the two-delivery T6 budget')
    if not execute:
        return {'schemaVersion': 1, 'executed': False, 'implementationSha256': current,
                'frameworkSha256': fingerprint(plan.ROOT), 'perInvocationReservations': reserved,
                'instruction': 'After CA review run once with --execute, reviewed digest and --exclusive-window; do not run alongside author bulk tests.'}
    root = plan.safe_path(out, exists=False)
    if root.exists() or not root.is_relative_to(plan.ROOT/'runs'):
        raise ValueError('fresh runs/ acceptance directory required')
    root.mkdir(parents=True, mode=0o700)
    before = time.process_time_ns(); wall = time.monotonic_ns()
    result = {'schemaVersion': 1, 'implementationSha256': current, 'frameworkSha256': fingerprint(plan.ROOT),
              'passed': False, 'executed': True, 'evidenceKind': 'public-bwrap-acceptance',
              'perInvocationReservations': reserved, 'cases': [],
              'benchmarks': 0, 'scoringGames': 0,
              'scope': 'Public-bot/public-or-scrimmage acceptance only; not independent timing or strength evidence.'}
    try:
        # Negative contracts must stop before any standard worker can be spawned.
        bad = json.loads(json.dumps(specs[0][1])); bad['bots'][0]['sha256'] = '0'*64
        try:
            plan.freeze(bad, (root/'bad-hash').relative_to(plan.ROOT).as_posix())
        except ValueError:
            result['wrongSourceHashRejected'] = True
        else:
            raise ValueError('wrong source digest was accepted')
        for jobs, spec in specs:
            folder = (root/f'jobs{jobs}').relative_to(plan.ROOT).as_posix()
            frame, digest = plan.freeze(spec, folder)
            try:
                experiment.execute(folder, digest)
            except ValueError:
                pass
            else:
                raise ValueError('runtime was not disabled by default')
            runtime = experiment.execute(folder, digest, enable_experimental=True)
            if runtime['status'] != 'complete':
                raise ValueError('standard experiment did not complete; no whole-run retry')
            summary = profile_bot.collect(folder)
            rows = experiment.Tail(plan.ROOT/folder/'batch/results.jsonl').poll(final=True)
            if len(rows) != frame['games'] or any(any(r['result'].get('faults') or []) for r in rows):
                raise ValueError('missing or faulty acceptance games')
            # Reuse standard recovery verification; never re-step an already verified replay.
            fresh_audits = 0; ingest_audits = 0
            for row in rows:
                path = profile_bot.local_artifact(row['replay'], plan.ROOT/folder/'batch')
                if plan.digest_file(path) != row['replaySha256']:
                    raise ValueError('acceptance replay changed')
                if row.get('replayVerifiedOnIngest'):
                    ingest_audits += 1
                else:
                    verify(path); fresh_audits += 1
            misses = []
            for p in (plan.ROOT/folder/'batch/preparations').glob('*/*/cache.json'):
                misses.append(not plan.load_json(p)['hit'])
            if sum(misses) > spec['caps']['compiles'] or (plan.ROOT/folder/'batch/bench').exists():
                raise ValueError('compile cap or no-benchmark contract failed')
            if any(summary['labels'][label]['TURN']['count'] == 0 for label in summary['labels']):
                raise ValueError('no TURN CPU telemetry')
            result['cases'].append({'jobs': jobs, 'completedGames': runtime['completedGames'],
                                    'auditedReplays': fresh_audits+ingest_audits,
                                    'newReplayAudits': fresh_audits, 'standardIngestAuditReceiptsReused': ingest_audits,
                                    'compileCacheMissReceipts': sum(misses),
                                    'headersAndCpuTotalsChecked': summary['completeReplaysHeaderAndCpuChecked'],
                                    'logVerified': True, 'cpuSummary': summary['labels'],
                                    'fixedLockSha256': spec['timing']['sha256']})
        result['passed'] = True
    except Exception as error:
        result['errorType'] = type(error).__name__
        result['message'] = str(error)
    finally:
        result['measuredScriptCpuSeconds'] = (time.process_time_ns()-before)/1e9
        result['scriptWallSeconds'] = (time.monotonic_ns()-wall)/1e9
        result['wholeProcessTreeCpuSeconds'] = None
        atomic_json(root/'acceptance-summary.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='runs/t6-acceptance01')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reviewed-sha256')
    parser.add_argument('--exclusive-window', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = run(args.out, execute=args.execute, reviewed_sha256=args.reviewed_sha256,
                     exclusive_window=args.exclusive_window)
        print(json.dumps(result, indent=2))
        return 0 if not args.execute or result['passed'] else 2
    except (OSError, ValueError) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
