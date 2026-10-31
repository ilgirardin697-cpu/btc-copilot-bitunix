"""Calendar-block uncertainty, paired baseline comparisons; no fitting."""
from datetime import date,timedelta
import numpy as np
from .simulation import SPLITS
from .data import iso
SEED=20261031
RESAMPLES=5000
BLOCK_DAYS=14
def day_axis(split):
    lo,hi=SPLITS[split];first=date.fromisoformat(iso(lo)[:10]);last=date.fromisoformat(iso(hi)[:10])
    return [(first+timedelta(days=i)).isoformat() for i in range((last-first).days)]
def daily(trades,split):
    days=day_axis(split);lookup={d:i for i,d in enumerate(days)}
    values=np.zeros(len(days));counts=np.zeros(len(days))
    for row in trades:
        if row['date'] in lookup:
            i=lookup[row['date']];values[i]+=row['net_r'];counts[i]+=1
    return values,counts
def samples(n):
    rng=np.random.default_rng(SEED)
    starts=rng.integers(0,n,size=(RESAMPLES,int(np.ceil(n/BLOCK_DAYS))))
    return ((starts[:,:,None]+np.arange(BLOCK_DAYS))%n).reshape(RESAMPLES,-1)[:,:n]
def interval(trades,split):
    if not trades:return [None,None]
    values,counts=daily(trades,split);idx=samples(len(values))
    ns=counts[idx].sum(axis=1);ok=ns>0
    means=values[idx].sum(axis=1)[ok]/ns[ok]
    return np.percentile(means,[2.5,97.5]).tolist()
def paired(trades,baseline,split):
    a,_=daily(trades,split);b,_=daily(baseline,split);x=a-b
    boot=x[samples(len(x))].mean(axis=1)
    return dict(mean_daily_r_difference=float(x.mean()),
                ci95=np.percentile(boot,[2.5,97.5]).tolist(),
                familywise_ci=np.percentile(boot,[100*.05/24,100*(1-.05/24)]).tolist())
def metrics(trades,split,portfolio=None,with_ci=True):
    n=len(trades)
    if not n:return dict(n=0,mean_net_r=None,median_net_r=None,ci95=[None,None],profit_factor=None)
    net=np.array([r['net_r'] for r in trades]);profit=net[net>0].sum();loss=-net[net<0].sum()
    trimmed=lambda k:float(np.mean(np.sort(net)[:-k])) if n>k else None
    gross=sum(r['qty']*r['gross_unit'] for r in trades)
    fees=sum(r['qty']*r['fees_unit'] for r in trades)
    fund=sum(r['qty']*r['funding_unit'] for r in trades)
    slippage=sum(r['qty']*r.get('slippage_unit',0) for r in trades)
    p=portfolio or {}
    return dict(n=n,long=sum(r['side']==1 for r in trades),short=sum(r['side']==-1 for r in trades),
        win_rate=float(np.mean(net>0)),mean_net_r=float(net.mean()),median_net_r=float(np.median(net)),
        p10_net_r=float(np.percentile(net,10)),p90_net_r=float(np.percentile(net,90)),
        mean_gross_r=float(np.mean([r['gross_r'] for r in trades])),ci95=interval(trades,split) if with_ci else [None,None],
        profit_factor=float(profit/loss) if loss else None,pf_infinite=bool(loss==0 and profit>0),
        target_hit_rate=float(np.mean([r['target_hit'] for r in trades])),
        ambiguous=sum(r['ambiguous'] for r in trades),mean_duration_hours=float(np.mean([r['duration_hours'] for r in trades])),
        mean_mae_r=float(np.mean([r['mae_r'] for r in trades])),mean_mfe_r=float(np.mean([r['mfe_r'] for r in trades])),
        mean_net_bps=float(np.mean([r['net_bps'] for r in trades])),gross_pnl_usdt=gross,
        commissions_usdt=fees,slippage_usdt=slippage,funding_proxy_usdt=fund,net_pnl_usdt=gross-fees+fund,
        net_return_pct=(p.get('equity',10000)/10000-1)*100 if portfolio else None,
        mtm_drawdown_pct=p.get('drawdown',0)*100 if portfolio else None,
        exposure_fraction=sum(r['duration_hours'] for r in trades)/((SPLITS[split][1]-SPLITS[split][0])/3600000),
        ex_best1_mean_r=trimmed(1),ex_best3_mean_r=trimmed(3))
def classify(evaluation,validation,stress,paired_result,halfyears):
    e=evaluation;n=e['n']
    if n<30:return 'INCONCLUSIVE'
    if (e['mean_net_r']<=0 and (e['profit_factor'] or 0)<=1) or e['ci95'][1]<=0:return 'NO EDGE'
    required=(n>=100 and e['long']>=30 and e['short']>=30 and e['ci95'][0]>0
        and (e['profit_factor'] or 0)>1.1 and (stress.get('mean_net_r') or 0)>0
        and (validation.get('mean_net_r') or 0)>0 and all(x['n']>0 and x['mean_net_r']>0 for x in halfyears.values())
        and e['ex_best3_mean_r'] is not None and e['ex_best3_mean_r']>0 and paired_result['familywise_ci'][0]>0)
    return 'PROMISING' if required else 'INCONCLUSIVE'
