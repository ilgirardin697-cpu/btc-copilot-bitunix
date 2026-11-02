"""Synthetic controls are math tests, never independent market/indicator evidence."""
import ast
import copy
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import replace
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
from . import core
from .data import read_csv,json_text,sha
from .render import command_preview,reference_svg,session_svg
from .risk import Costs,estimate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='9d40020d539033cefb8f01734db8c6a6fdbba2e3'
ZERO=Costs(D(0),D(0),D(0),D(0),D(0),'SYNTHETIC_ZERO_COST_CONTROL_ONLY')
ASSUMED=Costs(D('.0006'),D('.0006'),D('.0005'),D('.0005'),D(0),'ILLUSTRATIVE_NOT_ACCOUNT_FEES')


def fixture():
    day=date(2026,11,2);t=core.stamp(day,0)
    bars=tuple(core.Bar(k,D(100),D(102),D(98),D(100)) for k in range(t-24*core.HOUR,t+24*core.HOUR,core.HOUR))
    return bars,day,core.stamp(day,5)


def replace_bar(bars,t,o,c,h=None,l=None):
    return tuple(replace(b,open=D(o),close=D(c),high=D(h) if h else max(D(o),D(c))+1,
                         low=D(l) if l else min(D(o),D(c))-1) if b.open_time==t else b for b in bars)


@contextmanager
def test_only_formula(high='100',low='90',superior='120',inferior='80',delay=0):
    """ONLY unit tests may register this artificial provider. No runtime config path."""
    def provider(p):
        return core.Levels(D(high),D(low),D(superior),D(inferior),'SYNTHETIC_TEST_ONLY',
                           'NOT_ORIGINAL_INDICATOR_EVIDENCE',p.day,p.available_at+delay)
    with patch.object(core,'APPROVED_FORMULA_IDS',frozenset({'SYNTHETIC_TEST_ONLY'})),patch.object(core,'levels_for_pair',side_effect=provider):
        yield


class SessionTests(unittest.TestCase):
    def test_five_asia_four_london_exact_opens(self):
        b,d,t=fixture();p=core.pair(b,d,t)
        self.assertEqual([x.open_time for x in p.asia.candles],[core.stamp(d-timedelta(days=1),20)+i*core.HOUR for i in range(5)])
        self.assertEqual([x.open_time for x in p.london.candles],[core.stamp(d,1)+i*core.HOUR for i in range(4)])
        self.assertEqual(p.asia.end,p.london.start)
        self.assertEqual(core.iso(p.available_at),'2026-11-02T09:00:00Z')

    def test_00_belongs_to_asia_not_london(self):
        b,d,t=fixture();p=core.pair(b,d,t)
        self.assertEqual(p.asia.candles[-1].open_time,core.stamp(d,0))
        self.assertEqual(p.london.candles[0].open_time,core.stamp(d,1))

    def test_fixed_offset_no_dst(self):
        for day in ('2026-01-14','2026-03-08','2026-07-01','2026-11-01','2026-11-02'):
            self.assertEqual(core.iso(core.stamp(day,5)),day+'T09:00:00Z')

    def test_not_complete_one_ms_before_05(self):
        b,d,t=fixture()
        self.assertEqual(core.scan(b,d,t-1)['reason_codes'],['BOTH_SESSIONS_NOT_CLOSED'])

    def test_missing_session_prefix_fails_closed(self):
        b,d,t=fixture();b=tuple(x for x in b if x.open_time>=core.stamp(d,0))
        self.assertEqual(core.scan(b,d,t)['reason_codes'],['SESSION_INCOMPLETE_ASIA'])

    def test_gap_duplicate_or_unordered_fail(self):
        b,d,t=fixture()
        for x in (b[:3]+b[4:],b[:3]+b[2:],tuple(reversed(b))):
            with self.assertRaises(ValueError):core.scan(x,d,t)

    def test_ohlc_and_nan_fail(self):
        b,d,t=fixture()
        for value in (D('NaN'),D(-1)):
            with self.assertRaises(ValueError):core.validate((replace(b[0],high=value),))


class ConfirmationTests(unittest.TestCase):
    def test_long_full_body_even_red_candle(self):
        b=core.Bar(0,D(103),D(104),D(101),D(102))
        self.assertEqual(core.body_direction(b,D(100),D(90)),'LONG')

    def test_short_full_body_even_green_candle(self):
        b=core.Bar(0,D(87),D(90),D(86),D(89))
        self.assertEqual(core.body_direction(b,D(100),D(90)),'SHORT')

    def test_crossing_body_rejected(self):
        for o,c in ((99,102),(102,99)):
            self.assertIsNone(core.body_direction(core.Bar(0,D(o),D(103),D(98),D(c)),D(100),D(90)))

    def test_wick_only_rejected(self):
        self.assertIsNone(core.body_direction(core.Bar(0,D(95),D(105),D(85),D(96)),D(100),D(90)))

    def test_equality_not_strictly_outside(self):
        for o,c in ((100,101),(101,100),(90,89),(89,90)):
            self.assertIsNone(core.body_direction(core.Bar(0,D(o),D(103),D(87),D(c)),D(100),D(90)))

    def test_doji_outside_satisfies_literal_min_max(self):
        self.assertEqual(core.body_direction(core.Bar(0,D(101),D(102),D(100),D(101)),D(100),D(90)),'LONG')

    def test_approved_fixture_only_after_candle_closes(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'101','102')
        with test_only_formula():
            self.assertIsNone(core.scan(b,d,t+2*core.HOUR-1,ZERO,D(10000))['confirmation'])
            r=core.scan(b,d,t+2*core.HOUR,ZERO,D(10000))
        self.assertEqual(r['confirmation']['available_at'],t+2*core.HOUR)
        self.assertEqual(r['confirmation']['theoretical_entry'],D(102))
        self.assertEqual(r['paper_decision'],'ACEPTADA')
        self.assertIsNone(r['risk']['actual_fill'])
        self.assertEqual(r['trade_authority'],'NONE')

    def test_04_bar_only_known_at_05_boundary(self):
        b,d,t=fixture();b=replace_bar(b,t-core.HOUR,'101','102')
        with test_only_formula():
            self.assertIsNone(core.scan(b,d,t-1,ZERO,D(10000))['confirmation'])
            r=core.scan(b,d,t,ZERO,D(10000))
        self.assertEqual(r['confirmation']['available_at'],t)

    def test_no_confirmation_before_both_sessions_closed(self):
        b,d,t=fixture();b=replace_bar(b,t-2*core.HOUR,'101','102')
        with test_only_formula():r=core.scan(b,d,t,ZERO,D(10000))
        self.assertIsNone(r['confirmation'])

    def test_future_level_availability_not_backdated(self):
        b,d,t=fixture();b=replace_bar(b,t,'101','102')
        with test_only_formula(delay=2*core.HOUR):r=core.scan(b,d,t+core.HOUR,ZERO,D(10000))
        self.assertIn('LEVELS_AVAILABILITY_INVALID',r['reason_codes'])
        self.assertIsNone(r['confirmation'])

    def test_close_reference_not_next_open_fill(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'101','102');b=replace_bar(b,t+2*core.HOUR,'115','116')
        with test_only_formula():r=core.scan(b,d,t+2*core.HOUR,ZERO,D(10000))
        self.assertEqual(r['confirmation']['theoretical_entry'],D(102))
        self.assertIsNone(r['risk']['actual_fill'])

    def test_first_rejection_not_replaced_by_later_better_entry(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'104.5','105');b=replace_bar(b,t+2*core.HOUR,'100.5','101')
        with test_only_formula(superior='106'):r=core.scan(b,d,t+3*core.HOUR,ZERO,D(10000))
        self.assertEqual(r['confirmation']['theoretical_entry'],D(105))
        self.assertEqual(r['paper_decision'],'RECHAZADA')
        self.assertIn('NET_RR_BELOW_1_5',r['reason_codes'])

    def test_prefix_invariance_and_no_stop_widening_after_confirmation(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'101','102')
        with test_only_formula():
            a=core.scan(b,d,t+2*core.HOUR,ZERO,D(10000));later=core.scan(b,d,t+10*core.HOUR,ZERO,D(10000))
        self.assertEqual(json_text(a['confirmation']),json_text(later['confirmation']))
        self.assertEqual(json_text(a['risk']),json_text(later['risk']))

    def test_future_ohlc_cannot_change_past_result(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'101','102')
        corrupt=tuple(replace(x,high=D('NaN'),close=D(-1)) if x.available_at>t+2*core.HOUR else x for x in b)
        with test_only_formula():
            self.assertEqual(json_text(core.scan(b,d,t+2*core.HOUR,ZERO,D(10000))),json_text(core.scan(corrupt,d,t+2*core.HOUR,ZERO,D(10000))))


class ATRTests(unittest.TestCase):
    def test_wilder_seed_and_update(self):
        b=tuple(core.Bar(i*core.HOUR,D(100),D(101),D(99),D(100)) for i in range(15))
        out=core.atr14(b)
        self.assertEqual(out[:13],(None,)*13)
        self.assertEqual(out[13],D(2))
        b=b[:-1]+(replace(b[-1],high=D(104)),)
        self.assertAlmostEqual(float(core.atr14(b)[14]),31/14,places=13)

    def test_tr_accounts_for_previous_close(self):
        b=tuple(core.Bar(i*core.HOUR,D(100),D(101),D(99),D(100)) for i in range(14))
        gap=core.Bar(14*core.HOUR,D(110),D(111),D(109),D(110))
        self.assertAlmostEqual(float(core.atr14(b+(gap,))[-1]),37/14,places=13)

    def test_atr_prefix_invariance(self):
        b,d,t=fixture();self.assertEqual(core.atr14(b)[:20],core.atr14(b[:20]))


class RiskTests(unittest.TestCase):
    def long(self,costs=ZERO,target='104',capital='10000',atr='5',entry='101'):
        return estimate('LONG',D(entry),D(100),D(90),D(target),None if atr is None else D(atr),costs,None if capital is None else D(capital))

    def test_long_sl_and_exact_minimum_1_5(self):
        r=self.long();self.assertEqual((r['stop'],r['net_rr']),(D(99),D('1.5')));self.assertTrue(r['risk_filter_passed'])

    def test_short_sl_symmetric_owner_rule(self):
        r=estimate('SHORT',D(99),D(110),D(100),D(96),D(5),ZERO,D(10000))
        self.assertEqual((r['stop'],r['net_rr']),(D(101),D('1.5')));self.assertTrue(r['risk_filter_passed'])

    def test_below_minimum_rejected(self):
        self.assertIn('NET_RR_BELOW_1_5',self.long(target='103.99')['reason_codes'])

    def test_costs_reduce_rr_and_can_reject_gross_1_5(self):
        r=self.long(ASSUMED)
        self.assertLess(r['net_rr'],D('1.5'));self.assertFalse(r['risk_filter_passed'])
        self.assertIsNone(r['actual_fill'])

    def test_no_double_fee_in_each_counterfactual(self):
        costs=Costs(D('.001'),D('.001'),D(0),D(0),D(0),'UNIT')
        r=self.long(costs)
        self.assertEqual(r['net_risk_per_btc'],D('2.200'))
        self.assertEqual(r['net_reward_per_btc'],D('2.795'))

    def test_tp_behind_or_equal_entry_rejected(self):
        for target in ('100','101'):
            self.assertIn('TP_NOT_AHEAD_OF_ENTRY',self.long(target=target)['reason_codes'])

    def test_stop_equal_entry_rejected(self):
        self.assertIn('SL_ENTRY_ORDER_INVALID',self.long(entry='99')['reason_codes'])

    def test_atr_unknown_not_substituted(self):
        self.assertIn('ATR14_UNAVAILABLE',self.long(atr=None)['reason_codes'])

    def test_costs_unknown_not_assumed_free(self):
        self.assertIn('COST_ASSUMPTIONS_MISSING',self.long(None)['reason_codes'])

    def test_funding_reserve_reduces_rr(self):
        r=self.long(replace(ZERO,funding_reserve_per_btc=D('.1')))
        self.assertLess(r['net_rr'],self.long()['net_rr'])

    def test_invalid_costs_and_funding_credits_rejected(self):
        for costs in (replace(ZERO,entry_fee=D(-1)),replace(ZERO,exit_slippage=D(1)),replace(ZERO,funding_reserve_per_btc=D(-1))):
            self.assertIn('COST_ASSUMPTIONS_INVALID',self.long(costs)['reason_codes'])

    def test_025_percent_risk_includes_costs(self):
        r=self.long(ASSUMED,target='110')
        self.assertTrue(r['risk_filter_passed'])
        self.assertEqual(r['simulated_risk_budget'],D(25))
        self.assertLessEqual(r['estimated_stop_risk'],D(25))
        self.assertLessEqual(r['notional_scenario'],D(10000))

    def test_notional_cap_without_leverage(self):
        r=self.long(target='120',entry='100.001',atr='0')
        self.assertLessEqual(r['notional_scenario'],D(10000))
        self.assertEqual(r['notional_cap_multiple'],1)

    def test_capital_not_taken_from_account(self):
        self.assertIn('SIMULATED_CAPITAL_MISSING_OR_INVALID',self.long(capital=None)['reason_codes'])


class EvidenceAndIsolationTests(unittest.TestCase):
    def test_no_formula_registered_by_default(self):
        self.assertFalse(core.APPROVED_FORMULA_IDS)
        b,d,t=fixture();r=core.scan(b,d,t+core.HOUR,ZERO,D(10000))
        self.assertFalse(r['levels_verified']);self.assertIsNone(r['confirmation'])
        self.assertEqual(r['paper_decision'],'RECHAZADA')
        self.assertTrue(all(getattr(r['levels'],k) is None for k in core.LEVEL_NAMES))

    def test_reference_values_cannot_activate_a_formula(self):
        b,d,t=fixture()
        def malicious(p):return core.Levels(D('78285'),D('77517.20'),D('78653.44'),D('77095.25'),'verified','user_flag',p.day,p.available_at)
        with patch.object(core,'levels_for_pair',side_effect=malicious),patch.object(core,'body_direction',side_effect=AssertionError('must not be called')):
            r=core.scan(b,d,t+core.HOUR,ZERO,D(10000))
        self.assertIn('FORMULA_ORIGINAL_NO_VERIFICADA',r['reason_codes'])
        self.assertIsNone(r['confirmation'])

    def test_owner_values_are_visual_only_and_not_forced_symmetric(self):
        r=json.loads((HERE/'fixtures/owner_reference.json').read_text())
        v={k:D(x['value']) for k,x in r['levels'].items()}
        self.assertEqual(v,dict(HIGH=D('78285.00'),LOW=D('77517.20'),SUPERIOR=D('78653.44'),INFERIOR=D('77095.25')))
        self.assertNotEqual(v['SUPERIOR']-v['HIGH'],v['LOW']-v['INFERIOR'])
        self.assertFalse(r['formula_verified']);self.assertFalse(r['market_replay_verified'])
        self.assertEqual(r['venue'],'UNKNOWN')

    def test_public_demo_hash_and_validity(self):
        m=json.loads((HERE/'fixtures/public_data_manifest.json').read_text())
        p=HERE/'fixtures/public_sessions_demo.csv'
        self.assertEqual(sha(p),m['sha256']);b=read_csv(p);core.validate(b);self.assertEqual(len(b),72)

    def test_manual_preview_has_no_fake_entry(self):
        b,d,t=fixture();s=command_preview(core.scan(b,d,t),'UNKNOWN ORIGINAL VENUE')
        self.assertIn('PAPER: RECHAZADA',s);self.assertIn('Entrada teórica al cierre: UNKNOWN',s)
        self.assertIn('TRADE AUTHORITY: NONE',s)

    def test_svgs_valid_deterministic_and_clearly_separated(self):
        ref=json.loads((HERE/'fixtures/owner_reference.json').read_text())
        text=reference_svg(ref);ET.fromstring(text);self.assertEqual(text,reference_svg(ref))
        self.assertIn('NO es cálculo',text)
        b,d,t=fixture();r=core.scan(b,d,t+core.HOUR)
        ET.fromstring(session_svg(b,r,'SYNTHETIC CONTROL ONLY'))

    def test_verified_synthetic_path_can_draw_confirm_entry_sl_tp(self):
        b,d,t=fixture();b=replace_bar(b,t+core.HOUR,'101','102')
        with test_only_formula():r=core.scan(b,d,t+2*core.HOUR,ZERO,D(10000))
        text=session_svg(b,r,'SYNTHETIC, NOT MARKET EVIDENCE');ET.fromstring(text)
        self.assertIn('SL ',text);self.assertIn('TP ',text);self.assertIn('NO fill real',text)

    def test_no_production_consumers_or_nonresearch_mutations(self):
        changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],cwd=ROOT,text=True).splitlines()
        self.assertTrue(all(x.startswith(('research/alpha_arcanox_killzones_v1/',
            '.github/workflows/alpha-arcanox-killzones-v1.yml')) for x in changed),changed)
        paths=subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT,text=True).splitlines()
        for p in paths:
            if p.startswith(('research/','tests/','test_')):continue
            self.assertNotIn('alpha_arcanox_killzones_v1',(ROOT/p).read_text(encoding='utf-8'),p)

    def test_no_network_orders_sender_legacy_or_frozen_imports(self):
        allowed={'dataclasses','datetime','decimal','csv','hashlib','json','pathlib','html','argparse'}
        for p in HERE.glob('*.py'):
            if p.name.startswith('test_'):continue
            permitted=allowed|({'base64'} if p.name=='compare_source.py' else set())
            for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                if isinstance(n,ast.Import):self.assertTrue(all(x.name.split('.')[0] in permitted for x in n.names),p.name)
                if isinstance(n,ast.ImportFrom) and not n.level:self.assertIn(n.module.split('.')[0],permitted,p.name)


if __name__=='__main__':unittest.main()
