"""Real exported observations and isolated PAPER mechanics; no live calls."""
import copy
import hashlib
import json
import unittest
from tempfile import TemporaryDirectory
from decimal import Decimal as D
from pathlib import Path
from .core import Candle,HOUR
from .evidence import analyze,load_evidence,bars_from_rows,LOGS,LOG_SHA
from .profiles import OWNER_B
from .replay import Replay
from .risk import Costs
from .paper_review import review,first_touches,reprice,evaluate_signal,SPEC_PATH

HERE=Path(__file__).resolve().parent
ZERO=Costs(D(0),D(0),D(0),D(0),D(0),'SYNTHETIC_TEST_ONLY_NOT_REAL_FEES')


class RealPlatformEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=analyze()

    def test_real_source_is_separate_from_synthetic_comparator_fixture(self):
        self.assertEqual(hashlib.sha256(LOGS.read_bytes()).hexdigest(),LOG_SHA)
        self.assertEqual(len(load_evidence()),64)
        self.assertEqual(self.result['tickerid'],'BINANCE:BTCUSDT')

    def test_exact_compared_count_without_initial_state_injection(self):
        r=self.result
        self.assertEqual((r['input_rows'],r['compared_rows'],r['skipped_rows'],r['complete_cycles']),(64,33,31,2))
        self.assertEqual(r['comparison_first_bar_open_utc'],'2026-11-02T11:00:00Z')
        self.assertEqual(r['comparison_last_bar_open_utc'],'2026-11-03T19:00:00Z')

    def test_every_compared_field_matches_and_errors_are_measured_not_inferred(self):
        self.assertEqual(self.result['mismatches'],[])
        self.assertEqual(self.result['max_abs_error'],0)
        for key,result in self.result['by_field'].items():
            self.assertEqual(result['compared'],33,key)
            self.assertEqual(result['mismatches'],0,key)
            self.assertEqual(result['max_abs_error'],0,key)

    def test_first_cycle_levels_match_but_full_cycle_not_claimed(self):
        first,*later=self.result['measurement_records']
        self.assertEqual(first['HIGH'],78285)
        self.assertEqual(first['LOW'],77517.2)
        self.assertEqual(first['SUPERIOR'],78653.4351)
        self.assertEqual(first['INFERIOR'],77095.25)
        self.assertEqual(first['displayed_SUPERIOR'],'78653.44')
        self.assertFalse(first['complete_ohlc_replay_validated'])
        self.assertTrue(all(x['complete_ohlc_replay_validated'] for x in later))

    def test_only_two_of_three_original_pine_signals_replay_validated(self):
        s=self.result['logged_PINE_A_signals']
        self.assertEqual(len(s),3);self.assertEqual(self.result['replay_validated_signal_count'],2)
        self.assertIsNone(s[0]['python_confirmation'])
        self.assertTrue(s[1]['python_confirmation']);self.assertTrue(s[2]['python_confirmation'])

    def test_signal_times_distinguish_open_from_confirmation(self):
        _,short,long=self.result['logged_PINE_A_signals']
        self.assertEqual((short['bar_open_utc'],short['confirmed_at_utc']),
                         ('2026-11-02T11:00:00Z','2026-11-02T12:00:00Z'))
        self.assertEqual((long['bar_open_utc'],long['confirmed_at_utc']),
                         ('2026-11-03T12:00:00Z','2026-11-03T13:00:00Z'))

    def test_original_three_close_only_signals_do_not_satisfy_body(self):
        self.assertTrue(all(not s['whole_body_on_PINE_A_levels'] for s in self.result['logged_PINE_A_signals']))

    def test_body_examples_are_later_bars_and_not_mislabeled_owner(self):
        a,b=self.result['PINE_A_body_diagnostics']
        self.assertEqual((a['bar_open_utc'],a['confirmed_at_utc']),
                         ('2026-11-02T12:00:00Z','2026-11-02T13:00:00Z'))
        self.assertEqual((b['bar_open_utc'],b['confirmed_at_utc']),
                         ('2026-11-03T13:00:00Z','2026-11-03T14:00:00Z'))
        self.assertIn('NOT_OWNER_B',a['interpretation'])

    def test_dst_fold_preserves_hourly_utc_continuity(self):
        rows=self.result['dst_clock']
        self.assertEqual(rows[1]['new_york'],'2026-11-01T01:00:00-04:00')
        self.assertEqual(rows[2]['new_york'],'2026-11-01T01:00:00-05:00')
        self.assertEqual(rows[2]['fold'],1)
        self.assertEqual(rows[2]['owner_fixed_utc4'],'2026-11-01T02:00:00-04:00')
        self.assertFalse(rows[2]['inLondon_PINE_A']);self.assertTrue(rows[3]['inLondon_PINE_A'])


class OwnerReviewEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=review()

    def test_complete_owner_pairs_independent_from_pine_a(self):
        r=self.result;self.assertEqual((r['complete_pairs'],r['first_confirmations']),(2,2))
        incomplete,short,long=r['cycles']
        self.assertEqual(incomplete['status'],'EXCLUDED_INITIAL_PARTIAL_PAIR')
        self.assertIsNone(incomplete['asia_open_utc'])
        self.assertEqual(short['levels_available_at_utc'],'2026-11-02T09:00:00Z')
        self.assertEqual(long['levels_available_at_utc'],'2026-11-03T09:00:00Z')
        self.assertAlmostEqual(long['levels']['lowGuideValue'],76388.88)
        self.assertNotEqual(long['levels']['newTopTarget'],77939.27199999998)

    def test_do_not_consume_pine_state_or_levels_in_owner_replay(self):
        rows=load_evidence();modified=copy.deepcopy(rows)
        for row in modified:
            row['globalHigh']=1;row['globalLow']=1;row['targetTop']=1;row['aHigh']=1
        def trace(source):
            e=Replay(OWNER_B)
            return [e.append(b,as_of=b.available_at) for b in bars_from_rows(source)]
        self.assertEqual(trace(rows),trace(modified))

    def test_two_full_body_signals_not_none_in_owner(self):
        _,short,long=self.result['cycles']
        self.assertEqual(short['signal']['confirmed_at_utc'],'2026-11-02T13:00:00Z')
        self.assertEqual(long['signal']['confirmed_at_utc'],'2026-11-03T14:00:00Z')
        for c in (short,long):
            s=c['signal'];self.assertIsNotNone(s['atr14_at_confirmation'])
            if s['side']=='LONG':
                self.assertGreater(min(s['signal_open'],s['signal_close']),D(str(c['levels']['highGuideValue'])))
            else:
                self.assertLess(max(s['signal_open'],s['signal_close']),D(str(c['levels']['lowGuideValue'])))

    def test_advance_200_preserved_and_filter_rejects_both_under_frozen_costs(self):
        for c in self.result['cycles'][1:]:
            r=c['signal']['plan_at_close']
            self.assertFalse(r['accepted'])
            self.assertLess(r['net_rr'],D('1.5'))
            self.assertEqual(abs(r['theoretical_target']-r['advanced_tp']),D(200))
            self.assertEqual(c['status'],'REJECTED_AT_CONFIRMATION')

    def test_after_close_next_open_is_only_a_reference_not_real_fill(self):
        for c in self.result['cycles'][1:]:
            s=c['signal'];p=s['plan_at_close']
            self.assertEqual(s['confirmed_at_utc'],s['next_open_reference_utc'])
            self.assertIn('NOT_AVAILABLE',s['actual_executable_quote'])
            self.assertIsNone(p['actual_fill'])
            self.assertFalse(p['operational_paper_authorized'])

    def test_both_stops_occur_before_later_targets_no_invented_profit(self):
        for c in self.result['cycles'][1:]:
            s=c['signal'];path=s['reference_path']
            self.assertEqual(path['first_event']['kind'],'SL')
            self.assertLess(path['sl_touch']['bar_open_utc'],path['advanced_tp_touch']['bar_open_utc'])
            self.assertLess(path['advanced_tp_touch']['bar_open_utc'],path['theoretical_target_touch']['bar_open_utc'])
            self.assertIsNone(s['realized_net_pnl'])
        self.assertEqual(self.result['entered_scenarios'],0)
        self.assertEqual(self.result['matured_scenarios'],0)
        self.assertIn('INSUFFICIENT',self.result['profitability_conclusion'])

    def test_protocol_was_frozen_and_does_not_change_existing_rules(self):
        self.assertEqual(hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
                         '6ae03fc0315cf5ad81d4bdb47690518140ebb8f21c6ea1893313f63261e127dc')

    def test_real_report_build_keeps_parity_and_owner_results_separate(self):
        from .real_artifacts import write_artifacts
        with TemporaryDirectory() as directory:
            p,b=write_artifacts(Path(directory))
            self.assertEqual(p['input_rows'],64)
            self.assertEqual(p['complete_cycles'],2)
            self.assertEqual(b['profile'],'OWNER_B')
            self.assertNotIn('realized_net_pnl',p)


class ChronologicalPaperMechanics(unittest.TestCase):
    def candle(self,hour,o=100,hi=110,lo=90,c=100):
        return Candle(hour*HOUR,o,hi,lo,c)

    def test_confirmation_bar_tp_or_stop_never_counts(self):
        bars=[self.candle(0,hi=200,lo=1),self.candle(1)]
        r=first_touches('LONG',85,120,130,bars,HOUR,3*HOUR)
        self.assertIsNone(r['first_event']);self.assertIsNone(r['theoretical_target_touch'])

    def test_gap_in_outcome_window_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'NON_CONTIGUOUS'):
            first_touches('LONG',85,120,130,[self.candle(1),self.candle(3)],HOUR,4*HOUR)

    def test_both_in_same_bar_adverse_stop_first(self):
        r=first_touches('LONG',85,120,130,[self.candle(1,hi=125,lo=75)],HOUR,3*HOUR)
        self.assertEqual(r['first_event']['kind'],'SL');self.assertTrue(r['first_event']['ambiguous'])

    def test_stop_gap_uses_worse_open(self):
        r=first_touches('LONG',85,120,130,[self.candle(1,o=70,hi=80,lo=65,c=75)],HOUR,3*HOUR)
        self.assertEqual(r['first_event']['reference_exit'],70)
        r=first_touches('SHORT',115,80,70,[self.candle(1,o=130,hi=140,lo=125,c=135)],HOUR,3*HOUR)
        self.assertEqual(r['first_event']['reference_exit'],130)

    def test_tp_gap_does_not_assume_better_fill(self):
        r=first_touches('LONG',85,120,140,[self.candle(1,o=130,hi=135,lo=125,c=130)],HOUR,3*HOUR)
        self.assertEqual(r['first_event']['reference_exit'],120)

    def test_original_target_later_is_not_first_trade_outcome(self):
        bars=[self.candle(1,hi=110,lo=80),self.candle(2,hi=140)]
        r=first_touches('LONG',85,120,130,bars,HOUR,4*HOUR)
        self.assertEqual(r['first_event']['kind'],'SL')
        self.assertIsNotNone(r['theoretical_target_touch'])

    def plan(self):
        signal=Candle(0,80010,80020,80000,80010)
        snapshot=dict(profile='OWNER_B',data_complete=True,longBreak=True,shortBreak=False,
            time=0,available_at=HOUR,atr14=100,
            frozen=dict(newTopTarget=80700,newBottomTarget=78300,
                        highGuideValue=80000,lowGuideValue=79000))
        return snapshot,signal

    def test_censor_no_false_early_exit_or_win(self):
        snapshot,signal=self.plan()
        nextbar=Candle(HOUR,80010,80020,80000,80010)
        r=evaluate_signal(snapshot,signal,[signal,nextbar],D(10000),ZERO)
        self.assertEqual(r['outcome'],'RIGHT_CENSORED');self.assertIsNone(r['realized_net_pnl'])

    def test_tp_after_entry_has_profit_but_not_unreached_original_target(self):
        snapshot,signal=self.plan()
        nextbar=Candle(HOUR,80010,80600,80000,80500)
        r=evaluate_signal(snapshot,signal,[signal,nextbar],D(10000),ZERO)
        self.assertEqual(r['outcome'],'TP');self.assertGreater(r['realized_net_pnl'],0)
        self.assertIsNone(r['trade_path']['theoretical_target_touch'])

    def test_no_next_bar_no_simulated_entry(self):
        snapshot,signal=self.plan()
        r=evaluate_signal(snapshot,signal,[signal],D(10000),ZERO)
        self.assertEqual(r['execution_status'],'PENDING_NEXT_OPEN');self.assertIsNone(r['realized_net_pnl'])

    def test_next_open_invalidates_ordering_without_moving_stop(self):
        p=dict(side='LONG',stop=D(79980),advanced_tp=D(80500))
        r=reprice(p,80600,D(10000),ZERO)
        self.assertFalse(r['accepted']);self.assertEqual(p['stop'],79980)


if __name__=='__main__':
    unittest.main()
