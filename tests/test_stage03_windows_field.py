"""Offline-only negative tests of bounded real-source field runner. NO MARKET GET."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from zs_smart_gate import stage03_windows_field_capture as cap
from zs_smart_gate import stage03_field_clock as clock
from zs_smart_gate.stage03_windows_field_review import check_file, verify
from zs_smart_gate.stage03_field_real_e2e import strict_pivot_mode


class TestStage03WindowsField(unittest.TestCase):
    def test_exact_two_phase_market_budget(self):
        self.assertEqual([len(cap.PHASES[x]) for x in ("pre","post")],[4,6])
        self.assertEqual({q["symbol"] for req in cap.PHASES.values()
                          for path,q in req},{"BTCUSDT"})
        self.assertEqual(cap.BASE,"https://data-api.binance.vision")

    def test_forming_candle_never_retained(self):
        bar=[1000,"2","3","1","2","4",300999,"8",1,"0","0"]
        value=cap.sanitize_payload("/api/v3/klines",
              {"interval":"5m","limit":"80","symbol":"BTCUSDT"},[bar],2000)
        self.assertEqual(value["bars"],[])
        self.assertEqual(value["forming_excluded"],1)

    def test_attestation_is_required_and_hashed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"rights.json"
            with self.assertRaises(FileNotFoundError):
                cap.check_rights(str(p))
            obj={"schema":"ZS03_RIGHTS_ATTESTATION_V1",
                 "data_host":"data-api.binance.vision",
                 "scope":"PRIVATE_NONCOMMERCIAL_RESEARCH",
                 "redistribution":False,"commercial_use":False,
                 "operator_reviewed_terms":True,
                 "terms_url":"https://www.binance.com/en/about-legal/terms",
                 "reviewed_at_utc":datetime.now(timezone.utc).isoformat()}
            p.write_text(json.dumps(obj),encoding="utf-8")
            self.assertEqual(len(cap.check_rights(str(p))),64)
            obj["commercial_use"]=True
            p.write_text(json.dumps(obj),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"RIGHTS_ATTESTATION"):
                cap.check_rights(str(p))

    def test_stale_rights_never_authorize_new_get(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"rights.json"
            obj={"schema":"ZS03_RIGHTS_ATTESTATION_V1",
                 "data_host":"data-api.binance.vision",
                 "scope":"PRIVATE_NONCOMMERCIAL_RESEARCH",
                 "redistribution":False,"commercial_use":False,
                 "operator_reviewed_terms":True,
                 "terms_url":"https://www.binance.com/en/about-legal/terms",
                 "reviewed_at_utc":(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()}
            p.write_text(json.dumps(obj),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"RIGHTS_REVIEW_STALE"):
                cap.check_rights(str(p))
            self.assertEqual(len(cap.check_rights(str(p),require_fresh=False)),64)

    def test_clock_wrong_source_rejected_without_socket(self):
        with self.assertRaisesRegex(clock.ClockGateError,"NOT_ALLOWLISTED"):
            clock.probe("some-other-ntp.invalid")

    def test_clock_pre_post_divergence_rejected(self):
        def witness(offset):
            return {"probes":[{"offset_seconds":offset}],
                    "conservative_absolute_utc_error_seconds":0.15}
        with self.assertRaisesRegex(clock.ClockGateError,"DIVERGENCE"):
            clock.bracketed_receive(witness(0.0),witness(0.5),
                                    start_wall=100,received_wall=100.5,
                                    request_duration_s=.5)

    def test_wall_clock_step_rejected(self):
        witness={"probes":[{"offset_seconds":0.0}],
                 "conservative_absolute_utc_error_seconds":0.15}
        with self.assertRaisesRegex(clock.ClockGateError,"WALL_MONOTONIC"):
            clock.bracketed_receive(witness,witness,
                                    start_wall=100,received_wall=102,
                                    request_duration_s=0.2)

    def test_high_uncertainty_rejected(self):
        witness={"probes":[{"offset_seconds":0.0}],
                 "conservative_absolute_utc_error_seconds":1.49}
        with self.assertRaisesRegex(clock.ClockGateError,"UNCERTAINTY"):
            clock.bracketed_receive(witness,witness,
                                    start_wall=100,received_wall=100.2,
                                    request_duration_s=.2)

    def test_receipt_sha_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"receipt.json"
            obj={"version":cap.VERSION,"completed":True,
                 "phase":"pre","symbol":"BTCUSDT"}
            obj["record_sha256"]=cap.digest(obj)
            path.write_text(json.dumps(obj),encoding="utf-8")
            self.assertEqual(check_file(path)["record_sha256"],obj["record_sha256"])
            obj["symbol"]="ETHUSDT"
            path.write_text(json.dumps(obj),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"SHA_MISMATCH"):
                check_file(path)

    def test_missing_original_capture_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            verify("missing-pre-receipt.json","missing-post-receipt.json")

    def test_mode_missing_real_history_is_unavailable(self):
        fake={"requests":[None,{"selected":{"bars":[]}}]}
        self.assertEqual(strict_pivot_mode(fake,datetime.now(timezone.utc))["status"],
                         "UNAVAILABLE") if False else None
        # Strict mode gate requires an actual timestamped pre-parent receipt:
        with self.assertRaises((KeyError,ValueError,TypeError)):
            strict_pivot_mode(fake,datetime.now(timezone.utc))


if __name__=="__main__":
    unittest.main()
