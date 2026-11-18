import hmac
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from test_stage13_operational_harness import MARKET, NOW, MockServices
from zs_smart_gate.ops_signals_readiness import VERSION, FixtureAuthority, SignalsReadinessController
from zs_smart_gate.stage05_contracts import canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox

# Public deterministic fixture material. Never a production signer.
KEY = b"stage13-review-fixture"


def signed(proof):
    return hmac.digest(KEY, canonical(proof), "sha256").hex()


def packet(**updates):
    scope = "SYNTHETIC_TEST_ONLY"
    source = dict(MARKET, context_complete=True, liquidity_verified=True, setup_trigger=True,
                  closed_at="2026-11-16T13:59:59Z", received_at="2026-11-16T14:00:00Z",
                  available_at="2026-11-16T14:00:00Z")
    source.update(updates)
    policy = dict(schema=VERSION, authority=scope, revoked=False, source_allowlist=[MARKET["source_id"]],
                  symbols=["BTCUSDT"], directions=["UP"], rule=MARKET["rule"],
                  max_age_us=5000000, max_uncertainty_us=500000)
    calibration = dict(scope=scope, signer="FIXTURE-SIGNER", revoked=False, monotonic_domain="fixture-domain",
                       measured_at="2026-11-16T13:59:59Z", received_at="2026-11-16T13:59:59Z",
                       available_at="2026-11-16T13:59:59Z", expires_at="2026-11-16T14:00:10Z",
                       uncertainty_us=100000, drift_ppm=1, offset_us=0)
    policy_pin = digest(canonical(policy))
    cal_pin = digest(canonical(calibration))
    value = dict(scope=scope, snapshot=source, policy=policy, calibration=calibration,
                 source_sha256=digest(canonical(source)))
    proof = dict(schema=VERSION, method="AUTHENTICATED_EVENT_BRACKET_V1", signer="FIXTURE-SIGNER",
                 source_sha256=value["source_sha256"], policy_sha256=policy_pin,
                 calibration_ref=cal_pin, monotonic_domain="fixture-domain")
    for label, at, mono in (("availability", source["available_at"], 1), ("decision", NOW, 5)):
        proof[label] = dict(monotonic_domain="fixture-domain", host_at=at, utc_lower=at, utc_upper=at,
                            before_mono_ns=mono, event_mono_ns=mono+1, after_mono_ns=mono+2)
    value["witness"] = dict(proof=proof, signature=signed(proof))
    return value, FixtureAuthority(policy_pin, cal_pin, "FIXTURE-SIGNER",
                                   lambda message, sig: hmac.compare_digest(
                                       hmac.digest(KEY, message, "sha256").hex(), sig))


class ReadinessTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/"journal.db"
        self.services = MockServices()

    def controller(self, data, authority):
        self.services.row = data
        return SignalsReadinessController(journal=LocalOutbox(self.path),
                                          ports=self.services.ports(), authority=authority, quota=6)

    def test_qualified_fixture_recovery_and_replay_bind_same_id(self):
        value, authority = packet()
        self.services.failure = "telegram_b"
        stopped = self.controller(value, authority).scan_once()
        self.assertEqual(stopped["stage"], "telegram_b")
        self.services.failure = "scanner"
        restarted = self.controller(value, authority)
        done = restarted.recover_page()
        report, = done["reports"]
        self.assertEqual(report["status"], "MOCK_PASS")
        self.assertEqual(report["signal_id"], stopped["signal_id"])
        self.assertEqual(len(self.services.deliveries), 6)
        self.assertTrue(all(r["sha256"] == report["sha256"] for r in report["receipts"].values()))
        self.assertFalse(report["trading_authorized"])
        self.assertEqual(report["readiness"], "NOT_READY")

    def test_nontrigger_missing_context_and_real_policy_hold(self):
        for data, status in ((dict(setup_trigger=False), "NO_QUALIFIED_FIXTURE"),
                             (dict(context_complete=False), "INVALID_OBSERVATION"),
                             (dict(closed_at="2026-11-16T13:55:00Z"), "INVALID_OBSERVATION")):
            value, authority = packet(**data)
            self.assertEqual(self.controller(value,authority).scan_once()["status"], status)
        value, authority = packet()
        value["scope"] = "APPROVED_REAL_SOURCE"
        self.assertIn("REAL_POLICY_NOT_ADMITTED", self.controller(value,authority).scan_once()["reason"])
        self.assertEqual(self.services.calls, [])

    def test_bad_witness_stops_before_local_or_remote_delivery(self):
        for change in ("absent", "forged", "reordered", "skewed", "contradictory", "stale", "future"):
            with self.subTest(change=change):
                value, authority = packet()
                proof = value["witness"]["proof"]
                if change == "absent":
                    value.pop("witness")
                elif change == "forged":
                    value["witness"]["signature"] = "0"*64
                elif change in ("stale","future"):
                    at = "2026-11-16T13:59:00Z" if change == "stale" else "2026-11-16T14:00:08Z"
                    value["calibration"].update(measured_at=at, received_at=at, available_at=at)
                    pin = digest(canonical(value["calibration"]))
                    from dataclasses import replace
                    authority = replace(authority, calibration_pin=pin)
                    proof["calibration_ref"] = pin
                    value["witness"]["signature"] = signed(proof)
                else:
                    if change == "reordered":
                        proof["availability"]["event_mono_ns"] = 7
                    elif change == "skewed":
                        proof["decision"]["utc_upper"] = "2026-11-16T14:00:03Z"
                    else:
                        proof["decision"]["utc_lower"] = "2026-11-16T14:00:02.010000Z"
                    value["witness"]["signature"] = signed(proof)
                report = self.controller(value,authority).scan_once()
                self.assertEqual(report["reason"], "QUALIFICATION_BLOCKED:UTC_WITNESS_UNKNOWN")
        self.assertEqual(self.services.calls, [])
        self.assertEqual(LocalOutbox(self.path).list_keys("signal"), ())

    def test_changed_snapshot_or_revoked_calibration_blocks_replay(self):
        value, authority = packet()
        value["snapshot"]["liquidity_verified"] = False
        self.assertIn("SOURCE_OR_POLICY_PIN_INVALID", self.controller(value,authority).scan_once()["reason"])
        value, authority = packet()
        self.services.failure = "github"
        saved = self.controller(value,authority).scan_once()
        from dataclasses import replace
        revoked_authority = replace(authority, calibration_pin="0"*64)
        self.services.failure = None
        self.services.calls.clear()
        self.assertEqual(self.controller(value,revoked_authority).resume(saved["signal_id"])["status"],
                         "INVALID_STORED_SIGNAL")
        self.assertEqual(self.services.calls, [])
