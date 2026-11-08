"""The single user-authorized damage-22 experiment; no parameter search.

Plan both full matrices, run them sequentially at jobs=6, then audit both. The
accepted default remains unchanged. Calibration and combined outputs are private.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

from arena.tournament import run_tournament
from tools.analyze_zoo import SINGLES, analyze, relative
from tools.generate_hidden_maps import ROOT, immutable_write, json_bytes, private_path, validate
from tools.phase_b_holdout import BATCH, REFERENCE, frozen_inputs, validate_plan

CANDIDATE = ROOT / 'rules/candidates/phase-b-soldier-damage-22.json'
CONTROL = ROOT / 'private/phase-b/damage22'
DESTINATIONS = {
    'public': ROOT / 'runs/development/phase-b-damage22-public',
    'calibration': CONTROL / 'calibration',
}


def check_candidate(candidate, frozen):
    if (candidate != {**frozen, 'SOLDIER_DMG': 22} or frozen['SOLDIER_DMG'] != 20
            or any(type(v) is not int for v in candidate.values())):
        raise ValueError('only SOLDIER_DMG 20->22 is authorized in this experiment')
    return candidate


def task_content(task):
    return {k: v for k, v in task.items() if k != 'taskId'}


def check_plan(manifest, old, candidate):
    """Same maps/order, bot bytes, seat/seed pairs and concurrency, only DMG differs."""
    request = manifest['request']
    check_candidate(request['ruleset'], old['request']['ruleset'])
    if request['ruleset'] != candidate or manifest['bots'] != old['bots']:
        raise ValueError('candidate rules/names changed')
    for key in ('jobs', 'pairs', 'seeds', 'sandbox', 'framework', 'sourceHashes', 'referenceSha256', 'mapHashes'):
        if request[key] != old['request'][key]:
            raise ValueError('paired experiment input differs: ' + key)
    if [task_content(t) for t in manifest['tasks']] != [task_content(t) for t in old['tasks']]:
        raise ValueError('paired experiment task/seat/map plan changed')
    for task in manifest['tasks']:
        expected = sha256(json.dumps([request, task_content(task)], sort_keys=True).encode()).hexdigest()
        if task['taskId'] != expected:
            raise ValueError('invalid task identity')


def check_baseline_report(manifest, report, names):
    # Existing review reports relativize paths; immutable manifests keep absolute
    # paths. Normalize only presentation, preserving every hash/configuration.
    if relative(manifest['request']) != relative(report['request']) or manifest['bots'] != names:
        raise ValueError('baseline plan/report mismatch')


def inputs():
    baseline, sources, frozen = frozen_inputs()
    candidate = check_candidate(json.loads(CANDIDATE.read_text()), frozen)
    catalog = validate(ROOT / 'private/maps')
    # Anchor the private catalog to the already published pre-outcome commitment.
    committed = json.loads((ROOT / 'data/phase-b/maps.json').read_text())
    if sha256((ROOT / 'private/maps/catalog.json').read_bytes()).hexdigest() != committed['privateCatalogSha256']:
        raise ValueError('committed hidden catalog changed')
    old_public = ROOT / baseline['batch']
    reports = {'public': baseline, 'calibration': json.loads((BATCH.parent / 'holdout-v15-analysis/report.json').read_text())}
    old_runs = {'public': old_public, 'calibration': BATCH}
    manifests = {}
    for group, path in old_runs.items():
        report = reports[group]
        for name in ('manifest.json', 'results.jsonl', 'attempts.jsonl'):
            if sha256((path / name).read_bytes()).hexdigest() != report['inputsSha256'][name]:
                raise ValueError('baseline ledger changed')
        old = json.loads((path / 'manifest.json').read_text())
        check_baseline_report(old, report, baseline['bots'])
        for key in ('jobs', 'pairs', 'seeds', 'sandbox', 'ruleset', 'framework', 'sourceHashes', 'referenceSha256'):
            if old['request'][key] != baseline['request'][key]:
                raise ValueError('baseline input mismatch: ' + key)
        if len(old['tasks']) != (3680 if group == 'public' else 2208):
            raise ValueError('baseline task count mismatch')
        for filename, digest in zip(old['request']['maps'], old['request']['mapHashes']):
            if sha256(Path(filename).read_bytes()).hexdigest() != digest:
                raise ValueError('original map content changed')
        manifests[group] = old
    validate_plan(manifests['calibration'], catalog, baseline)
    private_path(CONTROL)
    for group, out in DESTINATIONS.items():
        if group == 'calibration':
            private_path(out)
        elif not out.resolve().is_relative_to(ROOT / 'runs'):
            raise ValueError('public raw games must stay in runs/')
    return sources, candidate, manifests


def summary_checks(report, group):
    """Numeric gates; transcript symmetry/robustness are reported separately."""
    if not report['complete']:
        return {'complete': False, 'passed': False}
    rates = report['rateChecks']['winRate']
    observed = report['observedChecks']
    checks = {'1': rates['eachSingleLosesToAnother'],
              '2': rates['balancedOverall70'] and rates['balancedEveryType55'],
              '4': observed['drawRateBelow10'], '6': observed['bothEndings20To80'],
              '7': all(c['winRate'] >= .5 for c in report['matrix']
                       if c['bot'] == 'M-balanced' and c['opponent'] in SINGLES and c['mapType'] != 'all')}
    if group == 'public':
        checks.update({'3': observed['fairness'],
                       '5': observed['selfMedianAtLeast120'] and observed['selfBy60Below20']})
    integrity = report['replayAudit']['allVerified'] and report['botFaultGames'] == report['protocolWarnings'] == 0
    return {'complete': True, 'integrity': integrity, 'conditions': checks,
            'passed': integrity and all(checks.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'run', 'analyze'))
    args = parser.parse_args()
    start = time.process_time_ns()
    sources, candidate, old = inputs()
    CONTROL.mkdir(parents=True, exist_ok=True)
    receipt = {'action': args.action, 'startedAt': datetime.now(timezone.utc).isoformat(),
               'gitHead': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'worktreeDirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
               'candidateSha256': sha256(CANDIDATE.read_bytes()).hexdigest(),
               'scope': 'controller process including input checks; excludes children/compilation; run includes benchmark harness',
               'compileCpuHours': None, 'fullCpuHours': None, 'groups': {}}
    usage = CONTROL / 'control-usage'
    usage.mkdir(exist_ok=True)
    number = len(list(usage.glob('*.json')))
    try:
        # Check every existing plan before starting either matrix.
        if args.action != 'plan':
            for group, out in DESTINATIONS.items():
                m = json.loads((out / 'manifest.json').read_text())
                check_plan(m, old[group], candidate)
                if m['request']['maps'] != old[group]['request']['maps'] or m['request']['sources'] != [str(p) for p in sources]:
                    raise ValueError('plan input paths changed')
        for group, out in DESTINATIONS.items():
            if args.action in ('plan', 'run'):
                if args.action == 'plan' and out.exists():
                    raise ValueError('candidate batch already exists; do not create a second experiment')
                result = run_tournament(sources, [Path(p) for p in old[group]['request']['maps']], out,
                    jobs=6, include_self=['M-balanced'], seeds=(17, 29), reference=REFERENCE,
                    sandbox='bwrap', ruleset=candidate, resume=args.action == 'run',
                    max_tasks=0 if args.action == 'plan' else None)
                check_plan(json.loads((out / 'manifest.json').read_text()), old[group], candidate)
                receipt['groups'][group] = {k: result[k] for k in ('tasks', 'completed', 'remaining', 'infraErrorAttempts')}
                if args.action == 'run' and result['status'] != 'complete':
                    raise ValueError('incomplete experiment; preserve all failures and stop')
            else:
                analysis_out = out.with_name(out.name + '-analysis')
                report = analyze(out, analysis_out, jobs=4)
                receipt['groups'][group] = summary_checks(report, group)
            print(json.dumps({'group': group, **receipt['groups'][group]}), flush=True)
        receipt['status'] = 'complete'
    except Exception as error:
        receipt.update(status='failed', error=type(error).__name__)
        raise
    finally:
        receipt['processCpuNs'] = time.process_time_ns() - start
        immutable_write(usage / f'{number:02d}-{args.action}.json', json_bytes(receipt))


if __name__ == '__main__':
    main()
