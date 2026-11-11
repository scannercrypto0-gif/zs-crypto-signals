"""One bounded, read-only BTCUSDT qualification observation on Windows."""
import argparse
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import sys
import time

import zs_smart_gate
from zs_smart_gate import setup021
from zs_smart_gate.binance_live import to_candles
from zs_smart_gate.core import MarketSnapshot
from zs_smart_gate.e2e51 import public_get
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03_qv1_intraday_up import Inputs, POLICY_SHA256, evaluate_up, inputs_payload, inputs_sha256
from zs_smart_gate.stage03_qv1_policy import Policy, verify_event_bracket, _gates
from zs_smart_gate.stage05_contracts import canonical, digest, parse_utc
from zs_smart_gate.stage05_custody import LocalOutbox

SYMBOL = "BTCUSDT"
SCOPE = "APPROVED_REAL_SOURCE"
FEED = "BINANCE_SPOT_PUBLIC_REST"
WINDOWS = {"5m": 300000, "30m": 1800000, "1h": 3600000, "4h": 14400000}


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc)


def stamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def netnod_probe(archive):
    # Use the existing audited NTS packet verifier with Netnod's documented
    # Stockholm key exchange and a narrowly pinned timestamp server.
    zs_smart_gate.__path__.append(str(archive / "src" / "zs_smart_gate"))
    from zs_smart_gate import stage03_nts_authority as authority
    parser = inspect.getsource(authority.parse_ke)
    parser = parser.replace("if host != original_host:", "if host != '194.58.207.79':")
    parser = parser.replace("if body != b'\\0{':", "if body != struct.pack('!H', 4123):").replace("port = 123", "port = 4123")
    exec(parser, vars(authority))
    probe = archive / "scripts" / "stage03-nts-probe.py"
    original = probe.read_text(encoding="utf-8")
    code = original.replace("time.cloudflare.com", "sth1.nts.netnod.se").replace(
        "sock.connect(('sth1.nts.netnod.se',123))",
        "if (negotiated['host'], negotiated['port']) != ('194.58.207.79', 4123):\n"
        "                raise ValueError('NETNOD_ENDPOINT_MISMATCH')\n"
        "            sock.connect((negotiated['host'], negotiated['port']))")
    if code == original or "NETNOD_ENDPOINT_MISMATCH" not in code:
        raise ValueError("NTS_PROBE_SOURCE_MISMATCH")
    namespace = {"__name__": "bounded_netnod"}
    exec(compile(code, str(probe), "exec"), namespace)
    return namespace["run"]


def observe(root, archive, anchor):
    probe = netnod_probe(archive)
    receipts = []
    samples = []

    def clock_sample(name):
        start = time.monotonic_ns()
        result = probe(root / name)
        end = time.monotonic_ns()
        samples.append({"name": name, "started_mono_ns": start, "returned_mono_ns": end, "result": result})
        (root / "clock-summary.json").write_bytes(canonical(samples))
        if result["status"] != "NTS_AUTHENTICATED_CLOCK_PARTIAL":
            raise ValueError("CLOCK_SAMPLE_FAILED:" + name)

    def get(path, **params):
        payload = public_get(path, {"symbol": SYMBOL, **params})
        at = datetime.now(timezone.utc)
        receipts.append({"path": path, "params": params, "received_at": stamp(at), "payload": payload})
        (root / "market-receipts.json").write_bytes(canonical(receipts))
        return payload, at

    target_ms = anchor * 1000
    for frame, period in WINDOWS.items():
        close_ms = target_ms // period * period
        values, _ = get("klines", interval=frame, limit="22" if frame == "5m" else "1", endTime=str(close_ms-1))
        if len(values) != (22 if frame == "5m" else 1) or values[-1][6]+1 != close_ms:
            raise ValueError("CLOSED_KLINE_BOUNDARY:" + frame)
    get("exchangeInfo")
    get("ticker/bookTicker")
    clock_sample("before-availability")
    get("ticker/24hr")
    available_marker = time.monotonic_ns()
    clock_sample("after-availability")
    clock_sample("before-decision")
    decision = datetime.now(timezone.utc)
    decision_marker = time.monotonic_ns()
    clock_sample("after-decision")
    capture = dict(anchor=anchor, available_marker=available_marker, decision_marker=decision_marker,
                   decision_at=stamp(decision))
    (root / "capture-markers.json").write_bytes(canonical(capture))
    evaluate_capture(root, receipts, samples, capture)


def evaluate_capture(root, receipts, samples, capture):
    anchor = capture["anchor"]
    available_marker, decision_marker = capture["available_marker"], capture["decision_marker"]
    decision = parse_utc(capture["decision_at"])
    first, second, third, fourth = (
        (sample["started_mono_ns"], sample["returned_mono_ns"], sample["result"]["sample"])
        for sample in samples if sample["result"]["status"] == "NTS_AUTHENTICATED_CLOCK_PARTIAL"
    )
    rows = {r["params"]["interval"]: (r["payload"], parse_utc(r["received_at"]))
            for r in receipts if r["path"] == "klines"}
    _, _, _, _, info_row, book_row, ticker_row = receipts
    info, book, ticker = (row["payload"] for row in (info_row, book_row, ticker_row))
    book_at, ticker_at = (parse_utc(row["received_at"]) for row in (book_row, ticker_row))

    def interval(before, after, marker, at, domain):
        def edges(sample):
            center = sample["sample_local_received"] + sample["offset_seconds"]
            # Add 1 ms margin beyond the authenticated protocol radius.
            radius = sample["conditional_radius_seconds"] + 0.001
            return center-radius, center+radius
        return dict(monotonic_domain=domain, host_at=stamp(at), utc_lower=stamp(utc(edges(before[2])[0])),
                    utc_upper=stamp(utc(edges(after[2])[1])), before_mono_ns=before[1],
                    event_mono_ns=marker, after_mono_ns=after[0])

    symbol, = info["symbols"]
    if symbol["symbol"] != SYMBOL or book["symbol"] != SYMBOL or ticker["symbol"] != SYMBOL:
        raise ValueError("MARKET_SYMBOL_MISMATCH")
    ticker_age = ticker_at.timestamp() - ticker["closeTime"]/1000
    if not -0.25 <= ticker_age <= 89:
        raise ValueError("TICKER_SOURCE_TIMESTAMP_OUTSIDE_WINDOW")
    market = MarketSnapshot(SYMBOL, symbol["quoteAsset"], symbol["isSpotTradingAllowed"], symbol["status"],
                            ticker["quoteVolume"], book["bidPrice"], book["askPrice"], ticker_at)
    klines, received = rows["5m"]
    def window(frame):
        values, at = rows[frame]
        bar = values[-1]
        return CandleWindow(frame, utc(bar[0]/1000), utc((bar[6]+1)/1000), at, at, FEED,
                            bar[1], bar[2], bar[3], bar[4], bar[5], bar[7])
    parent, hourly, four_hour = (window(frame) for frame in ("30m", "1h", "4h"))
    child = CandleWindow.from_five_minute(to_candles(klines, received)[-1], source_id=FEED)
    candles = {bar.timeframe: {"feed": FEED, "symbol": SYMBOL, "closed": True,
               **{key: stamp(getattr(bar,key)) for key in ("open_at","close_at","received_at","available_at")}}
               for bar in (child, parent, hourly, four_hour)}
    quote = dict(bound_feed=FEED, available_at=stamp(ticker_at), book_symbol=SYMBOL, ticker_symbol=SYMBOL,
                 quote_asset=market.quote_asset, window="ROLLING_24H", bid=str(market.bid),
                 ask=str(market.ask), quote_volume=str(market.quote_volume_24h))
    for key, at in (("book", book_at), ("ticker", ticker_at)):
        quote.update({key+"_"+field: stamp(at) for field in ("observed_at", "received_at", "available_at")})
    setup = setup021.evaluate(symbol=SYMBOL, klines=klines, market=market,
                              received_at=received, decision_at=decision, partition="DEV")
    setup_state = {"CLOSED_CAUSAL_TRIGGER": "DETECTED_SIGNAL", "NO_BREAKOUT": "RESEARCH_CANDIDATE",
                   "NO_FALSE_TO_TRUE_TRANSITION": "RESEARCH_CANDIDATE"}.get(setup["reason_codes"][0], "UNKNOWN")
    source = dict(venue="BINANCE_SPOT", feed=FEED, scope=SCOPE, path=["INTRADAY","UP"], symbol=SYMBOL,
                  event_close_at=stamp(parent.close_at), decision_at=stamp(decision), liquidity=quote,
                  clock=dict(bound_feed=FEED, available_at=stamp(decision)),
                  receipts_sha256=digest(canonical(receipts)), candles_sha256=digest(canonical(candles)),
                  components_sha256=digest(canonical({})), setup_state=setup_state)
    row = dict(source=source, source_scope=SCOPE, horizon="INTRADAY", direction="UP", setup_version="1.1",
               symbol=SYMBOL, event_close_at=source["event_close_at"], decision_at=source["decision_at"],
               candles=candles, components={}, setup_state=source["setup_state"])
    data = Inputs(row, klines, market, parent, (hourly, four_hour),
                  ReconciliationTolerance(0, 0, 0, "EXACT_BINANCE_SPOT"), received)
    source["joined_inputs_sha256"] = inputs_sha256(data)
    row["source_sha256"] = digest(canonical(source))
    domain = digest(canonical([anchor, available_marker, decision_marker]))
    witness = dict(identity="NETNOD_STOCKHOLM", method="AUTHENTICATED_EVENT_BRACKET_V1",
                   source_sha256=row["source_sha256"], decision_at=stamp(decision),
                   calibration_ref=digest(canonical(samples)), monotonic_domain=domain,
                   availability=interval(first, second, available_marker, ticker_at, domain),
                   decision=interval(third, fourth, decision_marker, decision, domain))
    policy = Policy("OWNER_DELEGATED_RESEARCH_OBSERVATION", SCOPE, None, 1499999, 0)
    base = evaluate_up(data, policy_sha256=POLICY_SHA256)
    # Research observation only. Static production trust registries stay empty.
    gates = _gates(data, base, policy, witness, digest(canonical(witness)))
    gates["UTC_WITNESS"] = verify_event_bracket(witness, decision, ticker_at, policy)
    outcome = "UNKNOWN" if "UNKNOWN" in gates.values() else "REJECTED" if "FAIL" in gates.values() else "QUALIFIED"
    record = dict(scope="READ_ONLY_MARKET_QUALIFICATION_RESEARCH", observation_outcome=outcome,
                  production_qualification_enabled=False, signal_id=None, gates=gates,
                  decision_time_semantics="INPUT_SNAPSHOT_FROZEN_BEFORE_OFFLINE_EVALUATION",
                  policy_sha256=policy.sha256, source=row, joined_inputs=inputs_payload(data),
                  witness=witness, witness_sha256=digest(canonical(witness)), evaluator=base)
    raw = canonical(record)
    journal = LocalOutbox(root / "audit.sqlite")
    key = "qv-observation/" + row["source_sha256"]
    journal.create_if_absent(key, raw)
    if LocalOutbox(root / "audit.sqlite").read(key) != raw:
        raise ValueError("READBACK_MISMATCH")
    (root / "qualification.json").write_bytes(raw)
    print(json.dumps(dict(outcome=outcome, gates=gates, readback_sha256=digest(raw),
                          setup_reason=base["setup_reason"], market_requests=len(receipts), time_samples=len(samples))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anchor", type=int)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.output.resolve().drive.upper() != "D:":
        raise SystemExit("PRIVATE_D_REQUIRED")
    if args.replay:
        def read(name):
            return json.loads((args.output / name).read_bytes())
        evaluate_capture(args.output, read("market-receipts.json"), read("clock-summary.json"),
                         read("capture-markers.json"))
        return
    if args.archive is None or args.anchor is None or args.anchor % 1800 or not 2 <= time.time()-args.anchor < 50:
        raise SystemExit("OUTSIDE_FRESH_30M_CAPTURE_WINDOW")
    args.output.mkdir(exist_ok=False)
    observe(args.output, args.archive, args.anchor)


if __name__ == "__main__":
    main()
