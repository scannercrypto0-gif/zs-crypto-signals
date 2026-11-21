"""Actual Windows PowerShell disabled install, task XML and Git bundle restore."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Ops24ControllerTests(unittest.TestCase):
    def test_disabled_install_status_task_and_offline_restore_with_activation_hold(self):
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=ROOT,text=True).strip()
        with tempfile.TemporaryDirectory(dir="D:/ZS-SMART-GATE/temp") as folder:
            root=Path(folder)/"installation"
            def run(action):
                return subprocess.run(
                    ["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass",
                     "-File",str(ROOT/"scripts"/"ops24-windows.ps1"),"-Action",action,
                     "-Root",str(root),"-Source",str(ROOT),"-Head",head,"-Tree",tree],
                    capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
            installed=run("InstallDisabled")
            self.assertEqual(installed.returncode,0,installed.stderr.decode(errors="replace"))
            self.assertTrue((root/"DISABLED").exists())
            self.assertTrue((root/"STOP_REQUESTED").exists())
            record=json.loads((root/"release.json").read_bytes())
            self.assertEqual(record["clock_profile"],"WINDOWS_STATUS_PROTECTED_REGISTRY_V1")
            self.assertEqual(record["head"],head)
            self.assertTrue(Path(record['git_executable']).is_absolute())
            self.assertEqual(len(record['git_sha256']),64)
            self.assertIn('runtime',record['python'])
            built=run("BuildTask")
            self.assertEqual(built.returncode,0,built.stderr.decode(errors="replace"))
            xml=(root/"worker.disabled.xml").read_text(encoding="utf-16")
            self.assertIn("<Enabled>false</Enabled>",xml)
            self.assertIn("<RunLevel>LeastPrivilege</RunLevel>",xml)
            self.assertIn("<LogonType>S4U</LogonType>",xml)
            self.assertNotIn("HighestAvailable",xml)
            status=run("Status")
            self.assertEqual(status.returncode,0,status.stderr.decode(errors="replace"))
            self.assertTrue(json.loads(status.stdout)["disabled"])
            blocked=run("Register")
            self.assertNotEqual(blocked.returncode,0)
            self.assertIn("STANDING_REVIEWED_RELEASE_EVIDENCE",blocked.stderr.decode(errors="replace"))
            restored=run("Restore")
            self.assertEqual(restored.returncode,0,restored.stderr.decode(errors="replace"))
            self.assertIn("OFFLINE_RESTORE_VERIFIED",restored.stdout.decode(errors="replace"))
            # Reinstalling the identical disabled release is safe and allows
            # a real rollback pointer without starting any scheduled worker.
            repeated=run("InstallDisabled")
            self.assertEqual(repeated.returncode,0,repeated.stderr.decode(errors="replace"))
            rolled=run("Rollback")
            self.assertEqual(rolled.returncode,0,rolled.stderr.decode(errors="replace"))
            self.assertIn("ROLLED_BACK_DISABLED",rolled.stdout.decode(errors="replace"))

    def test_standard_role_setup_cannot_self_elevate_from_normal_operator(self):
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
            '-File',str(ROOT/'scripts/ops24-standard-role-probe.ps1'),'-Source',str(ROOT),
            '-Head','a'*40,'-Tree','b'*40,'-Root','D:/ZS-SMART-GATE/temp/never-created-by-nonadmin'],
             capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'REQUIRES_ADMIN',result.stderr)

    def test_service_account_description_fits_actual_windows_parameter_limit(self):
        import re
        source=(ROOT/'scripts/ops24-standard-role-probe.ps1').read_text(encoding='utf-8-sig')
        marker=re.search(r"\$marker='([^']+)'",source)[1]
        command="(Get-Command New-LocalUser).Parameters['Description'].Attributes | Where-Object {$_ -is [System.Management.Automation.ValidateLengthAttribute]} | Select-Object -ExpandProperty MaxLength"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                 capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stderr)
        maximum=int(result.stdout.strip())
        self.assertLessEqual(len(marker),maximum)
