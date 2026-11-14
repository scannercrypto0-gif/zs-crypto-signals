"""Synthetic known-SD paired-normal reference and AR stress; not market evidence."""
import argparse
import json
import math
import random
from statistics import NormalDist
from zs_smart_gate.stage03_directional_study import independent_sample_plan


def simulate(repeats=4096, seed=12012):
    n = independent_sample_plan()
    critical = NormalDist().inv_cdf(1-.05/(2*20))
    rng, result = random.Random(seed), {}
    for rho in [0, .5]:
        for effect in [0, .25]:
            rejected = 0
            for _ in range(repeats):
                z = rng.gauss(0, 1)
                total = 0
                for _ in range(n):
                    z = rho*z+math.sqrt(1-rho*rho)*rng.gauss(0, 1)
                    total += effect+z
                rejected += abs(total/n*math.sqrt(n)) > critical
            result[f'AR{rho}:effect{effect}'] = dict(rejected=rejected, repeats=repeats,
                                                   rate=rejected/repeats)
    return dict(status='SYNTHETIC_REFERENCE_ONLY_NO_MARKET_ACCEPTANCE', seed=seed,
                independent_reference_blocks=n, known_population_sd=1, critical=critical,
                simulations=result, limitation='IID reference is not a calibrated paired-correlation-delta test; AR stress deliberately violates independence. No actual Neff or scientific GO inferred.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    args = p.parse_args()
    with open(args.output, 'x', encoding='utf8') as stream:
        json.dump(simulate(), stream, indent=2)
