"""Stage04 bounded custody interface / quota / crash / replay tests (Windows)."""
from copy import deepcopy
import unittest

from test_stage03_research_handoff import synthetic_handoff
from zs_smart_gate.stage04_custody_boundary import (
    MemoryFixtureStore, build_fixture_bundle, persist_fixture_once,
    restore_fixture, validate_bundle,
)
from zs_smart_gate.stage05_contracts import ContractError


class Stage04CustodyBoundaryTests(unittest.TestCase):
    def bundle(self):
        return build_fixture_bundle((synthetic_handoff(),))

    def test_research_only_manifest_source_and_authority_not_assumed(self):
        b = self.bundle()
        self.assertTrue(validate_bundle(b))
        self.assertEqual(b["manifest"]["canonical_backend"], "OWNER_DECISION_PENDING")
        self.assertEqual(b["manifest"]["restore_status"], "NOT_PROVEN")
        self.assertFalse(b["manifest"]["eligible_for_real_dispatch"])
        self.assertEqual(len(b["manifest"]["inventory"]), 1)

    def test_fixture_readback_replay_stable_without_duplicate(self):
        b=self.bundle()
        store=MemoryFixtureStore()
        first=persist_fixture_once(store,b)
        self.assertEqual(first.status,"VERIFIED_FIXTURE_ONLY_NOT_PERMANENT")
        count=len(store.data)
        second=persist_fixture_once(store,b)
        self.assertEqual(second,first)
        self.assertEqual(len(store.data),count)
        self.assertEqual(restore_fixture(store,b),first)
        self.assertFalse(first.canonical_backend_approved)

    def test_crash_partial_status_and_manual_verified_replay(self):
        b=self.bundle()
        store=MemoryFixtureStore(fail_after=1)
        first=persist_fixture_once(store,b)
        self.assertEqual(first.status,"UNKNOWN_PARTIAL_OR_CONFLICT")
        self.assertEqual(first.records_verified,1)
        self.assertEqual(restore_fixture(store,b).status,"INCOMPLETE_FIXTURE")
        # New explicit invocation after inspecting partial bytes; not automatic retry.
        store.fail_after=None
        self.assertEqual(persist_fixture_once(store,b).status,
                         "VERIFIED_FIXTURE_ONLY_NOT_PERMANENT")
        self.assertEqual(restore_fixture(store,b).status,
                         "VERIFIED_FIXTURE_ONLY_NOT_PERMANENT")

    def test_corrupt_recovery_does_not_claim_restored(self):
        b=self.bundle()
        store=MemoryFixtureStore()
        persist_fixture_once(store,b)
        record=next(k for k in store.data if "/records/" in k)
        store.data[record]=store.data[record]+b"x"
        self.assertEqual(restore_fixture(store,b).status,"FAIL_FIXTURE_BYTE_CONFLICT")
        self.assertEqual(persist_fixture_once(store,b).status,"UNKNOWN_PARTIAL_OR_CONFLICT")

    def test_bad_manifest_and_quota_are_denied(self):
        b=self.bundle()
        b["manifest"]["canonical_backend"]="GITHUB_VERIFIED_PRODUCTION"
        with self.assertRaises(ContractError):
            validate_bundle(b)
        with self.assertRaises(ContractError):
            build_fixture_bundle(tuple(synthetic_handoff() for _ in range(9)))

    def test_duplicate_event_and_forged_signal_denied(self):
        with self.assertRaisesRegex(ContractError,"DUPLICATE"):
            build_fixture_bundle((synthetic_handoff(), synthetic_handoff()))
        bad=deepcopy(synthetic_handoff())
        bad["signal_id"]="FORGED"
        with self.assertRaises(ContractError):
            build_fixture_bundle((bad,))

    def test_non_fixture_store_cannot_become_backend(self):
        with self.assertRaisesRegex(ContractError,"ONLY_IN_MEMORY"):
            persist_fixture_once(object(),self.bundle())
