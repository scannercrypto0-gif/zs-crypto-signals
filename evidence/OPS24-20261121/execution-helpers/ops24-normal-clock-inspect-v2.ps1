$ErrorActionPreference='Stop'
$root='D:\ZS-SMART-GATE\validation\OPS24-NORMAL-CLOCK-INSPECTION'
New-Item -ItemType Directory -Path $root -Force|Out-Null
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry64)
$rows=@()
foreach($name in @('SYSTEM\CurrentControlSet\Services\W32Time','SYSTEM\CurrentControlSet\Services\W32Time\Parameters','SOFTWARE\Policies\Microsoft\W32Time\Parameters')){
 $key=$base.OpenSubKey($name,$false)
 if($null -eq $key){continue}
 try{
  $acl=$key.GetAccessControl()
  $rows+=@{path=$name;values=@{Type=$key.GetValue('Type');NtpServer=$key.GetValue('NtpServer');ImagePath=$key.GetValue('ImagePath');ServiceDll=$key.GetValue('ServiceDll')};
    owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{@{sid=$_.IdentityReference.Value;rights=[int64]$_.RegistryRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
 }finally{$key.Dispose()}
}
$base.Dispose()
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

