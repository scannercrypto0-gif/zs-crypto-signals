"""013 new bounded paired-loss estimand, conditional finite-sample interval.

Calendar weeks, not asset-week rows, are the units. Independence between weeks
is NOT established by this module; absent external justification blocks science.
No rotation/exchangeability, OOS refit, or unbounded-return normal approximation.
"""
import math
from collections import defaultdict


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def paired_gain(a, b, outcome, scale):
    if any(x is None for x in (a, b, outcome)):
        return None
    if not all(finite(x) for x in (a, b, outcome, scale)) or not 0 <= a <= 1 or not 0 <= b <= 1 or scale <= 0:
        raise ValueError('PAIRED_LOSS_DOMAIN')
    y = min(1, max(-1, outcome/scale))
    # Fixed candidate prediction mapping, NOT a fitted/validated return forecast.
    return ((2*a-1-y)**2-(2*b-1-y)**2)/4


def bounded_interval(blocks, family=20, alpha=.05, independence_attested=False):
    if not blocks or not all(finite(x) and -1 <= x <= 1 for x in blocks):
        raise ValueError('INVALID_BOUNDED_BLOCKS')
    if type(family) is not int or family < 1 or not finite(alpha) or not 0 < alpha < 1:
        raise ValueError('INVALID_FAMILY')
    n = len(blocks)
    mean = sum(blocks)/n
    radius = math.sqrt(2*math.log(2*family/alpha)/n)
    return dict(mean=mean, lower=max(-1, mean-radius), upper=min(1, mean+radius),
                radius=radius, N_calendar_week_blocks=n, N_effective=None,
                status='CONDITIONAL_BOUND_ONLY' if independence_attested else 'BLOCKED_UNPROVED_BETWEEN_WEEK_INDEPENDENCE',
                scientific_pass=False, qualification_p=None,
                assumption='INDEPENDENT_BOUNDED_WEEK_UNITS; arbitrary within-week/asset dependence permitted')


def weekly_diagnostic(rows, a, b, scale, minimum_coverage=.9):
    if not rows or len(rows) != len(a) or len(a) != len(b):
        raise ValueError('PAIR_COUNT')
    if len({r['direction'] for r in rows}) != 1 or rows[0]['direction'] not in (-1, 1) or len({r['horizon'] for r in rows}) != 1:
        raise ValueError('DIRECTION_HORIZON_POOL_FORBIDDEN')
    if not finite(minimum_coverage) or not 0 < minimum_coverage <= 1:
        raise ValueError('INVALID_COVERAGE')
    events, cells = set(), defaultdict(list)
    for r, x, y in zip(rows, a, b):
        identity = r['asset'], r['close']
        if identity in events:
            raise ValueError('DUPLICATE_EVENT')
        events.add(identity)
        cells[r['week'], r['asset']].append((r, paired_gain(x, y, r['outcome'], scale)))
    assets = {r['asset'] for r in rows}
    step = 1800 if rows[0]['horizon'] == 'INTRADAY' else 14400
    expected = 604800//step
    week_values, audit = {}, {}
    for week in sorted({r['week'] for r in rows}):
        means, reasons = [], []
        for asset in sorted(assets):
            cell = cells[week, asset]
            # Parent close at week boundary belongs to previous event-close week;
            # use exact predefined close slots from 0..week-step, as frozen records do.
            slots = {r['slot'] for r, _ in cell}
            good = [v for _, v in cell if v is not None]
            if len(cell) != expected or slots != set(range(0, 604800, step)):
                reasons.append(asset+':INCOMPLETE_CALENDAR_WEEK')
            elif len(good)/expected < minimum_coverage:
                reasons.append(asset+':PAIRED_INPUT_COVERAGE')
            else:
                means.append(sum(good)/len(good))
        audit[str(week)] = dict(reasons=reasons, assets=len(means))
        if not reasons and len(means) == len(assets):
            week_values[str(week)] = sum(means)/len(means)
    result = dict(N_events=len(rows), N_paired_available=sum(v is not None for cell in cells.values() for _, v in cell),
                  N_calendar_weeks=len(week_values), week_audit=audit, weekly_values=week_values,
                  scale=scale, forecast_mapping='2*normalized_feature-1_FIXED_CANDIDATE',
                  missingness='complete-case pairs conditional on >=90% perasset/week; not unbiased full-event claim',
                  N_effective=None, N_required_actual=None, winner=None)
    result['interval'] = bounded_interval(list(week_values.values())) if week_values else None
    result['status'] = 'DEV_NEW_ESTIMAND_NOT_QUALIFIED' if week_values else 'INSUFFICIENT_COMPLETE_WEEKS'
    return result
