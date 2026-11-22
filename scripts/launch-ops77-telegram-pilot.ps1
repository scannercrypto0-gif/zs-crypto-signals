<# Owner normal-token finite research pilot. No scheduler or production switch. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Head,
 [Parameter(Mandatory=$true)][string]$WindowsEvidence,
 [Parameter(Mandatory=$true)][string]$Root,
 [string]$ClockRoot='D:\ZS-SMART-GATE\ops77-boot-fix-recovery-20261122',
 [string]$Secrets='D:\ZS-SMART-GATE\secrets\telegram-owner-20261122')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$source=Split-Path $PSScriptRoot -Parent
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if(([Security.Principal.WindowsPrincipal]::new($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'NORMAL_TOKEN_PILOT_REQUIRED'}
foreach($path in @($Root,$ClockRoot,$Secrets,$WindowsEvidence)){if(-not [IO.Path]::GetFullPath($path).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_PROJECT_PATH_REQUIRED'}}
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
$env:PSModuleAnalysisCachePath=Join-Path $Secrets 'ps-module-analysis-cache'
$env:PYTHONDONTWRITEBYTECODE='1'
$mapping=@{'signals-token'='ZS_SIGNALS_BOT_TOKEN';'signals-chat-a'='ZS_SIGNALS_CHAT_ID_A';'signals-chat-b'='ZS_SIGNALS_CHAT_ID_B';'interactive-token'='ZS_INTERACTIVE_BOT_TOKEN';'interactive-allowed-users'='ZS_INTERACTIVE_ALLOWED_USER_IDS';'interactive-allowed-chats'='ZS_INTERACTIVE_ALLOWED_CHAT_IDS';'analytics-token'='ZS_ANALYTICS_BOT_TOKEN';'analytics-chat'='ZS_ANALYTICS_CHAT_ID'}
$loaded=@();$code=2
try{
 foreach($path in @($Secrets)+@($mapping.Keys|ForEach-Object {Join-Path $Secrets ($_+'.dpapi')})){
  if((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'SECRET_REPARSE_REFUSED'}
  $acl=Get-Acl -LiteralPath $path
  if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @($id.User.Value,'S-1-5-18','S-1-5-32-544')){throw 'SECRET_OWNER_UNTRUSTED'}
  foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($rule.AccessControlType -eq 'Allow' -and -not([int]$rule.PropagationFlags -band 2) -and $rule.IdentityReference.Value -notin @($id.User.Value,'S-1-5-18','S-1-5-32-544') -and [int64]$rule.FileSystemRights -ne 0){throw 'SECRET_STORE_NOT_OWNER_PRIVATE'}
  }
 }
 foreach($name in $mapping.Keys){
  $key=$mapping[$name]
  if([Environment]::GetEnvironmentVariable($key,'Process')){throw 'AMBIGUOUS_EXISTING_SECRET_ENVIRONMENT'}
  $value=ConvertTo-SecureString ([IO.File]::ReadAllText((Join-Path $Secrets ($name+'.dpapi'))))
  $ptr=[IntPtr]::Zero
  try{$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($value);[Environment]::SetEnvironmentVariable($key,[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr),'Process');$loaded+=$key}
  finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)};$value.Dispose()}
 }
 & 'D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe' -I -B (Join-Path $PSScriptRoot 'ops77-telegram-pilot.py') --head $Head --root $Root --clock-root $ClockRoot --windows-evidence $WindowsEvidence --live
 $code=$LASTEXITCODE
}finally{foreach($key in $loaded){[Environment]::SetEnvironmentVariable($key,$null,'Process')}}
exit $code
