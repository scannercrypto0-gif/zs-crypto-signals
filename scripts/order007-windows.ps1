<#
ORDER007 Windows-local release manager. Never enables unattended scheduling.
All owned state, repository, Python venv and logs remain on fixed partition D:.
Install is disabled. Shadow is one bounded, explicitly invoked foreground cycle.
#>
[CmdletBinding()]
param(
  [ValidateSet('Install','Upgrade','Verify','StartForeground','Status','Stop','Disable','Uninstall','Restore','Rollback')]
  [string]$Action = 'Status',
  [string]$Root = 'D:\ZS-SMART-GATE',
  [string]$Commit,
  [string]$ExpectedTree,
  [switch]$LiveReadOnly,
  [switch]$AdminClockPilot
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-DLocation([string]$Value) {
  if ($Value -notmatch '^[dD]:\\' -or $Value -match '[\r\n]') {
    throw 'D_ONLY_ABSOLUTE_PATH_REQUIRED'
  }
  $full = [IO.Path]::GetFullPath($Value).TrimEnd('\')
  if (-not ($full -ieq 'D:' -or $full -imatch '^D:\\ZS-SMART-GATE($|\\)')) {
    throw 'ORDER007_OWNED_ROOT_REQUIRED'
  }
  $drive = Get-PSDrive -Name D -ErrorAction Stop
  if (-not (Test-Path 'D:\' -PathType Container)) { throw 'D_DRIVE_MISSING' }
  $part = $full
  while ($part -and (Test-Path -LiteralPath $part)) {
    if ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
      throw 'REPARSE_POINT_REJECTED'
    }
    $next = Split-Path -Path $part -Parent
    if ($next -eq $part) { break }
    $part = $next
  }
  return $full
}
function Hash-File([string]$Path) {
  (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Write-Record([string]$Path, $Object) {
  $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Object | ConvertTo-Json -Depth 12 -Compress) + "`n")
  $temp = "$Path.tmp.$PID"
  [IO.File]::WriteAllBytes($temp, $bytes)
  Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Get-Pin([string]$Directory) {
  $file = Join-Path $Directory 'state\installed.json'
  if (-not (Test-Path -LiteralPath $file)) { throw 'NO_INSTALLED_RELEASE' }
  $pin = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
  if ($pin.schema -ne 'zs.order007.windows-release.v1' -or $pin.mode -ne 'DISABLED' -or
      $pin.head -notmatch '^[a-f0-9]{40}$' -or $pin.tree -notmatch '^[a-f0-9]{40}$') {
    throw 'BAD_RELEASE_MANIFEST'
  }
  return $pin
}
function Assert-Checkout([string]$Directory, $Pin) {
  $repo = Join-Path $Directory 'repo'
  if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) { throw 'REPO_MISSING' }
  $head = ((& git -C $repo rev-parse HEAD) | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $head -ne $Pin.head) { throw 'RELEASE_HEAD_MISMATCH' }
  $tree = ((& git -C $repo rev-parse 'HEAD^{tree}') | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $tree -ne $Pin.tree) { throw 'RELEASE_TREE_MISMATCH' }
  $dirty = ((& git -C $repo status --porcelain) | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'UNCLEAN_RELEASE_CHECKOUT' }
}
$Root = Assert-DLocation $Root
if ($Root -ine 'D:\ZS-SMART-GATE') { throw 'CUSTOM_ROOT_NOT_SUPPORTED_BY_RELEASE_V1' }
$paths = @('repo','.venv','state','data','logs','cache','temp','backups','validation','config','outbox')
$releaseFile = Join-Path $Root 'state\installed.json'
$disabledFile = Join-Path $Root 'state\DISABLED'
$lockFile = Join-Path $Root 'state\shadow.lock'
$stopFile = Join-Path $Root 'state\STOP_REQUESTED'
$python = Join-Path $Root '.venv\Scripts\python.exe'
$repoPath = Join-Path $Root 'repo'

if ($Action -eq 'Install') {
  if ($Commit -notmatch '^[a-f0-9]{40}$' -or $ExpectedTree -notmatch '^[a-f0-9]{40}$') {
    throw 'EXACT_COMMIT_AND_TREE_REQUIRED'
  }
  if (Test-Path -LiteralPath $releaseFile) { throw 'RELEASE_ALREADY_INSTALLED_USE_VERIFY' }
  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  foreach ($p in $paths) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $p) | Out-Null }
  if (-not (Test-Path -LiteralPath (Join-Path $repoPath '.git'))) {
    & git clone --no-checkout 'https://github.com/scannercrypto0-gif/zs-crypto-signals.git' $repoPath
    if ($LASTEXITCODE -ne 0) { throw 'CLONE_FAILED' }
  }
  & git -C $repoPath fetch origin $Commit
  if ($LASTEXITCODE -ne 0) { throw 'FETCH_FAILED' }
  & git -C $repoPath checkout --detach $Commit
  if ($LASTEXITCODE -ne 0) { throw 'CHECKOUT_FAILED' }
  $actual = ((& git -C $repoPath rev-parse 'HEAD^{tree}') | Out-String).Trim()
  if ($actual -ne $ExpectedTree) { throw 'TREE_MISMATCH' }
  $dirty = ((& git -C $repoPath status --porcelain) | Out-String).Trim()
  if ($dirty) { throw 'DIRTY_CHECKOUT' }
  $env:TEMP = Join-Path $Root 'temp'
  $env:TMP = $env:TEMP
  $env:PIP_CACHE_DIR = Join-Path $Root 'cache'
  & py -3.12 -m venv (Join-Path $Root '.venv')
  if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_VENV_FAILED' }
  $version = ((& $python -c 'import platform; print(platform.python_version())') | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $version -ne '3.12.10') { throw 'PYTHON_3_12_10_REQUIRED' }
  # Uses the source checkout directly via PYTHONPATH; does not download
  # unpinned PyPI packages or install anything on C:.
  Write-Record $releaseFile ([ordered]@{
    schema='zs.order007.windows-release.v1'; head=$Commit; tree=$ExpectedTree
    python=$version; mode='DISABLED'; created_utc=[DateTime]::UtcNow.ToString('o')
    external_effects='OFF'; unattended='OFF'; storage='D_ONLY'
  })
  [IO.File]::WriteAllText($disabledFile, 'DISABLED')
  Write-Output "INSTALL_DISABLED HEAD=$Commit TREE=$ExpectedTree PYTHON=$version ROOT=$Root"
  return
}
if ($Action -eq 'Upgrade') {
  # Upgrade an already disabled release to a descendent exact HEAD/TREE.
  # Preserve local data and retain the prior installed manifest with SHA-256.
  $previous = Get-Pin $Root
  if ($Commit -notmatch '^[a-f0-9]{40}$' -or $ExpectedTree -notmatch '^[a-f0-9]{40}$') {
    throw 'UPGRADE_EXACT_COMMIT_AND_TREE_REQUIRED'
  }
  if (-not (Test-Path -LiteralPath $disabledFile) -or (Test-Path -LiteralPath $lockFile)) {
    throw 'UPGRADE_REQUIRES_DISABLED_NO_WORKER'
  }
  $oldTree = ((& git -C $repoPath rev-parse "$($previous.head)^{tree}") | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $oldTree -ne $previous.tree) {
    throw 'PRIOR_INSTALL_GIT_OBJECT_MISMATCH'
  }
  $newHead = ((& git -C $repoPath rev-parse HEAD) | Out-String).Trim()
  $newTree = ((& git -C $repoPath rev-parse 'HEAD^{tree}') | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $newHead -ne $Commit -or $newTree -ne $ExpectedTree) {
    throw 'UPGRADE_TARGET_HEAD_TREE_MISMATCH'
  }
  $dirty = ((& git -C $repoPath status --porcelain) | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'UPGRADE_DIRTY_CHECKOUT' }
  & git -C $repoPath merge-base --is-ancestor $previous.head $Commit
  if ($LASTEXITCODE -ne 0) { throw 'UPGRADE_NON_DESCENDANT_FORBIDDEN' }
  $version = ((& $python -c 'import platform; print(platform.python_version())') | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $version -ne '3.12.10') {
    throw 'UPGRADE_REQUIRES_EXISTING_D_PYTHON_3_12_10'
  }
  if (-not (Test-Path -LiteralPath (Join-Path $Root 'backups'))) {
    throw 'BACKUP_DIRECTORY_MISSING'
  }
  $backup = Join-Path $Root ('backups\release-before-upgrade-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $previous.head.Substring(0,12) + '.json')
  Copy-Item -LiteralPath $releaseFile -Destination $backup -ErrorAction Stop
  $backupHash = Hash-File $backup
  if ($backupHash -ne (Hash-File $releaseFile)) {
    throw 'PRIOR_RELEASE_BACKUP_HASH_MISMATCH'
  }
  Write-Record $releaseFile ([ordered]@{
    schema='zs.order007.windows-release.v1'; head=$Commit; tree=$ExpectedTree
    python=$version; mode='DISABLED'; created_utc=$previous.created_utc
    upgraded_utc=[DateTime]::UtcNow.ToString('o')
    previous_head=$previous.head; previous_tree=$previous.tree
    previous_release_sha256=$backupHash
    external_effects='OFF'; unattended='OFF'; storage='D_ONLY'
  })
  Assert-Checkout $Root (Get-Pin $Root)
  Write-Output "UPGRADE_DISABLED HEAD=$Commit TREE=$ExpectedTree PREVIOUS=$($previous.head) BACKUP=$backup BACKUP_SHA256=$backupHash"
  return
}
if ($Action -eq 'Stop') {
  if (-not (Test-Path -LiteralPath (Join-Path $Root 'state'))) { return }
  [IO.File]::WriteAllText($stopFile, [DateTime]::UtcNow.ToString('o'))
  Write-Output 'STOP_REQUESTED: shadow checks before each public GET; request timeout 8s and process-tree watchdog 120s. Ctrl+C is also supported.'
  return
}
if ($Action -eq 'Disable') {
  if (-not (Test-Path -LiteralPath (Join-Path $Root 'state'))) { throw 'NOT_INSTALLED' }
  [IO.File]::WriteAllText($disabledFile, 'DISABLED')
  [IO.File]::WriteAllText($stopFile, [DateTime]::UtcNow.ToString('o'))
  Write-Output 'DISABLED: no unattended task is installed by ORDER007 v1'
  return
}
if ($Action -eq 'Uninstall') {
  if (Test-Path -LiteralPath $lockFile) { throw 'WORKER_LOCK_PRESENT_REFUSING_UNINSTALL' }
  if (Test-Path -LiteralPath $releaseFile) {
    $pin = Get-Pin $Root
    [IO.File]::WriteAllText($disabledFile, 'DISABLED')
    Move-Item -LiteralPath $releaseFile -Destination (Join-Path $Root ('backups\uninstalled-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json'))
  }
  # No deletion: owner data, D: venv and evidence retained for manual audit.
  Write-Output 'UNINSTALLED_DISABLED_MANIFEST_ARCHIVED; OWNER_DATA_RETAINED'
  return
}
$pin = Get-Pin $Root
if ($Action -eq 'Status') {
  [ordered]@{
    utc=[DateTime]::UtcNow.ToString('o'); head=$pin.head; tree=$pin.tree
    installed=$true; enabled=$false; scheduled=$false
    foreground_running=(Test-Path -LiteralPath $lockFile)
    disabled=(Test-Path -LiteralPath $disabledFile)
    stop_requested=(Test-Path -LiteralPath $stopFile)
    recent_results=@(Get-ChildItem -Path (Join-Path $Root 'data') -Filter 'result.json' -Recurse -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 3 -ExpandProperty FullName)
    clock='NOT_INDEPENDENTLY_APPROVED'; production='OFF'; telegram='OFF'; sql='DEFERRED'
  } | ConvertTo-Json -Depth 6
  return
}
Assert-Checkout $Root $pin
if ($Action -in @('Restore','Rollback')) {
  if (Test-Path -LiteralPath $lockFile) { throw 'WORKER_LOCK_PRESENT' }
  & git -C $repoPath fsck --no-reflogs --connectivity-only
  if ($LASTEXITCODE -ne 0) { throw 'RESTORE_GIT_OBJECT_INTEGRITY_FAILED' }
  # Git normally writes a benign "HEAD is now at ..." on stderr.
  # PowerShell 5.1 redirects it into a terminating NativeCommandError when
  # acceptance captures all streams with ErrorActionPreference=Stop.
  # Quiet checkout suppresses only Git status text, never a genuine error.
  & git -C $repoPath checkout --quiet --detach $pin.head
  if ($LASTEXITCODE -ne 0) { throw 'RESTORE_FAILED' }
  Assert-Checkout $Root $pin
  Write-Output "RESTORE_VERIFIED HEAD=$($pin.head) TREE=$($pin.tree)"
  return
}
if ($Action -eq 'Verify') {
  if (-not (Test-Path -LiteralPath $python)) { throw 'D_VENV_MISSING' }
  $version = ((& $python -c 'import platform; print(platform.python_version())') | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $version -ne '3.12.10') { throw 'PYTHON_3_12_10_REQUIRED' }
  Write-Output "VERIFY_PASS HEAD=$($pin.head) TREE=$($pin.tree) PYTHON=$version ENABLED=FALSE"
  return
}
if ($Action -eq 'StartForeground') {
  if ($AdminClockPilot) {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
      throw 'CLOCK_PILOT_ADMIN_CONTEXT_REQUIRED'
    }
  }
  if (-not $LiveReadOnly) { throw 'EXPLICIT_LIVE_READ_ONLY_SWITCH_REQUIRED' }
  if (-not (Test-Path -LiteralPath $disabledFile)) { throw 'DISABLED_INSTALL_MARKER_REQUIRED' }
  if (Test-Path -LiteralPath $lockFile) { throw 'SHADOW_LOCK_PRESENT_STOP_OR_INVESTIGATE' }
  # Operator-visible 30m entry check before any child starts or public GET.
  # This cannot guarantee downstream readiness: discovery may exceed the
  # remaining 90-second window, in which case the Python scan stops safely.
  $utcNow=[DateTimeOffset]::UtcNow
  $epochMs=$utcNow.ToUnixTimeMilliseconds()
  $boundaryMs=[long]([math]::Floor($epochMs / 1800000) * 1800000)
  $ageSeconds=($epochMs - $boundaryMs) / 1000.0
  $remainingSeconds=[math]::Max(0.0, 90.0 - $ageSeconds)
  Write-Output ("CANDLE_ENTRY_PREFLIGHT BOUNDARY_MS={0} AGE_SECONDS={1:F3} REMAINING_SECONDS={2:F3}" -f $boundaryMs,$ageSeconds,$remainingSeconds)
  if ($ageSeconds -gt 90.0 -or $ageSeconds -lt 0.0) {
    Write-Output 'CANDLE_ENTRY_PREFLIGHT_BLOCKED_NO_PUBLIC_GETS'
    throw 'CANDLE_ENTRY_WINDOW_EXPIRED_BEFORE_LAUNCH'
  }
  if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
  $env:PYTHONPATH = (Join-Path $Root 'repo\src')
  $env:TEMP = Join-Path $Root 'temp'
  $env:TMP = $env:TEMP
  $env:PYTHONDONTWRITEBYTECODE = '1'
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $dest = Join-Path $Root ("data\shadow-$stamp-$PID")
  # order006 watchdog creates the output directory itself, fail closed if it exists.
  if (Test-Path -LiteralPath $dest) { throw 'FRESH_SHADOW_OUTPUT_REQUIRED' }
  try {
    [IO.File]::WriteAllText($lockFile, "pid=$PID `nstarted=$([DateTime]::UtcNow.ToString('o'))")
    Push-Location $repoPath
    try {
      # Existing Windows process-tree watchdog enforces 120-second maximum.
      $shadowArgs=@('-B','scripts/order007-shadow.py','--live-read-only','--root',$Root,'--output',$dest)
      if ($AdminClockPilot) { $shadowArgs += '--admin-clock-pilot' }
      & $python @shadowArgs
      $code = $LASTEXITCODE
    } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    Write-Record (Join-Path $dest 'foreground-exit.json') @{
      utc=[DateTime]::UtcNow.ToString('o'); head=$pin.head; tree=$pin.tree
      exit_code=$code; mode='PUBLIC_READ_ONLY_SHADOW'; admin_clock_pilot=[bool]$AdminClockPilot
      qualification='BLOCKED_UNTIL_SCIENTIFIC_AND_CLOCK_ACCEPTANCE'
    }
    Write-Output "SHADOW_FOREGROUND_EXIT=$code DATA=$dest"
    # Concise receipt only; never stream the giant private snapshot.
    $summaryPath=Join-Path $dest 'result.json'
    if (Test-Path -LiteralPath $summaryPath -PathType Leaf) {
      try {
        $summary=Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
        $stopReason=$summary.stop
        if (-not $stopReason -and $null -ne $summary.funnel) {
          $stopReason=$summary.funnel.stopped_reason
        }
        if (-not $stopReason) { $stopReason='NONE_RECORDED' }
        Write-Output "SHADOW_STOP_REASON=$stopReason"
        if ($null -ne $summary.boundary_preflight) {
          $bp=$summary.boundary_preflight
          Write-Output "CANDLE_WINDOW=$($bp.status) BOUNDARY_MS=$($bp.boundary_ms) AGE_SECONDS=$($bp.age_seconds) REMAINING_SECONDS=$($bp.remaining_seconds)"
        }
        if ($null -ne $summary.funnel) {
          Write-Output "MARKET_ELIGIBLE=$($summary.funnel.eligible) ATTEMPTED=$($summary.funnel.attempted) COVERAGE_PCT=$($summary.funnel.coverage_pct)"
        }
        Write-Output "PUBLIC_GETS=$($summary.requests) ESTIMATED_WEIGHT=$($summary.estimated_weight) OBSERVED_USED_WEIGHT=$($summary.observed_used_weight)"
      } catch {
        Write-Output 'SHADOW_SUMMARY_UNREADABLE_FAIL_CLOSED'
      }
    } else {
      Write-Output 'SHADOW_RESULT_MISSING'
    }
    if ($code -ne 0) { throw "SHADOW_PARTIAL_OR_STOP_EXIT=$code" }
  } finally {
    if (Test-Path -LiteralPath $lockFile) { Remove-Item -LiteralPath $lockFile -Force }
  }
  return
}
throw 'UNSUPPORTED_ACTION'
