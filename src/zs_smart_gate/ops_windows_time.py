"""Read-only Windows Time observation and stamped public Spot receipts."""
import math
import os
import re
import subprocess
import time
from datetime import datetime, timezone

from .ops_spot_preflight import public_get, run_preflight
from .stage05_contracts import ContractError, canonical, digest, utc_now

SOURCE = "time.cloudflare.com"
CANDIDATE = {"max_offset_s": .5, "max_conditional_uncertainty_s": .5,
             "max_sync_age_s": 600, "max_step_s": .05, "quorum": 4}
POLICY_ID = "WINDOWS_TIME_OPERATIONAL_V1"
# Set only through reviewed repository policy adoption.
REVIEWED_POLICY_SHA256 = "8a256ebdf21a808f630c3218d2f981ca22a8eb7154831f001e58c4b1defdf683"  # owner-approved P0, source/limits only; measurements still required
COMMANDS = {
    "service": ("sc.exe", "query", "W32Time"),
    "status": ("w32tm.exe", "/query", "/status"),
    "source": ("w32tm.exe", "/query", "/source"),
    "configuration": ("w32tm.exe", "/query", "/configuration"),
    "stripchart": ("w32tm.exe", "/stripchart", "/computer:"+SOURCE, "/samples:4", "/period:1"),
}


def now():
    return utc_now(lambda: datetime.now(timezone.utc))


def command(argv):
    wall_start, start_ns, started = time.time(), time.monotonic_ns(), now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=10)
        exit_code, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        exit_code, stdout, stderr = None, "", "TIMEOUT"
    end_ns = time.monotonic_ns()
    return dict(exit=exit_code, stdout=stdout, stderr=stderr, started_utc=started, received_utc=now(),
                start_mono_ns=start_ns, end_mono_ns=end_ns,
                wall_step_disagreement_s=round(abs((time.time()-wall_start)-(end_ns-start_ns)/1e9),6))


def assess(receipts, *, sync_age_s=None, policy=None):
    approved = (
        REVIEWED_POLICY_SHA256 is not None
        and isinstance(policy, dict)
        and policy == {"policy_id": POLICY_ID, "source": SOURCE, "limits": CANDIDATE}
        and digest(canonical(policy)) == REVIEWED_POLICY_SHA256
    )
    blockers = []
    for name in COMMANDS:
        row = receipts[name]
        # Windows w32tm may emit an access/error diagnostic on stdout even
        # when the process exit code is zero. Never infer authority from exit
        # code alone; reject diagnostic failures on either output stream.
        output = str(row.get("stdout", "")) + "\n" + str(row.get("stderr", ""))
        failed_output = re.search(
            r"(?i)(0x80070005|access[ ]+(?:is[ ]+)?denied|"
            r"the following error occurred)", output
        )
        if row["exit"] != 0 or failed_output:
            blockers.append(name.upper()+"_COMMAND_FAILED")
        if not 0 <= row["wall_step_disagreement_s"] <= CANDIDATE["max_step_s"]:
            blockers.append(name.upper()+"_TIME_STEP")
    service = receipts["service"]["stdout"]
    if not re.search(r"STATE\s*:\s*4\b", service):
        blockers.append("SERVICE_NOT_RUNNING")
    status = receipts["status"]["stdout"]
    fields = dict(re.findall(r"(?m)^([^:\r\n]+):[ \t]*([^\r\n]*)", status))
    source = fields.get("Source","").strip()
    query_source = receipts["source"]["stdout"].strip()
    if (source.split(",")[0].lower() != SOURCE
            or (receipts["source"]["exit"] == 0 and query_source.split(",")[0].lower() != SOURCE)):
        blockers.append("SOURCE_NOT_ALLOWLISTED")
    if not re.match(r"^0\b", fields.get("Leap Indicator","")) or not re.match(r"^(?:[1-9]|1[0-5])\b", fields.get("Stratum","")):
        blockers.append("SYNC_STATUS_UNVERIFIED")
    if sync_age_s is None or not 0 <= sync_age_s <= CANDIDATE["max_sync_age_s"]:
        blockers.append("SYNC_FRESHNESS_UNVERIFIED_OR_STALE")
    samples = [{"display_time":stamp,"rtt_s":float(rtt),"offset_s":float(offset)}
               for stamp,rtt,offset in re.findall(
                   r"(?m)^(\d\d:\d\d:\d\d),\s*d:([+-]?\d+\.\d+)s\s+o:([+-]?\d+\.\d+)s",
                   receipts["stripchart"]["stdout"])]
    if len(samples) < CANDIDATE["quorum"] or len({s["display_time"] for s in samples}) != len(samples):
        blockers.append("OFFSET_QUORUM_OR_DUPLICATE")
    if any(not math.isfinite(s["offset_s"]) or abs(s["offset_s"]) > CANDIDATE["max_offset_s"] or not math.isfinite(s["rtt_s"]) or s["rtt_s"] < 0 for s in samples):
        blockers.append("OFFSET_LIMIT")
    if samples and max(s["offset_s"] for s in samples)-min(s["offset_s"] for s in samples) > CANDIDATE["max_step_s"]:
        blockers.append("OFFSET_DISCONTINUITY")
    dispersion = re.fullmatch(r"(\d+\.\d+)s",fields.get("Root Dispersion",""))
    root_delay = re.fullmatch(r"(\d+\.\d+)s",fields.get("Root Delay",""))
    conditional = (float(dispersion[1])+float(root_delay[1])/2+max(s["rtt_s"] for s in samples)/2
                   if dispersion and root_delay and samples else None)
    if conditional is None or conditional > CANDIDATE["max_conditional_uncertainty_s"]:
        blockers.append("CONDITIONAL_UNCERTAINTY_UNVERIFIED_OR_HIGH")
    if not approved:
        blockers.append("OPERATIONAL_TOLERANCES_NOT_APPROVED")
    return dict(status="BLOCKED" if blockers else "OPERATIONAL_TIME_ACCEPTED",
                independent_time="INDEPENDENT_CRYPTOGRAPHIC_TIME_NOT_PROVEN",
                policy_id=POLICY_ID, blockers=blockers, source=source,
                sync_age_s=sync_age_s, candidate_limits=CANDIDATE, samples=samples,
                conditional_uncertainty_s=conditional,
                last_successful_sync_display=fields.get("Last Successful Sync Time"),
                stratum=fields.get("Stratum"), root_delay=fields.get("Root Delay"),
                root_dispersion=fields.get("Root Dispersion"))


def capture(root, *, sync_age, invoke=command, get=public_get, policy=None):
    observations = {}
    for name, args in COMMANDS.items():
        observations[name] = invoke(args)
        (root/f"time-{name}.private.json").write_bytes(canonical(observations[name]))
    status = assess(observations, sync_age_s=sync_age(observations["status"]["stdout"]), policy=policy)
    status["command_receipts"] = {
        k:{**{a:b for a,b in v.items() if a not in ("stdout","stderr")},
           "stdout_sha256":digest(v["stdout"].encode()),"stderr_sha256":digest(v["stderr"].encode()),
           "command":list(COMMANDS[k])} for k,v in observations.items()}
    (root/"clock.json").write_bytes(canonical(status))
    counter = 0
    def obtain(path, params, timeout):
        nonlocal counter
        counter += 1
        t0,m0 = time.time(),time.monotonic_ns()
        received = get(path,params,timeout)
        m1,t1 = time.monotonic_ns(),time.time()
        row = {"attempt":counter, "start_mono_ns":m0,"receive_mono_ns":m1,"receive_utc":now(),
               "wall_step_disagreement_s":abs((t1-t0)-(m1-m0)/1e9)}
        (root/f"spot-{counter}.timing.json").write_bytes(canonical(row))
        if isinstance(received[2],bytes) and len(received[2]) <= 262144:
            (root/f"spot-{counter}.private").write_bytes(received[2])
        if row["wall_step_disagreement_s"] > CANDIDATE["max_step_s"]:
            raise ContractError("OPS_HOST_TIME_STEP")
        return received

    def record(entry):
        with (root/"spot.jsonl").open("ab") as stream:
            stream.write(canonical(entry)+b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    market = run_preflight(get=obtain, monotonic=time.monotonic, utc_now=now, record=record)
    timing = [{"file": p.name, "sha256": digest(p.read_bytes())}
              for p in sorted(root.glob("spot-*.timing.json"))]
    result = {"clock":status["status"], "spot":market, "decision_utc":now(),
              "spot_receipts_sha256":digest((root/"spot.jsonl").read_bytes()),
              "clock_receipt_sha256":digest((root/"clock.json").read_bytes()), "timing_receipts":timing,
              "decision_mono_ns":time.monotonic_ns(), "readiness":"NOT_READY",
              "qualification":"QUALIFICATION_BLOCKED"}
    (root/"run.json").write_bytes(canonical(result))
    return result
