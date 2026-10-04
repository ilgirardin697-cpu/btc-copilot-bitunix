"""Offline math, event, persistence, market transport and presentation tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Observer dependencies are installed and fully tested by mlrsi-observer CI') from None
from guardian_signals import pine_rsi, pine_ema, rolling_mlrsi, cluster_three
from mlrsi_math import CAPTURED_CONFIG, CONFIG_VERSION, RSI_LENGTH, CausalSeries, ResearchEvents, TIMEFRAMES
from mlrsi_observer import MLRSIObserver, ObserverConfig, empty_frame
from mlrsi_public import PublicHistory, WARMUP_BARS, URL, atomic_json, validate_candles
import mlrsi_telegram


def candle(stamp, low=100, close=None):
    close = low + 2 if close is None else close
    return dict(time=stamp, open=close, high=close + 3, low=low, close=close)


def values(color='NEUTRAL', rsi=50, lower=40, upper=60):
    return dict(color=color, mlrsi_raw=rsi, mlrsi_smoothed=rsi, lower_threshold=lower,
                middle_centroid=50, upper_threshold=upper, valid=True, converged=True,
                window_count=3000, iterations=2)


def rsi29_seed_fixture():
    # 27 gains of one, then two losses of four: exactly 29 changes.
    return [100. + i for i in range(28)] + [123., 119., 124., 118., 121., 116., 122., 120., 123.]


class MathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.low = 200 + np.cumsum(np.random.default_rng(517).normal(size=3100))
        cls.reference = rolling_mlrsi(cls.low, length=29, max_data=3000, max_iter=1000)
        cls.series = CausalSeries()
        cls.actual = [cls.series.push(x) for x in cls.low]

    def test_source_low(self):
        self.assertEqual(CAPTURED_CONFIG['source'], 'LOW')

    def test_current_live_preset_is_low29(self):
        self.assertEqual(RSI_LENGTH, 29)
        self.assertEqual(CONFIG_VERSION, 'CAPTURE_LOW29_EMA4_CAUSAL_V2')
        self.assertEqual(CAPTURED_CONFIG, dict(source='LOW', rsi_length=29, smooth=True, ma_type='EMA',
                                             smoothing_period=4, alma_sigma=1, threshold_range_min=10,
                                             threshold_range_max=90, step=5, performance_memory=10,
                                             max_clustering_steps=1000, max_data_points=3000, clusters=3,
                                             wait_for_timeframe_close=True))

    def test_exactly_29_changes_seed_and_wilder_update(self):
        s = CausalSeries()
        lows = rsi29_seed_fixture()
        for x in lows[:29]:  # 29 candles = only 28 changes
            self.assertIsNone(s.push(x)['mlrsi_raw'])
        self.assertEqual(len(s.seed), 28)
        seeded = s.push(lows[29])
        self.assertEqual(len(s.seed), 29)
        self.assertAlmostEqual(s.up, 27 / 29)
        self.assertAlmostEqual(s.down, 8 / 29)
        self.assertAlmostEqual(seeded['mlrsi_raw'], 100 * 27 / 35)
        self.assertEqual(seeded['mlrsi_smoothed'], seeded['mlrsi_raw'])
        up, down = s.up, s.down
        s.push(lows[30])  # next gain of five; Wilder weight is 28/29
        self.assertAlmostEqual(s.up, (up * 28 + 5) / 29)
        self.assertAlmostEqual(s.down, down * 28 / 29)

    def test_rsi29_differs_from_historical_rsi27(self):
        lows = rsi29_seed_fixture()
        current = CausalSeries()  # separate live preset from unchanged research primitive
        actual = [current.push(x)['mlrsi_raw'] for x in lows]
        old = pine_rsi(lows, 27)
        self.assertIsNone(actual[27])
        self.assertTrue(np.isfinite(old[27]))
        self.assertNotAlmostEqual(actual[29], old[29])
        self.assertAlmostEqual(actual[29], pine_rsi(lows, 29)[29])

    def test_partial_29_seed_survives_restart(self):
        lows, s = rsi29_seed_fixture(), CausalSeries()
        for x in lows[:28]:
            s.push(x)
        restored = CausalSeries(json.loads(json.dumps(s.dump())))
        self.assertEqual(len(restored.seed), 27)
        self.assertEqual(restored.dump()['rsi_length'], 29)
        self.assertIsNone(restored.push(lows[28])['mlrsi_raw'])
        self.assertAlmostEqual(restored.push(lows[29])['mlrsi_raw'], pine_rsi(lows, 29)[29])

    def test_legacy_27_carry_never_reused_as_29(self):
        for length in (27, None):
            old = copy.deepcopy(self.series.dump())
            if length is None:
                old.pop('rsi_length')
            else:
                old['rsi_length'] = length
            with self.assertRaisesRegex(ValueError, 'MLRSI_SERIES_STATE_INVALID'):
                CausalSeries(old)

    def test_low_not_close(self):
        s = CausalSeries()
        close = self.low + np.sin(np.arange(len(self.low))) * 10 + 12
        self.assertNotAlmostEqual([s.push(x)['mlrsi_smoothed'] for x in close][-1], self.actual[-1]['mlrsi_smoothed'])

    def test_wilder_seed_and_raw(self):
        raw = pine_rsi(self.low, 29)
        np.testing.assert_allclose([v['mlrsi_raw'] if v['mlrsi_raw'] is not None else np.nan for v in self.actual], raw, equal_nan=True)
        self.assertIsNone(self.actual[28]['mlrsi_raw'])
        self.assertAlmostEqual(self.actual[29]['mlrsi_raw'], raw[29])

    def test_ema4_seed_and_update(self):
        np.testing.assert_allclose([v['mlrsi_smoothed'] if v['mlrsi_smoothed'] is not None else np.nan for v in self.actual],
                                   pine_ema(pine_rsi(self.low, 29), 4), equal_nan=True)

    def test_max_data_3000(self):
        self.assertEqual(self.actual[-1]['window_count'], 3000)
        np.testing.assert_allclose(self.series.history, self.reference['rsi'][-3000:])

    def test_max_iterations_1000(self):
        with patch('mlrsi_math.cluster_three', wraps=cluster_three) as fn:
            self.series.provisional(190)
            self.assertEqual(fn.call_args.args[1], 1000)

    def test_percentile_initialization(self):
        with patch('guardian_signals.np.quantile', wraps=np.quantile) as fn:
            cluster_three([10, 15, 20, 40, 70, 80])
            self.assertEqual(fn.call_args.args[1], [.25, .5, .75])
            self.assertEqual(fn.call_args.kwargs['method'], 'linear')

    def test_research_centroids_equal(self):
        for i in (33, 100, 700, 3028, 3099):
            v = self.actual[i]
            np.testing.assert_array_equal([v['lower_threshold'], v['middle_centroid'], v['upper_threshold']], self.reference['centroids'][i])

    def test_research_colors_equal(self):
        for i, v in enumerate(self.actual):
            if v['valid']:
                self.assertEqual(v['color'], {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[int(self.reference['state'][i])])

    def test_research_finite_and_convergence_policy(self):
        self.assertEqual([v['iterations'] for v in self.actual], self.reference['iterations'].tolist())
        self.assertEqual([v['converged'] for v in self.actual], self.reference['converged'].tolist())

    def test_determinism(self):
        s = CausalSeries()
        self.assertEqual([s.push(x) for x in self.low[:100]], self.actual[:100])

    def test_prefix_invariance(self):
        s = CausalSeries()
        self.assertEqual([s.push(x) for x in self.low[:400]], self.actual[:400])

    def test_future_extreme_no_change(self):
        s = CausalSeries()
        prefix = [s.push(x) for x in self.low[:60]]
        saved = copy.deepcopy(prefix)
        s.push(100000)
        self.assertEqual(saved, self.actual[:60])

    def test_incremental_restart_math(self):
        s = CausalSeries()
        for x in self.low[:54]:
            s.push(x)
        r = CausalSeries(json.loads(json.dumps(s.dump())))
        self.assertEqual([r.push(x) for x in self.low[54:100]], self.actual[54:100])

    def test_provisional_clone_does_not_change_confirmed(self):
        before = copy.deepcopy(self.series.dump())
        self.series.provisional(150)
        self.assertEqual(before, self.series.dump())

    def test_empty_clusters_and_ties(self):
        self.assertTrue(cluster_three([50] * 10)[2])
        self.assertEqual(CausalSeries().push(100)['color'], 'UNKNOWN')
        s = CausalSeries()
        self.assertTrue(all(s.push(100)['color'] == 'UNKNOWN' for _ in range(80)))

    def test_nonfinite_low_rejected(self):
        for x in (np.nan, np.inf, 0, -1):
            with self.assertRaises(ValueError):
                CausalSeries().push(x)

    def test_all_three_timeframes_same_independent_math(self):
        independent = {tf: CausalSeries() for tf in TIMEFRAMES}
        for i, x in enumerate(self.low[:45]):
            for s in independent.values():
                self.assertEqual(s.push(x), self.actual[i])
        independent['15m'].push(150)
        self.assertEqual(independent['1h'].count, independent['4h'].count)
        self.assertNotEqual(independent['15m'].count, independent['4h'].count)


class EventTests(unittest.TestCase):
    def machine(self, states, rsi=None):
        s = ResearchEvents(900000)
        return [s.step(i * 900000, values(c, (rsi or [50] * len(states))[i])) for i, c in enumerate(states)]

    def test_neutral_green_cross(self):
        self.assertEqual(self.machine(['NEUTRAL', 'GREEN']), [None, 'GREEN_CROSS'])

    def test_red_green_cross(self):
        self.assertEqual(self.machine(['RED', 'GREEN']), [None, 'GREEN_CROSS'])

    def test_neutral_red_cross(self):
        self.assertEqual(self.machine(['NEUTRAL', 'RED']), [None, 'RED_CROSS'])

    def test_green_red_cross(self):
        self.assertEqual(self.machine(['GREEN', 'RED']), [None, 'RED_CROSS'])

    def test_green_resume_rearm(self):
        self.assertEqual(self.machine(['GREEN'] * 7, [50, 51, 50, 51, 52, 52, 53]),
                         [None, None, None, 'GREEN_RESUME', None, None, 'GREEN_RESUME'])

    def test_red_resume_rearm(self):
        self.assertEqual(self.machine(['RED'] * 7, [50, 49, 50, 49, 48, 48, 47]),
                         [None, None, None, 'RED_RESUME', None, None, 'RED_RESUME'])

    def test_no_duplicate_cross(self):
        self.assertEqual(self.machine(['NEUTRAL', 'GREEN', 'GREEN', 'GREEN'], [50, 51, 52, 53]).count('GREEN_CROSS'), 1)

    def test_color_exit_clears_resume(self):
        self.assertEqual(self.machine(['GREEN', 'GREEN', 'NEUTRAL', 'GREEN'], [55, 54, 53, 56])[-1], 'GREEN_CROSS')

    def test_gap_no_transition(self):
        s = ResearchEvents(900000)
        s.step(0, values('NEUTRAL'))
        self.assertIsNone(s.step(1800000, values('GREEN')))

    def test_research_frozen_fixture(self):
        fixture = json.loads(Path('tests/fixtures/mlrsi_research_events.json').read_text('utf-8'))
        for reference in fixture['references']:
            result = {name: [] for name in reference['events']}
            s = ResearchEvents(reference['interval'])
            for i, (color, rsi) in enumerate(zip(fixture['colors'], fixture['rsi'])):
                event = s.step(i * reference['interval'], values(color, rsi))
                if event:
                    result[event].append(i)
            self.assertEqual(result, reference['events'])


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sent, self.logs = [], []
        self.now = 14400000 * 4000
        self.o = MLRSIObserver(self.tmp.name, send=self.sent.append, logger=self.logs.append, clock=lambda: self.now / 1000)
        # Seed a mature exact-math history; controlled values isolate event routing.
        for tf, interval in TIMEFRAMES.items():
            p = self.o.frames[tf]
            p.update(last_closed_timestamp=self.now, confirmed_color='NEUTRAL', fresh=True, last_successful_read=self.now,
                     latest_confirmed_values=dict(values(), source_low=100, close=102))
            self.o.series[tf].history.extend([40, 50, 60] * 1000)
            self.o.events[tf].step(self.now, values())
        self.o.primed = set(TIMEFRAMES)
        self.o.startup_sent = True
        self.o._publish(self.now)

    def closed_frame(self, tf, add=True, open_low=None):
        interval = TIMEFRAMES[tf]
        rows = [candle(self.o.frames[tf]['last_closed_timestamp'] - interval)]
        if add:
            rows.append(candle(self.o.frames[tf]['last_closed_timestamp']))
        if open_low is not None:
            rows.append(candle(rows[-1]['time'] + interval, open_low))
        return rows

    def record_events(self):
        if not self.o.journal_path.exists():
            return []
        return [json.loads(x) for x in self.o.journal_path.read_text('utf-8').splitlines()]

    def transition(self, tf='15m', color='GREEN', rsi=61):
        self.now += TIMEFRAMES[tf]
        with patch.object(self.o.series[tf], 'push', return_value=values(color, rsi)):
            self.o.observe({tf: self.closed_frame(tf)}, self.now)

    def open_value(self, tf='15m', color='NEUTRAL', rsi=59.1):
        with patch.object(self.o.series[tf], 'provisional', return_value=values(color, rsi)):
            self.o._open(tf, candle(self.now, low=99), True)
            return self.o.frames[tf]

    def test_open_candle_no_confirmed(self):
        with patch.object(self.o.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            self.o.observe({'15m': self.closed_frame('15m', add=False, open_low=99)}, self.now + 1)
        self.assertEqual(self.o.frames['15m']['confirmed_color'], 'NEUTRAL')
        self.assertNotIn('GREEN_CROSS', [r['event'] for r in self.record_events()])

    def test_closed_candle_confirms(self):
        self.transition()
        self.assertEqual(self.o.frames['15m']['confirmed_color'], 'GREEN')
        self.assertIn('GREEN_CROSS', [r['event'] for r in self.record_events()])

    def test_closed_edge_equality(self):
        self.now += TIMEFRAMES['15m']
        with patch.object(self.o.series['15m'], 'push', return_value=values('GREEN', 61)) as fn:
            self.o.observe({'15m': self.closed_frame('15m')}, self.now - 1)
            self.assertFalse(fn.called)
            self.o.observe({'15m': self.closed_frame('15m')}, self.now)
            self.assertEqual(fn.call_count, 1)

    def test_same_closed_timestamp_ignored(self):
        self.transition()
        n = len(self.record_events())
        with patch.object(self.o.series['15m'], 'push') as fn:
            self.o.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
            self.assertFalse(fn.called)
        self.assertEqual(len(self.record_events()), n)

    def test_tf_independent(self):
        old = copy.deepcopy(self.o.frames['4h']['latest_confirmed_values'])
        self.transition('1h', 'RED', 39)
        self.assertEqual(self.o.frames['4h']['latest_confirmed_values'], old)
        self.assertEqual(self.o.frames['15m']['confirmed_color'], 'NEUTRAL')

    def test_approaching_09(self):
        p = self.open_value()
        self.assertEqual(p['approaching_state'], 'APPROACHING_GREEN')
        self.assertTrue(p['approaching_green_latched'])

    def test_approaching_11_no(self):
        self.assertEqual(self.open_value(rsi=58.9)['approaching_state'], 'NO')

    def test_approaching_not_cross_or_confirmed(self):
        before = self.o.events['15m'].dump()
        self.open_value()
        self.assertEqual(self.o.frames['15m']['confirmed_color'], 'NEUTRAL')
        self.assertEqual(before, self.o.events['15m'].dump())

    def test_approaching_latch_rearm_strict(self):
        changes = []
        for distance in (.8, .5, .2, 1.2, 1.5, 1.7, .9):
            with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=60-distance)):
                changes += self.o._open('15m', candle(self.now), True)
        self.assertEqual([e[0] for e in changes], ['APPROACHING_GREEN', 'APPROACHING_GREEN'])

    def test_approaching_red_symmetric(self):
        self.assertEqual(self.open_value(rsi=40.9)['approaching_state'], 'APPROACHING_RED')

    def test_approaching_red_rearm_strict(self):
        changes = []
        for distance in (.9, .2, 1.5, 1.7, .8):
            with patch.object(self.o.series['15m'], 'provisional', return_value=values(rsi=40+distance)):
                changes += self.o._open('15m', candle(self.now), True)
        self.assertEqual([e[0] for e in changes], ['APPROACHING_RED', 'APPROACHING_RED'])

    def test_threshold_tie_neutral_not_approaching(self):
        self.assertEqual(self.open_value(rsi=60)['approaching_state'], 'NO')

    def test_provisional_green(self):
        p = self.open_value(color='GREEN', rsi=61)
        self.assertEqual(p['latest_provisional_values']['color'], 'GREEN')
        self.assertEqual(p['confirmed_color'], 'NEUTRAL')

    def test_provisional_red(self):
        p = self.open_value(color='RED', rsi=39)
        self.assertEqual(p['latest_provisional_values']['color'], 'RED')
        self.assertEqual(p['confirmed_color'], 'NEUTRAL')

    def test_provisional_same_open_dedup(self):
        with patch.object(self.o.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            first = self.o._open('15m', candle(self.now), True)
            second = self.o._open('15m', candle(self.now), True)
        self.assertEqual(first, [('PROVISIONAL_GREEN', '15m', False)])
        self.assertEqual(second, [])

    def test_provisional_vanish_neutral_no_cross(self):
        self.open_value(color='GREEN', rsi=61)
        self.transition(color='NEUTRAL', rsi=50)
        self.assertFalse(self.record_events())

    def test_provisional_new_candle_rearm(self):
        self.open_value(color='GREEN', rsi=61)
        with patch.object(self.o.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            self.assertEqual(self.o._open('15m', candle(self.now + TIMEFRAMES['15m']), True), [('PROVISIONAL_GREEN', '15m', False)])

    def confluence(self, color):
        self.now += TIMEFRAMES['4h']
        frames = {tf: [candle(self.now - interval)] for tf, interval in TIMEFRAMES.items()}
        for tf in TIMEFRAMES:
            self.o.frames[tf]['last_closed_timestamp'] = self.now - TIMEFRAMES[tf]
            self.o.events[tf].step(self.now - TIMEFRAMES[tf], values('NEUTRAL'))
        with patch.object(self.o.series['15m'], 'push', return_value=values(color, 61 if color == 'GREEN' else 39)), \
             patch.object(self.o.series['1h'], 'push', return_value=values(color, 61 if color == 'GREEN' else 39)), \
             patch.object(self.o.series['4h'], 'push', return_value=values(color, 61 if color == 'GREEN' else 39)):
            self.o.observe(frames, self.now)

    def test_green_3of3_grouped_and_dedup(self):
        self.confluence('GREEN')
        self.assertEqual(len(self.sent), 1)
        self.assertIn('GREEN_CROSS + 3/3 GREEN CONFIRMED', self.sent[0])
        self.o.observe({tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}, self.now)
        self.assertEqual(len(self.sent), 1)

    def test_red_3of3(self):
        self.confluence('RED')
        self.assertIn('3/3 RED CONFIRMED', self.sent[0])

    def test_red_3of3_dedup_and_rearm(self):
        self.confluence('RED')
        frames = {tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}
        self.o.observe(frames, self.now)
        self.assertEqual(len(self.sent), 1)
        self.o.frames['1h']['confirmed_color'] = 'NEUTRAL'
        self.o.observe(frames, self.now)
        self.assertFalse(self.o.previous_3of3_red)
        self.o.frames['1h']['confirmed_color'] = 'RED'
        self.o.observe(frames, self.now)
        self.assertEqual(sum('3/3 RED' in text for text in self.sent), 2)

    def test_resume_durable_duplicate_timestamp_ignored(self):
        self.o.frames['15m']['confirmed_color'] = 'GREEN'
        self.o.events['15m'].step(self.now, values('GREEN', 60))
        self.o.events['15m'].armed = True
        self.transition(color='GREEN', rsi=61)
        before = len(self.record_events())
        self.o.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
        self.assertEqual(len(self.record_events()), before)
        self.assertEqual(sum('GREEN_RESUME' in text for text in self.sent), 1)

    def test_confluence_leave_reenter(self):
        self.confluence('GREEN')
        self.o.frames['4h']['confirmed_color'] = 'NEUTRAL'
        self.o.observe({tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}, self.now)
        self.assertFalse(self.o.previous_3of3_green)
        self.o.frames['4h']['confirmed_color'] = 'GREEN'
        self.o.observe({tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}, self.now)
        self.assertEqual(sum('3/3 GREEN' in s for s in self.sent), 2)

    def test_two_confirmed_one_provisional_not_3of3(self):
        for tf in ('15m', '1h'):
            self.o.frames[tf]['confirmed_color'] = 'GREEN'
        self.open_value('4h', 'GREEN', 61)
        self.o.observe({tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}, self.now)
        self.assertFalse(self.o.previous_3of3_green)

    def test_restart_no_cross_replay(self):
        self.transition()
        r = MLRSIObserver(self.tmp.name, send=self.sent.append, logger=self.logs.append, clock=lambda: self.now / 1000)
        self.assertEqual(r.frames['15m']['last_confirmed_event'], 'GREEN_CROSS')
        with patch.object(r.series['15m'], 'push') as fn:
            r.observe({'15m': [candle(self.now - TIMEFRAMES['15m'])]}, self.now)
            self.assertFalse(fn.called)
        self.assertEqual(len(self.sent), 1)

    def test_restart_preserves_resume_rearm(self):
        self.o.events['15m'].step(self.now + 900000, values('GREEN', 61))
        self.o.events['15m'].step(self.now + 1800000, values('GREEN', 60))
        self.o._persist()
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertTrue(r.events['15m'].armed)
        self.assertEqual(r.events['15m'].step(self.now + 2700000, values('GREEN', 61)), 'GREEN_RESUME')

    def test_restart_completed_resume_not_replayed(self):
        self.o.frames['15m']['confirmed_color'] = 'GREEN'
        self.o.events['15m'].step(self.now, values('GREEN', 60))
        self.o.events['15m'].armed = True
        self.transition(color='GREEN', rsi=61)
        self.assertEqual(self.o.frames['15m']['last_confirmed_event'], 'GREEN_RESUME')
        before = len(self.record_events())
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append, clock=lambda: self.now / 1000)
        r.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
        self.assertEqual(len(self.record_events()), before)

    def test_restart_provisional_latches_survive(self):
        self.open_value(color='GREEN', rsi=61)
        self.o._persist()
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertTrue(r.frames['15m']['provisional_green_latched'])
        with patch.object(r.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            self.assertFalse(r._open('15m', candle(self.now), True))

    def test_startup_backfill_does_not_generate_events(self):
        self.o.primed.clear()
        self.o.startup_sent = False
        self.transition(color='GREEN', rsi=61)
        self.assertFalse(self.record_events())
        self.assertFalse(self.sent)

    def test_catchup_journals_actual_each_close_not_old_alerts(self):
        rows = [candle(self.now), candle(self.now + 900000), candle(self.now + 1800000)]
        self.now += 2700000
        with patch.object(self.o.series['15m'], 'push', side_effect=[values('GREEN', 61), values('NEUTRAL', 50), values('RED', 39)]):
            self.o.observe({'15m': rows}, self.now)
        records = self.record_events()
        self.assertEqual([r['mlrsi_smoothed'] for r in records if r['event'].endswith('_CROSS')], [61, 39])
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn('GREEN_CROSS', self.sent[0])

    def test_outbox_recovers_after_journal_failure(self):
        with patch.object(self.o, '_flush_journal', side_effect=OSError('crash')):
            self.transition()
        self.assertTrue(self.o.pending_journal_records)
        self.assertFalse(self.record_events())
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append, clock=lambda: self.now / 1000)
        r.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
        self.assertTrue(self.record_events())
        self.assertFalse(r.pending_journal_records)

    def test_outbox_reconcile_written_journal_no_duplicate(self):
        self.transition()
        self.o.pending_journal_records = self.record_events()
        self.o._persist()  # simulate crash after append before clearing outbox
        before = len(self.record_events())
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append, clock=lambda: self.now / 1000)
        r.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
        self.assertEqual(len(self.record_events()), before)

    def test_ambiguous_fsync_reconciles_bytes_before_retry(self):
        # Initial state write succeeds; journal bytes exist but fsync fails.
        with patch('mlrsi_observer.os.fsync', side_effect=OSError('ambiguous')), \
             patch.object(self.o, '_persist'):
            self.transition()
        before = len(self.record_events())
        self.assertGreater(before, 0)
        self.o.observe({'15m': self.closed_frame('15m', add=False)}, self.now)
        self.assertEqual(len(self.record_events()), before)

    def test_corrupt_state_static_silent_rebootstrap(self):
        self.o.state_path.write_text('{secret payload', encoding='utf-8')
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertEqual(r.frames['15m']['confirmed_color'], 'UNKNOWN')
        self.assertEqual(self.logs, ['MLRSI_STATE_INVALID_REBOOTSTRAP'])

    def test_corrupt_journal_blocks_append_nonfatal(self):
        self.o.journal_path.write_text('{bad payload', encoding='utf-8')
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertIsNone(r.journal_keys)
        with self.assertRaises(ValueError):
            r._flush_journal()

    def test_all_tf_closed_and_open_edge(self):
        for tf, interval in TIMEFRAMES.items():
            o = self.o
            old = o.frames[tf]['last_closed_timestamp']
            row = candle(old)
            with patch.object(o.series[tf], 'push', return_value=values('GREEN', 61)) as push:
                o.observe({tf: [candle(old - interval), row]}, old + interval - 1)
                self.assertFalse(push.called, tf)
                o.observe({tf: [candle(old - interval), row]}, old + interval)
                self.assertEqual(push.call_count, 1, tf)

    def test_real_low_math_enters_observer_unchanged(self):
        low = 200 + np.cumsum(np.random.default_rng(151).normal(size=3060))
        reference = rolling_mlrsi(low, length=29, max_data=3000, max_iter=1000)
        r = MLRSIObserver(Path(self.tmp.name) / 'real', logger=self.logs.append)
        interval = TIMEFRAMES['15m']
        rows = [candle(i * interval, x, x + 12 + np.sin(i)) for i, x in enumerate(low)]
        r.observe({'15m': rows}, len(rows) * interval)
        last = r.frames['15m']['latest_confirmed_values']
        self.assertAlmostEqual(last['mlrsi_smoothed'], reference['rsi'][-1])
        self.assertEqual(last['source_low'], low[-1])
        self.assertTrue(r.frames['15m']['fresh'])

    def test_confirmed_low_math_uses_rsi29(self):
        lows = rsi29_seed_fixture()
        self.o.series['15m'] = CausalSeries()
        for i, low in enumerate(lows):
            self.o._closed('15m', candle(i * TIMEFRAMES['15m'], low), False)
        last = self.o.frames['15m']['latest_confirmed_values']
        expected = rolling_mlrsi(lows, length=29, max_data=3000, max_iter=1000)
        self.assertAlmostEqual(last['mlrsi_raw'], pine_rsi(lows, 29)[-1])
        self.assertAlmostEqual(last['mlrsi_smoothed'], expected['rsi'][-1])
        np.testing.assert_array_equal([last['lower_threshold'], last['middle_centroid'], last['upper_threshold']],
                                      expected['centroids'][-1])
        self.assertEqual(last['color'], {-1: 'RED', 0: 'NEUTRAL', 1: 'GREEN'}[expected['state'][-1]])

    def test_provisional_uses_rsi29_without_changing_confirmed(self):
        lows, s = rsi29_seed_fixture(), CausalSeries()
        for low in lows:
            s.push(low)
        self.o.series['15m'] = s
        before = copy.deepcopy(s.dump())
        self.o._open('15m', candle(self.now, low=115), False)
        provisional = self.o.frames['15m']['latest_provisional_values']
        extended = lows + [115.]
        self.assertAlmostEqual(provisional['mlrsi_raw'], pine_rsi(extended, 29)[-1])
        self.assertAlmostEqual(provisional['mlrsi_smoothed'], pine_ema(pine_rsi(extended, 29), 4)[-1])
        self.assertNotAlmostEqual(provisional['mlrsi_smoothed'], pine_ema(pine_rsi(extended, 27), 4)[-1])
        self.assertEqual(s.dump(), before)

    def test_observer_restart_preserves_partial_rsi29_seed_all_timeframes(self):
        folder = Path(self.tmp.name) / 'seed29'
        o = MLRSIObserver(folder, logger=self.logs.append)
        lows = rsi29_seed_fixture()
        for tf, interval in TIMEFRAMES.items():
            for i, low in enumerate(lows[:28]):
                o._closed(tf, candle(i * interval, low), False)
        o._persist()
        r = MLRSIObserver(folder, logger=self.logs.append)
        for tf, interval in TIMEFRAMES.items():
            self.assertEqual(r.series[tf].dump()['rsi_length'], 29)
            self.assertEqual(len(r.series[tf].seed), 27)
            r._closed(tf, candle(28 * interval, lows[28]), False)
            self.assertIsNone(r.frames[tf]['latest_confirmed_values']['mlrsi_raw'])
            r._closed(tf, candle(29 * interval, lows[29]), False)
            self.assertAlmostEqual(r.frames[tf]['latest_confirmed_values']['mlrsi_raw'], pine_rsi(lows, 29)[29])

    def test_old27_state_rebootstraps_instead_of_mixing_presets(self):
        self.o._persist()
        old = json.loads(self.o.state_path.read_text('utf-8'))
        old['config_version'] = 'CAPTURE_LOW27_EMA4_CAUSAL_V1'
        old['config']['rsi_length'] = 27
        self.o.state_path.write_text(json.dumps(old), encoding='utf-8')
        r = MLRSIObserver(self.tmp.name, send=self.sent.append, logger=self.logs.append)
        for tf in TIMEFRAMES:
            self.assertEqual(r.series[tf].count, 0)
            self.assertEqual(list(r.series[tf].history), [])
            self.assertEqual(r.frames[tf]['confirmed_color'], 'UNKNOWN')
        self.assertIn('MLRSI_STATE_INVALID_REBOOTSTRAP', self.logs)
        self.assertEqual(self.sent, [])

    def test_legacy27_journal_preserved_with_original_version(self):
        self.transition()
        rows = self.record_events()
        for row in rows:
            row['config_version'] = 'CAPTURE_LOW27_EMA4_CAUSAL_V1'
        old = '\n'.join(json.dumps(row) for row in rows) + '\n'
        self.o.journal_path.write_text(old, encoding='utf-8')
        r = MLRSIObserver(self.tmp.name, logger=self.logs.append)
        self.assertIsNotNone(r.journal_keys)
        self.assertEqual(r.journal_path.read_text('utf-8'), old)
        self.assertNotIn('MLRSI_JOURNAL_INVALID', self.logs)
        current = r._record('COLOR_CHANGE', '15m', True, self.now)
        self.assertEqual(current['config_version'], CONFIG_VERSION)

    def test_unknown_journal_preset_still_rejected(self):
        self.transition()
        row = self.record_events()[0]
        row['config_version'] = 'UNKNOWN_PRESET'
        with self.assertRaisesRegex(ValueError, 'MLRSI_JOURNAL_INVALID'):
            self.o._validate_record(row)

    def test_status_and_startup_show_current_wilder29(self):
        for text in (self.o.status_text(), mlrsi_telegram.startup(self.o.snapshot())):
            self.assertIn('RSI: Wilder 29', text)
            self.assertNotIn('RSI: Wilder 27', text)

    def test_worker_nonblocking_and_not_double_started(self):
        with patch('mlrsi_observer.threading.Thread') as thread:
            self.o.start()
            self.o.start()
            self.assertEqual(thread.call_count, 1)
            self.assertTrue(thread.call_args.kwargs['daemon'])
            self.o.stop()
            self.assertFalse(thread.return_value.join.called)

    def test_restart_confluence_is_current_status(self):
        self.confluence('GREEN')
        self.sent.clear()
        r = MLRSIObserver(self.tmp.name, send=self.sent.append, logger=self.logs.append, clock=lambda: self.now / 1000)
        r.observe({tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}, self.now)
        self.assertEqual(len(self.sent), 1)
        self.assertIn('CURRENT STATUS', self.sent[0])
        self.assertNotIn('NEW SIGNAL', self.sent[0])

    def test_startup_once_no_signal(self):
        self.o.startup_sent = False
        self.o.primed.clear()
        frames = {tf: self.closed_frame(tf, add=False) for tf in TIMEFRAMES}
        self.o.observe(frames, self.now)
        self.o.observe(frames, self.now)
        self.assertEqual(len(self.sent), 1)
        self.assertIn('CURRENT STATUS', self.sent[0])
        self.assertFalse(self.record_events())

    def test_missing_tf_no_confluence_rearm(self):
        self.o.previous_3of3_green = True
        self.o.observe({}, self.now)
        self.assertTrue(self.o.previous_3of3_green)
        self.assertFalse(self.o.snapshot()['timeframes']['15m']['fresh'])

    def test_gap_fail_safe(self):
        self.now += 2700000
        with patch.object(self.o.series['15m'], 'push') as fn:
            self.o.observe({'15m': [candle(self.now - 900000)]}, self.now)
            self.assertFalse(fn.called)
        self.assertIn('MLRSI_TIMEFRAME_UNAVAILABLE', self.logs)

    def test_journal_schema(self):
        self.transition()
        row = self.record_events()[-1]
        self.assertIs(row['trade_authority'], False)
        self.assertIs(row['shadow_only'], True)
        self.assertEqual(row['source'], 'LOW')
        for k in ('recorded_at_utc', 'candle_timestamp_utc', 'source_low', 'mlrsi_raw', 'middle_centroid',
                  'distance_to_green', 'confirmed_state_15m', 'confirmed_state_1h', 'confirmed_state_4h',
                  'provisional_state_4h', 'config_version', 'observer_version'):
            self.assertIn(k, row)
        self.assertNotIn('return', row)

    def test_storage_separate_no_secrets(self):
        self.o._persist()
        text = self.o.state_path.read_text('utf-8')
        for secret in ('BITUNIX', 'TELEGRAM', 'api_key', 'secret', 'chat_id'):
            self.assertNotIn(secret, text)
        self.assertFalse((Path(self.tmp.name) / 'igod_live_state.json').exists())

    def test_fsync_journal_and_atomic_state(self):
        with patch('mlrsi_public.os.replace', wraps=__import__('os').replace) as replace, \
             patch('mlrsi_public.os.fsync', wraps=__import__('os').fsync) as sync:
            self.transition()
        self.assertTrue(replace.called)
        self.assertGreaterEqual(sync.call_count, 2)

    def test_storage_failure_nonfatal(self):
        with patch.object(self.o, '_persist', side_effect=OSError('secret payload')):
            self.transition()
        self.assertFalse(self.sent)
        self.assertNotIn('secret payload', str(self.logs))

    def test_telegram_failure_nonfatal(self):
        self.o.send = Mock(side_effect=RuntimeError('token payload'))
        self.transition()
        self.assertEqual(self.o.frames['15m']['confirmed_color'], 'GREEN')
        self.assertEqual(self.logs[-1], 'MLRSI_TELEGRAM_FAILED')

    def test_telegram_false_result_static_failure(self):
        self.o.send = lambda text: False
        self.transition()
        self.assertEqual(self.logs[-1], 'MLRSI_TELEGRAM_FAILED')

    def test_provisional_alert_disabled_still_observational_journal(self):
        self.o.config = ObserverConfig(provisional_alerts=False)
        with patch.object(self.o.series['15m'], 'provisional', return_value=values('GREEN', 61)):
            self.o.observe({'15m': self.closed_frame('15m', add=False, open_low=99)}, self.now)
        self.assertIn('PROVISIONAL_GREEN', [r['event'] for r in self.record_events()])
        self.assertFalse(self.sent)

    def test_approaching_disabled_no_alert(self):
        self.o.config = ObserverConfig(approaching_enabled=False)
        self.assertEqual(self.open_value()['approaching_state'], 'NO')

    def test_cycle_outage_nonfatal(self):
        self.o.provider = Mock()
        self.o.provider.fetch.side_effect = RuntimeError('secret response')
        self.o.cycle()
        self.assertEqual(self.logs.count('MLRSI_PUBLIC_READ_FAILED'), 3)
        self.assertNotIn('secret response', str(self.logs))

    def test_disabled_no_network_or_files(self):
        tmp = Path(self.tmp.name) / 'disabled'
        provider = Mock()
        r = MLRSIObserver(tmp, provider=provider, config=ObserverConfig(enabled=False))
        r.start()
        r.cycle()
        r.observe({}, self.now)
        self.assertFalse(provider.fetch.called)
        self.assertFalse(tmp.exists())

    def test_invalid_env_fallback_static(self):
        config = ObserverConfig.from_env({'MLRSI_OBSERVER_ENABLED': 'secret', 'MLRSI_APPROACH_DISTANCE': 'nan',
                                          'MLRSI_APPROACH_REARM_DISTANCE': '-1'}, self.logs.append)
        self.assertEqual(config, ObserverConfig())
        self.assertEqual(set(self.logs), {'MLRSI_CONFIG_INVALID_DEFAULT_USED'})

    def test_rearm_config_order(self):
        config = ObserverConfig.from_env({'MLRSI_APPROACH_DISTANCE': '2', 'MLRSI_APPROACH_REARM_DISTANCE': '1'}, self.logs.append)
        self.assertEqual((config.approach_distance, config.rearm_distance), (1.0, 1.5))

    def test_status_without_recent_event(self):
        text = self.o.status_text()
        for word in ('15m', '1H', '4H', 'Confirmed:', 'Provisional:', 'Approaching:', 'Upper:', 'Lower:',
                     'Último cierre:', 'Último evento:', 'CONFLUENCIA', 'SHADOW ONLY', 'TRADE AUTHORITY: NONE',
                     'GREEN_CROSS / RED_CROSS', 'GREEN_RESUME / RED_RESUME', 'NOT CONFIRMED'):
            self.assertIn(word, text)
        self.assertLess(len(text), 4096)

    def test_status_is_readonly_cached(self):
        before = copy.deepcopy(self.o.frames)
        with patch.object(self.o.provider, 'fetch') as fetch, patch.object(self.o, '_persist') as persist:
            self.o.status_text()
        self.assertFalse(fetch.called)
        self.assertFalse(persist.called)
        self.assertEqual(before, self.o.frames)

    def test_stale_status_not_claim_current(self):
        self.now += 100000
        self.assertIn('Datos no actuales', self.o.status_text())

    def test_all_alerts_show_three_tf(self):
        self.transition()
        self.assertTrue(all(all(tf in text for tf in ('15m', '1H', '4H')) for text in self.sent))

    def test_neutral_alert(self):
        self.o.frames['15m']['confirmed_color'] = 'GREEN'
        self.transition(color='NEUTRAL', rsi=50)
        self.assertIn('BACK TO NEUTRAL', self.sent[0])


class PublicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.transport = Mock()
        self.p = PublicHistory(self.tmp.name, self.transport)
        self.interval = TIMEFRAMES['15m']
        self.now = 4000 * self.interval

    def response(self, rows):
        r = Mock(status_code=200)
        r.json.return_value = [[p[k] for k in ('time', 'open', 'high', 'low', 'close')] for p in rows]
        return r

    def test_bootstrap_public_only_bounded(self):
        self.transport.get.side_effect = [self.response([candle(i * self.interval) for i in range(end-999, end+1)])
                                          for end in (4000, 3000, 2000, 1000)]
        rows = self.p.fetch('15m', self.now)
        self.assertEqual(self.transport.get.call_count, 4)
        for args in self.transport.get.call_args_list:
            self.assertEqual(args.args, (URL,))
            self.assertEqual(args.kwargs['params']['symbol'], 'BTCUSDT')
        self.assertGreaterEqual(len(rows), WARMUP_BARS)
        self.assertFalse(self.transport.post.called)

    def test_incremental_one_request(self):
        self.p.cache['15m'] = [candle(i * self.interval) for i in range(4000-WARMUP_BARS, 4001)]
        self.transport.get.return_value = self.response([candle(self.now)])
        self.p.fetch('15m', self.now)
        self.assertEqual(self.transport.get.call_count, 1)
        self.assertEqual(self.transport.get.call_args.kwargs['params']['startTime'], self.now)

    def test_cache_restart_incremental(self):
        cached = [candle(i * self.interval) for i in range(4000-WARMUP_BARS, 4001)]
        atomic_json(Path(self.tmp.name) / 'igod_mlrsi_cache_15m.json', dict(symbol='BTCUSDT', venue='BINANCE_SPOT', candles=cached))
        self.transport.get.return_value = self.response([candle(self.now)])
        self.p.fetch('15m', self.now)
        self.assertEqual(self.transport.get.call_count, 1)

    def test_malformed_candles_rejected(self):
        for rows in ([candle(1)], [candle(0, low=float('nan'))], [candle(0), candle(0)], [candle(self.now + self.interval)]):
            with self.assertRaises(ValueError):
                validate_candles(rows, '15m', self.now)

    def test_http_error_safe(self):
        self.transport.get.return_value = Mock(status_code=500)
        with self.assertRaisesRegex(ValueError, '^MLRSI_PUBLIC_UNAVAILABLE$'):
            self.p.fetch('15m', self.now)

    def test_no_netrc_credentials(self):
        self.assertFalse(PublicHistory(self.tmp.name).http.trust_env)

    def test_insufficient_history_fails(self):
        self.transport.get.return_value = self.response([candle(self.now)])
        with self.assertRaises(ValueError):
            self.p.fetch('15m', self.now)

    def test_closed_revision_rejected(self):
        self.p.cache['15m'] = [candle(i * self.interval) for i in range(4000-WARMUP_BARS, 4000)]
        self.p.verified_at['15m'] = self.now
        self.transport.get.return_value = self.response([candle(self.now-self.interval, low=99), candle(self.now)])
        with self.assertRaisesRegex(ValueError, 'MLRSI_CLOSED_CANDLE_REVISED'):
            self.p.fetch('15m', self.now)

    def test_open_cache_refresh_allowed(self):
        self.p.cache['15m'] = [candle(i * self.interval) for i in range(4000-WARMUP_BARS, 4001)]
        self.p.verified_at['15m'] = self.now
        self.transport.get.return_value = self.response([candle(self.now, low=99)])
        self.assertEqual(self.p.fetch('15m', self.now)[-1]['low'], 99)


if __name__ == '__main__':
    unittest.main()
