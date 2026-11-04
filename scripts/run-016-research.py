"""Reproduce016 frozen science calibration and archive source-to-decision path."""
import argparse,hashlib,json
from pathlib import Path
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.integrated_research016 import evaluate
from zs_smart_gate.science016 import calibrate,cost_scenario
from zs_smart_gate.prospective_causality import forward_gate

def run(fixtures,output,code_sha):
    root=Path(fixtures);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    raw_protocol=Path('research/stage03-016/protocol-016.json').read_bytes()
    protocol=json.loads(raw_protocol);decisions={}
    for symbol in ['BTCUSDT','ETHUSDT']:
        raw=(root/(symbol+'.json')).read_bytes();payload=json.loads(raw)
        decision=evaluate(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),decision_ms=payload['received_ms']+500)
        if decision['score']is not None or decision['publishable']:raise ValueError('PRODUCTION_STATE_FORBIDDEN')
        decisions[symbol]=decision
    # The run must be invoked only after code/protocol have been committed.
    calibration=calibrate(protocol)
    costs=[cost_scenario(20,direction=direction,fees_bps=cost/2,slippage_bps=cost/2,spread_bps=2)
           for direction in [1,-1]for cost in protocol['costs']['assumed_roundtrip_bps']]
    outputs={'decisions.json':decisions,'calibration.json':calibration,'cost-scenarios.json':costs,
             'forward-readiness.json':forward_gate(protocol_pinned=True)}
    for name,data in outputs.items():(output/name).write_bytes(canonical_bytes(data))
    report=dict(code_sha=code_sha,protocol_sha256=hashlib.sha256(raw_protocol).hexdigest(),
         freeze_commit='77ea1940765d2f6874330f075b3f34dcb1d74caf',
         files={name:hashlib.sha256(canonical_bytes(data)).hexdigest()for name,data in outputs.items()},
         new_market_OOS_events=0,forward_live_capture_events=0,source_mode='HISTORICAL_ARCHIVE_ENGINEERING_REPLAY',
         OOS='OOS_WAITING_FOR_FUTURE_ELIGIBLE_DATA',scientific_winner=None)
    (output/'run-manifest.json').write_bytes(canonical_bytes(report));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixtures',required=True);p.add_argument('--output',required=True);p.add_argument('--code-sha',required=True)
    a=p.parse_args();print(json.dumps(run(a.fixtures,a.output,a.code_sha),sort_keys=True))
