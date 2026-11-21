<# One standing-authority bootstrap; disabled until genuine deployment proof passes. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WindowsEvidence,[Parameter(Mandatory=$true)][string]$SourceEvidence,
 [string]$Root='D:\ZS-SMART-GATE\ops24-reviewed-v2')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'POWERSHELL_51_REQUIRED'}
foreach($path in @($Root,$WindowsEvidence,$SourceEvidence)){if(-not [IO.Path]::GetFullPath($path).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_PATH_REQUIRED'}}
$repo='scannercrypto0-gif/zs-crypto-signals'
$pr=(& gh api "repos/$repo/pulls/76"|Out-String|ConvertFrom-Json)
if($LASTEXITCODE -ne 0){throw 'GITHUB_RELEASE_STATE_UNVERIFIED'}
if(-not $pr.merged -or $pr.draft){throw 'PM_REVIEWED_MERGE_PENDING_NO_OWNER_REAUTHORIZATION_NEEDED'}
$head=[string]$pr.merge_commit_sha
$merged=(& gh api "repos/$repo/git/commits/$head"|Out-String|ConvertFrom-Json)
if($LASTEXITCODE -ne 0){throw 'GITHUB_MERGE_TREE_UNVERIFIED'}
$tree=[string]$merged.tree.sha
$windows=Get-Content (Join-Path $WindowsEvidence 'acceptance.json') -Raw|ConvertFrom-Json
if($windows.tree -cne $tree){throw 'MERGED_TREE_DIFFERS_FROM_WINDOWS_EVIDENCE'}
if(Test-Path (Join-Path $Root 'release.json')){if(-not(Test-Path (Join-Path $Root 'DISABLED'))){throw 'DISABLE_BEFORE_UPGRADE'}}
New-Item -ItemType Directory -Path $Root -Force|Out-Null
# DACL-only construction avoids copying a SACL or requiring SeSecurityPrivilege.
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner($sid);$acl.SetAccessRuleProtection($true,$false)
foreach($principal in @($sid.Value,'S-1-5-18','S-1-5-32-544')){
 $rule=New-Object Security.AccessControl.FileSystemAccessRule ([Security.Principal.SecurityIdentifier]::new($principal),'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule)
}
[IO.Directory]::SetAccessControl($Root,$acl)
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$source=Join-Path $Root ('release-'+$head)
if(-not(Test-Path $source)){
 & git -c credential.helper= -c 'credential.helper=!gh auth git-credential' clone --no-hardlinks --single-branch --branch main "https://github.com/$repo.git" $source
 if($LASTEXITCODE -ne 0){throw 'GITHUB_SOURCE_RESTORE_FAILED'}
 & git -C $source checkout --detach $head
 if($LASTEXITCODE -ne 0){throw 'EXACT_RELEASE_CHECKOUT_FAILED'}
}
$controller=Join-Path $source 'scripts\ops24-windows.ps1'
& $controller -Action InstallDisabled -Root $Root -Source $source -Head $head -Tree $tree
$python='D:\ZS-SMART-GATE\.venv\Scripts\python.exe'
$decision=Join-Path $Root ('standing-'+[guid]::NewGuid().ToString('N')+'.json')
& $python -B (Join-Path $source 'scripts\ops24-standing-release.py') --head $windows.head --tree $tree --windows $WindowsEvidence --source-proof $SourceEvidence --output $decision
if($LASTEXITCODE -ne 0){throw 'GENUINE_REVIEW_OR_WINDOWS_SOURCE_EVIDENCE_PENDING'}
Move-Item -LiteralPath $decision -Destination (Join-Path $Root 'standing-authority.json') -Force
& $controller -Action BuildTask -Root $Root
& $controller -Action Register -Root $Root
if(-not(Test-Path (Join-Path $Root 'deployment-proof.json'))){Write-Output 'RELEASE_INSTALLED_TASK_DISABLED_ACTUAL_G3_PROOF_PENDING';return}
& $controller -Action Verify -Root $Root
& $controller -Action Start -Root $Root
