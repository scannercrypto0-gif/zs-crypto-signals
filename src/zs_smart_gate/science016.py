"""Frozen016 inference-instrument calibration; never OOS market evidence."""
import math
import random
from bisect import bisect_left,bisect_right

def prediction_gain(feature,return_bps,*,direction,scale_bps):
    if (type(direction)is not int or direction not in(1,-1)or
        any(type(x)not in(int,float)or not math.isfinite(x)for x in(feature,return_bps,scale_bps))or
        not 0<=feature<=1 or scale_bps<=0):raise ValueError('PREDICTION_LOSS_DOMAIN')
    target=(1+max(-1,min(1,direction*return_bps/scale_bps)))/2
    return (.5-target)**2-(feature-target)**2

def fit_ecdf(samples,*,phase):
    if phase!='DEV':raise ValueError('OOS_REFIT_FORBIDDEN')
    if not samples or any(type(x)not in(int,float)or not math.isfinite(x)for x in samples):raise ValueError('FINITE_DEV_REQUIRED')
    return tuple(sorted(samples))

def ecdf_value(value,frozen_dev):
    if type(value)not in(int,float)or not math.isfinite(value)or not frozen_dev:raise ValueError('FINITE_FEATURE_AND_FROZEN_DEV_REQUIRED')
    return (bisect_left(frozen_dev,value)+bisect_right(frozen_dev,value))/(2*len(frozen_dev))

def partition(event,*,freeze_at,dev_end,oos_start,admitted_hashes,previously_viewed_hashes):
    # Admission pins are supplied by independent source/clock review, not raw labels.
    if (any(type(x)not in(int,float)or not math.isfinite(x)for x in(freeze_at,dev_end,oos_start))or
        not freeze_at<dev_end<oos_start or oos_start-dev_end<7*86400+4*3600):
        raise ValueError('PURGE_AND_EMBARGO_REQUIRED')
    if (event.get('raw_sha256')not in admitted_hashes or event.get('raw_sha256')in previously_viewed_hashes or
        event.get('source_mode')!='NEW_AFTER_FREEZE_LIVE_RECEIPT' or
        event.get('causality')!='PROSPECTIVE_CAUSALITY_PASS_CANDIDATE'):
        return 'INELIGIBLE_OLD_VIEWED_OR_UNADMITTED_DATA'
    decision=event.get('decision_at')
    if type(decision)not in(int,float)or not math.isfinite(decision)or decision<=freeze_at:return 'INELIGIBLE_BEFORE_FREEZE'
    return 'DEV'if decision<=dev_end else 'OOS'if decision>=oos_start else'PURGED_EMBARGO'

def dependence_diagnostic(block_means):
    n=len(block_means)
    if any(type(x)not in(int,float)or not math.isfinite(x)for x in block_means):raise ValueError('FINITE_BLOCKS_REQUIRED')
    rho=None;ess=None
    if n>=8:
        mean=sum(block_means)/n;den=sum((x-mean)**2 for x in block_means)
        if den>0:
            rho=max(-.99,min(.99,sum((a-mean)*(b-mean)for a,b in zip(block_means[:-1],block_means[1:]))/den))
            ess=max(1,min(n,n*(1-rho)/(1+rho)))
    return dict(blocks=n,lag1_rho_descriptive=rho,N_effective_diagnostic_not_qualified=ess,
                N_effective_qualified=None,N_required_qualified=None,independence_proved=False)

def interval(gains,family=24,alpha=.05,independence_attested=False):
    if not gains or any(type(x)not in(int,float)or not math.isfinite(x)or not -1<=x<=1 for x in gains):
        raise ValueError('BOUNDED_INDEPENDENT_BLOCK_INPUT_REQUIRED')
    if type(family)is not int or family<1 or not 0<alpha<1:raise ValueError('INVALID_FAMILY_OR_ALPHA')
    n=len(gains);mean=sum(gains)/n;radius=math.sqrt(2*math.log(2*family/alpha)/n)
    return dict(mean=mean,lower=max(-1,mean-radius),upper=min(1,mean+radius),radius=radius,
        independent_blocks=n,N_effective=None,N_required=None,
        status='CONDITIONAL_INDEPENDENT_BOUND'if independence_attested else 'HOLD_UNPROVED_BLOCK_INDEPENDENCE')

def cost_scenario(return_bps,*,direction,fees_bps,slippage_bps,spread_bps):
    values=[return_bps,fees_bps,slippage_bps,spread_bps]
    if type(direction)is not int or direction not in(1,-1)or any(type(x)not in(int,float)or not math.isfinite(x)for x in values)or min(values[1:])<0:
        raise ValueError('INVALID_COST_SCENARIO')
    return dict(net_scenario_bps=direction*return_bps-fees_bps-slippage_bps-spread_bps,
                actual_execution_or_profitability_proved=False)

def winner_gate(*,lower_bound,independent_oos,clock_pass,liquidity_pass,cost_review_pass):
    if any(x is not True for x in (independent_oos,clock_pass,liquidity_pass,cost_review_pass)):
        return 'HOLD_NO_QUALIFIED_WINNER'
    if type(lower_bound)not in(int,float)or not math.isfinite(lower_bound):raise ValueError('FINITE_LOWER_BOUND_REQUIRED')
    return 'WINNER_CANDIDATE_REVIEW_REQUIRED'if lower_bound>0 else 'NO_WINNER_WITH_VALID_EVIDENCE'

def wilson(k,n):
    z=1.959963984540054;p=k/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d;width=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0,center-width),12),round(min(1,center+width),12)]

def calibrate(protocol):
    c=protocol['calibration'];rng=random.Random(c['seed']);family=c['family'];reps=c['replicates']
    cells=[]
    for n in c['blocks']:
        radius=interval([0.]*n,family)['radius']
        for rho in c['between_block_rho']:
            for effect in c['effects']:
                rejected=0
                for _ in range(reps):
                    latent=rng.gauss(0,1);sums=[0.]*family
                    for _ in range(n):
                        latent=rho*latent+math.sqrt(1-rho*rho)*rng.gauss(0,1)
                        common=1 if latent>=0 else -1
                        for arm in range(family):
                            independent=sum(1 if rng.random()>=.5 else -1 for _ in range(c['within_block_events_per_asset']))/c['within_block_events_per_asset']
                            # Family/asset dependence is preserved in common market block.
                            gain=effect+(1-abs(effect))*(.8*common+.2*independent)
                            sums[arm]+=gain
                    rejected+=any(total/n-radius>0 for total in sums)
                cells.append(dict(blocks=n,between_block_rho=rho,effect=effect,reps=reps,
                    familywise_rejection=round(rejected/reps,12),wilson95=wilson(rejected,reps),
                    N_events_market=0,synthetic_events_per_arm=n*c['within_block_events_per_asset']*c['assets'],
                    cross_asset_replication='SAME_BLOCK_VALUES_REPLICATED_BOTH_ASSETS_NOT_EXTRA_N',
                    N_effective_qualified=None,N_required_qualified=None,
                    assumption_violated=rho!=0,endpoint='TYPE_I'if effect==0 else 'POWER'))
    return dict(experiment=protocol['schema'],status='SYNTHETIC_INSTRUMENT_CALIBRATION_ONLY',cells=cells,
        OOS='OOS_WAITING_FOR_FUTURE_ELIGIBLE_DATA',market_events=0,winner=None,
        empirical_market_power_or_effectiveN_proved=False,
        interpretation='rho>0 violates the independent-block bound; event counts do not repair that violation')
