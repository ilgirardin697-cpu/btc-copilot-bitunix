"""Visualize existing F4A results, no signal generation or target selection."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import numpy as np

from research.confluence_1h.data import load
from .evaluate import HERE


def plot(cache):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a,_,_=load(cache);out=HERE/'artifacts'
    deals=list(csv.DictReader((out/'trades_all.csv').read_text().splitlines()))
    primary=[r for r in deals if r['variant']=='PECECILLOS' and r['book']=='COMBINED' and r['window']=='FULL']
    raw=gzip.decompress((out/'equity.csv.gz').read_bytes()).decode()
    eq=list(csv.DictReader(io.StringIO(raw)))
    fig,ax=plt.subplots(2,1,figsize=(14,8),sharex=True)
    time=[datetime.fromtimestamp(t/1000,timezone.utc) for t in a[:,0]+3600000]
    ax[0].plot(time,a[:,4],lw=.5,color='#334155',label='USD-M BTCUSDT H1 closed price')
    for side,color,marker in [('1','green','^'),('-1','red','v')]:
        rows=[r for r in primary if r['target_r']=='2.0' and r['side']==side]
        x=[datetime.fromisoformat(r['available_at'].replace('Z','+00:00')) for r in rows]
        y=[float(r['entry_reference']) for r in rows]
        ax[0].scatter(x,y,color=color,marker=marker,label='LONG' if side=='1' else 'SHORT',s=35)
    for variant,target,color in [('BASE','2.0','grey'),('PECECILLOS','2.0','#2563eb'),('PECECILLOS','3.0','#a16207')]:
        rows=[r for r in eq if r['variant']==variant and r['target_r']==target and r['window']=='FULL']
        x=[datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')) for r in rows]
        ax[1].plot(x,[float(r['equity']) for r in rows],label=variant+' TP'+target+'R',color=color,lw=1)
    for axis in ax:axis.grid(alpha=.2);axis.legend(fontsize=8)
    ax[1].set_ylabel('Simulated USDT; initial200, no reset')
    fig.suptitle('F4A: one series substitution; n=7, INCONCLUSIVE\nOriginal conservative funding-bound scenario, not exact observed account returns')
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(out/'comparison_equity.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5));x=np.arange(7)
    for target,offset,color in [('2.0',-.17,'#2563eb'),('3.0',.17,'#a16207')]:
        rows=[r for r in primary if r['target_r']==target]
        ax.bar(x+offset,[float(r['net_r']) for r in rows],width=.3,color=color,label='TP'+target+'R')
    ax.axhline(0,color='black',lw=.7);ax.set_xticks(x,[r['available_at'][:10] for r in primary if r['target_r']=='2.0'],rotation=25)
    ax.set_ylabel('NetR, original conservative funding scenario');ax.legend();ax.grid(axis='y',alpha=.2)
    ax.set_title('All seven unique historical signals — co-primary scenarios, not14 independent trades')
    fig.tight_layout();fig.savefig(out/'all_seven_trades.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);args=p.parse_args();plot(args.cache)
