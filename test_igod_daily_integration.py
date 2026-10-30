import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from http.server import ThreadingHTTPServer
import threading
from unittest.mock import Mock, patch
try:
    import requests
except ImportError:
    raise unittest.SkipTest('Daily workflow installs requests and tzdata') from None

from test_igod_daily_plan import ASOF, history, synth
from igod_daily_plan.core import normalize
from igod_daily_plan.cycle import cycle_series
from igod_daily_plan.render import render, FOOTER
from igod_daily_plan.service import Planner, handler
from igod_daily_plan.state import State
from daily_plan_guardian import DailyPlanBridge
from daily_plan_safety import normalize_router, strip_router


def millis(year,month,day,hour,minute=0):
    return int(datetime(year,month,day,hour,minute,tzinfo=timezone.utc).timestamp()*1000)


def plan(now=ASOF, bias='WAIT'):
    return dict(bias=bias,asof_utc=datetime.fromtimestamp(now/1000,timezone.utc).isoformat(),
                source='BINANCE_USDM_PERPETUAL',entries=[],targets=[],risk=None)


class PlanAgeRegressionTests(unittest.TestCase):
    """Software fixtures, not independent market or TradingView evidence."""
    def setUp(self):
        indicators=dict(closed_at=plan()['asof_utc'],ao=10,ao_previous=9,
                        adx=22,adx_previous=21,plus_di=30,minus_di=10,
                        bbwp_previous=20,bbwp=25)
        self.value=dict(plan(),indicators={'weekly':indicators,'daily':indicators},
                        structural_levels={'supports':[{'price':100}],
                                           'resistances':[{'price':120}]},
                        reference_closed_at_utc=plan(ASOF-60_000)['asof_utc'])

    def assert_fresh(self, elapsed_ms, minutes):
        for mode in ('full','summary','levels'):
            with self.subTest(mode=mode):
                text=render(self.value,mode,ASOF+elapsed_ms)
                self.assertNotIn('desactualizado',text)
                self.assertIn(f'cálculo hace {minutes} min',text)
                self.assertIn('BINANCE_USDM_PERPETUAL',text)
                self.assertTrue(text.endswith(FOOTER))
                if mode=='full':
                    for label in ('AO 10.00','ADX 22.00','+DI 30.00','BBWP proxy'):
                        self.assertIn(label,text)
                if mode!='summary':
                    self.assertIn('SOPORTES: 100.00',text)
                    self.assertIn('RESISTENCIAS: 120.00',text)

    def test_plan_30_seconds_old_is_fresh_and_displays_zero_minutes(self):
        self.assert_fresh(30_000,0)

    def test_plan_one_minute_old_is_fresh(self):
        self.assert_fresh(60_000,1)

    def test_plan_19_minutes_old_is_fresh(self):
        self.assert_fresh(19*60_000,19)

    def test_plan_21_minutes_old_is_stale_and_hides_prices(self):
        for mode in ('full','summary','levels'):
            with self.subTest(mode=mode):
                text=render(self.value,mode,ASOF+21*60_000)
                self.assertIn('Plan desactualizado',text)
                self.assertIn('ESPERAR',text)
                for field in ('AO 10.00','100.00','120.00'):
                    self.assertNotIn(field,text)
                self.assertTrue(text.endswith(FOOTER))

    def test_reference_candle_age_is_also_in_minutes(self):
        text=render(self.value,now_ms=ASOF+60_000)
        self.assertIn('· hace 2 min',text)

    def test_future_plan_still_fails_closed(self):
        self.assertIn('Plan desactualizado',render(self.value,now_ms=ASOF-1))

    def test_unavailable_hides_even_injected_indicators_and_levels(self):
        for mode in ('full','summary','levels'):
            text=render(dict(self.value,bias='UNKNOWN'),mode,ASOF+30_000)
            self.assertIn('ESPERAR',text)
            for field in ('AO 10.00','100.00','120.00'):
                self.assertNotIn(field,text)

    def test_all_four_commands_with_realistic_calculation_latency(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=[ASOF]
            def calculate(now):
                clock[0]+=30_000  # Fetch/compute takes time after asof is recorded.
                return dict(self.value,asof_utc=plan(now)['asof_utc'])
            p=Planner(directory,clock=lambda:clock[0]/1000,calculator=calculate)
            try:
                for identifier,command in enumerate(('/diario','/resumen','/niveles','/alertas'),1):
                    response=p.command(command,identifier)
                    self.assertTrue(response['deliver'])
                    self.assertNotIn('desactualizado',response['text'])
                    if command=='/alertas':
                        self.assertIn('AVISOS DEL PLAN DIARIO',response['text'])
                    else:
                        self.assertIn('cálculo hace 0 min',response['text'])
                self.assertFalse(p.command('/diario',1)['deliver'])
            finally:
                p.state.close()

    def test_cache_uses_15_minutes_not_15_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=[ASOF]
            calculator=Mock(side_effect=lambda now:plan(now))
            p=Planner(directory,clock=lambda:clock[0]/1000,calculator=calculator)
            try:
                p.plan()
                clock[0]=ASOF+15*60_000-1
                p.plan()
                self.assertEqual(calculator.call_count,1)
                clock[0]+=1
                p.plan()
                self.assertEqual(calculator.call_count,2)
            finally:
                p.state.close()

    def test_silence_duration_is_stored_in_milliseconds(self):
        with tempfile.TemporaryDirectory() as directory:
            state=State(directory,ASOF)
            try:
                state.settings('/silencio 2',ASOF)
                self.assertEqual(state.get('preferences')['silent_until'],ASOF+120_000)
            finally:
                state.close()


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s=State(self.tmp.name,ASOF)
        self.addCleanup(lambda:self.s.close())

    def prefs(self,**values):
        p=self.s.get('preferences');p.update(values);self.s.put('preferences',p)

    def test_defaults_off(self):
        self.assertFalse(self.s.get('preferences')['daily'])
        self.assertIsNone(self.s.due(plan(),millis(2026,10,30,7)))

    def test_daily_0800_madrid_and_dedupe(self):
        self.prefs(daily=True)
        now=millis(2026,10,30,7)
        self.assertEqual(self.s.due(plan(now),now),'daily:2026-10-30')
        self.assertIsNone(self.s.due(plan(now),now))

    def test_DST_before_and_after_transition(self):
        self.prefs(daily=True)
        for day,hour in ((24,6),(25,7)):
            now=millis(2026,10,day,hour)
            self.assertEqual(self.s.due(plan(now),now),'daily:2026-10-'+str(day))

    def test_no_catchup_late_day(self):
        self.prefs(daily=True)
        now=millis(2026,10,30,12)
        self.assertIsNone(self.s.due(plan(now),now))

    def test_no_regular_night_messages(self):
        self.prefs(daily=True,changes=True,night=True)
        now=millis(2026,10,30,1)
        self.s.put('auto_baseline','old')
        self.assertIsNone(self.s.due(plan(now),now))

    def test_silence_persists(self):
        self.s.settings('/silencio',ASOF)
        self.s.close();self.s=State(self.tmp.name,ASOF+1000)
        self.assertEqual(self.s.get('preferences')['silent_until'],-1)

    def test_settings_do_not_enable_critical_or_night_implicitly(self):
        self.s.settings('/alertas on',ASOF)
        p=self.s.get('preferences')
        self.assertTrue(p['daily']);self.assertFalse(p['critical']);self.assertFalse(p['night'])

    def test_invalid_hour_does_not_mutate(self):
        before=self.s.get('preferences')
        self.assertIn('inválida',self.s.settings('/alertas hora 99:00',ASOF))
        self.assertEqual(self.s.get('preferences'),before)

    def test_scenario_frequency_limit(self):
        self.prefs(changes=True)
        now=millis(2026,10,30,12)
        self.s.put('auto_baseline','old')
        self.assertTrue(self.s.due(plan(now,'WATCH_LONG'),now))
        self.assertIsNone(self.s.due(plan(now+60_000,'WATCH_SHORT'),now+60_000))

    def test_unknown_never_alerts(self):
        self.prefs(daily=True,changes=True,critical=True,night=True)
        self.assertIsNone(self.s.due(plan(ASOF,'UNKNOWN'),ASOF))

    def test_critical_only_with_explicit_night_optin(self):
        now=millis(2026,10,30,1)
        self.s.put('prior_plan',dict(bias='SCENARIO_LONG',asof_utc='previous',
                                    invalidation={'hard_stop_both_legs':100}))
        new=dict(plan(now),reference_close_15m=90)
        self.prefs(critical=True)
        self.assertIsNone(self.s.due(new,now))
        self.prefs(critical=True,night=True)
        self.assertTrue(self.s.due(new,now).startswith('critical:'))
        self.assertIsNone(self.s.due(new,now))


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Planner(self.tmp.name,clock=lambda:ASOF/1000,calculator=lambda now:plan(now))
        self.addCleanup(lambda:self.p.state.close())

    def test_manual_works_while_silent(self):
        self.p.command('/silencio',1)
        for i,command in enumerate(('/diario','/resumen','/niveles'),2):
            response=self.p.command(command,i)
            self.assertTrue(response['deliver'])
            self.assertIn('ESPERAR',response['text'])

    def test_manual_update_dedupe_after_restart(self):
        self.assertTrue(self.p.command('/diario',10)['deliver'])
        self.p.state.close()
        self.p=Planner(self.tmp.name,clock=lambda:ASOF/1000,calculator=lambda now:plan(now))
        self.assertFalse(self.p.command('/diario',10)['deliver'])
        self.assertTrue(self.p.command('/diario',11)['deliver'])

    def test_one_diagnostic_ever(self):
        self.p.diagnostic=True
        self.assertEqual(self.p.notification()['id'],'DEPLOYMENT_TEST_V1')
        self.assertFalse(self.p.notification()['deliver'])

    def test_prospective_does_not_import_warmup_events_or_mature_early(self):
        cycle=dict(available_at=ASOF-86400_000,phase='ACELERACIÓN',pressure='SHORT')
        one=dict(plan(),cycle=cycle,daily_recent_closed=[dict(close_ts=ASOF-86400_000,c=100)])
        self.p.state.observe(one,ASOF)
        self.assertEqual(self.p.state.db.execute('SELECT count(*) FROM phase_events').fetchone()[0],0)
        later=ASOF+86400_000
        two=dict(plan(later),cycle=dict(cycle,available_at=later,phase='AGOTAMIENTO'),daily_recent_closed=[dict(close_ts=later,c=90)])
        self.p.state.observe(two,later+5000)
        self.assertEqual(self.p.state.db.execute('SELECT count(*) FROM phase_events').fetchone()[0],1)
        self.assertEqual(self.p.state.db.execute('SELECT count(*) FROM phase_outcomes').fetchone()[0],0)
        self.p.state.observe(two,later+6000)
        self.assertEqual(self.p.state.db.execute('SELECT count(*) FROM phase_events').fetchone()[0],1)

    def test_outcomes_start_at_actual_observation_and_mature_once(self):
        day=86400_000
        old=dict(plan(),cycle=dict(available_at=ASOF-day,phase='ACELERACIÓN',pressure='LONG'),
                 daily_recent_closed=[dict(close_ts=ASOF-day,c=100)])
        self.p.state.observe(old,ASOF)
        event_time=ASOF+day
        event=dict(plan(event_time+5000),reference_close_15m=100,
                   cycle=dict(available_at=event_time,phase='AGOTAMIENTO',pressure='LONG'),
                   daily_recent_closed=[dict(close_ts=event_time,c=100)])
        self.p.state.observe(event,event_time+5000)
        future=dict(event,reference_close_15m=110,
                    reference_closed_at_utc=datetime.fromtimestamp((event_time+day+900000)/1000,timezone.utc).isoformat())
        self.p.state.observe(future,event_time+day+900001)
        self.p.state.observe(future,event_time+day+900002)
        results=self.p.state.db.execute('SELECT horizon,payload FROM phase_outcomes').fetchall()
        self.assertEqual(len(results),1)
        self.assertEqual(results[0][0],1)
        self.assertIsNone(json.loads(results[0][1])['signed_return'])

    def test_protocol_change_rejected(self):
        with patch('igod_daily_plan.service.hashlib.sha256') as h:
            h.return_value.hexdigest.return_value='different'
            with self.assertRaisesRegex(ValueError,'PROTOCOL_CHANGED'):
                Planner(self.tmp.name,clock=lambda:ASOF/1000)

    def test_no_invented_levels_unknown(self):
        text=render(dict(plan(),bias='UNKNOWN'),now_ms=ASOF)
        self.assertIn('ESPERAR',text)
        self.assertNotIn('140',text)
        self.assertNotIn('ENTRADA A:',text)

    def test_stale_fails_closed(self):
        self.assertIn('desactualizado',render(plan(),now_ms=ASOF+21*60_000))

    def test_render_footer_and_limit(self):
        self.assertLess(len(render(plan(),now_ms=ASOF)),3900)
        self.assertTrue(render(plan(),now_ms=ASOF).endswith(FOOTER))

    def test_long_message_preserves_safety_footer(self):
        text=render(dict(plan(),reason_no_trade='x'*5000),now_ms=ASOF)
        self.assertLessEqual(len(text),3900)
        self.assertTrue(text.endswith(FOOTER))

    def test_broken_logger_does_not_break_plan(self):
        with patch('builtins.print',side_effect=OSError('unavailable stdout')):
            self.assertEqual(self.p.plan(refresh=True)['bias'],'WAIT')

    def test_technical_diagnostic_never_sends_at_night(self):
        self.p.diagnostic=True
        self.p.clock=lambda:millis(2026,10,30,22)/1000
        self.assertFalse(self.p.notification()['deliver'])


class CycleTests(unittest.TestCase):
    def test_prefix_invariance_real_formula(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        prefix=cycle_series(rows[:-1])
        self.assertEqual(prefix,cycle_series(rows)[:-1])

    def test_never_uses_future_pivots(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        before=cycle_series(rows)
        changed=copy.deepcopy(rows)
        changed[-1]['c']*=2;changed[-1]['h']=changed[-1]['c']+10
        self.assertEqual(before[:-1],cycle_series(changed)[:-1])

    def test_symmetric_start_after_ADX_floor(self):
        for side in (1,-1):
            rows=[dict(h=h,l=l,c=c,close_ts=ASOF+i*86400_000) for i,(h,l,c) in enumerate(
                [(101,99,100),(102,100,101),(110,100,105),(103,99,101),(102,98,100),(101,97,99),(120,100,119)])]
            if side==-1:
                rows=[dict(r,h=200-r['l'],l=200-r['h'],c=200-r['c']) for r in rows]
            values=[side*v for v in (1,1,.8,.7,.6,.5,.9)]
            adx=[dict(adx=v,plus_di=30 if side==1 else 10,minus_di=10 if side==1 else 30) for v in (30,29,28,27,26,25,26)]
            with patch('igod_daily_plan.cycle.ao_series',return_value=values),patch('igod_daily_plan.cycle.adx_series',return_value=adx),patch('igod_daily_plan.cycle.bbwp_series',return_value=[(30,30)]*6+[(35,31)]):
                result=cycle_series(rows)[-1]
            self.assertEqual(result['phase'],'POSIBLE INICIO')
            self.assertEqual(result['pressure'],'LONG' if side==1 else 'SHORT')
            self.assertGreaterEqual(result['prior_nonrising_days'],3)

    def test_no_direction_inferred_from_ADX_alone(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        result=cycle_series(rows)[-1]
        self.assertIn(result['phase'],('COMPRESIÓN','POSIBLE INICIO','ACELERACIÓN','AGOTAMIENTO','POSIBLE REVERSIÓN','INDETERMINADO'))
        self.assertEqual(result['interpretation'],'HYPOTHESIS — NOT VALIDATED')


class BridgeTests(unittest.TestCase):
    def test_real_private_HTTP_path_sends_once_through_existing_callback(self):
        with tempfile.TemporaryDirectory() as d:
            p=Planner(d,clock=lambda:ASOF/1000,calculator=lambda now:plan(now))
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(p))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            reply=Mock(return_value=True)
            b=DailyPlanBridge(reply,url='http://igod-daily-plan.railway.internal:8080')
            # Only the test substitutes loopback; production constructor rejects it.
            b.url='http://127.0.0.1:'+str(server.server_port)
            try:
                body=dict(command='/diario',update_id=1234)
                b.exchange('/command',body);b.exchange('/command',body)
                self.assertEqual(reply.call_count,1)
                self.assertIn('ESPERAR',reply.call_args.args[0])
            finally:
                server.shutdown();server.server_close();p.state.close()

    def test_bot_suffix_preserved_by_original_router(self):
        b=DailyPlanBridge(Mock(return_value=True),url='http://igod-daily-plan.railway.internal:8080')
        with patch.object(b,'start'):
            self.assertTrue(b.request('/diario@existing_bot',987))
        self.assertEqual(b.queue.get_nowait(),('/diario',987))

    def test_owner_filter_applies_before_daily_bridge(self):
        from guardian_commands import TelegramCommands,SnapshotCache
        reply=Mock(return_value=True)
        commands=TelegramCommands('test','owner',SnapshotCache(),reply,enabled=True)
        daily=Mock(return_value=True)
        commands._request_daily=daily
        for name in ('/diario','/resumen','/niveles','/alertas','/silencio'):
            self.assertFalse(commands.process(dict(update_id=12,message=dict(chat=dict(id='stranger'),text=name))))
            self.assertTrue(commands.process(dict(update_id=12,message=dict(chat=dict(id='owner'),text=name))))
        self.assertEqual(daily.call_count,5)

    def test_arbitrary_url_rejected(self):
        for url in ('https://evil.invalid','http://igod-daily-plan.railway.internal:8080@evil.invalid','http://igod-daily-plan.railway.internal:8080/private'):
            with self.assertRaises(ValueError):
                DailyPlanBridge(Mock(),url=url)

    def test_disabled_has_no_threads_or_network(self):
        reply=Mock(return_value=True);http=Mock()
        b=DailyPlanBridge(reply,url='',transport=http)
        b.start();self.assertIsNone(b.thread)
        self.assertTrue(b.request('/diario',1))
        http.post.assert_not_called()

    def test_existing_reply_callback_once_and_no_token(self):
        reply=Mock(return_value=True);http=Mock()
        response=http.post.return_value
        response.status_code=200;response.content=b'ok'
        response.json.return_value={'deliver':True,'text':'ESPERAR'}
        b=DailyPlanBridge(reply,url='http://igod-daily-plan.railway.internal:8080',transport=http)
        with patch('builtins.print',side_effect=OSError('broken logger')):
            b.exchange('/command',{'command':'/diario','update_id':1})
        reply.assert_called_once_with('ESPERAR')
        self.assertFalse(hasattr(b,'token'))
        self.assertFalse(http.post.call_args.kwargs['allow_redirects'])

    def test_no_second_Telegram_receiver_or_sender(self):
        for file in ('daily_plan_guardian.py','igod_daily_plan/service.py'):
            text=Path(file).read_text('utf-8')
            self.assertNotIn('getUpdates',text);self.assertNotIn('setWebhook',text)
            self.assertNotIn('api.telegram.org',text)

    def test_exact_router_normalization_retains_owner_and_old_commands(self):
        manifest=json.loads(Path('daily_router_extension.json').read_text())
        source=Path('guardian_commands.py').read_text('utf-8')
        restored=normalize_router(source)
        self.assertNotIn('DAILY_COMMANDS',restored)
        self.assertIn("!= self._owner",restored)
        self.assertIn("command == '/bitman'",restored)
        altered=source.replace('!= self._owner','== self._owner')
        self.assertNotEqual(normalize_router(altered),restored)
        self.assertNotEqual(ast.dump(strip_router(ast.parse(altered))),ast.dump(ast.parse(restored)))


if __name__=='__main__':
    unittest.main()
