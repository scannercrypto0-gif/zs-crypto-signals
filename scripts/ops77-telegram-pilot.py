"""Finite private research bridge: real source/clock, no qualified signal claim.

Never starts a permanent worker. Production qualification cannot be enabled by
a flag here: existing VerifiedUpstream permits rejection records only.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from zs_smart_gate.e2e51 import BASE, NoRedirect, analyze, capture, ms, persist
from zs_smart_gate.ops24_authority import windows_proof
from zs_smart_gate.ops24_release_clock import ReleaseClock
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage05_custody import VerifiedUpstream
from zs_smart_gate.stage05_runtime_bridge import TelegramBridge
from zs_smart_gate.stage05_telegram_http import BotSecrets, OwnerPermit, RuntimeFlags
from zs_smart_gate.windows_runner import process_lock

OWNER_COMMENT = 'repos/scannercrypto0-gif/zs-crypto-signals/issues/comments/7061701199'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--head', required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--clock-root', type=Path, required=True)
    p.add_argument('--windows-evidence', type=Path, required=True)
    p.add_argument('--polls', type=int, default=20, choices=range(1,41))
    p.add_argument('--live', action='store_true')
    args = p.parse_args()
    source = Path(__file__).resolve().parents[1]
    root = args.root.resolve()
    if os.name != 'nt' or Path('D:/ZS-SMART-GATE').resolve() not in root.parents:
        raise ContractError('WINDOWS_D_RUNTIME_REQUIRED')
    if not args.live:
        raise ContractError('EXPLICIT_FINITE_PILOT_SWITCH_REQUIRED')
    def git(*cmd):
        return subprocess.check_output(['git','-C',str(source),*cmd], text=True, timeout=15,
                                       creationflags=subprocess.CREATE_NO_WINDOW).strip()
    if git('rev-parse','HEAD') != args.head or git('status','--porcelain'):
        raise ContractError('PINNED_CLEAN_SOURCE_REQUIRED')
    tree = git('rev-parse','HEAD^{tree}')
    proof = windows_proof(args.windows_evidence,args.head,tree)
    cfg = BotSecrets.from_environ()
    if root.exists():
        raise ContractError('FRESH_PILOT_ROOT_REQUIRED')
    root.mkdir(parents=True)
    def save(name,value):
        (root/name).write_bytes(canonical(value))
    authority = json.loads(subprocess.check_output(['gh','api',OWNER_COMMENT],text=True,timeout=20,
                                                   creationflags=subprocess.CREATE_NO_WINDOW))
    if (authority.get('user',{}).get('login') != 'scannercrypto0-gif'
            or 'TEST/RESEARCH_ONLY' not in authority.get('body','')
            or 'do not send nonqualified' not in authority.get('body','')):
        raise ContractError('GENUINE_OWNER_PRIVATE_RESEARCH_AUTHORITY_REQUIRED')
    save('authority.json',dict(id=authority['id'],author=authority['user']['login'],
        body_sha256=digest(authority['body'].encode()),head=args.head,windows_proof=proof,
        scope='FINITE_PRIVATE_TEST_RESEARCH_ONLY_NOT_PRODUCTION'))
    release=json.loads((args.clock_root/'release.json').read_bytes())
    # The observed clock belongs to the separately pinned Windows deployment.
    # Do not claim its earlier deployment tests were tests of this bridge HEAD.
    clock=ReleaseClock(args.clock_root,release['head'],release['tree'])
    counts=dict(market=0,telegram=0)
    started=time.monotonic()
    def guard():
        if (root/'STOP_REQUESTED').exists() or time.monotonic()-started>180:
            raise ContractError('PILOT_STOP_OR_180S_LIMIT')
        witness=clock.refresh()
        raw=canonical(witness);pin=digest(raw)
        (root/('clock-'+pin+'.private.json')).write_bytes(raw)
        if witness['assessment']['status']!='OPERATIONAL_TIME_ACCEPTED':
            save('clock-hold.json',dict(head=args.head,assessment=witness['assessment'],witness_sha256=pin))
            raise ContractError('PILOT_OPERATIONAL_CLOCK_HOLD_NO_MARKET_OR_SEND')
        return True
    guard()
    def get(path,params):
        guard()
        if counts['market']>=6:
            raise ContractError('PILOT_SIX_MARKET_REQUEST_CAP')
        counts['market']+=1
        url=BASE+'/api/v3/'+path+('?' + urlencode(params) if params else '')
        request=Request(url,headers={'Accept':'application/json','Cache-Control':'no-cache'})
        with build_opener(NoRedirect()).open(request,timeout=5) as response:
            raw=response.read(262145)
            if response.status!=200 or len(raw)>262144:
                raise ContractError('MARKET_HTTP_OR_RESPONSE_SIZE_HOLD')
        pin=digest(raw);(root/('market-'+pin+'.raw.json')).write_bytes(raw)
        save('market-attempt-'+str(counts['market'])+'.json',dict(path=path,params=params,sha256=pin))
        return json.loads(raw)
    with process_lock(Path('D:/ZS-SMART-GATE/locks/telegram-interactive')) as acquired:
        if not acquired:
            raise ContractError('INTERACTIVE_CONSUMER_ALREADY_RUNNING')
        receipts=[]
        capture(receipts,get=get,clock=ms)
        guard()
        event=analyze(receipts,ms(),synthetic=False)
        stored,_=persist(root,receipts,event)
        journal=LocalChainJournal(root/'journal.sqlite')
        ref=journal.append_readback(stored)[0],digest(canonical(stored))
        upstream=VerifiedUpstream(journal,dict([ref]))
        until=(datetime.now(timezone.utc)+timedelta(seconds=180)).isoformat()
        # Permission derives from the fetched actual owner decision, while
        # runtime readiness is proved above, not from a fabricated PM signature.
        permit=OwnerPermit('OWNER-APPROVED-ISSUE51-7061701199',args.head,until,
            frozenset(('ANALYTICS','INTERACTIVE_POLL','INTERACTIVE_REPLY')),True,True)
        flags=RuntimeFlags(send=True,analytics=True,interactive_poll=True,interactive_reply=True)
        bridge=TelegramBridge(root=root/'bridge',config=cfg,upstream=upstream,
            references={event['symbol']:ref},clock_guard=guard,flags=flags,permit=permit,head_sha=args.head)
        http=bridge.transports['INTERACTIVE']
        for transport in bridge.transports.values():
            def attempted(method):
                guard();counts['telegram']+=1
                if counts['telegram']>46:
                    raise ContractError('PILOT_TELEGRAM_REQUEST_CAP')
            transport._on_attempt=attempted
        if http.verify_no_webhook(**bridge.opts).status!='ACCEPTED':
            raise ContractError('INTERACTIVE_WEBHOOK_OR_TRANSPORT_HOLD')
        archive=bridge.dispatch(event['symbol'])
        save('archive-result.json',archive)
        print('READY — FINITE RESEARCH PILOT; A AND B MAY SEND BTCUSDT',flush=True)
        replies=[]
        for _ in range(args.polls):
            guard();result=bridge.poll_once();replies.extend(result['replies'])
            save('pilot-status.json',dict(head=args.head,counts=counts,replies=replies,
                signal_id=None,signal_dispatch='BLOCKED_QUALIFIED_VERIFIER_UNAVAILABLE',archive=archive))
            observed={row['destination_label'] for row in replies if row['status']=='ACCEPTED'}
            if observed=={'A','B'} or result['status']!='ACCEPTED':break
            time.sleep(3)
        save('pilot-final.json',dict(head=args.head,counts=counts,replies=replies,
            qualified_signal_sent=False,production=False,continuous=False,
            accepted_interactive_routes=sorted({row['destination_label'] for row in replies if row['status']=='ACCEPTED'}),
            status='FINITE_RESEARCH_COMPLETED_NOT_SIGNAL_ACCEPTANCE'))
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        # Do not expose token-bearing URL/HTTP/subprocess exception strings.
        print(json.dumps(dict(status='HOLD',reason=str(exc) if isinstance(exc,ContractError) else type(exc).__name__)),flush=True)
        raise SystemExit(2)
