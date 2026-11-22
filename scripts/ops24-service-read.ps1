<# Add only SERVICE_QUERY_CONFIG|SERVICE_QUERY_STATUS|READ_CONTROL to the dedicated role.
   Existing DACL/deny ACEs retained. No SACL, owner, start/stop/change rights. #>
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
if(-not ('ZsClockServiceRead' -as [type])){
 Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
public static class ZsClockServiceRead {
 public const int ReadMask=0x20005;
 static bool Same(byte[] a,byte[] b){if(a.Length!=b.Length)return false;for(int i=0;i<a.Length;i++)if(a[i]!=b[i])return false;return true;}
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenSCManager(string machine,string database,uint access);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenService(IntPtr manager,string service,uint access);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool QueryServiceObjectSecurity(IntPtr service,uint info,byte[] data,uint size,out uint needed);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool SetServiceObjectSecurity(IntPtr service,uint info,byte[] data);
 [DllImport("advapi32.dll")] static extern bool CloseServiceHandle(IntPtr handle);
 public static byte[] AddRead(byte[] before,string sidText){
  var sid=new SecurityIdentifier(sidText);var sd=new RawSecurityDescriptor(before,0);
  if(sd.DiscretionaryAcl==null)throw new InvalidOperationException("NULL_SERVICE_DACL_REFUSED");
  int present=0;
  foreach(GenericAce entry in sd.DiscretionaryAcl){
   var ace=entry as CommonAce;
   if(ace!=null && !ace.IsCallback && ace.SecurityIdentifier==sid && ace.AceQualifier==AceQualifier.AccessAllowed && (ace.AceFlags&AceFlags.InheritOnly)==0)present|=ace.AccessMask;
  }
  int missing=ReadMask&~present;
  if(missing==0)return before;
  int index=sd.DiscretionaryAcl.Count;
  for(int i=0;i<sd.DiscretionaryAcl.Count;i++)if((sd.DiscretionaryAcl[i].AceFlags&AceFlags.Inherited)!=0){index=i;break;}
  sd.DiscretionaryAcl.InsertAce(index,new CommonAce(AceFlags.None,AceQualifier.AccessAllowed,missing,sid,false,null));
  var output=new byte[sd.BinaryLength];sd.GetBinaryForm(output,0);return output;
 }
 public static byte[] Read(IntPtr service){
  uint size;QueryServiceObjectSecurity(service,4,null,0,out size);
  if(size==0 || size>65536)throw new Win32Exception(Marshal.GetLastWin32Error());
  var bytes=new byte[size];if(!QueryServiceObjectSecurity(service,4,bytes,size,out size))throw new Win32Exception();return bytes;
 }
 public static string Grant(string sidText,string backup){
  var manager=OpenSCManager(null,null,1);if(manager==IntPtr.Zero)throw new Win32Exception();
  try{
   var service=OpenService(manager,"W32Time",0x60000);if(service==IntPtr.Zero)throw new Win32Exception();
   try{
    var before=Read(service);
    if(!System.IO.File.Exists(backup)){
     using(var file=new System.IO.FileStream(backup,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.None)){file.Write(before,0,before.Length);file.Flush(true);}
    }
    var after=AddRead(before,sidText);
    bool changed=!Same(before,after);
    if(changed && !SetServiceObjectSecurity(service,4,after))throw new Win32Exception();
    var observed=Read(service);
    if(!Same(observed,AddRead(observed,sidText)))throw new InvalidOperationException("SERVICE_READ_GRANT_NOT_OBSERVED");
    using(var sha=System.Security.Cryptography.SHA256.Create()){
     return (changed?"true":"false")+"|"+BitConverter.ToString(sha.ComputeHash(before)).Replace("-","").ToLowerInvariant()+"|"+BitConverter.ToString(sha.ComputeHash(observed)).Replace("-","").ToLowerInvariant();
    }
   }finally{CloseServiceHandle(service);}
  }finally{CloseServiceHandle(manager);}
 }
}
"@
}
function Enable-ZsProjectClockServiceRead {
 param([Parameter(Mandatory=$true)][string]$BackupRoot)
 $id=[Security.Principal.WindowsIdentity]::GetCurrent()
 if(-not([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'SERVICE_READ_SETUP_REQUIRES_ADMIN'}
 $root=[IO.Path]::GetFullPath($BackupRoot).TrimEnd('\')
 if($root -cne 'D:\ZS-SMART-GATE\secrets\ops77-worker'){throw 'PROTECTED_ROLE_VAULT_REQUIRED'}
 $user=Get-LocalUser -Name 'ZS_SG_Worker' -ErrorAction Stop
 if($user.Description -cne 'ZS SMART GATE read-only standard worker'){throw 'PROJECT_ROLE_MARKER_REQUIRED'}
 if(Get-LocalGroupMember -SID 'S-1-5-32-544'|Where-Object {$_.SID.Value -eq $user.SID.Value}){throw 'STANDARD_PROJECT_ACCOUNT_REQUIRED'}
 $values=[ZsClockServiceRead]::Grant($user.SID.Value,(Join-Path $root 'w32time-before-read-grant.sd')) -split '\|'
 [ordered]@{schema='zs.ops24.service-read-grant.v1';service='W32Time';mask=131077;changed=($values[0] -eq 'true');before_sha256=$values[1];after_sha256=$values[2];start_stop_change_config_granted=$false;owner_sacl_changed=$false;original_descriptor_backup_local=$true}
}
