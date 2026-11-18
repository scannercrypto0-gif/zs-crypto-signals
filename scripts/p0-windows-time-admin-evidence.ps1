# P0 Windows Time: bounded elevated diagnostics only. NEVER a runtime clock permit.
# The raw redirected stdout/stderr bytes are hashed as captured; report.json is UTF-8.
[CmdletBinding()]
param(
  [ValidateScript({ $_ -ceq 'D:\ZS-SMART-GATE' })]
  [string]$Root = 'D:\ZS-SMART-GATE',
  [ValidateRange(1, 15)]
  [int]$TimeoutSeconds = 8
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-PlainDirectory([string]$Path) {
  $entry = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  if (-not $entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'UNTRUSTED_DIRECTORY_OR_REPARSE_POINT'
  }
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'ADMINISTRATOR_REQUIRED'
}
if ($Root -cne 'D:\ZS-SMART-GATE') { throw 'OWNED_ROOT_REQUIRED' }
if (-not (Test-Path -LiteralPath 'D:\' -PathType Container)) { throw 'D_DRIVE_REQUIRED' }
foreach ($path in @($Root, (Join-Path $Root 'state'), (Join-Path $Root 'validation'))) {
  Assert-PlainDirectory $path
}
if (-not (Test-Path -LiteralPath (Join-Path $Root 'state\DISABLED') -PathType Leaf)) {
  throw 'DISABLED_MARKER_REQUIRED'
}
if (Test-Path -LiteralPath (Join-Path $Root 'state\shadow.lock')) {
  throw 'SHADOW_LOCK_PRESENT'
}
$system32 = Join-Path $env:SystemRoot 'System32'
Assert-PlainDirectory $system32
$commands = @(
  @{name='service';exe=(Join-Path $system32 'sc.exe');args=@('query','W32Time')},
  @{name='status';exe=(Join-Path $system32 'w32tm.exe');args=@('/query','/status')},
  @{name='source';exe=(Join-Path $system32 'w32tm.exe');args=@('/query','/source')},
  @{name='configuration';exe=(Join-Path $system32 'w32tm.exe');args=@('/query','/configuration')},
  @{name='peers';exe=(Join-Path $system32 'w32tm.exe');args=@('/query','/peers')}
)
foreach ($item in $commands) {
  if (-not (Test-Path -LiteralPath $item.exe -PathType Leaf)) { throw 'ALLOWLIST_BINARY_NOT_FOUND' }
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$folder = Join-Path $Root ("validation\CLOCK-ADMIN-EVIDENCE-$stamp-$([Guid]::NewGuid().ToString('N').Substring(0,8))")
New-Item -ItemType Directory -Path $folder -ErrorAction Stop | Out-Null
$results = New-Object 'System.Collections.Generic.List[object]'
$utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($item in $commands) {
  $stdout = Join-Path $folder "$($item.name).stdout.txt"
  $stderr = Join-Path $folder "$($item.name).stderr.txt"
  [IO.File]::WriteAllText($stdout, '', $utf8)
  [IO.File]::WriteAllText($stderr, '', $utf8)
  $startedUtc = [DateTime]::UtcNow.ToString('o')
  $timer = [Diagnostics.Stopwatch]::StartNew()
  $process = $null
  $timedOut = $false
  $code = 127
  $failure = $null
  try {
    # Fixed, absolute binary allowlist. No user-supplied commands or shell expansion.
    $process = Start-Process -FilePath $item.exe -ArgumentList $item.args `
      -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ErrorAction Stop
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
      $timedOut = $true
      try { $process.Kill() } catch { $failure = 'KILL_FAILED' }
      if (-not $process.WaitForExit(2000)) { $failure = 'PROCESS_DID_NOT_TERMINATE' }
      $code = 124
    } else {
      $code = [int]$process.ExitCode
    }
  } catch {
    $failure = 'PROCESS_START_OR_WAIT_FAILED'
    if ($null -ne $process) {
      try { if (-not $process.HasExited) { $process.Kill(); [void]$process.WaitForExit(2000) } } catch {}
    }
    $code = 127
  } finally {
    $timer.Stop()
    if ($null -ne $process) { $process.Dispose() }
  }
  $record = [ordered]@{
    command = $item.name
    argv = @([IO.Path]::GetFileName($item.exe)) + @($item.args)
    started_utc = $startedUtc
    finished_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_ms = [int64]$timer.ElapsedMilliseconds
    timeout_seconds = $TimeoutSeconds
    timed_out = $timedOut
    exit = $code
    failure = $failure
    stdout_sha256 = (Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash.ToLowerInvariant()
    stderr_sha256 = (Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash.ToLowerInvariant()
    stdout_bytes = (Get-Item -LiteralPath $stdout).Length
    stderr_bytes = (Get-Item -LiteralPath $stderr).Length
  }
  [void]$results.Add([pscustomobject]$record)
  Write-Output "$($item.name): EXIT=$code TIMEOUT=$timedOut"
}
$failed = @($results | Where-Object { $_.exit -ne 0 -or $_.timed_out }).Count -gt 0
$report = [ordered]@{
  schema = 'zs.windows-time.admin-evidence.v2'
  captured_utc = [DateTime]::UtcNow.ToString('o')
  collector_identity_sid = $identity.User.Value
  elevated = $true
  result = $(if ($failed) { 'DIAGNOSTIC_FAILED_CLOSED' } else { 'ADMIN_DIAGNOSTIC_ONLY' })
  operational_policy_approved = $false
  runtime_witness_authorized = $false
  shadow_rerun = $false
  command_allowlist = 'WINDOWS_TIME_READ_ONLY_FIVE'
  commands = @($results.ToArray())
}
$path = Join-Path $folder 'report.json'
[IO.File]::WriteAllText($path, ($report | ConvertTo-Json -Depth 10 -Compress) + "`n", $utf8)
Write-Output "EVIDENCE_DIR=$folder"
Write-Output "REPORT_SHA256=$((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant())"
if ($failed) { throw 'WINDOWS_TIME_DIAGNOSTIC_FAILED_CLOSED' }
Write-Output 'ADMIN_QUERY_ACCESS_PASS; POLICY_UNAPPROVED; NO_RUNTIME_BRIDGE; NO_SHADOW'
