"""010-PILOT-2A bounded private historical research. No network/scheduler.

DEV and OOS are immutable separate runs. Qualified V2/PIT/Forward stay blocked.
"""
import argparse,hashlib,json,math
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from zs_smart_gate.stage03_science_pilot import correlation,planned_independent_clusters
from zs_smart_gate.stage03_science_expanded import (VERSION,DOMAIN,load_archives,build_records,
    fit_models,normalized,semantic_arms,compare,holm,forward_admission)

parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('DEV','OOS'),required=True)
parser.add_argument('--root',required=True);args=parser.parse_args()
root=Path(args.root).resolve(strict=True)
if root.drive.upper()!='D:':raise SystemExit('PRIVATE_D_REQUIRED')
manifest_bytes=(root/'manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
protocol_bytes=(root/'protocol-2A.json').read_bytes()
if hashlib.sha256(protocol_bytes).hexdigest()!=manifest['protocol_sha256']:raise SystemExit('PROTOCOL_CHANGED')
if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=manifest['runner_sha256']:raise SystemExit('RUNNER_CHANGED')
phase=args.phase;output=root/(phase.lower()+'-results.json')
if output.exists():raise SystemExit('IMMUTABLE_RESULT_EXISTS')
data=load_archives(root/'batch-B',manifest)
records,audit=build_records(data,phase)
if phase=='DEV':models=fit_models(records,'DEV')
else:
    freeze=json.loads((root/'dev-freeze.json').read_text())
    if freeze['dev_sha256']!=hashlib.sha256((root/'dev-results.json').read_bytes()).hexdigest():raise SystemExit('DEV_RESULT_CHANGED')
    raw=(root/'dev-models.json').read_bytes()
    if freeze['models_sha256']!=hashlib.sha256(raw).hexdigest():raise SystemExit('DEV_MODEL_CHANGED')
    models=json.loads(raw)

comparisons={};strata={};coverage={};cohorts={};primary={}
for horizon,groups in [('INTRADAY',[f'I{i}' for i in range(1,7)]),('SWING',[f'S{i}' for i in range(1,7)])]:
    subset=[r for r in records if r['horizon']==horizon]
    cohorts[horizon]={':'.join(map(str,k)):v for k,v in Counter((r['asset'],r['direction'],r['setup'],r['regime']) for r in subset).items()}
    variants={}
    for group in groups:
        variants[group]={family:[normalized(r,group,models,family) for r in subset] for family in ('Q','R','D')}
        primary[group]=variants[group]['D' if group in DOMAIN else 'Q']
        coverage[group]={'total_rows':len(subset),'available_primary':sum(v is not None for v in primary[group]),'missing':sum(v is None for v in primary[group])}
        for a,b in [('Q','R')]+([('Q','D'),('R','D')] if group in DOMAIN else []):
            key=group+'_'+a+'_vs_'+b
            comparisons[key]=compare(subset,variants[group][a],variants[group][b])
            print(json.dumps({'phase':phase,'comparison':key,'status':comparisons[key]['status']}),flush=True)
        bins=defaultdict(list)
        for i,r in enumerate(subset):bins[(r['asset'],r['direction'],r['setup'],r['regime'])].append(i)
        strata[group]={':'.join(map(str,k)):{'N':len(indices),
          'N_available':sum(primary[group][i] is not None for i in indices),
          'descriptive_correlation':correlation([primary[group][i] for i in indices if primary[group][i] is not None],[subset[i]['outcome'] for i in indices if primary[group][i] is not None]),
          'inference':'DESCRIPTIVE_ONLY_NO_STRATUM_PVALUE'} for k,indices in bins.items()}
    for key in (('I2','I4') if horizon=='INTRADAY' else ('S3','S4')):
        if key in ('I2','S3'):
            arms=[semantic_arms(r,models,key) for r in subset]
            a=[x[0] for x in arms];b=[x[1] for x in arms]
            extras={'B':b,'ADD_RETENTION_ONLY':[(v+r['child']['retention'])/2 if v is not None and r['child']['retention'] is not None else None for v,r in zip(a,subset)],
              'ADD_CONSISTENCY_ONLY':[(v+r['child']['consistency'])/2 if v is not None and r['child']['consistency'] is not None else None for v,r in zip(a,subset)]}
        elif key=='I4':
            a=primary[key];extras={label:[(v+normalized(r,vol,models,'Q'))/2 if v is not None and normalized(r,vol,models,'Q') is not None else None for v,r in zip(a,subset)] for label,vol in [('B_BASE','V_BASE'),('B_QUOTE','V_QUOTE')]}
        else:
            arms=[semantic_arms(r,models,key) for r in subset];a=[x[0] for x in arms];extras={'B':[x[1] for x in arms]}
        for label,b in extras.items():
            name=key+'_A_vs_'+label;comparisons[name]=compare(subset,a,b)
            print(json.dumps({'phase':phase,'comparison':name,'status':comparisons[name]['status']}),flush=True)

adjusted=holm({key:value['p'] for key,value in comparisons.items()},40)
for key,value in comparisons.items():value['holm40_p_diagnostic']=adjusted[key]
clusters={(r['asset'],r['horizon'],r['close']) for r in records}
counts={h:{'N_raw':sum(r['horizon']==h for r in records),
  'N_event_clusters':sum(c[1]==h for c in clusters),
  'N_asset_day_blocks':len({(r['asset'],r['close']//86400) for r in records if r['horizon']==h})} for h in ('INTRADAY','SWING')}
missing_liquidity=all(v['available_primary']==0 for k,v in coverage.items() if k in ('I6','S6'))
if not missing_liquidity:raise SystemExit('HISTORICAL_LIQUIDITY_MUST_NOT_BE_INVENTED')
result={'version':VERSION,'phase':phase,'scope':'RETROSPECTIVE_DIAGNOSTICS_NOT_PIT_OR_EXECUTABLE_STRATEGY',
 'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'counts':counts,'quality_audit':audit,
 'coverage':coverage,'cohort_counts':cohorts,'strata':strata,'comparisons':comparisons,
 'primary_family_size':40,'actual_comparisons':len(comparisons),
 'planning_independent_clusters':planned_independent_clusters(comparisons=40),
 'N_effective_qualified':None,'N_REQUIRED_actual':None,'winner':None,
 'selection':'A_BASELINE_DIAGNOSTIC_ONLY_NO_QUALIFIED_SELECTION','PIT':'FAIL_HOLD','full_V2':'UNAVAILABLE_I6_S6',
 'source_publication_at':None,'independent_historical_bid_ask':None,
 'forward_check':forward_admission(now=1000,close=900,publication_attested=False,clock_age=0,uncertainty=.1,pinned=True,frozen=False,evidence_approved=False),
 'Forward':'NOT_STARTED_PUBLICATION_CLOCK_EVIDENCE_AND_FUTURE_ACCRUAL_REQUIRED',
 'scientific_acceptance':'PENDING_INDEPENDENT_REVIEW_NOT_SELF_APPROVED'}
with output.open('x') as f:json.dump(result,f,indent=2)
if phase=='DEV':
    with (root/'dev-models.json').open('x') as f:json.dump(models,f,sort_keys=True)
    frozen={'version':VERSION,'code_sha':manifest['code_sha'],'dev_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
      'models_sha256':hashlib.sha256((root/'dev-models.json').read_bytes()).hexdigest(),
      'selection':'NO_QUALIFIED_WINNER_A_BASELINE_FROZEN','utc':datetime.now(timezone.utc).isoformat()}
    with (root/'dev-freeze.json').open('x') as f:json.dump(frozen,f,indent=2)
print(json.dumps({'phase':phase,'counts':counts,'coverage':coverage,'comparisons':len(comparisons),'full_V2':result['full_V2'],'PIT':result['PIT']}),flush=True)

