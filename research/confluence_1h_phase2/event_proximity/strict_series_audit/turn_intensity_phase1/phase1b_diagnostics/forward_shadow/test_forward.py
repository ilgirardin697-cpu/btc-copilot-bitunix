"""Offline synthetic safety evidence; never prospective or platform parity data."""
import ast,copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Research tests require NumPy') from error
from ... import detect as old
from ...evaluate import clean
from ...test_turns import fixture
from . import protocol
from .models import Engine,feature_sets,turns,PROFILES
from .journal import Journal,JournalError,canonical,digest
from .market import Receipt,klines,funding,candle_key,HOUR
from .observer import Observer
from .observations import Facts,mtf
from .report import summarize,read_records

ROOT=protocol.ROOT.parents[6]
PREFIX=str(protocol.ROOT.relative_to(ROOT)).replace('\\','/')+'/'
BASE='3fcfc793f1db1c37dd9a3e905c9e7e1368f0c544'
ACT=1794873600000  # 2026-11-17 00:00 UTC, synthetic clock only


def bars(n=6030):
    rng=np.random.default_rng(804)
    c=70000*np.exp(np.cumsum(rng.normal(0,.002,n)));o=np.r_[c[0],c[:-1]]
    return np.c_[ACT-6000*HOUR+np.arange(n)*HOUR,o,np.maximum(o,c)+25,np.minimum(o,c)-25,c,rng.uniform(10,20,n)]


def raw_rows(a):
    return [[int(t),str(o),str(h),str(l),str(c),str(v),int(t+HOUR-1),'123',30,str(v/2),'60','0'] for t,o,h,l,c,v in a]


def receipt(a,received=None,raw=None,status=200):
    received=received or int(a[-1,0]+HOUR+1000)
    return Receipt(json.dumps(raw if raw is not None else raw_rows(a),separators=(',',':')).encode(),
                   'https://fapi.binance.com/fapi/v1/klines',
                   dict(symbol='BTCUSDT',interval='1h',startTime=int(a[0,0]),endTime=int(a[-1,0]+HOUR-1),limit=min(1500,len(a))),
                   received-100,received,received,status)


def funding_receipt(start,end,rows=None,received=None):
    received=received or end+1000
    return Receipt(json.dumps(rows or []).encode(),'https://fapi.binance.com/fapi/v1/fundingRate',
                   dict(symbol='BTCUSDT',startTime=int(start),endTime=int(end),limit=1000),received-100,received,received-10)


def features_fixture(pattern=0,side=1):
    a,f,i=fixture(pattern,side)
    f['kon_signal']=np.full(len(a),100.);f['kon_trend']=np.full(len(a),2.);f['sharks']=np.full(len(a),3.)
    return a,f,i


class ModelTests(unittest.TestCase):
    def test_22_exact_original_all_patterns_mirrors_and_audits(self):
        for p in range(3):
            for side in (1,-1):
                a,f,i=fixture(p,side);engine=Engine('TURN22_FORWARD_V1')
                self.assertEqual(clean(engine.warm(a,f)),clean(old.detect(a,f)))

    def test_22_gap_and_nonfinite_parity(self):
        for invalid in ('gap','nan'):
            a,f,i=fixture()
            if invalid=='gap':a[i:,0]+=HOUR
            else:f['minnows'][i]=np.nan
            self.assertEqual(clean(Engine('TURN22_FORWARD_V1').warm(a,f)),clean(old.detect(a,f)))

    def test_11_one_confirming_slope_available_one_hour_before_22(self):
        for p in range(3):
            for side in (1,-1):
                a,f,i=fixture(p,side)
                events=Engine('TURN11_EXPLORATORY_V1').warm(a,f)[0]
                e=next(e for e in events if e['pattern']==old.PATTERNS[p] and e['side']==side)
                self.assertEqual(e['i'],i-1);self.assertEqual(e['available_at'],a[i-1,0]+HOUR)

    def test_11_adx_vertex_uses_i_minus_one_not_two(self):
        a,f,i=fixture(1,-1);f['adx_rank'][:]=.9;f['adx_rank'][i-2]=.1
        events=Engine('TURN11_EXPLORATORY_V1').warm(a,f)[0]
        e=next(e for e in events if e['pattern']==old.PATTERNS[1] and e['side']==-1)
        self.assertIn('Q75',e['strata'])

    def test_11_ao_sign_span_removes_22_only_offset(self):
        a,f,i=fixture(0,1);f['ao'][i-3]=1.
        e=Engine('TURN11_EXPLORATORY_V1').warm(a,f)[0]
        self.assertTrue(any(e['pattern']==old.PATTERNS[0] and e['i']==i-1 for e in e))

    def test_11_dmi_gate_preserved(self):
        a,f,i=fixture(1,-1);f['plus_di'][:]=40
        events=Engine('TURN11_EXPLORATORY_V1').warm(a,f)[0]
        self.assertFalse(any(e['pattern']==old.PATTERNS[1] and e['side']==-1 for e in events))

    def test_only_one_or_two_slopes(self):
        with self.assertRaises(ValueError):turns([1,2,1],1,3)
        with self.assertRaises(ValueError):Engine('UNKNOWN')

    def test_actual_features_11_indices_and_intensity(self):
        a=bars(900);f=feature_sets(a);one=f['TURN11_EXPLORATORY_V1'];two=f['TURN22_FORWARD_V1']
        np.testing.assert_allclose(one['adx_curve'],abs(two['adx_slope']-old.lag(two['adx_slope'])),equal_nan=True)
        np.testing.assert_allclose(one['ao_intensity'],abs(two['ao']-old.lag(two['ao']))/a[:,4],equal_nan=True)
        np.testing.assert_allclose(one['pece_intensity'],abs(two['minnows']-old.lag(two['minnows'])),equal_nan=True)
        for key in ('ao','adx','plus_di','minus_di','regime4h','regime1d','bbwp'):
            np.testing.assert_array_equal(one[key],two[key])

    def test_prefix_invariance_both_profiles(self):
        a=bars(1000);full=feature_sets(a);pre=feature_sets(a[:900])
        for p in PROFILES:
            for k in full[p]:np.testing.assert_allclose(full[p][k][:900],pre[p][k],rtol=0,atol=0,equal_nan=True)
            events=Engine(p).warm(a,full[p])[0]
            self.assertEqual(clean([e for e in events if e['i']<900]),clean(Engine(p).warm(a[:900],pre[p])[0]))

    def test_cooldown_intensity_and_expiry_remain_identical(self):
        cfg=protocol.config();p=cfg['profiles']['TURN11_EXPLORATORY_V1']
        self.assertIn('25h cooldown before intensity',p['preserved'])
        for profile in PROFILES:
            a,f,i=fixture();f['ao_intensity_rank'][:]=.1
            events=Engine(profile).warm(a,f)[0]
            self.assertTrue(events);self.assertTrue(all(e['strata']==['ALL'] for e in events))
            for e in events:self.assertLessEqual(max(e['tokens'].values())-min(e['tokens'].values()),2)


class ReceiptTests(unittest.TestCase):
    def test_closed12_exact_values_and_no_input_mutation(self):
        a=bars(3);r=receipt(a);np.testing.assert_array_equal(klines(r),a)
        with self.assertRaises(TypeError):r.query['symbol']='ETHUSDT'
    def test_open_and_gap_and_duplicate_rejected(self):
        a=bars(3)
        with self.assertRaises(ValueError):klines(receipt(a,received=int(a[-1,0]+HOUR-1)))
        for aa in (a[[0,2]],a[[0,0,1]]):
            with self.assertRaises(ValueError):klines(receipt(aa))
    def test_bad_schema_nan_prices_volume(self):
        a=bars(1)
        for field,value in ((1,'oops'),(1,'NaN'),(2,'0'),(5,'-1'),(9,'999999')):
            rows=raw_rows(a);rows[0][field]=value
            with self.assertRaises(ValueError):klines(receipt(a,raw=rows))
    def test_only_official_public_endpoint_and_exact_parameters(self):
        a=bars(1);r=receipt(a)
        for url in ('https://evil.invalid/','https://fapi.binance.com/fapi/v1/order'):
            with self.assertRaises(ValueError):klines(Receipt(r.body,url,dict(r.query),r.request_started_ms,r.received_at_ms,r.exchange_time_ms))
        q=dict(r.query);q['token']='forbidden'
        with self.assertRaises(ValueError):klines(Receipt(r.body,r.url,q,r.request_started_ms,r.received_at_ms,r.exchange_time_ms))
    def test_revision_below_float_precision_and_equivalent_format(self):
        row=raw_rows(bars(1))[0];other=list(row);other[1]=str(row[1])+'0'
        self.assertEqual(candle_key(row),candle_key(other))
        other[1]=str(row[1])+'000000000001';self.assertNotEqual(candle_key(row),candle_key(other))
    def test_funding_missing_mark_not_assumed_zero(self):
        r=funding_receipt(ACT,ACT+HOUR,[dict(symbol='BTCUSDT',fundingTime=ACT,fundingRate='.001')])
        self.assertIsNone(funding(r)[0]['mark'])
    def test_funding_full_limit_not_proven_complete(self):
        r=funding_receipt(ACT,ACT+HOUR,[{}]*1000)
        with self.assertRaises(ValueError):funding(r)


class JournalTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def seed(self):
        j=Journal(self.root,'a'*64);j.append('X','1',{'x':1},1);j.append('X','2',{'x':2},2);return j
    def test_first_write_reboot_dedupe_and_conflict(self):
        j=self.seed();tip=j.tip;j.close();j=Journal(self.root,'a'*64)
        self.assertEqual(len(j.records),2);self.assertEqual(j.tip,tip)
        self.assertFalse(j.append('X','2',{'x':2},99))
        with self.assertRaises(JournalError):j.append('X','2',{'x':3},99)
        j.close()
    def test_second_writer_rejected(self):
        j=self.seed()
        with self.assertRaises(JournalError):Journal(self.root,'a'*64)
        j.close()
    def test_truncated_never_repaired(self):
        j=self.seed();path=j.path;j.close();raw=path.read_bytes()[:-1];path.write_bytes(raw)
        with self.assertRaises(JournalError):Journal(self.root,'a'*64)
        self.assertEqual(path.read_bytes(),raw)
    def test_tampering_reordering_previous_hash_duplicate(self):
        j=self.seed();path=j.path;j.close();original=path.read_bytes();lines=original.splitlines()
        bad=json.loads(lines[0]);bad['payload']['x']=9
        variants=[canonical(bad)+b'\n'+lines[1]+b'\n',lines[1]+b'\n'+lines[0]+b'\n',original+lines[1]+b'\n']
        for raw in variants:
            path.write_bytes(raw)
            with self.assertRaises(JournalError):Journal(self.root,'a'*64)
            self.assertEqual(path.read_bytes(),raw)
    def test_fsync_failure_sticky_no_duplicate_after_reopen(self):
        j=self.seed()
        with patch.object(__import__('os'),'fsync',side_effect=OSError('synthetic')):
            with self.assertRaises(JournalError):j.append('X','3',{},3)
        with self.assertRaises(JournalError):j.append('X','4',{},4)
        j.close();j=Journal(self.root,'a'*64);self.assertEqual(len(j.records),3)
        self.assertFalse(j.append('X','3',{},4));j.close()
    def test_blob_original_hash_and_tamper(self):
        j=self.seed();key=j.blob(b'public');self.assertEqual(j.read_blob(key),b'public')
        (j.blobs/(key+'.json')).write_bytes(b'altered')
        with self.assertRaises(JournalError):j.read_blob(key)
        with self.assertRaises(JournalError):j.blob(b'public')
        j.close()
    def test_external_tip_detects_valid_tail_removal(self):
        j=self.seed();tip=j.tip;path=j.path;j.close();path.write_bytes(path.read_bytes().splitlines()[0]+b'\n')
        j=Journal(self.root,'a'*64)
        with self.assertRaises(JournalError):j.verify_anchor(tip)
        j.close()
    def test_backward_clock_rejected(self):
        j=self.seed()
        with self.assertRaises(JournalError):j.append('X','3',{},1)
        j.close()


class ComparativeTests(unittest.TestCase):
    def test_zero_cross_series_explicit_red_cross_distinct(self):
        a,f,i=features_fixture();f['minnows'][i-1:i+1]=[-1,1];f['kon_signal'][:]=100
        result=Facts().step(i,a,f,False);events=result['events']
        self.assertTrue(any(e['kind']=='ZERO_CROSS' and e['series']=='pececillos' for e in events))
        self.assertFalse(any(e['kind']=='PECECILLOS_RED_CROSS' for e in events))
        f['kon_signal'][:]=0;events=Facts().step(i,a,f,False)['events']
        self.assertTrue(any(e['kind']=='PECECILLOS_RED_CROSS' for e in events))
    def test_both_turns_separate_and_pair_retained(self):
        a,f,i=features_fixture();facts=Facts();all_events=[]
        for j in range(len(a)):all_events+=facts.step(j,a,f,False)['events']
        for n in (1,2):
            self.assertTrue(any(e['kind']=='SLOPE_TURN' and e['series']=='ADX' and e['n']==n for e in all_events))
            self.assertTrue(any(e['kind']=='AO_ADX_PAIR' and e['n']==n for e in all_events))
    def test_bbwp_level_not_a_direction(self):
        a,f,i=features_fixture();f['bbwp'][i-2:i+1]=[88,80,81]
        result=Facts().step(i,a,f,False);event=next(e for e in result['events'] if e['kind']=='BBWP_SLOPE_TURN')
        self.assertEqual((event['level'],event['slope']),(81,1));self.assertNotIn('order',event)
    def test_weekly_monday_only_complete_closed(self):
        a=bars(6030);x=mtf(a[:6003]);last=int(a[6002,0]+HOUR)
        for row in x.values():self.assertLessEqual(row['available_at'],last)
        from datetime import datetime,timezone
        self.assertEqual(datetime.fromtimestamp(x['1W']['open_time']/1000,timezone.utc).weekday(),0)
        self.assertIsNone(x['1W']['bbwp']);self.assertIsNone(x['1W']['pececillos'])
        self.assertEqual(x['1W']['price_regime'],'UNKNOWN')
    def test_mtf_no_partial_hour4_leak(self):
        a=bars();x=mtf(a[:6001]);b=a[:6001].copy();b[-1,4]*=.99;b[-1,3]=min(b[-1,3],b[-1,4])-1
        y=mtf(b);self.assertEqual(x['4H'],y['4H']);self.assertEqual(x['1D'],y['1D']);self.assertEqual(x['1W'],y['1W'])
    def test_structural_break_recovery_failed_rebound_frozen_levels(self):
        a,f,i=features_fixture();a[:,2]=101;a[:,3]=99
        a[21,1:5]=[100,100,97,98];a[22,1:5]=[98,101,98,100];a[23,1:5]=[100,100,97,98]
        facts=Facts();events=[]
        for j in range(24):events+=facts.step(j,a,f,False)['events']
        self.assertTrue(any(e['kind']=='STRUCTURE_BREAK' and e['side']==-1 and e['level']==99 for e in events))
        self.assertTrue(any(e['kind']=='LEVEL_RECOVERY' and e['level']==99 for e in events))
        self.assertTrue(any(e['kind']=='FAILED_REBOUND' and e['level']==99 for e in events))
    def test_watch_labels_observational_no_gate(self):
        a,f,i=features_fixture();f['ao'][i-1:i+1]=[-3,-2];f['minnows'][i-1:i+1]=[-4,-3]
        f['plus_di'][:]=10;f['minus_di'][:]=30;facts=Facts()
        self.assertEqual(facts.step(i,a,f,False)['watch'],'WATCH_REBOUND')
        f['ao'][i+1]=-3;f['minnows'][i+1]=-4
        self.assertEqual(facts.step(i+1,a,f,False)['watch'],'WATCH_SHORT_REENTRY')


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=bars();cls.seed=[receipt(cls.a[j:j+1500],ACT) for j in range(0,6000,1500)]
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'isolated';self.now=ACT;self.o=None
    def tearDown(self):
        if self.o:self.o.close()
        self.tmp.cleanup()
    def start(self,**kw):
        self.o=Observer(self.root,enabled=True,clock=lambda:self.now,**kw);self.o.start(self.seed);return self.o
    def feed(self,j,**kw):
        self.now=int(self.a[j,0]+HOUR+1000);return self.o.ingest(receipt(self.a[j:j+1],self.now,**kw))
    def test_disabled_absolutely_no_io_or_processing(self):
        o=Observer(self.root);self.assertEqual(o.start(None),'DISABLED');self.assertEqual(o.ingest(None),'DISABLED')
        self.assertEqual(o.ingest_funding(None),'DISABLED');self.assertEqual(o.mature(),'DISABLED');self.assertFalse(self.root.exists())
    def test_forward_requires_separate_approval_and_identity(self):
        with self.assertRaises(ValueError):Observer(self.root,True,'FORWARD_SHADOW')
        self.assertFalse(self.root.exists())
    def test_seed_only_start_record_no_historical_imports(self):
        o=self.start();self.assertEqual([r['kind'] for r in o.store.records],['SESSION_START'])
        self.assertEqual(len(o.observations),0);self.assertEqual(o.start_record['historical_events_imported'],0)
        self.assertEqual(o.start_record['first_eligible_open_ms'],ACT+HOUR)
    def test_replay_same_state_and_duplicate_receipt_no_write(self):
        o=self.start();self.feed(6000);tip=o.store.tip;state=clean(o.observations);o.close()
        self.o=Observer(self.root,True,clock=lambda:self.now)
        self.assertEqual(clean(self.o.observations),state);self.assertEqual(self.o.store.tip,tip)
        self.feed(6000);self.assertEqual(self.o.store.tip,tip)
    def test_missing_hour_recovery_not_forward_no_skip(self):
        o=self.start();self.assertEqual(self.feed(6002),'MISSING_HOUR');self.assertEqual(len(o.observations),0)
        self.now=int(self.a[6002,0]+HOUR+1000)
        o.ingest(receipt(self.a[6000:6003],self.now));self.assertEqual(o.status,'HEALTHY')
        self.assertEqual(len(o.observations),3);self.assertTrue(all(not x['forward_eligible'] for x in o.observations.values()))
        self.assertEqual([o['collection_class'] for o in o.observations.values()],['LATE_RECOVERY','LATE_RECOVERY','ON_TIME'])
    def test_future_receipt_rejected_failure_recorded(self):
        o=self.start()
        with self.assertRaises(ValueError):o.ingest(receipt(self.a[6000:6001],ACT+2*HOUR))
        self.assertEqual(o.store.records[-1]['kind'],'COLLECTION_FAILURE');self.assertEqual(len(o.observations),0)
    def test_revision_fails_closed_no_rewrites(self):
        o=self.start();self.feed(6000);old=copy.deepcopy(o.observations)
        rows=raw_rows(self.a[6000:6001]);rows[0][4]=str(float(rows[0][4])+.1)
        self.assertEqual(o.ingest(receipt(self.a[6000:6001],self.now,raw=rows)),'DEGRADED')
        self.assertEqual(o.observations,old)
        with self.assertRaises(ValueError):self.feed(6001)
    def test_no_early_outcomes_then_h4_costs_pending_and_dedupe(self):
        o=self.start()
        for j in range(6000,6005):self.feed(j)
        self.assertFalse(any(r['kind']=='PRICE_OUTCOME' for r in o.store.records))
        self.feed(6005);out=[r for r in o.store.records if r['kind']=='PRICE_OUTCOME']
        self.assertEqual(len(out),2);self.assertTrue(all(r['payload']['net_fraction'] is None for r in out))
        self.assertTrue(all(r['payload']['reference_precedes_recording'] for r in out))
        count=len(o.store.records);o.mature();self.assertEqual(len(o.store.records),count)
        o.ingest_funding(funding_receipt(ACT,ACT+6*HOUR,received=self.now))
        net=[r for r in o.store.records if r['kind']=='COSTED_OUTCOME'];self.assertEqual(len(net),2)
        self.assertTrue(all(r['payload']['net_fraction']<r['payload']['raw_price_fraction'] for r in net))
    def test_funding_unknown_mark_does_not_publish_net(self):
        o=self.start();self.now=ACT+7*HOUR
        o.ingest(receipt(self.a[6000:6006],self.now))
        rows=[dict(symbol='BTCUSDT',fundingTime=ACT+2*HOUR,fundingRate='.001')]
        o.ingest_funding(funding_receipt(ACT,ACT+6*HOUR,rows,self.now))
        self.assertFalse(any(r['kind']=='COSTED_OUTCOME' for r in o.store.records))
    def test_all_horizons_mature_once_per_unique_observation(self):
        o=self.start();self.now=ACT+30*HOUR
        o.ingest(receipt(self.a[6000:6030],self.now));r=summarize(o.store.records)
        self.assertEqual(r['outcomes'],{'4':25,'12':17,'24':5})
        self.assertEqual(r['forward_eligible'],0);self.assertFalse(r['validated'])
        count=len(o.store.records);o.mature();self.assertEqual(len(o.store.records),count)
    def test_sidecar_failure_does_not_change_emissions_or_mutate_inputs(self):
        class Bad(Facts):
            def step(self,i,a,f,contexts=True):
                if contexts:a[-1,4]=0
                return super().step(i,a,f,contexts)
        o=self.start(sidecar=Bad());self.feed(6000)
        obs=next(iter(o.observations.values()));self.assertEqual(obs['comparative']['status'],'COMPARATIVE_UNAVAILABLE')
        self.assertEqual(o.a[-1,4],self.a[6000,4]);self.assertEqual(o.status,'HEALTHY')
        all_sets=feature_sets(self.a[:6001])
        for p in PROFILES:
            events,audit=Engine(p).warm(self.a[:6001],all_sets[p]);expected=[e for e in events if e['i']==6000]
            self.assertEqual(len(obs['profiles'][p]['events']),len(expected))
    def test_static_failure_codes_only_and_original_bytes_stored(self):
        o=self.start();self.feed(6000)
        with self.assertRaises(ValueError):o.note_failure('api_secret=forbidden')
        self.assertEqual(read_records(o.store.path,o.registry),o.store.records)
        for r in o.store.records:
            if r['kind']=='PUBLIC_SOURCE':
                data=o.store.read_blob(r['payload']['blob']);self.assertEqual(hashlib.sha256(data).hexdigest(),r['payload']['metadata']['sha256'])
    def test_uncommitted_snapshot_requires_replay_before_any_retry(self):
        o=self.start();original=o.store.append
        def fail(kind,*args,**kw):
            if kind=='CANDLE':raise JournalError('CLOCK_MOVED_BACKWARD')
            return original(kind,*args,**kw)
        with patch.object(o.store,'append',side_effect=fail):
            with self.assertRaises(JournalError):self.feed(6000)
        self.assertEqual(o.status,'DEGRADED')
        with self.assertRaises(ValueError):self.feed(6000)
        self.assertEqual(len(o.observations),0)
        o.close();self.o=Observer(self.root,True,clock=lambda:self.now);self.feed(6000)
        self.assertEqual(len(self.o.observations),1);self.assertEqual(self.o.status,'HEALTHY')


class BoundaryTests(unittest.TestCase):
    def test_sealed_registry_and_original_hashes_unchanged(self):
        self.assertEqual(protocol.verify(),protocol.EXPECTED)
        self.assertEqual(protocol.file_hash(ROOT/'research/confluence_1h_phase2/event_proximity/strict_series_audit/turn_intensity_phase1/detect.py'),'5f3bba638bf262ab286f02832545f2ef131eecaa4bc4eb9120c3286ba6b374c1')
    def test_only_new_lab_files_no_old_pr_or_runtime_edits(self):
        rows=subprocess.check_output(['git','diff',BASE,'--name-status'],cwd=ROOT,text=True).splitlines()
        for line in rows:
            status,name=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(name.startswith(PREFIX),line)
    def test_no_network_private_account_execution_or_service_hooks(self):
        banned={'requests','urllib','socket','ccxt','guardian_bitunix','trade_guardian','live_auto','bitman_manual','subprocess','http'}
        for path in protocol.ROOT.glob('*.py'):
            if path.name.startswith('test_'):continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in node.names]+([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                    for name in names:self.assertFalse(banned.intersection(name.split('.')),str(path))
        text=(protocol.ROOT/'models.py').read_text()
        for token in ('observations','Facts','WATCH_','weekly_forward','gates_ready','readiness'):self.assertNotIn(token,text)
    def test_runtime_has_no_forward_import_dynamic_or_static(self):
        names=subprocess.check_output(['git','ls-files','--','*.py'],cwd=ROOT,text=True).splitlines()
        for name in names:
            if name.startswith('research/') or Path(name).name.startswith('test_'):continue
            text=(ROOT/name).read_text('utf-8-sig');self.assertNotIn('forward_shadow',text,name)
    def test_new_registry_tampering_detected_without_refreezing(self):
        fake=json.loads((protocol.ROOT/'manifest.json').read_text());fake['files']['models.py']='0'*64
        original=Path.read_text
        def changed(path,*args,**kw):return json.dumps(fake) if path==protocol.ROOT/'manifest.json' else original(path,*args,**kw)
        with patch.object(Path,'read_text',changed):
            with self.assertRaisesRegex(ValueError,'PROTOCOL_MANIFEST'):protocol.verify()


if __name__=='__main__':unittest.main()
