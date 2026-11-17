"""Windows widget smoke test, without network or a configured live runner."""
from pathlib import Path
import json
import os
import runpy
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch


@skipUnless(os.name == "nt", "Windows dashboard")
class DashboardTests(TestCase):
    def test_foreground_start_and_stop(self):
        import tkinter as tk
        from tkinter import ttk

        real_tk = tk.Tk
        repo = Path(__file__).resolve().parents[1]
        with TemporaryDirectory(dir=repo) as tmp:
            output = Path(tmp)/"dashboard"
            finished = []

            def create():
                window = real_tk()
                window.withdraw()

                def check():
                    if (output/"run-1-exit.json").exists():
                        finished.append(json.loads((output/"run-1-exit.json").read_text()))
                        window.destroy()
                    else:
                        window.after(50, check)

                def exercise():
                    panel, = window.winfo_children()
                    buttons = {child.cget("text"):child for child in panel.winfo_children()
                               if isinstance(child, ttk.Button)}
                    buttons["Start offline checks"].invoke()
                    buttons["Stop checks"].invoke()
                    check()

                window.after_idle(exercise)
                window.after(8000, window.destroy)
                return window

            script = repo/"scripts"/"ops-dashboard.pyw"
            with patch.object(tk, "Tk", create), patch.object(sys, "argv",
                                                               [str(script), "--output", str(output)]):
                runpy.run_path(str(script), run_name="__main__")
            report, = finished
            self.assertTrue(report["stopped"])
            self.assertEqual(report["scope"], "OFFLINE_DIAGNOSTICS")
            self.assertTrue((output/"run-1-stderr.txt").is_file())
