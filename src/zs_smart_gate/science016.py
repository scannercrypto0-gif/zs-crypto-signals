"""Frozen016 inference-instrument calibration; never OOS market evidence."""
import math
import random

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
    if direction not in(1,-1)or any(type(x)not in(int,float)or not math.isfinite(x)for x in values)or min(values[1:])<0:
        raise ValueError('INVALID_COST_SCENARIO')
    return dict(net_scenario_bps=direction*return_bps-fees_bps-slippage_bps-spread_bps,
                actual_execution_or_profitability_proved=False)

def winner_gate(*,lower_bound,independent_oos,clock_pass,liquidity_pass,cost_review_pass):
    if any(x is not True for x in (independent_oos,clock_pass,liquidity_pass,cost_review_pass)):
        return 'HOLD_NO_QUALIFIED_WINNER'
    if not math.isfinite(lower_bound):raise ValueError('FINITE_LOWER_BOUND_REQUIRED')
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
