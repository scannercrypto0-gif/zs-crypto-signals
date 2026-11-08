# One-time owner Windows research-only quick 30m path. Does not alter old 4h event.
param(
 [Parameter(Mandatory=$true)]
 [ValidateSet("precheck","post","review")][string]$Phase,
 [Parameter(Mandatory=$true)][string]$ParentOpenUtc
)
$ErrorActionPreference = "Stop"
$root = 'D:\ZS Crypto Signals Latest Version'
Set-Location -LiteralPath $root
$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne 'stage03-r2-offline-dev-candidate-sd23') {
 throw 'QUICK30_WRONG_BRANCH'
}
git merge-base --is-ancestor df343722fd29da560bef60bc07b8f0f8b7a52fa2 HEAD
if ($LASTEXITCODE -ne 0) { throw 'QUICK30_NOT_ON_APPROVED_PR39' }
git diff --quiet
if ($LASTEXITCODE -ne 0) { throw 'QUICK30_TRACKED_WORKTREE_DIRTY' }
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw 'QUICK30_STAGED_CHANGES_PRESENT' }
$folder = Join-Path $root '_local_evidence\zs03-field'
$rights = Join-Path $folder 'rights-attestation.json'
if (-not (Test-Path -LiteralPath $rights)) { throw 'QUICK30_RIGHTS_ATTESTATION_MISSING' }
$env:PYTHONPATH = Join-Path $root 'src'
$argv = @('--phase',$Phase,'--parent-open-utc',$ParentOpenUtc,
  '--evidence-dir',$folder,'--rights-attestation',$rights,'--manual-authorized')
py -3.12 -m zs_smart_gate.stage03_field_quick30 @argv
if ($LASTEXITCODE -ne 0) { throw 'QUICK30_BLOCKED_NO_RETRY_OF_POST_ON_SAME_EVENT' }
