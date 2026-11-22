<# Reversible Microsoft high-accuracy poll/correction settings, not clock acceptance. #>
[CmdletBinding()]
param([ValidateSet('Apply','Restore')][string]$Action='Apply',
 [Parameter(Mandatory=$true)][string]$Head,
 [string]$Root='D:\ZS-SMART-GATE\ops77-clock-tuning-20261122')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$source=Split-Path $PSScriptRoot -Parent
if(((& git -C $source rev-parse HEAD)|Out-String).Trim() -cne $Head -or (& git -C $source status --porcelain)){throw 'EXACT_CLEAN_SOURCE_REQUIRED'}
if(-not [IO.Path]::GetFullPath($Root).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_ROOT_REQUIRED'}
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'WINDOWS_ADMINISTRATOR_TOKEN_REQUIRED'}
if((Get-CimInstance Win32_ComputerSystem).PartOfDomain){throw 'DOMAIN_CLOCK_POLICY_REQUIRES_SEPARATE_REVIEW'}
if(Test-Path 'HKLM:\SOFTWARE\Policies\Microsoft\W32Time'){throw 'MANAGED_CLOCK_POLICY_NOT_OVERRIDDEN'}
if(@(Get-ScheduledTask|Where-Object {$_.TaskName -like 'ZS*' -and $_.State -eq 'Running'}).Count){throw 'STOP_PROJECT_TASKS_BEFORE_CLOCK_CHANGE'}
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$key='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$values=@{MinPollInterval=6;MaxPollInterval=6;UpdateInterval=100;FrequencyCorrectRate=2}
$backup=Join-Path $Root 'before.json'
function Save-Json($Path,$Value){[IO.File]::WriteAllText($Path,($Value|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))}
function Apply-Values($Map){foreach($name in $values.Keys){Set-ItemProperty -LiteralPath $key -Name $name -Value ([int]$Map.$name)}}
function Reload-Time {
 $service=Get-Service W32Time
 if($service.Status -ne 'Stopped'){Stop-Service W32Time;$service.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(15))}
 Start-Service W32Time;$service.WaitForStatus('Running',[TimeSpan]::FromSeconds(15))
 $proc=Start-Process "$env:SystemRoot\System32\w32tm.exe" -ArgumentList '/resync','/rediscover' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Root 'resync.stdout.txt') -RedirectStandardError (Join-Path $Root 'resync.stderr.txt')
 $null=$proc.Handle
 if(-not $proc.WaitForExit(20000)){Stop-Process -Id $proc.Id -Force;throw 'BOUNDED_RESYNC_TIMEOUT'}
 $proc.WaitForExit();if($proc.ExitCode -ne 0){throw 'RESYNC_COMMAND_FAILED'}
}
if($Action -eq 'Apply'){
 if(Test-Path $Root){throw 'FRESH_CLOCK_TUNING_ROOT_REQUIRED'}
 New-Item -ItemType Directory -Path $Root|Out-Null
 $before=[ordered]@{schema='zs.ops77.clock-tuning.v1';head=$Head;utc=[DateTime]::UtcNow.ToString('o');values=@{};service_start_mode=(Get-CimInstance Win32_Service -Filter "Name='W32Time'").StartMode;service_was_running=((Get-Service W32Time).Status -eq 'Running')}
 foreach($name in $values.Keys){$before.values[$name]=[int](Get-ItemPropertyValue -LiteralPath $key -Name $name)}
 Save-Json $backup $before
 try {Apply-Values ([PSCustomObject]$values);Set-Service W32Time -StartupType Automatic;Reload-Time}
 catch {
  Apply-Values ([PSCustomObject]$before.values)
  $start=@{Auto='Automatic';Manual='Manual';Disabled='Disabled'}[$before.service_start_mode]
  Set-Service W32Time -StartupType $start
  if($before.service_was_running){Restart-Service W32Time}else{Stop-Service W32Time}
  throw
 }
}else{
 $before=Get-Content -LiteralPath $backup -Raw|ConvertFrom-Json
 if($before.schema -cne 'zs.ops77.clock-tuning.v1'){throw 'CLOCK_BACKUP_SCHEMA_INVALID'}
 Apply-Values $before.values
 $start=@{Auto='Automatic';Manual='Manual';Disabled='Disabled'}[$before.service_start_mode]
 Set-Service W32Time -StartupType $start
 if($before.service_was_running){Reload-Time}else{Stop-Service W32Time}
}
$after=[ordered]@{schema='zs.ops77.clock-tuning-receipt.v1';action=$Action;head=$Head;utc=[DateTime]::UtcNow.ToString('o');values=@{};clock_acceptance='NOT_MEASURED';source_unchanged=$true;limits_unchanged=$true;market_calls=0;telegram_calls=0;reference='https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy'}
foreach($name in $values.Keys){$after.values[$name]=[int](Get-ItemPropertyValue -LiteralPath $key -Name $name)}
Save-Json (Join-Path $Root ($Action.ToLowerInvariant()+'.json')) $after
Write-Output 'CLOCK_CONFIGURATION_APPLIED_REMEASUREMENT_REQUIRED_NOT_A_CLOCK_PASS'
