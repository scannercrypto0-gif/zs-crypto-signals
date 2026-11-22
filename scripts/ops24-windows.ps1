<# OPS24 disabled-first controller. Runtime activation has separate reviewed gates. #>
[CmdletBinding()]
param(
 [ValidateSet('InstallDisabled','PrepareClock','BuildTask','Status','Stop','Disable','Restore','Rollback','Register','Enable','Verify','Start','Health','Evidence')]
 [string]$Action='Status',
 [string]$Root='D:\ZS-SMART-GATE\ops24',
 [string]$Source,
 [string]$Head,
 [string]$Tree,
 [string]$WorkerSid='',
 [ValidateSet('PUBLIC_SPOT_READ_ONLY_NO_TELEGRAM_SQL_TRADING','DEPLOYMENT_RECOVERY_NO_MARKET_V1')][string]$Scope='PUBLIC_SPOT_READ_ONLY_NO_TELEGRAM_SQL_TRADING',
 [string]$Python='D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe'
)
$ErrorActionPreference='Stop'
if($Action -eq 'Start'){$Action='Enable'}
Set-StrictMode -Version Latest
if($PSVersionTable.PSVersion.Major -ne 5){throw 'WINDOWS_POWERSHELL_51_REQUIRED'}
$owned='D:\ZS-SMART-GATE\'
foreach($p in @($Root,$Python)){
 if(-not [IO.Path]::GetFullPath($p).StartsWith($owned,[StringComparison]::OrdinalIgnoreCase)){throw 'D_PROJECT_ROOT_REQUIRED'}
}
function Write-Atomic([string]$Path,[string]$Text){
 $temp=$Path+'.partial'
 [IO.File]::WriteAllText($temp,$Text,[Text.UTF8Encoding]::new($false))
 Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Invoke-Git([string[]]$Values){
 $out=Join-Path $Root 'git.stdout.txt'; $err=Join-Path $Root 'git.stderr.txt'
 $arguments=@($Values|ForEach-Object{'"'+$_+'"'})
 $p=Start-Process git -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
 $null=$p.Handle
 if(-not $p.WaitForExit(120000)){& taskkill.exe /PID $p.Id /T /F|Out-Null; throw 'GIT_OPERATION_TIMEOUT'}
 $p.WaitForExit()
 if($null -eq $p.ExitCode -or $p.ExitCode -ne 0){throw 'GIT_OPERATION_FAILED'}
}
function Register-ManagedServeTask {
 $xmlPath=Join-Path $Root 'worker.disabled.xml'
 if(-not(Test-Path $xmlPath)){throw 'BUILD_DISABLED_TASK_FIRST'}
 . (Join-Path $config.source 'scripts\ops24-managed-credential.ps1')
 . (Join-Path $config.source 'scripts\ops24-register-probe.ps1')
 $credential=Read-ZsManagedCredential -OwnerSid $config.owner_sid -WorkerSid $config.worker_sid
 try{
  Register-ZsIsolatedProbe -TaskName $task -Xml (Get-Content $xmlPath -Raw) -WorkerSid $config.worker_sid -WorkerCredential $credential -LogonType Password
  $registered=Get-ScheduledTask -TaskName $task
  if($registered.Principal.LogonType.ToString() -cne 'Password' -or $registered.Principal.RunLevel.ToString() -cne 'Limited'){Disable-ScheduledTask $task|Out-Null;throw 'REGISTERED_TASK_PROFILE_MISMATCH'}
  $scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect()
  $native=$scheduler.GetFolder('\').GetTask($task)
  $sddl='O:'+$config.owner_sid+'D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;'+$config.owner_sid+')(A;;GRGX;;;'+$config.worker_sid+')'
  $native.SetSecurityDescriptor($sddl,16)
  $sd=[Security.AccessControl.RawSecurityDescriptor]::new($native.GetSecurityDescriptor(5))
  if($sd.Owner.Value -cne $config.owner_sid){Disable-ScheduledTask $task|Out-Null;throw 'TASK_OWNER_PROTECTION_FAILED'}
 }finally{if($credential){$credential.Password.Dispose();$credential=$null}}
}
$sha=[Security.Cryptography.SHA256]::Create()
try{$rootPin=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes([IO.Path]::GetFullPath($Root).TrimEnd('\').ToUpperInvariant())))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
$task='ZS-SmartGate-OPS24-'+$rootPin.Substring(0,10)
if($Action -eq 'InstallDisabled'){
 if(-not $Source -or -not $Head -or -not $Tree){throw 'PINNED_SOURCE_REQUIRED'}
 $full=[IO.Path]::GetFullPath($Source)
 if(-not $full.StartsWith($owned,[StringComparison]::OrdinalIgnoreCase)){throw 'D_SOURCE_REQUIRED'}
 $actual=(& git -C $Source rev-parse HEAD|Out-String).Trim()
 $actualTree=(& git -C $Source rev-parse 'HEAD^{tree}'|Out-String).Trim()
 $dirty=(& git -C $Source status --porcelain|Out-String).Trim()
 if($actual -cne $Head -or $actualTree -cne $Tree -or $dirty){throw 'SOURCE_PIN_OR_CLEAN_MISMATCH'}
 New-Item -ItemType Directory -Path $Root -Force|Out-Null
 $releasePath=Join-Path $Root 'release.json'
 if((Test-Path $releasePath) -and -not(Test-Path (Join-Path $Root 'DISABLED'))){throw 'DISABLE_BEFORE_UPGRADE'}
 New-Item -ItemType Directory -Path (Join-Path $Root 'lock') -Force|Out-Null
 try{
   $installLock=[IO.File]::Open((Join-Path $Root 'lock\runner.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 }catch{throw 'EXISTING_WORKER_LOCKED'}
 try{
 if(Test-Path $releasePath){Copy-Item -LiteralPath $releasePath -Destination (Join-Path $Root 'previous.release.json') -Force}
 Write-Atomic (Join-Path $Root 'DISABLED') "disabled-by-install"
 Write-Atomic (Join-Path $Root 'STOP_REQUESTED') "disabled-by-install"
 $bundle=Join-Path $Root ('source-'+$Head+'.bundle')
 if(-not(Test-Path -LiteralPath $bundle)){Invoke-Git -Values @('-C',$Source,'bundle','create',$bundle,'HEAD')}
 $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $gitExecutable=(Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
 $record=[ordered]@{schema='zs.ops24.disabled-release.v2';task_profile='ZS_OPS77_STANDARD_PASSWORD_SERVE_V2';task_logon_type='Password';clock_contract='ZS_OPS77_RELEASE_BOUND_CATALOG_CLOCK_V2';clock_catalog_map_sha256=$null;scope=$Scope;git_executable=$gitExecutable;git_sha256=(Get-FileHash $gitExecutable).Hash.ToLowerInvariant();head=$Head;tree=$Tree;source=$Source;python=$Python;owner_sid=$owner;worker_sid=$(if($WorkerSid){$WorkerSid}else{$owner});
   bundle=$bundle;bundle_sha256=(Get-FileHash $bundle).Hash.ToLowerInvariant();clock_profile='WINDOWS_STATUS_PROTECTED_REGISTRY_V1';enabled=$false}
 Write-Atomic $releasePath ($record|ConvertTo-Json -Depth 5)
 Write-Output "INSTALLED_DISABLED HEAD=$Head TREE=$Tree"
 }finally{$installLock.Dispose()}
 return
}
if(-not(Test-Path -LiteralPath $Root)){Write-Output 'NOT_INSTALLED';return}
$config=Get-Content (Join-Path $Root 'release.json') -Raw|ConvertFrom-Json
if($config.owner_sid -cne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value){throw 'AUTHENTICATED_OPERATOR_REQUIRED'}
if($Action -eq 'PrepareClock'){
 if(-not(Test-Path (Join-Path $Root 'DISABLED'))){throw 'DISABLE_BEFORE_CLOCK_REPROVISION'}
 if($config.schema -cne 'zs.ops24.disabled-release.v2' -or $config.worker_sid -ceq $config.owner_sid){throw 'DEDICATED_V2_RELEASE_REQUIRED'}
 $target=Join-Path $Root ('catalog-'+[guid]::NewGuid().ToString('N')+'.json')
 $builder=Join-Path $config.source 'scripts\ops24-catalog-map.py'
 $p=Start-Process $config.python -ArgumentList @('-I','-B',('"'+$builder+'"'),'--head',$config.head,'--tree',$config.tree,'--output',('"'+$target+'"')) -WorkingDirectory $config.source -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Root 'catalog-prepare.stdout.raw.txt') -RedirectStandardError (Join-Path $Root 'catalog-prepare.stderr.raw.txt')
 $null=$p.Handle
 if(-not $p.WaitForExit(30000)){& taskkill.exe /PID $p.Id /T /F|Out-Null;throw 'CATALOG_PREPARE_TIMEOUT'}
 $p.WaitForExit();if($p.ExitCode -ne 0){throw 'CATALOG_PREPARE_FAILED'}
 Move-Item -LiteralPath $target -Destination (Join-Path $Root 'clock-catalog-map.json') -Force
 $config.clock_catalog_map_sha256=(Get-FileHash (Join-Path $Root 'clock-catalog-map.json')).Hash.ToLowerInvariant()
 Write-Atomic (Join-Path $Root 'release.json') ($config|ConvertTo-Json -Depth 8)
 . (Join-Path $config.source 'scripts\ops24-owned-acl.ps1')
 Set-ZsWorkerStateRoot -Root $Root -WorkerSid $config.worker_sid
 Write-Output 'RELEASE_PINNED_CLOCK_MAP_PREPARED_NO_ACCEPTANCE_REPLAY'
 return
}
if($Action -eq 'Status'){
 [ordered]@{disabled=(Test-Path (Join-Path $Root 'DISABLED'));stop_requested=(Test-Path (Join-Path $Root 'STOP_REQUESTED'));
 head=$config.head;tree=$config.tree;clock_profile=$config.clock_profile;
  status_file=(Join-Path $Root 'status.json');stability='NOT_ACCEPTED_BY_STATUS_ALONE'}|ConvertTo-Json
 return
}
if($Action -in @('Stop','Disable','Rollback')){
 Write-Atomic (Join-Path $Root 'STOP_REQUESTED') "operator-stop"
 if($Action -ne 'Stop'){Write-Atomic (Join-Path $Root 'DISABLED') "operator-disable"}
 $existing=Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
 if($existing){
   $deadline=[DateTime]::UtcNow.AddSeconds(15)
   while([DateTime]::UtcNow -lt $deadline -and (Get-ScheduledTask -TaskName $task).State -eq 'Running'){Start-Sleep -Milliseconds 200}
   if((Get-ScheduledTask -TaskName $task).State -eq 'Running'){Stop-ScheduledTask -TaskName $task;Write-Output 'FORCED_TASK_STOP_AFTER_GRACE_TIMEOUT'}
   if($Action -ne 'Stop'){Disable-ScheduledTask -TaskName $task|Out-Null}
 }
 if($Action -ne 'Rollback'){Write-Output 'STOP_OR_DISABLE_RECORDED';return}
 $previous=Join-Path $Root 'previous.release.json'
 if(-not(Test-Path $previous)){throw 'NO_PREVIOUS_RELEASE'}
 $old=Get-Content $previous -Raw|ConvertFrom-Json
 if((Get-FileHash $old.bundle).Hash.ToLowerInvariant() -cne $old.bundle_sha256){throw 'PREVIOUS_BUNDLE_CORRUPT'}
 Write-Atomic (Join-Path $Root 'release.json') (Get-Content $previous -Raw)
 Write-Output 'ROLLED_BACK_DISABLED_RESTORE_REQUIRED'
 return
}
if($Action -eq 'Restore'){
 if(-not(Test-Path (Join-Path $Root 'DISABLED'))){throw 'DISABLE_BEFORE_RESTORE'}
 if((Get-FileHash $config.bundle).Hash.ToLowerInvariant() -cne $config.bundle_sha256){throw 'RESTORE_BUNDLE_CORRUPT'}
 $target=Join-Path $Root ('restored-'+[guid]::NewGuid().ToString('N'))
 Invoke-Git -Values @('clone','--no-hardlinks',$config.bundle,$target)
 if(((& git -C $target rev-parse HEAD)|Out-String).Trim() -cne $config.head -or
    ((& git -C $target rev-parse 'HEAD^{tree}')|Out-String).Trim() -cne $config.tree){throw 'RESTORE_PIN_MISMATCH'}
 Write-Output "OFFLINE_RESTORE_VERIFIED HEAD=$($config.head) TREE=$($config.tree) PATH=$target"
 return
}
if($Action -in @('Verify','Health','Evidence')){
 $worker=Join-Path $config.source 'scripts\ops24-worker.py'
 & $config.python -B $worker $Action --root $Root
 if($LASTEXITCODE -ne 0){throw 'TECHNICAL_RELEASE_OR_HEALTH_GATE_HOLD'}
 return
}
if($Action -eq 'BuildTask'){
 if($config.schema -cne 'zs.ops24.disabled-release.v2' -or $config.task_logon_type -cne 'Password' -or $config.worker_sid -ceq $config.owner_sid){throw 'DEDICATED_PASSWORD_SERVE_V2_REQUIRED'}
 $worker=Join-Path $config.source 'scripts\ops24-worker.py'
 $command=[Security.SecurityElement]::Escape($config.python)
 $arguments=[Security.SecurityElement]::Escape('-I -B "'+$worker+'" Serve --root "'+$Root+'"')
 $sid=[Security.SecurityElement]::Escape($config.worker_sid)
 $xml='<?xml version="1.0" encoding="UTF-16"?>'+
 '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'+
 '<Triggers><BootTrigger><Enabled>true</Enabled><Delay>PT1M</Delay></BootTrigger></Triggers>'+
 '<Principals><Principal id="Owner"><UserId>'+$sid+'</UserId><LogonType>Password</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'+
 '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'+
 '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><Enabled>false</Enabled><Hidden>true</Hidden>'+
 '<StartWhenAvailable>true</StartWhenAvailable><RestartOnFailure><Interval>PT1M</Interval><Count>5</Count></RestartOnFailure><ExecutionTimeLimit>PT25H</ExecutionTimeLimit></Settings>'+
 '<Actions Context="Owner"><Exec><Command>'+$command+'</Command><Arguments>'+$arguments+'</Arguments><WorkingDirectory>'+[Security.SecurityElement]::Escape($config.source)+'</WorkingDirectory></Exec></Actions></Task>'
 [IO.File]::WriteAllText((Join-Path $Root 'worker.disabled.xml'),$xml,[Text.Encoding]::Unicode)
 Write-Output 'TASK_XML_V2_DISABLED_STANDARD_PASSWORD_SERVE'
 return
}
if($config.scope -ceq 'DEPLOYMENT_RECOVERY_NO_MARKET_V1' -and $Action -in @('Register','Enable')){
 & $config.python -I -B (Join-Path $config.source 'scripts\ops24-recovery-verify.py') --root $Root --head $config.head --tree $config.tree
 if($LASTEXITCODE -ne 0){throw 'RECOVERY_SCOPE_VERIFICATION_FAILED'}
 if($Action -eq 'Register'){Register-ManagedServeTask;Write-Output 'RECOVERY_SERVE_PASSWORD_TASK_REGISTERED_DISABLED';return}
 Remove-Item -LiteralPath (Join-Path $Root 'STOP_REQUESTED') -ErrorAction SilentlyContinue
 Remove-Item -LiteralPath (Join-Path $Root 'DISABLED') -ErrorAction SilentlyContinue
 Enable-ScheduledTask -TaskName $task|Out-Null;Start-ScheduledTask -TaskName $task
 Write-Output 'RECOVERY_SERVE_STARTED_ZERO_MARKET_NOT_A_24H_SOAK'
 return
}
# Registration/enablement remains a genuine gate until normal-worker deployment,
# reviewed full-market evidence and owner merge approval are installed.
if(-not(Test-Path (Join-Path $Root 'standing-authority.json'))){throw 'STANDING_REVIEWED_RELEASE_EVIDENCE_PENDING'}
if($Action -eq 'Enable' -and -not(Test-Path (Join-Path $Root 'window.json'))){
 $now=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
 $boundary=[long]([Math]::Floor($now/1800)+1)*1800
 Write-Atomic (Join-Path $Root 'window.json') (@{start_epoch=$boundary;seconds=86400;origin='AUTOMATIC_STANDING_READ_ONLY_WINDOW';planned_only=$true}|ConvertTo-Json)
}
$worker=Join-Path $config.source 'scripts\ops24-worker.py'
if($Action -eq 'Register'){
 & $config.python -B (Join-Path $config.source 'scripts\ops24-release-verify.py') (Join-Path $Root 'standing-authority.json')
}else{
 & $config.python -B $worker Validate --root $Root
}
if($LASTEXITCODE -ne 0){throw 'REVIEWED_RELEASE_OR_ACTUAL_DEPLOYMENT_GATE_HOLD'}
if($Action -eq 'Register'){
 Register-ManagedServeTask
 Write-Output 'TASK_REGISTERED_DISABLED'
 return
}
if($Action -eq 'Enable'){
 if(-not(Test-Path (Join-Path $Root 'window.json'))){throw 'AUTOMATIC_FINITE_WINDOW_NOT_COMPOSED'}
 Remove-Item -LiteralPath (Join-Path $Root 'STOP_REQUESTED') -ErrorAction SilentlyContinue
 Remove-Item -LiteralPath (Join-Path $Root 'DISABLED')
 Enable-ScheduledTask -TaskName $task|Out-Null
 Start-ScheduledTask -TaskName $task
 Write-Output 'REVIEWED_FINITE_RESEARCH_WORKER_STARTED'
}
