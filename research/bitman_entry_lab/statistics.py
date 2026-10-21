"""Calendar block uncertainty; no parameter search."""
import numpy as np
SEED=20261021
DRAWS=5000
MONTH=30*86400000

def interval(values,times,alpha=.025):
    a=np.asarray(values,float);t=np.asarray(times,dtype=np.int64)
    if len(a)<2:return [None,None],None
    block=t//MONTH;lo,hi=block.min(),block.max();n=int(hi-lo+1)
    if n<2:return [None,None],None
    count=np.bincount(block-lo,minlength=n);total=np.bincount(block-lo,weights=a,minlength=n)
    rng=np.random.default_rng(SEED);draw=rng.integers(0,n,size=(DRAWS,n))
    den=count[draw].sum(axis=1);num=total[draw].sum(axis=1)
    boot=num[den>0]/den[den>0]
    return np.quantile(boot,[.025,.975]).tolist(),float(np.quantile(boot,alpha))

def mean(a):return float(np.mean(a)) if len(a) else None
def drawdown(values):
    curve=np.r_[0.,np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(curve)-curve))
def summarize(rows,scenario='BASE',bootstrap=True):
    rows=sorted(rows,key=lambda r:r['entry_time']);n=len(rows)
    if not n:return dict(n=0,mean_R=None,ci95_R=[None,None],adjusted_lower_R=None)
    x=np.asarray([r['costs'][scenario]['net_R'] for r in rows])
    returns=np.asarray([r['costs'][scenario]['net_return'] for r in rows])
    ci,adj=interval(x,[r['signal_time'] for r in rows],.05/35) if bootstrap else ([None,None],None)
    gains=x[x>0].sum();loss=-x[x<0].sum()
    duration=sum(r['duration_hours'] for r in rows)
    span=(rows[-1]['exit_time']-rows[0]['entry_time'])/3600000
    return dict(n=n,long=sum(r['side']==1 for r in rows),short=sum(r['side']==-1 for r in rows),
        mean_R=float(x.mean()),median_R=float(np.median(x)),ci95_R=ci,adjusted_lower_R=adj,
        win_rate=float(np.mean(x>0)),profit_factor=float(gains/loss) if loss else None,
        mean_gross_R=mean([r['gross_R'] for r in rows]),mean_funding_R=mean([r['funding_R'] for r in rows]),
        mean_commission_R=mean([r['costs'][scenario]['commission_R'] for r in rows]),
        mean_slippage_R=mean([r['costs'][scenario]['slippage_R'] for r in rows]),
        mean_net_return=float(returns.mean()),mean_gross_return=mean([r['gross_return'] for r in rows]),
        quantiles_R=dict(zip(('p05','p25','p50','p75','p95'),map(float,np.quantile(x,[.05,.25,.5,.75,.95])))),
        max_drawdown_R=drawdown(x),max_drawdown_unit_notional=drawdown(returns),
        exposure=float(duration/span) if span else 0.,exposure_window='FIRST_ENTRY_TO_LAST_EXIT',observation_span_hours=span,
        trades_per_30days=float(n/(span/24/30)) if span else None,
        mean_duration_hours=mean([r['duration_hours'] for r in rows]),
        mean_mae_R=mean([r['mae_R'] for r in rows]),mean_mfe_R=mean([r['mfe_R'] for r in rows]),
        first_5m_adverse_rate=mean([r['first_5m_adverse'] for r in rows]),
        mean_entry_drift_bps=mean([r['entry_drift_bps'] for r in rows]),
        stop_target_ambiguous=sum(r['ambiguous_bar'] for r in rows),
        funding_boundary_ambiguities=sum(r['funding_boundary_ambiguities'] for r in rows),
        ex_best1_mean_R=float(np.sort(x)[:-1].mean()) if n>1 else None,
        ex_best3_mean_R=float(np.sort(x)[:-3].mean()) if n>3 else None)

def paired(rows,controls):
    pairs=[(r,controls[r['anchor_id']]) for r in rows if r['anchor_id'] in controls]
    if not pairs:return dict(n=0,mean_delta_R=None,ci95_delta_R=[None,None])
    delta=[r['costs']['BASE']['net_R']-c['costs']['BASE']['net_R'] for r,c in pairs]
    ci,_=interval(delta,[r['signal_time'] for r,c in pairs])
    return dict(n=len(pairs),mean_delta_R=mean(delta),ci95_delta_R=ci,
        signal_mean_R=mean([r['costs']['BASE']['net_R'] for r,c in pairs]),
        control_mean_R=mean([c['costs']['BASE']['net_R'] for r,c in pairs]),
        control=summarize([c for r,c in pairs]))

def classify(base,conservative,validation,control,annual,incremental):
    if not base.get('n'):return 'INCONCLUSIVE'
    if base['mean_R']<=0 or conservative['mean_R']<=0 or (control['mean_delta_R'] is not None and control['mean_delta_R']<=0):
        return 'NO EDGE'
    positive=lambda x:x is not None and x>0
    checks=[base['n']>=100,base['long']>=30,base['short']>=30,
        positive(base['ci95_R'][0]),positive(conservative['ci95_R'][0]),positive(base['adjusted_lower_R']),
        positive(control['ci95_delta_R'][0]),base['profit_factor'] is not None and base['profit_factor']>1,
        positive(base['ex_best3_mean_R']),positive(validation.get('mean_R')),
        bool(annual) and all(positive(x.get('mean_R')) for x in annual.values()),
        positive(incremental.get('mean_delta_R')),positive(incremental.get('ci95_delta_R',[None])[0])]
    return 'PROMISING FOR FORWARD VALIDATION' if all(checks) else 'INCONCLUSIVE'
