"""Frozen-result diagnostics/renderer, no parameter reselection from TEST."""
import json
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
from . import core,engine,mlrsi,run,comparators
from .data import ART,HOUR,load,stamp,digest
from .evaluate import native_scalar
from .safety import audit
from .spec import BASE_SHA,CUTOFF,FUSIONS
from .telegram import render


def write(name,value):
    (ART/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=native_scalar)+'\n',encoding='utf-8',newline='\n')


def paired(a,b):
    if not np.array_equal(a['times'],b['times']): raise ValueError('PAIRED_TIMES_DIFFER')
    weeks=a['times']//(7*24*HOUR);labels=np.unique(weeks)
    delta=np.log1p(a['returns'])-np.log1p(b['returns'])
    sums=np.array([delta[weeks==w].sum() for w in labels]);counts=np.array([(weeks==w).sum() for w in labels])
    rng=np.random.default_rng(773);values=[]
    for _ in range(500):
        ids=rng.integers(0,len(sums),len(sums));values.append(float(sums[ids].sum()/counts[ids].sum()*365.25*24))
    return dict(annual_log_growth_difference=float(delta.mean()*365.25*24),ci95=np.quantile(values,[.025,.975]).tolist(),
                repetitions=500,seed=773,blocks='paired7day calendar',multiplicity_corrected=False)


def extra_walk_forward(bars,funding,result):
    output={}
    for year in range(2022,2027):
        end=min(stamp(f'{year+1}-01-01T00:00:00Z'),stamp(CUTOFF)); split=stamp(f'{year}-01-01T00:00:00Z')
        train=bars[bars[:,0]+HOUR<=split]; sample=bars[bars[:,0]+HOUR<=end]
        base=core.base_features(train);base.update(mlrsi.features(train));cache={}
        periods=dict(TRAIN=(run.SPLITS['TRAIN'][0],stamp(f'{year-1}-01-01T00:00:00Z')),
                     VALIDATION=(stamp(f'{year-1}-01-01T00:00:00Z'),split))
        trial_base=core.base_features(sample);trial_base.update(mlrsi.features(sample));trial_cache={}
        output[str(year)]={}
        for side in (1,-1):
            parent=run.make_candidate(result['annual_walk_forward'][str(year)][str(side)]['selected'])
            configs=[replace(parent,name=f'F{i:02}',fusion=x) for i,x in enumerate(FUSIONS)]
            rows=[run.development(train,base,cache,p,side,funding[funding[:,0]<split],periods) for p in configs]
            eligible=[r for r in rows if run.eligibility(r)]
            chosen=sorted(eligible or rows,key=lambda r:(-run.score(r),len(r['parameters']['fusion']),r['parameters']['name']))[0]
            p=run.make_candidate(chosen['parameters'])
            output[str(year)][str(side)]=dict(selected=asdict(p),eligible=bool(eligible),selection_cutoff=split,
                metrics=run.run_candidate(sample,trial_base,trial_cache,p,side,funding,split,end)['metrics'])
        print('BITMAN_FUSION_WALK_FORWARD',year,flush=True)
    return output


def diagnostics():
    result=json.loads((ART/'test_results.json').read_text(encoding='utf-8'))
    lock=json.loads((ART/'selection_lock.json').read_text())
    if run.code_hash()!=lock['code_sha256']: raise ValueError('FROZEN_CODE_CHANGED')
    bars,funding=load();base=core.base_features(bars);base.update(mlrsi.features(bars));cache={}
    years={str(y):(max(stamp(f'{y}-01-01T00:00:00Z'),run.SPLITS['ALL'][0]),
                   min(stamp(f'{y+1}-01-01T00:00:00Z'),run.SPLITS['ALL'][1])) for y in range(2020,2027)}
    comparisons=comparators.evaluate(bars,base,funding)
    comparison_curves=comparators.evaluate(bars,base,funding,{'TEST':run.SPLITS['TEST']},keep_returns=True)
    annual_controls=comparators.evaluate(bars,base,funding,years)
    extra={}
    htf=comparators.v8_closed_state(bars)
    for key,r in result['configurations'].items():
        p=run.make_candidate(r['parameters']);side=1 if key.endswith('_1') else -1
        trial=run.run_candidate(bars,base,cache,p,side,funding,*run.SPLITS['TEST'])
        if trial['metrics']!=r['splits']['TEST']: raise ValueError('PRIMARY_STRATEGY_RESULT_CHANGED')
        year_metrics={y:run.run_candidate(bars,base,cache,p,side,funding,a,b)['metrics'] for y,(a,b) in years.items()}
        aligned=[t for t in trial['trades'] if htf[max(0,np.searchsorted(bars[:,0],t['signal_time'])-1)]==(1 if side==1 else 0)]
        extra[key]=dict(yearly=year_metrics,
            paired_vs_V8=paired(trial,comparison_curves['V8']['TEST']),
            paired_vs_EMA=paired(trial,comparison_curves['EMA_10_55']['TEST']),
            confirmed_4h_alignment=dict(n=len(aligned),expectancy=float(np.mean([t['net_return'] for t in aligned])) if aligned else None),
            mean_risk_distance_pct=float(np.mean([t['risk_distance']/t['entry_fill'] for t in trial['trades']])) if trial['trades'] else None)
    wf_path=ART/'fusion_walk_forward.json'
    if wf_path.exists(): wf=json.loads(wf_path.read_text())
    else: wf=extra_walk_forward(bars,funding,result);write('fusion_walk_forward.json',wf)
    corrected=dict(reason='V8 must carry lastCLOSED4H close>SMA200, not current1H price>SMA4H.',
        original_raw_result_sha256=digest(ART/'test_results.json'),primary_classic_fusion_unchanged=True,
        original_v8_diagnostic_deprecated=result['comparators']['V8'],
        canonical_comparators=comparisons,yearly_comparators=annual_controls,
        note='Original frozen test_results.json preserved. Canonical comparison tables use this correction.')
    write('comparison_correction.json',corrected);write('supplemental_diagnostics.json',extra)
    write('safety_audit.json',audit())
    build_report(result,lock,corrected,extra,wf)


def pct(v,d=2): return 'NA' if v is None else f'{v*100:+.{d}f}%'
def ratio(v): return 'NA' if v is None else f'{v:.3f}'


def metric_table(rows):
    lines=['| System/split | Return | CAGR | Sharpe | Sortino | MaxDD | PF | Expectancy | n | Win | Payoff |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,m in rows:
        lines.append(f"| {name} | {pct(m['total_return'])} | {pct(m['cagr'])} | {ratio(m['sharpe'])} | {ratio(m['sortino'])} | {pct(m['max_dd'])} | {ratio(m['profit_factor'])} | {pct(m['expectancy'],4)} | {m['trades']} | {pct(m['win_rate'])} | {ratio(m['payoff_ratio'])} |")
    return lines


def samples():
    base=dict(entry=82150.,atr=600.,stop_atr=2.,trail_atr=2.,trend={'1H':'BULL','4H':'BULL','1D':'BULL'},
        cloud='BULLISH',adx=28.4,adx_arrow='↑',momentum='POSITIVE ↑',bbwp=40.,bbwp_state='EXPANSION',
        structure='BREAKOUT + RETEST',vpoc='SUPPORTING (hourly histogram proxy)',mlrsi='UNAVAILABLE',
        conditions={'TREND':True,'RSI CLOUD':True,'MOMENTUM':True,'DMI':True})
    result={}
    for state in ('LONG','SHORT','SETUP_FORMING','WAIT','BLOCKED','DATA_RISK_ERROR'):
        snap=dict(base,state=state)
        if state=='SHORT': snap.update(trend={'1H':'BEAR','4H':'BEAR','1D':'BEAR'},cloud='BEARISH',momentum='NEGATIVE ↓')
        if state=='SETUP_FORMING': snap['conditions']={**base['conditions'],'STRUCTURE CONFIRMATION':False,'BBWP EXPANSION':False}
        if state=='WAIT': snap['conditions']={k:False for k in base['conditions']}
        if state=='BLOCKED': snap['reason']='Research gate not satisfied; no promotion.'
        if state=='DATA_RISK_ERROR': snap.update(adx=None,bbwp=None,trend={},conditions={},cloud='UNKNOWN',momentum='UNKNOWN',structure='UNKNOWN',vpoc='UNAVAILABLE')
        result[state]=render(snap)
    return result


def build_report(result,lock,corrected,extra,wf):
    lines=['# I-GOD BITMAN STRATEGY — PHASE2', '', '**REJECT**', '',
        f'BASE SHA: `{BASE_SHA}`. Branch: `bitman-phase2-research`. Cutoff: `{CUTOFF}`.',
        'PUBLIC BITMAN-INSPIRED PROXY. Not OFFICIAL BITMAN. Research/SHADOW only; trade_authority=false.',
        '`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`', '',
        '## Design and source limits', '',
        'Public sources, authorship boundaries and inaccessible original-video content: [SOURCES.md](SOURCES.md). '
        'Both cloud presets are publicly documented by a proxy author, not certified as Bitman private defaults. '
        'Preset publications in2026 may themselves reflect historical optimization. No exact private-indicator parity claimed.',
        '18 one-factor CLASSIC candidates; per-side TRAIN/VALIDATION selection, top3 parents then up to14 active parameter neighbors. '
        'CLASSIC frozen before eight FUSION additions. See preregistered.json and both lock files. '
        'No cartesian grid, no revised55/60/65 selection, no Early Breakout entry, no A–G SHORT reuse.',
        'The2024..cutoff TEST is chronological but reused OOS, not virgin data. '
        'No live/forward validation claim. Selection never reads its TEST metrics.', '',
        '## Exact frozen rules', '',
        'All features use closed1H; context4H/1D available only after their actual close. '
        'EMA10/55, close-source Wilder RSI cloud. Entry once on full-setup false→true, next1H open adverse slippage. '
        'No1m/5m trigger.15m timing omitted deliberately: no incremental evidence.',
        'LONG CLASSIC: EMA10>EMA55 on1H; RSI500 EMA36>EMA84; AO>0; +DI>-DI and ADX14>=20. '
        'No higher-TF alignment/slope/midpoint/structure/BBWP hard gate in the selected LONG.',
        'SHORT diagnostic fallback: EMA10<EMA55 on1H; RSI89 EMA9<EMA21 and RSI<50; AO<0; -DI>+DI and ADX14>=20. '
        '**No SHORT candidate was development-eligible**; no SHORT promotion even if a later row looks attractive.',
        'FUSION selected F00_CLASSIC for BOTH sides. No addition won the frozen development criterion. '
        'Identical FUSION/CLASSIC results are the same experiment, not independent confirmation.',
        'Initial2ATR14 stop frozen at signal; TP1 +1R30%, economic BE including realized TP/fees/slip, TP2 +2R30%, '
        '40% runner trailing2 frozen ATR. Tighten after close for next bar. Opposite EMA/cloud closes next open; max168h. '
        'Stop/gap first; ambiguous newBE beforeTP2. One position, no pyramid/reverse,1x nominal at entry, fixed qty.',
        'Base fee5bps/fill + adverse slip2bps (stop5); stress fee6/slip5/stop10. Partial fees correctly weighted. '
        'Historical signed funding on remaining qty; bar-open mark proxy, pre-order boundary holdings. '
        'Not exact Bitunix fills/margin/liquidation. Hourly close MTM DD, not worst intrabar DD. '
        'Exposure can drift after entry; no higher leverage used to rescue results.', '',
        '## TRAIN / VALIDATION / TEST / ALL', '',
        'TRAIN2020–2021; VALIDATION2022–2023; TEST2024–2026-10-15T19:00Z. Warmup2019-10 onward. '
        'Splits force flat; prior bars may warm indicators. PF/payoff NA if denominator absent.', '']
    rows=[]
    for key,r in result['configurations'].items():
        for split,m in r['splits'].items(): rows.append((key+'/'+split,m))
    lines+=metric_table(rows)
    lines+=['','## One-position combined portfolio','',
        'LONG and SHORT are also tested separately above. Combined never sums two1x portfolios; '
        'it permits at most one side and no same-bar reverse. SHORT remains rejected.', '']
    lines+=metric_table([(family+'/'+split,m) for family in ('classic_combined','fusion_combined') for split,m in result[family].items()])
    lines+=['','## Canonical comparators, common data/costs/accounting','',
        '**V8 correction:** raw first-pass artifact used current1H price versus4H SMA. '
        'The canonical adapter carries LAST CLOSED4H close>SMA200 until next4H close. '
        'Original raw JSON is retained; comparison_correction.json records both. '
        'CLASSIC/FUSION selections, trades and metrics are unchanged.',
        'D60 retains its frozen entry/exit definition but uses this common ledger and later cutoff. '
        'It is not a reranking or replacement of the old archived +68.76% result. '
        'Buy&hold funded and underlying/no-funding are distinct controls.', '']
    lines+=metric_table([(name+'/'+split,m) for name,rows in corrected['canonical_comparators'].items() for split,m in rows.items()])
    lines+=['','## Year by year, fixed global selections','',
        'Independent flat annual runs; do not multiply these to reconstruct a continuous TEST curve.', '']
    lines+=metric_table([(key+'/'+year,m) for key,values in extra.items() if key.startswith('classic') for year,m in values['yearly'].items()])
    lines+=['','## Annual anchored walk-forward','',
        'Each year: anchored TRAIN from2020 through year-2, VALIDATION=year-1, evaluate only year. '
        'Each fold physically truncates selection inputs before its year. Earlier global TEST years may become past '
        'fold training data; global frozen selection never changes. FUSION adds only the same locked eight sets '
        'after that fold CLASSIC freezes. This is historical simulation, not FORWARD_LIVE.', '']
    lines+=metric_table([(f'CLASSIC/{year}/{side}/{r["selected"]["name"]}',r['metrics']) for year,sides in result['annual_walk_forward'].items() for side,r in sides.items()])
    lines+=metric_table([(f'FUSION/{year}/{side}/{r["selected"]["name"]}',r['metrics']) for year,sides in wf.items() for side,r in sides.items()])
    lines+=['','##2026 regime diagnostics — no fitting to repair2026','',
        '| Year | Hours | Median ATR% | Median ADX | ADX rising | Sign persistence | Lag1 return correlation | False breakout3h | Breakout n | Median RSI89 | Taker>=60% | BBWP expansion |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for year,r in result['regime'].items():
        lines.append(f"| {year} | {r['hours']} | {pct(r['median_atr_pct'])} | {ratio(r['median_adx'])} | {pct(r['fraction_adx_rising'])} | {pct(r['sign_persistence'])} | {ratio(r['lag1_return_correlation'])} | {pct(r['false_breakout_3h'])} | {r['breakout_n']} | {ratio(r['median_cloud_rsi'])} | {pct(r['fraction_taker_ge60'])} | {pct(r['fraction_bbwp_expansion'])} |")
    lines+=['','Taker>=60 is a fixed descriptive statistic, NEVER a newly selected FUSION rule. '
        'False breakouts use only subsequently observed three-hour outcomes for diagnosis, not signal generation. '
        'Sign persistence/correlation are descriptive; these do not identify causal indicator failure.', '',
        '###2026 strategy/control results','']
    lines+=metric_table([(key,values['yearly']['2026']) for key,values in extra.items() if key.startswith('classic')]+
                        [(name,values['2026']) for name,values in corrected['yearly_comparators'].items()])
    for key,r in result['configurations'].items():
        if key.startswith('fusion'): continue
        d=r['diagnostics'];p=r['parameters'];m=r['splits']['TEST']
        fraction=sum(x['metrics']['expectancy']>0 for x in d['neighbors'])/len(d['neighbors'])
        lines+=['',f'## Robustness {key}', '',f'Positive TEST neighbor expectancy: {fraction:.1%}; no neighbor replaces the selected parent.', '']
        lines+=metric_table([(n['parameters']['name'],n['metrics']) for n in d['neighbors']])
        lines+=['','### Ablation','',
            'Removing TREND/RSI also removes that dependency from the opposite exit; no hidden retained entry block. '
            'STRUCTURE/VOLATILITY absent in selected parents: their removal is a no-op, NOT stability evidence.', '']
        lines+=metric_table([(name,row) for name,row in d['ablation'].items()])
        lines+=['','### Costs / concentration','']
        lines+=metric_table([('BASE',m),('STRESS6/5/10',d['stress'])]+[(f'fee{fee}bps+slip2',v) for fee,v in d['fee_sensitivity'].items()])
        for n,label in ((1,'without_best'),(3,'without_best3')):
            rem=d[label];lines.append(f"Without best{n}: return {pct(rem['total_return'])}; expectancy {pct(rem['expectancy'],4)}; DD {pct(rem['max_dd'])}. Fixed removed intervals; no opportunistic re-entry.")
        lines+=['Weekly expectancy bootstrap: `'+json.dumps(d['bootstrap'])+'`.',
                'Paired annual log-growth versus canonical V8: `'+json.dumps(extra[key]['paired_vs_V8'])+'`.',
                'No multiplicity-corrected significance claimed.','',
                '### Regime/volatility cohorts','',
                'Primary raw BULL/BEAR cohort used current price versus closed4H SMA (proxy, not confirmed4H regime). '
                'Canonical confirmed4H aligned entry cohort: `'+json.dumps(extra[key]['confirmed_4h_alignment'])+'`. '
                'RANGE=ADX<20; HIGH/LOW volatility cutpoint comes from TRAIN median ATR%. '
                'Raw conditional cohorts are descriptive; never report a compressed-time Sharpe as a strategy.',
                '```json',json.dumps(d['cohorts'],indent=2),'```']
    lines+=['','## FUSION incremental ablation, NOT a new TEST selection','',
        'Eight fixed additions, including unchangedCLASSIC. MLRSI is the frozen LOW29/PINE_PARITY_V4 '
        'mathematical module on this perpetual series; exact TradingView parity NOT proven. '
        'Calendar-year sessions bootstrap at most3200 preceding known1H bars; no gate anchored at end of unseen TEST. '
        'This is not the old LOW27 study or the actual spot forward journal.',
        'MLRSI veto allows GREEN/NEUTRAL LONG and RED/NEUTRAL SHORT; opposite/UNKNOWN blocked. '
        'RESUME variant requires the frozen event on the same bar; never the sole underlying setup. '
        'FLOW uses signed pressure around50% and improvement against prior3h, not60%. '
        'VPOC is prior72h typical-price histogram24 bins: explicitly a proxy, not true volume-at-price.', '']
    lines+=metric_table([(f'{side}/{name}',m) for side,rows in result['fusion_ablation'].items() for name,m in rows.items()])
    lines+=['','The development lock selected NONE of these additions. Any better TEST row is exploratory only; '
        'it cannot be installed/promoted by choosing from this table. No old component demonstrated a sufficiently '
        'robust incremental improvement under the predeclared selection. Early Breakout excluded (NO EDGE); '
        'wedges/triangles are causal diagnostics only, not claimed entry edge.', '',
        '## Promotion gates','']
    for key,r in result['configurations'].items(): lines += [f'- {key}: **{r["classification"]}**; `'+json.dumps(r['gates'])+'`.']
    lines+=['','Negative TEST expectancy is a hard REJECT. Adequate sample does not rescue PF/Sharpe/DD failures. '
        'Neither CLASSIC nor FUSION meets the required gates. Do not repair by retuning2026 or adding leverage.', '',
        '## Implementation / reproduction / forward','',
        'See README.md. Raw strategy snapshot and locks immutable. Serialization-only receipt records the initial '
        'np.int64 export failure. The re-export normalized NumPy scalars only; no selection, rule or cost changed. '
        'Canonical comparator correction is separate and cannot alter BITMAN signals.',
        'No deployment and no Telegram bot/poller added. Pure renderer; optional file-fed SHADOW observer uses '
        'separate storage and never receives account clients. Historical run never launches it. '
        'Forward adapter reuses the accepted read-only evaluator without modifying it or historical backtests.',
        'Actual Railway journals remain pending. Future imported evidence can contradict/strengthen hypotheses '
        'but cannot relabel this frozen negative TEST as profitable. Any new candidate needs a new preregistration.', '',
        '## Exact Telegram samples — ILLUSTRATIVE, NOT real observed setups','']
    messages=samples()
    for state in ('LONG','SHORT','SETUP_FORMING','WAIT','BLOCKED','DATA_RISK_ERROR'):
        lines += [f'### {state}','```text',messages[state],'```','']
    write('telegram_samples.json',messages)
    lines+=['## Safety','',
        'V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI MATH UNCHANGED. '
        'ML RSI RECOVERY UNCHANGED. EARLY BREAKOUT UNCHANGED. MANUAL COPILOT UNCHANGED.',
        '**NO MERGE. NO REAL ORDER. NO RAILWAY DEPLOY.**', '', '**Final classification: REJECT.**']
    (Path(__file__).parent/'BITMAN_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__': diagnostics()
