"""Render frozen descriptive results; no change to rules/parameters/selection."""
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import subprocess
import numpy as np
from .config import HOUR,TIMEFRAMES,HORIZONS,REENTRY_WINDOWS,REJECTED_PHASE2_SHA,CUTOFF
from .indicators import roll
from .market import verified_cache,aggregate
from .outcomes import measure,summarize
from .study import ART,stamp,split,write
from .config import Config
from .events import analyze
from .safety import audit
from .telegram import render


def pct(x):return 'NA' if x is None else f'{x*100:+.3f}%'


def table(rows):
    lines=['| TF / evento / grupo | n total | maduros | media retorno | mediana | MFE mediana | MAE mediana | +1 antes−1 | ambiguos1% | +2 antes−2 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,s in rows:
        get=lambda key:s.get(key,{}).get('median')
        lines.append(f"| {name} | {s['n_total']} | {s['n_complete']} | {pct(s.get('forward_return',{}).get('mean'))} | {pct(get('forward_return'))} | {pct(get('mfe'))} | {pct(get('mae'))} | {pct(s.get('race_1pct',{}).get('UP_FIRST'))} | {pct(s.get('race_1pct',{}).get('AMBIGUOUS'))} | {pct(s.get('race_2pct',{}).get('UP_FIRST'))} |")
    return lines


def ranks(x):
    unique,inverse,counts=np.unique(x,return_inverse=True,return_counts=True)
    return (np.cumsum(counts)-counts+(counts+1)/2)[inverse]


def association(records,field):
    pairs=[(r[field],r['outcomes']['24']['forward_return']) for r in records if r[field] is not None and r['outcomes']['24']['complete']]
    if len(pairs)<3:return dict(n=len(pairs),spearman=None)
    a=np.asarray(pairs)
    corr=float(np.corrcoef(ranks(a[:,0]),ranks(a[:,1]))[0,1]) if np.std(a[:,0]) and np.std(a[:,1]) else None
    return dict(n=len(pairs),spearman=corr,minimum=float(min(a[:,0])),median=float(np.median(a[:,0])),maximum=float(max(a[:,0])))


def v8_comparison(hourly):
    frame=aggregate(hourly,4*HOUR,stamp(CUTOFF));sma=roll(frame[:,4],200);valid=np.isfinite(sma)
    state=np.where(valid,frame[:,4]>sma,False);observations=[]
    for i in range(1,len(frame)):
        if not valid[i] or not valid[i-1] or state[i]==state[i-1]:continue
        t=int(frame[i,0]+4*HOUR)
        if t<stamp('2020-01-01T00:00:00Z'):continue
        period,end=split(t);kind='V8_LONG_SIGNAL' if state[i] else 'V8_FLAT_SIGNAL'
        observations.append(dict(kind=kind,period=period,timestamp=t,
            outcomes={str(h):measure(hourly,t,frame[i,4],h,end) for h in HORIZONS}))
    summaries={f'{kind}/{p}':{str(h):summarize([r['outcomes'][str(h)] for r in observations if r['kind']==kind and r['period']==p]) for h in HORIZONS}
               for kind in ('V8_LONG_SIGNAL','V8_FLAT_SIGNAL') for p in ('TRAIN','VALIDATION','TEST')}
    raw=subprocess.check_output(['git','show',REJECTED_PHASE2_SHA+':research/bitman/artifacts/comparison_correction.json'])
    archived=json.loads(raw)['canonical_comparators']['V8']
    return dict(fresh_price_event_study=summaries,archived_funded_strategy_metrics=archived,
        source_commit=REJECTED_PHASE2_SHA,
        note='Fresh table is gross event behavior, not funded strategy PnL. Archived net V8 remains an independent mechanical strategy; no replacement proposed.')


def samples():
    s=dict(state='LONG',event='KONKORDE_ENTRY',timeframe='4H',candle_close=stamp('2026-10-15T16:00:00Z'),
        close=82150.,mountain=12.,ma=10.,inside=True,distance_to_zero=10.,separation=2.,strength='NEW_INSIDE',
        reentry=False,reentry_max_bars=3,adx=28.4,adx_slope=.6,di_plus=30.,di_minus=14.,ao=450.,ao_slope=35.,
        bbwp=42.,bbwp_slope=7.,reasons=['Media dentro de montaña positiva','+DI supera -DI','Contexto observacional; NO permiso de entrada'])
    output={'LONG_ENTRY':render(s)}
    output['EXIT']=render(dict(s,state='WAIT',event='KONKORDE_EXIT',inside=False,ma=13.,distance_to_zero=13.,separation=None,strength='UNAVAILABLE',reasons=['Media fuera de la montaña','EXIT no equivale a señal SHORT']))
    output['REENTRY']=render(dict(s,event='KONKORDE_REENTRY',reentry=True))
    output['SETUP_FORMING']=render(dict(s,state='SETUP_FORMING',event=None,di_plus=10.,di_minus=20.,reasons=['Media dentro de montaña positiva','Falta alineación de DI']))
    output['WAIT']=render(dict(s,state='WAIT',event=None,inside=False,ma=13.,distance_to_zero=13.,separation=None,strength='UNAVAILABLE',reasons=['Sin contexto LONG completo']))
    output['BLOCKED_SHORT']=render(dict(s,state='BLOCKED',event=None,mountain=-12.,ma=-10.,di_plus=10.,di_minus=20.,ao=-450.,reasons=['Contexto bajista observado','SHORT_LOGIC_NOT_PROVEN']))
    return output


def main():
    r=json.loads((ART/'results.json').read_text());bins=json.loads((ART/'train_descriptive_bins.json').read_text())
    with gzip.open(ART/'events_and_outcomes.jsonl.gz','rt',encoding='utf-8') as stream:records=[json.loads(line) for line in stream]
    hourly,_=verified_cache();v8=v8_comparison(hourly);write(ART/'v8_comparison.json',v8)
    write(ART/'safety_audit.json',audit());write(ART/'telegram_samples.json',samples())
    extra={tf:{kind:{p:{field:association([x for x in records if x['timeframe']==tf and x['technical_event']==kind and x['period']==p],field) for field in ('distance_to_zero','separation')} for p in ('TRAIN','VALIDATION','TEST')} for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT')} for tf in TIMEFRAMES}
    write(ART/'continuous_associations.json',extra)
    reentry_yearly={tf:{str(y):{str(w):summarize([x['outcomes']['24'] for x in records if x['timeframe']==tf and x['year']==y and x['technical_event']=='KONKORDE_ENTRY' and w in x['reentry_windows']]) for w in REENTRY_WINDOWS} for y in range(2020,2027)} for tf in TIMEFRAMES}
    conditional2026={tf:{kind:{f'{field}/{tag}':summarize([x['outcomes']['24'] for x in records if x['timeframe']==tf and x['year']==2026 and x['technical_event']==kind and x['cohorts'][field]==tag])
        for field in ('zero','separation','adx','di','ao','bbwp') for tag in sorted(set(x['cohorts'][field] for x in records if x['timeframe']==tf))} for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT')} for tf in TIMEFRAMES}
    write(ART/'reentry_by_year.json',reentry_yearly);write(ART/'conditional_2026.json',conditional2026)
    strength={}
    for tf in TIMEFRAMES:
        series=analyze(hourly,tf,stamp(CUTOFF),Config(1));groups={p:{k:[] for k in ('EXPANDING','STABLE','CONTRACTING','NEW_INSIDE')} for p in ('TRAIN','VALIDATION','TEST')}
        for s in series:
            if not s['inside'] or s['candle_close']<stamp('2020-01-01T00:00:00Z'):continue
            period,end=split(s['candle_close']);groups[period][s['strength']].append(measure(hourly,s['candle_close'],s['close'],24,end))
        strength[tf]={p:{k:summarize(values) for k,values in g.items()} for p,g in groups.items()}
    write(ART/'inside_strength.json',strength)
    lines=['# I-GOD BITMAN REAL OBSERVER v0.1','',f'**{r["classification"]}**','',
        'KONKORDE_PROXY · SHADOW ONLY · trade_authority=false.',
        '**EXACT BITMAN KONKORDE PARITY: NOT PROVEN. SHORT_LOGIC_NOT_PROVEN.**',
        'BITMAN Phase2 remains officially **REJECT**, PR #22 / `44029b4768e2b4bc47643bb51bf8a28432623a39`.',
        f'Public-data cutoff: `{CUTOFF}`. Separate branch `bitman-real-observer`, from main `9d0024a45d8e40193162a3864a876ca5ab61d1da`.',
        '`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`','',
        '## Scope and evidence','',
        'This measures post-event price distributions, not a complete strategy, actual fills or account profitability. '
        'All returns below are GROSS/raw BTC orientation, including EXIT. No commission/funding-adjusted PnL is claimed. '
        'No order, sizing, stop, take-profit, leverage or operational direction is changed.',
        'Primary video observations were supplied by the user from direct viewing. Automated video retrieval failed; '
        'no invented transcript or independent viewing claim. The public Pine adapter is the numerical reference, '
        'not the private Micro Finanzas Personales Koncorde 2.0 formula. See [SOURCES.md](SOURCES.md).','',
        '## Exact public proxy formula','',
        '```text','P = OHLC4; T = HLC3',
        'RSI = Wilder RSI14(P), SMA seed of14 changes',
        'MF+ = SUM14(T*V where delta(T)>0); MF- = SUM14(T*V where delta(T)<0)',
        'MFI = 100*MF+/(MF++MF-)',
        'BollOsc = 100*(P-SMA25(P))/(4*populationSTD25(P))',
        'K = 100*(P-lowest21(L))/(highest21(H)-lowest21(L))',
        'Stoch = SMA3(K)',
        'mountain = (RSI+MFI+BollOsc+Stoch/3)/2',
        'MA = EMA15(mountain), alpha2/16, seed first finite value','```','',
        'Brown mountain only; no PVI/NVI hands segmentation. It is a composite trend area with volume through MFI, '
        'not direct institutional order flow. Private formula/normalization/parameters/plotting and TV parity are unknown. '
        'Zero denominators remain unavailable. No backfill or interpolation across gaps. See SOURCES for original public author links and licensing boundary.','',
        '## Events, direction and preregistration','',
        'Inside: `min(0,mountain)<MA<max(0,mountain)`. Touching boundary is outside. '
        'ENTRY outside→inside; EXIT inside→outside. First valid state/gap recovery is context, not a new event. '
        'REENTRY is an ENTRY subset after EXIT within N same-TF bars. All N=1/2/3/5 reported; no winner selected. '
        'Observer requires an explicit N; there is no hidden optimized default.',
        '`distance_to_zero=abs(MA)`; also mountain distance. '
        '`separation=abs(mountain-MA)` while inside, to the outer brown edge; compare consecutive inside bars only. '
        'NEW_INSIDE has no prior inside comparison. Shrinkage is diagnostic, not a new exit rule.',
        'Directional display: LONG = positive mountain + inside + +DI>−DI. '
        'No mandatory ADX magnitude/AO/BBWP gate, no score. This is a descriptive interpretation, not permission to trade '
        'or a statistical validation claim. Other forming positive cases are SETUP_FORMING; other contexts WAIT. '
        'Bearish mountain/DI/AO context is BLOCKED/SHORT_LOGIC_NOT_PROVEN. v0.1 cannot emit SHORT.',
        'ADX smoothing14/DI14; AO SMA5−SMA34 of HL2. BBWP CLOSE/SMA7/popSTD, strictly-lower rank against PRIOR100 widths. '
        'EXPANDING means percentile slope>0; no fitted compression zones. Trend Speed117/2.7/150/100/From start '
        'remains NOT IMPLEMENTED / FORMULA NOT VERIFIED. Production ML RSI LOW29/EMA4 unchanged; LOW27/SMA4 is separate, unimplemented research metadata.',
        'Protocol hash/source fingerprints locked before this study read outcomes. TRAIN2020–2021, VALIDATION2022–2023, '
        'TEST2024–cutoff, reused OOS. No parameter ranking/selection. Near/far and separation tertiles fit TRAIN only; '
        'these groups are not signal thresholds. Public hourly dataset reused from Phase2 only as data, never rules.','',
        '## Outcome methodology','',
        'Each signal is known at actual TF close. Reference is that closed candle price; future complete public1H '
        'candles start at/after the signal timestamp, even for4H/1D events. Thus1h and4h outcomes after a daily '
        'signal do not use unfinished daily data to generate it. Gaps and horizon/split boundaries are censored. '
        'MFE=max(0,max futureHigh/reference−1); MAE=min(0,min futureLow/reference−1). No retrospective intrabar fills.',
        'Independent first +1/−1/+2/−2 hit times are retained. Same hourly candle touching both barriers is AMBIGUOUS, '
        'never an invented winning order; neither is UNRESOLVED. Percentages use mature observations including '
        'ambiguous/unresolved; not invented win probabilities.',
        'Controls: deterministic non-event timestamps in the same UTC month/hour and same trailing24TFbar trend sign. '
        'Matching never inspects future returns. Missing exact matches are excluded from paired inference. '
        'Calendar-week block bootstrap500/seed9821; overlapping events, reused controls, selection exposure and '
        'secondary-table multiplicity limit inference. Primary endpoint is24h matched difference; EXIT is expected '
        'to precede lower BTC returns, not an automatically profitable SHORT.','',
        '## Frozen primary24h matched-control evidence','',
        '| TF | Event | Split | matched n | event−control raw | hypothesis-signed excess | signed CI95 |',
        '|---|---|---|---:|---:|---:|---|']
    for tf,events in r['primary24h_matched'].items():
        for kind,periods in events.items():
            for p,v in periods.items():lines.append(f"| {tf} | {kind} | {p} | {v['n']} | {pct(v['raw_event_minus_control_mean'])} | {pct(v['mean'])} | [{pct(v['ci95'][0])}, {pct(v['ci95'][1])}] |")
    lines+=['','Signed excess flips EXIT only for its stated bearish-outcome hypothesis; the forward-return tables '
            'and independent hit times remain raw BTC orientation. This does NOT implement SHORT.', '',
            '## Forward returns / MFE / MAE across horizons','']
    for tf in TIMEFRAMES:
        lines += [f'### {tf}','']
        lines+=table([(f'{kind}/{p}/{h}h',r['summaries'][tf][kind+'/'+p]['horizons'][str(h)]) for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT') for p in ('TRAIN','VALIDATION','TEST') for h in HORIZONS])
    lines+=['','## Independent first-touch timing, TEST24h','',
            '| TF/event | mature n | hit+1 | first hour median | hit−1 | first hour median | hit+2 | first hour median | hit−2 | first hour median |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for tf in TIMEFRAMES:
        for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            s=r['summaries'][tf][kind+'/TEST']['horizons']['24']
            vals=[s.get(k,{}) for k in ('first_up1_hour','first_down1_hour','first_up2_hour','first_down2_hour')]
            lines.append(f"| {tf}/{kind} | {s['n_complete']} | "+' | '.join(f"{pct(v.get('hit_fraction'))} | {v.get('median_hour_if_hit')}" for v in vals)+' |')
    lines+=['','## REENTRY sensitivity — no selected N','',
            'Subsets of ENTRY, not independent events or additional trades. Do not add their sample counts together. '
            'The observer requires an explicit presentation window; sample messages using3 are illustrative, not a recommendation.','']
    lines+=table([(f'{tf}/N{w}/{p}/24h',r['summaries'][tf][f'KONKORDE_REENTRY_{w}/'+p]['horizons']['24']) for tf in TIMEFRAMES for w in REENTRY_WINDOWS for p in ('TRAIN','VALIDATION','TEST')])
    lines+=['','## Events by year, including2026 separately','']
    lines+=table([(f'{tf}/{y}/{kind}/24h',s) for tf,years in r['yearly'].items() for y,kinds in years.items() for kind,s in kinds.items()])
    lines+=['','### REENTRY by year, mature24h n','',
        '| TF/year | N1 | N2 | N3 | N5 |','|---|---:|---:|---:|---:|']
    for tf,years in reentry_yearly.items():
        for y,windows in years.items():lines.append(f'| {tf}/{y} | '+' | '.join(str(windows[str(w)]['n_complete']) for w in REENTRY_WINDOWS)+' |')
    lines+=['','Full raw outcomes per annual subset: reentry_by_year.json. No window selected.']
    lines+=['','## Zero proximity and separation','',
        'Values are continuous and shown in the live renderer. LOW/MID/HIGH are TRAIN distribution tertiles, '
        'not objectively close-to-zero zones or thresholds for an entry. No profitable cutoff was searched. '
        'EXIT separation is unavailable outside the mountain. Exact TRAIN boundaries:',
        '```json',json.dumps(bins,indent=2),'```',
        'Continuous association with raw24h return is descriptive Spearman, not causal or a trading gate. '
        'Ranges/medians/n/correlations are retained in continuous_associations.json.','']
    for tf in TIMEFRAMES:
        for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            lines += [f'### {tf}/{kind} TEST proximity/separation','']
            lines+=table([(key,s['horizons']['24']) for key,s in r['conditional'][tf][kind].items() if key.startswith('TEST/') and key.split('/')[1] in ('zero','separation')])
    lines+=['','### Separation while MA stays inside','',
        'Every closed inside-state bar is a state observation, not a new signal. These samples overlap heavily '
        'and must not be treated as independent trials. No exit is generated by contraction.','']
    lines+=table([(f'{tf}/{key}/24h',s['horizons']['24']) for tf in TIMEFRAMES for key,s in r['states'][tf]['inside_bar_separation'].items() if key.startswith('TEST/')])
    lines+=['','### Inside separation expanding/contracting, TEST24h','']
    lines+=table([(f'{tf}/{key}',s) for tf in TIMEFRAMES for key,s in strength[tf]['TEST'].items()])
    lines+=['','## ADX / DI / AO / BBWP observational ablation','',
        'ADX favorable=rising, no absolute threshold. DI/AO alignment uses positive for ENTRY and negative for '
        'the EXIT downside hypothesis, without placing a SHORT. BBWP expanding=slope>0. These are marginal '
        'conditional distributions, NOT controlled causal effects or a new entry strategy. All TRAIN/VALIDATION '
        'tables and every horizon remain in results.json; the TEST24h display below cannot select new gates.','']
    for tf in TIMEFRAMES:
        for kind in ('KONKORDE_ENTRY','KONKORDE_EXIT'):
            lines += [f'### {tf}/{kind}','']
            lines+=table([(key,s['horizons']['24']) for key,s in r['conditional'][tf][kind].items() if key.startswith('TEST/') and key.split('/')[1] in ('adx','di','ao','bbwp')])
    lines+=['','###2026 conditional distributions, separate diagnostic','']
    lines+=table([(f'{tf}/{kind}/{key}',s) for tf,kinds in conditional2026.items() for kind,groups in kinds.items() for key,s in groups.items() if s['n_total']])
    lines+=['','## Descriptive LONG episodes','',
        'LONG is a display state, independent of technical ENTRY/REENTRY events. One transition into LONG is '
        'one observation; it is not repeated each bar. No SHORT episode is implemented. AO/ADX/BBWP remain '
        'context rather than mandatory gates. These raw outcomes do not validate an entry permission.','']
    lines+=table([(f'{tf}/{p}/24h',s['horizons']['24']) for tf in TIMEFRAMES for p,s in r['states'][tf]['long_episode'].items()])
    lines+=['','## Comparison with V8 — retain existing evidence','',
        'No replacement is proposed. The archived common-data/cutoff funded V8 TEST remains +66.55%, '
        'Sharpe0.732, MaxDD−32.01%. That is a specified net strategy comparator in Phase2, not a return '
        'claim for this observer. Its original mechanical strategy is unchanged.',
        'A fresh descriptive event table uses transitions of LAST CLOSED4H close>SMA200, with the same '
        'public hourly future measurements. Its gross event returns are not net strategy PnL and are not '
        'directly ranked against funded returns.','']
    lines+=table([(key+'/24h',h['24']) for key,h in v8['fresh_price_event_study'].items()])
    lines+=['','## Legacy signal audit','',
        'See [LEGACY_SIGNAL_AUDIT.md](LEGACY_SIGNAL_AUDIT.md): Guardian KEEP_ACTIVE, V8 KEEP_ACTIVE '
        'in its existing configured state, Copilot KEEP_AS_CONTEXT, unproven ML RSI RESEARCH_ONLY, '
        'negative studies ARCHIVE; selected noisy alerts DISABLE_ALERTS is a proposal only. '
        'No cleanup, deletion, service disablement, variable change or production Telegram alteration performed.','',
        '## Classification and limitations','',
        f'**{r["classification"]}** under the predeclared matched-control/sample/yearly gates. '
        'A positive raw move in a bull market, a favorable secondary cohort or a tiny daily sample is insufficient. '
        'No robust cross-timeframe incremental edge is established. No exact-private-parity or forward validation claim. '
        'Do not reinterpret this conclusion as the private Bitman indicator being disproven: this is the documented proxy only.',
        'Actual forward journals remain inaccessible. Future telemetry is separated by source/version and can '
        'motivate another preregistration; it cannot overwrite frozen results here.','',
        '## Telegram examples — ILLUSTRATIVE ONLY, not sent','']
    for name,text in samples().items():lines += [f'### {name}','```text',text,'```','']
    lines+=['## Tests / safety','',
        'Exact final counts and commands: artifacts/validation.json. No network in this observer or tests; '
        'read-only input files, pure renderer, separate storage, no account client or Telegram poller. '
        'Production file identity and pinned-source fingerprints: artifacts/safety_audit.json.',
        'V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED. '
        'MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.',
        '**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS.**']
    validation_path=ART/'validation.json'
    if validation_path.exists():
        validation=json.loads(validation_path.read_text())
        tests=validation['tests']
        lines+=['',f"Dedicated: {tests['dedicated']['passed']} passed; full repository: {tests['full']['passed']} passed; "
            f"failed: {tests['full']['failed']}; skipped: {tests['full']['skipped']}. "
            f"Guardian: {tests['guardian']['passed']}; V8: {tests['v8']['passed']}; Early Breakout: {tests['early_breakout']['passed']}. "
            f"Replay: {validation['replay']}; compile/safety: PASS."]
    (Path(__file__).parent/'BITMAN_REAL_OBSERVER_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print('BITMAN_REAL_REPORT_READY',r['classification'],flush=True)


if __name__=='__main__':main()
