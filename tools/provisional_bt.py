"""Small standard-library BT MLE with explicit separation and map bootstrap.

No pseudocounts, prior, Elo clipping, games or formal ladder assignment. A finite
MLE exists only in a strongly connected comparison graph (Ford's condition;
see BradleyTerryScalable's comparison-graph documentation). Fit the anchor's
strongly connected component; report other components as boundaries/unidentified.
"""
from collections import Counter
import math
import random

ELO_SCALE = 400/math.log(10)


def validate(counts):
    n = len(counts)
    if not n or any(len(row) != n for row in counts):
        raise ValueError('nonempty square win-score matrix required')
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for row in counts for v in row):
        raise ValueError('finite nonnegative win scores required')
    if any(counts[i][i] for i in range(n)):
        raise ValueError('exclude self play from BT')


def reachable(counts, start, reverse=False):
    found = {start}; queue = [start]
    while queue:
        i = queue.pop()
        for j in range(len(counts)):
            if (counts[j][i] if reverse else counts[i][j]) > 0 and j not in found:
                found.add(j); queue.append(j)
    return found


def solve(matrix, vector):
    """Pivoted elimination for the small anchored information matrix."""
    n = len(vector); a = [list(row)+[value] for row, value in zip(matrix, vector)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(a[i][k]))
        a[k], a[pivot] = a[pivot], a[k]
        if abs(a[k][k]) < 1e-14: raise ValueError('singular BT information matrix')
        for i in range(k+1, n):
            factor = a[i][k]/a[k][k]
            for j in range(k+1, n+1): a[i][j] -= factor*a[k][j]
    result = [0.0]*n
    for i in reversed(range(n)):
        result[i] = (a[i][n]-sum(a[i][j]*result[j] for j in range(i+1, n)))/a[i][i]
    return result


def softplus(x):
    return max(0.0, x)+math.log1p(math.exp(-abs(x)))


def fit(counts, anchor=0):
    validate(counts); n = len(counts)
    if type(anchor) is not int or not 0 <= anchor < n: raise ValueError('invalid anchor')
    below = reachable(counts, anchor); above = reachable(counts, anchor, reverse=True)
    component = sorted(below & above); free = [i for i in component if i != anchor]
    positions = {i: p for p, i in enumerate(free)}
    edges = [(i, j, counts[i][j], counts[j][i]) for i in component for j in component
             if i < j and counts[i][j]+counts[j][i] > 0]
    theta = [0.0]*n

    def likelihood(values):
        return sum(-a*softplus(values[j]-values[i])-b*softplus(values[i]-values[j]) for i, j, a, b in edges)

    residual = 0.0; iterations = 0
    for iterations in range(101):
        gradient = [0.0]*len(free); hessian = [[0.0]*len(free) for _ in free]
        for i, j, a, b in edges:
            delta = theta[i]-theta[j]
            p = 1/(1+math.exp(-delta)) if delta >= 0 else math.exp(delta)/(1+math.exp(delta))
            g = a-(a+b)*p; h = (a+b)*p*(1-p)
            if i != anchor:
                u = positions[i]; gradient[u] += g; hessian[u][u] += h
            if j != anchor:
                v = positions[j]; gradient[v] -= g; hessian[v][v] += h
            if i != anchor and j != anchor:
                u, v = positions[i], positions[j]; hessian[u][v] -= h; hessian[v][u] -= h
        residual = max(map(abs, gradient), default=0.0)
        if residual <= 1e-8: break
        if iterations == 100: raise ValueError('BT solver did not converge')
        step = solve(hessian, gradient)
        scale = min(1.0, 4/max(map(abs, step)))
        before = likelihood(theta)
        for _ in range(40):
            proposed = theta.copy()
            for i, change in zip(free, step): proposed[i] += scale*change
            if likelihood(proposed) >= before-1e-10:
                theta = proposed; break
            scale *= .5
        else: raise ValueError('BT line search did not converge')
    values = [theta[i]*ELO_SCALE if i in component else '-infinity' if i in below
              else '+infinity' if i in above else None for i in range(n)]
    return {'elo': values, 'anchorComponent': component, 'finiteFullMLE': len(component) == n,
            'iterations': iterations, 'maxScoreResidual': residual}


def percentile(values, probability):
    """Nearest-rank order statistic, retaining +/- infinity and no clipping."""
    if not values or not 0 < probability <= 1: raise ValueError('invalid percentile')
    ordered = sorted(values, key=lambda x: float('-inf') if x == '-infinity' else float('inf') if x == '+infinity' else x)
    return ordered[max(0, math.ceil(probability*len(ordered))-1)]


def bootstrap(clusters, anchor=0, *, samples=4000, seed=4219):
    if not clusters or type(samples) is not int or samples <= 0: raise ValueError('clusters and samples required')
    for matrix in clusters: validate(matrix)
    n = len(clusters[0]); size = len(clusters)
    if any(len(m) != n for m in clusters): raise ValueError('different graph dimensions')
    rng = random.Random(seed); values = [[] for _ in range(n)]; finite = 0
    for _ in range(samples):
        weights = Counter(rng.randrange(size) for _ in range(size))
        counts = [[sum(clusters[k][i][j]*weight for k, weight in weights.items())
                   for j in range(n)] for i in range(n)]
        result = fit(counts, anchor); finite += result['finiteFullMLE']
        for target, value in zip(values, result['elo']): target.append(value)
    summaries = []
    for row in values:
        missing = sum(v is None for v in row)
        summaries.append({'interval95': None if missing else [percentile(row, .025), percentile(row, .975)],
                          'unidentifiedSamples': missing, 'negativeInfiniteSamples': row.count('-infinity'),
                          'positiveInfiniteSamples': row.count('+infinity'), 'samples': samples})
    return {'samples': samples, 'seed': seed, 'mapClusters': size, 'finiteFullMLEReplicates': finite,
            'ratings': summaries, 'rawElo': values,
            'method': 'all opponents and both seats in each map jointly resampled; nearest-rank 2.5/97.5 percentiles; no rejected bootstrap draws, pseudocounts, clipping or multiplicity correction'}
