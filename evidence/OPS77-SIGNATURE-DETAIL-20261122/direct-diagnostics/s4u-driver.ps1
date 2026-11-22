$ErrorActionPreference='Stop'
$r='D:\ZS-SMART-GATE\validation\OPS77-signature-direct-diagnostic-20261122'
$env:PSModulePath=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\Modules'
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP;$env:PSModuleAnalysisCachePath=Join-Path $r 'driver-module-cache'
$task='ZS-OPS77-SelfDiagnostic-'+[guid]::NewGuid().ToString('N');$registered=$false
$report=[ordered]@{schema='zs.ops77.self-s4u-diagnostic.v1';origin='ACTUAL_STANDARD_USER_SELF_REGISTRATION';market_calls=0;telegram_calls=0;sql_writes=0;registered=$false}
try{
 $id=[Security.Principal.WindowsIdentity]::GetCurrent()
 if(([Security.Principal.WindowsPrincipal]::new($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'STANDARD_USER_REQUIRED'}
 $principal=New-ScheduledTaskPrincipal -UserId $id.Name -LogonType S4U -RunLevel Limited
 $action=New-ScheduledTaskAction -Execute (Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe') -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$r+'\s4u-action.ps1"') -WorkingDirectory $r
 $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 45) -Disable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
 Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings|Out-Null
 $registered=$true;$report.registered=$true
 Enable-ScheduledTask $task|Out-Null;Start-ScheduledTask $task
 $deadline=[DateTime]::UtcNow.AddSeconds(35)
 while([DateTime]::UtcNow -lt $deadline -and -not(Test-Path "$r\s4u-profile.raw.json") -and -not(Test-Path "$r\s4u-error.raw.txt")){Start-Sleep -Milliseconds 200}
 $report.last_task_result=(Get-ScheduledTaskInfo $task).LastTaskResult
 $report.profile_observed=Test-Path "$r\s4u-profile.raw.json"
}catch{$report.error_id=$_.FullyQualifiedErrorId;$report.hresult=$_.Exception.HResult}
finally{if($registered){Stop-ScheduledTask $task -ErrorAction SilentlyContinue;Unregister-ScheduledTask $task -Confirm:$false};$report.cleanup=$true;[IO.File]::WriteAllText("$r\self-s4u-report.json",($report|ConvertTo-Json -Depth 5))}
