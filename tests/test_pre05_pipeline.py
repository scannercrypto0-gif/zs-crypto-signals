"""008 regression: real modules, synthetic source, mocked GitHub only."""
from datetime import datetime, timezone
import hashlib
import unittest
from copy import deepcopy
from test_scanner import klines
from test_github_evidence_backend import MockContentsTransport
from zs_smart_gate.scanner import build_universe, inspect_candles
from zs_smart_gate.evidence_journal import SingleStudyJournal, canonical_bytes
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend, verify_snapshot
from zs_smart_gate.stage03b1_live import parse_kline
from zs_smart_gate.mtf_contracts import reconcile, ReconciliationTolerance

NOW=datetime(2026,11,2,9,1,tzinfo=timezone.utc)

def source(symbol):
    exchange={'symbols':[{'symbol':symbol,'quoteAsset':'USDT','status':'TRADING','isSpotTradingAllowed':True}]}
    ticker=[{'symbol':symbol,'quoteVolume':'50000000'}]
    book=[{'symbol':symbol,'bidPrice':'99.99','askPrice':'100.01'}]
    return exchange,ticker,book

class Pre05PipelineTests(unittest.TestCase):
    def scan(self,symbol,rows=None):
        universe=build_universe(*source(symbol),NOW)
        return inspect_candles(universe[0],rows if rows is not None else klines(int(NOW.timestamp()*1000)),NOW,NOW,0)

    def test_btc_eth_source_candidate_claim_receipt_independent_restore(self):
        for symbol in ('BTCUSDT','ETHUSDT'):
            with self.subTest(symbol=symbol):
                candidate=self.scan(symbol)
                self.assertEqual(candidate.status,'PASS')
                self.assertIsNone(candidate.candidate.score)
                payload={'source_id':'SYNTHETIC:PRE05-008','symbol':symbol,
                         'event_id':'evt-'+symbol,'kind':'RESEARCH_ONLY','candidate':candidate.as_dict()}
                transport=MockContentsTransport()
                backend=GitHubEvidenceBackend('study-pre05-008',branch='evidence-study-pre05-008',transport=transport,enabled=True)
                journal=SingleStudyJournal('study-pre05-008',backend,lambda:NOW)
                self.assertTrue(journal.claim_before_attempts('study-pre05-008',payload['event_id']))
                digest=hashlib.sha256(canonical_bytes(payload)).hexdigest()
                self.assertTrue(journal.append_and_readback(payload['event_id'],payload,digest))
                self.assertFalse(journal.claim_before_attempts('study-pre05-008',payload['event_id']))
                snapshot={k:bytes(v) for k,v in transport.files.items()}
                restored=verify_snapshot('study-pre05-008',snapshot)
                self.assertTrue(restored.ok,restored.status)
                self.assertEqual(restored.records_checked,2)
                receipt=next(k for k in snapshot if '/receipts/' in k)
                bad=deepcopy(snapshot);bad[receipt]+=b'corrupt'
                self.assertFalse(verify_snapshot('study-pre05-008',bad).ok)
                missing={k:v for k,v in snapshot.items() if k!=receipt}
                self.assertFalse(verify_snapshot('study-pre05-008',missing).ok)

    def test_unknown_join_not_promoted_and_missing_market_explicit(self):
        e,t,b=source('ETHUSDT')
        t.append({'symbol':'UNKNOWNUSDT','quoteVolume':'999999999'})
        b.append({'symbol':'UNKNOWNUSDT','bidPrice':'1','askPrice':'1'})
        self.assertEqual([x.symbol for x in build_universe(e,t,b,NOW)],['ETHUSDT'])
        missing=build_universe(e,[],b,NOW)[0]
        self.assertNotEqual(missing.status,'ELIGIBLE')
        self.assertTrue(missing.reasons)

    def test_missing_duplicate_stale_and_future_closed_windows(self):
        rows=klines(int(NOW.timestamp()*1000))
        for broken in (rows[:10],rows[:5]+[rows[4]]+rows[6:]):
            self.assertNotEqual(self.scan('ETHUSDT',broken).status,'PASS')
        stale=klines(int(NOW.timestamp()*1000)-600000)
        self.assertNotEqual(self.scan('ETHUSDT',stale).status,'PASS')
        # Open final bar is intentionally ignored, never fabricated as closed.
        self.assertEqual(self.scan('ETHUSDT',rows).status,'PASS')

    def test_harness_reconcile_signature_eth_30m(self):
        close=int(datetime(2026,11,2,9,tzinfo=timezone.utc).timestamp()*1000)
        def row(start,duration,base,quote):
            return [start,'100','101','99','100.5',str(base),start+duration-1,str(quote),1,'0','0','0']
        parent=parse_kline(row(close-1800000,1800000,600,60300),'30m',NOW)
        children=[parse_kline(row(close-1800000+i*300000,300000,100,10050),'5m',NOW) for i in range(6)]
        result=reconcile(parent,children,NOW,tolerance=ReconciliationTolerance('0','0','0','008_FIXTURE'))
        self.assertEqual(result.status,'PASS')

