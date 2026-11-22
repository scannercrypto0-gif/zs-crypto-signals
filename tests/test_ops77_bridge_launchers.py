"""Native PS5.1 parsing and refusal of privileged clock writes under normal token."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
PS=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')

class LauncherTests(unittest.TestCase):
    def test_actual_powershell51_parser_accepts_all_new_launchers(self):
        paths=['ops77-tune-clock.ps1','prepare-stage05-owner-store.ps1','launch-ops77-telegram-pilot.ps1']
        for name in paths:
            path=ROOT/'scripts'/name
            command="$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('"+str(path)+"',[ref]$t,[ref]$e);if($e.Count){exit 2};$PSVersionTable.PSVersion.ToString()"
            result=subprocess.run([PS,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(result.stdout.strip().startswith('5.1.'))

    def test_clock_repair_refuses_normal_token_before_creating_output(self):
        from zs_smart_gate.marketwide_capture import _is_admin
        self.assertFalse(_is_admin(),'This Windows acceptance must run with normal token')
        head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
        root=Path('D:/ZS-SMART-GATE/temp/ops77-unprivileged-clock-test-must-not-exist')
        self.assertFalse(root.exists())
        result=subprocess.run([PS,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/ops77-tune-clock.ps1'),'-Head',head,'-Root',str(root)],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('WINDOWS_ADMINISTRATOR_TOKEN_REQUIRED',result.stderr)
        self.assertFalse(root.exists())
