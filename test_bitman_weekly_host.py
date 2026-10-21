"""Passive host and optional manual context: no production IO in these tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

from bitman_weekly_forward import host,render
from bitman_manual.host import BitmanHost
from bitman_manual.render import render as core_render,unavailable,FOOTER
from test_bitman_readiness import ready_snapshot,current_example

ROOT=Path(__file__).resolve().parent
URL='http://bitman-market-data.railway.internal:8080/fapi/v1/klines'


def healthy():
    snapshot=json.loads((ROOT/'bitman_weekly_forward/bootstrap_manifest.json').read_text())['golden']
    return dict(status='HEALTHY',snapshot=snapshot,active=0,matured=0,horizons=dict.fromkeys(('1','2','3','4'),0),
                latest_event=None,updated_at=1000000)


def child(result):
    process=Mock(returncode=0);process.communicate.return_value=(json.dumps(result),'');process.poll.return_value=0
    return process


class PassiveHostTests(unittest.TestCase):
    def setUp(self):
        self.old=host._HOST;host._HOST=None;self.addCleanup(setattr,host,'_HOST',self.old)

    def test_default_disabled_no_thread_network_subprocess_or_storage(self):
        with patch.dict(os.environ,{},clear=True),patch.object(host,'WeeklyHost') as factory:
            host.after_cycle();self.assertIsNone(host.manual_context());host.shutdown()
        factory.assert_not_called()

    def test_enabled_starts_only_one_background_boundary_with_explicit_nonsecrets(self):
        worker=Mock()
        with patch.dict(os.environ,{host.FLAG:'true','BITMAN_MARKET_DATA_URL':URL,
                    'RAILWAY_GIT_COMMIT_SHA':'a'*40,'RAILWAY_VOLUME_MOUNT_PATH':'/data','TELEGRAM_TOKEN':'synthetic'},clear=True),\
             patch.object(host,'WeeklyHost',return_value=worker) as factory:
            for _ in range(100):host.after_cycle()
            self.assertEqual(host.manual_context(),worker.read.return_value)
        factory.assert_called_once_with('/data',URL,'a'*40);worker.start.assert_called_once()

    def test_thread_start_failure_can_retry_and_does_not_publish_broken_host(self):
        first=Mock();first.start.side_effect=RuntimeError();second=Mock()
        with patch.dict(os.environ,{host.FLAG:'true'},clear=True),patch.object(host,'WeeklyHost',side_effect=[first,second]):
            with self.assertRaises(RuntimeError):host.after_cycle()
            self.assertIsNone(host._HOST);host.after_cycle();self.assertIs(host._HOST,second)

    def test_credential_free_child_environment_and_request(self):
        secrets={'BITUNIX_API_KEY':'synthetic-secret','BITUNIX_SECRET':'synthetic-secret',
                 'TELEGRAM_BOT_TOKEN':'synthetic-secret','ACCOUNT_ID':'synthetic-private','HTTPS_PROXY':'http://synthetic',
                 'AUTO_TRADE':'true','BITMAN_MARKET_DATA_URL':URL,'PATH':os.environ.get('PATH','')}
        instance=host.WeeklyHost('/data',URL,'a'*40);process=child(healthy())
        with patch.dict(os.environ,secrets,clear=True),patch.object(host.subprocess,'Popen',return_value=process) as popen:
            instance.once()
        self.assertEqual(set(popen.call_args.kwargs['env']),{'PATH','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE'})
        request=json.loads(process.communicate.call_args.args[0])
        self.assertEqual(request,dict(storage_path='/data',market_data_url=URL,source_sha='a'*40))
        self.assertIn('bitman_weekly_forward.worker',popen.call_args.args[0])
        self.assertEqual(process.communicate.call_args.kwargs,{'timeout':60})

    def test_timeout_crash_and_bad_output_are_local_degraded_only(self):
        for failure in ('timeout','crash','json','oversize','unknown'):
            process=child(healthy())
            if failure=='timeout':process.communicate.side_effect=subprocess.TimeoutExpired('synthetic',60);process.poll.return_value=None
            elif failure=='crash':process.returncode=1
            elif failure=='json':process.communicate.return_value=('invalid','')
            elif failure=='oversize':process.communicate.return_value=('x'*32769,'')
            else:process.communicate.return_value=('{}','')
            instance=host.WeeklyHost('/data',URL,'a'*40)
            with patch.object(host.subprocess,'Popen',return_value=process):instance.once()
            self.assertEqual(instance.read()['status'],'DEGRADED')
            if failure=='timeout':process.kill.assert_called_once()

    def test_read_is_cache_only_copy_and_stale_unavailable(self):
        instance=host.WeeklyHost('/data',URL,'a'*40,clock=lambda:1000)
        instance._value=healthy();value=instance.read();value['snapshot']['bbwp']=99
        self.assertEqual(instance.read()['snapshot']['bbwp'],30)
        instance.clock=lambda:1661;self.assertEqual(instance.read(),{'status':'DEGRADED'})

    def test_shutdown_does_not_join_or_wait_for_worker(self):
        instance=host.WeeklyHost('/data',URL,'a'*40);instance._process=Mock();instance._process.poll.return_value=None
        instance.stop();instance._process.kill.assert_called_once();instance._process.communicate.assert_not_called()


class OptionalManualDisplay(unittest.TestCase):
    def test_disabled_preserves_exact_old_panel(self):
        panel=core_render(ready_snapshot());self.assertEqual(render.append_context(panel,None),panel)

    def test_optional_block_after_operability_and_before_full_safety_footer(self):
        for state in ('UP','DOWN','TRANSITION','CONFLICT'):
            panel=core_render(ready_snapshot(state));text=render.append_context(panel,healthy())
            self.assertEqual(text.replace('\n\n'+render.block(healthy()),'',1),panel)
            self.assertLess(text.index('OPERATIVA BITMAN'),text.index(render.HEADER))
            self.assertTrue(text.endswith(FOOTER));self.assertLess(len(text.encode('utf-16-le'))//2,3900)
            self.assertIn('NOT USED BY OPERABILITY',text)

    def test_bootstrap_block_has_no_advice_and_exact_proxy_context(self):
        text=render.block(healthy())
        for fragment in ('2026-10-19 00:00 UTC','GREEN','ABOVE ZERO','30.0','41.0','COOLING','STRICT: OTHER',
                         'LAG≤1: OTHER','LAG≤2: OTHER','Pending: NONE','0 active / 0 matured',
                         'EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN','EXACT BITMAN VOLATILITY PARITY: NOT PROVEN'):
            self.assertIn(fragment,text)
        for word in ('LONG','SHORT','BUY','SELL','ENTER','OPERAR','READY'):
            self.assertNotIn(word,text)

    def test_invalid_journal_exact_local_fallback_main_panel_survives(self):
        panel=core_render(current_example())
        extra=render.block({'status':'OBSERVER_JOURNAL_INVALID'})
        self.assertEqual(extra,render.HEADER+'\n⚠️ Journal no verificable\nResearch observer unavailable')
        text=render.append_context(panel,{'status':'OBSERVER_JOURNAL_INVALID'})
        self.assertIn('OPERATIVA BITMAN: NO OPERAR',text);self.assertNotIn('DATA TEMPORARILY UNAVAILABLE',text)

    def test_missing_stale_bad_state_do_not_break_manual_panel(self):
        panel=core_render(ready_snapshot())
        for view in ({},{'status':'STARTING'},{'status':'DEGRADED'},dict(healthy(),snapshot={})):
            text=render.append_context(panel,view)
            self.assertIn('Direction: UP',text);self.assertTrue(text.endswith(FOOTER))
            self.assertNotIn('DATA TEMPORARILY UNAVAILABLE',text)

    def test_manual_host_replies_once_even_if_optional_observer_read_raises(self):
        snapshot=ready_snapshot();payload=dict(ok=True,snapshot=snapshot,public_cache={})
        for side_effect in (None,RuntimeError('synthetic observer failure')):
            instance=BitmanHost(resolve_state=lambda:Path('/synthetic'),wall=lambda:0)
            reply=Mock()
            with patch('bitman_manual.host.subprocess.Popen',return_value=child(payload)),\
                 patch.object(host,'manual_context',return_value=healthy(),side_effect=side_effect):instance._run(reply)
            reply.assert_called_once();text=reply.call_args.args[0]
            self.assertIn('Direction: UP',text);self.assertNotIn('DATA TEMPORARILY UNAVAILABLE',text)

    def test_oversize_optional_block_omitted_without_replacing_existing_panel(self):
        panel='x'*3600+'\n\n⚠️ Directional research context\n'+FOOTER
        self.assertEqual(render.append_context(panel,healthy()),panel)
        text=render.append_context(unavailable(),healthy())
        self.assertEqual(text.replace('\n\n'+render.block(healthy()),'',1),unavailable())


if __name__=='__main__':unittest.main()
