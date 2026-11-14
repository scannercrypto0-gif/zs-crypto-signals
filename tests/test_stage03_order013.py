from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import struct
import unittest
from zs_smart_gate.stage03_source_clock import stamp, parse_ntp, validate_public_payload
from zs_smart_gate.stage03_bounded_inference import paired_gain, bounded_interval, weekly_diagnostic
from zs_smart_gate.stage03_review_capsule import verify_capsule


class ClockTests(unittest.TestCase):
    def fixture(self):
        t = 1790000000.
        raw = bytearray(48)
        raw[0], raw[1] = 36, 1
        raw[24:32], raw[32:40], raw[40:48] = stamp(t), stamp(t+.01), stamp(t+.011)
        return t, raw

    def test_conditional_not_absolute(self):
        t, r = self.fixture()
        result = parse_ntp(bytes(r), stamp(t), t, t+.03, .03)
        self.assertTrue(result['conditional_below_one_second'])
        self.assertFalse(result['absolute_UTC_certified'])

    def test_origin_mode_unsynchronized_and_short_packet(self):
        t, r = self.fixture()
        for packet in [bytes(r[:47]), bytes([r[0] | 192])+bytes(r[1:]), bytes([35])+bytes(r[1:])]:
            with self.assertRaises(ValueError):
                parse_ntp(packet, stamp(t), t, t+.03, .03)
        with self.assertRaisesRegex(ValueError, 'ORIGIN'):
            parse_ntp(bytes(r), stamp(t+1), t, t+.03, .03)

    def test_clock_step_and_server_processing_reject(self):
        t, r = self.fixture()
        with self.assertRaisesRegex(ValueError, 'CLOCK_STEP'):
            parse_ntp(bytes(r), stamp(t), t, t+.5, .03)
        r[40:48] = stamp(t+1)
        with self.assertRaisesRegex(ValueError, 'INCONSISTENT'):
            parse_ntp(bytes(r), stamp(t), t, t+.03, .03)

    def test_large_dispersion_does_not_pass_bound(self):
        t, r = self.fixture()
        r[8:12] = struct.pack('!I', 2*65536)
        self.assertFalse(parse_ntp(bytes(r), stamp(t), t, t+.03, .03)['conditional_below_one_second'])

    def test_large_offset_is_not_hidden_by_small_radius(self):
        t, r = self.fixture()
        r[32:40], r[40:48] = stamp(t+5.01), stamp(t+5.011)
        result = parse_ntp(bytes(r), stamp(t), t, t+.03, .03)
        self.assertLess(result['conditional_radius_seconds'], 1)
        self.assertFalse(result['conditional_below_one_second'])

    def test_market_schema_is_not_publication(self):
        r = validate_public_payload('bookTicker', {'symbol':'BTCUSDT','bidPrice':'99','askPrice':'101'}, 'BTCUSDT')
        self.assertFalse(r['independent_publication'])
        with self.assertRaises(ValueError):
            validate_public_payload('bookTicker', {'symbol':'ETHUSDT','bidPrice':'102','askPrice':'101'}, 'BTCUSDT')


class BoundedTests(unittest.TestCase):
    def rows(self):
        return [dict(asset=asset, horizon='SWING', direction=1, close=week*604800+slot,
                     week=week, slot=slot, outcome=.01)
                for week in range(3) for asset in ['BTC', 'ETH'] for slot in range(0, 604800, 14400)]

    def test_known_answer_and_extreme_domain(self):
        self.assertEqual(paired_gain(0, 1, .01, .01), 1)
        self.assertEqual(paired_gain(1, 0, .01, .01), -1)
        self.assertIsNone(paired_gain(None, 1, .01, .01))
        with self.assertRaises(ValueError):
            paired_gain(2, 1, .01, .01)

    def test_no_independence_claim_and_family_widening(self):
        r = bounded_interval([.1]*8)
        self.assertFalse(r['scientific_pass'])
        self.assertIn('BLOCKED', r['status'])
        self.assertGreater(r['radius'], bounded_interval([.1]*8, family=1)['radius'])

    def test_assets_do_not_multiply_week_sample_units(self):
        rows = self.rows()
        result = weekly_diagnostic(rows, [.4]*len(rows), [.6]*len(rows), .05)
        self.assertEqual(result['N_calendar_weeks'], 3)
        self.assertEqual(result['interval']['N_calendar_week_blocks'], 3)

    def test_i2_different_missing_slots_do_not_force_equal_signature(self):
        rows = self.rows()
        a, b = [.4]*len(rows), [.6]*len(rows)
        for i in [0, 85, 170]:
            b[i] = None
        result = weekly_diagnostic(rows, a, b, .05)
        self.assertEqual(result['N_calendar_weeks'], 3)

    def test_missingness_not_filled_and_partial_weeks_rejected(self):
        rows = self.rows()
        b = [.6]*len(rows)
        for i in range(20):
            b[i] = None
        self.assertEqual(weekly_diagnostic(rows, [.4]*len(rows), b, .05)['N_calendar_weeks'], 2)
        with self.assertRaises(ValueError):
            weekly_diagnostic(rows+rows[:1], [.4]*(len(rows)+1), [.6]*(len(rows)+1), .05)

    def test_direction_pool_rejected(self):
        rows = self.rows()
        rows[0]['direction'] = -1
        with self.assertRaises(ValueError):
            weekly_diagnostic(rows, [.4]*len(rows), [.6]*len(rows), .05)


class CapsuleTests(unittest.TestCase):
    def test_anchor_bytes_and_escape(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'raw').write_bytes(b'fixture')
            manifest = root/'manifest.json'
            body = {'files':[dict(path='raw',bytes=7,sha256=hashlib.sha256(b'fixture').hexdigest())]}
            manifest.write_text(json.dumps(body))
            anchor = hashlib.sha256(manifest.read_bytes()).hexdigest()
            self.assertEqual(verify_capsule(root, manifest, anchor)['checked'], 1)
            (root/'raw').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'BYTES_CHANGED'):
                verify_capsule(root, manifest, anchor)
            with self.assertRaisesRegex(ValueError, 'ANCHOR'):
                verify_capsule(root, manifest, '0'*64)
            body['files'][0]['path'] = '../outside'
            manifest.write_text(json.dumps(body))
            anchor = hashlib.sha256(manifest.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'PATH_REJECTED'):
                verify_capsule(root, manifest, anchor)


if __name__ == '__main__':
    unittest.main()
