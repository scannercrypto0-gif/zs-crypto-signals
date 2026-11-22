<# Finite scheduled-task diagnostic entry. All output remains on D:. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet('Probe','Health')][string]$Action,
 [Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(-not [IO.Path]::GetFullPath($Root).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_ROOT_REQUIRED'}
$env:PSModuleAnalysisCachePath=Join-Path $Root 'ps-module-analysis-cache'
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$env:PSModulePath=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\Modules'
$config=Get-Content (Join-Path $Root 'release.json') -Raw|ConvertFrom-Json
$worker=Join-Path $config.source 'scripts\ops24-worker.py'
$stdout=Join-Path $Root 'task.stdout.raw.txt';$stderr=Join-Path $Root 'task.stderr.raw.txt'
$process=Start-Process -FilePath $config.python -ArgumentList @('-I','-B',('"'+$worker+'"'),$Action,'--root',('"'+$Root+'"')) -WorkingDirectory $config.source -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$null=$process.Handle
if(-not $process.WaitForExit(60000)){& taskkill.exe /PID $process.Id /T /F|Out-Null;throw 'PROBE_PROCESS_TREE_TIMEOUT'}
$process.WaitForExit()
$code=if($null -eq $process.ExitCode){-1}else{[int]$process.ExitCode}
[IO.File]::WriteAllText((Join-Path $Root 'task.exit.txt'),[string]$code)
exit $code
