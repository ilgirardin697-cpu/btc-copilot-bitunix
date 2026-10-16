"""Academic funded ledger; cannot send requests or real orders."""
import numpy as np
from research.bitman_real.config import HOUR

BASE_COSTS=dict(fee_bps=5,slip_bps=2,stop_slip_bps=5)
STRESS_COSTS=dict(fee_bps=6,slip_bps=5,stop_slip_bps=10)


def performance(rr):
    rr=np.asarray(rr,float)
    if not len(rr):return dict(total_return=0.,cagr=0.,sharpe=0.,sortino=0.,max_dd=0.)
    curve=np.r_[1.,np.cumprod(1+rr)];vol=np.std(rr,ddof=1) if len(rr)>1 else 0.
    down=np.sqrt(np.mean(np.minimum(rr,0)**2));annual=365.25*24
    return dict(total_return=float(curve[-1]-1),cagr=float(curve[-1]**(annual/len(rr))-1) if curve[-1]>0 else -1.,
        sharpe=float(np.mean(rr)/vol*np.sqrt(annual)) if vol else 0.,
        sortino=float(np.mean(rr)/down*np.sqrt(annual)) if down else 0.,
        max_dd=float(np.min(curve/np.maximum.accumulate(curve)-1)))


def simulate(bars,funding,entries,opposite,atr,side,start,end,costs=None,stop_atr=2.,trailing=False,benchmark=False):
    if side not in (1,-1):raise ValueError('SIDE_INVALID')
    fee,slip,stop_slip=((costs or BASE_COSTS)[k]/10000 for k in ('fee_bps','slip_bps','stop_slip_bps'))
    indices=np.flatnonzero((bars[:,0]>=start)&(bars[:,0]+HOUR<=end));rates=np.zeros(len(bars))
    if len(funding):
        j=np.searchsorted(bars[:,0],funding[:,0],side='right')-1
        ok=(j>=0)&(j<len(bars))&(funding[:,0]<bars[-1,0]+HOUR)
        np.add.at(rates,j[ok],funding[ok,1])
    cash=previous=1.;qty=0.;entry_fill=stop=entry_equity=0.;entered=0;frozen_atr=0.
    trade=None;trades=[];returns=[];times=[];fees=slippage=funding_paid=turnover=0.;insolvent=False
    def close(price,i,reason,is_stop=False):
        nonlocal qty,cash,fees,slippage,turnover,trade
        fill=price*(1-side*(stop_slip if is_stop else slip));charge=qty*fill*fee
        cash+=side*qty*(fill-entry_fill)-charge
        fees+=charge;slippage+=qty*abs(price-fill);turnover+=qty*fill
        trade.update(exit_time=int(bars[i,0]),exit_reason=reason,exit_fill=float(fill),
            net_return=float(cash/entry_equity-1),fees=trade['fees']+charge,
            slippage=trade['slippage']+qty*abs(price-fill),hold_hours=int(i-entered+1))
        trades.append(trade);qty=0.
    for i in indices:
        o,h,l,c=bars[i,1:5];closed=False
        if qty:
            paid=side*qty*o*rates[i];cash-=paid;funding_paid+=paid;trade['funding']+=paid
            if not benchmark and (o-stop)*side<=0:close(o,i,'gap_stop',True);closed=True
            elif opposite[i]:close(o,i,'opposite');closed=True
            elif not benchmark and i-entered>=168:close(o,i,'max168h');closed=True
        if not qty and not closed and entries[i] and cash>0 and (benchmark or np.isfinite(atr[i]) and atr[i]>0):
            entered=i;entry_equity=cash;entry_fill=o*(1+side*slip);qty=cash/entry_fill
            charge=qty*entry_fill*fee;cash-=charge;fees+=charge;slippage+=qty*abs(o-entry_fill);turnover+=qty*entry_fill
            frozen_atr=atr[i] if not benchmark else np.inf;stop=entry_fill-side*stop_atr*frozen_atr
            trade=dict(entry_time=int(bars[i,0]),entry_fill=float(entry_fill),side=side,entry_equity=float(entry_equity),
                fees=float(charge),slippage=float(qty*abs(o-entry_fill)),funding=0.,signal_known_at=int(bars[i,0]))
        if qty and not benchmark:
            touched=l<=stop if side==1 else h>=stop
            if touched:close(min(o,stop) if side==1 else max(o,stop),i,'stop',True)
            elif trailing:
                new=(h if side==1 else l)-side*3*frozen_atr
                if (new-stop)*side>0:stop=new
        if qty and i==indices[-1]:close(c,i,'split_end')
        equity=cash+(side*qty*(c-entry_fill) if qty else 0.)
        if equity<=0:
            insolvent=True
            if qty:
                trade.update(exit_time=int(bars[i,0]),exit_reason='academic_insolvency_floor',exit_fill=None,
                    net_return=-1.,hold_hours=int(i-entered+1))
                trades.append(trade)
            elif trades and trades[-1]['exit_time']==int(bars[i,0]):trades[-1]['net_return']=max(-1.,trades[-1]['net_return'])
            equity=0.;cash=0.;qty=0.
        returns.append(equity/previous-1 if previous>0 else 0.);times.append(int(bars[i,0]));previous=equity
    values=np.array([t['net_return'] for t in trades]);win=values[values>0];loss=values[values<0]
    nwin=float(sum(win));nloss=float(-sum(loss));streak=worst=0
    for v in values:streak=streak+1 if v<0 else 0;worst=max(worst,streak)
    m=performance(returns);m.update(trades=len(values),expectancy=float(values.mean()) if len(values) else 0.,
        median_trade=float(np.median(values)) if len(values) else 0.,win_rate=float(np.mean(values>0)) if len(values) else 0.,
        profit_factor=nwin/nloss if nloss else None,
        payoff_ratio=float(-win.mean()/loss.mean()) if len(win) and len(loss) else None,
        fees=float(fees),slippage=float(slippage),funding=float(funding_paid),turnover=float(turnover),
        longest_losing_streak=worst,insolvent=insolvent)
    return dict(metrics=m,returns=np.array(returns),times=np.array(times,dtype=np.int64),trades=trades)


def removal(result,n):
    trades=sorted(result['trades'],key=lambda t:t['net_return'],reverse=True);rr=result['returns'].copy()
    for t in trades[:n]:rr[(result['times']>=t['entry_time'])&(result['times']<=t['exit_time'])]=0.
    return dict(performance(rr),trades=max(0,len(trades)-n),expectancy=float(np.mean([t['net_return'] for t in trades[n:]])) if len(trades)>n else 0.)


def bootstrap(result):
    trades=result['trades']
    if not trades:return dict(n=0,ci95=[None,None])
    weeks=np.arange(result['times'][0]//(168*HOUR),result['times'][-1]//(168*HOUR)+1)
    values=np.zeros(len(weeks));counts=values.copy()
    for t in trades:
        i=int(t['entry_time']//(168*HOUR)-weeks[0]);values[i]+=t['net_return'];counts[i]+=1
    rng=np.random.default_rng(6241);means=[]
    for _ in range(500):
        i=rng.integers(0,len(weeks),len(weeks));n=counts[i].sum()
        if n:means.append(float(values[i].sum()/n))
    return dict(n=len(trades),ci95=np.quantile(means,[.025,.975]).tolist(),blocks='calendar7day',seed=6241,repetitions=500)
