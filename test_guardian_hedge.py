"""Offline fixtures only. No real credentials, account requests or Telegram sends."""
import ast
from copy import deepcopy
from decimal import Decimal
from email.utils import formatdate
import hashlib,json,os,queue,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from guardian_hedge.model import build_view,Unverified,positions,account
from guardian_hedge.client import Reader,ACCOUNT,POSITIONS,TPSL,TICKER
from guardian_hedge.render import render_view
from guardian_hedge import host
from guardian_hedge.notifications import apply
from guardian_commands import SnapshotCache,render_command,NO_DATA,TelegramCommands
from guardian_risk import Config
from igod_notifications.policy import Policy,identity
from igod_notifications.adapters import event

ROOT=Path(__file__).resolve().parent
NOW=2_000_000_000

def fixture():return json.loads((ROOT/'tests/fixtures/guardian_hedge_anonymized.json').read_text())
def view(f=None):
    f=f or fixture()
    return build_view(f['positions'],f['account'],f['orders'],f['tickers'],started_at=NOW-2,completed_at=NOW)
def facts(v=None,at=NOW*1000):
    v=v or view()
    return dict(verified=True,at=at,managed=True,account_confirmed=v['pnl_reconciled'],legacy_cause='AMBIGUOUS_POSITIONS',
        positions=[dict(ref=identity(p['position_id']),side=p['side'],symbol=p['symbol'],coverage=p['coverage']['status'],coverage_fingerprint='fixture') for p in v['positions']],risk_reasons=v['risk']['reasons'])

class HTTP:
    def __init__(self,f=None):self.f=f or fixture();self.calls=[];self.override=None;self.counts={}
    def get(self,url,**kw):
        path=url.removeprefix('https://fapi.bitunix.com');self.calls.append((url,kw));self.counts[path]=self.counts.get(path,0)+1
        data={ACCOUNT:self.f['account'],POSITIONS:self.f['positions'],TPSL:self.f['orders'],TICKER:self.f['tickers']}[path]
        if self.override is not None:data=self.override(path,self.counts[path],deepcopy(data))
        body={'code':0,'data':deepcopy(data)}
        return Mock(status_code=200,headers={'Date':formatdate(NOW,usegmt=True)},content=json.dumps(body).encode(),json=Mock(return_value=body))

class ModelTests(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def test_two_sides_and_realized_costs_not_double_counted(self):
        v=view(self.f);self.assertEqual({p['side'] for p in v['positions']},{'LONG','SHORT'})
        self.assertEqual(v['gross_notional'],2440);self.assertEqual(v['net_notional_by_symbol']['BTCUSDT'],0)
        self.assertEqual(v['account']['equity_components'],1284);self.assertEqual(v['position_sums']['realized'],1)
        self.assertEqual(v['position_sums']['fees'],Decimal('1.1'));self.assertEqual(v['position_sums']['funding'],0)
    def test_margins_are_account_values_not_duplicate_equities(self):
        self.f['account']['margin']='200';v=view(self.f)
        self.assertEqual(v['account']['margin'],200);self.assertEqual(v['position_sums']['margin'],244)
        self.assertEqual(v['account']['equity_components'],1240)
    def test_both_stops_scoped_independently(self):
        v=view(self.f);self.assertTrue(all(p['coverage']['status']=='FULL_REGISTERED' for p in v['positions']))
        self.assertEqual([p['coverage']['sl'][0]['id'] for p in v['positions']],['20001','20002'])
    def test_tp_only_is_absent_stop(self):
        self.f['orders'][0]['slPrice']='0';v=view(self.f)
        self.assertEqual(v['positions'][0]['coverage']['status'],'ABSENT');self.assertEqual(v['risk']['status'],'UNPROTECTED')
        self.assertEqual(v['positions'][1]['coverage']['status'],'FULL_REGISTERED')
    def test_partial_insufficient_stop(self):
        self.f['orders'][0]['slQty']='0.01';self.assertEqual(view(self.f)['positions'][0]['coverage']['status'],'INSUFFICIENT')
    def test_zero_missing_limit_and_unknown_type_unverifiable(self):
        for key,value in (('slQty','0'),('slQty',None),('slOrderType','LIMIT'),('slStopType','UNKNOWN'),('slPrice','NaN'),('slPrice','62000')):
            f=fixture();f['orders'][0][key]=value
            with self.subTest(key=key,value=value):self.assertEqual(view(f)['positions'][0]['coverage']['status'],'UNVERIFIABLE')
    def test_split_full_coverage_registered_not_fill_guarantee(self):
        self.f['orders'][0]['slQty']='0.01';self.f['orders'].append(dict(self.f['orders'][0],id='20003'))
        v=view(self.f);self.assertEqual(v['positions'][0]['coverage']['status'],'FULL_REGISTERED');self.assertFalse(v['risk']['liquidation_risk_certified'])
    def test_overlapping_excess_quantity_not_certified(self):
        self.f['orders'].append(dict(self.f['orders'][0],id='20003'))
        self.assertEqual(view(self.f)['positions'][0]['coverage']['status'],'UNVERIFIABLE')
    def test_stop_beyond_liquidation_rejected(self):
        self.f['orders'][0]['slPrice']='49000';self.assertEqual(view(self.f)['positions'][0]['coverage']['status'],'UNVERIFIABLE')
    def test_duplicate_or_orphan_order_rejects_entire_view(self):
        for bad in (dict(self.f['orders'][0]),dict(self.f['orders'][0],id='20003',positionId='999')):
            f=fixture();f['orders'].append(bad)
            with self.assertRaises(Unverified):view(f)
    def test_duplicate_position_never_picks_one(self):
        self.f['positions'].append(dict(self.f['positions'][0]))
        with self.assertRaises(Unverified):view(self.f)
    def test_multitrade_same_side_preserves_distinct_ids(self):
        p=dict(self.f['positions'][0],positionId='10003',unrealizedPNL='0');self.f['positions'].append(p)
        v=view(self.f);self.assertEqual(len(v['positions']),3);self.assertEqual(v['gross_notional'],3660)
    def test_multiple_assets_not_cancelled_as_fake_net_zero(self):
        p=dict(self.f['positions'][0],positionId='10003',symbol='ETHUSDT',qty='1',avgOpenPrice='3000',liqPrice='2500',unrealizedPNL='0')
        self.f['positions'].append(p);self.f['tickers'].append(dict(symbol='ETHUSDT',markPrice='3000',lastPrice='3000'))
        v=view(self.f);self.assertEqual(v['gross_notional'],5440);self.assertEqual(v['net_notional_by_symbol'],{'BTCUSDT':0,'ETHUSDT':3000})
    def test_account_scope_and_bonus_unverified(self):
        for mutate in (lambda f:f['account'].update(marginCoin='BTC'),lambda f:f['account'].update(bonus='1'),lambda f:f['account'].update(positionMode='ONE_WAY'),lambda f:f['positions'][0].update(subAccountId=2)):
            f=fixture();mutate(f)
            with self.assertRaises(Unverified):view(f)
    def test_nonpositive_liquidation_is_documented_not_missing(self):
        for liq in ('0','-1'):
            self.f['positions'][0]['liqPrice']=liq;p=view(self.f)['positions'][0]
            self.assertEqual(p['liquidation_state'],'DOCUMENTED_NO_CURRENT_ESTIMATE');self.assertIsNone(p['liquidation_distance'])
    def test_missing_liquidation_remains_explicitly_unknown(self):
        self.f['positions'][0]['liqPrice']=None;v=view(self.f)
        self.assertEqual(v['positions'][0]['liquidation_state'],'UNAVAILABLE');self.assertIn('LIQUIDATION_UNAVAILABLE',v['risk']['reasons'])
    def test_cross_unexpected_reference_not_invented_liquidation(self):
        self.f['positions'][1]['liqPrice']='50000';v=view(self.f)
        self.assertIn('LIQUIDATION_DIRECTION_UNVERIFIED',v['risk']['reasons']);self.assertFalse(v['risk']['liquidation_risk_certified'])
    def test_two_percent_reference_unchanged_no_action(self):
        self.f['positions'][0]['liqPrice']='60000';v=view(self.f)
        self.assertEqual(v['risk']['status'],'CRITICAL_REFERENCE');self.assertFalse(v['protection_execution'])
    def test_pnl_mismatch_visible_not_falsely_reconciled(self):
        self.f['account']['crossUnrealizedPNL']='42';v=view(self.f)
        self.assertFalse(v['pnl_reconciled']);self.assertIn('PNL_ACCOUNT_POSITION_MISMATCH',v['risk']['reasons'])
    def test_position_and_order_order_invariant_and_input_not_mutated(self):
        before=deepcopy(self.f);v=view(self.f);self.assertEqual(self.f,before)
        self.f['positions'].reverse();self.f['orders'].reverse();self.assertEqual(v,view(self.f))
    def test_untrusted_exception_code_sanitized(self):self.assertEqual(str(Unverified('SECRET_VALUE_123')),'READ_UNAVAILABLE')

class ClientTests(unittest.TestCase):
    def setUp(self):self.http=HTTP();self.reader=Reader('private-key','private-secret',transport=self.http,clock=lambda:NOW,sleep=lambda _:None)
    def test_stable_account_full_positions_tpsl_and_get_only(self):
        v=self.reader.collect();self.assertTrue(v['read_complete']);self.assertEqual(len(v['positions']),2)
        self.assertEqual(self.http.counts[POSITIONS],2);self.assertEqual(self.http.counts[TPSL],2)
        self.assertFalse(self.http.trust_env)
        for url,kw in self.http.calls:self.assertFalse(kw['allow_redirects']);self.assertNotIn('positionId',kw['params'])
        self.assertNotIn('private-key',json.dumps(v,default=str));self.assertNotIn('private-secret',json.dumps(v,default=str))
    def test_arbitrary_paths_and_queries_blocked_before_network(self):
        for path,params in (('/api/v1/futures/trade/place_order',{}),('https://other.invalid',{}),(POSITIONS,{'symbol':'BTCUSDT'}),(ACCOUNT,{'marginCoin':'BTC'}),(TPSL,{'symbol':'BTCUSDT','limit':100,'skip':0,'positionId':'10001'})):
            with self.assertRaises(Unverified):self.reader.get(path,params)
        self.assertEqual(self.http.calls,[]);self.assertFalse(hasattr(self.reader,'post'))
    def test_partial_positions_total_rejected(self):
        self.http.override=lambda path,n,data:{'positionList':data,'total':3} if path==POSITIONS else data
        with self.assertRaisesRegex(Unverified,'POSITIONS_INCOMPLETE'):self.reader.collect()
    def test_position_size_entry_side_fees_and_funding_changes_fail_closed(self):
        for field,value in (('qty','0.03'),('avgOpenPrice','60100'),('side','SELL'),('fee','1'),('funding','-1')):
            self.http=HTTP();self.reader._http=self.http
            def change(path,n,data):
                if path==POSITIONS and n==2:data[0][field]=value
                return data
            self.http.override=change
            with self.subTest(field=field),self.assertRaisesRegex(Unverified,'POSITIONS_CHANGED'):self.reader.collect()
    def test_order_change_fails_closed(self):
        def change(path,n,data):
            if path==TPSL and n==2:data[0]['slPrice']='58000'
            return data
        self.http.override=change
        with self.assertRaisesRegex(Unverified,'ORDERS_CHANGED_DURING_READ'):self.reader.collect()
    def test_balance_change_fails_closed(self):
        self.http.override=lambda path,n,data:dict(data,available='900') if path==ACCOUNT and n==2 else data
        with self.assertRaisesRegex(Unverified,'ACCOUNT_CHANGED'):self.reader.collect()
    def test_http_redirect_auth_bad_date_timeout_all_unverified(self):
        for response in (Mock(status_code=302),Mock(status_code=451),Mock(status_code=200,content=b'{}',headers={},json=lambda:{})):
            self.reader._http=Mock(get=Mock(return_value=response))
            with self.assertRaises(Unverified):self.reader.collect()
        self.reader._http=Mock(get=Mock(side_effect=RuntimeError('PRIVATE_SECRET_RESPONSE')))
        with self.assertRaisesRegex(Unverified,'^READ_UNAVAILABLE$'):self.reader.collect()
    def test_expired_deadline_prevents_network(self):
        self.reader.deadline=self.reader.monotonic()-1
        with self.assertRaisesRegex(Unverified,'READ_DEADLINE'):self.reader.get(ACCOUNT,{'marginCoin':'USDT'})
        self.assertFalse(self.http.calls)
    def test_pagination_repeated_page_not_silently_accepted(self):
        self.http.override=lambda path,n,data:[deepcopy(data[0]) for _ in range(100)] if path==TPSL else data
        with self.assertRaises(Unverified):self.reader.collect()

class NotificationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=Policy(self.tmp.name)
    def tearDown(self):self.p.close();self.tmp.cleanup()
    def count(self):return self.p.db.execute('SELECT count(*) FROM outbox').fetchone()[0]
    def blind(self,at=NOW*1000):self.p.ingest(event('guardian','CRITICAL',at,'Private read unknown',incident_id='guardian:private-read',severity=3,material={'code':'AMBIGUOUS_POSITIONS'}),at)
    def test_only_complete_fresh_evidence_resolves_ambiguity_not_missing_stop(self):
        self.blind();f=fixture();f['orders'][0]['slPrice']='0'
        apply(self.p,facts(view(f),NOW*1000+1),NOW*1000+1)
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],0)
        self.assertEqual(self.p.db.execute("SELECT count(*) FROM incidents WHERE active=1 AND id LIKE 'guardian:hedge-stop:%'").fetchone()[0],1)
    def test_hundred_same_evaluations_do_not_spam(self):
        f=fixture();f['orders'][0]['slPrice']='0';value=facts(view(f))
        for i in range(100):apply(self.p,value,NOW*1000+i)
        self.assertEqual(self.count(),1)
    def test_read_failure_never_resolves_existing_incidents(self):
        self.blind();apply(self.p,dict(verified=False,at=NOW*1000+1,legacy_cause='AMBIGUOUS_POSITIONS'),NOW*1000+1)
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],1)
    def test_stale_future_and_older_evidence_rejected(self):
        self.blind();v=facts(at=NOW*1000-31000)
        with self.assertRaises(ValueError):apply(self.p,v,NOW*1000)
        with self.assertRaises(ValueError):apply(self.p,facts(at=NOW*1000+1),NOW*1000)
        apply(self.p,dict(verified=False,at=NOW*1000+2,legacy_cause='AMBIGUOUS_POSITIONS'),NOW*1000+2)
        self.assertEqual(apply(self.p,facts(),NOW*1000+3),[])
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],1)
    def test_real_private_error_is_not_masked(self):
        at=NOW*1000;self.p.ingest(event('guardian','CRITICAL',at,'Auth unavailable',incident_id='guardian:private-read',severity=3,material={'code':'HTTP_FAILURE_OR_STALE'}),at)
        apply(self.p,facts(at=at+1),at+1)
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],1)
    def test_pnl_mismatch_cannot_clear_ambiguity(self):
        self.blind();f=fixture();f['account']['crossUnrealizedPNL']='41'
        apply(self.p,facts(view(f),NOW*1000+1),NOW*1000+1)
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],1)
    def test_failed_or_unreconciled_overlay_never_relabels_real_private_failure(self):
        at=NOW*1000
        apply(self.p,facts(at=at),at)  # Persist that HEDGE was managed before the failure.
        self.p.ingest(event('guardian','CRITICAL',at+1,'Auth unavailable',incident_id='guardian:private-read',severity=3,material={'code':'HTTP_FAILURE_OR_STALE'}),at+1)
        failed=dict(verified=False,at=at+2,legacy_cause='HTTP_FAILURE_OR_STALE')
        mismatch=facts(at=at+3);mismatch['account_confirmed']=False
        for v in (failed,mismatch):
            apply(self.p,v,v['at'])
            row=self.p.db.execute("SELECT * FROM incidents WHERE id='guardian:private-read'").fetchone()
            self.assertEqual(json.loads(row['material'])['code'],'HTTP_FAILURE_OR_STALE');self.assertEqual(row['active'],1)
    def test_notification_failure_recovers_only_from_consistent_complete_evidence(self):
        at=NOW*1000;iid='guardian:hedge-notifications'
        self.p.ingest(event('guardian','CRITICAL',at,'Reconciliation failed',incident_id=iid,severity=3,material={'code':'HEDGE_NOTIFICATION_UNVERIFIABLE'}),at)
        v=facts(at=at+1);v['account_confirmed']=False;apply(self.p,v,at+1)
        self.assertEqual(self.p.db.execute('SELECT active FROM incidents WHERE id=?',(iid,)).fetchone()[0],1)
        apply(self.p,facts(at=at+2),at+2)
        self.assertEqual(self.p.db.execute('SELECT active FROM incidents WHERE id=?',(iid,)).fetchone()[0],0)
    def test_restart_position_closed_resolves_specific_stop_not_obsolete_reminder(self):
        f=fixture();f['orders'][0]['slPrice']='0';apply(self.p,facts(view(f)),NOW*1000)
        self.p.close();self.p=Policy(self.tmp.name)
        flat=fixture();flat['positions']=[];flat['orders']=[];flat['account']['crossUnrealizedPNL']='0'
        apply(self.p,facts(view(flat),NOW*1000+1000),NOW*1000+1000)
        self.assertEqual(self.p.db.execute("SELECT count(*) FROM incidents WHERE active=1 AND id LIKE 'guardian:hedge-stop:%'").fetchone()[0],0)
        self.assertEqual(self.p.db.execute("SELECT count(*) FROM outbox WHERE state='PENDING' AND priority=0").fetchone()[0],1)  # recovery only
    def test_silent_preference_cannot_mute_stop_critical(self):
        self.p.setting('silent',True);f=fixture();f['orders'][0]['slPrice']='0';apply(self.p,facts(view(f)),NOW*1000)
        self.assertEqual(self.count(),1)
    def test_legacy_risk_of_present_other_side_is_not_falsely_resolved(self):
        at=NOW*1000
        for pid in ('10001','closed-id'):
            self.p.ingest(event('guardian','CRITICAL',at,'Risk',incident_id='capital-risk:'+identity(pid),severity=3,material={'code':'CAPITAL_RISK','state':'EMERGENCY'}),at)
        apply(self.p,facts(at=at+1),at+1)
        self.assertEqual(self.p.db.execute('SELECT active FROM incidents WHERE id=?',('capital-risk:'+identity('10001'),)).fetchone()[0],1)
        self.assertEqual(self.p.db.execute('SELECT active FROM incidents WHERE id=?',('capital-risk:'+identity('closed-id'),)).fetchone()[0],0)
    def test_each_stop_alert_identifies_its_side(self):
        f=fixture()
        for o in f['orders']:o['slPrice']='0'
        apply(self.p,facts(view(f)),NOW*1000)
        payloads=[json.loads(row[0])['text'] for row in self.p.db.execute('SELECT payload FROM outbox')]
        self.assertTrue(any('LONG BTCUSDT' in p for p in payloads));self.assertTrue(any('SHORT BTCUSDT' in p for p in payloads))
    def test_hourly_critical_reminder_and_new_evidence_recovery(self):
        f=fixture();f['orders'][0]['slPrice']='0';v=view(f);apply(self.p,facts(v),NOW*1000)
        apply(self.p,facts(v,NOW*1000+3600001),NOW*1000+3600001);self.assertEqual(self.count(),2)
        apply(self.p,facts(view(),NOW*1000+3600002),NOW*1000+3600002)
        self.assertEqual(self.p.db.execute("SELECT count(*) FROM incidents WHERE active=1").fetchone()[0],0)
    def test_failure_during_commit_rolls_back_memory_incidents_and_outbox(self):
        self.blind();before=self.p.producer('hedge_readonly');original=self.p.producer
        def denied(key,value=None):
            if value is not None:raise OSError('disk')
            return original(key)
        f=fixture();f['orders'][0]['slPrice']='0'
        with patch.object(self.p,'producer',side_effect=denied):
            with self.assertRaises(OSError):apply(self.p,facts(view(f),NOW*1000+1),NOW*1000+1)
        self.assertEqual(self.p.producer('hedge_readonly'),before);self.assertEqual(self.count(),1)
        self.assertEqual(self.p.db.execute("SELECT active FROM incidents WHERE id='guardian:private-read'").fetchone()[0],1)

class HostAndRenderTests(unittest.TestCase):
    def tearDown(self):host.shutdown()
    def test_disabled_no_thread_network_store_or_overlay(self):
        with patch.dict(os.environ,{},clear=True),patch.object(host,'Reader') as reader:
            host.install(Mock(config=Config()));reader.assert_not_called();self.assertIsNone(host._host)
    def test_install_failure_cannot_interrupt_guardian(self):
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True),patch.object(host,'Reader',side_effect=RuntimeError('PRIVATE_SECRET')):
            host.install(Mock(config=Config()));self.assertIsNone(host._host)
    def test_install_does_not_fetch_before_completed_guardian_cycle(self):
        reader=Mock()
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True),patch.object(host,'Reader',return_value=reader):
            host.install(Mock(config=Config()));reader.collect.assert_not_called();self.assertFalse(host._host.thread.is_alive())
    def test_intercept_failure_cannot_hide_critical(self):
        host._host=Mock(read=Mock(side_effect=RuntimeError('PRIVATE_SECRET')))
        g=Mock(config=Config());g.telegram.host=Mock(failed=False);g.telegram.host.ready.is_set.return_value=True
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True):self.assertFalse(host.intercept_ambiguous(g,'blind:3',{'cause':'AMBIGUOUS_POSITIONS'}))
    def test_any_execution_permission_disables_new_layer(self):
        for flag in ('GUARDIAN_CAPITAL_V2_ENABLED','GUARDIAN_CAPITAL_V2_EXECUTION','V8_LIVE_EXECUTION'):
            with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true',flag:'true'},clear=True):self.assertFalse(host.eligible(Config()))
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True):
            self.assertFalse(host.eligible(Config(mode='PROTECT')));self.assertFalse(host.eligible(Config(allow_sl=True)));self.assertFalse(host.eligible(Config(allow_close=True)))
    def test_queue_failure_has_own_incident_and_cannot_relabel_private_read(self):
        h=host.Host(Mock(collect=Mock(return_value=view())),clock=lambda:NOW);h.refresh();h.started=True;host._host=h
        g=Mock(config=Config(),command_snapshot=SnapshotCache());g.telegram.host.queue.put_nowait.side_effect=queue.Full
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True):host.after_cycle(g)
        value=g.telegram.host.fallback.submit.call_args.args[0]
        self.assertEqual(value['incident_id'],'guardian:hedge-notifications')
    def test_slow_reader_never_waited_by_after_cycle_or_guardian(self):
        gate=threading.Event();reader=Mock();reader.collect.side_effect=lambda:(gate.wait(2),view())[1]
        h=host.Host(reader,clock=lambda:NOW);host._host=h;h.thread.start();g=Mock(config=Config(),command_snapshot=SnapshotCache());g.telegram.host=None
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True):
            start=time.perf_counter()
            for _ in range(100):host.after_cycle(g)
            self.assertLess(time.perf_counter()-start,.3)
        gate.set();h.stop.set();h.thread.join(3)
    def test_cache_failure_and_clock_jump_never_reuse_last_good_as_fresh(self):
        reader=Mock();reader.collect.return_value=view();h=host.Host(reader,clock=lambda:NOW);h.refresh();self.assertTrue(h.read()['read_complete'])
        reader.collect.side_effect=RuntimeError('PRIVATE_SECRET');h.refresh();self.assertFalse(h.read()['read_complete']);self.assertNotIn('PRIVATE_SECRET',str(h.read()))
    def test_invalidating_old_inflight_snapshot_prevents_recovery(self):
        reader=Mock(collect=Mock(return_value=view()));h=host.Host(reader,clock=lambda:NOW);h.legacy('HTTP_FAILURE_OR_STALE');h.refresh();self.assertFalse(h.read()['read_complete'])
    def test_only_exact_ambiguity_and_complete_hedge_can_be_intercepted(self):
        first=view();first['completed_at']=NOW-1
        h=host.Host(Mock(collect=Mock(side_effect=[first,view()])),clock=lambda:NOW);h.refresh();h.refresh();host._host=h
        coordinator=Mock(failed=False);coordinator.ready.is_set.return_value=True;g=Mock(config=Config());g.telegram.host=coordinator
        with patch.dict(os.environ,{'GUARDIAN_HEDGE_READONLY_ENABLED':'true'},clear=True):
            self.assertTrue(host.intercept_ambiguous(g,'blind:3',{'cause':'AMBIGUOUS_POSITIONS'}))
            self.assertFalse(host.intercept_ambiguous(g,'blind:3',{'cause':'API_REJECTED_AUTH_OR_REQUEST'}))
            self.assertFalse(host.intercept_ambiguous(g,'blind:3',{'cause':'AMBIGUOUS_POSITIONS'}))
    def test_financial_consistency_requires_two_distinct_complete_reads(self):
        v=view();h=host.Host(Mock(collect=Mock(return_value=v)),clock=lambda:NOW)
        h.refresh();self.assertFalse(h.read()['consistency_confirmed'])
        h.refresh();self.assertFalse(h.read()['consistency_confirmed'])  # Same capture is not a second read.
        v['completed_at']=NOW+.1;h.clock=lambda:NOW+.1;h.refresh();self.assertTrue(h.read()['consistency_confirmed'])
    def test_overlay_keeps_old_commands_and_does_not_mutate_source(self):
        c=SnapshotCache();v=view();c.publish_readonly(v)
        self.assertIn('LONG',render_command('/position',c.read(),NOW));self.assertIn('SHORT',render_command('/position',c.read(),NOW))
        self.assertEqual(render_command('/status',c.read(),NOW),NO_DATA)
        v['positions'].clear();self.assertEqual(len(c.read()['hedge_readonly']['positions']),2)
    def test_render_stop_taxonomy_prices_ids_and_no_trading_authority(self):
        for status in ('ABSENT','INSUFFICIENT','UNVERIFIABLE','FULL_REGISTERED'):
            v=view();v['positions'][0]['coverage']['status']=status;text=render_view('/risk',v,NOW)
            self.assertIn('10001',text);self.assertIn('10002',text);self.assertIn('TRADE AUTHORITY: NONE',text);self.assertLess(len(text),4096)
    def test_render_stale_unknown_does_not_show_old_prices_or_secrets(self):
        self.assertNotIn('61,000',render_view('/risk',view(),NOW+31))
        self.assertNotIn('PRIVATE_TOKEN',render_view('/risk',{'read_complete':False,'error':'PRIVATE_TOKEN'},NOW))
    def test_exact_seams_preserve_protection_and_old_command_ast(self):
        from guardian_hedge_safety import normalize_readonly,strip_readonly
        for name in ('trade_guardian.py','guardian_commands.py'):
            old=subprocess.check_output(['git','show','5c6cc6a:'+name],cwd=ROOT).decode()
            current=(ROOT/name).read_text('utf-8');self.assertEqual(ast.dump(ast.parse(normalize_readonly(name,current))),ast.dump(ast.parse(old)))
        old=subprocess.check_output(['git','show','5c6cc6a:guardian_commands.py'],cwd=ROOT).decode()
        self.assertEqual(ast.dump(strip_readonly(ast.parse((ROOT/'guardian_commands.py').read_text('utf-8')))),ast.dump(ast.parse(old)))
    def test_guard_rejects_read_cache_copy_and_routing_edits(self):
        from guardian_hedge_safety import normalize_readonly
        source=(ROOT/'guardian_commands.py').read_text('utf-8')
        for before,after in (('value = copy.deepcopy(self._value)','value = self._value'),
                             ('copy.deepcopy(self._readonly_value)','self._readonly_value'),
                             ("('/position', '/risk')","('/position', '/close')")):
            self.assertIn(before,source)
            with self.assertRaises(AssertionError):normalize_readonly('guardian_commands.py',source.replace(before,after))
    def test_guard_rejects_protection_edits_not_just_hash_refreeze(self):
        from guardian_hedge_safety import normalize_readonly
        source=(ROOT/'trade_guardian.py').read_text('utf-8');changed=source.replace("details['state'] == 'EMERGENCY'","details['state'] == 'NORMAL'",1)
        self.assertNotEqual(normalize_readonly('trade_guardian.py',source),normalize_readonly('trade_guardian.py',changed))
    def test_get_only_source_and_passive_dependency_boundary(self):
        source=(ROOT/'guardian_hedge/client.py').read_text('utf-8');tree=ast.parse(source)
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr in ('post','put','delete','patch','request') for n in ast.walk(tree)))
        forbidden=('guardian_bitunix','guardian_capital_v2','guardian_risk','v8_executor','readiness','research')
        for p in (ROOT/'guardian_hedge').glob('*.py'):
            for n in ast.walk(ast.parse(p.read_text('utf-8'))):
                if isinstance(n,ast.ImportFrom):self.assertFalse((n.module or '').startswith(forbidden),p)
        # No new observer or read result can feed the existing mutation modules.
        for name in ('guardian_risk.py','guardian_bitunix.py','live_auto.py','main.py','guardian_capital_v2/controller.py','bitman_manual/readiness.py'):
            self.assertNotIn('guardian_hedge',(ROOT/name).read_text('utf-8'),name)

if __name__=='__main__':unittest.main()
