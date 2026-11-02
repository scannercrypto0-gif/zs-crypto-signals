"""010 private retrospective diagnostics; no network, score or trading.

Run DEV first; freeze its diagnostics/normalizers, then OOS exactly once.
Historical integrity qualification is limited and does not establish PIT.
"""
import argparse,csv,io,json,hashlib,zipfile,random
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zs_smart_gate.stage03_science_pilot import (ECDF,child_features,relative_volume,
    split_admissible,fixed_outcome,correlation,planned_independent_clusters)

parser=argparse.ArgumentParser()
parser.add_argument('--phase',choices=('DEV','OOS'),required=True)
parser.add_argument('--root',required=True)
args=parser.parse_args();root=Path(args.root).resolve(strict=True)
if root.drive.upper()!='D:':raise SystemExit('PRIVATE_D_REQUIRED')
manifest=json.loads((root/'manifest.json').read_text())
phase=args.phase
output=root/(phase.lower()+'-diagnostics.json')
if output.exists():raise SystemExit('IMMUTABLE_RESULT_EXISTS')
boundary=datetime(2025,1,2,tzinfo=timezone.utc);horizon=timedelta(hours=1)
rows=[]
for symbol in ('BTCUSDT','ETHUSDT'):
    bars=[]
    for day in ('2025-01-01','2025-01-02'):
        name=f'{symbol}-5m-{day}.zip';raw=(root/'batch-A'/name).read_bytes()
        expected=manifest['dataset'][name]
        if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('DATA_CHANGED')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            data=list(csv.reader(io.TextIOWrapper(z.open(name[:-4]+'.csv'),encoding='utf-8')))
        for r in data:
            bars.append((int(r[0]),*[float(r[k]) for k in (1,2,3,4,5,7)]))
    if len(bars)!=576 or any(bars[i][0]-bars[i-1][0]!=300000000 for i in range(1,len(bars))):raise SystemExit('DATA_GAP')
    for i in range(23,len(bars)-14,6):
        close=datetime.fromtimestamp(bars[i][0]/1000000,tz=timezone.utc)+timedelta(minutes=5)
        decision=close+timedelta(seconds=60)
        # First full 5m open strictly after decision = close+5m.
        entry_index=i+2;end_index=entry_index+11
        end=datetime.fromtimestamp(bars[end_index][0]/1000000,tz=timezone.utc)+timedelta(minutes=5)
        if not split_admissible(decision,end,phase=phase,boundary=boundary,horizon=horizon):continue
        children=[b[1:] for b in bars[i-5:i+1]]
        for direction in (-1,1):
            f=child_features(children,direction)
            prior=direction*(bars[i-6][4]-bars[i-11][1])
            current=direction*(bars[i][4]-bars[i-5][1])
            setup='EARLY' if prior==0 else 'CONTINUATION' if prior>0 and current>0 else 'REVERSAL' if prior<0 and current>0 else 'NEGATIVE'
            rows.append({'asset':symbol,'close':close.isoformat(),'direction':direction,'setup':setup,
              'features':{**f,'rvol_base':relative_volume(bars[i][5],[b[5] for b in bars[i-20:i]]),
               'rvol_quote':relative_volume(bars[i][6],[b[6] for b in bars[i-20:i]])},
              'outcome':fixed_outcome(bars[entry_index][1],bars[end_index][4],direction)})

if phase=='DEV':
    fits={}
    for direction in (-1,1):
        selected=[r for r in rows if r['direction']==direction]
        fits[str(direction)]={key:ECDF.fit([r['features'][key] for r in selected if r['features'][key] is not None],phase='DEV').values for key in ('net_path','rvol_base','rvol_quote')}
else:
    raw=(root/'dev-diagnostics.json').read_bytes();freeze=json.loads((root/'dev-freeze.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=freeze['dev_result_sha256']:raise SystemExit('DEV_FREEZE_CHANGED')
    fits=json.loads(raw)['fits']

summary=[]
for direction in (-1,1):
    selected=[r for r in rows if r['direction']==direction]
    mappings={k:ECDF(tuple(v)) for k,v in fits[str(direction)].items()}
    arms={k:[] for k in ('I2_A','I2_B','I4_A','I4_B_BASE','I4_B_QUOTE')};ys=[]
    for r in selected:
        f=r['features'];a=mappings['net_path'].apply(f['net_path'])
        if any(f[k] is None for k in f) or a is None:continue
        arms['I2_A'].append(a);arms['I2_B'].append((a+f['retention']+f['consistency'])/3)
        arms['I4_A'].append(f['half_quote_share'])
        arms['I4_B_BASE'].append((f['half_quote_share']+mappings['rvol_base'].apply(f['rvol_base']))/2)
        arms['I4_B_QUOTE'].append((f['half_quote_share']+mappings['rvol_quote'].apply(f['rvol_quote']))/2)
        ys.append(r['outcome'])
    rng=random.Random(42);shuffled=ys[:];rng.shuffle(shuffled)
    summary.append({'direction':direction,'N_common_support':len(ys),'correlations':{k:correlation(v,ys) for k,v in arms.items()},
        'permuted_label_control':{k:correlation(v,shuffled) for k,v in arms.items()},
        'collinearity_I2A_I4A':correlation(arms['I2_A'],arms['I4_A']),
        'by_asset_setup_counts':{asset:{setup:sum(r['asset']==asset and r['setup']==setup for r in selected) for setup in ('EARLY','CONTINUATION','REVERSAL','NEGATIVE')} for asset in ('BTCUSDT','ETHUSDT')},
        'intervals_pvalues':None,'inference':'INSUFFICIENT_DAY_BLOCKS_NO_WINNER'})
clusters={(r['asset'],r['close']) for r in rows}
dayblocks={(r['asset'],r['close'][:10]) for r in rows}
result={'phase':phase,'protocol':'010-PILOT-1','execution':'RETROSPECTIVE_DESCRIPTIVE_ONLY_NOT_PIT',
 'manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),'N_raw':len(rows),'N_event_clusters':len(clusters),
 'N_asset_day_blocks':len(dayblocks),'N_effective':None,'N_REQUIRED_actual':None,
 'planning_independent_clusters':planned_independent_clusters(),'fits':fits,'summary':summary,
 'winner':None,'OOS_qualification':'NOT_ESTABLISHED','SCORE_UNAVAILABLE':True,
 'missing_groups':['I6','S6','S4_weekly_context','S1_confirmed_structure'],
 'full_strategy_DEV_OOS':'BLOCKED_PIT_AND_MISSING_INPUTS','FORWARD':'PENDING_INDEPENDENT_TIME_AND_FUTURE_ACCRUAL'}
with output.open('x') as f:json.dump(result,f,indent=2)
if phase=='DEV':
    with (root/'dev-freeze.json').open('x') as f:json.dump({'dev_result_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
      'selection':'A_BASELINE_FROZEN_FOR_DIAGNOSTIC_ONLY_NO_WINNER','frozen_at':datetime.now(timezone.utc).isoformat()},f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('fits','summary')},indent=2))
