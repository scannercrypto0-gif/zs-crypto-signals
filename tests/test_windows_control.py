from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from zs_smart_gate.windows_control import assess_task,clock_status,Control,MARKER,run_ps
from zs_smart_gate.windows_operations import record_health

NOW=datetime(2026,10,28,12,tzinfo=timezone.utc)
CLOCK='Leap Indicator: 0\nSource: time.windows.com\nLast Sync Error: 0\nTime since Last Good Sync Time: 3.0s\nRoot Dispersion: 7.9s'

def snapshot():
    return {'exists':True,'description':MARKER,'enabled':True,'time_service':'Running','clock':CLOCK,
        'xml':'''<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Actions><Exec>
        <Command>D:/pythonw.exe</Command><Arguments>safe</Arguments><WorkingDirectory>D:/repo</WorkingDirectory>
        </Exec></Actions><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy></Settings>
        <Principals><Principal><LogonType>InteractiveToken</LogonType></Principal></Principals>
        <Triggers><TimeTrigger><StartBoundary>2026-10-28T11:00:00+00:00</StartBoundary>
        <Repetition><Duration>P1D</Duration></Repetition></TimeTrigger></Triggers></Task>'''}

class ControlTests(unittest.TestCase):
    def assess(self,s,now=NOW):
        return assess_task(s,expected_executable='D:/pythonw.exe',expected_arguments='safe',repo='D:/repo',now=now)
    def test_running_paused_expired(self):
        s=snapshot();self.assertEqual(self.assess(s)[0],'RUNNING')
        s['enabled']=False;self.assertEqual(self.assess(s)[0],'PAUSED')
        self.assertEqual(self.assess(s,NOW+timedelta(days=1))[0],'EXPIRED')
    def test_mismatch_and_unknown(self):
        s=snapshot();s['xml']=s['xml'].replace('pythonw','python')
        self.assertEqual(self.assess(s)[1],'TASK_ACTION_MISMATCH')
        s=snapshot();s['description']='other';self.assertEqual(self.assess(s)[1],'UNKNOWN_TASK')
    def test_clock_stopped_stale_unknown(self):
        for text,service in [(CLOCK,'Stopped'),(CLOCK.replace('3.0s','1801s'),'Running'),('','Running')]:
            self.assertFalse(clock_status(text,service)['operational_simulation_ok'])
    def test_offline_simulation_no_live(self):
        s=snapshot();s['internet_hint']=False
        self.assertEqual(self.assess(s)[0],'RUNNING')
        self.assertEqual(clock_status(CLOCK,'Running')['exchange_uncertainty'],'UNKNOWN')
    def test_rapid_resume_never_runs_or_renews(self):
        executor=Mock();c=Control('D:/c','x','D:/repo','D:/state','D:/logs','D:/pythonw.exe',executor=executor)
        with patch.object(c,'status',return_value={'state':'PAUSED'}):
            c.resume();c.resume();c.resume()
        self.assertEqual(executor.call_count,3)
        for call in executor.call_args_list:
            self.assertIn('Enable-ScheduledTask',call.args[0]);self.assertNotIn('Start-ScheduledTask',call.args[0])
            self.assertNotIn('Register-',call.args[0])
        executor.reset_mock()
        with patch.object(c,'status',return_value={'state':'EXPIRED'}):c.resume()
        executor.assert_not_called()
    def test_consoleless_management(self):
        with patch('zs_smart_gate.windows_control.subprocess.run') as run:
            run.return_value=Mock(returncode=0,stdout='{}')
            run_ps('Get-Date')
            self.assertIn('creationflags',run.call_args.kwargs)
            self.assertTrue(run.call_args.kwargs['capture_output'])
    def test_health_success_failure_persists_without_console(self):
        with tempfile.TemporaryDirectory() as d:
            logs=Path(d)
            a=record_health(logs,exit_code=0,revision='a'*40,config_sha='b'*64)
            b=record_health(logs,exit_code=2,revision='a'*40,config_sha='b'*64,category='PIN_MISMATCH')
            self.assertEqual(a['last_success_utc'],b['last_success_utc'])
            c=record_health(logs,exit_code=0,revision='a'*40,config_sha='b'*64)
            self.assertEqual(c['last_failure_utc'],b['last_failure_utc'])
            self.assertIsNone(c['current_error_category'])
            self.assertEqual(json.loads((logs/'health.json').read_text())['model_api_calls'],0)
