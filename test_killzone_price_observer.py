"""Offline fixtures only: no actual prospective observations or external services."""
import ast
from contextlib import contextmanager
import csv
from datetime import date,datetime,timezone
import hashlib
import gzip
import io
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error

try:
    import numpy as np
except ModuleNotFoundError as exc:
    if exc.name!='numpy':raise
    raise unittest.SkipTest('Dedicated PRICE observer CI requires NumPy; dependency-free V8 stays isolated') from None
try:
    from igod_killzone_price_observer.features import HOUR,MINUTE,NY,schedule,atr_series,vector,final_label
except Exception as exc:
    from zoneinfo import ZoneInfoNotFoundError
    if isinstance(exc,ZoneInfoNotFoundError):raise unittest.SkipTest('Dedicated CI installs tzdata') from None
    raise
from igod_killzone_price_observer import frozen,features,geometry
from igod_killzone_price_observer.journal import Store,EvidenceError,canonical
from igod_killzone_price_observer.market import PublicSpot,NoRedirect,decode_klines
from igod_killzone_price_observer.observer import Observer,anchor_id,valid_schedule
from igod_killzone_price_observer.reports import derive
from igod_killzone_price_observer.service import Application,Config,handler_for
from igod_killzone_price_observer.compare import compare_export,save_comparison

ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'igod_killzone_price_observer'
DAY=date(2026,11,5)
SHA='1'*40


class FakeClock:
    def __init__(self,now):self.value=now;self.mono=1000
    def now_ms(self):return self.value
    def monotonic_ms(self):return self.mono
    def advance(self,ms):self.value+=ms;self.mono+=ms
    def set(self,t):self.advance(t-self.value)


def raw_row(t,o,h,l,c,step):
    return [t,str(o),str(h),str(l),str(c),'1.0',t+step-1,'100',2,'0.5','50','0']


class FixtureFeed:
    """Generated prices are UNIT TEST DATA, never market/parity/forward evidence."""
    def __init__(self,clock,day=DAY):
        self.clock=clock;self.day=day;self.s=schedule(day);self.calls=[]
        self.fail=False;self.gap=False;self.revise=False;self.both=False;self.slow=0;self.server_delta=0

    def price(self,hour):
        if hour<self.s['radar']:
            return 100+(hour//HOUR)%5
        if self.s['close']+HOUR<=hour<self.s['close']+2*HOUR:return 120.
        return 102.

    def response(self,url,timeout):
        from urllib.parse import urlparse,parse_qs
        path=urlparse(url.full_url).path;q={k:v[0] for k,v in parse_qs(urlparse(url.full_url).query).items()}
        self.calls.append((path,q))
        if self.fail:raise TimeoutError('not to be logged: api_key=PRIVATE_TEST_SECRET')
        if self.slow:self.clock.advance(self.slow)
        if path=='/api/v3/time':return Response(json.dumps({'serverTime':self.clock.now_ms()+self.server_delta}).encode())
        step=HOUR if q['interval']=='1h' else MINUTE
        start,end=int(q['startTime']),int(q['endTime'])+1
        rows=[]
        for t in range(start,end,step):
            p=self.price(t//HOUR*HOUR)
            if self.revise and t==self.s['asia']:p+=.1
            low,high=p-1,p+1
            if self.both and t==self.s['close']:low,high=1,1000
            rows.append(raw_row(t,p,high,low,p,step))
        if self.gap and len(rows)>1:rows.pop(1)
        return Response(json.dumps(rows,separators=(',',':')).encode())


class Response:
    def __init__(self,body,status=200):self.body=body;self.status=status;self.headers={'Content-Type':'application/json'}
    def read(self,n):return self.body[:n]
    def __enter__(self):return self
    def __exit__(self,*args):return False


class Opener:
    def __init__(self,feed):self.feed=feed
    def open(self,request,timeout):return self.feed.response(request,timeout)


@contextmanager
def rig(day=DAY):
    with tempfile.TemporaryDirectory() as tmp:
        s=schedule(day);clock=FakeClock(s['radar']-MINUTE)
        store=Store(Path(tmp)/'evidence',clock)
        feed=FixtureFeed(clock,day);market=PublicSpot(store,clock,Opener(feed))
        observer=Observer(store,market,clock,SHA)
        try:yield store,feed,clock,observer
        finally:store.close()


def capture_all(observer,clock,day=DAY):
    s=schedule(day)
    for m in (0,15,30,45,59):clock.set(s['radar']+m*MINUTE+2000);observer.tick()


class FrozenModelTests(unittest.TestCase):
    def test_exact_model_hash_and_no_training_function(self):
        self.assertEqual(frozen.verify_freeze()['model_sha256'],'db59d952e6c79da87adb7a31cba41a6ee3a5879a8e0c57638336e58f7be6a6d9')
        self.assertFalse(hasattr(frozen,'fit_structure'))

    def test_frozen_function_sources_equal_reviewed_pr43(self):
        m=json.loads((PACKAGE/'manifest.json').read_text())
        found={}
        for module in (frozen,features):
            text=Path(module.__file__).read_text(encoding='utf-8');tree=ast.parse(text)
            for n in tree.body:
                if isinstance(n,ast.FunctionDef) and n.name in m['reference_function_source_sha256']:
                    found[n.name]=hashlib.sha256(ast.get_source_segment(text,n).encode()).hexdigest()
        self.assertEqual(found,m['reference_function_source_sha256'])

    def test_reused_actual_pine_inference_12_not_market_validation(self):
        gold=json.loads((ROOT/'tests/fixtures/price_observer/reused_actual_pine_inference.json').read_text())
        self.assertIn('NOT_MARKET_OR_TIMESTAMP_CERTIFICATION',gold['origin'])
        self.assertEqual(len(gold['records']),12)
        for r in gold['records']:np.testing.assert_allclose(frozen.predict(r['features']),r['probabilities'],rtol=0,atol=1e-10)

    def test_softmax_sum_and_bad_features(self):
        self.assertAlmostEqual(float(frozen.predict([0,.5,0,1,0,2]).sum()),1.)
        for x in ([1,2],[0,np.nan,1,1,1,1]):
            with self.assertRaises(ValueError):frozen.predict(x)

    def test_dst_and_spring_missing_hour(self):
        self.assertEqual(datetime.fromtimestamp(schedule(date(2027,3,13))['radar']/1000,timezone.utc).hour,10)
        self.assertEqual(datetime.fromtimestamp(schedule(date(2027,3,15))['radar']/1000,timezone.utc).hour,9)
        with self.assertRaises(EvidenceError):valid_schedule(date(2027,3,14))

    def test_original_pine_projection(self):
        p=geometry.project(77897.03,77517.2,78285.,77850.)
        self.assertAlmostEqual(p['newTopTarget'],78653.4351)
        self.assertAlmostEqual(p['newBottomTarget'],77095.25)

    def test_1000h_warmup_matches_full_audited_history_strict_tolerance(self):
        folder=ROOT/'tests/fixtures/price_observer'
        raw=(folder/'atr_public_history.csv.gz').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),json.loads((folder/'atr_provenance.json').read_text())['sha256'])
        h=np.loadtxt(io.StringIO(gzip.decompress(raw).decode()),delimiter=',',skiprows=1)
        full=atr_series(h)
        for end in range(1000,len(h)+1,500):
            self.assertAlmostEqual(float(atr_series(h[end-1000:end])[-1]),float(full[end-1]),delta=1e-10)


class JournalTests(unittest.TestCase):
    def test_first_start_and_reboot_preserve_chain(self):
        with rig() as (s,f,c,o):
            initial=s.path.read_bytes();p=s.root;s.close()
            again=Store(p,c);Observer(again,PublicSpot(again,c,Opener(f)),c,SHA)
            try:
                self.assertTrue(again.path.read_bytes().startswith(initial))
                self.assertEqual(sum(r['record_type']=='ACTIVATION' for r in again.rows),1)
                self.assertEqual(again.rows[-1]['record_type'],'RECOVERY')
            finally:again.close()

    def test_raw_preserved_byte_identically_and_deduped(self):
        with rig() as (s,*_):
            raw=b'{"n": 1, "whitespace": true}\n'
            a=s.archive(raw);self.assertEqual(s.read_raw(a),raw);self.assertEqual(s.archive(raw),a)
            self.assertEqual(len(list((s.root/'raw').iterdir())),1)

    def test_single_writer(self):
        with rig() as (s,f,c,o):
            with self.assertRaisesRegex(EvidenceError,'LOCKED'):Store(s.root,c)

    def test_deterministic_record_id_and_conflict(self):
        with rig() as (s,*_):
            s.append('MISSED','ONE',{'reason':'TEST'})
            before=s.path.read_bytes();s.append('MISSED','ONE',{'reason':'TEST'})
            self.assertEqual(before,s.path.read_bytes())
            with self.assertRaises(EvidenceError):s.append('MISSED','ONE',{'reason':'OTHER'})

    def test_truncation_modification_prevhash_duplicate_reorder_fail_no_repair(self):
        transforms=[lambda a:a[:-1],lambda a:a.replace(b'ACTIVATION',b'ACTIVATIOM',1),
                    lambda a:a+a.splitlines()[0]+b'\n',
                    lambda a:b'\n'.join(reversed(a.splitlines()))+b'\n']
        for transform in transforms:
            with self.subTest(transform=transforms.index(transform)),rig() as (s,f,c,o):
                s.append('MISSED','TWO',{'reason':'TEST'});p=s.root;s.close()
                damaged=transform(s.path.read_bytes());s.path.write_bytes(damaged)
                with self.assertRaises(EvidenceError):Store(p,c)
                self.assertEqual(s.path.read_bytes(),damaged)

    def test_raw_tampering_detected_on_replay(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);ref=next(r for r in s.rows if r['record_type']=='CONTEXT')['data']['source']['raw_sha256']
            p=s.root;s.close();(p/'raw'/(ref+'.json')).write_bytes(b'[]')
            with self.assertRaises(EvidenceError):Store(p,c)

    def test_fsync_failure_poison_never_continues_appending(self):
        with rig() as (s,*_):
            with patch('igod_killzone_price_observer.journal.os.fsync',side_effect=OSError('SECRET')):
                with self.assertRaises(EvidenceError):s.append('MISSED','TEST',{'reason':'TEST'})
            self.assertTrue(s.poisoned)
            with self.assertRaises(EvidenceError):s.append('MISSED','OTHER',{'reason':'TEST'})

    def test_clock_backwards_refuses_write(self):
        with rig() as (s,f,c,o):
            before=s.path.read_bytes();c.advance(-1000)
            with self.assertRaises(EvidenceError):s.append('MISSED','BACKWARD',{})
            self.assertEqual(s.path.read_bytes(),before)

    def test_readonly_inspection_creates_no_files_and_is_equal_to_replay(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);before={p.relative_to(s.root):p.read_bytes() for p in s.root.rglob('*') if p.is_file() and p.name!='.writer.lock'}
            self.assertEqual(Store.inspect(s.root),s.rows)
            after={p.relative_to(s.root):p.read_bytes() for p in s.root.rglob('*') if p.is_file() and p.name!='.writer.lock'}
            self.assertEqual(before,after)

    def test_frozen_inference_checked_even_if_modified_chain_is_rehashed(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);p=s.root;s.close()
            rows=[json.loads(line) for line in s.path.read_bytes().splitlines()]
            pred=next(r for r in rows if r['record_type']=='PREDICTION')
            pred['data']['probabilities']=[1.,0.,0.]
            tip='0'*64
            for r in rows:
                r.pop('record_hash');r['prev_hash']=tip;r['record_hash']=hashlib.sha256(canonical(r)).hexdigest();tip=r['record_hash']
            damaged=b'\n'.join(canonical(r) for r in rows)+b'\n';s.path.write_bytes(damaged)
            with self.assertRaises(EvidenceError):Store(p,c)
            self.assertEqual(s.path.read_bytes(),damaged)


class MarketTests(unittest.TestCase):
    def test_only_two_public_get_paths_and_no_arbitrary_host(self):
        with rig() as (s,f,c,o):
            for path in ('https://evil.example/api','/api/v3/order','/fapi/v1/klines','/api/v3/account'):
                with self.assertRaises(EvidenceError):o.market.get(path,{})
            self.assertEqual(f.calls,[])

    def test_other_symbol_unknown_param_and_open_range_rejected(self):
        with rig() as (s,f,c,o):
            for params in (dict(symbol='ETHUSDT',interval='1m',startTime=0,endTime=1,limit=1),
                           dict(symbol='BTCUSDT',interval='1m',startTime=0,endTime=1,limit=1,url='bad')):
                with self.assertRaises(EvidenceError):o.market.get('/api/v3/klines',params)
            with self.assertRaises(EvidenceError):o.market.klines(c.now_ms(),c.now_ms()+MINUTE,'1m')

    def test_exact_closed_schema_gaps_duplicates_nan_volume(self):
        good=[raw_row(0,100,101,99,100,MINUTE),raw_row(MINUTE,100,101,99,100,MINUTE)]
        self.assertEqual(decode_klines(good,0,2*MINUTE,MINUTE).shape,(2,5))
        mutations=[good[:1],[good[0],good[0]],[good[0]+[0],good[1]]]
        from copy import deepcopy
        for field,value in ((6,0),(4,'NaN'),(5,'-1'),(9,'2')):
            bad=deepcopy(good);bad[0][field]=value;mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(EvidenceError):decode_klines(bad,0,2*MINUTE,MINUTE)

    def test_redirect_blocked_and_upstream_status_not_fallback(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))
        with rig() as (s,f,c,o):
            class Bad:
                def open(self,*a,**k):return Response(b'{"code":-1}',451)
            client=PublicSpot(s,c,Bad())
            with self.assertRaisesRegex(EvidenceError,'PUBLIC_HTTP_451'):client.clock_check()
            self.assertEqual(len(f.calls),0)

    def test_proxy_environment_ignored(self):
        with rig() as (s,f,c,o),patch.dict('os.environ',{'HTTPS_PROXY':'http://SECRET_PROXY:9999'}):
            client=PublicSpot(s,c)
            handlers=[h for h in client.opener.handlers if isinstance(h,__import__('urllib.request',fromlist=['ProxyHandler']).ProxyHandler)]
            self.assertTrue(not handlers or all(not h.proxies for h in handlers))

    def test_clock_skew_and_network_latency_fail_closed(self):
        with rig() as (s,f,c,o):
            f.server_delta=5000
            with self.assertRaisesRegex(EvidenceError,'CLOCK_UNVERIFIED'):o.market.clock_check()
            f.server_delta=0;f.slow=6000
            with self.assertRaisesRegex(EvidenceError,'CLOCK_UNVERIFIED'):o.market.clock_check()


class CaptureTests(unittest.TestCase):
    def test_five_anchors_real_receipt_source_hashes_and_no_06_forecast(self):
        with rig() as (s,f,c,o):
            capture_all(o,c)
            ps=[r for r in s.rows if r['record_type']=='PREDICTION']
            self.assertEqual([r['data']['minute'] for r in ps],[0,15,30,45,59])
            self.assertEqual(sum(r['record_type']=='DURABILITY' for r in s.rows),5)
            for r in ps:
                d=r['data'];self.assertGreaterEqual(r['created_at'],d['available_at'])
                self.assertEqual(r['origin'],'PYTHON_BINANCE_SPOT_LIVE')
                self.assertEqual(len(d['probabilities']),3)
                self.assertLess(d['emitted_at'],schedule(DAY)['close'])
                for source in d['sources']:self.assertLess(source['params']['endTime'],d['available_at'])
            c.set(schedule(DAY)['close']+2000);o.tick()
            self.assertEqual(sum(r['record_type']=='PREDICTION' for r in s.rows),5)

    def test_no_network_before_next_anchor(self):
        with rig() as (s,f,c,o):
            o.tick();self.assertEqual(f.calls,[])
            c.set(schedule(DAY)['radar']+2000);o.tick();n=len(f.calls)
            c.advance(5000);o.tick();self.assertEqual(len(f.calls),n)

    def test_restart_never_duplicates_predictions(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);p=s.root;s.close()
            again=Store(p,c)
            try:
                reboot=Observer(again,PublicSpot(again,c,Opener(f)),c,SHA);n=len(f.calls);reboot.tick()
                self.assertEqual(sum(r['record_type']=='PREDICTION' for r in again.rows),5)
                self.assertEqual(len(f.calls),n)
            finally:again.close()

    def test_missed_anchor_no_retrospective_prediction(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['radar']+5*MINUTE);o.tick()
            self.assertIn('MISSED:'+anchor_id(DAY,0),s.by_id)
            self.assertNotIn('PREDICTION:'+anchor_id(DAY,0),s.by_id)

    def test_activation_after_anchor_does_not_reconstruct_it(self):
        with tempfile.TemporaryDirectory() as t:
            c=FakeClock(schedule(DAY)['radar']+3000);s=Store(Path(t),c);f=FixtureFeed(c)
            try:
                o=Observer(s,PublicSpot(s,c,Opener(f)),c,SHA);o.tick()
                self.assertEqual(s.by_id['MISSED:'+anchor_id(DAY,0)]['data']['reason'],'NOT_ACTIVE_AT_ANCHOR')
            finally:s.close()

    def test_public_failure_max_attempts_and_no_secret_exception(self):
        with rig() as (s,f,c,o):
            f.fail=True
            for i in range(4):c.set(schedule(DAY)['radar']+2000+i*11000);o.tick()
            self.assertEqual(sum(r['record_type']=='ATTEMPT' for r in s.rows),3)
            self.assertNotIn('PRIVATE_TEST_SECRET',s.path.read_text())
            self.assertNotIn('PREDICTION:'+anchor_id(DAY,0),s.by_id)

    def test_gap_never_generates_probability_record(self):
        with rig() as (s,f,c,o):
            f.gap=True;c.set(schedule(DAY)['radar']+2000);o.tick()
            self.assertFalse(any(r['record_type']=='PREDICTION' for r in s.rows))
            self.assertEqual(s.rows[-1]['record_type'],'FAILURE')

    def test_capture_finishing_after_deadline_not_eligible(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['radar']+119000)
            original=o._context
            def late(*args):
                result=original(*args);c.advance(5000);return result
            with patch.object(o,'_context',side_effect=late):o.tick()
            self.assertFalse(any(r['record_type']=='DURABILITY' for r in s.rows))

    def test_no_durability_witness_after_crash_is_not_invented(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['radar']+2000)
            original=s.append
            def fail_witness(kind,*args):
                if kind=='DURABILITY':raise RuntimeError('simulated crash boundary')
                return original(kind,*args)
            with patch.object(s,'append',side_effect=fail_witness):o.tick()
            self.assertIn('PREDICTION:'+anchor_id(DAY,0),s.by_id)
            o.tick()
            self.assertNotIn('DURABILITY:'+anchor_id(DAY,0),s.by_id)
            self.assertIn('MISSED:'+anchor_id(DAY,0),s.by_id)

    def test_server_clock_not_yet_at_anchor_never_reads_future_prefix(self):
        with rig() as (s,f,c,o):
            f.server_delta=-1900;c.set(schedule(DAY)['radar']+1000)
            o.capture(DAY,0,schedule(DAY))
            self.assertFalse(any(path.endswith('klines') for path,q in f.calls))

    def test_server_upper_bound_rejects_capture_crossing06_even_if_host_lags(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['radar']+59*MINUTE+57000)
            f.server_delta=1900
            original=o._context
            def slow(*args):
                result=original(*args);c.advance(2000);return result
            with patch.object(o,'_context',side_effect=slow):o.capture(DAY,59,schedule(DAY))
            self.assertNotIn('DURABILITY:'+anchor_id(DAY,59),s.by_id)

    def test_journal_replay_reconstructs_same_existing_forecasts(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);before=[r for r in s.rows if r['record_type']=='PREDICTION'];p=s.root;s.close()
            reopened=Store(p,c)
            try:self.assertEqual(before,[r for r in reopened.rows if r['record_type']=='PREDICTION'])
            finally:reopened.close()


class OutcomeTests(unittest.TestCase):
    def test_no_early_outcome_and_eventual_target_label_with_independent_inputs(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);c.set(schedule(DAY)['end']-1);o.tick()
            self.assertNotIn('OUTCOME:'+DAY.isoformat(),s.by_id)
            c.set(schedule(DAY)['end']+2000);o.tick()
            record=s.by_id['OUTCOME:'+DAY.isoformat()]
            self.assertEqual(record['data']['outcome']['class_index'],0)
            self.assertTrue(record['data']['quality_pass'])
            report=derive(s.rows,c.now_ms())
            self.assertEqual(report['complete_cycles'],1);self.assertIsNotNone(report['metrics'])
            self.assertFalse(report['probabilities_validated'])

    def test_label_backfill_allowed_predictions_not_backfilled(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);count=sum(r['record_type']=='PREDICTION' for r in s.rows)
            c.set(schedule(DAY)['end']+2*HOUR);o.tick();o.tick()
            self.assertEqual(sum(r['record_type']=='OUTCOME' for r in s.rows),1)
            self.assertEqual(sum(r['record_type']=='PREDICTION' for r in s.rows),count)

    def test_both_targets_same_minute_is_ambiguous_not_a_win(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);f.both=True;c.set(schedule(DAY)['end']+2000);o.tick()
            self.assertEqual(s.by_id['OUTCOME:'+DAY.isoformat()]['data']['outcome']['class_index'],-1)
            self.assertEqual(derive(s.rows,c.now_ms())['complete_cycles'],0)

    def test_market_revision_preserves_original_forecast_and_marks_quality(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);old=[r['record_hash'] for r in s.rows if r['record_type']=='PREDICTION']
            f.revise=True;c.set(schedule(DAY)['end']+2000);o.tick()
            self.assertFalse(s.by_id['OUTCOME:'+DAY.isoformat()]['data']['quality_pass'])
            self.assertEqual(old,[r['record_hash'] for r in s.rows if r['record_type']=='PREDICTION'])
            self.assertEqual(derive(s.rows,c.now_ms())['complete_cycles'],0)

    def test_no_forecasts_no_historical_outcomes_download(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['end']+2000);o.tick()
            self.assertFalse(any(path.endswith('klines') for path,q in f.calls))
            self.assertFalse(any(r['record_type']=='OUTCOME' for r in s.rows))

    def test_incomplete_cycle_is_kept_in_coverage_denominator(self):
        with rig() as (s,f,c,o):
            c.set(schedule(DAY)['end']+2000);o.tick();r=derive(s.rows,c.now_ms())
            self.assertEqual(r['planned_cycles'],181);self.assertEqual(r['matured_calendar_cycles'],1)
            self.assertEqual(r['coverage_matured'],0.)

    def test_future_append_cannot_change_past_predictions_and_no_early_validation(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);before={r['record_id']:r for r in s.rows if r['record_type']=='PREDICTION'}
            c.set(schedule(DAY)['end']+2000);o.tick();r=derive(s.rows,c.now_ms())
            self.assertEqual(before,{r['record_id']:r for r in s.rows if r['record_type']=='PREDICTION'})
            self.assertEqual(r['status'],'COHORT_NOT_FINISHED_NO_EARLY_APPROVAL')
            self.assertIsNone(r['comparisons']['PRIOR']['brier_gain_ci97_5'])
            self.assertEqual(len(r['metrics']['by_class']),3)

    def test_missing_one_anchor_excludes_cycle_despite_outcome(self):
        with rig() as (s,f,c,o):
            ss=schedule(DAY)
            for minute in (0,15,45,59):c.set(ss['radar']+minute*MINUTE+2000);o.tick()
            c.set(ss['end']+2000);o.tick();r=derive(s.rows,c.now_ms())
            self.assertEqual(r['complete_cycles'],0)
            self.assertIn('MISSING_ANCHORS',r['excluded'][0]['reasons'])

    def test_neither_is_a_real_third_outcome_not_missing_data(self):
        with rig() as (s,f,c,o):
            original=f.price
            f.price=lambda t:original(t) if t<f.s['radar'] else 102.
            capture_all(o,c);c.set(f.s['end']+2000);o.tick()
            self.assertEqual(s.by_id['OUTCOME:'+DAY.isoformat()]['data']['outcome']['class_index'],2)

    def test_failed_outcome_can_recover_without_reissuing_forecasts(self):
        with rig() as (s,f,c,o):
            capture_all(o,c);f.fail=True;c.set(f.s['end']+2000);o.tick()
            self.assertNotIn('OUTCOME:'+DAY.isoformat(),s.by_id)
            f.fail=False;c.advance(60001);o.tick()
            self.assertIn('OUTCOME:'+DAY.isoformat(),s.by_id)
            self.assertEqual(sum(r['record_type']=='PREDICTION' for r in s.rows),5)


class ServiceSafety(unittest.TestCase):
    def test_disabled_no_network_writes_or_logger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'MUST_NOT_EXIST'
            with patch('igod_killzone_price_observer.service.Store',side_effect=AssertionError('NO STORE')):
                app=Application(Config(data_dir=path),sink=lambda v:self.fail('NO LOG'))
                app.tick();app.close()
            self.assertFalse(path.exists());self.assertEqual(app.status,'DISABLED')

    def test_config_reads_only_allowlisted_nonsecret_values(self):
        class Environ:
            def get(self,name,default=None):
                if name not in ('PRICE_OBSERVER_ENABLED','RAILWAY_GIT_COMMIT_SHA','PRICE_OBSERVER_SOURCE_SHA','PORT'):
                    raise AssertionError('SECRET READ')
                return default
        self.assertFalse(Config.from_env(Environ()).enabled)

    def test_enabled_requires_source_sha_and_independent_mount(self):
        with self.assertRaises(EvidenceError):Config.from_env({'PRICE_OBSERVER_ENABLED':'true'})
        with tempfile.TemporaryDirectory() as tmp:
            app=Application(Config(True,Path(tmp)/'x',SHA),mount_check=lambda p:False)
            self.assertEqual(app.status,'DEGRADED');self.assertIsNone(app.store)
            self.assertIsNone(app.public_status()['journal_records'])
            self.assertEqual(app.public_status()['evidence'],'UNAVAILABLE')

    def test_logger_failure_does_not_stop_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClock(schedule(DAY)['radar']-MINUTE);feed=FixtureFeed(c)
            app=Application(Config(True,Path(tmp),SHA),clock=c,mount_check=lambda p:True,
                market_factory=lambda s,c:PublicSpot(s,c,Opener(feed)),sink=lambda v:(_ for _ in ()).throw(RuntimeError('secret')))
            try:
                c.set(schedule(DAY)['radar']+2000);app.tick()
                self.assertEqual(sum(r['record_type']=='DURABILITY' for r in app.store.rows),1)
            finally:app.close()

    def test_unknown_exception_text_or_uppercase_secret_is_never_a_status_code(self):
        for error in (RuntimeError('api_key=PRIVATE'),EvidenceError('SECRETTOKENABC')):
            self.assertEqual(Application.safe_code(error),'INTERNAL_ERROR')
        self.assertEqual(Application.safe_code(EvidenceError('PUBLIC_HTTP_451')),'PUBLIC_HTTP_451')

    def test_no_production_sources_modified_and_no_runtime_research_imports(self):
        m=json.loads((PACKAGE/'manifest.json').read_text())
        for name,sha in m['protected_git_sha256'].items():
            raw=(ROOT/name).read_bytes()
            self.assertIn(sha,(hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()),name)
        for path in PACKAGE.glob('*.py'):
            tree=ast.parse(path.read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.ImportFrom):self.assertFalse((n.module or '').startswith('research'))
                if isinstance(n,ast.Import):self.assertFalse(any(a.name.startswith('research') for a in n.names))

    def test_no_execution_clients_or_trading_methods(self):
        forbidden={'guardian_bitunix','trade_guardian','guardian_risk','v8_executor','ccxt','telegram','subprocess'}
        for path in PACKAGE.glob('*.py'):
            tree=ast.parse(path.read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.ImportFrom):self.assertNotIn((n.module or '').split('.')[0],forbidden)
                if isinstance(n,ast.Import):self.assertFalse({a.name.split('.')[0] for a in n.names}&forbidden)
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                    self.assertNotIn(n.func.attr,{'place_order','cancel_order','create_order','market_order','set_leverage','send_message'})

    def test_http_health_status_report_are_read_only_and_post_is_rejected(self):
        from http.server import ThreadingHTTPServer
        app=Application(Config())
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(app))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
        try:
            for path in ('/health','/status','/report'):
                connection.request('GET',path);response=connection.getresponse();data=json.loads(response.read())
                self.assertEqual(response.status,200);self.assertEqual(data['trade_authority'],'NONE')
            connection.request('POST','/report',body='{}');response=connection.getresponse();response.read()
            self.assertEqual(response.status,405)
            connection.request('GET','/api/v3/order');response=connection.getresponse();response.read()
            self.assertEqual(response.status,404)
            self.assertIsNone(app.store)
        finally:connection.close();server.shutdown();thread.join(timeout=3);server.server_close();app.close()


class FinalReportGates(unittest.TestCase):
    """Contrived in-memory cohorts test gates only; never evidence or journal output."""
    def cohort(self,n):
        from igod_killzone_price_observer.observer import days
        from igod_killzone_price_observer.frozen import structure_predict,read_json
        rows=[]
        def record(kind,rid,data):
            return dict(record_type=kind,record_id=rid,data=data,origin='PYTHON_BINANCE_SPOT_LIVE',
                        protocol_version='IGOD_PRICE_BINANCE_FORWARD_V1')
        count=0
        for day in days('2026-11-05','2027-05-04'):
            try:s=valid_schedule(day)
            except EvidenceError:continue
            if count==n:break
            label=count%3
            for minute in (0,15,30,45,59):
                x=[minute/60,.5,0,1,0,2];at=s['radar']+minute*MINUTE;pid='PREDICTION:'+anchor_id(day,minute)
                rows.append(record('PREDICTION',pid,dict(cycle=day.isoformat(),minute=minute,available_at=at,
                    probabilities=predict_for_test(x),prior=read_json('frozen_PRIOR.json'),
                    structure=structure_predict(x,read_json('frozen_STRUCTURE.json')).tolist())))
                rows.append(record('DURABILITY','DURABILITY:'+anchor_id(day,minute),
                    dict(prediction_id=pid,prediction_durable_at=at+3000,server_utc_upper_at_fsync=at+4000,eligible=True)))
            rows.append(record('OUTCOME','OUTCOME:'+day.isoformat(),dict(cycle=day.isoformat(),
                outcome={'class_index':label},quality_pass=True)))
            count+=1
        return rows

    def test_even_sufficient_sample_cannot_pass_before_frozen_end(self):
        rows=self.cohort(172)
        r=derive(rows,schedule(date(2027,5,4))['end']-1)
        self.assertEqual(r['status'],'COHORT_NOT_FINISHED_NO_EARLY_APPROVAL')
        self.assertFalse(r['probabilities_validated'])

    def test_final_gates_have_block_intervals_but_never_self_certify_pine(self):
        rows=self.cohort(172);r=derive(rows,schedule(date(2027,5,4))['end']+2000)
        self.assertEqual(r['complete_cycles'],172)
        self.assertIn(r['status'],('FIXED_COHORT_FAILED','STATISTICAL_PASS_INDEPENDENT_REVIEW_REQUIRED'))
        self.assertIsNotNone(r['comparisons']['PRIOR']['brier_gain_ci97_5'])
        self.assertFalse(r['probabilities_validated'])
        self.assertEqual(r['tradingview_validation'],'NOT_ESTABLISHED_BY_THIS_BINANCE_COHORT')

    def test_171_cycles_fails_fixed95pct_coverage_even_above150(self):
        r=derive(self.cohort(171),schedule(date(2027,5,4))['end']+2000)
        self.assertEqual(r['status'],'INSUFFICIENT_SAMPLE_OR_COVERAGE')

    def test_tradingview_records_cannot_enter_binance_metrics(self):
        with self.assertRaisesRegex(EvidenceError,'MIXED_COHORT'):
            derive([dict(record_type='PREDICTION',origin='PINE_REALTIME_UNATTESTED',data={})],0)


def predict_for_test(x):
    return frozen.predict(x).tolist()


class TradingViewComparisonTests(unittest.TestCase):
    def export(self):
        gold=json.loads((ROOT/'tests/fixtures/price_observer/reused_actual_pine_inference.json').read_text())
        f=frozen.verify_freeze();stream=io.StringIO();w=csv.DictWriter(stream,['Fecha','Mensaje']);w.writeheader()
        for r in gold['records']:
            t=r['available_at'];minute=datetime.fromtimestamp(t/1000,NY).minute
            p=dict(protocol='IGOD_KILLZONE_PRICE_FORWARD_V1',protocol_hash=f['original_tv_protocol_sha256'],
                version=f['model_version'],available_at=t,emitted_at=t+500,minute=minute,
                status='EXPERIMENTAL_NOT_VALIDATED',origin='PINE_REALTIME_UNATTESTED',
                features=r['features'],research_probabilities=r['probabilities'])
            w.writerow(dict(Fecha=datetime.fromtimestamp((t-10000)/1000,timezone.utc).isoformat(),Mensaje='IGOD_PRICE_RADAR_V1='+json.dumps(p)))
        return stream.getvalue().encode()

    def test_real_inference_fixture_but_synthetic_wrapper_never_enters_binance_cohort(self):
        result=compare_export(self.export(),[])
        self.assertEqual(result['conditional_inference_passes'],12)
        self.assertEqual(result['status'],'INSUFFICIENT_OVERLAP')
        self.assertEqual(result['timestamp_anomalies'],12)
        self.assertFalse(result['tradingview_cohort_imported']);self.assertFalse(result['platform_parity_certified'])

    def test_original_export_retained_byte_for_byte_without_mutating_cohort(self):
        with rig() as (s,f,c,o):
            before=s.path.read_bytes();raw=self.export()
            result=save_comparison(raw,s.rows,s.root/'comparisons',c)
            self.assertEqual((s.root/'comparisons'/(result['original_sha256']+'.csv')).read_bytes(),raw)
            self.assertEqual(s.path.read_bytes(),before)


if __name__=='__main__':unittest.main()
