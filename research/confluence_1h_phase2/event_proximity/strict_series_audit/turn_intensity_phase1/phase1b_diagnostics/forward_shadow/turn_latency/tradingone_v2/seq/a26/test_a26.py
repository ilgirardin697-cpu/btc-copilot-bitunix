import ast
from copy import deepcopy
import gzip,hashlib,json,subprocess
from pathlib import Path
from types import SimpleNamespace
import unittest
try:
    import numpy
except ImportError:
    raise unittest.SkipTest("Numerical addendum is mandatory in the dedicated research CI with NumPy installed") from None
from . import run as r
from .member import observe

class AddendumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames,cls.manifest=r.load()
        cls.summary=json.loads((r.HERE/'out/summary.json').read_text('utf-8'))
        cls.pairs=json.loads((r.HERE/'out/paired.json').read_text('utf-8'))

    def test_declared_plan_not_rewritten(self):
        self.assertEqual(hashlib.sha256((r.HERE/'plan.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'a433c6db1c64e7a662bff504e3b191a97eb9bcf2d53e8c52363a4491ce465b39')

    def test_source_bytes_and_attribution_not_claimed_original(self):
        p=json.loads((r.HERE/'plan.json').read_text('utf-8'))
        for long,short in [('BITMAN_AUDITORIA_20261126.md','audit26.md'),('BITMAN_DIRECTO_20261125_IGOD.md','live25.md')]:
            self.assertEqual(hashlib.sha256((r.HERE/'s'/short).read_bytes()).hexdigest(),p['sources'][long]['sha256'])
        self.assertIn('not independent',p['source_grade']);self.assertEqual(p['vidiq_additional_calls'],0)

    def test_original_replay_exact_prefix(self):
        ledger,_,_=r.replay(self.frames,end=r.OLD_END)
        with gzip.open(r.HERE.parent/'out/ledger.gz','rt',encoding='utf-8') as f:expected=[json.loads(x) for x in f]
        self.assertEqual(ledger.rows,expected)

    def test_extended_replay_preserves_previous_records_hash_chain(self):
        with gzip.open(r.HERE/'out/ledger.gz','rt',encoding='utf-8') as f:rows=[json.loads(x) for x in f]
        self.assertTrue(r.Ledger.verify(rows));self.assertEqual(len(rows),2408)
        self.assertEqual(self.summary['old_ledger_records'],1835)

    def test_all_policies_use_identical_entries_sizes_and_stops(self):
        ids={p['id'] for p in self.pairs};self.assertEqual(len(ids),15)
        for id in ids:
            rows=[x for x in self.pairs if x['id']==id]
            self.assertEqual({x['policy'] for x in rows},set(r.POLICIES))
            self.assertEqual(len({(x['entry_at'],x['entry'],x['qty'],x['initial_stop']) for x in rows}),1)

    def test_baseline_same_realized_results_as_original_broker(self):
        rows=[x for x in self.pairs if x['policy']=='BASELINE_ATR' and x['completed']]
        self.assertEqual(len(rows),14);self.assertAlmostEqual(sum(x['net'] for x in rows),-142.84203891028804,places=9)

    def test_stop_updates_never_widen_and_only_next_bar(self):
        for p in self.pairs:
            for u in p['stop_updates']:
                self.assertGreaterEqual(p['side']*(u['new']-u['old']),0)
                self.assertEqual(u['effective_at']%r.M,0)
                self.assertGreater(u['effective_at'],p['entry_at'])

    def test_exit_indicator_cannot_use_own_future_bar(self):
        for p in self.pairs:
            for f in p['fills']:
                if f['reason'] in ('BBWP_TURN_EXIT','KONCORDE_CROSS_EXIT'):
                    h=self.frames['1h'].at(f['at'])
                    self.assertEqual(h['available_at'],f['at']);self.assertEqual(f['window_end'],f['at'])
                    self.assertLess(h['open_time'],f['at'])

    def test_current_open_positions_censored_not_invented_fills(self):
        self.assertIsNotNone(self.summary['simulation']['censored_open'])
        for p in self.pairs:
            if not p['completed']:self.assertGreater(p['remaining'],0)

    def test_sniper_public_price_order_not_a_profit_claim(self):
        s=self.summary['sniper'];self.assertEqual(s['confirmation_close'],59879.23)
        self.assertEqual(s['confirmation_utc'],'2026-11-25T20:00:00+00:00')
        self.assertEqual(s['target_touch_utc'],'2026-11-26T00:13:00+00:00')
        self.assertGreater(s['confirmation'],s['published']);self.assertGreater(s['target_touch'],s['confirmation'])
        self.assertEqual(s['net_pnl'],'NOT_ESTIMABLE')

    def test_sniper_excludes_target_touch_inside_confirmation_candle(self):
        published=self.summary['sniper']['published'];available=self.summary['sniper']['confirmation']
        h=SimpleNamespace(records=[dict(available_at=available,close=59879.23)])
        s=r.sniper({'1h':h},[[available-60000,0,99999,0],[available+60000,0,60900,0]])
        self.assertEqual(s['target_touch'],available+60000)

    def test_weekly_groups_are_magnitude_not_direction_or_signal(self):
        _,s=r.weekly(self.frames)
        self.assertEqual(len(s),12);self.assertEqual({x['group'] for x in s},{'ALL','RISING','NON_RISING','TURN_UP'})
        self.assertEqual(next(x for x in s if x['group']=='ALL' and x['horizon']==1)['n'],213)

    def test_modality_observes_not_filters_entries(self):
        self.assertEqual(sum(self.summary['modalities'].values()),15)
        self.assertEqual(self.summary['modalities'],{'COUNTER_TREND':7,'WITH_TREND':6,'MIXED':2})

    def test_member_angle_no_invented_signal_or_threshold(self):
        context={k:f.at(r.CUT) for k,f in self.frames.items()}
        row=observe(context);self.assertEqual(row['ao_confirmation'],'UNSPECIFIED')
        self.assertEqual(row['koncorde_confirmation'],'UNSPECIFIED');self.assertEqual(row['trade_authority'],'NONE')
        self.assertEqual(row['adx_points_per_hour'],context['1h']['adx_slope'])
        self.assertTrue(all(x['available_at']<=r.CUT for x in row['closed_context'].values()))
        p=json.loads((r.HERE/'member.json').read_text('utf-8'));self.assertIsNone(p['adx']['threshold'])

    def test_no_prior_files_changed_and_no_production_dependencies(self):
        root=Path.cwd();prefix=r.HERE.relative_to(root).as_posix()+'/'
        changes=subprocess.check_output(['git','diff','96a81117b2480d9e6ab8bd2c028f3cc90f6b7ae5','--name-status'],text=True).splitlines()
        for line in changes:
            status,name=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(name.startswith(prefix))
        for p in r.HERE.glob('*.py'):
            for n in ast.walk(ast.parse(p.read_text('utf-8'))):
                if isinstance(n,ast.ImportFrom):self.assertNotIn(n.module,('requests','guardian_bitunix','trade_guardian','v8_executor','telegram'))

if __name__=='__main__':unittest.main()
