[CmdletBinding()]
param(
    [ValidateSet('Plan','Install','Enable','Disable','Status','Stop','Uninstall')][string]$Action='Plan',
    [string]$PythonPath='D:\ZS-SMART-GATE\.venv\Scripts\pythonw.exe',
    [string]$WorkingDirectory='D:\ZS-SMART-GATE\repo',
    [string]$StateDirectory='D:\ZS-SMART-GATE\runtime',
    [string]$LogDirectory='D:\ZS-SMART-GATE\logs',
    [string]$ConfigPath='D:\ZS-SMART-GATE\runtime\deployment.json',
    [string]$ConfigSha,
    [string]$TaskName='ZS-WindowsRunner-Independent-Simulation',
    [ValidateRange(1,1440)][int]$IntervalMinutes=1,
    [ValidateRange(1,168)][int]$DurationHours=24,
    [switch]$OptIn
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'windows-storage.ps1')
$taskPath='\ZS-Offline-Pilot\'
$marker='ZS independent simulation-only runner v2; no LIVE transport'
if ($TaskName -notmatch '^ZS-WindowsRunner-[A-Za-z0-9-]+$') { throw 'Dedicated task name required' }
$existing=Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -ne $marker) { throw 'Refusing unknown task' }
if ($Action -in @('Stop','Disable','Uninstall')) {
    if ($existing) {
        Disable-ScheduledTask -InputObject $existing | Out-Null
        Stop-ScheduledTask -InputObject $existing
        if ($Action -eq 'Uninstall') { Unregister-ScheduledTask -InputObject $existing -Confirm:$false }
    }
    return
}
$PythonPath=Assert-DPath $PythonPath
if([IO.Path]::GetFileName($PythonPath) -ne 'pythonw.exe') { throw 'NO_CONSOLE_PYTHONW_REQUIRED' }
$WorkingDirectory=Assert-DPath $WorkingDirectory
$StateDirectory=Assert-DPath $StateDirectory
$LogDirectory=Assert-DPath $LogDirectory
if ($Action -eq 'Status') {
    $info=if($existing){ Get-ScheduledTaskInfo -InputObject $existing }
    $record=Join-Path $LogDirectory 'status.json'
    $last=if((Test-Path -LiteralPath $record) -and (Get-Item -LiteralPath $record).Length -le 65536){ Get-Content -LiteralPath $record -Raw | ConvertFrom-Json }
    $clockFile=Join-Path $StateDirectory 'clock-proof.json'
    $clockRecord=if((Test-Path -LiteralPath $clockFile) -and (Get-Item -LiteralPath $clockFile).Length -le 65536){ Get-Content -LiteralPath $clockFile -Raw | ConvertFrom-Json }
    [ordered]@{utc=[DateTime]::UtcNow.ToString('o'); taskState=if($existing){$existing.State.ToString()}else{'NOT_INSTALLED'};
        lastTaskResult=if($info){$info.LastTaskResult}; lastTickUtc=if($info){$info.LastRunTime.ToUniversalTime().ToString('o')};
        nextTickUtc=if($info){$info.NextRunTime.ToUniversalTime().ToString('o')};
        w32TimeStatus=(Get-Service W32Time).Status.ToString(); timeSource=(& w32tm /query /source 2>&1 | Out-String).Trim();
        timeDetails=(& w32tm /query /status /verbose 2>&1 | Out-String).Trim();
        recordedOsClockProof=$clockRecord; recordedClockProofAgeSeconds=if($clockRecord){([DateTimeOffset]::UtcNow-([DateTimeOffset]$clockRecord.measuredUtc)).TotalSeconds};
        latestDiagnostic=$last; livePermission='OFF'; evidence='DURABLE_GITHUB_EVIDENCE_PENDING';
        production='PRODUCTION_SIGNALS_NOT_AUTHORIZED'; scope=@(); stability='NO_24_7_CLAIM'} | ConvertTo-Json -Depth 12
    return
}
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path (Split-Path $PythonPath)) 'pyvenv.cfg'))) { throw 'D venv required' }
$entry=Assert-DPath (Join-Path $WorkingDirectory 'scripts/windows-tick.py')
if ($ConfigSha -notmatch '^[a-f0-9]{64}$') { throw 'Frozen ConfigSha required' }
$ConfigPath=Assert-DPath $ConfigPath
foreach($p in @($PythonPath,$WorkingDirectory,$entry,$ConfigPath,$StateDirectory,$LogDirectory)) {
    if($p.Contains('"') -or $p.Contains([char]10) -or $p.Contains([char]13)) { throw 'Invalid path characters' }
}
$arguments='-B "{0}" --config "{1}" --config-sha {2} --state-dir "{3}" --log-dir "{4}" --dry-run --once' -f $entry,$ConfigPath,$ConfigSha,$StateDirectory,$LogDirectory
$taskAction=New-ScheduledTaskAction -Execute $PythonPath -Argument $arguments -WorkingDirectory $WorkingDirectory
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Hours $DurationHours)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 30) -Disable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$definition=New-ScheduledTask -Action $taskAction -Trigger $trigger -Settings $settings -Principal $principal -Description $marker
if($Action -eq 'Plan') { $definition; return }
if(-not $OptIn) { throw 'Explicit -OptIn required' }
if($existing) {
    $xml=[xml](Export-ScheduledTask -InputObject $existing)
    if($xml.Task.Actions.Exec.Command -ne $PythonPath -or $xml.Task.Actions.Exec.WorkingDirectory -ne $WorkingDirectory -or $xml.Task.Actions.Exec.Arguments -ne $arguments -or $existing.Settings.MultipleInstances -ne 2) { throw 'Configuration differs; disable/uninstall then install reviewed configuration' }
}
if($Action -eq 'Install') {
    if(-not $existing) { Register-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -InputObject $definition | Out-Null }
    return
}
if(-not $existing) { throw 'Install before Enable' }
if((Get-Service W32Time).Status -ne 'Running') { throw 'CLOCK_UNTRUSTED' }
if(-not (Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled) { throw 'TASK_HISTORY_REQUIRED' }
$proofPath=Assert-DPath (Join-Path $StateDirectory 'clock-proof.json')
$proof=Get-Content -LiteralPath $proofPath -Raw | ConvertFrom-Json
$age=([DateTimeOffset]::UtcNow-([DateTimeOffset]$proof.measuredUtc)).TotalSeconds
if($proof.status -ne 'OS_CLOCK_VERIFIED' -or $age -lt 0 -or $age -gt 300 -or
   -not $proof.source -or $proof.source -match 'Local CMOS|Free.running' -or
   $proof.sampleCount -lt 3 -or $null -eq $proof.maxAbsOffsetSeconds -or
   [double]$proof.maxAbsOffsetSeconds -gt 0.5 -or [double]$proof.maxAbsOffsetSeconds -lt 0 -or
   $null -eq $proof.syncAgeSeconds -or [double]$proof.syncAgeSeconds -gt 300 -or [double]$proof.syncAgeSeconds -lt 0) { throw 'FRESH_CLOCK_PROOF_REQUIRED' }
Enable-ScheduledTask -InputObject $existing | Out-Null
