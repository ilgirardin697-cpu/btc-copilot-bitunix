"""All transports are offline fixtures; zero real endpoint requests."""
import ast,copy,json,sqlite3,subprocess,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
try:import numpy as np
except ImportError as error:raise unittest.SkipTest('Research CI installs NumPy') from error
from ..test_forward import bars,raw_rows,ACT,HOUR
from .client import PublicClient,PublicFailure
from .spool import Spool
from .qualification import schedule,revision_report,OFFSETS

class Response:
    def __init__(self,data,status=200):self.data=data;self.status=status
    def read(self,n):return self.data[:n]
    def getheader(self,name):return 'application/json' if name=='Content-Type' else None

class Fixture:
    def __init__(self,answers,calls):self.answers=answers;self.calls=calls
    def request(self,method,path,headers):self.calls.append((method,path,headers))
    def getresponse(self):
        value=self.answers.pop(0)
        if isinstance(value,Exception):raise value
        return value
    def close(self):pass

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.spool=Spool(self.root/'spool');self.now=ACT+2*HOUR+60000;self.answers=[];self.calls=[]
        self.client=PublicClient(self.spool,True,fixture_connection=lambda:Fixture(self.answers,self.calls),clock=lambda:self.now)
    def tearDown(self):self.spool.close();self.tmp.cleanup()
    def clock_reply(self):return Response(json.dumps(dict(serverTime=self.now)).encode())
    def test_default_off_no_http_or_filesystem(self):
        root=self.root/'disabled';c=PublicClient()
        with patch('http.client.HTTPSConnection') as http:
            with self.assertRaises(PublicFailure):c.server_time()
            http.assert_not_called()
        self.assertFalse(root.exists())
    def test_public_clock_and_exact_closed_page_and_raw_bytes(self):
        a=bars(6002)[6000:6002];raw=json.dumps(raw_rows(a)).encode();self.answers[:]=[self.clock_reply(),Response(raw)]
        result=self.client.closed_hours(ACT,ACT+2*HOUR-1);np.testing.assert_array_equal(result['rows'],a)
        r=result['receipt'];self.assertEqual(r['body'],raw);self.assertEqual(r['metadata']['body_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(r['metadata']['exchange_time_ms'],self.now);self.assertEqual(r['metadata']['clock_receipt_hash'],result['clock_receipt_hash'])
        self.assertTrue(all(c[0]=='GET' for c in self.calls));self.assertFalse(result['observation_or_prediction_emitted'])
    def test_no_private_path_unknown_query_symbol_or_interval(self):
        for path,query in [('/fapi/v1/order',{}),('https://evil.invalid/',{}),('/fapi/v1/time',{'signature':'forbidden'}),
             ('/fapi/v1/klines',dict(symbol='ETHUSDT',interval='1h',startTime=0,endTime=1,limit=1)),
             ('/fapi/v1/klines',dict(symbol='BTCUSDT',interval='15m',startTime=0,endTime=1,limit=1))]:
            with self.assertRaises(PublicFailure):self.client._get(path,query)
        self.assertEqual(self.calls,[])
    def test_no_real_network_without_separate_authorization(self):
        c=PublicClient(self.spool,True)
        with patch('http.client.HTTPSConnection') as http:
            with self.assertRaises(PublicFailure):c.server_time()
            http.assert_not_called()
    def test_no_redirect_or_geoblock_fallback(self):
        for status in (301,302,403,429,451,500):
            self.answers[:]=[Response(b'public error',status)]
            with self.assertRaisesRegex(PublicFailure,'PUBLIC_HTTP_'+str(status)):self.client.server_time()
        self.assertEqual(len(self.calls),6);self.assertTrue(self.spool.verify())
    def test_timeout_static_no_exception_text_and_recorded(self):
        self.answers[:]=[TimeoutError('secret-canary')]
        with self.assertRaisesRegex(PublicFailure,'PUBLIC_TRANSPORT_FAILURE'):self.client.server_time()
        text=self.spool.db.execute('SELECT metadata FROM receipts').fetchone()[0]
        self.assertNotIn('secret-canary',text);self.assertIn('PUBLIC_TRANSPORT_FAILURE',text)
    def test_open_candle_rejected_before_market_request(self):
        self.answers[:]=[self.clock_reply()]
        with self.assertRaisesRegex(PublicFailure,'OPEN_CANDLE'):self.client.closed_hours(ACT+2*HOUR,ACT+3*HOUR-1)
        self.assertEqual(len(self.calls),1)
    def test_partial_gap_duplicate_and_schema_fail_closed(self):
        a=bars(6002)[6000:6002];rows=raw_rows(a)
        for raw in (rows[:1],[rows[0],rows[0]],[[1,2,3]],{}):
            self.answers[:]=[self.clock_reply(),Response(json.dumps(raw).encode())]
            with self.assertRaises((ValueError,PublicFailure)):self.client.closed_hours(ACT,ACT+2*HOUR-1)
    def test_server_clock_skew_and_discontinuity(self):
        self.answers[:]=[Response(json.dumps(dict(serverTime=self.now+10000)).encode())]
        with self.assertRaises(PublicFailure):self.client.server_time()
        self.answers[:]=[self.clock_reply()];ticks=iter((0,10_000_000_000));self.client.monotonic=lambda:next(ticks)
        with self.assertRaisesRegex(PublicFailure,'CLOCK_DISCONTINUITY'):self.client.server_time()
    def test_regular_funding_and_missing_mark_explicit(self):
        rows=[dict(symbol='BTCUSDT',fundingTime=ACT,fundingRate='.001',rateType='Regular')]
        self.answers[:]=[self.clock_reply(),Response(json.dumps(rows).encode())]
        result=self.client.funding_history(ACT,ACT+HOUR);self.assertFalse(result['mark_complete']);self.assertEqual(result['rows'],rows)
        rows[0]['rateType']='Special';self.answers[:]=[self.clock_reply(),Response(json.dumps(rows).encode())]
        with self.assertRaises(PublicFailure):self.client.funding_history(ACT,ACT+HOUR)
    def test_append_only_spool_reboot_and_second_writer(self):
        self.spool.append({'kind':'FIXTURE'},b'original');tip=self.spool.tip
        with self.assertRaises((OSError,RuntimeError)):Spool(self.root/'spool')
        with self.assertRaises(sqlite3.IntegrityError):self.spool.db.execute('UPDATE receipts SET body=?',(b'bad',))
        with self.assertRaises(sqlite3.IntegrityError):self.spool.db.execute('DELETE FROM receipts')
        self.spool.close();self.spool=Spool(self.root/'spool');self.assertEqual(self.spool.tip,tip)
    def test_query_limits_and_invalid_clock_schema(self):
        with self.assertRaises(PublicFailure):self.client.closed_hours(ACT,ACT+1501*HOUR-1)
        self.answers[:]=[Response(b'{"serverTime":true}')]
        with self.assertRaises(PublicFailure):self.client.server_time()
    def test_oversized_body_is_explicitly_partial_and_never_accepted(self):
        self.answers[:]=[Response(b'x'*2000010)]
        with self.assertRaisesRegex(PublicFailure,'BODY_TOO_LARGE'):self.client.server_time()
        meta,raw=self.spool.db.execute('SELECT metadata,body FROM receipts WHERE id=1').fetchone()
        self.assertTrue(json.loads(meta)['body_truncated']);self.assertEqual(len(raw),2000001)

class QualificationTests(unittest.TestCase):
    def samples(self,origin='OFFLINE_FIXTURE'):
        raw=raw_rows(bars(1))[0]
        return [dict(origin=origin,close_ms=ACT+d*24*HOUR,received_ms=ACT+d*24*HOUR+s*1000,
                     offset_seconds=s,raw_candle=raw,valid=True) for d in range(48) for s in OFFSETS]
    def test_synthetic_samples_never_qualify_real_delay(self):
        result=revision_report(self.samples());self.assertEqual(result['qualification'],'NOT_QUALIFIED');self.assertFalse(result['real_network_measurements'])
    def test_missing_or_late_revision_cannot_auto_shift_delay(self):
        rows=self.samples('LIVE_PUBLIC_HTTPS');rows[-1]=copy.deepcopy(rows[-1]);rows[-1]['raw_candle'][4]='12345'
        r=revision_report(rows);self.assertEqual(r['proposed_wait_ms'],60000);self.assertEqual(r['qualification'],'NOT_QUALIFIED')
        self.assertTrue(r['late_numeric_revisions'])
        self.assertFalse(revision_report(rows[:6])['continuous_capture_authorized'])
    def test_schedule_boundary_is_close_not_open(self):
        self.assertEqual(schedule(ACT+59000)['status'],'WAIT_PUBLICATION')
        self.assertEqual(schedule(ACT+60000)['status'],'WITHIN_TIMELY_WINDOW')
        self.assertEqual(schedule(ACT+300001)['status'],'LATE_NOT_PRIMARY')
        self.assertFalse(schedule(ACT+60000)['qualified_for_continuous_capture'])
    def test_unknown_publication_at_zero_can_be_measured(self):
        rows=self.samples('LIVE_PUBLIC_HTTPS')
        for row in rows:
            if row['offset_seconds']==0:row['valid']=False;row.pop('raw_candle')
        r=revision_report(rows);self.assertEqual(r['qualification'],'OBSERVED_WINDOW_STABLE_REQUIRES_AUDIT')
        self.assertFalse(r['continuous_capture_authorized'])
    def test_no_runtime_dependency_or_old_source_changes(self):
        here=Path(__file__).resolve().parent;root=here.parents[7];prefix=here.relative_to(root).as_posix()+'/'
        changes=subprocess.check_output(['git','diff','9f307fd9feda6279253c0a0813d49b47d3f1d9b2','--name-status'],cwd=root,text=True).splitlines()
        for line in changes:
            status,name=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(name.startswith(prefix))
        for path in here.glob('*.py'):
            if path.name.startswith('test_'):continue
            text=path.read_text()
            for forbidden in ('guardian_bitunix','trade_guardian','readiness','gates_ready','TURN22','TURN11','bitman_weekly_forward'):
                self.assertNotIn(forbidden,text)

if __name__=='__main__':unittest.main()
