"""012 preparatory DEV only; explicit pinned external frozen feature dependency.

Never consumes old OOS rows. Prior 010 code is loaded only from the private frozen
snapshot, not included or transplanted into this PR. No network.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--frozen', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--protocol', required=True)
    args = p.parse_args()
    frozen, output = Path(args.frozen).resolve(), Path(args.output).resolve()
    if frozen.drive.upper() != 'D:' or output.drive.upper() != 'D:':
        raise SystemExit('PRIVATE_D_REQUIRED')
    protocol_bytes = Path(args.protocol).read_bytes()
    protocol = json.loads(protocol_bytes)
    code = frozen/'frozen-code'/'src'
    for name, key in [('stage03_science_expanded.py', 'feature_module_sha256'),
                      ('stage03_science_pilot.py', 'feature_helper_sha256')]:
        raw = (code/'zs_smart_gate'/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != protocol[key]:
            raise SystemExit('FROZEN_FEATURE_CODE_CHANGED')
    # Extend package search only for this standalone offline process.
    import zs_smart_gate
    zs_smart_gate.__path__.append(str(code/'zs_smart_gate'))
    from zs_smart_gate.stage03_science_expanded import load_archives, build_records, normalized, semantic_arms
    from zs_smart_gate.stage03_directional_study import conditional_compare, independent_sample_plan
    manifest = json.loads((frozen/'manifest.json').read_bytes())
    if manifest['code_sha'] != protocol['frozen_feature_code']:
        raise SystemExit('FROZEN_FEATURE_VERSION_MISMATCH')
    if hashlib.sha256((frozen/'dataset-index.json').read_bytes()).hexdigest() != protocol['raw_index_sha256']:
        raise SystemExit('FROZEN_DATA_INDEX_CHANGED')
    data = load_archives(frozen/'batch-B', manifest)
    records, quality = build_records(data, 'DEV')
    model_bytes = (frozen/'dev-models.json').read_bytes()
    freeze = json.loads((frozen/'dev-freeze.json').read_bytes())
    if hashlib.sha256(model_bytes).hexdigest() != freeze['models_sha256']:
        raise SystemExit('FROZEN_DEV_MODEL_CHANGED')
    models = json.loads(model_bytes)
    results = {}
    for horizon in ['INTRADAY', 'SWING']:
        for direction in [-1, 1]:
            rows = [r for r in records if r['horizon'] == horizon and r['direction'] == direction]
            arms = {}
            if horizon == 'INTRADAY':
                q = [normalized(r, 'I4', models, 'Q') for r in rows]
                robust = [normalized(r, 'I4', models, 'R') for r in rows]
                domain = [normalized(r, 'I4', models, 'D') for r in rows]
                arms.update(I4_QvsR=(q, robust), I4_QvsD=(q, domain), I4_RvsD=(robust, domain))
                for key in ['V_BASE', 'V_QUOTE']:
                    vol = [normalized(r, key, models, 'Q') for r in rows]
                    b = [(a+v)/2 if a is not None and v is not None else None for a, v in zip(domain, vol)]
                    arms['I4_AvsB_'+key] = domain, b
                semantic = ['I2']
            else:
                semantic = ['S3', 'S4']
            for group in semantic:
                pairs = [semantic_arms(r, models, group) for r in rows]
                arms[group+'_AvsB'] = [v[0] for v in pairs], [v[1] for v in pairs]
            for name, (a, b) in arms.items():
                key = horizon+':'+str(direction)+':'+name
                results[key] = conditional_compare(rows, a, b, repeats=1024)
                print(json.dumps({'comparison': key, 'status': results[key]['status']}), flush=True)
    result = dict(version=protocol['version'], protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  original_models_sha256=hashlib.sha256(model_bytes).hexdigest(), quality=quality,
                  comparisons=results, family_cap=20, reserved_liquidity_comparisons=4,
                  normal_reference_independent_blocks=independent_sample_plan(),
                  N_effective=None, N_REQUIRED_actual=None, OOS='PENDING_NO_QUALIFIED_UNSEEN_DATA',
                  PIT='FAIL_HOLD', full_V2='UNAVAILABLE', winner=None,
                  note='DEV diagnostics only, unverified rotation exchangeability, no qualifying p or scientific selection')
    with output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
