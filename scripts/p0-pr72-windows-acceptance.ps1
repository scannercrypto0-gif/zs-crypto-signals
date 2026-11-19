<# P0 Windows 5.1 / Python 3.12.10 diagnostics on exact PR72 HEAD/TREE.
Runs from a clean isolated D:\validation worktree, does NOT change installed release.
-CollectElevated triggers one interactive UAC prompt for read-only w32tm queries only.
Never approves clock policy, starts SHADOW, sends Telegram or schedules work.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedTree,
  [switch]$CollectElevated
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root='D:\ZS-SMART-GATE'
$repo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$utf8=[Text.UTF8Encoding]::new($false)
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$folder=Join-Path $root ('validation\P0-PR72-'+$stamp+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
$checks=[Collections.Generic.List[object]]::new()
$failures=[Collections.Generic.List[string]]::new()
$head=$null; $tree=$null; $pythonVersion=$null
$testExit=$null; $testCount=$null
$normalContext='UNKNOWN'; $elevated='NOT_REQUESTED'
$normalClockStatus='NOT_MEASURED'
function Hash([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function RunBounded([string]$Name,[string]$Exe,[string[]]$Argv,[int]$Seconds) {
  $out=Join-Path $folder ($Name+'.stdout.txt')
  $err=Join-Path $folder ($Name+'.stderr.txt')
  [IO.File]::WriteAllText($out,'',$utf8); [IO.File]::WriteAllText($err,'',$utf8)
  $p=$null; $code=127; $timeout=$false
  try {
    $p=Start-Process -FilePath $Exe -ArgumentList $Argv -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err -ErrorAction Stop
    if ($p.WaitForExit($Seconds*1000)) { $code=[int]$p.ExitCode }
    else {
      $timeout=$true; $code=124
      try { $p.Kill(); [void]$p.WaitForExit(2000) } catch {}
    }
  } catch {
    if ($null -ne $p) { try { if (-not $p.HasExited) { $p.Kill() } } catch {} }
    [IO.File]::AppendAllText($err,'PROCESS_LAUNCH_OR_WAIT_FAILED',$utf8)
  } finally {
    if ($null -ne $p) { $p.Dispose() }
  }
  $row=[ordered]@{name=$Name;exit=$code;timed_out=$timeout;timeout_seconds=$Seconds;stdout_sha256=(Hash $out);stderr_sha256=(Hash $err)}
  [void]$checks.Add([pscustomobject]$row)
  return $row
}
try {
  if (-not (Test-Path -LiteralPath (Join-Path $root 'state\DISABLED') -PathType Leaf) -or
      (Test-Path -LiteralPath (Join-Path $root 'state\shadow.lock'))) { throw 'DISABLED_NO_SHADOW_REQUIRED' }
  if (-not $repo.StartsWith((Join-Path $root 'validation')+'\',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'CLEAN_D_VALIDATION_WORKTREE_REQUIRED'
  }
  New-Item -ItemType Directory -Path $folder -ErrorAction Stop | Out-Null
  $head=(& git -C $repo rev-parse HEAD | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw 'BAD_GIT_HEAD' }
  $tree=(& git -C $repo rev-parse 'HEAD^{tree}' | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw 'BAD_GIT_TREE' }
  $dirty=(& git -C $repo status --porcelain | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $dirty -or $head -cne $ExpectedHead -or $tree -cne $ExpectedTree) {
    throw 'UNCLEAN_OR_UNPINNED_PR72_WORKTREE'
  }
  $python=Join-Path $root '.venv\Scripts\python.exe'
  $pythonVersion=(& $python -c 'import platform; print(platform.python_version())' | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.12.10') { throw 'EXACT_PYTHON_31210_REQUIRED' }
  $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
  $principal=[Security.Principal.WindowsPrincipal]::new($identity)
  $isAdmin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  $normalContext=$(if($isAdmin){'ADMIN_CONTEXT'}else{'NORMAL_USER_CONTEXT'})
  $env:PYTHONPATH=Join-Path $repo 'src'
  $env:PYTHONDONTWRITEBYTECODE='1'
  $test=RunBounded 'targeted-tests' $python @('-B','-m','unittest','discover','-s',(Join-Path $repo 'tests'),'-p','test_p0_clock_72.py','-v') 50
  $testExit=$test.exit
  $testStderr=Get-Content -LiteralPath (Join-Path $folder 'targeted-tests.stderr.txt') -Raw
  if ($testStderr -match 'Ran (\d+) tests') { $testCount=[int]$Matches[1] }
  # Existing direct clock and process-tree watchdog suites are scoped regression checks.
  foreach ($pattern in @('test_ops_windows_time.py','test_ops_windows_watchdog.py')) {
    $label=$pattern.Replace('.py','')
    $suite=RunBounded $label $python @('-B','-m','unittest','discover','-s',(Join-Path $repo 'tests'),'-p',$pattern,'-v') 50
    if ($suite.exit -ne 0) { [void]$failures.Add('REGRESSION_SUITE_FAILED_'+$label) }
  }
  $w32tm=Join-Path $env:SystemRoot 'System32\w32tm.exe'
  $normalClockStatus='NOT_MEASURED'
  foreach($what in @('source','configuration')) {
    $probe=RunBounded ('normal-'+$what) $w32tm @('/query',('/'+$what)) 8
    # w32tm can return EXIT=0 while stdout explicitly says Access Denied.
    # Preserve raw exit, but record an independent semantic result.
    $rawOut=[IO.File]::ReadAllText((Join-Path $folder ('normal-'+$what+'.stdout.txt')))
    $rawErr=[IO.File]::ReadAllText((Join-Path $folder ('normal-'+$what+'.stderr.txt')))
    $raw=$rawOut+[Environment]::NewLine+$rawErr
    $denied=[bool]($raw -match '(?i)(0x80070005|access[ ]+(?:is[ ]+)?denied)')
    $reportedError=[bool]($raw -match '(?i)(the following error occurred|0x[0-9a-f]{8})')
    $semantic=$(if($denied){'ACCESS_DENIED'}elseif($probe.exit -ne 0 -or $probe.timed_out -or $reportedError -or [string]::IsNullOrWhiteSpace($raw)){'COMMAND_UNVERIFIED'}else{'OUTPUT_RECEIVED_NOT_OPERATIONALLY_APPROVED'})
    if($semantic -eq 'ACCESS_DENIED'){$normalClockStatus='ACCESS_DENIED'}
    [void]$checks.Add([pscustomobject]@{
      name=('normal-'+$what+'-semantic')
      raw_exit=$probe.exit
      status=$semantic
      operationally_approved=$false
    })
    Write-Output "NORMAL_$($what.ToUpperInvariant())=$semantic RAW_EXIT=$($probe.exit)"
  }
  if (-not $isAdmin) {
    # Direct .NET ProcessStartInfo owns the child handle until ExitCode is read.
    # Start-Process -PassThru on Windows PowerShell 5.1 has returned a blank
    # ExitCode in owner evidence even after WaitForExit and Refresh.
    $denyScript=Join-Path $repo 'scripts\p0-windows-time-admin-evidence.ps1'
    $denyOut=Join-Path $folder 'nonadmin-collector.stdout.txt'
    $denyErr=Join-Path $folder 'nonadmin-collector.stderr.txt'
    $denyExit=$null
    $denyTimedOut=$false
    $denyProcess=$null
    $denyStdout=''
    $denyStderr=''
    try {
      $psi=[Diagnostics.ProcessStartInfo]::new()
      $psi.FileName=Join-Path $PSHOME 'powershell.exe'
      $psi.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$denyScript+'"'
      $psi.UseShellExecute=$false
      $psi.CreateNoWindow=$true
      $psi.RedirectStandardOutput=$true
      $psi.RedirectStandardError=$true
      $denyProcess=[Diagnostics.Process]::new()
      $denyProcess.StartInfo=$psi
      if (-not $denyProcess.Start()) { throw 'DENIAL_PROCESS_START_FAILED' }
      # Async readers avoid child-pipe deadlock; streams are small for denial.
      $outTask=$denyProcess.StandardOutput.ReadToEndAsync()
      $errTask=$denyProcess.StandardError.ReadToEndAsync()
      if (-not $denyProcess.WaitForExit(12000)) {
        $denyTimedOut=$true
        try { $denyProcess.Kill(); [void]$denyProcess.WaitForExit(2000) } catch {}
      } else {
        $denyProcess.WaitForExit()
        $denyExit=[int]$denyProcess.ExitCode
        $denyStdout=$outTask.GetAwaiter().GetResult()
        $denyStderr=$errTask.GetAwaiter().GetResult()
      }
    } catch {
      [void]$failures.Add('NONADMIN_COLLECTOR_PROCESS_CAPTURE_FAILED')
    } finally {
      if ($null -ne $denyProcess) { $denyProcess.Dispose() }
      [IO.File]::WriteAllText($denyOut,$denyStdout,$utf8)
      [IO.File]::WriteAllText($denyErr,$denyStderr,$utf8)
    }
    [void]$checks.Add([pscustomobject]@{
      name='nonadmin-collector'
      exit=$denyExit
      timed_out=$denyTimedOut
      timeout_seconds=12
      stdout_sha256=(Hash $denyOut)
      stderr_sha256=(Hash $denyErr)
    })
    if ($null -eq $denyExit -or $denyExit -ne 73 -or $denyTimedOut) {
      [void]$failures.Add('NONADMIN_COLLECTOR_DENIAL_EXIT_NOT_PROVEN')
    }
    if ($denyStderr -notmatch '(?m)^ADMINISTRATOR_REQUIRED\s*$') {
      [void]$failures.Add('NONADMIN_COLLECTOR_DENIAL_MARKER_NOT_PROVEN')
    }
  }
  if ($CollectElevated) {
    if ($isAdmin) { $elevated='ADMIN_CONTEXT_SPLIT_NOT_PROVEN' }
    else {
      $previous=@(Get-ChildItem -LiteralPath (Join-Path $root 'validation') -Directory -Filter 'CLOCK-ADMIN-EVIDENCE-*' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
      $collector=Join-Path $repo 'scripts\p0-windows-time-admin-evidence.ps1'
      $admin=$null
      try {
        $admin=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$collector+'"')) -PassThru -ErrorAction Stop
        if($admin.WaitForExit(65000)) { $elevated="ADMIN_EXIT_$($admin.ExitCode)" }
        else { $elevated='ADMIN_TIMEOUT';try{$admin.Kill();[void]$admin.WaitForExit(2000)}catch{} }
      } catch { $elevated='ADMIN_UAC_DECLINED_OR_START_FAILED' }
      finally {if($null -ne $admin){$admin.Dispose()}}
      $fresh=@(Get-ChildItem -LiteralPath (Join-Path $root 'validation') -Directory -Filter 'CLOCK-ADMIN-EVIDENCE-*' -ErrorAction SilentlyContinue | Where-Object { $previous -notcontains $_.FullName })
      if($fresh.Count -eq 1) {
        $manifest=Join-Path $fresh[0].FullName 'report.json'
        if(Test-Path -LiteralPath $manifest -PathType Leaf) {
          $data=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
          $valid=($data.schema -eq 'zs.windows-time.admin-evidence.v2' -and $data.elevated -eq $true -and $data.operational_policy_approved -eq $false -and $data.runtime_witness_authorized -eq $false -and @($data.commands).Count -eq 5)
          foreach($item in @($data.commands)) {
            foreach($stream in @('stdout','stderr')) {
              $file=Join-Path $fresh[0].FullName ($item.command+'.'+$stream+'.txt')
              $expected=$(if($stream -eq 'stdout'){$item.stdout_sha256}else{$item.stderr_sha256})
              if((Hash $file) -cne $expected){$valid=$false}
            }
          }
          $elevated+=$(if($valid){'_HASHES_VERIFIED'}else{'_HASHES_FAILED'})
          [void]$checks.Add([pscustomobject]@{name='admin-evidence';path=$manifest;sha256=(Hash $manifest);hashes_verified=$valid})
        }
      }
    }
  }
  if ($normalContext -ne 'NORMAL_USER_CONTEXT') {
    [void]$failures.Add('NORMAL_USER_PRIVILEGE_CONTEXT_NOT_VERIFIED')
  }
  if ($testExit -ne 0 -or $testCount -ne 12) {
    [void]$failures.Add('TARGETED_TESTS_NOT_ALL_PROVEN')
  }
  if ($CollectElevated -and $elevated -cne 'ADMIN_EXIT_0_HASHES_VERIFIED') {
    [void]$failures.Add('ELEVATED_COLLECTOR_NOT_VERIFIED')
  }
} catch { [void]$failures.Add([string]$_.Exception.Message) }
finally {
  if(-not(Test-Path -LiteralPath $folder)){New-Item -ItemType Directory -Path $folder -Force | Out-Null}
  $r=[ordered]@{
    schema='zs.p0.pr72.windows-local-acceptance.v1'
    created_utc=[DateTime]::UtcNow.ToString('o')
    expected_head=$ExpectedHead; observed_head=$head
    expected_tree=$ExpectedTree; observed_tree=$tree
    python=$pythonVersion; powershell=$PSVersionTable.PSVersion.ToString()
    normal_user=$normalContext; elevated_collector=$elevated
    normal_clock_status=$normalClockStatus
    targeted_tests_exit=$testExit; targeted_tests_discovered=$testCount
    checks=@($checks.ToArray());errors=@($failures.ToArray())
    clock_policy='NOT_INDEPENDENTLY_APPROVED';runtime_bridge='NOT_ESTABLISHED'
    shadow='NOT_RUN';scheduled='OFF';trading='OFF';telegram='OFF'
    outcome='P0_CLOCK_OPERATIONAL_BLOCKED'
  }
  $receipt=Join-Path $folder 'acceptance.json'
  [IO.File]::WriteAllText($receipt,($r | ConvertTo-Json -Depth 10 -Compress)+[Environment]::NewLine,$utf8)
  Write-Output "EVIDENCE_DIR=$folder"
  Write-Output "RECEIPT_SHA256=$(Hash $receipt)"
  Write-Output "HEAD=$head TREE=$tree PYTHON=$pythonVersion"
  Write-Output "TESTS_EXIT=$testExit COUNT=$testCount NORMAL=$normalContext ADMIN=$elevated"
  Write-Output "ERRORS=$($failures.Count) POLICY_UNAPPROVED SHADOW_NOT_RUN"
  foreach($entry in @($failures.ToArray())) { Write-Output "ERROR_DETAIL=$entry" }
}
if($failures.Count -gt 0 -or $testExit -ne 0 -or $head -cne $ExpectedHead -or
   $tree -cne $ExpectedTree -or $pythonVersion -ne '3.12.10') {
  throw 'P0_LOCAL_ACCEPTANCE_INCOMPLETE'
}
Write-Output 'P0_TARGETED_TESTS_FINISHED; OPERATIONAL_CLOCK_REMAINS_BLOCKED'
