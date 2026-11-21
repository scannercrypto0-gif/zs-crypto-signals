<# Isolated finite Windows Task Scheduler probe: normal token, zero market/Telegram/SQL. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$Head,
 [Parameter(Mandatory=$true)][string]$Tree,[Parameter(Mandatory=$true)][string]$Root,
 [ValidateSet('Probe','Health')][string]$ProbeAction='Probe',
 [string]$WorkerSid='',
 [PSCredential]$WorkerCredential,
 [string]$Python='D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'POWERSHELL_51_REQUIRED'}
foreach($p in @($Source,$Root)){if(-not [IO.Path]::GetFullPath($p).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_ROOT_REQUIRED'}}
if(Test-Path $Root){throw 'FRESH_ROOT_REQUIRED'}
New-Item -ItemType Directory -Path $Root|Out-Null
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$controller=Join-Path $Source 'scripts\ops24-windows.ps1'
$task='ZS-OPS24-IsolatedProbe-'+[guid]::NewGuid().ToString('N')
$record=[ordered]@{schema='zs.ops24.task-probe-driver.v2';head=$Head;tree=$Tree;task=$task;origin='ACTUAL_WINDOWS_SCHEDULER';market_calls=0;telegram_calls=0;sql_writes=0;registered=$false;probe_observed=$false;cleanup=$false;real_reboot='NOT_EXECUTED';real_logoff='NOT_EXECUTED'}
try{
 & $controller -Action InstallDisabled -Root $Root -Source $Source -Head $Head -Tree $Tree -Python $Python -WorkerSid $WorkerSid
 if($LASTEXITCODE -ne 0){throw 'DISABLED_INSTALL_FAILED'}
 if($WorkerSid){
  . (Join-Path $Source 'scripts\ops24-owned-acl.ps1')
  Set-ZsWorkerStateRoot -Root $Root -WorkerSid $WorkerSid
 }
 & $controller -Action BuildTask -Root $Root
 $xmlPath=Join-Path $Root 'worker.disabled.xml'
 $xml=(Get-Content $xmlPath -Raw).Replace(' Serve --root ',' Probe --root ').Replace('<ExecutionTimeLimit>PT25H</ExecutionTimeLimit>','<ExecutionTimeLimit>PT30S</ExecutionTimeLimit>')
 if(-not $xml.Contains(' Probe --root ')-or -not $xml.Contains('<RunLevel>LeastPrivilege</RunLevel>')){throw 'PROBE_TASK_XML_INVALID'}
 $systemPowerShell=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
 $entry=Join-Path $Source 'scripts\ops24-task-entry.ps1'
 $command=[Security.SecurityElement]::Escape($systemPowerShell)
 $arguments=[Security.SecurityElement]::Escape('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$entry+'" -Action '+$ProbeAction+' -Root "'+$Root+'"')
 if($ProbeAction -eq 'Health'){$xml=$xml.Replace('<ExecutionTimeLimit>PT30S</ExecutionTimeLimit>','<ExecutionTimeLimit>PT90S</ExecutionTimeLimit>')}
 $xml=[regex]::Replace($xml,'<Command>[^<]+</Command>',('<Command>'+$command+'</Command>'))
 $xml=[regex]::Replace($xml,'<Arguments>[^<]+</Arguments>',('<Arguments>'+$arguments+'</Arguments>'))
 $record.xml_sha256=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::Unicode.GetBytes($xml))).Replace('-','').ToLowerInvariant()
 . (Join-Path $Source 'scripts\ops24-register-probe.ps1')
 Register-ZsIsolatedProbe -TaskName $task -Xml $xml -WorkerSid $WorkerSid -WorkerCredential $WorkerCredential
 $record.registered=$true
 Enable-ScheduledTask -TaskName $task|Out-Null
 Start-ScheduledTask -TaskName $task
 $deadline=[DateTime]::UtcNow.AddSeconds($(if($ProbeAction -eq 'Health'){85}else{35}))
 while([DateTime]::UtcNow -lt $deadline -and -not(Test-Path (Join-Path $Root 'probe.json'))){Start-Sleep -Milliseconds 250}
 while([DateTime]::UtcNow -lt $deadline -and (Get-ScheduledTask -TaskName $task).State -eq 'Running'){Start-Sleep -Milliseconds 100}
 $info=Get-ScheduledTaskInfo -TaskName $task
 $record.last_task_result=$info.LastTaskResult
 $record.last_run_utc=$info.LastRunTime.ToUniversalTime().ToString('o')
 $record.python=$Python
 foreach($stream in @('stdout','stderr')){
  $path=Join-Path $Root ('task.'+$stream+'.raw.txt')
  if(Test-Path $path){$record[($stream+'_sha256')]=(Get-FileHash $path).Hash.ToLowerInvariant()}
 }
 if(-not(Test-Path (Join-Path $Root 'probe.json'))){throw 'ACTUAL_SCHEDULED_PROBE_NOT_OBSERVED'}
 $probe=Get-Content (Join-Path $Root 'probe.json') -Raw|ConvertFrom-Json
 $record.probe_observed=$true
 $record.probe_sha256=(Get-FileHash (Join-Path $Root 'probe.json')).Hash.ToLowerInvariant()
 $record.normal_token=$probe.normal_token
 if($ProbeAction -eq 'Health'){
  $record.clock_status=$probe.clock.assessment.status
  if($record.clock_status -cne 'OPERATIONAL_TIME_ACCEPTED'){throw 'STANDARD_ROLE_CLOCK_HOLD'}
 }
 $record.actual_session=$probe.windows.session
 $record.boot_utc=$probe.windows.boot_utc
 if(-not $probe.normal_token -or $probe.head -cne $Head -or $probe.tree -cne $Tree){throw 'NORMAL_SCHEDULED_TOKEN_OR_PIN_MISMATCH'}
 $record.status='SCHEDULED_NORMAL_TOKEN_PROBE_PASS_REBOOT_LOGOFF_PENDING'
}catch{
 $record.status='BLOCKED_WINDOWS_TASK_PREFLIGHT'
 $record.error_id=$_.FullyQualifiedErrorId
 $record.hresult=$_.Exception.HResult
}finally{
 if($record.registered){
  Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
  Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue|Out-Null
  Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
  $record.cleanup=(-not(Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue))
 }else{$record.cleanup=$true}
 [IO.File]::WriteAllText((Join-Path $Root 'task-probe-report.json'),($record|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
 Write-Output ($record|ConvertTo-Json -Depth 8)
}
if($record.status -like 'BLOCKED*'){exit 2}
