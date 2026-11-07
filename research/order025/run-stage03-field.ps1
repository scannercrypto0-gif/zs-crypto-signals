# ZS03 bounded source cycle. Manual PowerShell use only, no loop/scheduler.
param(
 [Parameter(Mandatory=$true)][ValidateSet("pre","post")][string]$Phase,
 [Parameter(Mandatory=$true)][string]$ParentOpenUtc
)
$ErrorActionPreference = "Stop"
$root = "D:\ZS Crypto Signals Latest Version"
Set-Location -LiteralPath $root
$expectedBranch = "stage03-r2-offline-dev-candidate-sd23"
$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne $expectedBranch) {
 throw "WRONG_BRANCH: expected $expectedBranch; got $branch"
}
git merge-base --is-ancestor 584efd52d4ac3ea3b98949c8918ac41594d67329 HEAD
if ($LASTEXITCODE -ne 0) { throw "BASELINE_HEAD_NOT_ANCESTOR" }
$env:PYTHONPATH = Join-Path $root "src"
$folder = Join-Path $root "_local_evidence\zs03-field"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
Write-Host "PRE=4 or POST=6 single GETs. BTCUSDT public Spot only. No credentials."
Write-Host "Independent UTC event witness is NOT established: scientific source gate stays blocked."
Write-Host "Verify provider terms and PRIVATE NONCOMMERCIAL retention rights before use."
py -3.12 -m zs_smart_gate.stage03_windows_field_capture --phase $Phase --parent-open-utc $ParentOpenUtc --evidence-dir $folder --rights-scope PRIVATE_NONCOMMERCIAL_RESEARCH --manual-authorized
if ($LASTEXITCODE -ne 0) { throw "PHASE_FAILED_NO_RETRY" }
