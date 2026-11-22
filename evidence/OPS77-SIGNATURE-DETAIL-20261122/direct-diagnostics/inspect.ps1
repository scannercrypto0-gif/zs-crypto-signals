
$ErrorActionPreference='Stop'
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry64)
$names=@('SYSTEM\CurrentControlSet\Services\W32Time',
 'SYSTEM\CurrentControlSet\Services\W32Time\Parameters',
 'SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient',
 'SYSTEM\CurrentControlSet\Services\autotimesvc',
 'SYSTEM\CurrentControlSet\Services\autotimesvc\Parameters',
 'SOFTWARE\Policies\Microsoft\W32Time\Parameters',
 'SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpClient')
$rows=@()
foreach($name in $names){
 $key=$base.OpenSubKey($name,$false)
 if($null -eq $key){continue}
 try{
  $acl=$key.GetAccessControl()
  $rows+=@{path=$name;values=@{Type=$key.GetValue('Type');NtpServer=$key.GetValue('NtpServer');ImagePath=$key.GetValue('ImagePath');ServiceDll=$key.GetValue('ServiceDll');Enabled=$key.GetValue('Enabled')};
   owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
   rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
    @{sid=$_.IdentityReference.Value;rights=[int64]$_.RegistryRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
 }finally{$key.Dispose()}
}
$base.Dispose()
$system32=[Environment]::SystemDirectory
$sidText=''
foreach($service in @('W32Time','autotimesvc')){
 # Native account translation does not require opening the Service Control
 # Manager. Microsoft documents NT SERVICE\SvcName for service SID lookup.
 $account=[Security.Principal.NTAccount]::new('NT SERVICE',$service)
 $sid=$account.Translate([Security.Principal.SecurityIdentifier]).Value
 if($sid -notmatch '^S-1-5-80-(\d+-){4}\d+$'){throw 'SERVICE_SID_QUERY_FAILED'}
 $sidText+=$sid+"`n"
}
$signatures=@()
foreach($name in @('sc.exe','w32tm.exe','w32time.dll','svchost.exe','autotimesvc.dll')){
 $file=Join-Path $system32 $name
 $signature=Get-AuthenticodeSignature -LiteralPath $file
 $acl=Get-Acl -LiteralPath $file
 $signatures+=@{file=$name;status=$signature.Status.ToString();signer=$signature.SignerCertificate.Subject;
  sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant();
  owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
  rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object{
   @{sid=$_.IdentityReference.Value;rights=[int64]$_.FileSystemRights;type=$_.AccessControlType.ToString();propagation=[int]$_.PropagationFlags}})}
}
@{registry=$rows;signatures=$signatures;service_sid_text=$sidText;system32=$system32}|ConvertTo-Json -Depth 12 -Compress
