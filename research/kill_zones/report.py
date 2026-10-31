"""Standalone scientific charts and readable research report, not runtime."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import numpy as np
from .data import HOUR,iso
from .models import levels
PRIMARY='NY_EXTREME_TIMES_TP95'
def fmt(value,digits=3):
    return 'UNKNOWN' if value is None else f'{value:.{digits}f}' if isinstance(value,(int,float)) else str(value)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
        ['| '+' | '.join(map(str,row))+' |' for row in rows])
def plots(out,trades,hourly,portfolios,metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    from matplotlib.patches import Rectangle
    plt.rcParams.update({'svg.hashsalt':'KILL_ZONES_V0','font.size':9})
    folder=out/'figures';folder.mkdir(exist_ok=True)
    primary=[r for r in trades if r['model']==PRIMARY and r['split']=='EVALUATION']
    examples=[]
    for side in (1,-1):
        for winner in (True,False):
            row=next((r for r in primary if r['side']==side and (r['net_r']>0)==winner),None)
            if row is None:continue
            z=row['boxes'];start=z['asia']['start']-2*HOUR;end=row['exit_at']+2*HOUR
            bars=hourly[(hourly[:,0]>=start)&(hourly[:,0]<=end)]
            dt=lambda t:datetime.fromtimestamp(t/1000,timezone.utc)
            dates=[dt(x) for x in bars[:,0]]
            fig,ax=plt.subplots(figsize=(13,6))
            for b in bars:
                x=md.date2num(dt(b[0]+HOUR));color='#16803c' if b[4]>=b[1] else '#be123c'
                ax.vlines(x,b[3],b[2],color=color,lw=.9)
                ax.add_patch(Rectangle((x-.013,min(b[1],b[4])),.026,max(abs(b[4]-b[1]),.01),facecolor=color,edgecolor=color))
            for key,color in (('asia','#bfdbfe'),('london','#ddd6fe')):
                box=z[key];x=md.date2num(dt(box['start']));w=(box['end']-box['start'])/(24*HOUR)
                ax.add_patch(Rectangle((x,box['low']),w,box['high']-box['low'],facecolor=color,alpha=.45,edgecolor='#666'))
                ax.text(x,box['high'],key.upper(),fontsize=9)
            times=np.linspace(z['asia']['end'],end,150)
            values=np.array([levels(z,row['geometry'],t) for t in times])
            ax.plot([dt(t) for t in times],values[:,0],color='#0369a1',label='Frozen resistance diagonal')
            ax.plot([dt(t) for t in times],values[:,1],color='#7c3aed',label='Frozen support diagonal')
            s=row['side'];which=0 if s==1 else 1
            ax.plot([dt(t) for t in times],values[:,which]+s*z['width'],color='#999',ls=':',alpha=.6,label='Parallel copy (illustrative)')
            for name,value,col in (('Entry',row['entry_price'],'#111'),('Stop',row['stop'],'#dc2626'),('Frozen TP95',row['target'],'#15803d')):
                ax.axhline(value,color=col,ls='--',label=f'{name}: {value:,.2f}')
            ax.scatter([dt(row['signal_at'])],[row['signal_close']],marker='o',s=55,color='#d97706',zorder=6,label='1H close confirms; entry next open')
            ax.scatter([dt(row['exit_at'])],[row['exit_price']],marker='x',s=70,color='#111',zorder=7,label=row['reason'])
            ax.set_title(f'Objective first {"profitable" if winner else "losing"} {"LONG" if s==1 else "SHORT"} evaluation trade | {row["date"]} | net {row["net_r"]:.3f} R\nBTCUSDT BINANCE USD-M | research approximation, video parity NOT PROVEN')
            ax.set_ylabel('USDT');ax.xaxis.set_major_formatter(md.DateFormatter('%m-%d %H:%M',tz=timezone.utc))
            ax.set_xlabel('UTC — candle plotted at close; 5m execution, hourly display');ax.grid(alpha=.2);ax.legend(loc='best',fontsize=8)
            fig.autofmt_xdate();fig.tight_layout()
            name=f'{"long" if side==1 else "short"}_{"winner" if winner else "loser"}'
            for suffix in ('svg','png'):fig.savefig(folder/(name+'.'+suffix),dpi=135,metadata={'Date':None} if suffix=='svg' else {})
            plt.close(fig)
            examples.append(dict(file='figures/'+name+'.png',date=row['date'],side='LONG' if side==1 else 'SHORT',
                available_at=iso(row['signal_at']),entry_at=iso(row['entry_at']),exit_at=iso(row['exit_at']),
                entry=row['entry_price'],stop=row['stop'],target=row['target'],net_r=row['net_r'],reason=row['reason']))
    fig,axes=plt.subplots(1,2,figsize=(13,4.5))
    p=portfolios.get(PRIMARY+'|EVALUATION',{}).get('curve',[])
    if p:axes[0].plot([datetime.fromtimestamp(x[0]/1000,timezone.utc) for x in p],[x[1] for x in p],lw=1)
    axes[0].set_title('Primary paper equity — 1% risk, <=1x notional');axes[0].set_ylabel('USDT; initial 10,000');axes[0].grid(alpha=.2)
    axes[1].hist([r['net_r'] for r in primary],bins=25,color='#475569');axes[1].axvline(0,color='#be123c')
    axes[1].set_title('Primary evaluation distribution');axes[1].set_xlabel('Net R after fees, slippage and funding proxy')
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(folder/'equity_distribution.png',dpi=135);plt.close(fig)
    return examples
def write(out,result,trades,hourly,portfolios):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    examples=plots(out,trades,hourly,portfolios,result['cells'])
    result['examples']=examples
    cells=result['cells'];primary=cells[PRIMARY]
    lines=['# I-GOD Kill Zones — research V0', '',
      '**'+result['conclusion']+'**. PAPER / SHADOW ONLY. TRADE AUTHORITY: NONE.', '',
      '## What was tested and what was not', '',
      'The original private Descript/Telegram links could not be opened. No transcript or diagonal anchor was independently viewed. '
      'The owner segment map is recorded in source_audit.json. **EXACT VIDEO DIAGONAL / PROJECTION PARITY: NOT PROVEN.** '
      'This result applies to two explicit geometry approximations, not a verified reproduction of the video. No quotations invented.',
      '', 'Protocol was committed before outcome computation: '+result['predeclared_commit']+'. '
      'The full specification and code/data lock are included. No parameter selection or rule change after evaluation.',
      '', '## Data and temporal separation', '',
      table(['Field','Value'],[[k,str(result['data'][k])] for k in ('venue','symbol','first_open','last_close','rows_5m','rows_1h','funding_rows','bars_sha256','hourly_sha256','funding_sha256')]),
      '', 'No kline gaps or duplicates: '+str(len(result['data']['gaps']))+' gap intervals. Complete-hour aggregation only. '
      'All 74 archive ZIPs are individually verified against official CHECKSUM files (manifest lists every URL/hash).',
      '', '**NO VIRGIN HOLDOUT.** 2024 development, 2025 validation, Jan–Sep 2026 chronological evaluation; '
      '2023 Sep–Dec is warmup. Price history has appeared in earlier research. 48h boundary embargo; 24h maximum holding; '
      'one position per model. This is historical research, not prospectively observed performance.',
      '', '## Causal mechanics and ambiguities', '',
      'Asia [20:00,00:00), previous local date; London [02:00,05:00). Primary IANA New York; fixed UTC−4 is a separate comparator. '
      'On spring DST Sunday London contains 2 physical hours. No fabricated hourly bar. Session highs/lows are frozen after London closes.',
      '', 'EXTREME_TIMES joins same-side extrema at their first hourly close timestamps; BOX_ENDS joins those prices at session endpoints. '
      'RANGE uses horizontal combined high/low. Only a fully closed hourly crossing confirms; a wick does not. '
      'Crossed/degenerate channels cannot confirm. A diagonal drifting across unchanged price is retained and flagged, not filtered after seeing outcomes.',
      '', 'Parallel-copy target = diagonal value at confirmation ± frozen combined range width, or measured horizontal range for RANGE. '
      'TP95 freezes 95% of the signal-close-to-target distance. This is an explicitly unverified translation convention. '
      'Stop is the opposite frozen range edge; entry next real hour open with adverse slippage; no repainting or future pivots.',
      '', '## Costs and execution realism', '',
      'Base: 0.06% commission plus 0.05% adverse slippage EACH leg; stress: 0.06% plus 0.10% EACH leg. '
      'All target exits pay taker costs too. These are assumptions, not verified fee-tier or Bitunix execution.',
      '', 'Funding uses real archived signed rates and timestamps, with last CLOSED 5m trade price as a settlement-mark proxy. '
      'Raw funding timestamps are preserved; observed offsets reach '+str(result['data']['funding_max_offset_ms'])+'ms. '
      'There is one record per expected 8h bin and no funding-bin gap. Rates are not interpolated. '
      'Exact-at-entry favorable funding credits are excluded. Exact settlement marks and future live funding remain unknown.',
      '', '5m stop/target collisions resolve stop-first. Stop gaps fill at worse open; target gaps give no favorable price improvement. '
      'MAE/MFE are conservative lower bounds from completed pre-exit bars plus exit fill; unknown exit-bar peaks are not counted. '
      'Drawdown uses 5m-close mark-to-market and realized exits, not only closed winners. Paper sizing includes stop cost reserve, capped at 1x notional.',
      '', '## All twelve predeclared variants', '',
      table(['Model','Split','n','Win %','Mean net R','95% block CI','PF','TP %','Net %','DD %','Stress mean R','Classification'],
       [[model,sp,m['n'],fmt(100*m['win_rate'],1) if m['n'] else '-',fmt(m['mean_net_r']),
         '['+', '.join(fmt(x) for x in m['ci95'])+']',fmt(m.get('profit_factor')),fmt(100*m.get('target_hit_rate',0),1),
         fmt(m.get('net_return_pct'),2),fmt(m.get('mtm_drawdown_pct'),2),
         fmt(cells[model]['stress'][sp].get('mean_net_r')),cells[model]['classification'] if sp=='EVALUATION' else 'NOT A SELECTION STAGE']
        for model in cells for sp,m in cells[model]['metrics'].items()]),
      '', 'Net % and drawdown are on the explicitly sized unlevered paper account, not an account-return promise.',
      '', '## Incremental diagonal value vs matched horizontal range baseline', '',
      'Paired daily net-R differences include zero-trade dates. Circular moving bootstrap: 14 calendar days, 5000 draws, fixed seed. '
      'The familywise interval is 99.5833% (twelve-cell Bonferroni). It is descriptive with dependent trials, not a proof of causality.',
      '',table(['Model','Daily R difference','95% CI','Familywise CI'],
        [[k,fmt(v['paired']['mean_daily_r_difference']),str([round(x,4) for x in v['paired']['ci95']]),
          str([round(x,4) for x in v['paired']['familywise_ci']])] for k,v in cells.items()]),
      '', '## Primary candidate — distribution, costs and failures', '',
      table(['Metric','Evaluation'],[[k,fmt(primary['metrics']['EVALUATION'].get(k),4)] for k in
        ('n','long','short','mean_gross_r','mean_net_r','median_net_r','p10_net_r','p90_net_r','profit_factor',
         'target_hit_rate','ambiguous','mean_mae_r','mean_mfe_r','mean_duration_hours','exposure_fraction',
         'gross_pnl_usdt','commissions_usdt','slippage_usdt','funding_proxy_usdt','net_pnl_usdt','ex_best1_mean_r','ex_best3_mean_r')]),
      '', 'Gross PnL uses simulated fills (already includes slippage); net subtracts commissions and adds signed funding. '
      'The separate slippage total is diagnostic and is not deducted twice. Adverse outcomes are never manually removed.',
      '', '![Equity and outcome distribution](figures/equity_distribution.png)', '',
      '## Long/short, temporal stability and best-event sensitivity', '',
      table(['Model','Slice','n','Mean net R','Median','PF'],
        [[k,sp,m['n'],fmt(m['mean_net_r']),fmt(m.get('median_net_r')),fmt(m.get('profit_factor'))]
         for k,v in cells.items() for sp,m in v['stability'].items()]),
      '',table(['Model','Ex best 1 mean R','Ex best 3 mean R','Line-drift-only trades','Evaluation ambiguous exits'],
        [[k,fmt(v['metrics']['EVALUATION'].get('ex_best1_mean_r')),fmt(v['metrics']['EVALUATION'].get('ex_best3_mean_r')),
          v['line_drift_count'],v['metrics']['EVALUATION'].get('ambiguous',0)] for k,v in cells.items()]),
      '', '## Frozen indicator complementarity — descriptive ablations only', '',
      'Only the predeclared primary geometry/clock/target is filtered. AO slope is direction/momentum; '
      'ADX slope is strength only and DMI supplies side. Existing formulas are imported read-only from frozen code. '
      'Konkorde remains KONKORDE_PROXY; **EXACT BITMAN KONKORDE PARITY: NOT PROVEN**. '
      'Higher-timeframe features use only already closed 4H/1D bars and are descriptive, not new fitted conditions.',
      '',table(['Filter','Split','Trades','Removed vs ALL','Mean net R','95% CI','PF'],
        [[k,sp,m['n'],result['ablations']['ALL'][sp]['n']-m['n'],fmt(m['mean_net_r']),
          str([round(x,3) if x is not None else None for x in m['ci95']]),fmt(m.get('profit_factor'))]
         for k,v in result['ablations'].items() for sp,m in v.items()]),
      '', '**ML RSI: UNAVAILABLE FOR INCREMENTAL EVALUATION.** The real confirmed export covers October 2026, after this cutoff. '
      'No historical ML RSI was reconstructed, no classical RSI substitution and no fabricated confirmed events. '
      'No result here establishes incremental confirmed ML RSI value.',
      '', '## Rejections and coverage', '',
      table(['Reason','Count'],sorted(result['rejections'].items())),'',
      'Session construction diagnostics: '+json.dumps(result['session_rejections'],sort_keys=True)+'. '
      'Counts aggregate variants and are not independent trading days. All raw candidates, fills and rejected reasons are retained locally; '
      'versioned trades.csv contains every completed trade, including losers.',
      '', '## Objective examples — winners AND losers', '',
      'Chosen by first chronological evaluation trade in each primary LONG/SHORT × profitable/losing cell. '
      'Never used to tune rules. Available_at is the completed 1H close; entry uses the subsequent open (same boundary timestamp, after close).',
      '',table(['UTC confirmation','Side','Entry','Stop','TP','Net R','Exit'],
        [[x['available_at'],x['side'],fmt(x['entry'],2),fmt(x['stop'],2),fmt(x['target'],2),fmt(x['net_r']),x['reason']] for x in examples])]
    for x in examples:lines.extend(['',f'![{x["side"]} {x["date"]}]({x["file"]})'])
    lines.extend(['', '## Limitations and decision', '',
      'Classification criteria were fixed before outcomes: PROMISING needs positive evaluation CI, validation/stress/half-year/ex-best-3 stability, '
      'adequate LONG/SHORT counts and corrected paired improvement vs RANGE. NO EDGE is a nonpositive net mean with PF≤1 or a nonpositive upper CI; '
      'otherwise INCONCLUSIVE (n<30 always insufficient). All cells are shown; no best geometry/clock/target is selected.',
      '', '**'+result['conclusion']+'**. The exact video rule remains untested until visual anchors/translation are available. '
      'No runtime, Guardian V2, V8, ML RSI, operability, weekly V1, Railway or Telegram changes. '
      'No strategy activation or orders. Any continuation requires a new forward research protocol and independent review.',
      '', 'Reproduce: install research/kill_zones/requirements.txt; '
      'python -m research.kill_zones.data --download --cache research/cache/kill_zones_public; '
      'python -m research.kill_zones.study run --cache research/cache/kill_zones_public. '
      'Use the published lock; do not overwrite it to fit altered inputs.'])
    (out/'KILL_ZONES_RESEARCH_V0.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
