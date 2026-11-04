import copy
import hashlib
import math
import struct
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from zs_smart_gate.clock017 import encode, decode, framed, request, verify, local_interval


class Clock017Tests(unittest.TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.delegate = Ed25519PrivateKey.generate()
        self.key = self.root.public_key().public_bytes_raw()
        self.nonce = b'n'*32

    def packet(self, radius=1, midpoint=100, index=0):
        delegation = encode({b'PUBK': self.delegate.public_key().public_bytes_raw(),
                             b'MINT': struct.pack('<Q', 90), b'MAXT': struct.pack('<Q', 110)})
        cert = encode({b'DELE': delegation, b'SIG\0': self.root.sign(
            b'RoughTime v1 delegation signature--\0'+delegation)})
        signed = encode({b'MIDP': struct.pack('<Q', midpoint), b'RADI': struct.pack('<I', radius),
                         b'ROOT': hashlib.sha512(b'\0'+self.nonce).digest()[:32]})
        return framed(encode({b'CERT': cert, b'SREP': signed, b'NONC': self.nonce,
            b'VER\0': struct.pack('<I', 0x8000000b), b'INDX': struct.pack('<I', index),
            b'PATH': b'', b'SIG\0': self.delegate.sign(b'RoughTime v1 response signature\0'+signed)}))

    def test_signed_delegation_response_nonce_and_radius(self):
        result = verify(self.packet(), self.nonce, self.key)
        self.assertEqual(result['radius_seconds'], 1)
        self.assertFalse(result['absolute_utc_admitted'])

    def test_wrong_root_key(self):
        with self.assertRaises(InvalidSignature):
            verify(self.packet(), self.nonce, Ed25519PrivateKey.generate().public_key().public_bytes_raw())

    def test_nonce_replay(self):
        with self.assertRaisesRegex(ValueError, 'NONCE'):
            verify(self.packet(), b'z'*32, self.key)

    def test_deployed_profile_without_nonce_echo_still_rejects_replay(self):
        fields = decode(self.packet()[12:])
        del fields[b'NONC']
        raw = framed(encode(fields))
        self.assertFalse(verify(raw, self.nonce, self.key)['nonce_echo_present'])
        with self.assertRaisesRegex(ValueError, 'MERKLE_ROOT'):
            verify(raw, b'z'*32, self.key)

    def test_response_signature_tampering(self):
        fields = decode(self.packet()[12:])
        fields[b'SIG\0'] = bytes([fields[b'SIG\0'][0]^1])+fields[b'SIG\0'][1:]
        with self.assertRaises(InvalidSignature):
            verify(framed(encode(fields)), self.nonce, self.key)

    def test_delegation_expiry(self):
        with self.assertRaisesRegex(ValueError, 'DELEGATION_TIME'):
            verify(self.packet(midpoint=120), self.nonce, self.key)

    def test_merkle_index(self):
        with self.assertRaisesRegex(ValueError, 'MERKLE_ROOT'):
            verify(self.packet(index=1), self.nonce, self.key)

    def test_interval_includes_full_rtt_and_never_grants_drift(self):
        sample = verify(self.packet(), self.nonce, self.key)
        result = local_interval(sample, sent_wall=99.9, received_wall=100.1, elapsed=.2)
        self.assertEqual(result['utc_received_interval'], [99, 101.2])
        self.assertFalse(result['below_one_second'])
        self.assertIsNone(result['max_drift_ppm'])
        self.assertEqual(result['status'], 'HOLD')

    def test_zero_radius_does_not_self_admit(self):
        result = local_interval(verify(self.packet(radius=0), self.nonce, self.key),
                                sent_wall=100, received_wall=100.1, elapsed=.1)
        self.assertTrue(result['below_one_second'])
        self.assertEqual(result['status'], 'HOLD')

    def test_nonfinite_or_reverse_clock(self):
        for value in [math.inf, math.nan, -1]:
            with self.assertRaises(ValueError):
                local_interval({}, sent_wall=0, received_wall=1, elapsed=value)

    def test_duplicate_tags_bad_offsets_and_truncation(self):
        for raw in [b'', b'\x01\0\0\0', struct.pack('<I', 99)+b'\0'*28,
                    struct.pack('<II', 2, 4)+b'AAAAAAAABBBBCCCC']:
            with self.assertRaises(ValueError):
                decode(raw)

    def test_request_profile_and_frame_length(self):
        raw = request(self.nonce, self.key)
        self.assertEqual(len(raw), 1024)
        self.assertEqual(decode(raw[12:])[b'NONC'], self.nonce)
        with self.assertRaisesRegex(ValueError, 'FRAME'):
            verify(self.packet()+b'\0'*4, self.nonce, self.key)
