"""Own mechanics fixtures are explicitly NOT independent TradingView evidence."""
import ast
import copy
import hashlib
import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from .core import Candle, HOUR, ATR14, display_tick, project, session_member
from .profiles import PINE_A, OWNER_B, SOURCE_SHA256
from .replay import Replay
from .risk import Costs, paper_plan
from .source_audit import audit, diagnostic_bytes, SOURCE, SOURCE_HASH
from .parity import compare, NUMERIC, BOOLEAN

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def stamp(s):
    return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)


def bar(t,o=100,h=110,l=90,c=100):
    return Candle(t,o,h,l,c)


def stream(profile=PINE_A,start='2026-10-30T23:00:00Z',count=28,overrides=None):
    t=stamp(start);overrides=overrides or {}
    return [bar(t+i*HOUR,**overrides.get(i,{})) for i in range(count)]


def run(bars,profile=PINE_A):
    e=Replay(profile)
    return [e.append(b,as_of=b.available_at) for b in bars]


class FormulaTests(unittest.TestCase):
    def test_staggered_asia_below(self):
        v=project(100,90,120,110)
        self.assertEqual(v['amplitude'],30)
        self.assertTrue(v['topInAsia']);self.assertFalse(v['bottomInAsia'])
        self.assertAlmostEqual(v['newTopTarget'],129.7)
        self.assertAlmostEqual(v['newBottomTarget'],80.3)

    def test_staggered_london_below(self):
        v=project(120,110,100,90)
        self.assertFalse(v['topInAsia']);self.assertTrue(v['bottomInAsia'])
        self.assertAlmostEqual(v['newTopTarget'],129.7)
        self.assertAlmostEqual(v['newBottomTarget'],80.3)

    def test_overlapping_boxes_not_rejected(self):
        v=project(110,90,120,100)
        self.assertAlmostEqual(v['topAnchor'],109.4)
        self.assertAlmostEqual(v['bottomAnchor'],100.6)

    def test_asia_contains_london_anchors_inside_london(self):
        v=project(120,80,110,90)
        self.assertFalse(v['topInAsia']);self.assertFalse(v['bottomInAsia'])
        self.assertEqual(v['amplitude'],40)
        self.assertAlmostEqual(v['newTopTarget'],149.4)
        self.assertAlmostEqual(v['newBottomTarget'],50.6)

    def test_london_contains_asia_anchors_inside_asia(self):
        v=project(110,90,120,80)
        self.assertTrue(v['topInAsia']);self.assertTrue(v['bottomInAsia'])

    def test_ties_choose_asia_in_both_comparisons(self):
        v=project(110,90,110,90)
        self.assertTrue(v['topInAsia']);self.assertTrue(v['bottomInAsia'])

    def test_zero_height_legal_pine_not_paper_trade(self):
        v=project(100,100,100,100)
        self.assertEqual(v['amplitude'],0)
        self.assertEqual(v['newTopTarget'],100)
        self.assertEqual(v['newBottomTarget'],100)

    def test_insets_are_box_height_not_btc_percent(self):
        v=project(80000,79000,81000,79500)
        self.assertEqual(v['topAnchor'],79970)
        self.assertEqual(v['bottomAnchor'],79545)
        self.assertNotEqual(v['topAnchor'],80000*.97)

    def test_guides_global_extrema_not_anchors(self):
        v=project(100,90,120,110)
        self.assertEqual((v['highGuideValue'],v['lowGuideValue']),(120,90))
        self.assertNotEqual(v['topAnchor'],v['highGuideValue'])

    def test_binary64_values_not_tick_rounded(self):
        v=project(100.01,90.02,120.03,110.04)
        self.assertAlmostEqual(v['topAnchor'],99.7103)
        self.assertEqual(display_tick(v['topAnchor'],.01),'99.71')
        self.assertNotEqual(v['topAnchor'],float(display_tick(v['topAnchor'],.01)))

    def test_display_ties_round_up(self):
        self.assertEqual(display_tick(100.005,.01),'100.01')

    def test_invalid_ohlc_rejected(self):
        for args in ((100,110,90,80),(100,float('nan'),90,100)):
            with self.assertRaises(ValueError):bar(0,*args)

    def test_invalid_box_rejected(self):
        with self.assertRaises(ValueError):project(90,100,120,110)

    def test_atr_seed_and_wilder(self):
        a=ATR14()
        for i in range(13):self.assertIsNone(a.append(bar(i*HOUR)))
        self.assertEqual(a.append(bar(13*HOUR)),20)
        self.assertAlmostEqual(a.append(bar(14*HOUR,h=120,l=80)),20+20/14)


class ClockAndSequenceTests(unittest.TestCase):
    def test_profile_a_defaults_exact(self):
        self.assertEqual((PINE_A.timezone_name,PINE_A.asia_start,PINE_A.asia_candles,
                          PINE_A.london_start,PINE_A.london_candles),('America/New_York',20,4,2,4))
        self.assertFalse(PINE_A.whole_body);self.assertTrue(PINE_A.independent_sides)

    def test_profile_b_fixed_and_full_body(self):
        self.assertEqual((OWNER_B.timezone_name,OWNER_B.asia_candles,OWNER_B.london_start),('UTC-4',5,1))
        self.assertTrue(OWNER_B.whole_body);self.assertFalse(OWNER_B.independent_sides)

    def test_a_summer_asia_and_london(self):
        bars=stream(count=32);out=run(bars)
        asia=[x['time'] for x in out if x['inAsia']]
        self.assertEqual(asia[:4],[stamp('2026-10-31T00:00:00Z')+i*HOUR for i in range(4)])
        london=[x['time'] for x in out if x['inLondon']]
        self.assertEqual(london[:4],[stamp('2026-10-31T06:00:00Z')+i*HOUR for i in range(4)])

    def test_a_winter_moves_one_hour(self):
        bars=stream(start='2026-11-03T00:00:00Z');out=run(bars)
        self.assertEqual(next(x['time'] for x in out if x['inAsia']),stamp('2026-11-03T01:00:00Z'))
        self.assertEqual(next(x['time'] for x in out if x['inLondon']),stamp('2026-11-03T07:00:00Z'))

    def test_b_utc4_includes_midnight_and_01_london(self):
        out=run(stream(count=20),OWNER_B)
        self.assertEqual([x['time'] for x in out if x['inAsia']],
                         [stamp('2026-10-31T00:00:00Z')+i*HOUR for i in range(5)])
        self.assertEqual([x['time'] for x in out if x['inLondon']],
                         [stamp('2026-10-31T05:00:00Z')+i*HOUR for i in range(4)])

    def test_b_does_not_shift_in_winter(self):
        b=bar(stamp('2026-11-03T00:00:00Z'))
        self.assertTrue(session_member(b,OWNER_B,20,5))
        self.assertFalse(session_member(b,PINE_A,20,4))

    def test_fall_dst_a_london_still_four_bars(self):
        out=run(stream(start='2026-10-31T23:00:00Z',count=20))
        self.assertEqual(sum(x['inLondon'] for x in out),4)
        self.assertEqual(sum(x['measureNow'] for x in out),1)

    def test_spring_dst_nonexistent_02_prevents_measurement(self):
        out=run(stream(start='2026-03-08T00:00:00Z',count=18))
        self.assertEqual(sum(x['inLondon'] for x in out),3)
        self.assertEqual(sum(x['measureNow'] for x in out),0)

    def test_levels_first_outside_london_not_its_last_bar(self):
        out=run(stream())
        m=next(x for x in out if x['measureNow'])
        self.assertEqual(m['time'],stamp('2026-10-31T10:00:00Z'))
        self.assertEqual(m['frozen']['levels_available_at'],m['time'])
        previous=out[out.index(m)-1]
        self.assertFalse(previous['pairReady'])
        self.assertEqual(m['available_at'],stamp('2026-10-31T11:00:00Z'))

    def test_half_bar_drawing_boundaries(self):
        m=next(x for x in run(stream()) if x['measureNow'])['frozen']
        self.assertEqual(m['asia_left'],stamp('2026-10-30T23:30:00Z'))
        self.assertEqual(m['asia_right'],stamp('2026-10-31T03:30:00Z'))
        self.assertEqual(m['london_right'],stamp('2026-10-31T09:30:00Z'))

    def test_literal_new_targets_outside_measurement_vs_frozen_targets(self):
        out=run(stream());i=next(i for i,x in enumerate(out) if x['measureNow'])
        self.assertIsNone(out[i+1]['amplitude'])
        self.assertEqual(out[i+1]['newTopTarget'],out[i+1]['topAnchor'])
        self.assertEqual(out[i+1]['targetTop'],out[i]['newTopTarget'])

    def test_missing_session_candle_not_completed(self):
        bars=stream();del bars[8]
        self.assertFalse(any(x['measureNow'] for x in run(bars)))

    def test_missing_inter_session_hour_retains_literal_pine_but_quality_false(self):
        bars=stream();del bars[5] # 04:00 UTC, outside both A sessions
        m=next(x for x in run(bars) if x['measureNow'])
        self.assertFalse(m['data_complete'])

    def test_partial_initial_asia_does_not_form_pair(self):
        self.assertFalse(any(x['measureNow'] for x in run(stream(start='2026-10-31T02:00:00Z',count=15))))

    def test_duplicate_rejected(self):
        e=Replay();b=bar(0);e.append(b)
        with self.assertRaises(ValueError):e.append(b)

    def test_open_candle_rejected_without_mutation(self):
        e=Replay();b=bar(0)
        with self.assertRaises(ValueError):e.append(b,as_of=HOUR-1)
        self.assertEqual(e.index,-1)

    def test_prefix_invariance(self):
        bars=stream(count=60)
        self.assertEqual(run(bars[:20]),run(bars)[:20])

    def test_preview_does_not_commit(self):
        e=Replay();r=e.preview(bar(0),HOUR)
        self.assertEqual(e.index,-1);self.assertEqual(r['time'],0)


class ConfirmationTests(unittest.TestCase):
    def setup_signal(self,profile=PINE_A,**ohlc):
        bars=stream(profile)
        # A first outside=10:00Z; B first outside=09:00Z.
        idx=11 if profile is PINE_A else 10
        bars[idx]=bar(bars[idx].open_time,**ohlc)
        return bars,idx,run(bars,profile)

    def test_a_close_only_crossing_body_accepted(self):
        _,i,out=self.setup_signal(o=100,h=120,l=99,c=115)
        self.assertTrue(out[i]['highConfirmed']);self.assertTrue(out[i]['longBreak'])

    def test_b_crossing_body_rejected(self):
        _,i,out=self.setup_signal(OWNER_B,o=100,h=120,l=99,c=115)
        self.assertFalse(out[i]['highConfirmed'])

    def test_b_whole_body_long_accepted(self):
        _,i,out=self.setup_signal(OWNER_B,o=111,h=120,l=99,c=115)
        self.assertTrue(out[i]['longBreak'])

    def test_b_whole_body_short_accepted(self):
        _,i,out=self.setup_signal(OWNER_B,o=89,h=99,l=80,c=85)
        self.assertTrue(out[i]['shortBreak'])

    def test_equality_is_not_confirmation(self):
        for p,o,h,l,c in ((PINE_A,100,111,90,110),(OWNER_B,110,120,99,115),
                           (OWNER_B,90,100,80,85)):
            _,i,out=self.setup_signal(p,o=o,h=h,l=l,c=c)
            self.assertFalse(out[i]['highConfirmed'] or out[i]['lowConfirmed'])

    def test_wick_only_no_confirmation(self):
        _,i,out=self.setup_signal(o=100,h=150,l=50,c=100)
        self.assertFalse(out[i]['highConfirmed'] or out[i]['lowConfirmed'])

    def test_pine_independent_one_alert_each_side_first_direction_stays(self):
        bars,i,_=self.setup_signal(o=100,h=120,l=99,c=115)
        bars[i+1]=bar(bars[i+1].open_time,115,120,100,116)
        bars[i+2]=bar(bars[i+2].open_time,100,101,80,85)
        out=run(bars)
        self.assertEqual(sum(x['highConfirmed'] for x in out),1)
        self.assertEqual(sum(x['lowConfirmed'] for x in out),1)
        self.assertFalse(out[i+2]['shortBreak']);self.assertEqual(out[i+2]['direction'],1)

    def test_owner_records_only_first_side(self):
        bars,i,_=self.setup_signal(OWNER_B,o=111,h=120,l=99,c=115)
        bars[i+1]=bar(bars[i+1].open_time,89,95,80,85)
        out=run(bars,OWNER_B)
        self.assertFalse(out[i+1]['lowConfirmed'])

    def test_no_band_alert_same_signal_candle(self):
        _,i,out=self.setup_signal(o=100,h=200,l=99,c=115)
        self.assertFalse(out[i]['upperTouch'])

    def test_band_entry_not_exact_target(self):
        _,i,out=self.setup_signal(o=100,h=120,l=99,c=115)
        self.assertTrue(out[i+1]['upperTouch']) # $500 band exceeds synthetic geometry
        self.assertFalse(out[i+1]['exactTopTouch'])
        self.assertFalse(out[i+2]['upperTouch']) # deduped

    def test_projection_length_not_signal_expiry(self):
        # Shrink only the DISPLAY setting, not any mathematical/signal threshold.
        bars=stream(count=18)
        e=Replay(replace(PINE_A,forward_bars=2));out=[e.append(b) for b in bars]
        self.assertTrue(out[-1]['pairReady'])
        self.assertGreater(out[-1]['time'],out[-1]['frozen']['futureTime'])
        self.assertTrue(out[-1]['startAsia'] is False)

    def test_new_asia_resets_pair_and_nullable_comparisons_are_false(self):
        out=run(stream(count=30));last=out[-1]
        self.assertFalse(last['pairReady'])
        self.assertFalse(last['topInAsia']);self.assertFalse(last['bottomInAsia'])


def risk_case(long=True,target=None):
    t=stamp('2026-10-31T10:00:00Z')
    b=bar(t,o=80010,h=80020,l=80000,c=80010) if long else bar(t,o=78990,h=79000,l=78980,c=78990)
    s=dict(profile='OWNER_B',data_complete=True,longBreak=long,shortBreak=not long,
           time=t,available_at=t+HOUR,atr14=100,
           frozen=dict(newTopTarget=80700 if target is None else target,
                       newBottomTarget=78300 if target is None else target,
                       highGuideValue=80000,lowGuideValue=79000))
    return s,b


ZERO=Costs(D(0),D(0),D(0),D(0),D(0),'TEST_ZERO_NOT_REAL_COST')
CONSERVATIVE=Costs(D('.0005'),D('.0005'),D('.0002'),D('.0002'),D(5),'ILLUSTRATIVE_NOT_ACCOUNT_FEES')


class OwnerRiskTests(unittest.TestCase):
    def test_long_advance_is_subtracted_price_200(self):
        s,b=risk_case();r=paper_plan(s,b,D(10000),ZERO)
        self.assertEqual(r['theoretical_target'],D(80700));self.assertEqual(r['advanced_tp'],D(80500))
        self.assertTrue(r['accepted'])

    def test_short_advance_is_added_price_200(self):
        s,b=risk_case(False);r=paper_plan(s,b,D(10000),ZERO)
        self.assertEqual(r['theoretical_target'],D(78300));self.assertEqual(r['advanced_tp'],D(78500))
        self.assertTrue(r['accepted'])

    def test_advance_is_not_pnl_200_or_band_500(self):
        s,b=risk_case();r=paper_plan(s,b,D(10000),ZERO)
        self.assertEqual(r['tp_advance_price'],200)
        self.assertNotEqual(r['quantity_btc']*D(200),D(200))
        self.assertEqual(PINE_A.top_band,500)

    def test_advanced_tp_behind_entry_rejects_long(self):
        s,b=risk_case(target=80200)
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['ADVANCED_TP_NOT_AHEAD_OF_ENTRY'])

    def test_advanced_tp_behind_entry_rejects_short(self):
        s,b=risk_case(False,target=78800)
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['ADVANCED_TP_NOT_AHEAD_OF_ENTRY'])

    def test_advanced_tp_equality_rejected(self):
        s,b=risk_case(target=80210)
        self.assertFalse(paper_plan(s,b,D(10000),ZERO)['accepted'])

    def test_rr_recomputed_with_advance_not_theoretical_target(self):
        s,b=risk_case(target=80240) # 230 gross theoretical reward, only30 advanced /30 risk =1R
        r=paper_plan(s,b,D(10000),ZERO)
        self.assertEqual(r['net_rr'],D(1));self.assertFalse(r['accepted'])

    def test_exact_1_5_net_rr_allowed(self):
        s,b=risk_case(target=80255)
        r=paper_plan(s,b,D(10000),ZERO)
        self.assertEqual(r['net_rr'],D('1.5'));self.assertTrue(r['accepted'])

    def test_costs_reduce_rr(self):
        s,b=risk_case();a=paper_plan(s,b,D(10000),ZERO);c=paper_plan(s,b,D(10000),CONSERVATIVE)
        self.assertLess(c['net_rr'],a['net_rr'])

    def test_missing_costs_fail_closed(self):
        s,b=risk_case();self.assertEqual(paper_plan(s,b,D(10000),None)['reasons'],['COST_ASSUMPTIONS_REQUIRED'])

    def test_risk_max_025_and_notional_no_leverage(self):
        s,b=risk_case();r=paper_plan(s,b,D(10000),ZERO)
        self.assertLessEqual(r['estimated_stop_loss'],D(25));self.assertLessEqual(r['notional'],D(10000))
        self.assertIsNone(r['actual_fill'])
        self.assertFalse(r['operational_paper_authorized'])

    def test_atr_unavailable_rejected(self):
        s,b=risk_case();s['atr14']=None
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['ATR14_UNAVAILABLE'])

    def test_a_has_no_owner_risk(self):
        s,b=risk_case();s['profile']='PINE_A'
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['NOT_OWNER_B_RISK_RULES'])

    def test_bad_data_blocks_paper_but_does_not_modify_pine(self):
        s,b=risk_case();s['data_complete']=False
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['INCOMPLETE_H1_DATA'])

    def test_no_confirmation_and_mismatch_rejected(self):
        s,b=risk_case();s['longBreak']=False
        self.assertFalse(paper_plan(s,b,D(10000),ZERO)['accepted'])
        s,b=risk_case();s['time']+=HOUR
        self.assertEqual(paper_plan(s,b,D(10000),ZERO)['reasons'],['SIGNAL_CANDLE_MISMATCH'])


class SourceAndBoundaryTests(unittest.TestCase):
    def test_original_source_bytes_frozen(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),SOURCE_HASH)
        self.assertGreater(len(audit()['inputs']),30)

    def test_diagnostic_original_is_exact_prefix_not_replacement(self):
        original=SOURCE.read_bytes();diagnostic=diagnostic_bytes()
        self.assertEqual(diagnostic[:len(original)],original)
        suffix=diagnostic[len(original):].decode('utf-8')
        self.assertIn('barstate.isconfirmed',suffix);self.assertIn('input.bool(false',suffix)
        self.assertNotIn('alertcondition(',suffix)

    def test_original_formula_lines_are_explicitly_audited(self):
        formulas='\n'.join(x['text'] for x in audit()['formula_lines'])
        self.assertIn('math.max(aHigh, lHigh) - math.min(aLow, lLow)',formulas)
        self.assertIn('topAnchor + nz(amplitude, 0)',formulas)
        self.assertIn('close > globalHigh',formulas)

    def test_runtime_files_equal_base_hashes(self):
        manifest=json.loads((HERE/'fixtures/protected_runtime_hashes.json').read_text())
        for path,sha in manifest['files'].items():
            raw=(REPO/path).read_bytes().replace(b'\r\n',b'\n')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),sha,path)

    def test_production_has_no_import_or_string_reference_to_this_lab(self):
        manifest=json.loads((HERE/'fixtures/protected_runtime_hashes.json').read_text())
        for path in manifest['files']:
            if path.endswith('.py'):
                text=(REPO/path).read_text(encoding='utf-8-sig')
                self.assertNotIn('alpha_arcanox_pine_v37',text,path)

    def test_lab_has_no_network_trading_or_subprocess_import(self):
        allowed={'dataclasses','datetime','zoneinfo','decimal','math','copy','argparse','hashlib',
                 'json','pathlib','re','csv','html'}
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Import):
                    for n in node.names:self.assertIn(n.name.split('.')[0],allowed,path.name)
                if isinstance(node,ast.ImportFrom) and not node.level:
                    self.assertIn(node.module.split('.')[0],allowed,path.name)

    def test_public_fixture_hash_and_no_old_setup_binding(self):
        manifest=json.loads((HERE/'fixtures/public_data_manifest.json').read_text())
        self.assertEqual(hashlib.sha256((HERE/'fixtures/public_sessions_demo.csv').read_bytes()).hexdigest(),manifest['sha256'])
        self.assertEqual(manifest['original_example_ticker'],'UNKNOWN')

    def test_generated_vector_and_diagnostic_determinism(self):
        from .build import CASES,figure
        for name,*prices in CASES:
            self.assertEqual(figure(name,project(*prices)),(HERE/f'artifacts/{name}.svg').read_text(encoding='utf-8'))
        self.assertEqual(diagnostic_bytes(),(HERE/'artifacts/Killzone_H1_v3_7_Lite_DIAGNOSTIC.pine').read_bytes())


def comparator_fixture():
    """Own synthetic plumbing test; NEVER saved as actual TradingView evidence."""
    bars=stream(count=28);out=run(bars);rows=[]
    for b,r in zip(bars,out):
        row={k:r[k] for k in NUMERIC+BOOLEAN}
        row.update(time=b.open_time,time_close=b.available_at,open=b.open,high=b.high,low=b.low,close=b.close,
                   tickerid='TEST_ONLY:SYNTHETIC',timeframe='60',confirmed=True,
                   source_sha256=SOURCE_SHA256,standard_chart=True,mintick=.01,
                   asiaTZ='America/New_York',londonTZ='America/New_York',asiaStartHour=20,asiaCandles=4,
                   londonStartHour=2,londonCandles=4,topInsetPct=3.0,bottomInsetPct=3.0,topUSD=500.0,bottomUSD=500.0)
        rows.append(row)
    return rows


class ComparatorPlumbingTests(unittest.TestCase):
    def test_synthetic_roundtrip_is_plumbing_not_independent_evidence(self):
        r=compare(comparator_fixture())
        self.assertEqual(r['status'],'MATCH_FOR_SUPPLIED_LOGS')
        self.assertIn('NOT_INDEPENDENTLY_AUTHENTICATED',r['evidence'])

    def test_changed_real_value_would_be_detected(self):
        rows=comparator_fixture();rows[12]['topAnchor']+=.1
        self.assertEqual(compare(rows)['status'],'MISMATCH')

    def test_missing_field_rejected(self):
        rows=comparator_fixture();del rows[12]['topAnchor']
        with self.assertRaisesRegex(ValueError,'MISSING_PINE_FIELD'):compare(rows)

    def test_mixed_ticker_rejected(self):
        rows=comparator_fixture();rows[-1]['tickerid']='OTHER:VENUE'
        with self.assertRaisesRegex(ValueError,'METADATA'):compare(rows)

    def test_wrong_config_rejected(self):
        rows=comparator_fixture();rows[0]['londonStartHour']=1
        with self.assertRaisesRegex(ValueError,'METADATA'):compare(rows)

    def test_wrong_version_or_non_standard_chart_rejected(self):
        for key,value in (('source_sha256','other-version'),('standard_chart',False)):
            rows=comparator_fixture();rows[0][key]=value
            with self.assertRaisesRegex(ValueError,'METADATA'):compare(rows)

    def test_empty_input_not_claimed_as_parity(self):
        with self.assertRaisesRegex(ValueError,'NO_REAL'):compare([])

    def test_time_and_confirmation_validated(self):
        rows=comparator_fixture();rows[0]['confirmed']=False
        with self.assertRaisesRegex(ValueError,'UNCONFIRMED'):compare(rows)
        rows=comparator_fixture();rows[0]['time_close']-=1
        with self.assertRaisesRegex(ValueError,'TIME_SCHEMA'):compare(rows)


if __name__=='__main__':
    unittest.main()
