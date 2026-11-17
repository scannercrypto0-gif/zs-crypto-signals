import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import certifi
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from zs_smart_gate.ops_nts_client import conditional_brackets, dependencies, run
from zs_smart_gate.ops_nts_protocol import dns_identity, extension, ke_record, parse_ke, stamp, verify_packet
from zs_smart_gate.stage05_contracts import ContractError, digest


class NTSTests(unittest.TestCase):
    def test_narrow_ke_negotiation_and_distinct_cookies(self):
        cookies = b"".join(ke_record(5, bytes([v])*32, False) for v in range(4))
        def records(host, port, cookie_records=cookies):
            return (ke_record(1,bytes(2)) + ke_record(4,bytes((0,15))) + cookie_records
                    + ke_record(6,host.encode(),False) + ke_record(7,struct.pack("!H",port),False)
                    + ke_record(0))
        host = "194.58.207.79"
        self.assertEqual(len(parse_ke(records(host,4123),host,4123)["cookies"]),4)
        for raw in (records("127.0.0.1",4123), records(host,123),
                    records(host,4123,ke_record(5,bytes(32),False)*4),
                    records(host,4123) + ke_record(0)):
            with self.assertRaises(ValueError):
                parse_ke(raw,host,4123)

    def test_real_aead_rejects_replay_tamper_and_unsynchronized_sample(self):
        key, identity, nonce = bytes(range(32)), b"x"*32, b"y"*16
        epoch = 1794891300
        origin = stamp(epoch)

        def response(leap=0):
            header = bytearray(48)
            header[0], header[1] = (leap << 6) | 0x24, 1
            header[24:48] = origin+stamp(epoch+.02)+stamp(epoch+.03)
            prefix = bytes(header) + extension(0x104, identity)
            ciphertext = AESSIV(key).encrypt(b"",[prefix,nonce])
            return prefix+extension(0x404,struct.pack("!HH",16,len(ciphertext))+nonce+ciphertext)

        def verify(raw, uid=identity, elapsed=.05):
            return verify_packet(raw,uid,key,origin,epoch,epoch+.05,elapsed)

        result = verify(response())
        self.assertFalse(result["absolute_UTC_certified"])
        self.assertLess(result["conditional_radius_seconds"], .1)
        with self.assertRaisesRegex(ValueError,"UNIQUE_ID"):
            verify(response(),b"z"*32)
        with self.assertRaises(InvalidTag):
            raw = response()
            verify(raw[:-1] + bytes((raw[-1]^1,)))
        with self.assertRaisesRegex(ValueError,"UNSYNCED"):
            verify(response(3))
        with self.assertRaisesRegex(ValueError,"LOCAL_CLOCK_STEP"):
            verify(response(),elapsed=.1)

    def test_deps_ca_hash_and_hostname(self):
        ca = Path(certifi.where())
        self.assertEqual(len(dependencies(ca,digest(ca.read_bytes()))),3)
        with self.assertRaisesRegex(ContractError,"CA_BUNDLE_PIN"):
            dependencies(ca,"0"*64)
        self.assertTrue(dns_identity("sth1.nts.netnod.se",["*.nts.netnod.se"]))
        self.assertFalse(dns_identity("sth1.nts.netnod.se",["*.netnod.se"]))

    def test_mock_combined_run_keeps_absolute_time_blocked(self):
        from datetime import datetime, timedelta, timezone
        from zs_smart_gate.stage05_contracts import canonical
        end = datetime.now(timezone.utc) + timedelta(seconds=120)
        anchor = 1794891300000
        def get(path, params, timeout):
            if path == "time":
                value = dict(serverTime=anchor+10)
            elif path == "exchangeInfo":
                value = dict(symbols=[dict(symbol=s,status="TRADING",quoteAsset="USDT",
                                           isSpotTradingAllowed=True) for s in ("BTCUSDT","ETHUSDT")])
            else:
                value = [[anchor-300000,"1","1","1","1","1",anchor-1,"1",0,"0","0"]]
            return 200,"26",canonical(value)

        def sample(root, index, *_):
            mark = (1, 4, 5, 8)[index]
            return dict(sample_local_received=1794891300+index/4, offset_seconds=0,
                        conditional_radius_seconds=.01,send_mono_ns=mark,receive_mono_ns=mark+1)

        with tempfile.TemporaryDirectory() as root, patch(
                "zs_smart_gate.ops_nts_client.establish", return_value=(b"",b"",[b""]*4,"pin")), patch(
                "zs_smart_gate.ops_nts_client.take_sample", side_effect=sample), patch(
                "zs_smart_gate.ops_nts_client.public_get", side_effect=get) as transport, patch(
                "zs_smart_gate.ops_nts_client.time.monotonic_ns", side_effect=(3, 7)):
            result = run(Path(root),ca_file="",ca_pin="pin",approved_ip="194.58.207.79",
                         time_end=end,spot_end=end)
        self.assertEqual((result["ke_attempts"],result["udp_attempts"],transport.call_count),(1,4,5))
        self.assertEqual(result["status"],"AUTHENTICATED_CONDITIONAL_ONLY")
        self.assertEqual(result["clock_absolute"],"NOT_VERIFIED")
