"""Offline negative and boundary tests for P0 NTS decision logic."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

file = Path(__file__).resolve().parents[1] / "scripts/p0-nts-witness.py"
spec = importlib.util.spec_from_file_location("p0_nts_witness", file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = datetime(2026, 11, 7, 10, 0, 3, tzinfo=timezone.utc)
STAMP = (NOW - timedelta(seconds=2)).strftime("%a %b %d %H:%M:%S %Y")


def data(offset="0.02", delay="0.05", dispersion="0.03", auth="Yes", leap="Normal"):
    tracking = (
        "Ref time (UTC) : " + STAMP + "\n"
        "Leap status : " + leap + "\n"
        "System time : " + offset + " seconds slow of NTP time\n"
        "Root delay : " + delay + " seconds\n"
        "Root dispersion : " + dispersion + " seconds\n"
    )
    nts = "Name/IP address Mode KeyID Type KLen Last Atmp NAK Cook CLen\n" + (
        "162.159.200.1 NTS 1 15 256 10s 0 0 8 100\n"
    )
    ntpdata = "Authenticated : " + auth + "\nLeap status : Normal\n"
    return tracking, nts, ntpdata


class P0ClockEvidenceUnitTests(unittest.TestCase):
    def test_valid_authenticated_conservative_interval(self):
        r = module.judge(*data(), now=NOW, drift_measurement=.001)
        self.assertEqual(r["status"], "UTC_WITNESS_PLAUSIBLE_THIS_HOST_THIS_INSTANT_ONLY")
        self.assertAlmostEqual(r["conservative_assumed_uncertainty_seconds"], .201, places=5)
        self.assertEqual(r["market_pit"], "NOT_ATTESTED")

    def test_bad_packet_auth_fails(self):
        with self.assertRaisesRegex(module.WitnessBlocked, "NTP_PACKET_NOT_AUTHENTICATED"):
            module.judge(*data(auth="No"), now=NOW, drift_measurement=0)

    def test_missing_nts_key_fails(self):
        tracking, _, ntp = data()
        with self.assertRaisesRegex(module.WitnessBlocked, "NTS_AUTH_KEY_NOT_ESTABLISHED"):
            module.judge(tracking, "example.org - 0 0 0 0 - 0 0 0 0", ntp,
                         now=NOW, drift_measurement=0)

    def test_asymmetry_delay_not_halved_and_strict_less(self):
        with self.assertRaisesRegex(module.WitnessBlocked, "UNCERTAINTY_NOT_STRICTLY"):
            module.judge(*data(offset="0.5", delay="0.85", dispersion="0.05"),
                         now=NOW, drift_measurement=0)

    def test_stale_time_fails(self):
        with self.assertRaisesRegex(module.WitnessBlocked, "NTS_SAMPLE_STALE"):
            module.judge(*data(), now=NOW+timedelta(seconds=40),
                         drift_measurement=0)

    def test_wrong_leap_fails(self):
        with self.assertRaisesRegex(module.WitnessBlocked, "LEAP_NOT_NORMAL"):
            module.judge(*data(leap="Not synchronised"), now=NOW, drift_measurement=0)


if __name__ == "__main__":
    unittest.main()
