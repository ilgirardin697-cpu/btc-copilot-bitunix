import ast
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
import v8_executor
from notification_v8_safety import normalize_relay_tree
from igod_notifications import client
from igod_notifications.adapters import v8_event


class RelayTests(unittest.TestCase):
    def test_shared_sdk_hashes_are_exact(self):
        root=Path(__file__).resolve().parent/'igod_notifications'
        for name,digest in json.loads((root/'sdk_hashes.json').read_text('utf-8')).items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest)

    def test_original_v8_ast_preserved_after_exact_presentation_removal(self):
        root=Path(__file__).resolve().parent
        old=subprocess.check_output(['git','show','724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6:v8_executor.py'],cwd=root).decode('utf-8')
        now=(root/'v8_executor.py').read_text('utf-8')
        self.assertEqual(ast.dump(ast.parse(old)),ast.dump(normalize_relay_tree(ast.parse(now))))

    def test_order_and_strategy_modules_unchanged(self):
        root=Path(__file__).resolve().parent
        for name in ('v8_bitunix.py','trend_v8.py','execution_guard.py','v8_notifications.py','live_auto.py'):
            old=subprocess.check_output(['git','show','724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6:'+name],cwd=root)
            self.assertEqual((root/name).read_bytes().replace(b'\r\n',b'\n'),old.replace(b'\r\n',b'\n'))

    def test_execution_flags_not_changed(self):
        with patch.dict(os.environ,{'V8_LIVE_EXECUTION':'false','IGOD_NOTIFICATION_RADAR_ENABLED':'true'}):
            original=dict(os.environ)
            for text in ('V8 SIGNAL LONG','V8 SIGNAL SHORT','V8 SIGNAL FLAT','V8 REAL DISARMED'):
                with patch('v8_executor._legacy_telegram') as legacy:
                    v8_executor.telegram(text);legacy.assert_not_called()
            self.assertEqual(dict(os.environ),original)

    def test_100_flat_heartbeat_evaluations_no_telegram(self):
        with patch.dict(os.environ,{'IGOD_NOTIFICATION_RADAR_ENABLED':'true'}),patch('v8_executor._legacy_telegram') as legacy:
            for i in range(100):v8_executor.telegram('V8 SIGNAL FLAT')
            legacy.assert_not_called()

    def test_disabled_reuses_original_sender(self):
        with patch.dict(os.environ,{'IGOD_NOTIFICATION_RADAR_ENABLED':'false'}),patch('v8_executor._legacy_telegram') as legacy:
            v8_executor.telegram('V8 SIGNAL LONG');legacy.assert_called_once_with('V8 SIGNAL LONG')

    def test_unknown_uncertainty_is_critical_not_opportunity(self):
        value=v8_event('V8 REAL BLOCKED — cycle uncertainty; no automatic order retry',1)
        self.assertEqual(value['kind'],'CRITICAL');self.assertNotIn('opportunity_id',value)

    def test_fallback_is_async_and_coalesces_same_crisis(self):
        called=threading.Event();release=threading.Event()
        def slow(text):called.set();release.wait(2)
        value=v8_event('V8 REAL BLOCKED — unique test crisis',int(time.time()*1000))
        start=time.monotonic()
        for i in range(100):self.assertTrue(client.fallback_async(value,slow))
        self.assertLess(time.monotonic()-start,.5);self.assertTrue(called.wait(1));release.set()

    def test_url_does_not_accept_arbitrary_host_or_account_endpoint(self):
        for url in ('https://api.bitunix.com/futures/trade','http://localhost/events',client.URL+'?url=evil'):
            with self.assertRaises(ValueError):client.valid_url(url)

    def test_post_uses_stable_body_hmac_no_telegram_credentials(self):
        obj=object.__new__(client.Client);obj.url=client.URL;obj.key='test-only-key';obj.http=Mock()
        value=v8_event('V8 REAL BLOCKED — unresolved test',1)
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.status=200;response.read.return_value=json.dumps({'ok':True,'record_id':value['id']}).encode()
        obj.http.open.return_value=response;obj.post(value)
        req=obj.http.open.call_args.args[0]
        self.assertEqual(req.full_url,client.URL);self.assertEqual(req.method,'POST')
        self.assertNotIn('TELEGRAM',str(req.headers));self.assertIn('X-igod-signature',req.headers)

    def test_no_ack_or_redirect_is_not_success(self):
        obj=object.__new__(client.Client);obj.url=client.URL;obj.key='k';obj.http=Mock()
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.status=302;obj.http.open.return_value=response
        with self.assertRaises(ValueError):obj.post(v8_event('V8 REAL BLOCKED — test',1))

    def test_no_new_poller_or_private_api_client(self):
        root=Path(__file__).resolve().parent
        for path in (root/'igod_notifications').glob('*.py'):
            text=path.read_text('utf-8')
            for token in ('getUpdates','BITUNIX_API_','/futures/trade/'):
                self.assertNotIn(token,text)

    def test_unreachable_old_incident_does_not_starve_new_crisis(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[];new_seen=threading.Event()
            def unavailable(obj,value):
                calls.append(value['text'])
                if 'new-crisis' in value['text']:new_seen.set()
                raise OSError('test-only-offline')
            with patch.object(client.Client,'post',unavailable),patch.object(client,'fallback_async',return_value=True) as fallback:
                obj=client.Client(client.URL,'test-key',directory,Mock())
                try:
                    obj.submit(v8_event('V8 REAL BLOCKED old-crisis',1800000000000))
                    obj.queue.join()
                    obj.submit(v8_event('V8 REAL BLOCKED new-crisis',1800000001000))
                    self.assertTrue(new_seen.wait(2));self.assertGreaterEqual(len(calls),2)
                finally:obj.stop.set();obj.thread.join(4)

    def test_spool_deduplicates_100_same_crisis_across_restart(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as directory:
            attempted=threading.Event()
            def unavailable(obj,value):attempted.set();raise OSError('offline')
            with patch.object(client.Client,'post',unavailable),patch.object(client,'fallback_async',return_value=True) as fallback:
                obj=client.Client(client.URL,'test-key',directory,Mock())
                try:
                    for i in range(100):obj.submit(v8_event('V8 REAL BLOCKED same-durable-crisis',1800000000000+i))
                    obj.queue.join();self.assertTrue(attempted.wait(2))
                finally:obj.stop.set();obj.thread.join(4)
                with closing(sqlite3.connect(Path(directory)/'notification_spool.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM spool').fetchone()[0],1)
                obj=client.Client(client.URL,'test-key',directory,Mock())
                try:
                    obj.submit(v8_event('V8 REAL BLOCKED same-durable-crisis',1800000000200));obj.queue.join()
                finally:obj.stop.set();obj.thread.join(4)
                with closing(sqlite3.connect(Path(directory)/'notification_spool.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM spool').fetchone()[0],1)
                self.assertEqual(fallback.call_count,1)


if __name__=='__main__':unittest.main()
