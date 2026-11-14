"""012 direction-conditional DEV diagnostics. Never accepts a mixed-direction pool."""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from statistics import median, NormalDist
import math
import random
from .stage03_research_evidence import digest


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def correlation(x, y):
    if len(x) != len(y) or len(x) < 3 or not all(numeric(v) for v in [*x, *y]):
        return None
    ax, ay = sum(x)/len(x), sum(y)/len(y)
    den = math.sqrt(sum((v-ax)**2 for v in x)*sum((v-ay)**2 for v in y))
    return sum((a-ax)*(b-ay) for a, b in zip(x, y))/den if den else None


def fit_reference(values, phase, trained_through, available_at):
    if phase != 'DEV':
        raise ValueError('HOLDOUT_FIT_FORBIDDEN')
    if not numeric(trained_through) or not numeric(available_at) or available_at < trained_through:
        raise ValueError('REFERENCE_BACKDATED')
    if len(values) < 3 or not all(numeric(v) for v in values):
        raise ValueError('REFERENCE_INVALID')
    v = sorted(values)
    m = median(v)
    body = dict(values=v, median=m, mad=median(abs(x-m) for x in v),
                trained_through=trained_through, available_at=available_at, phase='DEV')
    return dict(body, sha256=digest(body))


def normalize(value, family, reference, decision_at, domain=False):
    if value is None:
        return None
    if not numeric(value) or not numeric(decision_at):
        raise ValueError('NONFINITE_INPUT')
    if family == 'D':
        if not domain:
            return None
        if not 0 <= value <= 1:
            raise ValueError('DOMAIN_RANGE')
        return value
    if (not reference or reference['phase'] != 'DEV' or reference['available_at'] > decision_at
            or reference['trained_through'] > reference['available_at']):
        raise ValueError('REFERENCE_NOT_KNOWN')
    body = {k: v for k, v in reference.items() if k != 'sha256'}
    if reference.get('sha256') != digest(body):
        raise ValueError('REFERENCE_CHANGED')
    if family == 'Q':
        v = reference['values']
        return (bisect_left(v, value)+bisect_right(v, value))/(2*len(v))
    if family == 'R':
        return None if reference['mad'] == 0 else .5+math.atan((value-reference['median'])/(1.4826*reference['mad']))/math.pi
    raise ValueError('NORMALIZATION_FAMILY')


def independent_sample_plan(effect_sd=.25, family=20, alpha=.05, power=.8):
    """Normal paired-block reference planning, not observed effective sample size."""
    if not 0 < effect_sd or type(family) is not int or family < 1 or not 0 < alpha < 1 or not .5 < power < 1:
        raise ValueError('INVALID_POWER_PLAN')
    z = NormalDist().inv_cdf(1-alpha/(2*family))+NormalDist().inv_cdf(power)
    return math.ceil((z/effect_sd)**2)


def reject_lineage_overlap(groups):
    seen = set()
    for tokens in groups:
        tokens = set(tokens)
        if not tokens or seen & tokens:
            raise ValueError('SHARED_OR_MISSING_LINEAGE')
        seen.update(tokens)


def conditional_compare(rows, a, b, phase='DEV', repeats=1024, seed=12012):
    """Paired correlation delta within a single horizon/direction.

    Asset-specific week rotations preserve within-week serial ordering. Exchangeability
    remains an assumption; outputs are explicitly preparatory, never qualifying p.
    """
    if phase != 'DEV':
        raise ValueError('NEW_OOS_REQUIRES_FROZEN_UNSEEN_MANIFEST')
    if len(rows) != len(a) or len(a) != len(b) or not rows:
        raise ValueError('PAIR_IDENTITY')
    if len({r['direction'] for r in rows}) != 1 or next(iter({r['direction'] for r in rows})) not in (-1, 1):
        raise ValueError('MIXED_DIRECTION_POOL_FORBIDDEN')
    if len({r['horizon'] for r in rows}) != 1:
        raise ValueError('MIXED_HORIZON_POOL_FORBIDDEN')
    if type(repeats) is not int or not 16 <= repeats <= 4096:
        raise ValueError('RESAMPLING_LIMIT')
    identities = [(r['asset'], r['close']) for r in rows]
    if len(set(identities)) != len(rows):
        raise ValueError('DUPLICATE_EVENT')
    indices = [i for i in range(len(rows)) if numeric(a[i]) and numeric(b[i]) and numeric(rows[i]['outcome'])]
    groups = defaultdict(list)
    for i in indices:
        groups[rows[i]['asset']].append(i)
    bins = {}
    for asset, ids in groups.items():
        byweek = defaultdict(list)
        for i in ids:
            byweek[rows[i]['week']].append(i)
        # Keep only weeks with identical intraweek slots; do not silently align gaps.
        signatures = defaultdict(list)
        for week, ix in byweek.items():
            ordered = sorted(ix, key=lambda i: rows[i]['close'])
            signatures[tuple(rows[i]['slot'] for i in ordered)].append(ordered)
        for signature, weeks in signatures.items():
            if len(weeks) >= 3:
                bins[(asset, signature)] = weeks
    included = [i for weeks in bins.values() for ix in weeks for i in ix]
    def equal_asset_delta(x, y, target, assets):
        deltas = []
        for asset in sorted(set(assets)):
            ids = [i for i, v in enumerate(assets) if v == asset]
            ra = correlation([x[i] for i in ids], [target[i] for i in ids])
            rb = correlation([y[i] for i in ids], [target[i] for i in ids])
            if ra is not None and rb is not None:
                deltas.append(rb-ra)
        return sum(deltas)/len(deltas) if deltas else None
    delta = equal_asset_delta([a[i] for i in included], [b[i] for i in included],
                             [rows[i]['outcome'] for i in included], [rows[i]['asset'] for i in included])
    out = dict(status='DEV_PREPARATORY_ONLY', N_raw=len(rows), N_available=len(indices),
               N_aligned=len(included), N_asset_week_blocks=sum(len(w) for w in bins.values()),
               N_effective=None, N_REQUIRED_actual=None, qualification_p=None, delta=None,
               inference_assumption='WEEK_ROTATION_EXCHANGEABILITY_UNVERIFIED')
    if delta is None:
        return dict(out, status='INSUFFICIENT_OR_CONSTANT')
    rng, extreme = random.Random(seed), 0
    for _ in range(repeats):
        xx, yy, target, assets = [], [], [], []
        for (asset, signature), weeks in bins.items():
            offset = rng.randrange(len(weeks))
            for j, ix in enumerate(weeks):
                shifted = weeks[(j+offset) % len(weeks)]
                xx.extend(a[i] for i in ix)
                yy.extend(b[i] for i in ix)
                target.extend(rows[i]['outcome'] for i in shifted)
                assets.extend([asset]*len(ix))
        rotated = equal_asset_delta(xx, yy, target, assets)
        if rotated is not None and abs(rotated) >= abs(delta)-1e-15:
            extreme += 1
    return dict(out, delta=delta, diagnostic_rotation_p=(extreme+1)/(repeats+1), repeats=repeats)
