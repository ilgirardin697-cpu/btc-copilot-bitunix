"""Offline unit fixtures; no synthetic test counts as platform/forward evidence."""
import ast
import csv
from decimal import Decimal
import hashlib
import json
import gzip
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Dedicated confluence CI installs NumPy') from error

from research.confluence_1h.data import stamp
from research.confluence_1h.indicators import calculate
from research.confluence_1h_phase2.compare import load_market
from research.confluence_1h_phase2.semantics import HOUR, events
from .audit import HERE, load, visual_match
from .context import aggregate, context_at, DAY
from .detector import detect

ROOT=Path(__file__).resolve().parents[3]
BASE='4dcc5d94217b9b387fc69f93ad325e28aaf2a856'


def synthetic(n=12,side='UP',context='PEAK_DECELERATION',times=(3,4,5)):
    a=np.c_[stamp('2026-10-01T00:00:00Z')+np.arange(n)*HOUR,
            np.full(n,100.),np.full(n,102.),np.full(n,98.),np.full(n,100.),np.full(n,10.)]
    up=side=='UP'
    f=dict(minnows=np.full(n,1. if up else -1.),kon_trend=np.full(n,2.),sharks=np.full(n,3.),kon_signal=np.zeros(n),
           ao=-20+np.arange(n,dtype=float) if up else 20-np.arange(n,dtype=float),
           adx=50-np.arange(n,dtype=float) if context=='PEAK_DECELERATION' else 20+np.arange(n,dtype=float))
    ev={k:np.zeros(n,bool) for k in events(f)}
    cross,ao,adx=times
    ev['pececillos_cross_'+side.lower()][cross]=True
    ev['ao_negative_two_rising' if up else 'ao_positive_two_falling'][ao:]=True
    ev['adx_turn_down' if context=='PEAK_DECELERATION' else 'adx_turn_up'][adx]=True
    return a,f,ev


def run_case(a,f,ev):
    with patch('research.confluence_1h_phase2.event_proximity.detector.events',return_value=ev):
        return detect(a,f)


class ProximityTests(unittest.TestCase):
    def test_same_close_confirmation_has_no_backdating(self):
        a,f,e=synthetic(times=(3,3,3));r=run_case(a,f,e)
        obs=[x for x in r if x['record_type']=='PROXIMITY_OBSERVED']
        self.assertEqual(len(obs),1);self.assertEqual(obs[0]['available_at'],a[3,0]+HOUR)
        self.assertEqual(obs[0]['evidence_mode'],'RETROSPECTIVE_DIAGNOSTIC_REPLAY_NOT_FORWARD')

    def test_two_close_separation_allowed_without_changing_window(self):
        a,f,e=synthetic();r=run_case(a,f,e)
        obs=[x for x in r if x['record_type']=='PROXIMITY_OBSERVED']
        self.assertEqual(len(obs),1);self.assertEqual(obs[0]['available_at'],a[5,0]+HOUR)

    def test_three_close_separation_expires_bundle(self):
        a,f,e=synthetic(times=(3,4,6));r=run_case(a,f,e)
        self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))
        self.assertTrue(any(x['record_type']=='EXPIRED' for x in r))

    def test_both_directions_are_symmetric(self):
        for side in ('UP','DOWN'):
            a,f,e=synthetic(side=side)
            obs=[x for x in run_case(a,f,e) if x['record_type']=='PROXIMITY_OBSERVED']
            self.assertEqual([x['side_hypothesis'] for x in obs],[side])

    def test_adx_peak_and_trough_contexts_not_mixed(self):
        for context in ('PEAK_DECELERATION','TROUGH_BUILDING'):
            a,f,e=synthetic(context=context)
            obs=[x for x in run_case(a,f,e) if x['record_type']=='PROXIMITY_OBSERVED']
            self.assertEqual([x['adx_context'] for x in obs],[context])

    def test_persistent_ao_state_does_not_duplicate(self):
        a,f,e=synthetic(n=18);r=run_case(a,f,e)
        obs=[x for x in r if x['record_type']=='PROXIMITY_OBSERVED']
        self.assertEqual(len(obs),1)
        self.assertEqual(len({x['event_id'] for x in r}),len(r))

    def test_ao_sign_or_slope_break_invalidates_pending(self):
        for value in (-.5, .5):
            a,f,e=synthetic(times=(3,4,6));f['ao'][5]=value
            f['ao'][6:]=value-1-np.arange(len(a)-6)
            r=run_case(a,f,e)
            self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))
            self.assertTrue(any(x['reason']=='AO_SIGN_OR_RECOVERY_INVALID' for x in r))

    def test_lost_area_alignment_including_equal_invalidates(self):
        for value in (0.,-1.):
            a,f,e=synthetic();f['minnows'][4:]=value
            r=run_case(a,f,e)
            self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))
            self.assertTrue(any(x['reason']=='AREA_ALIGNMENT_LOST' for x in r))

    def test_adx_context_reversal_cancels(self):
        a,f,e=synthetic(times=(3,5,3));f['adx'][4:]=60+np.arange(len(a)-4)
        r=run_case(a,f,e)
        self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))
        self.assertTrue(any(x['reason']=='ADX_CONTEXT_REVERSED' for x in r))

    def test_expired_tokens_do_not_resurrect_when_new_cross_appears(self):
        a,f,e=synthetic(times=(3,4,7));e['pececillos_cross_up'][7]=True
        r=run_case(a,f,e)
        self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))

    def test_nonfinite_and_missing_hour_cancel_and_need_clean_prefix(self):
        for bad in ('nan','gap'):
            a,f,e=synthetic()
            if bad=='nan':f['minnows'][4]=np.nan
            else:a[4:,0]+=HOUR
            r=run_case(a,f,e)
            self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in r))
            self.assertTrue(any(x['reason']=='DATA_UNAVAILABLE_OR_GAP' for x in r))

    def test_duplicate_or_reversed_timestamps_rejected(self):
        a,f,e=synthetic();a[4,0]=a[3,0]
        with self.assertRaises(ValueError):run_case(a,f,e)

    def test_future_append_cannot_change_past_records(self):
        a,f,e=synthetic(n=18)
        full=run_case(a,f,e)
        for n in (4,6,9):
            prefix=run_case(a[:n],{k:v[:n] for k,v in f.items()},{k:v[:n] for k,v in e.items()})
            self.assertEqual(prefix,[r for r in full if r['available_at']<=a[n-1,0]+HOUR])

    def test_missing_one_component_cannot_be_completion(self):
        for missing in ('pececillos_cross_up','ao_negative_two_rising','adx_turn_down'):
            a,f,e=synthetic();e[missing][:]=False
            self.assertFalse(any(x['record_type']=='PROXIMITY_OBSERVED' for x in run_case(a,f,e)))


class ContextAndEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spot=load('SPOT_H1_FOCUS');cls.context=load('SPOT_H1_CONTEXT')

    def test_owner_report_is_not_fabricated_direct_capture_or_full_parity(self):
        m=json.loads((HERE/'visual_evidence.json').read_text())
        self.assertEqual(m['source_type'],'OWNER_REPORTED_EXTERNAL_VISUAL_COMPARISON')
        self.assertFalse(m['screenshot_received_and_inspected_in_this_task'])
        self.assertEqual(m['machine_readable_platform_records'],0)
        match=visual_match(self.spot)
        self.assertEqual(match['rounded_two_decimals']['pececillos'],'-40.40')
        self.assertLess(match['pececillos_absolute_error'],.005)
        self.assertFalse(match['complete_parity'])

    def test_owner_point_discriminates_named_candidates_only(self):
        r=visual_match(self.spot)
        hits=[k for k,v in r['rounded_two_decimals'].items() if v=='-40.40']
        self.assertEqual(hits,['pececillos'])
        self.assertAlmostEqual(r['values']['pececillos'],-40.39928839347632,places=10)

    def test_open_02_madrid_point_available_at_03_not_02(self):
        r=visual_match(self.spot)
        self.assertEqual(r['bar_open_utc'],'2026-11-15T01:00:00Z')
        self.assertEqual(r['earliest_available_at'],'2026-11-15T02:00:00Z')

    def test_exact_pine_plot_bindings_and_default_red_ema(self):
        source=(ROOT/'research/confluence_1h/reference_sources/koncorde_original.pine.txt').read_text('utf-8-sig')
        bindings=[("pececillos : na, 'Verde'",306),("tendencia : na, 'Marron'",307),("tiburones : na, 'Azul'",308)]
        for text,line in bindings:self.assertIn(text,source.splitlines()[line-1])
        self.assertLess(source.index("'Verde', color"),source.index("'Marron', color"))
        self.assertLess(source.index("'Marron', color"),source.index("'Azul', color"))
        self.assertIn('ma(type_ma01, tendencia, length_ma01, volumen)',source)

    def test_partial_higher_group_ignored_not_filled(self):
        a=self.spot[:169]
        weekly=aggregate(a,7*DAY,4*DAY)
        # Dataset starts on Tuesday: neither clipped edge week is complete here.
        self.assertEqual(len(weekly),0)
        self.assertTrue(all((r[0]%(4*HOUR))==0 for r in aggregate(a,4*HOUR)))

    def test_168_hours_required_for_week(self):
        start=stamp('2026-11-02T00:00:00Z')
        a=np.c_[start+np.arange(168)*HOUR,np.full(168,100),np.full(168,102),np.full(168,98),np.full(168,101),np.ones(168)]
        self.assertEqual(len(aggregate(a,7*DAY,4*DAY)),1)
        self.assertEqual(len(aggregate(a[:-1],7*DAY,4*DAY)),0)

    def test_weekly_open_week_and_daily_current_day_never_used(self):
        c=context_at(self.context,stamp('2026-11-15T13:00:00Z'))
        self.assertEqual(c['1W']['open_utc'],'2026-11-02T00:00:00Z')
        self.assertEqual(c['1W']['available_at'],'2026-11-09T00:00:00Z')
        self.assertEqual(c['1D']['open_utc'],'2026-11-14T00:00:00Z')
        self.assertEqual(c['4H']['available_at'],'2026-11-15T12:00:00Z')

    def test_current_4h_only_becomes_available_at_exact_close(self):
        before=context_at(self.context,stamp('2026-11-15T03:00:00Z'))
        after=context_at(self.context,stamp('2026-11-15T04:00:00Z'))
        self.assertEqual(before['4H']['available_at'],'2026-11-15T00:00:00Z')
        self.assertEqual(after['4H']['available_at'],'2026-11-15T04:00:00Z')

    def test_poisoning_future_hourly_rows_cannot_change_higher_context(self):
        at=stamp('2026-11-15T04:00:00Z');b=self.context.copy()
        b[b[:,0]+HOUR>at,1:5]*=3
        self.assertEqual(context_at(self.context,at),context_at(b,at))

    def test_weekly_insufficient_sma200_and_full_bbwp_not_invented(self):
        c=context_at(self.context,stamp('2026-11-15T13:00:00Z'))
        self.assertIsNone(c['1W']['sma200'])
        self.assertFalse(c['1W']['full_bbwp_history_available'])

    def test_late_case_is_slope_turn_not_red_cross_at_16_madrid(self):
        f=calculate(self.spot);ev=events(f);i=int(np.flatnonzero(self.spot[:,0]==stamp('2026-11-15T14:00:00Z'))[0])
        self.assertTrue(ev['pececillos_slope_turn_down'][i])
        self.assertFalse(ev['pececillos_cross_down'][i])
        self.assertGreater(f['minnows'][i],f['kon_signal'][i])
        self.assertLess(f['ao_slope'][i],0)
        self.assertAlmostEqual(f['adx'][i],29.72344734980479,places=8)
        self.assertEqual(f['bbwp'][i],40)

    def test_calendar_all_cases_kept_including_opposite_followthrough(self):
        rows=list(csv.DictReader((HERE/'artifacts/all_calendar_crosses.csv').read_text().splitlines()))
        self.assertEqual(len(rows),122)
        self.assertEqual(sum(r['description']=='OPPOSITE_DIRECTION_CLOSE' for r in rows),64)
        self.assertTrue(all('2026-10-01'<=r['open_utc']<'2026-11-15' for r in rows))

    def test_different_cancelled_bundles_at_one_close_have_unique_record_ids(self):
        raw=gzip.decompress((HERE/'artifacts/proximity_ledger.csv.gz').read_bytes()).decode()
        rows=list(csv.DictReader(io.StringIO(raw)));ids=[r['event_id'] for r in rows]
        self.assertEqual(len(ids),len(set(ids)))

    def test_frozen_proposal_before_additional_outcome_review(self):
        raw=(HERE/'proposal.json').read_bytes()
        frozen=subprocess.check_output(['git','show','dbaf7fbe8488dd148121b2f7407f9ce91c3c89fa:research/confluence_1h_phase2/event_proximity/proposal.json'],cwd=ROOT)
        self.assertEqual(raw,frozen)
        p=json.loads(raw);self.assertEqual(p['max_age_closed_bars'],2)
        self.assertIsNone(p['entry']);self.assertIsNone(p['stop']);self.assertFalse(p['pnl_evaluation_allowed'])

    def test_all_pr47_files_and_production_remain_unchanged(self):
        repo=HERE.parents[2]
        changed=subprocess.check_output(['git','diff',BASE,'--name-status'],cwd=repo,text=True).splitlines()
        for line in changed:
            status,path=line.split('\t',1)
            self.assertEqual(status,'A',line)
            self.assertTrue(path.startswith('research/confluence_1h_phase2/event_proximity/'),line)

    def test_no_network_orders_or_runtime_dependencies_in_new_modules(self):
        forbidden={'requests','urllib','socket','ccxt','guardian_bitunix','trade_guardian','bitman_manual','engine','simulate'}
        for p in HERE.glob('*.py'):
            if p.name.startswith('test_'):continue
            for node in ast.walk(ast.parse(p.read_text())):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in node.names]+([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                    for n in names:self.assertFalse(forbidden.intersection(n.split('.')),str(p))


if __name__=='__main__':
    unittest.main()
