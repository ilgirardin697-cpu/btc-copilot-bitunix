"""Public price reconstruction; not original chart/indicator parity."""
from pathlib import Path
from datetime import datetime,timezone
import csv,gzip,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.patches import Rectangle
HERE=Path(__file__).resolve().parent
def main():
    s=json.loads((HERE/'out/sniper.json').read_text());out=HERE/'out/sniper.png'
    if out.exists():raise ValueError('DO_NOT_OVERWRITE_FIGURE')
    with gzip.open(HERE/'d/1h.csv.gz','rt') as f:rows=[[float(v) for v in r] for r in list(csv.reader(f))[1:]]
    rows=[r for r in rows if s['published']-12*3600000<=r[0]<=s['target_touch']+4*3600000]
    fig,ax=plt.subplots(figsize=(12,5))
    for t,o,h,l,c,v in rows:
        x=md.date2num(datetime.fromtimestamp((t+1800000)/1000,timezone.utc));color='#169b72' if c>=o else '#c85050'
        ax.vlines(x,l,h,color=color,lw=1)
        ax.add_patch(Rectangle((x-.017,min(o,c)),.034,max(abs(c-o),.5),facecolor=color,edgecolor=color))
    for y,label,color in [(s['threshold'],'Member threshold59,758','#a17800'),(s['target'],'Member target60,900','#6244b4')]:ax.axhline(y,label=label,color=color,ls='--')
    for t,label,color in [(s['published'],'Publication (reported)','#777777'),(s['confirmation'],'Closed H1 confirmation','#1274ad'),(s['target_touch'],'First1m target touch','#6244b4')]:
        ax.axvline(datetime.fromtimestamp(t/1000,timezone.utc),color=color,ls=':',label=label)
    ax.xaxis.set_major_formatter(md.DateFormatter('%dNov %H:%M',tz=timezone.utc));ax.set_ylabel('BTCUSDT Spot price');ax.set_xlabel('UTC; H1 bodies plotted at interval centers; vertical timestamps are actual availability')
    ax.set_title('SniperRBW source-selected reconstruction — no verified fill/stop/PnL')
    ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper left');fig.autofmt_xdate();fig.tight_layout();fig.savefig(out,dpi=150);plt.close(fig)
    print(str(out))
if __name__=='__main__':main()
