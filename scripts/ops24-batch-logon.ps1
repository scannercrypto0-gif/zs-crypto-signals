<# Project-account-only batch logon provisioning; no group/global policy replacement. #>
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP
if(-not ('ZsBatchLogon' -as [type])){
 Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class ZsBatchLogon {
 [StructLayout(LayoutKind.Sequential)] struct Attr {public uint Length;public IntPtr Root,Name;public uint Attributes;public IntPtr Descriptor,Quality;}
 [StructLayout(LayoutKind.Sequential)] struct UString {public ushort Length,MaximumLength;public IntPtr Buffer;}
 [DllImport("advapi32.dll")] static extern uint LsaOpenPolicy(IntPtr system,ref Attr attr,uint access,out IntPtr policy);
 [DllImport("advapi32.dll")] static extern uint LsaEnumerateAccountRights(IntPtr policy,byte[] sid,out IntPtr rights,out uint count);
 [DllImport("advapi32.dll")] static extern uint LsaAddAccountRights(IntPtr policy,byte[] sid,UString[] rights,uint count);
 [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(uint status);
 [DllImport("advapi32.dll")] static extern uint LsaFreeMemory(IntPtr memory);
 [DllImport("advapi32.dll")] static extern uint LsaClose(IntPtr policy);
 static void Check(uint code){if(code!=0)throw new Win32Exception((int)LsaNtStatusToWinError(code));}
 public static bool Ensure(string sidText){
  var sid=new SecurityIdentifier(sidText);var bytes=new byte[sid.BinaryLength];sid.GetBinaryForm(bytes,0);
  var a=new Attr();a.Length=(uint)Marshal.SizeOf(typeof(Attr));IntPtr policy;
  Check(LsaOpenPolicy(IntPtr.Zero,ref a,0x810,out policy));
  try{
   IntPtr rights;uint count;uint status=LsaEnumerateAccountRights(policy,bytes,out rights,out count);
   bool allowed=false,denied=false;
   if(status!=0 && status!=0xC0000034)Check(status);
   if(status==0){try{
    int size=Marshal.SizeOf(typeof(UString));
    for(uint i=0;i<count;i++){
     var r=(UString)Marshal.PtrToStructure(IntPtr.Add(rights,(int)i*size),typeof(UString));
     string value=Marshal.PtrToStringUni(r.Buffer,r.Length/2);
     allowed|=value=="SeBatchLogonRight";denied|=value=="SeDenyBatchLogonRight";
    }
   }finally{LsaFreeMemory(rights);}}
   if(denied)throw new InvalidOperationException("EXPLICIT_BATCH_DENY_REQUIRES_POLICY_REVIEW");
   if(allowed)return false;
   const string right="SeBatchLogonRight";
   var u=new UString();u.Length=(ushort)(right.Length*2);u.MaximumLength=(ushort)(u.Length+2);u.Buffer=Marshal.StringToHGlobalUni(right);
   try{Check(LsaAddAccountRights(policy,bytes,new UString[]{u},1));}finally{Marshal.FreeHGlobal(u.Buffer);}
   return true;
  }finally{LsaClose(policy);}
 }
}
"@
}
function Enable-ZsProjectBatchLogon {
 param([ValidateSet('ZS_SG_Research','ZS_SG_Worker')][string]$Name='ZS_SG_Research')
 $id=[Security.Principal.WindowsIdentity]::GetCurrent()
 if(-not([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'BATCH_LOGON_SETUP_REQUIRES_ADMIN'}
 $user=Get-LocalUser -Name $Name -ErrorAction Stop
 if($user.Description -cne 'ZS SMART GATE read-only standard worker'){throw 'PROJECT_ROLE_MARKER_REQUIRED'}
 if(Get-LocalGroupMember -SID 'S-1-5-32-544'|Where-Object {$_.SID.Value -eq $user.SID.Value}){throw 'STANDARD_PROJECT_ACCOUNT_REQUIRED'}
 $added=[ZsBatchLogon]::Ensure($user.SID.Value)
 [ordered]@{schema='zs.ops24.batch-logon.v1';project_account_only=$true;right='SeBatchLogonRight';added=$added;deny_rights_removed=$false;admin_membership_added=$false}
}
