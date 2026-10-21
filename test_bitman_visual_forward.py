"""Offline synthetic contracts; no independent TradingView export is fabricated."""
import ast
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest
try:
    import numpy as np
    from bitman_manual.frozen import indicators
    from research.bitman_visual_forward import formulas,compare,design,snapshot,ledger_contract as ledger,reference
except ModuleNotFoundError as error:
    if error.name in ('numpy','requests'):raise unittest.SkipTest('Dedicated visual research workflow installs dependencies') from error
    raise

ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'research/bitman_visual_forward'
HOUR=design.HOUR
BASE=reference.BASE

def bars(n=240):
    t=np.arange(n)*HOUR+1792454400000
    c=100+np.arange(n)*.01+np.sin(np.arange(n)/7)
    o=np.r_[c[0],c[:-1]]
    return np.column_stack((t,o,np.maximum(o,c)+.5,np.minimum(o,c)-.5,c))

def source_snapshot(side=1):
    t=1800057600000;t=t//(24*HOUR)*(24*HOUR)
    return dict(candle_open_ms=t,available_at=t+HOUR,observed_at=t+HOUR+2500,activation_at=t-HOUR,
        venue='BINANCE_USDM_PERPETUAL',h4_available_at=t,d1_available_at=t,
        ao=3.5*side,ao_previous=3*side,ao_previous2=4*side,
        ao_slope=.5*side,ao_slope_previous=-side,ao_slope_previous2=-side,atr=2.,
        h4_ao=10*side,d1_ao=30*side,h4_regime=side,signal_close=100.,
        prior_high3=99. if side==1 else 101.,prior_low3=101. if side==-1 else 99.,
        prior_high6=103.,prior_low6=97.,adx=25.,adx_slope=-1.,adx_slope_previous=2.,
        di_plus=30.,di_minus=20.,fe=.4,fe_previous=.5)

def csv_fixture(mutate=None,profile='FROZEN_DEFINITION_V0'):
    a=bars();f=formulas.calculate(a);rows=[]
    columns={k:k for k in compare.KEYS+formulas.SERIES}
    for i,row in enumerate(a):
        item=dict(open_ms=int(row[0]),close_ms=int(row[0]+HOUR),closed=1,seed_start_ms=int(a[0,0]),
            open=row[1],high=row[2],low=row[3],close=row[4])
        item.update({k:float(v[i]) if np.isfinite(v[i]) else '' for k,v in f.items()})
        rows.append(item)
    if mutate:mutate(rows)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(columns),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);raw=stream.getvalue().encode()
    meta=dict(csv_sha256=compare.sha(raw),profile=profile,timeframe_minutes=60,timestamp_unit='UNIX_MILLISECONDS',
        venue='UNKNOWN',venue_verified=False,ticker_id=None,exported_at_ms=int(a[-1,0]+2*HOUR),columns=columns,
        pine_source_sha256=compare.sha((PACKAGE/'pine/visual_export_v0.pine').read_bytes().replace(b'\r\n',b'\n')))
    return raw,meta,a

class FormulaTests(unittest.TestCase):
    def test_same_math_as_frozen_without_inventing_volume(self):
        a=bars();out=formulas.calculate(a)
        fixture=np.column_stack((a,np.ones((len(a),2))))
        expected=indicators.calculate(fixture)
        for key in ('ao','ao_slope','atr','di_plus','di_minus','adx','adx_slope'):
            np.testing.assert_array_equal(out[key],expected[key])

    def test_rma_initialization_unknown_first_dm(self):
        a=bars();f=formulas.calculate(a)
        self.assertTrue(np.isnan(f['di_plus'][13]));self.assertTrue(np.isfinite(f['di_plus'][14]))
        self.assertTrue(np.isnan(f['adx'][26]));self.assertTrue(np.isfinite(f['adx'][27]))

    def test_prefix_and_future_perturbation(self):
        a=bars(400);p=formulas.calculate(a[:200]);full=formulas.calculate(a)
        for k in p:np.testing.assert_array_equal(p[k],full[k][:200])
        a[200:,1:]*=2
        future=formulas.calculate(a)
        for k in p:np.testing.assert_array_equal(p[k],future[k][:200])

    def test_gap_and_duplicate_rejected(self):
        for a in (np.delete(bars(),30,axis=0),np.insert(bars(),30,bars()[30],axis=0)):
            with self.assertRaises(ValueError):formulas.calculate(a)

    def test_snapshot_builder_only_closed_prefix(self):
        a=bars(1000);s=snapshot.observation(a,int(a[-3,0]),int(a[-1,0]+HOUR+2000),'BINANCE_USDM_PERPETUAL')
        self.assertLessEqual(s['h4_available_at'],s['available_at'])
        self.assertLessEqual(s['d1_available_at'],s['available_at'])
        self.assertEqual(s['prior_high6'],max(a[-7:-1,2]))
        self.assertEqual(s['source_input_sha256'],hashlib.sha256(a.astype('<f8').tobytes()).hexdigest())
        with self.assertRaises(ValueError):snapshot.observation(a,0,int(a[-1,0]),'BINANCE_USDM_PERPETUAL')
        with self.assertRaises(ValueError):snapshot.observation(a,0,int(a[-1,0]+HOUR),'BINANCE_SPOT')

class ComparisonTests(unittest.TestCase):
    def test_synthetic_formula_agreement_never_claims_real_visual_parity(self):
        raw,meta,a=csv_fixture();r=compare.compare(raw,meta)
        self.assertEqual(r['status'],'FORMULA_MATCH_ON_EXPORTED_OHLC')
        self.assertEqual(r['original_screenshot_parity'],'NOT_PROVEN')

    def test_hash_failure_and_explicit_mapping(self):
        raw,meta,a=csv_fixture()
        with self.assertRaisesRegex(ValueError,'CSV_HASH'):compare.compare(raw+b' ',meta)
        del meta['columns']['open_ms']
        with self.assertRaises(ValueError):compare.compare(raw,meta)

    def test_missing_seed_history_not_hidden_with_warmup_cut(self):
        raw,meta,a=csv_fixture(lambda r:r.pop(0))
        with self.assertRaisesRegex(ValueError,'SEED_HISTORY_MISSING'):compare.compare(raw,meta)

    def test_numeric_and_missing_differences_visible(self):
        raw,meta,a=csv_fixture(lambda r:r[-1].update(adx=999,ao=''))
        result=compare.compare(raw,meta)
        self.assertEqual(result['status'],'FORMULA_DIFFERENCES')
        self.assertEqual(result['series']['adx']['numeric_mismatches'],1)
        self.assertEqual(result['series']['ao']['missing_pattern_differences'],1)

    def test_unconfirmed_final_row_excluded(self):
        raw,meta,a=csv_fixture(lambda r:r[-1].update(closed=0))
        self.assertEqual(compare.compare(raw,meta)['excluded_open_rows'],1)

    def test_open_middle_row_and_future_confirmed_rejected(self):
        raw,meta,a=csv_fixture(lambda r:r[10].update(closed=0))
        with self.assertRaises(ValueError):compare.compare(raw,meta)
        raw,meta,a=csv_fixture();meta['exported_at_ms']=int(a[-1,0])
        with self.assertRaisesRegex(ValueError,'FUTURE_CANDLE'):compare.compare(raw,meta)

    def test_unknown_timezone_does_not_shift_epoch(self):
        raw,meta,a=csv_fixture();meta['chart_timezone']='UNKNOWN'
        self.assertEqual(compare.compare(raw,meta)['first_open_ms'],a[0,0])

    def test_spot_not_equated_to_usdm(self):
        raw,meta,a=csv_fixture();meta.update(venue='BINANCE_SPOT',ticker_id='BINANCE:BTCUSDT',venue_verified=True)
        with self.assertRaisesRegex(ValueError,'CROSS_VENUE'):compare.compare(raw,meta,a)

    def test_usdm_ohlc_equality_requires_attestation(self):
        raw,meta,a=csv_fixture();meta.update(venue='BINANCE_USDM_PERPETUAL',ticker_id='BINANCE:BTCUSDT.P',venue_verified=True)
        self.assertEqual(compare.compare(raw,meta,a)['market_comparison'],'EXACT_OHLC_MATCH')
        a[-1,4]+=.1
        self.assertEqual(compare.compare(raw,meta,a)['market_comparison'],'OHLC_DIFFERENCES')

    def test_original_unknown_inputs_diagnostic_not_proof(self):
        raw,meta,a=csv_fixture(profile='TV_BUILTINS_OR_ORIGINAL')
        self.assertEqual(compare.compare(raw,meta)['status'],'ORIGINAL_OR_NATIVE_SERIES_DIAGNOSTIC_ONLY')

    def test_frozen_exporter_hash_required(self):
        raw,meta,a=csv_fixture();meta['pine_source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'EXPORTER_SOURCE'):compare.compare(raw,meta)

    def test_rounding_tolerance_cannot_hide_changed_event_sign(self):
        diff=compare.series_diff([1e-12],[-1e-12],[0])
        self.assertEqual(diff['numeric_mismatches'],0)
        self.assertEqual(diff['sign_disagreements'],1)
        self.assertFalse(compare.formula_match({'ao_slope':diff}))

    def test_bad_timeframe_units_and_nonfinite_ohlc(self):
        raw,meta,a=csv_fixture();meta['timeframe_minutes']=15
        with self.assertRaises(ValueError):compare.compare(raw,meta)
        raw,meta,a=csv_fixture(lambda r:r[-1].update(high='inf'))
        with self.assertRaises(ValueError):compare.compare(raw,meta)

class DesignTests(unittest.TestCase):
    def test_long_and_short_symmetry(self):
        for side,label in ((1,'LONG'),(-1,'SHORT')):
            s=source_snapshot(side);r=design.assess(s)
            self.assertTrue(r['anchor']);self.assertEqual(r['hypothetical_side'],label)
            self.assertTrue(all(v['selected'] for v in r['candidates'].values()))
            self.assertFalse(r['trade_authority']);self.assertIsNone(r['target'])

    def test_adx_falling_not_direction_or_new_gate(self):
        s=source_snapshot();r=design.assess(s)
        self.assertFalse(r['diagnostics']['adx_turn_up'])
        self.assertTrue(r['candidates']['AO_CONTEXT']['selected'])
        s['adx_slope']=2.;s['adx_slope_previous']=-1.
        self.assertEqual(design.assess(s)['hypothetical_side'],'LONG')

    def test_missing_fe_only_excludes_fe_candidate(self):
        s=source_snapshot();s['fe']=None
        r=design.assess(s);self.assertTrue(r['candidates']['AO_CONTEXT']['selected'])
        self.assertFalse(r['candidates']['AO_FE']['selected'])
        self.assertIn('fe_available',r['candidates']['AO_FE']['missing'])

    def test_opposing_context_retains_ao_reference(self):
        s=source_snapshot();s['h4_ao']=-1.
        r=design.assess(s)
        self.assertTrue(r['candidates']['AO_ONLY']['selected'])
        self.assertFalse(r['candidates']['AO_CONTEXT']['selected'])

    def test_warmup_and_late_recovery_not_forward(self):
        s=source_snapshot();s['activation_at']=s['available_at']
        self.assertEqual(design.assess(s)['observation_class'],'WARMUP_NOT_FORWARD')
        s=source_snapshot();s['observed_at']=s['available_at']+HOUR
        self.assertEqual(design.assess(s)['observation_class'],'LATE_RECOVERY_NOT_PROSPECTIVE')

    def test_open_and_future_context_fail(self):
        for key,value in (('observed_at',source_snapshot()['available_at']-1),
            ('h4_available_at',source_snapshot()['available_at']+4*HOUR)):
            s=source_snapshot();s[key]=value
            with self.assertRaises(ValueError):design.assess(s)

    def test_cooldown_shared_and_inputs_not_modified(self):
        s=source_snapshot();old=copy.deepcopy(s)
        self.assertEqual(design.assess(s,s['available_at']-HOUR)['observation_class'],'COOLDOWN_REFERENCE')
        design.assess(s)
        self.assertEqual(s,old)

    def test_missing_correction_and_zero_not_recovery(self):
        for key in ('ao','ao_slope_previous','ao_slope_previous2'):
            s=source_snapshot();s[key]=0.
            self.assertFalse(design.assess(s)['anchor'])

    def test_no_backdated_next_open_or_uncommitted_fill(self):
        s=source_snapshot();r=design.assess(s);opening=r['next_paper_open_ms']
        self.assertGreater(opening,s['observed_at'])
        with self.assertRaises(ValueError):design.paper_entry(r,s['available_at'],100.,opening,s['observed_at'])
        with self.assertRaises(ValueError):design.paper_entry(r,opening,100.,opening,opening)
        e=design.paper_entry(r,opening,100.,opening+1000,s['observed_at'])
        self.assertEqual(e['target'],100.+2*(100.-r['stop']))
        self.assertEqual(e['entry_recorded_at'],opening+1000)

    def test_invalid_stop_not_replaced_by_atr(self):
        s=source_snapshot();r=design.assess(s)
        e=design.paper_entry(r,r['next_paper_open_ms'],200.,r['next_paper_open_ms'],s['observed_at'])
        self.assertEqual(e['kind'],'ENTRY_INVALIDATED')

    def test_maturity_gap_and_unknown_funding(self):
        s=source_snapshot();r=design.assess(s);e=design.paper_entry(r,r['next_paper_open_ms'],100.,r['next_paper_open_ms'],s['observed_at'])
        times=range(e['entry_time'],e['outcome_due'],design.M5)
        with self.assertRaises(ValueError):design.mature(e,e['outcome_due']-1,times,True)
        self.assertEqual(design.mature(e,e['outcome_due'],list(times)[:-1],True)['kind'],'CENSORED')
        self.assertEqual(design.mature(e,e['outcome_due'],times,False)['net_status'],'UNKNOWN_FUNDING')
        self.assertIsNone(design.costs(e,105.)['BASE']['net_R'])
        self.assertLess(design.costs(e,105.,0.)['STRESS']['net_R'],design.costs(e,105.,0.)['BASE']['net_R'])

    def test_calendar_controls_prefix_invariant_and_not_price_selected(self):
        start=source_snapshot()['available_at'];end=start+90*24*HOUR
        full=design.control_slots(start,end,'FIXED_V0');p=design.control_slots(start,end-30*24*HOUR,'FIXED_V0')
        self.assertEqual(p,[v for v in full if v['available_at']<end-30*24*HOUR])
        self.assertTrue(all(b['available_at']-a['available_at']>=72*HOUR for a,b in zip(full,full[1:])))

    def test_exact_candidate_and_stop_parity_against_pinned_pr33(self):
        module=ast.parse(reference.pinned('features.py').decode())
        names={'gates','raw_events'}
        code=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
        namespace=dict(np=np,frozen=indicators);exec(compile(code,'PINNED_PR33_REFERENCE','exec'),namespace)
        exits=ast.parse(reference.pinned('simulation.py').decode())
        code=ast.Module(body=[n for n in exits.body if isinstance(n,ast.FunctionDef) and n.name=='exit_levels'],type_ignores=[])
        exec(compile(code,'PINNED_PR33_EXITS','exec'),namespace)
        for side in (1,-1):
            for macro in (1,-1):
                for fe_falling in (True,False):
                    s=source_snapshot(side);s['d1_ao']=macro*30
                    if not fe_falling:s['fe']=.6
                    ao=np.array([5,4,3,3.5])*side;slope=ao-indicators.lag(ao)
                    f=dict(ao=ao,ao_slope=slope,h4_ao=np.ones(4)*s['h4_ao'],d1_ao=np.ones(4)*s['d1_ao'],
                        high3=np.ones(4)*s['prior_high3'],low3=np.ones(4)*s['prior_low3'],
                        di_plus=np.ones(4)*30,di_minus=np.ones(4)*20,adx_slope=np.ones(4),
                        fe_slope=np.ones(4)*(s['fe']-s['fe_previous']))
                    frame=np.column_stack((np.arange(4)*HOUR,np.ones((4,6))*100))
                    d=dict(features=f,bars=frame,interval=HOUR)
                    self.assertEqual(namespace['raw_events'](d,'A')[-1],side)
                    old=namespace['gates'](d,3,side,'A');new=design.assess(s)
                    for key in design.CANDIDATES:self.assertEqual(old[key],new['candidates'][key]['selected'])
                    e=design.paper_entry(new,new['next_paper_open_ms'],100.,new['next_paper_open_ms'],s['observed_at'])
                    frozen=namespace['exit_levels'](100.,side,s['atr'],s['prior_low6'],s['prior_high6'],'STRUCTURE_2R')
                    self.assertEqual((e['stop'],e['target'],e['risk']),frozen)

class LedgerTests(unittest.TestCase):
    def rows(self):
        a=ledger.append([],'ACTIVATION','SYNTHETIC_ONLY',0,100,{'scope':'SYNTHETIC_TEST_ONLY'})
        return ledger.append(a,'SIGNAL_ASSESSMENT','SYNTHETIC_ONLY',200,200,{'anchor':True})

    def test_append_dedupe_and_prefix_immutability(self):
        rows=self.rows();before=copy.deepcopy(rows)
        twice=ledger.append(rows,'SIGNAL_ASSESSMENT','SYNTHETIC_ONLY',200,201,{'anchor':True})
        self.assertEqual(rows,twice);self.assertEqual(rows,before)
        third=ledger.append(rows,'OUTCOME_MATURED','SYNTHETIC_ONLY',300,300,{'net_status':'UNKNOWN'})
        self.assertEqual(third[:2],rows);ledger.verify(third)

    def test_conflict_modified_reordered_truncated_chain_rejected(self):
        rows=self.rows()
        with self.assertRaises(ValueError):ledger.append(rows,'SIGNAL_ASSESSMENT','SYNTHETIC_ONLY',200,201,{'anchor':False})
        for mutated in (list(reversed(rows)),rows[1:],copy.deepcopy(rows)):
            if mutated==rows:mutated[0]['payload']['scope']='CHANGED'
            with self.assertRaises(ValueError):ledger.verify(mutated)
        duplicate=rows+[rows[1]]
        with self.assertRaises(ValueError):ledger.verify(duplicate)

    def test_record_id_and_created_at_cannot_be_rewritten(self):
        rows=self.rows();rows[1]['record_id']='a'*64
        row=rows[1];row['record_hash']=ledger.digest({k:v for k,v in row.items() if k!='record_hash'})
        with self.assertRaises(ValueError):ledger.verify(rows)
        with self.assertRaises(ValueError):ledger.append(self.rows(),'CENSORING','SYNTHETIC_ONLY',0,1,{})

    def test_suffix_truncation_needs_independent_checkpoint(self):
        rows=self.rows();tip=ledger.verify(rows)
        ledger.verify(rows,tip)
        with self.assertRaises(ValueError):ledger.verify(rows[:-1],tip)

    def test_unknown_optional_feature_remains_json_serializable(self):
        s=source_snapshot();s['fe']=float('nan')
        result=design.assess(s)
        json.dumps(result,allow_nan=False)
        self.assertIsNone(result['frozen_features']['fe'])

class BoundaryTests(unittest.TestCase):
    def test_new_design_manifest_is_inactive_and_verified(self):
        from research.bitman_visual_forward import protocol
        manifest=protocol.verify()
        self.assertIsNone(manifest['activation_at'])
        self.assertEqual(manifest['status'],'DRAFT_RESEARCH_NOT_AUTHORIZED')
        self.assertEqual(manifest['real_forward_records_created_by_this_pr'],0)
        self.assertEqual(manifest['trade_authority'],'NONE')
        self.assertEqual(manifest['pr33_head'],reference.PR33)
        self.assertEqual(manifest['candidates'],[
            'A:AO_ONLY:STRUCTURE_2R','A:AO_CONTEXT:STRUCTURE_2R','A:AO_FE:STRUCTURE_2R'])

    def test_all_production_files_unchanged(self):
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT).decode().splitlines()
        for name in paths:
            if name.startswith(('research/','.github/','test','tests/')):continue
            original=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
            self.assertEqual((ROOT/name).read_bytes().replace(b'\r\n',b'\n'),original.replace(b'\r\n',b'\n'),name)

    def test_no_runtime_import_or_execution_side_effects(self):
        names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','*.py'],cwd=ROOT).decode().splitlines()
        for name in names:
            if name.startswith(('research/','test','tests/')):continue
            self.assertNotIn('bitman_visual_forward',(ROOT/name).read_text('utf-8'),name)
        for path in PACKAGE.glob('*.py'):
            tree=ast.parse(path.read_text('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse(any(x in (node.module or '') for x in ('guardian_bitunix','trade_guardian','guardian_risk','telegram','v8_executor')))
                if isinstance(node,ast.Attribute):
                    self.assertNotIn(node.attr,('place_order','cancel_order','create_order','set_leverage','post','put','delete','send_message','Thread','Popen','getenv','environ'))
        self.assertNotIn('bitman_entry_lab',subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT).decode())

    def test_pine_is_passive_exporter_not_executed_reference(self):
        text=(PACKAGE/'pine/visual_export_v0.pine').read_text('utf-8')
        for forbidden in ('strategy(','strategy.','alert(','alertcondition(','request.'):
            self.assertNotIn(forbidden,text)
        capture=json.loads((PACKAGE/'capture_reference.json').read_text('utf-8'))
        self.assertFalse(capture['actual_csv_available']);self.assertIsNone(capture['chart_timezone'])
        self.assertEqual(capture['venue'],'UNKNOWN')

    def test_original_results_and_hashes_not_reinterpreted(self):
        saved=json.loads((PACKAGE/'artifacts/pr33_reference_summary.json').read_text('utf-8'))
        self.assertEqual(reference.summary(),saved)
        self.assertEqual(saved['original_classifications'],{'NO EDGE':28,'INCONCLUSIVE':7})
        self.assertEqual([x['reused_evaluation_n'] for x in saved['candidates']],[351,52,35])

    def test_weekly_v1_not_refrozen(self):
        from bitman_weekly_forward import protocol
        protocol.verify()
        self.assertEqual(protocol.EXPECTED_HASH,'d4fe75fce89e8f248123409c293b1114f9af2eb16b8aee5572b40802a54aefe8')

if __name__=='__main__':unittest.main()
