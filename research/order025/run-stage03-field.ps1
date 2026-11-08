# Owner Windows 11, manually invoked research-only Stage03 runbook.
param(
 [Parameter(Mandatory=$true)][ValidateSet("clock","rights","pre","post","review")][string]$Phase,
 [string]$ParentOpenUtc
)
$ErrorActionPreference="Stop"
$root="D:\ZS Crypto Signals Latest Version"
Set-Location -LiteralPath $root
$branch=(git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne "stage03-r2-offline-dev-candidate-sd23") {
 throw "WRONG_BRANCH"
}
git merge-base --is-ancestor 49767afae7564a8ed6e9084465eec2133d2123f8 HEAD
if ($LASTEXITCODE -ne 0) { throw "UNEXPECTED_BASELINE" }
git diff --quiet
if ($LASTEXITCODE -ne 0) { throw "TRACKED_WORKTREE_DIRTY" }
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw "STAGED_CHANGES_PRESENT" }
$env:PYTHONPATH=Join-Path $root "src"
$folder=Join-Path $root "_local_evidence\zs03-field"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$rights=Join-Path $folder "rights-attestation.json"

if ($Phase -eq "clock") {
 py -3.12 -m zs_smart_gate.stage03_field_clock
 if ($LASTEXITCODE -ne 0) { throw "CLOCK_PRECHECK_BLOCKED_NO_MARKET_GET" }
 return
}
if ($Phase -eq "rights") {
 Write-Host "REVIEW https://www.binance.com/en/about-legal/terms"
 Write-Host "REVIEW https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md"
 Write-Host "Historical Vision data terms do NOT automatically license live REST redistribution."
 Write-Host "This local attestation is ONLY for private noncommercial research and minimal local records."
 Write-Host "If rights or regional access are unclear, STOP."
 if (Test-Path -LiteralPath $rights) { throw "RIGHTS_FILE_EXISTS_NO_OVERWRITE" }
 $answer=Read-Host "Type I_ACCEPT_PRIVATE_RESEARCH_SCOPE only after personal terms review"
 if ($answer -cne "I_ACCEPT_PRIVATE_RESEARCH_SCOPE") { throw "RIGHTS_NOT_ATTESTED_NO_GET" }
 $obj=[ordered]@{
  schema="ZS03_RIGHTS_ATTESTATION_V1"
  data_host="data-api.binance.vision"
  scope="PRIVATE_NONCOMMERCIAL_RESEARCH"
  redistribution=$false
  commercial_use=$false
  operator_reviewed_terms=$true
  terms_url="https://www.binance.com/en/about-legal/terms"
  reviewed_at_utc=[DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
 }
 $data=$obj | ConvertTo-Json -Depth 5
 [System.IO.File]::WriteAllText($rights,$data,[System.Text.UTF8Encoding]::new($false))
 Write-Host "RIGHTS_FILE=$rights"
 Write-Host "RIGHTS_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $rights).Hash.ToLowerInvariant())"
 Write-Host "Not an independent legal certificate."
 return
}
if (-not (Test-Path -LiteralPath $rights)) { throw "RUN_RIGHTS_PHASE_FIRST" }
if ([string]::IsNullOrWhiteSpace($ParentOpenUtc)) { throw "PARENT_UTC_REQUIRED" }
try {
 $dt=[DateTimeOffset]::ParseExact($ParentOpenUtc,"yyyy-MM-ddTHH:mm:ssZ",
   [Globalization.CultureInfo]::InvariantCulture,
   [Globalization.DateTimeStyles]::AssumeUniversal).ToUniversalTime()
} catch { throw "PARENT_UTC_FORMAT_REQUIRED" }
$tag=$dt.ToString("yyyyMMddTHHmmZ")
$pre=Join-Path $folder "zs03-$tag-pre.json"
$post=Join-Path $folder "zs03-$tag-post.json"
if ($Phase -in @("pre","post")) {
 Write-Host "BTCUSDT SPOT public research: PRE=4 POST=6 GET, no retries/credentials/orders."
 $argv=@("--phase",$Phase,"--parent-open-utc",$ParentOpenUtc,
  "--evidence-dir",$folder,"--rights-scope","PRIVATE_NONCOMMERCIAL_RESEARCH",
  "--rights-attestation",$rights,"--manual-authorized")
 py -3.12 -m zs_smart_gate.stage03_windows_field_capture @argv
 if ($LASTEXITCODE -ne 0) { throw "FIELD_CAPTURE_BLOCKED_NO_RETRY" }
 return
}
if ($Phase -eq "review") {
 if (-not (Test-Path -LiteralPath $pre) -or -not (Test-Path -LiteralPath $post)) {
  throw "PRE_AND_POST_EVIDENCE_REQUIRED"
 }
 $argv=@("--pre",$pre,"--post",$post,"--rights-attestation",$rights)
 py -3.12 -m zs_smart_gate.stage03_windows_field_review @argv
 if ($LASTEXITCODE -ne 0) { throw "SOURCE_EVIDENCE_REVIEW_BLOCKED" }
 $out=Join-Path $folder "zs03-$tag-real-e2e.json"
 py -3.12 -m zs_smart_gate.stage03_field_real_e2e @argv --output $out
 if ($LASTEXITCODE -ne 0) { throw "REAL_RESEARCH_E2E_NOT_QUALIFIED" }
 Write-Host "LOCAL_PRIVATE_EVIDENCE_ONLY; STAGE03_CLOSED=false"
 return
}
throw "UNKNOWN_PHASE"
