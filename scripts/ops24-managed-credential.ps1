<# Owner-only CurrentUser DPAPI; credential is never passed in process arguments. #>
function Read-ZsManagedCredential {
 param([string]$OwnerSid,[string]$WorkerSid,
       [string]$Path='D:\ZS-SMART-GATE\secrets\ops77-worker\account.clixml')
 if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $OwnerSid){throw 'CREDENTIAL_OWNER_REQUIRED'}
 if(-not [IO.Path]::GetFullPath($Path).StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_CREDENTIAL_REQUIRED'}
 $trusted=@($OwnerSid,'S-1-5-18','S-1-5-32-544')
 foreach($p in @((Split-Path $Path -Parent),$Path)){
  $item=Get-Item -LiteralPath $p -ErrorAction Stop
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'CREDENTIAL_REPARSE_REFUSED'}
  $acl=Get-Acl -LiteralPath $p
  if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $trusted){throw 'CREDENTIAL_OWNER_UNTRUSTED'}
  foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($rule.AccessControlType -eq 'Allow' -and -not([int]$rule.PropagationFlags -band 2) -and $rule.IdentityReference.Value -notin $trusted -and [int64]$rule.FileSystemRights -ne 0){throw 'CREDENTIAL_NOT_OWNER_PRIVATE'}
  }
 }
 $credential=Import-Clixml -LiteralPath $Path
 if($credential -isnot [PSCredential]){throw 'DPAPI_CREDENTIAL_REQUIRED'}
 $sid=([Security.Principal.NTAccount]::new($credential.UserName)).Translate([Security.Principal.SecurityIdentifier]).Value
 if($sid -cne $WorkerSid -or $WorkerSid -ceq $OwnerSid){throw 'DEDICATED_WORKER_CREDENTIAL_MISMATCH'}
 return $credential
}
