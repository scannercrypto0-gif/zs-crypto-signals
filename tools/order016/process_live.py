from pathlib import Path
import sys,json,hashlib,base64,time
T=Path(__file__).resolve().parent;W=T/'work';sys.path.insert(0,str(W/'src'))
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.integrated_research016 import evaluate
from zs_smart_gate.binance_live import is_spot_enabled
from zs_smart_gate.prospective_causality import receipt,assess
r=json.loads((T/'live-compatibility/report.json').read_bytes())
if r['status']!='COMPLETED_ONE_BATCH' or r['http_attempts']!=6:raise SystemExit('LIVE_BATCH_BLOCKED_NO_SECOND_ROUND')
wire=[base64.b64decode(x['body_base64'],validate=True)for x in r['responses']]
payload=[json.loads(x)for x in wire]
server_time=payload[0]['serverTime']
info={x['symbol']:x for x in payload[1]['symbols']}
tickers={x['symbol']:x for x in payload[2]};books={x['symbol']:x for x in payload[3]}
boundary=r['responses'][-1]['received_wall_ns']//1000000+1
computed=time.time_ns();decisions={};sources={}
for i,symbol in enumerate(['BTCUSDT','ETHUSDT'],4):
 received=r['responses'][i]['received_wall_ns']//1000000
 cutoff=min(received,server_time)
 rows=[x for x in payload[i]if int(x[6])+1<=cutoff]
 fixture=dict(symbol=symbol,rows=rows,received_ms=received,
       provenance=dict(mode='BOUNDED_COMPATIBILITY_REPLAY',wire_sha256=r['responses'][i]['sha256'],
         source_cutoff_server_time_ms=server_time,publisher_publication_proof='MISSING',
         interpretation='Recorded source boundary replay, not actual future decision or new eligible OOS'))
 raw=canonical_bytes(fixture)
 market=dict(received_at=r['responses'][3]['received_wall_ns']/1e9,bid=books[symbol]['bidPrice'],ask=books[symbol]['askPrice'],
       quote_volume_24h=tickers[symbol]['quoteVolume'],quote_asset=info[symbol]['quoteAsset'],
       spot_enabled=is_spot_enabled(info[symbol]),trading_status=info[symbol]['status'])
 decisions[symbol]=evaluate(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),decision_ms=boundary,
                  source_mode='BOUNDED_COMPATIBILITY_REPLAY',market=market)
 sources[symbol]=dict(raw_json=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),market=market,decision_ms=boundary)
events=[];by_hash={};anchor='350692bdb10f7b36a17c731cf5593e744a3e1a089a911141d5a28202f96541d2';prev=anchor
for i,(raw,meta)in enumerate(zip(wire,r['responses']),1):
 e=receipt(raw,source_event_id=meta['path']+json.dumps(meta['params'],sort_keys=True),seq=i,epoch='016-one-shot',previous=prev,
       received_wall=meta['received_wall_ns']/1e9,received_mono=meta['received_mono_ns'],closed_at=0.)
 events.append(e);by_hash[e['raw_sha256']]=raw;prev=e['digest']
actual_causality=assess(events,by_hash,anchor=anchor,decision_wall=time.time_ns()/1e9,decision_mono=time.monotonic_ns(),
       epoch='016-one-shot',source_mode='NEW_FUTURE_OBSERVATION',used_digests=[x['digest']for x in events])
result=dict(http_attempts=6,successful_responses=len(wire),weight_attempted=r['weight_attempted'],response_bytes=r['response_bytes'],
 replay_as_of_ms=boundary,actual_analysis_computed_at_ns=computed,replay_is_not_field_decision=True,
 decisions=decisions,collector_receipt_chain_diagnostic=actual_causality,
 prospective_study_observations=0,OOS_new_eligible_events=0,forward_collector_started=False,
 ledger_limit='Post-capture application chain bound to prepublished plan; not independent observation or WORM',
 source_epoch_note='Monotonic clock is shared by child processes on this Windows host; no cross-host comparison')
(T/'live-compatibility/replay-sources.json').write_bytes(canonical_bytes(sources))
(T/'live-compatibility/replay-decisions.json').write_bytes(canonical_bytes(result))
print(json.dumps({k:v for k,v in result.items()if k not in['decisions','collector_receipt_chain_diagnostic']}))
print(json.dumps({s:dict(status=d['status'],scanner_status=(d['scanner_candidate']or{}).get('status'),reasons=d['reasons'],spread=d['liquidity']['spread_bps'])for s,d in decisions.items()}))
