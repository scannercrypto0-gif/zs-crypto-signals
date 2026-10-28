"""Frozen PR #7 content identities, Git blob SHA-1 at ab5875d182342c15982b9cec78205cd0497bdd3e."""
import hashlib
from pathlib import Path
import unittest

FROZEN = {
    ".github/workflows/stage03b3-auto.yml": "96516a847344cb9b21785a43e460c88c0d8debcb",
    ".github/workflows/stage03b3-capture.yml": "e18dc09e43eea456e8e9c62fd6f4f56a07006eac",
    ".github/workflows/stage03b3-preclose.yml": "811b0f8206cb3ff18ac9cb9e5258c7122184d57b",
    ".github/workflows/stage03b3-select.yml": "3d16ca065f8accaddfd95bfdfe8e801e364fa73f",
    "src/zs_smart_gate/stage03b3_auto.py": "2049292d39b0a0e508c0ed689923619598d15f14",
    "src/zs_smart_gate/stage03b3_capture.py": "ddfd0820942dcc1e915b59b41b73746603e782eb",
    "src/zs_smart_gate/stage03b3_manifest.py": "fa5cf0ccdfc8c95d2fa2778eb092cf55dc55f837",
    "src/zs_smart_gate/stage03b3_selection.py": "18ce532b421d11ace0be565b64c1721d7a9d8764",
    "src/zs_smart_gate/stage03b3_terminal.py": "a7e0aa1889d5e771dc04678e0cd4e99c2f6ca5b0",
    "tests/test_stage03b3.py": "5eeb1acfc704ca5d011a5b0ffc50e793fc65f7d1",
    "tests/test_stage03b3_auto.py": "fa854cd916f7d60acf88da0a334c46064f6188db"
}

class FrozenBaselineTests(unittest.TestCase):
    def test_stage03b3_blob_identities(self):
        root = Path(__file__).resolve().parents[1]
        for name, expected in FROZEN.items():
            with self.subTest(path=name):
                data = (root / name).read_bytes().replace(b"\r\n", b"\n")
                actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                self.assertEqual(actual, expected)

