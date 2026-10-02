"""Independent closed-candle scales; levels never confer permission."""
import copy
import unittest
from unittest.mock import patch
try:
    import numpy as np
    import requests
except ImportError:
    raise unittest.SkipTest('Guardian workflow installs dependencies') from None
import test_guardian_ux as ux
from guardian_signals import confirmed_market_levels, direction
from guardian_commands import _levels, _why


class HierarchicalTests(unittest.TestCase):
    def setUp(self):
        _, q, _ = ux.LevelTests.candles()
        self.h = q.copy()
        self.h[:, 0] = np.arange(len(q)) * 3600000
        self.q = q.copy()
        self.now = len(q) * 3600000
        self.q[:, 0] += self.now - len(q) * 900000

    def levels(self, now=None):
        return confirmed_market_levels(self.h, self.q, 105, now_ms=self.now if now is None else now)

    def test_both_scales_strict_reference_sides(self):
        data = self.levels()
        for scale in (data, data['structural']):
            self.assertEqual(scale['support'], 96)
            self.assertEqual(scale['resistance'], 110)
            self.assertLess(scale['support'], 105)
            self.assertGreater(scale['resistance'], 105)

    def test_scales_independent(self):
        before = self.levels()
        self.h[2, 2] = 130
        after = self.levels()
        self.assertEqual(after['resistance'], before['resistance'])
        self.assertEqual(after['support'], before['support'])
        self.assertNotEqual(after['structural']['resistance'], before['structural']['resistance'])

    def test_open_hour_and_quarter_excluded(self):
        expected = self.levels()
        self.h = np.vstack([self.h, [self.now, 105, 1000, 1, 105, 10, 5]])
        self.q = np.vstack([self.q, [self.now, 105, 1000, 1, 105, 10, 5]])
        self.assertEqual(expected, self.levels())

    def test_prefix_invariant_both_scales(self):
        for count in range(5, len(self.q) + 1):
            now = self.q[count - 1, 0] + 900000
            h = self.h[self.h[:, 0] + 3600000 <= now]
            self.assertEqual(confirmed_market_levels(h, self.q[:count], 105, now_ms=now), self.levels(now))

    def test_hour_pivot_confirmed_two_bars_later(self):
        result = self.levels()['structural']
        self.assertEqual(result['resistance_pivot_time'], 2 * 3600000)
        self.assertEqual(result['resistance_confirmed_time'], 5 * 3600000)

    def test_new_hour_pivot_not_available_early(self):
        self.h[-1, 2] = 200
        self.h[-1, 4] = 150
        self.q[-1, 1:5] = [145, 160, 140, 145]
        self.assertIsNone(self.levels()['structural']['resistance'])
        for i in range(2):
            self.h = np.vstack([self.h, [self.now + i * 3600000, 145, 160, 140, 145, 10, 5]])
        # Reference remains a closed quarter; only the hour confirmation changes.
        self.assertIsNone(self.levels(self.now + 3600000)['structural']['resistance'])
        self.assertEqual(self.levels(self.now + 7200000)['structural']['resistance'], 200)

    def test_structural_distances(self):
        result = self.levels()
        s = result['structural']
        self.assertAlmostEqual(s['support_distance_pct'], 9 / 105)
        self.assertAlmostEqual(s['resistance_distance_atr'], 5 / result['atr_1h'])

    def test_micro_label_display_only(self):
        data = dict(bias='WAIT', entry_quality='CAUTION', momentum='NEUTRAL', taker_buy=.5,
                    structure='MIXED', trend4='BULL', trend1='BULL', market_levels=self.levels())
        data['market_levels']['atr_1h'] = 100
        original = copy.deepcopy(data)
        with patch('requests.sessions.Session.request', side_effect=AssertionError('NO HTTP')) as http:
            text = _levels(data, mark=105)
            why = _why(data, mark=105)
        self.assertIn('Muy cercano — nivel local/timing', text)
        self.assertIn('R1 no confirma LONG', why)
        self.assertEqual(data, original)
        self.assertEqual(direction('BULL', 'BULL', 'NEUTRAL', .5, 'MIXED')[0], 'WAIT')
        http.assert_not_called()

    def test_crossing_local_price_cannot_change_direction(self):
        for price in (95, 105, 115):
            self.q[-1, 1:5] = [price, price + 1, price - 1, price]
            self.levels()
            self.assertEqual(direction('BULL', 'BULL', 'NEUTRAL', .5, 'MIXED')[0], 'WAIT')

    def test_full_and_compact_both_scales(self):
        data = dict(bias='WAIT', market_levels=self.levels())
        text = _levels(data)
        for label in ('NIVELES LOCALES 15m', 'NIVELES ESTRUCTURALES 1H', 'R1:', 'S1:', 'R2:', 'S2:', 'Pivote:', 'Confirmado:'):
            self.assertIn(label, text)
        self.assertIn('🏛 1H\n🔴 R2:', _levels(data, compact=True))
        self.assertIn('NO confirma LONG por sí solo', text)

    def test_unavailable_hour_omitted_compact(self):
        self.h[:, 2:4] = [110, 95]
        text = _levels(dict(bias='WAIT', market_levels=self.levels()), compact=True)
        self.assertIn('⚡ 15m', text)
        self.assertNotIn('🏛 1H', text)

    def test_exact_micro_boundary(self):
        data = dict(bias='WAIT', market_levels=dict(status='AVAILABLE', reference_price=100,
                                                  resistance=115, support=None, atr_1h=100))
        self.assertIn('Muy cercano', _levels(data, mark=100))
        data['market_levels']['resistance'] = 115.001
        self.assertNotIn('Muy cercano', _levels(data, mark=100))
