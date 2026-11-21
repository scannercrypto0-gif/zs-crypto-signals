$ErrorActionPreference='Stop'
$root='D:\ZS-SMART-GATE\validation\OPS24-NORMAL-CLOCK-INSPECTION'
New-Item -ItemType Directory -Path $root -Force|Out-Null
$paths=@(
 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\W32Time',
 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\W32Time\Parameters',
 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\W32Time\Parameters'
)
$rows=@()
foreach($p in $paths){
 if(Test-Path -LiteralPath $p){
  $values=Get-ItemProperty -LiteralPath $p
  $acl=Get-Acl -LiteralPath $p
  $rows+=@{path=$p;values=@{Type=$values.PSObject.Properties['Type'].Value;NtpServer=$values.PSObject.Properties['NtpServer'].Value;ImagePath=$values.PSObject.Properties['ImagePath'].Value;ServiceDll=$values.PSObject.Properties['ServiceDll'].Value};
   owner=$acl.Owner;rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{@{sid=$_.IdentityReference.Value;rights=[int64]$_.RegistryRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
 }
}
$signatures=@()
foreach($name in @('w32tm.exe','w32time.dll')){
 $p=Join-Path $env:SystemRoot ('System32\'+$name)
 $sig=Get-AuthenticodeSignature -LiteralPath $p
 $signatures+=@{file=$name;status=$sig.Status.ToString();signer=$sig.SignerCertificate.Subject;sha256=(Get-FileHash $p).Hash.ToLowerInvariant()}
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
$report=@{elevated=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);registry=$rows;signatures=$signatures}
[IO.File]::WriteAllText((Join-Path $root 'inspection.private.json'),($report|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
$report|ConvertTo-Json -Depth 10

