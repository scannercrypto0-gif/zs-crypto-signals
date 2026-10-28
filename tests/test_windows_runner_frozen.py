"""Verify surviving immutable Stage03B3 research sources after the owner canceled GH execution.

Retired workflow paths and the old test source are preserved in prior Git commits;
absence from the current checkout is an intentional cancellation, NOT corruption.
"""
import hashlib
from pathlib import Path
import unittest

FROZEN = {
    "src/zs_smart_gate/stage03b3_auto.py": "2049292d39b0a0e508c0ed689923619598d15f14",
    "src/zs_smart_gate/stage03b3_capture.py": "ddfd0820942dcc1e915b59b41b73746603e782eb",
    "src/zs_smart_gate/stage03b3_manifest.py": "fa5cf0ccdfc8c95d2fa2778eb092cf55dc55f837",
    "src/zs_smart_gate/stage03b3_selection.py": "18ce532b421d11ace0be565b64c1721d7a9d8764",
    "src/zs_smart_gate/stage03b3_terminal.py": "a7e0aa1889d5e771dc04678e0cd4e99c2f6ca5b0",
    "tests/test_stage03b3.py": "5eeb1acfc704ca5d011a5b0ffc50e793fc65f7d1",
}

RETIRED_GH_WORKFLOWS = (
    ".github/workflows/stage03b3-auto.yml",
    ".github/workflows/stage03b3-capture.yml",
    ".github/workflows/stage03b3-preclose.yml",
    ".github/workflows/stage03b3-select.yml",
)


class FrozenBaselineTests(unittest.TestCase):
    def test_original_cancelled_github_workflows_not_in_active_checkout(self):
        root = Path(__file__).resolve().parents[1]
        for name in RETIRED_GH_WORKFLOWS:
            with self.subTest(path=name):
                self.assertFalse((root / name).exists(), "cancelled study workflow revived")


    def test_stage03b3_blob_identities(self):
        root = Path(__file__).resolve().parents[1]
        for name, expected in FROZEN.items():
            with self.subTest(path=name):
                data = (root / name).read_bytes().replace(b"\r\n", b"\n")
                actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                self.assertEqual(actual, expected)

