"""Passive diagnostics only: fixtures and temporary journals, no production IO."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

import bitman_weekly_forward_logging as logging
import bitman_weekly_forward_log_worker as log_worker
from bitman_weekly_forward import host as original_host
from test_bitman_weekly_host import healthy,child

ROOT=Path(__file__).resolve().parent
REVIEWED='3127ec40742feaf77c2b19d7150057c290c85c0e'
URL='http://bitman-market-data.railway.internal:8080/fapi/v1/klines'
WEEK_OPEN=1791763200000
NEXT_DUE=1792973100000
FIELDS={'status','protocol_version','schema_version','journal_records','journal_tip_prefix','week_open','available_at',
        'strict_state','lag1_state','lag2_state','strict_pending','lag1_pending','lag2_pending',
        'forward_events','active','matured','h1','h2','h3','h4','evidence','next_due'}


def view():
    return dict(healthy(),journal_records=2,journal_tip='a'*64,week_open=WEEK_OPEN,
                forward_events=0,evidence='INSUFFICIENT',next_due=NEXT_DUE)


def drain(sink):
    lines=[]
    while True:
        try:lines.append(sink._queue.get_nowait());sink._queue.task_done()
        except queue.Empty:return lines


class StatusLogging(unittest.TestCase):
    def test_first_healthy_once_and_unchanged_repeat_silent(self):
        sink=logging.Diagnostics();value=view();before=copy.deepcopy(value)
        for _ in range(100):sink.status(value)
        self.assertEqual(value,before)
        lines=drain(sink);self.assertEqual(len(lines),1)
        data=json.loads(lines[0][len(logging.STATUS_PREFIX):])
        self.assertEqual(set(data),FIELDS);self.assertEqual(data['journal_records'],2)
        self.assertEqual(data['journal_tip_prefix'],'a'*12)
        self.assertEqual([data[k] for k in ('strict_state','lag1_state','lag2_state')],['OTHER']*3)

    def test_tip_change_compares_full_hash_even_same_twelve_character_prefix(self):
        sink=logging.Diagnostics();sink.status(view());sink.status(dict(view(),journal_tip='a'*12+'b'*52))
        self.assertEqual(len(drain(sink)),2)

    def test_status_and_record_count_changes_emit(self):
        sink=logging.Diagnostics();sink.status(view());sink.status(dict(view(),journal_records=3))
        sink.status({'status':'DEGRADED'});sink.status({'status':'DEGRADED'})
        sink.status({'status':'OBSERVER_JOURNAL_INVALID'})
        lines=drain(sink);self.assertEqual(len(lines),4)
        self.assertIn('BITMAN_WEEKLY_FORWARD_DEGRADED',lines[2])
        self.assertIn('BITMAN_WEEKLY_FORWARD_JOURNAL_INVALID',lines[3])

    def test_unrelated_changes_never_trigger(self):
        sink=logging.Diagnostics();value=view();sink.status(value)
        value.update(updated_at=999999,next_due=1234,evidence='anything',raw_candles=['private'])
        value['snapshot']['ao']=12345;sink.status(value)
        self.assertEqual(len(drain(sink)),1)

    def test_only_allowlisted_values_no_secrets_paths_payload_or_full_hash(self):
        token='987654321:synthetic-secret-canary'
        value=dict(view(),token=token,environment={'API_KEY':token},source_sha=token,
                   storage_path='/private/canary',raw_candles=[token],journal=[token],event_payload={'account':token})
        value['snapshot']['models'][logging.MODELS[0]]['pending']={'account':token}
        value['snapshot']['models'][logging.MODELS[1]]['state']=token
        value['horizons']['2']=token;value['next_due']=token
        sink=logging.Diagnostics();sink.status(value);text=drain(sink)[0]
        data=json.loads(text[len(logging.STATUS_PREFIX):])
        self.assertEqual(set(data),FIELDS);self.assertTrue(data['strict_pending'])
        self.assertIsNone(data['lag1_state']);self.assertIsNone(data['h2']);self.assertIsNone(data['next_due'])
        for forbidden in (token,'/private/canary','a'*64,'environment','raw_candles','event_payload','source_sha'):
            self.assertNotIn(forbidden,text)
        self.assertLess(len(text),1500)

    def test_invalid_values_are_static_or_null(self):
        for status in ('secret-canary',{},None,42):
            _,data=logging.status_projection(dict(view(),status=status,journal_tip='secret-canary',journal_records=True))
            self.assertEqual(data['status'],'BITMAN_WEEKLY_FORWARD_DEGRADED')
            self.assertIsNone(data['journal_tip_prefix']);self.assertIsNone(data['journal_records'])

    def test_logging_failure_and_full_queue_never_raise(self):
        sink=logging.Diagnostics()
        sink._queue.put_nowait=Mock(side_effect=OSError('secret-canary'))
        sink.status(view());sink.fetch(WEEK_OPEN)
        sink=logging.Diagnostics()
        for i in range(100):sink.status(dict(view(),journal_records=i))
        self.assertEqual(sink._queue.qsize(),32)

    def test_broken_output_sink_does_not_kill_log_thread(self):
        reached=threading.Event();calls=[]
        def writer(line):
            calls.append(line);reached.set();raise OSError('secret-canary')
        sink=logging.Diagnostics(writer);sink.start();sink.status(view())
        self.assertTrue(reached.wait(1));self.assertTrue(sink._thread.is_alive())

    def test_blocked_logger_never_delays_observer_or_guardian_hook(self):
        entered=threading.Event();release=threading.Event()
        def writer(line):entered.set();release.wait(3)
        sink=logging.Diagnostics(writer);sink.start();sink.status(view())
        self.assertTrue(entered.wait(1))
        instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=sink,clock=lambda:1000)
        done=threading.Event()
        def observe():
            with patch.object(logging.subprocess,'Popen',return_value=child(view())):instance.once()
            done.set()
        thread=threading.Thread(target=observe);thread.start()
        try:
            self.assertTrue(done.wait(1));self.assertEqual(instance.read()['status'],'HEALTHY')
            with patch.dict(os.environ,{original_host.FLAG:'true'},clear=True),\
                 patch.object(original_host,'_HOST',instance):logging.after_cycle()
        finally:release.set();thread.join(1)

    def test_stdout_fd_only_and_no_shared_textio_write(self):
        with patch.object(logging.os,'write') as write:
            logging.write_stdout('STATIC')
        write.assert_called_once_with(1,b'STATIC\n')


class HostAdapter(unittest.TestCase):
    def test_original_host_io_ast_retained_except_exact_passive_extensions(self):
        def method(file,cls):
            tree=ast.parse((ROOT/file).read_text('utf-8'))
            klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            return copy.deepcopy(next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='once'))
        old=method('bitman_weekly_forward/host.py','WeeklyHost')
        new=method('bitman_weekly_forward_logging.py','LoggingHost')
        diagnostic=ast.parse('try:\n self._diagnostics.status(result)\nexcept Exception:pass').body[0]
        removed=[]
        for node in ast.walk(new):
            if isinstance(node,ast.Constant) and node.value=='bitman_weekly_forward_log_worker':node.value='bitman_weekly_forward.worker'
        targets={ast.dump(ast.parse('forward_fetches(stderr_output,self._diagnostics,attempts)').body[0]):'marker',
                 ast.dump(ast.parse('attempts=set()').body[0]):'attempts',
                 ast.dump(ast.parse("forward_fetches(getattr(error,'stderr',None),self._diagnostics,attempts)").body[0]):'partial'}
        for node in ast.walk(new):
            if isinstance(node,ast.ExceptHandler) and node.name=='error':node.name=None
            if hasattr(node,'body') and isinstance(node.body,list):
                for child in list(node.body):
                    label=targets.get(ast.dump(child))
                    if label:node.body.remove(child);removed.append(label)
                for i,child in enumerate(node.body):
                    if ast.dump(child)==ast.dump(ast.parse('_,stderr_output=process.communicate(timeout=2)').body[0]):
                        node.body[i]=ast.parse('process.communicate(timeout=2)').body[0];removed.append('capture')
                    elif ast.dump(child)==ast.dump(ast.parse('output,stderr_output=process.communicate(json.dumps(request),timeout=TIMEOUT)').body[0]):
                        node.body[i]=ast.parse('output,_=process.communicate(json.dumps(request),timeout=TIMEOUT)').body[0];removed.append('channel')
        matches=[n for n in new.body if ast.dump(n)==ast.dump(diagnostic)]
        for match in matches:new.body.remove(match);removed.append('status')
        self.assertEqual(sorted(removed),['attempts','capture','channel','marker','marker','partial','status'])
        self.assertEqual(ast.dump(new),ast.dump(old))

    def test_original_worker_delegated_without_replacing_protocol_computation(self):
        import inspect
        source=inspect.getsource(log_worker.main)
        self.assertIn('from bitman_weekly_forward.worker import main as original_main',source)
        self.assertIn('original_main()',source)
        self.assertNotIn('observer.run',source)

    def test_disabled_is_absolutely_silent_and_does_not_construct_logger(self):
        with patch.dict(os.environ,{},clear=True),patch.object(logging,'LoggingHost') as factory,\
             patch.object(logging.os,'write') as write:
            for _ in range(10):logging.after_cycle()
        factory.assert_not_called();write.assert_not_called()

    def test_enabled_host_keeps_shared_manual_read_and_shutdown_source(self):
        instance=Mock()
        with patch.dict(os.environ,{original_host.FLAG:'true'},clear=True),\
             patch.object(original_host,'_HOST',None),patch.object(logging,'LoggingHost',return_value=instance) as factory:
            logging.after_cycle();logging.after_cycle()
            original_host.manual_context();original_host.shutdown()
        factory.assert_called_once();instance.read.assert_called_once();instance.stop.assert_called_once()

    def test_secret_environment_still_not_inherited_by_child(self):
        sink=logging.Diagnostics();instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=sink)
        with patch.dict(os.environ,{'PATH':'synthetic','TELEGRAM_TOKEN':'secret-canary','BITUNIX_API_KEY':'secret-canary'},clear=True),\
             patch.object(logging.subprocess,'Popen',return_value=child(view())) as popen:instance.once()
        self.assertEqual(set(popen.call_args.kwargs['env']),{'PATH','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE'})
        self.assertEqual(json.loads(popen.return_value.communicate.call_args.args[0]),
                         dict(storage_path='/data',market_data_url=URL,source_sha='a'*40))

    def test_logger_exceptions_cannot_degrade_worker_result(self):
        bad=Mock();bad.status.side_effect=OSError();bad.fetch.side_effect=OSError()
        process=child(view());process.communicate.return_value=(json.dumps(view()),logging.FETCH_PREFIX+str(WEEK_OPEN)+'\nsecret stderr')
        instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=bad)
        with patch.object(logging.subprocess,'Popen',return_value=process):instance.once()
        self.assertEqual(instance._value,view())

    def test_logger_initialization_failure_does_not_prevent_observation(self):
        with patch.object(logging,'Diagnostics',side_effect=OSError('secret-canary')):
            instance=logging.LoggingHost('/data',URL,'a'*40)
        with patch.object(logging.subprocess,'Popen',return_value=child(view())):instance.once()
        self.assertEqual(instance._value,view())
        failed=Mock();failed.start.side_effect=OSError()
        instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=failed)
        with patch.object(original_host.WeeklyHost,'start') as start:instance.start()
        start.assert_called_once()

    def test_timeout_keeps_real_fetch_marker_once_and_never_echoes_exception(self):
        marker=logging.FETCH_PREFIX+str(WEEK_OPEN)+'\n'
        process=Mock(returncode=None);process.poll.return_value=None
        process.communicate.side_effect=[subprocess.TimeoutExpired('secret-canary',60,stderr=marker.encode()),('',marker+'private stderr')]
        sink=logging.Diagnostics();instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=sink)
        with patch.object(logging.subprocess,'Popen',return_value=process):instance.once()
        lines=drain(sink);self.assertEqual(lines[0],marker.strip());self.assertEqual(len(lines),2)
        self.assertIn('BITMAN_WEEKLY_FORWARD_DEGRADED',lines[1]);self.assertNotIn('secret-canary',''.join(lines))
        self.assertEqual(instance._value,{'status':'DEGRADED'});process.kill.assert_called_once()

    def test_crash_after_get_still_forwards_attempt_without_raw_output(self):
        marker=logging.FETCH_PREFIX+str(WEEK_OPEN)+'\n'
        process=Mock(returncode=1);process.communicate.return_value=('',marker+'secret-canary');process.poll.return_value=1
        sink=logging.Diagnostics();instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=sink)
        with patch.object(logging.subprocess,'Popen',return_value=process):instance.once()
        lines=drain(sink);self.assertEqual(lines[0],marker.strip());self.assertEqual(len(lines),2)
        self.assertNotIn('secret-canary',''.join(lines));self.assertEqual(instance._value,{'status':'DEGRADED'})

    def test_frozen_protocol_files_manifest_and_hash_are_byte_identical(self):
        # Literal SHA from the reviewed HEAD remains enforceable in shallow CI.
        data=(ROOT/'bitman_weekly_forward/protocol_v1.json').read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(hashlib.sha256(data).hexdigest(),'2be9d6710668b8ec4deddb6e6b32ad4bd59d37addefdd840a493205d4b9fa09a')
        from bitman_weekly_forward.protocol import verify,EXPECTED_HASH
        self.assertEqual(EXPECTED_HASH,'d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8')
        self.assertEqual((ROOT/'tests/fixtures/weekly_forward_protocol.sha256').read_text().strip(),EXPECTED_HASH)
        verify()


class FetchDiagnostic(unittest.TestCase):
    def args(self,url=None,method='GET'):
        query='?symbol=BTCUSDT&interval=1h&startTime='+str(WEEK_OPEN)+'&endTime='+str(WEEK_OPEN+logging.WEEK-1)+'&limit=168'
        return (url or URL+query,None,{},method)

    def test_only_actual_matching_urllib_request_event_logs(self):
        with patch.object(log_worker.os,'write') as write:
            log_worker.audit_request('urllib.Request',self.args())
        write.assert_called_once_with(2,(logging.FETCH_PREFIX+str(WEEK_OPEN)+'\n').encode())

    def test_unrelated_requests_payloads_paths_or_invalid_week_never_log(self):
        with patch.object(log_worker.os,'write') as write:
            for event,args in (('import',self.args()),('urllib.Request',self.args(method='POST')),
                    ('urllib.Request',self.args(url='https://secret-canary/private')),
                    ('urllib.Request',self.args(url=self.args()[0]+'&token=secret-canary')),
                    ('urllib.Request',self.args(url=self.args()[0].replace('limit=168','limit=1'))),
                    ('urllib.Request',('secret-canary',))):log_worker.audit_request(event,args)
        write.assert_not_called()

    def test_fetch_logger_failure_cannot_prevent_get(self):
        with patch.object(log_worker.os,'write',side_effect=OSError('secret-canary')):
            log_worker.audit_request('urllib.Request',self.args())

    def test_parent_forwards_no_raw_stderr_or_unrecognized_output(self):
        sink=logging.Diagnostics()
        for raw in ('secret-canary\n{}','BITMAN_WEEKLY_FORWARD_FETCH=secret-canary\n{}'):
            logging.forward_fetches(raw,sink,set())
        self.assertEqual(drain(sink),[])

    def test_malformed_diagnostic_channel_never_corrupts_worker_result(self):
        process=child(view());process.communicate.return_value=(json.dumps(view()),logging.FETCH_PREFIX+'broken-secret-canary')
        sink=logging.Diagnostics();instance=logging.LoggingHost('/data',URL,'a'*40,diagnostics=sink)
        with patch.object(logging.subprocess,'Popen',return_value=process):instance.once()
        self.assertEqual(instance._value,view());lines=drain(sink)
        self.assertEqual(len(lines),1);self.assertNotIn('broken-secret-canary',lines[0])


class ActualWorkerBoundary(unittest.TestCase):
    """Isolated real Python audit hook; HTTP handler is an offline fixture."""
    SCRIPT=r'''
import io,json,sys,time
from email.message import Message
from urllib.parse import parse_qs,urlsplit
from urllib.response import addinfourl
from bitman_weekly_forward import worker,market,observer
from test_bitman_weekly_forward import START,SOURCE,MANIFEST,hours
import bitman_weekly_forward_log_worker as diagnostic
outer=json.loads(sys.stdin.read())
request=dict(storage_path=outer['folder'],market_data_url=market.PRIVATE_URL,source_sha=SOURCE)
now=START+(market.WEEK if outer['fetch'] else 0)
worker.time.time=lambda:now/1000
if outer['fetch']:observer.run(outer['folder'],market.PRIVATE_URL,SOURCE,START)
markers=[]
write=diagnostic.os.write
def record(fd,data):
    if data.startswith(b'BITMAN_WEEKLY_FORWARD_FETCH='):markers.append(data)
    return write(fd,data)
diagnostic.os.write=record
original_build=market.http.build_opener
class Fixture(market.http.HTTPHandler):
    def http_open(self,req):
        if outer['logging']:assert markers,'Request did not log before GET'
        opening=int(parse_qs(urlsplit(req.full_url).query)['startTime'][0])
        response=addinfourl(io.BytesIO(json.dumps(hours(opening)).encode()),Message(),req.full_url,200)
        response.msg='OK'
        return response
market.http.build_opener=lambda *handlers:original_build(*handlers,Fixture())
sys.stdin=io.StringIO(json.dumps(request))
(diagnostic.main if outer['logging'] else worker.main)()
'''

    def setUp(self):
        try:import numpy
        except ImportError:self.skipTest('Full observer workflow installs NumPy')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def execute(self,label,diagnostic=True,fetch=False):
        folder=str(Path(self.temp.name)/label)
        env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
        env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-B','-c',self.SCRIPT],cwd=ROOT,env=env,
            input=json.dumps(dict(folder=folder,logging=diagnostic,fetch=fetch)),
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0)
        lines=result.stdout.splitlines();data=json.loads(lines[-1]);self.assertEqual(data['status'],'HEALTHY')
        return Path(folder),lines,data,result.stderr

    def test_bootstrap_before_next_close_no_fetch_marker(self):
        folder,lines,data,stderr=self.execute('bootstrap')
        self.assertEqual(len(lines),1);self.assertEqual(data['journal_records'],2)
        self.assertFalse(any(line.startswith(logging.FETCH_PREFIX) for line in lines))
        self.assertNotIn(logging.FETCH_PREFIX,stderr)
        records=[json.loads(line) for line in (folder/'bitman_weekly_forward_v1.jsonl').read_text().splitlines()]
        self.assertEqual([r['record_type'] for r in records],['FORWARD_OBSERVATION_START','BOOTSTRAP'])

    def test_fetch_marker_emitted_before_actual_fixture_get_and_parent_forwards_only_marker(self):
        folder,lines,data,stderr=self.execute('new-week',fetch=True)
        marker=logging.FETCH_PREFIX+'1792368000000'
        self.assertIn(marker,stderr);self.assertEqual(len(lines),1)
        sink=logging.Diagnostics();logging.forward_fetches(stderr,sink,set())
        self.assertEqual(drain(sink),[marker])

    def test_logging_does_not_change_any_journal_bytes_or_result(self):
        for fetch in (False,True):
            a,_,av,_=self.execute('original-'+str(fetch),diagnostic=False,fetch=fetch)
            b,_,bv,_=self.execute('logging-'+str(fetch),fetch=fetch)
            self.assertEqual(av,bv)
            for name in ('bitman_weekly_forward_v1.jsonl','bitman_weekly_forward_v1_state.json'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())


if __name__=='__main__':unittest.main()
