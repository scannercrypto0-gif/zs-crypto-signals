"""QV1-B decision and custody boundary with an empty real qualification registry."""
from .stage03_qv1 import FRAMES, evaluate
from .stage05_contracts import ContractError, canonical, digest, ensure_event, make_document
from .stage05_custody import LocalOutbox, VerifiedUpstream

BOUNDARY_VERSION = "QV1-B-BOUNDARY-1"
FIXTURE_POLICY = "SYNTHETIC_TEST_ONLY.QV1-B.1"
FIXTURE_GATES = ("SETUP", "CONTEXT", "LIQUIDITY", "CLOCK")


def _validated(record):
    try:
        checked = evaluate(record)
        source = record["source"]
        if (source.get("venue") != "BINANCE_SPOT"
                or not isinstance(source.get("feed"), str) or not source["feed"]
                or source.get("scope") != record["source_scope"]
                or source.get("path") != [record["horizon"], record["direction"]]
                or source.get("event_close_at") != record["event_close_at"]
                or source.get("decision_at") != record["decision_at"]):
            raise ContractError("QV1_DECISION_NOT_BOUND_TO_SOURCE")
        for frame in FRAMES[record["horizon"]]:
            bar = record["candles"].get(frame)
            if bar is not None and (bar.get("feed") != source["feed"]
                                    or bar.get("symbol") != record["symbol"]):
                raise ContractError("QV1_MIXED_CANDLE_SOURCE:" + frame)
        for name in ("liquidity", "clock"):
            receipt = source.get(name)
            if receipt is not None and receipt.get("bound_feed") != source["feed"]:
                raise ContractError("QV1_MIXED_WITNESS_SOURCE:" + name)
        if record.get("sem_mappings") or source.get("sem_mappings"):
            raise ContractError("QV1_SEM_MAPPING_NOT_APPROVED")
    except ContractError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ContractError("QV1_EVIDENCE_SCHEMA_INVALID") from exc
    return checked


def evaluate_boundary(record):
    """Admit evidence, not a caller's claim that the candidate qualified."""
    checked = _validated(record)
    path = (record["horizon"], record["direction"])
    path_hold = ("APPROVED_SETUP_QUALIFICATION_BRIDGE_MISSING" if path == ("INTRADAY", "UP")
                 else "APPROVED_DIRECTIONAL_SETUP_MISSING")
    return {**checked, "boundary_version": BOUNDARY_VERSION, "path_hold": path_hold,
            "qualification_state": "UNKNOWN", "score_status": "SCORE_UNAVAILABLE",
            "score_reason": "SCORE_V2_POLICY_NOT_APPROVED"}


def _fixture_decision(record, gates):
    result = evaluate_boundary(record)
    if record["source_scope"] != "SYNTHETIC_TEST_ONLY":
        raise ContractError("QV1_FIXTURE_POLICY_FORBIDS_REAL_SOURCE")
    if (set(gates) - set(FIXTURE_GATES)
            or any(value not in ("PASS", "FAIL", "UNKNOWN") for value in gates.values())
            or record["source"].get("fixture_gates_sha256") != digest(canonical(gates))):
        raise ContractError("QV1_FIXTURE_GATES_INVALID_OR_UNBOUND")
    states = {gate: gates.get(gate, "UNKNOWN") for gate in FIXTURE_GATES}
    if result["state"] == "UNKNOWN":
        outcome = "UNKNOWN"
    elif "FAIL" in states.values():
        outcome = "REJECTED"
    elif result["state"] != "DETECTED_SIGNAL" or "UNKNOWN" in states.values():
        outcome = "UNKNOWN"
    else:
        outcome = "QUALIFIED"
    return {**result, "qualification": "SYNTHETIC_TEST_ONLY", "qualification_state": outcome,
            "qualification_policy": FIXTURE_POLICY, "gate_states": states}


def seal_fixture(record, gates, store):
    """Exercise positive qualification/custody without a real promotion path."""
    if type(store) is not LocalOutbox:
        raise ContractError("QV1_LOCAL_CUSTODY_REQUIRED")
    result = _fixture_decision(record, gates)
    body = canonical({"scope": "SYNTHETIC_TEST_ONLY", "record": record,
                      "gates": gates, "decision": result})
    key = "qualification-fixture/" + result["event_id"]
    store.create_if_absent(key, body)
    if store.read(key) != body:
        raise ContractError("QV1_FIXTURE_READBACK_CONFLICT")
    proof = digest(body)
    signal = ("fixture-sig-" + digest(canonical([FIXTURE_POLICY, result["event_id"]]))
              if result["qualification_state"] == "QUALIFIED" else None)
    return {**result, "signal_id": signal, "qualification_evidence_sha256": proof}


def fixture_stage05(record, gates, store, template):
    """Build only a synthetic Stage05 envelope. Unknown remains audit-only."""
    decision = seal_fixture(record, gates, store)
    if (decision.get("qualification") != "SYNTHETIC_TEST_ONLY"
            or template.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or decision.get("qualification_policy") != FIXTURE_POLICY):
        raise ContractError("QV1_FIXTURE_ENVELOPE_SCOPE_REQUIRED")
    state = decision["qualification_state"]
    if state == "UNKNOWN":
        return {"scope": "SYNTHETIC_TEST_ONLY", "route": "05B_AUDIT_ONLY", "decision": decision}
    for field in ("symbol", "direction", "horizon"):
        if template.get(field) != record[field]:
            raise ContractError("QV1_FIXTURE_ENVELOPE_IDENTITY_MISMATCH")
    candle = record["candles"]["30m" if record["horizon"] == "INTRADAY" else "4h"]
    times = {"decision_candle_open_at": candle["open_at"], "decision_candle_close_at": candle["close_at"],
             "received_at": candle["received_at"], "available_at": candle["available_at"],
             "decision_at": record["decision_at"], "record_created_at": record["decision_at"]}
    qualified = state == "QUALIFIED"
    event = {**template, "event_type": "QUALIFIED_SIGNAL" if qualified else "REJECTED_CANDIDATE",
             "candidate_id": decision["candidate_id"], "detection_event_key": decision["event_id"],
             "qualification_status": state, "signal_id": decision["signal_id"],
             "qualification_authority": "EXPLICIT_APPROVED_UPSTREAM" if qualified else None,
             "qualification_evidence_sha256": decision["qualification_evidence_sha256"] if qualified else None,
             "score": None, "trade_plan": None, "timestamps": times, "indicators": [],
             "source_manifest_sha256": decision["source_sha256"],
             "quality_metadata": {"qualification_policy": FIXTURE_POLICY,
                                  "score_status": decision["score_status"], "score_reason": decision["score_reason"]},
             "gates": [{"gate_id": key, "state": value, "reason_codes": ["SYNTHETIC_TEST_ONLY"]}
                       for key, value in decision["gate_states"].items()],
             "reject_reason_codes": [] if qualified else ["SYNTHETIC_GATE_FAILURE"]}
    ensure_event(event)
    return event


def recorded_rejection_archive(upstream, identity, expected_sha):
    """Read and replay the actual authorized rejection before building its archive."""
    if type(upstream) is not VerifiedUpstream:
        raise ContractError("QV1_VERIFIED_UPSTREAM_REQUIRED")
    event = upstream.read(identity, expected_sha)
    if event["qualification_status"] != "REJECTED" or event["signal_id"] is not None:
        raise ContractError("QV1_REAL_QUALIFICATION_POLICY_UNAVAILABLE")
    return event, make_document(event)
