"""Export allowlisted damage-22 aggregates, after independent ledger counting.

No games or replays are run. Output contains no map/task identities or per-game
rows. The complete local evidence remains in runs/ or private/ as appropriate.
"""
from __future__ import annotations

from collections import Counter
import csv
from hashlib import sha256
import json
import time

from arena.core.journal import records
from tools.analyze_damage22 import OUT, matched_rows
from tools.analyze_zoo import SINGLES
from tools.generate_hidden_maps import ROOT
from tools.phase_b_damage22 import CANDIDATE, CONTROL, DESTINATIONS, check_plan, inputs, summary_checks
from tools.phase_b_holdout import BASELINE, BATCH, MATRIX_FIELDS, cluster_fraction

PUBLIC = ROOT / 'data/phase-b/damage22'
CHANGE_FIELDS = ('bot', 'opponent', 'mapType', 'games', 'maps', 'baselineWins', 'candidateWins',
                 'baselineDraws', 'candidateDraws', 'transitions', 'winRateDelta', 'winRateDeltaCI95',
                 'scoreRateDelta', 'scoreRateDeltaCI95', 'improvedMaps', 'worsenedMaps', 'unchangedMaps')


def independent_counts(report, rows):
    names = report['bots']
    counts = Counter()
    for row in rows:
        a, b = (names[i] for i in row['players'])
        if a == b:
            continue
        for side, (bot, opponent) in enumerate(((a, b), (b, a))):
            result = 'D' if row['result']['winner'] is None else 'W' if row['result']['winner'] == side else 'L'
            for typ in ('all', row['mapType']):
                counts[bot, opponent, typ, result] += 1
    for cell in report['matrix']:
        key = cell['bot'], cell['opponent'], cell['mapType']
        expected = [counts[*key, outcome] for outcome in ('W', 'D', 'L')]
        if expected != [cell[k] for k in ('wins', 'draws', 'losses')] or sum(expected) != cell['games']:
            raise ValueError('independent aggregate counts disagree')
    if len(report['matrix']) != 450:
        raise ValueError('incomplete aggregate matrix')
    return len(report['matrix'])


def dump(name, value):
    path = PUBLIC / name
    if path.exists():
        raise ValueError('review output exists; do not overwrite')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def csv_rows(name, fields, rows):
    with (PUBLIC / name).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], sort_keys=True) if isinstance(row[k], (dict, list)) else row[k] for k in fields})


def main():
    start = time.process_time_ns()
    _, candidate, old_manifests = inputs()
    baseline = json.loads(BASELINE.read_text())
    old_paths = {'public': ROOT / baseline['batch'], 'calibration': BATCH}
    paired = json.loads((OUT / 'report.json').read_text())
    cohorts = json.loads((OUT / 'cohorts.json').read_text())
    review = {'schemaVersion': 1, 'decision': 'reject candidate and stop; no default/bot/map change or ladder work',
        'scope': 'single authorized SOLDIER_DMG 20->22 trial; calibration is now development data, not a fresh holdout',
        'bootstrap': {'replicates': 4000, 'unit': 'map, both seats retained together',
                      'limits': 'conditional on fixed maps and bot seeds; no multiplicity adjustment; point gates not waived by CI'},
        'groups': {}}
    usage = {'schemaVersion': 1, 'batches': {}, 'totalCpuHours': None, 'compilationCpuHours': None,
             'limits': 'partial process counters only; controllers exclude children; no RUSAGE_CHILDREN sums; not wall time'}
    provenance = {'schemaVersion': 1, 'candidateSha256': sha256(CANDIDATE.read_bytes()).hexdigest(),
                  'baselineRulesSha256': sha256((ROOT / 'rules/standard-1.json').read_bytes()).hexdigest(),
                  'runHead': 'cc3fc28a2f292892fe8c20667f659ba23a237920', 'runStartedClean': True,
                  'trajectoryAnalysisHead': '5cedf4c5b2d1b57f8c27b91275b95bade10fbcb5',
                  'cohortSupplement': 'added after outcome; exploratory, existing trajectories only',
                  'toolsSha256': {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in
                                  ('tools/phase_b_damage22.py', 'tools/analyze_damage22.py', 'tools/publish_damage22.py')},
                  'groups': {}}
    matrices = []; changes = []
    for group, path in DESTINATIONS.items():
        report = json.loads((path.with_name(path.name + '-analysis') / 'report.json').read_text())
        manifest = json.loads((path / 'manifest.json').read_text())
        check_plan(manifest, old_manifests[group], candidate)
        for name, digest in report['inputsSha256'].items():
            if sha256((path / name).read_bytes()).hexdigest() != digest:
                raise ValueError('candidate ledger changed after audit')
        rows = records(path / 'results.jsonl')
        checked = independent_counts(report, rows)
        pairs = matched_rows(records(old_paths[group] / 'results.jsonl'), rows, old_manifests[group], manifest)
        paired_cells = paired['groups'][group]['matrixChanges']
        old_report = baseline if group == 'public' else json.loads((BATCH.parent / 'holdout-v15-analysis/report.json').read_text())
        old_lookup = {(c['bot'], c['opponent'], c['mapType']): c for c in old_report['matrix']}
        new_lookup = {(c['bot'], c['opponent'], c['mapType']): c for c in report['matrix']}
        for cell in paired_cells:
            key = cell['bot'], cell['opponent'], cell['mapType']
            if (cell['baselineWins'] != old_lookup[key]['wins'] or cell['candidateWins'] != new_lookup[key]['wins']
                    or sum(cell['transitions'].values()) != cell['games']):
                raise ValueError('paired marginal counts disagree')
        names = manifest['bots']
        self_rows = [r for r in rows if names[r['players'][0]] == names[r['players'][1]] == 'M-balanced']
        non_idle = [r for r in rows if r['players'][0] != r['players'][1] and 'Z-idle' not in [names[i] for i in r['players']]]
        balanced = {k: report['balancedSelf'][k] for k in ('games', 'maps', 'medianTurns', 'by60Fraction',
                    'endReasons', 'baseEndingFraction', 'turnLimitFraction')}
        balanced['baseEndingFractionCI95'] = cluster_fraction(self_rows, lambda r: r['result']['reason'] == 'base_destroyed')
        balanced['turnLimitFractionCI95'] = cluster_fraction(self_rows, lambda r: r['result']['reason'].startswith('turn_limit_'))
        review['groups'][group] = {'gates': summary_checks(report, group), 'completedGames': len(rows),
            'attemptCounts': report['attemptCounts'], 'replaysVerified': sum(r['verified'] for r in report['replayAudit']['replays']),
            'botFaultGames': report['botFaultGames'], 'protocolWarnings': report['protocolWarnings'],
            'counters': {b: report['rateChecks']['winRate']['counters'][b] for b in SINGLES},
            'balancedSelf': balanced, 'nonIdleDistinctGames': len(non_idle),
            'nonIdleDrawGames': sum(r['result']['winner'] is None for r in non_idle),
            'drawRateExcludingIdleAndSameName': report['drawRateExcludingIdleAndSameName'],
            'fairness': [{k: r[k] for k in ('bot', 'maps', 'seatScoreRateDifference', 'CI95', 'within3PointsAndCIContainsZero')} for r in report['fairness']],
            'pairedGames': len(pairs), 'winnerChangedGames': sum(a['result']['winner'] != b['result']['winner'] for _, a, b in pairs),
            'endingChangedGames': sum(a['result']['reason'] != b['result']['reason'] for _, a, b in pairs),
            'independentlyCountedMatrixCells': checked,
            'replayAuditInputDigestsMatch': True, 'pairedMarginalsMatch': True}
        provenance['groups'][group] = {'inputsSha256': report['inputsSha256'],
            'baselineInputsSha256': old_report['inputsSha256'], 'reportSha256': sha256((path.with_name(path.name + '-analysis') / 'report.json').read_bytes()).hexdigest(),
            'executionFramework': report['executionFramework'], 'verificationFramework': report['verificationFramework']}
        usage['batches'][group] = {k: report['recordedUsage'][k] for k in ('botCpuNs', 'matchHarnessCpuNs',
            'replayVerificationCpuNs', 'turnHarnessCpuNsP95', 'turnHarnessCpuNsMax')}
        matrices.extend({'mapSet': group, **{k: c[k] for k in MATRIX_FIELDS}} for c in report['matrix'])
        changes.extend({'mapSet': group, **{k: c[k] for k in CHANGE_FIELDS}} for c in paired_cells)
    receipts = [json.loads(p.read_text()) for p in sorted((CONTROL / 'control-usage').glob('*.json'))]
    run = next(r for r in receipts if r['action'] == 'run')
    assert run['gitHead'] == provenance['runHead'] and not run['worktreeDirty'] and run['status'] == 'complete'
    usage['controllers'] = [{k:r[k] for k in ('action', 'status', 'processCpuNs', 'scope')} for r in receipts]
    usage['trajectoryDiagnostics'] = paired['usage']
    usage['cohortSupplementCpuNs'] = cohorts['processCpuNs']
    # Only aggregate all-map focus cohorts and the preregistered maze/tower slice.
    select = lambda r: r['mapType'] == 'all' or (r['focus'], r['opponent'], r['mapType']) == ('M-balanced', 'Z-towers', 'maze')
    selected = [r for r in paired['trajectories'] if select(r)]
    fields = ('mapSet', 'revision', 'focus', 'opponent', 'mapType', 'games', 'outcomes', 'endReasons', 'turns',
              'firstSoldier', 'firstSoldierContact', 'soldiersAtContact', 'firstBaseHit', 'firstBaseReached', 'firstTower',
              'soldierAttackCounts', 'casualties', 'soldierMoves', 'soldierFailedMoves', 'baseAttackTurns', 'samples', 'final')
    if all(g['gates']['passed'] for g in review['groups'].values()):
        raise ValueError('this rejected-trial export does not authorize acceptance')
    dump('results.json', review)
    csv_rows('candidate-matrix.csv', ('mapSet', *MATRIX_FIELDS), matrices)
    csv_rows('paired-changes.csv', ('mapSet', *CHANGE_FIELDS), changes)
    dump('trajectories.json', {'scope': 'aggregate-only planned focus pairs; side 0=focus (seat 0 for self-play); missing milestones not imputed',
                             'rows': [{k:r[k] for k in fields} for r in selected]})
    fields = ('mapSet', 'focus', 'opponent', 'mapType', 'games', 'firstSoldierSameGames', 'firstContactSameGames',
              'contactArmySameGames', 'baseContactLostGames', 'baseContactGainedGames', 'revisions', 'endTransitions', 'outcomeTransitions')
    dump('cohorts.json', {'scope': 'exploratory exhaustive outcome/ending partitions of focus cohorts; aggregate-only',
                        'groups': [{k:r[k] for k in fields} for r in cohorts['groups'] if select(r)]})
    dump('provenance.json', provenance)
    usage['publicationProcessCpuNsBeforeFinalWrite'] = time.process_time_ns() - start
    dump('usage.json', usage)
    print(json.dumps({'games': sum(s['completedGames'] for s in review['groups'].values()), 'matrixCellsChecked': 900,
                      'pairedCellsChecked': len(changes), 'candidateRejected': True}, indent=2))


if __name__ == '__main__':
    main()
