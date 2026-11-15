"""Predeclared matched comparisons and calendar-block power; no fitting."""
from statistics import NormalDist
import math
import numpy as np


def holm(pvalues):
    """Unassessable cells must be supplied as1, preserving the whole family."""
    p = np.asarray(pvalues, float)
    if len(p) != 6 or not np.isfinite(p).all() or ((p<0)|(p>1)).any():
        raise ValueError('SIX_VALID_P_VALUES_REQUIRED')
    order = np.argsort(p, kind='stable'); out = np.ones(6); running = 0.
    for j, i in enumerate(order):
        running = max(running, (6-j)*p[i]); out[i] = min(1., running)
    return out.tolist()


def required_n(sigma, effect=.001):
    if not np.isfinite(sigma) or sigma <= 0:
        return None
    z = NormalDist().inv_cdf(1-.05/6)+NormalDist().inv_cdf(.8)
    return int(math.ceil((z*sigma/effect)**2))


def calendar_bootstrap(values, days, first_day, last_day, replicates=2000):
    """Calendar7day moving blocks include days without observations."""
    x, days = np.asarray(values, float), np.asarray(days, int)
    if len(x) < 2 or not np.isfinite(x).all():
        return dict(n=len(x), effective_n=0., ci=None, p=1., occupied_blocks=0)
    n_days = last_day-first_day+1
    sums, counts = np.zeros(n_days), np.zeros(n_days)
    for v, d in zip(x, days):
        sums[d-first_day] += v; counts[d-first_day] += 1
    rng = np.random.default_rng(20261115)
    starts = rng.integers(0, n_days, (replicates, (n_days+6)//7))
    ix = ((starts[:,:,None]+np.arange(7))%n_days).reshape(replicates,-1)[:,:n_days]
    ns, ss = counts[ix].sum(axis=1), sums[ix].sum(axis=1)
    means = ss[ns>0]/ns[ns>0]
    variance = float(np.var(means, ddof=1)) if len(means)>1 else float('nan')
    ess = min(float(len(x)), float(np.var(x, ddof=1)/variance)) if variance>0 else 0.
    # Centered null bootstrap: dependence-aware approximation, not exact test.
    centered = means-float(np.mean(x))
    p = (1+int(np.count_nonzero(centered >= np.mean(x))))/(len(means)+1)
    return dict(n=len(x), effective_n=ess, ci=np.quantile(means,[.025,.975]).tolist(),
                p=float(p), occupied_blocks=len(set((days-first_day)//7)),
                valid_replicates=len(means), mean=float(np.mean(x)), median=float(np.median(x)))


def assess(values, days, first_day, last_day, minimum_n):
    r = calendar_bootstrap(values, days, first_day, last_day)
    r['required_effective_n'] = minimum_n
    r['testable'] = bool(minimum_n and r['effective_n'] >= minimum_n and r['occupied_blocks'] >= 20)
    r['classification'] = 'INCONCLUSO' if r['testable'] else 'NO TESTABLE'
    r['p_for_holm'] = r['p'] if r['testable'] else 1.
    return r
