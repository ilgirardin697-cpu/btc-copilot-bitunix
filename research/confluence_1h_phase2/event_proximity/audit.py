"""Descriptive cases, all fixed-calendar crosses and closed higher frames; no PnL."""
import csv
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from research.confluence_1h.data import stamp
from research.confluence_1h.indicators import calculate
from ..compare import load_market
from ..semantics import HOUR, SERIES, descriptive_rows, events, iso
from .context import context_at
from .detector import detect

HERE=Path(__file__).resolve().parent


def load(name):
    meta=json.loads((HERE/'fixtures'/(name+'.json')).read_text())
    return load_market(HERE/'fixtures'/(name+'.csv.gz'),meta)


def json_write(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def csv_write(path,rows,fields=None):
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf,fieldnames=fields or list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    raw=buf.getvalue().encode('utf-8')
    path.write_bytes(gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw)


def visual_match(a):
    t=stamp('2026-11-15T01:00:00Z');i=int(np.flatnonzero(a[:,0]==t)[0]);f=calculate(a)
    values={name:float(f[key][i]) for name,key in SERIES.items()}
    return dict(evidence_type='OWNER_REPORTED_EXTERNAL_VISUAL_POINT_NOT_CERTIFIED',
        bar_open_utc=iso(t),earliest_available_at=iso(t+HOUR),observed='-40.40',
        values=values,rounded_two_decimals={k:str(Decimal(str(v)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for k,v in values.items()},
        pececillos_absolute_error=float(abs(Decimal(str(values['pececillos']))-Decimal('-40.40'))),
        raw_platform_records=0,complete_parity=False,inspected_original_screenshot=False)


def review():
    out=HERE/'artifacts';out.mkdir(exist_ok=True)
    spot=load('SPOT_H1_FOCUS');context=load('SPOT_H1_CONTEXT')
    sr=descriptive_rows(spot)
    for venue,name in [('SPOT','SPOT_H1_FOCUS'),('USDM','USDM_H1_FOCUS')]:
        a=load(name);rows=descriptive_rows(a)
        early=[r for r in rows if stamp('2026-11-14T22:00:00Z')<=r['open_time_ms']<=stamp('2026-11-15T07:00:00Z')]
        csv_write(out/(venue+'_00_08_madrid.csv'),early)
    late=[r for r in sr if r['open_time_ms']>=stamp('2026-11-15T09:00:00Z')]
    csv_write(out/'SPOT_exhaustion.csv',late)
    match=visual_match(spot);json_write(out/'visual_point_comparison.json',match)
    asofs=['2026-11-15T03:00:00Z','2026-11-15T04:00:00Z',
           '2026-11-15T13:00:00Z','2026-11-15T14:00:00Z','2026-11-15T15:00:00Z']
    contexts={t:context_at(context,stamp(t)) for t in asofs}
    json_write(out/'closed_higher_context.json',contexts)
    ledger=detect(spot)
    csv_write(out/'proximity_ledger.csv.gz',ledger)
    protocol=json.loads((HERE/'review_protocol.json').read_text())
    lo,hi=stamp(protocol['additional_cases_open_from_utc']),stamp(protocol['additional_cases_open_until_exclusive_utc'])
    f=calculate(spot);ev=events(f);rows=[]
    for i,bar in enumerate(spot):
        if not lo<=bar[0]<hi:continue
        for side in ('UP','DOWN'):
            if not ev['pececillos_cross_'+side.lower()][i]:continue
            observed=(spot[i+4,4]-bar[4]) if i+4<len(spot) else None
            signed=observed*(1 if side=='UP' else -1) if observed is not None else None
            labels='CENSORED' if signed is None else 'SAME_DIRECTION_CLOSE' if signed>0 else 'OPPOSITE_DIRECTION_CLOSE' if signed<0 else 'FLAT'
            mtf=context_at(context,int(bar[0]+HOUR))
            row=dict(open_utc=iso(int(bar[0])),available_at=iso(int(bar[0]+HOUR)),side_hypothesis=side,
                pececillos=float(f['minnows'][i]),ma_trend=float(f['kon_signal'][i]),
                adx=float(f['adx'][i]),adx_turn_down=bool(ev['adx_turn_down'][i]),adx_turn_up=bool(ev['adx_turn_up'][i]),
                ao=float(f['ao'][i]),ao_slope=float(f['ao_slope'][i]),
                diagnostic_close_change_4h=observed,description=labels,
                bias_4h=mtf['4H']['bias_ao_dmi'],bias_1d=mtf['1D']['bias_ao_dmi'],bias_1w=mtf['1W']['bias_ao_dmi'],
                evidence_mode='POST_HOC_DESCRIPTIVE_NO_TRADE_OR_NET_RETURN')
            rows.append(row)
    csv_write(out/'all_calendar_crosses.csv',rows)
    examples=[]
    for side in ('UP','DOWN'):
        for label in ('SAME_DIRECTION_CLOSE','OPPOSITE_DIRECTION_CLOSE','FLAT'):
            examples.extend([r for r in rows if r['side_hypothesis']==side and r['description']==label][:2])
    json_write(out/'objective_examples.json',examples)
    primary=[r for r in ledger if r['record_type']=='PROXIMITY_OBSERVED' and r['area']=='pececillos' and lo<=r['bar_open_ms']<hi]
    all_confirm=[r for r in ledger if r['record_type']=='PROXIMITY_OBSERVED']
    summary=dict(calendar_range=[iso(lo),iso(hi)],days=45,all_pececillos_crosses=len(rows),
        cross_directions={side:sum(r['side_hypothesis']==side for r in rows) for side in ('UP','DOWN')},
        descriptive_outcomes={s:sum(r['description']==s for r in rows) for s in ('SAME_DIRECTION_CLOSE','OPPOSITE_DIRECTION_CLOSE','FLAT','CENSORED')},
        proposal_pececillos_proximities=len(primary),proximity_contexts={k:sum(r['adx_context']==k for r in primary) for k in ('PEAK_DECELERATION','TROUGH_BUILDING')},
        hypothesis_by_year_or_regime='NO_INFERENCE; SMALL POST_HOC_DESCRIPTION_ONLY',
        last_available_at=iso(int(spot[-1,0]+HOUR)),proposal_sha256=hashlib.sha256((HERE/'proposal.json').read_bytes()).hexdigest(),
        new_backtests=0,tradingview_exports=0,complete_platform_parity=False,trade_authority='NONE')
    groups={}
    for r in rows:
        key=':'.join((r['side_hypothesis'],r['bias_4h'],r['bias_1d'],r['bias_1w']))
        g=groups.setdefault(key,dict(n=0,same_direction=0,opposite_direction=0,flat=0))
        g['n']+=1;g['same_direction']+=r['description']=='SAME_DIRECTION_CLOSE'
        g['opposite_direction']+=r['description']=='OPPOSITE_DIRECTION_CLOSE';g['flat']+=r['description']=='FLAT'
    json_write(out/'descriptive_context_groups.json',groups)
    json_write(out/'summary.json',summary)
    return summary,examples


def plots(examples):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    from datetime import datetime
    from zoneinfo import ZoneInfo
    a=load('SPOT_H1_FOCUS');f=calculate(a)
    cases=[('early_15nov',stamp('2026-11-15T03:00:00Z')),('late_15nov',stamp('2026-11-15T15:00:00Z'))]
    cases += [('calendar_'+str(i+1),stamp(r['available_at'])) for i,r in enumerate(examples)]
    for name,at in cases:
        ids=np.flatnonzero((a[:,0]+HOUR>=at-8*HOUR)&(a[:,0]+HOUR<=at+4*HOUR))
        x=[datetime.fromtimestamp((a[i,0]+HOUR)/1000,ZoneInfo('Europe/Madrid')) for i in ids]
        fig,ax=plt.subplots(4,1,figsize=(12,10),sharex=True)
        ax[0].plot(x,a[ids,4],marker='.',label='BTCUSDT closed price')
        for key,label,c in [('minnows','pececillos','green'),('kon_trend','tendencia','#946332'),('kon_signal','ma_trend','red')]:
            ax[1].plot(x,f[key][ids],label=label,color=c,marker='.')
        ax[1].axhline(0,color='grey',linewidth=.6)
        ax[2].plot(x,f['adx'][ids],color='red',label='ADX14/14')
        ax[2].plot(x,f['bbwp'][ids],color='#596da2',label='BBWP7/100')
        ax[3].bar(x,f['ao'][ids],width=.025,color=['green' if f['ao_slope'][i]>0 else 'red' for i in ids])
        ax[3].set_ylabel('AO5/34')
        for axis in ax:
            axis.axvline(datetime.fromtimestamp(at/1000,ZoneInfo('Europe/Madrid')),color='purple',linestyle='--',label='Diagnostic close')
            axis.grid(alpha=.2);axis.legend(fontsize=7)
        ax[-1].xaxis.set_major_formatter(md.DateFormatter('%d %H:%M',tz=ZoneInfo('Europe/Madrid')))
        ax[-1].set_xlabel('Earliest availability at confirmed H1 close, Europe/Madrid')
        fig.suptitle(name+' — BINANCE SPOT LOCAL REPLAY\nPOST-HOC DIAGNOSTIC, NOT AN ENTRY / NOT PLATFORM PARITY')
        fig.tight_layout(rect=(0,0,1,.94));fig.savefig(HERE/'artifacts'/(name+'.png'),dpi=130);plt.close(fig)


if __name__=='__main__':
    summary,examples=review();plots(examples)
    print(json.dumps(summary))
