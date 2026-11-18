# Read-only, elevated Windows Time evidence. No service, policy or scheduler mutations.
[CmdletBinding()]
param([string]$Root = 'D:\ZS-SMART-GATE')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED' }
if ($Root -cne 'D:\ZS-SMART-GATE') { throw 'OWNED_ROOT_REQUIRED' }
if (-not (Test-Path -LiteralPath (Join-Path $Root 'state\DISABLED'))) { throw 'DISABLED_MARKER_REQUIRED' }
if (Test-Path -LiteralPath (Join-Path $Root 'state\shadow.lock')) { throw 'SHADOW_LOCK_PRESENT' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$folder = Join-Path $Root "validation\CLOCK-ADMIN-EVIDENCE-$stamp"
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$commands = @(
  @{name='service';exe='sc.exe';args=@('query','W32Time')},
  @{name='status';exe='w32tm.exe';args=@('/query','/status')},
  @{name='source';exe='w32tm.exe';args=@('/query','/source')},
  @{name='configuration';exe='w32tm.exe';args=@('/query','/configuration')},
  @{name='peers';exe='w32tm.exe';args=@('/query','/peers')}
)
$results = @()
foreach ($item in $commands) {
  $stdout = Join-Path $folder "$($item.name).stdout.txt"
  $stderr = Join-Path $folder "$($item.name).stderr.txt"
  $p = Start-Process -FilePath $item.exe -ArgumentList $item.args -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $results += [pscustomobject]@{
    command=$item.name; exit=$p.ExitCode
    stdout_sha256=(Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash.ToLowerInvariant()
    stderr_sha256=(Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  Write-Host "$($item.name): EXIT=$($p.ExitCode)"
}
$report = [ordered]@{
  schema='zs.windows-time.admin-evidence.v1'
  captured_utc=[DateTime]::UtcNow.ToString('o')
  elevated=$true
  operational_policy_approved=$false
  shadow_rerun=$false
  commands=$results
}
$path=Join-Path $folder 'report.json'
[IO.File]::WriteAllText($path,($report | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Host "EVIDENCE_DIR=$folder"
Write-Host "REPORT_SHA256=$((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant())"
if (@($results | Where-Object { $_.exit -ne 0 }).Count -gt 0) { throw 'WINDOWS_TIME_COMMAND_ACCESS_BLOCKED' }
Write-Host 'ADMIN_QUERY_ACCESS_PASS; OPERATIONAL_POLICY_STILL_BLOCKED; SHADOW_NOT_RERUN'
