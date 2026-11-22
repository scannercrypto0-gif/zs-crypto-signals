<# DACL-only owned-D helper. No SACL/owner mutation or privilege elevation. #>
if(-not ('ZsOwnedDacl' -as [type])){
 $env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
 Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class ZsOwnedDacl {
 [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string s,uint rev,out IntPtr sd,out uint len);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetSecurityDescriptorDacl(IntPtr sd,out bool present,out IntPtr dacl,out bool defaulted);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode)] static extern uint SetNamedSecurityInfo(string path,uint type,uint info,IntPtr owner,IntPtr group,IntPtr dacl,IntPtr sacl);
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr p);
 public static void Set(string path,string sddl){
  IntPtr sd;uint n;if(!ConvertStringSecurityDescriptorToSecurityDescriptor(sddl,1,out sd,out n))throw new Win32Exception();
  try{bool present,def;IntPtr acl;if(!GetSecurityDescriptorDacl(sd,out present,out acl,out def)||!present||acl==IntPtr.Zero)throw new Exception("DACL_REQUIRED");
   uint code=SetNamedSecurityInfo(path,1,0x80000004,IntPtr.Zero,IntPtr.Zero,acl,IntPtr.Zero);
   if(code!=0)throw new Win32Exception((int)code);
  }finally{LocalFree(sd);}
 }
}
"@
}
function Set-ZsOwnedReadOnlyTree([string]$Root,[string]$WorkerSid){
 $base=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $base.StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_ACL_SCOPE_REQUIRED'}
 $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $worker=[Security.Principal.SecurityIdentifier]::new($WorkerSid).Value
 $queue=[Collections.Generic.Queue[string]]::new();$queue.Enqueue($base);$count=0
 while($queue.Count){
  $dir=$queue.Dequeue()
  if($dir -cne $base -and -not $dir.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'ACL_PATH_ESCAPE'}
  [ZsOwnedDacl]::Set($dir,('D:P(A;OICI;FA;;;'+$owner+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FRFX;;;'+$worker+')'))
  $count++
  foreach($item in Get-ChildItem -LiteralPath $dir -Force){
   if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'ACL_REPARSE_POINT_REFUSED'}
   if($item.PSIsContainer){$queue.Enqueue($item.FullName)}else{
    [ZsOwnedDacl]::Set($item.FullName,('D:P(A;;FA;;;'+$owner+')(A;;FA;;;SY)(A;;FA;;;BA)(A;;FRFX;;;'+$worker+')'))
    $count++
   }
  }
 }
 return $count
}
function Set-ZsWorkerStateRoot([string]$Root,[string]$WorkerSid){
 $base=[IO.Path]::GetFullPath($Root).TrimEnd('\')
 if(-not $base.StartsWith('D:\ZS-SMART-GATE\',[StringComparison]::OrdinalIgnoreCase)){throw 'D_OWNED_ACL_SCOPE_REQUIRED'}
 $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $worker=[Security.Principal.SecurityIdentifier]::new($WorkerSid).Value
 [ZsOwnedDacl]::Set($base,('D:P(A;OICI;FA;;;'+$owner+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;;FRFXFW;;;'+$worker+')(A;OICIIO;0x1301bf;;;'+$worker+')'))
 foreach($name in @('release.json','standing-authority.json','deployment-proof.json','DISABLED','STOP_REQUESTED','window.json','clock-catalog-map.json')){
  $path=Join-Path $base $name
  if(Test-Path -LiteralPath $path){[ZsOwnedDacl]::Set($path,('D:P(A;;FA;;;'+$owner+')(A;;FA;;;SY)(A;;FA;;;BA)(A;;FRFX;;;'+$worker+')'))}
 }
}
