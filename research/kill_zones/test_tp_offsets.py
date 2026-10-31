"""Fixed offset causality and LONG/SHORT direction; no calibration."""
import unittest
try:
    import numpy as np
except ModuleNotFoundError as error:
    if error.name!='numpy':raise
    raise unittest.SkipTest('Dedicated Kill Zones CI installs scientific dependencies') from None
from .tp_offsets import targets,OFFSETS,lock_payload
class OffsetTests(unittest.TestCase):
    def row(self,side=1):
        return dict(model='NY_EXTREME_TIMES_TP100',side=side,entry_at=100,
                    signal_close=10000.,full_target=11000. if side==1 else 9000.,signal_index=0)
    def test_exactly_four_offsets(self):self.assertEqual(len(OFFSETS),4)
    def test_long_target_below_geometry(self):
        self.assertTrue(all(t['target']<11000 for t in targets([self.row()],np.array([200.]))))
    def test_short_target_above_geometry(self):
        self.assertTrue(all(t['target']>9000 for t in targets([self.row(-1)],np.array([200.]))))
    def test_atr_tenth_exact(self):
        rows={r['model']:r for r in targets([self.row()],np.array([200.]))}
        self.assertEqual(rows['NY_EXTREME_TIMES_ATR010']['target'],10980.)
    def test_atr_quarter_exact(self):
        rows={r['model']:r for r in targets([self.row(-1)],np.array([200.]))}
        self.assertEqual(rows['NY_EXTREME_TIMES_ATR025']['target'],9050.)
    def test_bps_exact(self):
        rows={r['model']:r for r in targets([self.row()],np.array([200.]))}
        self.assertEqual(rows['NY_EXTREME_TIMES_BPS5']['target'],10995.)
        self.assertEqual(rows['NY_EXTREME_TIMES_BPS10']['target'],10990.)
    def test_prefix_future_atr_not_consumed(self):
        a=targets([self.row()],np.array([200.]))
        b=targets([self.row()],np.array([200.,999999.]))
        self.assertEqual(a,b)
    def test_inputs_not_mutated(self):
        row=self.row();before=dict(row);targets([row],np.array([200.]));self.assertEqual(row,before)
    def test_no_other_models_expanded(self):
        row=dict(self.row(),model='NY_BOX_ENDS_TP100')
        self.assertEqual(targets([row],np.array([200.])),[])
    def test_missing_atr_never_invented(self):
        rows=targets([self.row()],np.array([np.nan]))
        self.assertEqual(len(rows),2);self.assertTrue(all(r['offset_kind']=='BPS' for r in rows))
if __name__=='__main__':unittest.main()
