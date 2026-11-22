<# One-time owner DPAPI migration to D:, keeps original store unchanged. No HTTP. #>
[CmdletBinding()]
param([string]$Source=(Join-Path $env:LOCALAPPDATA 'ZS-SmartGate\stage05-secrets'),
 [string]$Target='D:\ZS-SMART-GATE\secrets\telegram-owner-20261122')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(-not [IO.Path]::GetFullPath($Target).StartsWith('D:\ZS-SMART-GATE\secrets\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_SECRET_TARGET_REQUIRED'}
if(Test-Path $Target){throw 'FRESH_SECRET_STORE_REQUIRED'}
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
. (Join-Path $PSScriptRoot 'ops24-owned-acl.ps1')
$names=@('signals-token','signals-chat-a','signals-chat-b','interactive-token','interactive-allowed-users','interactive-allowed-chats','analytics-token','analytics-chat')
$plain=@{};$secure=@{}
function Plain($Value){$ptr=[IntPtr]::Zero;try{$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value);return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}}
try{
 foreach($name in $names){
  $file=Join-Path $Source ($name+'.dpapi')
  if((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'SECRET_REPARSE_REFUSED'}
  $secure[$name]=ConvertTo-SecureString ([IO.File]::ReadAllText($file))
  $plain[$name]=Plain $secure[$name]
 }
 $tokens=@('signals-token','interactive-token','analytics-token')|ForEach-Object {$plain[$_]}
 if(@($tokens|Select-Object -Unique).Count -ne 3 -or @($tokens|Where-Object {$_ -cnotmatch '^[0-9]{5,15}:[A-Za-z0-9_-]{20,80}$'}).Count){throw 'THREE_DISTINCT_VALID_TOKENS_REQUIRED'}
 $a=$plain['signals-chat-a'];$b=$plain['signals-chat-b']
 if($a -cnotmatch '^[0-9]{1,20}$' -or $b -cnotmatch '^[0-9]{1,20}$' -or $a -ceq $b -or $plain['analytics-chat'] -cne $a){throw 'PRIVATE_AB_ARCHIVE_ROUTE_MISMATCH'}
 # Owner explicitly restored BOTH private account routes. Private user IDs equal chat IDs.
 foreach($name in @('interactive-allowed-users','interactive-allowed-chats')){
  $secure[$name].Dispose();$secure[$name]=ConvertTo-SecureString ($a+','+$b) -AsPlainText -Force
  $plain[$name]=$a+','+$b
 }
 $staging=$Target+'.staging-'+[guid]::NewGuid().ToString('N')
 New-Item -ItemType Directory -Path $staging|Out-Null
 [ZsOwnedDacl]::Set($staging,('D:P(A;OICI;FA;;;'+$id.User.Value+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'))
 foreach($name in $names){
  $path=Join-Path $staging ($name+'.dpapi')
  [IO.File]::WriteAllText($path,(ConvertFrom-SecureString $secure[$name]),[Text.UTF8Encoding]::new($false))
  $check=ConvertTo-SecureString ([IO.File]::ReadAllText($path))
  try{if((Plain $check) -cne $plain[$name]){throw 'SECRET_LOCAL_READBACK_MISMATCH'}}finally{$check.Dispose()}
 }
 Move-Item -LiteralPath $staging -Destination $Target
 Write-Output 'OWNER_DPAPI_D_STORE_VERIFIED_8_OF_8_INTERACTIVE_AB_ONLY_HTTP_0'
}finally{
 foreach($value in $secure.Values){$value.Dispose()}
 $plain.Clear();$secure.Clear();$tokens=$null;$a=$null;$b=$null
}
