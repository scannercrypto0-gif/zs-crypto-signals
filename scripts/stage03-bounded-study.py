"""013 new preregistered DEV estimand and dependent synthetic calibration; no OOS."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from zs_smart_gate.stage03_bounded_inference import weekly_diagnostic, paired_gain, bounded_interval


def wilson(k, n):
    p, z = k/n, 1.96
    d = 1+z*z/n
    middle = (p+z*z/(2*n))/d
    width = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0, middle-width), min(1, middle+width)]


def calibrate(protocol):
    conf = protocol['simulation']
    rng = random.Random(conf['seed'])
    cells = {}
    for n in conf['K']:
        radius = bounded_interval([0]*n)['radius']
        for rho in conf['within_episode_AR']:
            for scenario in ['INDEPENDENT_NORMAL', 'INDEPENDENT_T3', 'SHARED_FACTOR_VIOLATES_INDEPENDENCE']:
                counts = {str(e): dict(typeI_or_power=0, covered=0) for e in conf['effects']}
                for _ in range(conf['replicates_per_cell']):
                    common = rng.gauss(0, 1)
                    means = []
                    for _ in range(n):
                        state, total = rng.gauss(0, 1), 0
                        for _ in range(conf['within_episode_points']):
                            noise = rng.gauss(0, 1)
                            if scenario == 'INDEPENDENT_T3':
                                noise /= math.sqrt(sum(rng.gauss(0, 1)**2 for _ in range(3))/3)
                            state = rho*state+math.sqrt(1-rho*rho)*noise
                            v = state if scenario != 'SHARED_FACTOR_VIOLATES_INDEPENDENCE' else math.sqrt(.9)*common+math.sqrt(.1)*state
                            total += 1 if v > 0 else -1
                        means.append(total/conf['within_episode_points'])
                    mean = sum(means)/n
                    for effect in conf['effects']:
                        # Symmetry gives E[sign(state)]=0 exactly, even with heavy tails.
                        # Thus bounded observations have true mean=effect, without clipping bias.
                        estimate = effect+(1-abs(effect))*.5*mean
                        counts[str(effect)]['typeI_or_power'] += abs(estimate) > radius
                        counts[str(effect)]['covered'] += abs(estimate-effect) <= radius
                for effect, count in counts.items():
                    reps = conf['replicates_per_cell']
                    cells[f'K{n}:rho{rho}:{scenario}:effect{effect}'] = dict(
                        K=n, rho=rho, scenario=scenario, effect=float(effect), repeats=reps,
                        rejection=count['typeI_or_power']/reps, coverage=count['covered']/reps,
                        rejection_Wilson95=wilson(count['typeI_or_power'], reps),
                        independent_reference_assumption=scenario != 'SHARED_FACTOR_VIOLATES_INDEPENDENCE')
                print(json.dumps(dict(K=n, rho=rho, scenario=scenario)), flush=True)
    return dict(status='CONDITIONAL_METHOD_CALIBRATION_NOT_MARKET_CERTIFICATION', cells=cells,
                actual_effective_sample_size=None, actual_required_sample_size=None,
                familywise_claim='Analytic union bound requires bounded independent week units; no joint market FWER estimated')


def dev(frozen):
    # The immutable 010 feature dependency remains external to this PR.
    import zs_smart_gate
    code = frozen/'frozen-code'/'src'/'zs_smart_gate'
    pins = {'stage03_science_expanded.py':'610208ff76184204b1dc1bd6bc752fca032cf8efd3b389ffa8e612759915b1bf',
            'stage03_science_pilot.py':'8d59f5a5ddc873a2d14fd6fe767d237ef68dd7f61561c5a0bf7f4fc532593de4'}
    for name, h in pins.items():
        if hashlib.sha256((code/name).read_bytes()).hexdigest() != h:
            raise ValueError('FROZEN_FEATURE_CHANGED')
    zs_smart_gate.__path__.append(str(code))
    from zs_smart_gate.stage03_science_expanded import load_archives, build_records, normalized, semantic_arms
    manifest = json.loads((frozen/'manifest.json').read_bytes())
    data = load_archives(frozen/'batch-B', manifest)
    records, audit = build_records(data, 'DEV')
    model_bytes = (frozen/'dev-models.json').read_bytes()
    if hashlib.sha256(model_bytes).hexdigest() != json.loads((frozen/'dev-freeze.json').read_bytes())['models_sha256']:
        raise ValueError('FROZEN_REFERENCE_CHANGED')
    models, result = json.loads(model_bytes), {}
    for horizon in ['INTRADAY', 'SWING']:
        for direction in [-1, 1]:
            rows = [r for r in records if r['horizon'] == horizon and r['direction'] == direction]
            arms = {}
            if horizon == 'INTRADAY':
                q, robust, domain = [[normalized(r, 'I4', models, family) for r in rows] for family in ['Q','R','D']]
                arms.update(I4_QvsR=(q,robust), I4_QvsD=(q,domain), I4_RvsD=(robust,domain))
                for key in ['V_BASE','V_QUOTE']:
                    vol = [normalized(r,key,models,'Q') for r in rows]
                    arms['I4_AvsB_'+key] = domain, [(a+v)/2 if a is not None and v is not None else None for a,v in zip(domain,vol)]
                semantics, scale = ['I2'], .01
            else:
                semantics, scale = ['S3','S4'], .05
            for group in semantics:
                pairs = [semantic_arms(r,models,group) for r in rows]
                arms[group+'_AvsB'] = [v[0] for v in pairs], [v[1] for v in pairs]
            for name,(a,b) in arms.items():
                value = weekly_diagnostic(rows,a,b,scale)
                strata = defaultdict(list)
                for r,x,y in zip(rows,a,b):
                    g = paired_gain(x,y,r['outcome'],scale)
                    if g is not None:
                        strata[(r['asset'],r['setup'],r['regime'])].append(g)
                value['descriptive_strata'] = {':'.join(k):dict(N=len(v),mean=sum(v)/len(v),inference='NONE') for k,v in strata.items()}
                result[f'{horizon}:{direction}:{name}'] = value
    return dict(status='DEV_NEW_QUESTION_NO_QUALIFIED_WINNER', comparisons=result, quality=audit,
                family=20,reserved_unavailable_liquidity=4,OOS='PENDING',winner=None,
                N_effective=None,N_required_actual=None,PIT='FAIL_HOLD')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--protocol',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--mode',choices=['DEV','SIMULATION'],required=True)
    p.add_argument('--frozen')
    args = p.parse_args()
    output = Path(args.output).resolve()
    if output.drive.upper() != 'D:':
        raise SystemExit('PRIVATE_D_REQUIRED')
    protocol_bytes = Path(args.protocol).read_bytes()
    protocol = json.loads(protocol_bytes)
    result = dev(Path(args.frozen).resolve()) if args.mode == 'DEV' else calibrate(protocol)
    result.update(protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with output.open('x',encoding='utf8') as stream:
        json.dump(result,stream,indent=2)
