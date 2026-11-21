<#
CLOCK74 exact-head offline acceptance on an isolated Windows checkout.
No install, restore of the active runtime, service change or market invocation.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ExpectedHead,
  [Parameter(Mandatory=$true)][string]$ExpectedTree,
  [string]$Source='',
  [string]$Output,
  [string]$Python='D:\ZS-SMART-GATE\.venv\Scripts\python.exe'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){
  throw 'WINDOWS_POWERSHELL_51_REQUIRED'
}
if(-not $Source){$Source=Split-Path $PSScriptRoot -Parent}
$owned='D:\ZS-SMART-GATE\'
foreach($value in @($Source,$Python)){
  if(-not [IO.Path]::GetFullPath($value).StartsWith($owned,[StringComparison]::OrdinalIgnoreCase)){
    throw 'D_PROJECT_PATH_REQUIRED'
  }
}
if(-not $Output){
  $Output=Join-Path $owned ('validation\CLOCK74-FINAL-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
}
if(-not [IO.Path]::GetFullPath($Output).StartsWith($owned,[StringComparison]::OrdinalIgnoreCase)){
  throw 'D_EVIDENCE_PATH_REQUIRED'
}
if(Test-Path -LiteralPath $Output){throw 'FRESH_OUTPUT_DIRECTORY_REQUIRED'}
$head=(& git -C $Source rev-parse HEAD | Out-String).Trim()
$tree=(& git -C $Source rev-parse 'HEAD^{tree}' | Out-String).Trim()
$before=(& git -C $Source status --porcelain | Out-String).Trim()
$version=(& $Python -c 'import platform; print(platform.python_version())' | Out-String).Trim()
if($head -cne $ExpectedHead -or $tree -cne $ExpectedTree -or $before){throw 'PIN_OR_CLEAN_CHECKOUT_MISMATCH'}
if($version -cne '3.12.10'){throw 'PYTHON_31210_REQUIRED'}
New-Item -ItemType Directory -Path $Output -ErrorAction Stop|Out-Null
$env:TEMP='D:\ZS-SMART-GATE\temp'
$env:TMP=$env:TEMP
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=Join-Path $Source 'src'
$started=[DateTime]::UtcNow.ToString('o')
$suites=@(
  'test_marketwide_capture','test_marketwide_research','test_order007_release',
  'test_p0_clock_72','test_p0_clock_73','test_ops_clock_recorded',
  'test_ops_windows_time','test_ops_windows_watchdog','test_clock74_acceptance'
)
$rows=@()
foreach($suite in $suites){
  $stdout=Join-Path $Output ($suite+'.stdout.raw.txt')
  $stderr=Join-Path $Output ($suite+'.stderr.raw.txt')
  $receipt=Join-Path $Output ($suite+'.result.json')
  $runner=Join-Path $Source 'scripts\clock74-offline-tests.py'
  $arguments=@('-B',('"'+$runner+'"'),$suite,'--receipt',('"'+$receipt+'"'))
  $proc=Start-Process -FilePath $Python -ArgumentList $arguments -WorkingDirectory $Source -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $timedOut=-not $proc.WaitForExit(120000)
  if($timedOut){
    & taskkill.exe /PID $proc.Id /T /F | Out-Null
    $proc.WaitForExit()
  }else{$proc.WaitForExit()}
  $exitCode=if($timedOut){124}elseif($null -eq $proc.ExitCode){-1}else{[int]$proc.ExitCode}
  $testResult=if(Test-Path -LiteralPath $receipt){Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json}else{$null}
  $rows+= [ordered]@{
    suite=$suite; exit=$exitCode; timed_out=$timedOut; result=$testResult
    stdout_sha256=(Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash.ToLowerInvariant()
    stderr_sha256=(Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}
$afterHead=(& git -C $Source rev-parse HEAD | Out-String).Trim()
$afterTree=(& git -C $Source rev-parse 'HEAD^{tree}' | Out-String).Trim()
$after=(& git -C $Source status --porcelain | Out-String).Trim()
$total=0; $passed=0; $failed=0; $errors=0; $skipped=0; $network=0; $success=$true
foreach($row in $rows){
  if($row.exit -ne 0 -or $null -eq $row.result){$success=$false}
  if($null -ne $row.result){
    $total+=$row.result.tests; $passed+=$row.result.passed; $failed+=$row.result.failures
    $errors+=$row.result.errors; $skipped+=$row.result.skipped; $network+=$row.result.python_network_attempts
    if(-not $row.result.success){$success=$false}
  }
}
$clean=($head -ceq $afterHead -and $tree -ceq $afterTree -and -not $after)
$summary=[ordered]@{
  schema='zs.clock74.final-windows-acceptance.v1'
  tested_head=$head; tested_tree=$tree; source_path=$Source
  started_utc=$started; finished_utc=[DateTime]::UtcNow.ToString('o')
  python=$version; powershell=$PSVersionTable.PSVersion.ToString()
  operating_system=(Get-CimInstance Win32_OperatingSystem).Caption
  clean_before=(!$before); clean_after=(!$after); unchanged_head_tree=$clean
  tests=$total; passed=$passed; failures=$failed; errors=$errors; skipped=$skipped
  python_network_attempts=$network; offline_only=$true
  suites=$rows; success=($success -and $clean -and $skipped -eq 0 -and $network -eq 0)
}
$summaryPath=Join-Path $Output 'acceptance.json'
[IO.File]::WriteAllText($summaryPath,($summary|ConvertTo-Json -Depth 12)+[Environment]::NewLine,[Text.UTF8Encoding]::new($false))
$manifest=@(Get-ChildItem -LiteralPath $Output -File | Sort-Object Name | ForEach-Object{
  (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()+'  '+$_.Name
})
[IO.File]::WriteAllText((Join-Path $Output 'SHA256SUMS'),($manifest -join [char]10)+[char]10,[Text.UTF8Encoding]::new($false))
Write-Output "CLOCK74_OFFLINE TESTS=$total PASS=$passed FAIL=$failed ERRORS=$errors SKIPPED=$skipped CLEAN=$clean NETWORK_ATTEMPTS=$network"
Write-Output "HEAD=$head TREE=$tree"
Write-Output "ACCEPTANCE_JSON=$summaryPath SHA256=$((Get-FileHash -LiteralPath $summaryPath -Algorithm SHA256).Hash.ToLowerInvariant())"
if(-not $summary.success){exit 1}
exit 0
