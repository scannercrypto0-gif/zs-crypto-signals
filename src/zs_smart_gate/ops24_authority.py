"""Standing-owner read-only authority composed from actual, immutable release evidence.

A shared-account PM COMMENT is a provenance record, never a formal APPROVE.
No per-run owner signature or fabricated accepted flag is consumed.
"""
import json
from pathlib import Path
import re
import subprocess

from .ops24_budget import Hold
from .ops24_science import intake
from .stage05_contracts import canonical,digest

REPO='scannercrypto0-gif/zs-crypto-signals'
STANDING=7061389384
SCOPE='PUBLIC_SPOT_READ_ONLY_NO_TELEGRAM_SQL_TRADING'


def github(path):
    result=subprocess.run(['gh','api',path],capture_output=True,text=True,timeout=30)
    if result.returncode:
        raise Hold('GITHUB_AUTHORITY_OR_RULES_UNVERIFIED')
    return json.loads(result.stdout)


def windows_proof(folder,head,tree):
    folder=Path(folder)
    raw=(folder/'acceptance.json').read_bytes()
    proof=json.loads(raw)
    if (proof.get('head')!=head or proof.get('tree')!=tree or proof.get('clean') is not True
            or proof.get('python')!='3.12.10' or not proof.get('powershell','').startswith('5.1.')
            or proof.get('success') is not True or proof.get('tests',0)<=0
            or any(proof.get(k)!=0 for k in ('failures','errors','skipped','network_attempts'))):
        raise Hold('WINDOWS_EXACT_RELEASE_EVIDENCE_REQUIRED')
    total=0
    for row in proof['suites']:
        stem=row['suite'].replace('.','_')
        for stream in ('stdout','stderr'):
            data=(folder/(stem+'.'+stream+'.raw.txt')).read_bytes()
            if digest(data)!=row[stream+'_sha256']:
                raise Hold('WINDOWS_RAW_RECEIPT_HASH_MISMATCH')
        result=json.loads((folder/(stem+'.json')).read_bytes())
        if result!=row['result'] or row['exit']!=0 or result['success'] is not True:
            raise Hold('WINDOWS_RAW_RESULT_MISMATCH')
        total+=result['tests']
    if total!=proof['tests']:
        raise Hold('WINDOWS_TEST_TOTAL_MISMATCH')
    return dict(sha256=digest(raw),tests=total,head=head,tree=tree)


def source_proof(folder,head,tree):
    folder=Path(folder)
    raw=(folder/'result.json').read_bytes()
    if digest(raw)!=(folder/'result.sha256').read_text().strip():
        raise Hold('SOURCE_RECEIPT_HASH_INVALID')
    row=json.loads(raw)
    if (row.get('head')!=head or row.get('tree')!=tree or row.get('coverage')!='MARKET_COVERAGE_VERIFIED'
            or row.get('eligible',0)<=0 or row.get('eligible')!=row.get('validated')
            or row.get('missing')!=0 or row.get('stop') is not None
            or row['budget']['halt'] is not None or row['budget']['active']!=0
            or row.get('signal_ids')!=[] or row.get('telegram_calls')!=0 or row.get('sql_writes')!=0):
        raise Hold('EXACT_RELEASE_FULL_MARKET_PROOF_REQUIRED')
    clock=row.get('decision_clock')
    if not isinstance(clock,dict) or not re.fullmatch(r'[a-f0-9]{64}',clock.get('witness_sha256','')):
        raise Hold('ACTUAL_CLOCK_RECEIPT_REQUIRED')
    witness=(folder/('clock-'+clock['witness_sha256']+'.private.json')).read_bytes()
    if digest(witness)!=clock['witness_sha256']:
        raise Hold('SOURCE_CLOCK_HASH_MISMATCH')
    from .ops24_normal_clock import assess_normal,PROFILE
    observed=json.loads(witness)
    assessed=assess_normal(observed['observations'],observed['provenance'],observed['assessment']['sync_age_s'])
    if observed['profile']!=PROFILE or assessed['status']!='OPERATIONAL_TIME_ACCEPTED':
        raise Hold('SOURCE_OPERATIONAL_CLOCK_NOT_PROVED')
    replay=intake(folder)  # Original hashes and common-D decisions, not a boolean permit.
    if replay['events']!=row['eligible']:
        raise Hold('SOURCE_ORIGINAL_REPLAY_INCOMPLETE')
    return dict(sha256=digest(raw),inventory_id=row['inventory_id'],eligible=row['eligible'],head=head,tree=tree)


def review_proof(reviews,head,tree):
    # PM must record this exact structured decision on the revised immutable head.
    marker='OPS24_RELEASE_ACCEPT '+head+' '+tree+' '+SCOPE
    matches=[r for r in reviews if r.get('commit_id')==head and r.get('state') in ('COMMENTED','APPROVED')
             and r.get('user',{}).get('login')=='scannercrypto0-gif'
             and marker in r.get('body','').splitlines() and 'PM' in r.get('body','')]
    if not matches:
        raise Hold('PM_REVISED_EXACT_RELEASE_REVIEW_PENDING')
    review=matches[-1]
    return dict(id=review['id'],url=review['html_url'],body_sha256=digest(review['body'].encode()),
                nature='PM_SHARED_ACCOUNT_COMMENT_NOT_FORMAL_INDEPENDENT_GITHUB_APPROVE')


def compose(*,head,tree,windows,source,fetch=github):
    authority=fetch(f'repos/{REPO}/issues/comments/{STANDING}')
    if (authority.get('user',{}).get('login')!='scannercrypto0-gif'
            or 'Standing authorization granted now' not in authority.get('body','')
            or 'read-only' not in authority.get('body','')):
        raise Hold('STANDING_OWNER_DIRECTIVE_NOT_VERIFIED')
    review=review_proof(fetch(f'repos/{REPO}/pulls/76/reviews?per_page=100'),head,tree)
    pr=fetch(f'repos/{REPO}/pulls/76')
    if pr['head']['sha']!=head or pr.get('draft') is not False or not pr.get('merged'):
        raise Hold('REVIEWED_PLATFORM_MERGE_PENDING')
    merge=fetch(f'repos/{REPO}/git/commits/'+pr['merge_commit_sha'])
    if merge['tree']['sha']!=tree:
        raise Hold('MERGED_TREE_DIFFERS_FROM_WINDOWS_PROOF')
    branch=fetch(f'repos/{REPO}/branches/main')
    if branch['commit']['sha']!=pr['merge_commit_sha']:
        raise Hold('INSTALLED_RELEASE_MUST_MATCH_CURRENT_MERGED_MAIN')
    return dict(schema='zs.ops24.standing-authority.v2',scope=SCOPE,head=pr['merge_commit_sha'],tree=tree,
        reviewed_source_head=head,authority_id=STANDING,authority_body_sha256=digest(authority['body'].encode()),
        review=review,platform=dict(pr=76,merged_commit=pr['merge_commit_sha'],branch_protected=branch['protected'],
                                   protection_bypass=False),windows=windows_proof(windows,head,tree),
        source=source_proof(source,head,tree),seconds=86400,
        decision='REVIEWED_READ_ONLY_RELEASE_ADMITTED_G3_DEPLOYMENT_PROOF_STILL_REQUIRED')


def verify_remote(decision,*,fetch=github):
    verify_cached(decision,head=decision['head'],tree=decision['tree'])
    authority=fetch(f'repos/{REPO}/issues/comments/{STANDING}')
    if digest(authority.get('body','').encode())!=decision['authority_body_sha256']:
        raise Hold('STANDING_AUTHORITY_CHANGED_RECOMPOSE_REQUIRED')
    proof=review_proof(fetch(f'repos/{REPO}/pulls/76/reviews?per_page=100'),
                       decision['reviewed_source_head'],decision['tree'])
    if proof!=decision['review']:
        raise Hold('PM_REVIEW_CHANGED_RECOMPOSE_REQUIRED')
    pr=fetch(f'repos/{REPO}/pulls/76')
    branch=fetch(f'repos/{REPO}/branches/main')
    merge=fetch(f'repos/{REPO}/git/commits/'+decision['head'])
    if (pr.get('merged') is not True or pr.get('merge_commit_sha')!=decision['head']
            or branch['commit']['sha']!=decision['head'] or merge['tree']['sha']!=decision['tree']):
        raise Hold('PLATFORM_RELEASE_STATE_CHANGED')
    return decision


def verify_cached(decision,*,head,tree):
    if (decision.get('schema')!='zs.ops24.standing-authority.v2' or decision.get('scope')!=SCOPE
            or decision.get('head')!=head or decision.get('tree')!=tree or decision.get('authority_id')!=STANDING
            or decision.get('platform',{}).get('merged_commit')!=head
            or decision.get('platform',{}).get('protection_bypass') is not False
            or decision.get('seconds')!=86400):
        raise Hold('STANDING_RELEASE_SCOPE_OR_PIN_INVALID')
    source_head=decision['reviewed_source_head']
    for name in ('windows','source'):
        if decision[name]['head']!=source_head or decision[name]['tree']!=tree:
            raise Hold('STANDING_EVIDENCE_RELEASE_MISMATCH')
    if decision['windows'].get('tests',0)<=0 or decision['source'].get('eligible',0)<=0:
        raise Hold('STANDING_ACTUAL_EVIDENCE_REQUIRED')
    return decision


def deployment_proof(root,head,tree,owner_sid):
    root=Path(root)
    manifest=json.loads((root/'deployment-proof.json').read_bytes())
    if (manifest.get('schema')!='zs.ops24.actual-deployment.v2' or manifest.get('head')!=head
            or manifest.get('tree')!=tree or manifest.get('owner_sid')!=owner_sid):
        raise Hold('ACTUAL_NORMAL_DEPLOYMENT_PROOF_PENDING')
    records={}
    for name in ('probe','before_boot','after_boot','logged_off','restore','stop'):
        item=manifest['receipts'][name]
        path=(root/item['file']).resolve()
        if root.resolve() not in path.parents or path.is_symlink():
            raise Hold('DEPLOYMENT_RECEIPT_PATH_INVALID')
        raw=path.read_bytes()
        if digest(raw)!=item['sha256']:
            raise Hold('DEPLOYMENT_RAW_HASH_MISMATCH')
        records[name]=json.loads(raw)
    probe=records['probe']
    if (probe.get('schema')!='zs.ops24.actual-normal-task-probe.v2' or probe.get('normal_token') is not True
            or probe.get('head')!=head or probe.get('tree')!=tree or probe['windows']['session']!=0
            or probe.get('market_calls')!=0 or probe.get('telegram_calls')!=0 or probe.get('sql_writes')!=0):
        raise Hold('ACTUAL_NONINTERACTIVE_NORMAL_TASK_REQUIRED')
    if (records['before_boot']['boot_utc']==records['after_boot']['boot_utc']
            or records['after_boot']['boot_utc']!=probe['windows']['boot_utc']):
        raise Hold('ACTUAL_REBOOT_NOT_OBSERVED')
    if (records['logged_off'].get('owner_sid')!=owner_sid
            or records['logged_off'].get('owner_explorer_pids')!=[]
            or records['logged_off'].get('observed_utc',0)<probe['measured_utc']):
        raise Hold('ACTUAL_OWNER_LOGOFF_NOT_OBSERVED')
    if records['restore'].get('head')!=head or records['restore'].get('tree')!=tree:
        raise Hold('ACTUAL_RESTORE_RELEASE_MISMATCH')
    if (records['stop'].get('stop_requested') is not True or records['stop'].get('worker_pids')!=[]
            or records['stop'].get('lock_exclusive') is not True):
        raise Hold('ACTUAL_STOP_PROOF_REQUIRED')
    return dict(receipt_sha256=digest(canonical(manifest)),scope='ACTUAL_DEPLOYMENT_RECORDS_ONLY')


def verify_protected_cache(root,decision,config):
    """A standard worker trusts owner-written immutable files, never owner credentials.

    The owner bootstrap verified real GitHub records online. This read-only cache
    lets the separate standard account start offline without a GitHub write token.
    """
    import os
    from .ops24_normal_clock import system_directory
    root=Path(root).resolve()
    owner,worker=config['owner_sid'],config['worker_sid']
    if owner==worker or digest((root/'standing-authority.json').read_bytes())!=config.get('standing_authority_sha256'):
        raise Hold('PROTECTED_STANDING_CACHE_REQUIRED')
    script=r"""
$ErrorActionPreference='Stop'
$root=$env:ZS_CACHE_ROOT
$source=$env:ZS_CACHE_SOURCE
$rows=@()
foreach($path in @($root,(Join-Path $root 'release.json'),(Join-Path $root 'standing-authority.json'),$source,(Join-Path $source '.git'))){
 $acl=Get-Acl -LiteralPath $path
 $rows+=@{path=$path;owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
  rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
   @{sid=$_.IdentityReference.Value;rights=[int64]$_.FileSystemRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
}
ConvertTo-Json -InputObject @($rows) -Depth 8 -Compress
"""
    result=subprocess.run([str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),
                           '-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=15,
          env={**os.environ,'ZS_CACHE_ROOT':str(root),'ZS_CACHE_SOURCE':config['source'],
               'PSModulePath':str(system_directory()/'WindowsPowerShell/v1.0/Modules')},
          creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise Hold('PROTECTED_CACHE_ACL_QUERY_FAILED')
    allowed={owner,'S-1-5-18','S-1-5-32-544'}
    for row in json.loads(result.stdout):
        if row['owner'] not in allowed:raise Hold('PROTECTED_CACHE_OWNER_MISMATCH')
        for ace in row['rules']:
            if ace['type']!='Allow' or ace['propagation']&2 or ace['sid'] in allowed:continue
            mask=0xD0156|0x10000000|0x40000000
            if str(Path(row['path']).resolve()).lower()==str(root).lower() and ace['sid']==worker:
                mask=0xD0040|0x10000000  # No root delete/delete-child/ownership/DACL mutation.
            if ace['rights']&mask:raise Hold('STANDING_CACHE_WRITABLE_BY_UNTRUSTED_PRINCIPAL')
    return dict(scope='OWNER_VERIFIED_CACHE_NO_GITHUB_CREDENTIALS_IN_WORKER',
                authority_sha256=config['standing_authority_sha256'])
