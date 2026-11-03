from pathlib import Path
import tempfile
import unittest
from zs_smart_gate.evidence_journal import (study_capacity,MAX_STUDY_BYTES,
    MIGRATION_015_CAP_BYTES,MIGRATION_015_RAW_STUDY)
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend
from zs_smart_gate.custody_aggregate import aggregate_bytes,ALLOWED_STUDIES
from test_github_evidence_backend import MockContentsTransport

class OwnerCapacity015Tests(unittest.TestCase):
    def test_only_exact_owner_approved_namespace_is_extended(self):
        self.assertEqual(study_capacity(MIGRATION_015_RAW_STUDY),48*1024*1024)
        for name in ['other-study','custody-010-014-015','custody-010-014-015-raw-other']:
            self.assertEqual(study_capacity(name),10*1024*1024)
            with self.assertRaises(ValueError):
                GitHubEvidenceBackend(name,branch='evidence-test',max_study_bytes=MIGRATION_015_CAP_BYTES)

    def test_approved_raw_reservation_still_stops_at_48mib(self):
        b=GitHubEvidenceBackend(MIGRATION_015_RAW_STUDY,branch='evidence-test',enabled=True,
            transport=MockContentsTransport(),max_study_bytes=MIGRATION_015_CAP_BYTES)
        self.assertTrue(b.reserve_capacity(MIGRATION_015_RAW_STUDY,'payload',MAX_STUDY_BYTES+1,MIGRATION_015_CAP_BYTES))
        self.assertFalse(b.reserve_capacity(MIGRATION_015_RAW_STUDY,'over',MIGRATION_015_CAP_BYTES,MIGRATION_015_CAP_BYTES))

    def test_consolidated_cap_cannot_be_evaded_by_packet_splitting(self):
        with tempfile.TemporaryDirectory()as temp:
            for study in ALLOWED_STUDIES:
                p=Path(temp)/'studies'/study;p.mkdir(parents=True)
                with (p/'fixture').open('wb')as f:f.truncate(17*1024*1024)
            with self.assertRaisesRegex(ValueError,'CONSOLIDATED_48MIB_LIMIT'):
                aggregate_bytes(temp,list(ALLOWED_STUDIES))

    def test_unknown_or_missing_packet_is_not_accepted(self):
        with tempfile.TemporaryDirectory()as temp:
            with self.assertRaises(ValueError):aggregate_bytes(temp,['different'])
            with self.assertRaises(ValueError):aggregate_bytes(temp,list(ALLOWED_STUDIES))
