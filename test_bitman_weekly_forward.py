"""Offline V1 data, models, durable journals and outcomes. Temporary storage only."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

try:
    import numpy as np
    from bitman_weekly_forward import protocol as p,features,models,market,journal,observer
except ModuleNotFoundError as error:
    if error.name=='numpy':raise unittest.SkipTest('Dedicated weekly workflow installs numpy') from error
    raise

ROOT=Path(__file__).resolve().parent
BOOT,MANIFEST=features.load_bootstrap()
START=MANIFEST['available_at']+p.MARGIN
SOURCE='a'*40


def hours(opening,count=168,close=101):
    rows=[]
    for i in range(count):
        c=close if i==167 else 100
        rows.append([opening+i*p.HOUR,'100',str(max(102,c+1)),str(min(98,c-1)),str(c),'10',
                     opening+(i+1)*p.HOUR-1,'1000',1,'4','400','0'])
    return rows


def fake_fetch(opening,now,url):
    return market.aggregate(hours(opening),opening,now)


def vector(ao,colors,slopes):
    n=len(ao);times=p.MONDAY+np.arange(n)*p.WEEK
    f=dict(ao=np.asarray(ao,float),color=np.asarray(colors),bbwp_slope=np.asarray(slopes,float),
           valid=np.ones(n,bool),frame=np.column_stack((times,np.full((n,4),100.))),available_at=times+p.WEEK,
           ao_slope=np.r_[0,np.diff(ao)],sign=np.where(np.asarray(ao)>0,'ABOVE','BELOW'),bbwp=50+np.cumsum(slopes))
    f['turn']=(f['bbwp_slope']>0)&(np.r_[np.nan,f['bbwp_slope'][:-1]]<=0)
    return f


def reference():
    spec=importlib.util.spec_from_file_location('audited_weekly_reference',ROOT/'tests/fixtures/weekly_forward_reference.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class GoldenAndModels(unittest.TestCase):
    def test_protocol_hash_and_source_immutability(self):
        self.assertEqual(p.EXPECTED_HASH,(ROOT/'tests/fixtures/weekly_forward_protocol.sha256').read_text().strip())
        self.assertEqual(p.verify()['lags'],[0,1,2])
        original=p.file_hash
        with patch.object(p,'file_hash',side_effect=lambda path:'0'*64 if Path(path).name=='indicators.py' else original(path)):
            with self.assertRaisesRegex(ValueError,'PROTOCOL_INVALID'):p.verify()

    def test_120_public_ohlc_only_no_historical_outcomes(self):
        self.assertEqual(len(BOOT),120)
        self.assertEqual(set(BOOT[0]),{'open_time','open','high','low','close'})
        self.assertEqual(BOOT[-1]['open_time']+p.WEEK,1792368000000)
        self.assertEqual(MANIFEST['source_pr31_commit'],'772446da2b7e045483c2e1d9a5c0acc185c47fe4')
        self.assertEqual(p.file_hash(p.ROOT/'bootstrap_v1.csv'),MANIFEST['sha256'])

    def test_complete_golden_not_rounded(self):
        got=features.golden_check(BOOT,MANIFEST)
        self.assertEqual(got,MANIFEST['golden'])
        self.assertEqual(got['ao'],10698.622352941165)
        self.assertEqual(got['ao_slope'],348.99441176469554)
        self.assertEqual(got['atr'],6175.9111711882015)

    def test_wrong_golden_fails_closed(self):
        manifest=copy.deepcopy(MANIFEST);manifest['golden']['ao']+=.01
        with self.assertRaisesRegex(ValueError,'GOLDEN'):features.golden_check(BOOT,manifest)

    def test_formula_and_resolution_functions_ast_equal_audited_reference(self):
        audit=ast.parse((ROOT/'tests/fixtures/weekly_forward_reference.py').read_text('utf-8'))
        actual=ast.parse((p.ROOT/'models.py').read_text('utf-8'))
        for name in ('classify','resolve'):
            a=next(n for n in audit.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in actual.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b))

    def test_all_four_rule_and_outcome_asts_match_exact_pr31_commit(self):
        audit=json.loads((ROOT/'tests/fixtures/weekly_forward_reference_audit.json').read_text())
        self.assertEqual(audit['reference_commit'],'772446da2b7e045483c2e1d9a5c0acc185c47fe4')
        for file,names in (('models.py',('classify','resolve')),('outcomes.py',('causal_range','outcomes'))):
            tree=ast.parse((p.ROOT/file).read_text('utf-8'))
            for name in names:
                node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
                self.assertEqual(hashlib.sha256(ast.dump(node).encode()).hexdigest(),audit['ast_sha256'][name])

    def test_all_required_fixture_types_and_lags(self):
        audit=reference()
        for kind in p.KINDS:
            for lag in (0,1,2):
                sign=1 if '_UP' in kind else -1
                values=([3,2,2.5,3,3.5,4] if kind.startswith('REACC') else [-2,-1,.1,.2,.3,.4])
                values=[v*sign for v in values]
                colors=(['GREEN','RED','GREEN','GREEN','GREEN','GREEN'] if kind.startswith('REACC') else ['GREEN']*6)
                if sign==-1:colors=['RED' if c=='GREEN' else 'GREEN' for c in colors]
                slopes=[1,-1]+[-1]*lag+[1]*(4-lag)
                f=vector(values,colors,slopes)
                actual=models.calculate_models(f)
                expected=dict(f);expected['state'],expected['pullback_weeks']=audit.classify(f)
                expected['signal']=np.isin(expected['state'],p.KINDS)
                expected['side']=np.where(np.isin(expected['state'],(p.KINDS[0],p.KINDS[2])),1,
                                          np.where(np.isin(expected['state'],(p.KINDS[1],p.KINDS[3])),-1,0))
                for maximum,name in enumerate(p.MODELS):
                    with self.subTest(kind=kind,lag=lag,maximum=maximum):
                        golden=audit.resolve(expected,maximum)
                        np.testing.assert_array_equal(actual[name]['states'],golden['states'])
                        self.assertEqual(actual[name]['audit'],golden['audit'])
                        self.assertEqual(actual[name]['events'],golden['events'])
                if lag<=2:
                    event=actual[p.MODELS[lag]]['events'][0]
                    self.assertEqual((event['kind'],event['lag']),(kind,lag))

    def test_no_lag_three_or_boolean_allowed(self):
        f=vector([1,-1],['RED','RED'],[-1,1]);f['state'],_=models.classify(f)
        for value in (3,4,5,-1,True,1.0):
            with self.assertRaises(ValueError):models.resolve(f,value)

    def test_model_prefix_invariance_and_persistent_no_duplicate(self):
        f=vector([3,2,2.5,3,4,5],['GREEN','RED','GREEN','GREEN','GREEN','GREEN'],[1,-1,-1,-1,1,1])
        complete=models.calculate_models(f)
        for end in range(1,7):
            prefix=models.calculate_models({k:v[:end] for k,v in f.items()})
            for name in p.MODELS:
                self.assertEqual(prefix[name]['events'],[e for e in complete[name]['events'] if e['index']<end])
                np.testing.assert_array_equal(prefix[name]['states'],complete[name]['states'][:end])
        self.assertEqual(len(complete[p.MODELS[2]]['events']),1)

    def test_cancellations_expiry_zero_invalid_and_new_correction(self):
        cases=[([-.1,.1,0,.2],['GREEN','GREEN','RED','GREEN'],[-1,-1,-1,1],'ZERO_OR_OPPOSITE_SIGN'),
               ([3,2,2.5,2.4,2.6],['GREEN','RED','GREEN','RED','GREEN'],[1,-1,-1,-1,1],'NEW_CORRECTION'),
               ([-1,.1,.2,.3,.4],['GREEN']*5,[-1,-1,-1,-1,1],'DEADLINE_WITHOUT_VOLATILITY_CONFIRMATION'),
               ([-1,.1,-.1,-.2],['GREEN','GREEN','RED','RED'],[-1,-1,-1,1],'ZERO_OR_OPPOSITE_SIGN')]
        for ao,color,slopes,reason in cases:
            result=models.calculate_models(vector(ao,color,slopes))[p.MODELS[2]]
            self.assertTrue(any(r['reason']==reason for r in result['audit']))
        f=vector([-1,.1,.2,.3],['GREEN']*4,[-1,-1,-1,1]);f['valid'][2]=False
        result=models.calculate_models(f)[p.MODELS[2]]
        self.assertTrue(any(r['reason']=='INVALID_WEEK' for r in result['audit']))
        self.assertEqual(result['events'],[])

    def test_pending_zero_cross_owns_resolution_no_double_count(self):
        f=vector([-1,.2,.1,.3,.4],['GREEN','GREEN','RED','GREEN','GREEN'],[-1,-1,-1,1,1])
        m=models.calculate_models(f)[p.MODELS[2]]
        self.assertEqual(len(m['events']),1)
        self.assertEqual(m['events'][0]['kind'],'ZERO_CROSS_UP_EXPANSION')
        self.assertTrue(any(r['action']=='IGNORED' for r in m['audit']))


class MarketTests(unittest.TestCase):
    def setUp(self):self.opening=MANIFEST['available_at'];self.now=self.opening+p.WEEK+p.MARGIN

    def test_exact_168_week_aggregation(self):
        candle,sha=market.aggregate(hours(self.opening,close=105),self.opening,self.now)
        self.assertEqual(candle,dict(open_time=self.opening,open='100',high='106',low='98',close='105'))
        self.assertEqual(sha,p.digest(hours(self.opening,close=105)))

    def test_167_169_and_partial_week_rejected(self):
        for count in (0,167,169):
            with self.subTest(count=count),self.assertRaises(ValueError):
                market.aggregate(hours(self.opening,count),self.opening,self.now)
        with self.assertRaises(ValueError):market.aggregate(hours(self.opening),self.opening,self.opening+p.WEEK-1)

    def test_duplicate_gap_wrong_close_schema_ohlc_nan_rejected(self):
        for change in ('duplicate','gap','close','schema','bad_ohlc','nan'):
            rows=hours(self.opening)
            if change=='duplicate':rows[5]=rows[4]
            if change=='gap':rows[5][0]+=p.HOUR
            if change=='close':rows[5][6]-=1
            if change=='schema':rows[5].pop()
            if change=='bad_ohlc':rows[5][2]='99'
            if change=='nan':rows[5][4]='NaN'
            with self.subTest(change=change),self.assertRaises(ValueError):market.aggregate(rows,self.opening,self.now)

    def test_open_week_is_not_requested(self):
        with patch.object(market.http,'build_opener') as build,self.assertRaises(ValueError):
            market.fetch_week(self.opening,self.opening+p.HOUR,market.PRIVATE_URL)
        build.assert_not_called()

    def test_only_exact_private_url_no_public_or_proxy(self):
        for url in ('https://fapi.binance.com/fapi/v1/klines','http://evil','http://bitman-market-data.railway.internal:8080/fapi/v1/order',market.PRIVATE_URL+'?foo=bar'):
            with self.assertRaises(ValueError):market.validate_url(url)

    def response(self,status=200,body=None):
        r=Mock(status=status);r.read.return_value=body if body is not None else json.dumps(hours(self.opening)).encode()
        r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False);return r

    def test_http_get_no_proxy_redirect_credentials_and_fixed_parameters(self):
        opener=Mock();opener.open.return_value=self.response()
        with patch.object(market.http,'build_opener',return_value=opener) as build:
            market.fetch_week(self.opening,self.now,market.PRIVATE_URL)
        self.assertEqual(build.call_args.args[0].proxies,{})
        self.assertIsInstance(build.call_args.args[1],market.NoRedirect)
        req=opener.open.call_args.args[0]
        self.assertEqual(req.get_method(),'GET');self.assertNotIn('Authorization',req.headers)
        self.assertIn('limit=168',req.full_url);self.assertEqual(opener.open.call_args.kwargs,{'timeout':8})
        self.assertIsNone(market.NoRedirect().redirect_request(None,None,302,'',{},'http://evil'))

    def test_non_200_timeout_oversize_invalid_json_fail_closed(self):
        for failure in (451,429,500,'timeout','oversize','json'):
            opener=Mock()
            if failure=='timeout':opener.open.side_effect=TimeoutError()
            else:opener.open.return_value=self.response(failure if type(failure) is int else 200,
                    b'x'*(market.MAX_BYTES+1) if failure=='oversize' else b'notjson' if failure=='json' else None)
            with patch.object(market.http,'build_opener',return_value=opener),self.assertRaises(Exception):
                market.fetch_week(self.opening,self.now,market.PRIVATE_URL)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)

    def boot(self,now=START,fetch=fake_fetch):
        return observer.run(self.folder,market.PRIVATE_URL,SOURCE,now,fetch)

    def raw(self):return (self.folder/journal.NAME).read_bytes()
    def rows(self):return [json.loads(line) for line in self.raw().splitlines()]

    def rewrite(self,rows):
        previous=journal.ZERO
        for row in rows:
            row['prev_hash']=previous;row.pop('record_hash',None);row['record_hash']=p.digest(row);previous=row['record_hash']
        (self.folder/journal.NAME).write_bytes(b''.join(p.canonical(r)+b'\n' for r in rows))

    def invalid_unchanged(self):
        raw=self.raw()
        with self.assertRaises(journal.JournalInvalid):self.boot(START+1)
        self.assertEqual(self.raw(),raw)

    def test_first_start_and_schema_no_historical_events(self):
        view=self.boot();rows=self.rows()
        self.assertEqual([r['record_type'] for r in rows],['FORWARD_OBSERVATION_START','BOOTSTRAP'])
        self.assertEqual(view['forward_events'],0);self.assertEqual(view['horizons'],dict.fromkeys(('1','2','3','4'),0))
        self.assertEqual(rows[0]['payload']['activated_at'],START)
        self.assertEqual(rows[0]['payload']['deployment_source_sha'],SOURCE)
        for row in rows:
            self.assertEqual(row['protocol_hash'],p.EXPECTED_HASH);self.assertEqual(row['schema_version'],1)
            self.assertEqual(row['source_venue'],'BINANCE_USDM_PERPETUAL')

    def test_second_start_and_one_hundred_reboots_do_not_duplicate(self):
        self.boot();before=self.raw()
        for i in range(100):self.boot(START+i+1)
        self.assertEqual(self.raw(),before)

    def test_reboot_between_start_and_bootstrap(self):
        original=journal.Journal.append
        def broken(obj,kind,*args):
            if kind=='BOOTSTRAP':raise OSError('fixture interruption')
            return original(obj,kind,*args)
        with patch.object(journal.Journal,'append',broken),self.assertRaises(OSError):self.boot()
        self.assertEqual(len(self.rows()),1)
        self.boot(START+1);self.assertEqual(len(self.rows()),2)

    def test_fsync_failure_never_claims_committed_then_safe_reopen(self):
        with patch.object(journal.os,'fsync',side_effect=OSError()),self.assertRaisesRegex(ValueError,'DURABILITY'):
            self.boot()
        self.assertTrue(self.raw().endswith(b'\n'))
        view=self.boot(START+1)
        self.assertEqual(view['journal_records'],2)
        self.assertEqual(len({r['record_id'] for r in self.rows()}),2)

    def test_truncated_last_line_invalid_never_repaired(self):
        self.boot();(self.folder/journal.NAME).write_bytes(self.raw()[:-5]);self.invalid_unchanged()

    def test_modified_historical_line_invalid_never_repaired(self):
        self.boot();rows=self.rows();rows[0]['payload']['known_close']+=1
        (self.folder/journal.NAME).write_bytes(b''.join(p.canonical(r)+b'\n' for r in rows));self.invalid_unchanged()

    def test_wrong_previous_hash(self):
        self.boot();rows=self.rows();rows[1]['prev_hash']='f'*64
        rows[1]['record_hash']=p.digest({k:v for k,v in rows[1].items() if k!='record_hash'})
        (self.folder/journal.NAME).write_bytes(b''.join(p.canonical(r)+b'\n' for r in rows));self.invalid_unchanged()

    def test_duplicate_record_id_even_rehashed(self):
        self.boot();rows=self.rows();rows.append(copy.deepcopy(rows[-1]));self.rewrite(rows);self.invalid_unchanged()

    def test_reordered_records(self):
        self.boot();self.rewrite(list(reversed(self.rows())));self.invalid_unchanged()

    def test_semantic_tamper_even_rehashed(self):
        self.boot();rows=self.rows();rows[-1]['payload']['snapshot']['bbwp']=99
        self.rewrite(rows);self.invalid_unchanged()

    def test_missing_week_cannot_be_skipped(self):
        self.boot();self.boot(START+p.WEEK)
        rows=self.rows();row=next(r for r in rows if r['record_type']=='WEEK_SNAPSHOT')
        row['payload']['candle']['open_time']+=p.WEEK
        row['week_open']+=p.WEEK;row['available_at']+=p.WEEK
        row['weekly_candle_hash']=p.digest(row['payload']['candle'])
        self.rewrite(rows)
        raw=self.raw()
        with self.assertRaises(journal.JournalInvalid):self.boot(START+2*p.WEEK)
        self.assertEqual(self.raw(),raw)

    def test_no_network_until_new_monday_and_margin(self):
        fetch=Mock(side_effect=AssertionError('no request'))
        self.boot(fetch=fetch);self.boot(MANIFEST['available_at']+p.WEEK+p.MARGIN-1,fetch)
        fetch.assert_not_called()

    def test_market_unavailable_degrades_no_snapshot_or_event(self):
        self.boot()
        fetch=Mock(side_effect=OSError())
        view=self.boot(START+p.WEEK,fetch)
        self.assertEqual(view['status'],'DEGRADED');self.assertEqual(len(self.rows()),2)
        self.assertEqual(view['forward_events'],0)

    def test_replay_and_derived_state_rebuild(self):
        self.boot();a=self.boot(START+p.WEEK);raw=self.raw()
        (self.folder/journal.STATE).write_text('broken derived file')
        b=self.boot(START+p.WEEK+1)
        self.assertEqual(a['snapshot'],b['snapshot']);self.assertEqual(a['journal_tip'],b['journal_tip'])
        self.assertEqual(raw,self.raw())
        self.assertEqual(json.loads((self.folder/journal.STATE).read_text())['snapshot'],a['snapshot'])

    def test_future_append_never_changes_historical_prefix(self):
        self.boot();self.boot(START+p.WEEK);prefix=self.raw()
        self.boot(START+2*p.WEEK)
        self.assertTrue(self.raw().startswith(prefix))

    def test_rollout_later_than_bootstrap_is_warmup_not_forward(self):
        view=self.boot(START+2*p.WEEK)
        types=[r['record_type'] for r in self.rows()]
        self.assertEqual(types.count('RECOVERY'),2)
        self.assertNotIn('WEEK_SNAPSHOT',types);self.assertNotIn('MODEL_EVENT',types)
        self.assertEqual(view['forward_events'],0)

    def test_recovery_is_bounded_and_chronological(self):
        self.boot();fetch=Mock(side_effect=fake_fetch)
        view=self.boot(START+6*p.WEEK,fetch)
        self.assertEqual(view['status'],'DEGRADED');self.assertEqual(fetch.call_count,4)
        self.assertEqual([c.args[0] for c in fetch.call_args_list],[MANIFEST['available_at']+i*p.WEEK for i in range(4)])
        self.assertEqual(self.boot(START+6*p.WEEK+1)['status'],'HEALTHY')

    def test_deleted_previously_initialized_journal_not_regenerated(self):
        self.boot();(self.folder/journal.NAME).unlink()
        with self.assertRaises(journal.JournalInvalid):self.boot(START+1)
        self.assertFalse((self.folder/journal.NAME).exists())

    def test_protocol_or_golden_failure_before_any_storage(self):
        with patch.object(observer.p,'verify',side_effect=ValueError('INVALID')),self.assertRaises(ValueError):self.boot()
        self.assertEqual(list(self.folder.iterdir()),[])
        with patch.object(observer,'golden_check',side_effect=ValueError('GOLDEN')),self.assertRaises(ValueError):self.boot()
        self.assertEqual(list(self.folder.iterdir()),[])

    def test_bad_source_sha_before_any_storage(self):
        with self.assertRaisesRegex(ValueError,'SOURCE'):
            observer.run(self.folder,market.PRIVATE_URL,'UNKNOWN',START)
        self.assertEqual(list(self.folder.iterdir()),[])


class OutcomeJournalTests(unittest.TestCase):
    """Explicit synthetic feature seam tests storage/outcomes, not market claims."""
    def setUp(self):
        JournalTests.setUp(self)
        self.real_context=observer.context
        self.lag=0
        def synthetic(rows,manifest):
            f,mods,view=self.real_context(rows,manifest)
            for m in mods.values():m['events']=[]
            i=120+self.lag
            if len(rows)>i:
                name=p.MODELS[self.lag]
                event=dict(index=i,activation_index=120,kind='REACCELERATION_UP',side=1,lag=self.lag,pullback_weeks=1)
                mods[name]['events']=[event]
            return f,mods,view
        self.patcher=patch.object(observer,'context',side_effect=synthetic);self.patcher.start();self.addCleanup(self.patcher.stop)

    boot=JournalTests.boot
    raw=JournalTests.raw
    rows=JournalTests.rows

    def test_h1_h2_h3_h4_mature_only_with_new_closed_weeks_and_dedupe(self):
        self.boot();a=self.boot(START+p.WEEK)
        self.assertEqual(a['forward_events'],1);self.assertEqual(a['horizons']['1'],0)
        prefix=self.raw();self.boot(START+p.WEEK+1);self.assertEqual(self.raw(),prefix)
        for horizon in (1,2,3,4):
            view=self.boot(START+(horizon+1)*p.WEEK)
            self.assertEqual(view['horizons'][str(horizon)],1)
            for future in range(horizon+1,5):self.assertEqual(view['horizons'][str(future)],0)
        self.assertEqual(view['matured'],1)
        prefix=self.raw();self.boot(START+5*p.WEEK+1);self.assertEqual(self.raw(),prefix)
        self.assertEqual(sum(r['record_type']=='OUTCOME' for r in self.rows()),4)

    def test_reboot_after_snapshot_before_event_completes_once(self):
        self.boot();original=journal.Journal.append
        def broken(obj,kind,*args):
            if kind=='MODEL_EVENT':raise OSError('fixture crash')
            return original(obj,kind,*args)
        with patch.object(journal.Journal,'append',broken):self.boot(START+p.WEEK)
        self.assertEqual(sum(r['record_type']=='WEEK_SNAPSHOT' for r in self.rows()),1)
        view=self.boot(START+p.WEEK+1)
        self.assertEqual(view['forward_events'],1)
        self.assertEqual(sum(r['record_type']=='MODEL_EVENT' for r in self.rows()),1)

    def test_confirmation_move_during_lag_not_credited(self):
        self.lag=2
        self.boot()
        def fetch(opening,now,url):
            index=(opening-MANIFEST['available_at'])//p.WEEK
            return market.aggregate(hours(opening,close=[100,200,1000,1100][index]),opening,now)
        for i in range(1,5):self.boot(START+i*p.WEEK,fetch)
        event=next(r for r in self.rows() if r['record_type']=='MODEL_EVENT')
        outcome=next(r for r in self.rows() if r['record_type']=='OUTCOME')
        self.assertEqual(event['payload']['confirmation_close'],1000)
        self.assertAlmostEqual(outcome['payload']['metrics']['forward'],10)

    def test_late_recovered_event_explicitly_not_prospective(self):
        self.boot();view=self.boot(START+3*p.WEEK)
        self.assertEqual(view['forward_events'],0);self.assertEqual(view['late_recovery_events'],1)
        event=next(r for r in self.rows() if r['record_type']=='MODEL_EVENT')
        self.assertEqual(event['created_at'],START+3*p.WEEK)
        self.assertFalse(event['payload']['prospective'])
        self.assertEqual(event['payload']['observation_class'],'LATE_RECOVERY_NOT_PROSPECTIVE')


if __name__=='__main__':unittest.main()
