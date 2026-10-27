"""Offline causal-sequence, range/outcome and reproducibility tests."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from bitman_manual.frozen.indicators import calculate
    from research import bitman_state_data as data
    from research import bitman_weekly_state_machine as sm
    from research import bitman_state_analysis as analysis
except ModuleNotFoundError as error:
    if error.name == 'numpy':
        raise unittest.SkipTest('Dedicated research workflow installs existing numpy dependency') from error
    raise


def context(ao, colors, vol, valid=None):
    n = len(ao)
    return dict(ao=np.asarray(ao, float), color=np.asarray(colors), bbwp_slope=np.asarray(vol, float),
                valid=np.ones(n, bool) if valid is None else np.asarray(valid, bool))


def fixture(count=120):
    t = data.MONDAY+np.arange(count)*data.WEEK
    close = 100+np.sin(np.arange(count)/4)*8+np.arange(count)*.2
    return np.column_stack((t, close-.2, close+2, close-2, close, np.full(count, 10), np.full(count, 4)))


class StateSequenceTests(unittest.TestCase):
    def test_four_base_states(self):
        f = context([1, 1, -1, -1], ['GREEN', 'RED', 'RED', 'GREEN'], [1, -1, 1, -1])
        # Avoid an unintended zero-cross in this isolated base-state fixture.
        for i, expected in enumerate(('IMPULSE_UP', 'PULLBACK_UP', 'IMPULSE_DOWN', 'PULLBACK_DOWN')):
            one = {k: v[i:i+1] for k, v in f.items()}
            self.assertEqual(sm.classify(one)[0][0], expected)

    def test_reacceleration_up_is_one_resolution_of_two_pullback_weeks(self):
        f = context([2, 1.8, 1.6, 1.9, 2.2], ['GREEN', 'RED', 'RED', 'GREEN', 'GREEN'], [1, -2, 0, 3, 2])
        states, duration = sm.classify(f)
        self.assertEqual(list(states), ['IMPULSE_UP', 'PULLBACK_UP', 'PULLBACK_UP', 'REACCELERATION_UP', 'IMPULSE_UP'])
        self.assertEqual(duration[3], 2)
        self.assertEqual(np.count_nonzero(np.isin(states, sm.SIGNALS)), 1)

    def test_reacceleration_down_after_three_corrective_weeks(self):
        f = context([-3, -2.8, -2.6, -2.4, -2.9], ['RED', 'GREEN', 'GREEN', 'GREEN', 'RED'], [1, -1, -2, 0, 3])
        states, duration = sm.classify(f)
        self.assertEqual(states[-1], 'REACCELERATION_DOWN')
        self.assertEqual(duration[-1], 3)

    def test_zero_cross_up_overrides_impulse(self):
        states, duration = sm.classify(context([-2, -1, .1], ['GREEN']*3, [-2, -1, 2]))
        self.assertEqual(states[-1], 'ZERO_CROSS_UP_EXPANSION')
        self.assertEqual(duration[-1], 2)

    def test_zero_cross_down_active_expansion_does_not_require_turn(self):
        states, _ = sm.classify(context([1, -.1], ['RED']*2, [1, 2]))
        self.assertEqual(states[-1], 'ZERO_CROSS_DOWN_EXPANSION')

    def test_zero_equality_is_not_a_strict_cross_or_pullback_bridge(self):
        states, _ = sm.classify(context([-1, 0, 1], ['GREEN']*3, [-1, -1, 1]))
        self.assertEqual(states[-1], 'IMPULSE_UP')

    def test_no_delayed_zero_cross_expansion(self):
        states, _ = sm.classify(context([-1, .1, 1], ['GREEN']*3, [-1, -1, 1]))
        self.assertEqual(states[-1], 'IMPULSE_UP')
        self.assertNotIn('ZERO_CROSS_UP_EXPANSION', states)

    def test_other_breaks_pullback_run(self):
        states, _ = sm.classify(context([2, 1, 1.5, 2], ['RED', 'RED', 'GREEN', 'GREEN'], [-1, -1, -1, 1]))
        self.assertEqual(states[-1], 'IMPULSE_UP')

    def test_invalid_week_breaks_pullback_run(self):
        states, _ = sm.classify(context([2, 1.8, 2], ['RED', 'RED', 'GREEN'], [-1, -1, 1], [True, False, True]))
        self.assertEqual(states[-1], 'IMPULSE_UP')

    def test_color_and_zero_side_are_not_interchangeable(self):
        states, _ = sm.classify(context([-1, 1], ['GREEN', 'RED'], [-1, -1]))
        self.assertEqual(list(states), ['PULLBACK_DOWN', 'PULLBACK_UP'])

    def test_future_append_does_not_change_any_previous_state(self):
        f = context([2, 1, 3, -1, -2, -1, -3], ['GREEN', 'RED', 'GREEN', 'RED', 'RED', 'GREEN', 'RED'], [1, -1, 1, 1, 1, -1, 1])
        full = sm.classify(f)
        before = copy.deepcopy(f)
        for end in range(1, 8):
            partial = sm.classify({k: v[:end] for k, v in f.items()})
            np.testing.assert_array_equal(partial[0], full[0][:end])
            np.testing.assert_array_equal(partial[1], full[1][:end])
        for key in f:
            np.testing.assert_array_equal(f[key], before[key])


class ClosedDataTests(unittest.TestCase):
    def test_monday_utc_anchor(self):
        self.assertEqual(data.week_start(data.CUTOFF-1), data.CUTOFF-data.WEEK)
        self.assertEqual(data.week_start(data.CUTOFF), data.CUTOFF)

    def test_only_complete_42_bar_week_and_no_fill(self):
        rows = [[data.MONDAY+i*data.FOUR_HOURS, '100', '102', '98', '101', '10',
                 data.MONDAY+(i+1)*data.FOUR_HOURS-1, '1000', 2, '4', '400', '0'] for i in range(84)]
        complete, excluded = data.aggregate_weeks(rows[1:], data.MONDAY+2*data.WEEK)
        self.assertEqual(len(complete), 1)
        self.assertEqual(excluded[0]['bars'], 41)
        self.assertEqual(complete[0][5], '420')

    def test_gap_and_duplicate_rejected(self):
        rows = [[data.MONDAY+i*data.FOUR_HOURS, '100', '102', '98', '101', '10',
                 data.MONDAY+(i+1)*data.FOUR_HOURS-1, '1000', 2, '4', '400', '0'] for i in range(42)]
        for invalid in (rows[:5]+rows[6:], rows[:5]+rows[4:]):
            with self.assertRaises(ValueError):
                data.validate(invalid, data.FOUR_HOURS, data.MONDAY+data.WEEK)

    def test_no_open_week(self):
        rows = [[data.CUTOFF, '100', '102', '98', '101', '10', data.CUTOFF+data.FOUR_HOURS-1, '1', 1, '4', '1', '0']]
        with self.assertRaises(ValueError):
            data.validate(rows, data.FOUR_HOURS, data.CUTOFF)

    def test_frozen_arrays_exact_and_no_mutation(self):
        frame = fixture(150)
        original = frame.copy()
        frozen, f = calculate(frame), sm.features(frame)
        for name in frozen:
            np.testing.assert_array_equal(f[name], frozen[name])
        np.testing.assert_array_equal(frame, original)

    def test_feature_prefix_causality(self):
        frame = fixture(150)
        f = sm.features(frame)
        for end in (109, 117, 132, 149):
            partial = sm.features(frame[:end])
            for name in ('ao', 'bbwp', 'atr', 'state', 'signal', 'turn', 'sustained_turn', 'pullback_weeks'):
                np.testing.assert_array_equal(partial[name], f[name][:end])


class RangeOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.column_stack((data.MONDAY+np.arange(12)*data.WEEK, np.full(12, 100),
            np.full(12, 110), np.full(12, 90), np.full(12, 100), np.full(12, 10), np.full(12, 4)))
        self.f = dict(frame=self.frame, valid=np.ones(12, bool), atr=np.full(12, 10.))

    def test_range_uses_only_closed_past_including_signal(self):
        self.frame[5, 2] = 150
        self.assertEqual(sm.causal_range(self.frame, 4, 4), (110, 90))
        self.assertEqual(sm.causal_range(self.frame, 5, 4), (150, 90))

    def test_wick_is_not_close_breakout(self):
        self.frame[5, 2] = 130
        out = sm.outcomes(self.f, 4, 1)
        self.assertEqual(out['wick_breakout'][4], 1)
        self.assertEqual(out['breakout'][4], 0)
        self.assertEqual(out['large_10'][4], 0)
        self.assertEqual(out['move_20'][4], 1)

    def test_close_breakout_direction_and_time(self):
        self.frame[6, 4] = 115
        self.frame[6, 2] = 120
        out = sm.outcomes(self.f, 4, 2)
        self.assertEqual(out['first_week'][4], 2)
        self.assertEqual(out['first_side'][4], 1)
        self.assertEqual(out['large_10'][4], 1)
        self.assertAlmostEqual(out['beyond_up'][4], 10)

    def test_same_week_double_wick_order_unknown(self):
        self.frame[5, 2:4] = [130, 70]
        out = sm.outcomes(self.f, 4, 1)
        self.assertEqual(out['wick_side'][4], 2)

    def test_opposite_excursion_does_not_make_small_breakout_large(self):
        self.frame[5, 2:5] = [111, 70, 111]
        # Set a larger high boundary so the small up breakout is <20%.
        out = sm.outcomes(self.f, 4, 1)
        self.assertEqual(out['large_20'][4], 0)
        self.assertEqual(out['move_20'][4], 1)

    def test_horizon_censor_not_negative(self):
        out = sm.outcomes(self.f, 4, 4)
        self.assertTrue(np.isnan(out['large_10'][-4:]).all())
        self.assertTrue(np.isnan(out['first_week'][4]))

    def test_atr_fixed_at_signal_not_future(self):
        self.frame[5, 2] = 130
        self.f['atr'][5] = 10000
        out = sm.outcomes(self.f, 4, 1)
        self.assertEqual(out['max_atr'][4], 3)
        self.assertEqual(out['atr_2'][4], 1)

    def test_reentry_and_zero_followup_distinguished(self):
        self.frame[5, 2:5] = [125, 95, 120]
        one = sm.outcomes(self.f, 4, 1)
        two = sm.outcomes(self.f, 4, 2)
        self.assertTrue(np.isnan(one['sustained'][4]))
        self.assertEqual(two['reentered'][4], 1)
        self.assertEqual(two['sustained'][4], 0)

    def test_down_breakout_and_distance(self):
        self.frame[5, 2:5] = [105, 70, 80]
        out = sm.outcomes(self.f, 4, 1)
        self.assertEqual(out['first_side'][4], -1)
        self.assertEqual(out['beyond_down'][4], 20)


class InferenceTests(unittest.TestCase):
    def test_blocked_weights_are_deterministic_and_preserve_length(self):
        w = analysis.block_weights(37, 100, 8)
        np.testing.assert_array_equal(w, analysis.block_weights(37, 100, 8))
        np.testing.assert_array_equal(w.sum(axis=1), np.full(100, 37))
        self.assertFalse(np.array_equal(w, analysis.block_weights(37, 100, 4)))

    def test_tiny_sample_interval_not_published(self):
        self.assertEqual(analysis.ci(np.arange(100), 7), [None, None])
        self.assertEqual(analysis.ci(np.r_[np.arange(90), [np.nan]*10], 30), [None, None])

    def test_boot_median_even_weighted_case(self):
        result = analysis.boot_median(np.array([1., 4., 9.]), np.ones(3, bool), np.array([[1, 2, 1], [0, 0, 0]]))
        self.assertEqual(result[0], 4)
        self.assertTrue(np.isnan(result[1]))

    def test_greedy_overlap_removed_without_future_ranking(self):
        mask = np.zeros(12, bool)
        mask[[1, 2, 5, 6, 10, 11]] = True
        self.assertEqual(list(np.flatnonzero(sm.nonoverlap(mask))), [1, 6, 11])

    def test_empty_group_not_zero_performance(self):
        self.assertIsNone(analysis.mean([]))


class PublicSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = sm.load_inputs()
        cls.recorded = json.loads((sm.DEST/'analysis.json').read_text('utf-8'))

    def test_audited_snapshot_and_current_week(self):
        self.assertEqual(len(self.f['frame']), 371)
        self.assertEqual(self.f['valid'].sum(), 263)
        self.assertEqual(sm.iso(self.f['available_at'][-1]), '2026-10-19T00:00:00+00:00')

    def test_all_seven_signal_episodes_once_no_persistent_count(self):
        eps = sm.episodes(self.f)
        self.assertEqual(len(eps), 7)
        self.assertEqual(len({e['episode_id'] for e in eps}), 7)
        self.assertEqual(sum(e['state'].startswith('REACCELERATION') for e in eps), 4)

    def test_state_counts_and_current_other_not_forced_impulse(self):
        self.assertEqual(self.recorded['state_counts']['OTHER'], 140)
        self.assertEqual(self.f['state'][-1], 'OTHER')
        self.assertEqual(self.recorded['current']['large_move_watch'], 'NOT VALIDATED')

    def test_full_prior_pullback_in_zero_cross_episode(self):
        for episode in sm.episodes(self.f):
            self.assertEqual(len(episode['sequence']), episode['index']-(episode['index']-episode['pullback_weeks'] if episode['pullback_weeks'] else episode['index']-1)+1)

    def test_episodes_all_have_frozen_ranges_and_mature_horizon(self):
        for episode in self.recorded['episodes']:
            self.assertTrue(episode['mature_4w'])
            i = episode['index']
            self.assertEqual(sm.causal_range(self.f['frame'], i, 4), (episode['range_high'], episode['range_low']))

    def test_precision_recall_lift_from_raw_opportunities(self):
        out = sm.outcomes(self.f, 4, 4)
        valid = self.f['valid'] & np.isfinite(out['forward'])
        sig = self.f['signal'] & valid
        self.assertEqual(int(sig.sum()), 7)
        self.assertEqual(int(out['large_10'][valid].sum()), 128)
        self.assertEqual(int(out['large_10'][sig].sum()), 1)
        self.assertAlmostEqual(1/7/(128/259), .2890625)

    def test_all_requested_durations_levels_ranges_and_horizons_exist(self):
        with (sm.DEST/'summaries.csv').open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        groups = {r['group'] for r in rows}
        self.assertTrue({'REACC_GE1', 'REACC_GE2', 'REACC_GE3', 'REACC_EXACT_1', 'REACC_EXACT_2', 'REACC_EXACT_3', 'REACC_EXACT_GE4'}.issubset(groups))
        self.assertTrue({'LEVEL_GT50', 'LEVEL_LE50', 'LEVEL_CROSS_UP50', 'LEVEL_CROSS_DOWN50', 'LEVEL_FALL_THROUGH50', 'LEVEL_TURN_LE50', 'LEVEL_TURN_GT50'}.issubset(groups))
        self.assertEqual({int(r['horizon']) for r in rows}, {1, 2, 3, 4})
        self.assertEqual({int(r['range_weeks']) for r in rows}, {2, 4, 8})

    def test_falsification_zero_counts_explicit_not_omitted(self):
        counts = self.recorded['falsification_counts']
        self.assertEqual(counts['REACC_UP_NEGATIVE'], 2)
        self.assertEqual(counts['REACC_DOWN_POSITIVE'], 1)
        self.assertEqual(counts['REACC_UP_OPPOSITE'], 0)
        self.assertEqual(counts['LARGE_WITHOUT_SETUP'], 127)

    def test_temporal_controls_never_use_future_maturity(self):
        with (sm.DEST/'temporal_controls.csv').open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(rows)
        for row in rows:
            self.assertLessEqual(row['latest_control_mature_at'], row['signal_at'])

    def test_all_published_outcome_rows_reproduce(self):
        outputs = {(n, h): sm.outcomes(self.f, n, h) for n in sm.RANGES for h in sm.HORIZONS}
        with (sm.DEST/'observations.csv').open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3126)
        for row in rows:
            out = outputs[int(row['range_weeks']), int(row['horizon'])]
            i = int(row['index'])
            for key, values in out.items():
                if row[key] == '':
                    self.assertTrue(np.isnan(values[i]))
                else:
                    self.assertAlmostEqual(float(row[key]), values[i], places=10)

    def test_manifest_hash_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/'weekly_bars.csv').write_text('bad data', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'REUSED_INPUT_HASH_MISMATCH'):
                sm.load_inputs(p)

    def test_all_statistics_and_blocked_intervals_reproduce_from_public_inputs(self):
        replay = analysis.analyze(self.f)
        from research import bitman_state_reporting as reporting
        for name in ('summaries', 'comparisons', 'observations', 'temporal_controls', 'falsification'):
            with (sm.DEST/(name+'.csv')).open(newline='', encoding='utf-8') as stream:
                saved = reporting.numeric(list(csv.DictReader(stream)))
            self.assertEqual(len(saved), len(replay[name]), name)
            for expected, actual in zip(saved, replay[name]):
                for key, value in actual.items():
                    if value is None:
                        self.assertIsNone(expected[key], (name, key))
                    elif isinstance(value, bool):
                        self.assertEqual(str(value), expected[key], (name, key))
                    elif isinstance(value, (int, float)):
                        self.assertAlmostEqual(value, expected[key], places=9, msg=(name, key))
                    else:
                        self.assertEqual(value, expected[key], (name, key))
        for key in ('episodes', 'runs', 'influence', 'overlap', 'current', 'bootstrap_sensitivity', 'falsification_counts'):
            self.assertEqual(replay[key], self.recorded[key], key)

    def test_report_reproduces_and_never_claims_holdout_or_parity(self):
        from research import bitman_state_reporting as reporting
        read = lambda name: reporting.read_csv(sm.DEST, name)
        report = reporting.render(self.recorded, read('summaries'), read('comparisons'), read('temporal_controls'), read('falsification'))
        self.assertEqual(report, (sm.ROOT/'research/results/BITMAN_WEEKLY_STATE_MACHINE.md').read_text('utf-8'))
        self.assertIn('NO VIRGIN HOLDOUT', report)
        self.assertIn('NOT ASSESSABLE', report)
        self.assertIn('EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN', report)
        self.assertIn('EXACT BITMAN VOLATILITY PARITY: NOT PROVEN', report)
        self.assertEqual(reporting.conclusion(7), 'INCONCLUSIVE')

    def test_no_reliably_estimable_main_ci_is_invented(self):
        with (sm.DEST/'summaries.csv').open(newline='', encoding='utf-8') as stream:
            main = [r for r in csv.DictReader(stream) if r['group']=='SIGNALS' and r['scope']=='FULL' and r['range_weeks']=='4']
        for row in main:
            self.assertEqual(int(row['n']), 7)
            for name in ('precision_ci_low', 'precision_ci_high', 'max_move_ci_low', 'signed_ci_high'):
                self.assertEqual(row[name], '')
            self.assertEqual(row['sample_status'], 'INSUFFICIENT FOR CONCLUSION')


if __name__ == '__main__':
    unittest.main()
