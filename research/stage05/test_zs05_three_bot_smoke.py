"""Focused Stage05 smoke harness security checks; all network forbidden."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
from urllib.error import URLError
import importlib.util
import json

HERE = Path(__file__).with_name('zs05_three_bot_smoke_windows.py')
spec = importlib.util.spec_from_file_location('zs05_smoke', HERE)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
FAKE = {'05A': '123456:'+'A'*30, '05B': '234567:'+'B'*30, '05C': '345678:'+'C'*30}


class OfflineHarnessTests(TestCase):
    def test_default_dry_run_is_no_network_no_secret_no_git(self):
        with (patch.object(smoke.OPENER, 'open', side_effect=AssertionError('HTTP forbidden')) as net,
              patch.object(smoke, 'hidden_token', side_effect=AssertionError('secrets forbidden')) as keys,
              patch.object(smoke, 'private_folder', side_effect=AssertionError('writes forbidden')) as writes,
              patch.object(smoke.subprocess, 'run', side_effect=AssertionError('git forbidden')) as git,
              redirect_stdout(StringIO()) as output):
            self.assertEqual(smoke.main([]), 0)
            self.assertIn('DRY_RUN_PASS_NO_NETWORK_NO_SECRETS', output.getvalue())
            self.assertIn('"maximum_api_calls": 17', output.getvalue())
            for mocked in (net, keys, writes, git):
                mocked.assert_not_called()

    def test_route_only_exact_A_B_and_C_A(self):
        smoke.check_routes('1001', '1002', '1001', ('1001','1002'), FAKE)
        for a,b,c,allowed in (
                ('1001','1001','1001',('1001','1002')),
                ('1001','1002','1003',('1001','1002')),
                ('1001','1002','1001',('1001','1003')),
                ('1001','1002','1001',()),
                ('-1001','1002','-1001',('1001','1002'))):
            with self.subTest(a=a,b=b,c=c,allowed=allowed):
                with self.assertRaises(smoke.StopSmoke):
                    smoke.check_routes(a,b,c,allowed,FAKE)
        with self.assertRaises(smoke.StopSmoke):
            smoke.check_routes('1001','1002','1001',('1001','1002'),
                               {**FAKE,'05C': FAKE['05A']})

    def test_archive_documents_are_test_only_without_signal_id(self):
        docs = smoke.fixtures('DRY_SYNTHETIC_CASE')
        self.assertEqual(len(docs), 2)
        for kind,(filename,raw,sha) in docs.items():
            data=json.loads(raw)
            self.assertEqual(smoke.digest(raw),sha)
            self.assertEqual(data['payload_sha256'],smoke.digest(smoke.encoded(data['payload'])))
            self.assertEqual(data['payload']['signal_id'],None)
            self.assertTrue(data['payload']['test_only'])
            self.assertIn('test_only_',filename)
            self.assertEqual(data['payload']['kind'],kind)

    def test_identity_rejects_fake_role_and_token_swaps(self):
        result={'id':123456,'username':'zscryptosignalsbot','is_bot':True}
        self.assertEqual(smoke.identity(FAKE['05A'],result,'05A'),123456)
        for info, role in ((result,'05B'), ({**result,'id':98765},'05A'),
                           ({**result,'is_bot':False},'05A')):
            with self.assertRaises(smoke.StopSmoke):
                smoke.identity(FAKE['05A'],info,role)

    def test_network_timeout_stops_after_one_attempt_no_url_leak(self):
        state={'api_calls':0}
        with patch.object(smoke.OPENER,'open',side_effect=URLError('contains token')) as net:
            with self.assertRaises(smoke.StopSmoke) as caught:
                smoke.api(state,FAKE['05A'],'sendMessage',{'chat_id':'1001','text':'test'})
            self.assertEqual(str(caught.exception),'NETWORK_TIMEOUT_STOP_UNKNOWN')
            self.assertNotIn(FAKE['05A'],str(caught.exception))
            self.assertEqual(state['api_calls'],1)
            net.assert_called_once()

    def test_cap_and_denied_execute_on_non_windows(self):
        state={'api_calls':17}
        with self.assertRaisesRegex(smoke.StopSmoke,'API_CALL_LIMIT_17_EXCEEDED'):
            smoke.limit_counter(state)
        with (patch.object(smoke,'hidden_token',side_effect=AssertionError('secret access')) as get_secret,
              redirect_stdout(StringIO()) as output):
            code=smoke.main(['--execute','--head-sha','a'*40,'--tree-sha','b'*40,
                             '--script-sha256','c'*64])
            self.assertEqual(code,2)
            get_secret.assert_not_called()
            self.assertIn('SAFE_ABORT_BEFORE_LIVE',output.getvalue())


if __name__ == '__main__':
    main()