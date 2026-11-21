<# S4U registration for another local user requires credentials (Microsoft task security contract).
   Credential material exists only in process memory; never use command-line passwords. #>
function Register-ZsIsolatedProbe {
 [CmdletBinding()]
 param([string]$TaskName,[string]$Xml,[string]$WorkerSid='',
       [PSCredential]$WorkerCredential)
 if($WorkerSid){
  if(-not $WorkerCredential){throw 'OTHER_USER_S4U_CREDENTIAL_REQUIRED'}
  [xml]$document=$Xml
  $principal=$document.Task.Principals.Principal
  if($principal.UserId -cne $WorkerSid -or $principal.LogonType -cne 'S4U' -or $principal.RunLevel -cne 'LeastPrivilege'){
   throw 'ISOLATED_S4U_PRINCIPAL_MISMATCH'
  }
  $resolved=([Security.Principal.NTAccount]::new($WorkerCredential.UserName)).Translate([Security.Principal.SecurityIdentifier]).Value
  if($resolved -cne $WorkerSid){throw 'S4U_CREDENTIAL_IDENTITY_MISMATCH'}
  $password=$null
  try{
   $password=$WorkerCredential.GetNetworkCredential().Password
   Register-ScheduledTask -TaskName $TaskName -Xml $Xml -User $WorkerCredential.UserName -Password $password -ErrorAction Stop|Out-Null
  }finally{$password=$null}
 }else{
  Register-ScheduledTask -TaskName $TaskName -Xml $Xml -ErrorAction Stop|Out-Null
 }
}
