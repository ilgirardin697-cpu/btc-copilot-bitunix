"""Causal/offline public observer tests; transport is always mocked."""
from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Early research dependencies are installed by its dedicated CI') from None
from early_breakout_core import (Engine, Indicators, Parameters, STEP, validate_rows, aggregate,
                                 event_outcome, render_early, STATES)
from early_breakout_shadow import PublicMarket, ShadowStore, Observer, PUBLIC_KLINES, load_parameters
from research.early_breakout_research import (candidate_grid, parameter_id, select_candidate,
        concentration, incident_diagnostic, neighbors, split, records, VALID_END, load_frozen)
from research.early_breakout_data import public_get, row
from research.early_breakout_reference import manual_reference
from guardian_signals import snapshot, current_entry_quality


def bar(index, close=100, high=102, low=98, volume=100):
    return np.array([index*STEP, close, high, low, close, volume, volume*.5], float)


def metric(rank=.1, vol=2, acceleration=1):
    return dict(atr=1., atr_percentile=rank, vol_z=vol, macd_hist=1.,
                macd_slope=1., macd_acceleration=acceleration)


def watch(parameters=None):
    engine = Engine(parameters)
    for i in range(engine.parameters.duration):
        engine.step(bar(i), metric())
    return engine


class CausalTests(unittest.TestCase):
    def test_prior_100_rank_excludes_current(self):
        indicator = Indicators()
        for i in range(113):
            result = indicator.step(bar(i))
        self.assertIsNone(result['atr_percentile'])
        prior = list(indicator.history)
        self.assertEqual(len(prior), 100)
        result = indicator.step(bar(113, high=100.01, low=99.99))
        expected = sum(value <= result['atr'] for value in prior)/100
        self.assertEqual(result['atr_percentile'], expected)
        self.assertEqual(result['atr_percentile'], 0)
        self.assertNotEqual(sum(value <= result['atr'] for value in indicator.history)/100, expected)

    def test_constant_atr_ties_do_not_invent_compression(self):
        engine = Engine()
        events = []
        for i in range(150):
            events.extend(engine.step(bar(i)))
        self.assertFalse(events)
        self.assertEqual(engine.latest['atr_percentile'], 1)

    def test_indicator_prefix_invariant(self):
        rng = np.random.default_rng(22)
        prices = 100+np.cumsum(rng.normal(0, .1, 220))
        rows = [bar(i, p, p+.5, p-.5, rng.uniform(10, 100)) for i, p in enumerate(prices)]
        a, b = Indicators(), Indicators()
        full = [a.step(r) for r in rows]
        prefix = [b.step(r) for r in rows[:160]]
        self.assertEqual(prefix, full[:160])

    def test_macd_and_volume_formula_reference(self):
        indicator = Indicators()
        prices, volumes = np.arange(100, 125, dtype=float), np.arange(10, 35, dtype=float)
        e12, e26, signal = prices[0], prices[0], 0.
        histories = []
        for i, price in enumerate(prices):
            if i:
                e12, e26 = 2/13*price+11/13*e12, 2/27*price+25/27*e26
            macd = e12-e26
            signal = .2*macd+.8*signal
            histories.append(macd-signal)
            result = indicator.step(bar(i, price, price+1, price-1, volumes[i]))
        self.assertAlmostEqual(result['vol_z'], (volumes[-1]-volumes[-20:].mean())/volumes[-20:].std(ddof=1))
        self.assertAlmostEqual(result['macd_hist'], histories[-1])
        self.assertAlmostEqual(result['macd_acceleration'], histories[-1]-2*histories[-2]+histories[-3])

    def test_minimum_duration_and_nondirectional_squeeze(self):
        engine = Engine()
        for i in range(2):
            self.assertEqual(engine.step(bar(i), metric()), [])
        event = engine.step(bar(2), metric())[0]
        self.assertEqual((event['state'], event['direction'], event['duration']), ('SQUEEZE_WATCH', 0, 3))

    def test_episode_range_isolation(self):
        engine = Engine()
        engine.step(bar(0, high=1000, low=1), metric(rank=.9))
        for i in range(1, 4):
            engine.step(bar(i), metric())
        self.assertEqual((engine.episode['high'], engine.episode['low']), (102, 98))
        self.assertEqual(engine.episode['start_time'], 2*STEP)

    def test_interrupted_short_compressions_do_not_pool(self):
        engine = Engine()
        engine.step(bar(0), metric())
        engine.step(bar(1), metric())
        engine.step(bar(2), metric(rank=.9))
        engine.step(bar(3), metric())
        engine.step(bar(4), metric())
        self.assertEqual(engine.state, 'NONE')
        self.assertEqual(engine.episode['duration'], 2)

    def test_long_breakout_uses_prior_frozen_range(self):
        engine = watch()
        event = engine.step(bar(3, 104, 110, 97), metric(rank=.15))[0]
        self.assertEqual(event['state'], 'DEVELOPING_LONG')
        self.assertEqual(event['compression_high'], 102)
        self.assertEqual(event['compression_low'], 98)
        self.assertEqual(event['breakout_level'], 102)
        self.assertEqual(event['duration'], 3)

    def test_short_developing(self):
        engine = watch()
        event = engine.step(bar(3, 96, 100, 95), metric(acceleration=-1))[0]
        self.assertEqual((event['state'], event['direction'], event['breakout_level']), ('DEVELOPING_SHORT', -1, 98))

    def test_volume_gate_rejects(self):
        engine = watch()
        event = engine.step(bar(3, 104, 105, 100), metric(vol=1.49))[0]
        self.assertEqual(event['state'], 'RELEASE_FAILED')
        self.assertIsNone(event['developing'])

    def test_acceleration_signed_gate_and_off_control(self):
        for close, accel in ((104, -1), (96, 1), (104, 0)):
            engine = watch()
            event = engine.step(bar(3, close, close+1, close-1), metric(acceleration=accel))[0]
            self.assertEqual(event['state'], 'RELEASE_FAILED')
        engine = watch(replace(Parameters(), acceleration=False))
        self.assertEqual(engine.step(bar(3, 104, 105, 100), metric(acceleration=-1))[0]['state'], 'DEVELOPING_LONG')

    def test_later_closed_long_hold_retest(self):
        engine = watch()
        self.assertEqual(engine.step(bar(3, 104, 105, 100), metric())[0]['state'], 'DEVELOPING_LONG')
        event = engine.step(bar(4, 103, 105, 101), metric())[0]
        self.assertEqual(event['state'], 'CONFIRMING_LONG')
        self.assertEqual(event['cause'], 'LATER_CLOSED_CANDLE_HOLD')
        self.assertEqual(event['timestamp'], 5*STEP)

    def test_later_closed_short_hold_retest(self):
        engine = watch()
        engine.step(bar(3, 96, 100, 95), metric(acceleration=-1))
        self.assertEqual(engine.step(bar(4, 97, 99, 95), metric(acceleration=-1))[0]['state'], 'CONFIRMING_SHORT')

    def test_false_breakout_boundary_and_no_instant_flip(self):
        engine = watch()
        engine.step(bar(3, 104, 105, 100), metric())
        event = engine.step(bar(4, 102, 103, 100), metric())[0]
        self.assertEqual(event['state'], 'RELEASE_FAILED')
        self.assertEqual(event['cause'], 'BREAKOUT_RETURNED_INSIDE')
        event = engine.step(bar(5, 95, 96, 94), metric(acceleration=-1))[0]
        self.assertEqual(event['state'], 'NONE')

    def test_frozen_range_and_expiry(self):
        engine = watch()
        for i in range(3, 8):
            engine.step(bar(i, high=110, low=90), metric(rank=.8))
        self.assertEqual(engine.state, 'NONE')
        self.assertIsNone(engine.episode)

    def test_confirmed_release_expiry(self):
        engine = watch()
        engine.step(bar(3, 104, 105, 100), metric())
        engine.step(bar(4, 104, 105, 100), metric())
        for i in range(5, 9):
            engine.step(bar(i, 104, 105, 100), metric())
        self.assertEqual(engine.state, 'NONE')

    def test_gap_resets_compression_and_indicator_warmup(self):
        engine = watch()
        engine.step(bar(10))
        self.assertEqual(engine.state, 'NONE')
        self.assertIsNone(engine.episode)
        self.assertIsNone(engine.latest['atr_percentile'])

    def test_closed_candles_only_and_no_current_leakage(self):
        rows = np.asarray([bar(0), bar(1), bar(2, 200, 1000, 1)])
        np.testing.assert_equal(validate_rows(rows, STEP, 2*STEP), rows[:2])
        altered = rows.copy()
        altered[2, 2] = 2000
        np.testing.assert_equal(validate_rows(altered, STEP, 2*STEP), rows[:2])

    def test_event_prefix_invariant(self):
        rows = [bar(i, 100+i*.01, 101+i*.01, 99+i*.01) for i in range(250)]
        a, b = Engine(), Engine()
        full = [event for row in rows for event in a.step(row)]
        prefix = [event for row in rows[:180] for event in b.step(row)]
        self.assertEqual(prefix, [event for event in full if event['timestamp'] <= 180*STEP])

    def test_restore_indicator_and_episode_prefix(self):
        engine = Engine()
        for i in range(160):
            engine.step(bar(i, high=102-(i%50)*.01, low=98+(i%50)*.01))
        restarted = Engine(state=json.loads(json.dumps(engine.export())))
        for i in range(160, 190):
            self.assertEqual(restarted.step(bar(i)), engine.step(bar(i)))
        self.assertEqual(restarted.export(), engine.export())

    def test_aggregate_complete_groups_only(self):
        rows = np.array([[i*300000, 100, 101, 99, 100, 1, .5] for i in range(7)], float)
        self.assertEqual(len(aggregate(rows, STEP)), 2)
        self.assertEqual(len(aggregate(np.delete(rows, 1, axis=0), STEP)), 1)

    def test_malformed_market_data_rejected(self):
        for rows in ([], [[0, 1]], [[*bar(0)[:-1], np.nan]], [bar(0, high=99)], [bar(0, low=101)]):
            with self.assertRaises(ValueError):
                validate_rows(rows, STEP)

    def test_event_outcome_mfe_mae_and_adverse_first(self):
        rows = np.array([[i*300000, 100, 102.5, 98.5, 100.5, 1, .5] for i in range(12)], float)
        result = event_outcome(rows, dict(timestamp=0, price=100), 1)
        self.assertAlmostEqual(result['1']['mfe'], .025)
        self.assertAlmostEqual(result['1']['mae'], .015)
        self.assertFalse(result['1']['passages']['0.02/0.01']['success'])
        self.assertEqual(result['1']['passages']['0.02/0.01']['resolution'], 'ADVERSE')
        self.assertIsNone(result['4'])

    def test_short_outcome_symmetric_and_split_censoring(self):
        rows = np.array([[i*300000, 100, 100.4, 98, 99, 1, .5] for i in range(12)], float)
        result = event_outcome(rows, dict(timestamp=0, price=100), -1)
        self.assertTrue(result['1']['passages']['0.01/0.005']['success'])
        self.assertAlmostEqual(result['1']['mfe'], .02)
        self.assertAlmostEqual(result['1']['mae'], .004)
        self.assertIsNone(event_outcome(rows, dict(timestamp=0, price=100), -1, cutoff=3599999)['1'])

    def test_early_outputs_never_grant_permission(self):
        for state in STATES:
            text = render_early(dict(state=state, timestamp=STEP, price=100, duration=3))
            self.assertIn('NO ENTRAR', text)
            self.assertIn('NO ES UNA ORDEN DE ENTRADA', text)
            self.assertNotIn('PUEDES ENTRAR', text)
            self.assertNotIn('LONG_ALLOWED', text)
            self.assertNotIn('SHORT_ALLOWED', text)


class StoreObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ShadowStore(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.store.close)
        self.network = patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('LIVE NETWORK FORBIDDEN'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_atomic_state_journal_and_restart(self):
        self.store.save(dict(engine=watch().export(), latest={'fresh': True}))
        self.store.append('snapshots', {'timestamp': STEP})
        self.store.close()
        self.store = ShadowStore(self.tmp.name)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.state['engine']['state'], 'SQUEEZE_WATCH')
        self.assertEqual(self.store.read('snapshots'), [{'timestamp': STEP}])
        self.assertFalse((Path(self.tmp.name)/'state.json.tmp').exists())

    def test_torn_journal_fails_closed(self):
        self.store.close()
        (Path(self.tmp.name)/'events.jsonl').write_text('{')
        with self.assertRaisesRegex(ValueError, 'OBSERVER_STORE_UNVERIFIED'):
            ShadowStore(self.tmp.name)

    def test_second_process_lock_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'OBSERVER_STORE_UNVERIFIED'):
            ShadowStore(self.tmp.name)

    def test_all_journals_exist_and_append_fsync(self):
        for name in ('events', 'outcomes', 'snapshots'):
            self.assertTrue((Path(self.tmp.name)/(name+'.jsonl')).exists())
        import os
        with patch('early_breakout_shadow.os.fsync', wraps=os.fsync) as fsync:
            self.store.append('snapshots', {'timestamp': STEP})
        fsync.assert_called_once()

    def test_zero_hold_rejected_live(self):
        with self.assertRaises(ValueError):
            Observer(Mock(), self.store, Mock(), replace(Parameters(), hold=0))

    def test_restart_alert_dedup_even_if_state_lags_journal(self):
        engine = watch()
        self.store.save(dict(engine=engine.export(), latest={}))
        event = engine.step(bar(3, 104, 105, 100), metric(rank=.8))[0]
        self.store.append('events', event)  # crash after durable event, before state replacement
        self.store.close()
        self.store = ShadowStore(self.tmp.name)
        self.addCleanup(self.store.close)
        market, telegram = Mock(), Mock()
        market.bars.return_value = np.array([bar(3, 104, 105, 100)])
        observer = Observer(market, self.store, telegram, Parameters(), clock=lambda: 4*STEP/1000)
        with patch.object(Indicators, 'step', return_value=metric(rank=.8)):
            self.assertEqual(observer.cycle()['state'], 'DEVELOPING_LONG')
            observer.cycle()
        telegram.send.assert_not_called()
        self.assertEqual(len(self.store.read('events')), 1)

    def test_transition_alert_once_not_every_poll(self):
        self.store.save(dict(engine=watch().export(), latest={}))
        market, telegram = Mock(), Mock()
        market.bars.return_value = np.array([bar(3, 104, 105, 100)])
        observer = Observer(market, self.store, telegram, Parameters(), clock=lambda: 4*STEP/1000)
        with patch.object(Indicators, 'step', return_value=metric(rank=.8)):
            observer.cycle()
            observer.cycle()
        telegram.send.assert_called_once()
        self.assertEqual(len(self.store.read('snapshots')), 1)
        self.assertFalse(self.store.state['latest']['entry_permission'])

    def test_public_outage_no_stale_direction_or_orders(self):
        market = Mock()
        market.bars.side_effect = requests.Timeout('fake secret raw payload')
        observer = Observer(market, self.store, Mock(), Parameters())
        with patch('builtins.print') as output:
            result = observer.cycle()
        self.assertEqual((result['state'], result['fresh'], result['entry_permission']), ('NONE', False, False))
        output.assert_called_once_with('EARLY_PUBLIC_DATA_UNAVAILABLE', flush=True)

    def test_stale_or_invalid_candle_fails_safe(self):
        market = Mock()
        observer = Observer(market, self.store, Mock(), Parameters(), clock=lambda: 20*STEP/1000)
        for rows in (np.array([bar(0)]), np.array([bar(19, high=99)])):
            market.bars.return_value = rows
            with patch('builtins.print'):
                self.assertFalse(observer.cycle()['fresh'])

    def test_telegram_failure_nonfatal_no_trading_action(self):
        self.store.save(dict(engine=watch().export(), latest={}))
        market, telegram = Mock(), Mock()
        market.bars.return_value = np.array([bar(3, 104, 105, 100)])
        telegram.send.side_effect = RuntimeError('private-token')
        observer = Observer(market, self.store, telegram, Parameters(), clock=lambda: 4*STEP/1000)
        with patch.object(Indicators, 'step', return_value=metric(rank=.8)), patch('builtins.print'):
            self.assertTrue(observer.cycle()['fresh'])

    def test_parameter_change_does_not_silently_reuse_state(self):
        self.store.save(dict(engine=watch().export(), latest={}))
        with self.assertRaises(ValueError):
            Observer(Mock(), self.store, Mock(), replace(Parameters(), percentile=.15))

    def test_failed_release_public_enum_none_with_explicit_terminal_event(self):
        engine = watch()
        engine.step(bar(3, 104, 105, 100), metric())
        self.store.save(dict(engine=engine.export(), latest={}))
        market = Mock()
        market.bars.return_value = np.array([bar(4, 100)])
        observer = Observer(market, self.store, Mock(), Parameters(), clock=lambda: 5*STEP/1000)
        with patch.object(Indicators, 'step', return_value=metric()):
            result = observer.cycle()
        self.assertEqual((result['state'], result['event_state']), ('NONE', 'RELEASE_FAILED'))
        self.assertFalse(result['entry_permission'])

    def test_invalid_saved_engine_rejected(self):
        for state in ('LONG_ALLOWED', 'SHORT_ALLOWED', 'BAD'):
            with self.assertRaisesRegex(ValueError, 'ENGINE_STATE_INVALID'):
                Engine(state={'state': state})

    def test_outcome_once_and_journal_persists(self):
        event = dict(event_id='DEVELOPING_LONG:0', state='DEVELOPING_LONG', timestamp=0, price=100, direction=1)
        self.store.append('events', event)
        self.store.events.append(event)
        market = Mock()
        market.bars.return_value = np.array([[i*300000, 100, 101, 99, 100, 1, .5] for i in range(576)], float)
        observer = Observer(market, self.store, Mock(), Parameters())
        observer._outcomes(48*3600000)
        observer._outcomes(48*3600000)
        self.assertEqual(len(self.store.read('outcomes')), 1)
        market.bars.assert_called_once_with('5m', 0)

    def test_public_fetch_ignores_present_account_credentials(self):
        http = Mock()
        data = bar(0)
        http.get.return_value = Mock(status_code=200, json=Mock(return_value=[[*data[:6], STEP-1, 0, 0, data[6], 0, 0]]))
        with patch.dict('os.environ', {'BITUNIX_API_KEY': 'never-read', 'BITUNIX_API_SECRET': 'never-read'}):
            market = PublicMarket(http, clock=lambda: STEP/1000)
            market.bars()
        self.assertNotIn('never-read', str(http.get.call_args))
        self.assertNotIn('headers', http.get.call_args.kwargs)

    def test_http_property_only_public_get_no_trading_posts(self):
        calls = []
        row_data = bar(0)
        payload = [[*row_data[:6], STEP-1, 0, 0, row_data[6], 0, 0]]
        def transport(session, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method != 'GET' or url != PUBLIC_KLINES:
                raise AssertionError('NONPUBLIC TRANSPORT BLOCKED')
            return Mock(status_code=200, json=Mock(return_value=payload))
        with patch('requests.sessions.Session.request', new=transport):
            market = PublicMarket(clock=lambda: STEP/1000)
            rows = market.bars()
            observer = Observer(market, self.store, Mock(), Parameters(), clock=lambda: STEP/1000)
            observer.cycle()
        self.assertEqual(len(rows), 1)
        self.assertTrue(calls)
        self.assertTrue(all(method == 'GET' and url == PUBLIC_KLINES for method, url, _ in calls))
        self.assertTrue(all('headers' not in options for _, _, options in calls))


class ResearchSafetyTests(unittest.TestCase):
    def test_small_neighbor_grid(self):
        self.assertEqual(len(candidate_grid()), 9)
        self.assertEqual(len(neighbors(Parameters())), 8)
        for parameters in candidate_grid():
            self.assertLessEqual(sum(a != b for a, b in zip(asdict(parameters).values(), asdict(Parameters()).values())), 1)

    def test_test_period_cannot_select(self):
        metrics = dict(horizons={'24': dict(n=100, passages={'0.01/0.01': {'favorable_before_adverse': .6}}, mean_signed_return=.01)})
        train = {'x': dict(period='TRAIN', parameters=asdict(Parameters()), metrics=metrics)}
        valid = {'x': dict(period='VALIDATION', parameters=asdict(Parameters()), metrics=metrics)}
        self.assertEqual(select_candidate(train, valid)[0], 'x')
        valid['x']['period'] = 'TEST'
        with self.assertRaisesRegex(ValueError, 'TEST_SELECTION_BLOCKED'):
            select_candidate(train, valid)

    def test_zero_hold_never_selected(self):
        metrics = dict(horizons={'24': dict(n=100, passages={'0.01/0.01': {'favorable_before_adverse': .99}}, mean_signed_return=.01)})
        params = asdict(replace(Parameters(), hold=0))
        train = {'zero': dict(period='TRAIN', parameters=params, metrics=metrics)}
        valid = {'zero': dict(period='VALIDATION', parameters=params, metrics=metrics)}
        self.assertEqual(select_candidate(train, valid)[0], parameter_id(Parameters()))

    def test_committed_freeze_integrity_and_no_test_reselection(self):
        path = Path('research/early_breakout_artifacts/frozen_parameters.json')
        selected = load_frozen(path)
        self.assertFalse(selected['test_selection'])
        with tempfile.TemporaryDirectory() as directory:
            modified = Path(directory)/'frozen.json'
            selected['parameters']['percentile'] = .25
            modified.write_text(json.dumps(selected), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'FROZEN_SELECTION_INVALID'):
                load_frozen(modified)

    def test_frozen_reproduction_never_calls_selector(self):
        from types import SimpleNamespace
        import research.early_breakout_research as research
        with tempfile.TemporaryDirectory() as directory:
            cache, output = Path(directory)/'cache', Path(directory)/'output'
            cache.mkdir()
            output.mkdir()
            frozen = Path('research/early_breakout_artifacts/frozen_parameters.json').read_text(encoding='utf-8')
            (output/'frozen_parameters.json').write_text(frozen, encoding='utf-8')
            begin = 1704067200000
            base = np.array([[begin+i*300000, 100, 101, 99, 100, 1, .5] for i in range(120)], float)
            end = begin+120*300000
            np.savez_compressed(cache/'spot_5m.npz', bars=base)
            (cache/'manifest.json').write_text(json.dumps({'as_of': end, 'sources': []}), encoding='utf-8')
            args = SimpleNamespace(cache=str(cache), as_of='2024-01-01T10:00:00+00:00',
                                   download=False, incident_start=None, incident_end=None)
            q = aggregate(base, STEP)
            with patch.object(research, 'OUTPUT', output), patch.object(research, 'manual_reference',
                    return_value=({1: np.array([], dtype=int), -1: np.array([], dtype=int)}, np.zeros(len(q), int))):
                with patch.object(research, 'select_candidate', side_effect=AssertionError('NO RESELECTION')) as selector:
                    with patch('builtins.print'):
                        research.run(args)
                    selector.assert_not_called()
            self.assertEqual((output/'frozen_parameters.json').read_text(encoding='utf-8'), frozen)

    def test_split_boundaries(self):
        self.assertEqual(split(1640995200000-1), 'TRAIN')
        self.assertEqual(split(1640995200000), 'VALIDATION')
        self.assertEqual(split(VALID_END), 'TEST')

    def test_concentration_best_and_top3(self):
        rows = []
        for i, value in enumerate((.30, .20, .10, -.01, -.02)):
            path = dict(signed_return=value, mfe=max(value, 0), mae=max(-value, 0),
                        passages={key: dict(success=value > 0, resolution='FAVORABLE' if value > 0 else 'ADVERSE')
                                  for key in ('0.005/0.005', '0.01/0.005', '0.01/0.01', '0.02/0.01', '0.03/0.01')})
            rows.append(dict(direction=1, state='DEVELOPING_LONG', paths={'1': {str(h): path for h in (1, 4, 12, 24, 48)}},
                             lead_minutes={'1': None}, hold_success=True, false_breakout=False, gate_failed=False))
        result = concentration(rows)
        self.assertEqual(result['1']['developing_count'], 4)
        self.assertEqual(result['3']['developing_count'], 2)
        self.assertLess(result['3']['horizons']['24']['mean_signed_return'], 0)

    def test_incident_diagnostic_only_requires_date_not_price_match(self):
        confirmations = {1: np.array([100]), -1: np.array([110])}
        result = incident_diagnostic([], confirmations)
        self.assertFalse(result['used_for_selection'])
        self.assertEqual(result['status'], 'UNIDENTIFIED_DATE_NOT_PROVIDED')
        dated = incident_diagnostic([], confirmations, 90, 120)
        self.assertFalse(dated['used_for_selection'])
        self.assertEqual(dated['confirming_times']['1'], [100])

    def test_public_urls_only_and_microsecond_normalization(self):
        with self.assertRaisesRegex(ValueError, 'PUBLIC_URL_BLOCKED'):
            public_get('https://fapi.bitunix.com/private')
        values = ['1735689600000000', '100', '101', '99', '100', '10', 0, 0, 0, '5', 0, 0]
        self.assertEqual(row(values)[0], 1735689600000)

    def test_no_account_credentials_endpoints_or_coupling(self):
        for path in ('early_breakout_core.py', 'early_breakout_shadow.py',
                     'research/early_breakout_data.py', 'research/early_breakout_research.py'):
            source = Path(path).read_text(encoding='utf-8')
            for forbidden in ('BITUNIX_API', 'guardian_bitunix', 'trade_guardian', 'getUpdates',
                              'place_order', 'flash_close', 'change_leverage', 'change_margin',
                              'transfer(', 'withdraw(', 'PUEDES ENTRAR'):
                self.assertNotIn(forbidden, source)
        self.assertNotIn('GUARDIAN_', inspect.getsource(Observer))

    def test_reference_entry_confirmation_matches_existing_pure_rules(self):
        rng = np.random.default_rng(72)
        count = 4100*12
        price = 100*np.exp(np.cumsum(rng.normal(0, .0003, count)))
        volumes = rng.uniform(100, 200, count)
        base = np.column_stack((np.arange(count)*300000, price, price*1.001, price*.999,
                                price, volumes, volumes*rng.uniform(.2, .8, count)))
        q, h, f = aggregate(base, STEP), aggregate(base, 3600000), aggregate(base, 14400000)
        confirmations, _ = manual_reference(base, q)
        self.assertGreater(sum(len(values) for values in confirmations.values()), 0)
        sets = {side: set(values.tolist()) for side, values in confirmations.items()}
        for i in range(3200*4, len(q), 151):
            stamp = int(q[i, 0]+STEP)
            hourly = h[h[:, 0]+3600000 <= stamp]
            four = f[f[:, 0]+14400000 <= stamp][-220:]
            actual = snapshot(hourly, four, q[i-219:i+1], stamp)
            actual = current_entry_quality(actual, q[i, 4])
            for side, bias in ((1, 'LONG_ALLOWED'), (-1, 'SHORT_ALLOWED')):
                expected = actual['bias'] == bias and actual['entry_quality'] == 'GOOD'
                self.assertEqual(stamp in sets[side], expected)


if __name__ == '__main__':
    unittest.main()
