<# Owner-side real Windows audit capture. Labels never confer PASS. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Root,
 [ValidateSet('before_logoff','after_logoff','before_reboot','after_reboot','after_crash','after_stop','after_restore','snapshot')][string]$Step='snapshot')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(-not [IO.Path]::GetFullPath($Root).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_ROOT_REQUIRED'}
$config=Get-Content (Join-Path $Root 'release.json') -Raw|ConvertFrom-Json
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if($id.User.Value -cne $config.owner_sid){throw 'ACTUAL_OWNER_AUDIT_REQUIRED'}
$folder=Join-Path $Root 'operator-evidence';New-Item -ItemType Directory -Path $folder -Force|Out-Null
. (Join-Path $config.source 'scripts\ops24-owned-acl.ps1')
[ZsOwnedDacl]::Set($folder,('D:P(A;OICI;FA;;;'+$id.User.Value+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'))
$sha=[Security.Cryptography.SHA256]::Create()
$pin=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes([IO.Path]::GetFullPath($Root).TrimEnd('\').ToUpperInvariant())))).Replace('-','').ToLowerInvariant()
$name='ZS-SmartGate-OPS24-'+$pin.Substring(0,10)
$task=Get-ScheduledTask -TaskName $name
$info=Get-ScheduledTaskInfo -TaskName $name
$authority=Get-Content (Join-Path $Root 'recovery-authority.json') -Raw|ConvertFrom-Json
$events=@();$securityStatus='NOT_READ'
try{
 $start=[DateTimeOffset]::FromUnixTimeSeconds($authority.created_epoch).LocalDateTime
 foreach($event in Get-WinEvent -FilterHashtable @{LogName='Security';Id=4624,4634,4647;StartTime=$start} -MaxEvents 2000 -ErrorAction Stop){
  [xml]$x=$event.ToXml();$fields=@{};foreach($d in $x.Event.EventData.Data){$fields[$d.Name]=[string]$d.'#text'}
  if($fields['TargetUserSid'] -ceq $config.owner_sid -or $fields['SubjectUserSid'] -ceq $config.owner_sid){
   $events+=@{id=$event.Id;utc=$event.TimeCreated.ToUniversalTime().ToString('o');logon_type=$fields['LogonType'];target_logon_id=$fields['TargetLogonId'];subject_logon_id=$fields['SubjectLogonId'];native_event_sha256=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($event.ToXml())))).Replace('-','').ToLowerInvariant()}
  }
 }
 $securityStatus='BOUNDED_OWNER_EVENTS_READ_NOT_AN_AUTOMATIC_LOGOFF_PASS'
}catch{$securityStatus='UNVERIFIED_SECURITY_AUDIT_UNAVAILABLE_OR_NO_MATCH'}
$statusPath=Join-Path $Root 'status.json'
$record=[ordered]@{schema='zs.ops77.actual-owner-recovery-audit.v1';step=$Step;head=$config.head;tree=$config.tree;owner_sid=$config.owner_sid;utc=[DateTime]::UtcNow.ToString('o');boot_utc=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');task_state=$task.State.ToString();task_logon=$task.Principal.LogonType.ToString();last_result=$info.LastTaskResult;last_run_utc=$info.LastRunTime.ToUniversalTime().ToString('o');security_status=$securityStatus;owner_security_events=$events;acceptance='NOT_AUTOMATIC_REQUIRES_RECEIPT_CORRELATION'}
if(Test-Path $statusPath){$record.serve_status_sha256=(Get-FileHash $statusPath).Hash.ToLowerInvariant();$record.serve_status=Get-Content $statusPath -Raw|ConvertFrom-Json}
$path=Join-Path $folder ($Step+'-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')+'.json')
[IO.File]::WriteAllText($path,($record|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
Write-Output ('ACTUAL_OWNER_AUDIT_RECORDED_STEP_NOT_PASS='+$Step)
$sha.Dispose()
