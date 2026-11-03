"""Causal history and explicit stress blockers; synthetic mechanics, no network."""
import ast
import copy
import csv
import gzip
from decimal import Decimal as D
import hashlib
import json
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from ..core import Candle,HOUR
from ..risk import Costs
from ..profiles import OWNER_B
from .data import HERE,Minute,MINUTE,read_archive,verify_aggregation,spec
from .evaluate import build_cycles,price_outcome,settle_trade,drawdown,conservative_bound,bootstrap_mean_r
from .stress import budget,linear_solvency_threshold,require_verified_inputs,result

ZERO=Costs(D(0),D(0),D(0),D(0),D(0),'SYNTHETIC_TEST_ONLY')


def minute(i,o=100,h=101,l=99,c=100):return Minute(i*MINUTE,o,h,l,c)


class DataTests(unittest.TestCase):
    def archive(self,row):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'fixture.zip'
        with ZipFile(path,'w') as f:f.writestr('fixture.csv',','.join(map(str,row))+'\n')
        return path

    def row(self):
        t=1761955200000
        return [t*1000,'100','110','90','105','10',(t+HOUR)*1000-1,'1000','5','4','400','0']

    def test_microseconds_are_explicitly_normalized(self):
        b=read_archive(self.archive(self.row()),'1h')[0]
        self.assertEqual(b.open_time,1761955200000);self.assertEqual(b.available_at,1761958800000)

    def test_milliseconds_not_silently_misinterpreted(self):
        r=self.row();r[0]//=1000;r[6]//=1000
        with self.assertRaisesRegex(ValueError,'MICROSECONDS'):read_archive(self.archive(r),'1h')

    def test_bad_close_time_fails(self):
        r=self.row();r[6]-=1
        with self.assertRaisesRegex(ValueError,'TIME_MISMATCH'):read_archive(self.archive(r),'1h')

    def test_bad_schema_fails(self):
        with self.assertRaisesRegex(ValueError,'NOT_12'):read_archive(self.archive(self.row()[:11]),'1h')

    def test_bad_ohlc_fails(self):
        r=self.row();r[2]='99'
        with self.assertRaisesRegex(ValueError,'OHLC'):read_archive(self.archive(r),'1h')

    def test_aggregation_exact_not_tolerance_fitted(self):
        h=[Candle(0,100,101,99,100)];m=[minute(i) for i in range(60)]
        self.assertEqual(verify_aggregation(h,m),1)
        changed=copy.copy(m);changed[-1]=minute(59,c=100.01)
        with self.assertRaisesRegex(ValueError,'MISMATCH'):verify_aggregation(h,changed)

    def test_partial_hour_fails(self):
        with self.assertRaisesRegex(ValueError,'PARTIAL'):verify_aggregation([], [minute(0)])


class FrozenRulesTests(unittest.TestCase):
    def test_dates_costs_and_rules_are_fixed(self):
        s=spec()
        self.assertEqual(s['evaluation_start_inclusive'],'2025-11-01T00:00:00Z')
        self.assertEqual(s['evaluation_end_exclusive'],'2026-11-01T00:00:00Z')
        self.assertEqual(s['expected_evaluation_cycles'],365)
        self.assertEqual((s['tp_advance_price'],s['atr_stop_buffer'],s['minimum_net_rr']),('200','0.20','1.5'))
        self.assertEqual(s['entry_fee_rate'],'0.001');self.assertEqual(s['entry_slippage_rate'],'0.0002')

    def test_body_control_keeps_identical_sessions_and_levels(self):
        s=spec();s.update(evaluation_start_inclusive='1970-01-01T00:00:00Z',
            evaluation_end_exclusive='1970-01-03T00:00:00Z',expected_evaluation_cycles=2)
        bars=[Candle(i*HOUR,100,110,90,100) for i in range(48)]
        a=build_cycles(bars,s,True);b=build_cycles(bars,s,False)
        self.assertEqual([c['levels'] for c in a],[c['levels'] for c in b])

    def test_no_future_candle_needed_for_levels(self):
        s=spec();s.update(evaluation_start_inclusive='1970-01-01T00:00:00Z',
            evaluation_end_exclusive='1970-01-03T00:00:00Z',expected_evaluation_cycles=2)
        bars=[Candle(i*HOUR,100,110,90,100) for i in range(48)]
        before=build_cycles(bars,s)
        changed=bars[:];changed[-1]=Candle(47*HOUR,100,1000,1,100)
        after=build_cycles(changed,s)
        self.assertEqual(before[0]['levels'],after[0]['levels'])

    def test_study_not_imported_by_production(self):
        root=HERE.parents[2]
        manifest=json.loads((HERE.parent/'fixtures/protected_runtime_hashes.json').read_text())
        for path,expected in manifest['files'].items():
            raw=(root/path).read_bytes().replace(b'\r\n',b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),expected,path)
            self.assertNotIn(b'alpha_arcanox_pine_v37',raw,path)

    def test_data_download_has_no_credentials_or_mutating_http(self):
        source=(HERE/'download.py').read_text(encoding='utf-8')
        self.assertIn('https://data.binance.vision/data/spot/',source)
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,('post','put','patch','delete'))
        self.assertNotIn('Authorization',source);self.assertNotIn('APIKEY',source)


class PriceAndTradeTests(unittest.TestCase):
    def cycle(self):
        return dict(side='LONG',signal_close=100,available_at=MINUTE,
            atr14=10,levels=dict(newTopTarget=120,newBottomTarget=80,highGuideValue=100,lowGuideValue=90))

    def test_theoretical_target_after_stop_is_not_target_first(self):
        r=price_outcome(self.cycle(),[minute(1,l=90),minute(2,h=125)])
        self.assertEqual(r['order'],'SL_FIRST');self.assertIsNotNone(r['theoretical_touch'])

    def test_same_minute_target_stop_stays_ambiguous(self):
        r=price_outcome(self.cycle(),[minute(1,h=125,l=90)])
        self.assertEqual(r['order'],'SAME_MINUTE_AMBIGUOUS')

    def test_already_behind_target_not_counted_as_predictive_hit(self):
        c=self.cycle();c['signal_close']=130
        r=price_outcome(c,[minute(1,h=140)])
        self.assertFalse(r['target_ahead']);self.assertIsNone(r['theoretical_touch'])

    def test_empty_post_confirmation_window_not_a_failure(self):
        r=price_outcome(self.cycle(),[])
        self.assertEqual(r['coverage'],'NO_POST_CONFIRMATION_TIME')

    def trade(self):
        return dict(side='LONG',stop=D(95),advanced_tp=D(110)),dict(quantity_btc=D(1),
            adverse_entry_scenario=D(100),net_risk_per_btc=D(5),estimated_stop_loss=D(5),
            risk_budget=D(10),notional=D(100))

    def test_intraminute_ambiguity_adverse_first(self):
        p,e=self.trade();r,_,_=settle_trade(p,e,[minute(1,h=115,l=90)],D(1000),ZERO)
        self.assertEqual(r['outcome'],'SL');self.assertEqual(r['net_pnl'],-5)
        self.assertTrue(r['ambiguous_same_minute'])

    def test_next_minute_tp_can_follow_earlier_stop_but_trade_stays_loss(self):
        p,e=self.trade();r,_,_=settle_trade(p,e,[minute(1,l=90),minute(2,h=115)],D(1000),ZERO)
        self.assertEqual(r['net_pnl'],-5);self.assertEqual(r['exit_minute'],MINUTE)

    def test_stop_gap_uses_worse_open(self):
        p,e=self.trade();r,_,_=settle_trade(p,e,[minute(1,o=90,h=92,l=89,c=90)],D(1000),ZERO)
        self.assertEqual(r['net_pnl'],-10)

    def test_fees_and_slippage_not_double_counted(self):
        p,e=self.trade();fees=Costs(D('.001'),D('.001'),D(0),D('.001'),D(0),'TEST')
        r,_,_=settle_trade(p,e,[minute(1,h=115,l=99)],D(1000),fees)
        expected=(D(110)*D('.999')-100)-D('.001')*100-D('.001')*(D(110)*D('.999'))
        self.assertEqual(r['net_pnl'],expected)

    def test_timeout_preserves_all_equity_not_reset(self):
        p,e=self.trade();r,_,_=settle_trade(p,e,[minute(1,c=100.5)],D(900),ZERO)
        self.assertEqual(r['outcome'],'TIME_EXIT');self.assertEqual(r['capital_after'],D('900.5'))

    def test_drawdown_uses_path_not_just_final_return(self):
        self.assertAlmostEqual(drawdown([100,120,90,110]),25)
        self.assertAlmostEqual(conservative_bound([(0,100),(2,120),(4,110)],[(3,120,90)]),25)

    def test_drawdown_bound_covers_exit_fees_and_unknown_intraminute_order(self):
        self.assertGreaterEqual(conservative_bound([(0,100),(2,90)],[(2,105,95)]),10)
        self.assertAlmostEqual(conservative_bound([(0,100),(2,100)],[(2,150,90)]),40)

    def test_bootstrap_is_deterministic_and_empty_is_not_edge(self):
        s=spec();s['bootstrap']=dict(seed=1,replicates=20,circular_block_days=2)
        cycles=[{},dict(trade=dict(net_R=D(1))),dict(trade=dict(net_R=D(-2)))]
        self.assertEqual(bootstrap_mean_r(cycles,s),bootstrap_mean_r(cycles,s))
        self.assertEqual(bootstrap_mean_r([{},{}],s),[None,None])


class StressTests(unittest.TestCase):
    def test_40_times_half_equity_is_twenty_times_account_notional(self):
        b=budget(10000)
        self.assertEqual(b['initial_margin'],5000);self.assertEqual(b['notional'],200000)

    def test_remaining_equity_reduces_next_margin(self):
        first=budget(10000);remaining=first['equity']-first['initial_margin'];second=budget(remaining)
        self.assertEqual(second['initial_margin'],2500);self.assertEqual(second['notional'],100000)

    def test_invalid_equity_never_gets_new_budget(self):
        for e in (0,-1):
            with self.assertRaises(ValueError):budget(e)

    def test_synthetic_margin_equation_is_symmetric_in_solvency_not_assumed_tier(self):
        long=linear_solvency_threshold(100,1,2.5,'LONG','.004',0)
        short=linear_solvency_threshold(100,1,2.5,'SHORT','.004',0)
        self.assertLess(long,100);self.assertGreater(short,100)
        self.assertLess(abs((D('2.5')+long-100)-long*D('.004')),D('1e-20'))

    def test_missing_verified_inputs_block_historical_stress(self):
        with self.assertRaisesRegex(ValueError,'MISSING_VERIFIED'):require_verified_inputs({})

    def test_blocked_liquidations_and_ruin_are_none_not_zero(self):
        r=result();self.assertEqual(r['status'],'BLOCKED_NOT_EVALUABLE')
        for m in r['modes'].values():
            self.assertIsNone(m['liquidations']);self.assertIsNone(m['net_pnl'])
            self.assertIsNone(m['probability_of_ruin'])
        self.assertFalse(r['rr_filter_applied']);self.assertFalse(r['stop_loss_added'])


class ActualStudyArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.art=HERE/'artifacts'
        cls.data=json.loads(gzip.decompress((cls.art/'study_results.json.gz').read_bytes()))

    def test_all_365_cycles_exist_in_each_arm_and_csv(self):
        for arm in self.data['arms']:
            self.assertEqual(len(arm['cycles']),365)
            self.assertEqual(len({c['date'] for c in arm['cycles']}),365)
            with (self.art/('cycles_'+arm['variant']+'.csv')).open(encoding='utf-8',newline='') as f:
                self.assertEqual(len(list(csv.DictReader(f))),365)

    def test_no_capital_reset_between_losses_months_or_rejections(self):
        for arm in self.data['arms']:
            equity=D(10000)
            for c in arm['cycles']:
                self.assertEqual(D(c['capital_before']),equity)
                if 'trade' in c:equity=D(c['trade']['capital_after'])
            self.assertAlmostEqual(float(equity),arm['summary']['strategy']['ending_realized_equity'])

    def test_monthly_net_sums_to_total_with_actual_remaining_equity(self):
        for arm in self.data['arms']:
            self.assertAlmostEqual(sum(v['strategy']['net_pnl'] for v in arm['summary']['monthly'].values()),
                                   arm['summary']['strategy']['net_pnl'])
            self.assertAlmostEqual(list(arm['summary']['monthly'].values())[-1]['strategy']['ending_realized_equity'],
                                   arm['summary']['strategy']['ending_realized_equity'])

    def test_trade_entries_are_after_signal_and_no_real_leverage(self):
        for arm in self.data['arms']:
            for c in arm['cycles']:
                if 'trade' not in c:continue
                t=c['trade']
                self.assertEqual(t['entry_time'],c['available_at'])
                self.assertGreaterEqual(t['exit_minute'],t['entry_time'])
                self.assertLess(t['exit_minute'],c['expiry'])
                self.assertLessEqual(D(t['notional']),D(t['capital_before']))
                self.assertLessEqual(D(t['estimated_stop_risk']),D(t['capital_before'])*D('.0025'))

    def test_all_trade_costs_reconcile(self):
        for arm in self.data['arms']:
            for c in arm['cycles']:
                if 'trade' not in c:continue
                t=c['trade'];net=D(t['net_pnl'])
                expected=D(t['gross_before_costs'])-D(t['slippage_cost'])-D(t['entry_fee'])-D(t['exit_fee'])
                self.assertLess(abs(net-expected),D('1e-18'))

    def test_current_study_also_fits_entry_fee_inside_available_equity(self):
        for arm in self.data['arms']:
            for c in arm['cycles']:
                if 'trade' in c:
                    t=c['trade']
                    self.assertLessEqual(D(t['notional'])+D(t['entry_fee']),D(t['capital_before']))

    def test_drawdown_bound_never_below_observed_drawdown(self):
        for arm in self.data['arms']:
            for entry in [arm['summary']]+list(arm['summary']['monthly'].values()):
                s=entry['strategy']
                self.assertGreaterEqual(s['adverse_minute_drawdown_upper_bound_pct']+1e-10,
                                        s['minute_close_mtm_max_drawdown_pct'])

    def test_sensitivity_is_identical_in_sessions_and_levels_not_pine_a(self):
        a,b=self.data['arms']
        self.assertEqual([c['levels'] for c in a['cycles']],[c['levels'] for c in b['cycles']])
        self.assertTrue(self.data['price_control_comparison']['sessions_and_levels_exactly_identical'])

    def test_data_provenance_has_all_official_checksums_and_units(self):
        d=self.data['data'];self.assertEqual((d['h1_rows'],d['m1_rows'],d['exact_aggregated_hours']),(9504,525600,8760))
        for key,n in (('h1_manifest',13),('m1_manifest',12)):
            self.assertEqual(len(d[key]['archives']),n)
            for archive in d[key]['archives']:
                self.assertTrue(archive['official_checksum_verified'])
                self.assertIn('/spot/',archive['url']);self.assertEqual(archive['source_time_unit'],'microseconds')

    def test_reporting_fix_preserved_ledgers_and_classification(self):
        first=json.loads(gzip.decompress((self.art/'first_result_before_dd_reporting_fix.json.gz').read_bytes()))
        for a,b in zip(first['arms'],self.data['arms']):
            self.assertEqual(a['cycles'],b['cycles']);self.assertEqual(a['equity_curve'],b['equity_curve'])
            self.assertEqual(a['classification'],b['classification'])

    def test_versioned_artifacts_have_valid_checksums(self):
        manifest=json.loads((self.art/'artifact_manifest.json').read_text())
        for filename,record in manifest['files'].items():
            raw=(self.art/filename).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),record['sha256'],filename)

    def test_hourly_public_input_is_causal_contiguous_and_includes_only_closed_window(self):
        rows=list(csv.DictReader(io.StringIO(gzip.decompress((self.art/'hourly_input.csv.gz').read_bytes()).decode())))
        times=[int(x['open_time']) for x in rows]
        self.assertEqual(len(times),9504)
        self.assertTrue(all(b-a==HOUR for a,b in zip(times,times[1:])))


if __name__=='__main__':unittest.main()
