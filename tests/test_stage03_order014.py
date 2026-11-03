import importlib.util
import struct
import unittest
from zs_smart_gate.stage03_nts_authority import (
    ke_record,parse_ke,ke_complete,dns_identity,extension,protected_packet,verify_packet,decision_clock_gate)
from zs_smart_gate.stage03_source_clock import stamp
from zs_smart_gate.stage03_source_acceptance import assess_submission,REQUIRED


def ke():
    return ke_record(1,b'\0\0')+ke_record(4,b'\0\x0f')+ke_record(5,b'c'*32,False)+ke_record(0)


class AuthorityTests(unittest.TestCase):
    def test_ke_complete_and_strict_negotiation(self):
        self.assertTrue(ke_complete(ke()))
        self.assertFalse(ke_complete(ke()[:-1]))
        self.assertEqual(parse_ke(ke(),'time.cloudflare.com')['aead'],15)

    def test_unknown_critical_error_truncated_and_duplicate_fail(self):
        for bad in [ke()[:-1],ke_record(55,b'x')+ke(),ke_record(2,b'\0\0')+ke(),ke()+ke_record(0),ke_record(1,b'\0\0')+ke()]:
            with self.assertRaises(ValueError):
                parse_ke(bad,'time.cloudflare.com')

    def test_no_host_or_port_redirect(self):
        for prefix in [ke_record(6,b'evil.example'),ke_record(7,struct.pack('!H',4444))]:
            with self.assertRaises(ValueError):
                parse_ke(prefix+ke(),'time.cloudflare.com')

    def test_tls_dns_exact_or_single_label_wildcard_only(self):
        self.assertTrue(dns_identity('time.cloudflare.com',['*.cloudflare.com']))
        self.assertFalse(dns_identity('time.cloudflare.com',['*.com']))
        self.assertFalse(dns_identity('evil.time.cloudflare.com',['*.cloudflare.com']))
        self.assertFalse(dns_identity('time.cloudflare.com.evil',['time.cloudflare.com']))

    def sample(self):
        return dict(authentication='TLS13_NTSKE_AND_AES_SIV_CMAC_256',sample_local_received=100,
                    conditional_local_error_bound_seconds=.2)

    def test_authenticated_source_still_requires_error_attestation(self):
        self.assertEqual(decision_clock_gate(self.sample(),101,20), 'CLOCK_AUTHENTICATED_AUTHORITY_ERROR_ATTESTATION_MISSING')
        self.assertEqual(decision_clock_gate(self.sample(),101,20,True),'CLOCK_PASS_CANDIDATE_REVIEW_REQUIRED')
        self.assertEqual(decision_clock_gate(self.sample(),101,20,'False'),'CLOCK_AUTHENTICATED_AUTHORITY_ERROR_ATTESTATION_MISSING')

    def test_unauthenticated_expired_divergent_or_unknown_drift_fail(self):
        s = self.sample()
        self.assertEqual(decision_clock_gate({**s,'authentication':'NONE'},101,20),'CLOCK_UNAUTHENTICATED')
        self.assertEqual(decision_clock_gate(s,131,20),'CLOCK_STALE_OR_FUTURE')
        self.assertEqual(decision_clock_gate(s,99,20),'CLOCK_STALE_OR_FUTURE')
        self.assertEqual(decision_clock_gate(s,110,100000),'CLOCK_BOUND_EXCEEDED')
        self.assertEqual(decision_clock_gate(s,101,float('nan')),'CLOCK_DRIFT_UNKNOWN')
        self.assertEqual(decision_clock_gate({**s,'conditional_local_error_bound_seconds':float('nan')},101,20),'CLOCK_SAMPLE_INCOMPLETE')

    def test_source_timestamps_alone_never_qualify(self):
        for semantics in ['EVENT_TIME','COLLECTOR_ARRIVAL','CANDLE_CLOSE']:
            r = assess_submission(dict(assets=['BTCUSDT','ETHUSDT'],period=['2025-01-01','2025-07-01'],publication_semantics=semantics))
            self.assertIn('EVENT_OR_COLLECTOR_TIME_IS_NOT_PUBLICATION',r['reasons'])

    def test_external_review_and_all_liquidity_channels_required(self):
        submission = dict(assets=['BTCUSDT','ETHUSDT'],period=['2025-01-01','2025-07-01'],
                          publication_semantics='ISSUER_ORIGINAL_PUBLICATION',bid_ask=True,
                          rolling_24h_eligibility=True,gap_and_revision_manifest=True)
        submission.update({name:('%064x'%i)for i,name in enumerate(REQUIRED,1)})
        self.assertEqual(assess_submission(submission)['status'],'BLOCKED_EXTERNAL_EVIDENCE')
        r = assess_submission(submission,[submission[k]for k in REQUIRED])
        self.assertFalse(r['scientific_acceptance'])
        self.assertIn('CANDIDATE',r['status'])
        submission['period']=['2025-02-01','2025-02-02']
        self.assertIn('HISTORICAL_SCOPE_NOT_ATTESTED',assess_submission(submission)['reasons'])


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'Optional crypto dependency absent; real NTS locally verified separately')
class CryptoTests(unittest.TestCase):
    def test_rfc5297_known_answer(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESSIV
        key=bytes.fromhex('fffefdfcfbfaf9f8f7f6f5f4f3f2f1f0f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff')
        ad=bytes.fromhex('101112131415161718191a1b1c1d1e1f2021222324252627')
        plain=bytes.fromhex('112233445566778899aabbccddee')
        self.assertEqual(AESSIV(key).encrypt(plain,[ad]).hex(),'85632d07c6e8f37f950acd320a2ecc9340c02b9690c4dc04daef7f6afe5c')

    def reply(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESSIV
        t = 1790000000.
        header = bytearray(48);header[0]=36;header[1]=1
        header[24:32],header[32:40],header[40:48]=stamp(t),stamp(t+.01),stamp(t+.011)
        key,uid,nonce = bytes(range(32)),b'u'*32,b'n'*16
        prefix = bytes(header)+extension(0x104,uid)
        tag = AESSIV(key).encrypt(b'',[prefix,nonce])
        packet = prefix+extension(0x404,struct.pack('!HH',16,len(tag))+nonce+tag)
        return t,packet,key,uid

    def test_verified_packet_is_only_clock_partial(self):
        t,p,key,uid = self.reply()
        r = verify_packet(p,uid,key,stamp(t),t,t+.03,.03)
        self.assertFalse(r['absolute_UTC_certified'])
        self.assertFalse(r['publication_proved'])

    def test_tamper_nonce_tag_uid_header_and_trailer_rejected(self):
        t,p,key,uid = self.reply()
        for where in [1,55,len(p)-1,len(p)-20]:
            bad=bytearray(p);bad[where]^=1
            with self.assertRaises(Exception):
                verify_packet(bytes(bad),uid,key,stamp(t),t,t+.03,.03)
        with self.assertRaises(ValueError):
            verify_packet(p+extension(0x104,uid),uid,key,stamp(t),t,t+.03,.03)

    def test_client_request_matches_aead_contract(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESSIV
        header,uid,key,nonce=b'\x23'+b'\0'*47,b'u'*32,bytes(range(32)),b'n'*16
        packet=protected_packet(header,uid,b'c'*32,key,nonce)
        pos=len(packet)-40
        self.assertEqual(AESSIV(key).decrypt(packet[-16:],[packet[:pos],nonce]),b'')


if __name__ == '__main__':
    unittest.main()
