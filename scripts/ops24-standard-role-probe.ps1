<# One-time least-privilege account + isolated zero-market scheduled probe. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$Head,
 [Parameter(Mandatory=$true)][string]$Tree,[Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not([Security.Principal.WindowsPrincipal]::new($identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'ONE_TIME_WINDOWS_ACCOUNT_SETUP_REQUIRES_ADMIN'}
foreach($p in @($Source,$Root)){if(-not [IO.Path]::GetFullPath($p).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_PATH_REQUIRED'}}
if(((& git -C $Source rev-parse HEAD)|Out-String).Trim() -cne $Head -or ((& git -C $Source rev-parse 'HEAD^{tree}')|Out-String).Trim() -cne $Tree -or (& git -C $Source status --porcelain)){throw 'EXACT_CLEAN_SOURCE_REQUIRED'}
$env:PSModuleAnalysisCachePath='D:\ZS-SMART-GATE\temp\ps-module-analysis-cache'
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$name='ZS_SG_Research'
$marker='ZS SMART GATE read-only standard worker'
$user=Get-LocalUser -Name $name -ErrorAction SilentlyContinue
if($user -and $user.Description -cne $marker){throw 'EXISTING_NONPROJECT_ACCOUNT_MUST_NOT_BE_MODIFIED'}
if(-not $user){
 $bytes=New-Object byte[] 48
 $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
 try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
 $secure=ConvertTo-SecureString ('Zs!9'+[Convert]::ToBase64String($bytes)) -AsPlainText -Force
 New-LocalUser -Name $name -Password $secure -Description $marker -AccountNeverExpires -PasswordNeverExpires|Out-Null
 $secure.Dispose();[Array]::Clear($bytes,0,$bytes.Length)
 $user=Get-LocalUser -Name $name
}
$adminGroup=Get-LocalGroup -SID 'S-1-5-32-544'
if(Get-LocalGroupMember -Group $adminGroup|Where-Object{$_.SID.Value -eq $user.SID.Value}){throw 'WORKER_ACCOUNT_MUST_NOT_BE_ADMIN'}
$users=Get-LocalGroup -SID 'S-1-5-32-545'
if(-not(Get-LocalGroupMember -Group $users|Where-Object{$_.SID.Value -eq $user.SID.Value})){Add-LocalGroupMember -Group $users -Member $user}
$workerSid=$user.SID.Value
$ownerSid=$identity.User.Value
# Give the app account read/execute only on this immutable source and D runtime.
foreach($folder in @($Source,'D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77')){
 & icacls.exe $folder /inheritance:r /grant:r ('*'+$ownerSid+':(OI)(CI)F') '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' ('*'+$workerSid+':(OI)(CI)RX') /T /C /Q 1>$null
 if($LASTEXITCODE -ne 0){throw 'WORKER_READ_EXECUTE_ACL_FAILED'}
}
& (Join-Path $Source 'scripts\ops24-task-probe.ps1') -Source $Source -Head $Head -Tree $Tree -Root $Root -WorkerSid $workerSid
$code=$LASTEXITCODE
# Only public role facts are printed. SID/account credentials stay local.
[ordered]@{schema='zs.ops24.standard-role-setup.v1';worker_is_local_standard_account=$true;admin_membership=$false;password_exported=$false;market_calls=0;telegram_calls=0;task_probe_exit=$code;head=$Head;tree=$Tree}|ConvertTo-Json
exit $code
