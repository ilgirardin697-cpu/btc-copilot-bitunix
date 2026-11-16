"""All closed November observations; no hindsight winner-selection chart."""
import csv
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from .replay import HERE


def generate():
    complete=HERE/'artifacts/november_full.csv'
    rows=list(csv.DictReader((complete if complete.exists() else HERE/'artifacts/november.csv').open(encoding='utf-8')))
    for venue in ('SPOT','USDM'):
        for zoom in (False,True):
            rr=[r for r in rows if r['venue']==venue and (not zoom or r['available_madrid'].startswith('2026-11-15'))]
            x=np.array([md.date2num(datetime.fromisoformat(r['earliest_available_utc'].replace('Z','+00:00'))) for r in rr])
            get=lambda key:np.array([float(r[key]) for r in rr])
            fig,axs=plt.subplots(4,1,figsize=(15,10),sharex=True,gridspec_kw={'height_ratios':[2,1,1,1]})
            o,c,h,l=[get(k) for k in ('open','close','high','low')]
            for xx,oo,cc,hh,ll in zip(x,o,c,h,l):
                color='#16865c' if cc>=oo else '#c84545'
                axs[0].vlines(xx,ll,hh,color=color,lw=.8);axs[0].bar(xx,cc-oo,bottom=oo,width=.025,color=color,alpha=.7)
            axs[0].set_ylabel('BTCUSDT price')
            axs[1].bar(x,get('ao'),width=.03,color=np.where(get('ao_slope')>0,'#1ba56b','#d44545'));axs[1].axhline(0,color='gray',lw=.6);axs[1].set_ylabel('AO5/34')
            axs[2].plot(x,get('adx'),color='#c23e48',label='ADX14/14');axs[2].plot(x,get('plus_di'),color='green',label='+DI',lw=.8);axs[2].plot(x,get('minus_di'),color='purple',label='-DI',lw=.8);axs[2].legend(loc='upper left',ncol=3,fontsize=8)
            axs[3].plot(x,get('pececillos'),color='#25864f',label='pececillos');axs[3].plot(x,get('red_ema'),color='#d44545',label='EMA15(tendencia)');axs[3].legend(loc='upper left',fontsize=8)
            for i,r in enumerate(rr):
                if r['ao_simple_up']=='True' or r['ao_simple_down']=='True':axs[1].axvline(x[i],color='gray',ls=':',alpha=.35)
                if r['ao_22_up']=='True' or r['ao_22_down']=='True':
                    axs[1].plot(x[i],float(r['ao']),'o',color='#175cba',ms=4)
                    axs[0].axvline(x[i],color='#175cba',alpha=.2,lw=.7)
                if r['confirmed_events']!='[]':axs[0].axvline(x[i],color='#8b2498',lw=1.5)
            for ax in axs:ax.grid(alpha=.15)
            axs[-1].xaxis.set_major_locator(md.HourLocator(byhour=range(0,24,3 if zoom else 12),tz=timezone.utc))
            axs[-1].xaxis.set_major_formatter(md.DateFormatter('%m-%d %H:%M',tz=timezone.utc))
            axs[-1].set_xlabel('UTC candle close / earliest availability. Gray: first AO slope; blue: AO2+2; purple: full frozen event.')
            fig.suptitle(f'BTCUSDT {venue} H1 — closed-data Python replay, not external chart parity\nPreobserved diagnostic, no trade recommendation')
            fig.tight_layout();target=HERE/'artifacts'/f'{venue}_{"nov15" if zoom else "all"}.png';fig.savefig(target,dpi=135);plt.close(fig)


if __name__=='__main__':generate()
