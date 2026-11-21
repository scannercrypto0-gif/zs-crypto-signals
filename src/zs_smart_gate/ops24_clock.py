"""Protected operational clock witness. This is not independent scientific UTC."""
import base64
import json
import math
import os
from pathlib import Path
import time

from .ops24_budget import Hold
from .ops24_source import atomic
from .ops_windows_time import COMMANDS, CANDIDATE, POLICY_ID, SOURCE, REVIEWED_POLICY_SHA256, assess, command
from .ops_windows_child import sync_age
from .stage05_contracts import canonical, digest


def is_admin():
    if os.name != "nt":
        return False
    import ctypes
    return ctypes.windll.shell32.IsUserAnAdmin() == 1


def sign(payload, private_key):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signature = private_key.sign(canonical(payload),padding.PKCS1v15(),hashes.SHA256())
    return dict(payload=payload,signature=base64.b64encode(signature).decode())


def verify_envelope(envelope, public_pem, expected_pin):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    if digest(public_pem) != expected_pin:
        raise Hold("CLOCK_AUTHORITY_PIN_MISMATCH")
    public = serialization.load_pem_public_key(public_pem)
    if not isinstance(public,rsa.RSAPublicKey) or public.key_size < 3072:
        raise Hold("CLOCK_AUTHORITY_KEY_INVALID")
    try:
        public.verify(base64.b64decode(envelope["signature"],validate=True),
                      canonical(envelope["payload"]),padding.PKCS1v15(),hashes.SHA256())
    except Exception:
        raise Hold("CLOCK_SIGNATURE_INVALID") from None
    return envelope["payload"]


def check_clock(envelope, public_pem, expected_pin, *, head, tree,
                wall=time.time, mono=time.monotonic):
    payload = verify_envelope(envelope,public_pem,expected_pin)
    if (payload.get("schema")!="zs.ops24.clock-witness.v1" or payload.get("head")!=head
            or payload.get("tree")!=tree or payload.get("policy_sha256")!=REVIEWED_POLICY_SHA256
            or payload.get("purpose")!="OPERATIONAL_CLOCK_ONLY"):
        raise Hold("CLOCK_WITNESS_SCOPE_INVALID")
    age = mono()-payload["mono"]
    wall_age = wall()-payload["wall"]
    values = (age,wall_age,payload["valid_seconds"],payload["uncertainty_s"])
    if (any(type(v) not in (int,float) or not math.isfinite(v) for v in values)
            or not 0<=age<=min(payload["valid_seconds"],30)
            or abs(age-wall_age)>.05):
        raise Hold("CLOCK_WITNESS_STALE_OR_STEP_OR_BOOT")
    observation = payload["assessment"]
    # Reassess the signed raw observations; never trust only an accepted flag.
    policy = dict(policy_id=POLICY_ID,source=SOURCE,limits=CANDIDATE)
    accepted = assess(payload["observations"],sync_age_s=payload["sync_age_s"]+age,policy=policy)
    if (observation!=assess(payload["observations"],sync_age_s=payload["sync_age_s"],policy=policy)
            or accepted["status"]!="OPERATIONAL_TIME_ACCEPTED"
            or not 0<=payload["uncertainty_s"]<=.5):
        raise Hold("CLOCK_OBSERVATIONS_NOT_ACCEPTED")
    return dict(status="OPERATIONAL_TIME_ACCEPTED",authority_sha256=expected_pin,
                witness_sha256=digest(canonical(envelope)),age_s=age,
                independent_cryptographic_utc="NOT_PROVEN")


def collect(private_key_path, output, *, head, tree):
    """Called only by the scoped privileged publisher, never by the worker."""
    if not is_admin():
        raise Hold("CLOCK_PUBLISHER_REQUIRES_EXPLICIT_ADMIN_CONTEXT")
    from cryptography.hazmat.primitives import serialization
    key_path = Path(private_key_path)
    key = serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    observations = {name:command(argv) for name,argv in COMMANDS.items()}
    age = sync_age(observations["status"]["stdout"])
    policy = dict(policy_id=POLICY_ID,source=SOURCE,limits=CANDIDATE)
    result = assess(observations,sync_age_s=age,policy=policy)
    if result["status"]!="OPERATIONAL_TIME_ACCEPTED":
        raise Hold("CLOCK_PUBLISHER_OBSERVATIONS_BLOCKED")
    payload = dict(schema="zs.ops24.clock-witness.v1",head=head,tree=tree,
        purpose="OPERATIONAL_CLOCK_ONLY",policy_sha256=REVIEWED_POLICY_SHA256,
        observations=observations,assessment=result,sync_age_s=age,
        mono=time.monotonic(),wall=time.time(),valid_seconds=30,
        uncertainty_s=result["conditional_uncertainty_s"])
    envelope = sign(payload,key)
    atomic(output,canonical(envelope))
    return dict(status=result["status"],witness_sha256=digest(canonical(envelope)))


def protected_authority(root):
    """Check the Windows ownership/DACL chain before trusting a deployment pin."""
    import subprocess
    root=Path(root).resolve()
    if os.name!="nt" or root.drive.upper()!="D:":
        raise Hold("PROTECTED_CLOCK_TRUST_NOT_PROVEN")
    script=r"""
$ErrorActionPreference='Stop'
try {
 $paths=@((Join-Path $env:OPS24_TRUST_ROOT 'release.json'),(Join-Path $env:OPS24_TRUST_ROOT 'authority.public.pem'))
 $allowed=@('S-1-5-18','S-1-5-32-544')
 foreach($file in $paths) {
  $item=Get-Item -LiteralPath $file -Force
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 70}
  $acl=Get-Acl -LiteralPath $file
  $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  if($owner -notin $allowed){exit 70}
  foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed -and
      ([int64]$rule.FileSystemRights -band 0x000D0156)){exit 70}
  }
 }
 $dir=[IO.Path]::GetFullPath($env:OPS24_TRUST_ROOT)
 while($dir){
  $item=Get-Item -LiteralPath $dir -Force
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 70}
  $acl=Get-Acl -LiteralPath $dir
  if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $allowed){exit 70}
  foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $allowed -and
      ([int64]$rule.FileSystemRights -band 0x000D0040)){exit 70}
  }
  $next=Split-Path $dir -Parent
  if(-not $next -or $next -eq $dir){break}
  $dir=$next
 }
 exit 0
}catch{exit 71}
"""
    result=subprocess.run(
        [str(Path(os.environ["SystemRoot"])/"System32"/"WindowsPowerShell"/"v1.0"/"powershell.exe"),
         "-NoProfile","-NonInteractive","-Command",script],
        env={**os.environ,"OPS24_TRUST_ROOT":str(root)},capture_output=True,timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode!=0:
        raise Hold("PROTECTED_CLOCK_TRUST_ACL_NOT_PROVEN")
