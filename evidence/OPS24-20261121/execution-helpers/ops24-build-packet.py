"""Build factual OPS24 handoff from original bounded capture and Windows receipts."""
from pathlib import Path
import json,hashlib
base=Path('D:/ZS-SMART-GATE/validation')
out=base/'OPS24-20261121-evidence-source/evidence/OPS24-20261121'
live=base/'OPS24-20261121-full-market'
result=json.loads((live/'result.json').read_bytes()) if (live/'result.json').exists() else {}
test=json.loads((base/'OPS24-20261121-keepalive-fixed-evidence/acceptance.json').read_bytes())
repeat=json.loads((base/'OPS24-20261121-github-final-reproduction/acceptance.json').read_bytes())
clocks=[json.loads(p.read_bytes()) for p in live.glob('clock-*.private.json')]
packet=dict(schema='ZS_P0_OPS_FULL_MARKET_24H_ENGINEERING_PACKET_001',implementation_pr=76,governance_pr=75,
 head=test['head'],tree=test['tree'],windows=test,github_reproduction=repeat,
 matrices=dict(ENGINEERING='PASS_TARGETED_WINDOWS_41_REVIEW_PENDING',
 FULL_MARKET=result.get('coverage','BLOCKED_NO_RESULT'),STABILITY_24H='NOT_STARTED_NOT_PROVEN',
 QV1='SCIENCE_NOT_APPROVED',TELEGRAM_E2E='NOT_EXECUTED_NO_NEW_PERMISSION',SQL='DEFERRED',TRADING='NONE'),
 full_market={k:result.get(k) for k in ('head','tree','transport_profile','boundary_ms','inventory_id','discovered','eligible','validated','missing','decision_at','stop','budget','metrics')},
 operational_clock=dict(profile='WINDOWS_STATUS_PROTECTED_REGISTRY_V1',witnesses=len(clocks),
 statuses=[r['assessment']['status'] for r in clocks],
 max_sync_age_seconds=max((r['assessment']['sync_age_s'] for r in clocks),default=None),
 max_conditional_uncertainty_seconds=max((r['assessment']['conditional_uncertainty_s'] for r in clocks),default=None),
 original_rpc_failures_retained=True,independent_cryptographic_utc='NOT_PROVEN',independent_profile_review='PENDING_PM'),
 live_effects=dict(telegram_calls=0,sql_writes=0,trading_orders=0,source_scope='ONE_BOUNDED_PUBLIC_SPOT_SNAPSHOT',discovery_prior_calls=3),
 deployment=dict(installed_runtime_unchanged=True,task_registered=False,task_enabled=False,soak_started=False,
 real_reboot_executed=False,main_changed=False,pr75_changed=False,pr76_draft=True),
 next_gates=['INDEPENDENT_PM_EXACT_CODE_CLOCK_PROFILE_AND_WINDOWS_EVIDENCE_REVIEW',
 'ACTUAL_LEAST_PRIVILEGE_TASK_LOGOFF_REBOOT_STOP_DEPLOYMENT_PROOF',
 'SEPARATE_OWNER_EXACT_HEAD_MERGE_DEPLOYMENT_APPROVAL',
 'ONLY_THEN_FINITE_24H_READ_ONLY_SOAK_288_HEALTH_48_BOUNDARIES'],
 ci='NO_CHECKS_CONFIGURED_NO_CI_PASS_CLAIM',github_evidence_sync='READBACK_VERIFICATION_REPORTED_IN_HANDOFF_COMMENT')
(out/'acceptance-packet.json').write_text(json.dumps(packet,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(head=packet['head'],matrices=packet['matrices'],full_market=packet['full_market'],operational_clock=packet['operational_clock'])))
