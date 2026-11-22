"""Owner bootstrap records actual directive + tested new source; never LIVE admission."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_authority import github,windows_proof,REPO
from zs_smart_gate.ops24_release_clock import RECOVERY
from zs_smart_gate.stage05_contracts import canonical,digest
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--head',required=True);p.add_argument('--tree',required=True);p.add_argument('--windows',type=Path,required=True)
a=p.parse_args();comment=github(f'repos/{REPO}/issues/comments/7076686518');pr=github(f'repos/{REPO}/pulls/76')
if comment.get('user',{}).get('login')!='scannercrypto0-gif' or 'PRODUCTION_SERVE_UNPROVEN' not in comment.get('body','') or pr['head']['sha']!=a.head:raise ValueError('OFFICIAL_RECOVERY_DIRECTIVE_OR_PR_HEAD_UNVERIFIED')
now=int(time.time());record=dict(schema='zs.ops77.recovery-authority.v1',scope=RECOVERY,head=a.head,tree=a.tree,
    directive_id=7076686518,directive_body=comment['body'],directive_sha256=digest(comment['body'].encode()),
    windows_tests=windows_proof(a.windows,a.head,a.tree),created_epoch=now,expires_epoch=now+86400,
    limits=dict(market_calls=0,telegram_calls=0,sql_writes=0),production_admission=False)
raw=canonical(record);(a.root/'recovery-authority.json').write_bytes(raw)
path=a.root/'release.json';config=json.loads(path.read_bytes());config['recovery_authority_sha256']=digest(raw);path.write_bytes(canonical(config))
print('STANDING_DIRECTIVE_PINNED_FOR_RECOVERY_ONLY_NO_MARKET')
