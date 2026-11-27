import ast,copy,gzip,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Numerical research CI requires NumPy') from error
from .maths import Frame,features,validate,fortnight,STEPS,H,M,WEEK
from .engine import Engine,Ledger
from .paper import Paper,exposure,be_level,FEE,SLIP
from .run import replay
from research.confluence_1h.indicators import calculate
from ..profile import adx14

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[9]


def bars(n=310,frame='15m',anchor=0):
    x=np.arange(n)
    c=100+x*.02+np.sin(x/7)
    return np.column_stack((anchor+x*STEPS[frame],c-.1,c+.4,c-.5,c,100+np.sin(x)))


def context(t,ao=1.,accel=-1.,turn=0,pece=-1.,structure=()):
    r=dict(available_at=t,open_time=t-M,open=100.,high=101.,low=99.,close=100.,volume=10.,
        ao=1.,ao_slope=ao,ao_acceleration=accel,ao_turn=turn,pececillos=10.,pececillos_slope=pece,
        adx_slope=1.,adx_turn=0,bbwp=50.,bbwp_slope=-1.,bbwp_turn=0,pececillos_turn=0,
        atr=1.,warmup_complete=True,structure=list(structure),known_low=dict(price=98.),known_high=dict(price=102.))
    return {f:dict(copy.deepcopy(r),frame=f) for f in STEPS}


def plan(side=1,at=0,key='p',atr=1):
    return dict(id=key,side=side,at=at,signal_price=100.,atr=atr,
                pivot=98. if side==1 else 102.,thesis_level=98. if side==1 else 102.)


def candle(t,o=100.,h=100.2,l=99.8,c=100.):
    return [t,o,h,l,c,100.]


class MathAndTime(unittest.TestCase):
    def test_closed_only(self):
        with self.assertRaisesRegex(ValueError,'OPEN_CANDLE'):
            validate(bars(4),'15m',3*M)

    def test_gap_and_duplicate_rejected(self):
        a=bars(10)
        for d in (M,-M):
            b=a.copy();b[5:,0]+=d
            with self.assertRaisesRegex(ValueError,'GAP_OR_DUPLICATE'):
                validate(b,'15m',20*M)

    def test_wrong_grid_rejected(self):
        a=bars(5);a[:,0]+=1
        with self.assertRaisesRegex(ValueError,'TIME_GRID'):
            validate(a,'15m',10*M)

    def test_bad_ohlc_and_nan(self):
        a=bars(5);a[2,3]=200
        with self.assertRaisesRegex(ValueError,'OHLCV_RANGE'):
            validate(a,'15m',10*M)
        a[2,3]=np.nan
        with self.assertRaisesRegex(ValueError,'OHLCV_REQUIRED'):
            validate(a,'15m',10*M)

    def test_reused_ao_koncorde_exact(self):
        a=bars();f=features(a);ref=calculate(a)
        for name,other in [('ao','ao'),('pececillos','minnows'),('tiburones','sharks'),('roja','kon_signal')]:
            np.testing.assert_array_equal(f[name],ref[other])

    def test_adx_exact_reused(self):
        a=bars();f=features(a);expected=adx14(a)
        for name,ref in zip(('adx','plus_di','minus_di'),expected):
            np.testing.assert_array_equal(f[name],ref)

    def test_full_252_warmup_required(self):
        f=features(bars())
        self.assertTrue(np.isnan(f['bbwp'][:265]).all())
        self.assertTrue(np.isfinite(f['bbwp'][265:]).all())

    def test_source_math_prefix_invariance(self):
        a=bars(330);long=features(a);short=features(a[:300])
        for key in short:
            np.testing.assert_array_equal(short[key],long[key][:300])

    def test_acceleration_not_slope_or_direction(self):
        f=features(bars())
        np.testing.assert_allclose(f['ao_acceleration'][2:],np.diff(f['ao_slope'][1:]),equal_nan=True)

    def test_context_never_uses_open_higher_bar(self):
        f=Frame(bars(50,'4h'),'4h',200*H)
        self.assertEqual(f.at(31*H)['open_time'],24*H)
        self.assertEqual(f.at(32*H)['open_time'],28*H)

    def test_stale_context_rejected(self):
        f=Frame(bars(50),'15m',50*M)
        with self.assertRaisesRegex(ValueError,'STALE'):
            f.at(51*M)

    def test_fractal_announced_at_right2_not_pivot(self):
        a=bars(12)
        a[:,2]=102
        a[4,2]=120
        f=Frame(a,'15m',12*M)
        found=[r for r in f.records if r['new_fractals']]
        pivot=next(p for r in found for p in r['new_fractals'] if p['side']==1)
        self.assertEqual(pivot['pivot_at'],4*M)
        self.assertEqual(pivot['known_at'],7*M)
        self.assertIsNone(f.records[6]['known_high'])
        self.assertEqual(f.records[7]['known_high']['price'],120.)

    def test_fractal_future_append_does_not_change_past(self):
        a=bars(50);p=Frame(a[:30],'15m',30*M);full=Frame(a,'15m',50*M)
        self.assertEqual(p.records,full.records[:30])

    def test_2w_anchor_and_closed_pair(self):
        a=bars(8,'1w',4*24*H)
        b=fortnight(a)
        self.assertEqual(len(b),4)
        self.assertEqual(b[0,1],a[0,1]);self.assertEqual(b[0,4],a[1,4])
        self.assertEqual(b[0,5],a[:2,5].sum())
        self.assertEqual(len(fortnight(a[:1])),0)

    def test_insufficient_2w_history_stays_unknown(self):
        a=fortnight(bars(480,'1w',4*24*H))
        f=Frame(a,'2w',int(a[-1,0]+2*WEEK))
        self.assertIsNone(f.records[-1]['bbwp'])
        self.assertFalse(f.records[-1]['warmup_complete'])

    def test_tsa_uses_previous_closed_price_line(self):
        f=Frame(bars(40),'15m',40*M)
        self.assertEqual(f.records[12]['tsa_test_line'],f.records[11]['tsa_trend'])
        self.assertEqual(f.records[12]['fred'],'UNVERIFIED_NOT_A_SIGNAL')


class SequentialMemory(unittest.TestCase):
    def test_prealert_does_not_confirm_without_price(self):
        e=Engine();self.assertEqual(e.consume(context(H)),[])
        self.assertIsNotNone(e.watch[-1]);self.assertEqual(e.states[-1],'WATCH')

    def test_long_short_symmetry(self):
        for side in (-1,1):
            e=Engine()
            e.consume(context(H,ao=-side,accel=side,pece=side))
            c=context(H+M,ao=side,accel=side,turn=side,pece=side,
                      structure=('BREAK_UP' if side==1 else 'BREAK_DOWN',))
            c['1h']['available_at']=H
            plans=e.consume(c)
            self.assertEqual(len(plans),1);self.assertEqual(plans[0]['side'],side)
            self.assertEqual(plans[0]['at'],H+M)

    def test_opposite_break_invalidates(self):
        e=Engine();e.consume(context(H))
        e.consume(context(H+M,structure=('BREAK_UP',)))
        self.assertEqual(e.states[-1],'INVALIDATED')

    def test_watch_expires_and_false_alarm_retained(self):
        e=Engine()
        for i in range(10):
            c=context(H+i*M);c['1h']['available_at']=H
            e.consume(c)
        self.assertEqual(e.states[-1],'EXPIRED')
        self.assertTrue(any(r['kind']=='WATCH' for r in e.log.rows))

    def test_incomplete_invalidates_not_signal(self):
        e=Engine();c=context(H);c['4h']['warmup_complete']=False
        self.assertEqual(e.consume(c),[])
        self.assertIsNone(e.watch[-1])

    def test_future_context_rejected(self):
        c=context(H);c['1w']['available_at']=H+M
        with self.assertRaisesRegex(ValueError,'FUTURE_CONTEXT'):
            Engine().consume(c)

    def test_gap_or_duplicate_rejected(self):
        e=Engine();e.consume(context(H))
        with self.assertRaisesRegex(ValueError,'CLOCK'):
            e.consume(context(H+2*M))

    def test_no_adx_or_bbwp_direction_inference(self):
        c=context(H,ao=0,accel=0,pece=0)
        c['1h'].update(adx_slope=999,bbwp_slope=999)
        e=Engine();self.assertEqual(e.consume(c),[])
        self.assertEqual(e.watch,{1:None,-1:None})

    def test_first_deceleration_only_no_resurrection_same_slope_run(self):
        e=Engine()
        for i in range(24):
            e.consume(context(H+i*M,ao=1.,accel=-1.,pece=-1.))
        watches=[r for r in e.log.rows if r['kind']=='WATCH' and r['side']==-1]
        self.assertEqual(len(watches),1)
        self.assertIsNone(e.watch[-1])

    def test_new_slope_run_rearms_deceleration(self):
        e=Engine();e.consume(context(H,ao=1.,accel=-1.))
        e.consume(context(H+M,ao=-1.,accel=-1.,turn=-1))
        e.consume(context(H+2*M,ao=1.,accel=2.,turn=1))
        e.consume(context(H+3*M,ao=1.,accel=-1.))
        self.assertEqual(len([r for r in e.log.rows if r['kind']=='WATCH' and r['side']==-1]),2)

    def test_snapshot_is_not_mutated_by_future(self):
        e=Engine();e.consume(context(H))
        before=copy.deepcopy(e.log.rows)
        e.consume(context(H+M))
        self.assertEqual(e.log.rows[:len(before)],before)

    def test_replay_determinism(self):
        a=Engine();b=Engine()
        for i in range(8):
            a.consume(context(H+i*M));b.consume(context(H+i*M))
        self.assertEqual(a.log.rows,b.log.rows)

    def test_exhaustion_is_descriptive_not_order(self):
        e=Engine();e.active[-1]=dict(at=0)
        c=context(H);c['1h'].update(ao_turn=1)
        e.consume(c)
        self.assertTrue(any(r['kind']=='EXHAUSTION' for r in e.log.rows))


class SimulatedManagement(unittest.TestCase):
    def test_next_open_and_slippage(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        self.assertEqual(p.position['entry_at'],0)
        self.assertAlmostEqual(p.position['entry'],100*(1+SLIP))
        self.assertEqual(len(p.trades),0)

    def test_stop_cost_budget(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        x=copy.deepcopy(p.position)
        p.step(candle(M,h=100,l=90,c=95),1)
        self.assertAlmostEqual(p.trades[0]['net'],-50,places=8)
        self.assertLess(x['initial_stop'],x['entry'])

    def test_ambiguous_15m_adverse_first(self):
        p=Paper();p.enqueue(plan());p.step(candle(0,h=104,l=95),1)
        self.assertTrue(p.trades[0]['ambiguous'])
        self.assertFalse(p.trades[0]['tp1'])
        self.assertLess(p.trades[0]['net'],0)

    def test_gap_loss_can_exceed_budget(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        p.step(candle(M,o=90,h=91,l=89,c=90),1)
        self.assertLess(p.trades[0]['net'],-50)

    def test_partial_be_and_trail_are_next_bar(self):
        p=Paper();p.enqueue(plan());p.step(candle(0,h=102,l=99,c=101.5),1)
        self.assertTrue(p.position['tp1'])
        self.assertAlmostEqual(p.position['left'],p.position['qty']*.5)
        self.assertGreater(p.position['stop'],p.position['entry'])
        self.assertEqual(p.log.rows[-2]['kind'],'SIM_STOP_UPDATE')
        self.assertEqual(p.log.rows[-2]['effective_at'],M)

    def test_trailing_never_widens(self):
        p=Paper();p.enqueue(plan());p.step(candle(0,h=102,l=99,c=101.5),1)
        old=p.position['stop']
        p.step(candle(M,o=102,h=103,l=101,c=102.5),10)
        if p.position:
            self.assertGreaterEqual(p.position['stop'],old)

    def test_no_pyramiding_or_averaging(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        q=p.position['qty'];p.enqueue(plan(at=M,key='add'))
        p.step(candle(M),1)
        self.assertEqual(p.position['qty'],q)
        self.assertTrue(any(r.get('reason')=='POSITION_OPEN_NO_AVERAGING' for r in p.log.rows))

    def test_stale_plan_has_no_backdated_fill(self):
        p=Paper();p.enqueue(plan(at=-M));p.step(candle(0),1)
        self.assertIsNone(p.position)

    def test_missing_pivot_rejected(self):
        p=Paper();a=plan();a['pivot']=None;p.enqueue(a);p.step(candle(0),1)
        self.assertIsNone(p.position)

    def test_no_leverage_size_rejected_not_resized(self):
        p=Paper();a=plan(atr=.0001);a['pivot']=99.99
        p.enqueue(a);p.step(candle(0),1)
        self.assertIsNone(p.position)
        self.assertTrue(any(r.get('reason')=='LEVERAGE_REQUIRED_REJECTED' for r in p.log.rows))

    def test_close_before_entry_stop_level_rejected(self):
        p=Paper();a=plan();a['pivot']=101
        p.enqueue(a);p.step(candle(0),1)
        self.assertIsNone(p.position)

    def test_short_management(self):
        p=Paper();p.enqueue(plan(-1));p.step(candle(0,h=100.1,l=98,c=98.5),1)
        self.assertTrue(p.position['tp1'])
        self.assertLess(p.position['stop'],p.position['entry'])

    def test_net_be_covers_runner_costs_both_sides(self):
        for side in (-1,1):
            level=be_level(100,side,0.)
            fill=level*(1-side*SLIP)
            net=side*(fill-100)-FEE*(100+fill)
            self.assertAlmostEqual(net,0,places=12)

    def test_drawdown_halt_latched(self):
        p=Paper()
        for i in range(3):
            p.enqueue(plan(at=2*i*M,key=str(i)))
            p.step(candle(2*i*M),1)
            p.step(candle((2*i+1)*M,o=90,h=91,l=89,c=90),1)
        self.assertTrue(p.halted)
        p.enqueue(plan(at=6*M));p.step(candle(6*M),1)
        self.assertTrue(p.halted);self.assertIsNone(p.position)

    def test_restart_and_prefix_equal(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        restarted=copy.deepcopy(p)
        before=copy.deepcopy(p.log.rows)
        for x in (p,restarted):
            x.step(candle(M,h=102,l=99,c=101),1)
            x.step(candle(2*M,o=100,h=101,l=98,c=99),1)
        self.assertEqual(p.log.rows,restarted.log.rows)
        self.assertEqual(p.log.rows[:len(before)],before)

    def test_no_end_of_data_fake_fill(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        self.assertEqual(p.summary()['completed'],0)
        self.assertIsNotNone(p.summary()['censored_open'])

    def test_missing_funding_is_not_zero_futures(self):
        with self.assertRaisesRegex(ValueError,'FUTURES_BLOCKED'):
            Paper(venue='BINANCE_USDM_PERPETUAL')

    def test_no_early_time_exit(self):
        p=Paper();p.enqueue(plan());p.step(candle(0),1)
        for i in range(1,96):
            p.step(candle(i*M),1)
        self.assertEqual(p.trades[0]['exit_reason'],'TIME_EXIT_24H')
        self.assertEqual(p.trades[0]['exit_at'],24*H)

    def test_average_change_keeps_realized_loss_budget(self):
        lots=[dict(qty=.1,entry=100),dict(qty=.1,entry=90)]
        a=exposure(lots,85,1,100,2,realized_net=-1)
        b=exposure(lots,85,1,100,2,realized_net=0)
        self.assertAlmostEqual(a['net_at_stop'],b['net_at_stop']-1)
        self.assertTrue(a['excessive'])
        self.assertEqual(a['average_entry'],95)

    def test_profitable_stop_does_not_invent_capital_loss(self):
        a=exposure([dict(qty=.1,entry=100)],110,1,100,2)
        self.assertEqual(a['aggregate_loss_at_stop'],0)


class IntegrityAndIsolation(unittest.TestCase):
    def test_ledger_tamper_reorder_detected(self):
        l=Ledger();l.add('A',1,x=3);l.add('B',2,x=4)
        self.assertEqual(Ledger.verify(l.rows),l.tip)
        for changed in (copy.deepcopy(l.rows),list(reversed(l.rows))):
            changed[0]['x']=999
            with self.assertRaisesRegex(ValueError,'INVALID'):
                Ledger.verify(changed)

    def test_no_live_io_or_execution_modules(self):
        forbidden={'requests','socket','urllib','subprocess','os','bitunix','telegram','guardian','v8'}
        for p in HERE.glob('*.py'):
            if p.name.startswith('test_'):
                continue
            tree=ast.parse(p.read_text('utf-8'))
            for n in ast.walk(tree):
                if isinstance(n,(ast.Import,ast.ImportFrom)):
                    names=[a.name for a in n.names] if isinstance(n,ast.Import) else [(n.module or '').split('.')[0]]
                    self.assertFalse(forbidden.intersection(names),(p.name,n.lineno))
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
                    self.assertNotIn(n.func.id,{'eval','exec','__import__'})

    def test_previous_sources_bit_for_bit_unchanged(self):
        prefix=HERE.parent.relative_to(ROOT).as_posix()+'/'
        changed=subprocess.check_output(['git','diff','0017faf74f3b157aa5d2789e073a819854108a89','--name-status'],cwd=ROOT,text=True).splitlines()
        self.assertTrue(all(x.startswith('A\t'+prefix+'seq/') or x.startswith('A\t'+prefix+'sequential_market/') for x in changed))

    def test_no_production_consumer(self):
        files=subprocess.check_output(['git','ls-files','--','*.py'],cwd=ROOT,text=True).splitlines()
        for name in files:
            if name.startswith('research/') or Path(name).name.startswith('test_'):
                continue
            text=(ROOT/name).read_text('utf-8-sig')
            self.assertNotIn('tradingone_v2.seq',text,name)
            self.assertNotIn('IGOD_SEQUENTIAL_SHADOW_V0',text,name)

    def test_spec_hash_not_refrozen(self):
        raw=(HERE.parent/'sequential_market/spec.json').read_bytes().replace(b'\r\n',b'\n')
        # Frozen commit daa8673 uses LF; local CRLF receipt hash was a8e01e...
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'13e0564795eee7365a803841740446c66e7cae895b6433a87e56eb4f894a312b')

    def test_actual_reconstruction_prefix_invariance(self):
        data=HERE/'d'
        if not data.exists():
            self.skipTest('Bundled public inputs not installed yet')
        from .run import load,START
        frames,_=load(data)
        full,_,_=replay(frames,end=START+12*H)
        short,_,_=replay(frames,end=START+6*H)
        self.assertEqual(full.rows[:len(short.rows)],short.rows)


if __name__=='__main__':
    unittest.main()
