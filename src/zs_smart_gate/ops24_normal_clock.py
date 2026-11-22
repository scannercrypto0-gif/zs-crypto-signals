"""Normal-token live Windows Time observations with protected OS provenance.

Same owner-approved numerical policy; separate versioned observation profile.
No source/config query exit is rewritten and no caller JSON is a clock witness.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from .ops24_budget import Hold
from .marketwide_capture import _is_admin as is_admin
from .ops_windows_time import COMMANDS, CANDIDATE, POLICY_ID, SOURCE, assess, command
from .ops_windows_child import sync_age
from .stage05_contracts import canonical, digest

PROFILE="WINDOWS_STATUS_PROTECTED_REGISTRY_V1"
TRUSTED={"S-1-5-18","S-1-5-32-544",
         "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"}
INSPECT=r"""
$ErrorActionPreference='Stop'
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry64)
$names=@('SYSTEM\CurrentControlSet\Services\W32Time',
 'SYSTEM\CurrentControlSet\Services\W32Time\Parameters',
 'SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient',
 'SYSTEM\CurrentControlSet\Services\autotimesvc',
 'SYSTEM\CurrentControlSet\Services\autotimesvc\Parameters',
 'SOFTWARE\Policies\Microsoft\W32Time\Parameters',
 'SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpClient')
$rows=@()
foreach($name in $names){
 $key=$base.OpenSubKey($name,$false)
 if($null -eq $key){continue}
 try{
  $acl=$key.GetAccessControl()
  $rows+=@{path=$name;values=@{Type=$key.GetValue('Type');NtpServer=$key.GetValue('NtpServer');ImagePath=$key.GetValue('ImagePath');ServiceDll=$key.GetValue('ServiceDll');Enabled=$key.GetValue('Enabled')};
   owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
   rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
    @{sid=$_.IdentityReference.Value;rights=[int64]$_.RegistryRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
 }finally{$key.Dispose()}
}
$base.Dispose()
$system32=[Environment]::SystemDirectory
$sidText=''
foreach($service in @('W32Time','autotimesvc')){
 # Native account translation does not require opening the Service Control
 # Manager. Microsoft documents NT SERVICE\SvcName for service SID lookup.
 $account=[Security.Principal.NTAccount]::new('NT SERVICE',$service)
 $sid=$account.Translate([Security.Principal.SecurityIdentifier]).Value
 if($sid -notmatch '^S-1-5-80-(\d+-){4}\d+$'){throw 'SERVICE_SID_QUERY_FAILED'}
 $sidText+=$sid+"`n"
}
$signatures=@()
foreach($name in @('sc.exe','w32tm.exe','w32time.dll','svchost.exe','autotimesvc.dll')){
 $file=Join-Path $system32 $name
 $signature=Get-AuthenticodeSignature -LiteralPath $file
 $acl=Get-Acl -LiteralPath $file
 $signatures+=@{file=$name;status=$signature.Status.ToString();status_message=$signature.StatusMessage;signature_type=$signature.SignatureType.ToString();signer=$signature.SignerCertificate.Subject;
  sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant();
  owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
  rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
   @{sid=$_.IdentityReference.Value;rights=[int64]$_.FileSystemRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
}
@{registry=$rows;signatures=$signatures;service_sid_text=$sidText;system32=$system32}|ConvertTo-Json -Depth 12 -Compress
"""


def system_directory():
    import ctypes
    buffer=ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer,len(buffer)):
        raise Hold("SYSTEM_DIRECTORY_UNVERIFIED")
    return Path(buffer.value)


def inspect(*, diagnostic_root=None):
    binary=system_directory()/"WindowsPowerShell"/"v1.0"/"powershell.exe"
    result=subprocess.run([str(binary),"-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-Command",INSPECT],
                          env={**os.environ,"PSModulePath":str(system_directory()/"WindowsPowerShell"/"v1.0"/"Modules")},
                          capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    # A successful collector may return a rejected signature/ACL. Preserve its
    # raw output before validation too; collection success is never acceptance.
    if diagnostic_root is not None:
        from .ops24_source import atomic
        root=Path(diagnostic_root).resolve()
        if Path('D:/ZS-SMART-GATE').resolve() not in root.parents:
            raise Hold('D_OWNED_DIAGNOSTIC_ROOT_REQUIRED')
        atomic(root/'clock-provenance.stdout.raw.txt',result.stdout)
        atomic(root/'clock-provenance.stderr.raw.txt',result.stderr)
        atomic(root/'clock-provenance.collection.json',canonical(dict(
            exit_code=result.returncode,stdout_sha256=digest(result.stdout),
            stderr_sha256=digest(result.stderr),status='COLLECTED_UNVALIDATED' if result.returncode==0 else 'PROVENANCE_COLLECTION_FAILED')))
    if result.returncode!=0:
        raise Hold("NORMAL_CLOCK_OS_PROVENANCE_UNAVAILABLE")
    profile=json.loads(result.stdout)
    if diagnostic_root is not None and (Path(diagnostic_root)/'clock-catalog-map.json').exists():
        from .ops24_source import atomic
        try:
            profile=bind_catalogs(profile,Path(diagnostic_root)/'clock-catalog-map.json')
        except Exception as exc:
            profile['catalog_binding_error']=str(exc) if isinstance(exc,(Hold,OSError,ValueError)) else type(exc).__name__
            raise
        finally:
            atomic(Path(diagnostic_root)/'clock-provenance.bound-catalog.json',canonical(profile))
    return profile


CATALOG_INSPECT=r"""
$ErrorActionPreference='Stop'
$file=$env:TASK_CLOCK_CATALOG_PATH
$signature=Get-AuthenticodeSignature -LiteralPath $file
$acl=Get-Acl -LiteralPath $file
@{file=$file;status=$signature.Status.ToString();status_message=$signature.StatusMessage;signer=$signature.SignerCertificate.Subject;
 sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant();
 owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
 rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
 @{sid=$_.IdentityReference.Value;rights=[int64]$_.FileSystemRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}|ConvertTo-Json -Depth 8 -Compress
"""


def catalog_signature(path):
    binary=system_directory()/'WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(binary),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',CATALOG_INSPECT],
        env={**os.environ,'TASK_CLOCK_CATALOG_PATH':str(path),
             'PSModulePath':str(system_directory()/'WindowsPowerShell/v1.0/Modules')},
        capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return dict(status='COLLECTION_FAILED',exit=result.returncode,
                    stderr=result.stderr.decode('utf-8',errors='replace'),
                    stdout=result.stdout.decode('utf-8',errors='replace'))
    return json.loads(result.stdout)


def bind_catalogs(profile,map_path):
    from .ops24_catalog import member_proof
    mapping=json.loads(Path(map_path).read_bytes())
    if mapping.get('schema')!='zs.ops24.catalog-map.v1' or mapping.get('scope')!='DISCOVERY_ONLY_NOT_ACCEPTANCE':
        raise Hold('CATALOG_MAP_UNQUALIFIED')
    cache={}
    for row in profile['signatures']:
        # Never substitute for HashMismatch/NotTrusted/unknown failures.
        if row['status']!='NotSigned':
            continue
        item=mapping['files'][row['file']]
        if item['file_sha256']!=row['sha256']:
            raise Hold('CATALOG_MAP_BINARY_CHANGED')
        path=Path(item['catalog']).resolve(strict=True)
        if not path.is_relative_to(system_directory()/'CatRoot') or path.suffix.lower()!='.cat':
            raise Hold('CATALOG_OUTSIDE_PROTECTED_STORE')
        proof=member_proof(system_directory()/row['file'],catalog=path)
        row['explicit_catalog']=proof
        if proof['catalog_sha256']!=item['catalog_sha256']:
            raise Hold('CATALOG_MAP_CATALOG_CHANGED')
        if str(path) not in cache:
            cache[str(path)]=catalog_signature(path)
        # Preserve original NotSigned and its message; a separate actual member
        # verification, signed catalog and protected ACL must ALL validate.
        row['explicit_catalog']['signature']=cache[str(path)]
    return profile


def microsoft_signer(value):
    return isinstance(value,str) and value.startswith(('CN=Microsoft Windows,','CN=Microsoft Windows Publisher,')) and 'O=Microsoft Corporation' in value


def signature_verified(row):
    if row['status']=='Valid':
        return microsoft_signer(row['signer'])
    if row['status']!='NotSigned':
        return False
    proof=row.get('explicit_catalog',{})
    if (proof.get('version')!='WINDOWS_EXPLICIT_CATALOG_MEMBER_V1'
            or type(proof.get('winverifytrust_code')) is not int or proof['winverifytrust_code']!=0
            or proof.get('verified') is not True or proof.get('hash_algorithm')!='SHA256'
            or not re.fullmatch(r'[A-F0-9]{64}',proof.get('sip_member_tag',''))
            or proof.get('file_sha256')!=row['sha256']
            or Path(proof.get('file',''))!=system_directory()/row['file']):
        return False
    path=Path(proof.get('catalog','')).resolve()
    if not path.is_relative_to(system_directory()/'CatRoot') or path.suffix.lower()!='.cat':
        return False
    signed=proof.get('signature',{})
    if (signed.get('status')!='Valid' or not microsoft_signer(signed.get('signer'))
            or signed.get('sha256')!=proof.get('catalog_sha256')
            or not re.fullmatch(r'[a-f0-9]{64}',signed.get('sha256',''))
            or Path(signed.get('file',''))!=path or signed.get('owner') not in TRUSTED):
        return False
    if not isinstance(signed.get('rules'),list) or not signed['rules']:
        return False
    for ace in signed['rules']:
        if ((ace['propagation']&2)==0 and ace['type']=='Allow'
                and ace['rights']&0xD0156 and ace['sid'] not in TRUSTED|{'S-1-3-0'}):
            return False
    return True


def verify_provenance(profile):
    matches=set(re.findall(r"S-1-5-80-(?:\d+-){4}\d+",profile["service_sid_text"]))
    if len(matches)!=2:
        raise Hold("WINDOWS_TIME_SERVICE_SID_UNVERIFIED")
    allowed=TRUSTED|matches
    signatures={row["file"]:row for row in profile["signatures"]}
    if set(signatures)!={"sc.exe","w32tm.exe","w32time.dll","svchost.exe","autotimesvc.dll"}:
        raise Hold("SYSTEM_BINARY_SET_UNVERIFIED")
    for row in signatures.values():
        if (not signature_verified(row)
                or not re.fullmatch(r"[a-f0-9]{64}",row["sha256"])):
            raise Hold("SYSTEM_BINARY_SIGNATURE_UNVERIFIED")
        if row["owner"] not in TRUSTED:
            raise Hold("SYSTEM_BINARY_OWNER_UNVERIFIED")
        for ace in row["rules"]:
            if ((ace["propagation"]&2)==0 and ace["type"]=="Allow"
                    and ace["rights"]&0xD0156 and ace["sid"] not in TRUSTED|{"S-1-3-0"}):
                raise Hold("SYSTEM_BINARY_WRITABLE")
    rows={row["path"]:row for row in profile["registry"]}
    base="SYSTEM\\CurrentControlSet\\Services\\W32Time"
    auto="SYSTEM\\CurrentControlSet\\Services\\autotimesvc"
    for required in (base,base+"\\Parameters",base+"\\TimeProviders\\NtpClient",auto,auto+"\\Parameters"):
        if required not in rows:
            raise Hold("PROTECTED_CLOCK_CONFIG_MISSING")
    for row in rows.values():
        if row["owner"] not in TRUSTED:
            raise Hold("CLOCK_CONFIG_OWNER_UNTRUSTED")
        for ace in row["rules"]:
            if (ace["propagation"] & 2)==0 and ace["type"]=="Allow":
                if (ace["rights"] & (0xD0026|0x10000000|0x40000000)) and ace["sid"] not in allowed:
                    raise Hold("CLOCK_CONFIG_WRITABLE_BY_NONPRIVILEGED_PRINCIPAL")
    params=rows[base+"\\Parameters"]["values"]
    if params["Type"]!="NTP" or params["NtpServer"].lower()!=SOURCE+",0x8":
        raise Hold("CLOCK_CONFIG_SOURCE_MISMATCH")
    system32=Path(profile["system32"])
    if str(system32).lower()!=str(system_directory()).lower():
        raise Hold("SYSTEM_DIRECTORY_MISMATCH")
    if str(params["ServiceDll"]).lower()!=str(system32/"w32time.dll").lower():
        raise Hold("CLOCK_SERVICE_DLL_MISMATCH")
    image=rows[base]["values"]["ImagePath"].lower()
    if not image.startswith(str(system32/"svchost.exe").lower()+" -k localservice"):
        raise Hold("CLOCK_SERVICE_IMAGE_MISMATCH")
    if (str(rows[auto+"\\Parameters"]["values"]["ServiceDll"]).lower()!=str(system32/"autotimesvc.dll").lower()
            or not rows[auto]["values"]["ImagePath"].lower().startswith(
                str(system32/"svchost.exe").lower()+" -k autotimesvc")):
        raise Hold("AUTOTIME_OS_SERVICE_IMAGE_MISMATCH")
    if rows[base+"\\TimeProviders\\NtpClient"]["values"]["Enabled"]!=1:
        raise Hold("NTP_CLIENT_DISABLED")
    for name,row in rows.items():
        if name.startswith("SOFTWARE\\Policies"):
            values=row["values"]
            if ((values["Type"] is not None and values["Type"]!="NTP")
                    or (values["NtpServer"] is not None and values["NtpServer"].lower()!=SOURCE+",0x8")
                    or (values["Enabled"] is not None and values["Enabled"]!=1)):
                raise Hold("GPO_CLOCK_SOURCE_OVERRIDE")
    return True


def assess_normal(observations, profile, age):
    verify_provenance(profile)
    policy=dict(policy_id=POLICY_ID,source=SOURCE,limits=CANDIDATE)
    result=assess(observations,sync_age_s=age,policy=policy)
    retained=list(result["blockers"])
    # These exact two redundant RPC failures are substituted only after verified
    # protected configuration and active status source satisfy equivalent inputs.
    blockers=[value for value in retained if value not in ("SOURCE_COMMAND_FAILED","CONFIGURATION_COMMAND_FAILED")]
    return {**result,"status":"OPERATIONAL_TIME_ACCEPTED" if not blockers else "BLOCKED",
            "blockers":blockers,"original_rpc_blockers":retained,
            "observation_profile":PROFILE,"provenance_sha256":digest(canonical(profile)),
            "rpc_exit_codes":{name:observations[name]["exit"] for name in COMMANDS},
            "signature_method":"WINDOWS_AUTHENTICODE_OR_EXPLICIT_CATALOG_MEMBER_V1",
            "equivalence_review":("NATIVE_CATALOG_BINDING_PENDING_INDEPENDENT_REVIEW" if any(
                row['status']=='NotSigned' for row in profile['signatures']) else
                "BOUNDED_PROFILE_ACCEPTED_PM_REVIEW_6004705942_CURRENT_PROVENANCE_RECHECKED")}


class NormalClock:
    def __init__(self, *, observe=command, provenance=inspect, age=sync_age):
        self.observe,self.provenance,self.age=observe,provenance,age
        self.lock=threading.Lock()
        self.latest=None
        self.at_mono=self.at_wall=None

    def refresh(self):
        if is_admin():
            raise Hold("NORMAL_TOKEN_CLOCK_REQUIRED")
        with self.lock:
            mono,wall=time.monotonic(),time.time()
            if self.latest is not None and (mono<self.at_mono or
                    abs((wall-self.at_wall)-(mono-self.at_mono))>.05):
                raise Hold("NORMAL_CLOCK_TIME_STEP")
            if (self.latest is not None and 0<=mono-self.at_mono<=20
                    and self.latest["assessment"]["sync_age_s"] is not None
                    and self.latest["assessment"]["sync_age_s"]+(mono-self.at_mono)<=600
                    and abs((wall-self.at_wall)-(mono-self.at_mono))<=.05):
                return self.latest
            profile=self.provenance()
            verify_provenance(profile)
            system32=Path(profile["system32"])
            observations={name:self.observe((str(system32/argv[0]),*argv[1:]))
                          for name,argv in COMMANDS.items()}
            age=self.age(observations["status"]["stdout"])
            if abs((time.time()-wall)-(time.monotonic()-mono))>.05:
                raise Hold("NORMAL_CLOCK_OBSERVATION_TIME_STEP")
            result=assess_normal(observations,profile,age)
            self.latest=dict(profile=PROFILE,assessment=result,observations=observations,
                provenance=profile,measured_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                measured_mono_ns=time.monotonic_ns())
            self.at_mono,self.at_wall=time.monotonic(),time.time()
            return self.latest

    def accepted(self):
        try:
            return self.refresh()["assessment"]["status"]=="OPERATIONAL_TIME_ACCEPTED"
        except (Hold,OSError,ValueError,KeyError,subprocess.TimeoutExpired):
            return False

