#Requires -Version 7.0
param([Parameter(Mandatory)][string]$Manifest,[Parameter(Mandatory)][long]$ReviewCommentId,
      [string]$RunRoot='D:\ZS-SMART-GATE\order020-preflight\field-runtime',
      [string]$Venv='D:\ZS-SMART-GATE\order020-preflight\.venv')
$ErrorActionPreference='Stop'
foreach($p in @($Manifest,$RunRoot,$Venv)) {
    if(-not [IO.Path]::IsPathFullyQualified($p) -or [IO.Path]::GetPathRoot($p) -ne 'D:\' -or $p.Contains('"')) {
        throw 'D_ONLY_ABSOLUTE_PATHS_REQUIRED'
    }
}
if($ReviewCommentId -le 0){throw 'INDEPENDENT_PM_REVIEW_REQUIRED'}
New-Item -ItemType Directory -Path "$RunRoot\temp" -Force | Out-Null
$env:TEMP="$RunRoot\temp"; $env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path "$PSScriptRoot\..\src").Path
$env:PYTHONPYCACHEPREFIX="$RunRoot\pycache"
$env:GIT_TERMINAL_PROMPT='0';$env:GCM_INTERACTIVE='never'
$args020='"'+(Join-Path $PSScriptRoot 'run-020-once.py')+'" --manifest "'+$Manifest+'" --workspace "'+$RunRoot+'" --review-comment-id '+$ReviewCommentId
$p020=Start-Process -FilePath "$Venv\Scripts\pythonw.exe" -ArgumentList $args020 -WindowStyle Hidden -PassThru `
    -WorkingDirectory (Resolve-Path "$PSScriptRoot\..").Path `
    -RedirectStandardOutput "$RunRoot\stdout.txt" -RedirectStandardError "$RunRoot\stderr.txt"
try { Wait-Process -Id $p020.Id -Timeout 720 -ErrorAction Stop }
catch { if(Get-Process -Id $p020.Id -ErrorAction SilentlyContinue){Stop-Process -Id $p020.Id -Force}; throw 'ONE_SHOT_SUPERVISOR_LIMIT_NO_RETRY' }
# No schedule/service and no automatic second launch. CANCEL sentinel stops
# the native loop; a consumed attempt remains consumed even after an error.
