import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from zs_smart_gate.ops_windows_watchdog import run_tree


@unittest.skipUnless(os.name == "nt", "Windows Job Objects")
class WatchdogTests(unittest.TestCase):
    def test_normal_nonzero_exit_preserved(self):
        child = "import sys; assert sys.stdin.buffer.readline() == b'ZS-START\\n'; sys.exit(37)"
        self.assertEqual(run_tree([sys.executable, "-c", child], timeout=5), 37)

    def test_timeout_kills_descendant_only(self):
        with TemporaryDirectory() as root:
            marker = Path(root) / "pid"
            child = (
                "import pathlib, subprocess, sys, time;"
                "assert sys.stdin.buffer.readline() == b'ZS-START\\n';"
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            )
            outsider = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            try:
                self.assertEqual(run_tree([sys.executable, "-c", child, str(marker)], timeout=3), 124)
                pid = int(marker.read_text())
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                     f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{exit 1}}"],
                    timeout=10, capture_output=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIsNone(outsider.poll())
            finally:
                outsider.kill()
                outsider.wait(timeout=5)

    def test_operator_interrupt_returns_130_and_cleans_up(self):
        original = subprocess.Popen.wait

        def wait(proc, timeout=None):
            if timeout == 13:
                raise KeyboardInterrupt
            return original(proc, timeout=timeout)

        with patch.object(subprocess.Popen, "wait", wait):
            self.assertEqual(run_tree([sys.executable, "-c", "import time; time.sleep(60)"], 13), 130)

