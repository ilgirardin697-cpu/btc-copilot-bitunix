"""Causality / geometry checks, NOT a profitability experiment."""
import ast
import hashlib
import json
import subprocess
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from .chart import svg_chart
from .data import json_text, read_csv, sha
from .model import (Bar, HOUR, Point, Segment, body_cross, boundary, construct,
                    iso, observe, validate)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '9d40020d539033cefb8f01734db8c6a6fdbba2e3'


def fixture(side='UP'):
    """Artificial control prices. Not BTC, not a historical/forward event."""
    day = date(2026, 1, 14)
    start, freeze = boundary(day, 0), boundary(day, 5)
    rows = [Bar(t, D(100), D(102), D(98), D(100))
            for t in range(start - 5 * HOUR, freeze + 15 * HOUR, HOUR)]
    out = []
    for b in rows:
        if start - 4 * HOUR <= b.open_time < start:
            vals = (90, 95, 85, 90) if side == 'UP' else (110, 115, 105, 110)
        elif boundary(day, 2) <= b.open_time < freeze:
            last = b.open_time == freeze - HOUR
            vals = (110, 115 if last else 114, 105, 110) if side == 'UP' else (90, 95, 85 if last else 86, 90)
        elif b.open_time == freeze:
            vals = (118, 122, 117, 121) if side == 'UP' else (82, 83, 78, 79)
        elif b.open_time == freeze + HOUR:
            vals = (121, 122, 99, 100) if side == 'UP' else (79, 101, 78, 100)
        else:
            vals = (100, 102, 98, 100)
        out.append(replace(b, open=D(vals[0]), high=D(vals[1]), low=D(vals[2]), close=D(vals[3])))
    return tuple(out), day, freeze


class GeometryTests(unittest.TestCase):
    def test_clone_up_preserves_both_components(self):
        m = Segment(Point(10, D(85)), Point(18, D(115)))
        c = m.clone(Point(20, D(95)), 'UP')
        self.assertEqual(c, Segment(Point(20, D(95)), Point(28, D(125))))

    def test_clone_down_preserves_both_components(self):
        m = Segment(Point(18, D(85)), Point(10, D(115)))
        c = m.clone(Point(20, D(105)), 'DOWN')
        self.assertEqual(c, Segment(Point(28, D(75)), Point(20, D(105))))

    def test_one_measurement_not_hh_ll(self):
        b, d, t = fixture()
        s = construct(b, d, t)
        self.assertEqual((s.measurement.a.p, s.measurement.b.p), (D(85), D(115)))
        self.assertEqual(s.measurement.a.t, s.lower.low_at)
        self.assertEqual(s.measurement.b.t, s.upper.high_at)
        self.assertFalse(hasattr(s, 'resistance'))
        self.assertFalse(hasattr(s, 'support'))

    def test_line_actual_time_slope_and_reverse_time(self):
        self.assertEqual(Segment(Point(4, D(10)), Point(2, D(20))).at(3), D(15))

    def test_vertical_line_fails(self):
        with self.assertRaisesRegex(ValueError, 'VERTICAL'):
            Segment(Point(2, D(1)), Point(2, D(2))).at(4)

    def test_wrong_side_fails(self):
        with self.assertRaises(ValueError):
            Segment(Point(1, D(1)), Point(2, D(2))).clone(Point(3, D(3)), 'OTHER')

    def test_nested_boxes_not_forced(self):
        b, d, t = fixture()
        b = tuple(replace(x, high=D(110), low=D(80)) if t-3*HOUR <= x.open_time < t else x for x in b)
        r = observe(b, d, t)
        self.assertEqual((r['status'], r['reason']), ('UNAVAILABLE', 'BOX_ORDER_AMBIGUOUS'))

    def test_earliest_extreme_tie(self):
        b, d, t = fixture()
        s = construct(b, d, t)
        self.assertEqual(s.measurement.a.t, boundary(d, 0)-4*HOUR)


class TemporalTests(unittest.TestCase):
    def test_winter_and_summer_utc_boundaries(self):
        self.assertEqual(iso(boundary(date(2026, 1, 14), 5)), '2026-01-14T10:00:00Z')
        self.assertEqual(iso(boundary(date(2026, 9, 2), 5)), '2026-09-02T09:00:00Z')

    def test_nonexistent_dst_hour_rejected(self):
        with self.assertRaisesRegex(ValueError, 'NONEXISTENT'):
            boundary(date(2026, 3, 8), 2)

    def test_ambiguous_dst_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AMBIGUOUS'):
            boundary(date(2026, 11, 1), 1)

    def test_sessions_not_closed(self):
        b, d, t = fixture()
        self.assertEqual(observe(b, d, t-1)['reason'], 'SESSIONS_NOT_CLOSED')

    def test_open_confirmation_candle_ignored(self):
        b, d, t = fixture()
        self.assertIsNone(observe(b, d, t+HOUR-1)['confirmation'])

    def test_long_confirmation_available_only_after_close(self):
        b, d, t = fixture()
        r = observe(b, d, t+HOUR)
        self.assertEqual(r['confirmation']['side'], 'UP')
        self.assertEqual(r['confirmation']['available_at'], t+HOUR)
        self.assertEqual(r['plan']['status'], 'REFERENCE_PLAN')
        self.assertEqual(r['plan']['reference_entry'], D(121))
        self.assertEqual(r['plan']['stop'], D(85))
        self.assertEqual(r['plan']['target'], D(125))

    def test_short_confirmation_next_open_stop_target(self):
        b, d, t = fixture('DOWN')
        r = observe(b, d, t+HOUR)
        self.assertEqual(r['confirmation']['side'], 'DOWN')
        self.assertEqual(r['plan']['status'], 'REFERENCE_PLAN')
        self.assertEqual(r['plan']['reference_entry'], D(79))
        self.assertEqual((r['plan']['stop'], r['plan']['target']), (D(115), D(75)))

    def test_next_open_absent_pending_not_signal_close_fill(self):
        b, d, t = fixture()
        b = tuple(x for x in b if x.open_time < t+HOUR)
        self.assertEqual(observe(b, d, t+HOUR)['plan']['status'], 'ENTRY_PENDING')

    def test_future_high_low_close_cannot_change_plan(self):
        b, d, t = fixture()
        other = tuple(replace(x, high=D('NaN'), low=D(-999), close=D(9999))
                      if x.open_time >= t+HOUR else x for x in b)
        self.assertEqual(json_text(observe(b, d, t+HOUR)), json_text(observe(other, d, t+HOUR)))

    def test_future_append_preserves_confirmed_construction(self):
        b, d, t = fixture()
        prefix = tuple(x for x in b if x.open_time <= t+HOUR)
        a, c = observe(prefix, d, t+HOUR), observe(b, d, t+HOUR)
        self.assertEqual(json_text(a), json_text(c))

    def test_replay_deterministic(self):
        b, d, t = fixture()
        self.assertEqual(json_text(observe(b,d,t+HOUR)), json_text(observe(b,d,t+HOUR)))

    def test_bad_entry_order_rejected_not_target_moved(self):
        b, d, t = fixture()
        b = tuple(replace(x, open=D(130)) if x.open_time == t+HOUR else x for x in b)
        r = observe(b, d, t+HOUR)
        self.assertEqual(r['plan']['status'], 'REJECTED_STOP_TARGET_ORDER')
        self.assertEqual(r['plan']['target'], D(125))

    def test_wick_only_no_confirmation(self):
        self.assertIsNone(body_cross(Bar(0,D(100),D(120),D(90),D(101)),D(110)))

    def test_body_equality_close_no_confirmation(self):
        self.assertIsNone(body_cross(Bar(0,D(100),D(110),D(90),D(105)),D(105)))

    def test_open_equality_and_real_body_cross(self):
        self.assertEqual(body_cross(Bar(0,D(100),D(110),D(90),D(105)),D(100)), 'UP')

    def test_body_already_outside_not_reclassified_as_crossing(self):
        self.assertIsNone(body_cross(Bar(0,D(108),D(120),D(106),D(115)),D(105)))

    def test_no_multiple_confirmations_for_same_day(self):
        b, d, t = fixture()
        self.assertEqual(observe(b,d,t+10*HOUR)['confirmation']['available_at'], t+HOUR)

    def test_incomplete_session_rejected(self):
        b, d, t = fixture()
        # Cut prefix before Asia starts: no interior gap that could hide the cause.
        b = tuple(x for x in b if x.open_time >= boundary(d,0)-3*HOUR)
        self.assertEqual(observe(b,d,t)['reason'], 'SESSION_INCOMPLETE')

    def test_gap_and_duplicate_rejected(self):
        b, d, t = fixture()
        for bad in (b[:2]+b[3:], b[:2]+b[1:]):
            with self.assertRaisesRegex(ValueError,'GAP_OR_DUPLICATE'):
                observe(bad,d,t)

    def test_bad_ohlc_rejected(self):
        with self.assertRaisesRegex(ValueError,'OHLC'):
            validate([Bar(0,D(100),D(90),D(110),D(100))])


class EvidenceAndBoundaryTests(unittest.TestCase):
    def test_public_excerpt_hash_and_hourly_schema(self):
        m = json.loads((HERE/'examples/data_manifest.json').read_text())
        p = HERE/'examples/BTCUSDT_USDM_1h_20260901_03.csv'
        self.assertEqual(sha(p), m['excerpt_sha256'])
        b = read_csv(p)
        self.assertEqual(len(b),72)
        validate(b)
        self.assertEqual(m['venue'], 'BINANCE_USDM_PERPETUAL')

    def test_svg_deterministic_and_valid_both_sides(self):
        for side in ('UP','DOWN'):
            b,d,t = fixture(side)
            r = observe(b,d,t+HOUR)
            s = svg_chart(b,r,'SYNTHETIC CONTROL — NOT BTC')
            self.assertEqual(s,svg_chart(b,r,'SYNTHETIC CONTROL — NOT BTC'))
            ET.fromstring(s)
            self.assertIn('NO PERFORMANCE EVALUATION',s)
            self.assertNotIn('<script',s)
            self.assertNotIn('http://',s.replace('http://www.w3.org/2000/svg',''))

    def test_ambiguous_boxes_still_drawn_without_invented_geometry(self):
        bars = read_csv(HERE/'examples/BTCUSDT_USDM_1h_20260901_03.csv')
        cutoff = boundary(date(2026,9,3),20)
        r = observe(bars,'2026-09-02',cutoff)
        self.assertEqual(r['reason'],'BOX_ORDER_AMBIGUOUS')
        svg = svg_chart(bars,r,'BTCUSDT USD-M geometry only')
        ET.fromstring(svg)
        self.assertIn('No segment',svg.replace('no segment','No segment'))
        self.assertIsNone(r['confirmation'])

    def test_real_confirmation_rejected_target_not_moved(self):
        bars = read_csv(HERE/'examples/BTCUSDT_USDM_1h_20260901_03.csv')
        r = observe(bars,'2026-09-03',boundary(date(2026,9,3),20))
        self.assertEqual(iso(r['confirmation']['available_at']), '2026-09-03T15:00:00Z')
        self.assertEqual(r['plan']['target'],D('79105.30'))
        self.assertEqual(r['plan']['reference_entry'],D('80508.40'))
        self.assertEqual(r['plan']['status'],'REJECTED_STOP_TARGET_ORDER')

    def test_no_network_execution_or_pr40_imports(self):
        allowed={'dataclasses','datetime','decimal','zoneinfo','csv','hashlib','json','pathlib',
                 'html','argparse','io','zipfile'}
        for path in HERE.glob('*.py'):
            if path.name.startswith('test_'):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Import):
                    self.assertTrue(all(a.name.split('.')[0] in allowed for a in node.names),path)
                elif isinstance(node,ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split('.')[0],allowed,path)

    def test_runtime_has_no_consumers_and_all_protected_files_unchanged(self):
        paths = subprocess.check_output(['git','ls-files','*.py'],cwd=ROOT,text=True).splitlines()
        for name in paths:
            if name.startswith(('research/','test_','tests/')):
                continue
            self.assertNotIn('kill_zones_visual_v1',(ROOT/name).read_text(encoding='utf-8'),name)
        # Compare all existing non-research blobs byte-for-byte to the base index.
        changed = subprocess.check_output(['git','diff','--name-only',BASE,'--'],cwd=ROOT,text=True).splitlines()
        self.assertTrue(all(p.startswith(('research/kill_zones_visual_v1/',
                                        '.github/workflows/kill-zones-visual-v1.yml')) for p in changed),changed)


if __name__ == '__main__':
    unittest.main()
