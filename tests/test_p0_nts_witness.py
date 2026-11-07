"""Offline strict four-output NTS peer identity validation (no network)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/p0-nts-witness.py"
spec = importlib.util.spec_from_file_location("p0_nts_witness", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 11, 7, 10, 0, 3, tzinfo=timezone.utc)
STAMP = (NOW - timedelta(seconds=2)).strftime("%a %b %d %H:%M:%S %Y")
IP, HEX = "162.159.200.1", "A29FC801"


def data(offset="0.02", delay="0.05", dispersion="0.03",
         packet_auth="Yes", leap="Normal"):
    tracking = (
        f"Reference ID : {HEX} ({IP})\n"
        f"Ref time (UTC) : {STAMP}\n"
        f"Leap status : {leap}\n"
        f"System time : {offset} seconds slow of NTP time\n"
        f"Root delay : {delay} seconds\n"
        f"Root dispersion : {dispersion} seconds\n"
    )
    auth = ("Name/IP address Mode KeyID Type KLen Last Atmp NAK Cook CLen\n"
            "=========================================================\n"
            f"{IP} NTS 1 30 128 42 0 0 8 64\n")
    ntp = (f"Remote address : {IP} ({HEX})\n"
           f"Authenticated : {packet_auth}\n"
           "NTP tests : 111 111 1111\n"
           "Leap status : Normal\n")
    sources = ("MS Name/IP address Stratum Poll Reach LastRx Last sample\n"
               f"^* {IP} 3 4 77 4 +22us[+500us] +/-7125us\n")
    return tracking, auth, ntp, sources


def judge(parts=None, now=NOW, drift=.001):
    t,a,n,s = data() if parts is None else parts
    return module.judge(t,a,n,sources=s,now=now,drift_measurement=drift)


class P0ClockEvidenceUnitTests(unittest.TestCase):
    def blocked(self, message, parts=None, **opts):
        with self.assertRaisesRegex(module.WitnessBlocked, message):
            judge(parts,**opts)

    def test_valid_source_matched_across_four_readouts(self):
        x=judge()
        self.assertEqual(x["selected_authenticated_source_ip"], IP)
        self.assertAlmostEqual(x["conservative_assumed_uncertainty_seconds"], .201)
        self.assertEqual(x["stamp_margin_evidence"], "UNVERIFIED_OPERATIONAL_ASSUMPTION")
        self.assertEqual(x["market_pit"], "NOT_ATTESTED")

    def test_packet_auth_fails(self):
        self.blocked("NTP_PACKET_NOT_AUTHENTICATED",data(packet_auth="No"))

    def test_nts_key_missing_fails(self):
        t,a,n,s=data()
        self.blocked("NTS_AUTH_KEY_NOT_ESTABLISHED",
                     (t,a.replace("NTS 1", "NTS 0"),n,s))

    def test_selected_x_authenticated_y_rejected(self):
        t,a,n,s=data()
        self.blocked("SELECTED_SOURCE_AUTH_IDENTITY_MISMATCH",
                     (t,a.replace(IP,"162.159.200.2"),n,s))

    def test_second_unselected_source_rejected(self):
        t,a,n,s=data()
        self.blocked("SOURCE_INVENTORY_NOT_SINGLETON",
                     (t,a,n,s+"^? 162.159.200.2 3 4 0 - +0ns +/-0ns\n"))

    def test_multiple_auth_peers_rejected(self):
        t,a,n,s=data()
        self.blocked("AUTH_INVENTORY_NOT_SINGLETON",
                     (t,a+"162.159.200.2 NTS 2 30 128 42 0 0 8 64\n",n,s))

    def test_no_selected_peer(self):
        t,a,n,s=data()
        self.blocked("SOURCE_NOT_SELECTED",(t,a,n,s.replace("^*","^?")))

    def test_ntp_remote_mismatch(self):
        t,a,n,s=data()
        self.blocked("NTP_REMOTE_IDENTITY_MISMATCH",
                     (t,a,n.replace(IP,"162.159.200.2"),s))

    def test_ntp_remote_hex_mismatch(self):
        t,a,n,s=data()
        self.blocked("NTP_REMOTE_IDENTITY_MISMATCH",
                     (t,a,n.replace(HEX,"A29FC802"),s))

    def test_tracking_reference_mismatch(self):
        t,a,n,s=data()
        self.blocked("TRACKING_REFERENCE_IDENTITY_MISMATCH",
                     (t.replace(HEX,"A29FC802"),a,n,s))

    def test_duplicate_remote_field(self):
        t,a,n,s=data()
        self.blocked("IDENTITY_FIELD_MISSING_OR_DUPLICATE",
                     (t,a,n+f"Remote address : {IP} ({HEX})\n",s))

    def test_ntp_checks_not_all_pass(self):
        t,a,n,s=data()
        self.blocked("NTP_CHECKS_NOT_ALL_PASS",
                     (t,a,n.replace("111 111 1111","111 101 1111"),s))

    def test_full_root_delay_and_strict_bound(self):
        self.blocked("UNCERTAINTY_NOT_STRICTLY",
                     data(offset="0.5",delay="0.85",dispersion="0.05"),drift=0)

    def test_stale_and_future_time(self):
        self.blocked("NTS_SAMPLE_STALE",now=NOW+timedelta(seconds=40))
        self.blocked("NTS_SAMPLE_STALE",now=NOW-timedelta(seconds=10))

    def test_wrong_leap(self):
        self.blocked("LEAP_NOT_NORMAL",data(leap="Not synchronised"))

    def test_negative_delay(self):
        self.blocked("NEGATIVE_UNCERTAINTY_COMPONENT",data(delay="-0.01"))


if __name__=="__main__":
    unittest.main()
