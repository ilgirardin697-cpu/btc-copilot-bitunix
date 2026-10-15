"""Academic1x perpetual ledger, next-bar fills, no order/account interfaces."""
import math
import numpy as np
from .data import HOUR


def performance(returns, periods_per_year=365.25*24):
    rr=np.asarray(returns,float)
    if not len(rr): return dict(total_return=0.,cagr=0.,sharpe=0.,sortino=0.,max_dd=0.)
    curve=np.r_[1.,np.cumprod(1+rr)]; years=len(rr)/periods_per_year
    sd=float(np.std(rr,ddof=1)) if len(rr)>1 else 0.
    downside=math.sqrt(float(np.mean(np.minimum(rr,0)**2)))
    dd=float(np.min(curve/np.maximum.accumulate(curve)-1))
    return dict(total_return=float(curve[-1]-1),cagr=float(curve[-1]**(1/years)-1) if curve[-1]>0 else -1.,
                sharpe=float(np.mean(rr)/sd*math.sqrt(periods_per_year)) if sd else 0.,
                sortino=float(np.mean(rr)/downside*math.sqrt(periods_per_year)) if downside else 0.,max_dd=dd)


def economic_be(cash,entry_equity,qty,entry_fill,side,fee,stop_slip):
    if qty<=0: raise ValueError('BE_QTY_INVALID')
    effective=(entry_equity-cash+side*qty*entry_fill)/(qty*(side-fee))
    return effective/(1-side*stop_slip)


def simulate(bars, f, entry, opposite, funding, p, side, start, end, costs=None, benchmark=False):
    """All stop/trail prices committed before a bar; ambiguous touches stop first."""
    if side not in (-1,0,1): raise ValueError('SIDE_INVALID')
    combined=side==0; plans=p; conflicts=0
    costs=costs or dict(fee_bps=5,slip_bps=2,stop_slip_bps=5)
    fee,slip,stop_slip=(costs[k]/10000 for k in ('fee_bps','slip_bps','stop_slip_bps'))
    indices=np.flatnonzero((bars[:,0]>=start)&(bars[:,0]+HOUR<=end))
    rates=np.zeros(len(bars))
    if len(funding):
        k=np.searchsorted(bars[:,0],funding[:,0],side='right')-1
        valid=(k>=0)&(k<len(bars))&(funding[:,0]<bars[-1,0]+HOUR)
        np.add.at(rates,k[valid],funding[valid,1])
    cash=previous_equity=1.; qty=0.; initial_qty=0.; total_fees=total_slip=total_funding=turnover=0.
    stop=best=entry_fill=entry_open=entry_equity=initial_risk=0.; stop_kind='initial_stop'
    entry_index=0; took1=took2=False; active=None; ledger=[]; rr=[]; times=[]; insolvent=False

    def close_part(amount,price,i,reason,is_stop=False):
        nonlocal cash,qty,total_fees,total_slip,turnover
        amount=min(qty,amount)
        fill=price*(1-side*(stop_slip if is_stop else slip))
        fees=amount*fill*fee; sliding=amount*abs(price-fill)
        cash+=side*amount*(fill-entry_fill)-fees
        qty-=amount; total_fees+=fees; total_slip+=sliding; turnover+=amount*fill
        active['gross_price_pnl']+=side*amount*(price-entry_open)
        active['fees']+=fees; active['slippage']+=sliding
        active['fills'].append(dict(time=int(bars[i,0]),fraction=float(amount/initial_qty),price=float(fill),reason=reason))
        if qty<initial_qty*1e-10:
            qty=0.
            active.update(exit_time=int(bars[i,0]),exit_reason=reason,
                          net_return=float(cash/entry_equity-1),hold_hours=i-entry_index+1,
                          tp1_hit=took1,tp2_hit=took2)
            ledger.append(dict(active))

    for count,i in enumerate(indices):
        opening,high,low,closing=bars[i,1:5]
        closed_this_bar=False
        if qty:
            paid=side*qty*opening*rates[i]
            cash-=paid; total_funding+=paid; active['funding']+=paid
            invalid=opposite[side][i-1] if combined and i else opposite[i-1] if i else False
            if not benchmark and (opening-stop)*side<=0:
                close_part(qty,opening,i,stop_kind,True); closed_this_bar=True
            elif invalid:
                close_part(qty,opening,i,'opposite'); closed_this_bar=True
            elif not benchmark and i-entry_index>=168:
                close_part(qty,opening,i,'max_hold'); closed_this_bar=True
        triggered=[]
        if i and not qty and not closed_this_bar:
            triggered=[s for s in (1,-1) if entry[s][i-1]] if combined else [side] if entry[i-1] else []
            if len(triggered)>1: conflicts+=1; triggered=[]
        if triggered and cash>0:
            if combined: side=triggered[0]; p=plans[side]
            atr=f['atr'][i-1]
            if benchmark or np.isfinite(atr) and atr>0:
                entry_index=i; entry_equity=cash; entry_open=opening
                entry_fill=opening*(1+side*slip); initial_qty=qty=cash/entry_fill
                charge=qty*entry_fill*fee
                cash-=charge; total_fees+=charge; total_slip+=qty*abs(entry_fill-opening); turnover+=qty*entry_fill
                initial_risk=p.stop_atr*atr if not benchmark else math.inf
                stop=entry_fill-side*initial_risk; best=opening; took1=took2=False
                stop_kind='initial_stop'
                active=dict(entry_time=int(bars[i,0]),signal_time=int(bars[i-1,0]+HOUR),
                    entry_index=count,side='LONG' if side==1 else 'SHORT',entry_equity=float(entry_equity),
                    entry_fill=float(entry_fill),risk_distance=float(initial_risk) if not benchmark else None,
                    fees=float(charge),slippage=float(qty*abs(entry_fill-opening)),funding=0.,gross_price_pnl=0.,fills=[])
        if qty and not benchmark:
            touched=(low<=stop if side==1 else high>=stop)
            if touched:
                price=min(opening,stop) if side==1 else max(opening,stop)
                close_part(qty,price,i,stop_kind,True)
            elif p.exit=='runner':
                tp1=entry_fill+side*initial_risk; tp2=entry_fill+side*2*initial_risk
                favorable=high if side==1 else low
                if not took1 and (favorable-tp1)*side>=0:
                    took1=True
                    close_part(initial_qty*.3,tp1,i,'tp1')
                    be=economic_be(cash,entry_equity,qty,entry_fill,side,fee,stop_slip)
                    if (be-tp1)*side>=0:
                        close_part(qty,tp1,i,'be_unfeasible_market',True)
                        be=stop
                    if (be-stop)*side>0: stop=be; stop_kind='economic_be'
                    # If chronology is unknown, do not book TP2 before a newly
                    # activated BE that the same candle could also have hit.
                    if qty and (low<=stop if side==1 else high>=stop): close_part(qty,stop,i,'economic_be',True)
                if qty and took1 and not took2 and (favorable-tp2)*side>=0:
                    took2=True; close_part(initial_qty*.3,tp2,i,'tp2')
                if qty and took1:
                    best=max(best,high) if side==1 else min(best,low)
                    trail=best-side*p.trail_atr*(initial_risk/p.stop_atr)
                    if (trail-stop)*side>0: stop=trail; stop_kind='trailing'
        if qty and count==len(indices)-1:
            close_part(qty,closing,i,'split_end')
        equity=cash+(side*qty*(closing-entry_fill) if qty else 0.)
        if equity<=0:
            insolvent=True; equity=0.; cash=0.; qty=0.
        rr.append(equity/previous_equity-1 if previous_equity>0 else 0.)
        previous_equity=equity; times.append(int(bars[i,0]))
    returns=np.array(rr)
    m=performance(returns)
    values=np.array([t['net_return'] for t in ledger]); wins=values[values>0]; losses=values[values<0]
    streak=worst=0
    for value in values:
        streak=streak+1 if value<0 else 0; worst=max(worst,streak)
    m.update(trades=len(values),win_rate=float(np.mean(values>0)) if len(values) else 0.,
        expectancy=float(np.mean(values)) if len(values) else 0.,
        profit_factor=float(wins.sum()/-losses.sum()) if len(losses) else None,
        avg_winner=float(np.mean(wins)) if len(wins) else 0.,avg_loser=float(np.mean(losses)) if len(losses) else 0.,
        payoff_ratio=float(-np.mean(wins)/np.mean(losses)) if len(wins) and len(losses) else None,
        fees=float(total_fees),slippage=float(total_slip),funding=float(total_funding),turnover=float(turnover),
        longest_losing_streak=worst,insolvent=insolvent,
        simultaneous_signal_conflicts=conflicts,
        tp1_rate=float(np.mean([t['tp1_hit'] for t in ledger])) if ledger else 0.)
    return dict(metrics=m,returns=returns,times=np.array(times,np.int64),trades=ledger)


def removal(result,count):
    """Zero the fixed best trade intervals; no re-entry/opportunity reselection."""
    rr=result['returns'].copy(); times=result['times']
    trades=sorted(result['trades'],key=lambda t:t['net_return'],reverse=True)
    for row in trades[:count]: rr[(times>=row['entry_time'])&(times<=row['exit_time'])]=0.
    retained=trades[count:]
    return dict(performance(rr),expectancy=float(np.mean([t['net_return'] for t in retained])) if retained else 0.,
                trades=len(retained))


def bootstrap(result,seed=773,repetitions=500):
    if not result['trades']: return dict(n=0,expectancy_ci95=[None,None])
    first=int(result['times'][0]//(7*24*HOUR)); last=int(result['times'][-1]//(7*24*HOUR))
    sums=np.zeros(last-first+1); counts=sums.copy()
    for row in result['trades']:
        k=int(row['entry_time']//(7*24*HOUR))-first; sums[k]+=row['net_return']; counts[k]+=1
    rng=np.random.default_rng(seed); means=[]
    for _ in range(repetitions):
        ids=rng.integers(0,len(sums),len(sums)); n=counts[ids].sum()
        if n: means.append(float(sums[ids].sum()/n))
    return dict(n=len(result['trades']),weeks=len(sums),repetitions=repetitions,seed=seed,
                expectancy_ci95=np.quantile(means,[.025,.975]).tolist())
