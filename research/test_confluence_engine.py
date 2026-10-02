"""Synthetic causal, accounting and safety tests; no network needed."""
import inspect
import unittest
from unittest.mock import patch
import numpy as np
from research import confluence_engine_backtest as e

def bars(n=3000):
    rng=np.random.default_rng(31)
    c=100*np.exp(np.cumsum(rng.normal(0,.002,n)))
    o=np.r_[c[0],c[:-1]]
    return np.column_stack((e.START+np.arange(n)*e.STEP,o,np.maximum(o,c)*1.001,np.minimum(o,c)*.999,c,np.full(n,10.),rng.uniform(2,8,n)))

class ResearchTests(unittest.TestCase):
    def test_ml_rsi_prefix(self):
        a=bars()
        for n in (100,501,999):
            for short,long in zip(e.ml_rsi(a[:n,4]),e.ml_rsi(a[:,4])):
                np.testing.assert_array_equal(short,long[:n])

    def test_signals_prefix_invariant_no_lookahead(self):
        a=bars(11000)
        for tf in (5,15,30,60):
            full,f=e.features(a,tf,60)
            prefix,p=e.features(a[:7000],tf,60)
            for k in f:
                np.testing.assert_allclose(p[k],f[k][:len(prefix)],equal_nan=True,err_msg=k)
            for family in 'ABCDEF':
                np.testing.assert_array_equal(e.entries(p,family),e.entries(f,family)[:len(prefix)])

    def test_closed_candles(self):
        a=bars(49)
        self.assertEqual(len(e.aggregate(a,240)),1)
        source=e.aggregate(a,60); values=np.arange(len(source))+1
        v=e.align(values,source,60,np.array([e.START+59*60000,e.START+60*60000]))
        np.testing.assert_array_equal(v,[0,1])

    def test_validate_unclosed(self):
        row=[e.START,100,101,99,100,10,e.START+e.STEP-1,0,0,6]
        self.assertEqual(len(e.validate([row],e.START+e.STEP-1)),0)
        row[6]-=1
        with self.assertRaises(ValueError): e.validate([row])

    def test_divergence_confirmation(self):
        a=bars(12); a[:,3]=[10,9,5,9,10,11,9,4,9,10,11,12]
        oscillator=np.array([50,40,20,40,50,50,40,30,40,50,50,50])
        bull,_,_,_=e.pivots(a,oscillator)
        self.assertFalse(bull[7]); self.assertFalse(bull[8]); self.assertTrue(bull[9])
        for n in range(5,12):
            np.testing.assert_array_equal(e.pivots(a[:n],oscillator[:n])[0],bull[:n])

    def fixture(self):
        a=bars(6); a[:,1:5]=100
        f={'reg':np.ones(6,bool),'state':np.ones(6),'low':np.full(6,90.),'high':np.full(6,110.),'atr':np.ones(6)}
        sig=np.zeros(6,bool); sig[1]=True
        return a,f,sig

    def test_execution_next_bar_and_fees(self):
        a,f,sig=self.fixture()
        r=e.simulate(a,f,sig,np.empty((0,2)),5,cost=.001)
        self.assertEqual(r['trades'][0]['entry_time'],int(a[2,0]))
        self.assertAlmostEqual(r['metrics']['total_return'],-.002)
        self.assertAlmostEqual(r['metrics']['fees'],.001)
        self.assertAlmostEqual(r['metrics']['slippage'],.001)
        self.assertAlmostEqual(r['metrics']['turnover'],2.)

    def test_funding_direction_and_boundary(self):
        a,f,sig=self.fixture()
        funding=np.array([[a[1,0],.01],[a[2,0],.02]])
        r=e.simulate(a,f,sig,funding,5,cost=0)
        self.assertAlmostEqual(r['metrics']['total_return'],-.02)
        self.assertAlmostEqual(r['metrics']['funding'],.02)
        r=e.simulate(a,f,sig,funding,5,cost=0,side=-1)
        self.assertAlmostEqual(r['metrics']['total_return'],.02)

    def test_no_private_api_or_orders(self):
        for url in ('https://fapi.binance.com/fapi/v1/order','https://fapi.binance.com/fapi/v2/account','https://evil.com/data/a','http://data.binance.vision/data/a'):
            with self.assertRaises(ValueError): e.public_get(url)
        source=inspect.getsource(e)
        for forbidden in ('requests.post','requests.delete','v8_executor','live_auto','api_key','api_secret'):
            self.assertNotIn(forbidden,source)
        with patch.object(e.requests,'get') as get:
            get.return_value.status_code=200
            e.public_get('https://fapi.binance.com/fapi/v1/klines')
            self.assertEqual(get.call_count,1)

    def test_clean_splits(self):
        self.assertLess(e.START,e.TRAIN_END); self.assertLess(e.TRAIN_END,e.TEST_START)
        a,f,sig=self.fixture()
        hi=int(a[4,0]); sig[:]=True
        r=e.simulate(a,f,sig,np.empty((0,2)),5,lo=int(a[2,0]),hi=hi)
        self.assertTrue(all(int(a[2,0])<=t['entry_time']<hi and t['exit_time']<hi for t in r['trades']))

    def test_test_never_selects(self):
        metric=lambda x:{'trades':30,'Sharpe':x}
        rows=[{'id':'a','TRAIN':metric(1),'VALIDATION':metric(2),'TEST':metric(-100)}, {'id':'b','TRAIN':metric(1),'VALIDATION':metric(1),'TEST':metric(100)}]
        self.assertEqual(e.select(rows)['id'],'a')
        rows[0]['TEST']=metric(1000); rows[1]['TEST']=metric(-1000)
        self.assertEqual(e.select(rows)['id'],'a')

    def test_mfe_mae_and_first_passage(self):
        a=bars(600); a[:,1:5]=100; a[1,2]=102; a[2,3]=99
        x=e.excursions(a,np.array([a[0,0]]))['1']
        self.assertAlmostEqual(x['MFE_mean'],.02); self.assertAlmostEqual(x['MAE_mean'],-.01)
        self.assertEqual(x['first_passage']['0.01/0.01'],1.)
        a[1,3]=98
        self.assertEqual(e.excursions(a,np.array([a[0,0]]))['1']['first_passage']['0.01/0.01'],0.)

    def test_ablation_reproducible(self):
        a,f=e.features(bars(),15,60)
        np.testing.assert_array_equal(e.entries(f,'RLM'),e.entries(f,'R')&e.entries(f,'L')&e.entries(f,'M'))
        for family in ('R','L','M','RL','RM','LM','RLM'):
            first=e.simulate(a,f,e.entries(f,family),np.empty((0,2)),15)
            second=e.simulate(a,f,e.entries(f,family),np.empty((0,2)),15)
            self.assertEqual(first,second)

    def test_selected_ablation_preserves_entry(self):
        _,f=e.features(bars(11000),15,60)
        for family in 'BCDEF':
            np.testing.assert_array_equal(e.ablation_signals(f,family)['RLM'],e.entries(f,family))
        np.testing.assert_array_equal(e.ablation_signals(f,'A')['RM'],e.entries(f,'A'))

    def test_stop_first_when_both_touched(self):
        a,f,sig=self.fixture()
        a[2,2]=110; a[2,3]=90
        r=e.simulate(a,f,sig,np.empty((0,2)),5,exit_kind='rr',cost=0)
        self.assertEqual(r['trades'][0]['reason'],'stop')
        self.assertAlmostEqual(r['trades'][0]['return'],-.02)

    def test_funding_event_not_assigned_to_previous_bar(self):
        a,_,_=self.fixture()
        f=e.funding_vector(a,np.array([[a[2,0],.01],[a[3,0]+3,.02]]),5)
        self.assertEqual(f[1],0); self.assertEqual(f[2],.01); self.assertEqual(f[3],.02)

    def test_4h_stays_unknown_until_close(self):
        a=bars(10000); a[:,1:5]=100; a[-48:,1:5]=200
        g=e.aggregate(a,240); reg=g[:,4]>e.rolling(g[:,4],200)
        times=np.array([g[-1,0]+240*60000-1,g[-1,0]+240*60000])
        aligned=e.align(reg,g,240,times)
        self.assertEqual(aligned[0],reg[-2]); self.assertEqual(aligned[1],reg[-1])

    def test_forward_diagnostics_cannot_cross_split(self):
        a=bars(600); t=np.array([a[0,0],a[12,0]])
        x=e.excursions(a,t,cutoff=int(a[12,0]))
        self.assertEqual(x['1']['n'],1)
        self.assertEqual(x['4']['n'],0)

    def test_trade_compounding_equals_equity_with_funding(self):
        a,f=e.features(bars(),15,60)
        sig=e.entries(f,'D')
        funding=np.column_stack((a[::32,0],np.full(len(a[::32]),.0001)))
        r=e.simulate(a,f,sig,funding,15,exit_kind='atr')
        compounded=np.prod([1+t['return'] for t in r['trades']])-1
        self.assertAlmostEqual(compounded,r['metrics']['total_return'],places=10)

if __name__=='__main__': unittest.main()
