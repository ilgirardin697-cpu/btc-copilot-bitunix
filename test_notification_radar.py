import ast
import copy
import hashlib
import hmac
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from igod_notifications.policy import Policy,identity,packed,validate,render
from igod_notifications.adapters import event,guardian_alert,v8_event,copilot_snapshot
from igod_notifications.runtime import Host,Proxy,emit,observer_sender,daily_automatic,settings
from igod_notifications import runtime,client
from igod_notifications.server import handler,signature

NOW=1800000000000


def opportunity(kind='PRE_LONG',at=NOW,opp='same-opportunity',**kw):
    side='SHORT' if kind=='PRE_SHORT' else 'LONG'
    data=dict(opportunity_id=opp,slot='same-slot',side=side,timeframe='15m',context={'4H':'BULL','1H':'BULL'},
        factors=['MOMENTUM','STRUCTURE'],pending=['Closed reclaim'],price_confirmed=kind=='CONFIRMED',closed=True)
    data.update(kw)
    return event('experimental_shadow',kind,at,'Cambio experimental',**data)


def critical(at=NOW,**kw):
    data=dict(incident_id='private-read',severity=3,material={'code':'PRIVATE_READ_UNVERIFIED'},text='No verificable')
    data.update(kw)
    return event('guardian','CRITICAL',at,'Incidente de seguridad',**data)


def drain(p,now=NOW):
    out=[]
    while True:
        row=p.next(now)
        if row is None:break
        out.append(json.loads(row['payload']));p.finish(row,True,now)
    return out


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Policy(self.temp.name);self.addCleanup(lambda:self.p.close())

    def test_100_identical_opportunities_one_notification(self):
        for i in range(100):self.p.ingest(opportunity(at=NOW+i),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+100)),1)

    def test_100_unchanged_evaluations_after_restart_not_repeated(self):
        self.p.ingest(opportunity(),NOW);self.assertEqual(len(drain(self.p)),1)
        self.p.close();self.p=Policy(self.temp.name)
        for i in range(100):self.p.ingest(opportunity(at=NOW+1000+i),NOW+2000)
        self.assertEqual(drain(self.p,NOW+2000),[])

    def test_100_same_critical_with_changing_price_text_one_message(self):
        for i in range(100):self.p.ingest(critical(at=NOW+i,text='Mark '+str(i)),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+100)),1)

    def test_observations_never_become_alerts(self):
        for i in range(100):self.p.ingest(event('mlrsi','OBSERVATION',NOW+i,'Neutral/WAIT'),NOW+i)
        self.assertEqual(drain(self.p,NOW+100),[])
        self.assertEqual(self.p.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],100)

    def test_confirm_requires_prior_pre(self):
        result=self.p.ingest(opportunity('CONFIRMED',NOW+1),NOW+1)
        self.assertEqual(result['decision'],'NO_PRIOR_PREALERT');self.assertEqual(drain(self.p,NOW+1),[])

    def test_invalidated_requires_prior_pre(self):
        self.p.ingest(opportunity('INVALIDATED',NOW+1),NOW+1)
        self.assertEqual(drain(self.p,NOW+1),[])

    def test_lifecycle_pre_confirm_invalid_once_and_in_order(self):
        for kind,t in [('PRE_LONG',NOW),('CONFIRMED',NOW+1),('CONFIRMED',NOW+2),('INVALIDATED',NOW+3),('PRE_LONG',NOW+4)]:
            self.p.ingest(opportunity(kind,t),t)
        self.assertEqual([x['kind'] for x in drain(self.p,NOW+5)],['PRE_LONG','CONFIRMED','INVALIDATED'])

    def test_two_sources_same_opp_coordinate(self):
        a=opportunity();b=opportunity(at=NOW+1);b['source']='manual_copilot';b['id']=identity(b)
        self.p.ingest(a,NOW);self.p.ingest(b,NOW+1)
        self.assertEqual(len(drain(self.p,NOW+1)),1)

    def test_new_id_same_active_slot_does_not_spam(self):
        for i in range(100):self.p.ingest(opportunity(at=NOW+i,opp='id-'+str(i)),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+100)),1)

    def test_single_indicator_not_confirmed_or_pre(self):
        for kind in ('PRE_LONG','CONFIRMED'):
            with self.assertRaisesRegex(ValueError,'ISOLATED'):self.p.ingest(opportunity(kind,factors=['AO']),NOW)

    def test_no_price_confirmation_rejected(self):
        with self.assertRaisesRegex(ValueError,'PRICE_CONFIRMATION'):self.p.ingest(opportunity('CONFIRMED',price_confirmed=False),NOW)

    def test_same_or_future_bar_rejected(self):
        self.p.ingest(opportunity(),NOW)
        self.p.ingest(opportunity('CONFIRMED'),NOW)
        self.assertEqual(len(drain(self.p)),1)
        with self.assertRaisesRegex(ValueError,'TIME'):self.p.ingest(opportunity(at=NOW+30001),NOW)

    def test_event_id_collision_rejected(self):
        a=opportunity();self.p.ingest(a,NOW);a['what_changed']='different'
        with self.assertRaisesRegex(ValueError,'COLLISION'):self.p.ingest(a,NOW)

    def test_critical_bypasses_silence_even_after_routine_flood(self):
        self.p.setting('silent',True)
        for i in range(100):self.p.ingest(opportunity(at=NOW+i,opp=str(i),slot=str(i)),NOW+i)
        self.p.ingest(critical(at=NOW+101),NOW+101)
        rows=drain(self.p,NOW+101);self.assertEqual([r['kind'] for r in rows],['CRITICAL'])

    def test_critical_priority_before_queued_opportunity(self):
        self.p.ingest(opportunity(),NOW);self.p.ingest(critical(at=NOW+1),NOW+1)
        self.assertEqual([r['kind'] for r in drain(self.p,NOW+1)],['CRITICAL','PRE_LONG'])

    def test_escalation_and_material_coverage_change_not_silenced(self):
        for i,(severity,material) in enumerate([(1,{'qty':1}),(2,{'qty':1}),(3,{'qty':1}),(3,{'qty':2})]):
            self.p.ingest(critical(at=NOW+i,severity=severity,material=material),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+4)),4)

    def test_restart_lower_stage_does_not_renotify_same_outage(self):
        self.p.ingest(guardian_alert('blind:3','No verificable',NOW),NOW);drain(self.p)
        self.p.close();self.p=Policy(self.temp.name)
        for i in (1,2,3):self.p.ingest(guardian_alert('blind:'+str(i),'No verificable',NOW+100+i),NOW+100+i)
        self.assertEqual(drain(self.p,NOW+200),[])

    def test_late_critical_does_not_resurrect_resolved_incident(self):
        self.p.ingest(guardian_alert('blind:3','err',NOW),NOW)
        self.p.ingest(guardian_alert('blind:recovered','ok',NOW+100),NOW+100)
        old=guardian_alert('blind:3','old packet',NOW+1)
        result=self.p.ingest(old,NOW+200)
        self.assertEqual(result['decision'],'STALE_INCIDENT_NO_RESURRECTION')
        self.assertEqual(len(drain(self.p,NOW+200)),2)

    def test_private_failure_cause_change_is_material_and_sanitized(self):
        for i,cause in enumerate(('AMBIGUOUS_POSITIONS','AMBIGUOUS_POSITIONS','PRIVATE_AUTH_FAILED')):
            self.p.ingest(guardian_alert('blind:3','unverified',NOW+i,{'cause':cause}),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+5)),2)
        self.assertEqual(guardian_alert('blind:3','',NOW,{'cause':'secret/token?123'})['material']['code'],'PRIVATE_READ_UNVERIFIED')

    def test_risk_improvement_is_a_material_change_not_mark_price_noise(self):
        for i,state in enumerate(('EMERGENCY','EMERGENCY','DANGER','NORMAL')):
            self.p.ingest(guardian_alert('risk:position123'+state,'risk '+str(i),NOW+i),NOW+i)
        self.assertEqual(len(drain(self.p,NOW+5)),3)

    def test_recovery_once_and_new_incident_again(self):
        self.p.ingest(guardian_alert('blind:3','err',NOW),NOW)
        self.p.ingest(guardian_alert('blind:recovered','ok',NOW+1),NOW+1)
        self.p.ingest(guardian_alert('blind:recovered','ok',NOW+2),NOW+2)
        self.p.ingest(guardian_alert('blind:1','err',NOW+3),NOW+3)
        self.assertEqual(len(drain(self.p,NOW+4)),3)

    def test_one_hour_reminder_is_secondary_not_filter(self):
        self.p.ingest(critical(),NOW);drain(self.p)
        self.p.ingest(critical(at=NOW+3599999),NOW+3599999);self.assertEqual(drain(self.p,NOW+3599999),[])
        self.p.ingest(critical(at=NOW+3600000),NOW+3600000);self.assertEqual(len(drain(self.p,NOW+3600000)),1)

    def test_failed_critical_is_retried_not_lost(self):
        self.p.ingest(critical(),NOW);r=self.p.next(NOW);self.p.finish(r,False,NOW)
        self.assertIsNone(self.p.next(NOW));self.assertIsNotNone(self.p.next(NOW+10000))

    def test_crash_send_ambiguity_critical_retry_opportunity_uncertain(self):
        self.p.ingest(opportunity(),NOW);self.p.ingest(critical(),NOW)
        c=self.p.next(NOW);o=self.p.next(NOW)
        self.assertIsNotNone(c);self.assertIsNotNone(o)
        self.p.close();self.p=Policy(self.temp.name)
        rows=drain(self.p);self.assertEqual([r['kind'] for r in rows],['CRITICAL'])

    def test_undelivered_pre_does_not_send_confirmation(self):
        self.p.ingest(opportunity(),NOW);p=self.p.next(NOW);self.p.finish(p,False,NOW)
        self.p.ingest(opportunity('CONFIRMED',NOW+1),NOW+1)
        self.assertEqual(drain(self.p,NOW+2),[])

    def test_second_writer_excluded_and_recovery_after_release(self):
        with self.assertRaisesRegex(ValueError,'WRITER_ALREADY'):Policy(self.temp.name)
        self.p.close();self.p=Policy(self.temp.name)

    def test_offline_opportunity_expires_but_critical_never_expires(self):
        self.p.ingest(opportunity(),NOW);self.p.ingest(critical(),NOW)
        self.assertEqual([e['kind'] for e in drain(self.p,NOW+1800001)],['CRITICAL'])

    def test_silence_survives_restart_manual_unchanged(self):
        self.p.setting('silent',True);self.p.close();self.p=Policy(self.temp.name)
        self.assertTrue(self.p.setting('silent'))

    def test_corrupt_database_never_silently_rebuilt(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'radar.sqlite3';p.write_bytes(b'broken-notification-store')
            with self.assertRaises(Exception):Policy(d)
            self.assertEqual(p.read_bytes(),b'broken-notification-store')


def snapshot(reference=NOW,quality='CAUTION',reason='WAIT_RECLAIM',**fields):
    data=dict(bias='LONG_ALLOWED',entry_quality=quality,entry_reason=reason,entry_level=100.,last_closed_1h=reference,
        market_levels={'reference_time':reference},trend4='BULL',trend1='BULL',momentum='GREEN',structure='BULLISH',flow='BUY')
    data.update(fields);return dict(data=data)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Policy(self.temp.name);self.addCleanup(lambda:self.p.close())

    def process(self,s,now):
        for e in copilot_snapshot(self.p,s,now):self.p.ingest(e,now)

    def test_100_existing_analyses_only_one_pre(self):
        for i in range(100):self.process(snapshot(NOW+i),NOW+i)
        self.assertEqual([e['kind'] for e in drain(self.p,NOW+100)],['PRE_LONG'])

    def test_mapper_restart_and_later_existing_reclaim(self):
        self.process(snapshot(),NOW);drain(self.p)
        self.p.close();self.p=Policy(self.temp.name)
        self.process(snapshot(NOW+900000,'GOOD','CONFIRMED_RECLAIM'),NOW+900000)
        self.assertEqual([e['kind'] for e in drain(self.p,NOW+900000)],['CONFIRMED'])

    def test_already_confirmed_bootstrap_not_invent_prior_pre(self):
        self.process(snapshot(quality='GOOD',reason='CONFIRMED_RECLAIM'),NOW)
        self.assertEqual(drain(self.p),[])

    def test_wait_neutral_and_stale_no_new_pre(self):
        for bias in ('WAIT','UNKNOWN'):
            self.process(snapshot(bias=bias),NOW)
        self.process(snapshot(NOW-1800000),NOW)
        self.assertEqual(drain(self.p),[])

    def test_real_context_invalidation_only_after_pre(self):
        self.process(snapshot(),NOW);self.process(snapshot(NOW+900000,bias='WAIT'),NOW+900000)
        self.assertEqual([e['kind'] for e in drain(self.p,NOW+900000)],['PRE_LONG','INVALIDATED'])

    def test_short_symmetry(self):
        self.process(snapshot(bias='SHORT_ALLOWED',trend4='BEAR',trend1='BEAR',momentum='RED',structure='BEARISH',flow='SELL'),NOW)
        self.assertEqual(drain(self.p)[0]['kind'],'PRE_SHORT')

    def test_waits_and_startup_suppressed_criticals_retained(self):
        for key in ('copilot:WAIT:CAUTION','startup:123','aligned:pWAIT','conflict:pLONG_ALLOWED','new:p'):
            self.assertEqual(guardian_alert(key,'routine',NOW)['kind'],'OBSERVATION')
        for key in ('blind:3','risk:pEMERGENCY','tpsl:p','unresolved:p','lockout:p'):
            self.assertEqual(guardian_alert(key,'critical',NOW)['kind'],'CRITICAL')

    def test_tpsl_quantity_change_preserved_without_price_noise(self):
        for i,orders in enumerate(('qty1','qty1','qty2')):
            e=guardian_alert('tpsl:p','mark '+str(i),NOW+i,{'orders':orders,'target':90.,'risk':'WARNING'})
            self.p.ingest(e,NOW+i)
        self.assertEqual(len(drain(self.p,NOW+3)),2)

    def test_v8_routine_disarmed_flat_never_confirmed(self):
        for text in ('V8 SIGNAL LONG','V8 SIGNAL SHORT','V8 SIGNAL FLAT','V8 REAL DISARMED','V8 REAL BLOCKED — V8_LIVE_EXECUTION=false or DISARM'):
            self.assertEqual(v8_event(text,NOW)['kind'],'OBSERVATION')
        self.assertEqual(v8_event('V8 REAL BLOCKED — unresolved order',NOW)['kind'],'CRITICAL')

    def test_renderer_has_context_pending_and_no_order_authority(self):
        text=render(opportunity())
        for token in ('PRE-LONG','4H','1H','Pendiente','NO ES UNA ORDEN','TRADE AUTHORITY: NONE'):self.assertIn(token,text)
        self.assertLess(len(text),4096)
        self.assertIn('no verifica un stop',render(critical()))


class RuntimeTests(unittest.TestCase):
    def make(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        original=Mock();original._recipients=['owner'];original._deliver.return_value=True;original.send.return_value=True
        h=Host(original,temp.name,clock=lambda:NOW/1000);h.start();self.assertTrue(h.ready.wait(3))
        def cleanup():
            h.stop.set();h.thread.join(timeout=5)
        self.addCleanup(cleanup)
        return h,original

    def test_100_submissions_do_not_wait_for_sender(self):
        h,original=self.make();blocked=threading.Event()
        original._deliver.side_effect=lambda *args:blocked.wait(2) or True
        start=time.monotonic()
        for i in range(100):h.submit(critical(at=NOW+i))
        self.assertLess(time.monotonic()-start,.5)
        blocked.set();self.assertTrue(h.rpc('settings',None) is False)

    def test_proxy_manual_replies_bypass_silence_and_policy(self):
        h,old=self.make();h.rpc('settings',True)
        p=Proxy(old,h);p.send_owner('/diario answer')
        old.send_owner.assert_called_once_with('/diario answer')

    def test_manual_silence_can_be_reversed_without_touching_safety(self):
        h,old=self.make();reply=Mock()
        with patch.object(runtime,'_host',h),patch.object(runtime,'enabled',return_value=True):
            self.assertTrue(settings('/silencio',reply));self.assertTrue(h.rpc('settings',None))
            self.assertTrue(settings('/silencio off',reply));self.assertFalse(h.rpc('settings',None))
            self.assertFalse(settings('/diario',reply));self.assertFalse(settings('/bitman',reply))
            self.assertFalse(settings('/resumen',reply));self.assertFalse(settings('/niveles',reply))
        self.assertIn('SIEMPRE ACTIVA',reply.call_args.args[0])

    def test_observer_neutral_not_telegram(self):
        h,old=self.make();p=Proxy(old,h);p.send_observation('ML RSI NEUTRAL')
        h.rpc('settings',None)
        old._deliver.assert_not_called()

    def test_logging_failure_never_stops_critical(self):
        h,old=self.make()
        with patch('builtins.print',side_effect=OSError('secret-canary')):
            h.submit(critical());h.rpc('settings',None)
        self.assertTrue(h.thread.is_alive())

    def test_disabled_is_silent_no_threads_db_or_network(self):
        with patch.dict(os.environ,{},clear=True),patch.object(runtime,'Host') as cls:
            runtime.install(Mock());self.assertFalse(runtime.enabled());cls.assert_not_called()
            f=Mock(return_value=True);self.assertTrue(daily_automatic(f,'daily'));f.assert_called_once_with('daily')

    def test_failed_host_critical_fallback_not_routine(self):
        h,old=self.make();h.failed=True
        h.submit(critical());h.submit(event('mlrsi','OBSERVATION',NOW,'neutral'))
        old.send.assert_called_once()

    def test_remote_private_url_no_arbitrary_host(self):
        self.assertEqual(client.valid_url(client.URL),client.URL)
        for url in ('https://evil.test/events','http://localhost:8091/events',client.URL+'?url=http://evil',client.URL.replace('/events','/orders')):
            with self.assertRaises(ValueError):client.valid_url(url)

    def test_queue_full_keeps_critical_fallback(self):
        h,old=self.make()
        with patch.object(h.queue,'put_nowait',side_effect=queue.Full):
            self.assertTrue(h.submit(critical()))
            self.assertFalse(h.submit(event('mlrsi','OBSERVATION',NOW,'neutral')))
        old.send.assert_called_once()

    def test_no_telegram_secret_in_sanitized_diagnostic(self):
        with patch('builtins.print') as log:
            runtime.diagnostic('IGOD_NOTIFICATION_PROCESSED')
        self.assertNotIn('secret',str(log.call_args).lower())


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        old=Mock();old._recipients=['owner'];old._deliver.return_value=True
        self.h=Host(old,self.temp.name,clock=lambda:NOW/1000);self.h.start();self.assertTrue(self.h.ready.wait(3))
        self.addCleanup(self.cleanup_host)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.h,'test-only-key'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def cleanup_host(self):
        self.h.stop.set();self.h.thread.join(timeout=3)

    def request(self,value,path='/events',signed=True):
        raw=packed(value).encode();headers={'Content-Type':'application/json'}
        if signed:headers['X-IGOD-Signature']=signature('test-only-key',raw)
        req=Request('http://127.0.0.1:'+str(self.server.server_port)+path,data=raw,headers=headers,method='POST')
        with urlopen(req,timeout=3) as response:return json.load(response)

    def test_authenticated_v8_two_retries_one_durable_event(self):
        value=v8_event('V8 REAL BLOCKED — unresolved order',NOW)
        first=self.request(value);again=self.request(value)
        self.assertTrue(first['ok']);self.assertTrue(again['duplicate'])
        self.assertEqual(first['record_id'],value['id'])

    def test_missing_auth_rejected(self):
        with self.assertRaises(HTTPError) as err:self.request(v8_event('V8 SIGNAL FLAT',NOW),signed=False)
        self.assertEqual(err.exception.code,401)

    def test_remote_cannot_impersonate_manual_or_inject_order(self):
        with self.assertRaises(HTTPError) as err:self.request(opportunity())
        self.assertEqual(err.exception.code,403)
        with self.assertRaises(HTTPError) as err:self.request(v8_event('V8 SIGNAL FLAT',NOW),path='/order')
        self.assertEqual(err.exception.code,404)


class ArchitectureTests(unittest.TestCase):
    def test_shared_sdk_hashes_are_reviewed_not_silently_different(self):
        root=Path(__file__).resolve().parent/'igod_notifications'
        hashes=json.loads((root/'sdk_hashes.json').read_text('utf-8'))
        for name,digest in hashes.items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest)

    def test_no_trading_account_or_research_imports(self):
        root=Path(__file__).resolve().parent
        forbidden=('guardian_bitunix','guardian_risk','live_auto','research','v8_executor','guardian_capital_v2')
        for path in (root/'igod_notifications').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text('utf-8'))):
                if isinstance(node,ast.ImportFrom):self.assertFalse((node.module or '').startswith(forbidden),path)
                if isinstance(node,ast.Import):
                    for alias in node.names:self.assertFalse(alias.name.startswith(forbidden),path)
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    self.assertNotIn('BITUNIX_API_',node.value)
                    self.assertNotIn('/futures/trade/',node.value)

    def test_guardian_risk_and_math_sources_unchanged(self):
        root=Path(__file__).resolve().parent
        files=subprocess.check_output(['git','ls-tree','-r','--name-only','9d40020d539033cefb8f01734db8c6a6fdbba2e3'],cwd=root,text=True).splitlines()
        for name in files:
            if name.startswith(('guardian_capital_v2/','bitman_manual/frozen/','bitman_weekly_forward/')) or name in ('guardian_signals.py','guardian_risk.py','guardian_bitunix.py','guardian_telegram.py','mlrsi_math.py','mlrsi_observer.py','mlrsi_public.py','guardian_commands.py','live_auto.py','trend_v8.py'):
                old=subprocess.check_output(['git','show','9d40020d539033cefb8f01734db8c6a6fdbba2e3:'+name],cwd=root)
                self.assertEqual((root/name).read_bytes().replace(b'\r\n',b'\n'),old.replace(b'\r\n',b'\n'),name)

    def test_exact_notification_normalization_and_no_risk_escape(self):
        from notification_safety import normalize_notifications
        root=Path(__file__).resolve().parent
        old=subprocess.check_output(['git','show','9d40020d539033cefb8f01734db8c6a6fdbba2e3:trade_guardian.py'],cwd=root,text=True,encoding='utf-8')
        current=(root/'trade_guardian.py').read_text('utf-8')
        self.assertEqual(ast.dump(ast.parse(normalize_notifications('trade_guardian.py',current))),ast.dump(ast.parse(old)))
        changed=current.replace("details['state'] == 'EMERGENCY'","details['state'] == 'NORMAL'",1)
        self.assertNotEqual(ast.dump(ast.parse(normalize_notifications('trade_guardian.py',changed))),ast.dump(ast.parse(old)))


if __name__=='__main__':unittest.main()
