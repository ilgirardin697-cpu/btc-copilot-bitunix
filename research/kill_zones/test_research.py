"""Offline causal fixtures, statistical invariants and production boundary."""
import ast,hashlib,json,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import numpy as np
from . import data,models,simulation,statistics
from .data import HOUR,M5,stamp
def bars(n=400,start=None,step=M5,price=100):
    t=(stamp('2026-02-01T00:00:00Z') if start is None else start)+np.arange(n)*step
    return np.column_stack((t,np.full(n,price),np.full(n,price+1),np.full(n,price-1),
                            np.full(n,price),np.ones(n)*10,np.ones(n)*4))
def signal(base,side=1,**extra):
    return dict(model='NY_EXTREME_TIMES_TP95',date='2026-02-01',signal_at=int(base[0,0]),
        entry_at=int(base[0,0]),side=side,stop=90 if side==1 else 110,target=120 if side==1 else 80,
        signal_index=0,**extra)
class SessionTests(unittest.TestCase):
    def test_summer_ny_equals_fixed(self):
        self.assertEqual(models.boundaries(date(2025,7,5),'NY'),models.boundaries(date(2025,7,5),'UTC4'))
    def test_winter_clock_difference(self):
        ny=models.boundaries(date(2025,1,5),'NY');fixed=models.boundaries(date(2025,1,5),'UTC4')
        self.assertTrue(all(a-b==HOUR for a,b in zip(ny,fixed)))
    def test_spring_skipped_hour_not_fabricated(self):
        a,b,c,d,e=models.boundaries(date(2025,3,9),'NY')
        self.assertEqual(d-c,2*HOUR);self.assertEqual(b-a,4*HOUR)
    def test_fall_london_three_physical_hours(self):
        a,b,c,d,e=models.boundaries(date(2025,11,2),'NY')
        self.assertEqual(d-c,3*HOUR);self.assertEqual(b-a,4*HOUR)
    def test_session_half_open(self):
        a=bars(6,step=HOUR);a[-1,2]=999
        box=models.session(a,int(a[0,0]),int(a[4,0]))
        self.assertEqual(box['high'],101);self.assertEqual(box['hours'],4)
    def test_tie_earliest_extreme(self):
        a=bars(4,step=HOUR);box=models.session(a,int(a[0,0]),int(a[0,0]+4*HOUR))
        self.assertEqual(box['high_at'],a[0,0]+HOUR);self.assertEqual(box['low_at'],a[0,0]+HOUR)
    def test_missing_session_not_filled(self):
        a=bars(4,step=HOUR)
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):models.session(a[[0,1,3]],int(a[0,0]),int(a[0,0]+4*HOUR))
    def test_weekend_not_implicitly_filtered(self):
        self.assertEqual(date(2026,2,1).weekday(),6)
    def test_wick_no_confirmation(self):
        self.assertEqual(models.crossing(100,100,101,99,101,99),0)
    def test_closed_cross_symmetric(self):
        self.assertEqual(models.crossing(100,102,101,99,101,99),1)
        self.assertEqual(models.crossing(100,98,101,99,101,99),-1)
    def test_cross_requires_prior_inside(self):
        self.assertEqual(models.crossing(102,103,101,99,101,99),0)
    def test_degenerate_geometry_no_signal(self):
        self.assertEqual(models.crossing(100,103,99,101,99,101),0)
    def test_line_exact_anchors(self):
        self.assertEqual(models.line(100,0,120,5,0),100);self.assertEqual(models.line(100,0,120,5,5),120)
    def test_no_future_anchor(self):
        with self.assertRaises(ValueError):models.line(100,5,120,4,8)
    def test_primary_and_endpoint_geometries_differ_without_tuning(self):
        z=dict(asia=dict(high=100,low=90,high_at=1,low_at=2,end=4),
               london=dict(high=105,low=92,high_at=7,low_at=6,end=9),high=105,low=90)
        self.assertNotEqual(models.levels(z,'EXTREME_TIMES',10),models.levels(z,'BOX_ENDS',10))
        self.assertEqual(models.levels(z,'RANGE',10),(105,90))
    def test_signal_prefix_and_future_extremes_do_not_repaint_boxes(self):
        a=bars(72,start=stamp('2026-02-01T00:00:00Z'),step=HOUR)
        day=date(2026,2,2);le=models.boundaries(day,'NY')[3]
        i=int(np.searchsorted(a[:,0],le));a[i,2]=103;a[i,4]=102
        before=models.first_signal(a[:i+1],day,'NY','EXTREME_TIMES')
        a[i+10,2]=9999
        self.assertEqual(before,models.first_signal(a,day,'NY','EXTREME_TIMES'))
        self.assertEqual(before['boxes']['high'],101)
        self.assertEqual(before['signal_at'],le+HOUR)
    def test_incomplete_london_cannot_signal(self):
        a=bars(72,start=stamp('2026-02-01T00:00:00Z'),step=HOUR)
        day=date(2026,2,2);le=models.boundaries(day,'NY')[3]
        with self.assertRaisesRegex(ValueError,'INCOMPLETE'):
            models.first_signal(a[a[:,0]<le-HOUR],day,'NY','EXTREME_TIMES')
class DataTests(unittest.TestCase):
    def test_aggregation_exact(self):
        a=bars(12);g=data.aggregate(a,HOUR)
        self.assertEqual(len(g),1);self.assertEqual(g[0,5],120);self.assertEqual(g[0,6],48)
    def test_167_style_incomplete_hour_dropped(self):
        self.assertEqual(len(data.aggregate(bars(11),HOUR)),0)
    def test_duplicate_rejected(self):
        a=bars(12);a[3,0]=a[2,0]
        with self.assertRaises(ValueError):data.validate(a)
    def test_bad_ohlc_rejected(self):
        a=bars(12);a[0,2]=80
        with self.assertRaises(ValueError):data.validate(a)
    def test_nan_rejected(self):
        a=bars(12);a[0,4]=np.nan
        with self.assertRaises(ValueError):data.validate(a)
    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):data.url('spot','2025-01')
        with self.assertRaises(ValueError):data.url('bars','2030-01')
    def test_checksum_mutation_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bars-2025-01'
            p.with_suffix('.zip').write_bytes(b'altered');p.with_suffix('.checksum').write_text('0'*64)
            with self.assertRaisesRegex(ValueError,'CHECKSUM'):data.read(d,'bars','2025-01')
    def test_gap_hour_not_interpolated(self):
        a=bars(24);a=np.delete(a,3,axis=0);g=data.aggregate(a,HOUR)
        self.assertEqual(len(g),1);self.assertEqual(g[0,0],a[0,0]+HOUR)
class SimulationTests(unittest.TestCase):
    def test_next_open_not_signal_close(self):
        a=bars();a[0,1:5]=[105,106,104,105]
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['entry_price'],105)
    def test_both_touched_stop_first_long(self):
        a=bars();a[0,2:4]=[125,85]
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['reason'],'STOP');self.assertTrue(r['ambiguous']);self.assertEqual(r['net_r'],-1)
    def test_both_touched_stop_first_short(self):
        a=bars();a[0,2:4]=[115,75]
        r=simulation.simulate(signal(a,-1),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['reason'],'STOP');self.assertTrue(r['ambiguous']);self.assertEqual(r['net_r'],-1)
    def test_gap_beyond_stop_rejects_entry(self):
        a=bars();a[0,1:5]=[85,86,84,85]
        self.assertIn('STOP',simulation.simulate(signal(a),a,np.empty((0,2)))['rejection'])
    def test_gap_beyond_target_rejects_entry(self):
        a=bars();a[0,1:5]=[125,126,124,125]
        self.assertIn('TARGET',simulation.simulate(signal(a),a,np.empty((0,2)))['rejection'])
    def test_stop_gap_fills_worse(self):
        a=bars();a[1,1:5]=[85,86,84,85]
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['exit_price'],85);self.assertEqual(r['reason'],'STOP_GAP')
    def test_target_gap_gets_no_extra_profit(self):
        a=bars();a[1,1:5]=[125,126,124,125]
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['exit_price'],120)
    def test_commissions_both_legs(self):
        a=bars();a[1,2]=121
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=.001)
        self.assertAlmostEqual(r['fees_unit'],.22);self.assertAlmostEqual(r['net_unit'],19.78)
    def test_adverse_slippage_each_leg(self):
        a=bars();a[1,2]=121
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=.001,fee=0)
        self.assertAlmostEqual(r['entry_price'],100.1);self.assertAlmostEqual(r['exit_price'],119.88)
    def test_time_exit_24_physical_hours(self):
        a=bars()
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertEqual(r['duration_hours'],24);self.assertEqual(r['reason'],'TIME')
    def test_gap_censored_not_filled(self):
        a=bars();a=np.delete(a,5,axis=0)
        self.assertEqual(simulation.simulate(signal(a),a,np.empty((0,2)))['rejection'],'CENSORED_DATA_GAP')
    def test_no_outcome_before_history(self):
        a=bars(10)
        self.assertEqual(simulation.simulate(signal(a),a,np.empty((0,2)))['rejection'],'CENSORED_HISTORY_END')
    def test_funding_offset_uses_last_closed_bar(self):
        a=bars();t=a[3,0]+1;f=np.array([[t,.001]])
        cash,_=simulation.funding_cash(a,f,1,a[0,0],t+M5)
        self.assertAlmostEqual(cash,-.1)
    def test_short_receives_positive_funding(self):
        a=bars();t=a[3,0];cash,_=simulation.funding_cash(a,np.array([[t,.001]]),-1,a[0,0],t)
        self.assertAlmostEqual(cash,.1)
    def test_exact_entry_no_free_funding_credit(self):
        a=bars();t=a[2,0]
        cash,_=simulation.funding_cash(a,np.array([[t,.001]]),-1,t,t+M5)
        self.assertEqual(cash,0)
    def test_exact_entry_adverse_funding_charged(self):
        a=bars();t=a[2,0]
        cash,_=simulation.funding_cash(a,np.array([[t,.001]]),1,t,t+M5)
        self.assertAlmostEqual(cash,-.1)
    def test_exit_bar_future_peaks_not_counted(self):
        a=bars();a[1,2:4]=[150,85]
        r=simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0)
        self.assertLess(r['mfe_r'],1)
    def test_prefix_outcome_unchanged_after_exit(self):
        a=bars();a[1,2]=121
        before=simulation.simulate(signal(a),a[:5],np.empty((0,2)),slip=0,fee=0)
        a[100,2]=99999
        self.assertEqual(before,simulation.simulate(signal(a),a,np.empty((0,2)),slip=0,fee=0))
    def test_split_embargo(self):
        lo,hi=simulation.SPLITS['EVALUATION']
        self.assertIsNone(simulation.split_at(lo+HOUR));self.assertEqual(simulation.split_at(lo+49*HOUR),'EVALUATION')
        self.assertIsNone(simulation.split_at(hi-HOUR))
    def test_no_overlapping_positions(self):
        a=bars();s=signal(a);s2=dict(s,entry_at=s['entry_at']+HOUR)
        t,r,p=simulation.replay([s,s2],a,np.empty((0,2)))
        self.assertEqual(len(t),1);self.assertEqual(r[0]['reason'],'OVERLAPPING_POSITION')
class FeatureTests(unittest.TestCase):
    def test_frozen_formula_parity(self):
        from bitman_manual.frozen.core import feature
        a=bars(600,step=HOUR);x=np.arange(len(a))*.04+np.sin(np.arange(len(a))/4)
        a[:,1:5]+=x[:,None]
        out=models.context(a);reference=feature(a)
        for key in ('ao','ao_slope','adx','adx_slope','di_plus','di_minus'):
            np.testing.assert_allclose(out['h1_'+key],reference[key],equal_nan=True,rtol=0,atol=0)
    def test_feature_prefix_and_confirmed_higher_timeframes(self):
        a=bars(600,step=HOUR);a[:,1:5]+=np.sin(np.arange(len(a))/3)[:,None]
        before=models.context(a[:510]);after=models.context(a)
        for key in before:
            if key.endswith('konkorde'):np.testing.assert_array_equal(before[key],after[key][:510])
            else:np.testing.assert_allclose(before[key],after[key][:510],equal_nan=True,rtol=0,atol=0)
    def test_adx_not_direction(self):
        c=dict(h1_ao_slope=np.array([-1.]),h1_di_plus=np.array([10.]),h1_di_minus=np.array([20.]),
               h1_adx_slope=np.array([1.]),h1_konkorde=np.array(['KONKORDE_BEARISH_CONTEXT']))
        self.assertFalse(models.gate(c,0,1,'DMI_ADX'));self.assertTrue(models.gate(c,0,-1,'DMI_ADX'))
class StatisticsAndBoundaryTests(unittest.TestCase):
    def test_block_indices_deterministic(self):
        np.testing.assert_array_equal(statistics.samples(100),statistics.samples(100))
    def test_small_sample_inconclusive(self):
        self.assertEqual(statistics.classify({'n':29},{},{},{},{}),'INCONCLUSIVE')
    def test_negative_net_no_edge(self):
        e=dict(n=100,mean_net_r=-.1,profit_factor=.8,ci95=[-.2,0])
        self.assertEqual(statistics.classify(e,{},{},{},{}),'NO EDGE')
    def test_identity_baseline_difference_zero(self):
        rows=[dict(date='2026-02-01',net_r=.2)]
        p=statistics.paired(rows,rows,'EVALUATION')
        self.assertEqual(p['familywise_ci'],[0,0])
    def test_production_source_unchanged(self):
        lock=Path(__file__).with_name('protocol_lock.json')
        if not lock.exists():self.skipTest('Lock created before first outcome run')
        from .study import production_hashes
        self.assertEqual(json.loads(lock.read_text())['production_hashes'],production_hashes())
    def test_no_production_research_dependency_or_authority(self):
        from .study import production_hashes
        for path in production_hashes():
            source=Path(path).read_text(encoding='utf-8')
            self.assertNotIn('kill_zones',source,path)
        for path in Path(__file__).parent.glob('*.py'):
            if path.name=='test_research.py':continue
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith(('guardian_capital_v2','guardian_bitunix','v8_executor','mlrsi_math')))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,('post','sendMessage','place_order','cancel_order','getenv'),str(path))
if __name__=='__main__':unittest.main()
