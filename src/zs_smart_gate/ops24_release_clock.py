"""Release-bound live OS/catalog observer shared by Serve and market children.

Short observation reuse remains bounded by NormalClock's existing20s policy;
each actual collection re-verifies native members, signatures and catalog ACLs.
The protected location map is checked for drift even during that short reuse.
"""
import json
import os
from pathlib import Path
import subprocess

from .ops24_budget import Hold
from .ops24_normal_clock import NormalClock,inspect,system_directory
from .stage05_contracts import digest

CONTRACT='ZS_OPS77_RELEASE_BOUND_CATALOG_CLOCK_V2'
TASK_PROFILE='ZS_OPS77_STANDARD_PASSWORD_SERVE_V2'
RECOVERY='DEPLOYMENT_RECOVERY_NO_MARKET_V1'

def validate_map(root,head,tree):
    root=Path(root)
    config=json.loads((root/'release.json').read_bytes())
    if (config.get('schema')!='zs.ops24.disabled-release.v2' or config.get('head')!=head
            or config.get('tree')!=tree or config.get('task_profile')!=TASK_PROFILE
            or config.get('task_logon_type')!='Password' or config.get('clock_contract')!=CONTRACT
            or config.get('owner_sid')==config.get('worker_sid')):
        raise Hold('SERVE_RELEASE_CLOCK_CONTRACT_MISMATCH')
    path=root/'clock-catalog-map.json'
    if path.is_symlink():raise Hold('CATALOG_MAP_REPARSE_REFUSED')
    raw=path.read_bytes()
    if digest(raw)!=config.get('clock_catalog_map_sha256'):
        raise Hold('CATALOG_MAP_PIN_MISMATCH')
    mapping=json.loads(raw)
    if (mapping.get('schema')!='zs.ops24.catalog-map.v2' or mapping.get('release_head')!=head
            or mapping.get('release_tree')!=tree
            or mapping.get('scope')!='DISCOVERY_ONLY_NOT_ACCEPTANCE'):
        raise Hold('CATALOG_MAP_RELEASE_MISMATCH')
    return config

def map_acl(root,config):
    script=r"""
$ErrorActionPreference='Stop';$rows=@()
foreach($p in @($env:OPS_CLOCK_ROOT,(Join-Path $env:OPS_CLOCK_ROOT 'release.json'),(Join-Path $env:OPS_CLOCK_ROOT 'clock-catalog-map.json'))){
 $i=Get-Item -LiteralPath $p
 if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'REPARSE_REFUSED'}
 $a=Get-Acl -LiteralPath $p
 $rows+=@{path=$p;owner=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value;rules=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{@{sid=$_.IdentityReference.Value;rights=[int64]$_.FileSystemRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
};ConvertTo-Json -InputObject @($rows) -Depth8 -Compress
""".replace('-Depth8','-Depth 8')
    result=subprocess.run([str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),
        '-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=10,
        env={**os.environ,'OPS_CLOCK_ROOT':str(Path(root).resolve()),
             'PSModulePath':str(system_directory()/'WindowsPowerShell/v1.0/Modules')},
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise Hold('CATALOG_MAP_ACL_UNVERIFIED')
    trusted={config['owner_sid'],'S-1-5-18','S-1-5-32-544'}
    for row in json.loads(result.stdout):
        if row['owner'] not in trusted or not row['rules']:
            raise Hold('CATALOG_MAP_OWNER_UNTRUSTED')
        for ace in row['rules']:
            if ace['type']!='Allow' or ace['propagation']&2 or ace['sid'] in trusted:continue
            mask=0xD0156|0x10000000|0x40000000
            if Path(row['path'])==Path(root).resolve() and ace['sid']==config['worker_sid']:
                mask=0xD0040|0x10000000
            if ace['rights']&mask:raise Hold('CATALOG_MAP_WRITABLE_BY_NONOWNER')

class ReleaseClock:
    def __init__(self,root,head,tree,*,acl=map_acl,collect=inspect):
        self.root=Path(root);self.head=head;self.tree=tree
        self.release_pin=digest((self.root/'release.json').read_bytes())
        self.acl,self.collect=acl,collect
        self.clock=NormalClock(provenance=self.provenance)

    def provenance(self):
        config=validate_map(self.root,self.head,self.tree)
        self.acl(self.root,config)
        result=self.collect(diagnostic_root=self.root)
        self.check()
        return result

    def check(self):
        if digest((self.root/'release.json').read_bytes())!=self.release_pin:
            raise Hold('RELEASE_CHANGED_RESTART_REQUIRED')
        return validate_map(self.root,self.head,self.tree)

    def refresh(self):
        self.check()
        witness=self.clock.refresh()
        return {**witness,'release_clock_contract':CONTRACT,'release_head':self.head,'release_tree':self.tree,
                'scoped_review':{'id':6011308846,'profile_matches_reviewed_os':
                    witness['assessment'].get('provenance_sha256')=='e7e418904de89f6fe1f7b2a0812ea8314b8dd84235f2365a3e843aa08ac83c1e',
                    'scope':'BOUNDED_OPERATIONAL_NOT_SCIENTIFIC_UTC'}}

    def accepted(self):
        try:return self.refresh()['assessment']['status']=='OPERATIONAL_TIME_ACCEPTED'
        except (Hold,OSError,ValueError,KeyError,subprocess.TimeoutExpired):return False
