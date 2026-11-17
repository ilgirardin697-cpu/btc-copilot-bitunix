import copy,json,unittest
from pathlib import Path
import subprocess
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Dedicated numerical research CI requires NumPy; bare runtime is optional') from error
from mlrsi_math import CausalSeries
from research.confluence_1h.indicators import calculate as old
from .backquant import OriginalMLRSI,equal_v5,percentile
from .profile import calculate,settings,adx14,tsa,tsa_table,HERE,H,wma,bbwp_color


def bars(n=250):
    x=np.arange(n);c=60000+x*.2+100*np.sin(x/9)+50*np.cos(x/21)
    return np.column_stack((1794009600000+x*H,c-5,c+20,c-25,c,20+np.sin(x)))


class SourceAndProfile(unittest.TestCase):
    def test_active_inputs_not_defaults(self):
        cfg=settings()['active_inputs']
        self.assertEqual((cfg['bbwp']['i_basisLen'],cfg['bbwp']['i_lookback']),(13,252))
        self.assertEqual((cfg['mlrsi']['rsiLength'],cfg['mlrsi']['maType'],cfg['mlrsi']['sig']),(27,'ALMA',1))
        self.assertEqual((cfg['tsa']['max_length'],cfg['tsa']['accel_multiplier']),(119,2.8))

    def test_original_has_no_opt_substitute(self):
        s=(HERE/'sources/mlrsi.pine').read_text('utf-8')
        self.assertIn('distances = array.new_float(3)',s)
        self.assertIn('new_centroids = array.new_float(3)',s)
        self.assertIn('"ALMA" => ta.alma(src, len, 0, almaSig)',s)
        self.assertNotIn('OPT',s)

    def test_all_old_sources_unchanged(self):
        root=HERE.parents[8];prefix=HERE.relative_to(root).as_posix()+'/'
        lines=subprocess.check_output(['git','diff','e098354b4f162d05bb814db3dda330372c09fa62','--name-status'],cwd=root,text=True).splitlines()
        for line in lines:self.assertTrue(line.startswith('A\t'+prefix),line)

    def test_runtime_does_not_import_profile(self):
        root=HERE.parents[8]
        paths=subprocess.check_output(['git','ls-files','--','*.py'],cwd=root,text=True).splitlines()
        for p in paths:
            if p.startswith('research/') or Path(p).name.startswith('test_'):continue
            self.assertNotIn('tradingone_v2',(root/p).read_text('utf-8-sig'),p)


class OriginalBackQuantTests(unittest.TestCase):
    def test_first_bar_grows_three_na_to_six(self):
        m=OriginalMLRSI(0);r=m.push(100)
        self.assertEqual(m.centroids,[None]*6);self.assertEqual(r['iterations'],2)

    def test_na_equality_is_v5_not_python(self):
        self.assertTrue(equal_v5([None,1],[3,None]))
        self.assertFalse(equal_v5([None],[None,None]))
        self.assertFalse(equal_v5([2],[3]))

    def test_linear_percentile(self):
        self.assertEqual(percentile([None,8,2,4,6],25),3.5)

    def test_no_rolling_eviction(self):
        m=OriginalMLRSI(5,max_data=3)
        for i in range(20):m.push(100+i)
        self.assertEqual(len(m.values),18)

    def test_gate_depends_on_load_anchor(self):
        m=OriginalMLRSI(100,max_data=3)
        for i in range(97):self.assertFalse(m.push(100+i)['eligible'])
        self.assertTrue(m.push(197)['eligible'])

    def test_alma_requires_four_rsi_values(self):
        m=OriginalMLRSI(40)
        rr=[m.push(v) for v in bars(40)[:,3]]
        self.assertIsNotNone(rr[27]['raw']);self.assertIsNone(rr[29]['value'])
        self.assertIsNotNone(rr[30]['value'])

    def test_alma_zero_offset_manual_weighting(self):
        m=OriginalMLRSI(60);rr=[m.push(v) for v in bars(60)[:,3]]
        raw=np.array([r['raw'] for r in rr[-4:]],float)
        weights=np.exp(-(np.arange(4)**2)/32)
        self.assertAlmostEqual(rr[-1]['value'],float(raw@weights/weights.sum()),places=12)

    def test_literal_control_flow_matches_audited_ema29_not_its_configuration(self):
        a=bars(130);literal=OriginalMLRSI(130,length=29,ma='EMA');oper=CausalSeries();oper.configure_bootstrap(130)
        for low in a[:,3]:
            x=literal.push(low);y=oper.push(low)
            for k,j in [('value','mlrsi_smoothed'),('lower','lower_threshold'),('upper','upper_threshold')]:
                if x[k] is None:self.assertIsNone(y[j])
                else:self.assertAlmostEqual(x[k],y[j],places=9)

    def test_preview_rollback_no_commit(self):
        m=OriginalMLRSI(150)
        for low in bars(150)[:,3]:m.push(low)
        before=m.state();p=m.preview(60100)
        self.assertEqual(m.state(),before)
        self.assertEqual(p,m.preview(60100))
        self.assertNotEqual(p['value'],m.preview(60300)['value'])

    def test_fixed_anchor_prefix_invariance(self):
        low=bars(150)[:,3];m=OriginalMLRSI(150);left=[m.push(v) for v in low[:100]]
        n=OriginalMLRSI(150);full=[n.push(v) for v in low]
        self.assertEqual(left,full[:100])

    def test_changed_anchor_can_change_reloaded_history(self):
        low=bars(100)[:,3]
        a=OriginalMLRSI(80,max_data=40);b=OriginalMLRSI(99,max_data=40)
        x=[a.push(v) for v in low];y=[b.push(v) for v in low]
        self.assertNotEqual(x[70]['samples'],y[70]['samples'])
        self.assertNotEqual(x[70]['upper'],y[70]['upper'])

    def test_no_valid_cluster_scatter_after_literal_index_shift(self):
        m=OriginalMLRSI(100)
        rr=[m.push(v) for v in bars(100)[:,3]]
        self.assertTrue(rr[-1]['valid'])
        self.assertTrue(all(rr[-1][k] is None for k in ('cluster1','cluster2','cluster3')))


class FormulaTests(unittest.TestCase):
    def test_ao_and_full_koncorde_are_audited_formulas(self):
        a=bars();f,_=calculate(a);ref=old(a)
        for k,j in [('ao','ao'),('pececillos','minnows'),('tendencia','kon_trend'),('tiburones','sharks'),('roja','kon_signal')]:
            np.testing.assert_array_equal(f[k],ref[j])

    def test_adx14_reference_on_finite_history(self):
        a=bars();f,p,m=adx14(a);ref=old(a)
        np.testing.assert_allclose(f,ref['adx'],atol=1e-12,equal_nan=True)
        np.testing.assert_allclose(p,ref['plus_di'],atol=1e-12,equal_nan=True)

    def test_bbwp_signal_sma5(self):
        f,_=calculate(bars())
        self.assertAlmostEqual(f['bbwp_signal'][-1],float(np.mean(f['bbwp'][-5:])))

    def test_ao_color_flat_red_not_strict_bearish_turn(self):
        a=bars(100);a[:,1:5]=[100,102,99,101]
        f,_=calculate(a);self.assertEqual(f['ao_color'][-1],'RED')
        self.assertEqual(f['ao_slope'][-1],0)
        self.assertEqual(f['ao_turn'][-1],0)

    def test_bbwp_custom_white_at_25(self):
        self.assertEqual(bbwp_color(25,settings()['active_inputs']['bbwp']),'#FFFFFFFF')

    def test_hma5_explicit_finite_reference(self):
        x=np.arange(20,dtype=float)
        a=2*wma(x,2)-wma(x,5);out=wma(a,2)
        self.assertAlmostEqual(out[-1],(a[-2]+2*a[-1])/3)

    def test_tsa_dynamic_ema_literal_reference(self):
        a=bars(50);cfg=settings()['active_inputs']['tsa'];f=tsa(a,cfg)
        prev=None;deltas=[]
        for i,c in enumerate(a[:,4]):
            greatest=max(a[:i+1,4]);norm=(c+greatest)/(2*greatest);length=5+norm*114
            delta=abs(c-(a[i-1,4] if i else 0));deltas.append(delta)
            factor=delta/max(deltas);alpha=min(1,2/(length+1)*(1+factor*2.8))
            prev=c if prev is None else alpha*c+(1-alpha)*prev
            self.assertAlmostEqual(f['tsa_trend'][i],prev,places=9)
        table=tsa_table(f)
        self.assertAlmostEqual(table['current_raw_wave'],float(f['tsa_raw_speed'][-1]))

    def test_tsa_prefix_invariance(self):
        a=bars(100);cfg=settings()['active_inputs']['tsa']
        full=tsa(a,cfg);prefix=tsa(a[:70],cfg)
        for k in full:np.testing.assert_array_equal(full[k][:70],prefix[k])

    def test_full_profile_prefix_fixed_anchor(self):
        a=bars(150);full,_=calculate(a,150);prefix,_=calculate(a[:100],150)
        for k in full:np.testing.assert_array_equal(full[k][:100],prefix[k])

    def test_incomplete_gapped_input_rejected(self):
        a=bars();a[50:,0]+=H
        with self.assertRaisesRegex(ValueError,'GAP'):calculate(a)


if __name__=='__main__':unittest.main()
