"""Offline OHLC fills only. No client, network, credentials or execution API."""
import numpy as np
from .data import M5,HOUR
COSTS={'BASE':(0.0005,0.0001),'CONSERVATIVE':(0.00075,0.0003),'STRESS':(0.001,0.0005)}

def exit_levels(entry,side,atr,low6,high6,kind):
    if not np.isfinite(atr) or atr<=0:return None
    if kind=='ATR_2R':risk=1.5*atr;stop=entry-side*risk
    elif kind=='STRUCTURE_2R':
        stop=low6-0.25*atr if side==1 else high6+0.25*atr
        risk=side*(entry-stop)
        if not np.isfinite(risk) or not 0.5*atr<=risk<=4*atr:return None
    else:raise ValueError('UNKNOWN_EXIT')
    if min(stop,entry+side*2*risk)<=0:return None
    return stop,entry+side*2*risk,risk

def simulate(base,funding,data,i,side,kind):
    b,f,dt=data['bars'],data['features'],data['interval']
    entry_time=int(b[i,0]+dt);limit=24 if kind=='ATR_2R' else 48;end=entry_time+limit*dt
    left=int(np.searchsorted(base[:,0],entry_time));right=int(np.searchsorted(base[:,0],end))
    path=base[left:right]
    if len(path)!=limit*dt//M5 or not np.array_equal(path[:,0],np.arange(entry_time,end,M5)):return None,'INCOMPLETE_PATH'
    # Preserve raw funding calc_time (often a few ms after scheduled boundary).
    expected=np.arange((entry_time//(8*HOUR))*8*HOUR,end,8*HOUR,dtype=np.int64)
    expected=expected[expected>=entry_time]
    ids=np.searchsorted(funding[:,0],expected)
    if any(j>=len(funding) or not 0<=funding[j,0]-t<1000 for t,j in zip(expected,ids)):
        return None,'FUNDING_COVERAGE'
    entry=float(path[0,1]);levels=exit_levels(entry,side,f['atr'][i],f['low6'][i],f['high6'][i],kind)
    if levels is None:return None,'INVALID_STOP'
    stop,target,risk=levels
    mae=mfe=0.;ambiguous=False;reason='TIME';exit_price=float(path[-1,4]);exit_at=end
    for j,row in enumerate(path):
        t,o,h,l,c,_,_=row;adverse=min(side*(l-entry),side*(h-entry));favorable=max(side*(l-entry),side*(h-entry))
        gap_stop=side*(o-stop)<=0;hit_stop=(l<=stop if side==1 else h>=stop)
        hit_target=(h>=target if side==1 else l<=target)
        if gap_stop or hit_stop:
            exit_price=float(o if gap_stop else stop);reason='STOP';ambiguous=bool(hit_stop and hit_target)
            mae=min(mae,side*(exit_price-entry))
            # No favorable excursion is credited on a stop candle with unknown ordering.
            exit_at=int(t if gap_stop else t+M5);break
        if hit_target:
            exit_price=float(target);reason='TARGET';mfe=max(mfe,2*risk)
            # Ordering is unknown: retain the adverse bound of this no-stop candle.
            mae=min(mae,adverse)
            exit_at=int(t+M5);break
        mae=min(mae,adverse);mfe=max(mfe,favorable)
    selected=funding[(funding[:,0]>=entry_time)&(funding[:,0]<exit_at)]
    payment=0.;ambiguous_funding=0
    for t,rate in selected:
        k=int(np.searchsorted(base[:,0],t,side='right')-1)
        price=float(base[k,1]);cash=side*float(rate)*price
        # At entry/exit candle ownership is unresolved; debit only, never credit.
        uncertain=(t<entry_time+M5 or t>=exit_at-M5)
        if uncertain:cash=max(0.,cash);ambiguous_funding+=1
        payment+=cash
    gross=side*(exit_price-entry)
    costs={name:dict(net_R=float((gross-payment-(fee+slip)*(entry+exit_price))/risk),
        net_return=float((gross-payment-(fee+slip)*(entry+exit_price))/entry),
        commission_R=float(fee*(entry+exit_price)/risk),slippage_R=float(slip*(entry+exit_price)/risk))
        for name,(fee,slip) in COSTS.items()}
    return dict(signal_time=int(data['available_at'][i]),entry_time=entry_time,entry=entry,
        exit_time=exit_at,exit_price=exit_price,side=side,stop=stop,target=target,risk=risk,reason=reason,
        gross_R=float(gross/risk),gross_return=float(gross/entry),funding_R=float(payment/risk),
        funding_estimate=True,funding_boundary_ambiguities=ambiguous_funding,ambiguous_bar=ambiguous,
        mae_R=float(mae/risk),mfe_R=float(mfe/risk),duration_hours=float((exit_at-entry_time)/HOUR),
        entry_drift_bps=float(side*(entry/b[i,4]-1)*10000),
        first_5m_adverse=bool(side*(path[0,4]-entry)<0),costs=costs),None
