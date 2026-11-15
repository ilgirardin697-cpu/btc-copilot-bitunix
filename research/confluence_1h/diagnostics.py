"""Explain gates without inventing additional strategies or changing parameters."""
from datetime import datetime,timezone
import numpy as np
from .data import iso


def gate_funnel(bars,features,flags,start,end):
    years=np.array([iso(t)[:4] for t in bars[:,0]]);rows=[]
    for year in ['ALL']+sorted(set(years[start:end])):
        mask=np.zeros(len(bars),bool);mask[start:end]=True
        if year!='ALL':mask &=years==year
        for side,k,a in [('LONG','kon_long','ao_long'),('SHORT','kon_short','ao_short')]:
            current=mask.copy()
            for label,key in [('KON_CROSS_AND_PREVIOUS_SIGN',k),('PLUS_LAGGED_ADX_DECLINE','adx_lagged_decline'),('PLUS_AO_TWO_SLOPES',a),('PLUS_BBWP_ABOVE85','bbwp_above')]:
                current &=flags[key]
                rows.append(dict(year=year,side=side,gate=label,n=int(current.sum())))
    return rows


def rejection_plots(bars,f,sig,start,end,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    selections=[]
    # Objective diagnostic choices: first qualifying crossing per side; and first
    # crossing+ADX+AO that still fails BBWP. No use of subsequent PnL or path.
    for side,k,a in [('LONG','kon_long','ao_long'),('SHORT','kon_short','ao_short')]:
        for mode in ('FIRST_CROSS','FIRST_PRE_BBWP_REJECTION'):
            mask=sig[k].copy()
            if mode!='FIRST_CROSS':mask &=sig['adx_lagged_decline']&sig[a]&~sig['bbwp_above']
            ids=np.flatnonzero(mask);ids=ids[(ids>=start)&(ids<end)]
            if len(ids):selections.append((side,mode,int(ids[0])))
    for count,(side,mode,i) in enumerate(selections,1):
        lo=max(start,i-30);hi=min(end,i+19)
        t=[datetime.fromtimestamp(x/1000,timezone.utc) for x in bars[lo:hi,0]]
        fig,axs=plt.subplots(4,1,figsize=(13,9),sharex=True)
        axs[0].plot(t,bars[lo:hi,4],label='Binance USD-M H1 close')
        axs[1].plot(t,f['kon_trend'][lo:hi],label='Koncorde trend');axs[1].plot(t,f['kon_signal'][lo:hi],label='EMA15');axs[1].axhline(0,color='gray',lw=.5)
        axs[2].plot(t,f['ao'][lo:hi],label='AO');axs[2].axhline(0,color='gray',lw=.5)
        axs[3].plot(t,f['adx'][lo:hi],label='ADX');axs[3].plot(t,f['bbwp'][lo:hi],label='BBWP');axs[3].axhline(40,color='gray',lw=.6);axs[3].axhline(85,color='orange',lw=.6)
        x=datetime.fromtimestamp(bars[i,0]/1000,timezone.utc)
        for ax in axs:ax.axvline(x,color='purple',ls=':');ax.legend(fontsize=7);ax.grid(alpha=.15)
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=timezone.utc))
        failed=[label for label,key in [('ADX','adx_lagged_decline'),('AO','ao_long' if side=='LONG' else 'ao_short'),('BBWP','bbwp_above')] if not sig[key][i]]
        fig.suptitle(f'REJECTED component crossing, NOT a trade: {side}; failed {",".join(failed)}; {mode}; UTC')
        fig.tight_layout();fig.savefig(out/f'rejected_{count}.png',dpi=150);plt.close(fig)
    return [dict(side=side,selection_rule=mode,signal_candle_open=iso(bars[i,0]),available_at=iso(bars[i,0]+3600000),
        accepted=False,not_a_historical_trade=True) for side,mode,i in selections]
