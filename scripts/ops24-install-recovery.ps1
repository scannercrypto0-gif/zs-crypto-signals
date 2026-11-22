<# Persistent Serve G3 validation, no market, no merge, no scientific/soak PASS. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$Head,
 [Parameter(Mandatory=$true)][string]$Tree,[Parameter(Mandatory=$true)][string]$WindowsEvidence,
 [Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'RECOVERY_TASK_SETUP_REQUIRES_ADMIN'}
foreach($p in @($Source,$Root,$WindowsEvidence)){if(-not [IO.Path]::GetFullPath($p).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_PATH_REQUIRED'}}
if(Test-Path $Root){throw 'FRESH_RECOVERY_ROOT_REQUIRED'}
if(((& git -C $Source rev-parse HEAD)|Out-String).Trim() -cne $Head -or ((& git -C $Source rev-parse 'HEAD^{tree}')|Out-String).Trim() -cne $Tree -or (& git -C $Source status --porcelain)){throw 'EXACT_CLEAN_RELEASE_REQUIRED'}
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$role=Get-LocalUser -Name 'ZS_SG_Worker' -ErrorAction Stop
if($role.Description -cne 'ZS SMART GATE read-only standard worker' -or (Get-LocalGroupMember -SID 'S-1-5-32-544'|Where-Object {$_.SID.Value -eq $role.SID.Value})){throw 'EXISTING_STANDARD_ROLE_REQUIRED'}
. (Join-Path $Source 'scripts\ops24-owned-acl.ps1')
. (Join-Path $Source 'scripts\ops24-managed-credential.ps1')
$credential=Read-ZsManagedCredential -OwnerSid $id.User.Value -WorkerSid $role.SID.Value
$credential.Password.Dispose();$credential=$null
# Owner processes retain full access; never mutate or run the existing03B3 task.
$foreign=@(Get-ScheduledTask|Where-Object {$_.TaskName -like 'ZS*' -and $_.State -eq 'Running' -and $_.Principal.UserId -notin @($id.User.Value,$id.Name,'SYSTEM','S-1-5-18')})
if($foreign.Count){throw 'EXISTING_OTHER_ZS_WORKER_MUST_BE_REVIEWED_BEFORE_PARENT_HARDENING'}
Protect-ZsDeploymentContainers -Source $Source -WorkerSid $role.SID.Value -BackupRoot 'D:\ZS-SMART-GATE\secrets\ops77-worker'
$null=Set-ZsOwnedReadOnlyTree -Root $Source -WorkerSid $role.SID.Value
$python='D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe'
$null=Set-ZsOwnedReadOnlyTree -Root (Split-Path $python -Parent) -WorkerSid $role.SID.Value
$controller=Join-Path $Source 'scripts\ops24-windows.ps1'
& $controller -Action InstallDisabled -Root $Root -Source $Source -Head $Head -Tree $Tree -WorkerSid $role.SID.Value -Scope DEPLOYMENT_RECOVERY_NO_MARKET_V1
& $controller -Action PrepareClock -Root $Root
& $python -I -B (Join-Path $Source 'scripts\ops24-recovery-authority.py') --root $Root --head $Head --tree $Tree --windows $WindowsEvidence
if($LASTEXITCODE -ne 0){throw 'ACTUAL_WINDOWS_RECOVERY_AUTHORITY_FAILED'}
Set-ZsWorkerStateRoot -Root $Root -WorkerSid $role.SID.Value
& $controller -Action BuildTask -Root $Root
& $controller -Action Register -Root $Root
& $controller -Action Start -Root $Root
Write-Output 'SERVE_RECOVERY_DEPLOYED_AWAIT_ACTUAL_HEARTBEAT_NOT_HEALTH_RETEST'
