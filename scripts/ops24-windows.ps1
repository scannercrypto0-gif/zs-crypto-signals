<# OPS24 disabled-first controller. Runtime activation has separate reviewed gates. #>
[CmdletBinding()]
param(
 [ValidateSet('InstallDisabled','BuildTask','Status','Stop','Disable','Restore','Rollback','Register','Enable','Verify','Start','Health','Evidence')]
 [string]$Action='Status',
 [string]$Root='D:\ZS-SMART-GATE\ops24',
 [string]$Source,
 [string]$Head,
 [string]$Tree,
 [string]$Python='D:\ZS-SMART-GATE\.venv\Scripts\python.exe'
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
 $record=[ordered]@{schema='zs.ops24.disabled-release.v1';head=$Head;tree=$Tree;source=$Source;python=$Python;owner_sid=$owner;
   bundle=$bundle;bundle_sha256=(Get-FileHash $bundle).Hash.ToLowerInvariant();clock_profile='WINDOWS_STATUS_PROTECTED_REGISTRY_V1';enabled=$false}
 Write-Atomic $releasePath ($record|ConvertTo-Json -Depth 5)
 Write-Output "INSTALLED_DISABLED HEAD=$Head TREE=$Tree"
 }finally{$installLock.Dispose()}
 return
}
if(-not(Test-Path -LiteralPath $Root)){Write-Output 'NOT_INSTALLED';return}
$config=Get-Content (Join-Path $Root 'release.json') -Raw|ConvertFrom-Json
if($config.owner_sid -cne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value){throw 'AUTHENTICATED_OPERATOR_REQUIRED'}
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
   Stop-ScheduledTask -TaskName $task
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
 $worker=Join-Path $config.source 'scripts\ops24-worker.py'
 $command=[Security.SecurityElement]::Escape($config.python)
 $arguments=[Security.SecurityElement]::Escape('-B "'+$worker+'" Serve --root "'+$Root+'"')
 $sid=[Security.SecurityElement]::Escape($config.owner_sid)
 $xml='<?xml version="1.0" encoding="UTF-16"?>'+
 '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'+
 '<Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>'+
 '<Principals><Principal id="Owner"><UserId>'+$sid+'</UserId><LogonType>S4U</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'+
 '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'+
 '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><Enabled>false</Enabled><Hidden>true</Hidden>'+
 '<ExecutionTimeLimit>PT25H</ExecutionTimeLimit></Settings>'+
 '<Actions Context="Owner"><Exec><Command>'+$command+'</Command><Arguments>'+$arguments+'</Arguments></Exec></Actions></Task>'
 [IO.File]::WriteAllText((Join-Path $Root 'worker.disabled.xml'),$xml,[Text.Encoding]::Unicode)
 Write-Output 'TASK_XML_DISABLED_LEAST_PRIVILEGE_S4U_REVIEW_REQUIRED'
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
& $config.python -B $worker Validate --root $Root
if($LASTEXITCODE -ne 0){throw 'REVIEWED_ACTIVATION_NOT_VALID'}
if($Action -eq 'Register'){
 $xmlPath=Join-Path $Root 'worker.disabled.xml'
 if(-not(Test-Path $xmlPath)){throw 'BUILD_DISABLED_TASK_FIRST'}
 Register-ScheduledTask -TaskName $task -Xml (Get-Content $xmlPath -Raw) -ErrorAction Stop|Out-Null
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
