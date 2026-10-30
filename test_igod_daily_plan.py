"""Unit tests use synthetic candles; they are NOT real forward results."""
import copy
import math
import time
import unittest
try:
    import requests
except ImportError:
    raise unittest.SkipTest('Daily workflow installs requests') from None
from unittest.mock import patch
from igod_daily_plan.core import (STEPS, HISTORIES, WEEKLY_ANCHOR, normalize, adx_series, ao_series,
                                  bbwp_series, pivots, support_resistance, risk_sizing, generate_plan)

ASOF=1793476800000 # 2026-10-31 20:00Z, synthetic fixtures only


def synth(tf,n=330,asof=ASOF,slope=0.02, wiggle=0.65):
    step=STEPS[tf]
    last_open=(((asof-1-(WEEKLY_ANCHOR if tf=='1w' else 0))//step)*step +(WEEKLY_ANCHOR if tf=='1w' else 0))
    first=last_open-(n-1)*step
    out=[]
    for i in range(n):
        p=120+ i*slope + math.sin(i*.31)*wiggle + math.sin(i*.085)*wiggle
        c=p+math.sin(i*.2)*.05
        o=p-math.sin(i*.1)*.03
        h=max(c,o)+.23
        l=min(c,o)-.23
        out.append([first+i*step,str(o),str(h),str(l),str(c),'150',first+(i+1)*step-1,'18000',60,'90','12000','0'])
    return out


def history(asof=ASOF,slope=0.02):return {tf:synth(tf,HISTORIES[tf]+1,asof,slope) for tf in HISTORIES}

class TestDailyPlan(unittest.TestCase):
    def test_normalization_only_closed(self):
        rows=synth('1d',331)
        closed=normalize(rows,'1d',ASOF,330)
        self.assertTrue(all(x['close_ts']<=ASOF for x in closed))
        self.assertEqual(len(closed),330)

    def test_valid_weekly_monday_alignment(self):
        r=synth('1w',331)
        self.assertTrue(all((x[0]-WEEKLY_ANCHOR)%STEPS['1w']==0 for x in r))
        self.assertEqual(len(normalize(r,'1w',ASOF,330)),330)

    def test_data_gap_rejected(self):
        r=synth('1h',261)
        del r[60]
        with self.assertRaisesRegex(ValueError,'GAPPED_OR_DUPLICATE'):
            normalize(r,'1h',ASOF,250)

    def test_current_open_is_excluded(self):
        asof=ASOF+7*60*1000
        rows=synth('15m',221,asof)
        a=normalize(rows,'15m',asof,220)
        rows[-1][4]=rows[-1][1] # current bar close arbitrarily changed
        b=normalize(rows,'15m',asof,220)
        self.assertEqual(a,b)

    def test_future_close_not_accepted(self):
        rows=synth('1h',261)
        rows[-1][6]+=1
        with self.assertRaisesRegex(ValueError,'KLINE_CLOSE_TIMESTAMP'):
            normalize(rows,'1h',ASOF,250)

    def test_ao_math(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        s=ao_series(rows)
        self.assertAlmostEqual(s[-1],sum((x['h']+x['l'])/2 for x in rows[-5:])/5-
                               sum((x['h']+x['l'])/2 for x in rows[-34:])/34)

    def test_adx_wilder_bounds_length(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        s=adx_series(rows)
        self.assertEqual(len(s),len(rows))
        self.assertTrue(0<=s[-1]['adx']<=100)
        self.assertTrue(0<=s[-1]['plus_di']<=100)
        self.assertTrue(0<=s[-1]['minus_di']<=100)

    def test_bbwp_warmup_no_fake_percentiles(self):
        rows=normalize(synth('1d',331),'1d',ASOF,330)
        bb=bbwp_series(rows)
        self.assertIsNone(bb[200][0])
        self.assertIsNotNone(bb[-1][0]);self.assertTrue(0<=bb[-1][0]<=100)

    def test_pivots_need_two_right_bars(self):
        r=normalize(synth('1h',261),'1h',ASOF,260)
        hs,ls=pivots(r)
        self.assertTrue(all(x['confirmed_at']>x['pivot_at'] for x in hs+ls))
        self.assertTrue(all(x['confirmed_at']<=r[-1]['close_ts'] for x in hs+ls))

    def test_max_risk_including_costs(self):
        x=risk_sizing(140,78000,77000,75000,79000)
        self.assertIsNotNone(x)
        self.assertLessEqual(x['maximum_combined_estimated_loss_usdt'],.7+.0001)
        self.assertLessEqual(x['maximum_combined_notional_usdt'],140.0001)
        self.assertGreater(x['qty_per_leg_btc'],0)

    def test_zero_qty_blocks_no_fake_entry(self):
        self.assertIsNone(risk_sizing(.01,79000,77000,75000,80000))

    def test_missing_one_timeframe_fails_closed(self):
        data=history(); del data['1w']
        result=generate_plan(data,ASOF)
        self.assertEqual(result['bias'],'UNKNOWN');self.assertFalse(result['entries'])

    def test_unconfirmed_confluence_returns_wait(self):
        data=history()
        r=generate_plan(data,ASOF)
        if r['bias'].startswith('SCENARIO'):
            self.assertEqual(len(r['entries']),2)
            self.assertIn('NONE:',r['execution'])
        else:
            self.assertFalse(r['entries'])
        self.assertEqual(r['trade_authority'],'NONE')

    def test_synthetic_long_two_entries_bounded(self):
        r=generate_plan(history(slope=.02),ASOF)
        self.assertEqual(r['bias'],'SCENARIO_LONG')
        self.assertEqual(len(r['entries']),2)
        self.assertEqual(len(r['targets']),2)
        self.assertLessEqual(r['risk']['maximum_combined_estimated_loss_usdt'],.7001)
        self.assertTrue(all(x['conditional_not_executable'] for x in r['entries']))
        self.assertLess(r['invalidation']['hard_stop_both_legs'],r['entries'][1]['entry_zone_center'])

    def test_synthetic_short_two_entries_bounded(self):
        r=history(slope=-.1)
        forced_daily={'ao':-100,'ao_previous':-70,'adx':25,'adx_previous':22,
                      'plus_di':10,'minus_di':30,'bbwp':55,'bbwp_previous':30,
                      'bbwp_signal':20,'closed_at':'synthetic'}
        forced_weekly={'ao':9000,'ao_previous':9500,'adx':25,'adx_previous':26,
                       'plus_di':20,'minus_di':18,'bbwp':48,'bbwp_previous':60,
                       'bbwp_signal':50,'closed_at':'synthetic'}
        levels={'resistances':[{'price':98.0,'confirmed_at':1,'timeframe':'1h'},
                                {'price':98.6,'confirmed_at':1,'timeframe':'1h'}],
                'supports':[{'price':96.0,'confirmed_at':1,'timeframe':'1h'},
                            {'price':95.0,'confirmed_at':1,'timeframe':'4h'}]}
        with patch('igod_daily_plan.core.read_indicators',side_effect=[forced_daily,forced_weekly]), \
             patch('igod_daily_plan.core.support_resistance',return_value=levels):
            plan=generate_plan(r,ASOF)
        self.assertEqual(plan['bias'],'SCENARIO_SHORT')
        self.assertEqual(len(plan['entries']),2)
        self.assertGreater(plan['entries'][1]['entry_zone_center'],plan['entries'][0]['entry_zone_center'])
        self.assertLess(plan['targets'][0]['structural_take_profit'],plan['targets'][1]['structural_take_profit'])
        self.assertTrue(plan['invalidation']['stop_is_not_placed_on_exchange'])
        self.assertLessEqual(plan['risk']['maximum_combined_estimated_loss_usdt'],.7001)

    def test_structural_levels_need_confirmations(self):
        rs=normalize(synth('1h',261),'1h',ASOF,260)
        levels=support_resistance({'1h':rs},reference=rs[-1]['c'],min_gap=.02)
        self.assertTrue(all(x['price']>rs[-1]['c'] for x in levels['resistances']))
        self.assertTrue(all(x['price']<rs[-1]['c'] for x in levels['supports']))

    def test_daily_chart_provisional_bar_cannot_influence_plan(self):
        rows=history()
        original=generate_plan(rows,ASOF)
        altered=copy.deepcopy(rows)
        # Only the currently open 1d candle changes: it must be ignored.
        altered['1d'][-1][2]=str(float(altered['1d'][-1][2])+100)
        # Source digest of full inputs may change, but indicators/bias must not.
        new=generate_plan(altered,ASOF)
        self.assertEqual(original['bias'],new['bias'])
        self.assertEqual(original.get('indicators'),new.get('indicators'))

    def test_public_market_only_whitelisted_get(self):
        from igod_daily_plan.market import public_klines,BASE
        class Response:
            status_code=200
            def json(self):return synth('1d',HISTORIES['1d']+1)
        class Session:
            trust_env=False
            auth=None
            def __init__(self):self.headers={};self.calls=[]
            def get(self,url,**kwargs):
                self.calls.append((url,kwargs))
                return Response()
        sess=Session()
        rows=public_klines('1d',ASOF,HISTORIES['1d'],session=sess)
        self.assertEqual(len(rows),HISTORIES['1d'])
        self.assertEqual(sess.calls[0][0],BASE)
        self.assertEqual(sess.calls[0][1]['params']['symbol'],'BTCUSDT')
        self.assertFalse(sess.calls[0][1]['allow_redirects'])
        self.assertIsNone(sess.auth)

    def test_public_http_failure_does_not_fallback(self):
        from igod_daily_plan.market import public_klines
        class Response:
            status_code=451
        class Session:
            trust_env=False
            auth=None
            headers={}
            def get(self,*a,**kw):return Response()
        with self.assertRaisesRegex(ValueError,'PUBLIC_HTTP_451'):
            public_klines('1d',ASOF,HISTORIES['1d'],session=Session())

    def test_invalid_public_timeframe_denied(self):
        from igod_daily_plan.market import public_klines
        with self.assertRaisesRegex(ValueError,'PUBLIC_REQUEST_DENIED'):
            public_klines('1m',ASOF,330)

    def test_no_live_mutation_imports(self):
        import inspect, igod_daily_plan.core as module
        s=inspect.getsource(module)
        for forbidden in ('place_order(', 'flash_close_position(', 'requests.post(', 'set_leverage('):
            self.assertNotIn(forbidden,s)

if __name__=='__main__':unittest.main()
