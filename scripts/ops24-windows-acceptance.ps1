<# OPS24 exact-head Windows acceptance; only affected suites plus CLOCK74 regression. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExpectedHead,
 [Parameter(Mandatory=$true)][string]$ExpectedTree,
 [Parameter(Mandatory=$true)][string]$Output,
 [string]$Dependencies='',
 [string]$Source=''
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if(-not $Source){$Source=Split-Path $PSScriptRoot -Parent}
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'POWERSHELL_51_REQUIRED'}
foreach($path in @($Source,$Output)){if(-not [IO.Path]::GetFullPath($path).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_PROJECT_PATH_REQUIRED'}}
if($Dependencies -and -not($Dependencies -match '^[dD]:\\')){throw 'D_DEPENDENCIES_REQUIRED'}
$head=(& git -C $Source rev-parse HEAD|Out-String).Trim()
$tree=(& git -C $Source rev-parse 'HEAD^{tree}'|Out-String).Trim()
if($head -cne $ExpectedHead -or $tree -cne $ExpectedTree -or (& git -C $Source status --porcelain)){throw 'SOURCE_PIN_OR_CLEAN_MISMATCH'}
$python='D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe'
if(((& $python -c 'import platform; print(platform.python_version())')|Out-String).Trim() -cne '3.12.10'){throw 'PYTHON_31210_REQUIRED'}
if(Test-Path $Output){throw 'FRESH_OUTPUT_REQUIRED'}
New-Item -ItemType Directory -Path $Output|Out-Null
$env:TEMP='D:\ZS-SMART-GATE\temp'; $env:TMP=$env:TEMP
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path $Source 'src')+$(if($Dependencies){';'+$Dependencies}else{''})
$suites=@('test_ops24','test_ops24_runtime','test_ops24_normal_clock','test_ops24_intervals','test_ops24_authority','test_ops24_control',
 'test_marketwide_capture.MarketCaptureTests.test_exact_eleventh_http_receipt_accepted_twelfth_forbidden')
$rows=@()
$started=[DateTime]::UtcNow.ToString('o')
foreach($suite in $suites){
 $name=$suite.Replace('.','_')
 $stdout=Join-Path $Output ($name+'.stdout.raw.txt'); $stderr=Join-Path $Output ($name+'.stderr.raw.txt')
 $receipt=Join-Path $Output ($name+'.json')
 $runner=Join-Path $Source 'scripts\clock74-offline-tests.py'
 $p=Start-Process $python -ArgumentList @('-B',('"'+$runner+'"'),$suite,'--receipt',('"'+$receipt+'"')) -WindowStyle Hidden -WorkingDirectory $Source -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 $null=$p.Handle
 $timedOut=-not $p.WaitForExit(180000)
 if($timedOut){& taskkill.exe /PID $p.Id /T /F|Out-Null}
 $p.WaitForExit()
 $code=if($timedOut){124}elseif($null -eq $p.ExitCode){-1}else{[int]$p.ExitCode}
 $result=if(Test-Path $receipt){Get-Content $receipt -Raw|ConvertFrom-Json}else{$null}
 $rows+=[ordered]@{suite=$suite;exit=$code;result=$result;stdout_sha256=(Get-FileHash $stdout).Hash.ToLowerInvariant();stderr_sha256=(Get-FileHash $stderr).Hash.ToLowerInvariant()}
}
$clean=(-not(& git -C $Source status --porcelain)) -and $head -ceq ((& git -C $Source rev-parse HEAD)|Out-String).Trim()
$total=0; $failed=0; $errors=0; $skips=0; $network=0; $ok=$clean
foreach($row in $rows){
 if($row.exit -ne 0 -or $null -eq $row.result){$ok=$false}
 if($null -ne $row.result){
  $total+=$row.result.tests; $failed+=$row.result.failures; $errors+=$row.result.errors
  $skips+=$row.result.skipped; $network+=$row.result.python_network_attempts
  if(-not $row.result.success){$ok=$false}
 }
}
$report=[ordered]@{schema='zs.ops24.windows-acceptance.v1';head=$head;tree=$tree;clean=$clean;python='3.12.10';powershell=$PSVersionTable.PSVersion.ToString();started_utc=$started;finished_utc=[DateTime]::UtcNow.ToString('o');tests=$total;failures=$failed;errors=$errors;skipped=$skips;network_attempts=$network;suites=$rows;success=$ok}
[IO.File]::WriteAllText((Join-Path $Output 'acceptance.json'),($report|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
Write-Output "OPS24 TESTS=$total FAILURES=$failed ERRORS=$errors SKIPS=$skips NETWORK=$network SUCCESS=$ok"
Write-Output "HEAD=$head TREE=$tree OUTPUT=$Output"
if(-not $ok){exit 1}
