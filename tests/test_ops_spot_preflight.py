from unittest import TestCase
from datetime import datetime, timezone

from zs_smart_gate.ops_spot_preflight import SYMBOLS, run_preflight
from zs_smart_gate.stage05_contracts import canonical, utc_now


class PreflightTests(TestCase):
    def execute(self, override=None, clocks=None):
        attempts, receipts = [], []
        anchor = 1794891300000

        def get(path, params, timeout):
            attempts.append((path, params, timeout))
            if override is not None:
                forced = override(len(attempts))
                if forced is not None:
                    return forced
            payload = {"serverTime":anchor+1000}
            if path == "exchangeInfo":
                payload = {"symbols":[dict(symbol=s, quoteAsset="USDT", status="TRADING",
                                           isSpotTradingAllowed=True) for s in SYMBOLS]}
            elif path == "klines":
                payload = [[anchor-300000,"1","1","1","1","1",anchor-1,"1",1,"0","0","0"]]
            return 200, "20", canonical(payload)

        run = run_preflight(get=get, monotonic=clocks or (lambda: 0),
                            utc_now=lambda: utc_now(lambda: datetime(2026, 11, 17, 5, 0, 0, 123456, timezone.utc)), record=receipts.append)
        return run, attempts, receipts

    def test_fixed_five_attempts_and_closed_candle_anchor(self):
        run, attempts, receipts = self.execute()
        self.assertEqual(run["status"], "SOURCE_READBACK_PASS_CLOCK_PENDING")
        self.assertEqual(run["independent_clock"], "NOT_VERIFIED")
        self.assertEqual(run["estimated_weight"], 26)
        self.assertEqual([r[0] for r in attempts], ["time","exchangeInfo","klines","klines","time"])
        self.assertEqual([r[1]["symbol"] for r in attempts if r[0]=="klines"], list(SYMBOLS))
        self.assertEqual(len(receipts), 10)
        self.assertTrue(all("response_sha256" in row for row in receipts[1::2]))

    def test_http_quota_and_bad_candles_stop_without_retry(self):
        for response, reason in (((429,None,b""),"OPS_HTTP_429"), ((302,None,b""),"OPS_HTTP_302"),
                                 ((200,None,b"{}"),"OPS_QUOTA_HEADROOM_UNVERIFIED"),
                                 ((200,"20",b"[]"),"OPS_CLOSED_CANDLE_INVALID")):
            run, attempts, receipts = self.execute(lambda index: response if index==3 else None)
            self.assertEqual(run["status"],reason)
            self.assertEqual(len(attempts),3)
            self.assertEqual(receipts[-1]["state"],"STOPPED")

    def test_elapsed_cap_stops_before_second_attempt(self):
        ticks = iter((0, 0, 5, 120))
        run, attempts, _ = self.execute(clocks=lambda: next(ticks))
        self.assertEqual(run["status"],"OPS_BUDGET_STOP")
        self.assertEqual(len(attempts),1)
