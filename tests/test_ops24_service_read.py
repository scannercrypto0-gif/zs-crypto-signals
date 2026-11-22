"""Service read-only DACL transformation; no actual service mutation in tests."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ServiceReadTests(unittest.TestCase):
    def test_additive_read_preserves_owner_group_audit_denies_and_is_idempotent(self):
        helper=ROOT/'scripts/ops24-service-read.ps1'
        command=". '"+str(helper)+"';$ErrorActionPreference='Stop';$sd=[Security.AccessControl.RawSecurityDescriptor]::new('O:SYG:SYD:(D;;0x20;;;BU)(A;;0x20000;;;SY)S:(AU;SA;0x1;;;BU)');$b=New-Object byte[] $sd.BinaryLength;$sd.GetBinaryForm($b,0);$a=[ZsClockServiceRead]::AddRead($b,'S-1-5-32-545');$after=[Security.AccessControl.RawSecurityDescriptor]::new($a,0);$again=[ZsClockServiceRead]::AddRead($a,'S-1-5-32-545');$sections=[Security.AccessControl.AccessControlSections]::Owner -bor [Security.AccessControl.AccessControlSections]::Group -bor [Security.AccessControl.AccessControlSections]::Audit;@{mask=$after.DiscretionaryAcl[2].AccessMask;old_count=$sd.DiscretionaryAcl.Count;new_count=$after.DiscretionaryAcl.Count;denied_mask=$after.DiscretionaryAcl[0].AccessMask;denied_type=$after.DiscretionaryAcl[0].AceQualifier.ToString();old_allow_mask=$after.DiscretionaryAcl[1].AccessMask;owner_group_audit_preserved=($sd.GetSddlForm($sections) -ceq $after.GetSddlForm($sections));idempotent=([Convert]::ToBase64String($a) -ceq [Convert]::ToBase64String($again))}|ConvertTo-Json -Compress"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',command],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stderr)
        row=json.loads(result.stdout)
        self.assertEqual(row['mask'],0x20005)
        self.assertEqual(row['new_count'],row['old_count']+1)
        self.assertEqual(row['denied_mask'],0x20)
        self.assertEqual(row['denied_type'],'AccessDenied')
        self.assertEqual(row['old_allow_mask'],0x20000)
        self.assertTrue(row['owner_group_audit_preserved'])
        self.assertTrue(row['idempotent'])
        self.assertEqual(row['mask'] & (0x10000|0x40000|0x80000|0x2|0x10|0x20|0x40|0x100),0)

    def test_normal_operator_cannot_mutate_service_security(self):
        helper=ROOT/'scripts/ops24-service-read.ps1'
        command=". '"+str(helper)+"';try{Enable-ZsProjectClockServiceRead -BackupRoot 'D:\\ZS-SMART-GATE\\secrets\\ops77-worker';exit 9}catch{if($_.Exception.Message -cne 'SERVICE_READ_SETUP_REQUIRES_ADMIN'){throw};'NONADMIN_SERVICE_MUTATION_REJECTED'}"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',command],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'NONADMIN_SERVICE_MUTATION_REJECTED')
