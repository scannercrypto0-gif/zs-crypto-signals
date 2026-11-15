"""Bounded two-asset public Spot capture and R0/R1/R2 replay."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import time

from zs_smart_gate.binance_live import timestamp
from zs_smart_gate.e2e51 import public_get
from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.scanner import build_universe, select_sample
from zs_smart_gate.stage03_r1_closed_parent import Closed30mItem, MarketReceipt, _evaluate_closed_30m
from zs_smart_gate.stage03_r2_raw_features import _attach_raw_features
from zs_smart_gate.stage03_qv1_policy import Policy, verify_event_bracket
from zs_smart_gate.stage05_contracts import canonical, digest, parse_utc

POOL = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
FRAMES = {"30m": 1800000, "5m": 300000, "1h": 3600000, "4h": 14400000}
SCOPE = "RECORDED_PUBLIC_SPOT"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def selection(receipts):
    listing, ticker, book = receipts[:3]
    expected = json.dumps(POOL, separators=(",", ":"))
    for receipt, path in zip((listing, ticker, book), ("exchangeInfo", "ticker/24hr", "ticker/bookTicker")):
        if receipt["path"] != path or receipt["params"] != {"symbols": expected}:
            raise ValueError("INVENTORY_REQUEST_MISMATCH")
    inventory = build_universe(listing["payload"], ticker["payload"], book["payload"],
                               parse_utc(book["received_at"]))
    if {row.symbol for row in inventory} != set(POOL):
        raise ValueError("INVENTORY_MISSING_ASSET")
    selected = select_sample(inventory, 2, 0)
    if len(selected) != 2:
        raise ValueError("TWO_ELIGIBLE_ASSETS_REQUIRED")
    return inventory, selected


def candle_plan(symbol, anchor):
    for frame, period in FRAMES.items():
        yield {"symbol": symbol, "interval": frame, "limit": "6" if frame == "5m" else "1",
               "endTime": str(anchor // period * period - 1)}


def evaluate(raw):
    capture = json.loads(raw)
    receipts = capture["receipts"]
    inventory, selected = selection(receipts)
    anchor = capture["anchor_ms"]
    if len(receipts) != 11 or anchor % FRAMES["30m"]:
        raise ValueError("CAPTURE_SIZE_OR_ANCHOR")
    closed = timestamp(anchor)
    ready = parse_utc(receipts[-1]["received_at"])
    decision = parse_utc(capture["decision_at"])
    arrivals = [parse_utc(row["received_at"]) for row in receipts]
    if arrivals != sorted(arrivals) or not closed < arrivals[0] <= ready < decision:
        raise ValueError("CAPTURE_RECEIPT_ORDER")
    if (decision-arrivals[0]).total_seconds() > 90:
        raise ValueError("MARKET_INPUT_NOT_FRESH")
    ticker_rows = {row["symbol"]:row for row in receipts[1]["payload"]}
    for item in selected:
        age = arrivals[1].timestamp() - ticker_rows[item.symbol]["closeTime"]/1000
        if not -0.25 <= age <= 89:
            raise ValueError("TICKER_TIME_OUTSIDE_WINDOW")
    domain = digest(canonical(capture["markers"]))
    samples = capture["samples"]

    def bracket(i, label, at):
        before, after = samples[i:i+2]
        def edge(row, side):
            sample = row["result"]["sample"]
            center = sample["sample_local_received"] + sample["offset_seconds"]
            return datetime.fromtimestamp(center + side * (sample["conditional_radius_seconds"] + .001),
                                          timezone.utc).isoformat().replace("+00:00", "Z")
        return dict(monotonic_domain=domain, host_at=at, utc_lower=edge(before,-1), utc_upper=edge(after,1),
                    before_mono_ns=before["end"], event_mono_ns=capture["markers"][label],
                    after_mono_ns=after["start"])

    if len(samples) != 4 or any(row["result"]["status"] != "NTS_AUTHENTICATED_CLOCK_PARTIAL" for row in samples):
        raise ValueError("CLOCK_SAMPLES_INVALID")
    witness = dict(monotonic_domain=domain, availability=bracket(0,"availability",receipts[-1]["received_at"]),
                   decision=bracket(2,"decision",capture["decision_at"]))
    if verify_event_bracket(witness, decision, ready, Policy("BOUNDED_RESEARCH", SCOPE, None, 1499999, 0)) != "PASS":
        raise ValueError("CLOCK_BRACKETS_NOT_ADMISSIBLE")

    results = []
    for index, entry in enumerate(selected):
        block = receipts[3+4*index:7+4*index]
        windows = {}
        feed = "BINANCE_SPOT_PUBLIC_REST:" + entry.symbol
        for receipt, params in zip(block, candle_plan(entry.symbol, anchor)):
            frame = params["interval"]
            at = parse_utc(receipt["received_at"])
            bars = receipt["payload"]
            if receipt["path"] != "klines" or receipt["params"] != params or len(bars) != int(params["limit"]):
                raise ValueError("CANDLE_RECEIPT_BINDING")
            if bars[-1][6] != int(params["endTime"]):
                raise ValueError("CANDLE_CLOSE_MISMATCH")
            windows[frame] = tuple(CandleWindow(
                frame, timestamp(bar[0]), timestamp(bar[6]+1), at, at, feed,
                bar[1], bar[2], bar[3], bar[4], bar[5], bar[7]) for bar in bars)
            if any(bar.errors_at(decision) for bar in windows[frame]):
                raise ValueError("CANDLE_INVALID")
        manifest = digest(canonical({"symbol": entry.symbol, "market": receipts[:3], "candles": block,
                                     "witness": witness, "clock_samples_sha256": digest(canonical(samples))}))
        observed = entry.market.observed_at
        item = Closed30mItem(entry.market, MarketReceipt(feed, observed, observed, ready), entry.symbol,
                             windows["30m"][0], windows["5m"], (windows["1h"][0], windows["4h"][0]),
                             manifest, source_scope=SCOPE)
        row = _evaluate_closed_30m(item, closed_at=closed, decision_at=decision,
                                  source_scope=SCOPE, expected_feed=feed)
        _attach_raw_features(item, row, decision)
        if row["evaluation_status"] != "POLICY_HOLD" or row["raw_features_status"] != "RESEARCH_MEASURED":
            raise ValueError("R0_R1_R2_NOT_ADMITTED:" + entry.symbol + ":" + str(row["reason_codes"]))
        results.append(row)
    if any(len({row[key] for row in results}) != 2 for key in ("event_id","raw_features_sha256","source_manifest_sha256")):
        raise ValueError("CROSS_ASSET_IDENTITY_COLLISION")
    return dict(capture_sha256=digest(raw), market_requests=len(receipts), clock_samples=len(samples),
                inventory={row.symbol:row.status for row in inventory}, rows=results, witness=witness)


def collect(root, archive):
    started = time.monotonic()
    probe = runpy.run_path(str(Path(__file__).with_name("probe-qv1-market-qualification.py")))
    clock = probe["netnod_session"](archive, root / "clock-session")
    receipts, samples = [], []
    anchor = int(time.time() * 1000) // FRAMES["30m"] * FRAMES["30m"]

    def get(path, params):
        if len(receipts) >= 11 or time.monotonic()-started > 155:
            raise ValueError("REQUEST_BUDGET")
        receipt = dict(path=path, params=params, started_at=now())
        receipts.append(receipt)
        (root / "attempts.json").write_bytes(canonical(receipts))
        receipt.update(payload=public_get(path,params), received_at=now())

    def sample(name):
        start = time.monotonic_ns()
        result = clock(root / name)
        samples.append(dict(start=start, end=time.monotonic_ns(), result=result))

    shared = {"symbols":json.dumps(POOL,separators=(",",":"))}
    for endpoint in ("exchangeInfo","ticker/24hr","ticker/bookTicker"):
        get(endpoint, shared)
    _, selected = selection(receipts)
    plan = [params for item in selected for params in candle_plan(item.symbol, anchor)]
    for params in plan[:-1]:
        get("klines", params)
    sample("before-availability")
    get("klines", plan[-1])
    available = time.monotonic_ns()
    sample("after-availability")
    time.sleep(.25)
    sample("before-decision")
    decision_at, decision = now(), time.monotonic_ns()
    sample("after-decision")
    raw = canonical(dict(anchor_ms=anchor, receipts=receipts, samples=samples, decision_at=decision_at,
                         markers=dict(availability=available,decision=decision)))
    (root / "capture.json").write_bytes(raw)
    if time.monotonic()-started >= 180:
        raise ValueError("RUN_TIME_BUDGET")
    return raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--archive", type=Path)
    mode.add_argument("--replay-sha256")
    args = parser.parse_args()
    if args.output.resolve().drive.upper() != "D:":
        raise SystemExit("D_DRIVE_REQUIRED")
    if args.archive:
        args.output.mkdir(exist_ok=False)
        raw = collect(args.output, args.archive)
    else:
        raw = (args.output / "capture.json").read_bytes()
        if digest(raw) != args.replay_sha256:
            raise SystemExit("CAPTURE_PIN_MISMATCH")
    result = evaluate(raw)
    (args.output / "result.json").write_bytes(canonical(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","witness")}))
    for row in result["rows"]:
        print(row["identity"]["symbol"], row["evaluation_status"], row["reconciliation"], row["raw_features_sha256"])
