import unittest
from dataclasses import replace
from igod_paper.vendor.paper_engine_v0 import Bar, Config, run

T = 1761868800  # UTC 5m boundary
C = Config(starting_equity=140,minimum_notional=.01,qty_step=.000001,cooldown_bars=0)

def b(i, price=100, high=101, low=99, signal='WAIT', quality='CAUTION', atr=1):
    return Bar(T+300*i,price,high,low,price,atr,signal,quality)

class PaperOnly(unittest.TestCase):
    def test_entry_is_next_bar_open(self):
        rows=[b(0,signal='LONG_ALLOWED',quality='GOOD'),b(1,high=100.5,low=99.5)]
        x=run(rows,C)
        self.assertEqual(x['open_paper_position']['entry_ts'],T+300)
        self.assertEqual(len(x['closed_trades']),0)
    def test_no_good_no_trade(self):
        self.assertEqual(run([b(0,signal='LONG_ALLOWED'),b(1)],C)['closed_trades'],[])
        self.assertIsNone(run([b(0,signal='LONG_ALLOWED'),b(1)],C)['open_paper_position'])
    def test_both_stop_target_stop_first(self):
        rows=[b(0,signal='LONG_ALLOWED',quality='GOOD'),b(1,high=105,low=95)]
        x=run(rows,C)
        self.assertEqual(x['closed_trades'][0]['reason'],'STOP')
        self.assertLess(x['realized_equity'],140)
    def test_short_stop(self):
        x=run([b(0,signal='SHORT_ALLOWED',quality='GOOD'),b(1,high=106,low=99)],C)
        self.assertEqual(x['closed_trades'][0]['side'],'SHORT')
        self.assertEqual(x['closed_trades'][0]['reason'],'STOP')
    def test_gap_refused(self):
        with self.assertRaises(ValueError):run([b(0),b(2)],C)
    def test_bad_ohlc_refused(self):
        with self.assertRaises(ValueError):run([b(0,high=98)],C)
    def test_unknown_signal_refused(self):
        with self.assertRaises(ValueError):run([b(0,signal='BUY_NOW')],C)
    def test_no_future_signal_used(self):
        x=run([b(0),b(1,signal='LONG_ALLOWED',quality='GOOD')],C)
        self.assertIsNone(x['open_paper_position'])
    def test_equity_cap_and_minimum_notional(self):
        cfg=replace(C,minimum_notional=100000)
        x=run([b(0,signal='LONG_ALLOWED',quality='GOOD'),b(1)],cfg)
        self.assertTrue(any(e['event']=='BLOCKED_MINIMUM_SIZE_OR_RISK' for e in x['events']))
    def test_valid_no_input(self):
        x=run([],C)
        self.assertEqual(x['realized_equity'],140)
        self.assertEqual(x['mode'],'PAPER_ONLY_NO_LIVE_API')

if __name__=='__main__':unittest.main()
