"""Independent synthetic contracts, not market/scientific acceptance tests."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from zs_smart_gate.stage03_research_evidence import (
    Approval, TimingEvidence, assess_pit, EvidenceJournal, journal_records,
    AttemptClaims, DepthSequence, ForwardConfig, offline_forward, forward_scope_digest)
from zs_smart_gate.stage03_directional_study import (
    fit_reference, normalize, correlation, conditional_compare,
    independent_sample_plan, reject_lineage_overlap)


def timing():
    return TimingEvidence(1000, 1001, 1002, 1050, 1060, 1045, .2,
                          'SYNTHETIC_SOURCE', 'a'*64, 'b'*64, 'c'*64, 'd'*64,
                          asset='BTCUSDT', frame='30m', clock_drift_ppm=20)


def approvals():
    return tuple(Approval(k, h*64, 'SYNTHETIC_INDEPENDENT_AUTHORITY',
                          'FIXTURE_ONLY_NOT_REAL_REVIEW', True)
                 for k, h in [('PUBLICATION', 'b'), ('AVAILABILITY', 'c'), ('CLOCK', 'd')])


class PitTests(unittest.TestCase):
    def test_missing_publication_is_not_inferred_from_close(self):
        self.assertEqual(assess_pit(replace(timing(), publication_at=None), approvals()),
                         'PUBLICATION_OR_AVAILABILITY_MISSING')

    def test_independent_review_is_required(self):
        self.assertEqual(assess_pit(timing()), 'PUBLICATION_INDEPENDENT_REVIEW_MISSING')

    def test_exchange_clock_does_not_self_certify(self):
        a = tuple(replace(x, authority='BINANCE') for x in approvals())
        self.assertEqual(assess_pit(timing(), a), 'PUBLICATION_INDEPENDENT_REVIEW_MISSING')

    def test_proof_digest_must_match(self):
        self.assertEqual(assess_pit(replace(timing(), clock_sha256='e'*64), approvals()),
                         'CLOCK_INDEPENDENT_REVIEW_MISSING')

    def test_future_receipt_and_clock_regressions(self):
        self.assertEqual(assess_pit(replace(timing(), received_at=1061), approvals()), 'NONCAUSAL_TIMELINE')
        self.assertEqual(assess_pit(replace(timing(), clock_measured_at=1051), approvals()), 'CLOCK_SAMPLE_STALE_OR_FUTURE')

    def test_subsecond_is_strict_and_clock_age_bounded(self):
        for u in [1, -1, float('nan'), float('inf'), True]:
            self.assertNotEqual(assess_pit(replace(timing(), uncertainty_seconds=u), approvals()),
                                'PIT_CONTRACT_CHECKED_EXTERNAL_REVIEW_REQUIRED')
        self.assertEqual(assess_pit(replace(timing(), clock_measured_at=1029), approvals()), 'CLOCK_SAMPLE_STALE_OR_FUTURE')

    def test_explicit_external_review_contract_only(self):
        self.assertEqual(assess_pit(timing(), approvals()), 'PIT_CONTRACT_CHECKED_EXTERNAL_REVIEW_REQUIRED')

    def test_clock_drift_must_be_bounded_through_decision(self):
        self.assertEqual(assess_pit(replace(timing(), clock_drift_ppm=None), approvals()), 'CLOCK_DRIFT_BOUND_MISSING')
        self.assertEqual(assess_pit(replace(timing(), clock_drift_ppm=100000), approvals()), 'CLOCK_PROJECTED_UNCERTAINTY_REJECTED')


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_roundtrip_and_exclusive_creation(self):
        path = self.root/'journal'
        with EvidenceJournal(path, 'fixture') as j:
            j.append('RAW', {'x': 1})
        self.assertEqual([r['kind'] for r in journal_records(path)], ['HEADER', 'RAW', 'FOOTER'])
        with self.assertRaises(FileExistsError):
            EvidenceJournal(path, 'other')

    def test_tamper_duplicate_truncation(self):
        path = self.root/'journal'
        with EvidenceJournal(path, 'fixture') as j:
            j.append('RAW', {'x': 1})
        raw = path.read_bytes()
        for bad in [raw.replace(b'"x":1', b'"x":2'), raw+raw.splitlines(keepends=True)[1], raw[:-1]]:
            target = self.root/'bad'
            target.write_bytes(bad)
            with self.assertRaises(ValueError):
                journal_records(target)

    def test_crash_remains_unclosed_and_auditable(self):
        path = self.root/'journal'
        with self.assertRaises(RuntimeError):
            with EvidenceJournal(path, 'fixture') as j:
                j.append('CLAIM', {'event': 'x'})
                raise RuntimeError('injected crash')
        with self.assertRaisesRegex(ValueError, 'UNCLOSED'):
            journal_records(path)
        self.assertEqual(len(journal_records(path, require_closed=False)), 2)

    def test_resource_bound_and_nonfinite_payload(self):
        with EvidenceJournal(self.root/'journal', 'fixture', max_bytes=1024) as j:
            with self.assertRaises(ValueError):
                j.append('RAW', {'n': float('nan')})
            with self.assertRaisesRegex(ValueError, 'SIZE_LIMIT'):
                j.append('RAW', {'x': 'a'*2000})

    def test_claim_survives_new_process_object_without_retry(self):
        self.assertTrue(AttemptClaims(self.root).claim('a'*64, 'event'))
        self.assertFalse(AttemptClaims(self.root).claim('a'*64, 'event'))
        self.assertTrue(AttemptClaims(self.root).claim('a'*64, 'different'))


class DepthTests(unittest.TestCase):
    def book(self):
        d = DepthSequence('BTCUSDT')
        d.seed(10, [(99, 2)], [(101, 3)], 100)
        return d

    def test_seed_needs_bridging_update(self):
        d = self.book()
        self.assertEqual(d.state, 'SNAPSHOT_ONLY')
        self.assertEqual(d.apply('BTCUSDT', 10, 11, [(99, 4)], [], 100, 101, 102), 'SYNCED')
        self.assertEqual(d.bids[99], 4)  # absolute quantity, not additive delta

    def test_duplicate_does_not_advance(self):
        d = self.book()
        self.assertEqual(d.apply('BTCUSDT', 9, 10, [(99, 5)], [], 100, 100, 100), 'DUPLICATE_IGNORED')
        self.assertEqual(d.bids[99], 2)

    def test_gap_blocks_until_new_epoch(self):
        d = self.book()
        with self.assertRaisesRegex(ValueError, 'SEQUENCE_GAP'):
            d.apply('BTCUSDT', 12, 12, [], [], 100, 101, 102)
        self.assertEqual(d.apply('BTCUSDT', 11, 11, [], [], 100, 101, 102), 'NEEDS_SNAPSHOT')
        d.seed(20, [(99, 1)], [(101, 1)], 103)
        self.assertEqual(d.epoch, 2)

    def test_bad_timing_symbol_cross_and_level_are_rejected(self):
        for symbol, bids, source, receipt, decision in [
            ('ETHUSDT', [], 100, 101, 102), ('BTCUSDT', [(102, 1)], 100, 101, 102),
            ('BTCUSDT', [], 102, 101, 102), ('BTCUSDT', [], 100, 101, 104),
            ('BTCUSDT', [(99, float('nan'))], 100, 101, 102)]:
            d = self.book()
            with self.assertRaises(ValueError):
                d.apply(symbol, 11, 11, bids, [], source, receipt, decision)
            self.assertIsNone(d.last)

    def test_failed_resync_does_not_retain_valid_book(self):
        d = self.book()
        d.apply('BTCUSDT', 11, 11, [], [], 100, 101, 102)
        with self.assertRaises(ValueError):
            d.seed(20, [(102, 1)], [(101, 1)], 103)
        self.assertIsNone(d.last)
        self.assertEqual(d.state, 'NEEDS_SNAPSHOT')


class ForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def config(self):
        c = ForwardConfig(True, '', 'b'*40, 'FIXTURE_OWNER_SCOPE', 'FIXTURE_RIGHTS', 2,
                          (('BTCUSDT', '30m', 1000), ('ETHUSDT', '30m', 1000)))
        return replace(c, manifest_sha256=forward_scope_digest(c))

    def run_fixture(self, config, e, packets):
        path = self.root/('j'+str(len(list(self.root.glob('j*')))))
        with EvidenceJournal(path, 'synthetic') as j:
            return offline_forward(config, e, approvals(), packets, AttemptClaims(self.root/'claims'), j)

    def test_default_never_consumes_input_or_claims(self):
        def forbidden():
            raise AssertionError('NOT_ARMED_CONSUMED_INPUT')
            yield
        r = self.run_fixture(ForwardConfig(), timing(), forbidden())
        self.assertEqual((r['status'], r['HTTP_requests']), ('NOT_ARMED', 0))
        self.assertEqual(list((self.root/'claims').glob('*.claim')), [])

    def test_missing_proof_is_zero_attempts(self):
        r = self.run_fixture(self.config(), replace(timing(), publication_at=None), [])
        self.assertEqual(r['packets'], 0)
        self.assertEqual(r['HTTP_requests'], 0)

    def test_future_scope_or_late_event_is_blocked(self):
        self.assertEqual(self.run_fixture(replace(self.config(), accepted_code_sha=''), timing(), [])['status'], 'FROZEN_SCOPE_MISSING')
        e = replace(timing(), event_close=0, publication_at=1, source_available_at=2)
        self.assertEqual(self.run_fixture(self.config(), e, [])['status'], 'LATE_OR_EARLY_ZERO_HTTP')

    def test_bounded_smoke_no_live_requests_duplicate_denied(self):
        r = self.run_fixture(self.config(), timing(), ({'i': i} for i in range(100)))
        self.assertEqual((r['packets'], r['HTTP_requests']), (2, 0))
        self.assertEqual(r['status'], 'OFFLINE_SMOKE_ONLY_NOT_FORWARD_EVIDENCE')
        self.assertEqual(self.run_fixture(self.config(), timing(), [])['status'], 'DUPLICATE_OR_UNCERTAIN_ZERO_HTTP')

    def test_manifest_integrity_and_asset_identity(self):
        self.assertEqual(self.run_fixture(replace(self.config(), max_packets=3), timing(), [])['status'], 'FROZEN_SCOPE_MISSING')
        self.run_fixture(self.config(), timing(), [])
        self.assertEqual(self.run_fixture(self.config(), replace(timing(), asset='ETHUSDT'), [])['status'], 'OFFLINE_SMOKE_ONLY_NOT_FORWARD_EVIDENCE')
        self.assertEqual(self.run_fixture(self.config(), replace(timing(), asset='XRPUSDT'), [])['status'], 'OUTSIDE_FROZEN_EVENT_SCOPE')


class ScienceTests(unittest.TestCase):
    def rows(self, direction=1):
        return [dict(asset='BTC', direction=direction, horizon='INTRADAY', close=w*100+s,
                     week=w, slot=s, outcome=(s-1)*(w+1)/100) for w in range(5) for s in range(3)]

    def test_pooled_cancellation_is_refused(self):
        rows = self.rows()+self.rows(-1)
        x = [r['close'] % 3 for r in rows]
        y = [r['direction']*r['outcome'] for r in rows]
        with self.assertRaisesRegex(ValueError, 'MIXED_DIRECTION'):
            conditional_compare(rows, x, y)

    def test_directional_and_horizon_cohorts_remain_separate(self):
        rows = self.rows()
        r = conditional_compare(rows, [x['close'] for x in rows], [x['slot'] for x in rows], repeats=16)
        self.assertIsNone(r['qualification_p'])
        self.assertEqual(r['N_asset_week_blocks'], 5)
        rows[0]['horizon'] = 'SWING'
        with self.assertRaisesRegex(ValueError, 'MIXED_HORIZON'):
            conditional_compare(rows, [1]*15, [2]*15)

    def test_no_refit_or_relabelled_old_oos(self):
        with self.assertRaisesRegex(ValueError, 'HOLDOUT_FIT'):
            fit_reference([1, 2, 3], 'OOS', 10, 11)
        with self.assertRaisesRegex(ValueError, 'NEW_OOS'):
            conditional_compare(self.rows(), [1]*15, [2]*15, phase='OOS')

    def test_normalization_ties_tails_missing_and_zero_mad(self):
        ref = fit_reference([1, 2, 2, 3], 'DEV', 10, 11)
        self.assertEqual(normalize(2, 'Q', ref, 11), .5)
        self.assertEqual(normalize(-100, 'Q', ref, 11), 0)
        self.assertEqual(normalize(100, 'Q', ref, 11), 1)
        self.assertIsNone(normalize(None, 'Q', ref, 11))
        flat = fit_reference([1, 1, 1], 'DEV', 10, 11)
        self.assertIsNone(normalize(1, 'R', flat, 11))
        self.assertIsNone(normalize(2, 'D', ref, 11))

    def test_late_reference_and_duplicate_event_rejected(self):
        ref = fit_reference([1, 2, 3], 'DEV', 10, 11)
        with self.assertRaisesRegex(ValueError, 'NOT_KNOWN'):
            normalize(1, 'Q', ref, 10)
        rows = self.rows()+self.rows()[:1]
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_EVENT'):
            conditional_compare(rows, [1]*16, [2]*16)

    def test_lineage_does_not_multiply_observations(self):
        with self.assertRaisesRegex(ValueError, 'LINEAGE'):
            reject_lineage_overlap([['BTC:5m:100:price'], ['BTC:5m:100:price']])
        reject_lineage_overlap([['BTC:5m:100:price'], ['BTC:5m:100:volume']])

    def test_planning_not_actual_effective_samples(self):
        self.assertGreater(independent_sample_plan(family=20), independent_sample_plan(family=1))
        self.assertIsNone(correlation([1]*3, [1, 2, 3]))

    def test_reference_tamper_is_rejected(self):
        ref = fit_reference([1, 2, 3], 'DEV', 10, 11)
        ref['values'][0] = -100
        with self.assertRaisesRegex(ValueError, 'REFERENCE_CHANGED'):
            normalize(1, 'Q', ref, 12)


if __name__ == '__main__':
    unittest.main()
