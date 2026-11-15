"""Synthetic numerical tests are not external platform or profitable-trade evidence."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Dedicated offline confluence CI installs NumPy') from error
from .detect import prior_rank, two_turn, detect, features, PATTERNS, HOUR
from .inference import holm, required_n, assess, calendar_bootstrap
from .outcomes import outcome
from .evaluate import match_controls, intervals, HERE
from .risk_stress import sized_quantity, isolated_threshold, illustrative_scenarios

ROOT=HERE.parents[4]
PREFIX='research/confluence_1h_phase2/event_proximity/strict_series_audit/turn_intensity_phase1/'
PARENT='9793acff82388c5a60b59796af4c6fa765331129'


def fixture(pattern=0, side=1):
    n=30; t=np.arange(n)*HOUR+1735689600000
    a=np.c_[t,np.full(n,100.),np.full(n,101.),np.full(n,99.),np.full(n,100.),np.ones(n)]
    f={k:np.full(n,1.) for k in ('ao','adx','minnows','plus_di','minus_di','atr','adx_rank','adx_curve_rank',
          'ao_intensity_rank','pece_intensity_rank','ao_level_normalized','ao_slope_normalized','adx_curve',
          'pece_intensity','bbwp','regime4h','regime1d','vol_rank')}
    i=10
    # Four strictly signed slopes; t-2 vertex available only at close t.
    ao=np.array([-6.,-7,-8,-7,-6])*side if pattern==0 else np.array([-8.,-7,-6,-7,-8])*(-side)
    if pattern==1:
        ao=np.array([-8.,-7,-6,-7,-8])*(-side)  # no zero-side gate
    f['ao'][:]=ao[0];f['ao'][i-4:i+1]=ao;f['ao'][i+1:]=ao[-1]
    pece=np.array([-1.,-2,-3,-2,-1])*side
    f['minnows'][:]=pece[0];f['minnows'][i-4:i+1]=pece;f['minnows'][i+1:]=pece[-1]
    adx=np.array([30.,31,32,31,30]) if pattern!=1 else np.array([30.,29,28,29,30])
    f['adx'][:]=adx[0];f['adx'][i-4:i+1]=adx;f['adx'][i+1:]=adx[-1]
    f['plus_di'][:]=30 if side==1 else 10;f['minus_di'][:]=10 if side==1 else 30
    for key in ('adx_curve_rank','ao_intensity_rank','pece_intensity_rank'):
        f[key][:]=.8
    f['adx_rank'][:]=.2 if pattern==1 else .8
    return a,f,i


class CausalTests(unittest.TestCase):
    def test_rank_excludes_current_and_future(self):
        x=np.array([1.,2,3,100,5]);r=prior_rank(x,3)
        self.assertEqual(r[3],1.);self.assertEqual(r[4],2/3)
        x[4]=-100;self.assertEqual(prior_rank(x,3)[3],r[3])
    def test_midrank_ties_and_missing_history(self):
        self.assertEqual(prior_rank([2,2,2,2],3)[3],.5)
        self.assertTrue(np.isnan(prior_rank([2,np.nan,2,3],3)[3]))
    def test_two_before_two_after_available_only_last_close(self):
        t=two_turn(np.array([5.,4,3,4,5,6]),1)
        np.testing.assert_array_equal(np.flatnonzero(t),[4])
    def test_all_three_patterns_and_mirrors(self):
        for p in range(3):
            for side in (1,-1):
                a,f,i=fixture(p,side);e,_=detect(a,f)
                found=[x for x in e if x['pattern']==PATTERNS[p] and x['side']==side]
                self.assertEqual(len(found),1,(p,side,e));self.assertEqual(found[0]['i'],i)
                self.assertEqual(found[0]['available_at'],a[i,0]+HOUR)
                self.assertEqual(found[0]['strata'],['ALL','Q75'])
    def test_peak_vs_trough_level_tail_not_reused(self):
        a,f,i=fixture(1,-1);f['adx_rank'][:]=.9
        e,_=detect(a,f);event=next(e for e in e if e['pattern']==PATTERNS[1] and e['side']==-1)
        self.assertEqual(event['strata'],['ALL'])
    def test_q90_not_relaxed_to_generate_more_signals(self):
        a,f,i=fixture();f['ao_intensity_rank'][:]=.74
        event=next(e for e in detect(a,f)[0] if e['pattern']==PATTERNS[0] and e['side']==1)
        self.assertEqual(event['strata'],['ALL'])
    def test_adx_never_supplies_down_direction_without_dmi(self):
        a,f,i=fixture(1,-1);f['plus_di'][:]=40
        self.assertFalse(any(e['pattern']==PATTERNS[1] and e['side']==-1 for e in detect(a,f)[0]))
    def test_pececillos_slope_not_red_cross(self):
        a,f,i=fixture();f['red_line']=np.full(len(a),1000.)
        self.assertTrue(any(e['pattern']==PATTERNS[0] for e in detect(a,f)[0]))
    def test_failed_recovery_cannot_cross_zero(self):
        a,f,i=fixture(2,-1);f['ao'][i-2]=.1
        self.assertFalse(any(e['pattern']==PATTERNS[2] and e['side']==-1 for e in detect(a,f)[0]))
    def test_turn_tokens_expire_no_resurrection(self):
        a,f,i=fixture();f['minnows']=np.r_[np.full(9,-1.),[-1,-2,-3,-2,-1],np.full(16,-1.)]
        self.assertFalse(any(e['pattern']==PATTERNS[0] for e in detect(a,f)[0]))
    def test_nonfinite_candle_and_gap_cannot_emit(self):
        for kind in ('nan','gap'):
            a,f,i=fixture()
            if kind=='nan':a[i,4]=np.nan
            else:a[i:,0]+=HOUR
            self.assertFalse(any(e['pattern']==PATTERNS[0] for e in detect(a,f)[0]))
    def test_no_persistent_state_duplicates_and_cooldown_precedes_intensity(self):
        a,f,i=fixture();events,_=detect(a,f)
        self.assertEqual(len([e for e in events if e['pattern']==PATTERNS[0] and e['side']==1]),1)
        f['ao_intensity_rank'][:]=.1
        self.assertEqual(len([e for e in detect(a,f)[0] if e['pattern']==PATTERNS[0] and e['side']==1]),1)
    def test_prefix_invariance_real_indicator_initialization_and_percentiles(self):
        rng=np.random.default_rng(8);c=50000*np.exp(np.cumsum(rng.normal(0,.003,1000)));o=np.r_[c[0],c[:-1]]
        a=np.c_[1735689600000+np.arange(1000)*HOUR,o,np.maximum(o,c)+30,np.minimum(o,c)-30,c,rng.uniform(10,20,1000)]
        full=features(a);pre=features(a[:900])
        for k in full:np.testing.assert_allclose(full[k][:900],pre[k],rtol=0,atol=0,equal_nan=True)
        past=[e for e in detect(a,full)[0] if e['i']<900]
        self.assertEqual(json.dumps(past,sort_keys=True),json.dumps(detect(a[:900],pre)[0],sort_keys=True))


class InferenceTests(unittest.TestCase):
    def test_holm_preserves_six_and_monotone_adjustment(self):
        np.testing.assert_allclose(holm([.001,.01,.02,.04,.4,1]),[.006,.05,.08,.12,.8,1])
        with self.assertRaises(ValueError):holm([.01]*3)
    def test_power_increases_with_variance_and_smaller_effect(self):
        self.assertGreater(required_n(.02),required_n(.01))
        self.assertGreater(required_n(.01,.0005),required_n(.01,.001))
        self.assertIsNone(required_n(float('nan')))
    def test_small_sample_no_testable_even_favorable(self):
        r=assess([.2,.3],[1,2],0,30,100)
        self.assertEqual(r['classification'],'NO TESTABLE');self.assertEqual(r['p_for_holm'],1.)
    def test_block_inference_deterministic_and_ess_never_above_n(self):
        values=np.tile([.02,.02,-.02,-.02],30);days=np.arange(120)
        a=calendar_bootstrap(values,days,0,120);b=calendar_bootstrap(values,days,0,120)
        self.assertEqual(a,b);self.assertLessEqual(a['effective_n'],120)
    def test_matches_same_side_regime_month_volatility(self):
        n=700;t=1735689600000+np.arange(n)*HOUR
        a=np.c_[t,np.full(n,100.),np.full(n,101.),np.full(n,99.),np.full(n,100.),np.ones(n)]
        f={'vol_rank':np.where(np.arange(n)%2,.9,.1),'regime4h':np.where(np.arange(n)%3,1.,-1.),'atr':np.ones(n)}
        ev=[dict(i=200,side=-1,event_id='TEST')]
        m=match_controls(a,f,ev,0,n)[0];self.assertTrue(m['matched']);self.assertEqual(m['side'],-1)
        for i in m['controls']:
            self.assertEqual(f['regime4h'][i],f['regime4h'][200]);self.assertEqual(f['vol_rank'][i],f['vol_rank'][200])
            self.assertGreaterEqual(abs(i-200),25)
        for x,y in zip(sorted(m['controls']),sorted(m['controls'])[1:]):self.assertGreaterEqual(y-x,25)
    def test_insufficient_match_not_relaxed(self):
        a,f,i=fixture();f['vol_rank'][:]=.1;f['regime4h'][:]=1
        self.assertFalse(match_controls(a,f,[dict(i=i,side=1,event_id='X')],0,len(a))[0]['matched'])


class OutcomeTests(unittest.TestCase):
    def test_entry_next_open_and_exact_12h_after_entry_not_signal(self):
        a,f,i=fixture();a[i+1,1]=102;a[i+13,1]=105
        o=outcome(a,np.empty((0,6)),i,1,2)
        self.assertEqual(o['entry_i'],i+1);self.assertEqual(o['exit_i'],i+13)
        self.assertAlmostEqual(o['entry'],102*1.0005);self.assertAlmostEqual(o['exit'],105*.9995)
        self.assertAlmostEqual(o['net_percent'],100*o['net_fraction']);self.assertNotIn('net_r',o)
    def test_long_short_fees_and_slippage_both_adverse(self):
        a,f,i=fixture()
        for side in (1,-1):self.assertLess(outcome(a,np.empty((0,6)),i,side,1)['net_fraction'],0)
    def test_funding_boundary_and_missing_mark_never_claimed_exact(self):
        a,f,i=fixture();fund=np.array([[a[i+1,0],.001,np.nan,8,98,102]])
        o=outcome(a,fund,i,1,1)
        self.assertIsNone(o['exact_net_fraction']);self.assertEqual(o['missing_marks'],1)
        self.assertEqual(o['boundary_settlements'],1);self.assertLess(o['net_fraction'],o['optimistic_fraction'])
    def test_no_early_outcome_or_gap_fill(self):
        a,f,i=fixture();self.assertIsNone(outcome(a[:20],np.empty((0,6)),i,1,1))
        a[i+2:,0]+=HOUR;self.assertIsNone(outcome(a,np.empty((0,6)),i,1,1))
    def test_no_stop_or_r_in_phase1(self):
        a,f,i=fixture();r=outcome(a,np.empty((0,6)),i,1,2)
        self.assertFalse(any(k in r for k in ('stop','target_r','net_r','win_r')))


class StressAndIsolationTests(unittest.TestCase):
    def test_size_from_stop_and_costs_not_margin_percentage(self):
        near=sized_quantity(10000,100000,99000,1);far=sized_quantity(10000,100000,95000,1)
        self.assertGreater(near['qty'],far['qty'])
        for r in (near,far):self.assertLessEqual(r['planned_loss'],100)
    def test_current_maintenance_rate_not_historical_liquidation_claim(self):
        r=isolated_threshold(100000,.5,5000,1,.003,50)
        self.assertAlmostEqual(r['price'],90400)
        self.assertIn('CONDITIONAL',r['status'])
    def test_stress_exposure_and_gap_can_breach_planned_risk(self):
        rows=illustrative_scenarios()
        stress=[r for r in rows if r['model'].startswith('STRESS')]
        self.assertTrue(all(r['qty']==.5 for r in stress))
        self.assertTrue(any(r['stop_beyond_conditional_threshold'] for r in stress))
        self.assertTrue(all(r['gap_1pct_loss_before_liquidation_model']>r['planned_loss'] for r in rows))
    def test_protocol_frozen_before_outcome_measurement(self):
        raw=subprocess.check_output(['git','show','a6b3cfb:'+PREFIX+'protocol.json'],cwd=ROOT)
        self.assertEqual(raw,(HERE/'protocol.json').read_bytes())
        p=json.loads(raw);self.assertEqual(p['intensity']['primary'],'Q75')
        self.assertEqual(p['outcomes']['primary_hours'],12);self.assertFalse(p['forward']['currently_running'])
    def test_old_research_and_every_runtime_file_unchanged(self):
        lines=subprocess.check_output(['git','diff',PARENT,'--name-status'],cwd=ROOT,text=True).splitlines()
        for line in lines:
            status,path=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(path.startswith(PREFIX),line)
    def test_offline_modules_no_private_or_execution_imports(self):
        banned={'requests','socket','urllib','ccxt','guardian_bitunix','trade_guardian','bitman_manual','live_auto'}
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in node.names]+([node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                    for name in names:self.assertFalse(banned.intersection(name.split('.')),str(path))
    def test_public_receipts_are_unsigned_get_only(self):
        for name in ('pairs','tiers'):
            receipt=json.loads((HERE/'public_metadata'/f'{name}_receipt.json').read_text())
            raw=(HERE/'public_metadata'/f'{name}.json').read_bytes()
            self.assertEqual(receipt['method'],'GET');self.assertFalse(receipt['authentication'])
            self.assertEqual(receipt['sha256'],hashlib.sha256(raw).hexdigest())


if __name__=='__main__':unittest.main()
